import { test, expect } from '@playwright/test'

/**
 * Diagnostic: drive the full ingestion flow with the built-in food-delivery
 * sample in Figma UI mode, then inspect the resulting Neo4j state to find out
 * which UI nodes ended up without a sceneGraph (the "일부만 생성됨" symptom).
 *
 * We don't have a cypher REST endpoint, so:
 *  - count the SSE `progress` events whose data.type === 'UI' (claimed creates)
 *  - call /api/graph/stats for the final UI count
 *  - read each UI from the canvas tree and check whether its sceneGraph field
 *    looks populated (non-empty, has nodes)
 */
test('Figma UI mode bulk generation — find missing wireframes', async ({ page }) => {
  test.setTimeout(20 * 60_000) // ingestion of the full sample takes minutes

  const sseUiEvents: { name: string; displayName: string; sceneGraphLen: number }[] = []
  const sseAllPhases: string[] = []
  const consoleErrors: string[] = []

  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 300))
  })

  // Capture SSE network frames so we can count UI 'progress' events even though
  // EventSource events are not exposed via the page object directly.
  const sseFrames: string[] = []
  page.on('response', async resp => {
    const ct = resp.headers()['content-type'] || ''
    if (!resp.url().includes('/api/ingest/stream/')) return
    if (!ct.includes('text/event-stream')) return
    // We can't read the body of an SSE response (it never finishes). Skip.
  })

  await page.goto('/', { waitUntil: 'networkidle' })
  await expect(page.locator('#app')).toBeVisible()

  // Hook the page's EventSource to relay SSE events into the test via window
  await page.addInitScript(() => {
    const originalES = window.EventSource
    ;(window as any).__sseEvents = []
    window.EventSource = class extends originalES {
      constructor(url: string | URL, init?: EventSourceInit) {
        super(url, init)
        this.addEventListener('progress', (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data)
            ;(window as any).__sseEvents.push({ kind: 'progress', data })
          } catch {}
        })
        this.addEventListener('done', (e: MessageEvent) => {
          try {
            const data = JSON.parse((e as any).data || '{}')
            ;(window as any).__sseEvents.push({ kind: 'done', data })
          } catch { (window as any).__sseEvents.push({ kind: 'done' }) }
        })
        this.addEventListener('error', (e: any) => {
          ;(window as any).__sseEvents.push({ kind: 'error', readyState: this.readyState })
        })
      }
    } as any
  })

  // Reload so the addInitScript hook is in place before main.js runs
  await page.reload({ waitUntil: 'networkidle' })

  // Open ingestion modal
  const uploadBtn = page.locator('button.upload-btn').first()
  await uploadBtn.waitFor({ state: 'visible', timeout: 15_000 })
  await uploadBtn.click()
  console.log('[diag] Modal opened')

  // Make sure we're on text-input mode then click "샘플 요구사항 사용"
  const textTab = page.locator('.tab-btn').filter({ hasText: '텍스트 입력' }).first()
  if (await textTab.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await textTab.click()
  }
  const sampleBtn = page.locator('button.sample-btn').filter({ hasText: '샘플 요구사항' }).first()
  await sampleBtn.click()
  console.log('[diag] Sample requirements loaded')

  // Switch UI generation mode to Figma UI
  const figmaUiBtn = page.locator('.tab-btn--small').filter({ hasText: 'Figma UI' }).first()
  await figmaUiBtn.click()
  console.log('[diag] UI generation mode = Figma UI')

  // Click 분석 시작
  const startBtn = page.locator('button').filter({ hasText: '분석 시작' }).first()
  await startBtn.click()

  // If existing data → confirm clear
  const clearBtn = page.locator('button').filter({ hasText: '삭제하고 계속' }).first()
  if (await clearBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
    console.log('[diag] Existing data found → clearing')
    await clearBtn.click()
  } else {
    console.log('[diag] No existing data clear dialog (already empty)')
  }

  // Wait for SSE 'done' event with a progress poll
  const startedAt = Date.now()
  const TIMEOUT_MS = 18 * 60_000
  let lastReport = 0
  let lastPhase = ''
  let lastProgress = -1
  let done = false

  let completeSeenAt = 0
  while (Date.now() - startedAt < TIMEOUT_MS) {
    const snapshot = await page.evaluate(() => (window as any).__sseEvents?.slice() ?? [])
    if (snapshot.length > 0) {
      // copy and clear so we don't double-count
      await page.evaluate(() => { (window as any).__sseEvents.length = 0 })
      for (const ev of snapshot) {
        if (ev.kind === 'done') { done = true; continue }
        if (ev.kind !== 'progress') continue
        const d = ev.data || {}
        if (d.phase) lastPhase = d.phase
        if (typeof d.progress === 'number') lastProgress = d.progress
        sseAllPhases.push(d.phase || '?')
        if (d.data?.type === 'UI' && d.data?.object) {
          const obj = d.data.object
          const sg = obj.sceneGraph
          sseUiEvents.push({
            name: obj.name || '?',
            displayName: obj.displayName || obj.name || '?',
            sceneGraphLen: typeof sg === 'string' ? sg.length : (sg ? JSON.stringify(sg).length : 0)
          })
        }
      }
    }
    if (done) break
    // The backend only emits `progress` events (no explicit `done`). Treat
    // phase=complete + progress=100 as terminal; give it 6s of grace for any
    // trailing UI events to drain.
    if (lastPhase === 'complete' && lastProgress === 100) {
      if (!completeSeenAt) completeSeenAt = Date.now()
      else if (Date.now() - completeSeenAt > 6000) { done = true; break }
    } else {
      completeSeenAt = 0
    }
    if (Date.now() - lastReport > 15_000) {
      lastReport = Date.now()
      console.log(`[diag] phase=${lastPhase} progress=${lastProgress} UIs(SSE)=${sseUiEvents.length}`)
    }
    await page.waitForTimeout(1500)
  }

  console.log(`[diag] SSE finished. done=${done} totalUiEvents=${sseUiEvents.length}`)
  console.log(`[diag] phases observed (unique): ${[...new Set(sseAllPhases)].join(', ')}`)

  // Now query the backend graph stats and per-UI sceneGraph state.
  const stats = await page.evaluate(async () => {
    const r = await fetch('/api/graph/stats')
    return r.ok ? r.json() : { error: r.status }
  })
  console.log(`[diag] /api/graph/stats: ${JSON.stringify(stats)}`)

  // Group SSE UI events: how many have empty sceneGraph?
  const empty = sseUiEvents.filter(u => u.sceneGraphLen < 50)
  const populated = sseUiEvents.filter(u => u.sceneGraphLen >= 50)
  console.log(`[diag] SSE UI events: total=${sseUiEvents.length} populated=${populated.length} empty=${empty.length}`)
  console.log(`[diag] Empty UIs (first 30):`)
  for (const u of empty.slice(0, 30)) console.log(`  - ${u.displayName} (sgLen=${u.sceneGraphLen})`)

  console.log(`[diag] Populated UIs (first 5):`)
  for (const u of populated.slice(0, 5)) console.log(`  - ${u.displayName} (sgLen=${u.sceneGraphLen})`)

  await page.screenshot({ path: 'test-results/figma-ui-bulk-final.png', fullPage: false })

  // We don't fail on count — this is a diagnostic. But we DO fail if zero UIs
  // came out, which would indicate a different (catastrophic) bug.
  expect(sseUiEvents.length).toBeGreaterThan(0)
})
