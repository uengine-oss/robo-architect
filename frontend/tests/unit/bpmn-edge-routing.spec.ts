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
  expect(out.f[0]).toEqual(now.f[0])
  expect(out.f[out.f.length - 1]).toEqual(now.f[1])
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
