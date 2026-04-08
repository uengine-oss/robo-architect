"""
Event Modeling API - 이벤트 모델링 뷰 시각화

Swimlane 구조 (위→아래):
  - Actor swimlane (상단): Actor별 UI 와이어프레임 배치
  - Interaction swimlane (중간): Command(입력) / ReadModel(출력)
  - BC swimlane (하단): BoundedContext별 Event 배치

타임라인 순서 (좌→우):
  진입점 Command(Policy에 의해 INVOKE되지 않는 Command)에서 시작하여
  EMITS → TRIGGERS → INVOKES 체인을 BFS 추적하여 자동 도출.

Vertical Slice (각 열):
  UI(actor) → Command(interaction) → Event(BC) → ReadModel(interaction) → UI(actor)
"""

from __future__ import annotations

from collections import deque
from typing import Any

from fastapi import APIRouter
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/event-modeling")
async def get_event_modeling(request: Request, bc_ids: str | None = None) -> dict[str, Any]:
    """
    GET /api/graph/event-modeling?bc_ids=id1,id2

    Swimlane 기반 이벤트 모델링 데이터 반환.
    bc_ids가 지정되면 해당 BC + Policy 체인으로 연결된 BC만 포함.
    """

    SmartLogger.log(
        "INFO",
        "Event Modeling view requested.",
        category="api.graph.event_modeling.request",
        params=http_context(request),
    )

    # ── 1. 쿼리 ──────────────────────────────────────────────────
    commands_query = """
    MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command)
    OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
    OPTIONAL MATCH (cmdUi:UI)-[:ATTACHED_TO]->(cmd)
    RETURN cmd.id AS cmdId, cmd.name AS cmdName, cmd.displayName AS cmdDisplayName,
           cmd.actor AS cmdActor,
           agg.id AS aggId, agg.name AS aggName,
           bc.id AS bcId, bc.name AS bcName, bc.displayName AS bcDisplayName,
           evt.id AS evtId, evt.name AS evtName, evt.displayName AS evtDisplayName,
           evt.sequence AS evtTimelineSequence,
           cmdUi.id AS cmdUiId, cmdUi.name AS cmdUiName,
           cmdUi.displayName AS cmdUiDisplayName, cmdUi.template AS cmdUiTemplate,
           cmdUi.description AS cmdUiDescription
    """

    readmodels_query = """
    MATCH (bc:BoundedContext)-[:HAS_READMODEL]->(rm:ReadModel)
    OPTIONAL MATCH (rmUi:UI)-[:ATTACHED_TO]->(rm)
    OPTIONAL MATCH (rm)-[:HAS_CQRS]->(:CQRSConfig)-[:HAS_OPERATION]->(op:CQRSOperation)-[:TRIGGERED_BY]->(triggerEvt:Event)
    WITH rm, bc, rmUi, collect(DISTINCT triggerEvt.id) AS triggerEventIds
    RETURN rm.id AS rmId, rm.name AS rmName, rm.displayName AS rmDisplayName,
           rm.actor AS rmActor,
           bc.id AS bcId, bc.name AS bcName,
           rmUi.id AS rmUiId, rmUi.name AS rmUiName,
           rmUi.displayName AS rmUiDisplayName, rmUi.template AS rmUiTemplate,
           triggerEventIds
    """

    chains_query = """
    MATCH (srcEvt:Event)-[:TRIGGERS]->(pol:Policy)-[:INVOKES]->(tgtCmd:Command)
    RETURN srcEvt.id AS sourceEventId, tgtCmd.id AS targetCommandId
    """

    # BC에 직접 연결된 Event (HAS_EVENT) 중 Command EMITS 경로에 없는 것도 표시
    bc_events_query = """
    MATCH (bc:BoundedContext)-[:HAS_EVENT]->(evt:Event)
    WHERE NOT (()-[:EMITS]->(evt))
    RETURN DISTINCT bc.id AS bcId, bc.name AS bcName, bc.displayName AS bcDisplayName,
           evt.id AS evtId, evt.name AS evtName, evt.displayName AS evtDisplayName,
           evt.sequence AS evtTimelineSequence
    """

    with get_session() as session:
        # bc_ids 필터: 지정된 BC + Policy 체인으로 연결된 BC 확장
        filter_bc_ids: set[str] | None = None
        if bc_ids:
            seed_ids = {bid.strip() for bid in bc_ids.split(",") if bid.strip()}
            # 연결된 BC 확장: Event → TRIGGERS → Policy → INVOKES → Command in other BC
            expand_result = session.run(
                """
                MATCH (bc:BoundedContext) WHERE bc.id IN $seeds
                OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(:Command)-[:EMITS]->(evt:Event)
                              -[:TRIGGERS]->(:Policy)<-[:HAS_POLICY]-(otherBc:BoundedContext)
                RETURN collect(DISTINCT bc.id) + collect(DISTINCT otherBc.id) AS allIds
                """,
                seeds=list(seed_ids),
            ).single()
            all_ids = expand_result["allIds"] if expand_result else list(seed_ids)
            filter_bc_ids = {bid for bid in all_ids if bid}

        cmd_records = [dict(r) for r in session.run(commands_query)]
        orphan_event_records = [dict(r) for r in session.run(bc_events_query)]
        rm_records = [dict(r) for r in session.run(readmodels_query)]
        chain_records = [dict(r) for r in session.run(chains_query)]

    # ── 2. 인덱스 구축 (bc_ids 필터 적용) ─────────────────────────
    commands = {}
    events = {}
    cmd_uis = {}
    cmd_to_events = {}
    event_to_cmd = {}
    bc_info = {}

    for r in cmd_records:
        cmd_id = r["cmdId"]
        bc_id = r["bcId"]
        if filter_bc_ids and bc_id not in filter_bc_ids:
            continue
        actor = r["cmdActor"] or "System"

        if cmd_id not in commands:
            commands[cmd_id] = {
                "id": cmd_id,
                "name": r["cmdName"],
                "displayName": r["cmdDisplayName"] or r["cmdName"],
                "actor": actor,
                "aggregateName": r["aggName"],
                "bcId": bc_id,
            }
            cmd_to_events[cmd_id] = []

        if bc_id not in bc_info:
            bc_info[bc_id] = {
                "id": bc_id,
                "name": r["bcName"],
                "displayName": r["bcDisplayName"] or r["bcName"],
            }

        evt_id = r["evtId"]
        if evt_id and evt_id not in events:
            ts = r.get("evtTimelineSequence")
            try:
                stored_seq = int(ts) if ts is not None else None
            except (TypeError, ValueError):
                stored_seq = None
            events[evt_id] = {
                "id": evt_id,
                "name": r["evtName"],
                "displayName": r["evtDisplayName"] or r["evtName"],
                "commandId": cmd_id,
                "commandName": r["cmdName"],
                "actor": actor,
                "bcId": bc_id,
                "storedSequence": stored_seq,
            }
            if evt_id not in cmd_to_events[cmd_id]:
                cmd_to_events[cmd_id].append(evt_id)
            event_to_cmd[evt_id] = cmd_id

        ui_id = r["cmdUiId"]
        if ui_id and cmd_id not in cmd_uis:
            cmd_uis[cmd_id] = {
                "id": ui_id,
                "name": r["cmdUiName"],
                "displayName": r["cmdUiDisplayName"] or r["cmdUiName"],
                "description": r["cmdUiDescription"],
                "template": r["cmdUiTemplate"],
                "actor": actor,
                "commandId": cmd_id,
            }

    for r in orphan_event_records:
        evt_id = r.get("evtId")
        if not evt_id or evt_id in events:
            continue
        if filter_bc_ids and r.get("bcId") not in filter_bc_ids:
            continue
        bc_id = r.get("bcId")
        if not bc_id:
            continue
        ts = r.get("evtTimelineSequence")
        try:
            stored_seq = int(ts) if ts is not None else None
        except (TypeError, ValueError):
            stored_seq = None
        events[evt_id] = {
            "id": evt_id,
            "name": r["evtName"],
            "displayName": r["evtDisplayName"] or r["evtName"],
            "commandId": None,
            "commandName": "",
            "actor": "System",
            "bcId": bc_id,
            "storedSequence": stored_seq,
        }
        if bc_id not in bc_info:
            bc_info[bc_id] = {
                "id": bc_id,
                "name": r["bcName"],
                "displayName": r["bcDisplayName"] or r["bcName"],
            }

    # ReadModel
    readmodels = {}
    rm_uis = {}
    bc_to_rms = {}
    event_to_rms = {}

    for r in rm_records:
        rm_id = r["rmId"]
        bc_id = r["bcId"]
        if filter_bc_ids and bc_id not in filter_bc_ids:
            continue
        if rm_id not in readmodels:
            trigger_evt_ids = [eid for eid in (r.get("triggerEventIds") or []) if eid]
            readmodels[rm_id] = {
                "id": rm_id,
                "name": r["rmName"],
                "displayName": r["rmDisplayName"] or r["rmName"],
                "actor": r["rmActor"] or "user",
                "bcId": bc_id,
                "triggerEventIds": trigger_evt_ids,
            }
            bc_to_rms.setdefault(bc_id, [])
            if rm_id not in bc_to_rms[bc_id]:
                bc_to_rms[bc_id].append(rm_id)
            for evt_id in trigger_evt_ids:
                event_to_rms.setdefault(evt_id, [])
                if rm_id not in event_to_rms[evt_id]:
                    event_to_rms[evt_id].append(rm_id)

        rm_ui_id = r["rmUiId"]
        if rm_ui_id and rm_id not in rm_uis:
            rm_uis[rm_id] = {
                "id": rm_ui_id,
                "name": r["rmUiName"],
                "displayName": r["rmUiDisplayName"] or r["rmUiName"],
                "template": r["rmUiTemplate"],
            }

    # Policy 체인
    event_to_next_cmds = {}
    policy_invoked_cmds = set()
    for r in chain_records:
        src_evt, tgt_cmd = r["sourceEventId"], r["targetCommandId"]
        if src_evt and tgt_cmd:
            event_to_next_cmds.setdefault(src_evt, [])
            if tgt_cmd not in event_to_next_cmds[src_evt]:
                event_to_next_cmds[src_evt].append(tgt_cmd)
            policy_invoked_cmds.add(tgt_cmd)

    # ── 3. Command/ReadModel sequence = 연결된 Event의 storedSequence ──
    # Event의 timeline_seq가 유일한 X축 기준. Command/ReadModel/UI는 여기에 맞춤.
    cmd_sequence = {}  # cmdId -> sequence (Event의 storedSequence)

    for cmd_id in commands:
        evt_ids = cmd_to_events.get(cmd_id, [])
        best_seq = None
        for eid in evt_ids:
            evt = events.get(eid)
            if evt:
                ss = evt.get("storedSequence")
                if ss is not None:
                    seq_val = int(ss)
                    if best_seq is None or seq_val < best_seq:
                        best_seq = seq_val
        cmd_sequence[cmd_id] = best_seq  # None if no Event linked

    # max_sequence: 모든 Event의 storedSequence 중 최대값
    # EMITS 없는 Command: 임시로 큰 값 부여 (압축 단계에서 재매핑됨)
    temp_max = max((s for s in cmd_sequence.values() if s is not None), default=0)
    for ev in events.values():
        ss = ev.get("storedSequence")
        if ss is not None:
            temp_max = max(temp_max, int(ss))
    unlinked_offset = temp_max + 1
    for cmd_id in commands:
        if cmd_sequence.get(cmd_id) is None:
            cmd_sequence[cmd_id] = unlinked_offset
            unlinked_offset += 1

    # ── 3a-2. 병렬 흐름: 같은 Command가 EMITS하는 이벤트는 동일 sequence ──
    # 성공/실패 분기(예: OrderPlaced / OrderPlacementFailed)가 같은 column에 배치됨.
    # 그룹 내 최소 sequence로 통일.
    for cmd_id, evt_ids in cmd_to_events.items():
        if len(evt_ids) <= 1:
            continue
        group_seqs = []
        for eid in evt_ids:
            ev = events.get(eid)
            if ev and ev.get("storedSequence") is not None:
                group_seqs.append(int(ev["storedSequence"]))
        if not group_seqs:
            continue
        min_seq = min(group_seqs)
        for eid in evt_ids:
            ev = events.get(eid)
            if ev and ev.get("storedSequence") is not None:
                ev["storedSequence"] = min_seq

    # ── 3b. Sequence 압축: 표시되는 sequence를 1부터 연속 번호로 재매핑
    # (BC 필터 시 중간이 빈 sequence 30→1, 31→2 등으로 압축)
    used_seqs: set[int] = set()
    for ev in events.values():
        ss = ev.get("storedSequence")
        if ss is not None:
            used_seqs.add(int(ss))
    for cid, seq in cmd_sequence.items():
        if seq is not None:
            used_seqs.add(seq)

    if used_seqs:
        sorted_seqs = sorted(used_seqs)
        seq_remap = {old: new for new, old in enumerate(sorted_seqs, start=1)}

        # 이벤트 재매핑
        for ev in events.values():
            ss = ev.get("storedSequence")
            if ss is not None:
                ev["storedSequence"] = seq_remap.get(int(ss), int(ss))

        # 커맨드 재매핑
        for cid in list(cmd_sequence.keys()):
            old = cmd_sequence[cid]
            if old is not None:
                cmd_sequence[cid] = seq_remap.get(old, old)

        max_sequence = max(seq_remap.values()) if seq_remap else 1
    else:
        max_sequence = 1

    # ── 4. Swimlane 구조 구성 ─────────────────────────────────────

    # --- Actor Swimlanes (상단) ---
    actors_map = {}
    for cmd_id, cmd in commands.items():
        actor = cmd["actor"]
        if actor not in actors_map:
            actors_map[actor] = {"actor": actor, "uis": []}
        ui = cmd_uis.get(cmd_id)
        if ui:
            actors_map[actor]["uis"].append({
                **ui,
                "sequence": cmd_sequence.get(cmd_id, 1),
            })

    # ReadModel UI: CQRS trigger 관계가 있는 경우만 actor swimlane에 배치
    for rm_id, rm in readmodels.items():
        rm_ui = rm_uis.get(rm_id)
        trigger_ids = rm.get("triggerEventIds", [])
        if not rm_ui or not trigger_ids:
            continue  # CQRS 관계 없으면 actor swimlane에 배치하지 않음

        rm_actor = rm["actor"]
        if rm_actor not in actors_map:
            actors_map[rm_actor] = {"actor": rm_actor, "uis": []}
        rm_seq = 1
        for evt_id in trigger_ids:
            trig = events.get(evt_id)
            if trig and trig.get("storedSequence") is not None:
                try:
                    rm_seq = max(rm_seq, int(trig["storedSequence"]))
                except (TypeError, ValueError):
                    pass
        actors_map[rm_actor]["uis"].append({
            **rm_ui,
            "actor": rm_actor,
            "readModelId": rm_id,
            "readModelName": rm["name"],
            "isOutput": True,
            "sequence": rm_seq,
        })

    actor_swimlanes = []
    for actor in sorted(actors_map):
        data = actors_map[actor]
        data["uis"].sort(key=lambda u: u["sequence"])
        actor_swimlanes.append(data)

    # --- Interaction (중간): Commands + ReadModels ---
    interaction_commands = []
    for cmd_id, cmd in commands.items():
        evt_ids = cmd_to_events.get(cmd_id, [])
        interaction_commands.append({
            **cmd,
            "sequence": cmd_sequence.get(cmd_id, 1),
            "uiId": cmd_uis[cmd_id]["id"] if cmd_id in cmd_uis else None,
            "eventIds": evt_ids,
        })
    interaction_commands.sort(key=lambda c: c["sequence"])

    interaction_readmodels = []
    for rm_id, rm in readmodels.items():
        trigger_ids = rm.get("triggerEventIds", [])
        # CQRS 관계 없는 ReadModel은 Interaction에 배치하지 않음
        # (어떤 Event에서 프로비저닝되는지 모르면 적절한 X 배치 불가)
        if not trigger_ids:
            continue

        rm_ui = rm_uis.get(rm_id)
        rm_seq = 1
        for evt_id in trigger_ids:
            trig = events.get(evt_id)
            if trig and trig.get("storedSequence") is not None:
                try:
                    rm_seq = max(rm_seq, int(trig["storedSequence"]))
                except (TypeError, ValueError):
                    pass

        interaction_readmodels.append({
            **rm,
            "sequence": rm_seq,
            "uiId": rm_ui["id"] if rm_ui else None,
            "uiDisplayName": rm_ui["displayName"] if rm_ui else None,
        })
    interaction_readmodels.sort(key=lambda r: r["sequence"])

    # --- System Swimlanes (하단): BC별 Events ---
    bc_events_map = {}
    for evt_id, evt in events.items():
        bc_id = evt["bcId"]
        if bc_id not in bc_events_map:
            bc_events_map[bc_id] = []
        evt_cmd = event_to_cmd.get(evt_id)
        if evt.get("storedSequence") is not None:
            try:
                evt_col = int(evt["storedSequence"])
            except (TypeError, ValueError):
                evt_col = cmd_sequence.get(evt_cmd, 1) if evt_cmd else 1
        else:
            evt_col = cmd_sequence.get(evt_cmd, 1) if evt_cmd else 1
        bc_events_map[bc_id].append({
            **evt,
            "sequence": evt_col,
        })

    system_swimlanes = []
    for bc_id, evts in bc_events_map.items():
        evts.sort(key=lambda e: e["sequence"])
        info = bc_info.get(bc_id, {})
        system_swimlanes.append({
            "bcId": bc_id,
            "bcName": info.get("name", ""),
            "bcDisplayName": info.get("displayName", ""),
            "events": evts,
        })
    system_swimlanes.sort(key=lambda s: s["bcName"])

    # ── 5. 연결선 (flows) ────────────────────────────────────────
    flows = []

    for cmd_id, cmd in commands.items():
        s = cmd_sequence.get(cmd_id, 1)
        # UI → Command
        ui = cmd_uis.get(cmd_id)
        if ui:
            flows.append({
                "type": "ui-to-command",
                "sourceId": ui["id"],
                "targetId": cmd_id,
                "sequence": s,
            })
        # Command → Event
        for evt_id in cmd_to_events.get(cmd_id, []):
            flows.append({
                "type": "command-to-event",
                "sourceId": cmd_id,
                "targetId": evt_id,
                "sequence": s,
            })
            # Event → ReadModel (CQRS)
            for rm_id in event_to_rms.get(evt_id, []):
                flows.append({
                    "type": "event-to-readmodel",
                    "sourceId": evt_id,
                    "targetId": rm_id,
                    "sequence": s,
                })
            # Event → next Command (Policy chain)
            for next_cmd in event_to_next_cmds.get(evt_id, []):
                flows.append({
                    "type": "event-to-command",
                    "sourceId": evt_id,
                    "targetId": next_cmd,
                    "sequence": s,
                })

    # ReadModel → UI (output)
    for rm_id, rm_ui in rm_uis.items():
        flows.append({
            "type": "readmodel-to-ui",
            "sourceId": rm_id,
            "targetId": rm_ui["id"],
        })

    payload = {
        "actorSwimlanes": actor_swimlanes,
        "interactionCommands": interaction_commands,
        "interactionReadModels": interaction_readmodels,
        "systemSwimlanes": system_swimlanes,
        "flows": flows,
        "maxSequence": max_sequence,
    }

    SmartLogger.log(
        "INFO",
        "Event Modeling data returned.",
        category="api.graph.event_modeling.done",
        params={
            **http_context(request),
            "summary": {
                "actorSwimlanes": len(actor_swimlanes),
                "interactionCommands": len(interaction_commands),
                "interactionReadModels": len(interaction_readmodels),
                "systemSwimlanes": len(system_swimlanes),
                "flows": len(flows),
                "maxSequence": max_sequence,
            },
        },
    )

    return payload


