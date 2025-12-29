from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.delete("/clear")
async def clear_all_nodes(request: Request):
    """
    DELETE /api/graph/clear - 모든 노드와 관계 삭제
    새로운 인제스션 전에 기존 데이터를 모두 삭제합니다.
    """
    query = """
    MATCH (n)
    DETACH DELETE n
    """
    SmartLogger.log(
        "WARNING",
        "Graph clear requested: DETACH DELETE all nodes/relationships (destructive).",
        category="api.graph.clear.request",
        params=http_context(request),
    )
    with get_session() as session:
        result = session.run(query)
        summary = result.consume()
        SmartLogger.log(
            "INFO",
            "Graph cleared: all nodes/relationships removed.",
            category="api.graph.clear.done",
            params={
                **http_context(request),
                "deleted": {
                    "nodes_deleted": summary.counters.nodes_deleted,
                    "relationships_deleted": summary.counters.relationships_deleted,
                },
            },
        )
        return {
            "status": "cleared",
            "nodes_deleted": summary.counters.nodes_deleted,
            "relationships_deleted": summary.counters.relationships_deleted,
        }


@router.get("/stats")
async def get_graph_stats(request: Request):
    """
    GET /api/graph/stats - 그래프 통계 조회
    현재 Neo4j에 저장된 노드 수를 반환합니다.
    """
    query = """
    MATCH (n)
    WITH labels(n)[0] as label, count(n) as count
    RETURN collect({label: label, count: count}) as stats
    """
    SmartLogger.log(
        "INFO",
        "Graph stats requested: counting nodes by label.",
        category="api.graph.stats.request",
        params=http_context(request),
    )
    with get_session() as session:
        result = session.run(query)
        record = result.single()
        if record:
            stats = {item["label"]: item["count"] for item in record["stats"] if item["label"]}
            total = sum(stats.values())
            SmartLogger.log(
                "INFO",
                "Graph stats computed: counts by label returned.",
                category="api.graph.stats.done",
                params={**http_context(request), "total": total, "by_type": stats},
            )
            return {"total": total, "by_type": stats}
        SmartLogger.log(
            "INFO",
            "Graph stats empty: no nodes found.",
            category="api.graph.stats.empty",
            params=http_context(request),
        )
        return {"total": 0, "by_type": {}}


