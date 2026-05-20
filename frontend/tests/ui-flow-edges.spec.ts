import { test, expect } from '@playwright/test'

/**
 * Spec 025 — UI Sticker Flow Edges with Conditional Gateways.
 *
 * Verifies the visual contract on the event-modeling canvas:
 *   - `NEXT_UI` edges render as dashed purple arrows between UI stickers
 *   - `Gateway` nodes render as yellow diamonds (SVG polygons)
 *   - Condition labels are visible on edges out of a Gateway
 *
 * The backend is mocked at the network boundary so the test doesn't
 * require a live Neo4j or LLM provider.
 */

const SCREENSHOT_PATH = 'tests/.artifacts/spec-025-ui-flow.png'

// Canned API response — same shape as /api/graph/event-modeling, with the
// spec 025 additive fields populated.
const CANNED_RESPONSE = {
  // Empty existing data-flow layer is fine — we are only asserting the new layer.
  actorSwimlanes: [
    {
      actor: '고객',
      uis: [
        { id: 'ui-login', name: 'Login', displayName: 'Login', sequence: 1, isOutput: false },
        { id: 'ui-dashboard', name: 'Dashboard', displayName: 'Dashboard', sequence: 2, isOutput: false },
        { id: 'ui-detail', name: 'Detail', displayName: 'Detail', sequence: 3, isOutput: false },
      ]
    }
  ],
  interactionCommands: [],
  interactionReadModels: [],
  systemSwimlanes: [
    {
      bcId: 'bc-order',
      bcName: 'Order',
      bcDisplayName: 'Order',
      events: []
    }
  ],
  flows: [],
  maxSequence: 3,
  // ── spec 025 — UI flow layer ───────────────────────────────────────
  gateways: [
    {
      id: 'gw-approval',
      key: 'order.gateway.approval-abc123',
      label: '주문 승인?',
      kind: 'exclusive',
      bounded_context_id: 'bc-order',
      source: 'llm',
      created_at: '2026-05-15T00:00:00',
      updated_at: '2026-05-15T00:00:00'
    }
  ],
  uiFlowEdges: [
    {
      id: 'e-login-dashboard',
      source_id: 'ui-login',
      source_kind: 'ui',
      target_id: 'ui-dashboard',
      target_kind: 'ui',
      condition: '',
      source: 'llm',
      document_excerpt: '로그인 성공 시 대시보드로 이동',
      created_at: '2026-05-15T00:00:00',
      updated_at: '2026-05-15T00:00:00'
    },
    {
      id: 'e-dashboard-gw',
      source_id: 'ui-dashboard',
      source_kind: 'ui',
      target_id: 'gw-approval',
      target_kind: 'gateway',
      condition: '',
      source: 'llm',
      document_excerpt: '대시보드에서 주문 검토 후 결정',
      created_at: '2026-05-15T00:00:00',
      updated_at: '2026-05-15T00:00:00'
    },
    {
      id: 'e-gw-detail-approve',
      source_id: 'gw-approval',
      source_kind: 'gateway',
      target_id: 'ui-detail',
      target_kind: 'ui',
      condition: '승인됨',
      source: 'llm',
      document_excerpt: '승인 시 상세 화면',
      created_at: '2026-05-15T00:00:00',
      updated_at: '2026-05-15T00:00:00'
    },
    {
      id: 'e-gw-login-reject',
      source_id: 'gw-approval',
      source_kind: 'gateway',
      target_id: 'ui-login',
      target_kind: 'ui',
      condition: '반려됨',
      source: 'llm',
      document_excerpt: '반려 시 로그인 화면으로 복귀',
      created_at: '2026-05-15T00:00:00',
      updated_at: '2026-05-15T00:00:00'
    }
  ]
}

