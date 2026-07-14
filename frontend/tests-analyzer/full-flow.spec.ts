/**
 * graph integrity UI E2E — **업로드부터** 전 구간.
 *
 * 왜 이 순서인가:
 *   "이미 분석된 그래프를 구경"하면 스트림 경로(analyze_router → executor → NDJSON → 프론트)가
 *   전혀 안 밟힌다. 사용자가 실제로 겪는 건 그 경로다. 그래서 업로드 → 인제스천 → **스트림 수신**
 *   → 그래프 → 스키마 순으로 UI 가 직접 몰고 간다.
 *
 * 전제: antlr · analyzer · catalog · gateway · 명시적으로 선택한 Neo4j database.
 */
import { test, expect, Page } from '@playwright/test'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
// frontend/tests-analyzer → robo-architect → project → data
const DATA = resolve(__dirname, '..', '..', '..', 'data')
const SRC = [
  'cart.c', 'catalog.c', 'common_util.c', 'inventory.c', 'member.c', 'order.c',
  'payment.c', 'promotion.c', 'review_point.c', 'settlement.c', 'shipping.c', 'shopmall.h',
].map(f => resolve(DATA, 'source', f))
const DDL = [resolve(DATA, 'ddl', 'shopmall_schema.sql')]

const TAB_CODE = '[title="코드"]'
const TAB_GRAPH = '[title="코드 그래프"]'
const TAB_SCHEMA = '[title="데이터 스키마"]'

const SHOT = (n: string) => ({ path: `playwright-report-analyzer/${n}.png`, fullPage: true })

/**
 * 프론트 오류 수집 — **콘솔 문자열 + 실패한 네트워크 응답(URL 포함)**.
 *
 * 왜 둘 다인가: 브라우저 콘솔의 `Failed to load resource: ... 500` 메시지에는 **URL 이 없다**.
 * 문자열만 보면 "어느 서비스가 죽었는지" 알 수 없어 무관한 실패까지 통째로 걸러내게 된다
 * (= 검증이 무의미해짐). 그래서 응답을 URL 과 함께 따로 모아 **우리 스택(/robo/) 이 실패했는지**를
 * 정확히 본다.
 */
interface Failures { console: string[]; net: string[] }

function collectErrors(page: Page): Failures {
  const f: Failures = { console: [], net: [] }
  page.on('console', m => { if (m.type() === 'error') f.console.push(m.text()) })
  page.on('pageerror', e => f.console.push(String(e)))
  page.on('response', r => {
    if (r.status() >= 400) f.net.push(`${r.status()} ${r.url()}`)
  })
  page.on('requestfailed', r => f.net.push(`FAILED ${r.url()}`))
  return f
}

/**
 * 검증 대상과 **무관한 환경 결손**만 제외한다.
 *
 * `alarms` SSE: `AlarmToast.vue` 가 `${TEXT2SQL_BASE_URL}/events/stream/alarms` (= text2sql **8000**)
 * 로 EventSource 를 걸고 5초마다 재연결한다. 이 검증은 **analyzer 파트만**(antlr·analyzer·catalog·
 * gateway) 띄우므로 8000 이 없어 계속 실패한다. → 그래프/스키마 탭과 무관하며 045/046 결함이 아니다.
 * (전역 알람까지 보려면 text2sql 8000 을 함께 띄워야 한다.)
 */
const IGNORED_NET = /events\/stream\/alarms|favicon/i
const IGNORED_CONSOLE = /favicon|ResizeObserver|DevTools|Download the Vue|SSE 오류|Failed to load resource/i

/** 우리 스택(/robo/·프론트 자산) 의 실패만 남긴다. */
const realFailures = (f: Failures) => ({
  console: f.console.filter(x => !IGNORED_CONSOLE.test(x)),
  net: f.net.filter(x => !IGNORED_NET.test(x)),
})

function assertNoFailures(f: Failures) {
  const r = realFailures(f)
  expect(r.net, `실패한 네트워크 요청:\n${r.net.join('\n')}`).toHaveLength(0)
  expect(r.console, `콘솔 에러:\n${r.console.join('\n')}`).toHaveLength(0)
}

test.describe.configure({ mode: 'serial' })

