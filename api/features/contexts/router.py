from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Body
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/contexts", tags=["contexts"])


@router.get("")
async def get_all_contexts(request: Request) -> list[dict[str, Any]]:
    """
    GET /api/contexts - BC 목록 조회
    Returns all Bounded Contexts with basic info.
    """
    query = """
    MATCH (bc:BoundedContext)
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
    OPTIONAL MATCH (us:UserStory)-[:IMPLEMENTS]->(bc)
    WITH bc, count(DISTINCT agg) as aggregateCount, count(DISTINCT us) as userStoryCount
    RETURN {
        id: bc.id,
        name: bc.name,
        description: bc.description,
        owner: bc.owner,
        domainType: bc.domainType,
        userStoryIds: bc.userStoryIds,
        aggregateCount: aggregateCount,
        userStoryCount: userStoryCount
    } as context
    ORDER BY bc.name
    """
    SmartLogger.log(
        "INFO",
        "Contexts list requested: returning all bounded contexts with aggregate/user story counts.",
        category="api.contexts.list.request",
        params=http_context(request),
    )
    with get_session() as session:
        result = session.run(query)
        items = [dict(record["context"]) for record in result]
        SmartLogger.log(
            "INFO",
            "Contexts list returned.",
            category="api.contexts.list.done",
            params={**http_context(request), "items": items},
        )
        return items


@router.get("/{context_id}/tree")
async def get_context_tree(context_id: str, request: Request) -> dict[str, Any]:
    """
    GET /api/contexts/{id}/tree - BC 하위 트리
    Returns the full tree structure under a Bounded Context.
    """
    query = """
    MATCH (bc:BoundedContext {id: $context_id})
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
    OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
    OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
    OPTIONAL MATCH (bc)-[:HAS_POLICY]->(pol:Policy)
    WITH bc, agg, cmd, evt, pol
    WITH bc,
         agg,
         collect(DISTINCT {
             id: cmd.id,
             name: cmd.name,
             type: 'Command',
             actor: cmd.actor
         }) as commands,
         collect(DISTINCT {
             id: evt.id,
             name: evt.name,
             type: 'Event',
             version: evt.version
         }) as events
    WITH bc,
         collect(DISTINCT {
             id: agg.id,
             name: agg.name,
             type: 'Aggregate',
             rootEntity: agg.rootEntity,
             commands: commands,
             events: events
         }) as aggregates
    MATCH (bc)-[:HAS_POLICY]->(pol:Policy)
    OPTIONAL MATCH (evt:Event)-[:TRIGGERS]->(pol)
    OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
    WITH bc, aggregates,
         collect(DISTINCT {
             id: pol.id,
             name: pol.name,
             type: 'Policy',
             description: pol.description,
             triggerEventId: evt.id,
             invokeCommandId: cmd.id
         }) as policies
    RETURN {
        id: bc.id,
        name: bc.name,
        type: 'BoundedContext',
        description: bc.description,
        aggregates: aggregates,
        policies: policies
    } as tree
    """
    SmartLogger.log(
        "INFO",
        "Context tree requested: building BC->Aggregate->Command->Event + Policy tree.",
        category="api.contexts.tree.request",
        params={**http_context(request), "inputs": {"context_id": context_id}},
    )
    with get_session() as session:
        result = session.run(query, context_id=context_id)
        record = result.single()
        if not record:
            SmartLogger.log(
                "WARNING",
                "Context tree not found: BC id did not match any node.",
                category="api.contexts.tree.not_found",
                params={**http_context(request), "inputs": {"context_id": context_id}},
            )
            raise HTTPException(status_code=404, detail=f"Context {context_id} not found")
        tree = dict(record["tree"])
        SmartLogger.log(
            "INFO",
            "Context tree returned.",
            category="api.contexts.tree.done",
            params={
                **http_context(request),
                "inputs": {"context_id": context_id},
                "summary": {
                    "aggregates": len(tree.get("aggregates") or []),
                    "policies": len(tree.get("policies") or []),
                },
            },
        )
        return tree


