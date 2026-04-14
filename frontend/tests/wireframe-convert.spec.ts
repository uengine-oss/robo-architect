import { test, expect } from '@playwright/test'

/**
 * E2E test: Convert HTML wireframe to Figma-style design via OpenPencil AI.
 * Uses OpenAI GPT-5.3 Codex directly.
 */

const AI_CONFIG = {
  'open-pencil:ai-provider': 'openai',
  'open-pencil:ai-key:openai': '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',
  'open-pencil:ai-model': 'gpt-5.3-codex'
}

test.describe('Wireframe Conversion with OpenPencil AI', () => {
  test.setTimeout(120_000)

  test('convert HTML wireframe to Figma-style design', async ({ page }) => {
    // 1. Set AI config in localStorage
    await page.goto('/')
    for (const [key, value] of Object.entries(AI_CONFIG)) {
      await page.evaluate(([k, v]) => localStorage.setItem(k, v), [key, value])
    }

    // Collect errors
    const pageErrors: string[] = []
    page.on('pageerror', err => pageErrors.push(err.message))
    page.on('console', msg => {
      const text = msg.text()
      if (msg.type() === 'error') {
        if (!text.includes('404') && !text.includes('Failed to load resource')) {
          console.log(`[browser:error] ${text}`)
        }
      }
      // Capture AIChat debug logs
      if (text.includes('[AIChat]') || text.includes('[InspectorPanel]')) {
        console.log(`[browser] ${text}`)
      }
    })

    // 2. Reload with config
    await page.reload({ waitUntil: 'networkidle' })
    await expect(page.locator('#app')).toBeVisible()
    console.log('[test] App loaded')

    // 3. Wait for navigator (left-panel)
    const navigator = page.locator('aside.left-panel')
    await expect(navigator).toBeVisible({ timeout: 10_000 })
    console.log('[test] Navigator visible')

    // 4. Click "Expand All" to reveal all tree nodes
    const expandAllBtn = page.locator('.tree-action-btn[title="Expand All"]')
    if (await expandAllBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await expandAllBtn.click()
      await page.waitForTimeout(1000)
      console.log('[test] Expanded all tree nodes')
    }

    // 5. Find a UI node in the tree
    // UI nodes have icon class tree-node__icon--ui
    const uiNodeHeaders = page.locator('.tree-node__icon--ui')
    const uiCount = await uiNodeHeaders.count()
    console.log(`[test] Found ${uiCount} UI nodes`)

    if (uiCount === 0) {
      test.skip(true, 'No UI nodes found in navigator tree')
      return
    }

    // Pick the first UI node — click its header to select, then double-click to add to canvas
    const firstUIIcon = uiNodeHeaders.first()
    const firstUIHeader = firstUIIcon.locator('..') // parent = tree-node__header
    const uiLabel = await firstUIHeader.locator('.tree-node__label').textContent()
    console.log(`[test] Selected UI node: "${uiLabel}"`)

    await firstUIHeader.dblclick()
    console.log('[test] Double-clicked UI node in navigator — adding to canvas')
    await page.waitForTimeout(2000)

    // 6. Now double-click the node ON THE CANVAS to open InspectorPanel
    // VueFlow nodes have [data-id="nodeId"] attribute
    // Find the UI node on the canvas (vue-flow__node class)
    const canvasNode = page.locator('.vue-flow__node').filter({ hasText: uiLabel! }).first()
    const canvasNodeExists = await canvasNode.isVisible({ timeout: 5_000 }).catch(() => false)
    console.log(`[test] Canvas node visible: ${canvasNodeExists}`)

    if (!canvasNodeExists) {
      // Fallback: try any vue-flow__node
      const anyNode = page.locator('.vue-flow__node').first()
      await anyNode.dblclick()
    } else {
      await canvasNode.dblclick()
    }
    console.log('[test] Double-clicked canvas node')
    await page.waitForTimeout(1000)

    // Wait for InspectorPanel — look for the Inspector header text
    const inspectorPanel = page.locator('.inspector-panel, [class*="inspector-panel"]').first()
    const inspectorText = page.getByText('Inspector', { exact: false }).first()
    await expect(inspectorText).toBeVisible({ timeout: 10_000 })
    console.log('[test] Inspector panel visible')

    // 7. Click "UI Preview" tab if needed
    const previewTab = page.locator('button, div').filter({ hasText: /^UI Preview$/ }).first()
    if (await previewTab.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await previewTab.click()
      await page.waitForTimeout(500)
    }

    // 8. Check for convert button vs already-converted
    const convertBtn = page.locator('.ui-preview-frame__convert-btn')
    const hasConvertBtn = await convertBtn.isVisible({ timeout: 5_000 }).catch(() => false)
    console.log(`[test] Convert button visible: ${hasConvertBtn}`)

    if (!hasConvertBtn) {
      // Already has SceneGraph or no HTML template
      const openEditorBtn = page.locator('.ui-preview-frame__open-editor')
      const alreadyConverted = await openEditorBtn.isVisible({ timeout: 3_000 }).catch(() => false)
      if (alreadyConverted) {
        console.log('[test] Already has Figma-style design — pass')
        return
      }
      test.skip(true, 'No convert button and no existing design')
      return
    }

    // 9. Click convert
    await convertBtn.click()
    console.log('[test] Clicked "Figma 스타일 와이어프레임으로 변환"')

    // 10. Wait for AI conversion panel (either old or new class)
    const convertPanel = page.locator('.ui-preview-convert-panel, .inspector-design-ai-layout, .inspector-design-editor__generating')
    await expect(convertPanel.first()).toBeVisible({ timeout: 10_000 })
    console.log('[test] AI conversion panel visible — generating...')

    // 11. Wait for completion (up to 90s) — panel disappears or changes to editor
    await expect(convertPanel.first()).toBeHidden({ timeout: 90_000 })
    console.log('[test] AI conversion complete')

    // 12. Dump the sceneGraph from the correct UI node
    await page.waitForTimeout(2000)

    // Get all canvas node IDs and find the UI one
    const uiNodeId = await page.evaluate(() => {
      const allNodes = document.querySelectorAll('.vue-flow__node')
      for (const n of allNodes) {
        const label = n.querySelector('.es-node__label')?.textContent || ''
        if (label.includes('InventoryStatus')) return n.getAttribute('data-id')
      }
      // fallback: return second node (first is usually BC)
      return allNodes[allNodes.length - 1]?.getAttribute('data-id')
    })
    console.log(`[test] UI node ID: ${uiNodeId}`)

    if (uiNodeId) {
      const apiResp = await page.request.get(`/api/graph/expand-with-bc/${uiNodeId}`)
      if (apiResp.ok()) {
        const apiData = await apiResp.json()
        const uiNode = apiData.nodes?.find((n: any) => n.id === uiNodeId)
        const sgRaw = uiNode?.sceneGraph
        console.log(`[test] sceneGraph raw type: ${typeof sgRaw}, length: ${sgRaw?.length || 0}`)
        if (sgRaw && sgRaw.length > 10) {
          const sg = typeof sgRaw === 'string' ? JSON.parse(sgRaw) : sgRaw
          const nodeCount = Object.keys(sg.nodes || {}).length
          console.log(`[test] SceneGraph nodes: ${nodeCount}`)
          for (const [nid, ndata] of Object.entries(sg.nodes || {}).slice(0, 8)) {
            const nd = ndata as any
            console.log(`[test]   ${nid}: type=${nd.type}, name=${nd.name || ''}, children=${nd.childIds?.length || 0}`)
          }
        } else {
          console.log('[test] No real sceneGraph saved')
        }
      }
    }

    // Also check the component's internal state via DOM inspection
    const viewState = await page.evaluate(() => {
      const convertPanel = document.querySelector('.ui-preview-convert-panel')
      const framePreview = document.querySelector('.ui-preview-frame canvas')
      const htmlPreview = document.querySelector('.ui-preview-frame__body [data-wf-root]') ||
                          document.querySelector('.ui-preview-frame__body .wf-root')
      const openEditorBtn = document.querySelector('.ui-preview-frame__open-editor')
      const convertBtn = document.querySelector('.ui-preview-frame__convert-btn')
      return {
        convertPanelVisible: !!convertPanel,
        framePreviewCanvas: !!framePreview,
        htmlPreview: !!htmlPreview,
        openEditorBtn: !!openEditorBtn,
        convertBtn: !!convertBtn
      }
    })
    console.log(`[test] View state:`, JSON.stringify(viewState))

    const criticalErrors = pageErrors.filter(e =>
      e.includes('forEach is not a function') ||
      e.includes('remoteEntry') ||
      e.includes('Failed to fetch dynamically imported module')
    )
    expect(criticalErrors).toHaveLength(0)

    // Take screenshot of UI Preview
    await page.waitForTimeout(3000)
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.waitForTimeout(500)
    await page.screenshot({ path: 'test-results/convert-preview.png', fullPage: false })
    console.log('[test] Preview screenshot saved')

    // Switch to Design tab (inside the inspector panel tabs)
    const designTab = page.locator('.inspector-tab').filter({ hasText: 'Design' })
    if (await designTab.isVisible({ timeout: 2000 }).catch(() => false)) {
      await designTab.click()
      console.log('[test] Clicked Design tab')
      await page.waitForTimeout(8000) // Wait for FrameEditor + CanvasKit init
      await page.screenshot({ path: 'test-results/convert-design.png', fullPage: false })
      console.log('[test] Design tab screenshot saved')

      // Check if canvas element exists in the FrameEditor
      const editorCanvas = page.locator('.frame-editor canvas, [data-test-id="canvas-element"]')
      const hasEditorCanvas = await editorCanvas.isVisible({ timeout: 3000 }).catch(() => false)
      console.log(`[test] FrameEditor canvas visible: ${hasEditorCanvas}`)

      // Check errors
      const designErrors = await page.evaluate(() => {
        const el = document.querySelector('.frame-editor__loading')
        const err = document.querySelector('.inspector-design-editor__empty')
        const editor = document.querySelector('.frame-editor')
        return {
          loading: !!el,
          empty: !!err,
          editorVisible: !!editor,
          editorHTML: editor?.innerHTML?.slice(0, 300) || 'N/A'
        }
      })
      console.log(`[test] Design state:`, JSON.stringify(designErrors))
    } else {
      console.log('[test] Design tab not found')
    }

    console.log('[test] ✓ Test complete')
  })
})
