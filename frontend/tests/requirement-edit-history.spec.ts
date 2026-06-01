import { test, expect, Page } from '@playwright/test'
import { fileURLToPath } from 'url'
import path from 'path'

/**
 * Spec 033 — Requirement Direct-Edit with Edit History (사용자 매뉴얼용)
 *
 * 사용자 관점의 시나리오를 Playwright로 캡처합니다:
 *  1. Requirements 패널에서 UserStory 선택 → 개요 탭
 *  2. 편집 탭 클릭 → 편집 폼 (현재 값 채워짐)
 *  3. 필드 수정 후 저장 → "저장되었습니다" + 개요 탭 복귀
 *  4. 이력 탭 클릭 → 타임라인 (편집자·시각·변경 필드 diff)
 *  5. 충돌 시 에러 메시지
 *
 * 목 백엔드 사용 (실제 Neo4j 불필요).
 */

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const SHOTS_DIR = path.resolve(
  __dirname,
  '../../specs/033-requirement-edit-history/manual/screenshots',
)

// ── Mock data ──────────────────────────────────────────────────────────────

const MOCK_TREE = {
  epics: [
    {
      id: 'bc-membership',
      name: '회원가입',
      displayName: '회원가입 바운디드 컨텍스트',
      features: [
        {
          id: 'feat-consent',
          name: '동의 처리',
          description: '법정대리인 동의 흐름',
          source: 'llm',
          userStories: [
            {
              id: 'us-consent-001',
              role: '법정대리인',
              action: '업무처리 동의 또는 확인을 한다',
              benefit: '미성년자 또는 대리 동의가 필요한 고객의 회원가입 및 관련 업무가 적법하게 처리된다',
              priority: 'medium',
              status: 'draft',
              commandId: 'cmd-confirm-consent',
              commandName: 'ConfirmLegalGuardianConsent',
              acceptanceCriteria: [
                { kind: 'given', name: 'Aggregate: LegalGuardianConsent', description: null },
                { kind: 'when', name: 'Command: ConfirmLegalGuardianConsent', description: null },
                { kind: 'then', name: 'Happy path: Legal guardian successfully confirms consent for a minor using phone verification.', description: null },
                { kind: 'then', name: 'Consent confirmation fails due to mismatched legal guardian ID.', description: null },
              ],
            },
          ],
        },
      ],
      unassignedFeature: null,
    },
  ],
  unassigned: [],
}

const MOCK_DESIGN_TRACE = { nodes: [], relationships: [], empty: true }

const MOCK_HISTORY_EMPTY = { items: [] }

const MOCK_HISTORY_WITH_ENTRY = {
  items: [
    {
      id: 'hist-abc-001',
      timestamp: '2026-05-30T09:06:26.000+00:00',
      userName: 'jinyoung',
      userEmail: 'jyjang@uengine.org',
      changes: {
        action: {
          before: '업무처리 동의 또는 확인을 한다',
          after: '동의서를 검토하고 제출한다',
        },
        status: {
          before: 'draft',
          after: 'ready',
        },
      },
    },
  ],
}

const MOCK_PATCH_RESPONSE = {
  userStory: {
    id: 'us-consent-001',
    role: '법정대리인',
    action: '동의서를 검토하고 제출한다',
    benefit: '미성년자 또는 대리 동의가 필요한 고객의 회원가입 및 관련 업무가 적법하게 처리된다',
    priority: 'medium',
    status: 'ready',
    commandId: 'cmd-confirm-consent',
    commandName: 'ConfirmLegalGuardianConsent',
    acceptanceCriteria: [
      { kind: 'given', name: 'Aggregate: LegalGuardianConsent', description: null },
      { kind: 'when', name: 'Command: ConfirmLegalGuardianConsent', description: null },
    ],
  },
  changed: true,
  updatedAt: '2026-05-30T09:06:26.000+00:00',
}

// ── Helpers ────────────────────────────────────────────────────────────────

async function setupMocks(page: Page, historyData = MOCK_HISTORY_EMPTY) {
  await page.route('**/api/requirements/tree', (route) =>
    route.fulfill({ json: MOCK_TREE }),
  )
  await page.route('**/api/requirements/user-story/*/design-trace', (route) =>
    route.fulfill({ json: MOCK_DESIGN_TRACE }),
  )
  await page.route('**/api/requirements/clarification/flags', (route) =>
    route.fulfill({ json: { userStoryFlags: {} } }),
  )
  await page.route('**/api/requirements/clarification/clarity**', (route) =>
    route.fulfill({ json: null }),
  )
  await page.route('**/api/graph/traceability/**', (route) =>
    route.fulfill({ json: { rules: [] } }),
  )
  await page.route('**/api/requirements/user-story/*/history', (route) =>
    route.fulfill({ json: historyData }),
  )
}

const BASE_URL = process.env.APP_URL ?? 'http://localhost:5174'

async function navigateToRequirementsTab(page: Page) {
  await page.goto(BASE_URL)
  // Top nav bar has: Requirements | Event Modeling | Design | Aggregate | Code
  await page.getByRole('button', { name: 'Requirements' }).click()
  // Wait for the requirements tree to load (API mock)
  await page.waitForTimeout(800)
}

