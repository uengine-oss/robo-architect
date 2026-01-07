from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/impact/{user_story_id}")
async def get_impact_analysis(user_story_id: str, request: Request) -> dict[str, Any]:
    """
    Analyze the impact of changing a User Story.

    Returns:
    - The original user story
    - All connected objects (Aggregate, Command, Event) that may need updates
    """
    SmartLogger.log(
        "INFO",
        "Impact analysis requested: resolving connected nodes for the given user story.",
        category="change.impact.inputs",
        params={**http_context(request), "inputs": {"user_story_id": user_story_id}},
    )
    query = """
    MATCH (us:UserStory {id: $user_story_id})

    // Path 1: Direct IMPLEMENTS relationships
    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(directTarget)
    WHERE directTarget:Aggregate OR directTarget:Command OR directTarget:Event OR directTarget:BoundedContext

    // Path 2: Through BoundedContext - find the BC this user story belongs to
    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(bc:BoundedContext)
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(bcAgg:Aggregate)
    OPTIONAL MATCH (bcAgg)-[:HAS_COMMAND]->(bcCmd:Command)
    OPTIONAL MATCH (bcCmd)-[:EMITS]->(bcEvt:Event)

    // Path 3: If user story implements an aggregate, get its commands and events
    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(usAgg:Aggregate)
    OPTIONAL MATCH (usAgg)-[:HAS_COMMAND]->(usAggCmd:Command)
    OPTIONAL MATCH (usAggCmd)-[:EMITS]->(usAggEvt:Event)

    // Path 4: If user story implements a command, get its events
    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(usCmd:Command)
    OPTIONAL MATCH (usCmd)-[:EMITS]->(usCmdEvt:Event)
    OPTIONAL MATCH (usAggParent:Aggregate)-[:HAS_COMMAND]->(usCmd)

    WITH us,
         collect(DISTINCT bc) as bcs,
         collect(DISTINCT bcAgg) + collect(DISTINCT usAgg) + collect(DISTINCT usAggParent) as allAggs,
         collect(DISTINCT bcCmd) + collect(DISTINCT usAggCmd) + collect(DISTINCT usCmd) as allCmds,
         collect(DISTINCT bcEvt) + collect(DISTINCT usAggEvt) + collect(DISTINCT usCmdEvt) as allEvts

    // Get the first BC (user story typically belongs to one BC)
    WITH us,
         CASE WHEN size(bcs) > 0 THEN bcs[0] ELSE null END as bc,
         allAggs, allCmds, allEvts

    RETURN {
        id: us.id,
        role: us.role,
        action: us.action,
        benefit: us.benefit,
        priority: us.priority,
        status: us.status
    } as userStory,
    bc {.id, .name, .description} as boundedContext,
    [a IN allAggs WHERE a IS NOT NULL | a {.id, .name, .rootEntity, type: 'Aggregate'}] as aggregates,
    [c IN allCmds WHERE c IS NOT NULL | c {.id, .name, .actor, type: 'Command'}] as commands,
    [e IN allEvts WHERE e IS NOT NULL | e {.id, .name, .version, type: 'Event'}] as events
    """

    with get_session() as session:
        SmartLogger.log(
            "INFO",
            "Impact analysis executing Neo4j query: collecting aggregates/commands/events reachable from user story.",
            category="change.impact.query",
            params={**http_context(request), "user_story_id": user_story_id},
        )
        result = session.run(query, user_story_id=user_story_id)
        record = result.single()

        if not record:
            SmartLogger.log(
                "WARNING",
                "Impact analysis failed: user story not found in Neo4j.",
                category="change.impact.not_found",
                params={**http_context(request), "user_story_id": user_story_id},
            )
            raise HTTPException(status_code=404, detail=f"User story {user_story_id} not found")

        user_story = dict(record["userStory"])
        bounded_context = dict(record["boundedContext"]) if record["boundedContext"] else None

        impacted_nodes: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for agg in record["aggregates"]:
            if agg and agg["id"] not in seen_ids:
                impacted_nodes.append(dict(agg))
                seen_ids.add(agg["id"])
        for cmd in record["commands"]:
            if cmd and cmd["id"] not in seen_ids:
                impacted_nodes.append(dict(cmd))
                seen_ids.add(cmd["id"])
        for evt in record["events"]:
            if evt and evt["id"] not in seen_ids:
                impacted_nodes.append(dict(evt))
                seen_ids.add(evt["id"])

        SmartLogger.log(
            "INFO",
            "Impact analysis computed: impacted nodes deduplicated and returned.",
            category="change.impact.done",
            params={
                **http_context(request),
                "user_story_id": user_story_id,
                "boundedContext": bounded_context.get("id") if bounded_context else None,
                "impactedNodes": len(impacted_nodes),
            },
        )
        return {"userStory": user_story, "boundedContext": bounded_context, "impactedNodes": impacted_nodes}


