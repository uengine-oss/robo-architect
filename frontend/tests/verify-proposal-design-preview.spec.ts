import { test, expect, Page } from '@playwright/test'

/**
 * 043-fix — Proposal Tactical Diff 의 Command/Event '열기' → Design 캔버스 미리보기.
 *
 * 요구사항(DoD) 증명:
 *  (A) 전술적 변경의 Command/Event '열기' 클릭 시 'Data' 가 아닌 'Design' 탭으로 전환된다.
 *  (B) Design 탭에서 해당 Command/Event 가 속한 Aggregate·BC + 연계 요소
 *      (Command/Event/ReadModel 등)를 캔버스에 함께 불러온다.
 *  (C) 대상 Command/Event 가 포커스(선택)되고 우측 Inspector 패널이 열린다.
 *
 * 데이터: 이미 Neo4j 에 적재된 PRO-001(그린필드 CREATE 제안). 새 데이터 적재 없음.
 *   - AGG-cart  ← CMD-add-to-cart  → EVT-item-added-to-cart
 *   - AGG-order ← CMD-place-order  → EVT-order-placed
 *   - RM-order-status (ReadModel), BC = EP-order
 *
 * 전제: Neo4j(7687) 가동 + 백엔드(8000) + 프런트(5173, playwright webServer) 가동.
 */

const BASE = 'http://localhost:5173'

async function openProposalDiff(page: Page) {
  await page.goto(BASE)
  await page.waitForLoadState('networkidle')

  // Proposals 탭
  const proposalsTab = page.locator('.top-bar__tab', { hasText: 'Proposals' }).first()
  await proposalsTab.click()
  await page.waitForTimeout(1000)

  // PRO-001 상세
  const item = page.locator('.proposal-item', { hasText: 'PRO-001' }).first()
  await item.waitFor({ timeout: 10000 })
  await item.click()
  await page.waitForTimeout(1000)

  // 상세는 기본 'diff' 탭 → IntentDecompositionView(전술적 변경) 표시
  await expect(page.locator('.diff-entry--tactical').first()).toBeVisible({ timeout: 10000 })
}

/** label(Command/Event)과 일치하는 전술 엔트리의 '열기' 버튼을 클릭한다. */
async function clickOpenForLabel(page: Page, label: string, occurrence = 0) {
  const entry = page
    .locator('.diff-entry--tactical')
    .filter({ has: page.locator('.diff-entry__label', { hasText: new RegExp(`^${label}$`) }) })
    .nth(occurrence)
  await entry.scrollIntoViewIfNeeded()
  const openBtn = entry.locator('.open-in-viewer')
  await expect(openBtn, `'${label}' 엔트리에 '열기' 버튼이 있어야 함`).toBeVisible()
  // 미매핑이면 비활성('열기 불가') — Command/Event 는 design 매핑이므로 활성이어야 함.
  await expect(openBtn).toHaveText(/열기$/)
  await openBtn.click()
}

