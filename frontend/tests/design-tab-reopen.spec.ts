import { test, expect } from '@playwright/test'

/**
 * E2E: Open Design tab on UI node A, then open Design tab on UI node B.
 * The second open must not crash with CanvasKit "deleted object" errors.
 */
test.describe('Design tab re-open', () => {
  test.setTimeout(180_000)

  test('open Design tab on two different UI nodes sequentially', async ({ page }) => {
    const ckErrors: string[] = []
    page.on('pageerror', err => {
      ckErrors.push(err.message)
      console.log(`[pageerror] ${err.message.slice(0, 200)}`)
    })
    page.on('console', msg => {
      if (msg.type() === 'error' || msg.type() === 'warning') {
        const t = msg.text()
        if (!t.includes('404') && !t.includes('Failed to load resource') && !t.includes('Vue Flow')) {
          if (msg.type() === 'error') ckErrors.push(t)
          console.log(`[console:${msg.type()}] ${t.slice(0, 200)}`)
        }
      }
    })

    // 1. Load app & expand tree
    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.locator('#app')).toBeVisible()
    const expandBtn = page.locator('.tree-action-btn[title="Expand All"]')
    if (await expandBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await expandBtn.click()
      await page.waitForTimeout(1000)
    }

    // 2. Find at least 2 UI nodes
    const uiHeaders = page.locator('.tree-node__icon--ui').locator('..')
    const uiCount = await uiHeaders.count()
    console.log(`[test] Found ${uiCount} UI nodes`)
    test.skip(uiCount < 2, 'Need at least 2 UI nodes')

    // Helper: open a UI node by index → inspector → Design tab
    async function openDesignTab(index: number): Promise<{ label: string; visible: boolean }> {
      const header = uiHeaders.nth(index)
      const label = (await header.locator('.tree-node__label').textContent()) || `UI-${index}`
      console.log(`[test] Opening UI[${index}]: "${label}"`)

      // Double-click in tree to add to canvas
      await header.dblclick()
      await page.waitForTimeout(2000)

      // Double-click on canvas node to open inspector
      const canvasNode = page.locator('.vue-flow__node').filter({ hasText: label }).first()
      if (await canvasNode.isVisible({ timeout: 5_000 }).catch(() => false)) {
        await canvasNode.dblclick()
      } else {
        // Fallback: click the last added node
        const allNodes = page.locator('.vue-flow__node')
        const count = await allNodes.count()
        await allNodes.nth(count - 1).dblclick()
      }
      await page.waitForTimeout(1000)

      // Wait for inspector
      await expect(page.getByText('Inspector', { exact: false }).first()).toBeVisible({ timeout: 10_000 })

      // Ensure sceneGraph exists (generate if empty)
      const previewTab = page.locator('.inspector-tab').filter({ hasText: 'UI Preview' }).first()
      if (await previewTab.isVisible({ timeout: 2_000 }).catch(() => false)) {
        await previewTab.click()
        await page.waitForTimeout(500)
      }
      const hasPreview = await page.locator('.frame-preview').isVisible({ timeout: 3_000 }).catch(() => false)
      if (!hasPreview) {
        const genBtn = page.locator('button[title*="component library"]').first()
        if (await genBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
          await genBtn.click()
          await page.locator('.frame-preview').waitFor({ state: 'visible', timeout: 90_000 })
          console.log(`[test] Generated sceneGraph for "${label}"`)
        }
      }

      // Click Design tab
      const designTab = page.locator('.inspector-tab').filter({ hasText: 'Design' })
      await designTab.click()
      console.log(`[test] Design tab clicked for "${label}"`)

      // Wait for either frame-editor to appear or fallback text
      const frameEditor = page.locator('.frame-editor')
      const loadingText = page.getByText('Loading design editor', { exact: false })
      const emptyText = page.getByText('AI로 디자인 생성', { exact: false })
      try {
        await Promise.race([
          frameEditor.waitFor({ state: 'visible', timeout: 15_000 }),
          loadingText.waitFor({ state: 'visible', timeout: 15_000 }),
          emptyText.waitFor({ state: 'visible', timeout: 15_000 }),
          page.waitForTimeout(15_000)
        ])
      } catch {}
      await page.waitForTimeout(2000)

      // Check if frame-editor rendered
      const visible = await page.locator('.frame-editor').isVisible({ timeout: 5_000 }).catch(() => false)

      // Debug DOM state
      const domDebug = await page.evaluate(() => {
        const de = document.querySelector('.inspector-design-editor')
        const content = document.querySelector('.inspector-design-editor__content')
        const empty = document.querySelector('.inspector-design-editor__empty')
        const fe = document.querySelector('.frame-editor')
        const loading = document.querySelector('.frame-editor__loading')
        const canvas = document.querySelector('.frame-editor canvas, [data-test-id="canvas-element"]')
        const converting = document.querySelector('.inspector-design-editor__generating')
        return {
          designEditor: de ? `${de.clientWidth}x${de.clientHeight}` : 'none',
          content: content ? `${content.clientWidth}x${content.clientHeight}` : 'none',
          empty: !!empty,
          frameEditor: fe ? `${fe.clientWidth}x${fe.clientHeight}` : 'none',
          loading: !!loading,
          canvas: canvas ? `${(canvas as HTMLElement).clientWidth}x${(canvas as HTMLElement).clientHeight}` : 'none',
          converting: !!converting,
          activeTab: document.querySelector('.inspector-tab.active')?.textContent || 'unknown'
        }
      })
      console.log(`[test] DOM for "${label}":`, JSON.stringify(domDebug))

      console.log(`[test] FrameEditor visible for "${label}": ${visible}`)
      return { label, visible }
    }

    // ===== Open first UI node =====
    ckErrors.length = 0
    const first = await openDesignTab(0)
    await page.screenshot({ path: 'test-results/design-reopen-node1.png' })
    const errorsAfterFirst = [...ckErrors]
    console.log(`[test] Errors after 1st node: ${errorsAfterFirst.length}`)

    // ===== Close inspector (click canvas background) =====
    await page.locator('.vue-flow__pane').click({ position: { x: 50, y: 50 } })
    await page.waitForTimeout(1500)
    console.log('[test] Inspector closed')

    // ===== Open second UI node =====
    ckErrors.length = 0
    const second = await openDesignTab(1)
    await page.screenshot({ path: 'test-results/design-reopen-node2.png' })
    const errorsAfterSecond = [...ckErrors]
    console.log(`[test] Errors after 2nd node: ${errorsAfterSecond.length}`)
    for (const e of errorsAfterSecond.slice(0, 5)) console.log(`[test]   ${e.slice(0, 120)}`)

    // ===== Assertions =====
    // Second node's Design tab must work
    expect(second.visible, `Design tab for "${second.label}" should be visible`).toBeTruthy()
    expect(errorsAfterSecond.filter(e => e.includes('deleted')),
      'No "deleted object" errors on 2nd node'
    ).toHaveLength(0)

    console.log('[test] PASSED')
  })
})
