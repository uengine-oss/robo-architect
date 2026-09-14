import { test, expect, request as pwRequest, type Page, type BrowserContext } from '@playwright/test'
import { readFileSync } from 'fs'
import { resolve } from 'path'

/**
 * **두 사람이 정말로 같은 요소를 열었을 때** 잠기고, 반영되는가.
 *
 * 이 파일이 왜 필요한가 — 기존 동시편집 검사 둘(`collab-remote-change`,
 * `inspector-lock-banner`)은 **SSE 를 가짜로 태우고 부품만 잰다.** 진짜
 * 두 번째 사용자도, 진짜 Inspector 도 안 연다. 그래서 셋 다 통과하는데
 * 화면에서는 세 번 연속 안 됐다.
 *
 *     걸러 낸 것    dataLifecycle 의 hold/release · LockBanner 의 노드 종류
 *     못 본 것      잠금이 실제로 화면을 비활성화하는가
 *                   남의 저장이 내 화면에 실제로 나타나는가
 *
 * 여기서는 **브라우저 창을 둘 띄운다.** 느리고 환경을 타지만, 이것만이
 * 사용자가 보는 것을 본다.
 */

const API = process.env.ROBO_API_URL || 'http://localhost:8000'

/**
 * 개발용 계정의 비밀번호. `test` 만 공용 기본값을 쓰고 나머지는 계정마다 다르다
 * (`AUTH_DEV_LOGIN_ACCOUNTS=loginId:pw:사번:이름:부서, ...`).
 *
 * **값을 찍지 않는다.** 로컬 개발 자격이지만 로그에 남길 이유가 없다.
 */
