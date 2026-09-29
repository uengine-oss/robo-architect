import { test, expect } from '@playwright/test'

/**
 * 문서를 **다시** 올렸더니 화면만 빈 채로 남던 일 (2026-09-29).
 *
 * 재적재는 세션 아이디를 바꾼다(`fd8fc503` → `f836078c`). 그런데 화면은
 * `localStorage` 의 캐시된 아이디를 **검증 없이** 그대로 썼다.
 *
 *   낡은 아이디로 스냅샷을 부른다  →  404 가 아니라 **200 + 빈 것**이 온다
 *   → `res.ok` 검사를 통과한다     →  "프로세스가 없다" 로 보인다
 *
 * 오류가 아니라 빈 결과라서 더 나쁘다. graph 에는 프로세스 3개가 멀쩡히 있었다.
 *
 * 재는 것은 문구가 아니라 **어느 세션을 끝까지 불러왔는가** 다.
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
  projects: [{ graph: 'prj_aaa', displayName: '가 프로젝트', ownerUid: 'DEV-TEST', level: 'admin' }],
}

const FILLED = {
  processes: [{ id: 'proc_1', name: '월 근태 마감', bpmn_xml: '<definitions/>' }],
  actors: [], tasks: [{ id: 'task_1', name: '마감 대상 확인' }],
  rules: [], glossary: [], review_queue: [], unassigned_rule_ids: [], bpmn_xml: null,
}
const EMPTY = {
  processes: [], actors: [], tasks: [], rules: [], glossary: [],
  review_queue: [], unassigned_rule_ids: [], bpmn_xml: null,
}

async function boot(page: any, opts: { cachedSid?: string; liveSid: string }) {
  const snapshots: string[] = []
  let sessionListCalls = 0

  await page.addInitScript(([cached]: [string | null]) => {
    window.sessionStorage.setItem('robo.auth.token', 'stub-token')
    window.sessionStorage.setItem('robo.auth.project', 'prj_aaa')
    if (cached) window.localStorage.setItem('hybrid.session_id.prj_aaa', cached)
  }, [opts.cachedSid ?? null])

  await page.route('**/api/auth/provider', (r: any) => r.fulfill({ json: PROVIDER }))
  await page.route('**/api/auth/me', (r: any) => r.fulfill({ json: ME }))
  await page.route('**/api/projects', (r: any) =>
    r.request().method() === 'GET' ? r.fulfill({ json: PROJECTS }) : r.fallback())

  await page.route('**/api/ingest/hybrid/sessions', (r: any) => {
    sessionListCalls += 1
    return r.fulfill({
      json: { sessions: [{ session_id: opts.liveSid, updatedAt: null, processes: 1 }] },
    })
  })

  // **살아 있는 세션만 내용을 준다.** 낡은 아이디에는 200 + 빈 것 — 실제 서버가
  // 그렇게 답한다(세션 노드가 사라져도 라우트는 200 이다).
  await page.route('**/api/ingest/hybrid/session/*/snapshot', (r: any) => {
    const m = r.request().url().match(/session\/([^/]+)\/snapshot/)
    const sid = m ? m[1] : ''
    snapshots.push(sid)
    return r.fulfill({ json: sid === opts.liveSid ? { session_id: sid, ...FILLED } : { session_id: sid, ...EMPTY } })
  })

  await page.goto('/', { waitUntil: 'networkidle' })
  return { snapshots, listCalls: () => sessionListCalls }
}

test('재적재로 세션 아이디가 바뀌어도 살아 있는 세션을 찾아간다', async ({ page }) => {
  const { snapshots } = await boot(page, { cachedSid: 'sid-old', liveSid: 'sid-new' })

  await expect
    .poll(() => snapshots, { timeout: 10_000 })
    .toContain('sid-new')
})

test('낡은 아이디에서 멈추지 않는다', async ({ page }) => {
  // 되묻는 단계를 빼면 여기서 끝난다 — 화면은 "프로세스가 없다".
  const { snapshots } = await boot(page, { cachedSid: 'sid-old', liveSid: 'sid-new' })

  await expect.poll(() => snapshots, { timeout: 10_000 }).toContain('sid-new')
  expect(snapshots[snapshots.length - 1], '마지막으로 불러온 것이 살아 있는 세션이어야 한다')
    .toBe('sid-new')
})

test('캐시가 맞으면 목록을 다시 묻지 않는다', async ({ page }) => {
  // 정상 경로에 요청이 늘면 안 된다 — 되묻기는 **빈 결과일 때만**이다.
  const { snapshots, listCalls } = await boot(page, { cachedSid: 'sid-new', liveSid: 'sid-new' })

  await expect.poll(() => snapshots, { timeout: 10_000 }).toContain('sid-new')
  await page.waitForTimeout(1000)
  expect(listCalls(), '캐시가 맞는데 세션 목록을 불렀다').toBe(0)
})
