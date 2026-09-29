import { test, expect } from '@playwright/test'

// 공통 로그인 상태를 쓰지 않는다 — 로그인 화면 자체를 본다. 미리 로그인된 채로 들어가면
// 이 파일이 확인하려는 것이 통째로 가려진다.
test.use({ storageState: { cookies: [], origins: [] } })

/**
 * 로그인 게이트 · 개발용 로그인 · 관리자 화면.
 *
 * 서버 설정을 바꿔 가며 확인할 수 없으므로(백엔드를 재시작해야 한다) 인증 관련
 * 응답만 가로챈다. 여기서 보려는 것은 **화면이 서버의 대답에 어떻게 반응하는가**
 * 이고, 서버가 실제로 막는지는 `scripts/verify_auth_session.py` 가 본다.
 *
 * 두 층을 나눠 두는 이유는, 화면에서 숨기는 것과 서버가 막는 것을 같은 검사로
 * 확인하면 하나가 빠졌을 때 드러나지 않기 때문이다.
 */

const PROVIDER = {
  provider: 'swp',
  enterprise: true,
  callbackAllowlist: [],
  embeddings: {},
  devLogin: { enabled: true, loginId: 'test', employeeNo: 'DEV-TEST', allowRemote: false },
  approvalRequired: true,
  jwtSecretConfigured: true,
  sessionTtlSeconds: 28800,
  enforce: true,
  bindConnection: false,
}

const ADMIN_USER = {
  uid: 'DEV-TEST', displayName: '개발용 계정', department: '개발',
  role: 'admin', status: 'approved', source: 'dev',
}

async function stub(page: any, opts: { me?: any; provider?: any } = {}) {
  await page.route('**/api/auth/provider', (r: any) =>
    r.fulfill({ json: opts.provider ?? PROVIDER }))
  await page.route('**/api/auth/me', (r: any) =>
    r.fulfill({ json: opts.me ?? { authenticated: false, status: 'anonymous' } }))
}

