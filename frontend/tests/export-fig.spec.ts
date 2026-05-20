import { test, expect } from '@playwright/test'

/**
 * E2E test: Generate component wireframe → Download as .fig
 *
 * Tests the full flow: component button → sceneGraph → .fig download
 */
test.describe('Export .fig file', () => {
  test.setTimeout(120_000)

  test('generate wireframe then download .fig', async ({ page }) => {
    const browserErrors: string[] = []
    page.on('console', msg => {
      const text = msg.text()
      if (msg.type() === 'error' && !text.includes('404') && !text.includes('Failed to load resource')) {
        browserErrors.push(text)
        console.log(`[browser:error] ${text}`)
      }
    })

    // 1. Load app
    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.locator('#app')).toBeVisible()

    // 2. Expand tree and find UI node
    const expandBtn = page.locator('.tree-action-btn[title="Expand All"]')
    if (await expandBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await expandBtn.click()
      await page.waitForTimeout(1000)
    }

    const uiIcons = page.locator('.tree-node__icon--ui')
    const uiCount = await uiIcons.count()
    console.log(`[test] Found ${uiCount} UI nodes`)
    test.skip(uiCount === 0, 'No UI nodes')

    // 3. Open first UI node in inspector
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

    // 4. Go to UI Preview
    const previewTab = page.locator('button, div').filter({ hasText: /^UI Preview$/ }).first()
    if (await previewTab.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await previewTab.click()
      await page.waitForTimeout(500)
    }

    // 5. Check if sceneGraph already exists (download button enabled)
    const downloadBtn = page.locator('button[title*=".fig"]').first()
    const downloadEnabled = await downloadBtn.isEnabled({ timeout: 3_000 }).catch(() => false)
    console.log(`[test] Download button enabled: ${downloadEnabled}`)

    if (!downloadEnabled) {
      // Generate a wireframe first using component button
      console.log('[test] No sceneGraph yet, generating...')
      const componentBtn = page.locator('button[title*="component library"], button[title*="Generating"]').first()
      if (await componentBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await componentBtn.click()
      } else {
        const modeSelect = page.locator('.ui-preview-empty__mode-select').first()
        if (await modeSelect.isVisible({ timeout: 3_000 }).catch(() => false)) {
          await modeSelect.selectOption('component')
          await page.locator('.ui-preview-empty__btn').first().click()
        }
      }

      // Wait for generation to complete
      const framePreview = page.locator('.frame-preview, .ui-preview-frame canvas')
      await framePreview.first().waitFor({ state: 'visible', timeout: 90_000 })
      console.log('[test] Wireframe generated')
      await page.waitForTimeout(1000)
    }

    // 6. Debug: find the exact download button
    const allBtns = page.locator('.ui-preview-panel__btn')
    const btnCount = await allBtns.count()
    console.log(`[test] Action buttons: ${btnCount}`)
    for (let i = 0; i < btnCount; i++) {
      const btn = allBtns.nth(i)
      const title = await btn.getAttribute('title')
      const disabled = await btn.isDisabled()
      console.log(`[test]   btn[${i}]: title="${title}", disabled=${disabled}`)
    }

    // Intercept the export-fig API call
    const apiResponsePromise = page.waitForResponse(
      resp => resp.url().includes('/export-fig/'),
      { timeout: 30_000 }
    )

    // Click the download .fig button by exact title match
    const dlBtn = page.locator('button[title="Download as .fig file"]').first()
    const dlBtnExists = await dlBtn.isVisible({ timeout: 3_000 }).catch(() => false)
    console.log(`[test] Download .fig button found: ${dlBtnExists}`)

    if (!dlBtnExists) {
      // Fallback: last button
      const lastBtn = allBtns.last()
      const lastTitle = await lastBtn.getAttribute('title')
      console.log(`[test] Falling back to last button: "${lastTitle}"`)
      await lastBtn.click()
    } else {
      await dlBtn.click()
    }
    console.log('[test] Clicked download button')
    await dlBtn.click()

    // 7. Wait for API response
    const apiResponse = await apiResponsePromise.catch(e => {
      console.log(`[test] No API response: ${e.message}`)
      return null
    })

    if (apiResponse) {
      console.log(`[test] API status: ${apiResponse.status()}`)
      console.log(`[test] API content-type: ${apiResponse.headers()['content-type']}`)
      if (apiResponse.status() !== 200) {
        const body = await apiResponse.text().catch(() => '(no body)')
        console.log(`[test] API error body: ${body.slice(0, 500)}`)
      } else {
        const body = await apiResponse.body()
        console.log(`[test] API response size: ${body.length} bytes`)
        // Check it's a valid zip
        if (body.length > 4) {
          const header = String.fromCharCode(body[0], body[1])
          console.log(`[test] File header: "${header}" (expect "PK")`)
        }
      }
    }

    // Check for errors in UI
    await page.waitForTimeout(2000)
    const errorAlert = page.locator('.inspector-alert.error')
    const hasError = await errorAlert.isVisible({ timeout: 2_000 }).catch(() => false)
    if (hasError) {
      const errorText = await errorAlert.first().textContent()
      console.log(`[test] UI ERROR: ${errorText}`)
      expect.soft(errorText).not.toContain('Missing required field')
      expect.soft(errorText).not.toContain('Not found')
    }

    expect(apiResponse).not.toBeNull()
    expect(apiResponse!.status()).toBe(200)

    await page.screenshot({ path: 'test-results/export-fig-result.png', fullPage: false })
    console.log('[test] PASSED')
  })
})
