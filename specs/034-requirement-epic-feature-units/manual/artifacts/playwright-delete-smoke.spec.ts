import { test, expect } from '@playwright/test'
const APP = process.env.APP_URL || 'http://localhost:5180'

test('삭제 다이얼로그 — Epic 상세에서 열림 + 디자인제거 체크 + 복구안내', async ({ page }) => {
  test.setTimeout(60_000)
  await page.goto(APP)
  await page.locator('.top-bar__tabs button', { hasText: 'Requirements' }).first().click()
  await page.waitForSelector('.req-tree', { timeout: 30_000 })
  // 삭제 이력 버튼이 툴바에 있는지
  await expect(page.locator('.tb-btn', { hasText: '삭제 이력' })).toBeVisible()
  // 첫 Epic 선택
  const epicRow = page.locator('.tree-node--epic .tree-row').first()
  await epicRow.click()
  await page.waitForSelector('.epic-detail', { timeout: 10_000 })
  // 🗑 삭제 버튼
  await page.locator('.epic-detail .ed-delete').click()
  await page.waitForSelector('.dialog.dc', { timeout: 5_000 })
  // 디자인 제거 체크박스 + 복구 안내 문구
  await expect(page.locator('.dialog.dc')).toContainText('디자인도 함께 제거')
  await expect(page.locator('.dialog.dc')).toContainText('삭제 이력')
  const boxes = await page.locator('.dialog.dc .dc__opt input[type=checkbox]').count()
  expect(boxes).toBeGreaterThanOrEqual(1)
  await page.screenshot({ path: '/tmp/delete_dialog.png' })
  // 취소 — 데이터 변경 없음
  await page.locator('.dialog.dc .btn', { hasText: '취소' }).click()
  await expect(page.locator('.dialog.dc')).toHaveCount(0)
})
