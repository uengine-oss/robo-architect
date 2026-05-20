import { test, expect } from '@playwright/test'

/**
 * Diagnostic: Open Design tab on a UI node and capture all font-related
 * network failures + console output. The frontend's open-pencil FrameEditor
 * tries to fetch /Inter-Regular.ttf as a bundled-font fallback; if that 404s
 * AND Google Fonts is unreachable, text won't render.
 */
test('Design tab font loading diagnostic', async ({ page }) => {
  test.setTimeout(180_000)

  const failedRequests: { url: string; failure: string }[] = []
  const fontRequests: { url: string; status: number }[] = []
  const consoleMessages: { type: string; text: string }[] = []

  page.on('requestfailed', req => {
    const u = req.url()
    if (/font|ttf|otf|woff|googleapis/i.test(u)) {
      failedRequests.push({ url: u, failure: req.failure()?.errorText || 'unknown' })
    }
  })
  page.on('response', async resp => {
    const u = resp.url()
    if (/\.(ttf|otf|woff2?)(\?|$)|googleapis\.com\/webfonts|gstatic\.com/i.test(u)) {
      fontRequests.push({ url: u, status: resp.status() })
    }
  })
  page.on('console', msg => {
    const t = msg.text()
    if (/font|tofu|typeface|canvaskit/i.test(t) || msg.type() === 'error' || msg.type() === 'warning') {
      consoleMessages.push({ type: msg.type(), text: t.slice(0, 300) })
    }
  })
  page.on('pageerror', err => {
    consoleMessages.push({ type: 'pageerror', text: err.message.slice(0, 300) })
  })

  await page.goto('/', { waitUntil: 'networkidle' })
  await expect(page.locator('#app')).toBeVisible()

  const expandBtn = page.locator('.tree-action-btn[title="Expand All"]')
  if (await expandBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await expandBtn.click()
    await page.waitForTimeout(800)
  }

  const uiHeaders = page.locator('.tree-node__icon--ui').locator('..')
  const uiCount = await uiHeaders.count()
  console.log(`[diag] UI node count: ${uiCount}`)
  test.skip(uiCount === 0, 'Need at least 1 UI node')

  // Open first UI node → canvas → inspector
  await uiHeaders.first().dblclick()
  await page.waitForTimeout(2000)
  const allNodes = page.locator('.vue-flow__node')
  const count = await allNodes.count()
  if (count > 0) await allNodes.nth(count - 1).dblclick()
  await page.waitForTimeout(800)

  await expect(page.getByText('Inspector', { exact: false }).first()).toBeVisible({ timeout: 10_000 })

  const previewTab = page.locator('.inspector-tab').filter({ hasText: 'UI Preview' }).first()
  if (await previewTab.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await previewTab.click()
    await page.waitForTimeout(500)
  }

  const designTab = page.locator('.inspector-tab').filter({ hasText: 'Design' })
  if (await designTab.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await designTab.click()
    console.log('[diag] Design tab clicked')
  }

  // Wait for editor to render
  await page.waitForTimeout(8000)

  // Probe direct fetches against the dev server for the two bundled fonts
  const probe = await page.evaluate(async () => {
    const probeOne = async (url: string) => {
      try {
        const r = await fetch(url)
        return { url, status: r.status, ok: r.ok, bytes: r.ok ? (await r.arrayBuffer()).byteLength : 0 }
      } catch (e: any) {
        return { url, status: -1, ok: false, error: String(e?.message ?? e) }
      }
    }
    return Promise.all([
      probeOne('/Inter-Regular.ttf'),
      probeOne('/NotoNaskhArabic-Regular.ttf'),
      probeOne('/canvaskit.wasm')
    ])
  })

  // Probe Google Fonts API connectivity from the page (uses the open-pencil-bundled API key)
  const googleProbe = await page.evaluate(async () => {
    try {
      const r = await fetch('https://www.googleapis.com/webfonts/v1/webfonts?family=Inter&key=AIzaSyD1tYDR_dUEiV-Tw1vksEhZbUytgKW5pc8')
      return { status: r.status, ok: r.ok, body: r.ok ? (await r.text()).slice(0, 200) : null }
    } catch (e: any) {
      return { status: -1, error: String(e?.message ?? e) }
    }
  })

  console.log('[diag] Bundled font probes:', JSON.stringify(probe, null, 2))
  console.log('[diag] Google Fonts probe:', JSON.stringify(googleProbe))
  console.log('[diag] Font network requests:', JSON.stringify(fontRequests, null, 2))
  console.log('[diag] Failed font requests:', JSON.stringify(failedRequests, null, 2))
  console.log(`[diag] Console messages count: ${consoleMessages.length}`)
  for (const m of consoleMessages.slice(0, 30)) console.log(`  [${m.type}] ${m.text}`)

  await page.screenshot({ path: 'test-results/font-diag.png', fullPage: false })
})
