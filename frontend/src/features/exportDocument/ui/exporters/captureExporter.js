/**
 * 네이티브 데이터 기반 Word/PPT 내보내기
 * - 텍스트/테이블은 네이티브 객체 (수정 가능)
 * - 다이어그램(Mermaid SVG)만 이미지 캡처
 * - 같은 BC의 소분류들을 하나의 section/slide에 합쳐 페이지 낭비 방지
 */
import * as htmlToImage from 'html-to-image'
import {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, ImageRun, WidthType,
} from 'docx'
import PptxGenJS from 'pptxgenjs'
import { saveAs } from 'file-saver'

// ── Constants ──
const FONT = '맑은 고딕'
const PAGE_W = 9026
const MARGIN = { top: 1440, right: 1440, bottom: 1440, left: 1440 }
const BORDERS = {
  top: { size: 1, color: '999999' }, bottom: { size: 1, color: '999999' },
  left: { size: 1, color: '999999' }, right: { size: 1, color: '999999' },
  insideHorizontal: { size: 1, color: '999999' }, insideVertical: { size: 1, color: '999999' },
}

// ── Word primitives ──
function txt(s, o = {}) { return new TextRun({ text: s || '-', font: FONT, size: o.size || 22, bold: o.bold, italic: o.italic, color: o.color }) }
function para(t, o = {}) { return new Paragraph({ children: typeof t === 'string' ? [txt(t, o)] : t, spacing: { after: o.after ?? 120, before: o.before ?? 0 }, alignment: o.align, indent: o.indent, heading: o.heading }) }
function h2(t) { return para(t, { heading: HeadingLevel.HEADING_2, size: 28, bold: true, after: 200 }) }
function h3(t) { return para(t, { heading: HeadingLevel.HEADING_3, size: 24, bold: true, after: 120 }) }
function h4(t) { return para(t, { size: 22, bold: true, after: 80 }) }
function empty() { return para('', { after: 60 }) }
function sec(children) { return { properties: { page: { margin: MARGIN } }, children } }

function tbl(headers, rows, widths) {
  const ws = widths || headers.map(() => Math.floor(PAGE_W / headers.length))
  return new Table({
    rows: [
      new TableRow({ children: headers.map((h, i) => new TableCell({ children: [new Paragraph({ children: [txt(h, { bold: true, size: 20 })], alignment: AlignmentType.CENTER })], shading: { fill: 'F1F3F5' }, width: { size: ws[i], type: WidthType.DXA } })) }),
      ...rows.map(row => new TableRow({ children: row.map((c, i) => new TableCell({ children: [new Paragraph({ children: [txt(String(c ?? '-'), { size: 20 })] })], width: { size: ws[i], type: WidthType.DXA } })) }))
    ],
    width: { size: PAGE_W, type: WidthType.DXA }, columnWidths: ws, borders: BORDERS,
  })
}

// ── SVG capture ──
async function captureSvg(container, selector) {
  if (!container) return null
  try {
    const el = container.querySelector(selector)
    const svg = el?.querySelector('svg') || el
    if (!svg) return null
    await new Promise(r => setTimeout(r, 500))
    const origWarn = console.warn
    console.warn = (...a) => { if (!a.join(' ').match(/cssRules|CSSStyleSheet|Error inlining/)) origWarn.apply(console, a) }
    try {
      const url = await htmlToImage.toPng(svg, { backgroundColor: '#ffffff', pixelRatio: 2, skipFonts: true, cacheBust: true })
      return await (await fetch(url)).arrayBuffer()
    } finally { console.warn = origWarn }
  } catch { return null }
}

// ── Word 섹션 커버 페이지 ──
function wordSectionCover(num, title, desc) {
  return sec([
    ...Array(6).fill(null).map(() => empty()),
    para(String(num), { align: AlignmentType.CENTER, size: 72, bold: true, color: '228BE6', after: 200 }),
    para(title, { align: AlignmentType.CENTER, size: 32, bold: true, after: 120 }),
    para(desc, { align: AlignmentType.CENTER, size: 20, color: '6C757D', after: 200 }),
  ])
}

