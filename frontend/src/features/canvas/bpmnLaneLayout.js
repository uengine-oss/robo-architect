/**
 * BPMN 을 **시퀀스 순서 + 레인**으로 다시 배치한다 — 레인 수와 상관없이 한 가지 길.
 *
 * 2026-11-16 · test 1112 에서 본 것
 *   - 레인 하나: ELK 가 되돌림 간선을 잘못 골라 시작이 가운데 → 63bae17 로 고쳤다
 *   - 레인 여럿: 서버 DI 를 그대로 썼는데, 서버가 **들어오는 선이 없는 작업**(생성이 화살표를 빠뜨린
 *     "마감 해제" 같은 것)을 맨 앞 열에 두고, 같은 칸의 게이트웨이를 그 아래에 쌓았다. 선만 다시
 *     그어서는(66c8779) 자리가 틀린 것을 못 고친다.
 *
 * 그래서
 *   1) 가로(열)는 ELK layered 로 — 되돌림 간선은 들어온 DI 의 x 로 고르고(INTERACTIVE),
 *      시작·끝은 첫·마지막 층에 묶는다. **들어오는 선이 없는 작업**은 문서 순서(=시퀀스 순서)에서
 *      바로 앞 작업 뒤에 오도록 배치 전용 간선을 하나 넣는다(그리지는 않는다).
 *   2) 세로(행)는 레인으로 — 노드는 자기 레인 띠 안에 놓고, 같은 열·같은 레인이 여럿이면 ELK 의 위아래
 *      순서대로 쌓는다. 레인이 없거나 하나면 띠도 하나다.
 *   3) 선은 bpmnEdgeRouting 으로 — 노드를 피해 직교로.
 *
 * 순수 계산(`computeLaneLayout`)과 XML 읽고 쓰기(`layoutBpmnWithLanes`)를 나눈다 — 계산은 노드로 잰다.
 */
import { routeEdges } from './bpmnEdgeRouting.js'

const COL_GAP = 175        // 열 간격(작업 폭 100 + 통로)
const ROW_H = 110          // 레인 안 한 줄 높이
const LANE_PAD = 40       // 레인 위아래 여백 — 위/아래로 도는 선이 레인 안에 들어오게
const HEAD_W = 30          // 풀·레인 머리 폭
const TASK_H = 80

export const NODE_SIZE = (tag) =>
  tag.endsWith('Event') ? { w: 36, h: 36 }
    : tag.endsWith('Gateway') ? { w: 50, h: 50 }
      : { w: 100, h: 80 }

const isTaskLike = (tag) => !tag.endsWith('Gateway') && !tag.endsWith('Event')

/**
 * @param {{
 *   nodes: {id:string, tag:string, w:number, h:number}[],   // 문서 순서(= 서버가 시퀀스 순으로 쓴 순서)
 *   flows: {id:string, s:string, t:string}[],
 *   lanes: {id:string, nodeIds:string[]}[],
 *   hintX?: Record<string, number>,                          // 들어온 DI 의 x(있으면)
 * }} model
 * @param {{ layout: Function }} elk
 */
