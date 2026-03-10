"""
Big Picture Timeline API - 이벤트 스토밍 빅피처 단계 시각화

업무 흐름 분석:
- BC(바운디드 컨텍스트)별 스윔레인
- Actor별 이벤트 그룹핑
- 시계열 기반 이벤트 배치
- Cross-BC Event → Policy → Command → Event 체인 시각화
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/bigpicture-timeline")
async def get_bigpicture_timeline(request: Request) -> dict[str, Any]:
    """
    GET /api/graph/bigpicture-timeline
    
    빅피처 타임라인 데이터 반환:
    - swimlanes: BC별 스윔레인 (Actor 포함)
    - connections: Cross-BC 이벤트 연결
    - allBCs: 필터용 BC 목록
    """
    
    SmartLogger.log(
        "INFO",
        "BigPicture timeline requested: building BC swimlanes with events and cross-BC connections.",
        category="api.graph.bigpicture.request",
        params=http_context(request),
    )

    # 1. 모든 BC와 관련 데이터 조회
    swimlanes_query = """
    MATCH (bc:BoundedContext)
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(evt:Event)
    OPTIONAL MATCH (us:UserStory)-[:IMPLEMENTS]->(bc)
    
    WITH bc, 
         collect(DISTINCT {
             id: evt.id,
             name: evt.name,
             displayName: evt.displayName,
             commandId: cmd.id,
             commandName: cmd.name,
             aggregateId: agg.id,
             aggregateName: agg.name,
             actor: cmd.actor,
             version: evt.version
         }) as eventsRaw,
         collect(DISTINCT cmd.actor) as actorsRaw,
         collect(DISTINCT us.role) as userRoles
    
    // Filter out null events
    WITH bc, 
         [e IN eventsRaw WHERE e.id IS NOT NULL] as events,
         [a IN actorsRaw WHERE a IS NOT NULL] as actors,
         [r IN userRoles WHERE r IS NOT NULL] as roles
    
    // Combine actors from commands and user story roles
    WITH bc, events, 
         [x IN (actors + roles) WHERE x IS NOT NULL | x] as allActors
    
    RETURN {
        bcId: bc.id,
        bcName: bc.name,
        bcDisplayName: bc.displayName,
        bcDescription: bc.description,
        actors: allActors,
        events: events
    } as swimlane
    ORDER BY bc.name
    """

    # 2. Cross-BC 연결 조회 (Event → TRIGGERS → Policy → INVOKES → Command → EMITS → Event)
    connections_query = """
    // Find Event → TRIGGERS → Policy connections (cross-BC)
    MATCH (sourceEvt:Event)<-[:EMITS]-(sourceCmd:Command)<-[:HAS_COMMAND]-(sourceAgg:Aggregate)<-[:HAS_AGGREGATE]-(sourceBc:BoundedContext)
    MATCH (sourceEvt)-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(targetBc:BoundedContext)
    WHERE sourceBc <> targetBc
    
    // Get the Command invoked by Policy and its resulting Event
    OPTIONAL MATCH (pol)-[:INVOKES]->(targetCmd:Command)-[:EMITS]->(targetEvt:Event)
    
    RETURN {
        sourceEventId: sourceEvt.id,
        sourceEventName: sourceEvt.name,
        sourceBcId: sourceBc.id,
        sourceBcName: sourceBc.name,
        
        policyId: pol.id,
        policyName: pol.name,
        
        targetCommandId: targetCmd.id,
        targetCommandName: targetCmd.name,
        targetEventId: targetEvt.id,
        targetEventName: targetEvt.name,
        targetBcId: targetBc.id,
        targetBcName: targetBc.name
    } as connection
    """

    # 3. Same-BC Policy 연결 조회 (Event → TRIGGERS → Policy within same BC)
    same_bc_connections_query = """
    MATCH (sourceEvt:Event)<-[:EMITS]-(sourceCmd:Command)<-[:HAS_COMMAND]-(sourceAgg:Aggregate)<-[:HAS_AGGREGATE]-(bc:BoundedContext)
    MATCH (sourceEvt)-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(bc)
    
    // Get the Command invoked by Policy and its resulting Event
    OPTIONAL MATCH (pol)-[:INVOKES]->(targetCmd:Command)-[:EMITS]->(targetEvt:Event)
    WHERE targetEvt <> sourceEvt
    
    RETURN {
        sourceEventId: sourceEvt.id,
        sourceEventName: sourceEvt.name,
        bcId: bc.id,
        bcName: bc.name,
        
        policyId: pol.id,
        policyName: pol.name,
        
        targetCommandId: targetCmd.id,
        targetCommandName: targetCmd.name,
        targetEventId: targetEvt.id,
        targetEventName: targetEvt.name,
        isSameBC: true
    } as connection
    """

    with get_session() as session:
        # Get swimlanes
        swimlanes_result = session.run(swimlanes_query)
        swimlanes_raw = [dict(record["swimlane"]) for record in swimlanes_result]

        # Collect all events first (before sequence assignment)
        all_events = {}  # event_id -> event_data
        all_bcs = []
        bc_to_events = {}  # bc_id -> list of event_ids
        
        for lane in swimlanes_raw:
            bc_id = lane["bcId"]
            bc_name = lane["bcName"]
            bc_display_name = lane.get("bcDisplayName")

            all_bcs.append({
                "id": bc_id,
                "name": bc_name,
                "displayName": bc_display_name or bc_name
            })

            events = lane.get("events", [])
            bc_to_events[bc_id] = []
            
            for evt in events:
                evt_id = evt["id"]
                all_events[evt_id] = {
                    "id": evt_id,
                    "name": evt.get("name"),
                    "displayName": evt.get("displayName"),
                    "commandId": evt.get("commandId"),
                    "commandName": evt.get("commandName"),
                    "aggregateId": evt.get("aggregateId"),
                    "aggregateName": evt.get("aggregateName"),
                    "actor": evt.get("actor"),
                    "bcId": bc_id,
                    "bcName": bc_name,
                    "bcDisplayName": bc_display_name,
                    "bcDescription": lane.get("bcDescription"),
                    "triggeredPolicies": []
                }
                bc_to_events[bc_id].append(evt_id)

        # Get cross-BC connections
        connections_result = session.run(connections_query)
        connections = []
        event_dependencies = {}  # source_event_id -> [target_event_id, ...]
        
        for record in connections_result:
            conn = dict(record["connection"])
            if conn.get("sourceEventId") and conn.get("targetEventId"):
                source_id = conn.get("sourceEventId")
                target_id = conn.get("targetEventId")
                
                connections.append({
                    "sourceEventId": source_id,
                    "targetEventId": target_id,
                    "policyId": conn.get("policyId"),
                    "policyName": conn.get("policyName"),
                    "type": "cross-bc",
                    "sourceBcId": conn.get("sourceBcId"),
                    "targetBcId": conn.get("targetBcId")
                })
                
                # Build dependency graph
                # Only add dependency if both events exist in all_events
                if source_id in all_events and target_id in all_events:
                    if source_id not in event_dependencies:
                        event_dependencies[source_id] = []
                    if target_id not in event_dependencies[source_id]:
                        event_dependencies[source_id].append(target_id)
                
                # Add triggered policy info
                if source_id in all_events:
                    all_events[source_id]["triggeredPolicies"].append({
                        "policyId": conn.get("policyId"),
                        "policyName": conn.get("policyName"),
                        "targetBcName": conn.get("targetBcName"),
                        "targetEventId": target_id,
                        "targetEventName": conn.get("targetEventName")
                    })
            elif conn.get("sourceEventId") and conn.get("policyId"):
                # Event triggers policy but no downstream event yet
                source_id = conn.get("sourceEventId")
                if source_id in all_events:
                    all_events[source_id]["triggeredPolicies"].append({
                        "policyId": conn.get("policyId"),
                        "policyName": conn.get("policyName"),
                        "targetBcName": conn.get("targetBcName"),
                        "targetEventId": None,
                        "targetEventName": None
                    })

        # Get same-BC connections
        same_bc_result = session.run(same_bc_connections_query)
        
        for record in same_bc_result:
            conn = dict(record["connection"])
            if conn.get("sourceEventId") and conn.get("targetEventId"):
                source_id = conn.get("sourceEventId")
                target_id = conn.get("targetEventId")
                
                connections.append({
                    "sourceEventId": source_id,
                    "targetEventId": target_id,
                    "policyId": conn.get("policyId"),
                    "policyName": conn.get("policyName"),
                    "type": "same-bc",
                    "bcId": conn.get("bcId")
                })
                
                # Build dependency graph
                # Only add dependency if both events exist in all_events
                if source_id in all_events and target_id in all_events:
                    if source_id not in event_dependencies:
                        event_dependencies[source_id] = []
                    if target_id not in event_dependencies[source_id]:
                        event_dependencies[source_id].append(target_id)
                
                # Add triggered policy info
                bc_id = conn.get("bcId")
                if source_id in all_events:
                    existing = [p for p in all_events[source_id]["triggeredPolicies"] if p.get("policyId") == conn.get("policyId")]
                    if not existing:
                        all_events[source_id]["triggeredPolicies"].append({
                            "policyId": conn.get("policyId"),
                            "policyName": conn.get("policyName"),
                            "targetBcName": conn.get("bcName"),
                            "targetEventId": target_id,
                            "targetEventName": conn.get("targetEventName")
                        })

        # Note: We intentionally do NOT create dependencies based on same-Aggregate command order.
        # Events within the same BC that have no explicit Policy-based dependencies should
        # be at the same sequence level (same step), allowing them to be stacked vertically.
        # For example, OrderPlaced and OrderCancelled in the same BC should be at the same
        # sequence if they don't have explicit dependencies via Policy connections.

        # Topological sort for global sequence assignment
        event_to_sequence = {}  # event_id -> sequence
        
        def topological_sort():
            # Initialize in-degree for all events
            in_degree = {evt_id: 0 for evt_id in all_events.keys()}
            
            # Calculate in-degree based on dependencies
            for source_id, targets in event_dependencies.items():
                for target_id in targets:
                    if target_id in in_degree:
                        in_degree[target_id] += 1
            
            # Debug: Log dependency graph
            SmartLogger.log(
                "DEBUG",
                f"Topological sort: {len(all_events)} events, {len(event_dependencies)} sources with dependencies",
                category="api.graph.bigpicture.toposort",
                params={
                    "total_events": len(all_events),
                    "dependency_sources": len(event_dependencies),
                    "total_dependencies": sum(len(targets) for targets in event_dependencies.values()),
                    "events_with_in_degree_0": len([evt_id for evt_id, degree in in_degree.items() if degree == 0])
                }
            )
            
            # Find all events with no dependencies (in-degree = 0)
            queue = [evt_id for evt_id, degree in in_degree.items() if degree == 0]
            result = []
            current_sequence = 1
            
            # Process events level by level (BFS-like)
            while queue:
                level_size = len(queue)
                level_events = []
                
                # Process all events at current level
                for _ in range(level_size):
                    evt_id = queue.pop(0)
                    level_events.append(evt_id)
                    result.append(evt_id)
                
                # Assign same sequence to all events at this level
                for evt_id in level_events:
                    event_to_sequence[evt_id] = current_sequence
                
                # Find next level events
                next_level = []
                for evt_id in level_events:
                    for dep in event_dependencies.get(evt_id, []):
                        if dep in in_degree:
                            in_degree[dep] -= 1
                            if in_degree[dep] == 0:
                                next_level.append(dep)
                
                queue = next_level
                current_sequence += 1
            
            # Assign sequence to events not in dependency graph (standalone events)
            # Group them by BC and assign same sequence if they have no dependencies
            standalone_events = [evt_id for evt_id in all_events.keys() if evt_id not in event_to_sequence]
            if standalone_events:
                # Group standalone events by BC
                standalone_by_bc = {}
                for evt_id in standalone_events:
                    bc_id = all_events[evt_id]["bcId"]
                    if bc_id not in standalone_by_bc:
                        standalone_by_bc[bc_id] = []
                    standalone_by_bc[bc_id].append(evt_id)
                
                # Assign same sequence to standalone events in same BC
                for bc_id, evt_ids in standalone_by_bc.items():
                    for evt_id in evt_ids:
                        event_to_sequence[evt_id] = current_sequence
                    current_sequence += 1
            
            return result

        topological_sort()

        # Build swimlanes with phase-ordered sequences
        swimlanes = []
        for lane in swimlanes_raw:
            bc_id = lane["bcId"]
            bc_name = lane["bcName"]
            bc_display_name = lane.get("bcDisplayName")
            actors = list(set(lane.get("actors", [])))

            processed_events = []
            for evt_id in bc_to_events.get(bc_id, []):
                if evt_id in all_events:
                    evt_data = all_events[evt_id]
                    sequence = event_to_sequence.get(evt_id, 999)  # Default to high number if not assigned
                    
                    processed_events.append({
                        "id": evt_data["id"],
                        "name": evt_data.get("name"),
                        "displayName": evt_data.get("displayName"),
                        "sequence": sequence,
                        "commandId": evt_data.get("commandId"),
                        "commandName": evt_data.get("commandName"),
                        "aggregateId": evt_data.get("aggregateId"),
                        "aggregateName": evt_data.get("aggregateName"),
                        "actor": evt_data.get("actor"),
                        "triggeredPolicies": evt_data.get("triggeredPolicies", [])
                    })
            
            # Sort events by sequence
            processed_events.sort(key=lambda e: e["sequence"])
            
            swimlanes.append({
                "bcId": bc_id,
                "bcName": bc_name,
                "bcDisplayName": bc_display_name,
                "bcDescription": lane.get("bcDescription"),
                "actors": actors if actors else ["System"],
                "events": processed_events
            })

        payload = {
            "swimlanes": swimlanes,
            "connections": connections,
            "allBCs": all_bcs
        }
        
        SmartLogger.log(
            "INFO",
            "BigPicture timeline returned.",
            category="api.graph.bigpicture.done",
            params={
                **http_context(request),
                "summary": {
                    "swimlanes": len(swimlanes),
                    "connections": len(connections),
                    "totalEvents": sum(len(lane["events"]) for lane in swimlanes)
                }
            }
        )
        
        return payload


@router.get("/bigpicture-timeline/{bc_id}")
async def get_bigpicture_timeline_for_bc(bc_id: str, request: Request) -> dict[str, Any]:
    """
    GET /api/graph/bigpicture-timeline/{bc_id}
    
    특정 BC와 outbound flow로 연결된 BC들의 타임라인 데이터 반환:
    - 시작 BC에서 outbound되는 Event → Policy → Command → Event 체인을 따라 연결된 모든 BC 포함
    - phase 순서를 고려한 sequence 계산
    """
    
    SmartLogger.log(
        "INFO",
        f"BigPicture timeline requested for BC {bc_id}: building swimlanes with outbound flow.",
        category="api.graph.bigpicture.request",
        params={**http_context(request), "bc_id": bc_id},
    )

    # 1. 시작 BC와 outbound flow로 연결된 모든 BC 찾기 (재귀적으로)
    with get_session() as session:
        # First, find all connected BCs through outbound flow
        connected_bcs_result = session.run(
            """
            MATCH (startBc:BoundedContext {id: $bc_id})
            
            // Find all BCs connected via outbound flow: Event → TRIGGERS → Policy → INVOKES → Command → EMITS → Event
            OPTIONAL MATCH (startBc)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(:Command)-[:EMITS]->(sourceEvt:Event)
                   -[:TRIGGERS]->(:Policy)<-[:HAS_POLICY]-(targetBc:BoundedContext)
            
            // Collect all connected BC IDs (including start BC)
            WITH startBc.id as startBcId, collect(DISTINCT targetBc.id) as targetBcIds
            
            // Combine start BC with target BCs
            WITH targetBcIds + [startBcId] as connectedBcIds
            
            // Unwind and return
            UNWIND connectedBcIds as bcId
            WITH bcId
            WHERE bcId IS NOT NULL
            RETURN DISTINCT bcId
            """,
            bc_id=bc_id
        )
        connected_bc_ids = [record["bcId"] for record in connected_bcs_result if record["bcId"]]
        
        if not connected_bc_ids:
            # If no connections found, just use the starting BC
            connected_bc_ids = [bc_id]

        # 2. 연결된 BC들의 swimlane 데이터 조회
        swimlanes_query = """
        MATCH (bc:BoundedContext)
        WHERE bc.id IN $bc_ids
        OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(evt:Event)
        OPTIONAL MATCH (us:UserStory)-[:IMPLEMENTS]->(bc)
        
        WITH bc, 
             collect(DISTINCT {
                 id: evt.id,
                 name: evt.name,
                 displayName: evt.displayName,
                 commandId: cmd.id,
                 commandName: cmd.name,
                 aggregateId: agg.id,
                 aggregateName: agg.name,
                 actor: cmd.actor,
                 version: evt.version
             }) as eventsRaw,
             collect(DISTINCT cmd.actor) as actorsRaw,
             collect(DISTINCT us.role) as userRoles
        
        // Filter out null events
        WITH bc, 
             [e IN eventsRaw WHERE e.id IS NOT NULL] as events,
             [a IN actorsRaw WHERE a IS NOT NULL] as actors,
             [r IN userRoles WHERE r IS NOT NULL] as roles
        
        // Combine actors from commands and user story roles
        WITH bc, events, 
             [x IN (actors + roles) WHERE x IS NOT NULL | x] as allActors
        
        RETURN {
            bcId: bc.id,
            bcName: bc.name,
            bcDisplayName: bc.displayName,
            bcDescription: bc.description,
            actors: allActors,
            events: events
        } as swimlane
        ORDER BY bc.name
        """

        # Get swimlanes for connected BCs
        swimlanes_result = session.run(swimlanes_query, bc_ids=connected_bc_ids)
        swimlanes_raw = [dict(record["swimlane"]) for record in swimlanes_result]

        # Process swimlanes: assign sequence numbers based on phase order
        swimlanes = []
        all_bcs = []
        global_event_map = {}  # id -> swimlane info
        event_to_sequence = {}  # eventId -> sequence (based on phase order)

        # Build event dependency graph for phase ordering
        # Events that trigger policies come before events emitted by policy-invoked commands
        event_dependencies = {}  # eventId -> [dependent eventIds]
        
        # First pass: collect all events and their dependencies
        for lane in swimlanes_raw:
            for evt in lane.get("events", []):
                event_dependencies[evt["id"]] = []

        # 3. Cross-BC 연결 조회 쿼리 정의 (Event → TRIGGERS → Policy → INVOKES → Command → EMITS → Event)
        connections_query = """
        MATCH (sourceEvt:Event)<-[:EMITS]-(sourceCmd:Command)<-[:HAS_COMMAND]-(sourceAgg:Aggregate)<-[:HAS_AGGREGATE]-(sourceBc:BoundedContext)
        MATCH (sourceEvt)-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(targetBc:BoundedContext)
        WHERE sourceBc <> targetBc
           AND sourceBc.id IN $bc_ids
           AND targetBc.id IN $bc_ids
        
        OPTIONAL MATCH (pol)-[:INVOKES]->(targetCmd:Command)-[:EMITS]->(targetEvt:Event)
        
        RETURN {
            sourceEventId: sourceEvt.id,
            sourceEventName: sourceEvt.name,
            sourceBcId: sourceBc.id,
            sourceBcName: sourceBc.name,
            
            policyId: pol.id,
            policyName: pol.name,
            
            targetCommandId: targetCmd.id,
            targetCommandName: targetCmd.name,
            targetEventId: targetEvt.id,
            targetEventName: targetEvt.name,
            targetBcId: targetBc.id,
            targetBcName: targetBc.name
        } as connection
        """

        # Get connections to build dependency graph
        connections_result_temp = session.run(connections_query, bc_ids=connected_bc_ids)
        for record in connections_result_temp:
            conn = dict(record["connection"])
            source_id = conn.get("sourceEventId")
            target_id = conn.get("targetEventId")
            if source_id and target_id:
                if source_id not in event_dependencies:
                    event_dependencies[source_id] = []
                if target_id not in event_dependencies:
                    event_dependencies[target_id] = []
                event_dependencies[source_id].append(target_id)

        # Topological sort for phase ordering - same level events get same sequence
        def topological_sort():
            # Initialize in-degree for all events
            in_degree = {evt_id: 0 for evt_id in event_dependencies}
            
            # Calculate in-degree based on dependencies
            for evt_id, deps in event_dependencies.items():
                for dep in deps:
                    if dep in in_degree:
                        in_degree[dep] += 1
            
            # Find all events with no dependencies (in-degree = 0)
            queue = [evt_id for evt_id, degree in in_degree.items() if degree == 0]
            result = []
            current_sequence = 1
            
            # Process events level by level (BFS-like)
            while queue:
                level_size = len(queue)
                level_events = []
                
                # Process all events at current level
                for _ in range(level_size):
                    evt_id = queue.pop(0)
                    level_events.append(evt_id)
                    result.append(evt_id)
                
                # Assign same sequence to all events at this level
                for evt_id in level_events:
                    event_to_sequence[evt_id] = current_sequence
                
                # Find next level events
                next_level = []
                for evt_id in level_events:
                    for dep in event_dependencies.get(evt_id, []):
                        if dep in in_degree:
                            in_degree[dep] -= 1
                            if in_degree[dep] == 0:
                                next_level.append(dep)
                
                queue = next_level
                current_sequence += 1
            
            # Assign sequence to events not in dependency graph (standalone events)
            # Group them by BC and assign same sequence if they have no dependencies
            all_event_ids = set()
            for lane in swimlanes_raw:
                for evt in lane.get("events", []):
                    all_event_ids.add(evt["id"])
            
            standalone_events = [evt_id for evt_id in all_event_ids if evt_id not in event_to_sequence]
            if standalone_events:
                # Group standalone events by BC
                standalone_by_bc = {}
                for evt_id in standalone_events:
                    # Find BC for this event
                    bc_id = None
                    for lane in swimlanes_raw:
                        for evt in lane.get("events", []):
                            if evt["id"] == evt_id:
                                bc_id = lane["bcId"]
                                break
                        if bc_id:
                            break
                    
                    if bc_id:
                        if bc_id not in standalone_by_bc:
                            standalone_by_bc[bc_id] = []
                        standalone_by_bc[bc_id].append(evt_id)
                
                # Assign same sequence to standalone events in same BC
                for bc_id, evt_ids in standalone_by_bc.items():
                    for evt_id in evt_ids:
                        event_to_sequence[evt_id] = current_sequence
                    current_sequence += 1
            
            return result

        topological_sort()

        # Process swimlanes with phase-ordered sequences
        for idx, lane in enumerate(swimlanes_raw):
            bc_id_lane = lane["bcId"]
            bc_name = lane["bcName"]
            bc_display_name = lane.get("bcDisplayName")

            all_bcs.append({
                "id": bc_id_lane,
                "name": bc_name,
                "displayName": bc_display_name or bc_name
            })

            events = lane.get("events", [])
            actors = list(set(lane.get("actors", [])))
            
            # Sort events by phase order (sequence from topological sort)
            # If event not in topological sort, use a default sequence
            processed_events = []
            for evt in events:
                evt_id = evt["id"]
                sequence = event_to_sequence.get(evt_id, 999)  # Default to high number if not in sort
                
                event_data = {
                    "id": evt_id,
                    "name": evt.get("name"),
                    "displayName": evt.get("displayName"),
                    "sequence": sequence,
                    "commandId": evt.get("commandId"),
                    "commandName": evt.get("commandName"),
                    "aggregateId": evt.get("aggregateId"),
                    "aggregateName": evt.get("aggregateName"),
                    "actor": evt.get("actor"),
                    "triggeredPolicies": []
                }
                processed_events.append(event_data)
                global_event_map[evt_id] = {
                    "bcId": bc_id_lane,
                    "sequence": sequence
                }
            
            # Sort events by sequence
            processed_events.sort(key=lambda e: e["sequence"])
            
            swimlanes.append({
                "bcId": bc_id_lane,
                "bcName": bc_name,
                "bcDisplayName": bc_display_name,
                "bcDescription": lane.get("bcDescription"),
                "actors": actors if actors else ["System"],
                "events": processed_events
            })

        # 4. Same-BC Policy 연결 조회
        same_bc_connections_query = """
        MATCH (sourceEvt:Event)<-[:EMITS]-(sourceCmd:Command)<-[:HAS_COMMAND]-(sourceAgg:Aggregate)<-[:HAS_AGGREGATE]-(bc:BoundedContext)
        MATCH (sourceEvt)-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(bc)
        WHERE bc.id IN $bc_ids
        
        OPTIONAL MATCH (pol)-[:INVOKES]->(targetCmd:Command)-[:EMITS]->(targetEvt:Event)
        WHERE targetEvt <> sourceEvt
        
        RETURN {
            sourceEventId: sourceEvt.id,
            sourceEventName: sourceEvt.name,
            bcId: bc.id,
            bcName: bc.name,
            
            policyId: pol.id,
            policyName: pol.name,
            
            targetCommandId: targetCmd.id,
            targetCommandName: targetCmd.name,
            targetEventId: targetEvt.id,
            targetEventName: targetEvt.name,
            isSameBC: true
        } as connection
        """

        # Get cross-BC connections
        connections_result = session.run(connections_query, bc_ids=connected_bc_ids)
        connections = []
        
        for record in connections_result:
            conn = dict(record["connection"])
            if conn.get("sourceEventId") and conn.get("targetEventId"):
                connections.append({
                    "sourceEventId": conn["sourceEventId"],
                    "targetEventId": conn["targetEventId"],
                    "policyId": conn.get("policyId"),
                    "policyName": conn.get("policyName"),
                    "type": "cross-bc",
                    "sourceBcId": conn.get("sourceBcId"),
                    "targetBcId": conn.get("targetBcId")
                })
                
                # Add triggered policy info to source event
                for lane in swimlanes:
                    for evt in lane["events"]:
                        if evt["id"] == conn["sourceEventId"]:
                            evt["triggeredPolicies"].append({
                                "policyId": conn.get("policyId"),
                                "policyName": conn.get("policyName"),
                                "targetBcName": conn.get("targetBcName"),
                                "targetEventId": conn.get("targetEventId"),
                                "targetEventName": conn.get("targetEventName")
                            })

        # Get same-BC connections
        same_bc_result = session.run(same_bc_connections_query, bc_ids=connected_bc_ids)
        
        for record in same_bc_result:
            conn = dict(record["connection"])
            if conn.get("sourceEventId") and conn.get("targetEventId"):
                connections.append({
                    "sourceEventId": conn["sourceEventId"],
                    "targetEventId": conn["targetEventId"],
                    "policyId": conn.get("policyId"),
                    "policyName": conn.get("policyName"),
                    "type": "same-bc",
                    "bcId": conn.get("bcId")
                })
                
                # Add triggered policy info
                for lane in swimlanes:
                    if lane["bcId"] == conn.get("bcId"):
                        for evt in lane["events"]:
                            if evt["id"] == conn["sourceEventId"]:
                                existing = [p for p in evt["triggeredPolicies"] if p["policyId"] == conn.get("policyId")]
                                if not existing:
                                    evt["triggeredPolicies"].append({
                                        "policyId": conn.get("policyId"),
                                        "policyName": conn.get("policyName"),
                                        "targetBcName": conn.get("bcName"),
                                        "targetEventId": conn.get("targetEventId"),
                                        "targetEventName": conn.get("targetEventName")
                                    })

        payload = {
            "swimlanes": swimlanes,
            "connections": connections,
            "allBCs": all_bcs
        }
        
        SmartLogger.log(
            "INFO",
            f"BigPicture timeline returned for BC {bc_id}.",
            category="api.graph.bigpicture.done",
            params={
                **http_context(request),
                "bc_id": bc_id,
                "summary": {
                    "swimlanes": len(swimlanes),
                    "connections": len(connections),
                    "totalEvents": sum(len(lane["events"]) for lane in swimlanes)
                }
            }
        )
        
        return payload

