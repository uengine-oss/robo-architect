import { test, expect } from '@playwright/test'

// 공통 로그인 상태를 쓰지 않는다 — 선택기의 초기 상태를 직접 만든다. 미리 로그인된 채로 들어가면
// 이 파일이 확인하려는 것이 통째로 가려진다.
test.use({ storageState: { cookies: [], origins: [] } })

/**
 * 프로젝트 선택기.
 *
 * 서버 응답을 가로채 **화면이 무엇을 보여 주고 무엇을 보내는가**만 본다. 권한이
 * 실제로 막히는지는 `scripts/verify_projects.py` 와
 * `scripts/verify_connection_binding.py` 가 저장소 층에서 확인한다.
 *
 * 여기서 특히 보려는 것은 **고른 프로젝트가 이후 요청에 실리는가** 다. 실리지
 * 않으면 화면에는 바뀐 것처럼 보이는데 서버는 이전 프로젝트를 계속 본다 —
 * 오류 없이 틀린 화면이라 가장 나쁜 실패다.
 */

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
    { graph: 'prj_aaa', displayName: '인사관리 설계', ownerUid: 'DEV-TEST', level: 'admin' },
    { graph: 'prj_bbb', displayName: '급여 개편', ownerUid: '20002', level: 'read' },
  ],
}

const MEMBERS = {
  members: [
    { role: 'p_dev_test', level: 'admin', uid: 'DEV-TEST', displayName: '개발용 계정' },
    { role: 'p_20002', level: 'read', uid: '20002', displayName: '이초대' },
  ],
}

async function open(page: any, opts: { project?: string; projects?: any } = {}) {
  // addInitScript 는 **새로고침마다** 돈다. 프로젝트를 무조건 다시 심으면 화면에서
  // 바꾼 선택을 덮어써, 제품이 멀쩡한데도 안 바뀐 것처럼 보인다.
  // 없을 때만 심어 첫 진입 상태만 만든다.
  await page.addInitScript(([token, project]: [string, string | null]) => {
    window.localStorage.setItem('robo.auth.token', token)
    if (project && !window.localStorage.getItem('robo.auth.project')) {
      window.localStorage.setItem('robo.auth.project', project)
    }
  }, ['stub-token', opts.project ?? null])

  await page.route('**/api/auth/provider', (r: any) => r.fulfill({ json: PROVIDER }))
  await page.route('**/api/auth/me', (r: any) => r.fulfill({ json: ME }))
  await page.route('**/api/projects', (r: any) => {
    if (r.request().method() !== 'GET') return r.fallback()
    return r.fulfill({ json: opts.projects ?? PROJECTS })
  })
  await page.goto('/', { waitUntil: 'networkidle' })
}

