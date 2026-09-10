import { test, expect, Page } from '@playwright/test'

/**
 * 인제스천 교체 고지와 지난 판 (ENT-ING-002).
 *
 * 인제스천은 **교체**다 — 시작하자마자 이 프로젝트의 설계를 통째로 지운다.
 * 오랫동안 그것을 묻지도 알리지도 않았고, 확인 대화상자는 코드에 있었지만
 * **한 번도 열리지 않는 죽은 코드**였다(`showClearConfirm` 을 true 로 만드는
 * 곳이 없었다). 그런 종류의 회귀는 화면을 봐서는 드러나지 않는다.
 *
 * 그래서 여기서 재는 것은 셋이다.
 *
 * ```
 * 지울 것이 있으면   확인을 받고서야 인제스천이 시작된다
 * 지울 것이 없으면   묻지 않는다 (첫 인제스천에 확인을 붙이면 사람이 안 읽는다)
 * 지난 판           보관된 것을 내보내기 화면에서 다시 고를 수 있다
 * ```
 */

const PREVIEW = '**/api/ingest/replacement-preview'

async function openIngestionModal(page: Page) {
  await page.goto('/', { waitUntil: 'networkidle' })
  // 상단 탭 이름은 `Stories` 다 — 패널 제목은 여전히 Requirements 라서
  // 옛 이름으로 찾으면 조용히 시간만 초과한다.
  await page.getByRole('button', { name: 'Stories', exact: true }).first().click()
  await page.getByRole('button', { name: '문서 업로드' }).first().click()
  await expect(page.locator('.modal-body').first()).toBeVisible({ timeout: 15_000 })
}

/** 시작 버튼을 누를 수 있는 상태로 만든다 — 텍스트 입력 모드에 글을 넣는다. */
async function fillSomething(page: Page) {
  await page.getByRole('button', { name: '텍스트 입력' }).click()
  await page.locator('textarea').first()
    .fill('휴가 신청은 부서장 승인을 받는다. 반려되면 다시 신청할 수 있다.')
}

/** 시작 버튼. 라벨은 `분석 시작` 이고 푸터에 있다. */
function startButton(page: Page) {
  return page.getByRole('button', { name: '분석 시작' })
}

test.describe('인제스천 교체 고지', () => {
  test('지울 것이 있으면 확인을 받기 전에는 시작하지 않는다', async ({ page }) => {
    await page.route(PREVIEW, route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        graph: 'robo', sessions: ['b6544050'], total: 892,
        counts: { BoundedContext: 5, UserStory: 36, Command: 23 },
        preserved: ['FigmaBinding'],
      }),
    }))

    // 업로드가 실제로 나갔는지를 **가로챈 호출 수**로 잰다. 화면 상태만 보면
    // "시작 안 했다"를 확인할 수 없다.
    let uploads = 0
    await page.route('**/api/ingest/upload', route => {
      uploads += 1
      return route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ session_id: 'zz', content_length: 10 }) })
    })

    await openIngestionModal(page)
    await fillSomething(page)
    await startButton(page).click()

    const dialog = page.locator('.clear-confirm-dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText('교체')
    await expect(dialog).toContainText('892')
    await expect(dialog).toContainText('BoundedContext')
    await expect(dialog).toContainText('보관')
    expect(uploads).toBe(0)

    await dialog.getByRole('button', { name: '취소' }).click()
    await expect(dialog).toBeHidden()
    expect(uploads).toBe(0)
  })

  test('확인하면 그때 시작한다 — 따로 지우지 않는다', async ({ page }) => {
    await page.route(PREVIEW, route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ graph: 'robo', sessions: ['x'], total: 12,
        counts: { BoundedContext: 12 }, preserved: [] }),
    }))
    let uploads = 0
    let clears = 0
    await page.route('**/api/graph/clear', route => { clears += 1; return route.fulfill({ status: 200, body: '{}' }) })
    await page.route('**/api/ingest/clear-all', route => { clears += 1; return route.fulfill({ status: 200, body: '{}' }) })
    await page.route('**/api/ingest/upload', route => {
      uploads += 1
      return route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ session_id: 'zz', content_length: 10 }) })
    })

    await openIngestionModal(page)
    await fillSomething(page)
    await startButton(page).click()
    await page.locator('.clear-confirm-dialog').getByRole('button', { name: '교체하고 계속' }).click()

    await expect.poll(() => uploads, { timeout: 5000 }).toBe(1)
    // 별도 삭제를 부르면 보관 대상이 먼저 사라져 스냅샷이 빈 채로 남는다.
    expect(clears).toBe(0)
  })

  test('첫 인제스천이면 묻지 않는다', async ({ page }) => {
    await page.route(PREVIEW, route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ graph: 'prj_new', sessions: [], total: 0, counts: {}, preserved: [] }),
    }))
    let uploads = 0
    await page.route('**/api/ingest/upload', route => {
      uploads += 1
      return route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ session_id: 'zz', content_length: 10 }) })
    })

    await openIngestionModal(page)
    await fillSomething(page)
    await startButton(page).click()

    await expect.poll(() => uploads, { timeout: 5000 }).toBe(1)
    await expect(page.locator('.clear-confirm-dialog')).toBeHidden()
  })
})

test.describe('지난 판', () => {
  test('보관된 판을 내보내기 화면에서 고를 수 있다', async ({ page }) => {
    await page.route('**/api/deliverables/snapshots', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ available: true, graph: 'robo', snapshots: [
        { snapshotKey: 'old1-20260910T101010-ab12', sessionId: 'old1', name: '휴가신청',
          capturedAt: '2026-09-10T10:10:10+00:00', boundedContexts: 5, reason: 'ingest' },
      ] }),
    }))

    let asked = ''
    await page.route('**/api/deliverables/snapshots/*', route => {
      asked = route.request().url()
      return route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ sessionId: 'old1', sectionKeys: [], projectInfo: { projectName: '휴가신청' },
          boundedContexts: [], eventStorming: { contexts: [] } }) })
    })

    await page.goto('/', { waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Design', exact: true }).first().click()
    await page.locator('[title="Export Document"]').first().click()

    const picker = page.locator('.session-picker__select')
    await expect(picker).toBeVisible()
    // 지금 판과 지난 판이 갈려 있어야 한다 — 섞이면 옛 문서를 납품하게 된다.
    await expect(picker.locator('optgroup[label="지난 판 (보관됨)"]')).toHaveCount(1)

    await picker.selectOption('snap:old1-20260910T101010-ab12')
    await expect.poll(() => asked, { timeout: 5000 }).toContain('old1-20260910T101010-ab12')
    await expect(page.locator('.session-picker__past')).toBeVisible()
  })
})