// ════════════════════════════════════════
//  WORD (.docx)
// ════════════════════════════════════════
export async function exportToWord(data, container, onProgress) {
  const { allContexts, fullTrees, sortedContexts, allUserStories, crossBCPolicies, sectionNumbers: sn, selectedSections, helpers } = data
  const { bcName, bcTree, getCommandsFromTree, getReadModelsFromTree, allCmdsForCtx, allEvtsForCtx, resolveNodeName } = helpers
  const sections = []
  const aggTotal = Object.values(fullTrees).reduce((s, t) => s + (t.aggregates?.length || 0), 0)

  // ── 표지 ──
  sections.push(sec([
    ...Array(10).fill(null).map(() => empty()),
    para('Robo Architect', { align: AlignmentType.CENTER, size: 24, bold: true, color: '228BE6', after: 200 }),
    para('', { after: 100 }),
    para('소프트웨어 아키텍처 설계서', { align: AlignmentType.CENTER, size: 40, bold: true, after: 160 }),
    para('Event Storming 기반 설계 산출물', { align: AlignmentType.CENTER, size: 24, color: '495057', after: 600 }),
    para(`Bounded Context ${allContexts.length}개 · Aggregate ${aggTotal}개 · User Story ${allUserStories.length}개`, { align: AlignmentType.CENTER, size: 20, color: '868E96' }),
    para(new Date().toLocaleDateString('ko-KR'), { align: AlignmentType.CENTER, size: 20, color: 'ADB5BD' }),
  ]))

  // ── 목차 ──
  const toc = []
  function tocAdd(t, indent) { toc.push(para(t, { size: indent ? 20 : 22, bold: !indent, after: indent ? 60 : 100, indent: indent ? { left: 720 } : undefined })) }
  if (selectedSections.userStories) tocAdd(`${sn.userStories}. 사용자 스토리 종합`)
  if (selectedSections.boundedContext) {
    tocAdd(`${sn.boundedContext}. Bounded Context 정의`)
    sortedContexts.forEach((c, i) => tocAdd(`${sn.boundedContext}-${i + 1}. ${bcName(c)}`, true))
  }
  if (selectedSections.modelOverview) {
    tocAdd(`${sn.modelOverview}. 이벤트 스토밍 모델 전반 정보`)
    sortedContexts.forEach((c, i) => tocAdd(`${sn.modelOverview}-${i + 1}. ${bcName(c)}`, true))
  }
  if (selectedSections.apiSpecification) {
    tocAdd(`${sn.apiSpecification}. API 명세`)
    sortedContexts.forEach((c, i) => tocAdd(`${sn.apiSpecification}-${i + 1}. ${bcName(c)}`, true))
  }
  if (selectedSections.aggregateDetail) {
    tocAdd(`${sn.aggregateDetail}. Aggregate 상세`)
    sortedContexts.forEach((c, ci) => (bcTree(c)?.aggregates || []).forEach((a, ai) => tocAdd(`${sn.aggregateDetail}-${ci + 1}-${ai + 1}. ${bcName(c)} / ${a.displayName || a.name}`, true)))
  }
  sections.push(sec([h2('목 차'), ...toc]))

  // ── 1. 사용자 스토리 ──
  if (selectedSections.userStories) {
    sections.push(wordSectionCover(sn.userStories, '사용자 스토리 종합', '시스템에 등록된 사용자 스토리를 Bounded Context 별로 정리합니다.'))
    sections.push(sec([
      h2(`${sn.userStories}. 사용자 스토리 종합`),
      allUserStories.length
        ? tbl(['BC', 'As a', 'I want to', 'So that', '우선순위', '상태'],
            allUserStories.map(s => [s.bcName, s.role || '-', s.action || s.name || '-', s.benefit || '-', s.priority || '-', s.status || '-']),
            [1400, 1000, 2500, 2500, 700, 700])
        : para('등록된 사용자 스토리가 없습니다.', { italic: true, color: '999999' })
    ]))
  }

  // ── 2. Bounded Context (요약 + 모든 BC 상세를 한 section에) ──
  if (selectedSections.boundedContext) {
    sections.push(wordSectionCover(sn.boundedContext, 'Bounded Context 정의', '도메인을 구성하는 Bounded Context의 역할, 구성 요소, 상호 관계를 정의합니다.'))
    const ch = [
      h2(`${sn.boundedContext}. Bounded Context 정의`),
      tbl(['BC', '도메인 유형', '설명', 'Agg', 'Cmd', 'Evt', 'RM', 'US'],
        sortedContexts.map(c => { const t = bcTree(c); return [bcName(c), c.domainType || '-', (c.description || t?.description || '-').slice(0, 80), t?.aggregates?.length || 0, t?.aggregates?.reduce((s, a) => s + (a.commands?.length || 0), 0) || 0, t?.aggregates?.reduce((s, a) => s + (a.events?.length || 0), 0) || 0, t?.readmodels?.length || 0, t?.userStories?.length || 0] }),
        [1400, 1100, 2800, 600, 600, 600, 600, 600]),
      empty(),
    ]
    // BC 상세를 같은 section에 이어 붙임
    sortedContexts.forEach((ctx, ci) => {
      const t = bcTree(ctx)
      ch.push(h3(`${sn.boundedContext}-${ci + 1}. ${bcName(ctx)} [${ctx.domainType || ''}]`))
      if (ctx.description || t?.description) ch.push(para(ctx.description || t?.description, { size: 20, color: '666666', after: 60 }))
      // 구성요소를 테이블로
      const elements = []
      if (t?.aggregates?.length) elements.push(['Aggregate', t.aggregates.map(a => a.displayName || a.name).join(', ')])
      if (t?.policies?.filter(p => p.name).length) elements.push(['Policy', t.policies.filter(p => p.name).map(p => p.displayName || p.name).join(', ')])
      if (t?.readmodels?.length) elements.push(['Read Model', t.readmodels.map(r => r.displayName || r.name).join(', ')])
      if (t?.uis?.length) elements.push(['UI', t.uis.map(u => u.displayName || u.name).join(', ')])
      if (elements.length) ch.push(tbl(['구성요소', '목록'], elements, [1600, 7400]))
      ch.push(empty())
    })

    // Cross-BC Policy
    if (crossBCPolicies.length) {
      ch.push(h3(`${sn.boundedContext}-${sortedContexts.length + 1}. 컨텍스트 간 연관 관계`))
      const img = await captureSvg(container, '.ctx-map-wrap')
      if (img) {
        ch.push(new Paragraph({ children: [new ImageRun({ data: img, transformation: { width: 550, height: 350 }, type: 'png' })], alignment: AlignmentType.CENTER, spacing: { after: 200 } }))
      }
      ch.push(tbl(['발행 BC', 'Event', 'Policy', '수신 BC', 'Command'], crossBCPolicies.map(r => [r.fromBC, r.fromEvent, r.policy, r.toBC, r.toCommand]), [1600, 1800, 2200, 1600, 1800]))
    }
    sections.push(sec(ch))
  }

  // ── 3. 모델 전반 (한 BC = 한 section, 내부 소분류 합침) ──
  if (selectedSections.modelOverview) {
    sections.push(wordSectionCover(sn.modelOverview, '이벤트 스토밍 모델 전반 정보', 'Command, Event, Policy, Read Model 구성 요소를 정리합니다.'))
    sortedContexts.forEach((ctx, ci) => {
      const t = bcTree(ctx); if (!t) return
      const bcN = bcName(ctx)
      const ch = [h2(`${sn.modelOverview}-${ci + 1}. ${bcN}`)]
      let sub = 0

      if (t.aggregates?.length) {
        sub++; ch.push(h3(`${sn.modelOverview}-${ci + 1}-${sub}. Aggregate`))
        const rows = []; t.aggregates.forEach(a => { rows.push([a.displayName || a.name, a.rootEntity || '-', (a.invariants || []).join('; ') || '-']) })
        ch.push(tbl(['이름', 'Root Entity', 'Invariants'], rows, [1600, 1400, 6000]))
      }

      const cmds = allCmdsForCtx(ctx)
      if (cmds.length) {
        sub++; ch.push(h3(`${sn.modelOverview}-${ci + 1}-${sub}. Command`))
        ch.push(tbl(['이름', 'Aggregate', 'Actor', 'Input Schema', '발생 Event'],
          cmds.map(c => [c.displayName || c.name, c.aggName, c.actor || '-', c.schema.map(s => `${s.name}(${s.type})`).join(', ') || '-', (c.events || []).map(e => e.displayName || e.name || e).join(', ') || '-']),
          [1600, 1200, 800, 2800, 2000]))
      }

      const evts = allEvtsForCtx(ctx)
      if (evts.length) {
        sub++; ch.push(h3(`${sn.modelOverview}-${ci + 1}-${sub}. Event`))
        ch.push(tbl(['이름', 'Aggregate', 'Version', 'Payload'],
          evts.map(e => [e.displayName || e.name, e.aggName, e.version || '-', e.payloadFields.map(f => `${f.name}(${f.type})`).join(', ') || '-']),
          [1800, 1200, 800, 5200]))
      }

      const pols = (t.policies || []).filter(p => p.name)
      if (pols.length) {
        sub++; ch.push(h3(`${sn.modelOverview}-${ci + 1}-${sub}. Policy`))
        ch.push(tbl(['이름', 'Trigger Event', 'Invoke Command', '설명'],
          pols.map(p => [p.displayName || p.name, resolveNodeName(p.triggerEventId), resolveNodeName(p.invokeCommandId), (p.description || '-').slice(0, 100)]),
          [1800, 2000, 2000, 3200]))
      }

      if (t.readmodels?.length) {
        sub++; ch.push(h3(`${sn.modelOverview}-${ci + 1}-${sub}. Read Model`))
        ch.push(tbl(['이름', '유형', 'Actor', '결과', '설명'],
          t.readmodels.map(r => [r.displayName || r.name, r.provisioningType || '-', r.actor || '-', r.isMultipleResult || '-', (r.description || '-').slice(0, 80)]),
          [1600, 800, 800, 1000, 4800]))
      }

      sections.push(sec(ch))
    })
  }

  // ── 4. API 명세 (한 BC = 한 section) ──
  if (selectedSections.apiSpecification) {
    sections.push(wordSectionCover(sn.apiSpecification, 'API 명세', 'Command 및 Read Model 상세 정보입니다.'))
    sortedContexts.forEach((ctx, ci) => {
      const t = bcTree(ctx); if (!t) return
      const ch = [h2(`${sn.apiSpecification}-${ci + 1}. ${bcName(ctx)} - API 명세`)]

      const cmds = getCommandsFromTree(t)
      if (cmds.length) {
        ch.push(h3(`${sn.apiSpecification}-${ci + 1}-1. Command`))
        ch.push(tbl(['Command', 'Aggregate', 'Actor', 'Input Schema', '발생 Event'],
          cmds.map(c => [c.name, c.agg, c.actor || '-', c.schema.map(s => `${s.name}(${s.type})`).join(', ') || '-', c.events.join(', ') || '-']),
          [1600, 1200, 800, 2800, 2000]))
      }

      const rms = getReadModelsFromTree(t)
      if (rms.length) {
        ch.push(h3(`${sn.apiSpecification}-${ci + 1}-2. Read Model`))
        ch.push(tbl(['이름', '유형', 'Actor', '결과', '설명'],
          rms.map(r => [r.name, r.pType, r.actor || '-', r.isMultiple || '-', (r.desc || '-').slice(0, 80)]),
          [1600, 800, 800, 1000, 4800]))
        rms.forEach(rm => {
          if (rm.props.length) {
            ch.push(h4(`${rm.name} - 속성`))
            ch.push(tbl(['이름', '타입', 'Key'], rm.props.map(p => [p.name, p.type || p.dataType || 'String', p.isKey ? 'Y' : '']), [3000, 3000, 1000]))
          }
        })
      }
      sections.push(sec(ch))
    })
  }

  // ── 5. Aggregate 상세 (한 Aggregate = 한 section) ──
  if (selectedSections.aggregateDetail) {
    sections.push(wordSectionCover(sn.aggregateDetail, 'Aggregate 상세', '속성, Enumeration, Value Object 구조를 정리합니다.'))
    sortedContexts.forEach((ctx, ci) => {
      const t = bcTree(ctx); if (!t?.aggregates?.length) return
      t.aggregates.forEach((agg, ai) => {
        const ch = [h2(`${sn.aggregateDetail}-${ci + 1}-${ai + 1}. ${bcName(ctx)} / ${agg.displayName || agg.name}`)]
        if (agg.rootEntity) ch.push(para(`Root Entity: ${agg.rootEntity}`, { size: 20, bold: true, after: 80 }))

        if (agg.properties?.length) {
          ch.push(h3('속성 (Properties)'))
          ch.push(tbl(['필드명', '타입', 'Key', 'FK', '설명'],
            agg.properties.map(p => [p.name, p.type || p.dataType || 'String', p.isKey ? 'Y' : '', p.isForeignKey ? 'Y' : '', p.description || '-']),
            [1800, 1400, 600, 600, 4600]))
        }
        if (agg.enumerations?.length) {
          ch.push(h3('Enumeration'))
          agg.enumerations.forEach(en => {
            const items = (en.items || en.values || []).map(i => typeof i === 'string' ? i : (i.value || i.name || '')).join(', ')
            ch.push(para(`${en.displayName || en.name}: [ ${items} ]`, { size: 20, after: 60 }))
          })
        }
        if (agg.valueObjects?.length) {
          ch.push(h3('Value Object'))
          agg.valueObjects.forEach(vo => {
            const fields = vo.properties || vo.fields || []
            if (fields.length) {
              ch.push(h4(vo.name))
              ch.push(tbl(['필드명', '타입'], fields.map(f => [f.name, f.type || f.dataType || 'String']), [4500, 4500]))
            } else {
              ch.push(para(vo.name, { size: 20, bold: true }))
            }
          })
        }
        sections.push(sec(ch))
      })
    })
  }

  const doc = new Document({ sections, styles: { default: { document: { run: { font: FONT, size: 22 } } } } })
  const blob = await Packer.toBlob(doc)
  saveAs(blob, `설계산출물-${new Date().toISOString().split('T')[0]}.docx`)
}

