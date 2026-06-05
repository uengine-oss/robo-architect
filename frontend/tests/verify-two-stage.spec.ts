import { test } from '@playwright/test'

test('2단계 승인 흐름 UI 확인', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.waitForTimeout(2000)

  await page.locator('button').filter({ hasText: 'Changes' }).first().click()
  await page.waitForTimeout(1200)

  // CHG-007 선택 (DRAFT - 아직 제출 안 됨)
  await page.locator('.cp-item').filter({ hasText: 'CHG-007' }).first().click()
  await page.waitForTimeout(800)
  await page.screenshot({ path: '/tmp/2stage-01-draft.png' })

  // 상태 흐름 표시 확인
  const flowSteps = await page.locator('.cd-flow__step').count()
  console.log('흐름 단계 수:', flowSteps)
  const currentStep = await page.locator('.cd-flow__step--current .cd-flow__label').textContent().catch(() => '')
  console.log('현재 단계:', currentStep)

  // 버튼 확인
  const submitBtn = await page.locator('button').filter({ hasText: '제출' }).isVisible().catch(() => false)
  console.log('제출 버튼:', submitBtn)

  // CHG-006 (SUBMITTED) 확인
  await page.locator('.cp-item').filter({ hasText: 'CHG-006' }).first().click()
  await page.waitForTimeout(800)
  await page.screenshot({ path: '/tmp/2stage-02-submitted.png' })
  const approve1Btn = await page.locator('button').filter({ hasText: '1차 승인' }).isVisible().catch(() => false)
  console.log('1차 승인 버튼:', approve1Btn)

  // CHG-005 (DRAFT) - 1차 승인 API로 진행시켜보기
  // 먼저 제출: CHG-007
  await page.locator('.cp-item').filter({ hasText: 'CHG-007' }).first().click()
  await page.waitForTimeout(500)
})
