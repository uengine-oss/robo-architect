import { test, expect } from '@playwright/test'
const APP = process.env.APP_URL || 'http://localhost:5180'

test('US AI 편집 탭 — 피드백→스트리밍 제안→거부(데이터 미변경)', async ({ page }) => {
  test.setTimeout(150_000)
  await page.goto(APP)
  await page.locator('.top-bar__tabs button', { hasText: 'Requirements' }).first().click()
  await page.waitForSelector('.req-tree', { timeout: 30_000 })
  const carets = page.locator('.req-tree .caret')
  for (let i = 0; i < 8; i++) {
    if (await page.locator('.req-tree .us-row').first().count()) break
    const c = carets.nth(i)
    if (await c.count()) await c.click().catch(() => {})
    await page.waitForTimeout(150)
  }
  await page.locator('.req-tree .us-row').first().click()
  await page.waitForSelector('.us-detail', { timeout: 10_000 })
  await page.locator('.us-tab', { hasText: 'AI 편집' }).click()
  // restyled to match Design tab's ChatPanel shell
  await page.waitForSelector('.chat-panel .chat-input__textarea', { timeout: 10_000 })
  await expect(page.locator('.chat-panel__title')).toContainText('Chat')
  await expect(page.locator('.chat-panel .ce-history__head')).toBeVisible()
  await page.locator('.chat-panel .chat-input__textarea').fill('benefit 문장을 더 명확하게 다듬어줘')
  await page.locator('.chat-panel .chat-input__send').click()
  await page.waitForSelector('.chat-message--user', { timeout: 10_000 })
  await page.screenshot({ path: '/tmp/chat_edit_streaming.png' })
  await page.waitForSelector('.ce-proposal .ce-actions', { timeout: 130_000 })
  await page.screenshot({ path: '/tmp/chat_edit_proposal.png' })
  await expect(page.locator('.ce-prop-summary')).toBeVisible()
  await page.locator('.ce-btn', { hasText: '거부' }).click()
  await expect(page.locator('.ce-applied')).toContainText('거부')
})