test('E2E-01 업로드 → 인제스천 → NDJSON 스트림 수신 → 그래프 렌더', async ({ page }) => {
  test.skip(
    process.env.ROBO_E2E_ALLOW_GRAPH_RESET !== '1',
    '기존 그래프를 삭제하는 테스트다. 전용 DB에서 ROBO_E2E_ALLOW_GRAPH_RESET=1로 명시 실행한다.',
  )
  test.setTimeout(20 * 60 * 1000)   // 분석은 LLM 이라 오래 걸린다
  const errors = collectErrors(page)

  // ── 1) 코드(업로드) 탭 ────────────────────────────────
  await page.goto('/')
  await page.locator(TAB_CODE).click()
  await page.screenshot(SHOT('01-code-tab'))

  // ── 2) 업로드 모달 열기 (DropZone 클릭) ───────────────
  await page.locator('.dropzone, [class*="drop"]').first().click()
  await expect(page.locator('input[type="file"]').first()).toBeAttached({ timeout: 10_000 })

  // ── 3) 소스 + DDL 주입 (숨김 input — 실제 UI 경로) ────
  const inputs = page.locator('input[type="file"]')
  await inputs.nth(1).setInputFiles(SRC)     // fileInput (multiple) — 소스
  await page.waitForTimeout(1500)
  await inputs.nth(3).setInputFiles(DDL)     // ddlFileInput (multiple) — DDL
  await page.waitForTimeout(1500)
  await page.screenshot(SHOT('02-files-picked'))

  // ── 4) 모달 확인 — 버튼 이름은 「업로드」다 (실물 확인) ──
  await page.screenshot(SHOT('03-files-picked-in-modal'))
  const upload = page.getByRole('button', { name: '업로드' })
  await expect(upload).toBeVisible({ timeout: 10_000 })
  await upload.click()
  await page.waitForTimeout(2500)
  await page.screenshot(SHOT('04-existing-data-modal'))

  // ── 4b) "기존 데이터 감지" 모달 — 매 run = full rebuild 이므로 「삭제 후 시작」.
  //        (Neo4j 에 이전 run 노드가 있으면 앱이 물어본다. 헌법 Cost&Safety 와 같은 정책.)
  const wipeStart = page.getByText('삭제 후 시작')
  if (await wipeStart.count()) {
    await wipeStart.click()
    await page.waitForTimeout(2000)
    await page.screenshot(SHOT('05-after-wipe-choice'))
  }

  // ── 5) ★인제스천 시작 → 여기서 NDJSON 스트림이 열린다 ──
  //        (위 선택으로 바로 시작될 수도 있으니 버튼이 있을 때만 누른다.)
  const ingest = page.getByRole('button', { name: /인제스천 시작/ })
  if (await ingest.count()) {
    await expect(ingest).toBeVisible({ timeout: 15_000 })
    await ingest.click()
  }

  // 앱은 처리 시작 시 그래프 탭으로 자동 전환한다(UploadTab:47 — 실시간 렌더).
  await expect(page.locator(TAB_GRAPH)).toHaveClass(/active/, { timeout: 30_000 })
  await page.screenshot(SHOT('05-stream-start'))

  // ── 6) ★스트림 실제 수신 검증 ─────────────────────────
  //   (a) 그래프 객체 카운트가 0 에서 증가 = node_event 수신
  const body = page.locator('body')
  await expect
    .poll(async () => {
      const t = await body.innerText()
      const m = t.match(/그래프 객체\s*([\d,]+)/)
      return m ? parseInt(m[1].replace(/,/g, ''), 10) : 0
    }, { timeout: 5 * 60 * 1000, intervals: [2000] })
    .toBeGreaterThan(0)
  await page.screenshot(SHOT('06-stream-nodes-arriving'))

  //   (b) 단계가 0/7 에서 진행 = phase/step 이벤트 수신 → 7/7 완료
  await expect
    .poll(async () => (await body.innerText()).match(/단계\s*(\d+)\s*\/\s*7/)?.[1] ?? '0',
          { timeout: 18 * 60 * 1000, intervals: [5000] })
    .toBe('7')
  await page.screenshot(SHOT('07-stream-done-7of7'))

  //   (c) 스트림으로 들어온 노드가 실제로 캔버스에 그려졌다
  await expect(page.locator('canvas, svg').first()).toBeVisible()
  const finalText = await body.innerText()
  const nodeCount = parseInt((finalText.match(/그래프 객체\s*([\d,]+)/)?.[1] ?? '0').replace(/,/g, ''), 10)
  expect(nodeCount, '스트림으로 받은 그래프 객체 수').toBeGreaterThan(100)
  assertNoFailures(errors)
})

