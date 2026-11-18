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

test.describe('⑬ 단계 탭 집계 — 진행중 + 지난 단계', () => {
  test('Intent 탭에 완료된 것도 남고 배지는 합, 지난 것엔 "지남" 표시', async ({ page }) => {
    await mockApi(page, [
      proposal('PRO-001', 'DRAFT'),
      proposal('PRO-002', 'ACCEPTED'),
      proposal('PRO-003', 'SUBMITTED'),
      proposal('PRO-004', 'DESTROYED'),
    ])
    await open(page)
    await expect(page.getByTestId('stage-count-DRAFT')).toHaveText('3')
    await expect(page.getByTestId('stage-count-SUBMITTED')).toHaveText('2')
    await expect(page.getByTestId('stage-count-ACCEPTED')).toHaveText('1')
    await expect(page.getByTestId('stage-count-DESTROYED')).toHaveText('1')
    await expect(page.getByTestId('stage-count-DRAFT')).toHaveAttribute('title', /1 · .*2/)

    await page.locator('.status-tab', { hasText: 'INTENT' }).click()
    const items = page.locator('.proposal-item .proposal-item__id')
    await expect(items).toHaveText(['PRO-001', 'PRO-002', 'PRO-003'])  // 진행중(001) 먼저, 지난 것(002·003)은 원래 순서
    await expect(page.getByTestId('stage-passed-chip')).toHaveCount(2)
  })

  test('프로포절 안의 탭은 기존 그대로(Intent → Plan → Impact)', async ({ page }) => {
    await mockApi(page, [proposal('PRO-001', 'DRAFT')])
    await open(page)
    await page.locator('.proposal-item').first().click()
    await expect(page.locator('.detail-tabs .tab-btn')).toHaveCount(3)
    await expect(page.locator('.detail-tabs')).toBeVisible()
  })
})
