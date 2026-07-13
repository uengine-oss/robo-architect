"""
Dual Merge 보상 트랜잭션 서비스.
1. git merge (코드 머지)
2. Neo4j TX (Strategic + Tactical Diff 반영, 상태 ACCEPTED)
실패 시 각각 롤백.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from api.features.proposal_lifecycle.services.sandbox_manager import SandboxManager
from api.features.proposal_lifecycle.services.proposal_apply import (
    apply_strategic_diff,
    apply_tactical_diff,
    apply_journeys,
    revoke_accepted_proposal,
)
from api.features.proposal_lifecycle.proposal_contracts import append_status_history
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

_sandbox = SandboxManager()


class DualMergeFailed(RuntimeError):
    def __init__(self, step: str, detail: str):
        super().__init__(f"DualMerge failed at {step}: {detail}")
        self.step = step
        self.detail = detail


def execute_dual_merge_sync(proposal_id: str, actor: str, comment: str | None = None) -> dict:
    """
    Dual Merge 실행(동기 본체). plan.md 구현 순서:
    1. Git merge → 실패 시 MERGE_FAILED
    2. Neo4j TX (apply_strategic + apply_tactical + ACCEPTED) → 실패 시 git reset + MERGE_FAILED
    3. Cleanup worktree

    반환: 라이브 반영 결과 요약({"strategic": n, "tactical": n, "journeys": n, "liveCounts": {...}}).
    MCP `proposal_accept` 와 HTTP accept 라우트가 공용으로 쓰는 단일 경로(SSOT).
    """
    SmartLogger.log("INFO", f"merge_start: {proposal_id}",
                    category="proposal_lifecycle.merge.start",
                    params={"proposalId": proposal_id, "actor": actor})

    # 대상 프로젝트(projectRoot) — git merge/reset/cleanup은 모두 여기서 실행된다.
    project_root = _get_project_root(proposal_id)
    if not project_root:
        _set_merge_failed(proposal_id, actor, "projectRoot가 없습니다 (구현이 시작되지 않았거나 메타데이터 손실)")
        raise DualMergeFailed("git_merge", "projectRoot 없음")

    # Step 1: Git merge
    merge_result = _sandbox.merge_to_main(proposal_id, project_root)
    if not merge_result.success:
        _set_merge_failed(proposal_id, actor, merge_result.error or "git merge 실패")
        raise DualMergeFailed("git_merge", merge_result.error or "git merge 실패")

    # Step 2: Neo4j TX
    try:
        applied = _apply_diffs_and_accept(proposal_id, actor, comment)
    except Exception as e:
        _sandbox.reset_merge(proposal_id, project_root)
        _set_merge_failed(proposal_id, actor, str(e))
        raise DualMergeFailed("graph_update", str(e))

    # Step 3: Cleanup
    try:
        _sandbox.cleanup_worktree(proposal_id, project_root)
    except Exception as e:
        SmartLogger.log("WARN", f"Worktree cleanup failed post-merge {proposal_id}: {e}",
                        category="proposal_lifecycle.merge.cleanup_warn",
                        params={"proposalId": proposal_id})

    # Spec docs 자동 갱신
    try:
        _update_spec_docs(proposal_id)
    except Exception as e:
        SmartLogger.log("WARN", f"Spec docs update failed {proposal_id}: {e}",
                        category="proposal_lifecycle.merge.spec_update_warn",
                        params={"proposalId": proposal_id})

    SmartLogger.log("INFO", f"merge_done: {proposal_id}",
                    category="proposal_lifecycle.merge.done",
                    params={"proposalId": proposal_id, **applied})
    return applied


async def execute_dual_merge(proposal_id: str, actor: str, comment: str | None = None) -> None:
    execute_dual_merge_sync(proposal_id, actor, comment)


def _get_project_root(proposal_id: str) -> str | None:
    with get_session() as session:
        record = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.projectRoot AS root",
            id=proposal_id,
        ).single()
    return record.get("root") if record else None


def _apply_diffs_and_accept(proposal_id: str, actor: str, comment: str | None) -> dict:
    """Neo4j TX: Strategic + Tactical Diff 반영 + ACCEPTED 상태 전환. 반환: 반영 요약."""
    with get_session() as session:
        result = session.run(
            """
            MATCH (p:Proposal {id: $id})
            RETURN p.strategicDiff AS sd, p.tacticalDiff AS td, p.journeys AS jny,
                   p.statusHistory AS history, p.status AS status
            """,
            id=proposal_id,
        )
        record = result.single()

    if not record:
        raise RuntimeError(f"Proposal {proposal_id} not found during dual merge")

    strategic_raw = record.get("sd") or "{}"
    tactical_raw = record.get("td") or "[]"
    journeys_raw = record.get("jny") or "[]"
    history_raw = record.get("history") or "[]"
    # Accept는 PENDING_ACCEPTANCE(검증 완료) 또는 TESTING(검증 생략)에서 진입 가능.
    from_status = record.get("status") or "PENDING_ACCEPTANCE"

    try:
        strategic_diff = json.loads(strategic_raw) if isinstance(strategic_raw, str) else strategic_raw
    except Exception:
        strategic_diff = {}

    try:
        tactical_diff = json.loads(tactical_raw) if isinstance(tactical_raw, str) else tactical_raw
    except Exception:
        tactical_diff = []

    try:
        journeys = json.loads(journeys_raw) if isinstance(journeys_raw, str) else journeys_raw
    except Exception:
        journeys = []

    now = datetime.now(timezone.utc).isoformat()
    new_history = append_status_history(history_raw, from_status, "ACCEPTED", actor, comment)

    with get_session() as session:
        # tempId(EP-001 등) → 실제 노드 id 매핑을 strategic→tactical에 공유해
        # 계층 관계(HAS_FEATURE/HAS_USER_STORY/IMPLEMENTS/HAS_AGGREGATE…)를 연결한다.
        ref_map: dict = {}

        # Strategic Diff 적용: BoundedContext(Epic)/Feature/UserStory/Process(+제네릭) 생성·수정 + EFFECT
        s_count = apply_strategic_diff(session, proposal_id, strategic_diff, ref_map)

        # Tactical Diff 적용: Aggregate/Command/Event/BC/VO 생성·수정 + EFFECT
        t_count = apply_tactical_diff(session, proposal_id, tactical_diff, ref_map)

        # Journey 적용: 화면 흐름(UI 생성 이후이므로 마지막)
        j_count = apply_journeys(session, proposal_id, journeys, ref_map)

        _validate_applied_counts(strategic_diff, tactical_diff, s_count, t_count)
        _validate_live_projection(session, proposal_id, strategic_diff, tactical_diff)
        live_counts = _live_counts(session, proposal_id)

        SmartLogger.log("INFO", f"diffs applied {proposal_id}: strategic={s_count}, tactical={t_count}, journeys={j_count}",
                        category="proposal_lifecycle.merge.diffs_applied",
                        params={"proposalId": proposal_id, "strategic": s_count, "tactical": t_count,
                                "journeys": j_count, "liveCounts": live_counts})

        # Proposal 상태 ACCEPTED 전환
        session.run(
            """
            MATCH (p:Proposal {id: $id})
            SET p.status = 'ACCEPTED',
                p.acceptedAt = datetime($at),
                p.statusHistory = $history,
                p.sandboxStatus = 'DESTROYED'
            """,
            id=proposal_id,
            at=now,
            history=new_history,
        )
    return {"strategic": s_count, "tactical": t_count, "journeys": j_count, "liveCounts": live_counts}


# 라이브 반영 증거로 노출하는 라벨(Accept 응답·로그).
_LIVE_COUNT_LABELS = [
    "BoundedContext", "Feature", "UserStory", "Process",
    "Aggregate", "Command", "Event", "ReadModel", "Policy", "UI",
    "Invariant", "ValueObject", "Enumeration", "Property",
]


def _live_counts(session, proposal_id: str) -> dict:
    """이 Proposal 이 라이브 그래프에 만든 노드 수(라벨별)."""
    counts: dict = {}
    for label in _LIVE_COUNT_LABELS:
        row = session.run(
            f"MATCH (n:{label} {{proposalSource: $pid}}) RETURN count(n) AS c",
            pid=proposal_id,
        ).single()
        value = row["c"] if row else 0
        if value:
            counts[label] = value
    return counts


def _count_items(strategic_diff: dict, key: str) -> int:
    items = strategic_diff.get(key) if isinstance(strategic_diff, dict) else []
    return len(items) if isinstance(items, list) else 0


def _validate_applied_counts(strategic_diff: dict, tactical_diff: list,
                             strategic_count: int, tactical_count: int) -> None:
    expected_strategic = sum(_count_items(strategic_diff, k)
                             for k in ("epics", "boundedContexts", "features", "userStories", "processes"))
    expected_tactical = len(tactical_diff) if isinstance(tactical_diff, list) else 0
    if expected_strategic and strategic_count <= 0:
        raise RuntimeError("Strategic diff produced no live graph changes")
    if expected_tactical and tactical_count <= 0:
        raise RuntimeError("Tactical diff produced no live graph changes")


def _tactical_label_count(tactical_diff: list, label: str) -> int:
    return sum(1 for item in (tactical_diff or [])
               if isinstance(item, dict)
               and (item.get("nodeLabel") or item.get("entityType")) == label)


def _validate_live_projection(session, proposal_id: str, strategic_diff: dict, tactical_diff: list) -> None:
    """Accept 전 live graph에 핵심 노드/관계가 실제로 생겼는지 검증한다.

    015-issue6: '반영했다'고 보고했지만 그래프가 비어 있던 회귀를 막는 하드 게이트.
    diff 에 있던 라벨은 라이브에도 반드시 있어야 한다(전술 전 라벨 커버).
    """
    expected_aggregates = _tactical_label_count(tactical_diff, "Aggregate")

    checks = [
        ("Feature", _count_items(strategic_diff, "features")),
        ("UserStory", _count_items(strategic_diff, "userStories")),
        ("Process", _count_items(strategic_diff, "processes")),
    ]
    checks += [
        (label, _tactical_label_count(tactical_diff, label))
        for label in ("Aggregate", "Command", "Event", "ReadModel", "Policy",
                      "UI", "Invariant", "ValueObject", "Enumeration")
    ]
    for label, expected in checks:
        if expected <= 0:
            continue
        row = session.run(
            f"MATCH (n:{label} {{proposalSource: $pid}}) RETURN count(n) AS c",
            pid=proposal_id,
        ).single()
        actual = row["c"] if row else 0
        if actual <= 0:
            raise RuntimeError(f"{label} live projection is empty after applying diff")

    if expected_aggregates > 0:
        row = session.run(
            """
            MATCH (:BoundedContext {proposalSource: $pid})-[:HAS_AGGREGATE]->(:Aggregate {proposalSource: $pid})
            RETURN count(*) AS c
            """,
            pid=proposal_id,
        ).single()
        if (row["c"] if row else 0) <= 0:
            raise RuntimeError("Aggregate live projection is not linked to BoundedContext")


async def execute_revoke(proposal_id: str, actor: str, revert_code: bool, comment: str | None = None) -> dict:
    """
    Accept된 Proposal 수거(revoke).
    1. Neo4j 그래프 역방향 복원 (생성 노드 삭제, MODIFY ops 역적용, EFFECT 제거)
    2. revert_code=True면 Accept 머지 커밋을 git revert
    3. 상태 ACCEPTED → PENDING_ACCEPTANCE (재accept 가능)
    """
    SmartLogger.log("INFO", f"revoke_start: {proposal_id}",
                    category="proposal_lifecycle.revoke.start",
                    params={"proposalId": proposal_id, "actor": actor, "revertCode": revert_code})

    # Step 1: 그래프 복원
    with get_session() as session:
        result = revoke_accepted_proposal(session, proposal_id)

    # Step 2: 코드 revert (선택)
    code_result = None
    if revert_code:
        project_root = _get_project_root(proposal_id)
        if project_root:
            mr = _sandbox.revert_merge_commit(proposal_id, project_root)
            code_result = {"success": mr.success, "error": mr.error}
            if not mr.success:
                SmartLogger.log("WARN", f"revoke git revert failed {proposal_id}: {mr.error}",
                                category="proposal_lifecycle.revoke.git_warn",
                                params={"proposalId": proposal_id})
        else:
            code_result = {"success": False, "error": "projectRoot 없음"}

    # Step 3: 상태 전환
    with get_session() as session:
        rec = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.statusHistory AS history", id=proposal_id
        ).single()
        history = (rec.get("history") if rec else None) or "[]"
        new_history = append_status_history(history, "ACCEPTED", "PENDING_ACCEPTANCE", actor,
                                            comment or "수거(revoke)")
        session.run(
            """
            MATCH (p:Proposal {id: $id})
            SET p.status = 'PENDING_ACCEPTANCE',
                p.statusHistory = $history
            REMOVE p.acceptedAt
            """,
            id=proposal_id, history=new_history,
        )

    SmartLogger.log("INFO", f"revoke_done: {proposal_id}",
                    category="proposal_lifecycle.revoke.done",
                    params={"proposalId": proposal_id, **result})
    return {**result, "codeRevert": code_result}


def _set_merge_failed(proposal_id: str, actor: str, detail: str) -> None:
    with get_session() as session:
        result = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.statusHistory AS history",
            id=proposal_id,
        )
        record = result.single()
        history = record.get("history") or "[]" if record else "[]"

    new_history = append_status_history(history, "PENDING_ACCEPTANCE", "MERGE_FAILED", actor, detail)

    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id: $id}) SET p.status = 'MERGE_FAILED', p.statusHistory = $history",
            id=proposal_id,
            history=new_history,
        )


def _update_spec_docs(proposal_id: str) -> None:
    """Accept 후 specs/ 디렉토리 마크다운 문서 자동 갱신 (v1: 간단한 이력 추가)."""
    from pathlib import Path
    specs_dir = Path(__file__).parents[4] / "specs"
    changelog_file = specs_dir / "proposal-changes.md"

    now = datetime.now(timezone.utc).isoformat()
    entry = f"\n## {proposal_id} — Accepted at {now}\n"

    with open(changelog_file, "a", encoding="utf-8") as f:
        f.write(entry)
