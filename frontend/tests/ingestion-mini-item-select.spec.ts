import { test, expect } from '@playwright/test'

/**
 * Spec 001-requirements-ingestion-sse — mid-generation property preview.
 *
 * While the floating progress panel is streaming, each entry in the live
 * created-items list is clickable. Clicking it must:
 *   1. Mark that item as selected in the canvas store so the sticker (if
 *      already on canvas) highlights and the list row shows the
 *      `mini-item--selected` style.
 *   2. Forward the item payload through `inspectorRequestStore.request`
 *      so CanvasWorkspace opens the InspectorPanel with the node's
 *      properties — even when the node is not yet rendered on the canvas.
 *
 * The backend is in-memory and SSE-driven, so we mock at the browser
 * boundary the same way `ingestion-resume-button.spec.ts` does.
 */

const SID = 'pwtest-mini-item'

test('clicking a streamed mini-item selects the node and opens the inspector', async ({
  page,
  context
}) => {
  // 1. Seed localStorage so checkAndRestoreSession picks the session.
  await context.addInitScript((sessionId) => {
    localStorage.setItem(
      'ingestion_active_session',
      JSON.stringify({ sessionId, startedAt: Date.now() })
    )
  }, SID)

  // 2. Controllable EventSource double (same pattern as resume-button test).
  await context.addInitScript(() => {
    class FakeEventSource {
      static __instances: any[] = []
      url: string
      readyState: number
      private _listeners: Record<string, Array<(e: any) => void>> = {}
      onopen: ((e: any) => void) | null = null
      onerror: ((e: any) => void) | null = null
      onmessage: ((e: any) => void) | null = null
      constructor(url: string) {
        this.url = url
        this.readyState = 0
        FakeEventSource.__instances.push(this)
        setTimeout(() => {
          this.readyState = 1
          this.onopen && this.onopen({})
        }, 10)
      }
      addEventListener(name: string, handler: (e: any) => void) {
        ;(this._listeners[name] ||= []).push(handler)
      }
      removeEventListener(name: string, handler: (e: any) => void) {
        const list = this._listeners[name]
        if (!list) return
        const idx = list.indexOf(handler)
        if (idx >= 0) list.splice(idx, 1)
      }
      close() {
        this.readyState = 2
      }
      __dispatch(name: string, data: any) {
        const ev = { data: typeof data === 'string' ? data : JSON.stringify(data) }
        ;(this._listeners[name] || []).forEach((h) => h(ev))
        if (name === 'message' && this.onmessage) this.onmessage(ev)
      }
    }
    ;(FakeEventSource as any).CONNECTING = 0
    ;(FakeEventSource as any).OPEN = 1
    ;(FakeEventSource as any).CLOSED = 2
    ;(window as any).EventSource = FakeEventSource
    ;(window as any).__sse = FakeEventSource
  })

  // 3. Stub the network endpoints the modal calls on restore.
  await page.route('**/api/ingest/session/' + SID + '/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        active: true,
        phase: 'extracting_aggregates',
        message: 'Aggregate 생성 중',
        progress: 60,
        isPaused: false,
        suspendState: 'running',
        tokens: { total: 100, approximate: false, byPhase: {} }
      })
    })
  })
  await page.route('**/api/ingest/cache/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ enabled: false })
    })
  })

  // The clicked item is not on the canvas yet — InspectorPanel will try to
  // fetch the node by id. Stub that endpoint so the panel renders without
  // network errors. Match the InspectorPanel fetch shape (`/api/graph/...`)
  // loosely: return 404 so it falls back to the inlined nodeData payload.
  await page.route('**/api/graph/**', async (route) => {
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'not found' })
    })
  })

  page.on('console', (msg) => {
    const text = msg.text()
    if (
      text.includes('inspector_open') ||
      text.includes('mini-item') ||
      msg.type() === 'error'
    ) {
      // eslint-disable-next-line no-console
      console.log('[browser]', msg.type(), text)
    }
  })

  await page.goto('/')

  const panel = page.locator('.floating-panel')
  await expect(panel).toBeVisible({ timeout: 15_000 })

  // Wait until the SSE double is wired before dispatching events.
  await page.waitForFunction(
    () => (window as any).__sse?.__instances?.length > 0,
    { timeout: 10_000 }
  )

  // 4. Push a progress event carrying a created Aggregate object — this is
  //    the shape ingestion_workflow_runner emits while streaming.
  const item = {
    id: 'agg-test-1',
    type: 'Aggregate',
    name: 'TestAggregate',
    displayName: 'Test Aggregate',
    description: 'A test aggregate streamed mid-run.',
    bcId: 'bc-test'
  }
  await page.evaluate((obj) => {
    const es = (window as any).__sse.__instances[0]
    es.__dispatch('progress', {
      phase: 'extracting_aggregates',
      message: 'Aggregate 생성: TestAggregate (1/1)',
      progress: 60,
      data: { object: obj },
      tokens: { total: 120, approximate: false },
      suspendState: 'running'
    })
  }, item)

  // 5. The mini-item appears in the live list with the correct affordances.
  const miniItem = panel.locator('.mini-item', { hasText: 'TestAggregate' })
  await expect(miniItem).toBeVisible({ timeout: 5_000 })
  await expect(miniItem).toHaveAttribute('role', 'button')

  // Before click: not selected.
  await expect(miniItem).not.toHaveClass(/mini-item--selected/)

  // Capture inspector_open console events so we can assert the bridge fired.
  const inspectorOpens: Array<Record<string, unknown>> = []
  page.on('console', (msg) => {
    const text = msg.text()
    if (text.includes('[RAW][CanvasWorkspace][inspector_open]')) {
      inspectorOpens.push({ text })
    }
  })

  // 6. Click the row → triggers selectNode + inspectorRequest bridge.
  await miniItem.click()

  // After click: row reflects canvas selection.
  await expect(miniItem).toHaveClass(/mini-item--selected/, { timeout: 3_000 })

  // 7. CanvasWorkspace consumed the inspector request — the inspector
  //    container becomes visible (panelMode flips to 'inspector').
  //    We don't assert specific Inspector internals (network-coupled); we
  //    only assert that the bridge produced an inspector_open log.
  await expect
    .poll(() => inspectorOpens.length, { timeout: 5_000 })
    .toBeGreaterThan(0)
})
