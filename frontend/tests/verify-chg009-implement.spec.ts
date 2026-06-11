import { test } from '@playwright/test'

test.setTimeout(480_000) // 8분

test('CHG-009: APPROVED → 구현 시작 → 태스크 진행 → IMPLEMENTED', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.waitForTimeout(2000)

  // 1. Changes 탭 진입
  await page.locator('button').filter({ hasText: 'Changes' }).first().click()
  await page.waitForTimeout(1200)

  // 2. CHG-009 선택
  await page.locator('.cp-item').filter({ hasText: 'CHG-009' }).first().click()
  await page.waitForTimeout(1000)
  await page.screenshot({ path: '/tmp/chg009-02-detail.png' })

  const status = await page.locator('.cd-status').textContent()
  console.log('현재 상태:', status?.trim())

  // 3. "구현 시작" 버튼 클릭
  const implBtn = page.locator('button').filter({ hasText: '구현 시작' })
  await implBtn.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})
  const visible = await implBtn.isVisible().catch(() => false)
  console.log('구현 시작 버튼 visible:', visible)
  if (!visible) {
    const tabs = await page.locator('.cd-tab').allTextContents()
    console.log('Available tabs:', tabs)
    await page.screenshot({ path: '/tmp/chg009-SKIP.png' })
    return
  }

  await implBtn.click()
  await page.waitForTimeout(1500)
  await page.screenshot({ path: '/tmp/chg009-03-after-click.png' })

  // 4. Preflight 다이얼로그 처리
  const overlay = page.locator('.cp-overlay')
  if (await overlay.isVisible().catch(() => false)) {
    console.log('Preflight 다이얼로그 표시됨')
    await page.screenshot({ path: '/tmp/chg009-04-preflight.png' })
    // 선행 Change 목록 출력
    const priorText = await overlay.textContent()
    console.log('Preflight 내용:', priorText?.trim().slice(0, 200))
    // 현재 Change만 구현 선택
    await page.locator('button').filter({ hasText: '현재 Change만' }).click()
    await page.waitForTimeout(1000)
    await page.screenshot({ path: '/tmp/chg009-04b-preflight-dismissed.png' })
  }

  // 5. 구현 탭 전환 대기 (autoStart → ChangeTasksView 마운트)
  await page.locator('.cd-tab').filter({ hasText: '구현' }).waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})
  await page.locator('.cd-tab').filter({ hasText: '구현' }).click().catch(() => {})
  await page.waitForTimeout(1000)
  await page.screenshot({ path: '/tmp/chg009-05-tasks-tab.png' })

  // 6. 스트리밍 진행 감시 (최대 7분)
  console.log('구현 SSE 스트림 시작 대기...')
  const deadline = Date.now() + 420_000
  let prevPct = -1
  let completed = false

  while (Date.now() < deadline) {
    await page.waitForTimeout(4000)

    const phase = await page.locator('.ctv-phase').textContent().catch(() => '')
    const pct   = await page.locator('.ctv-pct').textContent().catch(() => '0%')
    const tasks = await page.locator('.ctv-task').count().catch(() => 0)
    const done  = await page.locator('.ctv-done').isVisible().catch(() => false)

    const pctNum = parseInt(pct) || 0
    if (pctNum !== prevPct || tasks > 0) {
      console.log(`[${new Date().toISOString().slice(11,19)}] phase=${phase?.trim()} pct=${pct} tasks=${tasks}`)
      await page.screenshot({ path: `/tmp/chg009-progress-${Date.now()}.png` })
      prevPct = pctNum
    }

    if (done) {
      console.log('✓ 구현 완료!')
      completed = true
      break
    }
    if (phase?.toLowerCase().includes('error')) {
      console.log('✗ 에러 phase:', phase)
      break
    }
  }

  await page.screenshot({ path: '/tmp/chg009-06-final.png' })

  // 7. 최종 태스크 목록 출력
  const taskItems = await page.locator('.ctv-task').all()
  console.log(`\n최종 태스크 (${taskItems.length}개):`)
  for (const t of taskItems) {
    const icon  = await t.locator('.ctv-task__icon').textContent().catch(() => '')
    const id    = await t.locator('.ctv-task__id').textContent().catch(() => '')
    const title = await t.locator('.ctv-task__title').textContent().catch(() => '')
    console.log(` ${icon?.trim()} ${id?.trim()} ${title?.trim()}`)
  }

  // 8. 상태 변경 확인
  const finalStatus = await page.locator('.cd-status').textContent().catch(() => '')
  console.log('\n최종 Change 상태:', finalStatus?.trim())
  console.log('구현 완료 여부:', completed)
})
