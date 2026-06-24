import { reactive } from 'vue'

// 카드 시각화 ↔ Markdown 보기 토글의 공유 상태.
// 한 단계에서 바꾸면 다른 단계·읽기전용 재열람에도 같은 모드가 유지된다(탭 전환에도 보존).
export const stageViewPref = reactive({ mode: 'card' }) // 'card' | 'markdown'

// --- 경량 안전 Markdown 렌더러(ConstitutionEditor 와 동일 규칙: 제목/목록/인용/굵게/코드/표) ---
function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function inline(s) {
  return esc(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>')
}
function renderRow(cells) {
  return '<tr>' + cells.map(c => `<td>${inline(c)}</td>`).join('') + '</tr>'
}
export function renderMarkdown(src) {
  if (!src || !src.trim()) return '<p class="smv__empty">표시할 내용이 없습니다.</p>'
  const lines = String(src).replace(/\r\n/g, '\n').split('\n')
  const out = []
  let inList = false, inQuote = false, para = [], table = null
  const flushPara = () => { if (para.length) { out.push('<p>' + para.map(inline).join('<br>') + '</p>'); para = [] } }
  const closeList = () => { if (inList) { out.push('</ul>'); inList = false } }
  const closeQuote = () => { if (inQuote) { out.push('</blockquote>'); inQuote = false } }
  const closeTable = () => {
    if (!table) return
    const head = renderRow(table.header).replace(/<td>/g, '<th>').replace(/<\/td>/g, '</th>')
    out.push(`<table class="smv__tbl"><thead>${head}</thead><tbody>${table.rows.map(renderRow).join('')}</tbody></table>`)
    table = null
  }
  const splitCells = t => t.replace(/^\||\|$/g, '').split('|').map(s => s.trim())
  for (const ln of lines) {
    const t = ln.trimEnd()
    let m
    // 표: | a | b | 행이 이어지고, 두번째 행이 구분선(---)이면 헤더로 본다.
    if (/^\s*\|.*\|\s*$/.test(t)) {
      const cells = splitCells(t.trim())
      if (/^[-:\s|]+$/.test(t)) continue // 구분선 무시
      flushPara(); closeList(); closeQuote()
      if (!table) table = { header: cells, rows: [] }
      else table.rows.push(cells)
      continue
    }
    closeTable()
    if ((m = t.match(/^(#{1,6})\s+(.*)$/))) { flushPara(); closeList(); closeQuote(); const lvl = m[1].length; out.push(`<h${lvl}>${inline(m[2])}</h${lvl}>`); continue }
    if ((m = t.match(/^\s*[-*]\s+(.*)$/))) { flushPara(); closeQuote(); if (!inList) { out.push('<ul>'); inList = true } out.push(`<li>${inline(m[1])}</li>`); continue }
    if ((m = t.match(/^>\s?(.*)$/))) { flushPara(); closeList(); if (!inQuote) { out.push('<blockquote>'); inQuote = true } out.push(inline(m[1]) + '<br>'); continue }
    if (t.trim() === '') { flushPara(); closeList(); closeQuote(); continue }
    closeList(); closeQuote(); para.push(t)
  }
  flushPara(); closeList(); closeQuote(); closeTable()
  return out.join('\n')
}

// --- 단계 산출물 → Markdown 직렬화 ---
const list = (arr, fn) => (arr || []).map(fn).join('\n')
const bullets = (arr, fn = x => x) => (arr || []).filter(Boolean).map(x => `- ${fn(x)}`).join('\n')

function discoverMd(a) {
  const pivot = new Set(a.pivotalEvents || [])
  const evt = (a.events || []).map(e => {
    const tags = [pivot.has(e.name) ? '⭐ Pivotal' : '', e.external ? '🟪 외부' : ''].filter(Boolean).join(', ')
    return `| ${e.name || ''} | ${e.actor || ''} | ${tags || '—'} |`
  }).join('\n')
  const hot = (a.hotspots || []).map(h => `- 🔥 ${h.text}${h.disposition ? ` _(${h.disposition === 'RESOLVE_NOW' ? '지금 해결' : '보류'})_` : ''}`).join('\n')
  return [
    '# Discover — 이벤트 발굴',
    a.events?.length ? '\n## 도메인 이벤트 타임라인\n\n| 이벤트 | Actor | 태그 |\n| --- | --- | --- |\n' + evt : '',
    hot ? '\n## 🔥 Hotspots\n\n' + hot : '',
  ].filter(Boolean).join('\n')
}

function decomposeMd(a) {
  const sd = (a.subDomains || []).map(s =>
    `- **${s.name || ''}** — ${s.responsibility || '책임 미정'}${s.eventRefs?.length ? `\n  - 이벤트: ${s.eventRefs.join(' · ')}` : ''}`).join('\n')
  const adj = bullets(a.adjacency, x => `${x.from} → ${x.to}`)
  const notes = bullets(a.couplingNotes)
  return [
    '# Decompose — 서브도메인',
    sd ? '\n## 서브도메인\n\n' + sd : '',
    adj ? '\n## 인접 관계\n\n' + adj : '',
    notes ? '\n## 결합 노트\n\n' + notes : '',
  ].filter(Boolean).join('\n')
}

function strategizeMd(a) {
  const rows = (a.classifications || []).map(c =>
    `| ${c.subDomain || ''} | ${c.kind || 'SUPPORTING'} | ${c.rationale || ''}${c.buildVsBuy ? ` (buy: ${c.buildVsBuy})` : ''} |`).join('\n')
  const diff = a.differentiation?.differentiator
  return [
    '# Strategize — Core / Supporting / Generic',
    rows ? '\n## 분류\n\n| 서브도메인 | 분류 | 근거 / build-vs-buy |\n| --- | --- | --- |\n' + rows : '',
    diff ? `\n## 핵심 차별성\n\n> ${diff}` : '',
  ].filter(Boolean).join('\n')
}

function connectMd(a) {
  const rows = (a.interactions || []).map(it =>
    `| ${it.from || ''} → ${it.to || ''} | ${it.message || ''} | ${it.kind || 'EVENT'} | ${it.sync ? '동기' : 'pub/sub'} |`).join('\n')
  const warn = bullets(a.couplingWarnings, w => `⚠️ ${w}`)
  return [
    '# Connect — 컨텍스트 연동',
    rows ? '\n## 메시지 흐름\n\n| From → To | 메시지 | 종류 | 결합 |\n| --- | --- | --- | --- |\n' + rows : '',
    warn ? '\n## 결합 경고\n\n' + warn : '',
    a.messagingChannel ? `\n**메시징 채널:** ${a.messagingChannel}` : '',
  ].filter(Boolean).join('\n')
}

function defineMd(a) {
  return ['# Define — Bounded Context Canvas', ...(a.contexts || []).map(c => {
    const msgs = (arr, dir) => (arr || []).length
      ? `\n**${dir}**\n\n` + arr.map(m => `- ${m.collaborator || m.from || m.to || ''} — ${m.message || ''} (${m.type || ''})`).join('\n')
      : ''
    const ul = (c.ubiquitousLanguage || []).map(u => `- **${u.term}** — ${u.definition || ''}`).join('\n')
    return [
      `\n## ${c.name || 'Bounded Context'}`,
      c.purpose ? `\n**Purpose:** ${c.purpose}` : '',
      `\n**분류:** ${c.classification || '—'}${c.evolution ? ` · ${c.evolution}` : ''}${c.businessModel?.length ? ` · ${c.businessModel.join(', ')}` : ''}`,
      c.domainRoles?.length ? `\n**Domain Roles:** ${c.domainRoles.join(', ')}` : '',
      msgs(c.inbound, 'Inbound'),
      msgs(c.outbound, 'Outbound'),
      ul ? '\n**Ubiquitous Language**\n\n' + ul : '',
      c.businessDecisions?.length ? '\n**Business Decisions**\n\n' + bullets(c.businessDecisions) : '',
      c.assumptions?.length ? '\n**Assumptions**\n\n' + bullets(c.assumptions) : '',
      c.verificationMetrics?.length ? '\n**Verification Metrics**\n\n' + bullets(c.verificationMetrics) : '',
      c.openQuestions?.length ? '\n**Open Questions**\n\n' + bullets(c.openQuestions) : '',
      c.languageClashes?.length ? '\n**⚠️ Language Clashes**\n\n' + bullets(c.languageClashes) : '',
    ].filter(Boolean).join('\n')
  })].join('\n')
}

function tacticalMd(a) {
  return ['# Tactical — Aggregate Design', ...(a.aggregates || []).map(ag => {
    const st = (ag.stateTransitions || []).map(s => `- ${s.from} →${s.trigger}→ ${s.to}`).join('\n')
    return [
      `\n## ${ag.name || 'Aggregate'}`,
      (ag.description || ag.boundaryRationale) ? `\n${ag.description || ag.boundaryRationale}` : '',
      st ? '\n**State Transitions**\n\n' + st : '',
      ag.invariants?.length ? '\n**Enforced Invariants**\n\n' + bullets(ag.invariants) : '',
      ag.correctivePolicies?.length ? '\n**Corrective Policies**\n\n' + bullets(ag.correctivePolicies) : '',
      ag.handledCommands?.length ? '\n**Handled Commands:** ' + ag.handledCommands.join(', ') : '',
      ag.createdEvents?.length ? '\n**Created Events:** ' + ag.createdEvents.join(', ') : '',
    ].filter(Boolean).join('\n')
  })].join('\n')
}

const SERIALIZERS = {
  DISCOVER: discoverMd, DECOMPOSE: decomposeMd, STRATEGIZE: strategizeMd,
  CONNECT: connectMd, DEFINE: defineMd, TACTICAL: tacticalMd,
}

// 단계 산출물을 Markdown 문자열로 직렬화. 알 수 없는 단계는 JSON 코드블록 폴백.
export function artifactToMarkdown(stage, artifact) {
  const fn = SERIALIZERS[stage]
  const a = artifact || {}
  try { return fn ? fn(a) : '```json\n' + JSON.stringify(a, null, 2) + '\n```' }
  catch { return '```json\n' + JSON.stringify(a, null, 2) + '\n```' }
}
