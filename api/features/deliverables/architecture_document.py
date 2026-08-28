"""Session 단위 설계 산출물 스냅샷 빌더.

기준 템플릿(`local-msaez` `DocumentTemplate.vue`)의 8개 섹션 구성을 그대로
유지하면서, 데이터 출처만 Robo Architect 그래프로 바꾼다. 섹션 키와 추적성
매트릭스의 행 구조는 기준 템플릿과 동일한 이름을 쓴다.

    userScenario / valueStream / boundedContext / aggregateDesign /
    eventStorming / apiSpecification / aggregateDetail / traceabilityMatrix

기존 내보내기와의 결정적 차이는 **범위**다. `ExportDocumentTemplate.vue` 는
`/api/contexts` 전역을 읽어 같은 Neo4j 에 남아 있는 다른 세션·analyzer 잔여
데이터까지 한 문서에 섞는다. 여기서는 모든 조회를 `session_id` 로 고정해
하나의 Ingestion 세션만 담는다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from api.features.deliverables.aggregate_export import build_aggregate_payloads
from api.features.deliverables.api_contract import build_api_contracts
from api.features.ingestion.hybrid.ontology.neo4j_ops import fetch_session_snapshot
from api.features.ingestion.hybrid.pipeline_verification import verify_pipeline_status
from api.platform.neo4j import get_session
from api.platform.neo4j_helpers import build_context_full_tree

# 기준 템플릿의 섹션 선택 순서. 프런트엔드 체크박스 순서와 목차 번호가 이 배열을
# 따른다.
SECTION_KEYS = [
    "userScenario",
    "valueStream",
    "boundedContext",
    "aggregateDesign",
    "eventStorming",
    "apiSpecification",
    "aggregateDetail",
    "traceabilityMatrix",
]

# 기준 템플릿 `traceabilityMatrix.types` 와 동일한 키. BoundedContext 는 기준
# 템플릿에서 'service' 로 표기한다.
_TRACE_TYPE_BY_LABEL = {
    "BoundedContext": "service",
    "Aggregate": "aggregate",
    "Command": "command",
    "Event": "event",
    "Policy": "policy",
    "ReadModel": "readModel",
}

_DOMAIN_ORDER = {"Core Domain": 0, "Supporting Domain": 1, "Generic Domain": 2}


def _display(node: dict) -> str:
    return node.get("displayName") or node.get("name") or ""


def _us_name(us: dict) -> str:
    """기준 템플릿의 사용자 스토리 표기(`역할: 행위`)를 맞춘다."""
    role = us.get("role") or "user"
    action = us.get("action") or ""
    return f"{role}: {action}"


# ---------------------------------------------------------------------------
# 1. 사용자 시나리오 — User Story + 원문 근거(DocumentPassage)
# ---------------------------------------------------------------------------


def _build_user_scenario(session_id: str, snapshot: dict, bc_name_by_us: dict[str, str]) -> dict:
    """User Story 를 원문 출처와 함께 반환한다.

    기준 템플릿은 `projectInfo.userStory` 원문을 문단으로 잘라 그대로 싣는다.
    Robo Architect 는 정규화된 User Story 를 만들므로, 원문 문맥은 승격 출처인
    BpmTask 의 DocumentPassage(page/heading/원문 텍스트)로 대신한다. 비개발자가
    "이 스토리가 문서 어디서 나왔는지" 확인할 수 있게 하는 것이 목적이다.
    """
    passages_by_task: dict[str, list[dict]] = {}
    section_by_task: dict[str, str] = {}
    task_name_by_id: dict[str, str] = {}
    for task in snapshot.get("tasks") or []:
        task_name_by_id[task["id"]] = task.get("name") or ""
        section_by_task[task["id"]] = task.get("source_section") or ""
        passages_by_task[task["id"]] = [
            {
                "passageId": p.get("id"),
                "page": p.get("page"),
                "heading": p.get("heading"),
                "text": p.get("text"),
                "score": p.get("score"),
                "rank": p.get("rank"),
                "lowConfidence": bool(p.get("low_confidence")),
            }
            for p in (task.get("document_passages") or [])
        ]

    query = """
    MATCH (us:UserStory {session_id: $sid})
    RETURN us {.id, .role, .action, .benefit, .priority, .status,
               .sourceUnitId, .uiDescription, .acceptanceCriteria, .sequence} AS us
    ORDER BY coalesce(us.sequence, 9999), us.id
    """
    stories: list[dict] = []
    with get_session() as s:
        for rec in s.run(query, sid=session_id):
            us = dict(rec["us"])
            task_id = us.get("sourceUnitId") or ""
            sources = passages_by_task.get(task_id, [])
            stories.append(
                {
                    "id": us.get("id"),
                    "name": _us_name(us),
                    "role": us.get("role"),
                    "action": us.get("action"),
                    "benefit": us.get("benefit"),
                    "priority": us.get("priority"),
                    "status": us.get("status"),
                    "uiDescription": us.get("uiDescription"),
                    "acceptanceCriteria": us.get("acceptanceCriteria") or [],
                    "bcName": bc_name_by_us.get(us.get("id"), ""),
                    "sourceTask": (
                        {
                            "id": task_id,
                            "name": task_name_by_id.get(task_id, ""),
                            "sourceSection": section_by_task.get(task_id, ""),
                        }
                        if task_id
                        else None
                    ),
                    "sources": sources,
                }
            )

    grounded = sum(1 for s_ in stories if s_["sources"])
    return {
        "stories": stories,
        "summary": {
            "total": len(stories),
            "grounded": grounded,
            "ungrounded": len(stories) - grounded,
        },
    }


# ---------------------------------------------------------------------------
# 2. Value Stream — BPM Process / Actor / Task / Gateway
# ---------------------------------------------------------------------------


def _build_value_stream(snapshot: dict, promoted_us_by_task: dict[str, list[dict]]) -> dict:
    """프로세스별 Actor 포함 선형 흐름을 만든다.

    기준 템플릿의 `getValueStreamLinearPages` 는 `{name, displayName, actor}`
    배열의 배열(path)을 그린다. 그 계약을 그대로 유지하되, 근거를 ES Event 체인
    대신 실제 BPM Task 순서로 둔다. 문서에서 뽑아낸 업무 흐름이 최종 설계서에
    남지 않던 공백(`swimlanes = []`)을 메우는 부분이다.
    """
    actor_name_by_id = {a["id"]: (a.get("label") or a.get("name") or "") for a in (snapshot.get("actors") or [])}

    tasks_by_process: dict[str, list[dict]] = {}
    for task in snapshot.get("tasks") or []:
        tasks_by_process.setdefault(task.get("process_id") or "", []).append(task)

    processes = []
    for proc in snapshot.get("processes") or []:
        pid = proc.get("id")
        ordered = sorted(
            tasks_by_process.get(pid, []),
            key=lambda t: (t.get("sequence_index") if t.get("sequence_index") is not None else 9999),
        )
        path = []
        for task in ordered:
            actor_ids = task.get("actor_ids") or []
            path.append(
                {
                    "name": task.get("id"),
                    "displayName": task.get("name") or "",
                    "actor": ", ".join(actor_name_by_id.get(aid, "") for aid in actor_ids).strip(", "),
                    "description": task.get("description") or "",
                    "sourceSection": task.get("source_section") or "",
                    # 승격 결과를 프로세스 단계에 함께 표시 — Task 가 어떤 User
                    # Story 가 됐는지 문서에서 바로 보이게 한다.
                    "promotedTo": promoted_us_by_task.get(task.get("id"), []),
                }
            )
        processes.append(
            {
                "id": pid,
                "name": proc.get("name") or "",
                "description": proc.get("description") or "",
                "actors": sorted({actor_name_by_id.get(aid, "") for t in ordered for aid in (t.get("actor_ids") or [])} - {""}),
                "taskCount": len(ordered),
                # 기준 템플릿의 path 계약 — 한 프로세스가 하나의 선형 경로.
                "linearPaths": [path] if path else [],
            }
        )

    return {
        "processes": processes,
        "actors": [{"id": a["id"], "name": a.get("label") or a.get("name") or "", "description": a.get("description") or ""} for a in (snapshot.get("actors") or [])],
        "glossary": snapshot.get("glossary") or [],
        "bpmnXml": snapshot.get("bpmn_xml") or "",
    }


# ---------------------------------------------------------------------------
# 3. 추적성 매트릭스
# ---------------------------------------------------------------------------


def _fetch_direct_links(session_id: str) -> dict[str, list[dict]]:
    """`(UserStory)-[:IMPLEMENTS]->(element)` 직접 매핑을 element 기준으로 모은다."""
    query = """
    MATCH (us:UserStory {session_id: $sid})-[:IMPLEMENTS]->(n)
    WHERE n:BoundedContext OR n:Aggregate OR n:Command OR n:Event
       OR n:Policy OR n:ReadModel
    RETURN n.id AS element_id, labels(n) AS labels,
           us {.id, .role, .action} AS us
    """
    by_element: dict[str, list[dict]] = {}
    with get_session() as s:
        for rec in s.run(query, sid=session_id):
            by_element.setdefault(rec["element_id"], []).append(dict(rec["us"]))
    return by_element


def _collect_elements(trees: list[dict]) -> list[dict]:
    """BC full-tree 들을 추적성 행 후보(요소) 목록으로 평탄화한다."""
    elements: list[dict] = []
    for tree in trees:
        bc_label = _display(tree)
        elements.append(
            {
                "type": _TRACE_TYPE_BY_LABEL["BoundedContext"],
                "id": tree.get("id"),
                "name": bc_label,
                "technical": tree.get("name"),
                "parent": "",
                "parentAggregateId": None,
            }
        )
        for agg in tree.get("aggregates") or []:
            agg_label = _display(agg)
            elements.append(
                {
                    "type": _TRACE_TYPE_BY_LABEL["Aggregate"],
                    "id": agg.get("id"),
                    "name": agg_label,
                    "technical": agg.get("name"),
                    "parent": bc_label,
                    "parentAggregateId": agg.get("id"),
                }
            )
            for cmd in agg.get("commands") or []:
                elements.append(
                    {
                        "type": _TRACE_TYPE_BY_LABEL["Command"],
                        "id": cmd.get("id"),
                        "name": _display(cmd),
                        "technical": cmd.get("name"),
                        "parent": agg_label,
                        "parentAggregateId": agg.get("id"),
                    }
                )
                for evt in cmd.get("events") or []:
                    elements.append(
                        {
                            "type": _TRACE_TYPE_BY_LABEL["Event"],
                            "id": evt.get("id"),
                            "name": _display(evt),
                            "technical": evt.get("name"),
                            "parent": agg_label,
                            "parentAggregateId": agg.get("id"),
                        }
                    )
            for evt in agg.get("events") or []:
                elements.append(
                    {
                        "type": _TRACE_TYPE_BY_LABEL["Event"],
                        "id": evt.get("id"),
                        "name": _display(evt),
                        "technical": evt.get("name"),
                        "parent": agg_label,
                        "parentAggregateId": agg.get("id"),
                    }
                )
        for pol in tree.get("policies") or []:
            elements.append(
                {
                    "type": _TRACE_TYPE_BY_LABEL["Policy"],
                    "id": pol.get("id"),
                    "name": _display(pol),
                    "technical": pol.get("name"),
                    "parent": bc_label,
                    "parentAggregateId": None,
                }
            )
        for rm in tree.get("readmodels") or []:
            elements.append(
                {
                    "type": _TRACE_TYPE_BY_LABEL["ReadModel"],
                    "id": rm.get("id"),
                    "name": _display(rm),
                    "technical": rm.get("name"),
                    "parent": bc_label,
                    "parentAggregateId": None,
                }
            )

    # 같은 요소가 여러 경로로 잡히는 경우(예: Command 아래 Event 와 Aggregate 아래
    # Event) 한 번만 남긴다.
    deduped: dict[str, dict] = {}
    for el in elements:
        if el["id"] and el["id"] not in deduped:
            deduped[el["id"]] = el
    return list(deduped.values())


def _build_traceability_matrix(session_id: str, trees: list[dict]) -> dict:
    """기준 템플릿 `traceabilityMatrixGroups` 와 같은 형태로 조립한다.

    반환 구조: `{groups: [{us, rows}], inferred: [...], unmapped: [...]}`.

    provenance 규칙도 기준 템플릿을 따른다.

    - `direct`   — 요소에 US 직접 연결(IMPLEMENTS)이 있다.
    - `inferred` — 직접 연결은 없지만 상위 Aggregate 의 매핑을 상속했다.
    - 그 외      — 미매핑으로 남긴다. 근거 없는 요소를 BC 의 모든 US 에 붙이는
      식의 대량 거짓 매핑은 만들지 않는다.
    """
    direct = _fetch_direct_links(session_id)
    elements = _collect_elements(trees)

    # Aggregate 별 US 매핑 캐시 — 하위 요소의 추론 상속에 쓴다.
    agg_us_cache = {el["id"]: direct.get(el["id"], []) for el in elements if el["type"] == "aggregate"}

    groups: dict[str, dict] = {}
    unmapped: list[dict] = []
    inferred: list[dict] = []
    stats = {"direct": 0, "inferred": 0, "unmapped": 0}

    for el in elements:
        us_list = direct.get(el["id"]) or []
        provenance = "direct"

        if not us_list:
            parent_id = el.get("parentAggregateId")
            if parent_id and parent_id != el["id"] and agg_us_cache.get(parent_id):
                us_list = agg_us_cache[parent_id]
                provenance = "inferred"

        if not us_list:
            stats["unmapped"] += 1
            unmapped.append(
                {
                    "type": el["type"],
                    "name": el["name"],
                    "technical": el["technical"],
                    "parent": el["parent"],
                    "id": el["id"],
                }
            )
            continue

        if provenance == "inferred":
            stats["inferred"] += 1
            inferred.append(
                {
                    "type": el["type"],
                    "name": el["name"],
                    "parent": el["parent"],
                    "inferredUs": ", ".join(u["id"] for u in us_list),
                }
            )
            continue

        stats["direct"] += 1
        for us in us_list:
            key = us["id"]
            group = groups.setdefault(key, {"us": {"id": us["id"], "name": _us_name(us)}, "rows": []})
            group["rows"].append(
                {
                    "type": el["type"],
                    "name": el["name"],
                    "technical": el["technical"],
                    "parent": el["parent"],
                    "id": el["id"],
                    "provenance": provenance,
                }
            )

    total = stats["direct"] + stats["inferred"] + stats["unmapped"]
    return {
        "groups": sorted(groups.values(), key=lambda g: g["us"]["id"]),
        "inferred": inferred,
        "unmapped": unmapped,
        "summary": {
            "elements": total,
            "directElements": stats["direct"],
            "inferredElements": stats["inferred"],
            "unmappedElements": stats["unmapped"],
            "mappedUserStories": len(groups),
            "directRatio": round(stats["direct"] / total, 4) if total else 0.0,
        },
    }


# ---------------------------------------------------------------------------
# 조립
# ---------------------------------------------------------------------------


def _fetch_session_contexts(session_id: str) -> list[dict]:
    query = """
    MATCH (bc:BoundedContext {session_id: $sid})
    RETURN bc {.id, .name, .displayName, .domainType} AS bc
    """
    with get_session() as s:
        rows = [dict(rec["bc"]) for rec in s.run(query, sid=session_id)]
    return sorted(rows, key=lambda b: (_DOMAIN_ORDER.get(b.get("domainType"), 9), b.get("name") or ""))


def _fetch_promoted_map(session_id: str) -> tuple[dict[str, list[dict]], dict[str, str]]:
    """`task_id -> [User Story]` 와 `us_id -> BC 표시명` 을 함께 만든다."""
    query = """
    MATCH (t:BpmTask {session_id: $sid})-[:PROMOTED_TO]->(us:UserStory {session_id: $sid})
    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(bc:BoundedContext {session_id: $sid})
    RETURN t.id AS task_id, us {.id, .role, .action} AS us,
           bc {.name, .displayName} AS bc
    """
    by_task: dict[str, list[dict]] = {}
    bc_by_us: dict[str, str] = {}
    with get_session() as s:
        for rec in s.run(query, sid=session_id):
            us = dict(rec["us"])
            by_task.setdefault(rec["task_id"], []).append({"id": us.get("id"), "name": _us_name(us)})
            bc = rec.get("bc")
            if bc:
                bc_by_us[us.get("id")] = _display(dict(bc))
    return by_task, bc_by_us


def fetch_session_trees(session_id: str) -> list[dict]:
    """세션에 속한 BC 들의 full-tree 를 도메인 유형 순으로 반환한다.

    문서 전체가 필요 없는 소비자(Aggregate JSON 내보내기 등)가 스냅샷 조립
    비용을 치르지 않도록 분리해 둔다.
    """
    trees = []
    for ctx in _fetch_session_contexts(session_id):
        tree = build_context_full_tree(ctx["id"])
        if tree:
            trees.append(tree)
    return trees


def build_architecture_document(session_id: str) -> dict[str, Any] | None:
    """Session 하나를 기준으로 설계 산출물 스냅샷을 조립한다.

    세션에 Bounded Context 가 하나도 없으면 None (라우트가 404 로 변환).
    """
    contexts = _fetch_session_contexts(session_id)
    if not contexts:
        return None

    snapshot = fetch_session_snapshot(session_id)
    promoted_by_task, bc_name_by_us = _fetch_promoted_map(session_id)

    # ES 계열 4개 섹션(boundedContext / aggregateDesign / eventStorming /
    # apiSpecification / aggregateDetail)은 기존 full-tree 계약을 그대로 쓴다.
    # 현재 내보내기 템플릿이 이미 이 구조를 렌더링하고 있어, 재구현하지 않고
    # 범위만 세션으로 좁히는 것이 목적이다.
    trees = fetch_session_trees(session_id)

    return {
        "sessionId": session_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sectionKeys": SECTION_KEYS,
        "projectInfo": {
            "projectName": (snapshot.get("processes") or [{}])[0].get("name") or session_id,
            "sessionId": session_id,
            "processCount": len(snapshot.get("processes") or []),
            "taskCount": len(snapshot.get("tasks") or []),
        },
        "readiness": verify_pipeline_status(session_id),
        "userScenario": _build_user_scenario(session_id, snapshot, bc_name_by_us),
        "valueStream": _build_value_stream(snapshot, promoted_by_task),
        "boundedContexts": contexts,
        "eventStorming": {"contexts": trees},
        "apiSpecification": build_api_contracts(trees),
        "aggregateExport": build_aggregate_payloads(trees),
        "traceabilityMatrix": _build_traceability_matrix(session_id, trees),
    }
