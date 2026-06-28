import { test, expect } from '@playwright/test'

// 043 ODA 표준 분해 모드 — 매뉴얼용 헤디드 데모. 시드된 PRO-ODA-DEMO(게이트 FAIL)를
// 사용해 모드 선택 → 정합성 매핑 → 적합성 게이트/면제 → 표준 산출물을 캡처한다.

const DIR = 'test-results'
const SS = (n: number, label: string) =>
  `${DIR}/demo-${String(n).padStart(2, '0')}-${label}.png`
const DEMO_ID = 'PRO-ODA-DEMO'

test('ODA 표준 분해 모드 — 사용 흐름 캡처', async ({ page }) => {
  test.setTimeout(120_000)

  // 0) 앱 진입 → Proposals 탭
  await page.goto('/')
  await page.waitForTimeout(1500)
  await page.locator('.top-bar__tab', { hasText: 'Proposals' }).click()
  await page.waitForTimeout(1200)
  await page.screenshot({ path: SS(1, 'proposals-list'), fullPage: false })

  // 1) 새 Proposal → 분해 모드 스위치(3종) 표시
  await page.locator('.panel-toolbar button.btn--primary').first().click()
  await page.waitForTimeout(800)
  await page.locator('.mode-switch').waitFor({ state: 'visible' })
  await page.screenshot({ path: SS(2, 'create-three-modes') })

  // 2) ODA 표준 모드 선택(라디오 하이라이트)
  await page.locator('.mode-switch__opt', { hasText: 'ODA' }).click()
  await page.locator('textarea.proposal-create__textarea')
    .fill('고객이 주문을 우선처리(expedite)하고 수수료를 부과한다')
  await page.waitForTimeout(500)
  await page.screenshot({ path: SS(3, 'create-oda-selected') })

  // 3) 생성 패널 닫고 시드된 ODA 데모 Proposal 열기
  await page.locator('.proposal-create .btn-close').click()
  await page.waitForTimeout(500)
  const item = page.locator('.proposal-item', { hasText: DEMO_ID })
  await item.first().scrollIntoViewIfNeeded()
  await item.first().click()
  await page.waitForTimeout(1200)
  await page.locator('.oda-track').waitFor({ state: 'visible' })

  // 4) 표준 정합성 매핑(UC/SID/TMF/Component)
  await page.screenshot({ path: SS(4, 'oda-alignment') })

  // 5) 적합성 게이트 — REUSE/EXTEND/NEW 분류 + FAIL + 위반 + 면제 입력
  await expect(page.locator('.gate-badge--fail')).toBeVisible()
  await page.locator('.oda-violations').scrollIntoViewIfNeeded()
  await page.screenshot({ path: SS(5, 'oda-conformance-fail'), fullPage: true })

  // 6) 면제 사유 입력
  await page.locator('.oda-waive__input').fill('표준 위반은 마이그레이션 일정상 차기 릴리스에서 해소 — 리스크 수용')
  await page.waitForTimeout(400)
  await page.locator('.oda-waive').scrollIntoViewIfNeeded()
  await page.screenshot({ path: SS(6, 'oda-waive-reason') })

  // 7) 면제 실행 → 게이트 WAIVED, plan 실행 활성화
  await page.locator('.oda-waive button').click()
  await page.waitForTimeout(1500)
  await expect(page.locator('.gate-badge--waived')).toBeVisible()
  await page.screenshot({ path: SS(7, 'oda-gate-waived'), fullPage: true })

  // 8) 표준 산출물(데이터모델·계약·아키텍처·BDD)
  await page.locator('.oda-artifacts').scrollIntoViewIfNeeded()
  await page.screenshot({ path: SS(8, 'oda-artifacts') })

  // 9) Plan 단계 — SUBMITTED ODA Proposal 열고 Plan 탭(041 Constitution 기반 구현계획)
  const planItem = page.locator('.proposal-item', { hasText: 'PRO-ODA-PLAN' })
  await planItem.first().scrollIntoViewIfNeeded()
  await planItem.first().click()
  await page.waitForTimeout(1000)
  await page.locator('.tab-btn', { hasText: 'Plan' }).first().click()
  await page.waitForTimeout(1200)
  await page.locator('.plan-section').first().waitFor({ state: 'visible' })
  await page.screenshot({ path: SS(9, 'oda-plan-stage'), fullPage: true })

  // 10) Impact Map — 표준 tacticalDiff 로 수렴된 전술 설계(다운스트림 무분기)
  await page.locator('.tab-btn', { hasText: 'Impact' }).first().click()
  await page.waitForTimeout(1200)
  await page.screenshot({ path: SS(10, 'oda-impact-converged'), fullPage: true })
})