test.describe('로그인 게이트', () => {
  test.setTimeout(120_000)

  test('강제가 켜져 있으면 로그인 화면이 앞을 막는다', async ({ page }) => {
    await stub(page)
    await page.goto('/', { waitUntil: 'domcontentloaded' })

    const card = page.locator('.login__card')
    await expect(card, '로그인 화면이 떠야 한다').toBeVisible({ timeout: 30_000 })
    await expect(card).toContainText('로그인이 필요합니다')
    await expect(page.getByRole('button', { name: 'SWP 로 로그인' })).toBeVisible()
    // 개발용 칸은 서버가 켜져 있다고 답할 때만 뜬다.
    await expect(card).toContainText('개발용 로그인')
    await expect(card, '사내 배포본 경고가 함께 보여야 한다').toContainText('꺼져 있어야 합니다')
  })

  test('서버가 개발용 로그인을 껐다고 하면 칸이 없다', async ({ page }) => {
    await stub(page, { provider: { ...PROVIDER, devLogin: { enabled: false } } })
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.login__card')).toBeVisible({ timeout: 30_000 })
    await expect(page.locator('.login__card')).not.toContainText('개발용 로그인')
  })

  test('강제가 꺼져 있으면 지금까지처럼 바로 들어간다', async ({ page }) => {
    await stub(page, { provider: { ...PROVIDER, enforce: false } })
    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.locator('.login__card')).toHaveCount(0)
    await expect(page.locator('.gate__card'), '강제가 꺼졌으면 기다릴 이유도 없다').toHaveCount(0)
  })

  /**
   * **여기가 2026-09-29 에 비어 있던 자리다.**
   *
   * 위의 모든 검사는 `/api/auth/provider` 를 즉시 성공으로 가로챈다. 그래서
   * "서버가 대답하기 전" 이라는 상태를 한 번도 밟지 않았고, 그 상태에서 앱이
   * 통째로 열리는 것을 아무도 못 봤다. 실측: 창이 뜬 뒤 백엔드가 응답하기까지
   * 44초, 첫 설치에서는 2분 이상. 그 시간 동안 `provider === null` →
   * `enforced === false` → 게이트가 열렸다.
   *
   * `enforce: false` 를 확인하는 검사가 있었던 것이 오히려 함정이었다 —
   * **"응답이 없다" 와 "강제가 꺼져 있다" 를 코드가 같게 다뤘기 때문에**
   * 통과하는 검사가 곧 통과하는 우회였다.
   */
  test('응답이 오기 전에는 로그인 화면도 런처도 열지 않는다', async ({ page }) => {
    // 영원히 대답하지 않는 서버. 끊지 않고 붙잡는다 — 실제 증상이 그랬다
    // (백엔드가 아직 listen 하지 않아 연결 자체가 늦는다).
    await page.route('**/api/auth/provider', () => { /* 응답하지 않는다 */ })
    await page.route('**/api/auth/me', (r: any) =>
      r.fulfill({ json: { authenticated: false, status: 'anonymous' } }))
    await page.goto('/', { waitUntil: 'domcontentloaded' })

    const gate = page.locator('.gate__card')
    await expect(gate, '확인 중 화면이 앞을 막아야 한다').toBeVisible({ timeout: 30_000 })
    await expect(gate).toContainText('인증 설정을 확인하는 중')

    // 열려서는 안 되는 것들. 이 세 줄이 옛 코드에서 실패한다.
    await expect(page.locator('.launcher'), '런처가 열리면 안 된다').toHaveCount(0)
    await expect(page.locator('.app-container'), '작업화면이 열리면 안 된다').toHaveCount(0)
    await expect(page.locator('.login__card'), '아직 강제 여부를 모른다').toHaveCount(0)
  })

  test('늦게라도 오면 그때 로그인 화면으로 넘어간다', async ({ page }) => {
    await page.route('**/api/auth/me', (r: any) =>
      r.fulfill({ json: { authenticated: false, status: 'anonymous' } }))
    // 첫 요청은 실패시키고, 두 번째부터 성공시킨다 — 재시도가 진짜로 도는지 본다.
    let calls = 0
    await page.route('**/api/auth/provider', async (r: any) => {
      calls += 1
      if (calls === 1) return r.abort('connectionrefused')
      await r.fulfill({ json: PROVIDER })
    })

    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.gate__card')).toBeVisible({ timeout: 15_000 })
    await expect(page.locator('.login__card'), '재시도가 성공하면 로그인으로 바뀐다')
      .toBeVisible({ timeout: 30_000 })
    await expect(page.locator('.gate__card')).toHaveCount(0)
    expect(calls, '한 번 실패했으면 다시 물어봐야 한다').toBeGreaterThan(1)
  })

  test('끝까지 못 닿으면 열지 않고 이유를 말한다', async ({ page }) => {
    await page.route('**/api/auth/me', (r: any) => r.abort('connectionrefused'))
    // 1회 예산으로 부르는 경로를 흉내 내지 않고, 화면이 스스로 포기한 뒤를 본다.
    // `attempts` 예산이 크므로 스토어를 직접 몰아 세운다.
    await page.route('**/api/auth/provider', (r: any) => r.abort('connectionrefused'))
    await page.addInitScript(() => {
      // 부팅 재시도 예산을 짧게 줄인다 — 300초를 기다릴 수는 없다.
      ;(window as any).__ROBO_AUTH_PROVIDER_ATTEMPTS__ = 2
    })
    await page.goto('/', { waitUntil: 'domcontentloaded' })

    const gate = page.locator('.gate__card')
    await expect(gate).toBeVisible({ timeout: 30_000 })
    await expect(gate, '닿지 못한 것을 "인증 꺼짐" 으로 읽지 않는다')
      .toContainText('인증 서버에 닿지 못했습니다', { timeout: 30_000 })
    await expect(gate).toContainText('열지 않았습니다')
    await expect(page.locator('.launcher')).toHaveCount(0)
    await expect(page.locator('.app-container')).toHaveCount(0)
  })

  test('승인 대기는 안내를 보여 주고 토큰을 저장하지 않는다', async ({ page }) => {
    await stub(page)
    await page.route('**/api/auth/dev-login', (r: any) =>
      r.fulfill({ json: { authenticated: false, status: 'pending',
                          user: { ...ADMIN_USER, role: 'member', status: 'pending' } } }))
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.login__card')).toBeVisible({ timeout: 30_000 })

    await page.locator('.login__input').first().fill('test')
    await page.locator('.login__input').nth(1).fill('test')
    await page.getByRole('button', { name: '들어가기' }).click()

    await expect(page.locator('.login__card')).toContainText('승인을 기다리는 중입니다')
    const stored = await page.evaluate(() => window.sessionStorage.getItem('robo.auth.token'))
    expect(stored, '대기 상태에서는 토큰이 저장되면 안 된다').toBeNull()
  })

  test('로그인하면 게이트가 열리고 이후 요청에 토큰이 실린다', async ({ page }) => {
    await stub(page)
    await page.route('**/api/auth/dev-login', (r: any) =>
      r.fulfill({ json: { authenticated: true, status: 'approved',
                          user: ADMIN_USER, accessToken: 'stub-token', expiresIn: 28800 } }))

    const seen: string[] = []
    await page.route('**/api/contexts', async (r: any) => {
      seen.push(r.request().headers()['authorization'] || '')
      await r.fulfill({ json: [] })
    })

    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.login__card')).toBeVisible({ timeout: 30_000 })
    await page.locator('.login__input').first().fill('test')
    await page.locator('.login__input').nth(1).fill('test')
    await page.getByRole('button', { name: '들어가기' }).click()

    await expect(page.locator('.login__card'), '게이트가 열려야 한다').toHaveCount(0, { timeout: 20_000 })
    const stored = await page.evaluate(() => window.sessionStorage.getItem('robo.auth.token'))
    expect(stored).toBe('stub-token')

    // 인터셉터가 실어 보내는지 — 호출부를 고치지 않고도 붙는 것이 요점이다.
    await page.evaluate(() => fetch('/api/contexts'))
    await expect.poll(() => seen.length, { timeout: 10_000 }).toBeGreaterThan(0)
    expect(seen[seen.length - 1]).toBe('Bearer stub-token')
  })
})

