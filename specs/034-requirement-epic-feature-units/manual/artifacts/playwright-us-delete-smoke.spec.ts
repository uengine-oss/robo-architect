import { test, expect } from '@playwright/test'
const APP = process.env.APP_URL || 'http://localhost:5180'

test('User Story 상세에서 🗑 삭제 → 다이얼로그(User Story 삭제) 열림, 취소', async ({ page }) => {
  test.setTimeout(60_000)
  await page.goto(APP)
  await page.locator('.top-bar__tabs button', { hasText: 'Requirements' }).first().click()
  await page.waitForSelector('.req-tree', { timeout: 30_000 })
  // 트리에서 caret을 펼쳐 첫 US 행을 찾는다
  const carets = page.locator('.req-tree .caret')
  for (let i = 0; i < 8; i++) {
    const usRow = page.locator('.req-tree .us-row').first()
    if (await usRow.count()) break
    const c = carets.nth(i)
    if (await c.count()) await c.click().catch(() => {})
    await page.waitForTimeout(150)
  }
  const usRow = page.locator('.req-tree .us-row').first()
  await expect(usRow).toBeVisible({ timeout: 10_000 })
  await usRow.click()
  await page.waitForSelector('.us-detail .us-tab--delete', { timeout: 10_000 })
  await page.locator('.us-detail .us-tab--delete').click()
  await page.waitForSelector('.dialog.dc', { timeout: 5_000 })
  await expect(page.locator('.dialog.dc')).toContainText('User Story 삭제')
  await expect(page.locator('.dialog.dc')).toContainText('디자인도 함께 제거')
  await page.screenshot({ path: '/tmp/us_delete_dialog.png' })
  await page.locator('.dialog.dc .btn', { hasText: '취소' }).click()
  await expect(page.locator('.dialog.dc')).toHaveCount(0)
})
