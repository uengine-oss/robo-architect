import { test, expect } from '@playwright/test'

test('intent SSE 스트리밍 이벤트 및 tool-feed UI 검증', async ({ page }) => {
  // SSE 이벤트를 intercept해서 로깅
  const sseEvents: { type: string; data: string }[] = []
  await page.route('**/api/proposals/stream/*/intent', async (route) => {
    const response = await route.fetch()
    const body = await response.text()
    // 이벤트 파싱
    const lines = body.split('\n')
    let currentType = ''
    for (const line of lines) {
      if (line.startsWith('event:')) currentType = line.slice(6).trim()
      else if (line.startsWith('data:')) sseEvents.push({ type: currentType, data: line.slice(5).trim() })
    }
    await route.fulfill({ response })
  })

  // 페이지 이동
  await page.goto('http://localhost:5173')
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: 'test-results/intent-01-initial.png', fullPage: false })

  // Proposals 탭 찾기
  const proposalsTab = page.locator('text=Proposals').first()
  await proposalsTab.waitFor({ timeout: 10000 })
  await proposalsTab.click()
  await page.waitForTimeout(1000)
  await page.screenshot({ path: 'test-results/intent-02-proposals-panel.png' })

  // "+ 새 Proposal" 버튼 클릭
  const newBtn = page.locator('button:has-text("새 Proposal"), button:has-text("+ 새 Proposal")').first()
  await newBtn.waitFor({ timeout: 5000 })
  await newBtn.click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: 'test-results/intent-03-create-form.png' })

  // 프롬프트 입력
  const textarea = page.locator('textarea').first()
  await textarea.waitFor({ timeout: 5000 })
  await textarea.fill('사용자 알림 기능을 추가해주세요. 이메일과 SMS 알림을 지원해야 합니다.')

  await page.screenshot({ path: 'test-results/intent-04-prompt-entered.png' })

  // SSE 스트림 모니터링 시작 (route intercept 대신 page.on 활용)
  const receivedEvents: string[] = []
  page.on('response', async (response) => {
    if (response.url().includes('/stream/') && response.url().includes('/intent')) {
      console.log(`SSE 연결됨: ${response.url()} status=${response.status()}`)
      try {
        const body = await response.text()
        const lines = body.split('\n')
        let currentType = ''
        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentType = line.slice(6).trim()
          } else if (line.startsWith('data:') && currentType) {
            receivedEvents.push(currentType)
            console.log(`SSE 이벤트: ${currentType} → ${line.slice(5, 80)}`)
          }
        }
      } catch {}
    }
  })

  // AI 분석 시작
  const submitBtn = page.locator('button:has-text("AI 분석 시작")').first()
  await submitBtn.waitFor({ timeout: 5000 })
  await submitBtn.click()
  console.log('⏳ AI 분석 시작...')

  // analyzing 단계 진입 확인
  await page.locator('text=자연어 인텐트 분해 중').waitFor({ timeout: 15000 })
  console.log('✅ analyzing 단계 진입')
  await page.screenshot({ path: 'test-results/intent-05-analyzing-start.png' })

  // 10초 후 스크린샷 (tool-feed 등장 여부 확인)
  await page.waitForTimeout(10000)
  await page.screenshot({ path: 'test-results/intent-06-after-10s.png' })

  // tool-feed 등장 여부 확인
  const toolFeed = page.locator('.tool-feed')
  const toolFeedVisible = await toolFeed.isVisible().catch(() => false)
  console.log(`tool-feed 표시 여부: ${toolFeedVisible}`)

  if (toolFeedVisible) {
    const entries = await toolFeed.locator('.tool-feed__entry').count()
    console.log(`tool-feed 항목 수: ${entries}`)
  }

  // 30초 더 대기 후 스크린샷
  await page.waitForTimeout(30000)
  await page.screenshot({ path: 'test-results/intent-07-after-40s.png' })

  // 완료 또는 tool_use 이벤트 대기 (최대 3분)
  console.log('⏳ 완료 또는 tool_use 이벤트 대기 중 (최대 3분)...')
  try {
    await Promise.race([
      page.locator('text=분석 완료, text=Proposal 보기, .proposal-create__done').waitFor({ timeout: 180000 }),
      page.locator('.tool-feed__entry').waitFor({ timeout: 180000 }),
    ])
  } catch {
    console.log('⚠️ 3분 내 완료 또는 tool-feed 미출현')
  }

  await page.screenshot({ path: 'test-results/intent-08-final.png' })

  // 결과 요약
  console.log('\n=== SSE 이벤트 수신 현황 ===')
  const toolUseCount = receivedEvents.filter(e => e === 'tool_use').length
  const phaseCount = receivedEvents.filter(e => e === 'phase').length
  const doneCount = receivedEvents.filter(e => e === 'done').length
  console.log(`phase 이벤트: ${phaseCount}`)
  console.log(`tool_use 이벤트: ${toolUseCount}`)
  console.log(`done 이벤트: ${doneCount}`)
  console.log(`전체 이벤트: ${receivedEvents.join(', ')}`)
  console.log(`tool-feed UI: ${toolFeedVisible ? '표시됨' : '없음'}`)

  // 기본 기능 동작 확인
  expect(phaseCount).toBeGreaterThan(0)
})
