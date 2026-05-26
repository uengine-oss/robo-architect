import { test, expect, Page } from '@playwright/test'

/**
 * Spec 030 — Requirements Clarification flow (tab-based UX).
 *
 * Drives the new clarification UX end-to-end against a mocked backend:
 *  - ambiguity badge renders on a user story (us-fast)
 *  - clicking the user story opens the detail panel
 *  - the detail panel has a "명확화" tab with a badge counter
 *  - opening that tab fires a single-story clarification session
 *  - SSE stream delivers questions_ready, queue renders inside the tab
 *  - "추천 답변 수락" → /answer → before/after diff
 *  - "적용" → /apply → proposal collapses
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

const CLARITY_BEFORE = {
  scope: { scopeType: 'project', scopeId: '*', scopeName: '전체 프로젝트' },
  totalUserStories: 2,
  flaggedUserStories: 1,
  resolvedUserStories: 0,
  overallScore: 0.85,
  scores: [
    { category: 'functional_scope',         score: 1.0,  flaggedCount: 0, resolvedCount: 0 },
    { category: 'domain_data_model',        score: 1.0,  flaggedCount: 0, resolvedCount: 0 },
    { category: 'interaction_flow',         score: 1.0,  flaggedCount: 0, resolvedCount: 0 },
    { category: 'non_functional',           score: 0.5,  flaggedCount: 1, resolvedCount: 0 },
    { category: 'integration_dependencies', score: 1.0,  flaggedCount: 0, resolvedCount: 0 },
    { category: 'edge_cases',               score: 1.0,  flaggedCount: 0, resolvedCount: 0 },
    { category: 'constraints_tradeoffs',    score: 1.0,  flaggedCount: 0, resolvedCount: 0 },
    { category: 'terminology',              score: 1.0,  flaggedCount: 0, resolvedCount: 0 },
    { category: 'completion_signals',       score: 1.0,  flaggedCount: 0, resolvedCount: 0 },
    { category: 'misc_placeholders',        score: 1.0,  flaggedCount: 0, resolvedCount: 0 },
  ],
}

async function mockBackend(page: Page) {
  // Catch-all for any unmocked GETs (returns empty JSON).
  await page.route('**/api/**', (route) => route.fulfill({ json: {} }))

  await page.route('**/api/requirements/tree', (r) => r.fulfill({ json: TREE }))

  // Flags — return FLAGS_INITIAL until /apply has been called, then empty.
  let applyCalled = false
  await page.route('**/api/requirements/clarification/flags', (r) => {
    r.fulfill({ json: applyCalled ? FLAGS_EMPTY : FLAGS_INITIAL })
  })

  // Session POST.
  await page.route('**/api/requirements/clarification/sessions', (r) => {
    if (r.request().method() === 'POST') r.fulfill({ json: SESSION_INITIAL })
    else r.fulfill({ json: {} })
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

  // Session snapshot.
  await page.route(
    `**/api/requirements/clarification/sessions/${SESSION_ID}`,
    (r) => {
      if (r.request().method() === 'GET') r.fulfill({ json: SESSION_AWAITING })
      else r.fulfill({ json: {} })
    },
  )

  await page.route(
    `**/api/requirements/clarification/sessions/${SESSION_ID}/answer`,
    (r) => r.fulfill({ json: PROPOSAL }),
  )

  await page.route(
    `**/api/requirements/clarification/sessions/${SESSION_ID}/apply`,
    (r) => { applyCalled = true; r.fulfill({ json: APPLY_RESP }) },
  )

  // Clarity radar — initial 85% (1 of 2 US flagged on non_functional),
  // after apply jumps to 100%.
  await page.route('**/api/requirements/clarification/clarity*', (r) => {
    if (applyCalled) {
      const clean = {
        ...CLARITY_BEFORE,
        flaggedUserStories: 0,
        overallScore: 1.0,
        scores: CLARITY_BEFORE.scores.map((s) => ({ ...s, score: 1.0, flaggedCount: 0 })),
      }
      r.fulfill({ json: clean })
    } else {
      r.fulfill({ json: CLARITY_BEFORE })
    }
  })
}

test.use({ headless: false, viewport: { width: 1500, height: 900 } })

const SHOT = (name: string) => `../specs/030-requirements-clarify-agent/manual/images/${name}`

test('Requirements clarification: select → tab → scan → answer → apply', async ({ page }) => {
  await mockBackend(page)
  await page.goto('/')

  // ── Open the Requirements tab ──────────────────────────────────────────
  await page.getByRole('button', { name: 'Requirements' }).first().click()

  // Tree loaded — expand BC + Feature so US rows are visible.
  await page.getByText('Order', { exact: true }).first().click()
  await page.getByText('주문 검색', { exact: true }).first().click()

  // ── Ambiguity badge on us-fast row only ────────────────────────────────
  const fastRow = page.locator('.tree-node--us', { hasText: '주문을 빠르게 검색하고 싶다' })
  await expect(fastRow.locator('.ambig-badge')).toBeVisible()
  await expect(fastRow.locator('.ambig-badge')).toContainText('1')

  const clearRow = page.locator('.tree-node--us', { hasText: '4개 필터로 검색한다' })
  await expect(clearRow.locator('.ambig-badge')).toHaveCount(0)

  // ── Radar dashboard appears in the empty-state of the detail pane ─────
  // (No user story is selected yet, so the right pane shows the radar.)
  const radar = page.locator('.clarity-radar')
  await expect(radar).toBeVisible({ timeout: 5_000 })
  await expect(radar.locator('.cr-pct')).toContainText('85%')
  await expect(radar.locator('polygon')).toHaveCount(1)
  // 10 axis labels — one per SpecKit clarify category.
  await expect(radar.locator('.cr-axis-label')).toHaveCount(10)
  await page.screenshot({ path: SHOT('00-clarity-radar.png'), fullPage: false })
  await page.screenshot({ path: SHOT('01-tree-badge.png'), fullPage: false })

  // ── Click us-fast → detail panel opens; flagged story auto-jumps to the
  //    "명확화" tab so the user immediately sees what needs attention. ───
  await fastRow.locator('.us-row').first().click()

  // Tab bar visible with both tabs (scoped to the detail tabbar — the
  // toolbar's "요구사항 명확화 (전체)" button shares text otherwise).
  const tabbar = page.locator('.us-tabs')
  await expect(tabbar.getByRole('button', { name: '개요' })).toBeVisible()
  const clarifTab = tabbar.getByRole('button', { name: /명확화/ })
  await expect(clarifTab).toBeVisible()

  // The clarification tab carries the same ❓ counter as the tree badge.
  await expect(clarifTab.locator('.tab-badge')).toContainText('1')

  // Wait for the agent to deliver the queue (SSE + snapshot refresh).
  await expect(page.locator('.cp-question')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.cp-question')).toContainText('빠르게')
  await expect(page.locator('.cp-pill').first()).toContainText('non_functional')
  await expect(page.locator('.cp-recommended')).toContainText('p95 1초 이내')
  await expect(page.locator('.cp-btn--option')).toHaveCount(2)
  await page.screenshot({ path: SHOT('02-detail-tab-question.png'), fullPage: false })

  // ── Switch to 개요 to show coexistence + come back ─────────────────────
  await tabbar.getByRole('button', { name: '개요' }).click()
  await expect(page.locator('.us-detail__statement')).toBeVisible()
  await page.screenshot({ path: SHOT('03-overview-tab.png'), fullPage: false })
  await clarifTab.click()
  await expect(page.locator('.cp-question')).toBeVisible()

  // ── Accept the recommended answer → /answer → proposal renders ─────────
  await page.getByRole('button', { name: '추천 답변 수락' }).click()
  await expect(page.locator('.cp-proposal-header')).toBeVisible({ timeout: 5_000 })
  await expect(page.locator('.cp-diff-col').first()).toContainText('빠르게')
  await expect(page.locator('.cp-diff-col').nth(1)).toContainText('p95 1초 이내')
  await page.screenshot({ path: SHOT('04-edit-proposal.png'), fullPage: false })

  // ── "적용" → /apply → proposal collapses, badge clears ─────────────────
  await page.getByRole('button', { name: '적용' }).click()
  await expect(page.locator('.cp-proposal-header')).toBeHidden({ timeout: 5_000 })

  // After apply, the second /flags call returns empty → tab badge gone.
  await expect(clarifTab.locator('.tab-badge')).toHaveCount(0, { timeout: 5_000 })
  await page.screenshot({ path: SHOT('05-after-apply.png'), fullPage: false })
})
