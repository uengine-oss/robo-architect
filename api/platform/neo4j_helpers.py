"""
공통 Neo4j 헬퍼. 038 effect_analyzer.load_domain_nodes에서 승격.
양쪽 feature(038, 039)에서 공용으로 사용.

040: read-only 그래프 슬라이스 빌더를 플랫폼 계층으로 승격 — 라이브 read 엔드포인트와
Proposal 미리보기(오버레이 투영)가 동일한 읽기 로직을 공유한다(Constitution V: 교차
의존은 sibling 직접 임포트가 아니라 플랫폼 경유). 모든 함수는 **읽기 전용**이다.
"""

from __future__ import annotations

import json
from typing import Any

from api.platform.neo4j import get_session


def load_domain_nodes(limit: int = 200) -> list[dict]:
    """UserStory·BoundedContext·Aggregate·Feature 노드 목록을 Neo4j에서 조회한다."""
    query = """
    MATCH (n)
    WHERE n:UserStory OR n:BoundedContext OR n:Aggregate OR n:Feature
    RETURN n.id AS id,
           labels(n)[0] AS label,
           COALESCE(n.title, n.name, n.action, n.key, '') AS name
    LIMIT $limit
    """
    with get_session() as session:
        result = session.run(query, limit=limit)
        return result.data()


def resolve_bc_id_for_node(node_id: str) -> str | None:
    """임의의 도메인 노드 id가 속한 BoundedContext id를 해소한다(읽기 전용).

    Aggregate/Command/Event/ReadModel/UI 등 BC 하위 노드면 그 BC를 반환.
    노드 자체가 BC면 그대로 반환. 없으면 None.
    """
    query = """
    MATCH (n {id: $id})
    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE|HAS_POLICY|HAS_READMODEL|HAS_UI*1..3]->(n)
    WITH n, bc
    RETURN CASE WHEN n:BoundedContext THEN n.id ELSE coalesce(bc.id, n.bcId) END AS bcId
    LIMIT 1
    """
    with get_session() as session:
        rec = session.run(query, id=node_id).single()
        return rec["bcId"] if rec and rec.get("bcId") else None


