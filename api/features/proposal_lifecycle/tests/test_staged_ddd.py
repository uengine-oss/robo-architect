"""042 — Staged DDD decomposition 단위 테스트 (Neo4j 불필요, 순수 로직 + monkeypatch).

Test Plan TP-A…F 의 결정 가능한(LLM/DB 비의존) 부분을 커버한다. 스테이지 SSE 실행
(실제 스킬 호출)은 단위 테스트 범위 밖이며 quickstart 시나리오로 검증한다.
"""

import json

import pytest

from api.features.proposal_lifecycle.proposal_contracts import (
    DecompositionMode, DddStage, DDD_STAGE_ORDER, NON_OMITTABLE_STAGES,
    StagePlan, StagePlanItem, ProposalResponse,
)
from api.features.proposal_lifecycle.services import staged_runner
from api.features.proposal_lifecycle.services import strategic_memory


# --- TP-A: 모드 필드 -------------------------------------------------------

def test_create_request_defaults_simplified():
    from api.features.proposal_lifecycle.proposal_contracts import CreateProposalRequest
    assert CreateProposalRequest(originalPrompt="x").decompositionMode == DecompositionMode.SIMPLIFIED


def test_proposal_response_parses_mode_and_stage_plan():
    node = {
        "id": "PRO-001", "status": "DRAFT", "decompositionMode": "DETAILED_DDD",
        "stagePlan": json.dumps({"version": 1, "stages": [
            {"stage": "DISCOVER", "applies": True, "recommendSkip": False, "skipped": False, "reason": "r"}]}),
        "currentStage": "DISCOVER",
        "stageArtifacts": json.dumps({"DISCOVER": {"stage": "DISCOVER", "events": []}}),
    }
    r = ProposalResponse.from_neo4j(node, [])
    assert r.decompositionMode == DecompositionMode.DETAILED_DDD
    assert r.currentStage == "DISCOVER"
    assert r.stagePlan.stages[0].stage == DddStage.DISCOVER
    assert "DISCOVER" in r.stageArtifacts


# --- TP-C: 스테이지 플랜 / 생략 규칙 --------------------------------------

def test_validate_stage_plan_blocks_discover_skip():
    err = staged_runner.validate_stage_plan([{"stage": "DISCOVER", "skipped": True}])
    assert err and err["reason"] == "discover_not_skippable"


def test_validate_stage_plan_allows_other_skips():
    assert staged_runner.validate_stage_plan([{"stage": "CONNECT", "skipped": True}]) is None


def test_active_stages_respects_skip_and_order():
    plan = {"stages": [
        {"stage": "DISCOVER", "applies": True, "skipped": False},
        {"stage": "DECOMPOSE", "applies": True, "skipped": True},
        {"stage": "STRATEGIZE", "applies": True, "skipped": False},
        {"stage": "CONNECT", "applies": True, "skipped": True},
        {"stage": "DEFINE", "applies": True, "skipped": False},
        {"stage": "TACTICAL", "applies": True, "skipped": False},
    ]}
    assert staged_runner._active_stages(plan) == ["DISCOVER", "STRATEGIZE", "DEFINE", "TACTICAL"]


def test_next_stage_after_skips_skipped():
    plan = {"stages": [
        {"stage": "DISCOVER", "applies": True, "skipped": False},
        {"stage": "DECOMPOSE", "applies": True, "skipped": True},
        {"stage": "STRATEGIZE", "applies": True, "skipped": False},
    ]}
    assert staged_runner.next_stage_after(plan, "DISCOVER") == "STRATEGIZE"
    assert staged_runner.next_stage_after(plan, "STRATEGIZE") is None


# --- TP-B/F: 재개(resume) + 직전 단계 가드 --------------------------------

def test_resume_point_first_missing_artifact(monkeypatch):
    state = {
        "stagePlan": {"stages": [
            {"stage": "DISCOVER", "applies": True, "skipped": False},
            {"stage": "STRATEGIZE", "applies": True, "skipped": False},
        ]},
        "stageArtifacts": {"DISCOVER": {"x": 1}},
    }
    monkeypatch.setattr(staged_runner, "load_state", lambda pid: state)
    assert staged_runner.resume_point("PRO-1") == "STRATEGIZE"


def test_prior_stage_incomplete(monkeypatch):
    state = {
        "stagePlan": {"stages": [
            {"stage": "DISCOVER", "applies": True, "skipped": False},
            {"stage": "STRATEGIZE", "applies": True, "skipped": False},
        ]},
        "stageArtifacts": {},
    }
    monkeypatch.setattr(staged_runner, "load_state", lambda pid: state)
    assert staged_runner.prior_stage_incomplete("PRO-1", "STRATEGIZE") is True
    assert staged_runner.prior_stage_incomplete("PRO-1", "DISCOVER") is False


# --- TP-D: 전략 메모리 충돌 감지 + 승격 게이트 ----------------------------