test('UI flow layer: NEXT_UI edges and Gateway diamonds render on the event-modeling canvas', async ({ page }) => {
  // Route order matters: Playwright gives priority to the LAST-registered
  // matching route. Register the broad catch-all first, the specific
  // event-modeling mock last so it wins for that URL.
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
      body: JSON.stringify(CANNED_RESPONSE)
    })
  })

  await page.goto('/')

  // Switch to the Event Modeling tab.
  await page.getByRole('button', { name: 'Event Modeling', exact: true }).click()

  // Drive the Pinia store directly: directly populate the canvas refs from
  // our canned response. We skip the network fetch path entirely because
  // _rebuildCanvas() requires processChains (which need commands+events)
  // and our fixture intentionally has none — we only want to test the
  // UI-flow layer on its own.
  await page.evaluate(async (resp) => {
    const root = document.querySelector('#app') as any
    if (!root || !root.__vue_app__) throw new Error('Vue app not mounted on #app')
    const pinia = root.__vue_app__.config.globalProperties.$pinia
    if (!pinia) throw new Error('Pinia not found on app')
    const store = pinia._s.get('eventModeling')
    if (!store) throw new Error('eventModeling store not found')
    store.actorSwimlanes = resp.actorSwimlanes
    store.interactionCommands = resp.interactionCommands
    store.interactionReadModels = resp.interactionReadModels
    store.systemSwimlanes = resp.systemSwimlanes
    store.flows = resp.flows
    store.maxSequence = resp.maxSequence
    store.gateways = resp.gateways
    store.uiFlowEdges = resp.uiFlowEdges
  }, CANNED_RESPONSE)

  // ── Assertion 1: Gateway diamond renders ───────────────────────────
  const gatewayLayer = page.getByTestId('em-gateways-layer')
  await expect(gatewayLayer).toBeVisible()

  const gatewayNode = page.getByTestId('em-gateway-gw-approval')
  await expect(gatewayNode).toBeVisible()

  // The diamond is an SVG polygon with the yellow fill we specified.
  const polygon = gatewayNode.locator('polygon')
  await expect(polygon).toHaveAttribute('fill', '#fff8db')
  await expect(polygon).toHaveAttribute('stroke', '#f08c00')

  // ── Assertion 2: Gateway label text is rendered ────────────────────
  await expect(gatewayNode.locator('text')).toContainText('주문 승인?')

  // ── Assertion 3: NEXT_UI paths render with the light-gray solid style ─
  const uiFlowPaths = page.locator('.em-uiflow-paths > path[stroke="#c4c8d0"]')
  // We have 4 edges in the fixture: login→dashboard, dashboard→gw,
  // gw→detail, gw→login. All four should produce visible paths.
  await expect(uiFlowPaths).toHaveCount(4)

  for (let i = 0; i < 4; i++) {
    const p = uiFlowPaths.nth(i)
    // Solid line — no dash array.
    await expect(p).not.toHaveAttribute('stroke-dasharray', /.+/)
  }

  // ── Assertion 4: Condition labels appear for the two gateway-out edges ──
  // The label <g> wrappers are v-show="p.condition" so empty-condition edges
  // produce hidden <text> nodes. Query *visible* text nodes only.
  const visibleLabels = await page.locator('.em-uiflow-paths text:visible').allTextContents()
  expect(visibleLabels.some(t => t.includes('승인됨'))).toBeTruthy()
  expect(visibleLabels.some(t => t.includes('반려됨'))).toBeTruthy()

  // ── Assertion 5: Selecting a gateway updates the store ─────────────
  // Click directly on the polygon body — the bounding box of the parent <g>
  // includes the diamond's empty corners which would fall through.
  await gatewayNode.locator('polygon').click()
  const selected = await page.evaluate(() => {
    const root = document.querySelector('#app') as any
    const pinia = root.__vue_app__.config.globalProperties.$pinia
    const store = pinia._s.get('eventModeling')
    return { id: store.selectedItemId, type: store.selectedItemType }
  })
  expect(selected.id).toBe('gw-approval')
  expect(selected.type).toBe('gateway')

  // ── Screenshot for visual verification (artifact) ──────────────────
  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true })
})


