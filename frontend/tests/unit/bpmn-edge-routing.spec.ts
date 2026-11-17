/**
 * BPMN 선 다시 긋기 (2026-11-16) — 노드 자리는 그대로, 노드를 가로지르는 선만 돌린다.
 */
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import { routeEdges, crossesNodes } from '../../src/features/canvas/bpmnEdgeRouting.js'

// 한 줄에 A · B · C, 아래 줄에 D. 열 간격 200, 작업 120×80.
const boxes = {
  A: { x: 200, y: 100, w: 120, h: 80 },
  B: { x: 400, y: 100, w: 120, h: 80 },
  C: { x: 600, y: 100, w: 120, h: 80 },
  D: { x: 400, y: 260, w: 120, h: 80 },
}
const straight = (s, t) => [
  { x: boxes[s].x + boxes[s].w, y: boxes[s].y + 40 },
  { x: boxes[t].x, y: boxes[t].y + 40 },
]

test('가로지르지 않는 선은 그대로 둔다', () => {
  const now = { f1: straight('A', 'B') }
  const out = routeEdges(boxes, [{ id: 'f1', s: 'A', t: 'B' }], now)
  expect(out.f1).toBe(now.f1)
})

test('열을 건너뛰는 선(A→C)이 B 를 가로지르면 돌아간다', () => {
  const now = { f: straight('A', 'C') }
  expect(crossesNodes(now.f, boxes, 'A', 'C')).toBe(true)
  const out = routeEdges(boxes, [{ id: 'f', s: 'A', t: 'C' }], now)
  expect(crossesNodes(out.f, boxes, 'A', 'C')).toBe(false)
  // 같은 줄을 건너뛰면 위 꼭짓점에서 나와 줄 위로 넘어가 대상 위에서 꽂는다 — 시작·끝은 상자 테두리 위
  const onEdge = (p: any, b: any) =>
    p.x >= b.x - 0.5 && p.x <= b.x + b.w + 0.5 && p.y >= b.y - 0.5 && p.y <= b.y + b.h + 0.5 &&
    (Math.abs(p.x - b.x) < 0.5 || Math.abs(p.x - b.x - b.w) < 0.5 || Math.abs(p.y - b.y) < 0.5 || Math.abs(p.y - b.y - b.h) < 0.5)
  expect(onEdge(out.f[0], boxes.A)).toBe(true)
  expect(onEdge(out.f[out.f.length - 1], boxes.C)).toBe(true)
  expect(Math.min(...out.f.map((p: any) => p.y))).toBeLessThan(boxes.B.y)   // 줄 위로 넘어간다
})

test('서로 다른 출발점의 선은 포개지지 않는다(입구 앞 짧은 토막 말고)', () => {
  const flows = [{ id: 'p', s: 'A', t: 'C' }, { id: 'q', s: 'D', t: 'C' }]
  const out = routeEdges(boxes, flows, {})
  const segs = (pts: any[]) => pts.slice(1).map((b, i) => ({ a: pts[i], b }))
  for (const s1 of segs(out.p)) for (const s2 of segs(out.q)) {
    const h1 = s1.a.y === s1.b.y, h2 = s2.a.y === s2.b.y
    if (h1 !== h2) continue
    const c1 = h1 ? s1.a.y : s1.a.x, c2 = h2 ? s2.a.y : s2.a.x
    if (Math.abs(c1 - c2) > 4) continue
    const [l1, r1] = h1 ? [Math.min(s1.a.x, s1.b.x), Math.max(s1.a.x, s1.b.x)] : [Math.min(s1.a.y, s1.b.y), Math.max(s1.a.y, s1.b.y)]
    const [l2, r2] = h2 ? [Math.min(s2.a.x, s2.b.x), Math.max(s2.a.x, s2.b.x)] : [Math.min(s2.a.y, s2.b.y), Math.max(s2.a.y, s2.b.y)]
    expect(Math.min(r1, r2) - Math.max(l1, l2)).toBeLessThanOrEqual(48)
  }
})

test('되돌아가는 선(C→A)도 노드를 피한다', () => {
  const now = { b: [{ x: 720, y: 140 }, { x: 200, y: 140 }] }
  const out = routeEdges(boxes, [{ id: 'b', s: 'C', t: 'A' }], now)
  expect(crossesNodes(out.b, boxes, 'C', 'A')).toBe(false)
})

test('모든 선분은 직교다', () => {
  const out = routeEdges(boxes, [{ id: 'f', s: 'A', t: 'C' }, { id: 'b', s: 'C', t: 'A' }], {
    f: straight('A', 'C'), b: [{ x: 720, y: 140 }, { x: 200, y: 140 }],
  })
  for (const pts of Object.values(out)) {
    for (let i = 1; i < pts.length; i++) {
      expect(pts[i].x === pts[i - 1].x || pts[i].y === pts[i - 1].y).toBe(true)
    }
  }
})
