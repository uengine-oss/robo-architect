"""B-2 — "요구사항 생성 엔진" 이 실제로 무엇을 돌렸는지 응답에 싣는다(LLM 실호출 없음).

claude-ide 를 골라도 로컬 claude 가 실패하면 조용히 in-process 로 넘어갔다 —
engineUsed/engineFallbackReason 으로 그 폴백이 화면까지 드러나야 한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from api.features.requirements.ddd_wizard import engine as wizard_engine
from api.features.requirements.requirements_contracts import GeneratedStory
from api.features.requirements.routes import child_story_generation as csg


def _llm_returning(stories):
    llm = MagicMock()
    llm.with_structured_output.return_value.invoke.return_value = csg._LLMStories(stories=stories)
    return llm


def test_child_claude_ok_reports_claude_ide():
    st = [GeneratedStory(role="r", action="a", benefit="b")]
    with patch.object(csg, "_generate_via_claude", return_value=st):
        out, used, reason = csg._generate("n", "", "Epic", None, [], engine="claude-ide")
    assert used == "claude-ide" and reason is None and len(out) == 1


def test_child_claude_fail_falls_back_visibly():
    st = [GeneratedStory(role="r", action="a", benefit="b")]
    with patch.object(csg, "_generate_via_claude", side_effect=RuntimeError("boom")), \
         patch.object(csg, "get_llm", return_value=_llm_returning(st)):
        out, used, reason = csg._generate("n", "", "Epic", None, [], engine="claude-ide")
    assert used == "in-process"
    assert reason and "boom" in reason
    assert len(out) == 1


def test_child_in_process_has_no_reason():
    with patch.object(csg, "get_llm", return_value=_llm_returning([])):
        _, used, reason = csg._generate("n", "", "Epic", None, [], engine="in-process")
    assert used == "in-process" and reason is None


def test_child_both_fail_reports_none():
    llm = MagicMock()
    llm.with_structured_output.side_effect = RuntimeError("nokey")
    with patch.object(csg, "_generate_via_claude", side_effect=RuntimeError("boom")), \
         patch.object(csg, "get_llm", return_value=llm):
        out, used, reason = csg._generate("n", "", "Epic", None, [], engine="claude-ide")
    assert out == [] and used == "none"
    assert "boom" in reason and "nokey" in reason


def test_wizard_claude_fail_then_llm_fail_is_deterministic():
    with patch.object(wizard_engine, "_via_claude", side_effect=RuntimeError("boom")), \
         patch("api.features.ingestion.ingestion_llm_runtime.get_llm", side_effect=RuntimeError("nokey")):
        p = wizard_engine.generate_step("decompose", {"subdomains": "주문"}, None, engine="claude-ide")
    assert p.engineRequested == "claude-ide"
    assert p.engineUsed == "deterministic"
    assert "boom" in (p.engineFallbackReason or "")
    assert p.artifactMarkdown


def test_wizard_claude_ok():
    with patch.object(wizard_engine, "_via_claude", return_value=("# art", [])):
        p = wizard_engine.generate_step("discover", {}, None, engine="claude-ide")
    assert p.engineUsed == "claude-ide" and p.engineFallbackReason is None
