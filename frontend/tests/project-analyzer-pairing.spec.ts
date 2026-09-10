import { test, expect } from '@playwright/test'

/**
 * 프로젝트의 분석 짝 지정.
 *
 * API 는 처음부터 있었는데 **화면에 거는 자리가 없었다.** 새 프로젝트를 만들고
 * 분석을 돌려도 짝을 맺을 방법이 없어 추적성이 계속 비어 있었고, 그건 오류가
 * 아니라 "결과가 없다"로 보인다.
 *
 * 그래서 재는 것은 둘이다 — 관리 등급에게만 열리는가, 누른 값이 실제로 서버로
 * 나가는가. 화면 상태만 보면 "저장했다"와 "저장한 척했다"가 구별되지 않는다.
 */

const LIST = '**/api/projects'

function projects(rows: any[]) {
  return (route: any) => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ projects: rows }),
  })
}

const ADMIN = {
  graph: 'prj_a1', displayName: '새 프로젝트', level: 'admin',
  analyzerGraph: null, ownerUid: 'DEV-TEST', adopted: false,
}
const READER = { ...ADMIN, graph: 'prj_b2', displayName: '남의 프로젝트', level: 'read' }

/**
 * 목록은 **서버가 사람 말로** 준다.
 *
 * 처음에는 graph 이름을 타이핑하게 만들었는데 `prj_a1_a` 는 내부 식별자다.
 * 오타 하나로 남의 분석을 가리키거나 없는 이름으로 거부당한다.
 */
const OPTIONS = [
  { graph: 'prj_a1_a', label: '이 프로젝트의 분석', kind: 'own', current: false },
  { graph: 'analyzer_run', label: '전환 전 공용 분석', kind: 'legacy', current: false },
]

test('고르는 목록이 뜨고, 고른 값이 서버로 나간다', async ({ page }) => {
  await page.route(LIST, projects([ADMIN, READER]))
  await page.route('**/api/projects/prj_a1/analyzer-options', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ options: OPTIONS }),
  }))

  let sent: any = null
  await page.route('**/api/projects/prj_a1/analyzer', route => {
    sent = route.request().postDataJSON()
    return route.fulfill({ status: 200, contentType: 'application/json',
      body: JSON.stringify({ graph: 'prj_a1', analyzerGraph: 'prj_a1_a' }) })
  })

  await page.goto('/', { waitUntil: 'networkidle' })
  await page.locator('.pp__btn').click()

  const row = page.locator('.pp__list li', { hasText: '새 프로젝트' })
  await row.locator('.pp__pairbtn').click()

  const select = page.locator('.pp__pairform select')
  await expect(select).toBeVisible()
  // 사람 말이 보여야 한다. graph 이름만 보이면 고를 수 없다.
  await expect(select).toContainText('이 프로젝트의 분석')
  await expect(select).toContainText('전환 전 공용 분석')
  // 안 쓰는 선택지도 있어야 한다 — 해제할 길이 없으면 되돌릴 수 없다.
  await expect(select).toContainText('쓰지 않음')

  await select.selectOption('prj_a1_a')
  await page.locator('.pp__pairform button[type="submit"]').click()
  await expect.poll(() => sent, { timeout: 5000 }).toEqual({ analyzerGraph: 'prj_a1_a' })
})

test('남과 나눠 쓰는 분석을 고르면 경고한다', async ({ page }) => {
  await page.route(LIST, projects([ADMIN, READER]))
  await page.route('**/api/projects/prj_a1/analyzer-options', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ options: OPTIONS }),
  }))

  await page.goto('/', { waitUntil: 'networkidle' })
  await page.locator('.pp__btn').click()
  await page.locator('.pp__list li', { hasText: '새 프로젝트' }).locator('.pp__pairbtn').click()

  const select = page.locator('.pp__pairform select')
  // 자기 짝이면 경고가 없어야 한다 — 늘 뜨면 사람이 안 읽는다.
  await select.selectOption('prj_a1_a')
  await expect(page.locator('.pp__warnline')).toHaveCount(0)
  await select.selectOption('analyzer_run')
  await expect(page.locator('.pp__warnline')).toContainText('함께 사라집니다')
})

test('읽기 등급에게는 짝 버튼이 없다', async ({ page }) => {
  await page.route(LIST, projects([ADMIN, READER]))
  await page.goto('/', { waitUntil: 'networkidle' })
  await page.locator('.pp__btn').click()

  // "없다"를 재기 전에 **보일 수 있는 상태였는지**부터 확인한다. 목록이 안 떴는데
  // 버튼이 없는 것을 통과로 읽으면 아무것도 확인하지 않는 검사가 된다.
  await expect(page.locator('.pp__list li')).toHaveCount(2)
  await expect(page.locator('.pp__list li', { hasText: '새 프로젝트' })
    .locator('.pp__pairbtn')).toHaveCount(1)
  await expect(page.locator('.pp__list li', { hasText: '남의 프로젝트' })
    .locator('.pp__pairbtn')).toHaveCount(0)
})

test('짝이 없으면 목록이 그렇게 말한다', async ({ page }) => {
  await page.route(LIST, projects([ADMIN]))
  await page.goto('/', { waitUntil: 'networkidle' })
  await page.locator('.pp__btn').click()
  await expect(page.locator('.pp__pair--none')).toContainText('분석 미지정')
})