function devPassword(loginId: string): string {
  if (loginId === (process.env.AUTH_DEV_LOGIN_ID || 'test')) {
    return process.env.AUTH_DEV_LOGIN_PASSWORD || 'test'
  }
  // playwright 는 frontend/ 에서 돈다. `__dirname` 은 여기서 정의되지 않아
  // 한 번 조용히 기본 비밀번호로 떨어졌고, 그러면 401 만 보이고 **왜인지가
  // 안 보인다.** 못 찾으면 말하게 한다.
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

// 로그인 상태를 spec 이 직접 만든다 — globalSetup 의 것은 한 사람 몫이다.
test.use({ storageState: { cookies: [], origins: [] } })

/**
 * 실제로 눌리는 저장 버튼.
 *
 * 패널에 `저장` 이 **둘** 있다. 머리쪽(`title="Save"`)은 어떤 칸을 고쳐도 계속
 * 잠겨 있고, 본문 아래쪽 것만 켜진다. 앞의 것을 집어 "저장이 안 켜진다"고
 * 한참 헤맸다 — 별도 문제로 적어 뒀다.
 */
function enabledSave(page: Page) {
  return page.locator('.inspector-panel__btn.primary:not([title="Save"])').first()
}

type Who = { token: string; uid: string; name: string }

async function login(loginId: string): Promise<Who> {
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
 * 둘 다 **쓸 수 있는** 프로젝트.
 *
 * "볼 수 있는" 으로 고르면 안 된다 — 읽기 권한이면 잠금 자체가 403 이라
 * 잠금을 재려다 권한을 재게 된다. 실제로 한 번 그렇게 헛짚었다.
 */
async function sharedGraph(a: Who, b: Who): Promise<string> {
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
  return both[0] as string
}

async function openApp(ctx: BrowserContext, who: Who, graph: string): Promise<Page> {
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
 * 스토어를 창 안에서 붙잡아 둔다.
 *
 * 앱은 pinia 를 `window` 에 안 내놓는다. 개발 서버에서는 소스 모듈이 같은
 * 인스턴스라, 모듈을 들여와 `useXStore()` 를 부르면 **앱이 쓰는 바로 그
 * 스토어**가 온다(앱이 이미 `app.use(pinia)` 로 활성 인스턴스를 정해 뒀다).
 * 기존 검사들이 `dataLifecycle.js` 를 이렇게 들여온다.
 */
async function attach(page: Page) {
  await page.waitForFunction(() => !!document.querySelector('#app'), null, { timeout: 20_000 })
  await page.evaluate(async () => {
    const { useCollabStore } = await import('/src/features/collab/collab.store.js')
    const { useAuthStore } = await import('/src/features/auth/auth.store.js')
    ;(window as any).__collab = useCollabStore()
    ;(window as any).__auth = useAuthStore()
  })
}

/** 잠금 스트림이 붙었는지. 안 붙었으면 아래 검사는 전부 무의미하다. */
async function waitConnected(page: Page, label: string) {
  await expect
    .poll(async () => page.evaluate(() => {
      const c = (window as any).__collab
      return c ? !!c.connected : null
    }), { timeout: 25_000, message: `${label}: collab 스트림이 안 붙었다` })
    .toBe(true)
}

/** 이 창이 보고 있는 잠금 목록. 스토어에서 직접 읽는다 — 화면보다 앞선다. */
function locksOf(page: Page) {
  return page.evaluate(() => {
    const c = (window as any).__collab
    return c ? JSON.parse(JSON.stringify(c.locks || [])) : null
  })
}

test.describe('두 사람이 같은 프로젝트를 볼 때', () => {
  let alice: Who, tester: Who, graph: string

  test.beforeAll(async () => {
    ;[alice, tester] = await Promise.all([login('alice'), login('test')])
    graph = await sharedGraph(alice, tester)
    console.log(`[test] ${alice.uid} · ${tester.uid} · graph=${graph}`)
  })

  test('앨리스가 잡은 요소를 test 가 열면 잠긴 것으로 보인다', async ({ browser }) => {
    const ca = await browser.newContext()
    const cb = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    const pb = await openApp(cb, tester, graph)
    await waitConnected(pa, 'alice')
    await waitConnected(pb, 'test')

    // 잡는 것은 HTTP 한 번이다. 캔버스를 헤집지 않고 **잠금만** 잰다 —
    // 여기서 실패하면 화면 조작은 볼 것도 없다.
    const elementId = `zz-e2e-${Date.now()}`
    const took = await pa.evaluate(async (id) => {
      const r = await fetch('/api/collab/lock', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ elementId: id, label: '검사용' }),
      })
      return { status: r.status, body: await r.text() }
    }, elementId)
    expect(took.status, `alice 가 잠금을 못 잡았다 — ${took.status} ${took.body}`).toBe(200)
    expect(JSON.parse(took.body).ok, '200 인데 ok 가 아니다').toBe(true)

    try {
      // **test 의 화면에 그 잠금이 도착하는가.** 스트림 한 바퀴는 2초.
      await expect
        .poll(async () => {
          const ls = await locksOf(pb)
          return (ls || []).some((l: any) => l.elementId === elementId)
        }, { timeout: 15_000, message: 'test 창에 잠금이 안 왔다' })
        .toBe(true)

      // 도착하는 것과 **남의 것으로 읽히는 것**은 다르다. uid 가 안 맞으면
      // 목록에는 있는데 화면은 안 잠긴다.
      const blocked = await pb.evaluate((id) => {
        const c = (window as any).__collab
        const me = (window as any).__auth?.user?.uid ?? null
        const l = (c?.locks || []).find((x: any) => x.elementId === id)
        return { me, holder: l?.uid ?? null, isOther: !!c?.heldByOther?.(id) }
      }, elementId)
      expect(blocked.me, 'test 창이 자기 uid 를 모른다 — 그러면 내 잠금도 남의 것으로 보인다')
        .toBeTruthy()
      expect(blocked.isOther, `잠금은 왔는데 남의 것으로 안 읽힌다 (holder=${blocked.holder}, me=${blocked.me})`)
        .toBe(true)

      // **내 잠금은 나에게 잠김이 아니다.** 이게 뒤집히면 잡은 사람이 자기
      // 요소를 못 고친다.
      const selfBlocked = await pa.evaluate((id) => {
        const c = (window as any).__collab
        return !!c?.heldByOther?.(id)
      }, elementId)
      expect(selfBlocked, '잡은 사람 화면에서 자기 잠금이 남의 것으로 보인다').toBe(false)
    } finally {
      await pa.evaluate((id) => fetch('/api/collab/unlock', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ elementId: id }),
      }), elementId).catch(() => {})
      await ca.close(); await cb.close()
    }
  })

  test('앨리스가 저장하면 test 창이 새로고침 없이 안다', async ({ browser }) => {
    const ca = await browser.newContext()
    const cb = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    const pb = await openApp(cb, tester, graph)
    await waitConnected(pa, 'alice')
    await waitConnected(pb, 'test')

    try {
      await pb.evaluate(() => {
        ;(window as any).__seen = []
        window.addEventListener('robo:data-changed', (e: any) =>
          (window as any).__seen.push(e?.detail?.reason))
        ;(window as any).__remote = []
        window.addEventListener('robo:remote-changes', (e: any) =>
          (window as any).__remote.push(...(e?.detail?.changes || [])))
      })
      const revBefore = await pb.evaluate(
        () => (window as any).__collab?.rev ?? null)
      expect(revBefore, 'test 창이 판 번호를 모른다').not.toBeNull()

      // **앨리스가 Inspector 로 저장하는 것과 같은 경로를 쓴다.**
      // `/api/collab/*` 는 알림에서 일부러 제외돼 있어 잠금으로는 판이 안 오른다
      // — 그걸로 재면 앱이 멀쩡해도 실패한다(한 번 그렇게 헛짚었다).
      const target = await pa.evaluate(async () => {
        const r = await fetch('/api/contexts')
        const rows = await r.json().catch(() => [])
        const bc = (Array.isArray(rows) ? rows : []).find((b: any) => b?.id)
        return bc ? { id: bc.id, name: bc.name } : null
      })
      expect(target, '고칠 요소를 못 찾았다 — 이 프로젝트에 BoundedContext 가 있어야 한다').not.toBeNull()

      const wrote = await pa.evaluate(async (t: any) => {
        const r = await fetch(`/api/graph/update-node/${t.id}`, {
          method: 'PUT',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ description: `동시편집 검사 ${Date.now()}` }),
        })
        return { status: r.status, body: (await r.text()).slice(0, 200) }
      }, target)
      expect(wrote.status, `앨리스가 저장하지 못했다 — ${wrote.status} ${wrote.body}`)
        .toBeLessThan(400)

      // 판이 오르는 것이 먼저다. 이게 안 오르면 알릴 것이 없다.
      await expect
        .poll(async () => pb.evaluate(() => (window as any).__collab?.rev ?? -1),
          { timeout: 20_000, message: 'test 창의 판 번호가 안 올랐다' })
        .toBeGreaterThan(revBefore as number)

      // **판만 오르고 화면이 안 울리면 사용자에게는 아무 일도 안 일어난 것이다.**
      await expect
        .poll(async () => pb.evaluate(() => ((window as any).__seen || []).length),
          { timeout: 15_000, message: 'test 창에서 robo:data-changed 가 안 울렸다' })
        .toBeGreaterThan(0)

    } finally {
      await ca.close(); await cb.close()
    }
  })

  /**
   * **여기가 사용자가 보는 자리다.** 위의 둘은 스토어까지만 본다 — 잠금이
   * 스토어에 도착해도 화면이 그대로면 사람은 고칠 수 있다고 믿고 고친다.
   */
  test('잠긴 요소를 열면 Inspector 가 실제로 못 고치게 한다', async ({ browser }) => {
    const ca = await browser.newContext()
    const cb = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    const pb = await openApp(cb, tester, graph)
    await waitConnected(pa, 'alice')
    await waitConnected(pb, 'test')

    /**
     * Inspector 를 연다. **캔버스를 거치지 않는다** — 트리 잎을 더블클릭하면
     * 바로 열린다. `.vue-flow__node` 를 기다리면 0개로 조용히 실패한다
     * (이 프로젝트에서는 캔버스가 아예 안 뜬다).
     *
     * 두 창이 **같은 잎**을 열어야 한다. 이름으로 고르지 않으면 서로 다른 것을
     * 열고도 "잠기지 않았다"고 말하게 된다.
     */
    /** Design 탭으로 가서 트리를 펼친다. 트리는 지연 로딩이라 펼치기가 먼저다. */
    async function gotoDesign(page: Page) {
      const designTab = page.locator('.top-bar__tab, .app-tab, button')
        .filter({ hasText: /^Design$/ }).first()
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
        .toBeGreaterThan(10)
    }

    /**
     * Inspector 를 연다. **캔버스를 거치지 않는다** — 트리 잎을 더블클릭하면
     * 바로 열린다. `.vue-flow__node` 를 기다리면 0개로 조용히 실패한다
     * (이 프로젝트에서는 캔버스가 아예 안 뜬다).
     */
    async function openLeaf(page: Page, label: string) {
      await gotoDesign(page)
      const row = page.locator('.tree-node__label').filter({ hasText: label }).first()
      await expect(row, `트리에 "${label}" 이 없다`).toBeVisible({ timeout: 15_000 })
      await row.dblclick()
      await expect(page.locator('.inspector-panel'),
        'Inspector 가 안 열렸다').toBeVisible({ timeout: 15_000 })
      await page.waitForTimeout(2500)
    }

    /**
     * 두 창이 같은 것을 열도록 **한 창에서 먼저 골라 본다.**
     *
     * 이름 모양으로 고르면 안 된다 — BC 머리("총무 및 경비 (supporting)")도
     * 규칙을 통과하는데 더블클릭해도 Inspector 가 안 열린다. **열리는지를 직접
     * 재서** 고른다.
     */
    async function pickLeafLabel(page: Page): Promise<string> {
      await gotoDesign(page)
      const labels = (await page.locator('.tree-node__label').allTextContents())
        .map((t) => t.trim())
        .filter((t) => t && !/\(\d+\)\s*$/.test(t))
      for (const label of labels.slice(0, 40)) {
        const row = page.locator('.tree-node__label').filter({ hasText: label }).first()
        if (!(await row.isVisible().catch(() => false))) continue
        await row.dblclick()
        if (await page.locator('.inspector-panel')
          .isVisible({ timeout: 4_000 }).catch(() => false)) return label
      }
      throw new Error(`트리 ${labels.length}개 중 Inspector 가 열리는 잎이 없다`)
    }

    try {
      const label = await pickLeafLabel(pa)
      console.log(`[test] 두 창이 열 요소: "${label}"`)
      await openLeaf(pa, label)

      const heldByAlice = await pa.evaluate(() =>
        ((window as any).__collab?.locks || []).map((l: any) => l.elementId))
      expect(heldByAlice.length,
        'alice 가 열었는데 잠금이 안 잡혔다 — 여는 순간 잠그기로 돼 있다')
        .toBeGreaterThan(0)
      const elementId = heldByAlice[0]

      await openLeaf(pb, label)
      // 같은 요소를 열었는지 — 아니면 아래 검사는 아무것도 안 잰 것이다.
      await expect
        .poll(() => pb.evaluate((id) => {
          const c = (window as any).__collab
          return !!c?.heldByOther?.(id)
        }, elementId), { timeout: 15_000, message: 'test 창이 잠금을 남의 것으로 안 본다' })
        .toBe(true)

      // ① 배너가 보이는가
      await expect(pb.locator('.lockbar'),
        '잠김 안내가 안 뜬다 — 사람은 고칠 수 있다고 믿는다')
        .toBeVisible({ timeout: 10_000 })

      // ② 저장이 막히는가. 패널에 저장 버튼이 둘이라 **전부** 잠겨야 한다 —
      //    하나만 재면 남은 하나로 덮어쓸 수 있다.
      await expect
        .poll(() => pb.locator('.inspector-panel__btn.primary')
          .evaluateAll((els: any[]) => els.length && els.every((e) => e.disabled)),
          { timeout: 10_000, message: '저장 버튼이 안 잠겼다' })
        .toBe(true)

      // ③ **입력칸이 막히는가.** ①②만 있으면 사람은 계속 칠 수 있고, 다 친
      //    다음에야 저장이 안 된다는 것을 안다 — 그 사이에 친 글자는 사라진다.
      const editable = await pb.evaluate(() => {
        const panel = document.querySelector('.inspector-panel')
        if (!panel) return null
        const fields = [...panel.querySelectorAll('input, textarea, select')]
          .filter((el: any) => el.type !== 'hidden' && el.offsetParent !== null)
        // **`el.disabled` 로 재면 안 된다.** 그 속성은 자기 태그에 붙은 값만
        // 비추고, `fieldset` 이 물려준 상태는 `false` 로 보인다. 실제로 막혔는지
        // 는 `:disabled` 로 재야 안다.
        return {
          total: fields.length,
          open: fields.filter((el: any) => !el.matches(':disabled') && !el.readOnly).length,
        }
      })
      expect(editable, 'Inspector 가 안 열렸다').not.toBeNull()
      expect(editable!.total, '입력칸이 하나도 없으면 위 검사는 아무것도 안 잰 것이다')
        .toBeGreaterThan(0)
      expect(editable!.open,
        `잠겼는데 입력칸 ${editable!.open}/${editable!.total} 개가 아직 열려 있다`)
        .toBe(0)

      // ④ **잡은 사람은 여전히 고칠 수 있어야 한다.** ③만 재면 전부 잠가 놓고도
      //    통과한다 — 그러면 아무도 아무것도 못 고친다.
      const mine = await pa.evaluate(() => {
        const panel = document.querySelector('.inspector-panel')
        const fields = [...(panel?.querySelectorAll('input, textarea, select') || [])]
          .filter((el: any) => el.type !== 'hidden' && el.offsetParent !== null)
        return {
          total: fields.length,
          open: fields.filter((el: any) => !el.matches(':disabled') && !el.readOnly).length,
        }
      })
      expect(mine.open, `잡은 사람의 입력칸이 ${mine.open}/${mine.total} 만 열려 있다`)
        .toBeGreaterThan(0)

      // ⑤ **읽기로 보는 사람도 다른 탭은 봐야 한다.** 잠금은 겹쳐 쓰는 것을
      //    막는 것이지 사람을 막는 것이 아니다. 탭까지 잠그면 옆 사람이 무엇을
      //    하는지도 못 본다.
      const tabsUsable = await pb.evaluate(() => {
        const tabs = [...document.querySelectorAll('.inspector-panel .inspector-tab')]
        return { total: tabs.length, open: tabs.filter((t: any) => !t.matches(':disabled')).length }
      })
      expect(tabsUsable.total, 'Inspector 탭을 못 찾았다').toBeGreaterThan(0)
      expect(tabsUsable.open, `잠겼다고 탭까지 ${tabsUsable.total - tabsUsable.open}개 잠겼다`)
        .toBe(tabsUsable.total)
    } finally {
      await ca.close(); await cb.close()
    }
  })

  /**
   * **두 번째 증상.** "수정 후 렌더링이 안 된다" 는 보고가 여기다.
   *
   * 위의 "판 번호가 오른다"는 스토어까지만 본다. 사람이 보는 것은 **열어 둔
   * 화면의 값**이다 — Inspector 를 열어 둔 채로 남이 고치면 그 값이 바뀌는가.
   */
  test('열어 둔 Inspector 가 남의 저장을 반영한다', async ({ browser }) => {
    // 창 둘을 띄우고 트리를 훑는다 — 기본 60초로는 모자란다.
    test.setTimeout(180_000)
    const ca = await browser.newContext()
    const cb = await browser.newContext()
    const pa = await openApp(ca, alice, graph)
    const pb = await openApp(cb, tester, graph)
    await waitConnected(pa, 'alice')
    await waitConnected(pb, 'test')

    async function gotoDesign(page: Page) {
      const t = page.locator('.top-bar__tab, .app-tab, button').filter({ hasText: /^Design$/ }).first()
      if (await t.isVisible({ timeout: 8_000 }).catch(() => false)) { await t.click(); await page.waitForTimeout(1500) }
      const expand = page.locator('.tree-action-btn[title="Expand All"]')
      await expect(expand).toBeVisible({ timeout: 20_000 })
      await expand.click()
      await expect.poll(() => page.locator('.tree-node__label').count(), { timeout: 25_000 })
        .toBeGreaterThan(10)
    }

    try {
      // **앨리스가 먼저 연다(=잡는다), test 는 읽기로 본다.** 사용자가 본
      // 상황이 이것이다. 거꾸로 두면 test 가 잡은 쪽이 되어 남의 변경이
      // **일부러** 걸러진다(내가 고치는 중이니까) — 그러면 설계대로 도는 것을
      // 결함이라고 적게 된다. 한 번 그렇게 헛짚었다.
      //
      // 고를 때 **저장이 실제로 켜지는 요소**를 찾는다. UserStory 패널은 첫
      // textarea 를 고쳐도 저장이 안 켜진다(그 칸이 dirty 판정에 안 들어간다 —
      // 별도 문제로 적어 뒀다). 그런 걸 잡으면 저장을 못 눌러 이 검사가
      // 엉뚱한 데서 멈춘다.
      await gotoDesign(pa)
      const labels = (await pa.locator('.tree-node__label').allTextContents()).map((t) => t.trim())
      const marker = `남의저장${Date.now()}`
      let opened: { label: string; id: string } | null = null

      for (const label of labels.filter((t) => t && !/\(\d+\)\s*$/.test(t)).slice(0, 14)) {
        const row = pa.locator('.tree-node__label').filter({ hasText: label }).first()
        if (!(await row.isVisible().catch(() => false))) continue
        await row.dblclick()
        if (!(await pa.locator('.inspector-panel').isVisible({ timeout: 4_000 }).catch(() => false))) continue
        await pa.waitForTimeout(1500)
        const ids = await pa.evaluate(() =>
          ((window as any).__collab?.locks || []).map((l: any) => l.elementId))
        if (!ids.length) continue

        const field = pa.locator('.inspector-panel textarea').first()
        if (!(await field.isVisible({ timeout: 3_000 }).catch(() => false))) continue
        await field.click()
        await field.press('End')
        await field.pressSequentially(` ${marker}`, { delay: 10 })
        if (await enabledSave(pa).isEnabled({ timeout: 3_000 }).catch(() => false)) {
          opened = { label, id: ids[0] }
          break
        }
      }
      expect(opened, '저장이 켜지는 요소를 못 찾았다').not.toBeNull()
      console.log(`[test] 앨리스가 잡고 고친 요소: "${opened!.label}"`)

      // test 도 같은 것을 연다 — 읽기로.
      await gotoDesign(pb)
      const row = pb.locator('.tree-node__label').filter({ hasText: opened!.label }).first()
      await expect(row, `test 트리에 "${opened!.label}" 이 없다`).toBeVisible({ timeout: 15_000 })
      await row.dblclick()
      await expect(pb.locator('.inspector-panel')).toBeVisible({ timeout: 15_000 })
      await pb.waitForTimeout(2500)
      expect(await pb.evaluate((id) => !!(window as any).__collab?.heldByOther?.(id), opened!.id),
        'test 가 읽기로 보고 있어야 한다 — 잡은 쪽이면 남의 변경이 일부러 걸러진다')
        .toBe(true)

      const before = await pb.evaluate(() => {
        ;(window as any).__seen = []
        window.addEventListener('robo:data-changed', (e: any) =>
          (window as any).__seen.push(e?.detail?.reason))
        ;(window as any).__remote = []
        window.addEventListener('robo:remote-changes', (e: any) =>
          (window as any).__remote.push(...(e?.detail?.changes || [])))
        return [...document.querySelectorAll('.inspector-panel input, .inspector-panel textarea')]
          .map((el: any) => el.value).filter(Boolean)
      })
      expect(before.some((v: string) => v.includes(marker)),
        'test 가 열기 전에 이미 바뀐 값을 보고 있다 — 이러면 아무것도 안 잰 것이다')
        .toBe(false)

      // **사용자가 한 그대로** 저장 버튼을 누른다. API 를 직접 부르면 화면이
      // 보여 주는 칸과 어긋난다 — `description` 을 고쳤더니 그래프에는 들어갔고
      // 화면의 textarea 는 `action` 이라 아무 일도 없어 보였다.
      const save = enabledSave(pa)
      await expect(save, '앨리스의 저장 버튼이 잠겼다 — 잡은 사람인데').toBeEnabled({ timeout: 10_000 })
      await save.click()
      await pa.waitForTimeout(2000)

      await expect
        .poll(() => pb.evaluate((m) => [
          ...document.querySelectorAll('.inspector-panel input, .inspector-panel textarea'),
        ].some((el: any) => String(el.value || '').includes(m)), marker), {
          timeout: 25_000,
          message: `열어 둔 Inspector 가 남의 저장을 반영 안 한다 (그대로: ${JSON.stringify(before).slice(0, 160)})`,
        })
        .toBe(true)
        .catch(async (err: any) => {
          const diag = await pb.evaluate((id) => ({
            dataChanged: (window as any).__seen,
            remote: ((window as any).__remote || []).map((c: any) => c?.targetId),
            rev: (window as any).__collab?.rev,
            openId: id,
          }), opened!.id)
          throw new Error(`${err.message}\n  진단: ${JSON.stringify(diag)}`)
        })
    } finally {
      await ca.close(); await cb.close()
    }
  })
})
