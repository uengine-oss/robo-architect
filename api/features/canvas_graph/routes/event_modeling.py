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