// Fuller fixture: 3 vertical slices whose data-flow `sequence` is 1,2,3 but
// whose NEXT_UI flow is C → A → B. After the canvas rebuild, the columns
// must be re-ordered so the leftmost slice is C, then A, then B.
const REORDER_RESPONSE = {
  actorSwimlanes: [
    {
      actor: '고객',
      uis: [
        { id: 'ui-A', name: 'A화면', displayName: 'A화면', sequence: 1, isOutput: false },
        { id: 'ui-B', name: 'B화면', displayName: 'B화면', sequence: 2, isOutput: false },
        { id: 'ui-C', name: 'C화면', displayName: 'C화면', sequence: 3, isOutput: false },
      ]
    }
  ],
  interactionCommands: [
    { id: 'cmd-A', name: 'CmdA', displayName: 'CmdA', sequence: 1, actor: '고객' },
    { id: 'cmd-B', name: 'CmdB', displayName: 'CmdB', sequence: 2, actor: '고객' },
    { id: 'cmd-C', name: 'CmdC', displayName: 'CmdC', sequence: 3, actor: '고객' },
  ],
  interactionReadModels: [],
  systemSwimlanes: [
    {
      bcId: 'bc-x',
      bcName: 'X',
      bcDisplayName: 'X',
      events: [
        { id: 'evt-A', name: 'EvtA', displayName: 'EvtA', sequence: 1 },
        { id: 'evt-B', name: 'EvtB', displayName: 'EvtB', sequence: 2 },
        { id: 'evt-C', name: 'EvtC', displayName: 'EvtC', sequence: 3 },
      ]
    }
  ],
  flows: [
    { type: 'ui-to-command', sourceId: 'ui-A', targetId: 'cmd-A' },
    { type: 'ui-to-command', sourceId: 'ui-B', targetId: 'cmd-B' },
    { type: 'ui-to-command', sourceId: 'ui-C', targetId: 'cmd-C' },
    { type: 'command-to-event', sourceId: 'cmd-A', targetId: 'evt-A' },
    { type: 'command-to-event', sourceId: 'cmd-B', targetId: 'evt-B' },
    { type: 'command-to-event', sourceId: 'cmd-C', targetId: 'evt-C' },
  ],
  maxSequence: 3,
  gateways: [],
  // NEXT_UI flow: C → A → B  (deliberately ≠ data-flow sequence 1,2,3)
  uiFlowEdges: [
    { id: 'e-C-A', source_id: 'ui-C', source_kind: 'ui', target_id: 'ui-A', target_kind: 'ui', condition: '', source: 'llm', document_excerpt: '' },
    { id: 'e-A-B', source_id: 'ui-A', source_kind: 'ui', target_id: 'ui-B', target_kind: 'ui', condition: '', source: 'llm', document_excerpt: '' },
  ]
}

test('adding processes re-orders UI columns by NEXT_UI flow (C → A → B)', async ({ page }) => {
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
      body: JSON.stringify(REORDER_RESPONSE)
    })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Event Modeling', exact: true }).click()

  // Drive the real navigator → canvas path: fetchEventModeling() loads the
  // response, builds processChains, adds all to canvas, runs _rebuildCanvas()
  // which performs the NEXT_UI column re-ordering.
  const seqByUi = await page.evaluate(async () => {
    const root = document.querySelector('#app') as any
    const pinia = root.__vue_app__.config.globalProperties.$pinia
    const store = pinia._s.get('eventModeling')
    await store.fetchEventModeling()
    const uis = store.actorSwimlanes.flatMap((l: any) => l.uis)
    const out: Record<string, number> = {}
    for (const u of uis) out[u.id] = u.sequence
    return out
  })

  // Data-flow sequence was A=1, B=2, C=3.
  // NEXT_UI flow C → A → B must re-order columns so C is leftmost (seq 1),
  // A is second (seq 2), B is third (seq 3).
  expect(seqByUi['ui-C']).toBe(1)
  expect(seqByUi['ui-A']).toBe(2)
  expect(seqByUi['ui-B']).toBe(3)

  // The two NEXT_UI edges must render as solid light-gray paths.
  const uiFlowPaths = page.locator('.em-uiflow-paths > path[stroke="#c4c8d0"]')
  await expect(uiFlowPaths).toHaveCount(2)
  await expect(uiFlowPaths.first()).not.toHaveAttribute('stroke-dasharray', /.+/)

  await page.screenshot({ path: 'tests/.artifacts/spec-025-ui-flow-reorder.png', fullPage: true })
})

