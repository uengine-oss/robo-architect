from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/subgraph")
async def get_subgraph(
    request: Request,
    node_ids: list[str] = Query(..., description="List of node IDs to include"),
) -> dict[str, Any]:
    """
    GET /api/graph/subgraph - 선택 노드 기준 서브그래프
    Returns nodes and relations for the selected node IDs.

    Input: Node IDs
    Output: Nodes (Type, Name, Meta) + Relations (Type, Direction)
    """
    query = """
    // Get all requested nodes
    UNWIND $node_ids as nodeId
    MATCH (n)
    WHERE n.id = nodeId
    WITH collect(n) as nodes

    // Get relationships between these nodes
    UNWIND nodes as n1
    UNWIND nodes as n2
    OPTIONAL MATCH (n1)-[r]->(n2)
    WHERE n1 <> n2 AND r IS NOT NULL

    WITH nodes, collect(DISTINCT {
        source: n1.id,
        target: n2.id,
        type: type(r),
        properties: properties(r)
    }) as relationships

    UNWIND nodes as n
    WITH collect(DISTINCT {
        id: n.id,
        name: n.name,
        type: labels(n)[0],
        properties: properties(n)
    }) as nodes, relationships

    RETURN nodes, [r IN relationships WHERE r.source IS NOT NULL] as relationships
    """

    SmartLogger.log(
        "INFO",
        "Subgraph requested: returning nodes + relationships for given node_ids.",
        category="api.graph.subgraph.request",
        params={**http_context(request), "inputs": {"node_ids": summarize_for_log(node_ids)}},
    )
    with get_session() as session:
        result = session.run(query, node_ids=node_ids)
        record = result.single()

        if not record:
            SmartLogger.log(
                "INFO",
                "Subgraph empty: no matching nodes found for provided ids.",
                category="api.graph.subgraph.empty",
                params={**http_context(request), "inputs": {"node_ids": summarize_for_log(node_ids)}},
            )
            return {"nodes": [], "relationships": []}

        nodes = record["nodes"]
        relationships = record["relationships"]

        payload = {"nodes": nodes, "relationships": relationships}
        SmartLogger.log(
            "INFO",
            "Subgraph returned.",
            category="api.graph.subgraph.done",
            params={**http_context(request), "summary": {"nodes": len(nodes), "relationships": len(relationships)}},
        )
        return payload


