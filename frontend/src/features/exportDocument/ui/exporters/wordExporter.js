import {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, PageBreak, WidthType, BorderStyle,
  ShadingType, TableLayoutType, convertInchesToTwip,
} from 'docx'
import { saveAs } from 'file-saver'

// ── Design tokens ──
const FONT = 'Malgun Gothic'
const COLOR = { dark: '1a1a2e', blue: '228be6', gray: '6c757d', lightGray: '868e96', headerBg: 'f1f3f5', border: 'dee2e6', white: 'ffffff', coreBg: 'dbe4ff', coreFg: '364fc7', suppBg: 'fff3bf', suppFg: 'e67700', genBg: 'e9ecef', genFg: '495057', eventBg: 'fff3bf', eventFg: 'e67700', cmdBg: 'dbe4ff', cmdFg: '364fc7' }

// ── Primitives ──
function t(str, opts = {}) {
  return new TextRun({ text: str || '', font: FONT, size: opts.size || 20, bold: opts.bold, italic: opts.italic, color: opts.color || COLOR.dark, break: opts.break })
}

function p(children, opts = {}) {
  if (typeof children === 'string') children = [t(children, opts)]
  return new Paragraph({ children, spacing: { after: opts.after ?? 100, before: opts.before ?? 0 }, alignment: opts.align, indent: opts.indent, heading: opts.heading, ...opts.extra })
}

function pageBreak() { return p([new PageBreak()], { after: 0 }) }

function blankLines(n) { return Array.from({ length: n }, () => p('', { after: 200 })) }

// ── Table ──
const BORDER = { style: BorderStyle.SINGLE, size: 1, color: COLOR.border }
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER }

function cell(text, opts = {}) {
  return new TableCell({
    children: [p(text, { size: opts.size || 18, bold: opts.bold, color: opts.color, after: 40 })],
    shading: opts.bg ? { type: ShadingType.CLEAR, fill: opts.bg } : undefined,
    width: opts.width ? { size: opts.width, type: WidthType.DXA } : undefined,
    borders: BORDERS,
    verticalAlign: 'top',
  })
}

function table(headers, rows, colWidths) {
  const totalW = colWidths ? colWidths.reduce((a, b) => a + b, 0) : 9000
  const ws = colWidths || headers.map(() => Math.floor(totalW / headers.length))

  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => cell(h, { bold: true, bg: COLOR.headerBg, size: 17, width: ws[i] })),
  })

  const dataRows = rows.map(row => new TableRow({
    children: row.map((c, i) => cell(String(c ?? '-'), { width: ws[i], size: 17 })),
  }))

  return new Table({
    rows: [headerRow, ...dataRows],
    width: { size: totalW, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
  })
}

// ── Covers ──
function mainCover(stats, date) {
  return [
    ...blankLines(6),
    p('Robo Architect', { align: AlignmentType.CENTER, size: 22, bold: true, color: COLOR.blue, after: 300 }),
    p('소프트웨어 아키텍처 설계서', { align: AlignmentType.CENTER, size: 40, bold: true, after: 100 }),
    p('Event Storming 기반 설계 산출물', { align: AlignmentType.CENTER, size: 22, color: COLOR.gray, after: 400 }),
    p(stats, { align: AlignmentType.CENTER, size: 18, color: COLOR.lightGray, after: 80 }),
    p(date, { align: AlignmentType.CENTER, size: 18, color: COLOR.lightGray }),
    pageBreak(),
  ]
}

function sectionCover(num, title, desc) {
  return [
    ...blankLines(5),
    p(String(num), { align: AlignmentType.CENTER, size: 72, bold: true, color: COLOR.blue, after: 200 }),
    p(title, { align: AlignmentType.CENTER, size: 32, bold: true, after: 120 }),
    p(desc, { align: AlignmentType.CENTER, size: 20, color: COLOR.gray }),
    pageBreak(),
  ]
}

// ── Section heading with blue underline ──
function sectionTitle(text, level = HeadingLevel.HEADING_2) {
  return p(text, { heading: level, size: level === HeadingLevel.HEADING_2 ? 26 : 22, bold: true, after: 60, extra: { border: { bottom: { style: BorderStyle.SINGLE, size: 3, color: COLOR.blue, space: 4 } } } })
}

