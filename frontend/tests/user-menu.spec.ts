import { test, expect } from '@playwright/test'

/**
 * 사용자 표시와 로그아웃.
 *
 * 로그아웃에서 확인해야 할 것은 **토큰이 지워지는가**가 아니라 **화면에 남은
 * 데이터까지 사라지는가** 다. 토큰만 지우고 화면을 그대로 두면 다음 사람이
 * 앞사람의 프로젝트를 계속 본다 — 오류 없이 남의 데이터를 보여 주는 것이다.
 */

// 공통 로그인 상태를 쓰지 않는다 — 로그인 전/후를 여기서 직접 만든다.
test.use({ storageState: { cookies: [], origins: [] } })

const PROVIDER = {
  provider: 'swp', enterprise: true, callbackAllowlist: [], embeddings: {},
  devLogin: { enabled: true, loginId: 'test' }, approvalRequired: true,
  jwtSecretConfigured: true, sessionTtlSeconds: 28800, enforce: true, bindConnection: true,
}

const USER = {
  uid: 'DEV-TEST', displayName: '개발용 계정', department: '개발',
  role: 'admin', status: 'approved', source: 'dev',
}

async function signedIn(page: any, user = USER) {
  // addInitScript 는 **새로고침마다** 돈다. 로그아웃이 지운 것을 다시 심으면
  // 지워졌는지를 관찰할 수 없다 — 첫 진입에만 심도록 표식을 남긴다.
  await page.addInitScript(([token, project]: [string, string]) => {
    if (!window.localStorage.getItem('__seeded')) {
      window.localStorage.setItem('__seeded', '1')
      window.localStorage.setItem('robo.auth.token', token)
      window.localStorage.setItem('robo.auth.project', project)
    }
  }, ['stub-token', 'prj_aaa'])
  await page.route('**/api/auth/provider', (r: any) => r.fulfill({ json: PROVIDER }))
  await page.route('**/api/auth/me', (r: any) =>
    r.fulfill({ json: { authenticated: true, status: 'approved', user } }))
  await page.route('**/api/projects', (r: any) =>
    r.request().method() === 'GET'
      ? r.fulfill({ json: { projects: [{ graph: 'prj_aaa', displayName: '인사관리 설계', level: 'admin' }] } })
      : r.fallback())
  await page.goto('/', { waitUntil: 'networkidle' })
}

test.describe('사용자 메뉴', () => {
  test.setTimeout(120_000)

  test('누구로 들어와 있는지 보인다', async ({ page }) => {
    await signedIn(page)
    const btn = page.locator('.um__btn')
    await expect(btn).toBeVisible({ timeout: 30_000 })
    await expect(btn).toContainText('개발용 계정')
    await btn.click()
    const menu = page.locator('.um__menu')
    await expect(menu).toContainText('DEV-TEST')
    await expect(menu).toContainText('개발')
  })

  test('관리자와 개발용 로그인을 표시한다', async ({ page }) => {
    await signedIn(page)
    await page.locator('.um__btn').click()
    const menu = page.locator('.um__menu')
    await expect(menu.locator('.um__tag--admin')).toHaveText('관리자')
    await expect(menu.locator('.um__tag--dev'), '사내 배포본에서 이게 보이면 설정이 잘못된 것이다')
      .toHaveText('개발용 로그인')
  })

  test('일반 사용자에게는 관리자 표시가 없다', async ({ page }) => {
    await signedIn(page, { ...USER, role: 'member', source: 'swp' })
    await page.locator('.um__btn').click()
    await expect(page.locator('.um__tag--admin')).toHaveCount(0)
    await expect(page.locator('.um__tag--dev')).toHaveCount(0)
  })

  test('로그아웃하면 토큰과 프로젝트 선택이 함께 지워진다', async ({ page }) => {
    await signedIn(page)
    await page.locator('.um__btn').click()
    await page.getByRole('button', { name: '로그아웃' }).click()

    // 새로고침이 따라온다 — 토큰만 지우면 읽어 둔 설계가 화면에 그대로 남는다.
    // 재적재 중에는 evaluate 가 끊기므로 값이 비워질 때까지 지켜본다.
    await expect.poll(async () => {
      try {
        return await page.evaluate(() => [
          window.localStorage.getItem('robo.auth.token'),
          window.localStorage.getItem('robo.auth.project'),
        ])
      } catch {
        return ['(재적재 중)', '(재적재 중)']
      }
    }, { timeout: 30_000, message: '프로젝트 선택도 함께 지워져야 한다' }).toEqual([null, null])
  })

  test('로그아웃하면 화면을 다시 띄운다 — 앞사람 데이터가 남으면 안 된다', async ({ page }) => {
    await signedIn(page)
    // 재적재를 눈으로 확인한다. 토큰만 지우고 화면을 그대로 두면 이미 읽어 둔
    // 설계가 남아, 다음 사람이 앞사람의 프로젝트를 계속 본다.
    await page.evaluate(() => { (window as any).__beforeLogout = true })
    await page.locator('.um__btn').click()
    await page.getByRole('button', { name: '로그아웃' }).click()

    await expect.poll(async () => {
      try {
        return await page.evaluate(() => (window as any).__beforeLogout === true)
      } catch {
        return true   // 재적재 중
      }
    }, { timeout: 30_000, message: '페이지가 다시 뜨지 않았다' }).toBe(false)
  })

  test('로그아웃하면 로그인 화면으로 돌아간다', async ({ page }) => {
    await signedIn(page)
    // 로그아웃 뒤에는 세션이 없으므로 서버도 익명으로 답한다.
    await page.locator('.um__btn').click()
    await page.route('**/api/auth/me', (r: any) =>
      r.fulfill({ json: { authenticated: false, status: 'anonymous' } }))
    await page.getByRole('button', { name: '로그아웃' }).click()
    await expect(page.locator('.login__card')).toBeVisible({ timeout: 30_000 })
  })

  test('로그인하지 않았으면 메뉴가 없다', async ({ page }) => {
    // 강제를 꺼서 화면이 열리게 한다. 강제가 켜져 있으면 게이트가 앞을 막아
    // TopBar 자체가 안 뜨므로, 메뉴가 없는 것이 당연해져 검사가 무의미해진다.
    await page.route('**/api/auth/provider', (r: any) =>
      r.fulfill({ json: { ...PROVIDER, enforce: false } }))
    await page.route('**/api/auth/me', (r: any) =>
      r.fulfill({ json: { authenticated: false, status: 'anonymous' } }))
    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.locator('.top-bar'), '검사 전제 — 화면이 열려 있어야 한다')
      .toBeVisible({ timeout: 30_000 })
    await expect(page.locator('.um__btn')).toHaveCount(0)
  })
})
