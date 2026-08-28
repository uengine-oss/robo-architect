from __future__ import annotations

from api.features.deliverables import architecture_document as ad


def _tree():
    """BC 하나짜리 full-tree 축소본 — `build_context_full_tree` 반환 형태."""
    return {
        "id": "bc-1",
        "name": "OrderManagement",
        "displayName": "주문 관리",
        "aggregates": [
            {
                "id": "agg-1",
                "name": "Order",
                "displayName": "주문",
                "commands": [
                    {
                        "id": "cmd-1",
                        "name": "PlaceOrder",
                        "displayName": "주문 생성",
                        "events": [{"id": "evt-1", "name": "OrderPlaced", "displayName": "주문 생성됨"}],
                    }
                ],
                # Command 아래에서 이미 잡힌 Event 가 Aggregate 아래에도 나타나는 경우
                "events": [{"id": "evt-1", "name": "OrderPlaced", "displayName": "주문 생성됨"}],
            }
        ],
        "policies": [{"id": "pol-1", "name": "NotifyOnPlaced", "displayName": "생성 시 알림"}],
        "readmodels": [{"id": "rm-1", "name": "OrderDetail", "displayName": "주문 상세"}],
    }


def test_collect_elements_dedupes_events_seen_twice():
    els = ad._collect_elements([_tree()])
    ids = [e["id"] for e in els]

    assert ids.count("evt-1") == 1
    assert {e["type"] for e in els} == {"service", "aggregate", "command", "event", "policy", "readModel"}


def test_traceability_direct_and_inferred(monkeypatch):
    """직접 IMPLEMENTS 가 있으면 direct, 없으면 상위 Aggregate 매핑을 상속한다."""
    monkeypatch.setattr(
        ad,
        "_fetch_direct_links",
        lambda sid: {
            "bc-1": [{"id": "US-001", "role": "고객", "action": "주문한다"}],
            "agg-1": [{"id": "US-001", "role": "고객", "action": "주문한다"}],
            # cmd-1 / evt-1 은 직접 연결 없음 → agg-1 상속
            # pol-1 / rm-1 은 Aggregate 부모가 없으므로 미매핑
        },
    )
    m = ad._build_traceability_matrix("sid", [_tree()])

    assert [g["us"]["id"] for g in m["groups"]] == ["US-001"]
    assert {r["type"] for r in m["groups"][0]["rows"]} == {"service", "aggregate"}
    assert all(r["provenance"] == "direct" for r in m["groups"][0]["rows"])

    assert {r["type"] for r in m["inferred"]} == {"command", "event"}
    assert m["inferred"][0]["inferredUs"] == "US-001"

    # 근거 없는 요소를 BC 의 US 전체에 붙이지 않고 정직하게 미매핑으로 남긴다.
    assert {r["type"] for r in m["unmapped"]} == {"policy", "readModel"}

    assert m["summary"] == {
        "elements": 6,
        "directElements": 2,
        "inferredElements": 2,
        "unmappedElements": 2,
        "mappedUserStories": 1,
        "directRatio": round(2 / 6, 4),
    }


def test_traceability_all_unmapped_when_no_links(monkeypatch):
    monkeypatch.setattr(ad, "_fetch_direct_links", lambda sid: {})
    m = ad._build_traceability_matrix("sid", [_tree()])

    assert m["groups"] == []
    assert m["inferred"] == []
    assert len(m["unmapped"]) == 6
    assert m["summary"]["directRatio"] == 0.0


def _snapshot():
    return {
        "processes": [{"id": "proc-1", "name": "주문 처리", "description": "설명"}],
        "actors": [
            {"id": "actor-1", "label": "고객", "description": "주문자"},
            {"id": "actor-2", "label": "상담사", "description": "지원"},
        ],
        "tasks": [
            {"id": "task-2", "process_id": "proc-1", "name": "검증", "sequence_index": 1, "actor_ids": ["actor-2"]},
            {"id": "task-1", "process_id": "proc-1", "name": "접수", "sequence_index": 0, "actor_ids": ["actor-1"], "source_section": "1단계"},
            # sequence_index 가 없는 Task 는 뒤로 밀린다.
            {"id": "task-3", "process_id": "proc-1", "name": "종료", "sequence_index": None, "actor_ids": []},
        ],
        "glossary": [{"term": "자동납부"}],
        "bpmn_xml": "<xml/>",
    }


def test_value_stream_orders_tasks_and_resolves_actors():
    vs = ad._build_value_stream(_snapshot(), {"task-1": [{"id": "US-001", "name": "고객: 주문한다"}]})
    path = vs["processes"][0]["linearPaths"][0]

    assert [step["displayName"] for step in path] == ["접수", "검증", "종료"]
    assert [step["actor"] for step in path] == ["고객", "상담사", ""]
    assert path[0]["promotedTo"] == [{"id": "US-001", "name": "고객: 주문한다"}]
    assert path[0]["sourceSection"] == "1단계"
    assert vs["processes"][0]["actors"] == ["고객", "상담사"]
    assert vs["processes"][0]["taskCount"] == 3
    assert vs["bpmnXml"] == "<xml/>"


def test_value_stream_process_without_tasks_has_no_path():
    snap = _snapshot()
    snap["tasks"] = []
    vs = ad._build_value_stream(snap, {})

    assert vs["processes"][0]["linearPaths"] == []
    assert vs["processes"][0]["taskCount"] == 0


def test_section_keys_match_reference_template():
    """기준 템플릿(DocumentTemplate.vue)의 섹션 구성과 순서를 유지한다."""
    assert ad.SECTION_KEYS == [
        "userScenario",
        "valueStream",
        "boundedContext",
        "aggregateDesign",
        "eventStorming",
        "apiSpecification",
        "aggregateDetail",
        "traceabilityMatrix",
    ]
