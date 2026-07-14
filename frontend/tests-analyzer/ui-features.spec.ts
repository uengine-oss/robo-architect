/**
 * 코드 그래프 탭 + 데이터 스키마 탭 — **기능 전수** 육안 검증.
 *
 * 목적: 자동 단정만으로는 "보이긴 하는데 이상한" 상태를 못 잡는다. 그래서 각 기능을 실제로
 * 조작하고 **단계마다 스크린샷**을 남겨 사람이 눈으로 판정한다.
 *
 * 산출물: `D:\work\robo\_ui-verification\{graph,schema}\*.png`
 * 전제:   antlr · analyzer · catalog · gateway · 명시적으로 선택한 Neo4j database
 */
import { test, expect, Page } from '@playwright/test'

const OUT = 'D:/work/robo/_ui-verification'
const G = (n: string) => `${OUT}/graph/${n}.png`
const S = (n: string) => `${OUT}/schema/${n}.png`

const TAB_GRAPH = '[title="코드 그래프"]'
const TAB_SCHEMA = '[title="데이터 스키마"]'

/** 실패한 네트워크 요청 수집 (알람 SSE = text2sql 8000 미기동 → 무관하므로 제외). */
function netFailures(page: Page): string[] {
  const f: string[] = []
  page.on('response', r => {
    if (r.status() >= 400 && !/events\/stream\/alarms|favicon/i.test(r.url())) {
      f.push(`${r.status()} ${r.url()}`)
    }
  })
  return f
}

test.describe.configure({ mode: 'serial' })
test.setTimeout(5 * 60 * 1000)

// ═══════════════════════════════════════════════════════════════
//  코드 그래프 탭
// ═══════════════════════════════════════════════════════════════

test('그래프 탭 — 기능 전수', async ({ page }) => {
  const fails = netFailures(page)

  await page.goto('/')
  await page.locator(TAB_GRAPH).click()
  await expect(page.getByText('MODULES')).toBeVisible({ timeout: 60_000 })
  await page.waitForTimeout(2000)
  await page.screenshot({ path: G('01-초기-네비게이터'), fullPage: true })

  // ── 1) Navigator 노드를 캔버스로 **드래그** → 1-hop 이웃 함께 표시 ──
  const canvas = page.locator('.graph-canvas, canvas, svg').first()
  const src = page.getByText('cart_add_item', { exact: true }).first()
  await expect(src).toBeVisible({ timeout: 20_000 })
  await src.dragTo(canvas)
  await page.waitForTimeout(3000)
  await page.screenshot({ path: G('02-드래그로-캔버스에-놓기'), fullPage: true })

  // ── 2) 캔버스의 노드를 클릭 → 노드 패널 정보 표시 ──
  await canvas.click({ position: { x: 640, y: 420 } })
  await page.waitForTimeout(1500)
  await page.screenshot({ path: G('03-캔버스-노드-클릭-패널'), fullPage: true })

  // ── 3) 노드 패널 **검색** (이름) → 결과 → 상세 ──
  const search = page.getByPlaceholder('🔍 노드 이름, 또는 업무 말로 물어보기')
  if (await search.count()) {
    await search.fill('CART_MOD')                    // DEFINE 상수 (value='"CART"')
    await page.waitForTimeout(1500)
    await page.screenshot({ path: G('04-노드검색-결과드롭다운'), fullPage: true })

    const hit = page.locator('.search-result-item').first()
    if (await hit.count()) {
      await hit.click()
      await page.waitForTimeout(1500)
      await page.screenshot({ path: G('05-상수카드-값표시'), fullPage: true })
    }

    // 변수(MEMBER) — var_type 표시 확인 (045 FR-009)
    await search.fill('')
    await search.fill('reg_id')
    await page.waitForTimeout(1500)
    const hit2 = page.locator('.search-result-item').first()
    if (await hit2.count()) {
      await hit2.click()
      await page.waitForTimeout(1500)
      await page.screenshot({ path: G('06-변수카드-타입표시'), fullPage: true })
    }

    // 함수 — 원문 코드는 code viewer에 표시하고 주석은 원문 안에서만 보인다.
    await search.fill('')
    await search.fill('cart_add_item')
    await page.waitForTimeout(1500)
    const hit3 = page.locator('.search-result-item').first()
    if (await hit3.count()) {
      await hit3.click()
      await page.waitForTimeout(1500)
      await page.screenshot({ path: G('07-함수카드-원문'), fullPage: true })
    }
    await search.fill('')
  }

  // ── 4) 물리명 ↔ 논리명 토글 ──
  const nameToggle = page.getByText('물리명').first()
  if (await nameToggle.count()) {
    await nameToggle.click()
    await page.waitForTimeout(1500)
    await page.screenshot({ path: G('08-논리명-토글'), fullPage: true })
    await nameToggle.click()
    await page.waitForTimeout(800)
  }

  // ── 5) 보기 모드 드롭다운 ──
  const viewMode = page.getByText(/보기[::]/).first()
  if (await viewMode.count()) {
    await viewMode.click()
    await page.waitForTimeout(1200)
    await page.screenshot({ path: G('09-보기모드-드롭다운'), fullPage: true })
    await page.keyboard.press('Escape')
    await page.waitForTimeout(500)
  }

  // ── 6) 필터 드롭다운 (라벨·관계 필터) ──
  const filter = page.getByText('필터').first()
  if (await filter.count()) {
    await filter.click()
    await page.waitForTimeout(1200)
    await page.screenshot({ path: G('10-필터-드롭다운'), fullPage: true })
    await page.keyboard.press('Escape')
    await page.waitForTimeout(500)
  }

  // ── 7) 스타일 패널 (색상·굵기) ──
  const styleBtn = page.locator('[title*="스타일"], [class*="style-panel"], [class*="GraphStyle"]').first()
  if (await styleBtn.count()) {
    await styleBtn.click()
    await page.waitForTimeout(1200)
    await page.screenshot({ path: G('11-스타일패널'), fullPage: true })
  }

  await page.screenshot({ path: G('12-최종'), fullPage: true })
  expect(fails, `실패 요청:\n${fails.join('\n')}`).toHaveLength(0)
})

