import { test, expect } from '@playwright/test'
import path from 'path'

/**
 * 034 — Epic/Feature 등록·뷰·편집·radar 범위 필터링 (US1~US4) e2e.
 * Drives the real Requirements tab against a live backend + Neo4j, creating
 * a demo Epic + Feature through the UI, then exercising view / edit / radar.
 * One screenshot per distinct user-visible state → manual/screenshots/.
 */

const SHOTS = path.resolve(__dirname, '../screenshots')
const APP = process.env.APP_URL || 'http://localhost:5199'

const EPIC_NAME = 'E2E데모 결제관리'
const EPIC_DESC = '결제 및 환불과 관련된 요구사항을 묶는 Epic 입니다.'
const FEATURE_NAME = '결제 수단 관리'
const FEATURE_RENAMED = '결제 수단 등록·관리'

async function shot(page, name: string) {
  await page.evaluate(() => window.scrollTo(0, 0))
  // Viewport-only capture (not fullPage) → tight, readable frames.
  await page.screenshot({ path: `${SHOTS}/${name}` })
}

async function openRequirementsTab(page) {
  await page.goto(APP)
  // Default tab is 'Design' — switch to Requirements.
  const tab = page.locator('.top-bar__tabs button', { hasText: 'Requirements' }).first()
  await tab.click()
  await page.waitForSelector('.req-tree', { timeout: 30_000 })
  await page.waitForTimeout(800) // let tree fetch settle
}

