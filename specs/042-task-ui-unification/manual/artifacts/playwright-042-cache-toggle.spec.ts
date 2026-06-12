import { test, expect } from '@playwright/test'
import path from 'path'

const SHOTS = path.resolve(__dirname, '../screenshots')
const SESSION = process.env.HYBRID_SESSION || 'golden042'

test('ES 승격 모달에 LLM 캐시 토글', async ({ page }) => {
  await page.addInitScript((sid) => {
    try { localStorage.setItem('hybrid.session_id', sid) } catch (e) { /* ignore */ }
  }, SESSION)
  await page.goto('/')
  await page.waitForLoadState('networkidle')

  await page.getByRole('button', { name: 'Process', exact: true }).first().click()
  await page.waitForTimeout(1500)

  // "✨ 이벤트 스토밍 생성" 버튼 → 모달.
  const genBtn = page.getByText('이벤트 스토밍 생성', { exact: false }).first()
  await genBtn.click()
  await page.waitForSelector('.promote-modal', { timeout: 15_000 })
  await page.waitForTimeout(800)

  // 캐시 토글 행 존재 확인.
  await expect(page.getByText('LLM 캐시', { exact: true })).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/05_promote_cache_toggle.png` })
})