test.describe('프로젝트 선택기', () => {
  test.setTimeout(120_000)

  test('고른 프로젝트 이름이 상단에 보인다', async ({ page }) => {
    await open(page, { project: 'prj_aaa' })
    const btn = page.locator('.pp__btn')
    await expect(btn).toBeVisible({ timeout: 30_000 })
    await expect(btn).toContainText('인사관리 설계')
  })

  test('고르지 않았으면 선택 안 됨으로 보인다', async ({ page }) => {
    await open(page)
    await expect(page.locator('.pp__btn')).toContainText('선택 안 됨', { timeout: 30_000 })
  })

  test('목록에 등급이 함께 보인다', async ({ page }) => {
    await open(page, { project: 'prj_aaa' })
    await page.locator('.pp__btn').click()
    const items = page.locator('.pp__item')
    await expect(items).toHaveCount(2)
    await expect(items.nth(0)).toContainText('인사관리 설계')
    await expect(items.nth(0)).toContainText('관리')
    await expect(items.nth(1)).toContainText('읽기')
    await expect(items.nth(0), '지금 보고 있는 것이 표시돼야 한다')
      .toHaveClass(/pp__item--on/)
  })

  test('바꾸면 저장되고 이후 요청에 실린다', async ({ page }) => {
    await open(page, { project: 'prj_aaa' })
    await page.locator('.pp__btn').click()
    await page.locator('.pp__item', { hasText: '급여 개편' }).click()

    // 바꾸면 새로고침한다 — 스토어를 하나씩 비우다 빠뜨리면 이전 데이터가 남는다.
    await page.waitForLoadState('networkidle')
    await expect(page.locator('.pp__btn')).toContainText('급여 개편', { timeout: 30_000 })
    const saved = await page.evaluate(() => window.localStorage.getItem('robo.auth.project'))
    expect(saved).toBe('prj_bbb')

    const seen: string[] = []
    await page.route('**/api/contexts', async (r: any) => {
      seen.push(r.request().headers()['x-project-graph'] || '')
      await r.fulfill({ json: [] })
    })
    await page.evaluate(() => fetch('/api/contexts'))
    await expect.poll(() => seen.length, { timeout: 10_000 }).toBeGreaterThan(0)
    expect(seen[seen.length - 1], '고른 프로젝트가 요청에 실려야 한다').toBe('prj_bbb')
  })

  test('권한이 사라진 프로젝트는 선택이 풀린다', async ({ page }) => {
    // 목록에 없는 graph 를 고른 상태로 들어온다 — 회수됐거나 지워진 경우다.
    await open(page, { project: 'prj_gone' })
    await expect(page.locator('.pp__btn')).toContainText('선택 안 됨', { timeout: 30_000 })
    const saved = await page.evaluate(() => window.localStorage.getItem('robo.auth.project'))
    expect(saved, '남겨 두면 계속 403 을 받는다').toBeNull()
  })

  test('만들 때는 이름만 보낸다', async ({ page }) => {
    const posted: any[] = []
    await open(page)
    await page.route('**/api/projects', async (r: any) => {
      if (r.request().method() !== 'POST') return r.fallback()
      posted.push(r.request().postDataJSON())
      await r.fulfill({ json: { graph: 'prj_new', displayName: '새 설계', level: 'admin' } })
    })
    await page.locator('.pp__btn').click()
    await page.getByRole('button', { name: '＋ 새 프로젝트' }).click()
    await page.locator('.pp__input').fill('새 설계')
    await page.getByRole('button', { name: '만들기' }).click()

    await expect.poll(() => posted.length, { timeout: 10_000 }).toBe(1)
    expect(posted[0]).toEqual({ name: '새 설계' })
  })

  test('관리 등급일 때만 공유 관리가 뜬다', async ({ page }) => {
    await open(page, { project: 'prj_aaa' })
    await page.locator('.pp__btn').click()
    await expect(page.getByRole('button', { name: '공유 관리' })).toBeVisible()
  })

  test('읽기 등급이면 공유 관리가 없다', async ({ page }) => {
    await open(page, { project: 'prj_bbb' })
    await page.locator('.pp__btn').click()
    await expect(page.getByRole('button', { name: '공유 관리' })).toHaveCount(0)
  })

  test('초대는 사번과 등급을 보내고 소유자는 회수할 수 없다', async ({ page }) => {
    const invited: any[] = []
    await open(page, { project: 'prj_aaa' })
    await page.route('**/api/projects/prj_aaa/members', async (r: any) => {
      if (r.request().method() === 'POST') {
        invited.push(r.request().postDataJSON())
        return r.fulfill({ json: { graph: 'prj_aaa', uid: '30003', level: 'write' } })
      }
      await r.fulfill({ json: MEMBERS })
    })
    await page.locator('.pp__btn').click()
    await page.getByRole('button', { name: '공유 관리' }).click()

    const rows = page.locator('.pp__members li')
    await expect(rows).toHaveCount(2, { timeout: 15_000 })
    await expect(rows.filter({ hasText: 'DEV-TEST' }), '소유자에게는 회수가 없어야 한다')
      .toContainText('소유자')
    await expect(rows.filter({ hasText: '20002' }).locator('.pp__revoke')).toBeVisible()

    await page.locator('.pp__invite .pp__input').fill('30003')
    await page.locator('.pp__select').selectOption('write')
    await page.getByRole('button', { name: '초대' }).click()
    await expect.poll(() => invited.length, { timeout: 10_000 }).toBe(1)
    expect(invited[0]).toEqual({ uid: '30003', level: 'write' })
  })

  test('로그인하지 않았으면 선택기가 없다', async ({ page }) => {
    await page.route('**/api/auth/provider', (r: any) => r.fulfill({ json: PROVIDER }))
    await page.route('**/api/auth/me', (r: any) =>
      r.fulfill({ json: { authenticated: false, status: 'anonymous' } }))
    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.locator('.pp__btn')).toHaveCount(0)
  })
})
