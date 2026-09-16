import { test, expect, request as pwRequest, type Page } from '@playwright/test'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import { execFileSync } from 'child_process'

/**
 * **화면에서 문서를 넣어 BPM 이 나오는가 — 그리고 그게 우리 컨테이너가 낸 것인가.**
 *
 * 지금까지 pdf2bpmn 자체 호스팅은 **API 층까지만** 쟀다
 * (`scripts/verify_pdf2bpmn_selfhosted.py`). 사람은 화면에서 문서를 넣는다.
 * 그 사이에는 검사가 한 번도 안 지난 자리가 셋 있었다.
 *
 * ```
 * 화면 관문   코드 분석 그래프가 비어 있으면 **문서 첨부 칸 자체가 안 뜬다**
 * 경로 선택   facade 는 **PDF 만** 탄다 (pdf_path 가 있어야 한다).
 *             txt·md 를 올리면 조용히 native 로 떨어지고 native 는 빈 결과를 낸다
 * 출처        응답만 보면 바깥 서비스가 낸 것과 구분이 안 된다
 * ```
 *
 * 그래서 여기서는 **컨테이너에 들어온 요청 수**로 출처를 가른다. 로그 본문이
 * 아니라 개수다 — 본문은 요약돼 사라진 적이 있다.
 */

const API = process.env.ROBO_API_URL || 'http://localhost:8000'
const PDF = resolve(process.cwd(), 'tests/fixtures/leave-request-process.pdf')
const CONTAINER = process.env.PDF2BPMN_CONTAINER || 'pdf2bpmn-facade'

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

/** 컨테이너가 지금까지 받은 `/api/consulting-bpmn` 요청 수. */
function facadeHits(): number {
  const out = execFileSync('bash', ['-lc',
    `docker logs ${CONTAINER} 2>&1 | grep -c 'consulting-bpmn' || true`],
    { encoding: 'utf-8' })
  return parseInt(out.trim() || '0', 10)
}

async function login(loginId: string) {
  const ctx = await pwRequest.newContext()
  try {
    const r = await ctx.post(`${API}/api/auth/dev-login`, {
      multipart: { loginId, password: devPassword(loginId) },
    })
    const body = await r.json().catch(() => ({} as any))
    expect(body.accessToken, `${loginId} 로 로그인하지 못했다`).toBeTruthy()
    return { token: body.accessToken as string, uid: body.user?.uid || '' }
  } finally { await ctx.dispose() }
}

/**
 * 코드 분석 데이터가 **있는** 프로젝트. 없으면 화면에서 문서를 넣을 수 없다 —
 * 그 관문을 우회하면 이 검사가 재려는 화면 경로를 안 지난다.
 */
async function projectWithAnalyzerData(token: string): Promise<string> {
  const ctx = await pwRequest.newContext()
  try {
    const r = await ctx.get(`${API}/api/projects`, { headers: { Authorization: `Bearer ${token}` } })
    const rows = r.ok() ? ((await r.json()).projects || []) : []
    const candidates = rows.filter((p: any) => p.level && p.level !== 'read').map((p: any) => p.graph)
    const pinned = process.env.ROBO_TEST_PROJECT
    for (const g of (pinned ? [pinned] : candidates)) {
      const s = await ctx.get(`${API}/api/ingest/stats`, {
        headers: { Authorization: `Bearer ${token}`, 'X-Project-Graph': g },
      })
      const body = s.ok() ? await s.json().catch(() => ({})) : {}
      if (!body?.hasData) continue
      // **인제스천은 교체다** — 시작하는 순간 이 프로젝트의 설계를 지운다.
      // 설계가 들어 있는 프로젝트를 집으면 검사가 실 데이터를 날린다.
      // 한 번 그렇게 UserStory 를 깨뜨린 적이 있다. 비어 있는 것만 쓴다.
      const c = await ctx.get(`${API}/api/contexts`, {
        headers: { Authorization: `Bearer ${token}`, 'X-Project-Graph': g },
      })
      const ctxRows = c.ok() ? await c.json().catch(() => []) : []
      if (Array.isArray(ctxRows) && ctxRows.length > 0) continue
      return g
    }
    throw new Error(
      `코드 분석 데이터가 있는 프로젝트가 없다 (후보: ${candidates.join(', ')}). ` +
      `화면의 "코드 분석" 탭은 그게 없으면 문서 첨부 칸을 안 띄운다.`,
    )
  } finally { await ctx.dispose() }
}

async function openApp(page: Page, token: string, graph: string) {
  await page.addInitScript(([t, g]) => {
    localStorage.setItem('robo.auth.token', t as string)
    localStorage.setItem('robo.auth.project', g as string)
  }, [token, graph])
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('#app')).toBeVisible({ timeout: 20_000 })
}

test.use({ storageState: { cookies: [], origins: [] } })

