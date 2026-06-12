import { test, expect } from '@playwright/test'
import path from 'path'

/**
 * §039 US4 — "Big picture" 뷰 비활성화 회귀 캡처.
 *
 * 상단 탭 목록에 "Big picture" 진입점이 없고, 다른 뷰/네비게이터가 정상임을 확인.
 *
 * 전제: 프런트(5173) + 백엔드(8000) 구동.
 */

const SHOTS = path.resolve(__dirname, '../screenshots')

test('Big picture 탭 부재 확인', async ({ page }) => {
  await page.goto('/')
  await page.waitForLoadState('networkidle')

  // 상단 탭 내비에 "Big picture"가 없어야 한다.
  const bigPictureTab = page.getByRole('button', { name: 'Big picture', exact: true })
  await expect(bigPictureTab).toHaveCount(0)

  await page.screenshot({ path: `${SHOTS}/06_no_bigpicture_tab.png`, fullPage: false })

  // 다른 탭(Process/Design)으로 이동해 회귀 없음 확인.
  const processTab = page.getByRole('button', { name: 'Process', exact: true })
  if (await processTab.count()) {
    await processTab.first().click()
    await page.waitForTimeout(1500)
    await page.screenshot({ path: `${SHOTS}/07_other_views_ok.png`, fullPage: false })
  }
})
