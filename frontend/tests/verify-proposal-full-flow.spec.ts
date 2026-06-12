import { test, expect } from '@playwright/test'

/**
 * 039 Proposal Lifecycle — 전체 플로우 검증
 *  1. 페이지 로드 → Proposals 탭 진입
 *  2. 목록 로딩 (500 에러 없음 확인)
 *  3. 상세 보기 (기존 Proposal 선택)
 *  4. 새 Proposal 패널(모달 아님) 열기
 *  5. AI 분석 시작 → stream-log 실시간 출력(한국어 narration) 확인
 *  6. 중단 버튼 동작 확인
 */
test('039 Proposal 전체 플로우 — 목록/상세/생성/스트리밍/중단', async ({ page }) => {
  test.setTimeout(240_000)

  // 콘솔 에러 수집
  const consoleErrors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })

  // 네트워크 응답 추적 (500 에러 감지)
  const failedRequests: { url: string; status: number }[] = []
  page.on('response', (res) => {
    if (res.url().includes('/api/') && res.status() >= 500) {
      failedRequests.push({ url: res.url(), status: res.status() })
    }
  })

  // SSE 이벤트 수집
  const sseEvents: string[] = []
  page.on('response', async (res) => {
    if (res.url().includes('/stream/') && res.url().includes('/intent')) {
      console.log(`[SSE] 연결: ${res.url()} status=${res.status()}`)
    }
  })

  // --- 1. 페이지 로드 ---
  await page.goto('http://localhost:5173')
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: 'test-results/flow-01-initial.png' })

  // --- 2. Proposals 탭 진입 ---
  const proposalsTab = page.locator('text=Proposals').first()
  await proposalsTab.waitFor({ timeout: 10000 })
  await proposalsTab.click()
  await page.waitForTimeout(1500)
  await page.screenshot({ path: 'test-results/flow-02-proposals-list.png' })

  // 목록 로딩 확인 — 아이템이 있거나 "없습니다" 메시지
  const listItems = page.locator('.proposal-item')
  const itemCount = await listItems.count()
  console.log(`[목록] Proposal 아이템 수: ${itemCount}`)
  expect(failedRequests.length, `500 에러 발생: ${JSON.stringify(failedRequests)}`).toBe(0)

  // --- 3. 기존 Proposal 상세 보기 ---
  if (itemCount > 0) {
    await listItems.first().click()
    await page.waitForTimeout(1500)
    await page.screenshot({ path: 'test-results/flow-03-proposal-detail.png' })
    const detailVisible = await page.locator('.proposal-detail-pane').isVisible().catch(() => false)
    console.log(`[상세] detail-pane 표시: ${detailVisible}`)
  }

  // --- 4. 새 Proposal 패널 열기 (모달 아님) ---
  const newBtn = page.locator('button:has-text("새 Proposal")').first()
  await newBtn.waitFor({ timeout: 5000 })
  await newBtn.click()
  await page.waitForTimeout(800)

  // 패널이 detail-pane 안에 렌더되는지(모달 오버레이가 아닌지) 확인
  const createPanel = page.locator('.proposal-create')
  await expect(createPanel).toBeVisible({ timeout: 5000 })
  const overlayExists = await page.locator('.overlay, .modal-overlay').count()
  console.log(`[생성] 패널 표시됨, 오버레이(모달) 개수: ${overlayExists}`)
  await page.screenshot({ path: 'test-results/flow-04-create-panel.png' })

  // --- 5. AI 분석 시작 → stream-log 스트리밍 확인 ---
  const textarea = createPanel.locator('textarea').first()
  await textarea.fill('주문에 쿠폰 할인 적용 기능을 추가해줘. 정액·정률 쿠폰을 지원해야 해.')
  await page.screenshot({ path: 'test-results/flow-05-prompt.png' })

  const submitBtn = createPanel.locator('button:has-text("AI 분석 시작")').first()
  await submitBtn.click()
  console.log('[분석] AI 분석 시작 클릭')

  // analyzing 단계 — stream-log 터미널 등장
  const streamLog = page.locator('.stream-log').first()
  await streamLog.waitFor({ timeout: 15000 })
  console.log('[분석] stream-log 터미널 등장')
  await page.screenshot({ path: 'test-results/flow-06-analyzing.png' })

  // 실시간 로그 라인이 흐르는지 — 30초간 폴링하며 라인 수 증가 관찰
  let prevLineCount = 0
  let sawGrowth = false
  for (let i = 0; i < 12; i++) {
    await page.waitForTimeout(5000)
    const lineCount = await page.locator('.stream-log__line').count()
    if (lineCount > prevLineCount) {
      sawGrowth = true
      console.log(`[스트림] +${lineCount - prevLineCount} 라인 (총 ${lineCount})`)
      prevLineCount = lineCount
    }
    if (i === 2) await page.screenshot({ path: 'test-results/flow-07-stream-15s.png' })
    // 완료 단계 진입하면 중단
    const doneVisible = await page.locator('.proposal-create__done').isVisible().catch(() => false)
    const clarifyVisible = await page.locator('.proposal-create__clarify').isVisible().catch(() => false)
    if (doneVisible || clarifyVisible) {
      console.log(`[분석] 단계 전환 감지 (done=${doneVisible}, clarify=${clarifyVisible})`)
      break
    }
  }
  await page.screenshot({ path: 'test-results/flow-08-stream-after.png' })

  // 스트림 라인 내용 샘플 출력
  const sampleLines = await page.locator('.stream-log__line').allTextContents()
  console.log(`[스트림] 총 ${sampleLines.length} 라인, 샘플:`)
  sampleLines.slice(0, 10).forEach((l, i) => console.log(`  ${i}: ${l.slice(0, 80)}`))

  // --- 6. 중단 버튼 (아직 analyzing 단계일 때만) ---
  const stopBtn = page.locator('button:has-text("중단")')
  const stopVisible = await stopBtn.isVisible().catch(() => false)
  if (stopVisible) {
    await stopBtn.click()
    await page.waitForTimeout(1000)
    console.log('[중단] 중단 버튼 클릭 → input 단계 복귀 기대')
    await page.screenshot({ path: 'test-results/flow-09-stopped.png' })
    const backToInput = await page.locator('.proposal-create__input').isVisible().catch(() => false)
    console.log(`[중단] input 단계 복귀: ${backToInput}`)
  }

  // --- 결과 요약 ---
  console.log('\n=== 검증 요약 ===')
  console.log(`목록 아이템: ${itemCount}`)
  console.log(`500 에러: ${failedRequests.length}`)
  console.log(`스트림 라인 증가 관찰: ${sawGrowth}`)
  console.log(`총 스트림 라인: ${sampleLines.length}`)
  console.log(`콘솔 에러: ${consoleErrors.length}`)
  if (consoleErrors.length) {
    consoleErrors.slice(0, 5).forEach(e => console.log(`  ⚠️ ${e.slice(0, 120)}`))
  }

  // 핵심 단언: 500 에러 없음, 스트림 라인이 출력됨
  expect(failedRequests.length).toBe(0)
  expect(sampleLines.length).toBeGreaterThan(0)
})
