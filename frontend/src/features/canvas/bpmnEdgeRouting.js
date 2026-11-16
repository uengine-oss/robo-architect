/**
 * BPMN 선을 노드를 피해 다시 긋는다 — 노드 자리는 그대로 두고 **선만**.
 *
 * 레인이 둘 이상인 프로세스는 서버(bpmn_builder)의 DI 를 그대로 그린다(레인을 지키려고). 그 DI 는
 * 노드 자리가 시퀀스 순서로 맞지만 선은 "오른쪽으로 나가 → 가운데서 꺾어 → 왼쪽으로 들어간다" 하나라,
 * 열을 건너뛰거나 되돌아가는 선이 **사이의 노드를 가로질렀다**(2026-11-16 · test 1112 —
 * 월 근태 마감 4 · 휴가 신청 결재 6). 이미 저장된 프로세스도 고쳐 보이도록 화면에서 다시 긋는다.
 *
 * 규칙(직교선만):
 *   ① 지금 선이 아무 노드도 안 가로지르면 그대로 둔다
 *   ② 아니면 후보를 차례로 대 보고 처음으로 안 부딪히는 것을 쓴다
 *        곧은 선 → 열 사이 통로에서 한 번 꺾기 → 통로·가로 복도·통로(위아래로 돌아간다)
 *   ③ 다 부딪히면 원래 선을 둔다(나빠지지는 않는다)
 */

const PAD = 4

/** @typedef {{x:number,y:number,w:number,h:number}} Box */

function hits(a, b, r) {
  const x1 = Math.min(a.x, b.x), x2 = Math.max(a.x, b.x)
  const y1 = Math.min(a.y, b.y), y2 = Math.max(a.y, b.y)
  return x2 > r.x - PAD && x1 < r.x + r.w + PAD && y2 > r.y - PAD && y1 < r.y + r.h + PAD
}

function pathHits(pts, obstacles) {
  for (let i = 1; i < pts.length; i++) {
    for (const r of obstacles) if (hits(pts[i - 1], pts[i], r)) return true
  }
  return false
}

/** 지금 선(waypoints)이 시작·끝 말고 다른 노드를 가로지르나. */
export function crossesNodes(points, boxes, sourceId, targetId) {
  if (!points || points.length < 2) return false
  const obstacles = Object.entries(boxes).filter(([id]) => id !== sourceId && id !== targetId).map(([, b]) => b)
  return pathHits(points, obstacles)
}

function channelAfter(S, all) {
  const right = S.x + S.w
  const lefts = all.map(b => b.x).filter(x => x > right + 1)
  const next = lefts.length ? Math.min(...lefts) : right + 60
  return [right + (next - right) / 2, right + 12]
}

function channelBefore(T, all) {
  const left = T.x
  const rights = all.map(b => b.x + b.w).filter(x => x < left - 1)
  const prev = rights.length ? Math.max(...rights) : left - 60
  return [left - (left - prev) / 2, left - 12]
}

function corridorYs(all, sy, ty) {
  const ys = new Set()
  for (const b of all) { ys.add(b.y - 10); ys.add(b.y + b.h + 10) }
  const top = Math.min(...all.map(b => b.y)), bottom = Math.max(...all.map(b => b.y + b.h))
  ys.add(top - 24); ys.add(bottom + 24)
  const mid = (sy + ty) / 2
  return [...ys].sort((a, b) => Math.abs(a - mid) - Math.abs(b - mid))
}

/**
 * @param {Record<string, Box>} boxes  흐름 노드의 상자(시작·끝 이벤트 포함)
 * @param {{id:string,s:string,t:string}[]} flows
 * @param {Record<string, {x:number,y:number}[]>} [current]  지금 선 — 안 가로지르면 그대로 둔다
 * @returns {Record<string, {x:number,y:number}[]>}
 */
