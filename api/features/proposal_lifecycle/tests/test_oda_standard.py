"""043 — ODA 표준 모드 단위 테스트 (Neo4j/LLM 비의존, 순수 로직 + monkeypatch).

게이트(PASS/FAIL/WAIVE), 분류 완전성, mode/산출물 파싱(from_neo4j), 지식 루트 해석,
스킬 결과 파서를 커버한다. SSE 라이브 실행은 단위 범위 밖 → quickstart/manual 로 검증.
"""

import json

import pytest

from api.features.proposal_lifecycle.proposal_contracts import (
    DecompositionMode, CreateProposalRequest, ProposalResponse,
    OdaConformanceReport, WaiveConformanceRequest,
)
from api.features.proposal_lifecycle.services import oda_conformance, oda_runner


# --- TP-A: 모드 필드 -------------------------------------------------------

def test_create_request_defaults_simplified():
    assert CreateProposalRequest(originalPrompt="x").decompositionMode == DecompositionMode.SIMPLIFIED


def test_oda_mode_value():
    assert DecompositionMode.ODA_STANDARD.value == "ODA_STANDARD"
    assert CreateProposalRequest(originalPrompt="x", decompositionMode="ODA_STANDARD") \
        .decompositionMode == DecompositionMode.ODA_STANDARD


def test_proposal_response_parses_oda_payload():
    node = {
        "id": "PRO-900", "status": "DRAFT", "decompositionMode": "ODA_STANDARD",
        "odaAlignment": json.dumps({"useCases": [{"id": "UC003"}], "componentBlock": "coreFunction"}),
        "odaConformance": json.dumps({"items": [{"element": "Customer", "classification": "REUSE"}],
                                      "violations": [], "gateResult": "PASS"}),
        "odaArtifacts": json.dumps({"contracts": [{"api": "TMF629"}], "featureFiles": []}),
    }
    r = ProposalResponse.from_neo4j(node, [])
    assert r.decompositionMode == DecompositionMode.ODA_STANDARD
    assert r.odaAlignment.componentBlock == "coreFunction"
    assert r.odaConformance.gateResult == "PASS"
    assert r.odaArtifacts.contracts[0]["api"] == "TMF629"


def test_proposal_response_oda_fields_default_none():
    # ODA 산출물이 없는 (기존) Proposal 은 None 으로 안전 파싱.
    node = {"id": "PRO-1", "status": "DRAFT", "decompositionMode": "SIMPLIFIED"}
    r = ProposalResponse.from_neo4j(node, [])
    assert r.odaAlignment is None and r.odaConformance is None and r.odaArtifacts is None


def test_proposal_response_oda_malformed_is_none():
    node = {"id": "PRO-1", "status": "DRAFT", "decompositionMode": "ODA_STANDARD",
            "odaConformance": "{not json"}
    r = ProposalResponse.from_neo4j(node, [])
    assert r.odaConformance is None  # 깨진 JSON 이 500 을 만들지 않는다


# --- TP-B: 적합성 게이트 평가 ---------------------------------------------

def test_gate_pass_when_no_violations():
    g = oda_conformance.evaluate_gate({"violations": [], "items": [{"classification": "REUSE"}]})
    assert g["result"] == "PASS" and g["blocking"] is False


def test_gate_fail_blocks_on_violation():
    g = oda_conformance.evaluate_gate({"violations": [{"rule": "removed_std_field", "element": "id"}]})
    assert g["result"] == "FAIL" and g["blocking"] is True
    assert g["violations"][0]["rule"] == "removed_std_field"


def test_gate_waived_when_violation_has_waiver():
    g = oda_conformance.evaluate_gate({"violations": [{"rule": "x"}], "waiver": {"reason": "승인됨"}})
    assert g["result"] == "WAIVED" and g["blocking"] is False


def test_gate_pending_when_no_report():
    g = oda_conformance.evaluate_gate(None)
    assert g["result"] == "PENDING" and g["blocking"] is False


def test_gate_waiver_without_reason_still_fails():
    g = oda_conformance.evaluate_gate({"violations": [{"rule": "x"}], "waiver": {}})
    assert g["result"] == "FAIL"


# --- TP-C: 분류 완전성 (SC-003) -------------------------------------------

def test_all_classified_true():
    assert oda_conformance.all_classified(
        {"items": [{"classification": "REUSE"}, {"classification": "NEW"}]}) is True


def test_all_classified_false_on_unknown():
    assert oda_conformance.all_classified(
        {"items": [{"classification": "REUSE"}, {"classification": "FOO"}]}) is False


def test_all_classified_false_on_empty():
    assert oda_conformance.all_classified({"items": []}) is False
    assert oda_conformance.all_classified(None) is False


def test_can_proceed():
    assert oda_conformance.can_proceed({"violations": []}) is True
    assert oda_conformance.can_proceed({"violations": [{"rule": "x"}]}) is False
    assert oda_conformance.can_proceed({"violations": [{"rule": "x"}], "waiver": {"reason": "r"}}) is True


# --- TP-D: ensure_can_proceed 강제(게이트 차단) ----------------------------

def test_ensure_can_proceed_non_oda_passes(monkeypatch):
    monkeypatch.setattr(oda_conformance, "_load",
                        lambda pid: {"mode": "SIMPLIFIED", "conformance": None})
    assert oda_conformance.ensure_can_proceed("PRO-1") is None