test.describe('관리자 화면', () => {
  test.setTimeout(120_000)

  const USERS = {
    users: [
      { uid: '10001', displayName: '김대기', department: '인사', status: 'pending', role: 'member' },
      { uid: 'DEV-TEST', displayName: '개발용 계정', department: '개발', status: 'approved', role: 'admin' },
    ],
    approvalRequired: true,
    counts: { pending: 1, approved: 1, rejected: 0 },
  }

  async function openSettings(page: any, me: any) {
    // 토큰은 `sessionStorage` 에 있다 — 앱을 끄면 로그인부터이기 때문이다
    // (`auth-session-lifetime.spec.ts`).
    // 저장된 토큰이 없으면 화면이 서버에 물어보지도 않고 익명으로 둔다 —
    // 게이트에 걸려 TopBar 자체가 안 뜬다. 로그인해 둔 상태를 흉내 낸다.
    await page.addInitScript(() =>
      window.sessionStorage.setItem('robo.auth.token', 'stub-token'))
    await stub(page, { me })
    await page.route('**/api/accounts', (r: any) => r.fulfill({ json: USERS }))
    await page.goto('/', { waitUntil: 'networkidle' })
    await page.locator('.settings-btn').first().click()
    await expect(page.locator('.settings-panel')).toBeVisible({ timeout: 15_000 })
  }

  test('관리자에게만 사용자 관리가 보인다', async ({ page }) => {
    await openSettings(page, { authenticated: true, status: 'approved', user: ADMIN_USER })
    const section = page.locator('.settings-section', { hasText: '사용자 관리' })
    await expect(section).toBeVisible({ timeout: 15_000 })
    await expect(section).toContainText('승인 대기 1명')
    await expect(section.locator('tbody tr')).toHaveCount(1)   // 기본 필터가 '승인 대기'
    await expect(section).toContainText('김대기')
  })

  test('일반 사용자에게는 자리가 없다', async ({ page }) => {
    await openSettings(page, {
      authenticated: true, status: 'approved',
      user: { ...ADMIN_USER, uid: '20002', role: 'member' },
    })
    await expect(page.locator('.settings-section', { hasText: '사용자 관리' })).toHaveCount(0)
  })

  test('자기 계정에는 처리 버튼이 없다', async ({ page }) => {
    await openSettings(page, { authenticated: true, status: 'approved', user: ADMIN_USER })
    const section = page.locator('.settings-section', { hasText: '사용자 관리' })
    await section.locator('.ua__tab', { hasText: '전체' }).click()
    const selfRow = section.locator('tbody tr', { hasText: 'DEV-TEST' })
    await expect(selfRow).toContainText('본인')
    await expect(selfRow.locator('.ua__act')).toHaveCount(0)
  })

  test('승인을 누르면 그 사번으로 서버를 부른다', async ({ page }) => {
    const calls: any[] = []
    await openSettings(page, { authenticated: true, status: 'approved', user: ADMIN_USER })
    await page.route('**/api/accounts/*/status', async (r: any) => {
      calls.push({ url: r.request().url(), body: r.request().postDataJSON() })
      await r.fulfill({ json: { uid: '10001', status: 'approved' } })
    })
    // 이름을 부분 일치로 찾으면 '승인 대기' 탭이 먼저 잡힌다. 표 안의 버튼으로 좁힌다.
    const section = page.locator('.settings-section', { hasText: '사용자 관리' })
    const row = section.locator('tbody tr', { hasText: '10001' })
    await row.getByRole('button', { name: '승인', exact: true }).click()
    await expect.poll(() => calls.length, { timeout: 10_000 }).toBe(1)
    expect(calls[0].url).toContain('/api/accounts/10001/status')
    expect(calls[0].body).toEqual({ status: 'approved' })
  })
})
