/**
 * 프로포절 화면 — 실제 컴포넌트를 vite 로 띄우고 store 를 가짜 API 로 채워 본다.
 *
 * 백엔드·로그인 없이 돈다: 이 spec 이 vite dev 서버를 직접 열고(`tests/harness/`),
 * `/api/**` 는 page.route 로 가짜 응답을 준다. 그래서 단위 설정(`playwright.unit.config.ts`)
 * 에서 돈다 — 실패하면 원인은 화면 로직이지 환경이 아니다.
 */
import { expect, test, type Page } from '@playwright/test'
import { createServer, type ViteDevServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
let server: ViteDevServer
let base = ''

test.describe.configure({ mode: 'serial', timeout: 90_000 })
// 화면 글자는 브라우저 언어를 따른다 — 앱 시험과 같이 한국어 화면을 기준으로 잰다.
test.use({ locale: 'ko-KR' })

test.beforeAll(async () => {
  // 앱 vite.config 는 open-pencil·federation 까지 끌어온다 — 이 화면엔 필요 없고, 워크트리엔
  // open-pencil 이 없어 의존성 스캔이 깨진다. 프로포절 화면이 쓰는 것만 둔 최소 설정으로 띄운다.
  server = await createServer({
    root: ROOT,
    configFile: false,
    plugins: [vue()],
    resolve: { alias: { '@': path.join(ROOT, 'src') } },
    optimizeDeps: { entries: ['tests/harness/proposals.html'] },
    server: { port: 0, strictPort: false, hmr: false },
    logLevel: 'error',
  })
  await server.listen()
  const addr = server.httpServer?.address()
  const port = typeof addr === 'object' && addr ? addr.port : 0
  base = `http://localhost:${port}`
})

test.afterAll(async () => { await server?.close() })

type Proposal = Record<string, unknown> & { id: string; status: string }

function proposal(id: string, status: string, extra: Record<string, unknown> = {}): Proposal {
  return {
    id, status, title: `${id} 제목`, author: 'tester', createdAt: '2026-11-18T00:00:00Z',
    originalPrompt: '프롬프트', decompositionMode: 'SIMPLIFIED',
    strategicDiff: { epics: [{ tempId: 'E1', nodeTitle: '에픽' }] },
    ...extra,
  }
}

async function mockApi(page: Page, proposals: Proposal[], opts: { onDelete?: (body: unknown) => void } = {}) {
  await page.route('**/api/**', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const p = url.pathname
    if ((p === '/api/proposals' || p === '/api/proposals/') && req.method() === 'GET') {
      return route.fulfill({ json: proposals })
    }
    const m = p.match(/^\/api\/proposals\/([^/]+)$/)
    if (m && req.method() === 'GET') {
      const found = proposals.find((x) => x.id === m[1])
      return found ? route.fulfill({ json: found }) : route.fulfill({ status: 404, json: { detail: 'not found' } })
    }
    if (m && req.method() === 'DELETE') {
      opts.onDelete?.(req.postDataJSON())
      return route.fulfill({ json: { ok: true } })
    }
    // 하위 화면(Plan·Sandbox 등)이 부르는 나머지 — 빈 응답
    return route.fulfill({ json: {} })
  })
}

async function open(page: Page, query = '') {
  page.on('pageerror', (e) => console.log('[pageerror]', e.message))
  page.on('console', (m) => { if (m.type() === 'error') console.log('[console]', m.text()) })
  await page.goto(`${base}/tests/harness/proposals.html${query}`)
  await page.waitForFunction(() => (window as any).__harnessReady === true)
}

