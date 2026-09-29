import { test, expect } from '@playwright/test'

test.use({ storageState: { cookies: [], origins: [] } })

/**
 * 세션이 **앱을 끄면 사라지고, 새로고침은 견디는가**.
 *
 * ## 왜 바꿨나
 *
 * 토큰이 `localStorage` 에 있었다. 그러면 앱을 껐다 켜도 로그인 화면이 뜨지
 * 않는다(TTL 8시간). 2026-09-29 에 실제로 그랬다 — 새 빌드를 설치하고 켰는데
 * 전날 `test`/`test` 세션이 그대로 살아 있어 런처로 바로 들어갔다.
 *
 * 사내 배포본에서 그것은 **자리를 비운 PC 가 다음 사람에게 열려 있다**는 뜻이다.
 *
 * `sessionStorage` 는 문서 컨텍스트가 살아 있는 동안만 남는다. 창을 닫으면
 * 사라지고, 새로고침은 견딘다.
 *
 * ## 새로고침을 견디는 것이 왜 중요한가
 *
 * 프로젝트 전환이 `location.reload()` 로 통째로 다시 띄운다(`projects.store`).
 * 여기서 토큰이 날아가면 **프로젝트를 바꿀 때마다 로그인**하게 된다.
 * 그래서 "끄면 사라진다" 와 "새로고침은 견딘다" 를 **둘 다** 잰다.
 */

const PROVIDER = {
  provider: 'swp',
  enterprise: true,
  devLogin: { enabled: true, loginId: 'test', employeeNo: 'DEV-TEST' },
  approvalRequired: false,
  jwtSecretConfigured: true,
  sessionTtlSeconds: 28800,
  enforce: true,
  bindConnection: false,
}

const USER = { uid: 'DEV-TEST', displayName: '개발용 계정', role: 'member', status: 'approved' }

async function stub(page: any, opts: { authenticated?: boolean } = {}) {
  await page.route('**/api/auth/provider', (r: any) => r.fulfill({ json: PROVIDER }))
  await page.route('**/api/auth/me', (r: any) =>
    r.fulfill({
      json: opts.authenticated
        ? { authenticated: true, status: 'approved', user: USER }
        : { authenticated: false, status: 'anonymous' },
    }))
  await page.route('**/api/auth/dev-login', (r: any) =>
    r.fulfill({
      json: {
        authenticated: true, status: 'approved', user: USER,
        accessToken: 'stub-token', expiresIn: 28800,
      },
    }))
}

async function loginAsTest(page: any) {
  await expect(page.locator('.login__card')).toBeVisible({ timeout: 30_000 })
  await page.locator('.login__input').first().fill('test')
  await page.locator('.login__input').nth(1).fill('test')
  await page.getByRole('button', { name: '들어가기' }).click()
  await expect(page.locator('.login__card')).toHaveCount(0, { timeout: 20_000 })
}

test.describe('토큰이 어디에 남는가', () => {
  test.setTimeout(150_000)

  test('로그인하면 sessionStorage 에 남고 localStorage 에는 남지 않는다', async ({ page }) => {
    await stub(page)
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await loginAsTest(page)

    const where = await page.evaluate(() => ({
      session: window.sessionStorage.getItem('robo.auth.token'),
      local: window.localStorage.getItem('robo.auth.token'),
    }))
    expect(where.session, 'sessionStorage 에 있어야 한다').toBe('stub-token')
    expect(where.local, 'localStorage 에 남으면 앱을 꺼도 로그인이 유지된다').toBeNull()
  })

  test('예전 빌드가 localStorage 에 남긴 토큰을 지운다', async ({ page }) => {
    await stub(page)
    // 옛 빌드의 흔적을 심어 둔다.
    await page.addInitScript(() => {
      try {
        window.localStorage.setItem('robo.auth.token', 'old-token')
        window.localStorage.setItem('robo.auth.project', 'prj_old')
      } catch { /* ignore */ }
    })
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.login__card')).toBeVisible({ timeout: 30_000 })

    const left = await page.evaluate(() => ({
      token: window.localStorage.getItem('robo.auth.token'),
      project: window.localStorage.getItem('robo.auth.project'),
    }))
    expect(left.token, '남아 있는 자격증명은 지운다').toBeNull()
    expect(left.project).toBeNull()
  })
})

test.describe('세션의 수명', () => {
  test.setTimeout(150_000)

  test('새로고침은 견딘다 — 프로젝트 전환이 reload 를 쓴다', async ({ page }) => {
    await stub(page)
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await loginAsTest(page)

    // 로그인 뒤에는 서버도 인증된 사용자로 답한다.
    await stub(page, { authenticated: true })
    await page.reload({ waitUntil: 'domcontentloaded' })

    await expect(page.locator('.login__card'), '새로고침마다 로그인시키면 안 된다')
      .toHaveCount(0, { timeout: 20_000 })
    expect(await page.evaluate(() => window.sessionStorage.getItem('robo.auth.token')))
      .toBe('stub-token')
  })

  test('창을 닫으면 사라진다 — 앱을 켜면 로그인부터', async ({ page, context }) => {
    await stub(page)
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await loginAsTest(page)

    // 새 페이지 = 새 문서 컨텍스트. 앱을 껐다 켠 것과 같은 자리다.
    const fresh = await context.newPage()
    await stub(fresh)
    await fresh.goto('/', { waitUntil: 'domcontentloaded' })

    expect(
      await fresh.evaluate(() => window.sessionStorage.getItem('robo.auth.token')),
      '새 문서에는 토큰이 없어야 한다',
    ).toBeNull()
    await expect(fresh.locator('.login__card'), '로그인 화면이 떠야 한다')
      .toBeVisible({ timeout: 30_000 })
    await expect(fresh.locator('.login__card')).toContainText('SWP 로 로그인')
    await expect(fresh.locator('.login__card'), 'dev 로그인 칸도 함께')
      .toContainText('개발용 로그인')
    await fresh.close()
  })
})
