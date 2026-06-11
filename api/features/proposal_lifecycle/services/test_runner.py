"""
robo-proposal-test 스킬 호출 서비스.
UserStory GWT 인수 조건 LLM-as-judge + robo-sync 구조 검증.

검증은 **runner(스트리밍)** 로 실행하여 실행 로그(narration·tool 사용)를 실시간으로
보여준다(작업 분해와 동일 방식). 헤드리스 일회 실행(`run_tests`)은 비스트리밍 폴백.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import AsyncGenerator

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import run_skill_lines, run_skill_once, extract_json

_SKILL_ROOT = "robo-proposals"
_SKILL_NAME = "robo-proposal-test"


def _fetch_acceptance_criteria(proposal_id: str) -> list[dict]:
    """Proposal의 EFFECT 관계에서 UserStory GWT 인수 조건을 조회한다."""
    query = """
    MATCH (p:Proposal {id: $id})-[:EFFECT]->(us:UserStory)
    WHERE us.acceptanceCriteria IS NOT NULL
    RETURN us.id AS storyId,
           COALESCE(us.title, us.name, '') AS storyTitle,
           us.acceptanceCriteria AS criteria
    """
    with get_session() as session:
        result = session.run(query, id=proposal_id)
        return result.data()


def _build_test_prompt(proposal_id: str, stories: list[dict],
                       worktree_path: str | None, tactical_diff: str) -> str:
    scenarios = []
    for s in stories:
        criteria = s.get("criteria") or []
        if isinstance(criteria, str):
            try:
                criteria = json.loads(criteria)
            except Exception:
                criteria = [criteria]
        for c in criteria:
            scenarios.append({
                "storyId": s["storyId"],
                "storyTitle": s["storyTitle"],
                "scenario": c,
            })

    return (
        f"Proposal ID: {proposal_id}\n"
        f"샌드박스 경로: {worktree_path or '(없음)'}\n\n"
        f"검증할 인수 조건(GWT):\n{json.dumps(scenarios, ensure_ascii=False, indent=2)}\n\n"
        f"Tactical Diff (구조 검증용 — Aggregate/Command/Event/VO 의도된 변경):\n"
        f"{tactical_diff or '[]'}\n\n"
        "① 각 GWT 시나리오를 LLM-as-judge로 검증(category: acceptance)하고, "
        "② Tactical Diff의 각 요소가 샌드박스 구현체에 의도대로 반영됐는지 robo-sync 추출기로 "
        "구조 검증(category: structural)한 뒤, 합쳐서 TestRunResult JSON으로 출력하세요."
    )


def _load_proposal_for_test(proposal_id: str) -> dict | None:
    with get_session() as session:
        record = session.run(
            "MATCH (p:Proposal {id: $id}) "
            "RETURN p.sandboxWorktreePath AS path, p.statusHistory AS history, "
            "p.tacticalDiff AS tacticalDiff, p.status AS status",
            id=proposal_id,
        ).single()
    if not record:
        return None
    return {
        "path": record.get("path"),
        "history": record.get("history") or "[]",
        "tacticalDiff": record.get("tacticalDiff") or "[]",
        "status": record.get("status"),
    }


def reset_for_validation(proposal_id: str) -> tuple[int, str] | None:
    """검증 시작 전 상태를 정리한다(재검증이면 PENDING/MERGE_FAILED→TESTING, 결과 비움).
    문제가 있으면 (status_code, detail)을 반환, 정상이면 None."""
    with get_session() as session:
        record = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.status AS status, p.statusHistory AS hist",
            id=proposal_id,
        ).single()
    if not record:
        return (404, f"Proposal {proposal_id} not found")

    status = record["status"]
    if status not in ("TESTING", "PENDING_ACCEPTANCE", "MERGE_FAILED"):
        return (400, f"검증은 구현 완료(TESTING) 이후 가능합니다 (current: {status})")

    from api.features.proposal_lifecycle.proposal_contracts import append_status_history
    with get_session() as session:
        if status != "TESTING":
            new_hist = append_status_history(record.get("hist") or "[]", status, "TESTING", "system", "재검증")
            session.run(
                "MATCH (p:Proposal {id: $id}) SET p.status = 'TESTING', p.testResults = null, p.statusHistory = $h",
                id=proposal_id, h=new_hist,
            )
        else:
            session.run("MATCH (p:Proposal {id: $id}) SET p.testResults = null", id=proposal_id)
    return None


async def stream_validation(proposal_id: str) -> AsyncGenerator[tuple[str, dict], None]:
    """검증을 runner(스트리밍)로 실행하며 실행 로그를 yield한다:
    phase → log_line(narration/tool) → results → done. (작업 분해와 동일 포맷)

    클라이언트가 SSE를 닫으면(중지) run_skill_lines가 취소되며 서브프로세스를 kill한다.
    상태는 TESTING으로 남아 재검증 가능.
    """
    yield "phase", {"phase": "validation", "message": "검증 실행 중..."}

    err = reset_for_validation(proposal_id)
    if err:
        yield "error", {"code": "INVALID_STATE", "message": err[1]}
        return

    info = _load_proposal_for_test(proposal_id)
    if info is None:
        yield "error", {"code": "NOT_FOUND", "message": f"Proposal {proposal_id} not found"}
        return

    worktree_path = info["path"]
    tactical_diff = info["tacticalDiff"]
    stories = _fetch_acceptance_criteria(proposal_id)

    # GWT 인수 조건도, 구조 검증 대상(Tactical Diff)도 없으면 PENDING_ACCEPTANCE 직행.
    has_tactical = bool(tactical_diff and tactical_diff.strip() not in ("", "[]", "{}"))
    if not stories and not has_tactical:
        result = _empty_result(proposal_id)
        _save_results(proposal_id, result, info["history"])
        yield "log_line", {"text": "검증할 인수 조건/구조 변경이 없어 바로 통과 처리합니다."}
        yield "results", result
        yield "done", {"proposalId": proposal_id, "status": "PENDING_ACCEPTANCE"}
        return

    yield "log_line", {"text": f"인수 조건 {len(stories)}건 + 구조 검증 대상 로드. robo-sync 추출기로 대조합니다…"}

    human_prompt = _build_test_prompt(proposal_id, stories, worktree_path, tactical_diff)

    output_lines: list[str] = []
    suppress_log = False
    # 구조 검증(robo-sync 추출기)을 위해 샌드박스 worktree를 작업 경로로 전달한다.
    async for line in run_skill_lines(
        _SKILL_ROOT, _SKILL_NAME, human_prompt,
        add_dirs=[worktree_path] if worktree_path else None,
        cwd=worktree_path or None,
    ):
        if line.startswith("TOOL:"):
            parts = line[5:].split(":", 1)
            yield "log_line", {"text": f"[tool] {parts[0].strip()} {parts[1].strip() if len(parts) > 1 else ''}"}
            continue
        output_lines.append(line)
        stripped = line.strip()
        if stripped.startswith("```") or (not suppress_log and stripped in ("{", "[")):
            suppress_log = True
            continue
        if not suppress_log:
            yield "log_line", {"text": line}

    raw = "\n".join(output_lines)
    if not raw.strip():
        result = _empty_result(proposal_id)
    else:
        data = extract_json(raw)
        result = data if (data and isinstance(data, dict)) else _empty_result(proposal_id)
        result["proposalId"] = proposal_id

    _save_results(proposal_id, result, info["history"])
    SmartLogger.log("INFO", f"Validation done (stream): {proposal_id}",
                    category="proposal_lifecycle.test.done",
                    params={"proposalId": proposal_id,
                            "passed": result.get("passed", 0),
                            "failed": result.get("failed", 0)})

    yield "results", result
    yield "done", {"proposalId": proposal_id, "status": "PENDING_ACCEPTANCE"}


async def run_tests(proposal_id: str) -> None:
    """비스트리밍 폴백 — 헤드리스 일회 실행 후 결과를 저장하고 상태 전환.
    (UI는 stream_validation을 사용한다.)"""
    SmartLogger.log("INFO", f"Test run start: {proposal_id}",
                    category="proposal_lifecycle.test.start",
                    params={"proposalId": proposal_id})

    info = _load_proposal_for_test(proposal_id)
    if info is None:
        return

    worktree_path = info["path"]
    tactical_diff = info["tacticalDiff"]
    stories = _fetch_acceptance_criteria(proposal_id)

    has_tactical = bool(tactical_diff and tactical_diff.strip() not in ("", "[]", "{}"))
    if not stories and not has_tactical:
        _save_results(proposal_id, _empty_result(proposal_id), info["history"])
        return

    human_prompt = _build_test_prompt(proposal_id, stories, worktree_path, tactical_diff)
    raw = await run_skill_once(
        _SKILL_ROOT, _SKILL_NAME, human_prompt, timeout=180,
        add_dirs=[worktree_path] if worktree_path else None,
    )

    if not raw:
        test_result = _empty_result(proposal_id)
    else:
        data = extract_json(raw)
        test_result = data if (data and isinstance(data, dict)) else _empty_result(proposal_id)
        test_result["proposalId"] = proposal_id

    _save_results(proposal_id, test_result, info["history"])
    SmartLogger.log("INFO", f"Test run done: {proposal_id}",
                    category="proposal_lifecycle.test.done",
                    params={"proposalId": proposal_id,
                            "passed": test_result.get("passed", 0),
                            "failed": test_result.get("failed", 0)})


def _empty_result(proposal_id: str) -> dict:
    return {
        "proposalId": proposal_id,
        "totalScenarios": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "items": [],
    }


def _save_results(proposal_id: str, test_result: dict, history_json: str) -> None:
    from api.features.proposal_lifecycle.proposal_contracts import append_status_history
    new_history = append_status_history(history_json, "TESTING", "PENDING_ACCEPTANCE", "system")

    with get_session() as session:
        session.run(
            """
            MATCH (p:Proposal {id: $id})
            SET p.testResults = $testResults,
                p.status = 'PENDING_ACCEPTANCE',
                p.statusHistory = $history
            """,
            id=proposal_id,
            testResults=json.dumps(test_result, ensure_ascii=False),
            history=new_history,
        )
