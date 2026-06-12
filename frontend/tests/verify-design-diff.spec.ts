import { test } from '@playwright/test'

test('DesignChangesView 계층 diff UI 확인', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.waitForTimeout(2000)

  // Changes 탭
  await page.locator('button').filter({ hasText: 'Changes' }).first().click()
  await page.waitForTimeout(1000)

  // CHG-012 선택
  await page.locator('.cp-item').filter({ hasText: 'CHG-012' }).first().click()
  await page.waitForTimeout(1000)
  await page.screenshot({ path: '/tmp/diff-01-chg012.png' })

  // 설계 반영 탭 클릭
  const designTab = page.locator('.cd-tab').filter({ hasText: '설계 반영' })
  await designTab.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})
  await designTab.click()
  await page.waitForTimeout(800)
  await page.screenshot({ path: '/tmp/diff-02-design-tab.png' })

  // 레이어 확인
  const layerCount = await page.locator('.dcv-layer').count()
  const nodeCount  = await page.locator('.dcv-node').count()
  console.log('레이어:', layerCount, '| 노드:', nodeCount)

  // 첫 번째 완료 노드 클릭 (diff 펼침)
  const doneNodes = page.locator('.dcv-node--done')
  const doneCount = await doneNodes.count()
  console.log('완료 노드:', doneCount)

  if (doneCount > 0) {
    await doneNodes.first().click()
    await page.waitForTimeout(400)
    await page.screenshot({ path: '/tmp/diff-03-diff-open.png' })
    
    // 두 번째 노드도 펼침
    if (doneCount > 1) {
      await doneNodes.nth(1).click()
      await page.waitForTimeout(400)
    }
  }
  
  await page.screenshot({ path: '/tmp/diff-04-all-open.png' })
  
  // 레이어 이름 출력
  const layerNames = await page.locator('.dcv-layer__name').allTextContents()
  console.log('레이어 이름:', layerNames)
})