// ════════════════════════════════════════
//  PPT (.pptx)
// ════════════════════════════════════════
const PF = 'Malgun Gothic'
const SL_W = 10, SL_H = 7.5
const ROW_H = 0.38      // 행 높이 추정 (셀 wrap 고려 여유값)
const TITLE_H = 0.55
const CONTENT_TOP = 0.7  // title + 파란줄 + 충분한 여백
const CONTENT_BOTTOM = 6.9 // 하단 안전 마진

function pptCover(pptx, stats, date) {
  const s = pptx.addSlide({ bkgd: 'FFFFFF' })
  s.addText('Robo Architect', { x: 0, y: 1.5, w: '100%', fontSize: 16, color: '228BE6', align: 'center', fontFace: PF, bold: true })
  s.addShape('rect', { x: 4.5, y: 2.05, w: 1, h: 0.04, fill: { color: '228BE6' } })
  s.addText('소프트웨어 아키텍처 설계서', { x: 0, y: 2.4, w: '100%', fontSize: 28, color: '1A1A2E', align: 'center', fontFace: PF, bold: true })
  s.addText('Event Storming 기반 설계 산출물', { x: 0.5, y: 3.2, w: 9, fontSize: 14, color: '495057', align: 'center', fontFace: PF })
  if (stats) s.addText(stats, { x: 0, y: 4.5, w: '100%', fontSize: 10, color: '868E96', align: 'center', fontFace: PF })
  if (date) s.addText(date, { x: 0, y: 4.9, w: '100%', fontSize: 9, color: 'ADB5BD', align: 'center', fontFace: PF })
}