@router.put("/event-modeling/reorder")
async def reorder_events(request: Request) -> dict[str, Any]:
    """
    PUT /api/graph/event-modeling/reorder

    Event sequence 일괄 업데이트.
    Body: { "orders": [{ "eventId": "...", "sequence": 3 }, ...] }
    """
    body = await request.json()
    orders = body.get("orders", [])
    if not orders:
        return {"updated": 0}

    with get_session() as session:
        for item in orders:
            evt_id = item.get("eventId")
            seq = item.get("sequence")
            if evt_id and seq is not None:
                session.run(
                    "MATCH (e:Event {id: $id}) SET e.sequence = $seq",
                    id=evt_id,
                    seq=int(seq),
                )

    SmartLogger.log(
        "INFO",
        f"Event reorder: {len(orders)} events updated",
        category="api.graph.event_modeling.reorder",
        params={**http_context(request), "count": len(orders)},
    )

    return {"updated": len(orders)}


@router.post("/event-modeling/nodes")
async def add_event_modeling_node(request: Request) -> dict[str, Any]:
    """
    POST /api/graph/event-modeling/nodes

    Event Modeling 뷰에서 새 노드를 추가.
    Body: {
      "type": "event" | "command" | "readmodel" | "ui",
      "name": "NodeName",
      "displayName": "표시 이름",
      "bcId": "bounded-context-id",
      "sequence": 3,
      "actor": "User",
      "aggregateId": "agg-id"  (command 전용),
      "attachedToId": "cmd-or-rm-id"  (ui 전용),
      "attachedToType": "Command" | "ReadModel"  (ui 전용),
      "isOutput": false  (ui 전용)
    }
    """
    body = await request.json()
    node_type = body.get("type", "").lower()
    name = body.get("name", "NewNode")
    display_name = body.get("displayName", name)
    bc_id = body.get("bcId")
    sequence = body.get("sequence", 1)
    actor = body.get("actor", "User")

    if node_type not in ("event", "command", "readmodel", "ui"):
        return {"error": f"Invalid node type: {node_type}"}

    result_data: dict[str, Any] = {}

    with get_session() as session:
        if node_type == "event":
            if not bc_id:
                return {"error": "bcId is required for event"}
            rec = session.run(
                """
                MATCH (bc:BoundedContext {id: $bcId})
                CREATE (evt:Event {
                    id: randomUUID(),
                    name: $name,
                    displayName: $displayName,
                    sequence: $sequence,
                    actor: $actor,
                    createdAt: datetime(),
                    updatedAt: datetime()
                })
                MERGE (bc)-[:HAS_EVENT]->(evt)
                RETURN evt.id AS id, evt.name AS name, evt.displayName AS displayName
                """,
                bcId=bc_id, name=name, displayName=display_name,
                sequence=int(sequence), actor=actor,
            ).single()
            if rec:
                result_data = {"id": rec["id"], "name": rec["name"], "displayName": rec["displayName"], "type": "event", "bcId": bc_id, "sequence": sequence}

        elif node_type == "command":
            agg_id = body.get("aggregateId")
            if not agg_id:
                # aggregateId 없으면 BC 내 첫 번째 Aggregate 사용
                agg_rec = session.run(
                    "MATCH (bc:BoundedContext {id: $bcId})-[:HAS_AGGREGATE]->(agg:Aggregate) RETURN agg.id AS id LIMIT 1",
                    bcId=bc_id,
                ).single()
                agg_id = agg_rec["id"] if agg_rec else None
            if not agg_id:
                return {"error": "No aggregate found for this BC"}
            rec = session.run(
                """
                MATCH (agg:Aggregate {id: $aggId})
                CREATE (cmd:Command {
                    id: randomUUID(),
                    name: $name,
                    displayName: $displayName,
                    actor: $actor,
                    createdAt: datetime(),
                    updatedAt: datetime()
                })
                MERGE (agg)-[:HAS_COMMAND]->(cmd)
                RETURN cmd.id AS id, cmd.name AS name, cmd.displayName AS displayName
                """,
                aggId=agg_id, name=name, displayName=display_name, actor=actor,
            ).single()
            if rec:
                result_data = {"id": rec["id"], "name": rec["name"], "displayName": rec["displayName"], "type": "command", "bcId": bc_id, "actor": actor}

        elif node_type == "readmodel":
            if not bc_id:
                return {"error": "bcId is required for readmodel"}
            rec = session.run(
                """
                MATCH (bc:BoundedContext {id: $bcId})
                CREATE (rm:ReadModel {
                    id: randomUUID(),
                    name: $name,
                    displayName: $displayName,
                    actor: $actor,
                    createdAt: datetime(),
                    updatedAt: datetime()
                })
                MERGE (bc)-[:HAS_READMODEL]->(rm)
                RETURN rm.id AS id, rm.name AS name, rm.displayName AS displayName
                """,
                bcId=bc_id, name=name, displayName=display_name, actor=actor,
            ).single()
            if rec:
                result_data = {"id": rec["id"], "name": rec["name"], "displayName": rec["displayName"], "type": "readmodel", "bcId": bc_id, "actor": actor}

        elif node_type == "ui":
            attached_to_id = body.get("attachedToId")
            attached_to_type = body.get("attachedToType", "Command")
            rec = session.run(
                """
                CREATE (ui:UI {
                    id: randomUUID(),
                    name: $name,
                    displayName: $displayName,
                    actor: $actor,
                    attachedToId: $attachedToId,
                    attachedToType: $attachedToType,
                    createdAt: datetime(),
                    updatedAt: datetime()
                })
                RETURN ui.id AS id, ui.name AS name, ui.displayName AS displayName
                """,
                name=name, displayName=display_name, actor=actor,
                attachedToId=attached_to_id or "", attachedToType=attached_to_type,
            ).single()
            if rec:
                # ATTACHED_TO 관계 생성
                if attached_to_id:
                    session.run(
                        """
                        MATCH (ui:UI {id: $uiId}), (target {id: $targetId})
                        MERGE (ui)-[:ATTACHED_TO]->(target)
                        """,
                        uiId=rec["id"], targetId=attached_to_id,
                    )
                # BC에도 연결
                if bc_id:
                    session.run(
                        "MATCH (bc:BoundedContext {id: $bcId}), (ui:UI {id: $uiId}) MERGE (bc)-[:HAS_UI]->(ui)",
                        bcId=bc_id, uiId=rec["id"],
                    )
                result_data = {"id": rec["id"], "name": rec["name"], "displayName": rec["displayName"], "type": "ui", "actor": actor}

    SmartLogger.log(
        "INFO",
        f"Event Modeling node added: {node_type}",
        category="api.graph.event_modeling.add_node",
        params={**http_context(request), "nodeType": node_type, "result": result_data},
    )

    return {"node": result_data}


