"""BPM-task design-trace route (039 — bpm-event-unification).

Given a BPM task (`:BpmTask`), returns the design trajectory of every Command
promoted from that task — Command → Aggregate / UI / Event → Policy → Command —
in the SAME `{nodes, relationships}` shape as the User-Story design trace, so the
BPM task inspector's "포함 요소" modal can reuse the exact `DesignTraceCanvas`
Vue Flow rendering.

This is a READ-ONLY projection over already-persisted traceability edges
(`PROMOTED_FROM`, `ATTACHED_TO`, `EMITS`, `TRIGGERS`, `INVOKES`, `HAS_COMMAND`,
`HAS_PROPERTY`). It adds NO new node labels or relationships (spec 039 FR-005,
FR-011). The frontier-expansion logic is shared with the User-Story route via
`_expand_trace`.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.features.requirements.requirements_contracts import DesignTraceResponse
from api.features.requirements.routes.design_trace import _expand_trace
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/bpm-task/{task_id}/design-trace", response_model=DesignTraceResponse)
async def get_bpm_task_design_trace(
    task_id: str, request: Request, depth: int = 2
) -> DesignTraceResponse:
    """Load the design trace for one BPM task.

    Roots the trace at every Command promoted from the task
    (`(:Command)-[:PROMOTED_FROM]->(:BpmTask {id})`), then expands identically to
    the User-Story design trace. Returns `empty=True` when the task has no
    promoted Command. 404 when the task id does not exist.
    """
    SmartLogger.log(
        "INFO",
        "BPM task design trace requested.",
        category="canvas_graph.bpm_task_trace.request",
        params={**http_context(request), "task_id": task_id, "depth": depth},
    )

    depth = max(1, min(depth, 5))

    with get_session() as session:
        root = session.run(
            "MATCH (t:BpmTask {id: $tid}) RETURN t.id AS id",
            tid=task_id,
        ).single()
        if not root:
            raise HTTPException(status_code=404, detail=f"BpmTask {task_id} not found")

        # Roots = every Command attributable to this task. Two hybrid schemas
        # link BPM↔ES differently, so cover both:
        #   (a) (:BpmTask)-[:PROMOTED_TO]->(:UserStory)-[:IMPLEMENTS]->(:Command)
        #       — the promote-to-es bridge used in current sessions.
        #   (b) (:Command)-[:PROMOTED_FROM]->(:BpmTask)
        #       — the persistence.py traceability edge (newer/alt path).
        root_cmd_ids = [
            rec["cid"]
            for rec in session.run(
                """
                MATCH (t:BpmTask {id: $tid})
                OPTIONAL MATCH (t)-[:PROMOTED_TO]->(:UserStory)-[:IMPLEMENTS]->(c1:Command)
                OPTIONAL MATCH (c2:Command)-[:PROMOTED_FROM]->(t)
                WITH collect(DISTINCT c1.id) + collect(DISTINCT c2.id) AS ids
                UNWIND ids AS cid
                WITH DISTINCT cid WHERE cid IS NOT NULL
                RETURN cid
                """,
                tid=task_id,
            )
            if rec["cid"]
        ]

        if not root_cmd_ids:
            SmartLogger.log(
                "INFO",
                "BPM task design trace empty: no promoted Command.",
                category="canvas_graph.bpm_task_trace.empty",
                params={**http_context(request), "task_id": task_id},
            )
            return DesignTraceResponse(rootCommandId=None, nodes=[], relationships=[], empty=True)

        nodes, rels = _expand_trace(session, root_cmd_ids, depth)

    SmartLogger.log(
        "INFO",
        "BPM task design trace built.",
        category="canvas_graph.bpm_task_trace.done",
        params={
            **http_context(request),
            "task_id": task_id,
            "nodes": len(nodes),
            "relationships": len(rels),
        },
    )
    return DesignTraceResponse(
        rootCommandId=root_cmd_ids[0],
        nodes=list(nodes.values()),
        relationships=rels,
        empty=False,
    )
