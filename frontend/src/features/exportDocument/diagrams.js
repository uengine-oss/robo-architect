/**
 * 산출물 문서의 머메이드 도식 정의를 만든다.
 *
 * 화면과 떼어 둔 이유는 하나다 — **관계가 없을 때의 동작**을 검사할 수 있어야
 * 하기 때문이다. 종전 구현은 컨텍스트 간 관계가 하나도 없으면 정의를 빈 문자열로
 * 돌려보내 BC 가 몇 개든 도식이 통째로 빠졌는데, 관계가 있는 데이터로 화면을
 * 열어 보면 멀쩡해 보인다. 정의를 만드는 부분만 떼어 내면 그 조건을 직접 넣어
 * 확인할 수 있다. → `scripts/verify-export-diagrams.mjs`
 */

export const MMD_DOMAIN_CLASSDEF =
  '  classDef core fill:#dbe4ff,stroke:#4c6ef5,stroke-width:2px,color:#1a1a2e\n' +
  '  classDef supporting fill:#fff3bf,stroke:#f08c00,stroke-width:2px,color:#1a1a2e\n' +
  '  classDef generic fill:#f1f3f5,stroke:#adb5bd,stroke-width:2px,color:#1a1a2e\n'

export function domainClass(t) {
  const d = t || ''
  return d.includes('Core') ? 'core' : d.includes('Supporting') ? 'supporting' : 'generic'
}