test.describe('A-2 삭제 확인 입력', () => {
  test('모달이 뜨면 입력칸에 focus 가 가고, 바로 타이핑하면 삭제가 켜진다', async ({ page }) => {
    const deleted: unknown[] = []
    await mockApi(page, [proposal('PRO-001', 'DRAFT')], { onDelete: (b) => deleted.push(b) })
    await open(page)
    await page.locator('.proposal-item').first().hover()
    await page.locator('.proposal-item__delete').first().click()

    const input = page.getByTestId('delete-confirm-input')
    await expect(input).toBeFocused()
    const btn = page.getByTestId('delete-confirm-btn')
    await expect(btn).toBeDisabled()

    // 칸을 클릭하지 않고 바로 친다 — 고치기 전엔 focus 가 🗑 단추에 남아 아무 데도 안 들어갔다.
    await page.keyboard.type('PRO-00')
    await expect(btn).toBeDisabled()
    await page.keyboard.type('1')
    await expect(btn).toBeEnabled()
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('delete-confirm-input')).toHaveCount(0)
    expect(deleted).toEqual([{ confirmId: 'PRO-001' }])
  })

  test('IME 조합 중인 글자도 값에 따라오고, 조합이 끝나면 맞춰진다', async ({ page }) => {
    await mockApi(page, [proposal('PRO-001', 'DRAFT')])
    await open(page)
    await page.locator('.proposal-item__delete').first().click({ force: true })
    const input = page.getByTestId('delete-confirm-input')
    await expect(input).toBeFocused()
    const cdp = await page.context().newCDPSession(page)
    await cdp.send('Input.insertText', { text: 'PRO-00' })
    // 마지막 글자가 아직 조합 중 — v-model 이면 값이 'PRO-00' 에 머문다
    await cdp.send('Input.imeSetComposition', { text: '1', selectionStart: 1, selectionEnd: 1 })
    await expect(page.getByTestId('delete-confirm-btn')).toBeEnabled()
    await cdp.send('Input.insertText', { text: '1' })
    await expect(input).toHaveValue('PRO-001')
    await expect(page.getByTestId('delete-confirm-btn')).toBeEnabled()
  })

  test('붙여넣기 앞뒤 공백은 걷되, 다른 값이면 끝까지 꺼져 있다', async ({ page }) => {
    const deleted: unknown[] = []
    await mockApi(page, [proposal('PRO-001', 'DRAFT')], { onDelete: (b) => deleted.push(b) })
    await open(page)
    await page.locator('.proposal-item__delete').first().click({ force: true })
    const input = page.getByTestId('delete-confirm-input')
    const btn = page.getByTestId('delete-confirm-btn')
    await input.fill('pro-001')
    await expect(btn).toBeDisabled()
    await input.fill('  PRO-001 \n')
    await expect(btn).toBeEnabled()
    await btn.click()
    await expect(input).toHaveCount(0)
    expect(deleted).toEqual([{ confirmId: 'PRO-001' }])
  })

  test('id 복사 단추가 클립보드에 id 를 넣는다', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await mockApi(page, [proposal('PRO-001', 'DRAFT')])
    await open(page)
    await page.locator('.proposal-item__delete').first().click({ force: true })
    await expect(page.getByTestId('delete-target-id')).toHaveText('PRO-001')
    await page.getByTestId('delete-copy-id').click()
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('PRO-001')
    // 복사 후 focus 는 입력칸으로 돌아온다 — 곧장 Ctrl+V
    await expect(page.getByTestId('delete-confirm-input')).toBeFocused()
    await page.keyboard.press('Control+V')
    await expect(page.getByTestId('delete-confirm-btn')).toBeEnabled()
  })
})

