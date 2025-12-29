from __future__ import annotations

import time

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


def fetch_bc_data(bc_id: str) -> dict | None:
    t0 = time.perf_counter()
    query = """
    MATCH (bc:BoundedContext {id: $bc_id})
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
    OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
    OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
    WITH bc, agg,
         collect(DISTINCT {id: cmd.id, name: cmd.name, actor: cmd.actor}) as commands,
         collect(DISTINCT {id: evt.id, name: evt.name, version: evt.version}) as events
    WITH bc, collect(DISTINCT {
        id: agg.id,
        name: agg.name,
        rootEntity: agg.rootEntity,
        commands: commands,
        events: events
    }) as aggregates

    OPTIONAL MATCH (bc)-[:HAS_POLICY]->(pol:Policy)
    OPTIONAL MATCH (triggerEvt:Event)-[:TRIGGERS]->(pol)
    OPTIONAL MATCH (pol)-[:INVOKES]->(invokeCmd:Command)
    WITH bc, aggregates, collect(DISTINCT {
        id: pol.id,
        name: pol.name,
        description: pol.description,
        triggerEventId: triggerEvt.id,
        triggerEventName: triggerEvt.name,
        invokeCommandId: invokeCmd.id,
        invokeCommandName: invokeCmd.name
    }) as policies

    RETURN {
        id: bc.id,
        name: bc.name,
        description: bc.description,
        aggregates: [a IN aggregates WHERE a.id IS NOT NULL],
        policies: [p IN policies WHERE p.id IS NOT NULL]
    } as bc_data
    """

    with get_session() as session:
        result = session.run(query, bc_id=bc_id)
        record = result.single()
        if record:
            bc_data = dict(record["bc_data"])
            SmartLogger.log(
                "INFO",
                "PRD: fetched BC data from Neo4j.",
                category="api.prd.neo4j.fetch_bc",
                params={
                    "bc_id": bc_id,
                    "duration_ms": int((time.perf_counter() - t0) * 1000),
                    "summary": {
                        "aggregates": len(bc_data.get("aggregates") or []),
                        "policies": len(bc_data.get("policies") or []),
                    },
                },
            )
            return bc_data
    SmartLogger.log(
        "WARNING",
        "PRD: BC not found while fetching data.",
        category="api.prd.neo4j.fetch_bc.not_found",
        params={"bc_id": bc_id, "duration_ms": int((time.perf_counter() - t0) * 1000)},
    )
    return None


def get_bcs_from_nodes(node_ids: list[str]) -> list[dict]:
    t0 = time.perf_counter()
    query = """
    // Direct BC nodes
    UNWIND $node_ids as nodeId
    OPTIONAL MATCH (bc:BoundedContext {id: nodeId})
    WITH collect(DISTINCT bc.id) as directBCs

    // BCs containing the nodes
    UNWIND $node_ids as nodeId
    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE|HAS_POLICY*1..3]->(n {id: nodeId})
    WITH directBCs, collect(DISTINCT bc.id) as containingBCs

    // BCs for Commands (via Aggregate)
    UNWIND $node_ids as nodeId
    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command {id: nodeId})
    WITH directBCs, containingBCs, collect(DISTINCT bc.id) as cmdBCs

    // BCs for Events (via Command)
    UNWIND $node_ids as nodeId
    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg2:Aggregate)-[:HAS_COMMAND]->(cmd2:Command)-[:EMITS]->(evt:Event {id: nodeId})
    WITH directBCs, containingBCs, cmdBCs, collect(DISTINCT bc.id) as evtBCs

    WITH directBCs + containingBCs + cmdBCs + evtBCs as allBCIds
    UNWIND allBCIds as bcId
    WITH DISTINCT bcId WHERE bcId IS NOT NULL
    RETURN collect(bcId) as bc_ids
    """

    bc_ids: list[str] = []
    with get_session() as session:
        result = session.run(query, node_ids=node_ids)
        record = result.single()
        if record:
            bc_ids = record["bc_ids"] or []

    SmartLogger.log(
        "INFO",
        "PRD: resolved BC IDs from selected node IDs.",
        category="api.prd.neo4j.resolve_bcs",
        params={
            "inputs": {"node_ids": summarize_for_log(node_ids)},
            "resolved_bc_ids": bc_ids,
            "duration_ms": int((time.perf_counter() - t0) * 1000),
        },
    )

    bcs: list[dict] = []
    for bc_id in bc_ids:
        bc_data = fetch_bc_data(bc_id)
        if bc_data:
            bcs.append(bc_data)
    return bcs


