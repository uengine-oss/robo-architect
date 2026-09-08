import { test, expect } from '@playwright/test'
import { writeFileSync } from 'fs'
import { apiHeaders } from './api-auth'

/**
 * 산출물 문서 — 기준 템플릿(local-msaez DocumentTemplate.vue)과의 정합.
 *
 * 보는 것은 셋이다.
 *   1) 섹션 구성이 기준과 같은가 — 특히 'Aggregate 설계'가 제자리에 있는가
 *   2) 머메이드 도식이 실제로 그려지는가 — BC 분해 결과와 BC 별 Aggregate 구조도
 *   3) 페이지네이션 규칙이 인쇄 매체에서 실제로 걸리는가
 *
 * 3번은 계산된 스타일을 인쇄 매체로 바꿔 놓고 재는 것이지, PDF 를 뽑아 보는 것이
 * 아니다. 인쇄 경로는 지금 기업 납품 설정으로 꺼져 있다.
 *
 * rtk 래퍼가 통과한 실행의 콘솔을 삼키므로 실측값은 파일로도 남긴다.
 */
const DIAG = '/tmp/export-doc-diag.json'

test.describe('산출물 문서', () => {
  test.setTimeout(180_000)

  async function openDoc(page: any) {
    await page.goto('/', { waitUntil: 'networkidle' })
    // 첫 화면은 Proposals 다. 산출물 버튼은 캔버스 오른쪽 띠에 있으므로 Design 을 먼저 연다.
    await page.getByRole('button', { name: 'Design', exact: true }).first().click()
    const exportBtn = page.locator('[title="Export Document"]').first()
    await expect(exportBtn, '산출물 버튼이 있어야 한다').toBeVisible({ timeout: 30_000 })
    await exportBtn.click()
    // 데이터를 다 읽어야 섹션이 생긴다.
    await expect(page.locator('.doc .loading-box')).toHaveCount(0, { timeout: 120_000 })
    await page.waitForTimeout(1_500)
  }

  test('섹션 구성 · 도식 · 인쇄 페이지네이션', async ({ page, request }) => {
    const diag: any = {}

    // 인증 강제가 켜져 있으면 직접 호출도 자격이 필요하다. 없으면 401 이 오고
    // `contexts.length` 가 undefined 가 돼, 원인이 인증이라는 것이 안 드러난다.
    const headers = await apiHeaders(request)
    const contexts = await (
      await request.get('http://localhost:8000/api/contexts', { headers })
    ).json()
    diag.bcCount = contexts.length

    await openDoc(page)

    // ── 1. 섹션 구성 ──
    const labels = await page.locator('.section-selector .chk span').allTextContents()
    diag.sections = labels
    expect(labels, '기준의 애그리거트 설계 자리가 있어야 한다').toContain('Aggregate 설계')
    // 순서도 기준을 따른다 — BC 다음, 모델 전반 앞.
    expect(labels.indexOf('Aggregate 설계')).toBe(labels.indexOf('Bounded Context') + 1)
    expect(labels.indexOf('Aggregate 설계')).toBe(labels.indexOf('모델 전반 정보') - 1)

    // ── 2. 도식 ──
    // BC 분해 결과는 컨텍스트 간 관계가 없어도 그려져야 한다.
    const overview = page.locator('[data-mmd-id="bc-overview"] svg')
    await expect(overview, 'BC 분해 결과 도식이 그려져야 한다').toHaveCount(1, { timeout: 30_000 })
    diag.overviewNodes = await page.locator('[data-mmd-id="bc-overview"] svg .node').count()
    expect(diag.overviewNodes, 'BC 수만큼 노드가 있어야 한다').toBeGreaterThanOrEqual(contexts.length)

    // BC 마다 Aggregate 구조도.
    const aggDiagrams = page.locator('[data-mmd-id^="agg-"] svg')
    diag.aggDiagrams = await aggDiagrams.count()
    expect(diag.aggDiagrams, 'BC 별 Aggregate 구조도가 있어야 한다').toBeGreaterThan(0)
    diag.mmdFail = await page.locator('.mmd-fail').count()
    expect(diag.mmdFail, '그리지 못한 도식이 없어야 한다').toBe(0)

    // 기준의 하위 구성 — '어그리거트 모델' / '어그리거트 분석' 두 자리
    const heads = await page.locator('.doc h3').allTextContents()
    diag.aggHeads = heads.filter(h => h.includes('Aggregate 모델') || h.includes('Aggregate 분석'))
    expect(diag.aggHeads.some(h => h.includes('-1. Aggregate 모델')), '모델이 있어야 한다').toBeTruthy()
    expect(diag.aggHeads.some(h => h.includes('-2. Aggregate 분석')), '분석이 있어야 한다').toBeTruthy()

    // BC 섹션의 번호가 기준과 같은 자리에 있는가
    const bcHeads = await page.locator('.doc h3').allTextContents()
    diag.bcHeads = bcHeads.filter(h => h.includes('분해 결과') || h.includes('Bounded Context 요약'))
    expect(diag.bcHeads.some(h => h.includes('-1. 분해 결과'))).toBeTruthy()
    expect(diag.bcHeads.some(h => h.includes('-2. Bounded Context 요약'))).toBeTruthy()

    // ── 3. 인쇄 페이지네이션 ──
    await page.emulateMedia({ media: 'print' })
    await page.waitForTimeout(300)
    const print = await page.evaluate(() => {
      const g = (el: Element | null, p: string) => (el ? getComputedStyle(el).getPropertyValue(p).trim() : '')
      const thead = document.querySelector('.doc .tbl thead')
      const row = document.querySelector('.doc .tbl tbody tr')
      const block = document.querySelector('.doc .block')
      // 가장 긴 표가 한 장(A4 본문 ≈ 1050px)을 넘는지도 같이 잰다.
      let tallest = 0
      document.querySelectorAll('.doc .tbl').forEach(t => { tallest = Math.max(tallest, (t as HTMLElement).offsetHeight) })
      return {
        theadDisplay: g(thead, 'display'),
        rowBreakInside: g(row, 'break-inside') || g(row, 'page-break-inside'),
        blockBreakInside: g(block, 'break-inside') || g(block, 'page-break-inside'),
        tallestTablePx: tallest,
      }
    })
    diag.print = print
    writeFileSync(DIAG, JSON.stringify(diag, null, 2))
    console.log('[test]', JSON.stringify(diag, null, 2))

    // 표가 한 장을 넘는 순간부터 아래 셋이 의미를 갖는다.
    expect(print.theadDisplay, '표 머리글이 장마다 되풀이돼야 한다').toBe('table-header-group')
    expect(print.rowBreakInside, '행이 가운데서 잘리면 안 된다').toBe('avoid')
    expect(print.blockBreakInside, '긴 블록은 넘겨서 이어져야 한다 — avoid 면 임의 위치에서 잘린다').toBe('auto')
  })
})

