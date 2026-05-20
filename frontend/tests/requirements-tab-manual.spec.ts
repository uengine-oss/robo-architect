import { test, expect } from '@playwright/test'

/**
 * Spec 026 — Requirements Tab feature walkthrough.
 *
 * Drives every Requirements-tab capability end to end against a mocked
 * backend and captures screenshots into docs/requirements-tab-manual/images/
 * for the user manual. No Neo4j / backend process required.
 */

const IMG = '../docs/requirements-tab-manual/images'

const TREE = {
  epics: [
    {
      id: 'bc-order',
      name: 'Order',
      features: [
        {
          id: 'feat-cancel',
          name: '주문 취소',
          description: '고객 주문 취소·환불',
          source: 'llm',
          userStories: [
            {
              id: 'us-1',
              role: 'customer',
              action: 'cancel my order',
              benefit: 'I can get a refund if I change my mind',
              priority: 'high',
              status: 'approved',
              commandId: 'cmd-cancel',
              commandName: 'CancelOrder',
              acceptanceCriteria: [
                { kind: 'given', name: 'Command: CancelOrder', description: '주문 취소 명령이 실행됨' },
                { kind: 'when', name: 'Aggregate: Order', description: 'Order Aggregate가 명령을 처리함' },
                { kind: 'then', name: 'Event: OrderCancelled', description: '주문 취소 이벤트가 발생함' },
              ],
            },
            {
              id: 'us-2',
              role: 'customer',
              action: 'see my cancellation status',
              benefit: 'I know the refund progress',
              priority: 'medium',
              status: 'draft',
              commandId: null,
              commandName: null,
              acceptanceCriteria: [],
            },
          ],
        },
        {
          id: 'feat-place',
          name: '주문 생성',
          description: '',
          source: 'llm',
          userStories: [
            {
              id: 'us-3',
              role: 'customer',
              action: 'place an order',
              benefit: 'I can buy products',
              priority: 'high',
              status: 'approved',
              commandId: 'cmd-place',
              commandName: 'PlaceOrder',
              acceptanceCriteria: [
                { kind: 'given', name: 'Command: PlaceOrder', description: null },
              ],
            },
          ],
        },
      ],
      unassignedFeature: {
        id: '__unassigned__bc-order',
        name: '미분류',
        source: 'manual',
        userStories: [
          {
            id: 'us-4',
            role: 'customer',
            action: 'rate a delivered order',
            benefit: 'I can share feedback',
            priority: 'low',
            status: 'draft',
            commandId: null,
            commandName: null,
            acceptanceCriteria: [],
          },
        ],
      },
    },
    {
      id: 'bc-payment',
      name: 'Payment',
      features: [
        {
          id: 'feat-refund',
          name: '환불 처리',
          description: '',
          source: 'llm',
          userStories: [
            {
              id: 'us-5',
              role: 'system',
              action: 'process a refund',
              benefit: 'the customer gets their money back',
              priority: 'high',
              status: 'approved',
              commandId: 'cmd-refund',
              commandName: 'ProcessRefund',
              acceptanceCriteria: [
                { kind: 'then', name: 'Event: RefundProcessed', description: null },
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

// Design trace includes the UI wireframe attached to the command.
// `displayName` is the logical (localized) label shown on the canvas.
const TRACE = {
  rootCommandId: 'cmd-cancel',
  nodes: [
    { id: 'ui-cancel', name: 'CancelOrderScreen', displayName: '주문취소 화면', type: 'UI', properties: [] },
    {
      id: 'agg-order', name: 'Order', displayName: '주문', type: 'Aggregate',
      properties: [
        { id: 'ap1', name: 'id', type: 'UUID', isKey: true },
        { id: 'ap2', name: 'status', type: 'String' },
        { id: 'ap3', name: 'totalAmount', type: 'Decimal' },
      ],
    },
    {
      id: 'cmd-cancel', name: 'CancelOrder', displayName: '주문 취소', type: 'Command', actor: 'customer',
      properties: [
        { id: 'cp1', name: 'orderId', type: 'UUID', isKey: true },
        { id: 'cp2', name: 'reason', type: 'String' },
      ],
    },
    {
      id: 'evt-cancelled', name: 'OrderCancelled', displayName: '주문 취소됨', type: 'Event',
      properties: [
        { id: 'ep1', name: 'orderId', type: 'UUID' },
        { id: 'ep2', name: 'cancelledAt', type: 'DateTime' },
      ],
    },
    { id: 'pol-refund', name: 'RefundOnOrderCancellation', displayName: '취소 시 환불', type: 'Policy', properties: [] },
    {
      id: 'cmd-refund', name: 'ProcessRefund', displayName: '환불 처리', type: 'Command', actor: 'system',
      properties: [{ id: 'rp1', name: 'orderId', type: 'UUID', isKey: true }],
    },
    { id: 'agg-refund', name: 'Refund', displayName: '환불', type: 'Aggregate', properties: [] },
  ],
  relationships: [
    { source: 'ui-cancel', target: 'cmd-cancel', type: 'ATTACHED_TO' },
    { source: 'agg-order', target: 'cmd-cancel', type: 'HAS_COMMAND' },
    { source: 'cmd-cancel', target: 'evt-cancelled', type: 'EMITS' },
    { source: 'evt-cancelled', target: 'pol-refund', type: 'TRIGGERS' },
    { source: 'pol-refund', target: 'cmd-refund', type: 'INVOKES' },
    { source: 'agg-refund', target: 'cmd-refund', type: 'HAS_COMMAND' },
  ],
  empty: false,
}

const PROPOSALS = {
  proposals: [
    {
      role: 'customer',
      action: 'apply a discount coupon at checkout',
      benefit: 'I can pay less',
      suggestedBoundedContextId: 'bc-order',
      suggestedFeatureId: 'feat-place',
      suggestedFeatureName: '주문 생성',
      confidence: 0.82,
      unclear: false,
    },
  ],
  warnings: [
    { code: 'feature_unresolved', message: "'쿠폰' Feature가 없어 기존 Feature로 분류했습니다." },
  ],
}

const IMPACT_REPORT = {
  id: 'report-1',
  status: 'done',
  trigger: 'add',
  findings: [
    {
      kind: 'duplicate',
      severity: 'warning',
      message: '기존 User Story와 중복 가능성: "customer: place an order"',
      relatedNodeIds: ['us-3'],
    },
  ],
  createdAt: '2026-05-17T00:00:00Z',
}

// expand-with-bc node details, keyed by node id — InspectorPanel fetches these.
const NODE_DETAILS: Record<string, any> = {
  'cmd-cancel': {
    id: 'cmd-cancel',
    name: 'CancelOrder',
    type: 'Command',
    description: '고객이 주문을 취소하는 명령',
    actor: 'customer',
    key: 'order.order.cancel-order',
  },
  'ui-cancel': {
    id: 'ui-cancel',
    name: 'CancelOrder 화면',
    type: 'UI',
    description: '주문번호 입력 후 취소 사유를 선택하는 화면',
    key: 'ui.command.cmd-cancel',
  },
}

test('Requirements tab — full feature walkthrough with screenshots', async ({ page, context }) => {
  // ── Mock the backend (catch-all first, specifics override) ─────────────
  await context.route('**/api/graph/**', (r) =>
    r.fulfill({ json: { nodes: [], relationships: [], properties: [] } }),
  )
  await context.route('**/api/contexts**', (r) => r.fulfill({ json: [] }))
  await context.route('**/api/user-stories/unassigned**', (r) => r.fulfill({ json: [] }))
  await context.route('**/api/graph/stats**', (r) =>
    r.fulfill({ json: { total: 12, by_type: { UserStory: 5, BoundedContext: 2 } } }),
  )
  await context.route('**/api/graph/expand-with-bc/**', (r) => {
    const id = decodeURIComponent(r.request().url().split('/').pop()!.split('?')[0])
    const node = NODE_DETAILS[id] || { id, name: id, type: 'Command' }
    r.fulfill({ json: { nodes: [node], relationships: [], bcContext: { id: 'bc-order', name: 'Order' } } })
  })
  await context.route('**/api/requirements/tree', (r) => r.fulfill({ json: TREE }))
  await context.route('**/api/requirements/user-story/*/design-trace*', (r) =>
    r.fulfill({ json: TRACE }),
  )
  await context.route('**/api/requirements/user-story/propose', (r) =>
    r.fulfill({ json: PROPOSALS }),
  )
  await context.route('**/api/requirements/user-story/confirm', (r) =>
    r.fulfill({
      json: { userStory: TREE.epics[0].features[0].userStories[0], impactReportId: 'report-1' },
    }),
  )
  await context.route('**/api/requirements/impact-report/report-1', (r) =>
    r.fulfill({ json: IMPACT_REPORT }),
  )

  // ── US1: open the Requirements tab ─────────────────────────────────────
  await page.goto('/')
  await page.getByRole('button', { name: 'Requirements' }).first().click()
  await expect(page.getByText('Order', { exact: true })).toBeVisible()
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${IMG}/01-tab-overview.png`, fullPage: true })

  // ── US1: drill down Epic → Feature → User Story → Acceptance Criteria ──
  await page.getByText('Order', { exact: true }).click()
  await page.getByText('주문 취소', { exact: true }).click()
  await page.getByText('Payment', { exact: true }).click()
  await page.getByText('환불 처리', { exact: true }).click()
  const us1Caret = page
    .locator('.tree-node--us', { hasText: 'customer: cancel my order' })
    .locator('.caret')
  await us1Caret.click()
  await expect(page.getByText('Aggregate: Order').first()).toBeVisible()
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${IMG}/02-tree-drilldown.png`, fullPage: true })

  // ── US1: select a user story → detail panel ───────────────────────────
  await page.getByText('customer: cancel my order').click()
  await expect(page.getByText('I want cancel my order')).toBeVisible()
  await page.waitForTimeout(900)
  await page.screenshot({ path: `${IMG}/03-user-story-detail.png`, fullPage: true })

  // ── US2: design-trace canvas (incl. the attached UI wireframe) ────────
  await expect(page.locator('.trace-canvas')).toBeVisible()
  await expect(page.locator('.vue-flow__node[data-id="ui-cancel"]')).toBeVisible()
  await page.waitForTimeout(800)
  await page.locator('.req-detail-pane__canvas').screenshot({
    path: `${IMG}/04-design-trace.png`,
  })

  // ── US2: click a canvas node → property inspector opens on the right ──
  await page.locator('.vue-flow__node[data-id="cmd-cancel"]').click()
  await expect(page.locator('.req-inspector-pane')).toBeVisible()
  await page.waitForTimeout(900)
  await page.screenshot({ path: `${IMG}/05-canvas-node-inspector.png`, fullPage: true })

  // ── US3: Add Requirement dialog — natural-language mode ───────────────
  await page.getByRole('button', { name: '+ 요구사항 추가' }).click()
  await expect(page.getByRole('heading', { name: '요구사항 추가' })).toBeVisible()
  await page.locator('.nl-input').fill('체크아웃 시 할인 쿠폰을 적용할 수 있어야 한다.')
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${IMG}/06-add-natural-language.png`, fullPage: true })

  // ── US3: propose → review proposals ────────────────────────────────────
  await page.getByRole('button', { name: '분석' }).click()
  await expect(page.locator('.proposal')).toBeVisible()
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${IMG}/07-add-proposals.png`, fullPage: true })

  // ── US3: manual input mode ─────────────────────────────────────────────
  await page.getByRole('button', { name: '수동 입력' }).click()
  await page.locator('.dialog__body input').first().fill('회원')
  await page.locator('.dialog__body input').nth(1).fill('비밀번호를 재설정한다')
  await page.waitForTimeout(200)
  await page.screenshot({ path: `${IMG}/08-add-manual.png`, fullPage: true })

  // ── US5: impact report — confirm a proposal triggers analysis ─────────
  await page.getByRole('button', { name: '자연어 입력' }).click()
  await page.getByRole('button', { name: '분석' }).click()
  await expect(page.locator('.proposal')).toBeVisible()
  await page.locator('.proposal').getByRole('button', { name: '추가' }).click()
  await expect(page.locator('.impact-panel')).toBeVisible()
  await expect(page.getByText('중복 가능성', { exact: false })).toBeVisible()
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${IMG}/09-impact-report.png`, fullPage: true })

  // ── US3/US6: document upload modal (incremental upsert) ───────────────
  await page.locator('.req-toolbar').getByRole('button', { name: '문서 업로드' }).click()
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${IMG}/10-document-upload.png`, fullPage: true })
})
