import { test, expect } from '@playwright/test'

/**
 * narration 스트리밍 검증 — stream-log에 raw JSON이 아니라 [태그] 서술이 흐르는지.
 */
test('intent 스트림에 한국어 narration이 표시되고 raw JSON은 숨겨진다', async ({ page }) => {
  test.setTimeout(180_000)

  await page.goto('http://localhost:5173')
  await page.waitForLoadState('networkidle')

  await page.locator('text=Proposals').first().click()
  await page.waitForTimeout(1000)

  await page.locator('button:has-text("새 Proposal")').first().click()
  await page.waitForTimeout(600)

  const panel = page.locator('.proposal-create')
  await panel.locator('textarea').first().fill('회원 등급별 차등 적립 기능을 추가해줘. 등급이 높을수록 적립률이 올라가야 해.')
  await panel.locator('button:has-text("AI 분석 시작")').first().click()

  const streamLog = page.locator('.stream-log').first()
  await streamLog.waitFor({ timeout: 15000 })

  // narration 라인이 등장할 때까지 폴링하며 캡처 (최대 120초).
  // 단계 전환 시 stream-log가 비워지므로 "관측된 최대값"을 추적해 단언한다.
  let maxNarration = 0
  let maxJsonLike = 0
  let bestNarrationLines: string[] = []
  let captured = false
  for (let i = 0; i < 40; i++) {
    await page.waitForTimeout(3000)
    const lines = await page.locator('.stream-log__line').allTextContents()
    const narrationLines = lines.filter(l => /^\s*\[.+?\]/.test(l.trim()))
    // 순수 JSON처럼 보이는 줄 (중괄호/따옴표로 시작) — 0에 가까워야 함
    const jsonLikeLines = lines.filter(l => {
      const s = l.trim()
      return s.startsWith('{') || s.startsWith('}') || s.startsWith('"') || s === ']' || s === '['
    })
    if (narrationLines.length > maxNarration) {
      maxNarration = narrationLines.length
      bestNarrationLines = narrationLines
    }
    if (jsonLikeLines.length > maxJsonLike) maxJsonLike = jsonLikeLines.length
    if (narrationLines.length >= 3 && !captured) {
      await page.screenshot({ path: 'test-results/narration-mid.png' })
      captured = true
    }
    console.log(`[${i*3}s] 전체 ${lines.length}줄, narration ${narrationLines.length}줄, json-like ${jsonLikeLines.length}줄`)
    const done = await page.locator('.proposal-create__done, .proposal-create__clarify').first().isVisible().catch(() => false)
    if (done) { console.log('단계 전환 감지'); break }
    if (maxNarration >= 5) { await page.waitForTimeout(2000); break }
  }

  await page.screenshot({ path: 'test-results/narration-final.png' })

  console.log('\n=== 관측된 최대 narration 라인 ===')
  bestNarrationLines.forEach(l => console.log('  ' + l.trim().slice(0, 100)))
  console.log(`\n=== 최대 json-like 라인 수: ${maxJsonLike} (적을수록 좋음) ===`)

  // 핵심 단언: narration([태그])이 표시되고, raw JSON 줄은 거의 없어야 함
  expect(maxNarration, 'narration([태그]) 라인이 표시되어야 함').toBeGreaterThan(0)
  expect(maxJsonLike, 'raw JSON 줄은 표시에서 억제되어야 함').toBeLessThanOrEqual(1)
})