function pptSec(pptx, num, title, desc) {
  const s = pptx.addSlide({ bkgd: 'F8F9FA' })
  s.addText(String(num), { x: 0, y: 0.8, w: '100%', fontSize: 52, color: '228BE6', align: 'center', fontFace: PF, bold: true })
  s.addText(title, { x: 0, y: 1.8, w: '100%', fontSize: 24, color: '1A1A2E', align: 'center', fontFace: PF, bold: true })
  if (desc) s.addText(desc, { x: 1, y: 2.6, w: 8, fontSize: 12, color: '6C757D', align: 'center', fontFace: PF })
}

/**
 * SlideBuilder: 한 슬라이드에 여러 소 주제를 합쳐 넣는 도구
 * - addTitle(): 슬라이드 최상단 타이틀 + 파란 줄
 * - addSubTitle(): 소 주제 제목 (bold text)
 * - addTable(): 테이블 추가, 공간 부족 시 자동 새 슬라이드
 * - addDesc(): 설명 텍스트
 */
class SlideBuilder {
  constructor(pptx) {
    this.pptx = pptx
    this.slide = null
    this.curY = CONTENT_BOTTOM // force new slide on first add
    this.pageTitle = ''
  }

  _newSlide(title) {
    this.slide = this.pptx.addSlide()
    this.pageTitle = title || this.pageTitle
    this.slide.addText(this.pageTitle, { x: 0.4, y: 0.15, w: 9, fontSize: 14, color: '1A1A2E', fontFace: PF, bold: true })
    this.slide.addShape('rect', { x: 0.4, y: 0.42, w: 9.2, h: 0.02, fill: { color: '228BE6' } })
    this.curY = CONTENT_TOP
  }

