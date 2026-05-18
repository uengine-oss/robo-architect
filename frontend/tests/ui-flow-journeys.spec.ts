import { test, expect } from '@playwright/test'
import { readFileSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

/**
 * Spec 025 — journey-based navigator list.
 *
 * Verifies against REAL PDF-derived data: the fixture
 * `spec-025-pdf-event-modeling.json` is the actual /api/graph/event-modeling
 * response dumped from the graph produced by ingesting
 * `input/회원가입 · 회원탈퇴 정책서 Full v1.0 확정본.pdf` (NEXT_UI re-derived).
 *
 * Asserts:
 *  - `journeyChains` groups command-processes into NEXT_UI journeys (top)
 *    + leftover command-processes as individual entries (bottom)
 *  - single click replaces the canvas, Ctrl+click toggles (multi-compare)
 */

const FIXTURE = JSON.parse(
  readFileSync(join(__dirname, 'fixtures', 'spec-025-pdf-event-modeling.json'), 'utf-8')
)

async function bootEventModeling(page) {
  await page.route('**/api/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  })
  await page.route('**/api/graph/event-modeling**', async (route) => {
    if (route.request().method() !== 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(FIXTURE),
    })
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Event Modeling', exact: true }).click()
}

test('journeyChains groups PDF-derived NEXT_UI into journeys + leftovers', async ({ page }) => {
  await bootEventModeling(page)

  const result = await page.evaluate(async () => {
    const root = document.querySelector('#app') as any
    const store = root.__vue_app__.config.globalProperties.$pinia._s.get('eventModeling')
    await store.fetchProcessList()
    const items = store.journeyChains
    return {
      total: items.length,
      journeys: items
        .filter((i: any) => i.kind === 'journey')
        .map((i: any) => ({
          journeyId: i.journeyId, name: i.name, badge: i.badge,
          uiCount: i.uiCount, procs: i.processIds.length,
        })),
      leftovers: items.filter((i: any) => i.kind === 'process').length,
      commandChains: store.processChains.length,
    }
  })

  console.log('JOURNEY_DUMP ' + JSON.stringify(result, null, 2))

  // The PDF (회원가입·회원탈퇴 정책서) yields 4 purpose-driven journeys —
  // NOT one giant blob. Journey grouping is by NEXT_UI `journey_id`.
  expect(result.journeys.length).toBe(4)
  for (const j of result.journeys) {
    expect(j.journeyId).toBeTruthy()
    expect(j.procs).toBeGreaterThan(0)
    expect(j.uiCount).toBeGreaterThan(0)
    expect(j.badge).toBeGreaterThan(0)   // badge = NEXT_UI edge count
  }
  // Distinct journey names (purposes).
  const names = result.journeys.map((j: any) => j.name)
  expect(new Set(names).size).toBe(4)
  // List covers everything: journeys + leftover command-processes.
  expect(result.total).toBe(result.journeys.length + result.leftovers)
})

test('selecting a journey filters the canvas to that journey only', async ({ page }) => {
  await bootEventModeling(page)

  const r = await page.evaluate(async () => {
    const root = document.querySelector('#app') as any
    const store = root.__vue_app__.config.globalProperties.$pinia._s.get('eventModeling')
    await store.fetchProcessList()
    const journeys = store.journeyChains.filter((i: any) => i.kind === 'journey')
    const j0 = journeys[0]

    // single click journey 0 → canvas shows ONLY journey 0's edges
    store.showCanvasItem(j0)
    const edgesA = store.uiFlowEdges.map((e: any) => e.journey_id)
    const activeA = [...store.activeJourneyIds]

    // switch to journey 1 → canvas replaced with journey 1's edges
    const j1 = journeys[1]
    store.showCanvasItem(j1)
    const edgesB = store.uiFlowEdges.map((e: any) => e.journey_id)

    return {
      j0Id: j0.journeyId, j1Id: j1.journeyId,
      edgesA, activeA, edgesB,
    }
  })

  // Active journey set holds exactly the clicked journey.
  expect(r.activeA).toEqual([r.j0Id])
  // Every rendered NEXT_UI edge belongs to journey 0 (no cross-journey leak).
  expect(r.edgesA.length).toBeGreaterThan(0)
  for (const jid of r.edgesA) expect(jid).toBe(r.j0Id)
  // After switching, every edge belongs to journey 1.
  expect(r.edgesB.length).toBeGreaterThan(0)
  for (const jid of r.edgesB) expect(jid).toBe(r.j1Id)
})

test('single click replaces canvas; Ctrl+click toggles (multi-compare)', async ({ page }) => {
  await bootEventModeling(page)

  const r = await page.evaluate(async () => {
    const root = document.querySelector('#app') as any
    const store = root.__vue_app__.config.globalProperties.$pinia._s.get('eventModeling')
    await store.fetchProcessList()
    const items = store.journeyChains
    const a = items[0]
    const b = items[1]

    // single click on A → canvas == A.processIds
    store.showCanvasItem(a)
    const afterA = new Set(store.canvasProcessIds)

    // single click on B → canvas REPLACED with B.processIds (A gone)
    store.showCanvasItem(b)
    const afterB = new Set(store.canvasProcessIds)

    // Ctrl+click on A → A added on top of B (accumulate)
    store.toggleCanvasItem(a)
    const afterCtrlA = new Set(store.canvasProcessIds)

    // Ctrl+click on A again → A removed (toggle off)
    store.toggleCanvasItem(a)
    const afterCtrlAgain = new Set(store.canvasProcessIds)

    return {
      aIds: a.processIds,
      bIds: b.processIds,
      afterA: [...afterA],
      afterB: [...afterB],
      afterCtrlA: [...afterCtrlA],
      afterCtrlAgain: [...afterCtrlAgain],
    }
  })

  // single click A: canvas exactly = A
  expect(new Set(r.afterA)).toEqual(new Set(r.aIds))
  // single click B: canvas exactly = B (A replaced, not accumulated)
  expect(new Set(r.afterB)).toEqual(new Set(r.bIds))
  for (const id of r.aIds) {
    if (!r.bIds.includes(id)) expect(r.afterB).not.toContain(id)
  }
  // Ctrl+click A: B still present AND A present (accumulated)
  for (const id of r.bIds) expect(r.afterCtrlA).toContain(id)
  for (const id of r.aIds) expect(r.afterCtrlA).toContain(id)
  // Ctrl+click A again: A removed, B remains
  for (const id of r.aIds) {
    if (!r.bIds.includes(id)) expect(r.afterCtrlAgain).not.toContain(id)
  }
  for (const id of r.bIds) expect(r.afterCtrlAgain).toContain(id)
})
