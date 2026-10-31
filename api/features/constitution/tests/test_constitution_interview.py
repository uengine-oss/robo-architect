"""041 — 프로젝트 헌장 인터뷰(결정적 게이팅 질문) 단위 테스트 (Neo4j·Claude CLI 불필요).

질문 순서·선택은 백엔드가 답변 상태만 보고 결정한다. 그래프 BC 조회(load_domain_nodes),
제안 조회(get_session), 스킬 실행(run_skill_lines), 헌장 저장(store)은 모두 대역으로 바꾼다.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager

import pytest

import api.platform.neo4j as neo4j_mod
import api.platform.neo4j_helpers as neo4j_helpers
from api.features.constitution import router as constitution_router
from api.features.constitution.services import constitution_interview as iv
from api.features.proposal_lifecycle.tests.lifecycle_fakes import (
    FakeResult,
    capture_logs,
    fake_skill_lines,
    forbid_real_backends,
)

MICRO_FULL = ["architectureStyle", "techStack", "repoStrategy", "repoMode", "deploymentTarget", "messaging"]


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """모듈 전역 인터뷰 상태를 테스트마다 비우고, 그래프 BC 는 기본 0개."""
    forbid_real_backends(monkeypatch)
    capture_logs(monkeypatch)
    iv._answers.clear()
    iv._recs.clear()
    monkeypatch.setattr(iv, "_proposal_ctx", None)
    graph_bcs: list[dict] = []
    monkeypatch.setattr(neo4j_helpers, "load_domain_nodes", lambda *a, **k: list(graph_bcs))
    yield graph_bcs
    iv._answers.clear()
    iv._recs.clear()


def _bcs(*names):
    return [{"id": f"bc-{i}", "label": "BoundedContext", "name": n} for i, n in enumerate(names)]


def _walk(answers: dict) -> list[str]:
    """next_question 이 묻는 순서대로 답하며 물어본 field 목록을 돌려준다."""
    asked = []
    for _ in range(10):
        q = iv.next_question()
        if q is None:
            return asked
        asked.append(q["field"])
        iv.record_answer(q["field"], answers.get(q["field"], q["recommended"]))
    raise AssertionError(f"interview did not finish: {asked}")


# ── 첫 질문 · 추천 ────────────────────────────────────────────────────────────

def test_first_question_is_architecture_style(clean_state):
    q = iv.next_question()
    assert q["index"] == 1 and q["field"] == "architectureStyle"
    assert q["options"] == ["MONOLITH", "MICROSERVICES"]


@pytest.mark.parametrize("names, expected", [
    ((), "MONOLITH"),
    (("주문", "결제", "배송"), "MONOLITH"),
    (("주문", "결제", "배송", "정산"), "MICROSERVICES"),
])
def test_architecture_recommendation_follows_bounded_context_count(clean_state, names, expected):
    clean_state.extend(_bcs(*names))
    q = iv.next_question()
    assert q["recommended"] == expected
    assert f"BoundedContext {len(names)}개" in q["rationale"]


def test_only_named_bounded_contexts_are_counted(clean_state):
    clean_state.extend(_bcs("주문", "결제", "배송"))
    clean_state.extend([{"id": "agg-1", "label": "Aggregate", "name": "Order"},
                        {"id": "us-1", "label": "UserStory", "name": "고객: 주문"},
                        {"id": "bc-x", "label": "BoundedContext", "name": ""}])
    assert iv.next_question()["recommended"] == "MONOLITH"


def test_graph_lookup_failure_falls_back_to_zero_contexts(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("neo4j down")

    monkeypatch.setattr(neo4j_helpers, "load_domain_nodes", boom)
    q = iv.next_question()
    assert q["recommended"] == "MONOLITH" and "BoundedContext 0개" in q["rationale"]


# ── 질문 순서 ─────────────────────────────────────────────────────────────────

def test_monolith_asks_only_style_and_stack(clean_state):
    assert _walk({"architectureStyle": "MONOLITH"}) == ["architectureStyle", "techStack"]
    assert iv.answers_snapshot() == {
        "architectureStyle": "MONOLITH", "repoStrategy": "MONOREPO",  # 모놀리스는 MONOREPO 자동 확정
        "techStack": "Spring Boot + JPA + PostgreSQL + Vue 3",
    }


def test_microservices_repo_per_service_asks_every_gate(clean_state):
    asked = _walk({"architectureStyle": "MICROSERVICES", "repoStrategy": "REPO_PER_SERVICE"})
    assert asked == MICRO_FULL


def test_microservices_monorepo_skips_repo_mode(clean_state):
    asked = _walk({"architectureStyle": "MICROSERVICES", "repoStrategy": "MONOREPO"})
    assert asked == ["architectureStyle", "techStack", "repoStrategy", "deploymentTarget", "messaging"]
    assert "repoMode" not in iv.answers_snapshot()


def test_question_indexes_and_free_text_stack(clean_state):
    iv.record_answer("architectureStyle", "MICROSERVICES")
    q = iv.next_question()
    assert (q["index"], q["field"], q.get("allowFree")) == (2, "techStack", True)
    iv.record_answer("techStack", "Go + Postgres + Svelte")  # 보기 밖 직접 입력 허용
    assert iv.next_question()["index"] == 3
    iv.record_answer("repoStrategy", "REPO_PER_SERVICE")
    assert iv.next_question()["index"] == 4
    iv.record_answer("repoMode", "SPLIT_GIT")
    assert iv.next_question()["index"] == 5
    iv.record_answer("deploymentTarget", "Kubernetes")
    assert iv.next_question()["index"] == 6
    iv.record_answer("messaging", "RabbitMQ")
    assert iv.next_question() is None


def test_answers_are_keyed_by_field_not_order(clean_state):
    iv.record_answer("techStack", "Node/NestJS + Prisma + PostgreSQL + React")
    assert iv.next_question()["field"] == "architectureStyle"
    iv.record_answer("architectureStyle", "MONOLITH")
    assert iv.next_question() is None


def test_empty_field_is_ignored(clean_state):
    assert iv.record_answer("", "MONOLITH") == 0
    assert iv.answers_snapshot() == {}


# ── 앞 질문으로 돌아가 답을 바꾸는 경우 ─────────────────────────────────────────

def test_switching_to_monolith_drops_microservice_only_answers(clean_state):
    _walk({"architectureStyle": "MICROSERVICES", "repoStrategy": "REPO_PER_SERVICE"})
    iv.record_answer("architectureStyle", "MONOLITH")
    assert iv.answers_snapshot() == {
        "architectureStyle": "MONOLITH", "repoStrategy": "MONOREPO",
        "techStack": "Spring Boot + JPA + PostgreSQL + Vue 3",  # 상위 결정과 무관한 답은 유지
    }
    assert iv.next_question() is None


def test_switching_to_microservices_reasks_repo_strategy(clean_state):
    _walk({"architectureStyle": "MONOLITH"})
    iv.record_answer("architectureStyle", "MICROSERVICES")
    assert "repoStrategy" not in iv.answers_snapshot()  # 자동 MONOREPO 는 비운다
    assert iv.next_question()["field"] == "repoStrategy"


def test_changing_repo_strategy_drops_only_repo_mode(clean_state):
    _walk({"architectureStyle": "MICROSERVICES", "repoStrategy": "REPO_PER_SERVICE"})
    iv.record_answer("repoStrategy", "MONOREPO")
    snap = iv.answers_snapshot()
    assert "repoMode" not in snap
    assert snap["deploymentTarget"] == "Kubernetes" and snap["messaging"].startswith("Kafka")
    assert iv.next_question() is None


def test_changing_back_to_repo_per_service_reasks_repo_mode(clean_state):
    _walk({"architectureStyle": "MICROSERVICES", "repoStrategy": "MONOREPO"})
    iv.record_answer("repoStrategy", "REPO_PER_SERVICE")
    assert iv.next_question()["field"] == "repoMode"


def test_reanswering_the_same_value_keeps_downstream(clean_state):
    _walk({"architectureStyle": "MICROSERVICES", "repoStrategy": "REPO_PER_SERVICE"})
    before = iv.answers_snapshot()
    iv.record_answer("architectureStyle", "MICROSERVICES")
    assert iv.answers_snapshot() == before


def test_reset_answers_starts_over(clean_state):
    _walk({"architectureStyle": "MONOLITH"})
    iv._recs["techStack"] = {"recommended": "x"}
    iv.reset_answers()
    assert iv.answers_snapshot() == {} and iv._recs == {}
    assert iv.next_question()["field"] == "architectureStyle"


# ── 제안(Plan 게이트) 맥락 · Claude 분석 추천 ─────────────────────────────────────

def _proposal_session(monkeypatch, record):
    runs = []

    class _S:
        def run(self, query, **params):
            runs.append((query, params))
            return FakeResult(record)

    @contextmanager
    def fake_session(*_a, **_k):
        yield _S()

    monkeypatch.setattr(neo4j_mod, "get_session", fake_session)
    return runs


SD = {"epics": [{"op": "CREATE", "entityTitle": n} for n in ("주문", "결제", "배송", "정산")]
      + [{"op": "CREATE"}, "bad"]}


def test_set_proposal_context_uses_proposal_bounded_contexts(clean_state, monkeypatch):
    clean_state.extend(_bcs("그래프BC"))
    _proposal_session(monkeypatch, {"prompt": "주문·결제·배송·정산 분리", "sd": json.dumps(SD, ensure_ascii=False)})
    iv.record_answer("architectureStyle", "MONOLITH")

    ctx = iv.set_proposal_context("PRO-009")
    assert ctx == {"id": "PRO-009", "prompt": "주문·결제·배송·정산 분리", "bc_names": ["주문", "결제", "배송", "정산"]}
    assert iv.answers_snapshot() == {}  # Plan 게이트 진입은 새 인터뷰
    q = iv.next_question()
    assert q["recommended"] == "MICROSERVICES" and "BoundedContext 4개" in q["rationale"]


def test_set_proposal_context_tolerates_lookup_failure(monkeypatch):
    @contextmanager
    def broken(*_a, **_k):
        raise RuntimeError("neo4j down")
        yield  # pragma: no cover

    monkeypatch.setattr(neo4j_mod, "get_session", broken)
    assert iv.set_proposal_context("PRO-010") == {"id": "PRO-010", "prompt": "", "bc_names": []}


def test_analysis_recommendations_override_defaults(clean_state):
    iv._recs.update({"techStack": {"recommended": "Python/FastAPI + SQLAlchemy + PostgreSQL + Vue 3",
                                   "rationale": "프롬프트가 FastAPI 를 언급"}})
    q = iv.next_question()
    assert q["field"] == "architectureStyle" and "fromAnalysis" not in q
    iv.record_answer("architectureStyle", "MONOLITH")
    q = iv.next_question()
    assert q["recommended"].startswith("Python/FastAPI") and q["rationale"] == "프롬프트가 FastAPI 를 언급"
    assert q["fromAnalysis"] is True


def _collect(agen):
    async def run():
        return [ev async for ev in agen]
    return asyncio.run(run())


def test_analyze_without_proposal_context_asks_without_skill(clean_state, monkeypatch):
    calls = []
    monkeypatch.setattr(iv, "run_skill_lines", fake_skill_lines([], calls=calls))
    events = _collect(iv.analyze_proposal())
    assert [k for k, _ in events] == ["phase", "log_line", "question", "done"]
    assert dict(events)["question"]["field"] == "architectureStyle"
    assert calls == []


def test_analyze_proposal_applies_claude_recommendations(clean_state, monkeypatch):
    monkeypatch.setattr(iv, "_proposal_ctx", {"id": "PRO-009", "prompt": "Kafka 로 연동", "bc_names": ["주문", "결제"]})
    analysis = {"action": "analysis", "recommendations": [
        {"area": "architectureStyle", "recommended": "MICROSERVICES", "rationale": "결제 독립 배포 필요"},
        {"area": "repoStrategy", "recommended": "MONOREPO", "rationale": "소규모 팀"},
        {"recommended": "area 없는 항목은 무시"},
    ], "seededFrom": ["Kafka 로 연동"]}
    calls = []
    lines = ["TOOL:Read:/x", "[분석] 두 컨텍스트", "```json",
             *json.dumps(analysis, ensure_ascii=False, indent=2).splitlines(), "```"]
    monkeypatch.setattr(iv, "run_skill_lines", fake_skill_lines(lines, calls=calls))

    events = _collect(iv.analyze_proposal())
    logs = [d["text"] for k, d in events if k == "log_line"]
    assert "[분석] 두 컨텍스트" in logs
    assert "[추천] architectureStyle: MICROSERVICES — 결제 독립 배포 필요" in logs
    assert "[시드] Kafka 로 연동" in logs
    assert not any(entry.lstrip().startswith(("{", '"')) for entry in logs)  # JSON 은 로그로 흘리지 않는다
    q = dict(events)["question"]
    # 그래프 BC 2개면 기본은 MONOLITH 지만 Claude 분석 추천이 우선한다
    assert q["recommended"] == "MICROSERVICES" and q["fromAnalysis"] is True
    assert set(iv._recs) == {"architectureStyle", "repoStrategy"}
    assert calls[0]["name"] == "robo-project-constitution"
    assert "BoundedContext(2개): 주문, 결제" in calls[0]["prompt"]


def test_analyze_failure_still_asks_first_question(clean_state, monkeypatch):
    monkeypatch.setattr(iv, "_proposal_ctx", {"id": "PRO-009", "prompt": "", "bc_names": []})
    monkeypatch.setattr(iv, "run_skill_lines", fake_skill_lines(["[분석] 시작"], raises=RuntimeError("claude not found")))
    events = _collect(iv.analyze_proposal())
    assert any(k == "log_line" and "[분석 경고] claude not found" in d["text"] for k, d in events)
    assert dict(events)["question"]["field"] == "architectureStyle"
    assert iv._recs == {}


# ── 헌장 합성(stream_project_constitution) ─────────────────────────────────────

def test_stream_asks_pending_question_without_running_skill(clean_state, monkeypatch):
    calls = []
    monkeypatch.setattr(iv, "run_skill_lines", fake_skill_lines([], calls=calls))
    iv.record_answer("architectureStyle", "MONOLITH")
    events = _collect(iv.stream_project_constitution())
    assert dict(events)["question"]["field"] == "techStack"
    assert events[-1] == ("done", {"pending": True})
    assert calls == []


def _complete_monolith():
    iv.record_answer("architectureStyle", "MONOLITH")
    iv.record_answer("techStack", "Spring Boot + JPA + PostgreSQL + Vue 3")


def test_stream_synthesizes_and_saves_once_all_gates_are_answered(clean_state, monkeypatch):
    _complete_monolith()
    monkeypatch.setattr(iv, "_proposal_ctx", {"id": "PRO-009", "prompt": "부분 환불", "bc_names": ["환불"]})
    out = {"action": "done", "raw": "# Constitution\n## Core Principles\n- 단일 배포",
           "fields": {"architectureStyle": "MONOLITH", "repoStrategy": "MONOREPO"}}
    calls, saved = [], []
    monkeypatch.setattr(iv, "run_skill_lines",
                        fake_skill_lines(["[작성] 헌장 본문"] + _fenced(out), calls=calls))
    monkeypatch.setattr(iv.store, "upsert_project_constitution",
                        lambda raw, fields: saved.append((raw, fields)) or "a" * 64)

    events = _collect(iv.stream_project_constitution())
    assert saved == [(out["raw"], out["fields"])]
    assert events[-1] == ("done", {"raw": out["raw"], "fields": out["fields"], "constitutionHash": "a" * 64})
    assert ("draft", {"raw": out["raw"]}) in events
    prompt = calls[0]["prompt"]
    assert "- architectureStyle: MONOLITH" in prompt and "- repoStrategy: MONOREPO" in prompt
    assert "원본 프롬프트: 부분 환불" in prompt
    # 합성이 끝나면 인터뷰 상태를 모두 비운다
    assert iv.answers_snapshot() == {} and iv._recs == {} and iv._proposal_ctx is None


@pytest.mark.parametrize("lines", [
    [],
    ["헌장을 작성하지 못했습니다."],
    ["```json", '{"action": "done", "fields": {}}', "```"],  # raw 없음
])
def test_stream_synthesis_failure_keeps_answers_for_retry(clean_state, monkeypatch, lines):
    _complete_monolith()
    saved = []
    monkeypatch.setattr(iv, "run_skill_lines", fake_skill_lines(lines))
    monkeypatch.setattr(iv.store, "upsert_project_constitution", lambda *a: saved.append(a))
    events = _collect(iv.stream_project_constitution())
    assert events[-1][0] == "error" and events[-1][1]["code"] == "CONSTITUTION_SYNTH_FAILED"
    assert saved == []
    assert iv.answers_snapshot()["architectureStyle"] == "MONOLITH"


def _fenced(obj):
    return ["```json", *json.dumps(obj, ensure_ascii=False, indent=2).splitlines(), "```"]


# ── 라우터(인터뷰 네비게이션) ───────────────────────────────────────────────────

def test_router_start_answer_state_flow(clean_state):
    r = asyncio.run(constitution_router.interview_start())
    assert r["question"]["field"] == "architectureStyle" and r["answers"] == {}
    body = constitution_router.ConstitutionAnswerRequest(field="architectureStyle", answer="MONOLITH")
    r = asyncio.run(constitution_router.interview_answer(body))
    assert r["question"]["field"] == "techStack" and r["complete"] is False
    body = constitution_router.ConstitutionAnswerRequest(field="techStack", answer="Go")
    r = asyncio.run(constitution_router.interview_answer(body))
    assert r["question"] is None and r["complete"] is True
    s = asyncio.run(constitution_router.interview_state())
    assert s["complete"] is True and s["answers"]["repoStrategy"] == "MONOREPO"


def test_router_legacy_answer_uses_question_index_key(clean_state):
    body = constitution_router.ConstitutionAnswerRequest(questionIndex=3, answer="x")
    r = asyncio.run(constitution_router.answer_project_constitution(body))
    assert r["answers"] == {"q3": "x"}


@pytest.mark.xfail(strict=True, reason=(
    "BUG: reset_answers 는 _answers/_recs 만 비우고 _proposal_ctx 는 남긴다 (constitution_interview.py "
    "reset_answers). Plan 게이트에서 분석(analyze)만 하고 헌장을 만들지 않은 채 Design 쪽 인터뷰를 "
    "새로 시작하면(/interview/start, /stream?fresh=true) 그래프 대신 지난 제안의 BC 로 추천하고, 합성 "
    "프롬프트에도 그 제안 맥락이 들어간다."))
def test_fresh_design_interview_forgets_previous_proposal_context(clean_state, monkeypatch):
    clean_state.extend(_bcs("주문"))
    _proposal_session(monkeypatch, {"prompt": "4개 컨텍스트", "sd": json.dumps(SD, ensure_ascii=False)})
    iv.set_proposal_context("PRO-009")           # Plan 게이트 진입 후 이탈
    asyncio.run(constitution_router.interview_start())  # Design 쪽 새 인터뷰
    q = iv.next_question()
    assert "BoundedContext 1개" in q["rationale"] and q["recommended"] == "MONOLITH"
