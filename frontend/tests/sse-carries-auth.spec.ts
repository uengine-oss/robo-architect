import { test, expect } from '@playwright/test'

/**
 * 탐색(룰 매핑)이 401 로 막히던 일.
 *
 *     GET /api/ingest/hybrid/process/{sid}/{pid}/explore  →  401 Unauthorized
 *
 * **`EventSource` 는 헤더를 못 싣는다.** 우리 인터셉터는 `window.fetch` 를
 * 감싸므로 EventSource 로 연 스트림에는 `Authorization` 도 `X-Project-Graph` 도
 * 안 붙는다. 인증을 통과하더라도 프로젝트 헤더가 없으면 **엉뚱한 graph** 를
 * 본다 — 그쪽은 401 도 안 나고 조용히 틀린다.
 *
 * 그래서 재는 것은 화면이 아니라 **스트림 요청에 무엇이 실렸는가** 다.
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

test('탐색 스트림에 인증과 프로젝트가 실린다', async ({ page }) => {
  const seen: Record<string, string | undefined>[] = []

  await page.addInitScript(() => {
    window.localStorage.setItem('robo.auth.token', 'stub-token')
    window.localStorage.setItem('robo.auth.project', 'prj_aaa')
  })
  await page.route('**/api/auth/provider', (r: any) => r.fulfill({ json: PROVIDER }))
  await page.route('**/api/auth/me', (r: any) => r.fulfill({ json: ME }))
  await page.route('**/api/projects', (r: any) =>
    r.request().method() === 'GET' ? r.fulfill({ json: PROJECTS }) : r.fallback())
  await page.route('**/api/ingest/hybrid/sessions', (r: any) =>
    r.fulfill({ json: { sessions: [] } }))

  await page.route('**/api/ingest/hybrid/task/**/retrieve*', (r: any) => {
    const h = r.request().headers()
    seen.push({ auth: h['authorization'], graph: h['x-project-graph'] })
    return r.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'event: agent\ndata: {"type":"AgentDone"}\n\n',
    })
  })

  await page.goto('/', { waitUntil: 'networkidle' })

  // 스토어를 직접 부른다 — 캔버스에서 태스크를 고르는 절차는 이 검사의 주제가
  // 아니고, 주제는 "스트림이 어떻게 열리는가" 다.
  await page.evaluate(async () => {
    const mod = await import('/src/features/canvas/bpmn.store.js')
    mod.useBpmnStore().startAgentStream('sid-1', 'task-1', { force: false })
  })

  await expect.poll(() => seen.length, { timeout: 10_000 }).toBeGreaterThan(0)
  expect(seen[0].auth, '토큰이 실려야 한다 — 없으면 401').toBe('Bearer stub-token')
  expect(seen[0].graph, '프로젝트가 실려야 한다 — 없으면 엉뚱한 graph 를 본다')
    .toBe('prj_aaa')
})

test('스트림이 끊겨도 다시 잇지 않는다', async ({ page }) => {
  // `EventSource` 는 끊기면 자동으로 다시 잇는다. 이 스트림들은 한 번 돌고
  // 끝나는 작업이라, 되잇는 것은 **LLM 을 한 번 더 태우는 것**과 같다.
  let calls = 0

  await page.addInitScript(() => {
    window.localStorage.setItem('robo.auth.token', 'stub-token')
    window.localStorage.setItem('robo.auth.project', 'prj_aaa')
  })
  await page.route('**/api/auth/provider', (r: any) => r.fulfill({ json: PROVIDER }))
  await page.route('**/api/auth/me', (r: any) => r.fulfill({ json: ME }))
  await page.route('**/api/projects', (r: any) =>
    r.request().method() === 'GET' ? r.fulfill({ json: PROJECTS }) : r.fallback())
  await page.route('**/api/ingest/hybrid/sessions', (r: any) =>
    r.fulfill({ json: { sessions: [] } }))
  await page.route('**/api/ingest/hybrid/task/**/retrieve*', (r: any) => {
    calls += 1
    // 이벤트 하나 주고 바로 닫는다 = 서버가 끝냈다.
    return r.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'event: agent\ndata: {"type":"AgentDone"}\n\n',
    })
  })

  await page.goto('/', { waitUntil: 'networkidle' })
  await page.evaluate(async () => {
    const mod = await import('/src/features/canvas/bpmn.store.js')
    mod.useBpmnStore().startAgentStream('sid-1', 'task-1', { force: false })
  })

  await expect.poll(() => calls, { timeout: 10_000 }).toBe(1)
  await page.waitForTimeout(4000)
  expect(calls, '되이으면 같은 탐색을 두 번 태운다').toBe(1)
})
