/**
 * 창 둘 · 두 사람 검사의 공용 부품.
 *
 * `collab-two-users.spec.ts` 가 쓰던 것을 그대로 꺼냈다. 두 벌이면 한쪽만
 * 고치고 다른 쪽에서 재게 된다 — pdf2bpmn facade 에서 이미 한 번 겪은 모양이다.
 *
 * **여기 있는 것은 전부 "어떻게 재는가"에 관한 것이다.** 무엇을 재는가는
 * 각 spec 에 있다.
 */
import { expect, request as pwRequest, type Page, type BrowserContext } from '@playwright/test'
import { readFileSync } from 'fs'
import { resolve } from 'path'

export const API = process.env.ROBO_API_URL || 'http://localhost:8000'

export type Who = { token: string; uid: string; name: string }

/**
 * 개발용 계정의 비밀번호. `test` 만 공용 기본값을 쓰고 나머지는 계정마다 다르다.
 * **값을 찍지 않는다.**
 */
export function devPassword(loginId: string): string {
  if (loginId === (process.env.AUTH_DEV_LOGIN_ID || 'test')) {
    return process.env.AUTH_DEV_LOGIN_PASSWORD || 'test'
  }
  // playwright 는 frontend/ 에서 돈다. 못 찾으면 **말하게 한다** — 조용히
  // 기본 비밀번호로 떨어지면 401 만 보이고 왜인지가 안 보인다.
  const envPath = resolve(process.cwd(), '../.env')
  let env = ''
  try {
    env = readFileSync(envPath, 'utf-8')
  } catch {
    throw new Error(`개발용 계정 비밀번호를 읽을 곳이 없다: ${envPath}`)
  }
  const line = env.split('\n').find((l) => l.startsWith('AUTH_DEV_LOGIN_ACCOUNTS='))
  for (const acc of (line || '').slice('AUTH_DEV_LOGIN_ACCOUNTS='.length).trim().split(',')) {
    const f = acc.split(':')
    if (f[0]?.trim() === loginId && f[1]) return f[1]
  }
  throw new Error(`${envPath} 의 AUTH_DEV_LOGIN_ACCOUNTS 에 '${loginId}' 가 없다`)
}

export async function login(loginId: string): Promise<Who> {
  const ctx = await pwRequest.newContext()
  try {
    const r = await ctx.post(`${API}/api/auth/dev-login`, {
      multipart: { loginId, password: devPassword(loginId) },
    })
    const body = await r.json().catch(() => ({} as any))
    expect(body.accessToken, `${loginId} 로 로그인하지 못했다 (${body.status || r.status()})`).toBeTruthy()
    return { token: body.accessToken, uid: body.user?.uid || '', name: body.user?.displayName || loginId }
  } finally {
    await ctx.dispose()
  }
}

/**
 * 둘 다 **쓸 수 있고 설계가 들어 있는** 프로젝트.
 *
 * "볼 수 있는" 으로 고르면 잠금이 403 이라 잠금 대신 권한을 재게 된다.
 * 빈 프로젝트를 고르면 트리가 안 떠서 "잠금이 안 돌아온다"로 보인다.
 * **둘 다 실제로 밟은 함정이다.**
 */
export async function sharedGraph(a: Who, b: Who): Promise<string> {
  const listFor = async (w: Who) => {
    const ctx = await pwRequest.newContext()
    try {
      const r = await ctx.get(`${API}/api/projects`, { headers: { Authorization: `Bearer ${w.token}` } })
      const rows = r.ok() ? ((await r.json()).projects || []) : []
      return new Set(rows.filter((p: any) => p.level && p.level !== 'read').map((p: any) => p.graph))
    } finally { await ctx.dispose() }
  }
  const [ga, gb] = await Promise.all([listFor(a), listFor(b)])
  const both = [...ga].filter((g: any) => gb.has(g))
  expect(both.length,
    `둘 다 쓰기 권한인 프로젝트가 있어야 한다 (${a.uid}: ${[...ga].join('/')} · ${b.uid}: ${[...gb].join('/')})`)
    .toBeGreaterThan(0)

  const ctx = await pwRequest.newContext()
  try {
    for (const g of both) {
      const r = await ctx.get(`${API}/api/contexts`, {
        headers: { Authorization: `Bearer ${a.token}`, 'X-Project-Graph': g as string },
      })
      const rows = r.ok() ? await r.json().catch(() => []) : []
      if (Array.isArray(rows) && rows.some((b2: any) => b2?.id)) return g as string
    }
  } finally { await ctx.dispose() }
  throw new Error(`설계가 들어 있는 공용 프로젝트가 없다 (후보: ${both.join(', ')})`)
}

