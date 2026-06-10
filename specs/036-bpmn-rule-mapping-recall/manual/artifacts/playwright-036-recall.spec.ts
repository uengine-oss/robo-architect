import { test, expect } from '@playwright/test'
import path from 'path'

/**
 * §036 용어 정규화 — before/after 매뉴얼 캡처.
 *
 * 036은 신규 UI가 없다. "성공 화면" = 기존 BPMN 내비게이터에서 어휘갭으로
 * 누락되던 룰(zapamcom*)이 "본인확인" 활동에 매핑되어 나타나는 장면이다.
 *
 * before/after 대비는 백엔드 env 토글로 만든다:
 *   1) 백엔드를 HYBRID_GLOSSARY_NORMALIZE=0 으로 기동 → 골든 PDF 인제스트 →
 *      이 spec 실행 → 01_off_missing.png (누락 상태)
 *   2) 백엔드를 HYBRID_GLOSSARY_NORMALIZE=1 으로 재기동 → 재인제스트 →
 *      이 spec 실행 → 02_on_recovered.png (회복 상태)
 * (Playwright는 프런트만 구동하므로 backend env는 외부에서 제어한다.)
 *
 * 전제: 앱 구동(localhost:5199) + neo4j analyzer 그래프 적재 + LLM 키.
 * 셀렉터는 라이브 UI 기준으로 보정할 것(아래 TODO).
 */

const SHOTS = path.resolve(__dirname, '../screenshots')
const APP = process.env.APP_URL || 'http://localhost:5199'
const PHASE = process.env.NORMALIZE_PHASE || 'on' // 'off' | 'on'
const SHOT_NAME = PHASE === 'off' ? '01_off_missing.png' : '02_on_recovered.png'

async function shot(page, name: string) {
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${SHOTS}/${name}` })
}

test('BPMN 활동 룰 매핑 패널 캡처 (자동납부 본인확인)', async ({ page }) => {
  await page.goto(APP)

  // TODO(라이브 보정): BPMN/프로세스 내비게이터 탭으로 이동.
  // 034 패턴: page.locator('.top-bar__tabs button', { hasText: 'Process' }).click()
  await page.waitForLoadState('networkidle')

  // TODO(라이브 보정): "본인확인" 활동(Task) 노드를 선택해 룰 매핑 패널을 연다.
  // 예: await page.locator('.bpmn-task', { hasText: '본인확인' }).click()
  // await page.waitForSelector('.rule-mapping-panel', { timeout: 60_000 })

  // 매핑 패널(매핑된 룰 R 카운트/목록)이 보이는 상태에서 캡처.
  await shot(page, SHOT_NAME)
  await shot(page, '03_mapping_panel_detail.png')

  // 회복 단계에서는 zapamcom 계열 룰이 최소 1건 매핑되어야 한다(시각 + 단언).
  // TODO(라이브 보정): expect(page.locator('.rule-mapping-panel')).toContainText(/zapamcom|본인확인/)
})