  _needSpace(h) {
    return this.curY + h > CONTENT_BOTTOM
  }

  /** 새 슬라이드 강제 시작 (섹션 첫 페이지) */
  startPage(title) {
    this._newSlide(title)
  }

  /** 소 주제 제목 */
  addSubTitle(text) {
    const h = 0.28
    if (this._needSpace(h)) this._newSlide()
    this.slide.addText(text, { x: 0.4, y: this.curY, w: 9, fontSize: 11, color: '1A1A2E', fontFace: PF, bold: true })
    this.curY += h
  }

  /** 설명 텍스트 */
  addDesc(text) {
    if (!text) return
    // 긴 텍스트는 줄바꿈 고려
    const lines = Math.ceil((text.length || 1) / 100)
    const h = 0.22 * lines + 0.1
    if (this._needSpace(h)) this._newSlide()
    this.slide.addText(text, { x: 0.4, y: this.curY, w: 9, fontSize: 9, color: '6C757D', fontFace: PF, wrap: true })
    this.curY += h
  }

  /** 테이블 추가 — 자동 페이지 분할, 칼럼 너비 기반 높이 추정 */
  addTable(headers, rows, colW) {
    if (!rows.length) return

    // 칼럼 너비를 반영한 행 높이 추정
    // 한 글자 ≈ 0.07인치 (fontSize 7.5~8 기준), 칼럼 너비 내 몇 줄인지 계산
    const CHAR_W = 0.075
    function estimateRowH(row) {
      let maxLines = 1
      row.forEach((cell, i) => {
        const text = String(cell ?? '-')
        const colWidth = colW[i] || 1.5
        const charsPerLine = Math.floor(colWidth / CHAR_W)
        const lines = Math.ceil(text.length / Math.max(charsPerLine, 5))
        if (lines > maxLines) maxLines = lines
      })
      return ROW_H + (maxLines - 1) * 0.18 // 기본 높이 + 추가 줄당 0.18인치
    }

    let remaining = rows
    while (remaining.length > 0) {
      // 현재 슬라이드에 들어갈 수 있는 행 수 계산
      let budget = CONTENT_BOTTOM - this.curY - 0.1 - ROW_H // header 높이 빼기
      if (budget < ROW_H) {
        this._newSlide()
        budget = CONTENT_BOTTOM - this.curY - 0.1 - ROW_H
      }

      let take = 0
      let usedH = 0
      while (take < remaining.length) {
        const rh = estimateRowH(remaining[take])
        if (usedH + rh > budget) break
        usedH += rh
        take++
      }
      take = Math.max(1, take) // 최소 1행

      const chunk = remaining.slice(0, take)
      remaining = remaining.slice(take)

      const totalH = ROW_H + chunk.reduce((s, r) => s + estimateRowH(r), 0) // header + data

      const data = [
        headers.map(h => ({ text: h, options: { bold: true, fontSize: 8, color: '495057', fill: { color: 'F1F3F5' }, fontFace: PF, valign: 'middle' } })),
        ...chunk.map(row => row.map(v => ({ text: String(v ?? '-'), options: { fontSize: 7.5, color: '1A1A2E', fontFace: PF, valign: 'top' } })))
      ]
      this.slide.addTable(data, { x: 0.3, y: this.curY, w: SL_W - 0.6, colW, border: { type: 'solid', pt: 0.5, color: 'DEE2E6' } })
      this.curY += totalH + 0.12 // 테이블 아래 여백

      if (remaining.length > 0) {
        this._newSlide()
      }
    }
  }