test.describe('D-1 ⑬ + C-2 ③ 단계 탭 한 줄', () => {
  const tab = (page: Page, key: string) => page.locator(`[data-testid="stage-tabs"] [data-stage="${key}"]`)
  const stateOf = (page: Page, key: string) => tab(page, key).getAttribute('data-state')

  test('탭은 한 줄뿐이다 — 상세 안에 둘째 탭 줄이 없고, 상태 필터는 목록 머리 드롭다운이다', async ({ page }) => {
    await mockApi(page, [proposal('PRO-001', 'DRAFT'), proposal('PRO-002', 'SUBMITTED')])
    await open(page)
    const tabs = page.getByTestId('stage-tabs').locator('.tab-btn')
    await expect(tabs).toHaveText([/Intent/, /Plan/, /Sandbox/, /Validate/, /Accept/])
    await expect(page.locator('.status-tabs')).toHaveCount(0)
    // 선택 전엔 탭이 꺼져 있고 칩이 없다
    await expect(tabs.first()).toBeDisabled()
    await expect(page.locator('.stage-chip')).toHaveCount(0)

    await page.locator('.proposal-item', { hasText: 'PRO-001' }).click()
    await expect(page.locator('.proposal-detail')).toBeVisible()
    await expect(page.locator('.detail-tabs')).toHaveCount(0)
    await expect(page.locator('.tab-btn')).toHaveCount(5)
    await expect(page.locator('.stage-chip')).toHaveCount(5)

    // 상태 드롭다운 — 숫자가 붙는다
    const sel = page.getByTestId('status-filter')
    await expect(sel.locator('option')).toHaveCount(8)
    await sel.selectOption('SUBMITTED')
    await expect(page.locator('.proposal-item')).toHaveCount(1)
    await expect(page.locator('.proposal-item')).toContainText('PRO-002')
    await sel.selectOption('')
    await page.getByTestId('proposal-search').fill('pro-001')
    await expect(page.locator('.proposal-item')).toHaveCount(1)
    await expect(page.locator('.proposal-item')).toContainText('PRO-001')
  })

  test('DRAFT — Intent 진행중 · 나머지 잠김, Sandbox 를 누르면 본문 대신 잠금 안내', async ({ page }) => {
    await mockApi(page, [proposal('PRO-001', 'DRAFT')])
    await open(page)
    await page.locator('.proposal-item').first().click()
    await expect(page.locator('.intent-view')).toBeVisible()
    expect(await stateOf(page, 'intent')).toBe('active')
    for (const k of ['plan', 'sandbox', 'validate', 'accept']) expect(await stateOf(page, k)).toBe('locked')

    await tab(page, 'sandbox').click()
    await expect(page.getByTestId('stage-locked')).toBeVisible()
    await expect(page.locator('.detail-content')).toHaveAttribute('data-stage', 'sandbox')

    // Plan 은 DRAFT 에서도 열린다(자체 잠금 안내 + Impact 섹션)
    await tab(page, 'plan').click()
    await expect(page.locator('.plan-locked')).toBeVisible()
    await expect(page.getByTestId('plan-impact')).toBeVisible()
  })

  test('Impact 는 Plan 안의 접힌 섹션 — 비면 "Plan 단계를 돌리면 채워집니다", 있으면 그린다', async ({ page }) => {
    await mockApi(page, [
      proposal('PRO-001', 'SUBMITTED'),
      proposal('PRO-002', 'SUBMITTED', {
        tacticalDiff: [{ tempId: 'T1', entityType: 'Aggregate', entityTitle: '주문', action: 'CREATE' }],
        impactMap: [{ nodeId: 'n1', kind: 'Aggregate', name: '주문' }],
        implementationPlan: { ok: true },
      }),
    ])
    await open(page)
    await page.locator('.proposal-item', { hasText: 'PRO-001' }).click()
    await tab(page, 'plan').click()
    const impact = page.getByTestId('plan-impact')
    await expect(impact).toBeVisible()
    expect(await impact.evaluate((el) => (el as HTMLDetailsElement).open)).toBe(false)
    await impact.locator('summary').click()
    await expect(page.getByTestId('plan-impact-empty')).toHaveText(/Plan 단계를 돌리면 채워집니다/)
    expect(await stateOf(page, 'plan')).toBe('active')
    expect(await stateOf(page, 'sandbox')).toBe('locked')

    // 다른 프로포절을 골라도 보던 단계(Plan)에 머문다 — 목록은 같은 자리
    await page.locator('.proposal-item', { hasText: 'PRO-002' }).click()
    await expect(page.locator('.proposal-id')).toHaveText('PRO-002')
    await expect(page.locator('.detail-content')).toHaveAttribute('data-stage', 'plan')
    const impact2 = page.getByTestId('plan-impact')
    if (!(await impact2.evaluate((el) => (el as HTMLDetailsElement).open))) await impact2.locator('summary').click()
    await expect(page.getByTestId('plan-impact-empty')).toHaveCount(0)
    await expect(impact2.locator('.impact-conflict')).toHaveCount(1)
    // 확정 Plan 이 있으면 Sandbox 칩이 준비됨
    expect(await stateOf(page, 'sandbox')).toBe('ready')
  })

  test('TESTING — 앞 단계 완료 · Validate 진행중 · Accept 도 열린다', async ({ page }) => {
    await mockApi(page, [proposal('PRO-009', 'TESTING')])
    await open(page)
    await page.locator('.proposal-item').first().click()
    await expect(page.locator('.proposal-detail')).toBeVisible()
    for (const k of ['intent', 'plan', 'sandbox']) expect(await stateOf(page, k)).toBe('done')
    expect(await stateOf(page, 'validate')).toBe('active')
    expect(await stateOf(page, 'accept')).toBe('locked')
    await tab(page, 'accept').click()
    await expect(page.locator('.detail-content')).toHaveAttribute('data-stage', 'accept')
    await expect(page.getByTestId('stage-locked')).toHaveCount(0)
  })

  test('042 Detailed DDD — DRAFT 의 Intent 탭엔 전략 단계, SUBMITTED 의 Plan 탭엔 전술 단계가 그대로 융합된다', async ({ page }) => {
    const stagePlan = { stages: [
      { stage: 'DISCOVER', skipped: false }, { stage: 'DECOMPOSE', skipped: false }, { stage: 'STRATEGIZE', skipped: false },
      { stage: 'CONNECT', skipped: false }, { stage: 'DEFINE', skipped: false }, { stage: 'TACTICAL', skipped: false },
    ] }
    await mockApi(page, [
      proposal('PRO-D1', 'DRAFT', { decompositionMode: 'DETAILED_DDD', stagePlan }),
      proposal('PRO-D2', 'SUBMITTED', { decompositionMode: 'DETAILED_DDD', stagePlan,
        stageArtifacts: { DISCOVER: {}, DECOMPOSE: {}, STRATEGIZE: {} } }),
    ])
    await open(page)
    await page.locator('.proposal-item', { hasText: 'PRO-D1' }).click()
    await expect(page.locator('.detail-content[data-stage="intent"] .strat-stages')).toBeVisible()

    await page.locator('.proposal-item', { hasText: 'PRO-D2' }).click()
    await expect(page.locator('.proposal-id')).toHaveText('PRO-D2')
    await tab(page, 'plan').click()
    await expect(page.locator('.detail-content[data-stage="plan"] .plan-stages')).toBeVisible()
    await expect(page.getByTestId('plan-impact')).toBeVisible()
    // Intent 탭은 전략 단계 이력 탭(StageArtifactTabs)으로 돌아간다
    await tab(page, 'intent').click()
    await expect(page.locator('.detail-content[data-stage="intent"] .stage-artifact-tabs')).toBeVisible()
  })

  test('화면 그림 — 단계 탭 한 줄 + 목록 머리 드롭다운', async ({ page }) => {
    await mockApi(page, [proposal('PRO-001', 'SUBMITTED', { implementationPlan: { ok: true } }), proposal('PRO-002', 'DRAFT')])
    await page.setViewportSize({ width: 1280, height: 720 })
    await open(page)
    await page.locator('.proposal-item', { hasText: 'PRO-001' }).click()
    await tab(page, 'plan').click()
    await page.getByTestId('plan-impact').locator('summary').click()
    await page.screenshot({ path: test.info().outputPath('stage-tabs.png') })
  })
})
