"""작업 분해(robo-proposal-tasks) 결과 파싱 · 저장 · 렌더 단위 테스트 (Neo4j·Claude CLI 불필요).

스킬 출력은 SKILL.md 계약대로 "narration 줄들 + 빈 줄 + JSON" 이다. run_skill_lines 를
줄 목록을 흘리는 가짜로 바꿔 stream_tasks 의 SSE 이벤트·저장·오류 로그를 확인한다.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager

import pytest

from api.features.proposal_lifecycle.services import tasks_runner
from api.features.proposal_lifecycle.services.tasks_progress import parse_tasks_markdown
from api.features.proposal_lifecycle.tests.lifecycle_fakes import (
    FakeResult,
    capture_logs,
    fake_skill_lines,
    forbid_real_backends,
)

PID = "PRO-003"

CTX = {
    "title": "부분 환불",
    "prompt": "주문 금액 일부만 환불할 수 있게 해 주세요",
    "strategicDiff": json.dumps({"userStories": [{"op": "CREATE", "entityTitle": "고객: 부분 환불 요청"}]},
                                ensure_ascii=False),
    "tacticalDiff": json.dumps([{"nodeLabel": "Aggregate", "changeType": "MODIFY", "nodeTitle": "Refund"}]),
    "implementationPlan": "{}",
    "constitution": "# Constitution\n- MONOLITH",
}

TASKS_JSON = {
    "tasks": [
        {"id": "T001", "phase": "Phase 1: Setup", "text": "결제 도메인 디렉터리 구조 생성",
         "files": ["src/payment/"], "parallel": False},
        {"id": "T002", "phase": "Phase 2: Domain", "text": "PartialRefundAmount VO 추가",
         "files": ["src/payment/PartialRefundAmount.ts"], "parallel": True},
        {"id": "T003", "phase": "Phase 3: API", "text": "부분 환불 요청 Command 핸들러 구현",
         "files": ["src/payment/RefundCommand.ts"], "parallel": False},
    ]
}

NARRATION = [
    "[검토] Tactical: 환불 Aggregate에 PartialRefundAmount VO 추가, 부분환불 Command 신규",
    "[검토] Strategic: \"부분 환불 요청\" UserStory 1건 신규",
    "[작업] 결제 도메인 VO 파일 생성 (PartialRefundAmount)",
    "[순서] Setup → Domain(VO) → API(Command/검증)",
    "",
]


def _fenced(obj) -> list[str]:
    return ["```json", *json.dumps(obj, ensure_ascii=False, indent=2).splitlines(), "```"]


class _Session:
    def __init__(self, sink, record=None):
        self.sink, self.record = sink, record

    def run(self, query, **params):
        self.sink.append((" ".join(query.split()), params))
        return FakeResult(self.record)


@pytest.fixture
def env(monkeypatch):
    forbid_real_backends(monkeypatch)
    logs = capture_logs(monkeypatch)
    runs: list = []
    calls: list = []

    @contextmanager
    def fake_session(*_a, **_k):
        yield _Session(runs)

    monkeypatch.setattr(tasks_runner, "get_session", fake_session)
    monkeypatch.setattr(tasks_runner, "_get_context", lambda pid: dict(CTX))

    def use_output(lines=None, raises=None):
        monkeypatch.setattr(tasks_runner, "run_skill_lines", fake_skill_lines(lines, raises, calls))

    use_output([])
    return type("Env", (), {"logs": logs, "runs": runs, "calls": calls, "use_output": staticmethod(use_output),
                            "mp": monkeypatch})


def _stream():
    async def collect():
        return [ev async for ev in tasks_runner.stream_tasks(PID)]
    return asyncio.run(collect())


def _saved(env):
    saves = [p for q, p in env.runs if "SET p.tasksJson = $tasks" in q]
    return [json.loads(p["tasks"]) for p in saves]


# ── 정상 출력 ────────────────────────────────────────────────────────────────

def test_narration_then_fenced_json_yields_tasks_and_saves(env):
    env.use_output(NARRATION + _fenced(TASKS_JSON) + ["", "작업 분해를 마쳤습니다."])
    events = _stream()

    kinds = [k for k, _ in events]
    assert kinds[0] == "phase" and kinds[-2:] == ["tasks", "done"]
    logs = [d["text"] for k, d in events if k == "log_line"]
    assert logs == NARRATION  # JSON 블록(및 그 뒤 꼬리말)은 화면 로그로 흘리지 않는다
    tasks = dict(events)["tasks"]
    assert tasks["count"] == 3
    assert [t["id"] for t in tasks["tasks"]] == ["T001", "T002", "T003"]
    assert tasks["tasks"][1] == {"id": "T002", "phase": "Phase 2: Domain", "text": "PartialRefundAmount VO 추가",
                                 "files": ["src/payment/PartialRefundAmount.ts"], "parallel": True}
    assert dict(events)["done"] == {"proposalId": PID, "count": 3}
    assert _saved(env) == [tasks["tasks"]]
    assert env.runs[0][1]["id"] == PID
    assert env.calls[0]["name"] == "robo-proposal-tasks"
    assert any(entry["category"] == "proposal_lifecycle.tasks.done" for entry in env.logs)


def test_tool_lines_become_tool_log_and_are_not_parsed(env):
    env.use_output(["TOOL:Read:/work/shop/src/payment/Refund.ts", "TOOL:Grep"] + _fenced(TASKS_JSON))
    events = _stream()
    logs = [d["text"] for k, d in events if k == "log_line"]
    assert logs == ["[tool] Read /work/shop/src/payment/Refund.ts", "[tool] Grep "]
    assert dict(events)["tasks"]["count"] == 3


def test_bare_json_without_fence_is_parsed_and_hidden_from_log(env):
    env.use_output(NARRATION + json.dumps(TASKS_JSON, ensure_ascii=False, indent=2).splitlines())
    events = _stream()
    assert [d["text"] for k, d in events if k == "log_line"] == NARRATION
    assert dict(events)["tasks"]["count"] == 3


def test_top_level_task_array_is_accepted(env):
    env.use_output(_fenced(TASKS_JSON["tasks"]))
    events = _stream()
    assert dict(events)["tasks"]["count"] == 3


def test_tasks_are_normalized(env):
    raw = {"tasks": [
        {"text": "  ID 없는 작업  "},                                   # → T001, phase 기본값
        "문자열 항목은 버린다",
        {"id": "T010", "phase": " Phase 2: Domain ", "text": "VO 추가",
         "files": ["src/a.ts", 3, None], "parallel": "yes"},
        {"id": "T011", "text": "   "},                                 # 빈 텍스트는 버린다
        {"text": "네 번째 위치의 작업"},                                   # 원래 인덱스 기준 → T005
    ]}
    env.use_output(_fenced(raw))
    tasks = dict(_stream())["tasks"]["tasks"]
    assert tasks == [
        {"id": "T001", "phase": "Tasks", "text": "ID 없는 작업", "files": [], "parallel": False},
        {"id": "T010", "phase": "Phase 2: Domain", "text": "VO 추가", "files": ["src/a.ts"], "parallel": True},
        {"id": "T005", "phase": "Tasks", "text": "네 번째 위치의 작업", "files": [], "parallel": False},
    ]


# ── 실패·오류 ────────────────────────────────────────────────────────────────

def test_unknown_proposal_is_not_found_without_running_skill(env):
    env.mp.setattr(tasks_runner, "_get_context", lambda pid: None)
    events = _stream()
    assert events[-1] == ("error", {"code": "NOT_FOUND", "message": f"Proposal {PID} not found"})
    assert env.calls == []


@pytest.mark.parametrize("sd, td", [("{}", "[]"), (None, None), ("", "")])
def test_no_diff_is_rejected_before_running_skill(env, sd, td):
    env.mp.setattr(tasks_runner, "_get_context", lambda pid: {**CTX, "strategicDiff": sd, "tacticalDiff": td})
    events = _stream()
    assert events[-1][0] == "error" and events[-1][1]["code"] == "NO_DIFF"
    assert env.calls == []


def test_skill_process_error_is_reported(env):
    env.use_output(["[검토] 시작", "PHASE:error"])
    events = _stream()
    assert events[-1][0] == "error" and events[-1][1]["code"] == "TASKS_FAILED"
    assert "Claude 실행 오류" in events[-1][1]["message"]
    assert _saved(env) == []


def test_empty_output_is_tasks_failed(env):
    env.use_output(["", "   "])
    events = _stream()
    assert events[-1] == ("error", {"code": "TASKS_FAILED", "message": "작업 분해 실패"})


@pytest.mark.parametrize("name, lines, parsed_type", [
    ("truncated_json", NARRATION + ["```json", '{"tasks": [', '  {"id": "T001", "phase": "Phase 1: Setup",',
                                     '   "text": "디렉터리 생성"'], "NoneType"),
    ("markdown_checklist_instead_of_json", NARRATION + [
        "## Phase 1: Setup", "- [ ] T001 결제 도메인 디렉터리 구조 생성",
        "## Phase 2: Domain", "- [ ] T002 [P] PartialRefundAmount VO 추가"], "NoneType"),
    ("json_without_tasks_key", NARRATION + _fenced({"summary": "작업 3개", "phases": ["Setup"]}), "dict"),
    ("tasks_all_blank", _fenced({"tasks": [{"id": "T001", "text": ""}, {"id": "T002"}]}), "dict"),
])
def test_unparseable_output_logs_error_with_raw_excerpt(env, name, lines, parsed_type):
    env.use_output(lines)
    events = _stream()
    assert events[-1] == ("error", {"code": "TASKS_PARSE_FAILED", "message": "작업 분해 결과 파싱 실패"})
    assert _saved(env) == []
    [err] = [entry for entry in env.logs if entry["level"] == "ERROR"]
    assert err["category"] == "proposal_lifecycle.tasks.parse_failed"
    raw = "\n".join(lines)
    assert err["params"]["proposalId"] == PID
    assert err["params"]["rawChars"] == len(raw)
    assert err["params"]["parsedType"] == parsed_type
    assert err["params"]["rawHead"] == raw[:1500] and err["params"]["rawTail"] == raw[-1500:]


def test_parse_failure_log_truncates_long_output(env):
    lines = [f"[작업] 아주 긴 서술 {i:04d} " + "가" * 40 for i in range(200)]
    env.use_output(lines)
    _stream()
    [err] = [entry for entry in env.logs if entry["level"] == "ERROR"]
    raw = "\n".join(lines)
    assert len(err["params"]["rawHead"]) == 1500 and len(err["params"]["rawTail"]) == 1500
    assert err["params"]["rawHead"] == raw[:1500] and err["params"]["rawTail"] == raw[-1500:]


@pytest.mark.xfail(strict=True, reason=(
    "BUG(견고성): stream_tasks 는 extract_json(가장 큰 JSON 하나)만 쓴다 (tasks_runner.py stream_tasks). "
    "모델이 narration 에서 입력 Diff 를 JSON 으로 인용하는 등 tasks 보다 큰 블록이 있으면 그 블록이 선택돼 "
    "TASKS_PARSE_FAILED 가 난다. plan_runner 는 같은 문제로 extract_json_candidates 에서 필요한 키를 고른다."))
def test_tasks_block_is_found_even_when_a_larger_json_is_quoted(env):
    quoted_diff = {"tacticalDiff": [{"nodeLabel": "Aggregate", "nodeTitle": f"Refund{i}",
                                     "changeType": "MODIFY", "reason": "부분 환불 금액 검증 추가"} for i in range(8)]}
    env.use_output(["[검토] 입력 Diff 는 다음과 같다:"] + _fenced(quoted_diff) + [""] + _fenced(TASKS_JSON))
    events = _stream()
    assert events[-1][0] == "done", events[-1]


# ── 프롬프트 · 컨텍스트 ───────────────────────────────────────────────────────

def test_prompt_carries_diffs_constitution_and_plan():
    prompt = tasks_runner._build_tasks_prompt(PID, {**CTX, "implementationPlan": '{"architectureDecisions": []}'})
    assert f"Proposal ID: {PID}" in prompt
    assert CTX["strategicDiff"] in prompt and CTX["tacticalDiff"] in prompt
    assert "# Constitution" in prompt and '"architectureDecisions"' in prompt
    no_con = tasks_runner._build_tasks_prompt(PID, {**CTX, "constitution": None})
    assert "(Constitution 없음)" in no_con


def test_get_context_reads_proposal_and_constitution(monkeypatch):
    forbid_real_backends(monkeypatch)
    runs: list = []
    record = {"title": "부분 환불", "prompt": None, "strategicDiff": None, "tacticalDiff": "[1]",
              "implementationPlan": None, "projectRoot": "/work/shop"}

    @contextmanager
    def fake_session(*_a, **_k):
        yield _Session(runs, record)

    from api.features.proposal_lifecycle.services import constitution_runner
    roots: list = []
    monkeypatch.setattr(tasks_runner, "get_session", fake_session)
    monkeypatch.setattr(constitution_runner, "read_constitution", lambda root: roots.append(root) or "# C")
    ctx = tasks_runner._get_context(PID)
    assert ctx == {"title": "부분 환불", "prompt": "", "strategicDiff": "{}", "tacticalDiff": "[1]",
                   "implementationPlan": "{}", "constitution": "# C"}
    assert roots == ["/work/shop"]


# ── 렌더 · 재조회 ─────────────────────────────────────────────────────────────

def test_render_tasks_markdown_groups_by_phase():
    md = tasks_runner.render_tasks_markdown(PID, "부분 환불", TASKS_JSON["tasks"])
    lines = md.splitlines()
    assert lines[0] == f"# Tasks: 부분 환불 ({PID})"
    assert "## Phase 1: Setup" in lines and "## Phase 2: Domain" in lines and "## Phase 3: API" in lines
    assert "- [ ] T001 결제 도메인 디렉터리 구조 생성 (src/payment/)" in lines
    assert "- [ ] T002 [P] PartialRefundAmount VO 추가 (src/payment/PartialRefundAmount.ts)" in lines
    assert lines.index("## Phase 1: Setup") < lines.index("- [ ] T001 결제 도메인 디렉터리 구조 생성 (src/payment/)") \
        < lines.index("## Phase 2: Domain")


def test_rendered_markdown_round_trips_through_progress_parser():
    tasks = TASKS_JSON["tasks"] + [{"id": "T004", "phase": "Phase 3: API", "text": "검증 규칙 추가",
                                    "files": [], "parallel": False}]
    progress = parse_tasks_markdown(tasks_runner.render_tasks_markdown(PID, None, tasks))
    assert progress["total"] == 4 and progress["done"] == 0
    assert [(s["title"], s["total"]) for s in progress["sections"]] == [
        ("Phase 1: Setup", 1), ("Phase 2: Domain", 1), ("Phase 3: API", 2)]


@pytest.mark.parametrize("record, exists", [
    (None, False),
    ({"title": "x", "tasksJson": None}, False),
    ({"title": "x", "tasksJson": "not json"}, False),
    ({"title": "x", "tasksJson": "[]"}, False),
    ({"title": "x", "tasksJson": json.dumps(TASKS_JSON["tasks"], ensure_ascii=False)}, True),
])
def test_load_tasks(monkeypatch, record, exists):
    forbid_real_backends(monkeypatch)

    @contextmanager
    def fake_session(*_a, **_k):
        yield _Session([], record)

    monkeypatch.setattr(tasks_runner, "get_session", fake_session)
    out = tasks_runner.load_tasks(PID)
    assert out["exists"] is exists
    if exists:
        assert len(out["tasks"]) == 3 and "## Phase 1: Setup" in out["markdown"]
    else:
        assert out == {"exists": False, "tasks": [], "markdown": ""}
