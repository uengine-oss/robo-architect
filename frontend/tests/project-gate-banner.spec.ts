import { test, expect } from '@playwright/test'

/**
 * 프로젝트가 없을 때 화면이 뭐라고 말하는가.
 *
 * 프로젝트가 0개인 사용자는 화면마다 403 을 받는다. 백엔드는 정확히
 * `{"detail": "프로젝트를 먼저 고르세요.", "code": "PROJECT_NOT_SELECTED"}` 로
 * 답하는데, 화면은 **"서버 연결 실패 (서버가 실행 중인지 확인해주세요)"** 라고
 * 알렸다. 멀쩡한 백엔드를 의심하게 만드는 거짓말이다.
 *
 * 원인은 문구로 판정한 것이었다.
 *
 *   "Failed to fetch user stories (HTTP 403)"   ← 우리가 만든 문구
 *   e.message.includes('Failed to fetch')       ← 네트워크 판정 규칙
 *
 * 그래서 두 가지를 잰다. **안내가 뜨는가**, 그리고 **거짓말을 멈췄는가.**
 * 앞의 것만 재면 배너를 띄우면서 동시에 "서버 연결 실패"를 찍어도 통과한다.
 */

const DENIED = {
  status: 403,
  contentType: 'application/json',
  body: JSON.stringify({ detail: '프로젝트를 먼저 고르세요.', code: 'PROJECT_NOT_SELECTED' }),
}

const FORBIDDEN = {
  status: 403,
  contentType: 'application/json',
  body: JSON.stringify({ detail: '이 프로젝트에 접근할 권한이 없습니다: prj_x',
                         code: 'PROJECT_FORBIDDEN' }),
}

/** graph 를 쓰는 경로는 전부 막고, 프로젝트 목록만 정상으로 둔다. */
async function denyGraphRoutes(page: any, reply: any) {
  await page.route('**/api/projects', (route: any) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ projects: [] }),
  }))
  await page.route('**/api/contexts**', (route: any) => route.fulfill(reply))
  await page.route('**/api/user-stories/**', (route: any) => route.fulfill(reply))
  await page.route('**/api/requirements/**', (route: any) => route.fulfill(reply))
}

test('프로젝트를 안 골랐으면 그렇게 말한다', async ({ page }) => {
  await denyGraphRoutes(page, DENIED)
  await page.goto('/', { waitUntil: 'networkidle' })

  const banner = page.locator('.pgate')
  await expect(banner).toBeVisible()
  await expect(banner).toContainText('프로젝트를 선택해 주세요')
  // 할 일이 같이 있어야 한다 — "안 된다"만 말하는 안내는 사람을 세워 둔다.
  await expect(banner).toContainText('새로 만들 수 있습니다')
  // 개발자 말(상태 코드·서버 사정)은 화면에 나오지 않는다.
  await expect(banner).not.toContainText('403')
  await expect(banner).not.toContainText('권한 응답')
})

test('403 을 서버 장애로 옮기지 않는다', async ({ page }) => {
  const lied: string[] = []
  page.on('console', (msg) => {
    const t = msg.text()
    if (t.includes('서버 연결 실패') || t.includes('서버가 실행 중인지')) lied.push(t)
  })

  await denyGraphRoutes(page, DENIED)
  await page.goto('/', { waitUntil: 'networkidle' })
  // 배너가 떴다 = 403 이 실제로 오갔다. 이 줄이 없으면 "아무 요청도 없었다"가
  // 통과로 읽힌다.
  await expect(page.locator('.pgate')).toBeVisible()

  expect(lied, `403 인데 서버 장애라고 말했다:\n${lied.join('\n')}`).toEqual([])
})

