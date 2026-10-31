import { test, expect, Page } from '@playwright/test'
import { shotDir } from './helpers/shots'
import { gotoView, railItem } from './helpers/nav'

/**
 * Spec 027 — aggregate-invariants end-to-end test.
 *
 * Drives the real navigator tree + right-side property panel with the backend
 * mocked at the network boundary (no Neo4j needed). Also captures the
 * screenshots embedded in specs/027-aggregate-invariants/manual/USER-GUIDE.md.
 *
 * Covers: S1 (Invariants group in the design tree), S2 (create + edit in the
 * property panel), DR-1 (invariant GWT hides "When"), DR-2/DR-3 (Then exception
 * + aggregate exception catalog), US2 (shared Command references).
 */

// Relative to the Playwright cwd (the `frontend/` directory).
// 문서 그림은 UPDATE_MANUAL_SHOTS=1 일 때만 덮어쓴다(helpers/shots).
const IMG_DIR = shotDir('../specs/027-aggregate-invariants/manual/images', 'aggregate-invariants')
const IMG = (name: string) => `${IMG_DIR}/${name}`

const CONTEXTS = [
  { id: 'bc-1', name: 'Order', domainType: 'Core Domain', aggregateCount: 1, userStoryCount: 0 },
]

const FULL_TREE = {
  id: 'bc-1',
  name: 'Order',
  type: 'BoundedContext',
  domainType: 'Core Domain',
  userStories: [],
  aggregates: [
    {
      id: 'agg-1',
      name: 'Order',
      type: 'Aggregate',
      rootEntity: 'Order',
      invariants: [],
      enumerations: [],
      valueObjects: [],
      exceptions: [],
      commands: [{ id: 'cmd-1', name: 'PlaceOrder', type: 'Command', events: [], properties: [] }],
      events: [],
      properties: [],
    },
  ],
  policies: [],
  readmodels: [],
  uis: [],
}

const INVARIANT = {
  id: 'inv-1',
  key: 'order.order.invariant.order-total-positive-abc',
  name: '주문 총액 양수',
  declaration: '주문 총액은 항상 0보다 커야 한다',
  description: null as string | null,
  source: 'manual',
  seq: 1,
  aggregateId: 'agg-1',
  aggregateName: 'Order',
  referencedConditions: [] as any[],
  ownGwtParentId: null as string | null,
  isSpecified: false,
}

