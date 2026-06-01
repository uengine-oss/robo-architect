import { test, expect } from '@playwright/test'
import path from 'path'

/**
 * 034 — Epic→Feature(spec.md) 자동 생성 e2e:
 * Epic 선택 → "✨ Feature 자동생성" → deep agent 리즈닝 스트림 패널 →
 * 검토 모달(각 Feature의 US·acceptance criteria·edge cases·가정) 확인.
 */
const SHOTS = path.resolve(__dirname, '../screenshots')
const APP = process.env.APP_URL || 'http://localhost:5180'
const EPIC = 'PW테스트배송'

test('Epic → Feature 자동생성 (리즈닝 스트림 + acceptance criteria)', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto(APP)
  await page.locator('.top-bar__tabs button', { hasText: 'Requirements' }).first().click()
  await page.waitForSelector('.req-tree', { timeout: 30_000 })
  await page.waitForTimeout(800)

  // Epic 선택
  await page.locator('.tree-node--epic .tree-row', { hasText: EPIC }).first().click()
  await page.waitForSelector('.epic-detail', { timeout: 10_000 })
  await page.screenshot({ path: `${SHOTS}/fg_01_epic_selected.png` })

  // Feature 자동생성 → 리즈닝 스트림 패널
  await page.locator('.epic-detail .ed-gen').click()
  await page.waitForSelector('.fgs', { timeout: 10_000 })
  await page.waitForTimeout(2500) // 리즈닝 몇 줄 흐르도록
  await page.screenshot({ path: `${SHOTS}/fg_02_reasoning_stream.png` })

  // 완료되면 검토 모달
  await page.waitForSelector('.dialog:has-text("Feature 자동 생성 — 제안 검토")', { timeout: 160_000 })
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${SHOTS}/fg_03_review.png` })

  // 첫 Feature 펼쳐 acceptance criteria 확인
  await page.locator('.feat .feat__toggle').first().click()
  await page.waitForSelector('.feat .sec ul.ac li', { timeout: 10_000 })
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${SHOTS}/fg_04_review_expanded_ac.png`, fullPage: true })

  // acceptance criteria가 실제로 1개 이상 렌더됐는지 단언
  const acCount = await page.locator('.feat .sec ul.ac li').count()
  expect(acCount).toBeGreaterThan(0)

  // 닫기(등록하지 않음 — 테스트 데이터 최소화)
  await page.locator('.dialog:has-text("Feature 자동 생성 — 제안 검토") .btn', { hasText: '취소' }).click()
})