test('E2E-02 그래프 탭 — 노드 상세 카드 (045 FR-009/010/011/019)', async ({ page }) => {
  test.setTimeout(3 * 60 * 1000)
  const errors = collectErrors(page)

  await page.goto('/')
  await page.locator(TAB_GRAPH).click()
  // Navigator 트리에 노드가 실제로 올라올 때까지 (catalog → Neo4j)
  await expect(page.getByText('MODULES')).toBeVisible({ timeout: 60_000 })

  /**
   * 상세 패널의 **노드 검색**으로 연다 (`NodeDetailPanel.vue:467` `.node-search-input`
   * → 결과 드롭다운 `.search-result-item` 클릭 → `handleSearchResultSelect`).
   *
   * 왜 Navigator 트리가 아닌가 (실물 확인):
   *   Navigator 는 **모듈(→함수 F + 그 모듈이 쓰는 컬럼 C)** 과 **테이블**만 보여준다.
   *   변수(MEMBER)·상수(DEFINE)는 트리에 **아예 없다**. 그래서 트리로는 그 카드를 못 연다.
   *   (옛 테스트가 `product_code` 를 트리에서 클릭했을 때 열린 건 같은 이름의 **DB 컬럼**이었다
   *    → 컬럼 카드에도 "타입" 행이 있어 **거짓 통과**했다.)
   */
  const searchBox = page.getByPlaceholder('🔍 노드 이름, 또는 업무 말로 물어보기')
  const openNode = async (name: string) => {
    await searchBox.fill('')
    await searchBox.fill(name)
    await page.waitForTimeout(1200)
    const hit = page.locator('.search-result-item').first()
    await expect(hit, `검색 결과에 ${name} 이 떠야 한다`).toBeVisible({ timeout: 15_000 })
    await hit.click()
    await page.waitForTimeout(1500)
    return await page.locator('body').innerText()
  }

  // ★ 노드 이름은 **전역에서 유일한 것**만 쓴다.
  //   (옛 테스트는 `product_code` 를 썼는데 같은 이름이 C 변수 **와** DB 컬럼 두 개 있었다.
  //    컬럼 카드가 열려도 "타입" 행이 있어 **거짓 통과**했다 — 정작 검증하려던 변수 카드는
  //    열리지도 않았다. 그래서 아래는 값까지 단정해 엉뚱한 카드면 반드시 실패하게 한다.)

  // FR-009 — 변수/멤버 카드에 **타입 값**이 실제로 뜬다.
  //   `reg_id` = MEMBER, var_type='char' (Neo4j 실측).
  //   옛 프론트는 `variable_type` 을 읽어 이 행이 **영구 공백**이었다.
  const varText = await openNode('reg_id')
  await page.screenshot(SHOT('08-variable-card'))
  expect(varText, 'FR-009 var_type 값이 화면에 뜬다').toMatch(/char/)

  // FR-010 — 상수 카드에 **값**이 뜬다. `CART_MOD` = DEFINE, value='"CART"'.
  const constText = await openNode('CART_MOD')
  await page.screenshot(SHOT('09-constant-card'))
  expect(constText, 'FR-010 상수 값이 화면에 뜬다').toMatch(/CART/)

  // 함수 카드에 원문 코드가 코드 viewer로 뜬다. 주석은 원문의 일부로만 보이고
  // 별도 주석 카드로 중복 표시하지 않는다.
  const fnText = await openNode('cart_add_item')
  await page.screenshot(SHOT('10-function-card'))
  expect(fnText, '원문 코드').toMatch(/원문 코드/)
  await expect(page.locator('.monaco-editor').first()).toBeVisible()
  await expect(page.locator('.detail-card__label', { hasText: '주석' })).toHaveCount(0)

  assertNoFailures(errors)
})

test('E2E-03 스키마 탭 — 테이블·논리명 (045 FR-013)', async ({ page }) => {
  test.setTimeout(3 * 60 * 1000)
  const errors = collectErrors(page)

  await page.goto('/')
  await page.locator(TAB_SCHEMA).click()
  await expect(page.locator(TAB_SCHEMA)).toHaveClass(/active/)
  await page.waitForTimeout(8000)
  await page.screenshot(SHOT('10-schema-tab'))

  const text = await page.locator('body').innerText()
  // DDL 22 테이블이 실제로 렌더된다
  expect(text, '테이블 렌더').toMatch(/member|orders|payment|shipping|product/i)
  // FR-013 — 논리명(한글)이 화면에 뜬다 (전엔 artifact 에 빈값이었다)
  expect(text, 'FR-013 논리명').toMatch(/[가-힣]{2,}/)
  assertNoFailures(errors)
})
