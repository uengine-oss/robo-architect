from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
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
            params={**http_context(request), "count": len(items)},
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
    RETURN bc {.id, .name, .description, .owner} as bc
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
    RETURN agg {.id, .name, .rootEntity, .invariants} as aggregate
    ORDER BY agg.name
    """

    # Get Commands per Aggregate
    cmd_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)
    RETURN agg.id as aggregateId, cmd {.id, .name, .actor, .inputSchema} as command
    ORDER BY cmd.name
    """

    # Get Events
    evt_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(evt:Event)
    RETURN agg.id as aggregateId, cmd.id as commandId, evt {.id, .name, .version} as event
    ORDER BY evt.name
    """

    # Get Policies
    pol_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_POLICY]->(pol:Policy)
    OPTIONAL MATCH (evt:Event)-[:TRIGGERS]->(pol)
    OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
    RETURN pol {.id, .name, .description} as policy,
           evt.id as triggerEventId,
           cmd.id as invokeCommandId
    ORDER BY pol.name
    """

    # Get ReadModels for this BC (and their properties)
    rm_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_READMODEL]->(rm:ReadModel)
    OPTIONAL MATCH (rm)-[:HAS_PROPERTY]->(prop:Property)
    WITH rm, collect(prop {.id, .name, .type, .description, .isRequired}) as properties
    RETURN rm {.id, .name, .description, .provisioningType} as readmodel, properties
    ORDER BY readmodel.name
    """

    # Get UI wireframes for this BC
    ui_query = """
    MATCH (bc:BoundedContext {id: $context_id})-[:HAS_UI]->(ui:UI)
    RETURN ui {.id, .name, .description, .template, .attachedToId, .attachedToType, .attachedToName, .userStoryId} as ui
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
            rm["properties"] = [p for p in (record["properties"] or []) if p and p.get("id")]
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