@router.get("/{context_id}/full-tree")
async def get_context_full_tree(context_id: str, request: Request) -> dict[str, Any]:
    """
    GET /api/contexts/{id}/full-tree - BC 하위 전체 트리 (정규화된 구조)
    """
    # Get BC info
    bc_query = """
    MATCH (bc:BoundedContext {id: $context_id})
    RETURN bc {.id, .name, .displayName, .description, .owner, .domainType, .userStoryIds} as bc
    """

    # Get User Stories for this BC
    us_query = """
    MATCH (us:UserStory)-[:IMPLEMENTS]->(bc:BoundedContext {id: $context_id})
    RETURN us {.id, .role, .action, .benefit, .priority, .status} as userStory
    ORDER BY us.id
    """

    # Get Aggregates
    agg_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_AGGREGATE]->(agg:Aggregate)
    RETURN agg {.id, .name, .displayName, .rootEntity, .invariants, .enumerations, .valueObjects} as aggregate
    ORDER BY agg.name
    """

    # Get Commands per Aggregate
    cmd_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)
    RETURN agg.id as aggregateId, cmd {.id, .name, .displayName, .actor, .category, .inputSchema} as command
    ORDER BY cmd.name
    """

    # Get Events
    evt_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(evt:Event)
    RETURN agg.id as aggregateId, cmd.id as commandId, evt {.id, .name, .displayName, .version, .payload} as event
    ORDER BY evt.name
    """

    # Get Policies
    pol_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_POLICY]->(pol:Policy)
    OPTIONAL MATCH (evt:Event)-[:TRIGGERS]->(pol)
    OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
    RETURN pol {.id, .name, .displayName, .description} as policy,
           evt.id as triggerEventId,
           cmd.id as invokeCommandId
    ORDER BY pol.name
    """

    # Get ReadModels for this BC
    rm_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_READMODEL]->(rm:ReadModel)
    RETURN rm {.id, .name, .displayName, .description, .provisioningType, .actor, .isMultipleResult} as readmodel
    ORDER BY readmodel.name
    """

    # Get UI wireframes for this BC
    ui_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_UI]->(ui:UI)
    RETURN ui {.id, .name, .displayName, .description, .template, .attachedToId, .attachedToType, .attachedToName, .userStoryId} as ui
    ORDER BY ui.name
    """

    # Get CQRS Operations for ReadModels in this BC
    cqrs_ops_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_READMODEL]->(rm:ReadModel)-[:HAS_CQRS]->(cqrs:CQRSConfig)-[:HAS_OPERATION]->(op:CQRSOperation)
    OPTIONAL MATCH (op)-[:TRIGGERED_BY]->(evt:Event)
    RETURN rm.id as readmodelId,
           op {.id, .operationType, .triggerEventId} as operation,
           evt.name as triggerEventName
    ORDER BY rm.id, op.operationType
    """

    with get_session() as session:
        SmartLogger.log(
            "INFO",
            "Context full-tree requested: returning normalized structure (BC + user stories + aggregates + policies).",
            category="api.contexts.full_tree.request",
            params={**http_context(request), "inputs": {"context_id": context_id}},
        )
        bc_result = session.run(bc_query, context_id=context_id)
        bc_record = bc_result.single()
        if not bc_record:
            SmartLogger.log(
                "WARNING",
                "Context full-tree not found: BC id did not match any node.",
                category="api.contexts.full_tree.not_found",
                params={**http_context(request), "inputs": {"context_id": context_id}},
            )
            raise HTTPException(status_code=404, detail=f"Context {context_id} not found")
        bc = dict(bc_record["bc"])
        bc["type"] = "BoundedContext"

        # User Stories
        us_result = session.run(us_query, context_id=context_id)
        user_stories = []
        for record in us_result:
            us = dict(record["userStory"])
            us["type"] = "UserStory"
            us["name"] = f"{us.get('role', 'user')}: {us.get('action', '')[:30]}..."
            user_stories.append(us)

        # Aggregates
        agg_result = session.run(agg_query, context_id=context_id)
        aggregates: dict[str, Any] = {}
        for record in agg_result:
            agg = dict(record["aggregate"])
            agg["type"] = "Aggregate"
            agg["commands"] = []
            agg["events"] = []
            
            # Parse JSON strings for enumerations and valueObjects
            if isinstance(agg.get("enumerations"), str):
                try:
                    agg["enumerations"] = json.loads(agg["enumerations"])
                except (json.JSONDecodeError, TypeError):
                    agg["enumerations"] = []
            elif agg.get("enumerations") is None:
                agg["enumerations"] = []
            
            if isinstance(agg.get("valueObjects"), str):
                try:
                    agg["valueObjects"] = json.loads(agg["valueObjects"])
                except (json.JSONDecodeError, TypeError):
                    agg["valueObjects"] = []
            elif agg.get("valueObjects") is None:
                agg["valueObjects"] = []
            
            aggregates[agg["id"]] = agg

        # Commands
        cmd_result = session.run(cmd_query, context_id=context_id)
        commands_map: dict[str, Any] = {}
        for record in cmd_result:
            agg_id = record["aggregateId"]
            cmd = dict(record["command"])
            cmd["type"] = "Command"
            cmd["events"] = []
            if agg_id in aggregates:
                aggregates[agg_id]["commands"].append(cmd)
                commands_map[cmd["id"]] = cmd

        # Events
        evt_result = session.run(evt_query, context_id=context_id)
        for record in evt_result:
            agg_id = record["aggregateId"]
            cmd_id = record["commandId"]
            evt = dict(record["event"])
            evt["type"] = "Event"
            if cmd_id in commands_map:
                commands_map[cmd_id]["events"].append(evt)
            if agg_id in aggregates:
                aggregates[agg_id]["events"].append(evt)

        # Policies
        pol_result = session.run(pol_query, context_id=context_id)
        policies = []
        for record in pol_result:
            pol = dict(record["policy"])
            pol["type"] = "Policy"
            pol["triggerEventId"] = record["triggerEventId"]
            pol["invokeCommandId"] = record["invokeCommandId"]
            policies.append(pol)

        # ReadModels
        rm_result = session.run(rm_query, context_id=context_id)
        readmodels = []
        readmodels_map: dict[str, Any] = {}
        for record in rm_result:
            rm = dict(record["readmodel"])
            rm["type"] = "ReadModel"
            rm["properties"] = []
            rm["operations"] = []
            readmodels.append(rm)
            readmodels_map[rm["id"]] = rm

        # CQRS Operations for ReadModels
        cqrs_ops_result = session.run(cqrs_ops_query, context_id=context_id)
        for record in cqrs_ops_result:
            rm_id = record["readmodelId"]
            if rm_id in readmodels_map and record["operation"]:
                op = dict(record["operation"])
                op["type"] = "CQRSOperation"
                op["triggerEventName"] = record["triggerEventName"]
                readmodels_map[rm_id]["operations"].append(op)

        # UI wireframes
        ui_result = session.run(ui_query, context_id=context_id)
        uis = []
        for record in ui_result:
            ui = dict(record["ui"])
            ui["type"] = "UI"
            uis.append(ui)

        bc["userStories"] = user_stories
        bc["aggregates"] = list(aggregates.values())
        bc["policies"] = policies
        bc["readmodels"] = readmodels
        bc["uis"] = uis

        # Attach properties to Aggregate/Command/Event/ReadModel (sorted):
        # isKey desc -> isForeignKey desc -> name asc (null treated as false)
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

        SmartLogger.log(
            "INFO",
            "Context full-tree returned.",
            category="api.contexts.full_tree.done",
            params={
                **http_context(request),
                "inputs": {"context_id": context_id},
                "counts": {
                    "userStories": len(user_stories),
                    "aggregates": len(bc["aggregates"]),
                    "policies": len(policies),
                    "readmodels": len(readmodels),
                    "uis": len(uis),
                },
            },
        )
        return bc


@router.get("/aggregates/viewer")
async def get_all_aggregates_for_viewer(request: Request) -> dict[str, Any]:
    """
    GET /api/contexts/aggregates/viewer - 모든 BC의 Aggregate, VO, Enum 조회
    Returns all Aggregates across all Bounded Contexts with their enumerations and value objects.
    """
    query = """
    MATCH (bc:BoundedContext)
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
    OPTIONAL MATCH (agg)-[:HAS_PROPERTY]->(prop:Property)
    WITH bc, agg, collect(DISTINCT prop {
        .id, .name, .displayName, .type, .description, .isKey, .isForeignKey, .isRequired
    }) as properties
    ORDER BY bc.name, agg.name
    RETURN {
        bcId: bc.id,
        bcName: bc.name,
        bcDisplayName: bc.displayName,
        bcDescription: bc.description,
        aggregateId: agg.id,
        aggregateName: agg.name,
        aggregateDisplayName: agg.displayName,
        rootEntity: agg.rootEntity,
        invariants: agg.invariants,
        enumerations: agg.enumerations,
        valueObjects: agg.valueObjects,
        properties: properties
    } as item
    """
    
    SmartLogger.log(
        "INFO",
        "Aggregate viewer data requested: returning all aggregates with VO/Enum across all BCs.",
        category="api.contexts.aggregates.viewer.request",
        params=http_context(request),
    )
    
    with get_session() as session:
        result = session.run(query)
        items = []
        for record in result:
            item = dict(record["item"])
            # Parse JSON strings for enumerations and valueObjects
            if isinstance(item.get("enumerations"), str):
                try:
                    item["enumerations"] = json.loads(item["enumerations"])
                except (json.JSONDecodeError, TypeError):
                    item["enumerations"] = []
            elif item.get("enumerations") is None:
                item["enumerations"] = []
            
            if isinstance(item.get("valueObjects"), str):
                try:
                    item["valueObjects"] = json.loads(item["valueObjects"])
                except (json.JSONDecodeError, TypeError):
                    item["valueObjects"] = []
            elif item.get("valueObjects") is None:
                item["valueObjects"] = []
            
            items.append(item)
        
        # Group by BC
        bc_map: dict[str, Any] = {}
        for item in items:
            bc_id = item.get("bcId")
            if not bc_id:
                continue
            
            if bc_id not in bc_map:
                bc_map[bc_id] = {
                    "id": bc_id,
                    "name": item.get("bcName", ""),
                    "displayName": item.get("bcDisplayName") or item.get("bcName", ""),
                    "description": item.get("bcDescription", ""),
                    "aggregates": []
                }
            
            agg_id = item.get("aggregateId")
            if agg_id:
                bc_map[bc_id]["aggregates"].append({
                    "id": agg_id,
                    "name": item.get("aggregateName", ""),
                    "displayName": item.get("aggregateDisplayName") or item.get("aggregateName", ""),
                    "rootEntity": item.get("rootEntity", ""),
                    "invariants": item.get("invariants", []),
                    "enumerations": item.get("enumerations", []),
                    "valueObjects": item.get("valueObjects", []),
                    "properties": item.get("properties", [])
                })
        
        result_data = {
            "boundedContexts": list(bc_map.values())
        }
        
        SmartLogger.log(
            "INFO",
            "Aggregate viewer data returned.",
            category="api.contexts.aggregates.viewer.done",
            params={
                **http_context(request),
                "counts": {
                    "boundedContexts": len(result_data["boundedContexts"]),
                    "totalAggregates": sum(len(bc.get("aggregates", [])) for bc in result_data["boundedContexts"])
                }
            },
        )
        return result_data


@router.put("/aggregates/{aggregate_id}/properties")
async def update_aggregate_properties(
    aggregate_id: str,
    request: Request,
    properties: list[dict[str, Any]] = Body(..., embed=True),
) -> dict[str, Any]:
    """
    PUT /api/contexts/aggregates/{id}/properties - Aggregate의 Properties 업데이트
    Aggregate Viewer에서 Properties를 수정할 때 사용됩니다.
    """
    SmartLogger.log(
        "INFO",
        f"Update request for Aggregate {aggregate_id} properties.",
        category="api.contexts.aggregates.update_properties.request",
        params={
            **http_context(request),
            "aggregate_id": aggregate_id,
            "properties_count": len(properties),
        },
    )
    try:
        # Convert properties to PropertyOps format
        rows = []
        for prop in properties:
            if not prop.get("name") or not prop.get("type"):
                continue
            rows.append({
                "parentType": "Aggregate",
                "parentId": aggregate_id,
                "name": prop.get("name"),
                "type": prop.get("type"),
                "description": prop.get("description", ""),
                "isKey": prop.get("isKey", False),
                "isForeignKey": prop.get("isForeignKey", False),
                "isRequired": prop.get("isRequired", False),
                "fkTargetHint": prop.get("fkTargetHint"),
            })
        
        if not rows:
            raise ValueError("No valid properties provided")
        
        # Upsert properties using direct query
        query = """
        UNWIND $rows as row
        WITH row
        WHERE row.parentType IN ['Aggregate','Command','Event','ReadModel']
          AND row.parentId IS NOT NULL AND trim(toString(row.parentId)) <> ''
          AND row.name IS NOT NULL AND trim(toString(row.name)) <> ''
          AND row.type IS NOT NULL AND trim(toString(row.type)) <> ''
        MERGE (p:Property {parentType: row.parentType, parentId: row.parentId, name: row.name})
        ON CREATE SET p.id = randomUUID(),
                      p.createdAt = datetime()
        SET p.type = row.type,
            p.description = coalesce(row.description, ''),
            p.isKey = coalesce(row.isKey, false),
            p.isForeignKey = coalesce(row.isForeignKey, false),
            p.isRequired = coalesce(row.isRequired, false),
            p.parentType = row.parentType,
            p.parentId = row.parentId,
            p.fkTargetHint = row.fkTargetHint,
            p.updatedAt = datetime()
        WITH row, p
        MATCH (parent {id: row.parentId})
        WHERE row.parentType IN labels(parent)
        MERGE (parent)-[:HAS_PROPERTY]->(p)
        RETURN count(p) as upserted
        """
        with get_session() as session:
            result = session.run(query, rows=rows).single()
            upserted = int((result or {}).get("upserted") or 0)
        
        # Fetch updated aggregate with properties
        query = """
        MATCH (agg:Aggregate {id: $aggregate_id})
        OPTIONAL MATCH (agg)-[:HAS_PROPERTY]->(prop:Property)
        WITH agg, collect(DISTINCT prop {
            .id, .name, .type, .description, .isKey, .isForeignKey, .isRequired
        }) as properties
        RETURN {
            id: agg.id,
            name: agg.name,
            rootEntity: agg.rootEntity,
            invariants: agg.invariants,
            properties: properties
        } as aggregate
        """
        with get_session() as session:
            result_query = session.run(query, aggregate_id=aggregate_id)
            record = result_query.single()
            if not record:
                raise ValueError(f"Aggregate {aggregate_id} not found")
            agg_dict = dict(record["aggregate"])
        
        SmartLogger.log(
            "INFO",
            f"Aggregate {aggregate_id} properties updated successfully.",
            category="api.contexts.aggregates.update_properties.done",
            params={**http_context(request), "aggregate_id": aggregate_id, "upserted": upserted},
        )
        return agg_dict
    except ValueError as e:
        SmartLogger.log(
            "ERROR",
            f"Failed to update Aggregate {aggregate_id} properties: {e}",
            category="api.contexts.aggregates.update_properties.error",
            params={**http_context(request), "aggregate_id": aggregate_id, "error": str(e)},
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"An unexpected error occurred while updating Aggregate {aggregate_id} properties: {e}",
            category="api.contexts.aggregates.update_properties.unexpected_error",
            params={**http_context(request), "aggregate_id": aggregate_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/aggregates/{aggregate_id}/enumerations-valueobjects")
async def update_aggregate_enumerations_valueobjects(
    aggregate_id: str,
    request: Request,
    enumerations: list[dict[str, Any]] = Body(default=[]),
    value_objects: list[dict[str, Any]] = Body(default=[]),
) -> dict[str, Any]:
    """
    PUT /api/contexts/aggregates/{id}/enumerations-valueobjects - Aggregate의 Enumerations와 ValueObjects 업데이트
    Aggregate Viewer에서 Enumerations와 ValueObjects를 수정할 때 사용됩니다.
    """
    SmartLogger.log(
        "INFO",
        f"Update request for Aggregate {aggregate_id} enumerations and value objects.",
        category="api.contexts.aggregates.update_enum_vo.request",
        params={
            **http_context(request),
            "aggregate_id": aggregate_id,
            "enumerations_count": len(enumerations),
            "value_objects_count": len(value_objects),
        },
    )
    try:
        # Use get_session directly instead of AggregateOps instance
        # AggregateOps methods use self.session() which requires Neo4jClient mixin
        # So we'll implement the update logic directly here
        from api.features.ingestion.event_storming.neo4j_ops.aggregates import AggregateOps
        from api.features.ingestion.event_storming.neo4j_client import get_neo4j_client
        
        neo4j_client = get_neo4j_client()
        updated = neo4j_client.update_aggregate_enumerations_and_value_objects(
            aggregate_id=aggregate_id,
            enumerations=enumerations,
            value_objects=value_objects,
        )
        
        # Parse JSON strings back to lists for return value
        if isinstance(updated.get("enumerations"), str):
            try:
                updated["enumerations"] = json.loads(updated["enumerations"])
            except (json.JSONDecodeError, TypeError):
                updated["enumerations"] = []
        elif updated.get("enumerations") is None:
            updated["enumerations"] = []
        
        if isinstance(updated.get("valueObjects"), str):
            try:
                updated["valueObjects"] = json.loads(updated["valueObjects"])
            except (json.JSONDecodeError, TypeError):
                updated["valueObjects"] = []
        elif updated.get("valueObjects") is None:
            updated["valueObjects"] = []
        
        SmartLogger.log(
            "INFO",
            f"Aggregate {aggregate_id} enumerations and value objects updated successfully.",
            category="api.contexts.aggregates.update_enum_vo.done",
            params={**http_context(request), "aggregate_id": aggregate_id},
        )
        return updated
    except ValueError as e:
        SmartLogger.log(
            "ERROR",
            f"Failed to update Aggregate {aggregate_id} enumerations and value objects: {e}",
            category="api.contexts.aggregates.update_enum_vo.error",
            params={**http_context(request), "aggregate_id": aggregate_id, "error": str(e)},
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"An unexpected error occurred while updating Aggregate {aggregate_id} enumerations and value objects: {e}",
            category="api.contexts.aggregates.update_enum_vo.unexpected_error",
            params={**http_context(request), "aggregate_id": aggregate_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal server error")

