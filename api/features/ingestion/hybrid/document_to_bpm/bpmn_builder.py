"""Minimal BPMN 2.0 XML builder for hybrid Phase 1 skeleton.

Produces a valid BPMN XML with a single pool, lanes per actor, tasks in sequence
order, and a linear sequence flow. Intentionally simple — gateways/branches are
out of scope for v0.1.
"""

from __future__ import annotations

import re

from api.features.ingestion.hybrid.contracts import BpmSkeleton


def _safe(v: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]", "_", v or "")
    if not s or not s[0].isalpha():
        s = "n_" + s
    return s


def _esc(v: str) -> str:
    return (v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_bpmn_xml(skeleton: BpmSkeleton) -> str:
    """Generate a minimal, valid BPMN 2.0 XML from a BpmSkeleton."""
    if not skeleton.tasks:
        return _empty_bpmn()

    actors = skeleton.actors or []
    tasks = sorted(skeleton.tasks, key=lambda t: t.sequence_index)
    actor_by_id = {a.id: a for a in actors}

    # Group tasks into lanes (by first actor_id). Only actors that actually
    # have tasks become lanes — LLM frequently over-declares actors that end
    # up with no tasks, and empty lanes are just visual noise on the canvas.
    lane_tasks: dict[str, list] = {}
    for t in tasks:
        key = t.actor_ids[0] if t.actor_ids else "system"
        lane_tasks.setdefault(key, []).append(t)

    # IDs
    start_id = "StartEvent_1"
    end_id = "EndEvent_1"
    task_ids = [f"Task_{_safe(t.id)}" for t in tasks]

    # Sequence flow ids
    flows: list[tuple[str, str, str]] = []
    prev = start_id
    for i, tid in enumerate(task_ids):
        flows.append((f"Flow_{i}", prev, tid))
        prev = tid
    flows.append((f"Flow_{len(task_ids)}", prev, end_id))

    # Lane XML
    lanes_xml = []
    for lane_id, lane_list in lane_tasks.items():
        actor = actor_by_id.get(lane_id)
        name = _esc(actor.name if actor else "System")
        refs = "\n        ".join(
            f"<flowNodeRef>Task_{_safe(t.id)}</flowNodeRef>" for t in lane_list
        )
        lanes_xml.append(
            f'      <lane id="Lane_{_safe(lane_id)}" name="{name}">\n        {refs}\n      </lane>'
        )

    # Tasks XML (with incoming/outgoing for valid BPMN)
    tasks_xml = []
    for i, t in enumerate(tasks):
        tid = task_ids[i]
        incoming = f"Flow_{i}"
        outgoing = f"Flow_{i + 1}"
        tasks_xml.append(
            f'    <task id="{tid}" name="{_esc(t.name)}">\n'
            f"      <incoming>{incoming}</incoming>\n"
            f"      <outgoing>{outgoing}</outgoing>\n"
            f"    </task>"
        )

    flows_xml = "\n".join(
        f'    <sequenceFlow id="{fid}" sourceRef="{src}" targetRef="{dst}" />'
        for fid, src, dst in flows
    )

    start_xml = (
        f'    <startEvent id="{start_id}">\n'
        f"      <outgoing>Flow_0</outgoing>\n"
        f"    </startEvent>"
    )
    end_xml = (
        f'    <endEvent id="{end_id}">\n'
        f"      <incoming>Flow_{len(task_ids)}</incoming>\n"
        f"    </endEvent>"
    )

    # DI: lay tasks out left-to-right per lane row
    lane_keys = list(lane_tasks.keys())
    lane_h = 180
    lane_y0 = 80
    x0 = 180
    gap_x = 180
    task_w, task_h = 120, 80
    shapes: list[str] = []

    # Pool/lane shapes
    pool_w = x0 + (len(tasks) + 1) * gap_x + 100
    pool_h = len(lane_keys) * lane_h
    shapes.append(
        f'<bpmndi:BPMNShape id="Pool_di" bpmnElement="Pool_1" isHorizontal="true">'
        f'<dc:Bounds x="100" y="{lane_y0}" width="{pool_w}" height="{pool_h}" /></bpmndi:BPMNShape>'
    )
    for idx, lk in enumerate(lane_keys):
        y = lane_y0 + idx * lane_h
        shapes.append(
            f'<bpmndi:BPMNShape id="Lane_{_safe(lk)}_di" bpmnElement="Lane_{_safe(lk)}" isHorizontal="true">'
            f'<dc:Bounds x="130" y="{y}" width="{pool_w - 30}" height="{lane_h}" /></bpmndi:BPMNShape>'
        )

    # Start event
    start_y = lane_y0 + 60
    shapes.append(
        f'<bpmndi:BPMNShape id="{start_id}_di" bpmnElement="{start_id}">'
        f'<dc:Bounds x="{x0}" y="{start_y}" width="36" height="36" /></bpmndi:BPMNShape>'
    )

    # Task shapes
    task_positions: dict[str, tuple[int, int]] = {}
    for i, t in enumerate(tasks):
        lane_idx = lane_keys.index(t.actor_ids[0] if t.actor_ids else "system")
        x = x0 + (i + 1) * gap_x
        y = lane_y0 + lane_idx * lane_h + (lane_h - task_h) // 2
        task_positions[task_ids[i]] = (x, y)
        shapes.append(
            f'<bpmndi:BPMNShape id="{task_ids[i]}_di" bpmnElement="{task_ids[i]}">'
            f'<dc:Bounds x="{x}" y="{y}" width="{task_w}" height="{task_h}" /></bpmndi:BPMNShape>'
        )

    # End event
    end_x = x0 + (len(tasks) + 1) * gap_x
    shapes.append(
        f'<bpmndi:BPMNShape id="{end_id}_di" bpmnElement="{end_id}">'
        f'<dc:Bounds x="{end_x}" y="{start_y}" width="36" height="36" /></bpmndi:BPMNShape>'
    )

    # Edges — exit right border of source, enter left border of target.
    # For cross-lane jumps (different y), add an orthogonal elbow midway.
    def _bounds(shape_id: str) -> tuple[int, int, int, int]:
        if shape_id == start_id:
            return (x0, start_y, 36, 36)
        if shape_id == end_id:
            return (end_x, start_y, 36, 36)
        x, y = task_positions[shape_id]
        return (x, y, task_w, task_h)

    edges: list[str] = []
    for fid, src, dst in flows:
        sx0, sy0, sw, sh = _bounds(src)
        dx0, dy0, dw, dh = _bounds(dst)
        sx, sy = sx0 + sw, sy0 + sh // 2          # right-middle of source
        dx, dy = dx0, dy0 + dh // 2               # left-middle of target
        if sy == dy:
            points = [(sx, sy), (dx, dy)]
        else:
            mid_x = (sx + dx) // 2
            points = [(sx, sy), (mid_x, sy), (mid_x, dy), (dx, dy)]
        waypoints = "".join(f'<di:waypoint x="{x}" y="{y}" />' for x, y in points)
        edges.append(
            f'<bpmndi:BPMNEdge id="{fid}_di" bpmnElement="{fid}">{waypoints}</bpmndi:BPMNEdge>'
        )

    di_xml = "\n      ".join(shapes + edges)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
             xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
             xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
             id="Definitions_hybrid"
             targetNamespace="http://hybrid.ingestion">
  <collaboration id="Collaboration_1">
    <participant id="Participant_1" name="{_esc(skeleton.process.name) if skeleton.process else 'Hybrid BPM'}" processRef="Process_1" />
  </collaboration>
  <process id="Process_1" isExecutable="false">
    <laneSet id="LaneSet_1">
{chr(10).join(lanes_xml)}
    </laneSet>
{start_xml}
{chr(10).join(tasks_xml)}
{end_xml}
{flows_xml}
  </process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Collaboration_1">
      {di_xml}
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</definitions>
"""


def _empty_bpmn() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="Definitions_empty" targetNamespace="http://hybrid.ingestion">
  <process id="Process_1" isExecutable="false"/>
</definitions>
"""
