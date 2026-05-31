import { test, expect } from '@playwright/test'
import path from 'path'

const SHOTS = path.resolve(__dirname, '../screenshots')
const APP = process.env.APP_URL || 'http://localhost:5180'

test.use({
  viewport: { width: 1400, height: 2200 },
  // SSE/long-poll SPA never reaches networkidle — use a normal load.
  launchOptions: { args: ['--no-sandbox', '--disable-dev-shm-usage'] },
})
test.setTimeout(120_000)

async function openRequirements(page) {
  await page.goto(APP, { waitUntil: 'domcontentloaded' })
  // 앱 셸이 뜰 때까지 대기(탭 바의 Requirements 텍스트).
  await page.waitForTimeout(2500)
  // 상단 탭의 Requirements 버튼(첫 번째)만 클릭.
  const reqTab = page.getByRole('button', { name: 'Requirements' }).first()
  if (await reqTab.count()) {
    await reqTab.click().catch(() => {})
  }
  await page.waitForTimeout(1000)
}

test('01 — 요구사항 탭 + DDD 마법사 진입 버튼', async ({ page }) => {
  await openRequirements(page)
  await page.screenshot({ path: `${SHOTS}/01_requirements_tab.png`, fullPage: true })
})

test('02 — 마법사 프로파일링 화면', async ({ page }) => {
  await openRequirements(page)
  await page.getByRole('button', { name: /DDD 마법사/ }).first().click()
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${SHOTS}/02_wizard_profiling.png`, fullPage: true })
})

test('03 — 추천 단계 선택 화면', async ({ page }) => {
  await openRequirements(page)
  await page.getByRole('button', { name: /DDD 마법사/ }).first().click()
  await page.waitForTimeout(600)
  await page.getByRole('button', { name: '추천 받기 →' }).click()
  await page.waitForTimeout(1500)
  await page.screenshot({ path: `${SHOTS}/03_wizard_plan.png`, fullPage: true })
})

test('04 — 단계 진행 화면(답변/문서 입력)', async ({ page }) => {
  await openRequirements(page)
  await page.getByRole('button', { name: /DDD 마법사/ }).first().click()
  await page.waitForTimeout(600)
  await page.getByRole('button', { name: '추천 받기 →' }).click()
  await page.waitForTimeout(1200)
  await page.getByRole('button', { name: '시작 →' }).click()
  await page.waitForTimeout(1000)
  await page.screenshot({ path: `${SHOTS}/04_wizard_step.png`, fullPage: true })
})
