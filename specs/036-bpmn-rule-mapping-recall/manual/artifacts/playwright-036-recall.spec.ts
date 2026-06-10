import { test } from '@playwright/test'
import path from 'path'

/**
 * §036 용어 정규화 — before/after 매뉴얼 캡처.
 *
 * 036은 신규 UI가 없다. "성공 화면" = 기존 BPMN 내비게이터에서 어휘갭으로
 * 누락되던 룰(zapamcom*)이 "본인확인" 활동에 매핑되어 나타나는 장면.
 *
 * 화면은 영속된 REALIZED_BY 매핑(DB)을 rehydrate한다. 따라서 before/after는
 * 백엔드 env 재기동 없이, 하니스로 DB를 off/on 상태로 만든 뒤 이 spec을 각각
 * 실행해 캡처한다(NORMALIZE_PHASE=off|on 으로 파일명 구분):
 *   HYBRID_GLOSSARY_NORMALIZE=0 run_mapping.py ...   # DB=baseline
 *   NORMALIZE_PHASE=off npx playwright test ...       # 01_off_missing.png
 *   HYBRID_GLOSSARY_NORMALIZE=1 run_mapping.py ...   # DB=recovered
 *   NORMALIZE_PHASE=on  npx playwright test ...       # 02_on_recovered.png
 *
 * 전제: 프런트(5173) + 백엔드(8000) 구동, golden036 세션이 DB에 존재.
 */

const SHOTS = path.resolve(__dirname, '../screenshots')
const SESSION = process.env.HYBRID_SESSION || 'golden036'
const PHASE = process.env.NORMALIZE_PHASE || 'on'
const CANVAS_SHOT = PHASE === 'off' ? '01_off_missing.png' : '02_on_recovered.png'
const PANEL_SHOT = PHASE === 'off' ? '01b_off_panel.png' : '03_mapping_panel_detail.png'

test('BPMN 룰 매핑 캡처 (자동납부 본인확인)', async ({ page }) => {
  // 앱이 golden036 세션을 rehydrate 하도록 localStorage 주입(로드 전에).
  await page.addInitScript((sid) => {
    try { localStorage.setItem('hybrid.session_id', sid) } catch (e) { /* ignore */ }
  }, SESSION)

  await page.goto('/')
  await page.waitForLoadState('networkidle')

  // Process 탭으로 이동 → BpmnPanel.
  const processTab = page.getByRole('button', { name: 'Process', exact: true })
  if (await processTab.count()) await processTab.first().click()

  // BPMN 캔버스(rehydrate 렌더) 대기.
  await page.waitForSelector('.bpmn-canvas svg', { timeout: 60_000 }).catch(() => {})
  await page.waitForTimeout(2500) // 매핑 오버레이/배지 정착

  await page.screenshot({ path: `${SHOTS}/${CANVAS_SHOT}`, fullPage: false })

  // 좌측 네비의 "본인확인 방식 결정" task 행을 더블클릭해 룰 인스펙터를 연다.
  const label = page.getByText('본인확인 방식 결정', { exact: false }).first()
  if (await label.count()) {
    await label.dblclick({ force: true }).catch(() => {})
    await page.waitForTimeout(1800)
    await page.screenshot({ path: `${SHOTS}/${PANEL_SHOT}`, fullPage: false })
  }
})
