from __future__ import annotations

from api.features.proposal_lifecycle.services import proposal_state_service


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
