from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/all-nodes")
async def get_all_nodes(request: Request) -> dict[str, List[dict[str, Any]]]:
    """
    Get all nodes grouped by type for frontend reference.
    """
    query = """
    MATCH (bc:BoundedContext)
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
    OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
    OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
    OPTIONAL MATCH (bc)-[:HAS_POLICY]->(pol:Policy)

    WITH bc,
         collect(DISTINCT agg {.id, .name, .rootEntity}) as aggregates,
         collect(DISTINCT cmd {.id, .name, .actor}) as commands,
         collect(DISTINCT evt {.id, .name, .version}) as events,
         collect(DISTINCT pol {.id, .name, .triggerCondition}) as policies

    RETURN bc {.id, .name, .description,
        aggregates: aggregates,
        commands: commands,
        events: events,
        policies: policies
    } as boundedContext
    """

    with get_session() as session:
        SmartLogger.log(
            "INFO",
            "All-nodes requested: returning nodes grouped by BC for frontend reference.",
            category="change.all_nodes.request",
            params=http_context(request),
        )
        result = session.run(query)
        bounded_contexts: list[dict[str, Any]] = []
        for record in result:
            bounded_contexts.append(dict(record["boundedContext"]))

        SmartLogger.log(
            "INFO",
            "All-nodes returned.",
            category="change.all_nodes.done",
            params={**http_context(request), "boundedContexts": len(bounded_contexts)},
        )
        return {"boundedContexts": bounded_contexts}


