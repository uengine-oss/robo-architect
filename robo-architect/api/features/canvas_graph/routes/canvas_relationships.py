from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/find-relations")
async def find_relations(
    request: Request,
    node_ids: list[str] = Query(..., description="List of node IDs on canvas"),
) -> list[dict[str, Any]]:
    """
    Find ALL relations between nodes that are currently on the canvas.
    This includes:
    - Direct relations (HAS_COMMAND, EMITS, etc.)
    - Cross-BC relations (Event TRIGGERS Policy, Policy INVOKES Command)
    """
    direct_query = """
    UNWIND $node_ids as sourceId
    UNWIND $node_ids as targetId
    MATCH (source {id: sourceId})-[r]->(target {id: targetId})
    WHERE sourceId <> targetId
    RETURN DISTINCT {
        source: source.id,
        target: target.id,
        type: type(r)
    } as relationship
    """

    cross_bc_query = """
    UNWIND $node_ids as evtId
    UNWIND $node_ids as polId
    MATCH (evt:Event {id: evtId})-[r:TRIGGERS]->(pol:Policy {id: polId})
    RETURN DISTINCT {
        source: evt.id,
        target: pol.id,
        type: 'TRIGGERS'
    } as relationship

    UNION

    // Policy → INVOKES → Command (cross-BC)
    UNWIND $node_ids as polId
    UNWIND $node_ids as cmdId
    MATCH (pol:Policy {id: polId})-[r:INVOKES]->(cmd:Command {id: cmdId})
    RETURN DISTINCT {
        source: pol.id,
        target: cmd.id,
        type: 'INVOKES'
    } as relationship
    """

    relationships: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    with get_session() as session:
        SmartLogger.log(
            "INFO",
            "Find relations requested: discovering relationships among canvas nodes.",
            category="api.graph.find_relations.request",
            params={**http_context(request), "inputs": {"node_ids": summarize_for_log(node_ids)}},
        )
        result = session.run(direct_query, node_ids=node_ids)
        for record in result:
            rel = dict(record["relationship"])
            key = (rel["source"], rel["target"], rel["type"])
            if key not in seen:
                seen.add(key)
                relationships.append(rel)

        result = session.run(cross_bc_query, node_ids=node_ids)
        for record in result:
            rel = dict(record["relationship"])
            key = (rel["source"], rel["target"], rel["type"])
            if key not in seen:
                seen.add(key)
                relationships.append(rel)

    SmartLogger.log(
        "INFO",
        "Find relations returned.",
        category="api.graph.find_relations.done",
        params={**http_context(request), "summary": {"relationships": len(relationships)}},
    )
    return relationships


@router.get("/find-cross-bc-relations")
async def find_cross_bc_relations(
    request: Request,
    new_node_ids: list[str] = Query(..., description="Newly added node IDs"),
    existing_node_ids: list[str] = Query(..., description="Existing node IDs on canvas"),
) -> list[dict[str, Any]]:
    """
    Find cross-BC relationships between newly added nodes and existing canvas nodes.

    This is optimized for the use case where user drops a new BC onto canvas
    and we need to find connections like:
    - Event (existing) → TRIGGERS → Policy (new)
    - Event (new) → TRIGGERS → Policy (existing)
    - Policy (existing) → INVOKES → Command (new)
    - Policy (new) → INVOKES → Command (existing)
    """
    query = """
    // Event → TRIGGERS → Policy (existing event triggers new policy)
    UNWIND $existing_ids as evtId
    UNWIND $new_ids as polId
    OPTIONAL MATCH (evt:Event {id: evtId})-[:TRIGGERS]->(pol:Policy {id: polId})
    WITH collect({source: evt.id, target: pol.id, type: 'TRIGGERS'}) as r1

    // Event → TRIGGERS → Policy (new event triggers existing policy)
    UNWIND $new_ids as evtId
    UNWIND $existing_ids as polId
    OPTIONAL MATCH (evt:Event {id: evtId})-[:TRIGGERS]->(pol:Policy {id: polId})
    WITH r1, collect({source: evt.id, target: pol.id, type: 'TRIGGERS'}) as r2

    // Policy → INVOKES → Command (existing policy invokes new command)
    UNWIND $existing_ids as polId
    UNWIND $new_ids as cmdId
    OPTIONAL MATCH (pol:Policy {id: polId})-[:INVOKES]->(cmd:Command {id: cmdId})
    WITH r1, r2, collect({source: pol.id, target: cmd.id, type: 'INVOKES'}) as r3

    // Policy → INVOKES → Command (new policy invokes existing command)
    UNWIND $new_ids as polId
    UNWIND $existing_ids as cmdId
    OPTIONAL MATCH (pol:Policy {id: polId})-[:INVOKES]->(cmd:Command {id: cmdId})
    WITH r1, r2, r3, collect({source: pol.id, target: cmd.id, type: 'INVOKES'}) as r4

    RETURN r1 + r2 + r3 + r4 as relationships
    """

    with get_session() as session:
        SmartLogger.log(
            "INFO",
            "Find cross-BC relations requested: checking TRIGGERS/INVOKES across new vs existing sets.",
            category="api.graph.find_cross_bc.request",
            params={
                **http_context(request),
                "inputs": {
                    "new_node_ids": summarize_for_log(new_node_ids),
                    "existing_node_ids": summarize_for_log(existing_node_ids),
                },
            },
        )
        result = session.run(query, new_ids=new_node_ids, existing_ids=existing_node_ids)
        record = result.single()

        if not record:
            SmartLogger.log(
                "INFO",
                "Find cross-BC relations empty: no matching cross-BC edges found.",
                category="api.graph.find_cross_bc.empty",
                params={**http_context(request)},
            )
            return []

        relationships: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for rel in record["relationships"]:
            if rel.get("source") and rel.get("target"):
                key = (rel["source"], rel["target"], rel["type"])
                if key not in seen:
                    seen.add(key)
                    relationships.append(rel)

        SmartLogger.log(
            "INFO",
            "Find cross-BC relations returned.",
            category="api.graph.find_cross_bc.done",
            params={**http_context(request), "summary": {"relationships": len(relationships)}},
        )
        return relationships