test('전체 시나리오 — 등록·뷰·편집·radar', async ({ page }) => {
  // ── 01 초기 화면 ──────────────────────────────────────────────────
  await openRequirementsTab(page)
  await shot(page, '01_requirements_initial.png')

  // ── 02 추가 다이얼로그 + 단위 선택 ───────────────────────────────
  await page.getByRole('button', { name: '+ 요구사항 추가' }).click()
  await page.waitForSelector('.dialog__units')
  await shot(page, '02_add_dialog_units.png')

  // ── 03 Epic 등록 폼 작성 ─────────────────────────────────────────
  await page.locator('.dialog__units button', { hasText: 'Epic' }).click()
  await page.getByPlaceholder('예: 주문 관리').fill(EPIC_NAME)
  await page.getByPlaceholder('이 Epic(Bounded Context)의 책임').fill(EPIC_DESC)
  await shot(page, '03_epic_form_filled.png')

  // ── 04 Epic 등록 결과 (트리 반영) ────────────────────────────────
  await page.getByRole('button', { name: 'Epic 추가' }).click()
  await page.waitForSelector(`.tree-node--epic:has-text("${EPIC_NAME}")`, { timeout: 15_000 })
  await shot(page, '04_epic_created_in_tree.png')

  // ── 05 Feature 등록 폼 (소속 Epic 선택) ──────────────────────────
  await page.getByRole('button', { name: '+ 요구사항 추가' }).click()
  await page.waitForSelector('.dialog__units')
  await page.locator('.dialog__units button', { hasText: 'Feature' }).click()
  await page.locator('label:has-text("소속 Epic") select').selectOption({ label: EPIC_NAME })
  await page.getByPlaceholder('예: 주문 취소').fill(FEATURE_NAME)
  await shot(page, '05_feature_form_filled.png')

  // ── 06 Feature 등록 결과 ─────────────────────────────────────────
  await page.getByRole('button', { name: 'Feature 추가' }).click()
  await page.waitForTimeout(1200)
  // Expand the epic via its caret to reveal the feature.
  const epicRow = page.locator('.tree-node--epic', { hasText: EPIC_NAME }).first()
  await epicRow.locator('.caret').first().click()
  await page.waitForSelector(`.tree-node--feature:has-text("${FEATURE_NAME}")`, { timeout: 10_000 })
  await shot(page, '06_feature_created_in_tree.png')

  // ── 07 Epic 전용 뷰 (선택) + radar ───────────────────────────────
  await epicRow.locator('.tree-row').first().click()
  await page.waitForSelector('.epic-detail', { timeout: 10_000 })
  await page.waitForTimeout(800)
  await shot(page, '07_epic_detail_view.png')

  // ── 08 Feature 전용 뷰 (선택) + radar ────────────────────────────
  // Click the feature from the Epic detail's feature list.
  await page.locator('.epic-detail .ed-list__item', { hasText: FEATURE_NAME }).first().click()
  await page.waitForSelector('.feature-detail', { timeout: 10_000 })
  await page.waitForTimeout(800)
  await shot(page, '08_feature_detail_view.png')

  // ── 09 Feature 편집 다이얼로그 ───────────────────────────────────
  await page.locator('.feature-detail .fd-edit').click()
  await page.waitForSelector('.dialog:has-text("Feature 편집")')
  const editInput = page.locator('.dialog:has-text("Feature 편집") input').first()
  await editInput.fill(FEATURE_RENAMED)
  await shot(page, '09_feature_edit_dialog.png')

  // ── 10 편집 저장 → 즉시 반영 ─────────────────────────────────────
  await page.locator('.dialog:has-text("Feature 편집")').getByRole('button', { name: '저장' }).click()
  await page.waitForTimeout(1200)
  await page.waitForSelector(`.feature-detail:has-text("${FEATURE_RENAMED}")`, { timeout: 10_000 })
  await shot(page, '10_feature_renamed_reflected.png')

  // ── 11 검증: 이름을 비우면 저장 버튼이 비활성화되어 저장 불가 ────
  await page.locator('.feature-detail .fd-edit').click()
  await page.waitForSelector('.dialog:has-text("Feature 편집")')
  await page.locator('.dialog:has-text("Feature 편집") input').first().fill('')
  const saveBtn = page.locator('.dialog:has-text("Feature 편집")').getByRole('button', { name: '저장' })
  await expect(saveBtn).toBeDisabled() // 빈 이름 → 저장 차단
  await shot(page, '11_feature_edit_validation.png')
  // close
  await page.locator('.dialog:has-text("Feature 편집")').getByRole('button', { name: '취소' }).click()

  // ── 12 DDD 적합성 검증 (US6, 실 LLM) ─────────────────────────────
  await page.locator('.feature-detail .fd-validate').click()
  await page.waitForSelector('.dialog:has-text("DDD 적합성 검증")', { timeout: 45_000 })
  await page.waitForTimeout(500)
  await shot(page, '12_ddd_validation.png')
  await page.locator('.dialog:has-text("DDD 적합성 검증")').getByRole('button', { name: '확인' }).click()

  // ── 13 하위 User Story 자동 생성 — 제안 검토 (US5, 실 LLM) ────────
  await page.locator('.feature-detail .fd-gen').click()
  await page.waitForSelector('.dialog:has-text("하위 User Story 자동 생성")', { timeout: 60_000 })
  await page.waitForTimeout(500)
  await shot(page, '13_generate_review.png')
  await page.locator('.dialog:has-text("하위 User Story 자동 생성")').getByRole('button', { name: '취소' }).click()

  // ── 14 Epic AI 제안 (US1, 실 LLM) ────────────────────────────────
  await page.getByRole('button', { name: '+ 요구사항 추가' }).click()
  await page.waitForSelector('.dialog__units')
  await page.locator('.dialog__units button', { hasText: 'Epic' }).click()
  await page.locator('.dialog__tabs button', { hasText: 'AI 제안' }).click()
  await page.getByPlaceholder('만들고 싶은 업무 영역(Epic)을 자연어로 설명하세요...').fill(
    '배송과 물류를 관리하는 영역이 필요하다. 출고, 배송추적, 반품 회수.',
  )
  await page.getByRole('button', { name: '제안 받기' }).click()
  await page.waitForSelector('.proposal', { timeout: 45_000 })
  await page.waitForTimeout(400)
  await shot(page, '14_epic_ai_propose.png')
  await page.locator('.dialog__close').click()

  // ── 15 설계 자동 반영 프롬프트 — Event Modeling 탭 진입 (US7) ─────
  await page.locator('.top-bar__tabs button', { hasText: 'Event Modeling' }).first().click()
  await page.waitForSelector('.drp', { timeout: 20_000 })
  await page.waitForTimeout(400)
  await shot(page, '15_design_reflect_prompt.png')
  await page.locator('.drp').getByRole('button', { name: '아니오' }).click()
})