export async function openApp(ctx: BrowserContext, who: Who, graph: string): Promise<Page> {
  const page = await ctx.newPage()
  // **모든 문서마다 다시 돈다.** 새로고침·라우팅에도 신원이 유지돼야 한다.
  await page.addInitScript(([token, g]) => {
    localStorage.setItem('robo.auth.token', token as string)
    localStorage.setItem('robo.auth.project', g as string)
  }, [who.token, graph])
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('#app')).toBeVisible({ timeout: 20_000 })
  await attach(page)
  return page
}

/**
 * 앱이 쓰는 바로 그 스토어를 창 안에서 붙잡아 둔다. 앱은 pinia 를 `window` 에
 * 안 내놓지만, 개발 서버에서는 소스 모듈이 같은 인스턴스다.
 */
export async function attach(page: Page) {
  await page.waitForFunction(() => !!document.querySelector('#app'), null, { timeout: 20_000 })
  await page.evaluate(async () => {
    const { useCollabStore } = await import('/src/features/collab/collab.store.js')
    const { useAuthStore } = await import('/src/features/auth/auth.store.js')
    ;(window as any).__collab = useCollabStore()
    ;(window as any).__auth = useAuthStore()
  })
}

/** 잠금 스트림이 붙었는지. 안 붙었으면 아래 검사는 전부 무의미하다. */
export async function waitConnected(page: Page, label: string) {
  await expect
    .poll(async () => page.evaluate(() => {
      const c = (window as any).__collab
      return c ? !!c.connected : null
    }), { timeout: 25_000, message: `${label}: collab 스트림이 안 붙었다` })
    .toBe(true)
}

/** 이 창이 보고 있는 잠금 목록. 스토어에서 직접 읽는다 — 화면보다 앞선다. */
export function locksOf(page: Page) {
  return page.evaluate(() => {
    const c = (window as any).__collab
    return c ? JSON.parse(JSON.stringify(c.locks || [])) : null
  })
}

/**
 * **서버가 아는** 잠금. 스토어는 스트림이 끊기면 낡는다 — 이 스펙은 바로 그
 * 상황을 재므로, 판정은 반드시 서버에 묻는다.
 *
 * 한 창에서 `fetch` 로 묻는다(브라우저 세션의 토큰·프로젝트 헤더를 그대로 탄다).
 */
export async function serverLocks(page: Page): Promise<any[]> {
  return page.evaluate(async () => {
    const r = await fetch('/api/collab/state')
    if (!r.ok) return []
    const j = await r.json().catch(() => ({}))
    return j.locks || []
  })
}

/** Design 탭으로 가서 트리를 펼친다. 트리는 지연 로딩이라 펼치기가 먼저다. */
export async function gotoDesignTree(page: Page, minNodes = 5) {
  const designTab = page.locator('nav').getByRole('button', { name: 'Design', exact: true })
  if (await designTab.isVisible({ timeout: 8_000 }).catch(() => false)) {
    await designTab.click()
    await page.waitForTimeout(1500)
  }
  const expand = page.locator('.tree-action-btn[title="Expand All"]')
  await expect(expand, 'Design 탭의 트리가 안 뜬다').toBeVisible({ timeout: 20_000 })
  await expand.click()
  await expect
    .poll(() => page.locator('.tree-node__label').count(),
      { timeout: 25_000, message: '트리가 안 펼쳐졌다' })
    .toBeGreaterThan(minNodes)
}

/**
 * 트리에서 요소를 하나 열어 **잠금을 잡는다.** 잡은 요소의 id 를 돌려준다.
 *
 * **API 로 지르지 않는다.** 직접 잠그면 `useElementLock` 이 아예 안 돌아서
 * 고친 코드를 하나도 안 지난다 — 한 번 그렇게 써서 헛짚었다.
 */
export async function openAnyElement(page: Page): Promise<string> {
  await gotoDesignTree(page)
  const labels = (await page.locator('.tree-node__label').allTextContents())
    .map((t) => t.trim()).filter((t) => t && !/\(\d+\)\s*$/.test(t))
  for (const label of labels.slice(0, 20)) {
    const row = page.locator('.tree-node__label').filter({ hasText: label }).first()
    if (!(await row.isVisible().catch(() => false))) continue
    await row.dblclick()
    if (!(await page.locator('.inspector-panel').isVisible({ timeout: 4_000 }).catch(() => false))) continue
    await page.waitForTimeout(1800)
    const ids = await page.evaluate(() =>
      ((window as any).__collab?.locks || []).map((l: any) => l.elementId))
    if (ids.length) return ids[0]
  }
  throw new Error('트리에서 요소를 열어 잠금을 잡지 못했다')
}