export async function computeLaneLayout(model, elk) {
  const { nodes, flows } = model
  const byId = new Map(nodes.map(n => [n.id, n]))
  const hintX = { ...(model.hintX || {}) }

  // 1) 들어오는 선이 없는 작업 → 문서 순서상 바로 앞 작업 뒤에(배치 전용 간선)
  const incoming = new Map(nodes.map(n => [n.id, 0]))
  for (const f of flows) if (incoming.has(f.t)) incoming.set(f.t, incoming.get(f.t) + 1)
  const hidden = []
  let prevTask = null
  for (const n of nodes) {
    if (n.tag !== 'startEvent' && incoming.get(n.id) === 0 && prevTask) {
      hidden.push({ id: `__layout_${n.id}`, s: prevTask.id, t: n.id })
      if (hintX[prevTask.id] !== undefined) hintX[n.id] = hintX[prevTask.id] + 150   // ELK 는 중심으로 견준다 — 폭보다 크게 띄운다
    }
    if (isTaskLike(n.tag)) prevTask = n
  }
  // 들어오는 선이 **모두 오른쪽에서** 오는 노드는 자리가 틀린 것이다(서버가 맨 앞 열에 둔 것 —
  // "마감 해제" 를 옮기자 그 게이트웨이가 홀로 앞에 남았다). 진짜 되돌림 대상은 왼쪽에서 오는
  // 선도 함께 있으므로 건드리지 않는다. 그 출발점 바로 뒤로 옮기고, 옮긴 것이 다른 것을 끌 수 있게 몇 번 돈다.
  const allIn = [...flows, ...hidden]
  for (let pass = 0; pass < nodes.length; pass++) {
    let moved = false
    for (const n of nodes) {
      if (n.tag === 'startEvent' || hintX[n.id] === undefined) continue
      const srcs = allIn.filter(f => f.t === n.id).map(f => hintX[f.s]).filter(x => x !== undefined)
      if (srcs.length && srcs.every(x => x >= hintX[n.id])) {
        hintX[n.id] = Math.max(...srcs) + 150
        moved = true
      }
    }
    if (!moved) break
  }
  const hasHints = nodes.every(n => hintX[n.id] !== undefined)

  const children = nodes.map(n => {
    const c = { id: n.id, width: n.w, height: n.h }
    if (hasHints) { c.x = hintX[n.id]; c.y = 0 }
    if (n.tag === 'startEvent') c.layoutOptions = { 'elk.layered.layering.layerConstraint': 'FIRST' }
    else if (n.tag === 'endEvent') c.layoutOptions = { 'elk.layered.layering.layerConstraint': 'LAST' }
    return c
  })
  if (hasHints) children.sort((a, b) => a.x - b.x)

  const res = await elk.layout({
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'RIGHT',
      'elk.layered.cycleBreaking.strategy': hasHints ? 'INTERACTIVE' : 'MODEL_ORDER',
      'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
      'elk.layered.spacing.nodeNodeBetweenLayers': '60',
      'elk.spacing.nodeNode': '40',
    },
    children,
    edges: [...flows, ...hidden]
      .filter(f => byId.has(f.s) && byId.has(f.t))
      .map(f => ({ id: f.id, sources: [f.s], targets: [f.t] })),
  })
  const elkPos = new Map((res.children || []).map(c => [c.id, { x: c.x, y: c.y, w: c.width }]))
  if (elkPos.size !== nodes.length) throw new Error('ELK 가 노드를 다 놓지 못했다')

  // 2) ELK 의 x(중심) → 열 번호
  const centers = [...new Set(nodes.map(n => Math.round(elkPos.get(n.id).x + elkPos.get(n.id).w / 2)))].sort((a, b) => a - b)
  const colOfCenter = new Map()
  let col = -1, last = -Infinity
  for (const c of centers) { if (c - last > 20) col += 1; colOfCenter.set(c, col); last = c }
  const colOf = (id) => colOfCenter.get(Math.round(elkPos.get(id).x + elkPos.get(id).w / 2))

  // 3) 레인 — 시작은 첫 대상의 레인, 끝은 첫 출발의 레인, 나머지 빠진 것은 첫 레인
  const lanes = model.lanes.length ? model.lanes : [{ id: null, nodeIds: nodes.map(n => n.id) }]
  const laneOf = new Map()
  lanes.forEach((l, i) => l.nodeIds.forEach(id => { if (byId.has(id)) laneOf.set(id, i) }))
  for (const n of nodes) {
    if (laneOf.has(n.id)) continue
    const f = n.tag === 'endEvent' ? flows.find(x => x.t === n.id) : flows.find(x => x.s === n.id)
    const other = f && (n.tag === 'endEvent' ? f.s : f.t)
    laneOf.set(n.id, other !== undefined && laneOf.has(other) ? laneOf.get(other) : 0)
  }

  // 레인 안의 줄 — ELK 가 정한 **위아래 자리(y)** 를 레인마다 줄 번호로 접는다.
  // ELK 는 게이트웨이에서 갈라지는 가지를 서로 다른 높이에 둔다. 그 순서를 지켜야 같은 레인 안에서도
  // 가지가 위아래로 벌어진다(전에는 같은 칸에 겹칠 때만 줄을 나눠, 가지가 한 줄에 늘어서 읽기 어려웠다).
  const centerY = (id) => elkPos.get(id).y + (byId.get(id).h / 2)
  const rowOf = new Map()
  const laneRows = lanes.map(() => 1)
  lanes.forEach((_, li) => {
    const ids = nodes.map(n => n.id).filter(id => laneOf.get(id) === li)
    const levels = [...new Set(ids.map(id => Math.round(centerY(id))))].sort((a, b) => a - b)
    const rowOfLevel = new Map()
    let r = -1, prev = -Infinity
    for (const y of levels) { if (y - prev > 25) r += 1; rowOfLevel.set(y, r); prev = y }
    for (const id of ids) rowOf.set(id, rowOfLevel.get(Math.round(centerY(id))))
    // 같은 줄·같은 열에 둘이 걸리면(ELK 가 아주 가깝게 둔 것) 아래로 밀어 낸다
    const taken = new Map()
    for (const id of [...ids].sort((a, b) => centerY(a) - centerY(b))) {
      let row = rowOf.get(id)
      while (taken.get(`${row}:${colOf(id)}`)) row += 1
      taken.set(`${row}:${colOf(id)}`, true)
      rowOf.set(id, row)
    }
    laneRows[li] = Math.max(1, ...ids.map(id => rowOf.get(id) + 1))
  })

  const left = 0, top = 0
  const laneTop = []
  let acc = top
  for (let i = 0; i < lanes.length; i++) { laneTop.push(acc); acc += laneRows[i] * ROW_H + LANE_PAD * 2 }
  const maxCol = Math.max(...nodes.map(n => colOf(n.id)))
  const poolW = HEAD_W * (model.lanes.length ? 2 : 1) + 40 + (maxCol + 1) * COL_GAP
  const firstColX = left + HEAD_W * (model.lanes.length ? 2 : 1) + 40

  const boxes = {}
  for (const n of nodes) {
    const cx = firstColX + colOf(n.id) * COL_GAP + 50
    const cy = laneTop[laneOf.get(n.id)] + LANE_PAD + rowOf.get(n.id) * ROW_H + TASK_H / 2
    boxes[n.id] = { x: Math.round(cx - n.w / 2), y: Math.round(cy - n.h / 2), w: n.w, h: n.h }
  }

  const laneBoxes = {}
  lanes.forEach((l, i) => {
    if (l.id) laneBoxes[l.id] = { x: left + HEAD_W, y: laneTop[i], w: poolW - HEAD_W, h: laneRows[i] * ROW_H + LANE_PAD * 2 }
  })
  const pool = { x: left, y: top, w: poolW, h: acc - top }
  const tags = Object.fromEntries(nodes.map(n => [n.id, n.tag]))
  const edges = routeEdges(boxes, flows, {}, tags)
  return { boxes, laneBoxes, pool, edges }
}

