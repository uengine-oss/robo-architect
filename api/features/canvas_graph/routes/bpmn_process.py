"""
BPMN Process Flow API - 이벤트 스토밍 데이터 기반 BPMN 프로세스 시각화

프로세스 흐름:
- Actor별 스윔레인
- Command → Event → (Policy) → Command 체이닝
- 시작점: 어떤 Policy로부터도 INVOKE되지 않는 Command
- 종료점: 어떤 Policy도 TRIGGER하지 않는 Event
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/bpmn/process-flows")
async def get_bpmn_process_flows(request: Request) -> dict[str, Any]:
    """
    GET /api/graph/bpmn/process-flows

    프로세스 흐름 목록 반환 (Navigator용):
    - 시작 Command에서 출발하는 각 프로세스 체인 식별
    - 각 흐름의 이름, 시작/끝 요약 반환
    """

    SmartLogger.log(
        "INFO",
        "BPMN process flows requested: identifying process chains from start commands.",
        category="api.graph.bpmn.flows.request",
        params=http_context(request),
    )

    # 시작 Command 찾기: 어떤 Policy로부터도 INVOKE되지 않는 Command
    start_commands_query = """
    MATCH (cmd:Command)<-[:HAS_COMMAND]-(agg:Aggregate)<-[:HAS_AGGREGATE]-(bc:BoundedContext)
    WHERE NOT (:Policy)-[:INVOKES]->(cmd)
    RETURN {
        id: cmd.id,
        name: cmd.name,
        displayName: cmd.displayName,
        actor: cmd.actor,
        aggregateId: agg.id,
        aggregateName: agg.name,
        bcId: bc.id,
        bcName: bc.name
    } as startCommand
    ORDER BY bc.name, cmd.name
    """

    # 한 단계 체인 조회: Command → Event → Policy → next Command
    step_query = """
    MATCH (cmd:Command {id: $cmd_id})-[:EMITS]->(evt:Event)
    OPTIONAL MATCH (evt)-[:TRIGGERS]->(pol:Policy)-[:INVOKES]->(nextCmd:Command)
    RETURN {
        commandId: cmd.id,
        commandName: cmd.name,
        commandDisplayName: cmd.displayName,
        commandActor: cmd.actor,
        eventId: evt.id,
        eventName: evt.name,
        eventDisplayName: evt.displayName,
        nextCommandId: nextCmd.id
    } as step
    """

    with get_session() as session:
        # 1. 시작 Command 목록 조회
        result = session.run(start_commands_query)
        start_commands = [dict(record["startCommand"]) for record in result]

        flows = []
        for cmd in start_commands:
            # 2. BFS로 체인 순회 (Python 레벨에서 반복)
            actors = set()
            end_event_name = None
            unique_commands = set()
            unique_events = set()
            visited_cmds = set()
            queue = [cmd["id"]]

            while queue:
                current_cmd_id = queue.pop(0)
                if current_cmd_id in visited_cmds:
                    continue
                visited_cmds.add(current_cmd_id)

                step_result = session.run(step_query, cmd_id=current_cmd_id)
                for record in step_result:
                    step = dict(record["step"])

                    unique_commands.add(step["commandId"])
                    if step.get("eventId"):
                        unique_events.add(step["eventId"])

                    actor = step.get("commandActor")
                    if actor:
                        actors.add(actor)

                    # 끝점 후보 업데이트
                    evt_display = step.get("eventDisplayName") or step.get("eventName")
                    if evt_display:
                        end_event_name = evt_display

                    next_cmd_id = step.get("nextCommandId")
                    if next_cmd_id and next_cmd_id not in visited_cmds and len(visited_cmds) < 20:
                        queue.append(next_cmd_id)

            cmd_display = cmd.get("displayName") or cmd.get("name")
            flow_name = cmd_display
            if end_event_name:
                flow_name = f"{cmd_display} → {end_event_name}"

            if cmd.get("actor"):
                actors.add(cmd["actor"])

            flows.append({
                "id": cmd["id"],
                "name": flow_name,
                "startCommandId": cmd["id"],
                "startCommandName": cmd_display,
                "endEventName": end_event_name,
                "actors": list(actors) if actors else ["System"],
                "bcId": cmd.get("bcId"),
                "bcName": cmd.get("bcName"),
                "nodeCount": len(unique_commands) + len(unique_events),
            })

        SmartLogger.log(
            "INFO",
            f"BPMN process flows returned: {len(flows)} flows identified.",
            category="api.graph.bpmn.flows.done",
            params={**http_context(request), "flowCount": len(flows)},
        )

        return {"flows": flows}


@router.get("/bpmn/process-flow/{start_command_id}")
async def get_bpmn_process_flow(start_command_id: str, request: Request) -> dict[str, Any]:
    """
    GET /api/graph/bpmn/process-flow/{start_command_id}

    특정 시작 Command에서 출발하는 프로세스 흐름의 BPMN XML 반환.
    Actor별 스윔레인, Command(activity), Event(intermediate event) 매핑.
    """

    SmartLogger.log(
        "INFO",
        f"BPMN process flow requested for command {start_command_id}.",
        category="api.graph.bpmn.flow.request",
        params={**http_context(request), "startCommandId": start_command_id},
    )

    # 시작 Command 정보 조회
    start_cmd_query = """
    MATCH (cmd:Command {id: $cmd_id})<-[:HAS_COMMAND]-(agg:Aggregate)<-[:HAS_AGGREGATE]-(bc:BoundedContext)
    RETURN {
        id: cmd.id, name: cmd.name, displayName: cmd.displayName,
        actor: cmd.actor, aggregateName: agg.name, bcName: bc.name
    } as info
    """

    # 한 단계 확장: Command → Events, Event → Policy → next Command
    expand_cmd_query = """
    MATCH (cmd:Command {id: $cmd_id})-[:EMITS]->(evt:Event)
    OPTIONAL MATCH (evt)-[:TRIGGERS]->(pol:Policy)-[:INVOKES]->(nextCmd:Command)
    OPTIONAL MATCH (cmd)<-[:HAS_COMMAND]-(agg:Aggregate)<-[:HAS_AGGREGATE]-(bc:BoundedContext)
    RETURN {
        cmdId: cmd.id, cmdName: cmd.name, cmdDisplayName: cmd.displayName,
        cmdActor: cmd.actor, cmdDescription: cmd.description,
        aggName: agg.name, bcName: bc.name,
        evtId: evt.id, evtName: evt.name, evtDisplayName: evt.displayName,
        evtDescription: evt.description,
        polId: pol.id, polName: pol.name, polDisplayName: pol.displayName,
        nextCmdId: nextCmd.id
    } as step
    """

    with get_session() as session:
        # 1. 시작 Command 정보
        start_result = session.run(start_cmd_query, cmd_id=start_command_id)
        start_record = start_result.single()
        start_command_info = dict(start_record["info"]) if start_record else None

        # 2. BFS로 체인 순회하며 노드 + 관계 수집
        nodes_map: dict[str, dict] = {}
        relations: list[dict] = []
        visited_cmds: set[str] = set()
        queue = [start_command_id]

        while queue:
            cmd_id = queue.pop(0)
            if cmd_id in visited_cmds:
                continue
            visited_cmds.add(cmd_id)
            if len(visited_cmds) > 30:  # 안전 제한
                break

            step_result = session.run(expand_cmd_query, cmd_id=cmd_id)
            for record in step_result:
                step = dict(record["step"])

                # Command 노드
                c_id = step["cmdId"]
                if c_id and c_id not in nodes_map:
                    nodes_map[c_id] = {
                        "id": c_id,
                        "name": step.get("cmdName"),
                        "displayName": step.get("cmdDisplayName"),
                        "label": "Command",
                        "actor": step.get("cmdActor"),
                        "description": step.get("cmdDescription"),
                        "aggregateName": step.get("aggName"),
                        "bcName": step.get("bcName"),
                    }

                # Event 노드
                e_id = step.get("evtId")
                if e_id and e_id not in nodes_map:
                    nodes_map[e_id] = {
                        "id": e_id,
                        "name": step.get("evtName"),
                        "displayName": step.get("evtDisplayName"),
                        "label": "Event",
                        "description": step.get("evtDescription"),
                    }

                # EMITS 관계
                if c_id and e_id:
                    relations.append({"source": c_id, "target": e_id, "type": "EMITS"})

                # Policy 노드 + TRIGGERS/INVOKES 관계
                pol_id = step.get("polId")
                next_cmd_id = step.get("nextCmdId")
                if pol_id and e_id:
                    if pol_id not in nodes_map:
                        nodes_map[pol_id] = {
                            "id": pol_id,
                            "name": step.get("polName"),
                            "displayName": step.get("polDisplayName"),
                            "label": "Policy",
                        }
                    relations.append({"source": e_id, "target": pol_id, "type": "TRIGGERS"})

                    if next_cmd_id:
                        relations.append({"source": pol_id, "target": next_cmd_id, "type": "INVOKES"})
                        if next_cmd_id not in visited_cmds:
                            queue.append(next_cmd_id)

        # 관계 중복 제거
        seen_rels: set[tuple] = set()
        unique_relations = []
        for rel in relations:
            key = (rel["source"], rel["target"], rel["type"])
            if key not in seen_rels:
                seen_rels.add(key)
                unique_relations.append(rel)
        relations = unique_relations

        # 2.5. Command에 연결된 UI wireframe 정보 조회 (ATTACHED_TO 관계 기반)
        command_ids = [
            nid for nid, n in nodes_map.items() if n["label"] == "Command"
        ]
        ui_map: dict[str, dict] = {}  # commandId → UI 정보
        if command_ids:
            ui_query = """
            MATCH (ui:UI)-[:ATTACHED_TO]->(cmd:Command)
            WHERE cmd.id IN $cmd_ids
            RETURN cmd.id as commandId,
                   ui {.id, .name, .displayName, .description, .template} as ui
            """
            ui_result = session.run(ui_query, cmd_ids=command_ids)
            for record in ui_result:
                cmd_id = record["commandId"]
                ui = dict(record["ui"])
                if cmd_id:
                    ui_map[cmd_id] = ui

        # 3. BPMN XML 생성
        bpmn_xml = _generate_bpmn_xml(
            start_command_info,
            nodes_map,
            relations,
        )

        # 4. 구조화된 데이터도 함께 반환 (프론트엔드에서 직접 사용 가능)
        structured = _build_structured_flow(
            start_command_info,
            nodes_map,
            relations,
        )

        SmartLogger.log(
            "INFO",
            f"BPMN process flow returned for command {start_command_id}.",
            category="api.graph.bpmn.flow.done",
            params={
                **http_context(request),
                "startCommandId": start_command_id,
                "nodeCount": len(nodes_map),
                "relationCount": len(relations),
                "uiCount": len(ui_map),
            },
        )

        return {
            "bpmnXml": bpmn_xml,
            "structured": structured,
            "startCommand": start_command_info,
            "nodes": list(nodes_map.values()),
            "relations": relations,
            "uiMap": ui_map,
        }


def _build_structured_flow(
    start_command: dict | None,
    nodes_map: dict[str, dict],
    relations: list[dict],
) -> dict:
    """프로세스 흐름을 구조화된 데이터로 변환."""

    # Actor별로 노드 그룹핑
    actors: dict[str, list] = {}
    command_to_events: dict[str, list] = {}
    event_to_next: dict[str, dict] = {}  # event -> {policy, command}

    for rel in relations:
        if rel["type"] == "EMITS":
            command_to_events.setdefault(rel["source"], []).append(rel["target"])
        elif rel["type"] == "TRIGGERS":
            event_to_next.setdefault(rel["source"], {})["policy"] = rel["target"]
        elif rel["type"] == "INVOKES":
            # Find which event triggered this policy
            for evt_id, info in event_to_next.items():
                if info.get("policy") == rel["source"]:
                    info["command"] = rel["target"]

    # Command 노드를 actor별로 분류
    for node_id, node in nodes_map.items():
        if node["label"] == "Command":
            actor = node.get("actor") or "System"
            actors.setdefault(actor, [])
            actors[actor].append(node)

    # 순서 결정: BFS로 시작 Command부터 순회
    ordered_steps = []
    visited = set()

    def traverse(cmd_id: str, depth: int = 0):
        if cmd_id in visited or depth > 20:  # 순환 방지
            return
        visited.add(cmd_id)

        cmd_node = nodes_map.get(cmd_id)
        if not cmd_node:
            return

        events = command_to_events.get(cmd_id, [])
        event_nodes = []
        for evt_id in events:
            evt_node = nodes_map.get(evt_id)
            if evt_node:
                event_nodes.append(evt_node)

        ordered_steps.append({
            "command": cmd_node,
            "events": event_nodes,
            "depth": depth,
        })

        # 다음 Command로 이동
        for evt_id in events:
            next_info = event_to_next.get(evt_id, {})
            next_cmd = next_info.get("command")
            if next_cmd:
                traverse(next_cmd, depth + 1)

    if start_command:
        traverse(start_command["id"])

    return {
        "actors": {actor: [n["id"] for n in cmds] for actor, cmds in actors.items()},
        "steps": ordered_steps,
        "commandToEvents": command_to_events,
        "eventToNext": {k: v for k, v in event_to_next.items()},
    }


def _generate_bpmn_xml(
    start_command: dict | None,
    nodes_map: dict[str, dict],
    relations: list[dict],
) -> str:
    """Neo4j 데이터를 BPMN 2.0 XML로 변환."""

    # 관계 인덱스 구축
    command_to_events: dict[str, list[str]] = {}
    event_to_policy: dict[str, str] = {}
    policy_to_command: dict[str, str] = {}

    for rel in relations:
        if rel["type"] == "EMITS":
            command_to_events.setdefault(rel["source"], []).append(rel["target"])
        elif rel["type"] == "TRIGGERS":
            event_to_policy[rel["source"]] = rel["target"]
        elif rel["type"] == "INVOKES":
            policy_to_command[rel["source"]] = rel["target"]

    # Actor별 Command 그룹핑
    actor_commands: dict[str, list[str]] = {}
    for node_id, node in nodes_map.items():
        if node["label"] == "Command":
            actor = node.get("actor") or "System"
            actor_commands.setdefault(actor, []).append(node_id)

    actors = list(actor_commands.keys())
    if not actors:
        actors = ["System"]

    # BFS로 순서 결정
    ordered_elements = []  # [(type, id, depth)]
    visited = set()

    def traverse(cmd_id: str, depth: int = 0):
        if cmd_id in visited or depth > 20:
            return
        visited.add(cmd_id)

        ordered_elements.append(("command", cmd_id, depth))
        events = command_to_events.get(cmd_id, [])
        for evt_id in events:
            if evt_id not in visited:
                visited.add(evt_id)
                ordered_elements.append(("event", evt_id, depth))
                policy_id = event_to_policy.get(evt_id)
                if policy_id:
                    next_cmd = policy_to_command.get(policy_id)
                    if next_cmd:
                        traverse(next_cmd, depth + 1)

    if start_command:
        traverse(start_command["id"])

    # BPMN XML 구성
    process_name = "Process"
    if start_command:
        process_name = start_command.get("displayName") or start_command.get("name") or "Process"

    # ═══════════════════════════════════════════════════════
    # Sugiyama 레이아웃 알고리즘 (process-gpt-vue3 참조)
    # ═══════════════════════════════════════════════════════

    # 레이아웃 상수
    LANE_MIN_HEIGHT = 150
    TASK_WIDTH = 120
    TASK_HEIGHT = 60
    EVENT_SIZE = 36
    EVENT_GAP = 14
    GATEWAY_SIZE = 42
    PARTICIPANT_LABEL_WIDTH = 30
    LANE_LABEL_WIDTH = 30
    LAYER_GAP = 180          # 레이어 간 X 간격
    NODE_GAP = 50            # 같은 레이어 내 Y 간격
    Y_PADDING = 30
    LANE_CONTENT_X = PARTICIPANT_LABEL_WIDTH + LANE_LABEL_WIDTH + 20
    START_EVENT_X = LANE_CONTENT_X + 10

    # Gateway 식별
    gateway_cmd_ids: set[str] = set()
    for cmd_id, evt_ids in command_to_events.items():
        if len(evt_ids) > 1:
            gateway_cmd_ids.add(cmd_id)

    # ── Sugiyama Step 1: 그래프 노드/엣지 구축 ──
    # BPMN 요소를 그래프 노드로 변환
    sg_nodes: dict[str, dict] = {}  # bpmn_ref -> {id, type, w, h, actor, layer, order, x, y}
    sg_edges: list[tuple[str, str]] = []  # (source_ref, target_ref)

    # StartEvent
    start_ref = "StartEvent_1"
    start_actor_name = (start_command or {}).get("actor") or "System"
    sg_nodes[start_ref] = {"type": "start", "w": EVENT_SIZE, "h": EVENT_SIZE, "actor": start_actor_name}

    # EndEvent
    end_ref = "EndEvent_1"
    sg_nodes[end_ref] = {"type": "end", "w": EVENT_SIZE, "h": EVENT_SIZE, "actor": start_actor_name}

    # Task, Gateway, IntermediateEvent 노드
    start_cmd_id = start_command["id"] if start_command else None
    for elem_type, elem_id, depth in ordered_elements:
        if elem_type == "command":
            node = nodes_map.get(elem_id, {})
            task_ref = f"Task_{_safe_id(elem_id)}"
            actor = node.get("actor") or "System"
            sg_nodes[task_ref] = {"type": "task", "w": TASK_WIDTH, "h": TASK_HEIGHT, "actor": actor}

            if elem_id in gateway_cmd_ids:
                gw_ref = f"Gateway_{_safe_id(elem_id)}"
                sg_nodes[gw_ref] = {"type": "gateway", "w": GATEWAY_SIZE, "h": GATEWAY_SIZE, "actor": actor}

        elif elem_type == "event":
            node = nodes_map.get(elem_id, {})
            evt_ref = f"IntEvent_{_safe_id(elem_id)}"
            # Event의 actor = parent command의 actor
            parent_actor = "System"
            for rel in relations:
                if rel["type"] == "EMITS" and rel["target"] == elem_id:
                    pcmd = nodes_map.get(rel["source"], {})
                    parent_actor = pcmd.get("actor") or "System"
                    break
            sg_nodes[evt_ref] = {"type": "event", "w": EVENT_SIZE, "h": EVENT_SIZE, "actor": parent_actor}

    # 엣지 구축 (sequence_flows와 동일한 연결)
    if start_cmd_id:
        sg_edges.append((start_ref, f"Task_{_safe_id(start_cmd_id)}"))

    for elem_type, elem_id, depth in ordered_elements:
        if elem_type == "command":
            task_ref = f"Task_{_safe_id(elem_id)}"
            evt_ids = command_to_events.get(elem_id, [])

            if elem_id in gateway_cmd_ids:
                gw_ref = f"Gateway_{_safe_id(elem_id)}"
                sg_edges.append((task_ref, gw_ref))
                for evt_id in evt_ids:
                    sg_edges.append((gw_ref, f"IntEvent_{_safe_id(evt_id)}"))
            else:
                for evt_id in evt_ids:
                    sg_edges.append((task_ref, f"IntEvent_{_safe_id(evt_id)}"))

            # incoming from events (Policy chain)
            for rel in relations:
                if rel["type"] == "INVOKES" and policy_to_command.get(rel["source"]) == elem_id:
                    for evt_id, pol_id in event_to_policy.items():
                        if pol_id == rel["source"]:
                            sg_edges.append((f"IntEvent_{_safe_id(evt_id)}", task_ref))

        elif elem_type == "event":
            evt_ref = f"IntEvent_{_safe_id(elem_id)}"
            if elem_id not in event_to_policy:
                sg_edges.append((evt_ref, end_ref))

    # ── Sugiyama Step 2: Layer Assignment (BFS) ──
    # 각 노드에 layer 할당 (longest path)
    adj: dict[str, list[str]] = {n: [] for n in sg_nodes}
    for s, t in sg_edges:
        if s in adj:
            adj[s].append(t)

    node_layer: dict[str, int] = {}
    # BFS from start
    from collections import deque
    queue: deque[str] = deque([start_ref])
    node_layer[start_ref] = 0
    visited_order: list[str] = []

    while queue:
        nid = queue.popleft()
        visited_order.append(nid)
        for target in adj.get(nid, []):
            new_layer = node_layer[nid] + 1
            if target not in node_layer or node_layer[target] < new_layer:
                node_layer[target] = new_layer
                queue.append(target)

    # 방문되지 않은 노드 처리
    for nid in sg_nodes:
        if nid not in node_layer:
            node_layer[nid] = 0

    # ── Sugiyama Step 2.5: Optimize Layers ──
    # 모든 엣지가 정방향이 되도록 layer 보정
    changed = True
    iterations = 0
    while changed and iterations < 50:
        changed = False
        iterations += 1
        for s, t in sg_edges:
            if s in node_layer and t in node_layer:
                if node_layer[t] <= node_layer[s]:
                    node_layer[t] = node_layer[s] + 1
                    changed = True

    # 레이어별 노드 그룹핑
    max_layer = max(node_layer.values()) if node_layer else 0
    layers: list[list[str]] = [[] for _ in range(max_layer + 1)]
    for nid, layer in node_layer.items():
        layers[layer].append(nid)

    # ── Sugiyama Step 3: Crossing Minimization (Barycenter) ──
    # 각 레이어의 노드 순서를 인접 레이어의 평균 위치로 정렬
    # 초기 순서: actor별 그룹핑
    actor_index = {a: i for i, a in enumerate(actors)}

    def actor_sort_key(nid: str) -> int:
        a = sg_nodes.get(nid, {}).get("actor", "System")
        return actor_index.get(a, 999)

    for layer in layers:
        layer.sort(key=actor_sort_key)

    # Barycenter sweeps (위→아래, 아래→위 반복)
    for sweep in range(4):
        if sweep % 2 == 0:
            # Forward sweep
            for li in range(1, len(layers)):
                bary: dict[str, float] = {}
                for nid in layers[li]:
                    # 이전 레이어에서 이 노드로 오는 엣지의 source 위치 평균
                    positions = []
                    for s, t in sg_edges:
                        if t == nid and s in node_layer and node_layer[s] == li - 1:
                            prev_layer = layers[li - 1]
                            if s in prev_layer:
                                positions.append(prev_layer.index(s))
                    bary[nid] = sum(positions) / len(positions) if positions else actor_sort_key(nid) * 100
                layers[li].sort(key=lambda n: bary.get(n, 0))
        else:
            # Backward sweep
            for li in range(len(layers) - 2, -1, -1):
                bary = {}
                for nid in layers[li]:
                    positions = []
                    for s, t in sg_edges:
                        if s == nid and t in node_layer and node_layer[t] == li + 1:
                            next_layer = layers[li + 1]
                            if t in next_layer:
                                positions.append(next_layer.index(t))
                    bary[nid] = sum(positions) / len(positions) if positions else actor_sort_key(nid) * 100
                layers[li].sort(key=lambda n: bary.get(n, 0))

    # ── Sugiyama Step 4: Coordinate Assignment ──
    # Actor별 lane 높이 계산 (각 레이어에서 같은 actor에 속한 노드 수 기준)
    actor_max_per_layer: dict[str, int] = {a: 1 for a in actors}
    for layer in layers:
        actor_count: dict[str, int] = {}
        for nid in layer:
            a = sg_nodes.get(nid, {}).get("actor", "System")
            actor_count[a] = actor_count.get(a, 0) + 1
        for a, cnt in actor_count.items():
            actor_max_per_layer[a] = max(actor_max_per_layer.get(a, 1), cnt)

    actor_lane_height: dict[str, int] = {}
    for actor in actors:
        max_n = actor_max_per_layer.get(actor, 1)
        # 가장 큰 노드 높이 기준 (Task가 가장 큼)
        needed = Y_PADDING * 2 + max_n * TASK_HEIGHT + (max_n - 1) * NODE_GAP
        actor_lane_height[actor] = max(LANE_MIN_HEIGHT, needed)

    actor_y: dict[str, int] = {}
    cumulative_y = 0
    for actor in actors:
        actor_y[actor] = cumulative_y
        cumulative_y += actor_lane_height[actor]
    total_height = cumulative_y

    # X 좌표: 레이어 기반
    layer_x: dict[int, float] = {}
    current_x = START_EVENT_X
    for li in range(len(layers)):
        layer_x[li] = current_x
        # 이 레이어의 최대 노드 너비로 간격 결정
        max_w = max((sg_nodes.get(nid, {}).get("w", EVENT_SIZE) for nid in layers[li]), default=EVENT_SIZE)
        current_x += max_w + LAYER_GAP

    total_width = current_x + 60  # EndEvent 여유 공간

    # Y 좌표: actor lane 내에서 해당 레이어의 같은 actor 노드들을 균등 분배
    element_positions: dict[str, dict] = {}
    gateway_positions: dict[str, dict] = {}

    for li, layer in enumerate(layers):
        # 같은 actor의 노드를 그룹핑
        actor_nodes_in_layer: dict[str, list[str]] = {}
        for nid in layer:
            a = sg_nodes.get(nid, {}).get("actor", "System")
            actor_nodes_in_layer.setdefault(a, []).append(nid)

        for actor, nids in actor_nodes_in_layer.items():
            y_base = actor_y.get(actor, 0)
            lane_h = actor_lane_height.get(actor, LANE_MIN_HEIGHT)
            n_nodes = len(nids)

            # 총 그룹 높이 계산
            total_node_h = sum(sg_nodes[nid]["h"] for nid in nids) + (n_nodes - 1) * EVENT_GAP
            group_top = y_base + (lane_h - total_node_h) / 2

            current_node_y = group_top
            for nid in nids:
                sn = sg_nodes[nid]
                x = layer_x[li] + (sg_nodes[nids[0]]["w"] - sn["w"]) / 2 if n_nodes > 1 else layer_x[li]
                # X를 해당 레이어의 중앙에 정렬 (노드 너비 차이 보정)
                x = layer_x[li]

                if sn["type"] == "gateway":
                    gateway_positions[nid.replace("Gateway_", "")] = {
                        "x": x, "y": current_node_y, "width": sn["w"], "height": sn["h"],
                    }
                else:
                    pos_key = nid  # bpmn ref를 키로 사용
                    element_positions[pos_key] = {
                        "x": x, "y": current_node_y, "width": sn["w"], "height": sn["h"],
                    }

                current_node_y += sn["h"] + EVENT_GAP

    # XML 생성
    # 요소별 색상 정의 (스크린샷 기준)
    COLORS = {
        "task":       {"fill": "#F5EDCE", "stroke": "#D4B85C"},
        "startEvent": {"fill": "#E2B43F", "stroke": "#C6A000"},
        "endEvent":   {"fill": "#FAFAFA", "stroke": "#424242"},
        "intEvent":   {"fill": "#F5EDCE", "stroke": "#D4B85C"},
        "gateway":    {"fill": "#FFF8E1", "stroke": "#C6A000"},
        "participant": {"fill": "#FAFAFA", "stroke": "#3949AB"},
        "lane":       {"fill": "#FFFFFF", "stroke": "#3949AB"},
    }

    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"',
        '  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"',
        '  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"',
        '  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"',
        '  xmlns:bioc="http://bpmn.io/schema/bpmn/biocolor/1.0"',
        '  xmlns:color="http://www.omg.org/spec/BPMN/non-normative/color/1.0"',
        f'  id="Definitions_1" targetNamespace="http://robo-architect.io/bpmn">',
        "",
        f'  <bpmn:collaboration id="Collaboration_1">',
    ]

    # 참가자 (전체 프로세스를 하나의 participant로)
    xml_parts.append(f'    <bpmn:participant id="Participant_1" name="{_xml_escape(process_name)}" processRef="Process_1" />')
    xml_parts.append("  </bpmn:collaboration>")
    xml_parts.append("")

    # 프로세스 정의
    xml_parts.append(f'  <bpmn:process id="Process_1" name="{_xml_escape(process_name)}" isExecutable="false">')

    # Gateway 식별: 여러 Event를 EMIT하는 Command에는 Parallel Gateway 삽입
    gateway_commands: set[str] = set()
    for cmd_id, evt_ids in command_to_events.items():
        if len(evt_ids) > 1:
            gateway_commands.add(cmd_id)

    # Lane Set
    xml_parts.append('    <bpmn:laneSet id="LaneSet_1">')
    for i, actor in enumerate(actors):
        lane_id = f"Lane_{i+1}"
        xml_parts.append(f'      <bpmn:lane id="{lane_id}" name="{_xml_escape(actor)}">')
        for node_id, node in nodes_map.items():
            if node["label"] == "Command" and (node.get("actor") or "System") == actor:
                xml_parts.append(f'        <bpmn:flowNodeRef>Task_{_safe_id(node_id)}</bpmn:flowNodeRef>')
                if node_id in gateway_commands:
                    xml_parts.append(f'        <bpmn:flowNodeRef>Gateway_{_safe_id(node_id)}</bpmn:flowNodeRef>')
                for evt_id in command_to_events.get(node_id, []):
                    xml_parts.append(f'        <bpmn:flowNodeRef>IntEvent_{_safe_id(evt_id)}</bpmn:flowNodeRef>')
        if i == 0 and start_command:
            sa = start_command.get("actor") or "System"
            if sa == actor:
                xml_parts.append('        <bpmn:flowNodeRef>StartEvent_1</bpmn:flowNodeRef>')
                xml_parts.append('        <bpmn:flowNodeRef>EndEvent_1</bpmn:flowNodeRef>')
        xml_parts.append("      </bpmn:lane>")
    xml_parts.append("    </bpmn:laneSet>")

    # Start Event
    start_cmd_id = start_command["id"] if start_command else None
    xml_parts.append('    <bpmn:startEvent id="StartEvent_1" name="Start">')
    if start_cmd_id:
        xml_parts.append(f'      <bpmn:outgoing>Flow_start_to_{_safe_id(start_cmd_id)}</bpmn:outgoing>')
    xml_parts.append("    </bpmn:startEvent>")

    # Flow 생성
    flow_counter = [0]

    def next_flow_id():
        flow_counter[0] += 1
        return f"Flow_{flow_counter[0]}"

    sequence_flows = []  # (id, source_ref, target_ref, name)

    for elem_type, elem_id, depth in ordered_elements:
        if elem_type == "command":
            node = nodes_map.get(elem_id, {})
            task_id = f"Task_{_safe_id(elem_id)}"
            name = node.get("displayName") or node.get("name") or elem_id
            xml_parts.append(f'    <bpmn:task id="{task_id}" name="{_xml_escape(name)}">')

            # incoming
            if elem_id == start_cmd_id:
                flow_id = f"Flow_start_to_{_safe_id(elem_id)}"
                xml_parts.append(f'      <bpmn:incoming>{flow_id}</bpmn:incoming>')
                sequence_flows.append((flow_id, "StartEvent_1", task_id, ""))

            for rel in relations:
                if rel["type"] == "INVOKES" and policy_to_command.get(rel["source"]) == elem_id:
                    for evt_id, pol_id in event_to_policy.items():
                        if pol_id == rel["source"]:
                            flow_id = next_flow_id()
                            policy_node = nodes_map.get(rel["source"], {})
                            flow_name = policy_node.get("displayName") or policy_node.get("name") or ""
                            xml_parts.append(f'      <bpmn:incoming>{flow_id}</bpmn:incoming>')
                            sequence_flows.append((flow_id, f"IntEvent_{_safe_id(evt_id)}", task_id, flow_name))

            # outgoing
            evt_ids = command_to_events.get(elem_id, [])
            if elem_id in gateway_commands:
                # Task → Gateway
                gw_id = f"Gateway_{_safe_id(elem_id)}"
                flow_id = next_flow_id()
                xml_parts.append(f'      <bpmn:outgoing>{flow_id}</bpmn:outgoing>')
                sequence_flows.append((flow_id, task_id, gw_id, ""))
            else:
                for evt_id in evt_ids:
                    flow_id = next_flow_id()
                    xml_parts.append(f'      <bpmn:outgoing>{flow_id}</bpmn:outgoing>')
                    sequence_flows.append((flow_id, task_id, f"IntEvent_{_safe_id(evt_id)}", ""))

            xml_parts.append("    </bpmn:task>")

            # Gateway element (여러 이벤트 분기)
            if elem_id in gateway_commands:
                gw_id = f"Gateway_{_safe_id(elem_id)}"
                xml_parts.append(f'    <bpmn:parallelGateway id="{gw_id}" />')
                for evt_id in evt_ids:
                    flow_id = next_flow_id()
                    sequence_flows.append((flow_id, gw_id, f"IntEvent_{_safe_id(evt_id)}", ""))

        elif elem_type == "event":
            node = nodes_map.get(elem_id, {})
            event_bpmn_id = f"IntEvent_{_safe_id(elem_id)}"
            name = node.get("displayName") or node.get("name") or elem_id
            is_end = elem_id not in event_to_policy

            xml_parts.append(f'    <bpmn:intermediateThrowEvent id="{event_bpmn_id}" name="{_xml_escape(name)}">')
            if is_end:
                flow_id = next_flow_id()
                xml_parts.append(f'      <bpmn:outgoing>{flow_id}</bpmn:outgoing>')
                sequence_flows.append((flow_id, event_bpmn_id, "EndEvent_1", ""))
            xml_parts.append("    </bpmn:intermediateThrowEvent>")

    # End Event
    xml_parts.append('    <bpmn:endEvent id="EndEvent_1" name="End" />')

    # Sequence Flows
    for flow_id, source_ref, target_ref, name in sequence_flows:
        name_attr = f' name="{_xml_escape(name)}"' if name else ""
        xml_parts.append(f'    <bpmn:sequenceFlow id="{flow_id}" sourceRef="{source_ref}" targetRef="{target_ref}"{name_attr} />')

    xml_parts.append("  </bpmn:process>")
    xml_parts.append("")

    # BPMN Diagram (DI)
    xml_parts.append('  <bpmndi:BPMNDiagram id="BPMNDiagram_1">')
    xml_parts.append('    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Collaboration_1">')

    # Participant shape
    pc = COLORS["participant"]
    xml_parts.append(f'      <bpmndi:BPMNShape id="Participant_1_di" bpmnElement="Participant_1" isHorizontal="true"'
                     f' bioc:stroke="{pc["stroke"]}" bioc:fill="{pc["fill"]}"'
                     f' color:background-color="{pc["fill"]}" color:border-color="{pc["stroke"]}">')
    xml_parts.append(f'        <dc:Bounds x="0" y="0" width="{total_width}" height="{total_height}" />')
    xml_parts.append("      </bpmndi:BPMNShape>")

    # Lane shapes (동적 높이 적용)
    lc = COLORS["lane"]
    for i, actor in enumerate(actors):
        lane_id = f"Lane_{i+1}"
        y = actor_y[actor]
        h = actor_lane_height[actor]
        xml_parts.append(f'      <bpmndi:BPMNShape id="{lane_id}_di" bpmnElement="{lane_id}" isHorizontal="true"'
                         f' bioc:stroke="{lc["stroke"]}" bioc:fill="{lc["fill"]}"'
                         f' color:background-color="{lc["fill"]}" color:border-color="{lc["stroke"]}">')
        xml_parts.append(f'        <dc:Bounds x="{PARTICIPANT_LABEL_WIDTH}" y="{y}" width="{total_width - PARTICIPANT_LABEL_WIDTH}" height="{h}" />')
        xml_parts.append("      </bpmndi:BPMNShape>")

    # Element shapes (Start, Task, Event, Gateway, End 전부 element_positions에서 참조)
    color_map = {
        "start": COLORS["startEvent"],
        "end": COLORS["endEvent"],
        "task": COLORS["task"],
        "event": COLORS["intEvent"],
        "gateway": COLORS["gateway"],
    }

    # ref_positions: edge waypoint 계산용
    ref_positions: dict[str, dict] = {}

    for bpmn_ref, pos in element_positions.items():
        sn = sg_nodes.get(bpmn_ref, {})
        c = color_map.get(sn.get("type", "event"), COLORS["intEvent"])
        xml_parts.append(f'      <bpmndi:BPMNShape id="{bpmn_ref}_di" bpmnElement="{bpmn_ref}"'
                         f' bioc:stroke="{c["stroke"]}" bioc:fill="{c["fill"]}"'
                         f' color:background-color="{c["fill"]}" color:border-color="{c["stroke"]}">')
        xml_parts.append(f'        <dc:Bounds x="{pos["x"]}" y="{pos["y"]}" width="{pos["width"]}" height="{pos["height"]}" />')
        xml_parts.append("      </bpmndi:BPMNShape>")
        ref_positions[bpmn_ref] = pos

    # Gateway shapes
    gc = COLORS["gateway"]
    for gw_key, gpos in gateway_positions.items():
        gw_bpmn_id = f"Gateway_{_safe_id(gw_key)}"
        xml_parts.append(f'      <bpmndi:BPMNShape id="{gw_bpmn_id}_di" bpmnElement="{gw_bpmn_id}"'
                         f' bioc:stroke="{gc["stroke"]}" bioc:fill="{gc["fill"]}"'
                         f' color:background-color="{gc["fill"]}" color:border-color="{gc["stroke"]}">')
        xml_parts.append(f'        <dc:Bounds x="{gpos["x"]}" y="{gpos["y"]}" width="{gpos["width"]}" height="{gpos["height"]}" />')
        xml_parts.append("      </bpmndi:BPMNShape>")
        ref_positions[gw_bpmn_id] = gpos

    # Sequence Flow edges (직교 경로 생성)
    for flow_id, source_ref, target_ref, _ in sequence_flows:
        source_pos = _get_element_center(source_ref, ref_positions, is_target=False)
        target_pos = _get_element_center(target_ref, ref_positions, is_target=True)
        if source_pos and target_pos:
            waypoints = _generate_orthogonal_waypoints(
                source_pos, target_pos, source_ref, target_ref, ref_positions
            )
            xml_parts.append(f'      <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">')
            for wx, wy in waypoints:
                xml_parts.append(f'        <di:waypoint x="{wx}" y="{wy}" />')
            xml_parts.append("      </bpmndi:BPMNEdge>")

    xml_parts.append("    </bpmndi:BPMNPlane>")
    xml_parts.append("  </bpmndi:BPMNDiagram>")
    xml_parts.append("</bpmn:definitions>")

    return "\n".join(xml_parts)


def _get_element_center(
    bpmn_ref: str,
    ref_positions: dict,
    is_target: bool = False,
    **_kwargs,
) -> tuple[float, float] | None:
    """BPMN 요소의 연결 포인트 좌표 (source=오른쪽 중앙, target=왼쪽 중앙)."""
    pos = ref_positions.get(bpmn_ref)
    if pos:
        cy = pos["y"] + pos["height"] / 2
        if is_target:
            return (pos["x"], cy)
        return (pos["x"] + pos["width"], cy)
    return None


def _generate_orthogonal_waypoints(
    source: tuple[float, float],
    target: tuple[float, float],
    source_ref: str,
    target_ref: str,
    ref_positions: dict,
) -> list[tuple[float, float]]:
    """
    직교(orthogonal) 경로 생성.

    process-gpt-vue3 의 generateEdgeCoordinates() 참조:
    - 같은 Y면 수평 직선
    - Y가 다르면 수평 → 수직 → 수평 (3-segment)
    - 노드 겹침 회피를 위한 중간점 보정
    """
    sx, sy = source
    tx, ty = target

    # 수평 직선: Y 차이가 거의 없으면
    if abs(sy - ty) < 5:
        return [(sx, sy), (tx, ty)]

    # 직교 경로: source 오른쪽 → 중간 X에서 꺾임 → target 왼쪽
    mid_x = (sx + tx) / 2

    # 중간 X가 노드와 겹치지 않도록 보정
    # source와 target 사이 공간의 중앙을 사용
    source_pos = ref_positions.get(source_ref)
    target_pos = ref_positions.get(target_ref)
    if source_pos and target_pos:
        source_right = source_pos["x"] + source_pos["width"]
        target_left = target_pos["x"]
        mid_x = (source_right + target_left) / 2

    return [
        (sx, sy),       # source 출발 (오른쪽 중앙)
        (mid_x, sy),    # 수평 이동
        (mid_x, ty),    # 수직 이동
        (tx, ty),       # target 도착 (왼쪽 중앙)
    ]


def _safe_id(node_id: str) -> str:
    """Neo4j ID를 XML safe ID로 변환."""
    return node_id.replace("-", "_").replace(".", "_").replace("@", "_at_").replace(" ", "_")


def _xml_escape(text: str) -> str:
    """XML 특수문자 이스케이프."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
