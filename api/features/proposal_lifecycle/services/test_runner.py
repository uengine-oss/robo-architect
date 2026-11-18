"""
robo-proposal-test 스킬 호출 서비스.
UserStory GWT 인수 조건 LLM-as-judge + robo-sync 구조 검증.

검증은 **runner(스트리밍)** 로 실행하여 실행 로그(narration·tool 사용)를 실시간으로
보여준다(작업 분해와 동일 방식). 헤드리스 일회 실행(`run_tests`)은 비스트리밍 폴백.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import run_skill_lines, run_skill_once, extract_json

_SKILL_ROOT = "robo-proposals"
_SKILL_NAME = "robo-proposal-test"
_EXTRACTOR_ROOT = (Path(__file__).parents[4] / "skills" / "robo-spec" / "robo-sync" / "extractors").resolve()


def _json_value(raw, fallback):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return fallback
    return raw if raw is not None else fallback


def _criteria_from_tactical_diff(raw) -> list[dict]:
    """Use the Proposal-owned Command GWT as the pre-Accept source of truth."""
    tactical = _json_value(raw, [])
    if not isinstance(tactical, list):
        return []
    stories = []
    for item in tactical:
        if not isinstance(item, dict) or item.get("nodeLabel") != "Command":
            continue
        criteria = item.get("gwt")
        if not isinstance(criteria, list) or not criteria:
            continue
        stories.append({
            "storyId": item.get("nodeId") or item.get("tempId") or item.get("nodeTitle"),
            "storyTitle": item.get("nodeTitle") or item.get("entityTitle") or "",
            "criteria": criteria,
        })
    return stories


def _criteria_from_strategic_diff(raw) -> list[dict]:
    strategic = _json_value(raw, {})
    if not isinstance(strategic, dict):
        return []
    stories = []
    for item in strategic.get("userStories") or []:
        if not isinstance(item, dict):
            continue
        criteria = item.get("acceptanceCriteria")
        if not isinstance(criteria, list) or not criteria:
            continue
        stories.append({
            "storyId": item.get("tempId") or item.get("entityId") or item.get("entityTitle"),
            "storyTitle": item.get("entityTitle") or "",
            "criteria": criteria,
        })
    return stories


def _fetch_acceptance_criteria(proposal_id: str) -> list[dict]:
    """Load acceptance criteria deterministically before the Proposal is accepted.

    Detailed/Simplified proposals own their pending Command GWT in tacticalDiff.
    EFFECT relationships may not exist until graph application, so they are only a
    fallback, followed by Strategic UserStory criteria for non-tactical changes.
    """
    with get_session() as session:
        proposal = session.run(
            "MATCH (p:Proposal {id: $id}) "
            "RETURN p.tacticalDiff AS tacticalDiff, p.strategicDiff AS strategicDiff",
            id=proposal_id,
        ).single()
        if not proposal:
            return []

        tactical = _criteria_from_tactical_diff(proposal.get("tacticalDiff"))
        if tactical:
            return tactical

        graph = session.run(
            "MATCH (p:Proposal {id: $id})-[:EFFECT]->(us:UserStory) "
            "WHERE us.acceptanceCriteria IS NOT NULL "
            "RETURN us.id AS storyId, COALESCE(us.title, us.name, '') AS storyTitle, "
            "us.acceptanceCriteria AS criteria",
            id=proposal_id,
        ).data()
        if graph:
            return graph
        return _criteria_from_strategic_diff(proposal.get("strategicDiff"))


def _acceptance_scenario_count(stories: list[dict]) -> int:
    total = 0
    for story in stories:
        criteria = _json_value(story.get("criteria"), [])
        total += len(criteria) if isinstance(criteria, list) else 1
    return total


# ── D-2 ⑭ 부분 재검증 ─────────────────────────────────────────────────────
# 통과 못 한 항목 하나를 고친 뒤 **그 항목만** 다시 잰다. 전체 재실행은 LLM 비용이 들고
# 이미 통과한 항목의 판정까지 흔든다(LLM-as-judge 는 결정적이지 않다).
# 결과는 기존 testResults 에 **병합**한다 — 고른 항목만 바꾸고 나머지는 그대로 둔다.

def parse_scenario_ids(raw) -> list[str]:
    """`?scenarioIds=SC-003,SC-007`(쉼표) 또는 반복 쿼리 목록을 정리한다(순서 유지·중복 제거)."""
    if raw is None:
        return []
    parts = raw if isinstance(raw, (list, tuple)) else [raw]
    out: list[str] = []
    for part in parts:
        for tok in str(part or "").split(","):
            tok = tok.strip()
            if tok and tok not in out:
                out.append(tok)
    return out


def _is_pass(result) -> bool:
    return str(result or "").upper() == "PASS"


def stamp_attempts(result: dict) -> dict:
    """전체 검증 결과의 각 항목에 시도 이력(③)을 처음 찍는다 — attempts=1.
    lastReason 은 **가장 최근에 통과하지 못한 사유**다(통과하면 직전 실패 사유를 남긴다)."""
    for it in result.get("items") or []:
        if not isinstance(it, dict):
            continue
        it.setdefault("attempts", 1)
        if "lastReason" not in it:
            it["lastReason"] = None if _is_pass(it.get("result")) else it.get("reason")
    return result


def recount(result: dict) -> dict:
    """요약 총계를 items 로부터 다시 센다(병합 뒤 총계가 어긋나지 않게)."""
    items = [it for it in (result.get("items") or []) if isinstance(it, dict)]
    counts: dict[str, int] = {}
    for it in items:
        r = str(it.get("result") or "").upper()
        counts[r] = counts.get(r, 0) + 1
    result["totalScenarios"] = len(items)
    result["passed"] = counts.get("PASS", 0)
    result["failed"] = counts.get("FAIL", 0)
    result["skipped"] = counts.get("SKIP", 0) + counts.get("SKIPPED", 0)
    return result


def select_partial_targets(existing: dict | None, scenario_ids: list[str]) -> tuple[list[dict], list[str]]:
    """기존 결과에서 재검증할 항목을 고른다. (찾은 항목, 없는 id) 를 돌려준다."""
    items = [it for it in ((existing or {}).get("items") or []) if isinstance(it, dict)]
    by_id = {str(it.get("scenarioId")): it for it in items}
    found = [by_id[sid] for sid in scenario_ids if sid in by_id]
    missing = [sid for sid in scenario_ids if sid not in by_id]
    return found, missing


def merge_partial_results(existing: dict, fresh: dict | None, scenario_ids: list[str]) -> dict:
    """부분 재검증 결과를 기존 결과에 병합한다 — **고른 항목만 바꾸고 나머지는 그대로**.

    - 새 결과에서 같은 scenarioId 를 찾아 판정·사유를 바꾼다(attempts +1).
      한 건만 재검증했는데 새 결과도 한 건이면 id 가 달라도 그 건으로 본다.
    - 새 결과에 그 항목이 없으면 **이전 판정을 유지**한다(FAIL 이 SKIP 으로 바뀌어
      Accept 게이트를 조용히 통과하는 일을 막는다). attempts 는 올리고 lastReason 에 적는다.
    - 고르지 않은 항목은 건드리지 않는다. 새 결과에 섞여 온 다른 항목도 버린다.
    """
    import copy

    merged = copy.deepcopy(existing or {})
    items = [it for it in (merged.get("items") or []) if isinstance(it, dict)]
    fresh_items = [it for it in ((fresh or {}).get("items") or []) if isinstance(it, dict)]
    fresh_by_id = {str(it.get("scenarioId")): it for it in fresh_items}
    wanted = set(scenario_ids)
    single_fallback = fresh_items[0] if (len(scenario_ids) == 1 and len(fresh_items) == 1) else None

    for it in items:
        sid = str(it.get("scenarioId"))
        if sid not in wanted:
            continue
        prev_attempts = it.get("attempts") or 1
        prev_last = it.get("lastReason")
        if prev_last is None and not _is_pass(it.get("result")):
            prev_last = it.get("reason")
        new = fresh_by_id.get(sid) or single_fallback
        it["attempts"] = int(prev_attempts) + 1
        if new is None:
            it["lastReason"] = "재검증 응답에 이 항목이 없었다 — 이전 판정을 유지한다"
            continue
        it["result"] = new.get("result") or it.get("result")
        it["reason"] = new.get("reason")
        if new.get("scenario"):
            it["scenario"] = new["scenario"]
        it["lastReason"] = prev_last if _is_pass(it["result"]) else new.get("reason")

    merged["items"] = items
    merged["proposalId"] = merged.get("proposalId") or (fresh or {}).get("proposalId")
    return recount(merged)


def _filter_tactical_for_targets(tactical_diff, targets: list[dict]) -> str:
    """구조 항목(storyId=요소 id)만 재검증하도록 Tactical Diff 를 그 요소로 줄인다."""
    structural = [t for t in targets if t.get("category") == "structural"]
    if not structural:
        return "[]"
    ids = {str(t.get("storyId")) for t in structural}
    titles = {str(t.get("storyTitle")) for t in structural}
    tactical = _json_value(tactical_diff, [])
    if not isinstance(tactical, list):
        return "[]"
    kept = [
        item for item in tactical
        if isinstance(item, dict) and (
            str(item.get("nodeId")) in ids or str(item.get("tempId")) in ids
            or str(item.get("nodeTitle")) in titles
        )
    ]
    return json.dumps(kept, ensure_ascii=False)


def _build_partial_prompt(proposal_id: str, targets: list[dict],
                          worktree_path: str | None, tactical_diff) -> str:
    """고른 항목만 다시 재는 프롬프트. scenarioId 는 **주어진 값 그대로** 돌려 달라고 한다."""
    def _row(t: dict, scenario_key: str) -> dict:
        return {
            "scenarioId": t.get("scenarioId"),
            "storyId": t.get("storyId"),
            "storyTitle": t.get("storyTitle"),
            "scenario": t.get(scenario_key) or t.get("scenario"),
            "previousResult": t.get("result"),
            "previousReason": t.get("reason"),
        }

    acceptance = [_row(t, "criterion") for t in targets if t.get("category") != "structural"]
    structural = [_row(t, "scenario") for t in targets if t.get("category") == "structural"]
    return (
        f"Proposal ID: {proposal_id}\n"
        f"샌드박스 경로: {worktree_path or '(없음)'}\n\n"
        f"robo-sync 추출기 경로(EXTRACTOR_ROOT): {_EXTRACTOR_ROOT}\n"
        "지원 추출기: TypeScript(ts_extract.mjs), Python(python_extract.py), "
        "Java(java_extract.py), Avro(avro_extract.py)\n\n"
        "**부분 재검증** — 아래에 적은 항목만 다시 판정하세요. 다른 항목은 만들지 마세요.\n"
        "각 item 의 scenarioId 는 **주어진 값 그대로** 쓰세요(새 번호 금지).\n"
        "previousResult/previousReason 은 직전 판정입니다 — 코드가 고쳐졌는지 다시 확인하세요.\n\n"
        f"재검증할 인수 조건(GWT):\n{json.dumps(acceptance, ensure_ascii=False, indent=2)}\n\n"
        f"재검증할 구조 항목:\n{json.dumps(structural, ensure_ascii=False, indent=2)}\n\n"
        "Tactical Diff (위 구조 항목에 해당하는 요소만):\n"
        f"{_filter_tactical_for_targets(tactical_diff, targets)}\n\n"
        "인수 조건은 LLM-as-judge(category: acceptance), 구조 항목은 robo-sync 추출기"
        "(category: structural)로 판정한 뒤 TestRunResult JSON 으로 출력하세요."
    )


def prepare_partial_validation(proposal_id: str, scenario_ids: list[str]):
    """부분 재검증 전 점검·상태 전환. 결과를 **비우지 않는다**(병합해야 하므로).

    반환: (오류 (status, detail) | None, 기존 결과 dict | None, 대상 항목 목록)
    """
    with get_session() as session:
        record = session.run(
            "MATCH (p:Proposal {id: $id}) "
            "RETURN p.status AS status, p.statusHistory AS hist, p.testResults AS testResults",
            id=proposal_id,
        ).single()
    if not record:
        return (404, f"Proposal {proposal_id} not found"), None, []
    status = record["status"]
    if status not in ("TESTING", "PENDING_ACCEPTANCE", "MERGE_FAILED"):
        return (400, f"검증은 구현 완료(TESTING) 이후 가능합니다 (current: {status})"), None, []
    existing = _json_value(record.get("testResults"), None)
    if not isinstance(existing, dict) or not existing.get("items"):
        return (409, "부분 재검증은 전체 검증 결과가 있어야 합니다 — 먼저 전체 검증을 실행하세요"), None, []
    targets, missing = select_partial_targets(existing, scenario_ids)
    if missing:
        return (400, f"검증 결과에 없는 시나리오: {', '.join(missing)}"), None, []

    if status != "TESTING":
        from api.features.proposal_lifecycle.proposal_contracts import append_status_history
        new_hist = append_status_history(
            record.get("hist") or "[]", status, "TESTING", "system",
            f"부분 재검증: {', '.join(scenario_ids)}",
        )
        with get_session() as session:
            session.run(
                "MATCH (p:Proposal {id: $id}) SET p.status = 'TESTING', p.statusHistory = $h",
                id=proposal_id, h=new_hist,
            )
    return None, existing, targets


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
        f"robo-sync 추출기 경로(EXTRACTOR_ROOT): {_EXTRACTOR_ROOT}\n"
        "지원 추출기: TypeScript(ts_extract.mjs), Python(python_extract.py), "
        "Java(java_extract.py), Avro(avro_extract.py)\n\n"
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


def _finalize_result(proposal_id: str, raw: str | None) -> dict:
    """스킬 출력(raw)에서 TestRunResult dict 를 뽑는다. 못 뽑으면 빈 결과."""
    if not raw or not raw.strip():
        return _empty_result(proposal_id)
    data = extract_json(raw)
    result = data if (data and isinstance(data, dict)) else _empty_result(proposal_id)
    result["proposalId"] = proposal_id
    return result


async def stream_validation(proposal_id: str, scenario_ids: list[str] | None = None
                            ) -> AsyncGenerator[tuple[str, dict], None]:
    """검증을 runner(스트리밍)로 실행하며 실행 로그를 yield한다:
    phase → log_line(narration/tool) → results → done. (작업 분해와 동일 포맷)

    `scenario_ids` 가 있으면 **부분 재검증**이다 — 그 항목만 다시 재고 기존 결과에
    병합한다(`results` 로 나가는 것은 병합된 **전체** 결과다). `done` 에 `scenarioIds` 를 싣는다.

    클라이언트가 SSE를 닫으면(중지) run_skill_lines가 취소되며 서브프로세스를 kill한다.
    상태는 TESTING으로 남아 재검증 가능(부분 재검증이면 기존 결과도 그대로 남는다).
    """
    partial = bool(scenario_ids)
    yield "phase", {"phase": "validation",
                    "message": "부분 재검증 실행 중..." if partial else "검증 실행 중...",
                    "scenarioIds": scenario_ids or []}

    existing: dict | None = None
    targets: list[dict] = []
    if partial:
        err, existing, targets = prepare_partial_validation(proposal_id, scenario_ids)
    else:
        err = reset_for_validation(proposal_id)
    if err:
        yield "error", {"code": "INVALID_STATE", "message": err[1], "status": err[0]}
        return

    info = _load_proposal_for_test(proposal_id)
    if info is None:
        yield "error", {"code": "NOT_FOUND", "message": f"Proposal {proposal_id} not found"}
        return

    worktree_path = info["path"]
    tactical_diff = info["tacticalDiff"]

    if partial:
        yield "log_line", {"text": f"부분 재검증 {len(targets)}건: {', '.join(scenario_ids)} — 나머지 결과는 그대로 둡니다."}
        human_prompt = _build_partial_prompt(proposal_id, targets, worktree_path, tactical_diff)
    else:
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

        yield "log_line", {"text": f"인수 조건 {_acceptance_scenario_count(stories)}건 + 구조 검증 대상 로드. robo-sync 추출기로 대조합니다…"}
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
    fresh = _finalize_result(proposal_id, raw)
    if partial:
        result = merge_partial_results(existing, fresh, scenario_ids)
    else:
        result = stamp_attempts(fresh)

    _save_results(proposal_id, result, info["history"])
    SmartLogger.log("INFO", f"Validation done (stream): {proposal_id}",
                    category="proposal_lifecycle.test.done",
                    params={"proposalId": proposal_id,
                            "partial": partial,
                            "scenarioIds": scenario_ids or [],
                            "passed": result.get("passed", 0),
                            "failed": result.get("failed", 0)})

    yield "results", result
    yield "done", {"proposalId": proposal_id, "status": "PENDING_ACCEPTANCE",
                   "scenarioIds": scenario_ids or []}


async def run_tests(proposal_id: str, scenario_ids: list[str] | None = None,
                    partial_ctx: tuple[dict, list[dict]] | None = None) -> None:
    """비스트리밍 폴백 — 헤드리스 일회 실행 후 결과를 저장하고 상태 전환.
    (UI는 stream_validation을 사용한다.)

    부분 재검증이면 라우트가 `prepare_partial_validation` 으로 얻은 (기존 결과, 대상)을
    `partial_ctx` 로 넘긴다 — 점검·상태 전환은 라우트가 먼저 끝낸다(오류를 HTTP 로 돌려주려고).
    """
    partial = bool(scenario_ids)
    SmartLogger.log("INFO", f"Test run start: {proposal_id}",
                    category="proposal_lifecycle.test.start",
                    params={"proposalId": proposal_id, "scenarioIds": scenario_ids or []})

    info = _load_proposal_for_test(proposal_id)
    if info is None:
        return

    worktree_path = info["path"]
    tactical_diff = info["tacticalDiff"]

    existing: dict | None = None
    if partial:
        existing, targets = partial_ctx or (None, [])
        human_prompt = _build_partial_prompt(proposal_id, targets, worktree_path, tactical_diff)
    else:
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

    fresh = _finalize_result(proposal_id, raw)
    if partial:
        test_result = merge_partial_results(existing, fresh, scenario_ids)
    else:
        test_result = stamp_attempts(fresh)

    _save_results(proposal_id, test_result, info["history"])
    SmartLogger.log("INFO", f"Test run done: {proposal_id}",
                    category="proposal_lifecycle.test.done",
                    params={"proposalId": proposal_id,
                            "partial": partial,
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
