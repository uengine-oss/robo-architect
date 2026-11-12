'use strict'
// Shell page: the tab strip (in the title bar) and the home — the same structure as
// Ontological Studio's shell (its src/renderer/shell/shell.js).
// Tabs live in the main process (src/main/tabs.ts); this page draws them and asks for changes
// through window.raShell. The home opens a project (a graph in the bundled Ontological DB +
// a code folder) through the launcher bridge (window.desktop), and reads the same /api the tabs
// use — this page is served from the same origin (app://app).
const S = window.raShell
const D = window.desktop

const ICONS = {
  home: '<path d="M4 10.5L12 4l8 6.5"/><path d="M6.5 9v10.5h11V9"/><path d="M10 19.5v-5h4v5"/>',
  Proposals: '<path d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14 3.5V8h5"/><path d="M9 13l2 2 4-4"/>',
  Stories: '<path d="M4 6.5h16M4 12h16M4 17.5h10"/><circle cx="18.5" cy="17.5" r="1.6"/>',
  Process: '<rect x="2.5" y="9" width="5.5" height="6" rx="1.4"/><rect x="16" y="9" width="5.5" height="6" rx="1.4"/><path d="M8 12h8"/><path d="M13.5 9.5L16 12l-2.5 2.5"/>',
  Design: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="8.5" y="13.5" width="7" height="7" rx="1.5"/><path d="M7 10.5v1.5h10v-1.5M12 12v1.5"/>',
  Data: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
  Code: '<path d="M8.5 7L3.5 12l5 5M15.5 7l5 5-5 5"/><path d="M13.5 4.5l-3 15"/>',
  Legacy: '<rect x="3" y="4" width="18" height="16" rx="2.2"/><path d="M7 9.5l3 2.5-3 2.5M12.5 15h4.5"/>',
  constitution: '<path d="M12 3l7 3v5.2c0 4.4-2.9 8.1-7 9.8-4.1-1.7-7-5.4-7-9.8V6z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
  graph: '<circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M8.4 6h7.2M7.1 8.1l3.8 7.8M16.9 8.1l-3.8 7.8"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  window: '<rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M3.5 9h17"/><path d="M14 13.5h3.5M15.75 11.75v3.5"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
  moon: '<path d="M20 14.2A8 8 0 0 1 9.8 4a8 8 0 1 0 10.2 10.2z"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
  arrow: '<path d="M7 17L17 7M9 7h8v8"/>',
  folder: '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
  logs: '<path d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14 3.5V8h5M9 12h7M9 15.5h7M9 19h4"/>',
  dot: '<circle cx="12" cy="12" r="2.5"/>',
}
const icon = (n, cls = 'ic') => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ICONS.dot}</svg>`
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])
const $ = (id) => document.getElementById(id)

const C = { teal: '#18b6a0', blue: '#4c8bf5', amber: '#e0a33e', violet: '#8d8ff5', pink: '#e06c9f', green: '#3fbf86', slate: '#93a1b3' }
const VIEW_LABEL = { Proposals: '프로포절', Stories: '요구사항', Process: '프로세스', Design: '설계', Data: '데이터', Code: '코드', Legacy: '레거시' }
const CARDS = [
  { title: '프로포절', desc: '요구사항 한 줄을 설계 · 계획 · 구현 · 검증까지 한 흐름으로.', icon: 'Proposals', c: 'teal', target: { view: 'Proposals' } },
  { title: '요구사항', desc: '바운디드 컨텍스트 › 기능 › 유저 스토리 › 인수 조건(GWT).', icon: 'Stories', c: 'blue', target: { view: 'Stories' } },
  { title: '프로세스', desc: 'BPM 흐름과 이벤트 모델링을 한 그래프에서.', icon: 'Process', c: 'violet', target: { view: 'Process' } },
  { title: '설계 캔버스', desc: '이벤트스토밍 — 애그리거트 · 커맨드 · 이벤트 · 정책.', icon: 'Design', c: 'amber', target: { view: 'Design' } },
  { title: '데이터 모델', desc: '애그리거트 · 엔티티 · 값 객체 · 불변식.', icon: 'Data', c: 'green', target: { view: 'Data' } },
  { title: '코드', desc: '코드 폴더와 Claude Code 터미널.', icon: 'Code', c: 'slate', target: { view: 'Code' } },
  { title: '레거시 · 데이터 소스', desc: '기존 코드를 분석하고 원천 DB 를 패브릭으로 연결.', icon: 'Legacy', c: 'pink', target: { view: 'Legacy' } },
  { title: '프로젝트 헌장', desc: '설계 원칙 · 기술 스택 · 아키텍처 스타일.', icon: 'constitution', c: 'slate', target: { view: 'Design', constitution: true } },
]
const FILTERS = [
  { key: 'all', label: '전체', side: '최근 항목', icon: 'clock' },
  { key: 'proposal', label: '프로포절', icon: 'Proposals' },
  { key: 'project', label: '프로젝트', icon: 'graph' },
]
const STATUS_KO = { INTENT: '인텐트', PLAN: '계획', IMPLEMENTING: '구현 중', VALIDATING: '검증 중', PENDING_ACCEPTANCE: '승인 대기', ACCEPTED: '수락됨', DESTROYED: '폐기됨' }

let tabState = { active: 'home', tabs: [] }
let session = null
let runtime = { status: 'initializing' }
let boot = null      // image download progress while starting-db (BackendStatusEvent.progress)
let bootError = ''   // why start-up failed (BackendStatusEvent.detail with fatal)
let info = {}
let projects = []
let items = []
let filter = 'all'
let query = ''
let picking = false
let pick = { graph: null, folder: '', busy: false, msg: '', err: false, newName: '' }

const ready = () => runtime.status === 'ready'
const unwrap = (r) => (r && r.ok ? r.data : null)

// ── tab strip ──
function renderTabs() {
  const home = `<div class="tab home${tabState.active === 'home' ? ' active' : ''}" data-id="home" role="tab" title="홈 (⌘1)">${icon('home')}<span class="tab-title">홈</span></div>`
  const rest = tabState.tabs.map((t, i) => `
    <div class="tab${tabState.active === t.id ? ' active' : ''}" data-id="${t.id}" role="tab" title="${esc(t.title)}${i < 8 ? ` (⌘${i + 2})` : ''}">
      ${t.loading ? '<span class="spin"></span>' : icon(t.view || 'Proposals')}
      <span class="tab-title">${esc(t.title)}</span>
      <button class="tab-x" data-close="${t.id}" title="닫기 (⌘W)">${icon('close')}</button>
    </div>`).join('')
  $('tabs').innerHTML = home + rest
  document.body.classList.toggle('at-home', tabState.active === 'home')
}
$('tabs').addEventListener('mousedown', (e) => {
  if (e.button !== 0 || e.target.closest('[data-close]')) return
  const tab = e.target.closest('.tab')
  if (tab && S) S.tabs.activate(tab.dataset.id)
})
$('tabs').addEventListener('click', (e) => {
  const x = e.target.closest('[data-close]')
  if (x && S) S.tabs.close(x.dataset.close)
})
$('tabs').addEventListener('auxclick', (e) => {
  const tab = e.target.closest('.tab')
  if (e.button === 1 && tab && tab.dataset.id !== 'home' && S) S.tabs.close(tab.dataset.id)
})
$('tabs').addEventListener('contextmenu', (e) => {
  const tab = e.target.closest('.tab')
  if (tab && tab.dataset.id !== 'home' && S) { e.preventDefault(); S.tabs.menu(tab.dataset.id) }
})
$('new-tab').innerHTML = icon('plus')
$('new-tab').addEventListener('click', () => S && S.tabs.activate('home'))
$('btn-window').innerHTML = icon('window')
$('btn-window').addEventListener('click', () => S && S.newWindow())

// ── theme (shared with the app's tabs through localStorage 'app_theme') ──
function theme() { return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark' }
function paintThemeButton() { $('btn-theme').innerHTML = icon(theme() === 'dark' ? 'sun' : 'moon') }
$('btn-theme').addEventListener('click', () => {
  const next = theme() === 'dark' ? 'light' : 'dark'
  document.documentElement.dataset.theme = next
  try { localStorage.setItem('app_theme', next) } catch {}
  paintThemeButton()
})
window.addEventListener('storage', (e) => {
  if (e.key === 'app_theme' && (e.newValue === 'light' || e.newValue === 'dark')) { document.documentElement.dataset.theme = e.newValue; paintThemeButton() }
})
paintThemeButton()

// ── home: greeting, project panel ──
function renderHello() {
  const name = session?.identity?.displayName
  $('hello').innerHTML = `안녕하세요${name ? `, ${esc(name)}님` : ''}.<br>무엇을 설계하고 싶으신가요?`
}

function renderProject() {
  const el = $('project')
  if (!ready()) {
    el.className = 'booting'
    el.innerHTML = `<span class="spin"></span><div><b>그래프 DB 와 서비스를 올리는 중입니다…</b><small>${esc(bootText())}</small></div>`
    return
  }
  if (session && !picking) {
    el.className = 'project'
    el.innerHTML = `${icon('graph')}
      <div class="project-main">
        <div class="project-name">${esc(session.graph || 'robo')}<span class="badge">프로젝트</span></div>
        <div class="project-sub" title="${esc(session.projectRoot)}">코드 폴더 · ${esc(session.projectRoot)}</div>
      </div>
      <div class="project-actions">
        <button class="btn" data-act="code">${icon('folder')}코드 폴더</button>
        <button class="btn" data-act="switch">프로젝트 바꾸기</button>
      </div>`
    return
  }
  // pick a project (graph) and a code folder — the old launcher, on the home
  if (!pick.graph) pick.graph = session?.graph || (projects.find((p) => p.lastUsed) || projects.find((p) => p.isDefault) || projects[0] || {}).name || null
  el.className = 'project pick'
  el.innerHTML = `
    <div class="pick-row"><span class="pick-label">프로젝트</span>
      <div class="chips">${projects.map((p) => `<button class="chip${pick.graph === p.name ? ' on' : ''}" data-graph="${esc(p.name)}">${icon('graph')}${esc(p.name)}<small>${p.isDefault ? '기본 · ' : ''}${p.types ? `노드 종류 ${p.types}` : '빈 프로젝트'}</small></button>`).join('')}</div>
    </div>
    <div class="pick-row"><span class="pick-label">새 프로젝트</span>
      <input class="field" id="new-name" placeholder="영문 소문자 (예: food_delivery)" value="${esc(pick.newName)}" spellcheck="false">
      <button class="btn" data-act="create">${icon('plus')}만들기</button>
      <span class="folder">프로젝트마다 그래프가 따로 생깁니다 — 한 그래프 DB 안에서 섞이지 않습니다.</span>
    </div>
    <div class="pick-row"><span class="pick-label">코드 폴더</span>
      <button class="btn" data-act="folder">${icon('folder')}폴더 선택…</button>
      <span class="folder">${esc(pick.folder || '구현 코드가 쌓일 Git 저장소 폴더를 고르세요')}</span>
    </div>
    <div class="pick-foot"><span class="msg${pick.err ? ' err' : ''}">${esc(pick.msg)}</span>
      ${session ? '<button class="btn" data-act="cancel">취소</button>' : ''}
      <button class="btn primary" data-act="open" ${pick.graph && pick.folder && !pick.busy ? '' : 'disabled'}>${pick.busy ? '여는 중…' : '프로젝트 열기'}</button>
    </div>`
}
$('project').addEventListener('input', (e) => { if (e.target.id === 'new-name') pick.newName = e.target.value })
$('project').addEventListener('keydown', (e) => { if (e.target.id === 'new-name' && e.key === 'Enter') createProject() })
$('project').addEventListener('click', async (e) => {
  const chip = e.target.closest('[data-graph]')
  if (chip) { pick.graph = chip.dataset.graph; renderProject(); return }
  const b = e.target.closest('[data-act]')
  if (!b) return
  const act = b.dataset.act
  if (act === 'code') S && S.open('code')
  else if (act === 'switch') { picking = true; pick = { graph: session.graph, folder: session.projectRoot, busy: false, msg: '', err: false, newName: '' }; renderProject() }
  else if (act === 'cancel') { picking = false; renderProject() }
  else if (act === 'create') createProject()
  else if (act === 'folder') {
    const r = unwrap(await D.projectRoot.choose())
    if (r && !r.cancelled) { pick.folder = r.path; pick.msg = r.valid ? '' : '이 폴더를 읽을 수 없습니다.'; pick.err = !r.valid; renderProject() }
  } else if (act === 'open') openProject()
})

async function createProject() {
  const name = pick.newName.trim()
  if (!name) return
  const r = await D.projects.create({ name })
  if (r.ok) { projects = r.data; pick.graph = name; pick.newName = ''; pick.msg = `프로젝트 ${name} 을 만들었습니다.`; pick.err = false }
  else { pick.msg = r.error.message; pick.err = true }
  renderProject(); renderSide(); buildItems(); renderRows()
}

async function openProject() {
  pick.busy = true; pick.msg = '백엔드를 이 프로젝트의 그래프로 맞추는 중…'; pick.err = false; renderProject()
  const r = await S.openProject(pick.graph, pick.folder)
  pick.busy = false
  if (r && r.ok) { session = r.data; picking = false; pick.msg = '' }
  else { pick.msg = (r && r.error) || '열지 못했습니다.'; pick.err = true }
  await load()
}

// ── cards ──
function renderCards() {
  const on = ready() && !!session
  $('cards').innerHTML = CARDS.map((c, i) => `<button class="card" data-card="${i}" style="--c:${C[c.c]}" ${on ? '' : 'disabled'} title="${on ? '' : '먼저 프로젝트를 여세요'}">
      <span class="card-icon">${icon(c.icon)}</span>
      <span class="card-title">${esc(c.title)}</span>
      <span class="card-desc">${esc(c.desc)}</span>
      <span class="card-go">${icon('arrow')}</span>
    </button>`).join('')
}
$('cards').addEventListener('click', (e) => {
  const el = e.target.closest('[data-card]')
  if (!el || el.disabled || !S) return
  const c = CARDS[Number(el.dataset.card)]
  S.openTab({ ...c.target, title: c.title })
})

// ── side ──
function renderSide() {
  const count = (k) => (k === 'all' ? items.length : items.filter((x) => x.type === k).length)
  $('side-nav').innerHTML = FILTERS.map((f) => `<button class="side-item${filter === f.key ? ' active' : ''}" data-filter="${f.key}">${icon(f.icon)}<span>${f.side || f.label}</span><span class="n">${count(f.key)}</span></button>`).join('')
  $('seg').innerHTML = FILTERS.map((f) => `<button class="${filter === f.key ? 'active' : ''}" data-filter="${f.key}">${f.label}</button>`).join('')
  $('side-quick').innerHTML = [
    ['code', 'folder', '코드 폴더'],
    ['logs', 'logs', '로그 폴더'],
    ['data', 'folder', '데이터 폴더'],
  ].map(([k, ic, label]) => `<button class="side-item" data-quick="${k}" ${k === 'code' && !session ? 'disabled' : ''}>${icon(ic)}<span>${label}</span><span class="go">${icon('arrow')}</span></button>`).join('')
}
for (const id of ['side-nav', 'seg']) {
  $(id).addEventListener('click', (e) => {
    const b = e.target.closest('[data-filter]')
    if (b) { filter = b.dataset.filter; renderSide(); renderRows() }
  })
}
$('side-quick').addEventListener('click', (e) => {
  const b = e.target.closest('[data-quick]')
  if (b && S) S.open(b.dataset.quick)
})
$('search-icon').outerHTML = icon('search')
$('q').addEventListener('input', (e) => { query = e.target.value.trim().toLowerCase(); renderRows() })

// ── list ──
function when(v) {
  if (v == null || v === '') return null
  const n = typeof v === 'number' ? (v < 1e12 ? v * 1000 : v) : Date.parse(v)
  return Number.isFinite(n) ? n : null
}
function fmtDate(ms) {
  if (!ms) return '—'
  const d = new Date(ms), now = new Date()
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  if (d.toDateString() === now.toDateString()) return `오늘 ${hm}`
  if (d.getFullYear() === now.getFullYear()) return `${d.getMonth() + 1}월 ${d.getDate()}일`
  return `${d.getFullYear()}. ${d.getMonth() + 1}. ${d.getDate()}.`
}
let proposals = []
function buildItems() {
  const next = []
  for (const p of proposals) {
    next.push({ type: 'proposal', name: p.title || p.id, kind: `프로포절 ${p.id}`, info: p.status, date: when(p.createdAt), icon: 'Proposals', c: 'teal', open: { view: 'Proposals', proposal: p.id, title: p.id } })
  }
  for (const g of projects) {
    const cur = session && session.graph === g.name
    next.push({ type: 'project', name: g.name, kind: cur ? '프로젝트 · 열려 있음' : '프로젝트', info: g.types ? `노드 종류 ${g.types}` : '빈 프로젝트', date: null, icon: 'graph', c: 'violet', project: g.name })
  }
  next.sort((a, b) => (b.date || 0) - (a.date || 0))
  items = next
}
function renderRows() {
  const list = items
    .filter((x) => filter === 'all' || x.type === filter)
    .filter((x) => !query || `${x.name} ${x.kind} ${x.info}`.toLowerCase().includes(query))
  $('rows').innerHTML = list.map((x) => `
    <tr data-row="${items.indexOf(x)}" style="--c:${C[x.c]}">
      <td><span class="name">${icon(x.icon)}${esc(x.name)}</span></td>
      <td class="kind">${esc(x.kind)}</td>
      <td class="info">${x.type === 'proposal' ? `<span class="st ${esc(x.info)}">${esc(STATUS_KO[x.info] || x.info)}</span>` : esc(x.info)}</td>
      <td class="date">${fmtDate(x.date)}</td>
    </tr>`).join('')
  $('empty').hidden = list.length > 0
  $('empty').textContent = items.length ? '조건에 맞는 항목이 없습니다.' : '아직 만든 것이 없습니다. 위에서 시작하세요.'
  $('count').textContent = `${FILTERS.find((f) => f.key === filter).label} · ${list.length}개`
}
$('rows').addEventListener('click', (e) => {
  const tr = e.target.closest('[data-row]')
  if (!tr) return
  const x = items[Number(tr.dataset.row)]
  if (x.open && S) S.openTab(x.open)
  else if (x.project) {
    picking = true
    pick = { graph: x.project, folder: session?.projectRoot || '', busy: false, msg: '코드 폴더를 확인하고 「프로젝트 열기」를 누르세요.', err: false, newName: '' }
    renderProject()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
})

// ── status ──
function bootText() {
  return ({
    initializing: '앱을 준비하는 중', 'starting-db': 'Docker 로 그래프 DB(Ontological) · Bolt · 패브릭 · 분석 서비스를 올리는 중 — 처음 실행은 몇 분 걸립니다',
    'starting-backend': 'Robo Architect 백엔드를 띄우는 중', fatal: '시작하지 못했습니다 — 로그 폴더를 보세요', 'backend-crashed': '백엔드가 멈췄습니다',
  })[runtime.status] || runtime.status
}
// first launch of a release: the images come from the registry (main/docker-images.ts)
const IMAGE_LABEL = { graphDb: 'Ontological DB', graphBolt: 'Bolt', analyzer: 'Analyzer', catalog: 'Catalog', fabric: 'Data fabric', parser: 'Parser', gateway: 'API gateway', wireframe: 'Wireframe renderer' }
const bytes = (n) => (n >= 1e9 ? `${(n / 1e9).toFixed(2)} GB` : `${Math.round(n / 1e6)} MB`)
function bootHtml() {
  const p = boot
  if (p && runtime.status === 'starting-db') {
    if (p.phase === 'loading') return `<span>Docker 이미지 묶음을 불러오는 중</span> · ${p.count}`
    const label = esc(IMAGE_LABEL[p.name] || p.name)
    const one = p.totalBytes ? ` · ${bytes(p.currentBytes)} / ${bytes(p.totalBytes)}` : ''
    const pct = p.overallTotal ? Math.min(100, Math.round((p.overallBytes / p.overallTotal) * 100)) : 0
    return `<span>Docker 이미지 내려받는 중</span> ${p.index}/${p.count} — ${label}${one}`
      + `<span class="pull-bar"><i style="width:${pct}%"></i></span>`
      + `<span>처음 실행에서 한 번만 받습니다</span>${p.overallTotal ? ` · ${bytes(p.overallBytes)} / ${bytes(p.overallTotal)}` : ''}`
  }
  if (runtime.status === 'fatal' && bootError) {
    if (/docker\.daemon_unavailable/.test(bootError)) return '<span>Docker Desktop 을 켠 뒤 앱을 다시 여세요</span>'
    if (/docker\.image_pull_failed/.test(bootError)) return '<span>Docker 이미지를 내려받지 못했습니다 — 인터넷 연결을 확인하고 앱을 다시 여세요</span>'
  }
  return esc(bootText())
}
// AI 키 행 — **키는 선택이다.** 이 PC 의 Claude Code 브리지가 LLM 을 대신하므로, 키가 없어도
// "레거시 분석 → 문서 업로드 → 설계 → 프로포절 → 구현 → 검증" 이 전 구간 돈다(2026-11-11 에
// PRO-001 을 끝까지 돌려 확인했다). 그래서 **노란 점으로 경고하지 않는다** — 예전 문구는
// "미설정" 을 빠뜨린 것처럼 보이게 하고 setx 를 맨 앞에 띄웠다.
//
// 키가 실제로 하는 일은 둘뿐이다:
//   ① **catalog** 의 표 설명·FK 추론 — 그 컨테이너는 브리지를 타지 않는다(굽기가
//      LLM_API_BASE=api.openai.com + 빈 키로 박는다) → 키가 없으면 못 한다
//   ② **임베딩** — 브리지에는 `/embeddings` 가 없다(`/chat/completions`·`/models` 뿐).
//      없으면 하이브리드 매퍼가 후보를 못 좁히고 전부 LLM 검증자에게 넘긴다
//      (agentic_retriever: "No embeddings available — degrade to return everything in scope").
//      결과는 나오지만 정밀도가 떨어지고 LLM 호출이 늘어난다
// ⚠ 키를 넣으면 llmBridgeEnv() 가 손을 뗀다 → **LLM 호출이 Claude Code 대신 그 키로 간다.**
//   과금 주체가 바뀌는 것이므로 '설정됨' 쪽에 그 말을 적는다.
//
// main 의 openAiKey 가 **이름과 설정 여부만** 넘긴다 — 값은 넘어오지도, 찍히지도 않는다.
function keyRowHtml() {
  const k = info.openAiKey
  if (!k || !Array.isArray(k.names)) return ''
  const name = esc(k.names[k.names.length - 1])
  // Finder 로 연 앱은 셸 설정을 안 읽으므로(host-path.ts 는 PATH 만 가져온다) macOS 는 launchctl 이다.
  const how = info.platform === 'darwin'
    ? `launchctl setenv ${name} &lt;키&gt;`
    : `setx ${name} &lt;키&gt;`
  if (k.set) {
    return `<div class="status-row"><span class="dot ok"></span><div><b>AI 키</b> 설정됨<small>카탈로그의 표 설명·FK 추론과 임베딩 매핑이 돕니다 · LLM 호출도 Claude Code 대신 이 키로 갑니다</small></div></div>`
  }
  // 에이전트도 없고 키도 없으면 그때는 **진짜 경고**다 — LLM 단계가 아예 못 돈다.
  if (!info.claude) {
    return `<div class="status-row"><span class="dot warn"></span><div><b>AI 키</b> 없음<small>Claude Code 도 없습니다 — 둘 중 하나는 있어야 분석·설계·구현이 돕니다 · ${how} 뒤 앱 다시 열기</small></div></div>`
  }
  return `<div class="status-row"><span class="dot"></span><div><b>AI 키</b> 없음 — 넣지 않아도 됩니다<small>LLM 은 위의 Claude Code 가 대신합니다. 키를 넣으면 ① 카탈로그의 표 설명·FK 추론이 돌고 ② 요구사항 매핑이 임베딩으로 더 정확해집니다 · ${how} 뒤 앱 다시 열기</small></div></div>`
}
// 에이전트 행. CLI 가 있나 없나만 말하던 자리다 — **누구 구독으로 도는지**도 말한다.
// 스킬과 LLM 브리지는 Anthropic 키를 지우고 `claude -p` 를 띄우므로(skill_runner._skill_env),
// 과금되는 계정은 이 PC 의 CLI 로그인이다. main 이 설정 파일에서 메일·요금제만 읽어 넘긴다.
function agentRowHtml() {
  const claude = info.claude
  if (!claude) {
    return `<div class="status-row"><span class="dot warn"></span><div><b>에이전트</b> 찾지 못함<small>claude CLI 를 설치하고 로그인하세요</small></div></div>`
  }
  const acc = info.claudeAccount
  const who = acc && acc.email
    ? `${esc(acc.email)}${acc.plan ? ` · ${esc(acc.plan)}` : ''} 계정으로 돕니다`
    : '로그인 정보를 못 읽었습니다 — 터미널에서 claude 를 한 번 실행해 로그인하세요'
  return `<div class="status-row"><span class="dot ${acc && acc.email ? 'ok' : 'warn'}"></span><div><b>에이전트</b> Claude Code<small>이 PC 의 CLI 가 스킬로 분석 · 계획 · 구현합니다 · ${who}</small></div></div>`
}
function renderStatus() {
  const ok = ready()
  const bad = runtime.status === 'fatal' || runtime.status === 'backend-crashed'
  $('status').innerHTML = `
    <div class="status-row"><span class="dot ${ok ? 'ok' : bad ? 'bad' : 'warn'}"></span><div><b>Ontological</b> ${ok ? '연결됨' : bad ? '멈춤' : '시작 중'}<small>${ok ? `그래프 ${esc(session?.graph || '—')} · Docker 컨테이너 ${info.stackServices ?? 8}개 · 127.0.0.1` : bootHtml()}</small></div></div>`
    + agentRowHtml()
    + keyRowHtml()
}

// ── loading ──
async function getJSON(u) {
  try { const r = await fetch(u, { cache: 'no-store' }); return r.ok ? await r.json() : null } catch { return null }
}
async function load() {
  if (!D || !S) return
  runtime = unwrap(await D.app.getRuntimeState()) || runtime
  info = (await S.info()) || {}
  session = info.session || (await S.session()) || null
  if (ready()) {
    projects = unwrap(await D.projects.list()) || []
    if (!session && !pick.folder) {
      const recent = unwrap(await D.projectRoot.listRecent()) || []
      if (recent[0]) pick.folder = recent[0].path
    }
    proposals = session ? (await getJSON('/api/proposals/?limit=100')) || [] : []
  }
  buildItems()
  renderHello(); renderProject(); renderCards(); renderSide(); renderRows(); renderStatus()
}

renderTabs(); renderCards(); renderSide(); renderRows(); renderStatus(); renderProject()
if (S) {
  S.tabs.onChange((state) => {
    const wasHome = tabState.active === 'home'
    tabState = state
    renderTabs()
    if (state.active === 'home' && !wasHome) load()
  })
  S.tabs.get().then((state) => { if (state) { tabState = state; renderTabs() } })
  S.onSession(() => load())
  document.body.classList.add(`os-${S.platform}`)
  S.isFullScreen().then((on) => document.body.classList.toggle('full', !!on))
  S.onFullScreen((on) => document.body.classList.toggle('full', on))
}
if (D && D.app && D.app.onBackendStatus) D.app.onBackendStatus((e) => {
  const same = e.status === runtime.status
  boot = e.progress || (e.status === 'starting-db' ? boot : null)
  if (e.status === 'fatal') bootError = e.detail || ''
  runtime = { ...runtime, status: e.status }
  // download ticks only redraw the status — a full load() per tick would refetch everything
  if (same && e.progress) renderStatus()
  else load()
})
load()
window.addEventListener('focus', () => { if (tabState.active === 'home') load() })
