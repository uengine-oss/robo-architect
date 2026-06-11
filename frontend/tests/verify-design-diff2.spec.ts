import { test } from '@playwright/test'

test('DesignChangesView diff 상세 확인', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 })
  await page.goto('/')
  await page.waitForTimeout(2000)

  await page.locator('button').filter({ hasText: 'Changes' }).first().click()
  await page.waitForTimeout(1000)
  await page.locator('.cp-item').filter({ hasText: 'CHG-012' }).first().click()
  await page.waitForTimeout(1000)
  
  await page.locator('.cd-tab').filter({ hasText: '설계 반영' }).click()
  await page.waitForTimeout(600)

  // 모든 완료 노드 펼치기
  const doneNodes = page.locator('.dcv-node--done')
  const count = await doneNodes.count()
  for (let i = 0; i < count; i++) {
    await doneNodes.nth(i).click()
    await page.waitForTimeout(200)
  }
  await page.screenshot({ path: '/tmp/diff-full.png', fullPage: false })
  console.log(`완료 노드 ${count}개 모두 펼침`)
})