test.describe('문서 업로드 → BPM (자체 호스팅 pdf2bpmn)', () => {
  test('화면에서 PDF 를 넣으면 우리 컨테이너가 BPM 을 낸다', async ({ page }) => {
    test.setTimeout(10 * 60_000)

    const who = await login('test')
    const graph = await projectWithAnalyzerData(who.token)
    const before = facadeHits()
    console.log(`[test] graph=${graph} facade hits before=${before}`)

    // 업로드 응답에서 session_id 를 집는다 — 나중에 그래프에 되읽는다.
    let sessionId = ''
    page.on('response', async (res) => {
      if (res.url().includes('/api/ingest/hybrid/upload') && res.ok()) {
        sessionId = (await res.json().catch(() => ({})))?.session_id || sessionId
      }
    })

    await openApp(page, who.token, graph)

    // ── 사람이 밟는 순서 그대로 ────────────────────────────────────────────
    await page.getByRole('button', { name: 'Stories', exact: true }).first().click()
    await page.getByRole('button', { name: '문서 업로드' }).first().click()
    await expect(page.locator('.modal-body').first()).toBeVisible({ timeout: 15_000 })

    await page.getByRole('button', { name: '코드 분석' }).click()

    // 첨부 칸이 떠야 한다. 안 뜨면 관문에 막힌 것이고, 그건 앱이 아니라
    // 이 프로젝트에 분석 데이터가 없다는 뜻이다.
    const drop = page.locator('.analyzer-doc-section')
    await expect(drop, '코드 분석 탭에 문서 첨부 칸이 안 떴다').toBeVisible({ timeout: 20_000 })

    await page.locator('.analyzer-section input[type="file"]').setInputFiles(PDF)

    const start = page.getByRole('button', { name: '분석 시작' })
    await expect(start).toBeEnabled({ timeout: 10_000 })
    await start.click()

    // 지울 것이 있으면 확인을 받는다 (ENT-ING-002). 그 대화상자는 서버에
    // `replacement-preview` 를 물어본 **뒤에** 뜨므로 3초로는 못 잡는다 —
    // 한 번 그 3초에 걸려 "업로드가 안 나갔다"로 보였다. 앱이 아니라 여기가 짧았다.
    //
    // **`isVisible()` 로 기다리면 안 된다** — 옵션에 timeout 을 줘도 즉시
    // 판정한다. 대화상자가 아직 안 떴을 때 false 가 나오고, 그러면 여기를
    // 조용히 건너뛰어 인제스천이 영영 시작되지 않는다. 두 회차를 그렇게 썼다.
    const confirm = page.locator('.clear-confirm-dialog')
    const appeared = await confirm.waitFor({ state: 'visible', timeout: 20_000 })
      .then(() => true).catch(() => false)
    if (appeared) await confirm.getByRole('button', { name: /교체/ }).click()

    // ── Phase 1 이 끝날 때까지 ────────────────────────────────────────────
    await expect
      .poll(() => sessionId, { timeout: 60_000, message: 'hybrid 업로드가 안 나갔다' })
      .not.toBe('')

    const ctx = await pwRequest.newContext()
    let snap: any = null
    try {
      await expect
        .poll(async () => {
          const r = await ctx.get(`${API}/api/ingest/hybrid/session/${sessionId}/snapshot`, {
            headers: { Authorization: `Bearer ${who.token}`, 'X-Project-Graph': graph },
          })
          // **못 읽은 것과 0 개를 구분한다.** 앞선 회차에서 그래프 저장소가
          // 중간에 끊겼는데 이 자리가 그것을 0 으로 뭉개, 실제로는 task 6 개가
          // 만들어졌는데 "Phase 1 이 아무것도 안 냈다"로 8분을 기다렸다.
          if (!r.ok()) throw new Error(`snapshot 을 못 읽었다 (${r.status()}) — 앱이 아니라 여기가 막힌 것일 수 있다`)
          snap = await r.json().catch(() => null)
          return (snap?.tasks || []).length
        }, { timeout: 8 * 60_000, intervals: [5_000], message: 'Phase 1 이 task 를 하나도 안 냈다' })
        .toBeGreaterThan(0)
    } finally { await ctx.dispose() }

    // **개수가 아니라 내용으로 본다.** 0 이 아니라고 값이 있는 게 아니다.
    const names = (snap.tasks || []).map((t: any) => t?.name).filter(Boolean)
    console.log(`[test] tasks=${names.length} :: ${names.slice(0, 8).join(' · ')}`)
    expect(names.length, 'task 에 이름이 하나도 없다 — 개수만 찼다').toBeGreaterThan(0)
    expect(String(snap.bpmn_xml || ''), 'BPMN XML 이 안 왔다').toContain('<bpmn')

    // ── 그게 **우리 것인가** ──────────────────────────────────────────────
    const after = facadeHits()
    console.log(`[test] facade hits after=${after}`)
    expect(after,
      `자체 호스팅 컨테이너(${CONTAINER})에 요청이 안 들어왔다 — 바깥 서비스나 native 로 갔다`)
      .toBeGreaterThan(before)

    // 캔버스에도 그려지는가 — 사람이 보는 마지막 자리.
    //
    // **한 번 새로 연다.** 인제스천이 도는 중의 Process 탭은 아직 비어 있다
    // (뒤 단계까지 끝나야 채워진다). 새로 열면 세션을 그래프에서 되찾아 그린다 —
    // 재방문이 사람이 실제로 보는 자리이기도 하다.
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page.locator('#app')).toBeVisible({ timeout: 20_000 })
    await page.getByRole('button', { name: 'Process', exact: true }).first().click()
    await expect(page.locator('.djs-element').first(),
      '캔버스에 BPMN 요소가 안 그려졌다').toBeVisible({ timeout: 60_000 })
    expect(await page.locator('.djs-element').count(),
      'BPMN 요소가 한두 개뿐이다 — 흐름이 안 그려진 것이다').toBeGreaterThan(5)
  })
})
