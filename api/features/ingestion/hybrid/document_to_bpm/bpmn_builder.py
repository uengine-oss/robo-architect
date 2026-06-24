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
    """Generate a minimal, valid BPMN 2.0 XML from a BpmSkeleton.

    When the skeleton carries gateways (native fallback detected branches), the
    branch-aware builder renders the diamonds + labeled branch edges; otherwise
    the original linear builder runs unchanged.
    """
    if not skeleton.tasks:
        return _empty_bpmn()
    if skeleton.gateways:
        try:
            return _build_bpmn_xml_with_gateways(skeleton)
        except Exception:
            # Layout is best-effort; never fail ingestion over a diagram. Fall
            # back to the linear render (gateways still persist as graph nodes).
            pass

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


def _build_bpmn_xml_with_gateways(skeleton: BpmSkeleton) -> str:
    """Branch-aware BPMN builder: lays out tasks + gateways over the flow graph.

    Layout is intentionally simple (longest-path columns, lane rows). bpmn-js
    renders it faithfully even if some branch edges overlap.
    """
    tasks = sorted(skeleton.tasks, key=lambda t: t.sequence_index)
    actors = skeleton.actors or []
    actor_by_id = {a.id: a for a in actors}
    task_ids = {t.id for t in tasks}

    start_id, end_id = "StartEvent_1", "EndEvent_1"

    def node_xml_id(nid: str) -> str:
        return f"Task_{_safe(nid)}" if nid in task_ids else f"Gateway_{_safe(nid)}"

    lane_of: dict[str, str] = {}
    for t in tasks:
        lane_of[t.id] = t.actor_ids[0] if t.actor_ids else "system"
    for g in skeleton.gateways:
        lane_of[g.id] = g.actor_ids[0] if g.actor_ids else "system"

    # Edge set: explicit gateway flows + linear backbone spliced around them.
    edges: list[tuple[str, str, str]] = []  # (src_node, tgt_node, label)
    explicit_out: set[str] = set()
    explicit_in: set[str] = set()
    for fl in skeleton.flows:
        s, t = fl.source_id, fl.target_id
        if s in lane_of and t in lane_of:
            edges.append((s, t, fl.name or ""))
            explicit_out.add(s)
            explicit_in.add(t)

    if tasks:
        edges.append((start_id, tasks[0].id, ""))
    for i in range(len(tasks) - 1):
        a, b = tasks[i].id, tasks[i + 1].id
        if a in explicit_out or b in explicit_in:
            continue  # routed through a gateway instead of linearly
        edges.append((a, b, ""))

    # Every node with no outgoing edge flows to end.
    has_out = {s for s, _, _ in edges}
    for nid in [t.id for t in tasks] + [g.id for g in skeleton.gateways]:
        if nid not in has_out:
            edges.append((nid, end_id, ""))

    # Columns via longest path from start over the edge graph.
    adj: dict[str, list[str]] = {}
    for s, t, _ in edges:
        adj.setdefault(s, []).append(t)
    col: dict[str, int] = {start_id: 0}
    # Relax in a few passes (DAG-ish; cycles tolerated, just capped).
    for _ in range(len(edges) + 2):
        changed = False
        for s, t, _ in edges:
            if s in col and col.get(t, -1) < col[s] + 1:
                col[t] = col[s] + 1
                changed = True
        if not changed:
            break
    max_col = max(col.values()) if col else 1
    col.setdefault(end_id, max_col + 1)
    for nid in [t.id for t in tasks] + [g.id for g in skeleton.gateways]:
        col.setdefault(nid, 1)

    lane_keys = list(dict.fromkeys(lane_of.values())) or ["system"]
    lane_y0, x0, gap_x = 80, 180, 200
    task_w, task_h, gw_s = 120, 80, 50
    row_h = 120  # vertical slot per stacked sibling within a lane
    node_list = [t.id for t in tasks] + [g.id for g in skeleton.gateways]

    # Stack nodes that share (lane, column) into vertical sub-rows so sibling
    # branches out of a gateway never sit on top of each other.
    from collections import defaultdict as _dd
    by_cell: dict[tuple[str, int], list[str]] = _dd(list)
    for nid in node_list:
        by_cell[(lane_of[nid], col.get(nid, 1))].append(nid)
    row_of: dict[str, int] = {}
    lane_rows: dict[str, int] = {lk: 1 for lk in lane_keys}
    for (lk, c), members in by_cell.items():
        for r, nid in enumerate(members):
            row_of[nid] = r
        lane_rows[lk] = max(lane_rows[lk], len(members))

    lane_height = {lk: max(lane_rows[lk] * row_h + 40, 140) for lk in lane_keys}
    lane_top: dict[str, int] = {}
    _acc = lane_y0
    for lk in lane_keys:
        lane_top[lk] = _acc
        _acc += lane_height[lk]
    pool_h = _acc - lane_y0
    last_col = max(col.values()) if col else 1

    def _cell_top(nid: str) -> int:
        lk = lane_of.get(nid, lane_keys[0])
        return lane_top[lk] + row_of.get(nid, 0) * row_h

    # Absolute boxes (x, y, w, h) for every flow node.
    box: dict[str, tuple[int, int, int, int]] = {}
    for t in tasks:
        x = x0 + col.get(t.id, 1) * gap_x
        box[t.id] = (x, _cell_top(t.id) + (row_h - task_h) // 2, task_w, task_h)
    for g in skeleton.gateways:
        x = x0 + col.get(g.id, 1) * gap_x
        box[g.id] = (x + (task_w - gw_s) // 2, _cell_top(g.id) + (row_h - gw_s) // 2, gw_s, gw_s)
    _start_y = lane_top[lane_keys[0]] + (row_h - 36) // 2
    box[start_id] = (x0, _start_y, 36, 36)
    box[end_id] = (x0 + (last_col + 1) * gap_x, _start_y, 36, 36)

    def bounds(nid: str, xmlid: str = "") -> tuple[int, int, int, int]:
        return box.get(nid, (x0, lane_y0, task_w, task_h))

    # --- process elements ---
    lanes_xml = []
    for lk in lane_keys:
        actor = actor_by_id.get(lk)
        name = _esc(actor.name if actor else "System")
        members = [n for n, l in lane_of.items() if l == lk]
        refs = "\n        ".join(f"<flowNodeRef>{node_xml_id(n)}</flowNodeRef>" for n in members)
        lanes_xml.append(f'      <lane id="Lane_{_safe(lk)}" name="{name}">\n        {refs}\n      </lane>')

    # assign flow ids + incoming/outgoing per node
    flow_ids: list[tuple[str, str, str, str]] = []  # (fid, src_xmlid, tgt_xmlid, label)
    inc: dict[str, list[str]] = {}
    out: dict[str, list[str]] = {}
    for i, (s, t, label) in enumerate(edges):
        fid = f"Flow_{i}"
        sx, tx = (start_id if s == start_id else node_xml_id(s)), (end_id if t == end_id else node_xml_id(t))
        flow_ids.append((fid, sx, tx, label))
        out.setdefault(sx, []).append(fid)
        inc.setdefault(tx, []).append(fid)

    def io(xmlid: str) -> str:
        return ("".join(f"<incoming>{f}</incoming>" for f in inc.get(xmlid, []))
                + "".join(f"<outgoing>{f}</outgoing>" for f in out.get(xmlid, [])))

    nodes_xml = [f'    <startEvent id="{start_id}">{io(start_id)}</startEvent>']
    for t in tasks:
        xi = node_xml_id(t.id)
        nodes_xml.append(f'    <task id="{xi}" name="{_esc(t.name)}">{io(xi)}</task>')
    for g in skeleton.gateways:
        xi = node_xml_id(g.id)
        gt = (g.gateway_type or "exclusive").lower()
        tag = {"parallel": "parallelGateway", "inclusive": "inclusiveGateway",
               "complex": "complexGateway"}.get(gt, "exclusiveGateway")
        nodes_xml.append(f'    <{tag} id="{xi}" name="{_esc(g.name)}">{io(xi)}</{tag}>')
    nodes_xml.append(f'    <endEvent id="{end_id}">{io(end_id)}</endEvent>')

    flows_xml = "\n".join(
        f'    <sequenceFlow id="{fid}" sourceRef="{sx}" targetRef="{tx}"'
        + (f' name="{_esc(label)}"' if label else "") + " />"
        for fid, sx, tx, label in flow_ids
    )

    # --- DI ---
    shapes: list[str] = []
    pool_w = x0 + (last_col + 2) * gap_x
    shapes.append(
        f'<bpmndi:BPMNShape id="Pool_di" bpmnElement="Pool_1" isHorizontal="true">'
        f'<dc:Bounds x="100" y="{lane_y0}" width="{pool_w}" height="{pool_h}" /></bpmndi:BPMNShape>'
    )
    for lk in lane_keys:
        shapes.append(
            f'<bpmndi:BPMNShape id="Lane_{_safe(lk)}_di" bpmnElement="Lane_{_safe(lk)}" isHorizontal="true">'
            f'<dc:Bounds x="130" y="{lane_top[lk]}" width="{pool_w - 30}" height="{lane_height[lk]}" /></bpmndi:BPMNShape>'
        )

    for t in tasks:
        x, y, w, h = bounds(t.id, node_xml_id(t.id))
        shapes.append(f'<bpmndi:BPMNShape id="{node_xml_id(t.id)}_di" bpmnElement="{node_xml_id(t.id)}">'
                      f'<dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}" /></bpmndi:BPMNShape>')
    for g in skeleton.gateways:
        x, y, w, h = bounds(g.id, node_xml_id(g.id))
        shapes.append(f'<bpmndi:BPMNShape id="{node_xml_id(g.id)}_di" bpmnElement="{node_xml_id(g.id)}" isMarkerVisible="true">'
                      f'<dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}" /></bpmndi:BPMNShape>')
    for nid in (start_id, end_id):
        x, y, w, h = bounds(nid, nid)
        shapes.append(f'<bpmndi:BPMNShape id="{nid}_di" bpmnElement="{nid}">'
                      f'<dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}" /></bpmndi:BPMNShape>')

    xmlid_to_node = {node_xml_id(t.id): t.id for t in tasks}
    xmlid_to_node.update({node_xml_id(g.id): g.id for g in skeleton.gateways})
    xmlid_to_node[start_id] = start_id
    xmlid_to_node[end_id] = end_id
    edges_di: list[str] = []
    for fid, sx, tx, _ in flow_ids:
        sb = bounds(xmlid_to_node[sx], sx)
        tb = bounds(xmlid_to_node[tx], tx)
        sx_, sy_ = sb[0] + sb[2], sb[1] + sb[3] // 2
        tx_, ty_ = tb[0], tb[1] + tb[3] // 2
        if sy_ == ty_:
            pts = [(sx_, sy_), (tx_, ty_)]
        else:
            mx = (sx_ + tx_) // 2
            pts = [(sx_, sy_), (mx, sy_), (mx, ty_), (tx_, ty_)]
        wp = "".join(f'<di:waypoint x="{x}" y="{y}" />' for x, y in pts)
        edges_di.append(f'<bpmndi:BPMNEdge id="{fid}_di" bpmnElement="{fid}">{wp}</bpmndi:BPMNEdge>')

    di_xml = "\n      ".join(shapes + edges_di)
    proc_name = _esc(skeleton.process.name) if skeleton.process else "Hybrid BPM"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
             xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
             xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
             id="Definitions_hybrid"
             targetNamespace="http://hybrid.ingestion">
  <collaboration id="Collaboration_1">
    <participant id="Participant_1" name="{proc_name}" processRef="Process_1" />
  </collaboration>
  <process id="Process_1" isExecutable="false">
    <laneSet id="LaneSet_1">
{chr(10).join(lanes_xml)}
    </laneSet>
{chr(10).join(nodes_xml)}
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