def test_ensure_can_proceed_oda_fail_blocks(monkeypatch):
    monkeypatch.setattr(oda_conformance, "_load", lambda pid: {
        "mode": "ODA_STANDARD",
        "conformance": {"violations": [{"rule": "broke_contract", "element": "TMF629"}]}})
    err = oda_conformance.ensure_can_proceed("PRO-1")
    assert err and err["reason"] == "oda_conformance_failed"
    assert err["violations"][0]["element"] == "TMF629"


def test_ensure_can_proceed_oda_pass(monkeypatch):
    monkeypatch.setattr(oda_conformance, "_load", lambda pid: {
        "mode": "ODA_STANDARD", "conformance": {"violations": []}})
    assert oda_conformance.ensure_can_proceed("PRO-1") is None


def test_ensure_can_proceed_oda_waived(monkeypatch):
    monkeypatch.setattr(oda_conformance, "_load", lambda pid: {
        "mode": "ODA_STANDARD",
        "conformance": {"violations": [{"rule": "x"}], "waiver": {"reason": "ok"}}})
    assert oda_conformance.ensure_can_proceed("PRO-1") is None


def test_ensure_can_proceed_oda_pending_blocks(monkeypatch):
    monkeypatch.setattr(oda_conformance, "_load", lambda pid: {
        "mode": "ODA_STANDARD", "conformance": None})
    err = oda_conformance.ensure_can_proceed("PRO-1")
    assert err and err["reason"] == "oda_conformance_pending"


# --- TP-E: 면제(waive) ----------------------------------------------------

def test_apply_waiver_nothing_to_waive(monkeypatch):
    monkeypatch.setattr(oda_conformance, "_load", lambda pid: {
        "mode": "ODA_STANDARD", "conformance": {"violations": []}})
    err = oda_conformance.apply_waiver("PRO-1", "사유")
    assert err and err["reason"] == "nothing_to_waive"


def test_apply_waiver_records_reason(monkeypatch):
    saved = {}
    monkeypatch.setattr(oda_conformance, "_load", lambda pid: {
        "mode": "ODA_STANDARD", "conformance": {"violations": [{"rule": "x"}]}})

    class _Sess:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def run(self, q, **kw): saved.update(kw)
    monkeypatch.setattr(oda_conformance, "get_session", lambda: _Sess())

    err = oda_conformance.apply_waiver("PRO-1", "리스크 수용")
    assert err is None
    persisted = json.loads(saved["conf"])
    assert persisted["gateResult"] == "WAIVED"
    assert persisted["waiver"]["reason"] == "리스크 수용"


def test_waive_request_model():
    assert WaiveConformanceRequest(reason="r").reason == "r"


# --- TP-F: 지식 루트 해석 (FR-014) ----------------------------------------

def test_resolve_knowledge_root_env(monkeypatch, tmp_path):
    (tmp_path / "sid").mkdir()
    (tmp_path / "repo" / "usecase-library").mkdir(parents=True)
    monkeypatch.setenv("ODA_KNOWLEDGE_ROOT", str(tmp_path))
    assert oda_runner.resolve_knowledge_root() == str(tmp_path)


def test_resolve_knowledge_root_none(monkeypatch, tmp_path):
    monkeypatch.setenv("ODA_KNOWLEDGE_ROOT", str(tmp_path / "nope"))
    monkeypatch.setattr(oda_runner, "_FALLBACK_ROOT", str(tmp_path / "missing"))
    monkeypatch.chdir(tmp_path)  # walk-up 에도 sid/+usecase-library 없음
    assert oda_runner.resolve_knowledge_root() is None


# --- TP-G: 스킬 결과 파서 (FR-003/013) ------------------------------------

def test_parse_intent_result_recomputes_gate():
    # 스킬이 gateResult 를 잘못(PASS) 줬어도 violations 로 재계산(FAIL).
    data = {
        "alignment": {"componentBlock": "coreFunction"},
        "conformance": {"gateResult": "PASS", "violations": [{"rule": "broke"}],
                        "items": [{"element": "x", "classification": "NEW"}]},
        "strategicDiff": {"version": 1, "userStories": [{"entityTitle": "T"}]},
        "journeys": [],
    }
    out = oda_runner.parse_intent_result(data)
    assert out["conformance"]["gateResult"] == "FAIL"  # 백엔드가 차단 권위
    assert out["alignment"]["componentBlock"] == "coreFunction"
    assert out["strategicDiff"]["userStories"][0]["entityTitle"] == "T"


def test_parse_plan_result_shape():
    data = {
        "conformance": {"violations": [], "items": [{"element": "a", "classification": "REUSE"}]},
        "tacticalDiff": [{"tempId": "agg1"}],
        "artifacts": {"contracts": [{"api": "TMF629"}], "featureFiles": [{"filename": "f.feature"}]},
    }
    out = oda_runner.parse_plan_result(data)
    assert out["conformance"]["gateResult"] == "PASS"
    assert out["tacticalDiff"][0]["tempId"] == "agg1"
    assert out["artifacts"]["contracts"][0]["api"] == "TMF629"


def test_parse_intent_result_empty_safe():
    out = oda_runner.parse_intent_result({})
    # 빈 conformance 는 아직 점검 전 → PENDING(차단도 PASS 도 아님).
    assert out["conformance"]["gateResult"] == "PENDING"
    assert out["strategicDiff"] == {} and out["alignment"] == {}
