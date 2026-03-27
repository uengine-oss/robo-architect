import PptxGenJS from 'pptxgenjs'

// ── Design tokens matching preview ──
const C = {
  DARK: '1A1A2E', BLUE: '228BE6', GRAY: '6C757D', LIGHT: '868E96',
  BG_DARK: '0D1117', BG_SEC: 'F8F9FA', BG_HEAD: 'F1F3F5', BORDER: 'DEE2E6', WHITE: 'FFFFFF',
}
const F = 'Malgun Gothic'

// ── Slide builders ──

function coverSlide(pptx, { stats, date }) {
  const s = pptx.addSlide({ bkgd: C.BG_DARK })
  s.addText('Robo Architect', { x: 0, y: 1.0, w: '100%', fontSize: 13, color: '58A6FF', align: 'center', fontFace: F, bold: true })
  s.addText('소프트웨어 아키텍처 설계서', { x: 0, y: 1.8, w: '100%', fontSize: 28, color: C.WHITE, align: 'center', fontFace: F, bold: true })
  s.addText('Event Storming 기반 설계 산출물', { x: 0.5, y: 2.6, w: 9, fontSize: 14, color: 'AAAAAA', align: 'center', fontFace: F })
  if (stats) s.addText(stats, { x: 0, y: 3.5, w: '100%', fontSize: 10, color: '888888', align: 'center', fontFace: F })
  if (date) s.addText(date, { x: 0, y: 3.9, w: '100%', fontSize: 9, color: '666666', align: 'center', fontFace: F })
}

function sectionSlide(pptx, num, title, desc) {
  const s = pptx.addSlide({ bkgd: C.BG_SEC })
  s.addText(String(num), { x: 0, y: 0.8, w: '100%', fontSize: 52, color: C.BLUE, align: 'center', fontFace: F, bold: true })
  s.addText(title, { x: 0, y: 1.8, w: '100%', fontSize: 24, color: C.DARK, align: 'center', fontFace: F, bold: true })
  s.addText(desc, { x: 1.5, y: 2.6, w: 7, fontSize: 11, color: C.GRAY, align: 'center', fontFace: F })
}

function titleBar(slide, title) {
  slide.addText(title, { x: 0.4, y: 0.15, w: 9, fontSize: 15, color: C.DARK, fontFace: F, bold: true })
  slide.addShape('rect', { x: 0.4, y: 0.48, w: 9.2, h: 0.025, fill: { color: C.BLUE } })
}

// ── Chunked table: manually splits rows across slides ──
function addChunkedTable(pptx, title, headers, rows, colW) {
  const MAX_ROWS = 11
  const totalW = colW.reduce((a, b) => a + b, 0)

  for (let i = 0; i < rows.length; i += MAX_ROWS) {
    const chunk = rows.slice(i, i + MAX_ROWS)
    const s = pptx.addSlide()
    titleBar(s, i === 0 ? title : `${title} (계속)`)

    const tblData = [
      headers.map(h => ({ text: h, options: { bold: true, fontSize: 8.5, color: '495057', fill: { color: C.BG_HEAD }, fontFace: F, align: 'left', valign: 'middle' } })),
      ...chunk.map(row => row.map(val => ({
        text: String(val ?? '-'),
        options: { fontSize: 8, color: C.DARK, fontFace: F, valign: 'top' }
      })))
    ]

    s.addTable(tblData, {
      x: 0.3, y: 0.6, w: totalW, colW,
      border: { type: 'solid', pt: 0.5, color: C.BORDER },
      rowH: 0.32,
    })
  }
}

function textSlide(pptx, title, lines) {
  const s = pptx.addSlide()
  titleBar(s, title)
  s.addText(
    lines.map(l => ({ text: l, options: { fontSize: 10, color: C.DARK, fontFace: F, breakType: 'break', lineSpacingMultiple: 1.4 } })),
    { x: 0.5, y: 0.65, w: 9, h: 4.5, valign: 'top', wrap: true }
  )
}

function domainTag(type) {
  if (type?.includes('Core')) return '[Core]'
  if (type?.includes('Supporting')) return '[Supporting]'
  return '[Generic]'
}

