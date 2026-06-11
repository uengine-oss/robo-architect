import { test } from '@playwright/test'

test('CHG-009 IMPLEMENTED 상태 UI 확인', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.waitForTimeout(2000)

  await page.locator('button').filter({ hasText: 'Changes' }).first().click()
  await page.waitForTimeout(1200)

  await page.locator('.cp-item').filter({ hasText: 'CHG-009' }).first().click()
  await page.waitForTimeout(1000)
  await page.screenshot({ path: '/tmp/chg009-implemented-detail.png' })

  // 이력 탭
  await page.locator('.cd-tab').filter({ hasText: '이력' }).click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: '/tmp/chg009-implemented-history.png' })

  const historyItems = await page.locator('.cd-history__badge').allTextContents()
  console.log('상태 이력:', historyItems)

  // 영향도 탭
  await page.locator('.cd-tab').filter({ hasText: '영향도' }).click()
  await page.waitForTimeout(1000)
  await page.screenshot({ path: '/tmp/chg009-implemented-impact.png' })
})
