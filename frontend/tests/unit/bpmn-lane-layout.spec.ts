/**
 * BPMN 시퀀스 순서 + 레인 배치 (2026-11-16 · test 1112 "월 근태 마감" 을 본떠).
 */
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS
import ELK from 'elkjs/lib/elk.bundled.js'
// @ts-expect-error 플레인 JS 모듈
import { computeLaneLayout, NODE_SIZE } from '../../src/features/canvas/bpmnLaneLayout.js'
// @ts-expect-error 플레인 JS 모듈
import { crossesNodes } from '../../src/features/canvas/bpmnEdgeRouting.js'

const n = (id: string, tag = 'task') => ({ id, tag, ...NODE_SIZE(tag) })

// 시작 → A → G1 ─(되돌림)→ A / ─→ B → C → 끝.  D 는 들어오는 선이 빠진 작업(시퀀스상 C 다음) → G2 → 끝
// 서버는 D·G2 를 맨 앞 열(x 작게)에 두었다 — 그 x 를 그대로 hint 로 준다.
const model = {
  nodes: [n('S', 'startEvent'), n('A'), n('B'), n('C'), n('D'), n('G1', 'exclusiveGateway'), n('G2', 'exclusiveGateway'), n('E', 'endEvent')],
  flows: [
    { id: 'f1', s: 'S', t: 'A' }, { id: 'f2', s: 'A', t: 'G1' }, { id: 'f3', s: 'G1', t: 'A' },
    { id: 'f4', s: 'G1', t: 'B' }, { id: 'f5', s: 'B', t: 'C' }, { id: 'f6', s: 'C', t: 'E' },
    { id: 'f7', s: 'D', t: 'G2' }, { id: 'f8', s: 'G2', t: 'E' }, { id: 'f9', s: 'G2', t: 'B' },
  ],
  lanes: [{ id: 'L1', nodeIds: ['A', 'B', 'C', 'G1'] }, { id: 'L2', nodeIds: ['D', 'G2'] }],
  hintX: { S: 180, A: 380, G1: 615, B: 780, C: 980, E: 1380, D: 380, G2: 415 },
}

test('시작은 맨 왼쪽 · 끝은 맨 오른쪽', async () => {
  const L = await computeLaneLayout(model, new ELK())
  const xs = Object.values(L.boxes).map((b: any) => b.x)
  expect(L.boxes.S.x).toBe(Math.min(...xs))
  expect(L.boxes.E.x).toBe(Math.max(...xs))
})

test('들어오는 선이 빠진 작업은 시퀀스상 앞 작업 뒤에, 그 게이트웨이는 그 뒤에', async () => {
  const L = await computeLaneLayout(model, new ELK())
  expect(L.boxes.D.x).toBeGreaterThan(L.boxes.C.x)
  expect(L.boxes.G2.x).toBeGreaterThan(L.boxes.D.x)
})

test('노드는 자기 레인 띠 안에', async () => {
  const L = await computeLaneLayout(model, new ELK())
  for (const lane of model.lanes) {
    const band = L.laneBoxes[lane.id]
    for (const id of lane.nodeIds) {
      const b = L.boxes[id]
      expect(b.y).toBeGreaterThanOrEqual(band.y)
      expect(b.y + b.h).toBeLessThanOrEqual(band.y + band.h)
    }
  }
})

test('노드를 가로지르는 선이 없다', async () => {
  const L = await computeLaneLayout(model, new ELK())
  for (const f of model.flows) expect(crossesNodes(L.edges[f.id], L.boxes, f.s, f.t)).toBe(false)
})
