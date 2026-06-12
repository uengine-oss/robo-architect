import { test, expect } from '@playwright/test'
import path from 'path'

/**
 * §043 US1/US4 — 단일 Process 탭 토글 + Event Modeling 형식 레인 캡처.
 *
 * 전제: 프런트(5173)+백엔드(8000), 하이브리드 세션 DB 존재.
 *   HYBRID_SESSION=<sid> npx playwright test --config playwright.config.ts
 */

const SHOTS = path.resolve(__dirname, '../screenshots')
const SESSION = process.env.HYBRID_SESSION || 'golden042'
const TASK_NAME = process.env.TASK_NAME || '결제수단별 처리 경로 결정'

test('단일 Process 탭 + BPM⇄EM 토글 + EM 레인', async ({ page }) => {
  await page.addInitScript((sid) => {
    try { localStorage.setItem('hybrid.session_id', sid) } catch (e) { /* ignore */ }
  }, SESSION)

  await page.goto('/')
  await page.waitForLoadState('networkidle')

  // US1: 상단 탭에 독립 'Event Modeling' 없음.
  await expect(page.getByRole('button', { name: 'Event Modeling', exact: true })).toHaveCount(0)
  await page.screenshot({ path: `${SHOTS}/01_no_em_tab.png` })

  // Process 탭 → ProcessPanel 토글(BPM/Event Modeling) 등장.
  await page.getByRole('button', { name: 'Process', exact: true }).first().click()
  await page.waitForSelector('.top-bar__subtoggle', { timeout: 20_000 })
  await page.waitForTimeout(1500)
  await page.screenshot({ path: `${SHOTS}/02_process_bpm.png` })

  // 토글 → Event Modeling 뷰.
  await page.locator('.top-bar__seg', { hasText: 'Event Modeling' }).click()
  await page.waitForTimeout(2000)
  await page.screenshot({ path: `${SHOTS}/03_process_em.png` })

  // 다시 BPM → task 더블클릭 → 인스펙터 → 포함요소 모달(EM 레인).
  await page.locator('.top-bar__seg', { hasText: 'BPM' }).click()
  await page.waitForTimeout(1500)
  const taskRow = page.locator('.hybrid-task-item', { hasText: TASK_NAME }).first()
  if (await taskRow.count()) {
    await taskRow.dblclick()
    const btn = page.locator('.hti-trace-btn')
    if (await btn.count()) {
      await btn.first().click()
      await page.waitForSelector('.bpm-trace-modal .em-lane', { timeout: 15_000 })
      await page.waitForTimeout(1500)
      await page.screenshot({ path: `${SHOTS}/04_em_lane_modal.png` })
      await expect(page.locator('.bpm-trace-modal .em-lane')).toBeVisible()
    }
  }
})
