import { test, expect } from '@playwright/test'

/**
 * Headed-mode diagnostic: drive a real UI sticker through the
 * "Figma 스타일 와이어프레임으로 변환" (open-pencil AI) flow and capture
 * everything needed to diagnose the "AI가 디자인을 생성하지 못했습니다" failure:
 *  - all /api/ai-design/* network calls + their full response bodies (SSE)
 *  - all console messages and page errors
 *  - the final on-screen state and a screenshot
 *
 * Run with:
 *   npx playwright test ai-design-headed-diag --headed --reporter=list
 */

test.describe('AI Design — headed diagnostic', () => {
  test('one UI sticker → Figma 변환 → capture failure', async ({ page }) => {
    test.setTimeout(300_000)

    // ── Collectors ────────────────────────────────────────────────────
    const consoleAll: { type: string; text: string }[] = []
    const pageErrors: string[] = []
    const aiCalls: {
      url: string
      method: string
      status?: number
      failed?: string
      body?: string
    }[] = []
    const otherApiCalls: { url: string; status?: number; method: string }[] = []

    page.on('console', (msg) => {
      consoleAll.push({ type: msg.type(), text: msg.text() })
    })
    page.on('pageerror', (err) => pageErrors.push(err.message))

    page.on('request', (req) => {
      const url = req.url()
      if (url.includes('/api/ai-design/')) {
        aiCalls.push({ url, method: req.method() })
      } else if (url.includes('/api/')) {
        otherApiCalls.push({ url, method: req.method() })
      }
    })
    page.on('requestfailed', (req) => {
      const url = req.url()
      if (url.includes('/api/ai-design/')) {
        const idx = aiCalls.findIndex((c) => c.url === url && c.status === undefined)
        const fail = req.failure()?.errorText
        if (idx >= 0) aiCalls[idx].failed = fail
        else aiCalls.push({ url, method: req.method(), failed: fail })
      }
    })
    page.on('response', async (resp) => {
      const url = resp.url()
      if (url.includes('/api/ai-design/')) {
        const idx = aiCalls.findIndex((c) => c.url === url && c.status === undefined)
        if (idx >= 0) {
          aiCalls[idx].status = resp.status()
          // Capture the SSE body so we can see what the proxy actually streamed.
          try {
            aiCalls[idx].body = (await resp.text()).slice(0, 4000)
          } catch (e: any) {
            aiCalls[idx].body = `<<read failed: ${e?.message || e}>>`
          }
        }
      } else if (url.includes('/api/')) {
        const idx = otherApiCalls.findIndex(
          (c) => c.url === url && c.status === undefined
        )
        if (idx >= 0) otherApiCalls[idx].status = resp.status()
      }
    })

    // ── Drive the UI ──────────────────────────────────────────────────
    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.locator('#app')).toBeVisible()

    await page.waitForFunction(
      () => localStorage.getItem('open-pencil:ai-provider') === 'openai-compatible',
      undefined,
      { timeout: 10_000 }
    )
    console.log('[test] bootstrap complete; localStorage wired to backend')

    // Expand the navigator tree so UI nodes are reachable.
    const navigator = page.locator('aside.left-panel')
    await expect(navigator).toBeVisible({ timeout: 10_000 })

    const expandAllBtn = page.locator('.tree-action-btn[title="Expand All"]')
    if (await expandAllBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await expandAllBtn.click()
      await page.waitForTimeout(800)
    }

    // Pick the first UI node we can find in the tree.
    const uiHeaders = page.locator('.tree-node__icon--ui')
    const uiCount = await uiHeaders.count()
    console.log(`[test] Found ${uiCount} UI nodes`)
    if (uiCount === 0) {
      test.skip(true, 'No UI nodes available in navigator')
      return
    }

    // Try each UI node in order until we find one with a convert button.
    // (Nodes that already have a sceneGraph hide the button.)
    let pickedLabel: string | null = null
    let convertBtnFound = false
    for (let i = 0; i < uiCount; i++) {
      const candidate = uiHeaders.nth(i).locator('..')
      const label = (await candidate.locator('.tree-node__label').textContent())?.trim()
      if (!label) continue

      console.log(`[test] trying UI #${i}: "${label}"`)
      await candidate.dblclick()
      await page.waitForTimeout(1200)

      const canvasMatch = page.locator('.vue-flow__node').filter({ hasText: label }).first()
      if (await canvasMatch.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await canvasMatch.dblclick()
      } else {
        await page.locator('.vue-flow__node').first().dblclick()
      }
      await page.waitForTimeout(1200)

      const uiPreviewTab = page.locator('button, div').filter({ hasText: /^UI Preview$/ }).first()
      if (await uiPreviewTab.isVisible({ timeout: 1_500 }).catch(() => false)) {
        await uiPreviewTab.click()
        await page.waitForTimeout(400)
      }

      const btn = page.locator('.ui-preview-frame__convert-btn').first()
      if (await btn.isVisible({ timeout: 2_500 }).catch(() => false)) {
        pickedLabel = label
        convertBtnFound = true
        break
      }
      console.log(`[test]   "${label}" already has a design — skip`)
    }

    if (!convertBtnFound || !pickedLabel) {
      console.log('[test] all UI nodes already have designs — nothing to convert')
      await page.screenshot({ path: 'test-results/ai-headed-all-converted.png' })
      test.skip(true, 'No UI node without an existing design')
      return
    }

    console.log(`[test] Picked UI: "${pickedLabel}"`)
    await page.screenshot({ path: 'test-results/ai-headed-before.png' })

    const convertBtn = page.locator('.ui-preview-frame__convert-btn').first()
    await convertBtn.click()
    console.log('[test] clicked convert')

    // Wait for the AI flow to surface an outcome — either the conversion
    // panel shows up, or the failed banner appears, or the design renders.
    // We give it up to 90 seconds and then dump everything.
    const generatingPanel = page.locator('.ui-preview-convert-panel, .inspector-design-ai-layout, .inspector-design-editor__generating').first()
    const failedBanner = page.locator('.ui-preview-frame__convert-bar--failed').first()

    const outcome = await Promise.race([
      generatingPanel.waitFor({ state: 'visible', timeout: 10_000 }).then(() => 'generating' as const).catch(() => null),
      failedBanner.waitFor({ state: 'visible', timeout: 10_000 }).then(() => 'failed-immediately' as const).catch(() => null),
    ])
    console.log('[test] initial outcome:', outcome)

    // Wait up to 180s for a definitive outcome:
    //   - failure banner appears, OR
    //   - generation panel disappears (success path), OR
    //   - 180s timeout (AI still grinding)
    await Promise.race([
      failedBanner.waitFor({ state: 'visible', timeout: 180_000 }).catch(() => null),
      generatingPanel.waitFor({ state: 'hidden', timeout: 180_000 }).catch(() => null),
      page.waitForTimeout(180_000),
    ])

    await page.screenshot({ path: 'test-results/ai-headed-after.png', fullPage: true })

    // Verify the saved sceneGraph by reading the UI node from the API.
    // This is the *authoritative* success signal: backend has it persisted.
    const apiSceneGraph = await page.evaluate(async (label) => {
      // Find the UI node whose displayName matches the picked label
      const r = await fetch('/api/contexts')
      if (!r.ok) return { found: false, reason: `contexts ${r.status}` }
      const ctxs = await r.json()
      for (const ctx of ctxs?.items || ctxs || []) {
        const cid = ctx.id || ctx.cid
        if (!cid) continue
        const tr = await fetch(`/api/contexts/${cid}/full-tree`)
        if (!tr.ok) continue
        const tree = await tr.json()
        const stack = [tree]
        while (stack.length) {
          const n = stack.shift()
          if (!n) continue
          if (n.label === 'UI' && (n.displayName === label || n.name === label)) {
            const r2 = await fetch(`/api/graph/expand-with-bc/${n.id}`)
            if (!r2.ok) return { found: true, sceneGraphSet: false, reason: `expand ${r2.status}` }
            const data = await r2.json()
            const ui = data.nodes?.find((x: any) => x.id === n.id)
            const sg = ui?.sceneGraph
            const hasSG = typeof sg === 'string' && sg.length > 10
            let nodeCount = 0
            if (hasSG) {
              try { nodeCount = Object.keys(JSON.parse(sg).nodes || {}).length } catch {}
            }
            return { found: true, sceneGraphSet: hasSG, nodeCount, sgLen: sg?.length || 0 }
          }
          if (n.children) stack.push(...n.children)
        }
      }
      return { found: false, reason: 'label not in any context tree' }
    }, pickedLabel)

    const finalState = await page.evaluate(() => ({
      convertFailed: !!document.querySelector('.ui-preview-frame__convert-bar--failed'),
      generating: !!document.querySelector('.ui-preview-convert-panel'),
      hasDesignTab: !!document.querySelector('.inspector-tab'),
      hasFrameEditor: !!document.querySelector('.frame-editor'),
      hasFrameEditorCanvas: !!document.querySelector('.frame-editor canvas, [data-test-id="canvas-element"]'),
      visibleErrorText:
        document.querySelector('.ui-preview-frame__convert-bar--failed span')?.textContent?.trim() || null,
    }))
    console.log('[test] persisted sceneGraph:', JSON.stringify(apiSceneGraph))

    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    console.log('[test] FINAL STATE:', JSON.stringify(finalState, null, 2))
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')

    console.log(`[test] /api/ai-design/* calls: ${aiCalls.length}`)
    for (const c of aiCalls) {
      console.log(`  ${c.method} ${c.url} → ${c.status ?? c.failed ?? 'pending'}`)
      if (c.body) {
        console.log(`    body[first 4000]:\n${c.body.split('\n').map((l) => '      ' + l).join('\n')}`)
      }
    }

    console.log(`[test] other /api/* calls: ${otherApiCalls.length}`)
    for (const c of otherApiCalls.slice(0, 10)) {
      console.log(`  ${c.method} ${c.url} → ${c.status ?? 'pending'}`)
    }

    const errLogs = consoleAll.filter((m) => m.type === 'error')
    const aiLogs = consoleAll.filter(
      (m) => m.text.includes('[AIChat]') || m.text.includes('[InspectorPanel]') || m.text.includes('[ai-design]')
    )
    console.log(`[test] console errors: ${errLogs.length}`)
    for (const m of errLogs.slice(0, 20)) console.log(`  [${m.type}] ${m.text.slice(0, 300)}`)
    console.log(`[test] AI/inspector console messages: ${aiLogs.length}`)
    for (const m of aiLogs.slice(0, 30)) console.log(`  [${m.type}] ${m.text.slice(0, 400)}`)

    console.log(`[test] page errors: ${pageErrors.length}`)
    for (const m of pageErrors.slice(0, 10)) console.log(`  ${m.slice(0, 400)}`)

    // Outcome ranking (most to least confident):
    //   1. apiSceneGraph.sceneGraphSet === true → backend has the design saved → SUCCESS
    //   2. finalState.convertFailed === true → on-screen failure banner → FAILED
    //   3. finalState.hasFrameEditor === true → editor mounted → SUCCESS (Design tab)
    //   4. neither → still generating or partial — INDETERMINATE
    if (apiSceneGraph?.sceneGraphSet) {
      console.log(
        `[test] OUTCOME: ✅ SUCCESS — sceneGraph persisted with ${apiSceneGraph.nodeCount} nodes (${apiSceneGraph.sgLen} bytes)`
      )
    } else if (finalState.convertFailed) {
      console.log('[test] OUTCOME: ❌ AI conversion FAILED — see logs for cause')
    } else if (finalState.hasFrameEditor) {
      console.log('[test] OUTCOME: ✅ SUCCESS — frame editor mounted (Design tab)')
    } else {
      console.log('[test] OUTCOME: ⚠️ indeterminate — generation may still be in progress')
    }
  })
})