test('adding one process pulls in NEXT_UI-connected processes', async ({ page }) => {
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
      body: JSON.stringify(REORDER_RESPONSE)
    })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Event Modeling', exact: true }).click()

  // REORDER_RESPONSE has 3 separate command-centric processes (cmd-A/B/C),
  // but the NEXT_UI edges C→A→B chain all three UIs into one journey.
  // Adding ONLY the cmd-A process must transitively pull in cmd-B + cmd-C.
  const result = await page.evaluate(async () => {
    const root = document.querySelector('#app') as any
    const store = root.__vue_app__.config.globalProperties.$pinia._s.get('eventModeling')
    await store.fetchProcessList()
    const chains = store.processChains
    const targetChain = chains.find((c: any) => c.steps.some((s: any) => s.id === 'ui-A'))
    if (!targetChain) throw new Error('process chain containing ui-A not found')
    store.addProcessToCanvas(targetChain.id)
    return {
      canvasCount: store.canvasProcessIds.size,
      uiIds: store.actorSwimlanes.flatMap((l: any) => l.uis).map((u: any) => u.id).sort(),
    }
  })

  // All 3 command-processes must be on canvas, all 3 UIs rendered.
  expect(result.canvasCount).toBe(3)
  expect(result.uiIds).toEqual(['ui-A', 'ui-B', 'ui-C'])
})

// Two independent NEXT_UI chains whose data-flow `sequence` values are
// INTERLEAVED (P1=1, Q1=2, P2=3, Q2=4). Plain Kahn would keep 1,2,3,4 →
// each chain stretched to span 2. Chain-following ordering must place each
// chain's columns ADJACENT so connecting lines are length 1.
const INTERLEAVE_RESPONSE = {
  actorSwimlanes: [
    {
      actor: '고객',
      uis: [
        { id: 'ui-P1', name: 'P1', displayName: 'P1', sequence: 1, isOutput: false },
        { id: 'ui-Q1', name: 'Q1', displayName: 'Q1', sequence: 2, isOutput: false },
        { id: 'ui-P2', name: 'P2', displayName: 'P2', sequence: 3, isOutput: false },
        { id: 'ui-Q2', name: 'Q2', displayName: 'Q2', sequence: 4, isOutput: false },
      ]
    }
  ],
  interactionCommands: [
    { id: 'cmd-P1', name: 'CmdP1', displayName: 'CmdP1', sequence: 1, actor: '고객' },
    { id: 'cmd-Q1', name: 'CmdQ1', displayName: 'CmdQ1', sequence: 2, actor: '고객' },
    { id: 'cmd-P2', name: 'CmdP2', displayName: 'CmdP2', sequence: 3, actor: '고객' },
    { id: 'cmd-Q2', name: 'CmdQ2', displayName: 'CmdQ2', sequence: 4, actor: '고객' },
  ],
  interactionReadModels: [],
  systemSwimlanes: [
    {
      bcId: 'bc-x', bcName: 'X', bcDisplayName: 'X',
      events: [
        { id: 'evt-P1', name: 'EvtP1', displayName: 'EvtP1', sequence: 1 },
        { id: 'evt-Q1', name: 'EvtQ1', displayName: 'EvtQ1', sequence: 2 },
        { id: 'evt-P2', name: 'EvtP2', displayName: 'EvtP2', sequence: 3 },
        { id: 'evt-Q2', name: 'EvtQ2', displayName: 'EvtQ2', sequence: 4 },
      ]
    }
  ],
  flows: [
    { type: 'ui-to-command', sourceId: 'ui-P1', targetId: 'cmd-P1' },
    { type: 'ui-to-command', sourceId: 'ui-Q1', targetId: 'cmd-Q1' },
    { type: 'ui-to-command', sourceId: 'ui-P2', targetId: 'cmd-P2' },
    { type: 'ui-to-command', sourceId: 'ui-Q2', targetId: 'cmd-Q2' },
    { type: 'command-to-event', sourceId: 'cmd-P1', targetId: 'evt-P1' },
    { type: 'command-to-event', sourceId: 'cmd-Q1', targetId: 'evt-Q1' },
    { type: 'command-to-event', sourceId: 'cmd-P2', targetId: 'evt-P2' },
    { type: 'command-to-event', sourceId: 'cmd-Q2', targetId: 'evt-Q2' },
  ],
  maxSequence: 4,
  gateways: [],
  // Chain P: P1 → P2.  Chain Q: Q1 → Q2.
  uiFlowEdges: [
    { id: 'e-P', source_id: 'ui-P1', source_kind: 'ui', target_id: 'ui-P2', target_kind: 'ui', condition: '', source: 'llm', document_excerpt: '' },
    { id: 'e-Q', source_id: 'ui-Q1', source_kind: 'ui', target_id: 'ui-Q2', target_kind: 'ui', condition: '', source: 'llm', document_excerpt: '' },
  ]
}

