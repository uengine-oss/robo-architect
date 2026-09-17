import { test, expect, request as pwRequest, type Page } from '@playwright/test'
import { graphWithDesign } from './helpers/collab'
import { readFileSync } from 'fs'
import { resolve } from 'path'

/**
 * **기본 수정 액션이 도는가** — 화면에서 직접 고치는 것.
 *
 * 동시편집 검사는 "남의 창에 가는가"만 본다. 그 앞에 있는 질문은 **내 창에서
 * 고쳐지긴 하는가** 다. 요소 종류마다 저장 경로가 다른데 그걸 한 번도 종류별로
 * 재본 적이 없다.
 *
 *     머리쪽 저장(title="Save")   일반 — `isDirty || propIsDirty`
 *     아래쪽 저장                 UserStory 전용 — `userStoryDirty`
 *                                 US 노드에서만 그려진다
 *
 * 이 둘을 섞어 재고 "저장이 안 켜진다"고 적은 적이 있다. 그래서 여기서는
 * **어느 버튼이 켜졌는지까지** 남긴다.
 *
 * 재는 것은 셋이다. 하나라도 빠지면 "된다"고 할 수 없다.
 *
 *     ① 고치면 저장이 켜진다
 *     ② 눌러서 오류가 안 난다
 *     ③ **그래프에 실제로 들어갔다** — 다시 읽어서 확인한다
 *
 * ③ 없이 ①②만 재면 저장이 조용히 아무것도 안 해도 통과한다.
 */

const API = process.env.ROBO_API_URL || 'http://localhost:8000'

function devPassword(loginId: string): string {
  if (loginId === (process.env.AUTH_DEV_LOGIN_ID || 'test')) {
    return process.env.AUTH_DEV_LOGIN_PASSWORD || 'test'
  }
  const envPath = resolve(process.cwd(), '../.env')
  const env = readFileSync(envPath, 'utf-8')
  const line = env.split('\n').find((l) => l.startsWith('AUTH_DEV_LOGIN_ACCOUNTS='))
  for (const acc of (line || '').slice('AUTH_DEV_LOGIN_ACCOUNTS='.length).trim().split(',')) {
    const f = acc.split(':')
    if (f[0]?.trim() === loginId && f[1]) return f[1]
  }
  throw new Error(`${envPath} 의 AUTH_DEV_LOGIN_ACCOUNTS 에 '${loginId}' 가 없다`)
}

test.use({ storageState: { cookies: [], origins: [] } })

let token = ''
let graph = ''

test.beforeAll(async () => {
  const ctx = await pwRequest.newContext()
  try {
    const r = await ctx.post(`${API}/api/auth/dev-login`, {
      multipart: { loginId: 'test', password: devPassword('test') },
    })
    token = (await r.json()).accessToken
    expect(token, '로그인하지 못했다').toBeTruthy()
    // **첫 번째를 그냥 집지 않는다.** 09-16 에 빈 프로젝트가 하나 생기자 그것이
    // 목록 맨 앞에 와서, 트리가 안 떠 "앱이 안 된다"처럼 보였다. 같은 함정이
    // `collab-two-users` 에도 있었다(done-v2 §58).
    graph = await graphWithDesign(token)
    console.log(`[test] graph=${graph}`)
  } finally { await ctx.dispose() }
})

async function openApp(browser: any): Promise<Page> {
  const ctx = await browser.newContext()
  const page = await ctx.newPage()
  await page.addInitScript(([t, g]) => {
    localStorage.setItem('robo.auth.token', t as string)
    localStorage.setItem('robo.auth.project', g as string)
  }, [token, graph])
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('#app')).toBeVisible({ timeout: 20_000 })
  const designTab = page.locator('.top-bar__tab, .app-tab, button').filter({ hasText: /^Design$/ }).first()
  if (await designTab.isVisible({ timeout: 8_000 }).catch(() => false)) {
    await designTab.click()
    await page.waitForTimeout(1500)
  }
  const expand = page.locator('.tree-action-btn[title="Expand All"]')
  await expect(expand, 'Design 탭의 트리가 안 뜬다').toBeVisible({ timeout: 20_000 })
  await expand.click()
  await expect
    .poll(() => page.locator('.tree-node__label').count(), { timeout: 25_000 })
    .toBeGreaterThan(10)
  return page
}

/** 그래프에 실제로 뭐가 들어갔는지. 화면을 안 거치고 직접 읽는다. */
async function readBack(id: string): Promise<any> {
  const ctx = await pwRequest.newContext()
  try {
    const r = await ctx.get(`${API}/api/graph/expand-with-bc/${encodeURIComponent(id)}`, {
      headers: { Authorization: `Bearer ${token}`, 'X-Project-Graph': graph },
    })
    if (!r.ok()) return null
    const j = await r.json()
    const nodes = j.nodes || j.graph?.nodes || []
    return nodes.find((n: any) => n.id === id || n?.data?.id === id) || null
  } finally { await ctx.dispose() }
}

