import { test, expect, Page } from '@playwright/test'

/**
 * Spec 030 — Requirements Clarification flow.
 *
 * Drives the new clarification UX end-to-end against a mocked backend:
 *  - flagged ambiguity badge renders on a user story (US-1)
 *  - right-click context menu on a user story → "🔍 이 요구사항 명확화"
 *  - clarification panel opens, SSE stream delivers questions_ready
 *  - first question + 추천 답변 + 옵션 표시
 *  - 추천 답변 수락 → /answer 호출 → before/after diff 표시
 *  - "적용" → /apply 호출 → 패널 진행
 *
 * No Neo4j / LLM / real backend process required.
 */

const TREE = {
  epics: [
    {
      id: 'bc-order',
      name: 'Order',
      features: [
        {
          id: 'feat-search',
          name: '주문 검색',
          description: '',
          source: 'llm',
          userStories: [
            {
              id: 'us-fast',
              role: '고객',
              action: '주문을 빠르게 검색하고 싶다',
              benefit: '결제 전 확인',
              priority: 'high',
              status: 'draft',
              commandId: null,
              commandName: null,
              acceptanceCriteria: [],
            },
            {
              id: 'us-clear',
              role: '고객',
              action: '주문 ID·고객 ID·주문일 4개 필터로 검색한다',
              benefit: '결제 전 확인',
              priority: 'high',
              status: 'approved',
              commandId: null,
              commandName: null,
              acceptanceCriteria: [
                { kind: 'then', name: 'p95 1초 이내 응답', description: null },
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

const SESSION_ID = 'sess-test-1'
const QUESTION_ID = 'q-test-1'

const SESSION_INITIAL = {
  sessionId: SESSION_ID,
  scope: { scopeType: 'user_story', scopeId: 'us-fast', scopeName: '고객: 주문을 빠르게 검색하고 싶다' },
  status: 'analyzing',
  progress: { phase: 'loading_scope', message: '범위 로드 중...', questionsTotal: 0, questionsAnswered: 0, currentQuestionIndex: 0 },
  questions: [],
  noAmbiguities: false,
  deferredNote: null,
  createdAt: '2026-05-25T00:00:00Z',
  endedAt: null,
}

const SESSION_AWAITING = {
  ...SESSION_INITIAL,
  status: 'awaiting_answers',
  progress: { phase: 'questions_ready', message: '질문 큐 준비됨', questionsTotal: 1, questionsAnswered: 0, currentQuestionIndex: 0 },
  questions: [
    {
      questionId: QUESTION_ID,
      order: 1,
      category: 'non_functional',
      priority: 1,
      questionType: 'closed',
      questionText: "'빠르게' 의 구체적 목표 응답 시간은?",
      referencedRequirementIds: ['us-fast'],
      recommendedAnswer: 'p95 1초 이내',
      options: [
        { key: 'a', label: 'p95 1초 이내' },
        { key: 'b', label: 'p95 3초 이내' },
      ],
      status: 'pending',
    },
  ],
}

const PROPOSAL = {
  questionId: QUESTION_ID,
  finalAnswer: 'p95 1초 이내',
  edits: [
    {
      requirementId: 'us-fast',
      baseUpdatedAt: '2026-05-25T00:00:00Z',
      before: {
        role: '고객', action: '주문을 빠르게 검색하고 싶다',
        benefit: '결제 전 확인', priority: 'high', status: 'draft', acceptanceCriteria: [],
      },
      after: {
        role: '고객', action: '주문을 p95 1초 이내에 검색',
        benefit: '결제 전 확인', priority: 'high', status: 'draft',
        acceptanceCriteria: ['검색은 p95 1초 이내에 응답한다'],
      },
      fieldsSummary: 'action sharpened + AC added',
    },
  ],
  needsDisambiguation: false,
  disambiguationPrompt: null,
}

const APPLY_RESP = {
  appliedRequirementIds: ['us-fast'],
  impactReportIds: ['rep-1'],
  conflict: null,
  noOp: false,
}

const FLAGS_INITIAL = {
  userStoryFlags: {
    'us-fast': {
      userStoryId: 'us-fast', sessionId: 'prev-session',
      questionIds: ['q-prev'], categories: ['non_functional'],
      scopeType: 'project', scopeId: '*',
      flaggedAt: '2026-05-25T00:00:00Z',
    },
  },
}

const FLAGS_EMPTY = { userStoryFlags: {} }

async function mockBackend(page: Page) {
  // Catch-all for any unmocked GETs (returns empty JSON).
  await page.route('**/api/**', (route) => route.fulfill({ json: {} }))

  await page.route('**/api/requirements/tree', (r) => r.fulfill({ json: TREE }))

  // Flags — first call returns 1 flagged story, subsequent calls return empty.
  let flagsCalls = 0
  await page.route('**/api/requirements/clarification/flags', (r) => {
    flagsCalls += 1
    r.fulfill({ json: flagsCalls === 1 ? FLAGS_INITIAL : FLAGS_EMPTY })
  })

  // Session POST.
  await page.route('**/api/requirements/clarification/sessions', (r) => {
    if (r.request().method() === 'POST') {
      r.fulfill({ json: SESSION_INITIAL })
    } else {
      r.fulfill({ json: {} })
    }
  })

  // SSE stream — single questions_ready event then end.
  await page.route(
    `**/api/requirements/clarification/sessions/${SESSION_ID}/stream`,
    (r) => {
      const body =
        `data: ${JSON.stringify({ phase: 'loading_scope', message: '범위 로드 중...', progress: 0.05 })}\n\n` +
        `data: ${JSON.stringify({ phase: 'scanning', message: '딥 에이전트 스캔 중...', progress: 0.3 })}\n\n` +
        `data: ${JSON.stringify({ phase: 'questions_ready', message: '질문 큐 준비됨', progress: 1.0, data: { questions: SESSION_AWAITING.questions, noAmbiguities: false, deferredNote: null } })}\n\n`
      r.fulfill({ contentType: 'text/event-stream', body })
    },
  )

  // Session snapshot — return awaiting_answers (questions visible).
  await page.route(
    `**/api/requirements/clarification/sessions/${SESSION_ID}`,
    (r) => {
      if (r.request().method() === 'GET') r.fulfill({ json: SESSION_AWAITING })
      else r.fulfill({ json: {} })
    },
  )

  // Answer.
  await page.route(
    `**/api/requirements/clarification/sessions/${SESSION_ID}/answer`,
    (r) => r.fulfill({ json: PROPOSAL }),
  )

  // Apply.
  await page.route(
    `**/api/requirements/clarification/sessions/${SESSION_ID}/apply`,
    (r) => r.fulfill({ json: APPLY_RESP }),
  )
}

test.use({ headless: false, viewport: { width: 1400, height: 900 } })

// Screenshots land next to the spec for visual proof / manual.
const SHOT = (name: string) => `../docs/clarification-manual/images/${name}`

test('Requirements clarification: right-click → scan → answer → apply', async ({ page }) => {
  await mockBackend(page)
  await page.goto('/')

  // ── Open the Requirements tab ──────────────────────────────────────────
  await page.getByRole('button', { name: 'Requirements' }).first().click()

  // Tree loaded — expand the BC + Feature so US rows are visible.
  await page.getByText('Order', { exact: true }).first().click()
  await page.getByText('주문 검색', { exact: true }).first().click()

  // ── Ambiguity badge shows on us-fast (flagged by previous session) ─────
  const fastRow = page.locator('.tree-node--us', { hasText: '주문을 빠르게 검색하고 싶다' })
  await expect(fastRow.locator('.ambig-badge')).toBeVisible()
  await expect(fastRow.locator('.ambig-badge')).toContainText('1')
  await page.screenshot({ path: SHOT('01-ambiguity-badge.png'), fullPage: false })

  // us-clear should NOT have an ambiguity badge.
  const clearRow = page.locator('.tree-node--us', { hasText: '4개 필터로 검색한다' })
  await expect(clearRow.locator('.ambig-badge')).toHaveCount(0)

  // ── Right-click on us-fast → context menu shows ────────────────────────
  await fastRow.locator('.us-row').first().click({ button: 'right' })
  await expect(page.locator('.ctx-menu')).toBeVisible()
  await expect(page.getByRole('button', { name: /이 요구사항 명확화/ })).toBeVisible()
  await page.screenshot({ path: SHOT('02-context-menu.png'), fullPage: false })

  // ── Click "이 요구사항 명확화" → clarification panel opens ──────────────
  await page.getByRole('button', { name: /이 요구사항 명확화/ }).click()

  // Wait for the panel to switch from analyzing → awaiting_answers + render Q1.
  await expect(page.locator('.cp-question')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.cp-question')).toContainText('빠르게')
  await expect(page.locator('.cp-pill').first()).toContainText('non_functional')

  // Recommended answer + closed options rendered.
  await expect(page.locator('.cp-recommended')).toContainText('p95 1초 이내')
  await expect(page.locator('.cp-btn--option')).toHaveCount(2)
  await page.screenshot({ path: SHOT('03-question-queue.png'), fullPage: false })

  // ── Accept the recommended answer → /answer call → proposal renders ────
  await page.getByRole('button', { name: '추천 답변 수락' }).click()

  // before/after diff appears.
  await expect(page.locator('.cp-proposal-header')).toBeVisible({ timeout: 5_000 })
  await expect(page.locator('.cp-diff-col').first()).toContainText('빠르게')
  await expect(page.locator('.cp-diff-col').nth(1)).toContainText('p95 1초 이내')
  await page.screenshot({ path: SHOT('04-edit-proposal.png'), fullPage: false })

  // ── "적용" → /apply call ───────────────────────────────────────────────
  await page.getByRole('button', { name: '적용' }).click()

  // Proposal collapses after apply (cleared).
  await expect(page.locator('.cp-proposal-header')).toBeHidden({ timeout: 5_000 })
  await page.screenshot({ path: SHOT('05-after-apply.png'), fullPage: false })
})