@router.delete("/event-modeling/nodes/{node_type}/{node_id}")
async def delete_event_modeling_node(request: Request, node_type: str, node_id: str) -> dict[str, Any]:
    """
    DELETE /api/graph/event-modeling/nodes/{node_type}/{node_id}

    Event Modeling 뷰에서 노드 삭제. 연결된 관계도 함께 제거.
    """
    label_map = {"event": "Event", "command": "Command", "readmodel": "ReadModel", "ui": "UI"}
    label = label_map.get(node_type.lower())
    if not label:
        return {"error": f"Invalid node type: {node_type}"}

    with get_session() as session:
        # DETACH DELETE로 모든 관계 포함 삭제
        result = session.run(
            f"MATCH (n:{label} {{id: $id}}) DETACH DELETE n RETURN count(n) AS cnt",
            id=node_id,
        ).single()
        deleted = result["cnt"] if result else 0

    SmartLogger.log(
        "INFO",
        f"Event Modeling node deleted: {node_type}/{node_id}",
        category="api.graph.event_modeling.delete_node",
        params={**http_context(request), "nodeType": node_type, "nodeId": node_id, "deleted": deleted},
    )

    return {"deleted": deleted}


@router.put("/event-modeling/move-event")
async def move_event_bc(request: Request) -> dict[str, Any]:
    """
    PUT /api/graph/event-modeling/move-event

    Event를 다른 BoundedContext로 이동.
    Body: { "eventId": "...", "targetBcId": "..." }
    """
    body = await request.json()
    event_id = body.get("eventId")
    target_bc_id = body.get("targetBcId")

    if not event_id or not target_bc_id:
        return {"error": "eventId and targetBcId are required"}

    with get_session() as session:
        # 기존 HAS_EVENT 관계 제거 + 새 BC에 연결
        session.run(
            """
            MATCH (evt:Event {id: $eventId})
            OPTIONAL MATCH (oldBc:BoundedContext)-[oldRel:HAS_EVENT]->(evt)
            DELETE oldRel
            WITH evt
            MATCH (newBc:BoundedContext {id: $targetBcId})
            MERGE (newBc)-[:HAS_EVENT]->(evt)
            """,
            eventId=event_id, targetBcId=target_bc_id,
        )

    SmartLogger.log(
        "INFO",
        f"Event moved to BC: {event_id} → {target_bc_id}",
        category="api.graph.event_modeling.move_event",
        params={**http_context(request), "eventId": event_id, "targetBcId": target_bc_id},
    )

    return {"moved": True, "eventId": event_id, "targetBcId": target_bc_id}