export function routeEdges(boxes, flows, current = {}) {
  const all = Object.values(boxes)
  const out = {}
  for (const f of flows) {
    const S = boxes[f.s], T = boxes[f.t]
    if (!S || !T) continue
    const now = current[f.id]
    if (now && !crossesNodes(now, boxes, f.s, f.t)) { out[f.id] = now; continue }

    const obstacles = Object.entries(boxes).filter(([id]) => id !== f.s && id !== f.t).map(([, b]) => b)
    const sx = S.x + S.w, sy = S.y + S.h / 2
    const tx = T.x, ty = T.y + T.h / 2
    const cand = []
    if (tx > sx) {
      if (Math.abs(sy - ty) < 1) cand.push([{ x: sx, y: sy }, { x: tx, y: ty }])
      for (const mx of [...channelAfter(S, all), ...channelBefore(T, all)]) {
        if (mx > sx && mx < tx) cand.push([{ x: sx, y: sy }, { x: mx, y: sy }, { x: mx, y: ty }, { x: tx, y: ty }])
      }
    }
    const m1s = channelAfter(S, all), m2s = channelBefore(T, all)
    for (const cy of corridorYs(all, sy, ty)) {
      for (const m1 of m1s) for (const m2 of m2s) {
        cand.push([{ x: sx, y: sy }, { x: m1, y: sy }, { x: m1, y: cy }, { x: m2, y: cy }, { x: m2, y: ty }, { x: tx, y: ty }])
      }
    }
    const chosen = cand.find(pts => !pathHits(pts, obstacles))
    out[f.id] = chosen || now || [{ x: sx, y: sy }, { x: tx, y: ty }]
  }
  return out
}

/**
 * BPMN XML 의 DI 에서 **노드를 가로지르는 선만** 다시 긋는다. 노드·레인 DI 는 손대지 않는다.
 * 실패하면 받은 XML 을 그대로 돌려준다.
 */
export function rerouteCrossingEdges(xml) {
  try {
    const doc = new DOMParser().parseFromString(xml, 'application/xml')
    if (doc.querySelector('parsererror')) return xml
    const all = [...doc.getElementsByTagName('*')]
    const flowNodeIds = new Set(all
      .filter(n => /^(task|\w+Task|callActivity|subProcess|\w+Gateway|startEvent|endEvent|intermediate\w+Event|boundaryEvent)$/.test(n.localName))
      .map(n => n.getAttribute('id')))
    const boxes = {}
    for (const sh of all.filter(n => n.localName === 'BPMNShape')) {
      const id = sh.getAttribute('bpmnElement')
      if (!flowNodeIds.has(id)) continue
      const b = [...sh.getElementsByTagName('*')].find(n => n.localName === 'Bounds')
      if (b) boxes[id] = { x: +b.getAttribute('x'), y: +b.getAttribute('y'), w: +b.getAttribute('width'), h: +b.getAttribute('height') }
    }
    const flows = all.filter(n => n.localName === 'sequenceFlow')
      .map(f => ({ id: f.getAttribute('id'), s: f.getAttribute('sourceRef'), t: f.getAttribute('targetRef') }))
    const edgeEls = new Map(all.filter(n => n.localName === 'BPMNEdge').map(e => [e.getAttribute('bpmnElement'), e]))
    const current = {}
    for (const [id, e] of edgeEls) {
      current[id] = [...e.getElementsByTagName('*')].filter(n => n.localName === 'waypoint')
        .map(w => ({ x: +w.getAttribute('x'), y: +w.getAttribute('y') }))
    }
    const routed = routeEdges(boxes, flows, current)
    let changed = false
    for (const [id, pts] of Object.entries(routed)) {
      const e = edgeEls.get(id)
      if (!e || pts === current[id]) continue
      const ns = ([...e.getElementsByTagName('*')].find(n => n.localName === 'waypoint') || {}).namespaceURI
        || 'http://www.omg.org/spec/DD/20100524/DI'
      for (const w of [...e.getElementsByTagName('*')].filter(n => n.localName === 'waypoint')) e.removeChild(w)
      for (const p of pts) {
        const w = doc.createElementNS(ns, 'di:waypoint')
        w.setAttribute('x', Math.round(p.x)); w.setAttribute('y', Math.round(p.y))
        e.appendChild(w)
      }
      changed = true
    }
    return changed ? new XMLSerializer().serializeToString(doc) : xml
  } catch (err) {
    console.warn('[bpmnEdgeRouting] reroute failed', err)
    return xml
  }
}