function subTitle(text) {
  return p(text, { size: 22, bold: true, after: 60 })
}

function desc(text) {
  return p(text, { size: 18, color: COLOR.gray, after: 80 })
}

function domainTag(type) {
  if (type?.includes('Core')) return `[Core Domain]`
  if (type?.includes('Supporting')) return `[Supporting Domain]`
  return `[Generic Domain]`
}

// ════════════════════════════════════════
//  MAIN EXPORT
// ════════════════════════════════════════
export async function exportToWord({ allContexts, fullTrees, sortedContexts, allUserStories, crossBCPolicies, sectionNumbers, selectedSections, helpers, valueStreamProcesses = [], glossaryTerms = [], traceGroups = [], traceInferred = [], traceUnmapped = [], traceSummary = null }) {
  const { bcName, bcTree, getCommandsFromTree, getReadModelsFromTree, allCmdsForCtx, allEvtsForCtx, resolveNodeName, traceTypeLabel, storySources, storySourceTask } = helpers
  const children = []
  const sn = sectionNumbers // shorthand

  const aggTotal = Object.values(fullTrees).reduce((s, tr) => s + (tr.aggregates?.length || 0), 0)

  // ══ 메인 표지 ══
  children.push(...mainCover(
    `Bounded Context ${allContexts.length}개 · Aggregate ${aggTotal}개 · User Story ${allUserStories.length}개`,
    new Date().toLocaleDateString('ko-KR')
  ))

  // ══ 목차 ══
  children.push(sectionTitle('목 차'))
  const toc = []
  if (selectedSections.userStories) toc.push(`${sn.userStories}. 사용자 스토리 종합`)
  if (selectedSections.valueStream && valueStreamProcesses.length) {
    toc.push(`${sn.valueStream}. 밸류 스트림 분석`)
    valueStreamProcesses.forEach((proc, i) => toc.push(`  ${sn.valueStream}-${i + 1}. ${proc.name}`))
  }
  if (selectedSections.boundedContext) {
    toc.push(`${sn.boundedContext}. Bounded Context 정의`)
    sortedContexts.forEach((ctx, i) => toc.push(`  ${sn.boundedContext}-${i + 1}. ${bcName(ctx)}`))
    if (crossBCPolicies.length) toc.push(`  ${sn.boundedContext}-${sortedContexts.length + 1}. 컨텍스트 간 연관 관계`)
  }
  if (selectedSections.modelOverview) toc.push(`${sn.modelOverview}. 이벤트 스토밍 모델 전반 정보`)
  if (selectedSections.apiSpecification) toc.push(`${sn.apiSpecification}. API 명세`)
  if (selectedSections.aggregateDetail) toc.push(`${sn.aggregateDetail}. Aggregate 상세`)
  if (selectedSections.traceabilityMatrix && traceSummary) toc.push(`${sn.traceabilityMatrix}. 추적성 매트릭스`)
  toc.forEach(item => children.push(p(item, { size: 20, bold: !item.startsWith(' '), after: 40, indent: item.startsWith(' ') ? { left: 400 } : undefined })))
  children.push(pageBreak())

  // ══ 1. 사용자 스토리 ══
  if (selectedSections.userStories) {
    children.push(...sectionCover(sn.userStories, '사용자 스토리 종합', '시스템에 등록된 사용자 스토리를 정리합니다.'))
    children.push(sectionTitle(`${sn.userStories}. 사용자 스토리 종합`))

    if (allUserStories.length) {
      children.push(table(
        ['Bounded Context', 'As a', 'I want to', 'So that', '우선순위', '상태'],
        allUserStories.map(s => [s.bcName, s.role || '-', s.action || s.name || '-', s.benefit || '-', s.priority || '-', s.status || '-']),
        [1400, 1000, 2500, 2500, 800, 800]
      ))
    } else {
      children.push(desc('등록된 사용자 스토리가 없습니다.'))
    }

    // 원문 근거 — 정규화된 스토리가 문서 어디에서 나왔는지 제시한다.
    const sourceRows = []
    for (const st of allUserStories) {
      const sources = storySources ? storySources(st.id) : []
      const task = storySourceTask ? storySourceTask(st.id) : null
      sources.forEach((src, i) => sourceRows.push([
        i === 0 ? st.id : '',
        i === 0 ? (task?.name || '-') : '',
        [src.page ? `p.${src.page}` : '', src.heading || ''].filter(Boolean).join(' / ') || '-',
        src.text || '-',
      ]))
    }
    if (sourceRows.length) {
      children.push(pageBreak())
      children.push(sectionTitle(`${sn.userStories}-1. 사용자 스토리 원문 근거`))
      children.push(desc('각 사용자 스토리가 업로드 문서의 어느 부분에서 도출됐는지 보여줍니다.'))
      children.push(table(['US ID', '업무 Task', '문서 위치', '원문 근거'], sourceRows, [900, 1900, 1500, 4700]))
    }
    children.push(pageBreak())
  }

  // ══ 밸류 스트림 분석 ══
  if (selectedSections.valueStream && valueStreamProcesses.length) {
    children.push(...sectionCover(sn.valueStream, '밸류 스트림 분석', '업로드 문서에서 도출한 업무 프로세스를 Actor 흐름으로 정리하고, 각 단계가 어떤 사용자 스토리로 승격됐는지 연결합니다.'))

    valueStreamProcesses.forEach((proc, pi) => {
      children.push(sectionTitle(`${sn.valueStream}-${pi + 1}. ${proc.name}`))
      if (proc.description) children.push(desc(proc.description))
      if (proc.actors?.length) children.push(desc(`참여 Actor · ${proc.actors.join(', ')}`))

      const path = proc.linearPaths?.[0] || []
      if (path.length) {
        children.push(p(
          path.map(step => `${step.displayName}${step.actor ? ` (${step.actor})` : ''}`).join(' → '),
          { size: 18, color: COLOR.gray, after: 120 }
        ))
        children.push(table(
          ['순서', 'Task', 'Actor', '설명', '승격된 User Story'],
          path.map((step, si) => [
            si + 1,
            step.displayName || '-',
            step.actor || '-',
            [step.description, step.sourceSection].filter(Boolean).join('\n') || '-',
            step.promotedTo?.length ? step.promotedTo.map(us => us.id).join(', ') : '미승격',
          ]),
          [700, 2100, 1400, 3400, 1400]
        ))
      }
      children.push(pageBreak())
    })

    if (glossaryTerms.length) {
      children.push(sectionTitle(`${sn.valueStream}-${valueStreamProcesses.length + 1}. 도메인 용어집`))
      children.push(table(
        ['용어', '설명'],
        glossaryTerms.map(g => [g.term || g.name || '-', g.definition || g.description || '-']),
        [2200, 6800]
      ))
      children.push(pageBreak())
    }
  }

  // ══ 2. Bounded Context ══
  if (selectedSections.boundedContext) {
    children.push(...sectionCover(sn.boundedContext, 'Bounded Context 정의', '도메인 구성 요소와 상호 관계를 정의합니다.'))

    // 요약
    children.push(sectionTitle(`${sn.boundedContext}. Bounded Context 요약`))
    children.push(table(
      ['Bounded Context', '도메인 유형', '설명', 'Agg', 'Cmd', 'Evt', 'RM', 'US'],
      sortedContexts.map(ctx => {
        const tr = bcTree(ctx)
        return [bcName(ctx), ctx.domainType || '-', (ctx.description || tr?.description || '-').slice(0, 80),
          tr?.aggregates?.length || 0, tr?.aggregates?.reduce((s, a) => s + (a.commands?.length || 0), 0) || 0,
          tr?.aggregates?.reduce((s, a) => s + (a.events?.length || 0), 0) || 0, tr?.readmodels?.length || 0, tr?.userStories?.length || 0]
      }),
      [1400, 1200, 2800, 600, 600, 600, 600, 600]
    ))
    children.push(p(''), pageBreak())

    // BC 상세
    sortedContexts.forEach((ctx, ci) => {
      const tr = bcTree(ctx)
      children.push(subTitle(`${sn.boundedContext}-${ci + 1}. ${bcName(ctx)} ${domainTag(ctx.domainType)}`))
      if (ctx.description || tr?.description) children.push(desc(ctx.description || tr?.description))
      if (tr?.aggregates?.length) children.push(p(`Aggregate: ${tr.aggregates.map(a => a.displayName || a.name).join(', ')}`, { size: 18, after: 40 }))
      if (tr?.policies?.filter(pol => pol.name).length) children.push(p(`Policy: ${tr.policies.filter(pol => pol.name).map(pol => pol.displayName || pol.name).join(', ')}`, { size: 18, after: 40 }))
      if (tr?.readmodels?.length) children.push(p(`Read Model: ${tr.readmodels.map(r => r.displayName || r.name).join(', ')}`, { size: 18, after: 40 }))
      if (tr?.uis?.length) children.push(p(`UI: ${tr.uis.map(u => u.displayName || u.name).join(', ')}`, { size: 18, after: 40 }))
      children.push(p(''))
    })

    // Cross-BC
    if (crossBCPolicies.length) {
      children.push(pageBreak())
      children.push(subTitle(`${sn.boundedContext}-${sortedContexts.length + 1}. 컨텍스트 간 연관 관계`))
      children.push(desc('서로 다른 Bounded Context 간 이벤트-Policy-커맨드 연결입니다.'))
      children.push(table(
        ['발행 BC', 'Event', 'Policy', '수신 BC', 'Command'],
        crossBCPolicies.map(r => [r.fromBC, r.fromEvent, r.policy, r.toBC, r.toCommand]),
        [1600, 1800, 2200, 1600, 1800]
      ))
    }
    children.push(pageBreak())
  }

  // ══ 3. 모델 전반 정보 ══
  if (selectedSections.modelOverview) {
    children.push(...sectionCover(sn.modelOverview, '이벤트 스토밍 모델 전반 정보', 'Command, Event, Policy, Read Model 구성 요소를 정리합니다.'))

    sortedContexts.forEach((ctx, ci) => {
      const tr = bcTree(ctx); if (!tr) return
      const bcN = bcName(ctx)
      let subIdx = 0

      // Aggregate
      if (tr.aggregates?.length) {
        subIdx++
        children.push(subTitle(`${sn.modelOverview}-${ci + 1}-${subIdx}. ${bcN} - Aggregate`))
        tr.aggregates.forEach(a => {
          children.push(p(`${a.displayName || a.name} (Root: ${a.rootEntity || '-'})`, { size: 20, bold: true, after: 40 }))
          if (a.invariants?.length) {
            children.push(p('비즈니스 규칙 (Invariants):', { size: 18, bold: true, after: 20 }))
            a.invariants.forEach(inv => children.push(p(`• ${inv}`, { size: 18, after: 20, indent: { left: 300 } })))
          }
          children.push(p(''))
        })
      }

      // Command
      const cmds = allCmdsForCtx(ctx)
      if (cmds.length) {
        subIdx++
        children.push(subTitle(`${sn.modelOverview}-${ci + 1}-${subIdx}. ${bcN} - Command`))
        children.push(table(
          ['이름', 'Aggregate', 'Actor', 'Input Schema', '발생 Event'],
          cmds.map(c => [c.displayName || c.name, c.aggName, c.actor || '-', c.schema.map(s => `${s.name}(${s.type})`).join(', ') || '-', (c.events || []).map(e => e.displayName || e.name || e).join(', ') || '-']),
          [1600, 1200, 800, 2800, 2000]
        ))
      }

      // Event
      const evts = allEvtsForCtx(ctx)
      if (evts.length) {
        subIdx++
        children.push(subTitle(`${sn.modelOverview}-${ci + 1}-${subIdx}. ${bcN} - Event`))
        children.push(table(
          ['이름', 'Aggregate', 'Version', 'Payload'],
          evts.map(e => [e.displayName || e.name, e.aggName, e.version || '-', e.payloadFields.map(f => `${f.name}(${f.type})`).join(', ') || '-']),
          [1800, 1200, 800, 5200]
        ))
      }

      // Policy
      const pols = (tr.policies || []).filter(pol => pol.name)
      if (pols.length) {
        subIdx++
        children.push(subTitle(`${sn.modelOverview}-${ci + 1}-${subIdx}. ${bcN} - Policy`))
        children.push(table(
          ['이름', 'Trigger Event', 'Invoke Command', '설명'],
          pols.map(pol => [pol.displayName || pol.name, resolveNodeName(pol.triggerEventId), resolveNodeName(pol.invokeCommandId), (pol.description || '-').slice(0, 100)]),
          [1800, 2000, 2000, 3200]
        ))
      }

      // ReadModel
      if (tr.readmodels?.length) {
        subIdx++
        children.push(subTitle(`${sn.modelOverview}-${ci + 1}-${subIdx}. ${bcN} - Read Model`))
        children.push(table(
          ['이름', '유형', 'Actor', '결과', '설명'],
          tr.readmodels.map(r => [r.displayName || r.name, r.provisioningType || '-', r.actor || '-', r.isMultipleResult || '-', (r.description || '-').slice(0, 80)]),
          [1600, 800, 800, 1000, 4800]
        ))
      }

      children.push(pageBreak())
    })
  }

  // ══ 4. API 명세 ══
  if (selectedSections.apiSpecification) {
    children.push(...sectionCover(sn.apiSpecification, 'API 명세', 'Command 및 Read Model 상세 정보입니다.'))

    sortedContexts.forEach((ctx, ci) => {
      const tr = bcTree(ctx); if (!tr) return
      const bcN = bcName(ctx)

      const cmds = getCommandsFromTree(tr)
      if (cmds.length) {
        children.push(subTitle(`${sn.apiSpecification}-${ci + 1}. ${bcN} - Command`))
        children.push(table(
          ['Command', 'Aggregate', 'Actor', 'Input Schema', '발생 Event'],
          cmds.map(c => [c.name, c.agg, c.actor || '-', c.schema.map(s => `${s.name}(${s.type})`).join(', ') || '-', c.events.join(', ') || '-']),
          [1600, 1200, 800, 2800, 2000]
        ))
      }

      const rms = getReadModelsFromTree(tr)
      rms.forEach((rm, ri) => {
        children.push(subTitle(`${sn.apiSpecification}-${ci + 1}. ${bcN} - Read Model: ${rm.name} [${rm.pType}]`))
        if (rm.desc) children.push(desc(rm.desc))
        if (rm.props.length) {
          children.push(p('속성', { size: 18, bold: true, after: 20 }))
          children.push(table(['이름', '타입', 'Key'], rm.props.map(pr => [pr.name, pr.type || pr.dataType || 'String', pr.isKey ? 'Y' : '']), [3000, 3000, 1000]))
        }
        if (rm.ops.length) {
          children.push(p('CQRS Operations', { size: 18, bold: true, after: 20 }))
          children.push(table(['Operation', 'Trigger Event'], rm.ops.map(o => [o.operationType || o.operation_type || '-', o.triggerEventName || '-']), [3000, 4000]))
        }
        children.push(p(''))
      })
      children.push(pageBreak())
    })
  }

  // ══ 5. Aggregate 상세 ══
  if (selectedSections.aggregateDetail) {
    children.push(...sectionCover(sn.aggregateDetail, 'Aggregate 상세', '속성, Enumeration, Value Object 구조를 정리합니다.'))

    sortedContexts.forEach((ctx, ci) => {
      const tr = bcTree(ctx); if (!tr?.aggregates?.length) return
      const bcN = bcName(ctx)

      tr.aggregates.forEach((agg, ai) => {
        children.push(subTitle(`${sn.aggregateDetail}-${ci + 1}-${ai + 1}. ${bcN} / ${agg.displayName || agg.name}`))
        if (agg.rootEntity) children.push(p(`Root Entity: ${agg.rootEntity}`, { size: 18, bold: true, after: 60 }))

        // Properties
        if (agg.properties?.length) {
          children.push(p('속성 (Properties)', { size: 20, bold: true, after: 40 }))
          children.push(table(
            ['필드명', '타입', 'Key', 'FK', '설명'],
            agg.properties.map(pr => [pr.name, pr.type || pr.dataType || 'String', pr.isKey ? 'Y' : '', pr.isForeignKey ? 'Y' : '', pr.description || '-']),
            [1800, 1400, 600, 600, 4600]
          ))
        }

        // Enumerations
        if (agg.enumerations?.length) {
          children.push(p('Enumeration', { size: 20, bold: true, after: 40 }))
          agg.enumerations.forEach(en => {
            const items = (en.items || en.values || []).map(i => typeof i === 'string' ? i : (i.value || i.name || '')).join(', ')
            children.push(p(`${en.displayName || en.name}: [ ${items} ]`, { size: 18, after: 40 }))
          })
        }

        // Value Objects
        if (agg.valueObjects?.length) {
          children.push(p('Value Object', { size: 20, bold: true, after: 40 }))
          agg.valueObjects.forEach(vo => {
            children.push(p(vo.name, { size: 18, bold: true, after: 20 }))
            const fields = vo.properties || vo.fields || []
            if (fields.length) {
              children.push(table(['필드명', '타입'], fields.map(f => [f.name, f.type || f.dataType || 'String']), [4000, 4000]))
            }
          })
        }
        children.push(pageBreak())
      })
    })
  }

  // ══ 추적성 매트릭스 ══
  if (selectedSections.traceabilityMatrix && traceSummary) {
    children.push(...sectionCover(sn.traceabilityMatrix, '추적성 매트릭스', '사용자 스토리별로 매핑된 이벤트 스토밍 요소를 보여줍니다.'))

    children.push(sectionTitle(`${sn.traceabilityMatrix}. 추적성 요약`))
    children.push(table(
      ['전체 요소', '직접 매핑', '추론 매핑', '미매핑', '매핑된 US', '직접 매핑률'],
      [[
        traceSummary.elements, traceSummary.directElements, traceSummary.inferredElements,
        traceSummary.unmappedElements, traceSummary.mappedUserStories,
        `${(traceSummary.directRatio * 100).toFixed(1)}%`,
      ]],
      [1500, 1500, 1500, 1500, 1500, 1500]
    ))
    children.push(pageBreak())

    // US 별 그룹 — 좁은 3 컬럼. 12 컬럼 매트릭스는 문서 폭에서 잘린다.
    traceGroups.forEach(g => {
      children.push(sectionTitle(`${g.us.id}`))
      children.push(desc(g.us.name))
      children.push(table(
        ['유형', '이름', 'ID'],
        g.rows.map(r => [
          traceTypeLabel ? traceTypeLabel(r.type) : r.type,
          [r.name || '-', r.technical && r.technical !== r.name ? `(${r.technical})` : '', r.parent ? `↳ ${r.parent}` : ''].filter(Boolean).join('\n'),
          r.id || '-',
        ]),
        [1300, 5000, 2700]
      ))
    })

    if (traceInferred.length) {
      children.push(pageBreak())
      children.push(sectionTitle(`추론 매핑 (${traceInferred.length})`))
      children.push(desc('직접 근거 없이 상위 Aggregate 의 매핑을 상속한 요소입니다.'))
      children.push(table(
        ['유형', '이름', '추론된 User Story'],
        traceInferred.map(r => [
          traceTypeLabel ? traceTypeLabel(r.type) : r.type,
          [r.name || '-', r.parent ? `↳ ${r.parent}` : ''].filter(Boolean).join('\n'),
          r.inferredUs || '-',
        ]),
        [1300, 5000, 2700]
      ))
    }

    if (traceUnmapped.length) {
      children.push(pageBreak())
      children.push(sectionTitle(`미매핑 요소 (${traceUnmapped.length})`))
      children.push(desc('어느 사용자 스토리와도 연결되지 않은 요소입니다.'))
      children.push(table(
        ['유형', '이름', 'ID'],
        traceUnmapped.map(r => [
          traceTypeLabel ? traceTypeLabel(r.type) : r.type,
          [r.name || '-', r.parent ? `↳ ${r.parent}` : ''].filter(Boolean).join('\n'),
          r.id || '-',
        ]),
        [1300, 5000, 2700]
      ))
    }
  }

  // ── Generate ──
  const doc = new Document({
    sections: [{ children }],
    styles: {
      default: {
        document: { run: { font: FONT, size: 20 } },
        heading2: { run: { font: FONT, size: 26, bold: true, color: COLOR.dark } },
        heading3: { run: { font: FONT, size: 22, bold: true, color: COLOR.dark } },
      },
    },
  })

  const blob = await Packer.toBlob(doc)
  const ts = new Date().toISOString().split('T')[0]
  saveAs(blob, `설계산출물-${ts}.docx`)
}