/**
 * Word 산출물에도 같은 내용이 실리는가.
 *
 * 내보내기는 화면 DOM 이 아니라 **데이터에서 따로** 문서를 만든다. 그래서 미리보기에만
 * 섹션을 넣으면 docx 에서는 오류 없이 빠진다 — 열어 보기 전에는 모른다. 실제로 받아서
 * 안을 들여다본다.
 */
test.describe('산출물 Word', () => {
  test.setTimeout(240_000)

  test('새 섹션과 표 머리글 반복이 docx 에 들어간다', async ({ page }) => {
    const { readFileSync, writeFileSync } = await import('fs')
    const { execSync } = await import('child_process')

    await page.goto('/', { waitUntil: 'networkidle' })
    await page.getByRole('button', { name: 'Design', exact: true }).first().click()
    await page.locator('[title="Export Document"]').first().click()
    await expect(page.locator('.doc .loading-box')).toHaveCount(0, { timeout: 120_000 })
    // 도식이 그려진 뒤라야 Word 가 그림을 담는다.
    await expect(page.locator('[data-mmd-id="bc-overview"] svg')).toHaveCount(1, { timeout: 30_000 })
    await page.waitForTimeout(1_500)

    // 내보내기는 드롭다운 안에 있다.
    await page.getByRole('button', { name: '내보내기' }).first().click()
    const wordBtn = page.locator('.export-dropdown__item', { hasText: 'Word' }).first()
    await expect(wordBtn, 'Word 내보내기 버튼').toBeVisible({ timeout: 15_000 })

    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 180_000 }),
      wordBtn.click(),
    ])
    const path = '/tmp/export-doc-check.docx'
    await download.saveAs(path)

    const xml = execSync(`unzip -p ${path} word/document.xml`, { maxBuffer: 64 * 1024 * 1024 }).toString()
    const media = execSync(`unzip -l ${path} | grep -c 'word/media/' || true`).toString().trim()

    const found = {
      bytes: readFileSync(path).length,
      aggregateDesign: xml.includes('Aggregate 설계'),
      aggModel: /Aggregate 모델/.test(xml),
      aggAnalysis: /Aggregate 분석/.test(xml),
      decomposition: xml.includes('분해 결과'),
      tblHeader: (xml.match(/<w:tblHeader\b/g) || []).length,
      // w:val 없는 셰이딩은 Word 가 표 손상으로 본다 (local-msaez e1f44ccf).
      shdWithoutVal: (xml.match(/<w:shd[^/]*\/>/g) || []).filter(t => !t.includes('w:val')).length,
      // 제어문자가 하나라도 남으면 OOXML 이 깨진다 (local-msaez 50e1e327).
      controlChars: (xml.match(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g) || []).length,
      cantSplit: (xml.match(/<w:cantSplit\b/g) || []).length,
      images: Number(media),
    }
    writeFileSync('/tmp/export-doc-word-diag.json', JSON.stringify(found, null, 2))
    console.log('[test]', JSON.stringify(found, null, 2))

    expect(found.aggregateDesign, 'Aggregate 설계 섹션이 docx 에 있어야 한다').toBeTruthy()
    expect(found.aggModel && found.aggAnalysis, '모델·분석 두 자리가 있어야 한다').toBeTruthy()
    expect(found.decomposition, 'BC 분해 결과가 있어야 한다').toBeTruthy()
    expect(found.tblHeader, '표마다 머리글 반복 표시가 있어야 한다').toBeGreaterThan(5)
    expect(found.cantSplit, '행을 자르지 않는 표시가 있어야 한다').toBeGreaterThan(20)
    expect(found.images, '도식이 그림으로 담겨야 한다').toBeGreaterThan(0)
    expect(found.shdWithoutVal, '셰이딩에 w:val 이 빠지면 Word 가 표 손상으로 본다').toBe(0)
    expect(found.controlChars, '본문에 XML 비허용 문자가 남으면 안 된다').toBe(0)
  })
})