# ── 노드 간 관계(Relation) CRUD ─────────────────────────────────

# 허용되는 관계 매핑: (sourceLabel, targetLabel) → relationshipType
_VALID_RELATIONS: dict[tuple[str, str], str] = {
    ("Command", "Event"): "EMITS",
    ("UI", "Command"): "ATTACHED_TO",
    ("UI", "ReadModel"): "ATTACHED_TO",
    ("Event", "Policy"): "TRIGGERS",
    ("Policy", "Command"): "INVOKES",
    ("Event", "ReadModel"): "EVENT_TO_READMODEL",  # CQRS 연결 (간접)
}


@router.post("/event-modeling/relations")
async def create_relation(request: Request) -> dict[str, Any]:
    """
    POST /api/graph/event-modeling/relations

    두 노드 간 관계 생성.
    Body: {
      "sourceId": "...",
      "targetId": "...",
      "sourceType": "command" | "event" | "readmodel" | "ui" | "policy",
      "targetType": "command" | "event" | "readmodel" | "ui" | "policy"
    }

    sourceType/targetType 조합에 따라 적절한 관계를 자동 생성:
      Command → Event : EMITS
      UI → Command : ATTACHED_TO
      UI → ReadModel : ATTACHED_TO
      Event → Policy : TRIGGERS
      Policy → Command : INVOKES
      Event → ReadModel : CQRSConfig + CQRSOperation(TRIGGERED_BY) 자동 생성
    """
    body = await request.json()
    source_id = body.get("sourceId")
    target_id = body.get("targetId")
    source_type = (body.get("sourceType") or "").capitalize()
    target_type = (body.get("targetType") or "").capitalize()

    # Readmodel → ReadModel 정규화
    if source_type == "Readmodel":
        source_type = "ReadModel"
    if target_type == "Readmodel":
        target_type = "ReadModel"

    if not source_id or not target_id:
        return {"error": "sourceId and targetId are required"}

    rel_type = _VALID_RELATIONS.get((source_type, target_type))
    if not rel_type:
        return {
            "error": f"Invalid relation: {source_type} → {target_type}",
            "validRelations": [
                {"from": k[0], "to": k[1], "type": v} for k, v in _VALID_RELATIONS.items()
            ],
        }

    result_data: dict[str, Any] = {"sourceId": source_id, "targetId": target_id, "relationType": rel_type}

    with get_session() as session:
        if rel_type == "EVENT_TO_READMODEL":
            # Event → ReadModel: CQRSConfig + CQRSOperation + TRIGGERED_BY 자동 생성
            # 1. CQRSConfig 확인/생성
            cqrs_id = f"CQRS-{target_id}"
            session.run(
                """
                MATCH (rm:ReadModel {id: $rmId})
                MERGE (cqrs:CQRSConfig {id: $cqrsId})
                  ON CREATE SET cqrs.readmodelId = $rmId
                MERGE (rm)-[:HAS_CQRS]->(cqrs)
                """,
                rmId=target_id, cqrsId=cqrs_id,
            )
            # 2. CQRSOperation + TRIGGERED_BY 생성
            op_id = f"CQRS-OP-{target_id}-INSERT-{source_id}"
            session.run(
                """
                MATCH (cqrs:CQRSConfig {id: $cqrsId}), (evt:Event {id: $evtId})
                MERGE (op:CQRSOperation {id: $opId})
                  ON CREATE SET op.operationType = 'INSERT',
                               op.cqrsConfigId = $cqrsId,
                               op.triggerEventId = $evtId
                MERGE (cqrs)-[:HAS_OPERATION]->(op)
                MERGE (op)-[:TRIGGERED_BY]->(evt)
                """,
                cqrsId=cqrs_id, evtId=source_id, opId=op_id,
            )
            result_data["relationType"] = "TRIGGERED_BY (via CQRSOperation)"
        else:
            # 일반 관계 MERGE
            session.run(
                f"""
                MATCH (src:{source_type} {{id: $srcId}}), (tgt:{target_type} {{id: $tgtId}})
                MERGE (src)-[:{rel_type}]->(tgt)
                """,
                srcId=source_id, tgtId=target_id,
            )

    SmartLogger.log(
        "INFO",
        f"Relation created: {source_type}-[{rel_type}]->{target_type}",
        category="api.graph.event_modeling.create_relation",
        params={**http_context(request), **result_data},
    )

    return {"created": True, **result_data}


