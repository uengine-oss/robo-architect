from __future__ import annotations

from typing import List

from fastapi import APIRouter
from starlette.requests import Request

from api.features.change_management.change_api_contracts import VectorSearchRequest, VectorSearchResult
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.post("/search")
async def vector_search(payload: VectorSearchRequest, request: Request) -> List[VectorSearchResult]:
    """
    Search for related objects using semantic/keyword matching.
    """
    query = """
    UNWIND $keywords as keyword
    MATCH (n)
    WHERE (
        ($nodeTypes IS NULL OR any(t IN $nodeTypes WHERE t IN labels(n)))
    )
    AND (n:Command OR n:Event OR n:Policy OR n:Aggregate)
    AND (
        toLower(n.name) CONTAINS toLower(keyword)
        OR toLower(coalesce(n.description, '')) CONTAINS toLower(keyword)
    )
    AND NOT n.id IN $excludeIds

    // Get the BC for each node
    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE|HAS_POLICY*1..3]->(n)

    WITH DISTINCT n, bc,
         CASE
             WHEN toLower(n.name) CONTAINS toLower($primary_keyword) THEN 1.0
             WHEN toLower(n.name) CONTAINS toLower($query) THEN 0.9
             ELSE 0.7
         END as score

    RETURN {
        id: n.id,
        name: n.name,
        type: labels(n)[0],
        bcId: bc.id,
        bcName: bc.name,
        description: n.description,
        similarity: score
    } as result
    ORDER BY score DESC
    LIMIT $limit
    """

    SmartLogger.log(
        "INFO",
        "Vector search requested: capturing router inputs for reproducibility.",
        category="change.search.inputs",
        params={**http_context(request), "inputs": summarize_for_log(payload.model_dump())},
    )

    keywords = [w.strip() for w in payload.query.split() if len(w.strip()) > 2]
    if not keywords:
        keywords = [payload.query]
        SmartLogger.log(
            "INFO",
            "Vector search keyword fallback: query had no tokens > 2 chars, using full query as keyword.",
            category="change.search.keyword_fallback",
            params={**http_context(request), "query": payload.query},
        )
    SmartLogger.log(
        "INFO",
        "Vector search executing Neo4j query.",
        category="change.search.query",
        params={
            **http_context(request),
            "query": payload.query,
            "keywords": keywords[:10],
            "limit": payload.limit,
            "nodeTypes": payload.nodeTypes,
            "excludeIds_count": len(payload.excludeIds or []),
        },
    )

    with get_session() as session:
        result = session.run(
            query,
            keywords=keywords,
            primary_keyword=keywords[0] if keywords else "",
            query=payload.query,
            nodeTypes=payload.nodeTypes if payload.nodeTypes else None,
            excludeIds=payload.excludeIds,
            limit=payload.limit,
        )

        results: list[VectorSearchResult] = []
        seen_ids = set()
        for record in result:
            obj = record["result"]
            if obj["id"] and obj["id"] not in seen_ids:
                seen_ids.add(obj["id"])
                results.append(
                    VectorSearchResult(
                        id=obj["id"],
                        name=obj["name"],
                        type=obj["type"],
                        bcId=obj.get("bcId"),
                        bcName=obj.get("bcName"),
                        similarity=obj.get("similarity", 0.5),
                        description=obj.get("description"),
                    )
                )

        SmartLogger.log(
            "INFO",
            "Vector search returned.",
            category="change.search.done",
            params={**http_context(request), "query": payload.query, "results": len(results)},
        )
        return results