/** BPMN XML 을 시퀀스 순서 + 레인으로 다시 배치한다. 실패하면 받은 XML 을 그대로. */
export async function layoutBpmnWithLanes(xml, elk) {
  try {
    const doc = new DOMParser().parseFromString(xml, 'application/xml')
    if (doc.querySelector('parsererror')) return xml
    const all = [...doc.getElementsByTagName('*')]
    const byLocal = (root, name) => [...root.getElementsByTagName('*')].filter(n => n.localName === name)
    const FLOW = /^(task|\w+Task|callActivity|subProcess|\w+Gateway|startEvent|endEvent|intermediate\w+Event)$/
    const procs = byLocal(doc, 'process')
    if (procs.length !== 1) return xml   // 여러 프로세스를 한 문서에 담은 것은 건드리지 않는다
    const proc = procs[0]
    const nodes = [...proc.children].filter(n => FLOW.test(n.localName))
      .map(n => ({ id: n.getAttribute('id'), tag: n.localName, ...NODE_SIZE(n.localName) }))
    if (!nodes.length) return xml
    const ids = new Set(nodes.map(n => n.id))
    const flows = byLocal(proc, 'sequenceFlow')
      .map(f => ({ id: f.getAttribute('id'), s: f.getAttribute('sourceRef'), t: f.getAttribute('targetRef') }))
      .filter(f => ids.has(f.s) && ids.has(f.t))
    const lanes = byLocal(proc, 'lane').map(l => ({
      id: l.getAttribute('id'),
      nodeIds: byLocal(l, 'flowNodeRef').map(r => (r.textContent || '').trim()),
    }))
    const hintX = {}
    for (const sh of all.filter(n => n.localName === 'BPMNShape')) {
      const id = sh.getAttribute('bpmnElement')
      const b = [...sh.getElementsByTagName('*')].find(n => n.localName === 'Bounds')
      if (b && ids.has(id)) hintX[id] = +b.getAttribute('x')
    }

    const { boxes, laneBoxes, pool, edges } = await computeLaneLayout({ nodes, flows, lanes, hintX }, elk)

    const plane = byLocal(doc, 'BPMNPlane')[0]
    if (!plane) return xml
    const exShape = byLocal(plane, 'BPMNShape')[0]
    const DI_NS = exShape ? exShape.namespaceURI : 'http://www.omg.org/spec/BPMN/20100524/DI'
    const DC_NS = 'http://www.omg.org/spec/DD/20100524/DC'
    const DI2_NS = 'http://www.omg.org/spec/DD/20100524/DI'
    while (plane.firstChild) plane.removeChild(plane.firstChild)
    const shape = (el, b, horizontal) => {
      const s = doc.createElementNS(DI_NS, 'bpmndi:BPMNShape')
      s.setAttribute('id', `${el}_di`)
      s.setAttribute('bpmnElement', el)
      if (horizontal) s.setAttribute('isHorizontal', 'true')
      const d = doc.createElementNS(DC_NS, 'dc:Bounds')
      d.setAttribute('x', b.x); d.setAttribute('y', b.y); d.setAttribute('width', b.w); d.setAttribute('height', b.h)
      s.appendChild(d)
      plane.appendChild(s)
    }
    const participant = byLocal(doc, 'participant')[0]
    if (participant) shape(participant.getAttribute('id'), pool, true)
    for (const [id, b] of Object.entries(laneBoxes)) shape(id, b, true)
    for (const [id, b] of Object.entries(boxes)) shape(id, b, false)
    for (const f of flows) {
      const pts = edges[f.id]
      if (!pts || pts.length < 2) continue
      const e = doc.createElementNS(DI_NS, 'bpmndi:BPMNEdge')
      e.setAttribute('id', `${f.id}_di`)
      e.setAttribute('bpmnElement', f.id)
      for (const p of pts) {
        const w = doc.createElementNS(DI2_NS, 'di:waypoint')
        w.setAttribute('x', Math.round(p.x)); w.setAttribute('y', Math.round(p.y))
        e.appendChild(w)
      }
      plane.appendChild(e)
    }
    return new XMLSerializer().serializeToString(doc)
  } catch (err) {
    console.warn('[bpmnLaneLayout] layout failed', err)
    return xml
  }
}
