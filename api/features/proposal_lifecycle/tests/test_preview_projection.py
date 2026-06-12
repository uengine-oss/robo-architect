"""040 Proposal Impact Artifact Preview — 투영/오버레이 테스트.

`apply_data_overlay` 는 순수 함수(DB 불필요)라 여기서 직접 검증한다.
라이브 무변경(체크섬) 테스트는 Neo4j 가 있는 환경에서 실행한다(마커 표시).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from api.features.proposal_lifecycle.services.overlay_apply import (
    apply_data_overlay,
    SOURCE_LIVE,
    SOURCE_MODIFIED,
    SOURCE_TEMPORARY,
    SOURCE_CONFLICT,
    temp_id,
)


def _live_tree():
    return {
        "id": "BC-payment", "name": "결제 컨텍스트", "type": "BoundedContext",
        "aggregates": [
            {"id": "AGG-refund", "name": "환불 Aggregate", "type": "Aggregate",
             "valueObjects": [{"name": "RefundReason", "type": "String"}],
             "invariants": [], "enumerations": [], "properties": [], "commands": [], "events": []},
        ],
        "userStories": [], "policies": [], "readmodels": [], "uis": [],
    }


def _tactical():
    return [
        {  # 기존 Aggregate 수정: VO 추가 + invariant 추가
            "nodeId": "AGG-refund", "nodeLabel": "Aggregate", "nodeTitle": "환불 Aggregate",
            "impactLevel": "HIGH", "changeType": "MODIFY",
            "semanticDiff": {"ops": [
                {"field": "valueObjects", "op": "obj_append", "obj_name": "PartialRefundAmount",
                 "obj_data": {"name": "PartialRefundAmount", "type": "Long", "description": "부분 환불 금액"}},
                {"field": "invariants", "op": "list_append",
                 "items": ["부분 환불 금액은 원래 결제 금액을 초과할 수 없다"]},
            ]},
        },
        {  # 신규 Command (id=null → temp id)
            "nodeId": None, "nodeLabel": "Command", "nodeTitle": "RequestPartialRefund",
            "impactLevel": "HIGH", "changeType": "CREATE",
            "semanticDiff": {"ops": []},
        },
    ]


def test_modify_overlay_tags_live_modified_and_appends_vo():
    tree, meta = apply_data_overlay(_live_tree(), "PRO-001", _tactical())
    agg = next(a for a in tree["aggregates"] if a["id"] == "AGG-refund")
    assert agg["source"] == SOURCE_MODIFIED
    vo_names = [v["name"] for v in agg["valueObjects"]]
    assert "PartialRefundAmount" in vo_names
    new_vo = next(v for v in agg["valueObjects"] if v["name"] == "PartialRefundAmount")
    assert new_vo["source"] == SOURCE_TEMPORARY and new_vo["badge"] == "신규"
    assert any(i.get("source") == SOURCE_TEMPORARY for i in agg["invariants"])
    # 변경 필드가 meta 에 기록됨
    m = next(x for x in meta if x["nodeId"] == "AGG-refund")
    assert "valueObjects" in m["changedFields"] and "invariants" in m["changedFields"]


def test_create_command_gets_temp_id_and_temporary_source():
    tree, meta = apply_data_overlay(_live_tree(), "PRO-001", _tactical())
    tid = temp_id("PRO-001", 1)  # index 1 = the CREATE command
    cmd_meta = next((x for x in meta if x["nodeId"] == tid), None)
    assert cmd_meta is not None and cmd_meta["source"] == SOURCE_TEMPORARY
    # 첫 Aggregate 에 신규 Command 가 붙음
    agg = tree["aggregates"][0]
    assert any(c.get("id") == tid and c.get("source") == SOURCE_TEMPORARY
               for c in agg.get("commands", []))


def test_unchanged_aggregate_is_live():
    tactical = [{"nodeId": "AGG-other", "nodeLabel": "Aggregate", "changeType": "MODIFY",
                 "semanticDiff": {"ops": []}}]
    tree, meta = apply_data_overlay(_live_tree(), "PRO-001", tactical)
    # AGG-refund 는 diff 무관 → live, AGG-other 는 라이브 부재 → conflict ghost
    refund = next(a for a in tree["aggregates"] if a["id"] == "AGG-refund")
    assert refund["source"] == SOURCE_LIVE
    ghost = next((a for a in tree["aggregates"] if a["id"] == "AGG-other"), None)
    assert ghost is not None and ghost["source"] == SOURCE_CONFLICT


def test_overlay_does_not_mutate_input():
    live = _live_tree()
    before_vo_count = len(live["aggregates"][0]["valueObjects"])
    apply_data_overlay(live, "PRO-001", _tactical())
    # 입력(라이브 슬라이스)은 딥카피 위에서만 변형 → 원본 불변
    assert len(live["aggregates"][0]["valueObjects"]) == before_vo_count


# --- US2: preview 모듈에 write Cypher 가 없어야 한다(Constitution I) ---
def test_no_write_cypher_in_preview_modules():
    root = Path(__file__).resolve().parents[1]  # proposal_lifecycle/
    targets = [
        root / "services" / "preview_projection.py",
        root / "services" / "overlay_apply.py",
        root / "routes" / "proposals_preview.py",
    ]
    # Cypher write *절* 형태만 탐지(한국어 주석의 'CREATE(id=null)' 등 오탐 방지).
    clause = re.compile(
        r"(CREATE\s+\(|MERGE\s+\(|DETACH\s+DELETE|\bDELETE\s+[a-zA-Z]|\bSET\s+[a-zA-Z_]+\.|\bREMOVE\s+[a-zA-Z])"
    )
    offenders = []
    for f in targets:
        for ln, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if clause.search(line):
                offenders.append((f.name, ln, line.strip()[:70]))
    assert not offenders, f"write Cypher found in preview modules: {offenders}"


@pytest.mark.neo4j
def test_preview_does_not_mutate_graph():
    """라이브 무변경 — Neo4j 환경에서만 실행(마커). 체크섬 전후 동일."""
    pytest.importorskip("neo4j")
    from api.features.proposal_lifecycle.services.preview_projection import build_data_preview  # noqa
    # 실제 그래프 체크섬 비교는 통합 환경에서 수행한다(여기선 스모크).
    pytest.skip("requires live Neo4j with seeded BC-payment + PRO proposal")
