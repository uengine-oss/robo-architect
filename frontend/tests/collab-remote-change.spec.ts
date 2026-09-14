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
    // **초기 스크립트에서 건다.** `goto` 뒤에 걸면 스트림이 먼저 도착해 놓친다
    // — 실제로 두 검사가 그렇게 비어 있었다.
    ;(window as any).__remote = []
    window.addEventListener('robo:remote-changes', (e: any) => {
      ;(window as any).__remote.push(...(e?.detail?.changes || []))
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

/**
 * 여기부터는 **요소 단위 반영**이다.
 *
 * "뭔가 바뀌었다"만 오면 받는 쪽이 통째로 다시 읽는다 — 그러면 편집 중이던
 * 화면이 초기화되고 Inspector 의 federated 편집기가 깨진다. 그래서 편집 중에는
 * 미뤄 뒀는데, 그러면 이번엔 **바로 안 보인다.**
 *
 * 서버가 무엇이 바뀌었는지 실어 주면 둘 다 풀린다 — 그 요소만 갈아끼우니
 * 미룰 이유가 없다.
 */

function withChanges(changes: unknown) {
  return sse(
    'event: hello\ndata: {"graph":"prj_aaa","rev":1,"viewers":[],"locks":[]}\n\n' +
    'event: changed\ndata: ' +
    JSON.stringify({ graph: 'prj_aaa', rev: 2, actorUid: 'DEV-ALICE', changes }) +
    '\n\n',
  )
}

async function bootWatching(page: any, body: any) {
  await boot(page, () => body)
}

/**
 * 스트림을 **붙잡았다 놓는다.**
 *
 * 열자마자 이벤트가 도착하면 검사가 준비를 마치기 전에 지나간다. 열어 두고,
 * 준비가 끝난 뒤에 내보낸다 — 실제 순서(창이 떠 있고, 나중에 남이 쓴다)와도
 * 이쪽이 더 가깝다.
 */
async function bootGated(page: any, body: string) {
  let release: () => void = () => {}
  const gate = new Promise<void>((r) => { release = r })
  await boot(page, () => ({
    status: 200,
    contentType: 'text/event-stream',
    body: 'event: hello\ndata: {"graph":"prj_aaa","rev":1,"viewers":[],"locks":[]}\n\n',
  }))
  // hello 만 먼저 보낸 스트림은 닫힌다. 두 번째 연결에서 본론을 내보낸다.
  await page.unroute('**/api/collab/stream')
  await page.route('**/api/collab/stream', async (r: any) => {
    await gate
    r.fulfill({ status: 200, contentType: 'text/event-stream', body })
  })
  return release
}

test('목록이 오면 그 요소만 갈아끼운다 — 통째로 다시 읽지 않는다', async ({ page }) => {
  await bootWatching(page, withChanges([
    { action: 'update', targetId: 'n1', targetType: 'Command' },
  ]))

  await expect
    .poll(() => page.evaluate(() => (window as any).__remote?.map((c: any) => c.targetId)),
      { timeout: 10_000 })
    .toEqual(['n1'])

  // 통째로 다시 읽는 쪽은 울리면 안 된다 — 울리면 편집 중이던 화면이 초기화된다.
  const coarse = await page.evaluate(() => (window as any).__dataChanged)
  expect(coarse, '목록이 있는데도 통째로 다시 읽으면 세분화한 의미가 없다')
    .not.toContain('remote-change')
})

test('목록이 없으면 통째로 다시 읽는다', async ({ page }) => {
  // 목록을 못 싣는 쓰기(그 밖의 42곳)가 여기로 온다. 이쪽을 없애면 그 변경이
  // **조용히 안 보인다.**
  await bootWatching(page, withChanges(undefined))

  await expect
    .poll(() => page.evaluate(() => (window as any).__dataChanged), { timeout: 10_000 })
    .toContain('remote-change')
})

test('빈 목록은 아무 일도 아니다 — 통째로 다시 읽지 않는다', async ({ page }) => {
  await bootWatching(page, withChanges([]))
  await page.waitForTimeout(2500)

  const coarse = await page.evaluate(() => (window as any).__dataChanged)
  const remote = await page.evaluate(() => (window as any).__remote)
  expect(coarse, '빈 목록을 "모른다"로 읽으면 헛되이 전부 다시 읽는다')
    .not.toContain('remote-change')
  expect(remote).toEqual([])
})

test('내가 열어 둔 요소는 남의 변경으로 안 바뀐다', async ({ page }) => {
  const release = await bootGated(page,
    'event: changed\ndata: ' + JSON.stringify({
      graph: 'prj_aaa', rev: 3, actorUid: 'DEV-ALICE',
      changes: [
        { action: 'update', targetId: 'n-open', targetType: 'Command' },
        { action: 'update', targetId: 'n-other', targetType: 'Event' },
      ],
    }) + '\n\n')

  // 남이 쓰기 **전에** "이걸 열어 놨다"고 알린다.
  await page.evaluate(async () => {
    const mod = await import('/src/features/collab/collab.store.js')
    mod.useCollabStore().setEditing('n-open')
  })
  release()

  await expect
    .poll(() => page.evaluate(() => (window as any).__remote?.map((c: any) => c.targetId)),
      { timeout: 10_000 })
    .toEqual(['n-other'])
})