def test_detect_conflicts_classification(monkeypatch):
    monkeypatch.setattr(strategic_memory.cstore, "get_project_strategic_memory",
                        lambda: {"contexts": {"결제": {"classification": "GENERIC"}}})
    artifact = {"classifications": [{"subDomain": "결제", "kind": "CORE"}]}
    conflicts = strategic_memory.detect_conflicts("PRO-1", "STRATEGIZE", artifact)
    assert len(conflicts) == 1
    assert conflicts[0]["field"] == "classification"
    assert conflicts[0]["memoryValue"] == "GENERIC"
    assert conflicts[0]["proposalValue"] == "CORE"


def test_detect_conflicts_coupling(monkeypatch):
    monkeypatch.setattr(strategic_memory.cstore, "get_project_strategic_memory",
                        lambda: {"couplingPosture": {"default": "PUBSUB"}})
    artifact = {"interactions": [{"from": "A", "to": "B", "message": "M", "kind": "COMMAND", "sync": True}]}
    conflicts = strategic_memory.detect_conflicts("PRO-1", "CONNECT", artifact)
    assert len(conflicts) == 1 and conflicts[0]["field"] == "couplingPosture"


def test_apply_stage_confirmation_blocks_unresolved(monkeypatch):
    monkeypatch.setattr(strategic_memory.cstore, "get_project_strategic_memory",
                        lambda: {"contexts": {"결제": {"classification": "GENERIC"}}})
    artifact = {"classifications": [{"subDomain": "결제", "kind": "CORE"}]}
    # 해소 없이 확정 → 409 error dict.
    err = strategic_memory.apply_stage_confirmation("PRO-1", "STRATEGIZE", artifact, [])
    assert err and err["reason"] == "unresolved_conflicts"


def test_apply_stage_confirmation_amend_promotes(monkeypatch):
    promoted = {}
    monkeypatch.setattr(strategic_memory.cstore, "get_project_strategic_memory",
                        lambda: {"contexts": {"결제": {"classification": "GENERIC"}}})
    monkeypatch.setattr(strategic_memory.cstore, "upsert_project_strategic_memory",
                        lambda m: promoted.update(m) or "h")
    monkeypatch.setattr(strategic_memory, "_record_conflicts", lambda *a, **k: None)
    artifact = {"classifications": [{"subDomain": "결제", "kind": "CORE", "rationale": "차별점"}]}
    err = strategic_memory.apply_stage_confirmation(
        "PRO-1", "STRATEGIZE", artifact,
        [{"bcId": "결제", "field": "classification", "resolution": "AMEND_MEMORY"}],
    )
    assert err is None
    assert promoted["contexts"]["결제"]["classification"] == "CORE"


def test_justify_local_keeps_memory(monkeypatch):
    promoted = {}
    monkeypatch.setattr(strategic_memory.cstore, "get_project_strategic_memory",
                        lambda: {"contexts": {"결제": {"classification": "GENERIC"}}})
    monkeypatch.setattr(strategic_memory.cstore, "upsert_project_strategic_memory",
                        lambda m: promoted.update(m) or "h")
    monkeypatch.setattr(strategic_memory, "_record_conflicts", lambda *a, **k: None)
    artifact = {"classifications": [{"subDomain": "결제", "kind": "CORE"}]}
    err = strategic_memory.apply_stage_confirmation(
        "PRO-1", "STRATEGIZE", artifact,
        [{"bcId": "결제", "field": "classification", "resolution": "JUSTIFY_LOCAL", "justification": "이번엔 예외"}],
    )
    assert err is None
    # JUSTIFY_LOCAL → 메모리 보존(GENERIC 유지).
    assert promoted["contexts"]["결제"]["classification"] == "GENERIC"


def test_promote_skips_non_durable_stages(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(strategic_memory.cstore, "get_project_strategic_memory", lambda: {})
    monkeypatch.setattr(strategic_memory.cstore, "upsert_project_strategic_memory",
                        lambda m: called.update(n=called["n"] + 1))
    # Discover/Decompose/Tactical 의 산출물은 지속 메모리로 승격하지 않는다(FR-020).
    strategic_memory.promote("DISCOVER", {"events": []})
    strategic_memory.promote("TACTICAL", {"aggregates": []})
    assert called["n"] == 0


# --- TP-B: artifact 구조 검증 헬퍼 ----------------------------------------

def test_strategize_validator():
    from api.features.proposal_lifecycle.services.stage_runners.strategize import _all_classified
    assert _all_classified({"classifications": [{"subDomain": "a", "kind": "CORE"}]}) is True
    assert _all_classified({"classifications": [{"subDomain": "a", "kind": "X"}]}) is False
    assert _all_classified({"classifications": []}) is False


def test_define_min_language():
    from api.features.proposal_lifecycle.services.stage_runners.define import _has_min_language
    five = [{"term": str(i), "definition": "d"} for i in range(5)]
    assert _has_min_language({"contexts": [{"ubiquitousLanguage": five}]}) is True
    assert _has_min_language({"contexts": [{"ubiquitousLanguage": five[:4]}]}) is False


def test_tactical_min_invariants():
    from api.features.proposal_lifecycle.services.stage_runners.tactical import _has_min_invariants
    assert _has_min_invariants({"aggregates": [{"invariants": ["a", "b"]}]}) is True
    assert _has_min_invariants({"aggregates": [{"invariants": ["a"]}]}) is False