// ═══════════════════════════════════════════════════════════════
//  데이터 스키마 탭
// ═══════════════════════════════════════════════════════════════

test('스키마 탭 — 기능 전수', async ({ page }) => {
  const fails = netFailures(page)

  await page.goto('/')
  await page.locator(TAB_SCHEMA).click()
  await page.waitForTimeout(8000)
  await page.screenshot({ path: S('01-초기-스키마캔버스'), fullPage: true })

  // ── 1) 테이블 카드 클릭 → 상세 패널 (컬럼·설명·출처) ──
  const table = page.getByText('member', { exact: true }).first()
  if (await table.count()) {
    await table.click()
    await page.waitForTimeout(2000)
    await page.screenshot({ path: S('02-테이블-상세패널'), fullPage: true })
  } else {
    // 캔버스 카드가 텍스트로 안 잡히면 카드 클래스로
    const card = page.locator('[class*="table-card"], [class*="TableCard"]').first()
    if (await card.count()) {
      await card.click()
      await page.waitForTimeout(2000)
      await page.screenshot({ path: S('02-테이블-상세패널'), fullPage: true })
    }
  }

  // ── 2) 논리명 ↔ 물리명 전환 (NameModeSwitch) ──
  const nameSwitch = page.locator('[class*="name-mode"], [class*="NameMode"]').first()
  if (await nameSwitch.count()) {
    await nameSwitch.click()
    await page.waitForTimeout(2000)
    await page.screenshot({ path: S('03-논리명-전환'), fullPage: true })
  } else {
    const t = page.getByText(/논리명|물리명/).first()
    if (await t.count()) {
      await t.click()
      await page.waitForTimeout(2000)
      await page.screenshot({ path: S('03-논리명-전환'), fullPage: true })
    }
  }

  // ── 3) 컬럼 클릭 → 컬럼 상세 (설명 출처: ddl / code / catalog) ──
  const col = page.getByText(/member_id|product_code|order_no/).first()
  if (await col.count()) {
    await col.click()
    await page.waitForTimeout(1800)
    await page.screenshot({ path: S('04-컬럼-상세-출처'), fullPage: true })
  }

  // ── 4) 관계(FK) — 카디널리티/편집 다이얼로그 ──
  const rel = page.locator('[class*="relationship"], [class*="edge"], path[class*="link"]').first()
  if (await rel.count()) {
    await rel.click({ force: true })
    await page.waitForTimeout(1500)
    await page.screenshot({ path: S('05-관계-선택'), fullPage: true })
  }

  await page.screenshot({ path: S('06-최종'), fullPage: true })
  expect(fails, `실패 요청:\n${fails.join('\n')}`).toHaveLength(0)
})
