import { test, expect } from '@playwright/test'

/**
 * Verifies the floating-panel resume (▶) button:
 *  - swaps icon (pause-bars → play-triangle) when the SSE stream emits a
 *    `phase: "paused"` event
 *  - dispatches POST /api/ingest/{sid}/resume on click
 *  - flips the icon back to pause-bars after resume
 *
 * The backend session store is in-memory and resets on every server reload, so
 * we mock at the browser layer:
 *  - EventSource is replaced with a controllable test double so the SSE
 *    connection stays open and never triggers `onerror` (which would otherwise
 *    flip the panel into the `오류 발생` error state and hide the button).
 *  - All /api/ingest/* HTTP calls are stubbed with `page.route`.
 */

const SID = 'pwtest123'

test('floating panel ▶ click sends /resume and unpauses session', async ({ page, context }) => {
  // 1. Seed localStorage so checkAndRestoreSession picks the session.
  await context.addInitScript((sessionId) => {
    localStorage.setItem(
      'ingestion_active_session',
      JSON.stringify({ sessionId, startedAt: Date.now() })
    )
  }, SID)

  // 2. Replace EventSource with a controllable double exposed on window.__sse.
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

  // 3. Status endpoint — initially paused.
  let backendIsPaused = true
  await page.route('**/api/ingest/session/' + SID + '/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        active: true,
        phase: backendIsPaused ? 'paused' : 'extracting_aggregates',
        message: backendIsPaused
          ? '⏸️ 일시 정지됨 (채팅으로 일부를 수정한 후 재개하세요)'
          : 'Aggregate 생성: Test (1/1)',
        progress: 45,
        isPaused: backendIsPaused,
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

  // 4. Resume endpoint.
  let resumeCallCount = 0
  await page.route('**/api/ingest/' + SID + '/resume', async (route) => {
    resumeCallCount++
    backendIsPaused = false
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        status: 'resumed',
        session_id: SID,
        is_paused: false
      })
    })
  })

  // 5. Pause endpoint (assert it's NOT called — that would mean the button
  //    decided we were unpaused and tried to pause us, which is the bug).
  let pauseCallCount = 0
  await page.route('**/api/ingest/' + SID + '/pause', async (route) => {
    pauseCallCount++
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        status: 'paused',
        session_id: SID,
        is_paused: true
      })
    })
  })

  page.on('console', (msg) => {
    const text = msg.text()
    if (
      text.includes('[ingestion.sse]') ||
      text.includes('Failed') ||
      msg.type() === 'error'
    ) {
      console.log('[browser]', msg.type(), text)
    }
  })

  await page.goto('/')

  const panel = page.locator('.floating-panel')
  await expect(panel).toBeVisible({ timeout: 15_000 })

  // Push a PAUSED event through the fake EventSource so the SSE handler runs.
  await page.waitForFunction(() => (window as any).__sse?.__instances?.length > 0, { timeout: 10_000 })
  await page.evaluate(() => {
    const es = (window as any).__sse.__instances[0]
    es.__dispatch('progress', {
      phase: 'paused',
      message: '⏸️ 일시 정지됨 (채팅으로 일부를 수정한 후 재개하세요)',
      progress: 45,
      data: { isPaused: true },
      tokens: { total: 100, approximate: false },
      suspendState: 'running'
    })
  })

  const label = panel.locator('.floating-panel__label')
  await expect(label).toContainText('일시 정지됨', { timeout: 5_000 })

  const pauseBtn = panel.locator('.panel-btn--pause')
  await expect(pauseBtn).toBeVisible()

  const titleAttr = await pauseBtn.getAttribute('title')
  console.log('[test] button title before click =', titleAttr)
  expect(titleAttr).toBe('재개')

  const pauseRectCount = await pauseBtn.locator('svg rect').count()
  const playPolygonCount = await pauseBtn.locator('svg polygon').count()
  console.log('[test] icon: rects=', pauseRectCount, 'polygons=', playPolygonCount)
  expect(playPolygonCount).toBe(1)
  expect(pauseRectCount).toBe(0)

  console.log('[test] clicking resume...')
  await pauseBtn.click()

  await expect.poll(() => resumeCallCount, { timeout: 5_000 }).toBe(1)
  console.log('[test] /resume called', resumeCallCount, 'time(s); /pause called', pauseCallCount, 'time(s)')
  expect(pauseCallCount).toBe(0)

  // Optimistic UI: label flips out of paused.
  await expect(label).not.toContainText('일시 정지됨', { timeout: 3_000 })

  // Push the next non-paused SSE event so the UI fully resumes.
  await page.evaluate(() => {
    const es = (window as any).__sse.__instances[0]
    es.__dispatch('progress', {
      phase: 'extracting_aggregates',
      message: 'Aggregate 생성: Test (1/1)',
      progress: 46,
      data: {},
      tokens: { total: 110, approximate: false },
      suspendState: 'running'
    })
  })

  await expect.poll(async () => await pauseBtn.locator('svg rect').count(), { timeout: 3_000 }).toBe(2)
  const titleAfter = await pauseBtn.getAttribute('title')
  console.log('[test] button title after click =', titleAfter)
  expect(titleAfter).toBe('일시정지')
})