/** Register every mocked route the Invariants UI touches. */
async function mockBackend(page: Page) {
  // Generic fallback so unrelated /api calls (Design canvas, etc.) stay quiet.
  await page.route('**/api/**', (route) => route.fulfill({ json: {} }))

  await page.route('**/api/user-stories/unassigned', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/contexts', (route) => route.fulfill({ json: CONTEXTS }))
  await page.route('**/api/contexts/bc-1/full-tree', (route) => route.fulfill({ json: FULL_TREE }))

  await page.route('**/api/aggregates/agg-1/invariants', (route) => {
    if (route.request().method() === 'POST') {
      return route.fulfill({ json: INVARIANT })
    }
    return route.fulfill({
      json: {
        aggregateId: 'agg-1',
        invariants: [
          {
            id: 'inv-1',
            key: INVARIANT.key,
            name: INVARIANT.name,
            declaration: INVARIANT.declaration,
            source: 'manual',
            seq: 1,
            isSpecified: false,
            referencedCommandCount: 0,
            type: 'Invariant',
          },
        ],
      },
    })
  })
  await page.route('**/api/invariants/inv-1', (route) => route.fulfill({ json: INVARIANT }))
  await page.route('**/api/invariants/inv-1/reference-candidates', (route) =>
    route.fulfill({
      json: { candidates: [{ commandId: 'cmd-1', commandName: 'PlaceOrder', hasGwt: false, alreadyReferenced: false }] },
    }),
  )
  await page.route('**/api/graph/gwt/Invariant/inv-1', (route) => route.fulfill({ json: { gwt: null } }))
  await page.route('**/api/graph/gwt/upsert', (route) =>
    route.fulfill({ json: { success: true, gwt: {} } }),
  )
  await page.route('**/api/aggregates/agg-1/exceptions', (route) =>
    route.fulfill({ json: { aggregateId: 'agg-1', exceptions: [] } }),
  )
}

/** Drill the navigator tree down to the expanded Invariants group. */
async function openInvariantsGroup(page: Page, { viaDesign = true } = {}) {
  await page.goto('/')
  // 시작 화면이 프로포절로 바뀌었다(0cefc7ac). 속성 패널(InspectorPanel)은 설계 화면에 있으므로 먼저 설계로 간다.
  // 프로포절 화면에도 같은 트리가 보인다 — viaDesign:false 는 그 트리에서 바로 시작한다(아래 BUG 시험).
  if (viaDesign) await gotoView(page, '설계')
  await page.getByText('Order (core)', { exact: true }).click()       // expand BC
  await page.getByText('Order', { exact: true }).first().click()       // expand Aggregate
  const group = page.getByText('Invariants', { exact: true })
  await expect(group).toBeVisible()
  await group.click()                                                  // expand the group
}

test('S1 — the Invariants group is a drill-down node under the Aggregate', async ({ page }) => {
  await mockBackend(page)
  await openInvariantsGroup(page)

  const inv = page.getByText('주문 총액은 항상 0보다 커야 한다')
  await expect(inv).toBeVisible()
  await page.screenshot({ path: IMG('01-design-tree-invariants.png'), fullPage: false })
})

test('S2 + DR-4 — opening an Invariant shows the editor in the right property panel', async ({ page }) => {
  await mockBackend(page)
  await openInvariantsGroup(page)

  await page.getByText('주문 총액은 항상 0보다 커야 한다').dblclick()

  // The editor renders inside the right-side InspectorPanel.
  await expect(page.getByText('선언문', { exact: true })).toBeVisible()
  await expect(page.getByText('선언만 — 세부 조건 없음')).toBeVisible()
  await expect(page.getByText('커맨드 인수조건 공유 참조 (0)')).toBeVisible()
  await page.screenshot({ path: IMG('02-invariant-editor-panel.png'), fullPage: false })
})

test('DR-1 + DR-2 — the invariant GWT editor hides "When" and offers an Exception', async ({ page }) => {
  await mockBackend(page)
  await openInvariantsGroup(page)
  await page.getByText('주문 총액은 항상 0보다 커야 한다').dblclick()
  await expect(page.getByText('선언문', { exact: true })).toBeVisible()

  // Open the invariant-owned GWT editor.
  await page.getByText('인베리언트 전용 조건', { exact: false }).click()

  // Given + Then are present; When is hidden for an invariant; Exception is offered.
  await expect(page.getByText('Given', { exact: true })).toBeVisible()
  await expect(page.getByText('Then', { exact: true })).toBeVisible()
  await expect(page.getByText('Exception', { exact: true })).toBeVisible()
  await expect(page.getByText('When', { exact: true })).toHaveCount(0)
  await page.getByText('Exception', { exact: true }).scrollIntoViewIfNeeded()
  await page.screenshot({ path: IMG('03-gwt-editor-no-when.png'), fullPage: false })
})

// 제품 결함(보고됨) — 설계 화면을 아직 한 번도 열지 않은 상태(시작 화면 = 프로포절)에서 트리의 Invariant 를
// 더블클릭하면 화면은 설계로 바뀌지만 속성 패널이 열리지 않는다. TreeNode.handleDoubleClick 이
// activeTab='Design' 과 같은 틱에 inspectorRequest.request() 를 보내는데, CanvasWorkspace 는 그때 아직
// 마운트 전이고 requestId 를 보는 watch 가 immediate 가 아니라 이 첫 요청을 놓친다(UserStory 더블클릭 ·
// ImplementationFile 클릭도 같은 경로). 고쳐지면 이 시험이 '예상 밖 통과'로 알려 주므로 그때 test.fail 을 걷는다.
test('BUG — Invariant double-click from the start view opens the editor on the first Design visit', async ({ page }) => {
  test.fail(true, 'CanvasWorkspace drops an inspectorRequest made before it mounts (watch not immediate)')
  await mockBackend(page)
  await openInvariantsGroup(page, { viaDesign: false })
  await page.getByText('주문 총액은 항상 0보다 커야 한다').dblclick()
  await expect(railItem(page, '설계')).toHaveClass(/is-active/) // 화면 전환은 된다
  await expect(page.getByText('선언문', { exact: true })).toBeVisible() // 편집기가 안 열린다 ← 결함
})
