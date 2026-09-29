import { test, expect } from '@playwright/test'

// 로그인 화면이 앞을 막으면 런처까지 닿지 못한다. 인증은 꺼진 것으로 흉내 낸다 —
// 여기서 보려는 것은 **런처가 뜨는가 마는가** 뿐이다.
test.use({ storageState: { cookies: [], origins: [] } })

/**
 * 고를 것이 없으면 런처를 묻지 않는가.
 *
 * ## 왜 이 검사가 생겼나
 *
 * 이 런처는 사용자가 자기 Neo4j 를 들고 오던 시절의 화면이다. 지금 납품본은
 * 앱이 스택을 소유하고 번들 연결을 스스로 만들어 미리 골라 둔다 — 사람이 정할
 * 것은 프로젝트 폴더뿐이고, 그것도 한 번 정하면 다음부터는 같은 값이다.
 *
 * 2026-09-18~29 에 preload 가 깨져 런처가 통째로 건너뛰어졌는데 **아무것도
 * 깨지지 않았다.** 브리지가 없으면 `app/http.js` 가 `X-Neo4j-*` 를 빼고 보내고
 * 백엔드가 자기 `.env` 로 폴백하는데, 납품본에서 그 `.env` 가 같은 번들 그래프를
 * 가리키기 때문이다. 연결 단계가 사실상 잉여라는 증거다.
 *
 * 그래서 건너뛰게 했다. 다만 **건너뛰면 안 되는 경우**가 있고, 이 파일의 절반은
 * 그쪽을 잰다 — 기억해 둔 폴더가 사라졌거나, 연결이 여럿이거나, 번들이 아닌
 * 연결일 때. 그때 조용히 넘어가면 사용자는 엉뚱한 그래프에 붙고도 모른다.
 */

const BUNDLED = {
  id: 'c1',
  label: 'Robo Architect (Bundled)',
  uri: 'bolt://127.0.0.1:62034',
  user: 'robo',
  database: 'robo',
  source: 'bundled',
  lastConnectedAt: null,
  createdAt: '2026-09-18T04:44:17.192Z',
}

const IDENTITY = { name: 'Kim', email: 'kim@example.com', source: 'git-config' }

interface Stub {
  connections?: unknown[]
  recentRoots?: { path: string }[]
  rootValid?: boolean
  enterOk?: boolean
}

/**
 * `window.desktop` 브리지를 흉내 낸다. 페이지 스크립트보다 먼저 올라가야
 * `session-store` 의 `IS_DESKTOP` 판정이 데스크톱으로 잡힌다.
 */
async function stubDesktop(page: any, s: Stub = {}) {
  const cfg = {
    connections: s.connections ?? [BUNDLED],
    recentRoots: s.recentRoots ?? [{ path: 'C:\\work\\proj' }],
    rootValid: s.rootValid ?? true,
    enterOk: s.enterOk ?? true,
    identity: IDENTITY,
  }
  await page.addInitScript((c: any) => {
    ;(window as any).__enterCalls = []
    const ok = (data: unknown) => Promise.resolve({ ok: true, data })
    ;(window as any).desktop = {
      connections: {
        list: () => ok(c.connections),
        resolveActiveForBackend: () => Promise.resolve({ ok: true, data: null }),
        probeStatus: () => ok({ status: 'unknown' }),
      },
      projectRoot: {
        listRecent: () => ok(c.recentRoots),
        validate: () => ok({ valid: c.rootValid, basename: 'proj', parent: 'C:\\work' }),
        choose: () => ok({ path: 'C:\\work\\proj', valid: true }),
      },
      identity: { resolve: () => ok(c.identity), setGitConfig: () => ok(c.identity) },
      launcher: {
        enter: (input: unknown) => {
          ;(window as any).__enterCalls.push(input)
          return c.enterOk
            ? ok({ identity: c.identity, activeConnectionId: 'c1' })
            : Promise.resolve({ ok: false, error: { code: 'PROJECT_ROOT_INVALID' } })
        },
        reopen: () => ok({ ok: true }),
      },
    }
  }, cfg)

  // 인증 게이트를 열어 둔다 — 이 파일의 관심사가 아니다.
  await page.route('**/api/auth/provider', (r: any) =>
    r.fulfill({ json: { provider: 'none', enforce: false, devLogin: { enabled: false } } }))
  await page.route('**/api/auth/me', (r: any) =>
    r.fulfill({ json: { authenticated: false, status: 'anonymous' } }))
}

const launcherCard = (page: any) => page.locator('.launcher-brand')

test.describe('고를 것이 없으면 묻지 않는다', () => {
  test.setTimeout(120_000)

  test('번들 연결 하나 + 기억해 둔 폴더가 유효하면 런처를 건너뛴다', async ({ page }) => {
    await stubDesktop(page)
    await page.goto('/', { waitUntil: 'domcontentloaded' })

    await expect(launcherCard(page), '고를 것이 없는데 화면을 보여주면 안 된다')
      .toHaveCount(0, { timeout: 20_000 })

    const calls = await page.evaluate(() => (window as any).__enterCalls)
    expect(calls.length, '건너뛰었다면 enter 를 스스로 불렀어야 한다').toBe(1)
    expect(calls[0]).toMatchObject({ connectionId: 'c1', projectRoot: 'C:\\work\\proj' })
  })
})

test.describe('건너뛰면 안 되는 경우 — 여기가 본론이다', () => {
  test.setTimeout(120_000)

  test('기억해 둔 폴더가 없으면 묻는다 (첫 실행)', async ({ page }) => {
    await stubDesktop(page, { recentRoots: [] })
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(launcherCard(page)).toBeVisible({ timeout: 20_000 })
    expect(await page.evaluate(() => (window as any).__enterCalls.length)).toBe(0)
  })

  test('폴더가 사라졌으면 묻는다 — 조용히 들어가면 안 된다', async ({ page }) => {
    await stubDesktop(page, { rootValid: false })
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(launcherCard(page)).toBeVisible({ timeout: 20_000 })
    expect(await page.evaluate(() => (window as any).__enterCalls.length)).toBe(0)
  })

  test('연결이 여럿이면 묻는다 — 그때는 고를 것이 실제로 있다', async ({ page }) => {
    await stubDesktop(page, {
      connections: [BUNDLED, { ...BUNDLED, id: 'c2', label: '사내 중앙 DB', source: 'manual' }],
    })
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(launcherCard(page)).toBeVisible({ timeout: 20_000 })
    expect(await page.evaluate(() => (window as any).__enterCalls.length)).toBe(0)
  })

  test('번들이 아닌 연결 하나뿐이어도 묻는다', async ({ page }) => {
    await stubDesktop(page, { connections: [{ ...BUNDLED, source: 'manual' }] })
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(launcherCard(page)).toBeVisible({ timeout: 20_000 })
    expect(await page.evaluate(() => (window as any).__enterCalls.length)).toBe(0)
  })

  test('자동 진입이 실패하면 화면을 보여 준다 — 빈 화면으로 멈추지 않는다', async ({ page }) => {
    await stubDesktop(page, { enterOk: false })
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(launcherCard(page), '실패했으면 사람이 고칠 수 있어야 한다')
      .toBeVisible({ timeout: 20_000 })
    expect(await page.evaluate(() => (window as any).__enterCalls.length)).toBe(1)
  })
})