// ════════════════════════════════════
//  MAIN EXPORT
// ════════════════════════════════════
export async function exportToPPT({ allContexts, fullTrees, sortedContexts, allUserStories, crossBCPolicies, sectionNumbers, selectedSections, helpers }) {
  const { bcName, bcTree, getCommandsFromTree, getReadModelsFromTree, allCmdsForCtx, allEvtsForCtx, resolveNodeName } = helpers
  const pptx = new PptxGenJS()
  pptx.layout = 'LAYOUT_WIDE'
  pptx.author = 'Robo Architect'

  const sn = sectionNumbers
  const aggTotal = Object.values(fullTrees).reduce((s, tr) => s + (tr.aggregates?.length || 0), 0)

  // ── 메인 표지 ──
  coverSlide(pptx, {
    stats: `BC ${allContexts.length}개 · Aggregate ${aggTotal}개 · US ${allUserStories.length}개`,
    date: new Date().toLocaleDateString('ko-KR'),
  })

  // ── 1. 사용자 스토리 ──
  if (selectedSections.userStories && allUserStories.length) {
    sectionSlide(pptx, sn.userStories, '사용자 스토리 종합', '시스템에 등록된 사용자 스토리를 정리합니다.')
    addChunkedTable(pptx, `${sn.userStories}. 사용자 스토리 종합`,
      ['BC', 'As a', 'I want to', 'So that', '우선순위'],
      allUserStories.map(s => [s.bcName, s.role || '-', (s.action || s.name || '-').slice(0, 50), (s.benefit || '-').slice(0, 50), s.priority || '-']),
      [1.3, 1.0, 3.0, 3.0, 0.9]
    )
  }

  // ── 2. Bounded Context ──
  if (selectedSections.boundedContext) {
    sectionSlide(pptx, sn.boundedContext, 'Bounded Context 정의', '도메인 구성 요소와 상호 관계를 정의합니다.')

    addChunkedTable(pptx, `${sn.boundedContext}. Bounded Context 요약`,
      ['BC', '도메인 유형', '설명', 'Agg', 'Cmd', 'Evt', 'RM'],
      sortedContexts.map(ctx => {
        const tr = bcTree(ctx)
        return [bcName(ctx), ctx.domainType || '-', (ctx.description || tr?.description || '-').slice(0, 60),
          tr?.aggregates?.length || 0, tr?.aggregates?.reduce((a, x) => a + (x.commands?.length || 0), 0) || 0,
          tr?.aggregates?.reduce((a, x) => a + (x.events?.length || 0), 0) || 0, tr?.readmodels?.length || 0]
      }),
      [1.5, 1.1, 3.5, 0.6, 0.6, 0.6, 0.6]
    )

    sortedContexts.forEach((ctx, ci) => {
      const tr = bcTree(ctx)
      const lines = []
      if (ctx.description || tr?.description) lines.push(ctx.description || tr?.description, '')
      if (tr?.aggregates?.length) lines.push(`● Aggregate: ${tr.aggregates.map(a => a.displayName || a.name).join(', ')}`)
      if (tr?.policies?.filter(p => p.name).length) lines.push(`● Policy: ${tr.policies.filter(p => p.name).map(p => p.displayName || p.name).join(', ')}`)
      if (tr?.readmodels?.length) lines.push(`● Read Model: ${tr.readmodels.map(r => r.displayName || r.name).join(', ')}`)
      if (tr?.uis?.length) lines.push(`● UI: ${tr.uis.map(u => u.displayName || u.name).join(', ')}`)
      if (lines.length) textSlide(pptx, `${sn.boundedContext}-${ci + 1}. ${bcName(ctx)} ${domainTag(ctx.domainType)}`, lines)
    })

    if (crossBCPolicies.length) {
      addChunkedTable(pptx, `${sn.boundedContext}-${sortedContexts.length + 1}. 컨텍스트 간 연관 관계`,
        ['발행 BC', 'Event', 'Policy', '수신 BC', 'Command'],
        crossBCPolicies.map(r => [r.fromBC, r.fromEvent, r.policy, r.toBC, r.toCommand]),
        [1.5, 1.8, 2.4, 1.5, 1.8]
      )
    }
  }

  // ── 3. 모델 전반 정보 ──
  if (selectedSections.modelOverview) {
    sectionSlide(pptx, sn.modelOverview, '이벤트 스토밍 모델 전반 정보', 'Command, Event, Policy, Read Model 구성 요소입니다.')

    sortedContexts.forEach((ctx, ci) => {
      const tr = bcTree(ctx); if (!tr) return
      const bcN = bcName(ctx)
      let sub = 0

      if (tr.aggregates?.length) {
        sub++
        const lines = []
        tr.aggregates.forEach(a => {
          lines.push(`● ${a.displayName || a.name} (Root: ${a.rootEntity || '-'})`)
          ;(a.invariants || []).forEach(inv => lines.push(`  - ${inv}`))
          lines.push('')
        })
        textSlide(pptx, `${sn.modelOverview}-${ci + 1}-${sub}. ${bcN} - Aggregate`, lines)
      }

      const cmds = allCmdsForCtx(ctx)
      if (cmds.length) {
        sub++
        addChunkedTable(pptx, `${sn.modelOverview}-${ci + 1}-${sub}. ${bcN} - Command`,
          ['이름', 'Aggregate', 'Actor', 'Input Schema', '발생 Event'],
          cmds.map(c => [c.displayName || c.name, c.aggName, c.actor || '-', c.schema.map(s => `${s.name}(${s.type})`).join(', ') || '-', (c.events || []).map(e => e.displayName || e.name || e).join(', ') || '-']),
          [1.6, 1.2, 0.8, 3.2, 2.4]
        )
      }

      const evts = allEvtsForCtx(ctx)
      if (evts.length) {
        sub++
        addChunkedTable(pptx, `${sn.modelOverview}-${ci + 1}-${sub}. ${bcN} - Event`,
          ['이름', 'Aggregate', 'Ver', 'Payload'],
          evts.map(e => [e.displayName || e.name, e.aggName, e.version || '-', e.payloadFields.map(f => `${f.name}(${f.type})`).join(', ') || '-']),
          [1.8, 1.2, 0.6, 5.6]
        )
      }

      const pols = (tr.policies || []).filter(p => p.name)
      if (pols.length) {
        sub++
        addChunkedTable(pptx, `${sn.modelOverview}-${ci + 1}-${sub}. ${bcN} - Policy`,
          ['이름', 'Trigger Event', 'Invoke Command', '설명'],
          pols.map(p => [p.displayName || p.name, resolveNodeName(p.triggerEventId), resolveNodeName(p.invokeCommandId), (p.description || '-').slice(0, 80)]),
          [1.8, 2.0, 2.0, 3.4]
        )
      }

      if (tr.readmodels?.length) {
        sub++
        addChunkedTable(pptx, `${sn.modelOverview}-${ci + 1}-${sub}. ${bcN} - Read Model`,
          ['이름', '유형', 'Actor', '결과', '설명'],
          tr.readmodels.map(r => [r.displayName || r.name, r.provisioningType || '-', r.actor || '-', r.isMultipleResult || '-', (r.description || '-').slice(0, 60)]),
          [1.8, 0.8, 0.8, 1.0, 4.8]
        )
      }
    })
  }

  // ── 4. API 명세 ──
  if (selectedSections.apiSpecification) {
    sectionSlide(pptx, sn.apiSpecification, 'API 명세', 'Command 및 Read Model 상세 정보입니다.')

    sortedContexts.forEach((ctx, ci) => {
      const tr = bcTree(ctx); if (!tr) return
      const bcN = bcName(ctx)

      const cmds = getCommandsFromTree(tr)
      if (cmds.length) {
        addChunkedTable(pptx, `${sn.apiSpecification}-${ci + 1}. ${bcN} - Command`,
          ['Command', 'Aggregate', 'Actor', 'Input Schema', '발생 Event'],
          cmds.map(c => [c.name, c.agg, c.actor || '-', c.schema.map(s => `${s.name}(${s.type})`).join(', ') || '-', c.events.join(', ') || '-']),
          [1.6, 1.2, 0.8, 3.2, 2.4]
        )
      }

      const rms = getReadModelsFromTree(tr)
      if (rms.length) {
        addChunkedTable(pptx, `${sn.apiSpecification}-${ci + 1}. ${bcN} - Read Model`,
          ['이름', '유형', 'Actor', '결과', '설명'],
          rms.map(r => [r.name, r.pType, r.actor || '-', r.isMultiple || '-', (r.desc || '-').slice(0, 60)]),
          [1.8, 0.8, 0.8, 1.0, 4.8]
        )
      }
    })
  }

  // ── 5. Aggregate 상세 ──
  if (selectedSections.aggregateDetail) {
    sectionSlide(pptx, sn.aggregateDetail, 'Aggregate 상세', '속성, Enumeration, Value Object 구조를 정리합니다.')

    sortedContexts.forEach((ctx, ci) => {
      const tr = bcTree(ctx); if (!tr?.aggregates?.length) return
      const bcN = bcName(ctx)

      tr.aggregates.forEach((agg, ai) => {
        const prefix = `${sn.aggregateDetail}-${ci + 1}-${ai + 1}. ${bcN} / ${agg.displayName || agg.name}`

        if (agg.properties?.length) {
          addChunkedTable(pptx, `${prefix} - Properties`,
            ['필드명', '타입', 'Key', 'FK', '설명'],
            agg.properties.map(p => [p.name, p.type || p.dataType || 'String', p.isKey ? 'Y' : '', p.isForeignKey ? 'Y' : '', (p.description || '-').slice(0, 50)]),
            [1.8, 1.4, 0.5, 0.5, 5.0]
          )
        }

        const lines = []
        if (agg.rootEntity) lines.push(`Root Entity: ${agg.rootEntity}`, '')
        if (agg.enumerations?.length) {
          lines.push('■ Enumeration')
          agg.enumerations.forEach(en => {
            const items = (en.items || en.values || []).map(i => typeof i === 'string' ? i : (i.value || i.name || '')).join(', ')
            lines.push(`  ${en.displayName || en.name}: [ ${items} ]`)
          })
          lines.push('')
        }
        if (agg.valueObjects?.length) {
          lines.push('■ Value Object')
          agg.valueObjects.forEach(vo => {
            const fields = (vo.properties || vo.fields || []).map(f => `${f.name}(${f.type || f.dataType || 'String'})`).join(', ')
            lines.push(`  ${vo.name}: ${fields || '-'}`)
          })
        }
        if (lines.length) textSlide(pptx, prefix, lines)
      })
    })
  }

  const ts = new Date().toISOString().split('T')[0]
  await pptx.writeFile({ fileName: `설계산출물-${ts}.pptx` })
}