  /** 간격 추가 */
  addGap(h = 0.1) { this.curY += h }
}

export async function exportToPPT(data, container, onProgress) {
  const { allContexts, fullTrees, sortedContexts, allUserStories, crossBCPolicies, sectionNumbers: sn, selectedSections, helpers } = data
  const { bcName, bcTree, getCommandsFromTree, getReadModelsFromTree, allCmdsForCtx, allEvtsForCtx, resolveNodeName } = helpers
  const pptx = new PptxGenJS()
  pptx.defineLayout({ name: 'CUSTOM', width: SL_W, height: SL_H })
  pptx.layout = 'CUSTOM'
  const aggTotal = Object.values(fullTrees).reduce((s, t) => s + (t.aggregates?.length || 0), 0)
  const sb = new SlideBuilder(pptx)

  // 표지
  pptCover(pptx, `BC ${allContexts.length}개 · Aggregate ${aggTotal}개 · US ${allUserStories.length}개`, new Date().toLocaleDateString('ko-KR'))

  // ── 목차 ──
  sb.startPage('목 차')
  const tocRows = []
  if (selectedSections.userStories) tocRows.push([`${sn.userStories}.`, '사용자 스토리 종합'])
  if (selectedSections.boundedContext) { tocRows.push([`${sn.boundedContext}.`, 'Bounded Context 정의']); sortedContexts.forEach((c, i) => tocRows.push([`  ${sn.boundedContext}-${i + 1}.`, bcName(c)])) }
  if (selectedSections.modelOverview) { tocRows.push([`${sn.modelOverview}.`, '이벤트 스토밍 모델 전반 정보']); sortedContexts.forEach((c, i) => tocRows.push([`  ${sn.modelOverview}-${i + 1}.`, bcName(c)])) }
  if (selectedSections.apiSpecification) tocRows.push([`${sn.apiSpecification}.`, 'API 명세'])
  if (selectedSections.aggregateDetail) tocRows.push([`${sn.aggregateDetail}.`, 'Aggregate 상세'])
  sb.addTable(['번호', '제목'], tocRows, [1.5, 7.5])

  // ── 1. US ──
  if (selectedSections.userStories && allUserStories.length) {
    pptSec(pptx, sn.userStories, '사용자 스토리 종합', '시스템에 등록된 사용자 스토리를 Bounded Context 별로 정리합니다.')
    sb.startPage(`${sn.userStories}. 사용자 스토리 종합`)
    sb.addTable(['BC', 'As a', 'I want to', 'So that', '우선순위'],
      allUserStories.map(u => [u.bcName, u.role || '-', (u.action || u.name || '-').slice(0, 50), (u.benefit || '-').slice(0, 50), u.priority || '-']),
      [1.2, 1.0, 3.0, 3.0, 0.9])
  }

  // ── 2. BC ──
  if (selectedSections.boundedContext) {
    pptSec(pptx, sn.boundedContext, 'Bounded Context 정의', '도메인을 구성하는 Bounded Context의 역할, 구성 요소, 상호 관계를 정의합니다.')
    sb.startPage(`${sn.boundedContext}. Bounded Context 요약`)
    sb.addTable(['BC', '도메인', '설명', 'Agg', 'Cmd', 'Evt', 'RM'],
      sortedContexts.map(c => { const t = bcTree(c); return [bcName(c), c.domainType || '-', (c.description || t?.description || '-').slice(0, 50), t?.aggregates?.length || 0, t?.aggregates?.reduce((a, x) => a + (x.commands?.length || 0), 0) || 0, t?.aggregates?.reduce((a, x) => a + (x.events?.length || 0), 0) || 0, t?.readmodels?.length || 0] }),
      [1.5, 1.0, 3.5, 0.6, 0.6, 0.6, 0.6])

    // BC 상세 — 여러 BC를 같은 슬라이드에 합침
    sortedContexts.forEach((ctx, ci) => {
      const t = bcTree(ctx)
      sb.addGap(0.1)
      sb.addSubTitle(`${sn.boundedContext}-${ci + 1}. ${bcName(ctx)} [${ctx.domainType || ''}]`)
      sb.addDesc(ctx.description || t?.description)
      const rows = []
      if (t?.aggregates?.length) rows.push(['Aggregate', t.aggregates.map(a => a.displayName || a.name).join(', ')])
      if (t?.policies?.filter(p => p.name).length) rows.push(['Policy', t.policies.filter(p => p.name).map(p => p.displayName || p.name).join(', ')])
      if (t?.readmodels?.length) rows.push(['Read Model', t.readmodels.map(r => r.displayName || r.name).join(', ')])
      if (t?.uis?.length) rows.push(['UI', t.uis.map(u => u.displayName || u.name).join(', ')])
      if (rows.length) sb.addTable(['구성요소', '목록'], rows, [1.5, 7.5])
    })

    if (crossBCPolicies.length) {
      sb.addGap(0.1)
      sb.addSubTitle(`${sn.boundedContext}-${sortedContexts.length + 1}. 컨텍스트 간 연관 관계`)
      sb.addTable(['발행 BC', 'Event', 'Policy', '수신 BC', 'Command'],
        crossBCPolicies.map(r => [r.fromBC, r.fromEvent, r.policy, r.toBC, r.toCommand]),
        [1.5, 1.8, 2.4, 1.5, 1.8])
    }
  }

  // ── 3. 모델 전반 — 한 BC의 소 주제들을 같은 슬라이드에 합침 ──
  if (selectedSections.modelOverview) {
    pptSec(pptx, sn.modelOverview, '이벤트 스토밍 모델 전반 정보', 'Command, Event, Policy, Read Model 구성 요소를 정리합니다.')
    sortedContexts.forEach((ctx, ci) => {
      const t = bcTree(ctx); if (!t) return; const bcN = bcName(ctx); let sub = 0
      sb.startPage(`${sn.modelOverview}-${ci + 1}. ${bcN}`)

      if (t.aggregates?.length) {
        sub++; sb.addSubTitle(`${sub}. Aggregate`)
        sb.addTable(['이름', 'Root Entity', 'Invariants'],
          t.aggregates.map(a => [a.displayName || a.name, a.rootEntity || '-', (a.invariants || []).join('; ') || '-']),
          [1.6, 1.4, 6.0])
      }

      const cmds = allCmdsForCtx(ctx)
      if (cmds.length) {
        sub++; sb.addSubTitle(`${sub}. Command`)
        sb.addTable(['이름', 'Agg', 'Actor', 'Input Schema', '발생 Event'],
          cmds.map(c => [c.displayName || c.name, c.aggName, c.actor || '-', c.schema.map(s => `${s.name}(${s.type})`).join(', ') || '-', (c.events || []).map(e => e.displayName || e.name || e).join(', ') || '-']),
          [1.6, 1.2, 0.8, 3.2, 2.4])
      }

      const evts = allEvtsForCtx(ctx)
      if (evts.length) {
        sub++; sb.addSubTitle(`${sub}. Event`)
        sb.addTable(['이름', 'Agg', 'Ver', 'Payload'],
          evts.map(e => [e.displayName || e.name, e.aggName, e.version || '-', e.payloadFields.map(f => `${f.name}(${f.type})`).join(', ') || '-']),
          [1.8, 1.2, 0.6, 5.6])
      }

      const pols = (t.policies || []).filter(p => p.name)
      if (pols.length) {
        sub++; sb.addSubTitle(`${sub}. Policy`)
        sb.addTable(['이름', 'Trigger', 'Invoke', '설명'],
          pols.map(p => [p.displayName || p.name, resolveNodeName(p.triggerEventId), resolveNodeName(p.invokeCommandId), (p.description || '-').slice(0, 80)]),
          [1.8, 2.0, 2.0, 3.4])
      }

      if (t.readmodels?.length) {
        sub++; sb.addSubTitle(`${sub}. Read Model`)
        sb.addTable(['이름', '유형', 'Actor', '결과', '설명'],
          t.readmodels.map(r => [r.displayName || r.name, r.provisioningType || '-', r.actor || '-', r.isMultipleResult || '-', (r.description || '-').slice(0, 80)]),
          [1.6, 0.8, 0.8, 1.0, 4.8])
      }
    })
  }

  // ── 4. API ──
  if (selectedSections.apiSpecification) {
    pptSec(pptx, sn.apiSpecification, 'API 명세', 'Command 및 Read Model 상세 정보입니다.')
    sortedContexts.forEach((ctx, ci) => {
      const t = bcTree(ctx); if (!t) return; const bcN = bcName(ctx)
      sb.startPage(`${sn.apiSpecification}-${ci + 1}. ${bcN}`)

      const cmds = getCommandsFromTree(t)
      if (cmds.length) {
        sb.addSubTitle('Command')
        sb.addTable(['Command', 'Agg', 'Actor', 'Schema', 'Event'],
          cmds.map(c => [c.name, c.agg, c.actor || '-', c.schema.map(s => `${s.name}(${s.type})`).join(', ') || '-', c.events.join(', ') || '-']),
          [1.6, 1.2, 0.8, 3.2, 2.4])
      }

      const rms = getReadModelsFromTree(t)
      if (rms.length) {
        sb.addSubTitle('Read Model')
        sb.addTable(['이름', '유형', 'Actor', '결과', '설명'],
          rms.map(r => [r.name, r.pType, r.actor || '-', r.isMultiple || '-', (r.desc || '-').slice(0, 60)]),
          [1.8, 0.8, 0.8, 1.0, 4.8])
      }
    })
  }

  // ── 5. Aggregate 상세 ──
  if (selectedSections.aggregateDetail) {
    pptSec(pptx, sn.aggregateDetail, 'Aggregate 상세', '속성, Enumeration, Value Object 구조를 정리합니다.')
    sortedContexts.forEach((ctx, ci) => {
      const t = bcTree(ctx); if (!t?.aggregates?.length) return; const bcN = bcName(ctx)
      t.aggregates.forEach((agg, ai) => {
        const pfx = `${sn.aggregateDetail}-${ci + 1}-${ai + 1}. ${bcN} / ${agg.displayName || agg.name}`
        sb.startPage(pfx)

        if (agg.properties?.length) {
          sb.addSubTitle('Properties')
          sb.addTable(['필드명', '타입', 'Key', 'FK', '설명'],
            agg.properties.map(p => [p.name, p.type || p.dataType || 'String', p.isKey ? 'Y' : '', p.isForeignKey ? 'Y' : '', (p.description || '-').slice(0, 50)]),
            [1.8, 1.4, 0.5, 0.5, 5.0])
        }

        const metaRows = []
        ;(agg.enumerations || []).forEach(en => { const items = (en.items || en.values || []).map(i => typeof i === 'string' ? i : (i.value || i.name || '')).join(', '); metaRows.push(['Enum', en.displayName || en.name, items]) })
        ;(agg.valueObjects || []).forEach(vo => { const fields = (vo.properties || vo.fields || []).map(f => `${f.name}(${f.type || f.dataType || 'String'})`).join(', '); metaRows.push(['VO', vo.name, fields || '-']) })
        if (metaRows.length) {
          sb.addSubTitle('Enumeration / Value Object')
          sb.addTable(['유형', '이름', '내용'], metaRows, [0.8, 2.0, 6.4])
        }
      })
    })
  }

  await pptx.writeFile({ fileName: `설계산출물-${new Date().toISOString().split('T')[0]}.pptx` })
}