/**
 * 고친 값을 제자리로 돌려놓는다.
 *
 * 화면을 거쳐 되돌리면 또 dirty 판정을 타야 해서 실패할 수 있다. 되돌리기는
 * **반드시 되는 길**이어야 하므로 API 로 직접 쓴다. 어느 칸이었는지는 화면이
 * 알려 주지 않으므로, 실제로 바뀐 필드를 원래 값과 대조해 찾는다.
 */
async function restore(id: string, original: string): Promise<boolean> {
  const ctx = await pwRequest.newContext()
  try {
    for (const field of ['description', 'action', 'name', 'displayName']) {
      const r = await ctx.put(`${API}/api/graph/update-node/${encodeURIComponent(id)}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Project-Graph': graph,
          'content-type': 'application/json',
        },
        data: { [field]: original },
      })
      if (r.ok()) {
        const back = JSON.stringify(await readBack(id) || {})
        if (back.includes(original.slice(-24))) return true
      }
    }
    return false
  } catch {
    return false
  } finally { await ctx.dispose() }
}

test('요소를 열어 고치고 저장하면 그래프에 들어간다', async ({ browser }) => {
  test.setTimeout(240_000)
  const page = await openApp(browser)

  const labels = (await page.locator('.tree-node__label').allTextContents())
    .map((t) => t.trim())
    .filter((t) => t && !/\(\d+\)\s*$/.test(t))

  type Row = { label: string; type: string; button: string | null; saved: boolean; note: string }
  const rows: Row[] = []
  const seenTypes = new Set<string>()

  const skipped: string[] = []

  // **줄은 번호로 잡는다.** 라벨 텍스트로 찾으면 `.first()` 가 다른 줄에 갈 수
  // 있고, 그러면 **연 요소와 종류를 서로 다른 줄에서 읽는다** — 실제로 그래서
  // UserStory 를 열어 놓고 "aggregate 가 저장이 안 된다"고 보고했다.
  const rowLocator = page.locator('.tree-node__label')
  const rowCount = Math.min(await rowLocator.count(), 120)

  for (let i = 0; i < rowCount; i += 1) {
    if (rows.length >= 8) break
    const row = rowLocator.nth(i)
    const label = (await row.textContent().catch(() => ''))?.trim() || ''
    if (!label || /\(\d+\)\s*$/.test(label)) continue
    if (!(await row.isVisible().catch(() => false))) { skipped.push(`${label.slice(0,18)}: 안 보임`); continue }
    await row.dblclick()
    if (!(await page.locator('.inspector-panel').isVisible({ timeout: 3_000 }).catch(() => false))) {
      skipped.push(`${label.slice(0,18)}: 패널이 안 열림`); continue
    }
    await page.waitForTimeout(1600)

    // 열린 요소의 id 는 잠금 목록이 알려 준다(여는 순간 잡는다).
    const openId = await page.evaluate(async () => {
      const { useCollabStore } = await import('/src/features/collab/collab.store.js')
      const c: any = useCollabStore()
      return (c.locks || []).map((l: any) => l.elementId)[0] || null
    })
    if (!openId) { skipped.push(`${label.slice(0,18)}: 잠금이 안 잡힘(=id 모름)`); continue }

    // **종류는 트리 아이콘에서 읽는다.** 그래프를 다시 읽어 `type` 을 보려
    // 했다가 전부 UserStory 로 나왔다 — 그 응답은 요소 하나가 아니라 주변
    // 서브그래프라, 같은 id 로 찾은 것이 내가 연 그것이 아니었다.
    // 트리는 `tree-node__icon--{type}` 으로 종류를 그대로 들고 있다.
    // 종류는 **연 바로 그 줄**에서 읽는다 — 텍스트로 다시 찾지 않는다.
    const type = await row.evaluate((el: any) => {
      const icon = el.closest('.tree-node__header')?.querySelector('[class*="tree-node__icon--"]')
      const cls = [...(icon?.classList || [])].find((c: string) => c.startsWith('tree-node__icon--'))
      return cls ? cls.replace('tree-node__icon--', '') : '(모름)'
    })
    if (seenTypes.has(type)) { skipped.push(`${label.slice(0,18)}: ${type} 이미 봄`); continue }
    seenTypes.add(type)

    const marker = `수정확인${Date.now()}`
    const field = page.locator('.inspector-panel textarea').first()
    if (!(await field.isVisible({ timeout: 2_500 }).catch(() => false))) {
      rows.push({ label, type, button: null, saved: false, note: '고칠 textarea 가 없다' })
      continue
    }
    const originalValue = await field.inputValue()
    // **이 입력칸이 정말 이 요소의 것인가.** 앞 요소의 흔적이 그대로 보이면
    // 패널이 안 바뀐 것일 수 있다 — 그러면 저장 여부를 단정하면 안 된다.
    // (`.inspector-panel__title` 은 쓸 수 없다. 요소 이름이 아니라 고정
    //  머리말 "Inspector · User Story" 라, 그걸로 가르려다 멀쩡한 7종까지
    //  거짓으로 실패시켰다.)
    const looksBorrowed = /수정확인\d{10,}/.test(originalValue)
    await field.click()
    await field.press('End')
    await field.pressSequentially(` ${marker}`, { delay: 8 })
    await page.waitForTimeout(500)

    // **어느 버튼이 켜졌는지까지 남긴다.** 이 둘을 섞어 재고 헛짚은 적이 있다.
    const btns = await page.locator('.inspector-panel__btn.primary').evaluateAll(
      (els: any[]) => els.map((e) => ({ title: e.title || '(없음)', disabled: e.disabled })))
    const liveIdx = btns.findIndex((b) => !b.disabled)
    if (liveIdx < 0) {
      rows.push({ label, type, button: null, saved: false,
        note: `고쳤는데 저장이 안 켜진다 — ${JSON.stringify(btns)}` })
      continue
    }

    await page.locator('.inspector-panel__btn.primary').nth(liveIdx).click()
    await page.waitForTimeout(3000)

    // **"값이 안 들어갔다"와 "응답에 그 요소가 없다"는 다른 사건이다.**
    // `expand-with-bc` 는 요소 하나가 아니라 주변 서브그래프를 준다 — 연 요소가
    // 그 안에 없으면 저장이 멀쩡해도 `null` 이 온다. 둘을 뭉치면 앱을 파게 된다.
    const after = await readBack(openId)
    const saved = after !== null && JSON.stringify(after).includes(marker)
    const unreadable = after === null

    // **더럽힌 것은 되돌린다.**
    //
    // 이 검사는 `zz_` 일회용 graph 가 아니라 **실제 프로젝트**를 연다 —
    // 화면을 거쳐야 하는 검사라 일회용 graph 로는 못 한다. 그 대신 고친 값을
    // 반드시 제자리로 돌려놓는다. 안 그러면 검사를 돌릴 때마다 남의 설계 문서에
    // "수정확인1789..." 가 한 줄씩 쌓인다(실제로 그랬다).
    //
    // 화면으로 되돌리면 또 dirty 판정을 타야 해서 실패할 수 있다. 되돌리기는
    // **반드시 되는 길**이어야 하므로 API 로 직접 쓴다.
    const restored = await restore(openId, originalValue)

    rows.push({
      label, type, button: btns[liveIdx].title, saved,
      note: [
        saved ? ''
          : unreadable
            ? `**못 읽었다** — expand-with-bc 응답에 ${openId} 가 없다. 저장 여부는 모른다`
            : looksBorrowed
              ? `**입력칸이 남의 것으로 보인다** — 원래값에 앞선 검사 흔적이 있다 (끝: ${originalValue.slice(-16)}). 저장 여부는 모른다`
              : `저장은 눌렀는데 그래프에 없다 (원래값 끝: ${originalValue.slice(-16)})`,
        restored ? '' : '**되돌리기 실패 — 이 요소에 검사 흔적이 남았다**',
      ].filter(Boolean).join(' · '),
    })
  }

  console.log(`\n건너뛴 것 ${skipped.length}개 (앞 12):`)
  for (const s2 of skipped.slice(0, 12)) console.log('   ' + s2)

  console.log('\n요소 종류별 — 직접 편집')
  for (const r of rows) {
    console.log(`  ${(r.type + '').padEnd(16)} 저장버튼=${String(r.button).padEnd(8)} 들어감=${r.saved}  ${r.note}`)
  }

  expect(rows.length, '열리는 요소를 하나도 못 찾았다').toBeGreaterThan(0)
  const broken = rows.filter((r) => !r.saved)
  expect(broken, `직접 편집이 안 되는 종류: ${broken.map((b) => `${b.type}(${b.note})`).join(' · ')}`)
    .toEqual([])

  // **실 데이터를 더럽힌 채로 통과하면 안 된다.** 되돌리기가 실패한 것이
  // 있으면 그 자리에 검사 흔적이 남았다는 뜻이고, 다음 사람이 그걸 설계 내용으로
  // 읽는다.
  const dirty = rows.filter((r) => r.note.includes('되돌리기 실패'))
  expect(dirty.map((d) => `${d.type}/${d.label.slice(0, 20)}`),
    '검사가 실제 프로젝트에 흔적을 남겼다').toEqual([])
})