def build_context_full_tree(context_id: str) -> dict[str, Any] | None:
    """BC 하위 전체 트리(정규화 구조)를 읽기 전용으로 조립해 반환한다.

    `GET /api/contexts/{id}/full-tree` 의 순수 빌더. 라우트는 이 함수를 호출하고
    요청 스코프 로깅만 담당한다. Proposal Data 미리보기도 이 함수로 라이브 슬라이스를
    얻은 뒤 오버레이를 얹는다. BC가 없으면 None.
    """
    bc_query = """
    MATCH (bc:BoundedContext {id: $context_id})
    RETURN bc {.id, .name, .displayName, .description, .owner, .domainType, .classification, .userStoryIds} as bc
    """
    us_query = """
    MATCH (us:UserStory)-[:IMPLEMENTS]->(bc:BoundedContext {id: $context_id})
    RETURN us {.id, .role, .action, .benefit, .priority, .status} as userStory
    ORDER BY us.id
    """
    agg_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_AGGREGATE]->(agg:Aggregate)
    RETURN agg {.id, .name, .displayName, .rootEntity, .invariants, .enumerations, .valueObjects, .exceptions} as aggregate
    ORDER BY agg.name
    """
    cmd_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)
    RETURN agg.id as aggregateId, cmd {.id, .name, .displayName, .actor, .category, .inputSchema} as command
    ORDER BY cmd.name
    """
    evt_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(evt:Event)
    RETURN agg.id as aggregateId, cmd.id as commandId, evt {.id, .name, .displayName, .version, .payload} as event
    ORDER BY evt.name
    """
    pol_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_POLICY]->(pol:Policy)
    OPTIONAL MATCH (evt:Event)-[:TRIGGERS]->(pol)
    OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
    RETURN pol {.id, .name, .displayName, .description} as policy,
           evt.id as triggerEventId,
           cmd.id as invokeCommandId
    ORDER BY pol.name
    """
    rm_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_READMODEL]->(rm:ReadModel)
    RETURN rm {.id, .name, .displayName, .description, .provisioningType, .actor, .isMultipleResult} as readmodel
    ORDER BY readmodel.name
    """
    ui_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_UI]->(ui:UI)
    RETURN ui {.id, .name, .displayName, .description, .template, .attachedToId, .attachedToType, .attachedToName, .userStoryId} as ui
    ORDER BY ui.name
    """
    inv_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_INVARIANT]->(inv:Invariant)
    OPTIONAL MATCH (inv)-[:VERIFIED_BY]->(c:Command)
    OPTIONAL MATCH (inv)-[:HAS_GWT]->(g:GWT)
    WITH agg.id AS aggregateId, inv,
         count(DISTINCT c) AS refCount, count(DISTINCT g) AS ownCount
    RETURN aggregateId,
           inv {.id, .key, .name, .declaration, .source, .seq} AS invariant,
           refCount, ownCount
    ORDER BY coalesce(inv.seq, 0), inv.declaration
    """
    cqrs_ops_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_READMODEL]->(rm:ReadModel)-[:HAS_CQRS]->(cqrs:CQRSConfig)-[:HAS_OPERATION]->(op:CQRSOperation)
    OPTIONAL MATCH (op)-[:TRIGGERED_BY]->(evt:Event)
    RETURN rm.id as readmodelId,
           op {.id, .operationType, .triggerEventId} as operation,
           evt.name as triggerEventName
    ORDER BY rm.id, op.operationType
    """

    with get_session() as session:
        bc_record = session.run(bc_query, context_id=context_id).single()
        if not bc_record:
            return None
        bc = dict(bc_record["bc"])
        bc["type"] = "BoundedContext"

        # User Stories
        user_stories = []
        for record in session.run(us_query, context_id=context_id):
            us = dict(record["userStory"])
            us["type"] = "UserStory"
            us["name"] = f"{us.get('role', 'user')}: {us.get('action', '')[:30]}..."
            user_stories.append(us)

        # Aggregates
        aggregates: dict[str, Any] = {}
        for record in session.run(agg_query, context_id=context_id):
            agg = dict(record["aggregate"])
            agg["type"] = "Aggregate"
            agg["commands"] = []
            agg["events"] = []
            for fld in ("enumerations", "valueObjects", "exceptions"):
                v = agg.get(fld)
                if isinstance(v, str):
                    try:
                        agg[fld] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        agg[fld] = []
                elif v is None:
                    agg[fld] = []
            aggregates[agg["id"]] = agg

        # Commands
        commands_map: dict[str, Any] = {}
        for record in session.run(cmd_query, context_id=context_id):
            agg_id = record["aggregateId"]
            cmd = dict(record["command"])
            cmd["type"] = "Command"
            cmd["events"] = []
            if agg_id in aggregates:
                aggregates[agg_id]["commands"].append(cmd)
                commands_map[cmd["id"]] = cmd

        # Events
        for record in session.run(evt_query, context_id=context_id):
            agg_id = record["aggregateId"]
            cmd_id = record["commandId"]
            evt = dict(record["event"])
            evt["type"] = "Event"
            if cmd_id in commands_map:
                commands_map[cmd_id]["events"].append(evt)
            if agg_id in aggregates:
                aggregates[agg_id]["events"].append(evt)

        # Policies
        policies = []
        for record in session.run(pol_query, context_id=context_id):
            pol = dict(record["policy"])
            pol["type"] = "Policy"
            pol["triggerEventId"] = record["triggerEventId"]
            pol["invokeCommandId"] = record["invokeCommandId"]
            policies.append(pol)

        # ReadModels
        readmodels = []
        readmodels_map: dict[str, Any] = {}
        for record in session.run(rm_query, context_id=context_id):
            rm = dict(record["readmodel"])
            rm["type"] = "ReadModel"
            rm["properties"] = []
            rm["operations"] = []
            readmodels.append(rm)
            readmodels_map[rm["id"]] = rm

        # CQRS Operations
        for record in session.run(cqrs_ops_query, context_id=context_id):
            rm_id = record["readmodelId"]
            if rm_id in readmodels_map and record["operation"]:
                op = dict(record["operation"])
                op["type"] = "CQRSOperation"
                op["triggerEventName"] = record["triggerEventName"]
                readmodels_map[rm_id]["operations"].append(op)

        # UI wireframes
        uis = []
        for record in session.run(ui_query, context_id=context_id):
            ui = dict(record["ui"])
            ui["type"] = "UI"
            uis.append(ui)

        # Invariants per Aggregate (027) — overwrites legacy invariants string list.
        invariants_map: dict[str, list[dict[str, Any]]] = {}
        for record in session.run(inv_query, context_id=context_id):
            agg_id = record["aggregateId"]
            inv = dict(record["invariant"])
            inv["type"] = "Invariant"
            inv["seq"] = int(inv.get("seq") or 0)
            inv["referencedCommandCount"] = int(record["refCount"] or 0)
            inv["isSpecified"] = (record["refCount"] or 0) > 0 or (record["ownCount"] or 0) > 0
            invariants_map.setdefault(agg_id, []).append(inv)
        for agg in aggregates.values():
            agg["invariants"] = invariants_map.get(agg.get("id", ""), [])

        bc["userStories"] = user_stories
        bc["aggregates"] = list(aggregates.values())
        bc["policies"] = policies
        bc["readmodels"] = readmodels
        bc["uis"] = uis

        # Properties + implementationFiles attach
        agg_ids = list(aggregates.keys())
        cmd_ids = list(commands_map.keys())
        evt_ids: list[str] = []
        for a in aggregates.values():
            for e in a.get("events", []) or []:
                if e and e.get("id"):
                    evt_ids.append(e["id"])
            for c in a.get("commands", []) or []:
                for e in c.get("events", []) or []:
                    if e and e.get("id"):
                        evt_ids.append(e["id"])
        rm_ids = list(readmodels_map.keys())
        parent_ids = [*agg_ids, *cmd_ids, *evt_ids, *rm_ids]

        if parent_ids:
            prop_query = """
            UNWIND $parent_ids as pid
            MATCH (prop:Property {parentId: pid})
            WITH pid, prop
            ORDER BY coalesce(prop.isKey, false) DESC,
                     coalesce(prop.isForeignKey, false) DESC,
                     prop.name ASC
            WITH pid, collect(prop {
                .id, .name, .displayName, .type, .description,
                .isKey, .isForeignKey, .isRequired,
                .parentType, .parentId
            }) as properties
            RETURN pid as parentId, properties
            """
            prop_map: dict[str, list[dict[str, Any]]] = {}
            for r in session.run(prop_query, parent_ids=parent_ids):
                pid = r.get("parentId")
                props = r.get("properties") or []
                if pid:
                    prop_map[str(pid)] = [dict(p) for p in props if p and p.get("id")]

            for agg in aggregates.values():
                agg["properties"] = prop_map.get(agg.get("id", ""), [])
                for cmd in agg.get("commands", []) or []:
                    cmd["properties"] = prop_map.get(cmd.get("id", ""), [])
                    for evt in cmd.get("events", []) or []:
                        evt["properties"] = prop_map.get(evt.get("id", ""), [])
                for evt in agg.get("events", []) or []:
                    evt["properties"] = prop_map.get(evt.get("id", ""), [])
            for rm in readmodels:
                rm["properties"] = prop_map.get(rm.get("id", ""), [])

            files_query = """
            UNWIND $parent_ids as eid
            MATCH (e {id: eid})-[:IMPLEMENTED_IN]->(impl:ImplementationFile)
            RETURN eid as elementId,
                   collect({
                       id: impl.id,
                       projectId: impl.projectId,
                       path: impl.path,
                       role: impl.role,
                       lastSeenAt: impl.lastSeenAt
                   }) as files
            """
            files_map: dict[str, list[dict[str, Any]]] = {}
            for r in session.run(files_query, parent_ids=parent_ids):
                eid = r.get("elementId")
                if eid:
                    files_map[str(eid)] = [dict(f) for f in (r.get("files") or [])]

            for agg in aggregates.values():
                agg["implementationFiles"] = files_map.get(agg.get("id", ""), [])
                for cmd in agg.get("commands", []) or []:
                    cmd["implementationFiles"] = files_map.get(cmd.get("id", ""), [])
                    for evt in cmd.get("events", []) or []:
                        evt["implementationFiles"] = files_map.get(evt.get("id", ""), [])
                for evt in agg.get("events", []) or []:
                    evt["implementationFiles"] = files_map.get(evt.get("id", ""), [])
            for rm in readmodels:
                rm["implementationFiles"] = files_map.get(rm.get("id", ""), [])

        return bc
