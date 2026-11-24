"""인스펙터 HTML 수정 챗 — 생성 단계와 같은 규칙인지 (2026-11-24)."""

from api.features.ai_design import html_template as H

CSS_TEMPLATE = (
    '<div class="wf-root wf-theme-ant" data-wf-root="1">\n  <style>\n.wf-root .wf-card { padding: 1px; }\n  </style>'
    '<div class="wf-card">신청서 정보</div></div>'
)
FIELDS = [{"name": "status", "displayName": "신청 상태", "type": "String", "isRequired": True, "description": ""}]


def _ctx(**kw):
    base = {"name": "AutoDebitApplicationDetail", "displayName": "자동납부 신청서 상세", "bcName": "자동납부",
            "attachedToType": "ReadModel", "attachedToName": "AutoDebitApplicationDetail",
            "description": "신청서 상세", "template": CSS_TEMPLATE, "fields": FIELDS, "multiple": "single result"}
    base.update(kw)
    return base


def test_edit_sends_structure_without_theme_css():
    _, user_p, _ = H.build_prompts(_ctx(), instruction="버튼을 더 크게")
    assert "신청서 정보" in user_p and "<style" not in user_p and ".wf-card { padding" not in user_p
    assert "버튼을 더 크게" in user_p and "Change only what is asked" in user_p


def test_same_rules_as_generation_fields_and_screen_type():
    sys_p, user_p, _ = H.build_prompts(_ctx(), instruction="")
    assert "Do NOT include a <style> block" in sys_p and "Korean" in sys_p
    assert "신청 상태 (status, String, required)" in user_p
    assert "READ-ONLY DETAIL" in user_p


def test_command_screen_is_input_form():
    _, user_p, _ = H.build_prompts(_ctx(attachedToType="Command", multiple=None, template=""), instruction="")
    assert "INPUT FORM" in user_p
