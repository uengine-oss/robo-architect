/**
 * E2E (headed): "회원탈퇴시 적립된 마일리지에 대한 승계기능"
 *
 * DRAFT → SUBMITTED → PLAN_APPROVED → DESIGN_APPLIED → APPROVED → (Code탭 /robo-implement)
 */
import { test, expect } from '@playwright/test'

const PROMPT = '회원탈퇴시 적립된 마일리지에 대한 승계기능이 필요하다. 탈퇴 회원의 마일리지를 지정한 다른 회원에게 양도할 수 있어야 한다.'

test.use({
  headless: false,
  launchOptions: { slowMo: 200 },      // 사람이 보기 좋은 속도
})
test.setTimeout(600_000)

async function log(msg: string) { console.log(`\n${msg}`) }

async function waitFor(ms: number, page) {
  await page.waitForTimeout(ms)
}

test('마일리지 승계 Change: 생성 → 2단계 승인 → Code탭 구현', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })

  // ── 1. Changes 탭 ────────────────────────────────────────────────────
  await log('① Changes 탭 진입')
  await page.goto('/', { waitUntil: 'networkidle' })
  await page.locator('button').filter({ hasText: 'Changes' }).first().click()
  await page.waitForSelector('.cp-list', { timeout: 10_000 })
  await page.screenshot({ path: '/tmp/ms-01-list.png' })

  // ── 2. Change 생성 ───────────────────────────────────────────────────
  await log('② Change 생성 다이얼로그')
  await page.locator('button').filter({ hasText: '+ 추가 Change' }).click()
  await page.waitForSelector('.cp-dialog', { timeout: 5_000 })
  await page.locator('.cp-textarea').fill(PROMPT)
  await page.waitForTimeout(400)
  await page.screenshot({ path: '/tmp/ms-02-dialog.png' })

  await log('③ 생성 + 분석 시작 클릭')
  await page.locator('button').filter({ hasText: '생성 + 분석 시작' }).click()

  // 다이얼로그가 닫힐 때까지 대기
  await page.waitForSelector('.cp-dialog', { state: 'hidden', timeout: 15_000 })
  await page.waitForTimeout(1000)
  await page.screenshot({ path: '/tmp/ms-03-created.png' })

  // 생성된 Change ID 추출
  const changeId = await page.locator('.cd-id').first().textContent({ timeout: 10_000 }).catch(() => '')
  await log(`④ 생성 완료: ${changeId?.trim()}`)

  // ── 3. 영향도 분석 대기 (백그라운드 자동 실행) ────────────────────────
  await log('⑤ 영향도 탭으로 이동 + 분석 완료 대기')
  // ChangeDetail이 자동으로 영향도 탭을 열었을 수 있음
  const impactTabBtn = page.locator('.cd-tab').filter({ hasText: '영향도' })
  await impactTabBtn.waitFor({ state: 'visible', timeout: 10_000 })
  await impactTabBtn.click()
  await page.waitForTimeout(500)

  // 분석 중 스피너 사라질 때까지 대기 (최대 3분)
  const analyzeBtn = page.locator('.civ-btn')
  const startMs = Date.now()
  while (Date.now() - startMs < 180_000) {
    await page.waitForTimeout(5000)
    const isAnalyzing = await page.locator('.civ-analyzing').isVisible().catch(() => false)
    const layerCount = await page.locator('.civ-layer').count().catch(() => 0)
    const nodeCount  = await page.locator('.civ-node').count().catch(() => 0)
    await log(`   분석 중: ${isAnalyzing} | 레이어: ${layerCount} | 노드: ${nodeCount}`)
    if (!isAnalyzing && layerCount > 0) {
      await log(`   ✅ 분석 완료: ${layerCount}개 레이어, ${nodeCount}개 노드`)
      break
    }
  }
  await page.screenshot({ path: '/tmp/ms-04-analyzed.png' })

  // ── 4. 제출 (DRAFT → SUBMITTED) ─────────────────────────────────────
  await log('⑥ 제출')
  const submitBtn = page.locator('button').filter({ hasText: '제출' })
  await submitBtn.waitFor({ state: 'visible', timeout: 5_000 }).catch(() => {})
  if (await submitBtn.isVisible()) {
    await submitBtn.click()
    await page.waitForTimeout(1500)
    const s = await page.locator('.cd-status').textContent().catch(() => '')
    await log(`   상태: ${s?.trim()}`)
  }
  await page.screenshot({ path: '/tmp/ms-05-submitted.png' })

  // ── 5. 1차 승인 (API) ─────────────────────────────────────────────────
  const id = changeId?.trim() || ''
  if (id) {
    await log('⑦ 1차 승인 (API: approver@uengine.org)')
    const r1 = await page.request.post(`/api/requirement-changes/${id}/approve`, {
      headers: {
        'Content-Type': 'application/json',
        'X-User-Email': 'approver@uengine.org',
        'X-User-Name': encodeURIComponent('Approver'),
      },
      data: { comment: '마일리지 승계 기능 - 1차 계획 승인' },
    })
    const b1 = await r1.json().catch(() => ({}))
    await log(`   응답 status: ${b1.status}`)

    // 목록에서 재선택해 상태 갱신
    await page.reload({ waitUntil: 'networkidle' })
    await page.locator('button').filter({ hasText: 'Changes' }).first().click()
    await page.waitForSelector('.cp-list', { timeout: 10_000 })
    await page.locator('.cp-item').filter({ hasText: id }).first().click()
    await page.waitForTimeout(1000)
    const s1 = await page.locator('.cd-status').textContent().catch(() => '')
    await log(`   UI 상태: ${s1?.trim()}`)
    await page.screenshot({ path: '/tmp/ms-06-plan-approved.png' })
  }

  // ── 6. 설계 반영 탭 → 설계 변경 적용 ────────────────────────────────
  await log('⑧ 설계 반영 탭')
  const designTabBtn = page.locator('.cd-tab').filter({ hasText: '설계 반영' })
  await designTabBtn.waitFor({ state: 'visible', timeout: 8_000 }).catch(() => {})

  if (await designTabBtn.isVisible()) {
    await designTabBtn.click()
    await page.waitForTimeout(800)
    await page.screenshot({ path: '/tmp/ms-07-design-tab.png' })

    const applyBtn = page.locator('button').filter({ hasText: '설계 변경 적용' })
    if (await applyBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await log('   설계 변경 적용 시작...')
      await applyBtn.click()

      // 완료 대기 (최대 5분)
      const t0 = Date.now()
      while (Date.now() - t0 < 300_000) {
        await page.waitForTimeout(6000)
        const still = await page.locator('.dcv-progress').isVisible().catch(() => false)
        const items = await page.locator('.dcv-item').count().catch(() => 0)
        const msg = await page.locator('.dcv-progress').textContent().catch(() => '')
        await log(`   ${still ? '⏳' : '✓'} items=${items} | "${msg?.trim().slice(0, 60)}"`)
        if (!still && items > 0) {
          await log(`   ✅ 설계 반영 완료: ${items}개`)
          break
        }
        // 상태가 DESIGN_APPLIED로 바뀌었으면 종료
        const statusNow = await page.locator('.cd-status').textContent().catch(() => '')
        if (statusNow?.includes('설계 반영')) break
      }
      await page.screenshot({ path: '/tmp/ms-08-design-applied.png' })
    } else {
      // 이미 완료된 경우
      const items = await page.locator('.dcv-item').count().catch(() => 0)
      await log(`   이미 반영된 항목: ${items}개`)
    }
  } else {
    await log('   ⚠️ 설계 반영 탭 없음')
    await page.screenshot({ path: '/tmp/ms-07-no-design-tab.png' })
  }

  // ── 7. 2차 승인 (API) ─────────────────────────────────────────────────
  if (id) {
    await log('⑨ 2차 승인 (API: approver@uengine.org)')
    const r2 = await page.request.post(`/api/requirement-changes/${id}/approve-impl`, {
      headers: {
        'Content-Type': 'application/json',
        'X-User-Email': 'approver@uengine.org',
        'X-User-Name': encodeURIComponent('Approver'),
      },
      data: { comment: '설계 반영 확인 완료 — 구현 허가' },
    })
    const b2 = await r2.json().catch(() => ({}))
    await log(`   응답 status: ${b2.status}`)

    // 페이지 갱신 + 재선택
    await page.reload({ waitUntil: 'networkidle' })
    await page.locator('button').filter({ hasText: 'Changes' }).first().click()
    await page.waitForSelector('.cp-list', { timeout: 10_000 })
    await page.locator('.cp-item').filter({ hasText: id }).first().click()
    await page.waitForTimeout(1000)
    const s2 = await page.locator('.cd-status').textContent().catch(() => '')
    await log(`   UI 상태: ${s2?.trim()}`)
    await page.screenshot({ path: '/tmp/ms-09-approved.png' })
  }

  // ── 8. 구현 시작 → Code 탭 + /robo-implement ─────────────────────────
  await log('⑩ 구현 시작 클릭 → Code 탭')
  const implBtn = page.locator('button').filter({ hasText: '구현 시작' })
  await implBtn.waitFor({ state: 'visible', timeout: 8_000 }).catch(() => {})

  if (await implBtn.isVisible()) {
    await implBtn.click()
    await page.waitForTimeout(2000)
    await page.screenshot({ path: '/tmp/ms-10-code-tab.png' })

    await log('   Claude 시작 + /robo-implement 전송 대기 (10초)...')
    await page.waitForTimeout(10000)
    await page.screenshot({ path: '/tmp/ms-11-robo-implement.png' })

    const termText = await page.locator('.xterm-rows, canvas').first()
      .evaluate(el => el.textContent || '').catch(() => '')
    const hasCmd = termText.includes('robo-implement') || termText.includes(id)
    await log(`   터미널 커맨드 확인: ${hasCmd}`)
  } else {
    await log('   ⚠️ 구현 시작 버튼 없음 (상태 확인 필요)')
    await page.screenshot({ path: '/tmp/ms-10-no-impl-btn.png' })
  }

  await log('\n🎉 E2E 테스트 완료!')
})
