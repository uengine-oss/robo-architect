"""Tests for the HTML policy-document extension (feature 023)."""
from __future__ import annotations

import pytest

from api.features.ddd_spec.projection import (
    AggregateAttribute,
    AggregateProjection,
    BoundedContextProjection,
    CommandProjection,
    EventProjection,
    GwtCriterion,
    MemberEntity,
    PolicyProjection,
    UserStoryProjection,
    WireframeProjection,
)
from api.features.prd_generation.html_templates import (
    data_extractor,
    diagram_render,
    orchestrator,
    registry,
)
from api.features.prd_generation.html_templates.schema import TemplateManifest


def _make_member_bc() -> BoundedContextProjection:
    cmd_join = CommandProjection(
        id="c-join",
        name="회원 계정 생성",
        description="검증이 끝난 고객의 회원 계정을 생성한다",
        events_emitted=["회원계정생성됨"],
        preconditions=["본인인증이 완료되어 있다"],
    )
    cmd_leave = CommandProjection(
        id="c-leave",
        name="회원 탈퇴 처리",
        description="회원 상태를 탈퇴유예 또는 탈퇴완료로 전환한다",
        events_emitted=["회원탈퇴완료"],
    )
    agg = AggregateProjection(
        id="agg-member",
        name="Member",
        slug="member",
        root_entity="Member",
        identity_type="MemberId",
        attributes=[
            AggregateAttribute(name="status", type="MemberStatus", mutability="mutable"),
            AggregateAttribute(name="ci", type="string", mutability="immutable"),
        ],
        invariants=["하나의 CI 는 하나의 활성 Member 에만 매핑된다"],
        commands=[cmd_join, cmd_leave],
        events=[EventProjection(id="e1", name="회원계정생성됨")],
        policies=[
            PolicyProjection(
                id="pol-rejoin",
                name="재가입 제한",
                description="탈퇴 후 30일 이내에는 재가입을 제한한다",
                effect="차단",
            )
        ],
        member_entities=[MemberEntity(name="MemberId", kind="identifier")],
    )
    wf1 = WireframeProjection(
        ui_id="ui1", name="가입 약관 화면", slug="terms",
        attached_to_type="Command", attached_to_name="약관 동의", actor="고객",
    )
    wf2 = WireframeProjection(
        ui_id="ui2", name="가입 완료 안내", slug="join-done",
        attached_to_type="Command", attached_to_name="회원 계정 생성", actor="고객",
    )
    us = UserStoryProjection(
        id="us-join",
        title="회원 가입",
        narrative="As a 고객, I want to 회원으로 가입하다, so that 서비스를 이용할 수 있다",
        priority="P1",
        aggregate_id="agg-member",
        acceptance_criteria=[
            GwtCriterion(
                id="us-join-ac0",
                given=["비회원 상태이다"],
                when="약관에 동의하고 본인인증을 완료한다",
                then=["회원 계정이 생성된다"],
            )
        ],
        wireframes=[wf1, wf2],
    )
    return BoundedContextProjection(
        id="bc-member",
        name="회원 관리",
        slug="member-mgmt",
        purpose="고객의 회원 생애주기(가입·휴면·탈퇴·재가입)를 관리한다",
        aggregates=[agg],
        user_stories=[us],
        key_terms=["Member", "MemberStatus", "CI"],
    )


def test_manifest_loads():
    registry.load.cache_clear()
    manifest = registry.load("policy-doc-full")
    assert manifest.id == "policy-doc-full"
    assert manifest.master_template == "document.html.j2"
    assert any(s.id == "overview.principles" and s.kind == "llm" for s in manifest.sections)


def test_unknown_template_raises():
    registry.load.cache_clear()
    with pytest.raises(registry.TemplateNotFoundError):
        registry.load("nope-not-real")


def test_empty_graph_renders():
    """No BCs in the graph should still produce a valid HTML document."""
    html = orchestrator.render_policy_doc(
        "policy-doc-full", [], project_name="Demo", use_llm=False
    )
    assert "<html" in html and "</html>" in html
    assert "1. 개요" in html
    assert "6. 정책" in html
    # Fallback principles are emitted.
    assert "이벤트 일관성" in html


def test_member_bc_renders_all_sections():
    bc = _make_member_bc()
    html = orchestrator.render_policy_doc(
        "policy-doc-full", [bc], project_name="NC 통합채널", use_llm=False
    )
    for section in [
        "1. 개요", "2. 주요 용어", "3. 유즈케이스",
        "4. 프로세스", "5. 기능", "6. 정책",
    ]:
        assert section in html, f"missing section: {section}"
    # Each major derived row appears with its generated ID prefix.
    assert "UC-MEM" in html
    assert "FN-MEM" in html
    assert "POL-MEM" in html
    # Glossary lists modeled terms.
    assert "Member" in html
    assert "재가입 제한" in html
    # Both SVG diagrams are inlined.
    assert html.count("<svg") >= 2


def test_data_extractor_builds_actors_and_use_cases():
    bc = _make_member_bc()
    manifest = registry.load("policy-doc-full")
    ctx = data_extractor.build_base_context([bc], manifest=manifest, project_name="t")
    assert any(a.name == "고객" for a in ctx["actors"])
    assert len(ctx["use_cases"]) == 1
    assert ctx["use_cases"][0].name == "회원 가입"
    assert len(ctx["functions"]) == 2
    assert any(f.name == "회원 계정 생성" for f in ctx["functions"])
    # Member.status attr surfaces in state transitions.
    assert ctx["state_transitions"], "expected at least one state transition"
    assert any("Member.status" in tr.from_state for tr in ctx["state_transitions"])


def test_diagram_renderer_handles_empty_input():
    assert diagram_render.render_usecase_diagram([], []) is None
    assert diagram_render.render_process_flowchart([]) is None


def test_no_llm_provider_does_not_crash(monkeypatch):
    """LLM section failure (missing provider) must degrade to fallback text."""
    bc = _make_member_bc()

    def _boom(*a, **kw):
        raise RuntimeError("no provider")

    monkeypatch.setattr(
        "api.features.prd_generation.html_templates.llm_sections._invoke_llm",
        _boom,
    )
    html = orchestrator.render_policy_doc(
        "policy-doc-full", [bc], project_name="x", use_llm=True
    )
    # Fallback principle bullets render even though the LLM raised.
    assert "이벤트 일관성" in html
    # Warning box appears for the failed section.
    assert "자동 생성 경고" in html


def test_html_policy_optional_zip_integration_flag_present():
    """Ensure TechStackConfig exposes the new fields without breaking defaults."""
    from api.features.prd_generation.prd_api_contracts import TechStackConfig

    cfg = TechStackConfig()
    assert cfg.include_html_policy is False
    assert cfg.html_template_id == "policy-doc-full"

    cfg2 = TechStackConfig(include_html_policy=True, html_template_id="policy-doc-full")
    assert cfg2.include_html_policy is True
