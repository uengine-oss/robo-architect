import { test, expect } from '@playwright/test'

/**
 * Settings 의 "생성 데이터 초기화".
 *
 * **실제로 지우지 않는다.** 지금 그래프에 데모용 모델이 들어 있고, 이 검사
 * 하나 때문에 10분짜리 레거시 분석을 다시 돌릴 수는 없다. 대신 DELETE 요청을
 * 가로채서 **어디를 부르는지**와 화면이 무엇을 보여주는지를 본다.
 */
test.describe('Settings — 생성 데이터 초기화', () => {
  test.setTimeout(120_000)

  async function openSettings(page: any) {
    await page.goto('/', { waitUntil: 'networkidle' })
    await page.locator('.settings-btn').first().click()
    return await page.locator('.settings-panel').isVisible({ timeout: 5_000 }).catch(() => false)
  }

  test('경고에 지워지는 수와 남는 것을 보여주고, 확인해야 부른다', async ({ page, request }) => {
    const stats = await (await request.get('http://localhost:8000/api/graph/stats')).json()
    const preserved = ['FigmaBinding', 'StoryboardPageMapping', 'BindingHistoryEvent', 'FigmaComponent']
      .reduce((sum, k) => sum + (stats.by_type?.[k] || 0), 0)
    console.log(`[test] 그래프 전체 ${stats.total}개 · 보존 라벨 ${preserved}개`)

    const opened = await openSettings(page)
    expect(opened, 'Settings 팝업을 열지 못했다').toBeTruthy()

    const section = page.locator('.settings-section--danger')
    await expect(section, '초기화 섹션이 있어야 한다').toBeVisible({ timeout: 10_000 })

    // 첫 화면에는 버튼 하나뿐 — 한 번에 지워지면 안 된다.
    await expect(section.locator('.danger-warning')).toHaveCount(0)
    await section.getByRole('button', { name: '생성 데이터 지우기' }).click()

    const warn = section.locator('.danger-warning')
    await expect(warn, '경고가 떠야 한다').toBeVisible({ timeout: 10_000 })
    await expect(warn).toContainText('되돌릴 수 없습니다')
    await expect(warn).toContainText('남는 것')
    await expect(warn, 'Figma 연결이 남는다고 알려야 한다').toContainText('Figma')

    // 실제 건수를 보여줘야 한다 — "세는 중" 에 머물면 안 된다.
    await expect(warn.locator('.danger-warning__row').first()).toContainText(/\d+개/, { timeout: 10_000 })
    const shown = (await warn.textContent()) || ''
    const n = Number((shown.match(/(\d+)개/) || [])[1] || 0)
    console.log(`[test] 경고가 알린 삭제 대상: ${n}개`)
    expect(n, '지울 것이 있는데 0개로 보이면 안 된다').toBeGreaterThan(0)
    // 보존되는 라벨까지 세면 Figma 연결도 지우는 것처럼 읽힌다.
    expect(n, `보존 라벨 ${preserved}개를 뺀 수여야 한다`).toBe(stats.total - preserved)

    // 확인 버튼이 그 수를 그대로 달고 있어야 한다.
    const confirm = section.locator('.danger-button--confirm')
    await expect(confirm).toContainText(`${n}개를 지웁니다`)

    // 취소하면 아무 일도 없어야 한다.
    let called = 0
    await page.route('**/api/ingest/clear-all', async (route) => {
      called++
      await route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ success: true, deleted: { UserStory: 3, Command: 2 } }) })
    })
    await section.getByRole('button', { name: '취소' }).click()
    await expect(warn).toHaveCount(0)
    expect(called, '취소했는데 요청이 나가면 안 된다').toBe(0)

    // 다시 열어 확인하면 그때 부른다. **가로챘으므로 실제로 지워지지 않는다.**
    await section.getByRole('button', { name: '생성 데이터 지우기' }).click()
    await expect(section.locator('.danger-button--confirm')).toBeVisible({ timeout: 10_000 })
    await section.locator('.danger-button--confirm').click()

    await expect(section.locator('.danger-status--done')).toBeVisible({ timeout: 15_000 })
    expect(called, 'DELETE /api/ingest/clear-all 을 한 번 불러야 한다').toBe(1)
    await expect(section).toContainText('5개를 지웠습니다')
    await expect(section, '새로 열라고 알려야 한다').toContainText('새로 열기')
    console.log('[test] 확인 후에만 호출 · 결과와 새로고침 안내 표시')
  })
})
