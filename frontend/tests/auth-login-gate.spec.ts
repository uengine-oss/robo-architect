import { test, expect } from '@playwright/test'

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
    const stored = await page.evaluate(() => window.localStorage.getItem('robo.auth.token'))
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
    const stored = await page.evaluate(() => window.localStorage.getItem('robo.auth.token'))
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
    // 저장된 토큰이 없으면 화면이 서버에 물어보지도 않고 익명으로 둔다 —
    // 게이트에 걸려 TopBar 자체가 안 뜬다. 로그인해 둔 상태를 흉내 낸다.
    await page.addInitScript(() =>
      window.localStorage.setItem('robo.auth.token', 'stub-token'))
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