async function selectUserStory(page: Page) {
  // Expand the Epic node (click the collapse toggle)
  const epicRow = page.locator('.tree-node, .epic-node, li').filter({ hasText: '회원가입' }).first()
  if (await epicRow.isVisible({ timeout: 3000 }).catch(() => false)) {
    await epicRow.click()
    await page.waitForTimeout(300)
  }

  // Expand the Feature node
  const featRow = page.locator('li, .tree-node').filter({ hasText: '동의 처리' }).first()
  if (await featRow.isVisible({ timeout: 3000 }).catch(() => false)) {
    await featRow.click()
    await page.waitForTimeout(300)
  }

  // Click the UserStory
  const storyItem = page.locator('text=업무처리 동의 또는 확인을 한다').first()
  await storyItem.waitFor({ timeout: 8000 })
  await storyItem.click()
  // Wait for detail panel to load
  await page.waitForSelector('.us-detail', { timeout: 5000 }).catch(() => {})
  await page.waitForTimeout(600)
}

// ── Tests ──────────────────────────────────────────────────────────────────

test.describe('033 — 요구사항 편집 및 이력 조회', () => {
  test.use({ viewport: { width: 1400, height: 900 } })

  test('01 — 요구사항 개요 화면', async ({ page }) => {
    await setupMocks(page)
    await navigateToRequirementsTab(page)
    await selectUserStory(page)

    await page.screenshot({
      path: `${SHOTS_DIR}/01_overview.png`,
      fullPage: false,
    })
  })

  test('02 — 편집 탭 클릭 → 편집 폼', async ({ page }) => {
    await setupMocks(page)
    await navigateToRequirementsTab(page)
    await selectUserStory(page)

    // Click the 편집 tab
    const editTab = page.getByRole('button', { name: '편집' })
    await editTab.waitFor({ timeout: 5000 })
    await editTab.click()
    await page.waitForTimeout(400)

    await page.screenshot({
      path: `${SHOTS_DIR}/02_edit_form.png`,
      fullPage: false,
    })
  })

  test('03 — 저장 완료 → 성공 알림 + 개요 탭 복귀', async ({ page }) => {
    await setupMocks(page)

    // Mock the PATCH endpoint
    await page.route('**/api/requirements/user-story/us-consent-001', async (route) => {
      if (route.request().method() === 'PATCH') {
        route.fulfill({ json: MOCK_PATCH_RESPONSE })
      } else {
        route.continue()
      }
    })

    await navigateToRequirementsTab(page)
    await selectUserStory(page)

    // Click 편집 tab
    const editTab = page.getByRole('button', { name: '편집' })
    await editTab.waitFor({ timeout: 5000 })
    await editTab.click()
    await page.waitForTimeout(300)

    // Modify the action field
    const actionField = page.locator('textarea').first()
    await actionField.clear()
    await actionField.fill('동의서를 검토하고 제출한다')

    // Change status to ready
    const statusSelect = page.locator('select').nth(1)
    await statusSelect.selectOption('ready')

    await page.screenshot({
      path: `${SHOTS_DIR}/03_edit_filled.png`,
      fullPage: false,
    })

    // Click 저장
    await page.getByRole('button', { name: '저장' }).click()
    await page.waitForTimeout(600)

    await page.screenshot({
      path: `${SHOTS_DIR}/04_save_success.png`,
      fullPage: false,
    })
  })

  test('04 — 이력 탭 (이력 없음)', async ({ page }) => {
    await setupMocks(page, MOCK_HISTORY_EMPTY)
    await navigateToRequirementsTab(page)
    await selectUserStory(page)

    const historyTab = page.getByRole('button', { name: '이력' })
    await historyTab.waitFor({ timeout: 5000 })
    await historyTab.click()
    await page.waitForTimeout(400)

    await page.screenshot({
      path: `${SHOTS_DIR}/05_history_empty.png`,
      fullPage: false,
    })
  })

  test('05 — 이력 탭 (편집 이력 표시)', async ({ page }) => {
    await setupMocks(page, MOCK_HISTORY_WITH_ENTRY)
    await navigateToRequirementsTab(page)
    await selectUserStory(page)

    const historyTab = page.getByRole('button', { name: '이력' })
    await historyTab.waitFor({ timeout: 5000 })
    await historyTab.click()
    await page.waitForTimeout(600)

    await page.screenshot({
      path: `${SHOTS_DIR}/06_history_entries.png`,
      fullPage: false,
    })
  })

  test('06 — 충돌 감지 에러 메시지', async ({ page }) => {
    await setupMocks(page)

    // Mock PATCH to return 409
    await page.route('**/api/requirements/user-story/us-consent-001', async (route) => {
      if (route.request().method() === 'PATCH') {
        route.fulfill({
          status: 409,
          json: { detail: { code: 'EDIT_CONFLICT', latestUpdatedAt: '2026-05-30T09:00:00Z' } },
        })
      } else {
        route.continue()
      }
    })

    await navigateToRequirementsTab(page)
    await selectUserStory(page)

    const editTab = page.getByRole('button', { name: '편집' })
    await editTab.waitFor({ timeout: 5000 })
    await editTab.click()
    await page.waitForTimeout(300)

    // Try to save — triggers 409
    await page.getByRole('button', { name: '저장' }).click()
    await page.waitForTimeout(600)

    await page.screenshot({
      path: `${SHOTS_DIR}/07_conflict_error.png`,
      fullPage: false,
    })
  })
})