@router.delete("/event-modeling/relations")
async def delete_relation(request: Request) -> dict[str, Any]:
    """
    DELETE /api/graph/event-modeling/relations

    두 노드 간 관계 삭제.
    Body: {
      "sourceId": "...",
      "targetId": "...",
      "sourceType": "command" | "event" | "readmodel" | "ui" | "policy",
      "targetType": "command" | "event" | "readmodel" | "ui" | "policy"
    }
    """
    body = await request.json()
    source_id = body.get("sourceId")
    target_id = body.get("targetId")
    source_type = (body.get("sourceType") or "").capitalize()
    target_type = (body.get("targetType") or "").capitalize()

    if source_type == "Readmodel":
        source_type = "ReadModel"
    if target_type == "Readmodel":
        target_type = "ReadModel"

    if not source_id or not target_id:
        return {"error": "sourceId and targetId are required"}

    rel_type = _VALID_RELATIONS.get((source_type, target_type))
    if not rel_type:
        return {"error": f"Invalid relation: {source_type} → {target_type}"}

    with get_session() as session:
        if rel_type == "EVENT_TO_READMODEL":
            # CQRSOperation + TRIGGERED_BY 관계 삭제
            session.run(
                """
                MATCH (op:CQRSOperation)-[:TRIGGERED_BY]->(evt:Event {id: $evtId})
                WHERE op.cqrsConfigId = $cqrsId
                DETACH DELETE op
                """,
                evtId=source_id, cqrsId=f"CQRS-{target_id}",
            )
        else:
            session.run(
                f"""
                MATCH (src:{source_type} {{id: $srcId}})-[r:{rel_type}]->(tgt:{target_type} {{id: $tgtId}})
                DELETE r
                """,
                srcId=source_id, tgtId=target_id,
            )

    SmartLogger.log(
        "INFO",
        f"Relation deleted: {source_type}-[{rel_type}]->{target_type}",
        category="api.graph.event_modeling.delete_relation",
        params={**http_context(request), "sourceId": source_id, "targetId": target_id, "relationType": rel_type},
    )

    return {"deleted": True, "sourceId": source_id, "targetId": target_id, "relationType": rel_type}


