import { test, expect } from '@playwright/test'

/**
 * 문서를 올렸는데 Process 탭이 비어 보이던 일.
 *
 * BPM 은 graph 에 멀쩡히 있었다(프로세스 1·태스크 12). 화면이 **세션 아이디를
 * 브라우저 `localStorage` 키 하나**로만 들고 있었던 것이 원인이다.
 *
 *   다른 창·다른 기기        값이 없다            → 빈 화면
 *   프로젝트를 바꿨다        이전 세션이 남는다   → 남의 BPM 이거나 빈 화면
 *
 * 오류가 안 나고 "아직 안 만들었나 보다"로 보이는 종류라 더 나쁘다.
 *
 * 그래서 재는 것은 화면 문구가 아니라 **어느 세션을 불러왔는가** 다. 스냅샷
 * 요청의 URL 을 가로채 세션 아이디를 확인한다.
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
  projects: [
    { graph: 'prj_aaa', displayName: '가 프로젝트', ownerUid: 'DEV-TEST', level: 'admin' },
    { graph: 'prj_bbb', displayName: '나 프로젝트', ownerUid: 'DEV-TEST', level: 'admin' },
  ],
}

/** graph 마다 다른 세션을 들고 있다 — 서버가 프로젝트를 보고 답한다. */
const SESSION_BY_GRAPH: Record<string, string> = {
  prj_aaa: 'sid-aaa',
  prj_bbb: 'sid-bbb',
}

async function boot(page: any, opts: { project?: string; cachedSid?: string } = {}) {
  const snapshots: string[] = []

  await page.addInitScript(([project, cached]: [string | null, string | null]) => {
    window.localStorage.setItem('robo.auth.token', 'stub-token')
    if (project) window.localStorage.setItem('robo.auth.project', project)
    // 옛 방식이 쓰던 전역 키 — 프로젝트를 안 가린다.
    if (cached) window.localStorage.setItem('hybrid.session_id', cached)
  }, [opts.project ?? null, opts.cachedSid ?? null])

  await page.route('**/api/auth/provider', (r: any) => r.fulfill({ json: PROVIDER }))
  await page.route('**/api/auth/me', (r: any) => r.fulfill({ json: ME }))
  await page.route('**/api/projects', (r: any) => {
    if (r.request().method() !== 'GET') return r.fallback()
    return r.fulfill({ json: PROJECTS })
  })

  await page.route('**/api/ingest/hybrid/sessions', (r: any) => {
    const graph = r.request().headers()['x-project-graph'] || ''
    const sid = SESSION_BY_GRAPH[graph]
    return r.fulfill({
      json: { sessions: sid ? [{ session_id: sid, updatedAt: null, processes: 1 }] : [] },
    })
  })

  await page.route('**/api/ingest/hybrid/session/*/snapshot', (r: any) => {
    const m = r.request().url().match(/session\/([^/]+)\/snapshot/)
    if (m) snapshots.push(m[1])
    return r.fulfill({
      json: {
        processes: [], actors: [], tasks: [], rules: [], glossary: [],
        review_queue: [], unassigned_rule_ids: [], bpmn_xml: null,
      },
    })
  })

  await page.goto('/', { waitUntil: 'networkidle' })
  return snapshots
}

test('캐시가 없어도 이 프로젝트의 BPM 을 찾는다', async ({ page }) => {
  // 새 창에서 처음 들어온 상태 — localStorage 에 세션 아이디가 없다.
  const snapshots = await boot(page, { project: 'prj_aaa' })

  await expect.poll(() => snapshots, { timeout: 10_000 }).toContain('sid-aaa')
})

test('프로젝트가 바뀌면 그 프로젝트의 세션을 본다', async ({ page }) => {
  // 옛 전역 키에 다른 프로젝트의 세션이 남아 있는 상태.
  // **이것을 그대로 쓰면 남의 BPM 을 보여 준다.**
  const snapshots = await boot(page, { project: 'prj_bbb', cachedSid: 'sid-aaa' })

  await expect.poll(() => snapshots, { timeout: 10_000 }).toContain('sid-bbb')
  expect(snapshots, '이전 프로젝트의 세션을 불러오면 안 된다').not.toContain('sid-aaa')
})

test('BPM 이 없는 프로젝트에서는 아무것도 안 부른다', async ({ page }) => {
  // "늘 첫 세션을 부른다"로 고치면 위 둘은 통과하면서 이 경우가 깨진다.
  const snapshots = await boot(page, { project: 'prj_ccc' })

  await page.waitForTimeout(2000)
  expect(snapshots).toEqual([])
})
