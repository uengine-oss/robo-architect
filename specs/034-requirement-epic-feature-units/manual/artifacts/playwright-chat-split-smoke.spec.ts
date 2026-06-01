import { test, expect } from '@playwright/test'
const APP = process.env.APP_URL || 'http://localhost:5180'

async function gotoReq(page) {
  await page.goto(APP)
  await page.locator('.top-bar__tabs button', { hasText: 'Requirements' }).first().click()
  await page.waitForSelector('.req-tree', { timeout: 30_000 })
}
async function expandToUS(page) {
  const carets = page.locator('.req-tree .caret')
  for (let i = 0; i < 10; i++) {
    if (await page.locator('.req-tree .us-row').first().count()) break
    const c = carets.nth(i); if (await c.count()) await c.click().catch(() => {})
    await page.waitForTimeout(120)
  }
}

test('우측 Chat split이 선택 항목(US/Epic)을 따라감 + 설계궤적 탭', async ({ page }) => {
  test.setTimeout(90_000)
  await gotoReq(page)

  // US 선택 (검증된 경로) → us-detail
  await expandToUS(page)
  await page.locator('.req-tree .us-row').first().click()
  await page.waitForSelector('.us-detail', { timeout: 10_000 })

  // 우측 Chat split 열기 → chip이 US
  await page.locator('.tb-btn', { hasText: 'Chat' }).click()
  await page.waitForSelector('.req-chat-pane .chat-panel', { timeout: 10_000 })
  await expect(page.locator('.req-chat-pane .chat-panel__title')).toContainText('Chat')
  await expect(page.locator('.req-chat-pane .chat-chip__icon')).toContainText('US')

  // 설계 궤적이 탭(하단 split 아님)
  await expect(page.locator('.req-detail-pane__canvas')).toHaveCount(0)
  await page.locator('.us-tab', { hasText: '설계 궤적' }).click()
  await page.waitForSelector('.us-tab-body--trace', { timeout: 10_000 })
  await page.screenshot({ path: '/tmp/chat_split_us.png' })

  // Epic 선택 → 같은 Chat split이 Epic을 따라감(chip EPIC)
  await page.locator('.tree-node--epic .tree-row').first().click()
  await page.waitForSelector('.epic-detail', { timeout: 10_000 })
  await expect(page.locator('.req-chat-pane .chat-chip__icon')).toContainText('EPIC')
  await page.screenshot({ path: '/tmp/chat_split_epic.png' })
})

test('왼쪽 트리뷰 split 드래그로 너비 조절', async ({ page }) => {
  test.setTimeout(60_000)
  await gotoReq(page)
  const treePane = page.locator('.req-tree-pane')
  const w0 = (await treePane.boundingBox())!.width
  const rz = page.locator('.req-tree-resizer')
  await expect(rz).toBeVisible()
  const box = (await rz.boundingBox())!
  await page.mouse.move(box.x + 2, box.y + 120)
  await page.mouse.down()
  await page.mouse.move(box.x + 160, box.y + 120, { steps: 8 })
  await page.mouse.up()
  const w1 = (await treePane.boundingBox())!.width
  expect(w1).toBeGreaterThan(w0 + 80)
})