@router.get("/event-modeling/connectable/{node_type}/{node_id}")
async def get_connectable_targets(request: Request, node_type: str, node_id: str) -> dict[str, Any]:
    """
    GET /api/graph/event-modeling/connectable/{node_type}/{node_id}

    해당 노드에서 연결 가능한 타겟 노드 목록 + 관계 유형.
    현재 이미 연결된 노드는 제외.
    """
    source_label = node_type.capitalize()
    if source_label == "Readmodel":
        source_label = "ReadModel"

    # 이 소스 타입에서 가능한 관계들
    possible = [(tgt, rel) for (src, tgt), rel in _VALID_RELATIONS.items() if src == source_label]
    if not possible:
        return {"targets": [], "nodeType": node_type}

    results = []

    with get_session() as session:
        for target_label, rel_type in possible:
            actual_rel = rel_type if rel_type != "EVENT_TO_READMODEL" else "TRIGGERED_BY"

            if rel_type == "EVENT_TO_READMODEL":
                # 이미 CQRS 연결된 ReadModel 제외
                records = session.run(
                    """
                    MATCH (tgt:ReadModel)
                    WHERE NOT EXISTS {
                        MATCH (tgt)-[:HAS_CQRS]->(:CQRSConfig)-[:HAS_OPERATION]->(:CQRSOperation)-[:TRIGGERED_BY]->(:Event {id: $srcId})
                    }
                    RETURN tgt.id AS id, tgt.name AS name, tgt.displayName AS displayName
                    """,
                    srcId=node_id,
                ).data()
            else:
                records = session.run(
                    f"""
                    MATCH (tgt:{target_label})
                    WHERE NOT EXISTS {{
                        MATCH (:{source_label} {{id: $srcId}})-[:{actual_rel}]->(tgt)
                    }}
                    RETURN tgt.id AS id, tgt.name AS name, tgt.displayName AS displayName
                    """,
                    srcId=node_id,
                ).data()

            for rec in records:
                results.append({
                    "id": rec["id"],
                    "name": rec["name"],
                    "displayName": rec["displayName"] or rec["name"],
                    "targetType": target_label.lower(),
                    "relationType": rel_type,
                })

    return {"targets": results, "nodeType": node_type, "nodeId": node_id}
