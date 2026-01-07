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

        # Process swimlanes: assign sequence numbers to events
        swimlanes = []
        all_bcs = []
        global_event_map = {}  # id -> swimlane info

        for idx, lane in enumerate(swimlanes_raw):
            bc_id = lane["bcId"]
            bc_name = lane["bcName"]
            
            all_bcs.append({
                "id": bc_id,
                "name": bc_name
            })
            
            # Group events by actor and assign sequence
            events = lane.get("events", [])
            actors = list(set(lane.get("actors", [])))
            
            # Sort events by command name (as proxy for temporal order)
            # In real implementation, this could use timestamp or explicit order
            events_sorted = sorted(events, key=lambda e: (e.get("aggregateName") or "", e.get("commandName") or "", e.get("name") or ""))
            
            processed_events = []
            for seq, evt in enumerate(events_sorted, start=1):
                event_data = {
                    "id": evt["id"],
                    "name": evt["name"],
                    "sequence": seq,
                    "commandId": evt.get("commandId"),
                    "commandName": evt.get("commandName"),
                    "aggregateId": evt.get("aggregateId"),
                    "aggregateName": evt.get("aggregateName"),
                    "actor": evt.get("actor"),
                    "triggeredPolicies": []  # Will be populated later
                }
                processed_events.append(event_data)
                global_event_map[evt["id"]] = {
                    "bcId": bc_id,
                    "sequence": seq
                }
            
            swimlanes.append({
                "bcId": bc_id,
                "bcName": bc_name,
                "bcDescription": lane.get("bcDescription"),
                "actors": actors if actors else ["System"],
                "events": processed_events
            })

        # Get cross-BC connections
        connections_result = session.run(connections_query)
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
            elif conn.get("sourceEventId") and conn.get("policyId"):
                # Event triggers policy but no downstream event yet
                for lane in swimlanes:
                    for evt in lane["events"]:
                        if evt["id"] == conn["sourceEventId"]:
                            evt["triggeredPolicies"].append({
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