test('chain-following ordering keeps NEXT_UI-connected columns adjacent (short lines)', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  })
  await page.route('**/api/graph/event-modeling**', async (route) => {
    if (route.request().method() !== 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
    }
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify(INTERLEAVE_RESPONSE)
    })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Event Modeling', exact: true }).click()

  const seq = await page.evaluate(async () => {
    const root = document.querySelector('#app') as any
    const store = root.__vue_app__.config.globalProperties.$pinia._s.get('eventModeling')
    await store.fetchEventModeling()
    const uis = store.actorSwimlanes.flatMap((l: any) => l.uis)
    const out: Record<string, number> = {}
    for (const u of uis) out[u.id] = u.sequence
    return out
  })

  // Each chain's two columns must be ADJACENT (line length 1), not span 2.
  expect(Math.abs(seq['ui-P1'] - seq['ui-P2'])).toBe(1)
  expect(Math.abs(seq['ui-Q1'] - seq['ui-Q2'])).toBe(1)
})

test('NEXT_UI lines: Bezier curve by default, toolbar toggle switches to straight', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  })
  await page.route('**/api/graph/event-modeling**', async (route) => {
    if (route.request().method() !== 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
    }
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify(CANNED_RESPONSE)
    })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Event Modeling', exact: true }).click()
  await page.evaluate(async (resp) => {
    const root = document.querySelector('#app') as any
    const store = root.__vue_app__.config.globalProperties.$pinia._s.get('eventModeling')
    store.actorSwimlanes = resp.actorSwimlanes
    store.interactionCommands = resp.interactionCommands
    store.interactionReadModels = resp.interactionReadModels
    store.systemSwimlanes = resp.systemSwimlanes
    store.flows = resp.flows
    store.maxSequence = resp.maxSequence
    store.gateways = resp.gateways
    store.uiFlowEdges = resp.uiFlowEdges
  }, CANNED_RESPONSE)

  const firstPath = page.locator('.em-uiflow-paths > path[stroke="#c4c8d0"]').first()

  // Default: Bezier curve — the path `d` uses a cubic-curve command (C).
  await expect(firstPath).toHaveAttribute('d', /C/)

  // Toolbar toggle exists and is active by default.
  const curveBtn = page.locator('button[title*="UI 흐름선"]')
  await expect(curveBtn).toHaveClass(/is-active/)

  // Click → straight: path `d` becomes an orthogonal step path (no C command).
  await curveBtn.click()
  await expect(curveBtn).not.toHaveClass(/is-active/)
  await expect(firstPath).not.toHaveAttribute('d', /C/)

  // Click again → back to Bezier.
  await curveBtn.click()
  await expect(firstPath).toHaveAttribute('d', /C/)
})
