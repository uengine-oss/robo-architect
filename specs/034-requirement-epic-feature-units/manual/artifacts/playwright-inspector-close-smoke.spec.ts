import { test, expect } from '@playwright/test'
const APP = process.env.APP_URL || 'http://localhost:5180'

test('설계 궤적 노드 클릭 → Inspector → 닫기 버튼으로 닫힘', async ({ page }) => {
  test.setTimeout(80_000)
  await page.goto(APP)
  await page.locator('.top-bar__tabs button', { hasText: 'Requirements' }).first().click()
  await page.waitForSelector('.req-tree', { timeout: 30_000 })
  const carets = page.locator('.req-tree .caret')
  for (let i = 0; i < 10; i++) {
    if (await page.locator('.req-tree .us-row').first().count()) break
    const c = carets.nth(i); if (await c.count()) await c.click().catch(() => {})
    await page.waitForTimeout(120)
  }
  await page.locator('.req-tree .us-row').first().click()
  await page.waitForSelector('.us-detail', { timeout: 10_000 })
  await page.locator('.us-tab', { hasText: '설계 궤적' }).click()
  await page.waitForSelector('.us-tab-body--trace', { timeout: 10_000 })
  // click a node in the design-trace canvas
  const node = page.locator('.us-tab-body--trace .vue-flow__node').first()
  await node.waitFor({ state: 'visible', timeout: 15_000 })
  await node.click()
  await page.waitForSelector('.req-inspector-pane', { timeout: 10_000 })
  await expect(page.locator('.req-inspector-close')).toBeVisible()
  await page.locator('.req-inspector-close').click()
  await expect(page.locator('.req-inspector-pane')).toHaveCount(0)
})
