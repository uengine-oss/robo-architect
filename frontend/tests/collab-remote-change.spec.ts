import { test, expect } from '@playwright/test'

/**
 * 남의 변경이 **새로고침 없이** 보이는가.
 *
 * 실측이었다 — bob 이 0 을 세고, alice 가 쓰고, bob 이 다시 세면 1 이다.
 * 응답은 늘 최신인데 **다시 물을 계기가 없었다.**
 *
 * 그래서 여기서 재는 것은 화면에 숫자가 뜨는지가 아니라 세 가지다.
 *
 *     1  스트림에 인증과 프로젝트가 실리는가   (안 실리면 401, 또는 남의 graph)
 *     2  남의 변경이 `robo:data-changed` 를 울리는가
 *     3  **내 변경은 안 울리는가**             (울리면 내가 내 편집 상태를 날린다)
 *
 * 3 이 없으면 1·2 만으로도 "된다"고 말할 수 있는데, 실제로는 쓸 때마다 화면이
 * 스스로 접힌다.
 */

test.use({ storageState: { cookies: [], origins: [] } })

const PROVIDER = {
  provider: 'swp', enterprise: true, callbackAllowlist: [], embeddings: {},
  devLogin: { enabled: false }, approvalRequired: true, jwtSecretConfigured: true,
  sessionTtlSeconds: 28800, enforce: false, bindConnection: true,
}
const ME = {
  authenticated: true, status: 'approved',
  user: { uid: 'DEV-TEST', displayName: '개발용 계정', role: 'admin', status: 'approved' },
}
const PROJECTS = {
  projects: [{
    graph: 'prj_aaa', displayName: '가 프로젝트', ownerUid: 'DEV-TEST',
    level: 'admin', analyzerGraph: 'prj_aaa_a',
  }],
}

/** `hello` 하나를 주고 스트림을 열어 둔 채로 둔다. */
function sse(body: string) {
  return { status: 200, contentType: 'text/event-stream', body }
}

async function boot(page: any, onStream: (headers: Record<string, string>) => any) {
  await page.addInitScript(() => {
    window.localStorage.setItem('robo.auth.token', 'stub-token')
    window.localStorage.setItem('robo.auth.project', 'prj_aaa')
    // 버스가 울린 횟수와 이유를 창에 남긴다 — 화면을 거치지 않고 잰다.
    ;(window as any).__dataChanged = []
    window.addEventListener('robo:data-changed', (e: any) => {
      ;(window as any).__dataChanged.push(e?.detail?.reason)
    })
  })
  await page.route('**/api/auth/provider', (r: any) => r.fulfill({ json: PROVIDER }))
  await page.route('**/api/auth/me', (r: any) => r.fulfill({ json: ME }))
  await page.route('**/api/projects', (r: any) =>
    r.request().method() === 'GET' ? r.fulfill({ json: PROJECTS }) : r.fallback())
  await page.route('**/api/ingest/hybrid/sessions', (r: any) =>
    r.fulfill({ json: { sessions: [] } }))
  await page.route('**/api/collab/stream', (r: any) =>
    r.fulfill(onStream(r.request().headers())))
  await page.goto('/', { waitUntil: 'domcontentloaded' })
}

test('알림 스트림에 인증과 프로젝트가 실린다', async ({ page }) => {
  const seen: Record<string, string | undefined>[] = []

  await boot(page, (h) => {
    seen.push({ auth: h['authorization'], graph: h['x-project-graph'] })
    return sse('event: hello\ndata: {"graph":"prj_aaa","rev":0,"viewers":[]}\n\n')
  })

  await expect.poll(() => seen.length, { timeout: 10_000 }).toBeGreaterThan(0)
  expect(seen[0].auth, '토큰이 없으면 401 이다').toBe('Bearer stub-token')
  expect(seen[0].graph, '프로젝트가 없으면 남의 graph 알림을 받는다').toBe('prj_aaa')
})

test('남의 변경이 새로고침 없이 화면 갱신을 부른다', async ({ page }) => {
  await boot(page, () => sse(
    'event: hello\ndata: {"graph":"prj_aaa","rev":1,"viewers":[]}\n\n' +
    // 다른 사람이 썼다.
    'event: changed\ndata: {"graph":"prj_aaa","rev":2,"actorUid":"DEV-ALICE"}\n\n',
  ))

  await expect
    .poll(() => page.evaluate(() => (window as any).__dataChanged), { timeout: 10_000 })
    .toContain('remote-change')
})

test('내가 쓴 변경으로는 내 화면을 다시 그리지 않는다', async ({ page }) => {
  await boot(page, () => sse(
    'event: hello\ndata: {"graph":"prj_aaa","rev":1,"viewers":[]}\n\n' +
    // 내가 썼다 — 내 화면은 이미 최신이다.
    'event: changed\ndata: {"graph":"prj_aaa","rev":2,"actorUid":"DEV-TEST"}\n\n',
  ))

  // 스트림이 도착할 시간을 준 뒤에 센다. 바로 세면 아직 안 온 것을
  // "안 울렸다"고 읽는다.
  await page.waitForTimeout(2500)
  const fired = await page.evaluate(() => (window as any).__dataChanged)
  expect(fired, '자기 변경에 반응하면 편집 중이던 상태가 접힌다')
    .not.toContain('remote-change')
})

test('다른 프로젝트의 알림은 무시한다', async ({ page }) => {
  await boot(page, () => sse(
    'event: hello\ndata: {"graph":"prj_aaa","rev":1,"viewers":[]}\n\n' +
    'event: changed\ndata: {"graph":"prj_남의것","rev":9,"actorUid":"DEV-ALICE"}\n\n',
  ))

  await page.waitForTimeout(2500)
  const fired = await page.evaluate(() => (window as any).__dataChanged)
  expect(fired).not.toContain('remote-change')
})
