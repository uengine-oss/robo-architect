import { test, expect, Page } from '@playwright/test'
import path from 'path'

const SHOTS = path.resolve(__dirname, '../../screenshots')
const APP   = process.env.APP_URL || 'http://localhost:5173'

test.use({ viewport: { width: 1400, height: 900 } })

// ── helper: navigate to Changes tab ─────────────────────────────────────
async function gotoChanges(page: Page) {
  await page.goto(APP)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1200)
  // Changes 탭 클릭 (TopBar)
  const changesTab = page.getByRole('button', { name: 'Changes' })
    .or(page.locator('[data-tab="Changes"]'))
    .or(page.getByText('Changes').first())
  await changesTab.click()
  await page.waitForTimeout(1000)
}

// ── 01: Changes 탭 — 목록 초기 화면 ──────────────────────────────────────
test('01 — Changes 탭 목록 화면', async ({ page }) => {
  await gotoChanges(page)

  // 전체 viewport 캡처
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: `${SHOTS}/01_changes_list.png` })
})

// ── 02: Change 상세 — 클릭하여 열기 ─────────────────────────────────────
test('02 — Change 상세 화면 (CHG-012)', async ({ page }) => {
  await gotoChanges(page)
  await page.waitForTimeout(800)

  // CHG-012 또는 첫 번째 항목 클릭
  const firstChange = page.locator('.chg-item, .change-item, [class*="chg"]').first()
    .or(page.getByText('CHG-012').first())
    .or(page.getByText('탈퇴 회원 마일리지').first())

  if (await firstChange.count() > 0) {
    await firstChange.click()
    await page.waitForTimeout(1200)
  }

  await page.screenshot({ path: `${SHOTS}/02_change_detail.png` })
})

// ── 03: Change 생성 모달 ─────────────────────────────────────────────────
test('03 — Change 생성 버튼 클릭', async ({ page }) => {
  await gotoChanges(page)
  await page.waitForTimeout(800)

  // "추가 Change" / "새 Change" / "+" 버튼 탐색
  const addBtn = page.getByRole('button', { name: /추가|새 Change|\+/ })
    .or(page.getByTitle(/추가|새 Change/))
    .or(page.locator('button').filter({ hasText: /추가|Change 추가|새 변경/ }))

  if (await addBtn.count() > 0) {
    await addBtn.first().click()
    await page.waitForTimeout(800)
    await page.screenshot({ path: `${SHOTS}/03_change_create_modal.png` })
  } else {
    // 버튼 미발견 시 현재 상태 캡처
    await page.screenshot({ path: `${SHOTS}/03_change_create_modal.png` })
  }
})

// ── 04: 영향도 분석 탭 ────────────────────────────────────────────────────
test('04 — 영향도 분석 탭 (Impact)', async ({ page }) => {
  await gotoChanges(page)
  await page.waitForTimeout(800)

  // 첫 번째 Change 클릭
  const chgItem = page.locator('text=CHG-012')
    .or(page.locator('text=탈퇴 회원 마일리지').first())
  if (await chgItem.count() > 0) {
    await chgItem.first().click()
    await page.waitForTimeout(1000)
  }

  // 영향도 탭 클릭
  const impactTab = page.getByRole('button', { name: '영향도' })
    .or(page.getByText('영향도').first())
    .or(page.locator('[class*="tab"]').filter({ hasText: /영향도|Impact/ }))

  if (await impactTab.count() > 0) {
    await impactTab.first().click()
    await page.waitForTimeout(1200)
  }

  await page.screenshot({ path: `${SHOTS}/04_impact_analysis.png` })
})

// ── 05: 설계 반영 탭 (DesignChangesView) ─────────────────────────────────
test('05 — 설계 반영 탭', async ({ page }) => {
  await gotoChanges(page)
  await page.waitForTimeout(800)

  // CHG-012 (DESIGN_APPLIED) 클릭
  const chgItem = page.locator('text=CHG-012')
    .or(page.locator('text=탈퇴 회원 마일리지').first())
  if (await chgItem.count() > 0) {
    await chgItem.first().click()
    await page.waitForTimeout(1000)
  }

  // 설계 반영 탭
  const designTab = page.getByRole('button', { name: '설계 반영' })
    .or(page.getByText('설계 반영').first())
    .or(page.locator('[class*="tab"]').filter({ hasText: /설계 반영/ }))

  if (await designTab.count() > 0) {
    await designTab.first().click()
    await page.waitForTimeout(1500)
  }

  await page.screenshot({ path: `${SHOTS}/05_design_changes.png` })
})

// ── 06: 상태 이력 탭 ─────────────────────────────────────────────────────
test('06 — 상태 이력 탭', async ({ page }) => {
  await gotoChanges(page)
  await page.waitForTimeout(800)

  const chgItem = page.locator('text=CHG-012')
    .or(page.locator('text=탈퇴 회원 마일리지').first())
  if (await chgItem.count() > 0) {
    await chgItem.first().click()
    await page.waitForTimeout(1000)
  }

  const historyTab = page.getByRole('button', { name: '이력' })
    .or(page.getByText('이력').first())
    .or(page.locator('[class*="tab"]').filter({ hasText: /이력|History/ }))

  if (await historyTab.count() > 0) {
    await historyTab.first().click()
    await page.waitForTimeout(800)
  }

  await page.screenshot({ path: `${SHOTS}/06_status_history.png` })
})

// ── 07: 승인 워크플로우 흐름 표시 ────────────────────────────────────────
test('07 — 승인 흐름 스텝 표시', async ({ page }) => {
  await gotoChanges(page)
  await page.waitForTimeout(800)

  // PLAN_APPROVED 상태인 CHG-011 클릭
  const chg11 = page.locator('text=CHG-011')
    .or(page.locator('[class*="chg"]').nth(1))
  if (await chg11.count() > 0) {
    await chg11.first().click()
    await page.waitForTimeout(1000)
  }

  await page.screenshot({ path: `${SHOTS}/07_approval_workflow.png` })
})

// ── 08: 회귀 테스트 탭 ────────────────────────────────────────────────────
test('08 — 회귀 테스트 탭', async ({ page }) => {
  await gotoChanges(page)
  await page.waitForTimeout(800)

  const chgItem = page.locator('text=CHG-012')
  if (await chgItem.count() > 0) {
    await chgItem.first().click()
    await page.waitForTimeout(1000)
  }

  const regressionTab = page.getByRole('button', { name: '회귀' })
    .or(page.getByText('회귀 테스트').first())
    .or(page.locator('[class*="tab"]').filter({ hasText: /회귀/ }))

  if (await regressionTab.count() > 0) {
    await regressionTab.first().click()
    await page.waitForTimeout(1200)
  }

  await page.screenshot({ path: `${SHOTS}/08_regression_tests.png` })
})