async function assertDesignFocus(
  page: Page,
  opts: {
    target: string
    bc: string
    owningAggregate: string
    // 대상이 속한 Aggregate 와 '연계된'(같은 agg→command→event 체인) 요소들 — 진짜 관계 증명용.
    relatedChain: string[]
    // BC 단위로 함께 실리는 보조 요소(예: BC 소유 ReadModel) — 동일 BC 그래프에 포함됨.
    bcScoped?: string[]
    failed: { url: string; status: number }[]
  },
) {
  // (A) Design 탭 활성 (Data 아님). 한 번에 한 탭만 is-active 라 'Data' 는 /Design/ 에 안 걸림.
  const activeTab = page.locator('.top-bar__tab.is-active')
  await expect(activeTab, 'Design 탭으로 전환되어야 함(Data 아님)').toHaveText(/Design/, { timeout: 10000 })

  // (B-1) 소속 Aggregate + BC 가 캔버스에 표시된다 — 요구사항의 1차 디스플레이.
  await expect(
    page.locator(`.vue-flow__node[data-id="${opts.bc}"]`),
    `소속 BC '${opts.bc}' 가 캔버스에 표시되어야 함`,
  ).toBeVisible({ timeout: 10000 })
  await expect(
    page.locator(`.vue-flow__node[data-id="${opts.owningAggregate}"]`),
    `소속 Aggregate '${opts.owningAggregate}' 가 캔버스에 표시되어야 함`,
  ).toBeVisible({ timeout: 10000 })

  // (B-2) 해당 Aggregate 와 '연계된' Command/Event(agg→command→event 체인)가 함께 로드된다.
  for (const id of opts.relatedChain) {
    await expect(
      page.locator(`.vue-flow__node[data-id="${id}"]`),
      `소속 Aggregate 와 연계된 '${id}' 가 함께 로드되어야 함`,
    ).toBeVisible({ timeout: 10000 })
  }

  // (B-3) 관계(엣지)가 실제로 렌더되어 "어디에 위치/연결되는지"(J1)를 보여준다.
  await expect(
    page.locator('.vue-flow__edge').first(),
    '요소 간 관계(엣지)가 캔버스에 렌더되어야 함',
  ).toBeVisible({ timeout: 10000 })

  // (B-4, 보조) 같은 BC 그래프의 BC-소유 요소(ReadModel 등)도 함께 실린다.
  for (const id of opts.bcScoped || []) {
    await expect(
      page.locator(`.vue-flow__node[data-id="${id}"]`),
      `같은 BC 그래프의 '${id}' 도 함께 로드되어야 함`,
    ).toBeVisible({ timeout: 10000 })
  }

  // (C) 대상 노드 포커스(선택) + Inspector 열림.
  await expect(
    page.locator(`.vue-flow__node[data-id="${opts.target}"].es-node--selected`),
    `대상 '${opts.target}' 가 선택(포커스)되어야 함`,
  ).toBeVisible({ timeout: 10000 })
  await expect(
    page.locator('.inspector-wrapper'),
    '우측 Inspector 패널이 열려야 함',
  ).toBeVisible({ timeout: 10000 })
  // Inspector 가 '대상' 노드를 보여주는지(id 노출)로 포커스-인스펙터 일치 확인.
  await expect(
    page.locator('.inspector-wrapper'),
    `Inspector 가 대상 '${opts.target}' 를 보여주어야 함`,
  ).toContainText(opts.target, { timeout: 10000 })

  // 미리보기 배너(읽기 전용) 표시 확인
  await expect(page.locator('.preview-banner')).toBeVisible({ timeout: 5000 })

  expect(opts.failed.length, `500 에러: ${JSON.stringify(opts.failed)}`).toBe(0)
}

test.describe('043-fix Proposal Design 미리보기(Command/Event 열기)', () => {
  test('Command 열기 → Design 탭 + Aggregate/BC/연계요소 로드 + 포커스 + Inspector', async ({ page }) => {
    test.setTimeout(90_000)
    const failed: { url: string; status: number }[] = []
    page.on('response', (r) => {
      if (r.url().includes('/api/') && r.status() >= 500) failed.push({ url: r.url(), status: r.status() })
    })

    await openProposalDiff(page)
    await clickOpenForLabel(page, 'Command', 0) // CMD-add-to-cart
    await page.waitForTimeout(1500)
    await page.screenshot({ path: 'test-results/design-preview-command.png', fullPage: true })

    await assertDesignFocus(page, {
      target: 'CMD-add-to-cart',
      bc: 'EP-order',
      owningAggregate: 'AGG-cart',
      // AGG-cart 와 연계된 체인: 대상 Command + 그 Command 가 발행하는 Event.
      relatedChain: ['CMD-add-to-cart', 'EVT-item-added-to-cart'],
      // 같은 BC 그래프의 BC-소유 ReadModel 도 함께.
      bcScoped: ['RM-order-status'],
      failed,
    })

    // Inspector 가 대상 Command 를 보여주는지(제목/이름 노출) 보조 확인
    const inspector = page.locator('.inspector-wrapper')
    console.log('[Inspector]', (await inspector.innerText()).slice(0, 200))
  })

  test('Event 열기 → Design 탭 + 소속 Command/Aggregate 로드 + 포커스 + Inspector', async ({ page }) => {
    test.setTimeout(90_000)
    const failed: { url: string; status: number }[] = []
    page.on('response', (r) => {
      if (r.url().includes('/api/') && r.status() >= 500) failed.push({ url: r.url(), status: r.status() })
    })

    await openProposalDiff(page)
    await clickOpenForLabel(page, 'Event', 1) // EVT-order-placed (두 번째 Event)
    await page.waitForTimeout(1500)
    await page.screenshot({ path: 'test-results/design-preview-event.png', fullPage: true })

    await assertDesignFocus(page, {
      target: 'EVT-order-placed',
      bc: 'EP-order',
      owningAggregate: 'AGG-order',
      // EVT-order-placed 는 CMD-place-order 가 발행 → 둘 다 AGG-order 체인.
      relatedChain: ['CMD-place-order', 'EVT-order-placed'],
      failed,
    })
  })
})
