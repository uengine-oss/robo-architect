"""순수 로직 단위 테스트 (035) — Neo4j/LLM 불필요.

- recommend_plan: 프로파일/스코프별 단계 추천
- WizardSession: 상태 전이·재개 보존
- engine._fallback: LLM 없이 결정적 산출물
- ddd_export._slug: 파일명 슬러그
"""

from __future__ import annotations

from api.features.requirements.ddd_wizard import wizard_session as store
from api.features.requirements.ddd_wizard.engine import _fallback
from api.features.requirements.ddd_wizard.step_prompts import (
    STEP_META,
    profile_summary,
    recommend_plan,
)
from api.features.requirements.requirements_contracts import ProfileAnswer
from api.features.requirements.routes.ddd_export import _slug


def _profile(**kw) -> ProfileAnswer:
    base = dict(projectType="greenfield", dddExperience="first_time", teamSize="small")
    base.update(kw)
    return ProfileAnswer(**base)


def test_recommend_plan_always_includes_required_steps():
    plan = recommend_plan(_profile(), scope="greenfield")
    keys = {s.key for s in plan}
    assert keys == {m[0] for m in STEP_META}  # 모든 단계 노출
    # discover/decompose/define은 필수(optional=False)
    required = {s.key for s in plan if not s.optional}
    assert {"discover", "decompose", "define"} <= required


def test_recommend_plan_greenfield_recommends_understand_and_strategize():
    plan = recommend_plan(_profile(), scope="greenfield")
    rec = {s.key for s in plan if s.recommended}
    assert "understand" in rec
    assert "strategize" in rec
    assert "code" in rec  # 학습용이 아니므로 code 추천


def test_recommend_plan_learning_excludes_code():
    plan = recommend_plan(_profile(projectType="learning"), scope="greenfield")
    rec = {s.key for s in plan if s.recommended}
    assert "code" not in rec


def test_recommend_plan_epic_scope_narrows_organise_connect():
    plan = recommend_plan(_profile(teamSize="large"), scope="epic")
    rec = {s.key for s in plan if s.recommended}
    # 에픽 스코프에서는 connect/organise를 추천에서 제외
    assert "organise" not in rec
    assert "connect" not in rec


def test_recommend_plan_large_team_greenfield_recommends_org_connect():
    plan = recommend_plan(_profile(teamSize="large"), scope="greenfield")
    rec = {s.key for s in plan if s.recommended}
    assert "connect" in rec
    assert "organise" in rec


def test_profile_summary_korean():
    s = profile_summary(_profile(), scope="greenfield")
    assert "신규" in s and "맨땅" in s


def test_wizard_session_state_transitions_and_resume():
    plan = recommend_plan(_profile(), scope="greenfield")
    sess = store.create_session(
        scope="greenfield", epic_id=None, profile=_profile(), plan=plan, engine="in-process"
    )
    assert sess.phase == "profiling"
    assert store.get_session(sess.session_id) is sess

    sess.record_answer("discover", {"notes": "주문이 생성됨"}, None)
    assert sess.phase == "proposing"
    assert sess.answers["discover"]["notes"] == "주문이 생성됨"

    from api.features.requirements.requirements_contracts import WizardProposal

    sess.record_proposal(WizardProposal(stepKey="discover", artifactMarkdown="x"))
    assert sess.phase == "awaiting_answers"

    sess.mark_confirmed("discover")
    assert "discover" in sess.completed_steps
    # 전체 단계 미완료 → step_running 으로 복귀(재개 가능)
    assert sess.phase == "step_running"
    # 재개: 완료 단계/답변 보존
    again = store.get_session(sess.session_id)
    assert again.completed_steps == ["discover"]
    assert "discover" in again.answers


def test_wizard_session_all_steps_confirmed_marks_done():
    plan = recommend_plan(_profile(), scope="greenfield")
    sess = store.create_session(
        scope="greenfield", epic_id=None, profile=_profile(), plan=plan, engine="in-process"
    )
    for s in plan:
        sess.mark_confirmed(s.key)
    assert sess.phase == "confirmed"


def test_engine_fallback_decompose_proposes_bounded_contexts():
    artifact, changes = _fallback("decompose", {"subdomains": "주문, 결제, 배송"}, None)
    assert "decompose" in artifact
    names = sorted(c["after"]["name"] for c in changes)
    assert names == ["결제", "배송", "주문"]
    assert all(c["targetType"] == "BoundedContext" for c in changes)


def test_engine_fallback_no_subdomains_no_changes():
    _, changes = _fallback("understand", {"notes": "가치 제안"}, None)
    assert changes == []


def test_engine_normalizes_bc_change_name_from_alternate_keys(monkeypatch):
    """LLM이 name 대신 displayName/title/label로 BC 이름을 줄 때 정규화되는지."""
    import api.features.requirements.ddd_wizard.engine as eng

    # _via_claude/get_llm를 타지 않도록 _parse가 직접 반환하게 가짜 LLM 경로를 막고
    # generate_step의 in-process 분기를 우회: 직접 previews 정규화 로직만 검증.
    def fake_parse(_raw):
        return "art", [
            {"action": "create", "targetType": "BoundedContext", "after": {"displayName": "주문관리"}},
            {"action": "create", "targetType": "BoundedContext", "label": "BoundedContext '결제' 생성", "after": {}},
            {"action": "create", "targetType": "BoundedContext", "after": {}, "label": "이름없음라벨"},
        ]

    monkeypatch.setattr(eng, "_parse", fake_parse)

    # in-process LLM 호출이 fake_parse 결과를 쓰도록 get_llm을 가짜로.
    class _FakeLLM:
        def invoke(self, _msgs):
            class _R:
                content = "{}"
            return _R()

    import api.features.ingestion.ingestion_llm_runtime as rt
    monkeypatch.setattr(rt, "get_llm", lambda: _FakeLLM())

    proposal = eng.generate_step("decompose", {}, None, engine="in-process")
    names = [c.after.get("name") for c in proposal.graphChanges]
    # 1) displayName→name, 2) label 따옴표→name, 3) 따옴표없는 label→name(폴백)
    assert "주문관리" in names
    assert "결제" in names
    # 빈 after + 라벨만 있으면 라벨 텍스트라도 이름으로 채워져 최소 3건 유지
    assert all(n for n in names)


def test_export_slug():
    assert _slug("Order Management") == "order-management"
    assert _slug("주문 관리") == "주문-관리"
    assert _slug("  ") == "untitled"
