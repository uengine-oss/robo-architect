"""
Big Picture Timeline API

Provides timeline data for the Event Storming Big Picture view.
Returns swimlanes organized by Bounded Context with events in chronological order,
and cross-BC connections via Policies.

Events are ordered using topological sorting to ensure that events triggered by
other events (via Policy chains) appear later in the timeline.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def topological_sort_events(
    all_events: list[dict], 
    event_chains: list[dict]
) -> dict[str, int]:
    """
    Topologically sort events based on their trigger chains.
    
    Returns a mapping of event_id -> global sequence number, where events
    that are triggered by other events have higher sequence numbers.
    
    Uses Kahn's algorithm for topological sorting.
    
    Args:
        all_events: List of event dicts with 'id' and 'bcId' keys
        event_chains: List of dicts with 'sourceEventId' and 'targetEventId' keys
        
    Returns:
        Dict mapping event_id to its global sequence number (1-indexed)
    """
    # Build directed graph: source -> [targets that must come after]
    graph: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = defaultdict(int)
    
    # Initialize all events with in-degree 0
    all_event_ids = {e['id'] for e in all_events}
    event_bc_map = {e['id']: e['bcId'] for e in all_events}
    
    for eid in all_event_ids:
        in_degree[eid] = 0
    
    # Add edges from event chains (source must come before target)
    for chain in event_chains:
        source_id = chain.get('sourceEventId')
        target_id = chain.get('targetEventId')
        
        # Only add edge if both events exist and are different
        if source_id and target_id and source_id in all_event_ids and target_id in all_event_ids:
            if source_id != target_id:  # Avoid self-loops
                graph[source_id].append(target_id)
                in_degree[target_id] += 1
    
    # Kahn's algorithm with stable ordering
    # Start with events that have no dependencies (in_degree = 0)
    # Sort by BC name for deterministic ordering within same dependency level
    queue = deque(sorted(
        [eid for eid in all_event_ids if in_degree[eid] == 0],
        key=lambda x: (event_bc_map.get(x, ''), x)
    ))
    
    sorted_result: list[str] = []
    
    while queue:
        current = queue.popleft()
        sorted_result.append(current)
        
        # Process neighbors and add newly ready events
        newly_ready = []
        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                newly_ready.append(neighbor)
        
        # Sort newly ready events for deterministic ordering
        newly_ready.sort(key=lambda x: (event_bc_map.get(x, ''), x))
        queue.extend(newly_ready)
    
    # Handle any remaining events (cycles) - add them at the end
    remaining = [eid for eid in all_event_ids if eid not in sorted_result]
    remaining.sort(key=lambda x: (event_bc_map.get(x, ''), x))
    sorted_result.extend(remaining)
    
    # Create sequence mapping (1-indexed)
    sequence_map = {eid: idx + 1 for idx, eid in enumerate(sorted_result)}
    
    return sequence_map


@router.get("/bigpicture/timeline")
async def get_bigpicture_timeline(request: Request) -> dict[str, Any]:
    """
    GET /api/graph/bigpicture/timeline - Big Picture 타임라인 데이터
    
    Returns swimlanes organized by Bounded Context, with events ordered by sequence,
    and cross-BC connections via Policy triggers.
    
    Response structure:
    {
        "swimlanes": [
            {
                "bcId": "BC-xxx",
                "bcName": "Context Name",
                "actors": ["Actor1", "Actor2"],
                "events": [
                    {
                        "id": "EVT-xxx",
                        "name": "EventName",
                        "sequence": 1,
                        "commandId": "CMD-xxx",
                        "commandName": "CommandName",
                        "aggregateId": "AGG-xxx",
                        "aggregateName": "AggregateName",
                        "triggeredPolicies": [...]
                    }
                ]
            }
        ],
        "crossBcConnections": [
            {
                "sourceEventId": "EVT-xxx",
                "targetEventId": "EVT-yyy",
                "policyId": "POL-xxx",
                "policyName": "PolicyName"
            }
        ]
    }
    """
    SmartLogger.log(
        "INFO",
        "Big Picture timeline requested: building swimlane data with cross-BC connections.",
        category="api.graph.bigpicture.timeline.request",
        params=http_context(request),
    )

    # Query 1: Get all BCs with their events and related data
    swimlanes_query = """
    MATCH (bc:BoundedContext)
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(evt:Event)
    OPTIONAL MATCH (us:UserStory)-[:IMPLEMENTS]->(bc)
    WITH bc, agg, cmd, evt, collect(DISTINCT us.role) as actors
    WITH bc, actors,
         collect(DISTINCT {
             eventId: evt.id,
             eventName: evt.name,
             commandId: cmd.id,
             commandName: cmd.name,
             aggregateId: agg.id,
             aggregateName: agg.name
         }) as eventData
    RETURN bc.id as bcId,
           bc.name as bcName,
           bc.description as bcDescription,
           [a IN actors WHERE a IS NOT NULL] as actors,
           [e IN eventData WHERE e.eventId IS NOT NULL] as events
    ORDER BY bc.name
    """

    # Query 2: Get cross-BC connections (Event -> TRIGGERS -> Policy -> INVOKES -> Command -> EMITS -> Event)
    cross_bc_query = """
    MATCH (sourceEvt:Event)-[:TRIGGERS]->(pol:Policy)-[:INVOKES]->(targetCmd:Command)-[:EMITS]->(targetEvt:Event)
    OPTIONAL MATCH (sourceBc:BoundedContext)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(:Command)-[:EMITS]->(sourceEvt)
    OPTIONAL MATCH (targetBc:BoundedContext)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(targetCmd)
    WHERE sourceBc.id <> targetBc.id OR sourceBc IS NULL OR targetBc IS NULL
    RETURN DISTINCT
           sourceEvt.id as sourceEventId,
           sourceEvt.name as sourceEventName,
           targetEvt.id as targetEventId,
           targetEvt.name as targetEventName,
           pol.id as policyId,
           pol.name as policyName,
           sourceBc.id as sourceBcId,
           targetBc.id as targetBcId
    """

    # Query 3: Get all policies with their trigger and invoke relationships
    policies_query = """
    MATCH (evt:Event)-[:TRIGGERS]->(pol:Policy)
    OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
    OPTIONAL MATCH (cmd)-[:EMITS]->(targetEvt:Event)
    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_POLICY]->(pol)
    RETURN evt.id as triggerEventId,
           pol.id as policyId,
           pol.name as policyName,
           cmd.id as invokeCommandId,
           cmd.name as invokeCommandName,
           targetEvt.id as targetEventId,
           targetEvt.name as targetEventName,
           bc.id as policyBcId
    """

    # Query 4: Get ALL event chains for topological sorting (includes same-BC chains)
    event_chains_query = """
    MATCH (sourceEvt:Event)-[:TRIGGERS]->(pol:Policy)-[:INVOKES]->(targetCmd:Command)-[:EMITS]->(targetEvt:Event)
    RETURN DISTINCT
           sourceEvt.id as sourceEventId,
           targetEvt.id as targetEventId
    """

    with get_session() as session:
        # Execute swimlanes query
        swimlanes_result = session.run(swimlanes_query)
        swimlanes_raw = [dict(record) for record in swimlanes_result]

        # Execute policies query to build triggered policies map
        policies_result = session.run(policies_query)
        policies_map: dict[str, list[dict]] = {}  # eventId -> list of triggered policies
        
        for record in policies_result:
            trigger_event_id = record["triggerEventId"]
            if trigger_event_id:
                if trigger_event_id not in policies_map:
                    policies_map[trigger_event_id] = []
                policies_map[trigger_event_id].append({
                    "policyId": record["policyId"],
                    "policyName": record["policyName"],
                    "invokeCommandId": record["invokeCommandId"],
                    "invokeCommandName": record["invokeCommandName"],
                    "targetEventId": record["targetEventId"],
                    "targetEventName": record["targetEventName"],
                    "policyBcId": record["policyBcId"],
                })

        # Execute cross-BC query
        cross_bc_result = session.run(cross_bc_query)
        cross_bc_connections = []
        
        for record in cross_bc_result:
            if record["sourceEventId"] and record["targetEventId"]:
                cross_bc_connections.append({
                    "sourceEventId": record["sourceEventId"],
                    "sourceEventName": record["sourceEventName"],
                    "targetEventId": record["targetEventId"],
                    "targetEventName": record["targetEventName"],
                    "policyId": record["policyId"],
                    "policyName": record["policyName"],
                    "sourceBcId": record["sourceBcId"],
                    "targetBcId": record["targetBcId"],
                })

        # Execute event chains query for topological sorting
        event_chains_result = session.run(event_chains_query)
        event_chains = []
        
        for record in event_chains_result:
            if record["sourceEventId"] and record["targetEventId"]:
                event_chains.append({
                    "sourceEventId": record["sourceEventId"],
                    "targetEventId": record["targetEventId"],
                })

        # Collect all events with their BC info for topological sorting
        all_events_flat = []
        for bc_data in swimlanes_raw:
            for evt in bc_data["events"]:
                all_events_flat.append({
                    "id": evt["eventId"],
                    "bcId": bc_data["bcId"],
                    "bcName": bc_data["bcName"],
                })

        # Calculate global sequence using topological sort
        # This ensures events triggered by other events have higher sequence numbers
        sequence_map = topological_sort_events(all_events_flat, event_chains)

        SmartLogger.log(
            "DEBUG",
            "Topological sort completed for events",
            category="api.graph.bigpicture.timeline.topological_sort",
            params={
                "total_events": len(all_events_flat),
                "event_chains": len(event_chains),
            },
        )

        # Build swimlanes with topologically sorted sequence numbers
        swimlanes = []
        
        for bc_data in swimlanes_raw:
            events_with_sequence = []
            
            for evt in bc_data["events"]:
                event_id = evt["eventId"]
                # Use topological sequence, fallback to 0 if not found
                global_sequence = sequence_map.get(event_id, 0)
                triggered_policies = policies_map.get(event_id, [])
                
                events_with_sequence.append({
                    "id": event_id,
                    "name": evt["eventName"],
                    "sequence": global_sequence,
                    "commandId": evt["commandId"],
                    "commandName": evt["commandName"],
                    "aggregateId": evt["aggregateId"],
                    "aggregateName": evt["aggregateName"],
                    "triggeredPolicies": triggered_policies,
                })
            
            # Sort events by their global sequence within the swimlane
            events_with_sequence.sort(key=lambda e: e["sequence"])
            
            # Filter out empty actors
            actors = [a for a in bc_data["actors"] if a]
            if not actors:
                actors = ["System"]  # Default actor if none specified
            
            swimlanes.append({
                "bcId": bc_data["bcId"],
                "bcName": bc_data["bcName"],
                "bcDescription": bc_data["bcDescription"],
                "actors": actors,
                "events": events_with_sequence,
            })

        # Calculate total events count for logging
        total_events = sum(len(s["events"]) for s in swimlanes)

        SmartLogger.log(
            "INFO",
            "Big Picture timeline returned.",
            category="api.graph.bigpicture.timeline.done",
            params={
                **http_context(request),
                "summary": {
                    "swimlanes": len(swimlanes),
                    "totalEvents": total_events,
                    "crossBcConnections": len(cross_bc_connections),
                },
            },
        )

        return {
            "swimlanes": swimlanes,
            "crossBcConnections": cross_bc_connections,
        }


@router.get("/bigpicture/summary")
async def get_bigpicture_summary(request: Request) -> dict[str, Any]:
    """
    GET /api/graph/bigpicture/summary - Big Picture 요약 통계
    
    Returns summary statistics for the big picture view.
    """
    SmartLogger.log(
        "INFO",
        "Big Picture summary requested.",
        category="api.graph.bigpicture.summary.request",
        params=http_context(request),
    )

    query = """
    MATCH (bc:BoundedContext)
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
    OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
    OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
    OPTIONAL MATCH (bc)-[:HAS_POLICY]->(pol:Policy)
    WITH bc,
         count(DISTINCT agg) as aggregateCount,
         count(DISTINCT cmd) as commandCount,
         count(DISTINCT evt) as eventCount,
         count(DISTINCT pol) as policyCount
    RETURN bc.id as bcId,
           bc.name as bcName,
           aggregateCount,
           commandCount,
           eventCount,
           policyCount
    ORDER BY bc.name
    """

    with get_session() as session:
        result = session.run(query)
        bc_stats = [dict(record) for record in result]

        total_bcs = len(bc_stats)
        total_events = sum(s["eventCount"] for s in bc_stats)
        total_policies = sum(s["policyCount"] for s in bc_stats)

        SmartLogger.log(
            "INFO",
            "Big Picture summary returned.",
            category="api.graph.bigpicture.summary.done",
            params={
                **http_context(request),
                "summary": {
                    "totalBCs": total_bcs,
                    "totalEvents": total_events,
                    "totalPolicies": total_policies,
                },
            },
        )

        return {
            "totalBCs": total_bcs,
            "totalEvents": total_events,
            "totalPolicies": total_policies,
            "bcStats": bc_stats,
        }

