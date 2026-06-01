// @ts-check
const { test, expect } = require('@playwright/test')
const path = require('path')

const SHOTS = path.resolve(__dirname, '../screenshots')
const APP = process.env.APP_URL || 'http://localhost:5182'

test.use({ viewport: { width: 1400, height: 2200 } })
test.setTimeout(90_000)

async function openRequirements(page) {
  await page.goto(APP, { waitUntil: 'domcontentloaded' })
  // SPA가 로드될 때까지 충분히 대기 (desktop launcher 등 gate 통과)
  await page.waitForTimeout(4000)
  // Requirements 탭 버튼 클릭 시도 (이미 활성이면 no-op)
  const reqBtn = page.locator('button', { hasText: 'Requirements' }).first()
  if (await reqBtn.count() > 0) {
    await reqBtn.click().catch(() => {})
    await page.waitForTimeout(500)
  }
}

test('01 — 요구사항 탭 전체 화면', async ({ page }) => {
  await openRequirements(page)
  await page.screenshot({ path: `${SHOTS}/01_requirements_tab.png`, fullPage: true })
})

test('02 — DDD 마법사 버튼 클릭 → 프로파일링 화면', async ({ page }) => {
  await openRequirements(page)
  // 툴바의 "🧭 DDD 마법사" 버튼 (이모지 포함, 부분 일치)
  const wizBtn = page.locator('button', { hasText: 'DDD 마법사' }).first()
  await wizBtn.waitFor({ state: 'visible', timeout: 10_000 })
  await wizBtn.click()
  await page.waitForTimeout(1000)
  await page.screenshot({ path: `${SHOTS}/02_wizard_profiling.png`, fullPage: true })
})

test('03 — 추천 받기 클릭 → 단계 선택 화면', async ({ page }) => {
  await openRequirements(page)
  const wizBtn = page.locator('button', { hasText: 'DDD 마법사' }).first()
  await wizBtn.waitFor({ state: 'visible', timeout: 10_000 })
  await wizBtn.click()
  await page.waitForTimeout(600)
  await page.locator('button', { hasText: '추천 받기' }).click()
  await page.waitForTimeout(1800)
  await page.screenshot({ path: `${SHOTS}/03_wizard_plan.png`, fullPage: true })
})

test('04 — 시작 → 단계 진행 화면', async ({ page }) => {
  await openRequirements(page)
  const wizBtn = page.locator('button', { hasText: 'DDD 마법사' }).first()
  await wizBtn.waitFor({ state: 'visible', timeout: 10_000 })
  await wizBtn.click()
  await page.waitForTimeout(600)
  await page.locator('button', { hasText: '추천 받기' }).click()
  await page.waitForTimeout(1500)
  const startBtn = page.locator('button', { hasText: '시작 →' })
  if (await startBtn.count() > 0) {
    await startBtn.click()
    await page.waitForTimeout(1200)
  }
  await page.screenshot({ path: `${SHOTS}/04_wizard_step.png`, fullPage: true })
})
