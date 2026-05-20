import { test, expect } from '@playwright/test'

/**
 * E2E test: Generate wireframe from .fig component library.
 *
 * Prerequisites:
 * - Backend API running
 * - Wireframe service: COMPONENT_LIBRARY_PATH=./input/common_only.fig bun run open-pencil/packages/cli/src/wireframe-service.ts
 * - Frontend dev server on localhost:5173
 */

test.describe('Component-based Wireframe Generation', () => {
  test.setTimeout(120_000)

  test('generate wireframe via component button and verify sceneGraph', async ({ page }) => {
    const errors: string[] = []
    page.on('console', msg => {
      if (msg.type() === 'error' && !msg.text().includes('404') && !msg.text().includes('Failed to load resource')) {
        errors.push(msg.text())
      }
    })

    // 1. Load & expand tree
    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.locator('#app')).toBeVisible()
    const expandBtn = page.locator('.tree-action-btn[title="Expand All"]')
    if (await expandBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await expandBtn.click()
      await page.waitForTimeout(1000)
    }

    // 2. Find UI nodes
    const uiIcons = page.locator('.tree-node__icon--ui')
    const uiCount = await uiIcons.count()
    console.log(`[test] Found ${uiCount} UI nodes`)
    test.skip(uiCount === 0, 'No UI nodes')

    // 3. Pick first UI, open inspector
    const firstHeader = uiIcons.first().locator('..')
    const uiLabel = await firstHeader.locator('.tree-node__label').textContent()
    console.log(`[test] UI: "${uiLabel}"`)
    await firstHeader.dblclick()
    await page.waitForTimeout(2000)

    const canvasNode = page.locator('.vue-flow__node').filter({ hasText: uiLabel! }).first()
    if (await canvasNode.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await canvasNode.dblclick()
    } else {
      await page.locator('.vue-flow__node').first().dblclick()
    }
    await page.waitForTimeout(1000)
    await expect(page.getByText('Inspector', { exact: false }).first()).toBeVisible({ timeout: 10_000 })

    // 4. Go to UI Preview tab
    const previewTab = page.locator('button, div').filter({ hasText: /^UI Preview$/ }).first()
    if (await previewTab.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await previewTab.click()
      await page.waitForTimeout(500)
    }

    // 5. Click component generate button (grid icon)
    const componentBtn = page.locator('button[title*="component library"], button[title*="Generating"]').first()
    if (await componentBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await componentBtn.click()
      console.log('[test] Clicked component button')
    } else {
      // Empty state: select mode + generate
      const modeSelect = page.locator('.ui-preview-empty__mode-select').first()
      if (await modeSelect.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await modeSelect.selectOption('component')
        await page.locator('.ui-preview-empty__btn').first().click()
        console.log('[test] Generated from empty state')
      } else {
        test.skip(true, 'No component button found')
        return
      }
    }

    // 6. Wait for result
    console.log('[test] Waiting for generation...')
    const errorAlert = page.locator('.inspector-alert.error')
    const framePreview = page.locator('.frame-preview, .ui-preview-frame canvas')

    let result = 'timeout'
    try {
      await Promise.race([
        errorAlert.first().waitFor({ state: 'visible', timeout: 90_000 }).then(() => { result = 'error' }),
        framePreview.first().waitFor({ state: 'visible', timeout: 90_000 }).then(() => { result = 'success' }),
      ])
    } catch { /* timeout */ }

    console.log(`[test] Result: ${result}`)
    await page.screenshot({ path: 'test-results/component-wireframe-result.png', fullPage: false })

    if (result === 'error') {
      const errorText = await errorAlert.first().textContent()
      console.log(`[test] ERROR: ${errorText}`)
      // These specific errors should not occur after our fixes
      expect(errorText).not.toContain('not valid JSON')
      expect(errorText).not.toContain("'tuple' object")
      expect(errorText).not.toContain("no attribute 'invoke'")
    }

    // 7. Verify sceneGraph was saved
    if (result === 'success') {
      const nodeId = await page.evaluate(() => {
        const nodes = document.querySelectorAll('.vue-flow__node')
        return nodes[nodes.length - 1]?.getAttribute('data-id')
      })
      if (nodeId) {
        const apiResp = await page.request.get(`/api/graph/expand-with-bc/${nodeId}`)
        if (apiResp.ok()) {
          const data = await apiResp.json()
          const uiNode = data.nodes?.find((n: any) => n.id === nodeId)
          const sg = uiNode?.sceneGraph
          if (sg) {
            const parsed = typeof sg === 'string' ? JSON.parse(sg) : sg
            const nodeCount = Object.keys(parsed.nodes || {}).length
            console.log(`[test] SceneGraph: ${nodeCount} nodes`)
            expect(nodeCount).toBeGreaterThan(2)
          }
        }
      }
    }

    expect(result).toBe('success')
    console.log('[test] PASSED')
  })
})
