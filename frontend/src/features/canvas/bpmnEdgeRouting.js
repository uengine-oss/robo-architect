/**
 * BPMN 선을 노드를 피해, **서로 겹치지 않게** 다시 긋는다 — 노드 자리는 그대로 두고 선만.
 *
 * 2026-11-16 · test 1112
 *   - 레인이 여럿이면 서버 DI 의 선이 사이 노드를 가로질렀다 → 노드를 피해 돌렸다(66c8779)
 *   - 그런데 돌린 선들이 **같은 통로·복도를 나눠 써서 서로 포개졌다** — "어디서 나와 어디로 가는지"
 *     를 읽을 수 없었다. 그래서 이미 그은 선분을 기억하고, 겹치면 몇 px 씩 비켜 선다.
 *     같은 출발점에서 갈라지는 선(팬아웃)만 줄기를 나눠 쓴다.
 *   - 게이트웨이에서 위·아래 가지로 가는 선은 **마름모의 위·아래 꼭짓점**에서 나와 꺾는다(BPMN 관례).
 *
 * 후보를 차례로 대 보고 처음으로 "노드도 안 가로지르고 다른 선과도 안 포개지는" 것을 쓴다.
 * 그런 것이 없으면 노드만 안 가로지르는 것, 그것도 없으면 원래 선.
 */

const PAD = 4
const STEP = 9          // 겹칠 때 비켜 서는 간격
const OFFSETS = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5]

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

function segments(pts) {
  const out = []
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1], b = pts[i]
    if (Math.abs(a.y - b.y) < 0.5) out.push({ h: true, c: a.y, lo: Math.min(a.x, b.x), hi: Math.max(a.x, b.x) })
    else if (Math.abs(a.x - b.x) < 0.5) out.push({ h: false, c: a.x, lo: Math.min(a.y, b.y), hi: Math.max(a.y, b.y) })
  }
  return out
}

/** 이미 그은 선분과 포개지나(같은 방향 · 4px 안 · 구간이 2px 넘게 겹침). */
function overlaps(pts, used, s, t) {
  const segs = segments(pts)
  for (const [i, seg] of segs.entries()) {
    const last = i === segs.length - 1
    for (const u of used) {
      // 같은 도착점으로 들어가는 **마지막 짧은 토막**만 겹쳐도 된다(입구가 하나다). 길게 겹치면 다른
      // 출발점들이 한 줄로 이어진 것처럼 보이므로(두 게이트웨이가 붙어 보임) 입구 앞 48px 까지만.
      if (last && u.last && u.t === t && Math.min(u.hi, seg.hi) - Math.max(u.lo, seg.lo) <= 48) continue
      // 같은 출발점에서 갈라지는 선(팬아웃)만 줄기를 나눠 쓴다. 같은 도착점으로 모이는 선까지 포개면
      // 서로 다른 두 출발점이 한 줄로 이어진 것처럼 보였다(월 근태 마감 — 두 게이트웨이가 붙어 보임).
      if (u.s === s) continue
      if (u.h !== seg.h || Math.abs(u.c - seg.c) > 4) continue
      if (Math.min(u.hi, seg.hi) - Math.max(u.lo, seg.lo) > 2) return true
    }
  }
  return false
}

function channelAfter(S, all) {
  const right = S.x + S.w
  const lefts = all.map(b => b.x).filter(x => x > right + 1)
  const next = lefts.length ? Math.min(...lefts) : right + 60
  return right + (next - right) / 2
}

function channelBefore(T, all) {
  const left = T.x
  const rights = all.map(b => b.x + b.w).filter(x => x < left - 1)
  const prev = rights.length ? Math.max(...rights) : left - 60
  return left - (left - prev) / 2
}

function corridorYs(all, sy, ty) {
  const ys = new Set()
  for (const b of all) { ys.add(b.y - 12); ys.add(b.y + b.h + 12) }
  const top = Math.min(...all.map(b => b.y)), bottom = Math.max(...all.map(b => b.y + b.h))
  ys.add(top - 26); ys.add(bottom + 26)
  const mid = (sy + ty) / 2
  return [...ys].sort((a, b) => Math.abs(a - mid) - Math.abs(b - mid))
}

const isGateway = (tag) => !!tag && tag.endsWith('Gateway')

