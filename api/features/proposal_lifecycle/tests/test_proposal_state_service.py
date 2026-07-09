from __future__ import annotations

from api.features.proposal_lifecycle.services import lifecycle_steps as L
from api.features.proposal_lifecycle.services import proposal_state_service
from api.features.proposal_lifecycle.services import proposal_state_service as S


def test_progress_header_is_thin_and_choices_in_footer():
    """014-report-design: 진행(상단 얇은 한 줄) / 선택지(하단 푸터) 분리(D1)."""
    node = {"decompositionMode": "SIMPLIFIED", "staleArtifacts": "[]"}
    step = L.StepDef("STRATEGIC_DIFF", None, L.GENERATE_DRAFT, True, None)
    pm = S._progress_meta(node, step, L.GENERATE_DRAFT, [], [])
    header, footer = pm["headerMarkdown"], pm["footerMarkdown"]
    # 상단 진행: 얇은 한 줄, 선택지 표/블록 없음.
    assert header.startswith("📍 **진행")
    assert "다음 행동 선택" not in header and "가능한 선택지" not in header
    # 하단 푸터: 액션 목록형 선택지(번호+볼드 라벨+힌트), 본문 하단 배치.
    assert footer.startswith("---")
    assert "## 다음 행동 선택" in footer
    assert "1. ✅ **승인** — 현재 단계 산출물을 확정합니다" in footer
    assert "2. ✏️ **수정**" in footer


def test_footer_includes_skip_only_on_stage_steps():
    node = {"decompositionMode": "DETAILED_DDD", "staleArtifacts": "[]"}
    step = L.StepDef("TACTICAL_DDD", "TACTICAL", L.GENERATE_DRAFT, True, None)
    pm = S._progress_meta(node, step, L.GENERATE_DRAFT, [{"phase": "STRATEGIC_DIFF", "stage": None}], [])
    footer = pm["footerMarkdown"]
    assert "⏭️ **건너뛰기**" in footer
    assert "↩️ **되돌리기 → 전략 Diff**" in footer
    # stageLabel 은 진행 한 줄에 괄호 병기.
    assert "(Tactical" in pm["headerMarkdown"]


def test_stale_shows_warning_quote_in_header():
    node = {"decompositionMode": "SIMPLIFIED", "staleArtifacts": '["임팩트 분석"]'}
    step = L.StepDef("CONSTITUTION", None, L.GENERATE_DRAFT, True, None)
    pm = S._progress_meta(node, step, L.GENERATE_DRAFT, [], ["임팩트 분석"])
    assert "⚠️ **무효화 대상**: 임팩트 분석" in pm["headerMarkdown"]


def test_next_step_blocks_unknown_explicit_phase(monkeypatch):
    monkeypatch.setattr(proposal_state_service, "get_node", lambda proposal_id: {"id": proposal_id})

    result = proposal_state_service.next_step("PRO-test", phase="NOT_A_PHASE")

    assert result["status"] == "blocked"
    assert result["reason"]["reason"] == "unknown_phase"


def test_next_step_blocks_pending_question_on_forced_phase(monkeypatch):
    monkeypatch.setattr(
        proposal_state_service,
        "get_node",
        lambda proposal_id: {"id": proposal_id, "pendingQuestionId": "PI-question"},
    )

    result = proposal_state_service.next_step("PRO-test", phase="TASKS")

    assert result["status"] == "blocked"
    assert result["reason"]["reason"] == "pending_question"
