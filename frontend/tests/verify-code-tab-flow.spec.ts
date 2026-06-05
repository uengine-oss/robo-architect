import { test } from '@playwright/test'

test('구현 시작 → Code 탭 이동 + /robo-implement 자동 전송', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.waitForTimeout(2000)

  // 1. Changes 탭
  await page.locator('button').filter({ hasText: 'Changes' }).first().click()
  await page.waitForTimeout(1200)

  // CHG-008 선택 (APPROVED 상태)
  await page.locator('.cp-item').filter({ hasText: 'CHG-008' }).first().click()
  await page.waitForTimeout(1000)
  await page.screenshot({ path: '/tmp/code-tab-01-chg008.png' })

  const status = await page.locator('.cd-status').textContent()
  console.log('CHG-008 상태:', status?.trim())

  // 2. 구현 시작 클릭
  const implBtn = page.locator('button').filter({ hasText: '구현 시작' })
  const visible = await implBtn.isVisible().catch(() => false)
  console.log('구현 시작 버튼:', visible)

  if (visible) {
    await implBtn.click()
    await page.waitForTimeout(1500)
    await page.screenshot({ path: '/tmp/code-tab-02-after-click.png' })

    // 3. Code 탭으로 이동했는지 확인
    const codeTabActive = await page.locator('.tb-tab--active, .top-tab--active, [class*="active"]')
      .filter({ hasText: 'Code' }).count().catch(() => 0)
    console.log('Code 탭 활성 요소:', codeTabActive)

    // URL이나 탭 상태 확인
    const currentTab = await page.locator('button[class*="active"], .tab-btn--active').textContent().catch(() => '')
    console.log('현재 활성 탭:', currentTab)

    // 터미널 영역 확인
    await page.waitForTimeout(2000)
    await page.screenshot({ path: '/tmp/code-tab-03-code-tab.png' })

    const terminalVisible = await page.locator('.xterm, .ccw-terminal, canvas').first().isVisible().catch(() => false)
    console.log('터미널 영역 표시:', terminalVisible)

    // 7초 대기 (Claude 시작 + 명령어 전송 시간)
    console.log('Claude 시작 및 /robo-implement 전송 대기 중 (8초)...')
    await page.waitForTimeout(8000)
    await page.screenshot({ path: '/tmp/code-tab-04-command-sent.png' })
  }
})
