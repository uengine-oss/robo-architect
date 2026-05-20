import { test, expect } from '@playwright/test'

/**
 * Debug test: check Design tab canvas height and fix iteratively.
 */
test('Design tab canvas fills available height', async ({ page }) => {
  test.setTimeout(60_000)

  // Set AI keys
  await page.goto('/')
  await page.evaluate(() => {
    localStorage.setItem('open-pencil:ai-provider', 'openai')
    localStorage.setItem('open-pencil:ai-key:openai', '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')
    localStorage.setItem('open-pencil:ai-model', 'gpt-5.3-codex')
  })
  await page.reload({ waitUntil: 'networkidle' })
  await page.setViewportSize({ width: 1920, height: 1080 })

  // Expand tree, find UI node
  const expandAll = page.locator('.tree-action-btn[title="Expand All"]')
  if (await expandAll.isVisible({ timeout: 5000 }).catch(() => false)) {
    await expandAll.click()
    await page.waitForTimeout(1000)
  }

  // Double-click a UI node to add to canvas
  const uiIcon = page.locator('.tree-node__icon--ui').first()
  const uiHeader = uiIcon.locator('..')
  await uiHeader.dblclick()
  await page.waitForTimeout(2000)

  // Double-click on canvas to open inspector
  const canvasNode = page.locator('.vue-flow__node').last()
  await canvasNode.dblclick()
  await page.waitForTimeout(1000)

  // Click Design tab
  const designTab = page.locator('.inspector-tab').filter({ hasText: 'Design' })
  await expect(designTab).toBeVisible({ timeout: 5000 })
  await designTab.click()
  await page.waitForTimeout(3000)

  // Measure heights
  const heights = await page.evaluate(() => {
    const inspector = document.querySelector('.inspector-panel-body, .inspector-body')
    const designEditor = document.querySelector('.inspector-design-editor')
    const content = document.querySelector('.inspector-design-editor__content')
    const frameEditor = document.querySelector('.frame-editor')
    const canvas = document.querySelector('.frame-editor__canvas')
    const canvasEl = document.querySelector('.frame-editor__canvas canvas, [data-test-id="canvas-element"]')
    const body = document.querySelector('.frame-editor__body')

    return {
      viewport: window.innerHeight,
      inspector: inspector?.getBoundingClientRect()?.height ?? 'N/A',
      designEditor: designEditor?.getBoundingClientRect()?.height ?? 'N/A',
      content: content?.getBoundingClientRect()?.height ?? 'N/A',
      frameEditor: frameEditor?.getBoundingClientRect()?.height ?? 'N/A',
      frameBody: body?.getBoundingClientRect()?.height ?? 'N/A',
      canvasDiv: canvas?.getBoundingClientRect()?.height ?? 'N/A',
      canvasEl: canvasEl?.getBoundingClientRect()?.height ?? 'N/A',
      // Check computed styles
      designEditorStyle: designEditor ? getComputedStyle(designEditor).height : 'N/A',
      contentStyle: content ? getComputedStyle(content).height : 'N/A',
      frameEditorStyle: frameEditor ? getComputedStyle(frameEditor).height : 'N/A',
    }
  })
  console.log('[test] Heights:', JSON.stringify(heights, null, 2))

  // Wait longer for zoomToFit ResizeObserver
  await page.waitForTimeout(4000)

  // Screenshot just the inspector panel area
  const inspectorEl = page.locator('.inspector-design-editor').first()
  if (await inspectorEl.isVisible().catch(() => false)) {
    await inspectorEl.screenshot({ path: 'test-results/design-inspector.png' })
  }
  await page.screenshot({ path: 'test-results/design-height.png' })

  // Also check the full parent chain with overflow
  const parentChain = await page.evaluate(() => {
    const el = document.querySelector('.frame-editor__canvas')
    if (!el) return 'frame-editor__canvas not found'
    const chain: string[] = []
    let cur: HTMLElement | null = el as HTMLElement
    for (let i = 0; i < 10 && cur; i++) {
      const r = cur.getBoundingClientRect()
      const s = getComputedStyle(cur)
      chain.push(`${cur.className.toString().slice(0,40)} | ${Math.round(r.height)}px | overflow:${s.overflow} | position:${s.position} | display:${s.display} | flex:${s.flex}`)
      cur = cur.parentElement
    }
    return chain
  })
  console.log('[test] Parent chain:')
  if (Array.isArray(parentChain)) {
    parentChain.forEach((line, i) => console.log(`  [${i}] ${line}`))
  } else {
    console.log(parentChain)
  }

  console.log(`[test] Canvas div height: ${typeof heights.canvasDiv === 'number' ? heights.canvasDiv : 'N/A'}px`)
  console.log(`[test] Canvas element height: ${typeof heights.canvasEl === 'number' ? heights.canvasEl : 'N/A'}px`)
})
