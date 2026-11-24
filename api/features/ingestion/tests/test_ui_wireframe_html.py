"""HTML 와이어프레임 (2026-11-24) — 실제 필드 · 화면 종류 · 대체 틀 · 테마 CSS."""

from api.features.ingestion.workflow.phases import ui_wireframes as W
from api.platform.ui_wireframe_template import fallback_ui_template, normalize_ui_template

FIELDS = [
    {"name": "cardNo", "displayName": "카드번호", "type": "String", "isRequired": True, "description": ""},
    {"name": "expiry", "displayName": "카드 유효기간", "type": "String", "isRequired": False, "description": "MM/YY"},
]


def test_command_prompt_carries_fields_and_single_primary_action():
    p = W._html_screen_prompt("Command", "UI Name: 카드 인증", FIELDS)
    assert "카드번호 (cardNo, String, required)" in p and "카드 유효기간 (expiry, String) — MM/YY" in p
    assert "INPUT FORM" in p and "ONE footer button group" in p


def test_readmodel_prompt_is_read_only_list_or_detail():
    lst = W._html_screen_prompt("ReadModel", "x", FIELDS, multiple=True)
    det = W._html_screen_prompt("ReadModel", "x", FIELDS, multiple=False)
    assert "READ-ONLY LIST" in lst and "No input form" in lst
    assert "READ-ONLY DETAIL" in det and "wf-kv" in det


def test_rm_multiple_values_from_model():
    assert W._rm_is_multiple("single result") is False
    assert W._rm_is_multiple("list") is True and W._rm_is_multiple("collection") is True
    assert W._rm_is_multiple(None) is None


def test_fallback_template_is_marked_and_not_reused():
    t = fallback_ui_template(ui_name="X", theme="ant")
    assert 'data-wf-fallback="1"' in t and W._is_fallback_template(t)
    # 표시가 생기기 전에 저장된 빈 틀도 알아본다
    assert W._is_fallback_template('<div class="wf-root">Loading state placeholder</div>')
    assert not W._is_fallback_template('<div class="wf-root"><div class="wf-card">카드번호</div></div>')


def test_unstyled_llm_html_gets_theme_css():
    html, rep = normalize_ui_template(
        '<div class="wf-root wf-theme-ant" data-wf-root="1"><div class="wf-card">a</div></div>', ui_name="X")
    assert rep.injected_theme_css and "<style>" in html and ".wf-root .wf-help" in html
    assert html.index("<style>") > html.index("data-wf-root")


def test_system_prompt_no_style_and_hint_class():
    sp = W._UI_WIREFRAME_SYSTEM_PROMPT
    assert "Do NOT include a <style> block" in sp and "wf-help" in sp