/** 라벨의 따옴표·줄바꿈이 정의를 깨지 않게 한다. */
export function mmdLabel(s) {
  return String(s == null ? '' : s).replace(/"/g, "'").replace(/[\r\n]+/g, ' ')
}

/**
 * BC 분해 결과 — 기준 템플릿(local-msaez) 3-2 에 해당한다.
 *
 * @param bcs        {name, domainType, aggregateCount} 목록
 * @param relations  {fromBC, toBC} 목록. 비어 있어도 BC 노드는 그린다.
 */
export function buildBcOverviewDef(bcs, relations = []) {
  const list = bcs || []
  if (!list.length) return ''
  const idMap = {}
  list.forEach((bc, i) => { idMap[bc.name] = 'BC' + i })
  let def = 'graph TD\n' + MMD_DOMAIN_CLASSDEF
  list.forEach((bc, i) => {
    const id = 'BC' + i
    def += `  ${id}["${mmdLabel(bc.name)}<br/><small>${mmdLabel(bc.domainType || '')} · Aggregate ${bc.aggregateCount || 0}</small>"]\n`
    def += `  class ${id} ${domainClass(bc.domainType)}\n`
  })
  const seen = new Set()
  ;(relations || []).forEach(rel => {
    const f = idMap[rel.fromBC], t = idMap[rel.toBC]
    if (!f || !t || f === t) return
    const key = `${f}-->${t}`
    if (seen.has(key)) return
    seen.add(key)
    def += `  ${f} --> ${t}\n`
  })
  return def
}

/** 컨텍스트 간 연관 관계 — Policy 이름을 간선에 붙인 상세 도식. 관계가 있어야 뜻이 있다. */
export function buildContextMapDef(bcs, relations = []) {
  const list = bcs || []
  if (!list.length || !(relations || []).length) return ''
  const idMap = {}
  list.forEach((bc, i) => { idMap[bc.name] = 'BC' + i })
  let def = 'graph LR\n' + MMD_DOMAIN_CLASSDEF
  list.forEach((bc, i) => {
    const id = 'BC' + i
    def += `  ${id}["${mmdLabel(bc.name)}<br/><small>${mmdLabel(bc.domainType || '')}</small>"]\n`
    def += `  class ${id} ${domainClass(bc.domainType)}\n`
  })
  const edges = new Map()
  relations.forEach(rel => {
    const f = idMap[rel.fromBC], t = idMap[rel.toBC]
    if (!f || !t) return
    const key = `${f}-->${t}`
    edges.has(key) ? edges.get(key).push(rel.policy) : edges.set(key, [rel.policy])
  })
  edges.forEach((labels, key) => {
    const [f, t] = key.split('-->')
    def += `  ${f} -->|"${mmdLabel(labels.join('<br/>'))}"| ${t}\n`
  })
  return def
}

/**
 * BC 하나의 Aggregate 구조도 — 기준 템플릿 4-1 에 해당한다.
 *
 * Aggregate 마다 묶음을 만들고 Enumeration 과 Value Object 를 매단다. Value Object 가
 * 다른 Aggregate 를 가리키면(`referencedAggregateName`) 그 참조를 Aggregate 사이의
 * 점선으로 잇는다 — 기준 구현에 없는 정보인데 우리 모델이 갖고 있어, 경계를 넘는
 * 참조가 그림에서 바로 보인다.
 */
export function buildAggregateModelDef(aggregates) {
  const aggs = aggregates || []
  if (!aggs.length) return ''
  let def = 'graph TD\n'
  def += '  classDef agg fill:#dbe4ff,stroke:#4c6ef5,stroke-width:2px,color:#1a1a2e\n'
  def += '  classDef enum fill:#fff3bf,stroke:#f08c00,color:#1a1a2e\n'
  def += '  classDef vo fill:#e6fcf5,stroke:#0ca678,color:#1a1a2e\n'
  // class 지정은 묶음 밖에 모은다 — 안에 두면 묶음의 구성원으로 잡힌다.
  const classes = []
  const byName = {}
  aggs.forEach((a, i) => { byName[a.name] = 'A' + i; byName[a.displayName || a.name] = 'A' + i })

  aggs.forEach((a, ai) => {
    const id = 'A' + ai
    const label = a.displayName || a.name
    const keys = (a.properties || []).filter(p => p.isKey).map(p => p.name)
    def += `  subgraph SG${ai}["${mmdLabel(label)}"]\n`
    def += `  ${id}["${mmdLabel(label)}<br/><small>${mmdLabel(a.rootEntity || label)} · 속성 ${(a.properties || []).length}` +
           `${keys.length ? ' · key ' + mmdLabel(keys.join(', ')) : ''}</small>"]\n`
    classes.push(`  class ${id} agg`)
    ;(a.enumerations || []).forEach((e, ei) => {
      const eid = `${id}E${ei}`
      const vals = (e.items || e.values || []).map(v => (typeof v === 'string' ? v : (v.value || v.name || ''))).filter(Boolean)
      def += `  ${eid}["${mmdLabel(e.displayName || e.name)}<br/><small>${mmdLabel(vals.slice(0, 4).join(' | '))}${vals.length > 4 ? ' …' : ''}</small>"]\n`
      def += `  ${id} --> ${eid}\n`
      classes.push(`  class ${eid} enum`)
    })
    ;(a.valueObjects || []).forEach((v, vi) => {
      const vid = `${id}V${vi}`
      const fields = (v.properties || v.fields || []).map(f => f.name).filter(Boolean)
      def += `  ${vid}["${mmdLabel(v.displayName || v.name)}<br/><small>${mmdLabel(fields.slice(0, 4).join(', '))}${fields.length > 4 ? ' …' : ''}</small>"]\n`
      def += `  ${id} --> ${vid}\n`
      classes.push(`  class ${vid} vo`)
    })
    def += '  end\n'
  })

  const seen = new Set()
  aggs.forEach((a, ai) => {
    ;(a.valueObjects || []).forEach(v => {
      const target = byName[v.referencedAggregateName]
      if (!target || target === 'A' + ai) return
      const key = `A${ai}=>${target}`
      if (seen.has(key)) return
      seen.add(key)
      def += `  A${ai} -.->|"${mmdLabel(v.referencedAggregateField || '참조')}"| ${target}\n`
    })
  })
  return def + classes.join('\n') + '\n'
}