function candidates(S, T, all, sTag) {
  const out = []
  const sx = S.x + S.w, sy = S.y + S.h / 2
  const tx = T.x, ty = T.y + T.h / 2
  const scx = S.x + S.w / 2
  const forward = tx > sx + 1

  const tcx = T.x + T.w / 2
  if (forward) {
    if (Math.abs(sy - ty) < 1) out.push([{ x: sx, y: sy }, { x: tx, y: ty }])
    // 게이트웨이 가지 — 위·아래 꼭짓점에서 나와 꺾는다
    if (isGateway(sTag) && Math.abs(sy - ty) >= S.h / 2) {
      const vy = ty < sy ? S.y : S.y + S.h
      out.push([{ x: scx, y: vy }, { x: scx, y: ty }, { x: tx, y: ty }])
    }
  } else {
    // 되돌아가기 — 아래 꼭짓점에서 나와 **줄 아래로** 돌아 대상 밑에서 올려 꽂는다
    const under = Math.max(S.y + S.h, T.y + T.h) + 16
    for (const k of OFFSETS.filter(k => k >= 0)) {
      const y = under + k * STEP
      out.push([{ x: scx, y: S.y + S.h }, { x: scx, y }, { x: tcx, y }, { x: tcx, y: T.y + T.h }])
    }
  }
  if (forward) {
    const a = channelAfter(S, all), b = channelBefore(T, all)
    for (const k of OFFSETS) {
      for (const mx of [b + k * STEP, a + k * STEP]) {
        if (mx > sx + 2 && mx < tx - 2) out.push([{ x: sx, y: sy }, { x: mx, y: sy }, { x: mx, y: ty }, { x: tx, y: ty }])
      }
    }
    // 앞으로 건너뛰기(같은 줄 · 사이에 노드가 있어 꺾기로 안 될 때) — 위 꼭짓점에서 나와 **줄 위로** 넘어가 대상 위에서 내려 꽂는다
    const over = Math.min(S.y, T.y) - 16
    for (const k of OFFSETS.filter(k => k >= 0)) {
      const y = over - k * STEP
      out.push([{ x: scx, y: S.y }, { x: scx, y }, { x: tcx, y }, { x: tcx, y: T.y }])
    }
  }
  const m1 = channelAfter(S, all), m2 = channelBefore(T, all)
  for (const cy of corridorYs(all, sy, ty)) {
    for (const k of OFFSETS) {
      const y = cy + (cy < sy ? -k : k) * STEP
      for (const j of [0, 1, -1, 2, -2]) {
        const x1 = m1 + j * STEP, x2 = m2 - j * STEP
        out.push([{ x: sx, y: sy }, { x: x1, y: sy }, { x: x1, y }, { x: x2, y }, { x: x2, y: ty }, { x: tx, y: ty }])
      }
    }
  }
  return out
}

/**
 * @param {Record<string, Box>} boxes
 * @param {{id:string,s:string,t:string}[]} flows
 * @param {Record<string, {x:number,y:number}[]>} [current]  지금 선 — 안 가로지르면 그대로 둔다
 * @param {Record<string, string>} [tags]                     노드 종류(게이트웨이 가지 모양에 쓴다)
 */
export function routeEdges(boxes, flows, current = {}, tags = {}) {
  const all = Object.values(boxes)
  const out = {}
  const used = []
  const remember = (f, pts) => {
    const segs = segments(pts)
    segs.forEach((seg, i) => used.push({ ...seg, s: f.s, t: f.t, last: i === segs.length - 1 }))
  }

  // 짧은 선부터 — 짧은 것이 좋은 자리를 먼저 가져가야 긴 선이 비켜 돈다
  const order = [...flows].filter(f => boxes[f.s] && boxes[f.t]).sort((p, q) => {
    const d = (f) => Math.abs(boxes[f.t].x - boxes[f.s].x) + Math.abs(boxes[f.t].y - boxes[f.s].y)
    return d(p) - d(q)
  })
  for (const f of order) {
    const S = boxes[f.s], T = boxes[f.t]
    const now = current[f.id]
    if (now && !crossesNodes(now, boxes, f.s, f.t) && !overlaps(now, used, f.s, f.t)) {
      out[f.id] = now; remember(f, now); continue
    }
    const obstacles = Object.entries(boxes).filter(([id]) => id !== f.s && id !== f.t).map(([, b]) => b)
    const cand = candidates(S, T, all, tags[f.s])
    const clean = cand.find(pts => !pathHits(pts, obstacles) && !overlaps(pts, used, f.s, f.t))
    const ok = clean || cand.find(pts => !pathHits(pts, obstacles))
    const chosen = ok || now || [{ x: S.x + S.w, y: S.y + S.h / 2 }, { x: T.x, y: T.y + T.h / 2 }]
    out[f.id] = chosen
    remember(f, chosen)
  }
  return out
}

/**
 * BPMN XML 의 DI 에서 **노드를 가로지르거나 포개진 선만** 다시 긋는다. 노드·레인 DI 는 손대지 않는다.
 * 실패하면 받은 XML 을 그대로 돌려준다.
 */
export function rerouteCrossingEdges(xml) {
  try {
    const doc = new DOMParser().parseFromString(xml, 'application/xml')
    if (doc.querySelector('parsererror')) return xml
    const all = [...doc.getElementsByTagName('*')]
    const FLOW = /^(task|\w+Task|callActivity|subProcess|\w+Gateway|startEvent|endEvent|intermediate\w+Event|boundaryEvent)$/
    const tags = {}
    for (const n of all) if (FLOW.test(n.localName)) tags[n.getAttribute('id')] = n.localName
    const boxes = {}
    for (const sh of all.filter(n => n.localName === 'BPMNShape')) {
      const id = sh.getAttribute('bpmnElement')
      if (!tags[id]) continue
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
    const routed = routeEdges(boxes, flows, current, tags)
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