test('HTTP 오류를 서버 장애로 옮기지 않는다', async ({ page }) => {
  // 403 만 재면 부족하다 — 403 은 문구가 한국어라 옛 규칙에도 안 걸린다.
  // **거짓말이 실제로 나오던 모양은 우리가 만든 영어 문구다.**
  //
  //   "Failed to fetch user stories (HTTP 500)"   ← 우리 문구
  //   msg.includes('Failed to fetch')             ← 옛 판정 규칙
  //
  // 500 으로 재야 그 규칙이 고쳐졌는지 드러난다.
  const lied: string[] = []
  page.on('console', (msg) => {
    const t = msg.text()
    if (t.includes('서버 연결 실패') || t.includes('서버가 실행 중인지')) lied.push(t)
  })

  await page.route('**/api/projects', (route: any) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ projects: [] }),
  }))
  const broken = { status: 500, contentType: 'application/json',
                   body: JSON.stringify({ detail: 'boom' }) }
  let served = 0
  const serve500 = (route: any) => { served += 1; return route.fulfill(broken) }
  await page.route('**/api/contexts**', serve500)
  await page.route('**/api/user-stories/**', serve500)

  await page.goto('/', { waitUntil: 'networkidle' })
  // **500 을 실제로 내보냈는지부터 센다.** 아무 요청도 없었으면 "거짓말이 없다"는
  // 통과가 공허하다 — 화면 상태가 아니라 가로챈 횟수로 잰다.
  await expect.poll(() => served, { timeout: 5000 }).toBeGreaterThan(0)

  expect(lied, `HTTP 500 인데 서버 장애라고 말했다:\n${lied.join('\n')}`).toEqual([])
})

test('권한이 없는 것과 안 고른 것을 구별한다', async ({ page }) => {
  // **프로젝트를 고른 상태**여야 이 경우가 성립한다. 목록이 비어 있으면 화면이
  // 고를 것이 없어 "안 골랐다"가 맞는 답이 된다 — 그 상태로 재면 구별을 못 잰다.
  await page.route('**/api/projects', (route: any) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ projects: [{
      graph: 'prj_x', displayName: '남의 프로젝트', level: 'read',
      analyzerGraph: null, ownerUid: 'DEV-BOB', adopted: false,
    }] }),
  }))
  // graph 를 쓰는 경로는 전부 막는다. 한 곳이라도 새면 다른 코드가 뒤에 와서
  // 배너를 덮어쓴다 — 실제로 그렇게 이 검사가 한 번 실패했다.
  await page.route(/\/api\/(?!auth|projects|accounts|health)/, (route: any) =>
    route.fulfill(FORBIDDEN))
  await page.goto('/', { waitUntil: 'networkidle' })

  const banner = page.locator('.pgate')
  await expect(banner).toBeVisible()
  await expect(banner).toContainText('볼 수 없습니다')
  // 둘을 같은 문구로 내보내면 사용자가 할 일을 알 수 없다 —
  // 하나는 "만들어라", 하나는 "요청해라"다.
  await expect(banner).toContainText('공유를 요청')
  // 머리글로 가른다 — 안내문에는 "프로젝트를 선택" 이 양쪽에 다 나온다.
  await expect(page.locator('.pgate__text')).toHaveText('이 프로젝트를 볼 수 없습니다.')
})

test('프로젝트가 정해진 뒤 늦게 온 403 은 안내를 되살리지 않는다', async ({ page }) => {
  // **경합이다.** 화면들의 `onMounted` 조회는 `/api/projects` 응답을 기다리지
  // 않고 먼저 나간다. 그 403(`PROJECT_NOT_SELECTED`)이 첫 프로젝트를 고른
  // **뒤에** 도착하면, `setProject` 가 지운 안내가 다시 붙고 아무도 다시
  // 지우지 않는다. 2026-09-30 증상 — 앱을 처음 띄우면 첫 프로젝트로 들어가
  // 있는데 "프로젝트를 선택해 주세요" 가 그대로 남아 있었다.
  await page.route('**/api/projects', (route: any) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ projects: [{
      graph: 'prj_mine', displayName: '내 프로젝트', level: 'owner',
      analyzerGraph: 'prj_mine_a', ownerUid: 'DEV-ME', adopted: true,
    }] }),
  }))
  // graph 경로는 **늦게** 안 골랐다고 답한다 — 선택이 먼저 끝나게 한다.
  await page.route(/\/api\/(?!auth|projects|accounts|health)/, async (route: any) => {
    await new Promise((r) => setTimeout(r, 600))
    await route.fulfill(DENIED)
  })
  await page.goto('/', { waitUntil: 'networkidle' })

  // 프로젝트가 정해진 화면에서 "안 골랐다" 는 참이 아니다.
  await expect(page.locator('.pgate__text')).toHaveCount(0)
})
