import { test, expect } from '@playwright/test'
import path from 'path'

/**
 * §039 US2 — BPM task "포함 요소 / 설계 궤적" 모달 캡처.
 *
 * BPM 뷰에서 task를 선택 → 인스펙터의 "포함 요소" 버튼 → 모달에 그 task의
 * UI·Command·Event 체인이 event-modeling 스티커로 렌더되는 장면. 모달을 닫으면
 * BPM 캔버스는 처음과 동일(엣지/노드 추가 0).
 *
 * 전제: 프런트(5173) + 백엔드(8000) 구동, 하이브리드 세션이 DB에 존재.
 *   HYBRID_SESSION=<sid> npx playwright test --config playwright.config.ts
 */

const SHOTS = path.resolve(__dirname, '../screenshots')
const SESSION = process.env.HYBRID_SESSION || 'golden039'

test('BPM task 포함 요소 모달 (설계 궤적)', async ({ page }) => {
  await page.addInitScript((sid) => {
    try { localStorage.setItem('hybrid.session_id', sid) } catch (e) { /* ignore */ }
  }, SESSION)

  await page.goto('/')
  await page.waitForLoadState('networkidle')

  // Process 탭 → BpmnPanel.
  const processTab = page.getByRole('button', { name: 'Process', exact: true })
  if (await processTab.count()) await processTab.first().click()
  await page.waitForTimeout(2000)

  // BPM task 선택 = 좌측 네비게이터(BUSINESS PROCESSES)의 task 행 더블클릭
  // (NavigatorPanel: `.hybrid-task-item` @dblclick → selectHybridTask).
  // 궤적이 있는(PROMOTED_TO→US→IMPLEMENTS→Command) task를 텍스트로 지정.
  const TASK_NAME = process.env.TASK_NAME || '결제수단별 처리 경로 결정'
  const taskRow = page.locator('.hybrid-task-item', { hasText: TASK_NAME }).first()
  await taskRow.waitFor({ timeout: 30_000 })
  await taskRow.dblclick()

  // HybridTaskInspector(.hti-panel) + 내 버튼(.hti-trace-btn) 등장 대기.
  await page.waitForSelector('.hti-trace-btn', { timeout: 30_000 })
  await page.screenshot({ path: `${SHOTS}/01_inspector_button.png`, fullPage: false })

  // "포함 요소 · 설계 궤적 보기" 버튼 클릭 → 모달.
  const traceBtn = page.locator('.hti-trace-btn')
  if (await traceBtn.count()) {
    await traceBtn.first().click()
    await page.waitForSelector('.bpm-trace-modal', { timeout: 15_000 })
    await page.waitForTimeout(1500) // VueFlow fit-view 정착
    await page.screenshot({ path: `${SHOTS}/02_trace_modal.png`, fullPage: false })

    // 모달 안에 스티커(또는 empty 안내)가 보이는지 확인.
    const modal = page.locator('.bpm-trace-modal')
    await expect(modal).toBeVisible()
    await page.screenshot({ path: `${SHOTS}/03_modal_stickers.png`, fullPage: false })

    // 닫기 → 캔버스 동일.
    await page.locator('.bpm-trace-modal__close').click()
    await expect(page.locator('.bpm-trace-modal')).toHaveCount(0)
    await page.waitForTimeout(800)
    await page.screenshot({ path: `${SHOTS}/04_canvas_unchanged.png`, fullPage: false })
  }
})
