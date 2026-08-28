<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import mermaid from 'mermaid'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { useNavigatorStore } from '@/features/navigator/navigator.store'
import { useBpmnStore } from '@/features/canvas/bpmn.store'
// 039 — 'Big picture' 뷰 비활성화: store import 제거.
// 039 후속 — Value Stream 은 BPM Session 스냅샷(Deliverable API)으로 복원한다.

const canvasStore = useCanvasStore()
const navigatorStore = useNavigatorStore()
const bpmnStore = useBpmnStore()

// 섹션 구성은 기준 템플릿(local-msaez DocumentTemplate.vue)의 순서를 따른다.
// userScenario / valueStream / boundedContext / eventStorming /
// apiSpecification / aggregateDetail / traceabilityMatrix
const selectedSections = ref({
  userStories: true,
  valueStream: true,
  boundedContext: true,
  modelOverview: true,
  apiSpecification: true,
  aggregateDetail: true,
  traceabilityMatrix: true,
})

const SECTION_LABELS = {
  userStories: '사용자 스토리',
  valueStream: '밸류 스트림 분석',
  boundedContext: 'Bounded Context',
  modelOverview: '모델 전반 정보',
  apiSpecification: 'API 명세',
  aggregateDetail: 'Aggregate 상세',
  traceabilityMatrix: '추적성 매트릭스',
}

const isLoading = ref(true)
const fullTrees = ref({})
const allContexts = ref([])
// Session 단위 산출물 스냅샷. null 이면 세션을 특정할 수 없어 전역 조회로
// 대체한 상태(= 이전 동작).
const deliverable = ref(null)

const sessionScoped = computed(() => !!deliverable.value)

/**
 * Session 범위로 고정된 산출물을 읽는다.
 *
 * 전역 `/api/contexts` 조회는 같은 Neo4j 에 여러 분석 결과가 있으면 서로 다른
 * 세션의 BC 가 한 문서에 섞인다. 납품 문서는 재현 가능해야 하므로 활성 Hybrid
 * Session 이 있으면 그 범위만 읽는다. 세션이 없거나(예: 수동 설계) 조회에
 * 실패하면 기존 전역 조회로 되돌아간다.
 */
async function loadFromSession(sessionId) {
  const resp = await fetch(`/api/deliverables/architecture-document?sessionId=${encodeURIComponent(sessionId)}`)
  if (!resp.ok) return false
  const doc = await resp.json()
  const trees = {}
  for (const tree of (doc.eventStorming?.contexts || [])) trees[tree.id] = tree
  // 목록 API 와 같은 필드(userStoryCount 등)를 쓰는 곳이 있어 트리에서 보강한다.
  allContexts.value = (doc.boundedContexts || []).map(bc => ({
    ...bc,
    description: trees[bc.id]?.description || '',
    userStoryCount: trees[bc.id]?.userStories?.length || 0,
  }))
  fullTrees.value = trees
  deliverable.value = doc
  return true
}

async function loadAllContexts() {
  const ctxResp = await fetch('/api/contexts')
  if (ctxResp.ok) allContexts.value = await ctxResp.json()
  const trees = {}
  await Promise.all(allContexts.value.map(async (ctx) => {
    try {
      const resp = await fetch(`/api/contexts/${ctx.id}/full-tree`)
      if (resp.ok) trees[ctx.id] = await resp.json()
    } catch (e) { /* skip */ }
  }))
  fullTrees.value = trees
}

async function loadAllData() {
  isLoading.value = true
  deliverable.value = null
  try {
    const sid = bpmnStore.hybridSessionId
    if (sid) {
      try {
        if (await loadFromSession(sid)) return
        console.warn('[ExportDocument] session snapshot unavailable, falling back to all contexts')
      } catch (e) {
        console.warn('[ExportDocument] session snapshot failed, falling back:', e)
      }
    }
    await loadAllContexts()
  } catch (e) {
    console.error('[ExportDocument] load error:', e)
  } finally {
    isLoading.value = false
  }
}

onMounted(loadAllData)
defineExpose({
  selectedSections, reload: loadAllData,
  // Data (reactive refs → export reads .value)
  get allContexts() { return allContexts.value },
  get fullTrees() { return fullTrees.value },
  get sortedContexts() { return sortedContexts.value },
  get allUserStories() { return allUserStories.value },
  get crossBCPolicies() { return crossBCPolicies.value },
  get sectionNumbers() { return sectionNumbers.value },
  get deliverable() { return deliverable.value },
  get sessionScoped() { return sessionScoped.value },
  get valueStreamProcesses() { return valueStreamProcesses.value },
  get glossaryTerms() { return glossaryTerms.value },
  get traceGroups() { return traceGroups.value },
  get traceInferred() { return traceInferred.value },
  get traceUnmapped() { return traceUnmapped.value },
  get traceSummary() { return traceSummary.value },
  get apiSpec() { return apiSpec.value },
  get apiSummary() { return apiSummary.value },
  get apiConvention() { return apiConvention.value },
  get aggregateExport() { return aggregateExport.value },
  // Helpers
  bcName, bcTree, getCommandsFromTree, getReadModelsFromTree,
  allCmdsForCtx, allEvtsForCtx, resolveNodeName, parseJsonFields,
  traceTypeLabel, storySources, storySourceTask, apiForCtx,
})

// ── Helpers ──
const sectionNumbers = computed(() => {
  let n = 0; const nums = {}
  if (selectedSections.value.userStories) nums.userStories = ++n
  if (selectedSections.value.valueStream) nums.valueStream = ++n
  if (selectedSections.value.boundedContext) nums.boundedContext = ++n
  if (selectedSections.value.modelOverview) nums.modelOverview = ++n
  if (selectedSections.value.apiSpecification) nums.apiSpecification = ++n
  if (selectedSections.value.aggregateDetail) nums.aggregateDetail = ++n
  if (selectedSections.value.traceabilityMatrix) nums.traceabilityMatrix = ++n
  return nums
})

const domainOrder = { 'Core Domain': 0, 'Supporting Domain': 1, 'Generic Domain': 2 }
const sortedContexts = computed(() =>
  [...allContexts.value].sort((a, b) => (domainOrder[a.domainType] ?? 9) - (domainOrder[b.domainType] ?? 9))
)

const allUserStories = computed(() => {
  const stories = []
  for (const [, tree] of Object.entries(fullTrees.value)) {
    const bn = tree.displayName || tree.name
    ;(tree.userStories || []).forEach(s => stories.push({ ...s, bcName: bn }))
  }
  // Session 범위로 고정된 경우 Navigator 의 전역 목록을 섞지 않는다. 다른 세션의
  // User Story 가 '미배정' 으로 딸려 들어와 문서 범위가 깨지기 때문.
  if (!sessionScoped.value) {
    ;(navigatorStore.userStories || []).forEach(s => {
      if (!stories.find(x => x.id === s.id)) stories.push({ ...s, bcName: '미배정' })
    })
  }
  return stories
})

// 039 — 'Big picture' 뷰 비활성화: swimlane(빅픽처) export 섹션 비활성화(빈 배열 → v-if 미렌더).
const swimlanes = computed(() => [])

function getEdgeRelationsForBC(bcId) {
  const ids = new Set(canvasStore.nodes.filter(n => n.parentNode === bcId).map(n => n.id))
  return canvasStore.edges
    .filter(e => { const et = e.data?.edgeType; return et && ['EMITS','TRIGGERS','INVOKES','HAS_COMMAND'].includes(et) && (ids.has(e.source) || ids.has(e.target)) })
    .map(e => {
      const s = canvasStore.nodes.find(n => n.id === e.source), t = canvasStore.nodes.find(n => n.id === e.target)
      return { edgeType: e.data.edgeType, sn: s?.data?.displayName||s?.data?.name||'', st: s?.type||'', tn: t?.data?.displayName||t?.data?.name||'', tt: t?.type||'' }
    })
}

const crossBCPolicies = computed(() => {
  const result = []
  for (const [, tree] of Object.entries(fullTrees.value)) {
    const bcDisplay = tree.displayName || tree.name
    ;(tree.policies || []).forEach(pol => {
      if (!pol.triggerEventId || !pol.invokeCommandId) return
      let triggerBC = null, triggerEvt = null, invokeBC = bcDisplay, invokeCmd = null
      for (const [, ot] of Object.entries(fullTrees.value)) {
        for (const a of (ot.aggregates || [])) {
          for (const ev of (a.events || [])) { if (ev.id === pol.triggerEventId) { triggerBC = ot.displayName||ot.name; triggerEvt = ev.displayName||ev.name } }
          for (const c of (a.commands || [])) {
            if (c.id === pol.invokeCommandId) { invokeBC = ot.displayName||ot.name; invokeCmd = c.displayName||c.name }
            for (const ev of (c.events || [])) { if (ev.id === pol.triggerEventId) { triggerBC = ot.displayName||ot.name; triggerEvt = ev.displayName||ev.name } }
          }
        }
      }
      if (triggerBC && triggerBC !== invokeBC) result.push({ fromBC: triggerBC, fromEvent: triggerEvt||'', policy: pol.displayName||pol.name, toBC: invokeBC, toCommand: invokeCmd||'' })
    })
  }
  return result
})

// ── Value Stream / 추적성 (Session 스냅샷 전용) ──
// 기준 템플릿의 `getValueStreamLinearPages` 와 `traceabilityMatrixGroups` 에
// 대응한다. Session 스냅샷이 없으면 빈 값 → 섹션 자체가 렌더링되지 않는다.
const valueStreamProcesses = computed(() => deliverable.value?.valueStream?.processes || [])
const glossaryTerms = computed(() => deliverable.value?.valueStream?.glossary || [])
const apiSpec = computed(() => deliverable.value?.apiSpecification || null)
// 기준 기능(local-msaez CodeGenerator "Export Aggregates") 대응 데이터.
const aggregateExport = computed(() => deliverable.value?.aggregateExport || null)
const apiSummary = computed(() => apiSpec.value?.summary || null)
const apiConvention = computed(() => apiSpec.value?.convention || '')
// BC id → 도출된 엔드포인트 계약
const apiByBc = computed(() => {
  const map = {}
  for (const c of (apiSpec.value?.contexts || [])) map[c.bcId] = c
  return map
})
function apiForCtx(ctx) { return apiByBc.value[ctx.id] || null }

const traceGroups = computed(() => deliverable.value?.traceabilityMatrix?.groups || [])
const traceInferred = computed(() => deliverable.value?.traceabilityMatrix?.inferred || [])
const traceUnmapped = computed(() => deliverable.value?.traceabilityMatrix?.unmapped || [])
const traceSummary = computed(() => deliverable.value?.traceabilityMatrix?.summary || null)

const TRACE_TYPE_LABELS = {
  service: 'Service', aggregate: 'Aggregate', command: 'Command',
  event: 'Event', policy: 'Policy', readModel: 'Read Model',
}
function traceTypeLabel(type) { return TRACE_TYPE_LABELS[type] || type }

// User Story ID → 원문 근거(문서 페이지·소제목·인용문). 사용자 시나리오 섹션에서
// "이 스토리가 문서 어디서 나왔는지" 를 보여주는 데 쓴다.
const storySourceById = computed(() => {
  const map = {}
  for (const st of (deliverable.value?.userScenario?.stories || [])) map[st.id] = st
  return map
})
function storySources(usId) { return storySourceById.value[usId]?.sources || [] }
function storySourceTask(usId) { return storySourceById.value[usId]?.sourceTask || null }

// ── Context Map (Mermaid) ──
mermaid.initialize({ startOnLoad: false, theme: 'base',
  themeVariables: { primaryColor:'#dbe4ff', primaryBorderColor:'#4c6ef5', primaryTextColor:'#1a1a2e', lineColor:'#868e96', fontSize:'13px', fontFamily:'Pretendard, sans-serif' },
  flowchart: { htmlLabels:true, curve:'basis', rankSpacing:60, nodeSpacing:40, padding:12 }, securityLevel:'loose' })

const contextMapRef = ref(null)
const contextMapDef = computed(() => {
  const bcs = sortedContexts.value
  if (!bcs.length || !crossBCPolicies.value.length) return ''
  const idMap = {}; bcs.forEach((bc, i) => { idMap[bcName(bc)] = `BC${i}` })
  let def = 'graph LR\n'
  def += '  classDef core fill:#dbe4ff,stroke:#4c6ef5,stroke-width:2px,color:#1a1a2e\n'
  def += '  classDef supporting fill:#fff3bf,stroke:#f08c00,stroke-width:2px,color:#1a1a2e\n'
  def += '  classDef generic fill:#f1f3f5,stroke:#adb5bd,stroke-width:2px,color:#1a1a2e\n'
  bcs.forEach(bc => {
    const name = bcName(bc), id = idMap[name], domain = bc.domainType||''
    def += `  ${id}["${name}<br/><small>${domain}</small>"]\n`
    def += `  class ${id} ${domain.includes('Core')?'core':domain.includes('Supporting')?'supporting':'generic'}\n`
  })
  const edgeMap = new Map()
  crossBCPolicies.value.forEach(rel => {
    const fid = idMap[rel.fromBC], tid = idMap[rel.toBC]; if (!fid||!tid) return
    const key = `${fid}-->${tid}`
    edgeMap.has(key) ? edgeMap.get(key).push(rel.policy) : edgeMap.set(key, [rel.policy])
  })
  edgeMap.forEach((labels, key) => {
    const [fid] = key.split('-->'), tid = key.split('-->')[1]
    def += `  ${fid} -->|"${labels.join('<br/>')}"| ${tid}\n`
  })
  return def
})

async function renderMermaid() {
  if (!contextMapDef.value) return
  await nextTick()
  const el = contextMapRef.value; if (!el) return
  try { const { svg } = await mermaid.render('ctx-map-' + Date.now(), contextMapDef.value); el.innerHTML = svg }
  catch (e) { console.error('[ExportDocument] mermaid error:', e) }
}
watch(contextMapDef, renderMermaid, { immediate: false })
watch(isLoading, (v) => { if (!v) renderMermaid() })

// ── Data helpers ──
function parseJsonFields(json) {
  if (!json) return []; try { const obj = typeof json === 'string' ? JSON.parse(json) : json; return Object.entries(obj).map(([k,v]) => ({ name:k, type: typeof v==='string'?v:JSON.stringify(v) })) } catch { return [] }
}
function getCommandsFromTree(tree) {
  const cmds = []; for (const a of (tree.aggregates||[])) { for (const c of (a.commands||[])) { cmds.push({ id:c.id, name:c.displayName||c.name, agg:a.displayName||a.name, actor:c.actor||'', events:(c.events||[]).map(e=>e.displayName||e.name), schema:parseJsonFields(c.inputSchema) }) } }; return cmds
}
function getReadModelsFromTree(tree) {
  return (tree.readmodels||[]).map(rm => ({ id:rm.id, name:rm.displayName||rm.name, desc:rm.description||'', pType:rm.provisioningType||'-', actor:rm.actor||'', isMultiple:rm.isMultipleResult||'', props:rm.properties||[], ops:rm.operations||[] }))
}
function bcTree(ctx) { return fullTrees.value[ctx.id] }
function bcName(ctx) { return fullTrees.value[ctx.id]?.displayName || ctx.name }
function allCmdsForCtx(ctx) {
  const t = bcTree(ctx); if (!t) return []
  const r = []; (t.aggregates||[]).forEach(a => (a.commands||[]).forEach(c => r.push({ ...c, aggName:a.displayName||a.name, schema:parseJsonFields(c.inputSchema) }))); return r
}
function allEvtsForCtx(ctx) {
  const t = bcTree(ctx); if (!t) return []
  const r = []; (t.aggregates||[]).forEach(a => (a.events||[]).forEach(e => r.push({ ...e, aggName:a.displayName||a.name, payloadFields:parseJsonFields(e.payload) }))); return r
}
function resolveNodeName(nodeId) {
  if (!nodeId) return '-'
  for (const [,tree] of Object.entries(fullTrees.value)) { for (const a of (tree.aggregates||[])) { for (const e of (a.events||[])) { if (e.id===nodeId) return e.displayName||e.name } for (const c of (a.commands||[])) { if (c.id===nodeId) return c.displayName||c.name; for (const e of (c.events||[])) { if (e.id===nodeId) return e.displayName||e.name } } } }
  return '-'
}
</script>

<template>
  <div class="doc">
    <div v-if="isLoading" class="loading-box"><div class="spinner-sm"></div><span>데이터를 불러오는 중...</span></div>

    <template v-if="!isLoading">
      <!-- Section selector -->
      <div class="section-selector no-print">
        <label v-for="(v,k) in selectedSections" :key="k" class="chk">
          <input type="checkbox" v-model="selectedSections[k]"/>
          <span>{{ SECTION_LABELS[k] }}</span>
        </label>
      </div>

      <!-- ═══ 메인 표지 (forced page) ═══ -->
      <div class="page page--main-cover">
        <div class="main-cover__brand">Robo Architect</div>
        <div class="main-cover__line"></div>
        <h1 class="main-cover__title">소프트웨어 아키텍처 설계서</h1>
        <p class="main-cover__sub">Event Storming 기반 설계 산출물</p>
        <div class="main-cover__stats">
          Bounded Context {{ allContexts.length }}개 &middot;
          Aggregate {{ Object.values(fullTrees).reduce((s,t)=>s+(t.aggregates?.length||0),0) }}개 &middot;
          User Story {{ allUserStories.length }}개
        </div>
        <div class="main-cover__date">{{ new Date().toLocaleDateString('ko-KR') }}</div>
      </div>

      <!-- ═══ 목차 (forced page) ═══ -->
      <div class="page page--toc">
        <h2 class="toc-heading">목 차</h2>
        <ol class="toc-list">
          <li v-if="selectedSections.userStories">{{ sectionNumbers.userStories }}. 사용자 스토리 종합</li>
          <li v-if="selectedSections.valueStream && valueStreamProcesses.length">{{ sectionNumbers.valueStream }}. 밸류 스트림 분석
            <ul><li v-for="p in valueStreamProcesses" :key="'toc-vs-'+p.id">{{ p.name }} <span class="toc-dim">[Task {{ p.taskCount }}]</span></li></ul>
          </li>
          <li v-if="selectedSections.boundedContext">{{ sectionNumbers.boundedContext }}. Bounded Context 정의
            <ul><li v-for="ctx in sortedContexts" :key="'toc-bc-'+ctx.id">{{ bcName(ctx) }} <span class="toc-dim">[{{ ctx.domainType }}]</span></li>
            <li v-if="crossBCPolicies.length">컨텍스트 간 연관 관계</li></ul>
          </li>
          <li v-if="selectedSections.modelOverview">{{ sectionNumbers.modelOverview }}. 이벤트 스토밍 모델 전반 정보
            <ul><li v-for="ctx in sortedContexts" :key="'toc-m-'+ctx.id">{{ bcName(ctx) }}</li></ul>
          </li>
          <li v-if="selectedSections.apiSpecification">{{ sectionNumbers.apiSpecification }}. API 명세 (Command / Read Model)</li>
          <li v-if="selectedSections.aggregateDetail">{{ sectionNumbers.aggregateDetail }}. Aggregate 상세</li>
          <li v-if="selectedSections.traceabilityMatrix && traceSummary">{{ sectionNumbers.traceabilityMatrix }}. 추적성 매트릭스</li>
        </ol>
      </div>

      <!-- ═══════ 1. 사용자 스토리 ═══════ -->
      <template v-if="selectedSections.userStories">
        <div class="page page--section-cover"><div class="sc__num">{{ sectionNumbers.userStories }}</div><div class="sc__title">사용자 스토리 종합</div><div class="sc__desc">시스템에 등록된 사용자 스토리를 Bounded Context 별로 정리합니다.</div></div>

        <div class="block">
          <h3>{{ sectionNumbers.userStories }}. 사용자 스토리 종합</h3>
          <p v-if="!allUserStories.length" class="empty-note">등록된 사용자 스토리가 없습니다.</p>
          <table v-if="allUserStories.length" class="tbl">
            <thead><tr><th style="width:120px">Bounded Context</th><th style="width:90px">As a</th><th>I want to</th><th>So that</th><th style="width:55px">우선순위</th><th style="width:50px">상태</th></tr></thead>
            <tbody><tr v-for="s in allUserStories" :key="s.id"><td>{{ s.bcName }}</td><td>{{ s.role||'-' }}</td><td>{{ s.action||s.name||'-' }}</td><td>{{ s.benefit||'-' }}</td><td class="c">{{ s.priority||'-' }}</td><td class="c">{{ s.status||'-' }}</td></tr></tbody>
          </table>
        </div>

        <!-- 원문 근거 — 정규화된 User Story 가 문서 어디에서 나왔는지 제시한다.
             (Session 스냅샷이 있을 때만) -->
        <div v-if="sessionScoped && allUserStories.some(s => storySources(s.id).length)" class="block">
          <h3>{{ sectionNumbers.userStories }}-1. 사용자 스토리 원문 근거</h3>
          <p class="desc">각 사용자 스토리가 업로드 문서의 어느 부분에서 도출됐는지 보여줍니다.</p>
          <table class="tbl">
            <thead><tr><th style="width:80px">US ID</th><th style="width:150px">업무 Task</th><th style="width:110px">문서 위치</th><th>원문 근거</th></tr></thead>
            <tbody>
              <template v-for="s in allUserStories" :key="'src-'+s.id">
                <tr v-for="(src,si) in storySources(s.id)" :key="'src-'+s.id+'-'+si">
                  <td class="b">{{ si === 0 ? s.id : '' }}</td>
                  <td>{{ si === 0 ? (storySourceTask(s.id)?.name || '-') : '' }}</td>
                  <td>
                    <span v-if="src.page">p.{{ src.page }}</span>
                    <div v-if="src.heading" class="toc-dim">{{ src.heading }}</div>
                    <div v-if="si === 0 && storySourceTask(s.id)?.sourceSection" class="toc-dim">{{ storySourceTask(s.id).sourceSection }}</div>
                  </td>
                  <td class="desc-cell">{{ src.text }}</td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </template>

      <!-- ═══════ 밸류 스트림 분석 ═══════ -->
      <template v-if="selectedSections.valueStream && valueStreamProcesses.length">
        <div class="page page--section-cover"><div class="sc__num">{{ sectionNumbers.valueStream }}</div><div class="sc__title">밸류 스트림 분석</div><div class="sc__desc">업로드 문서에서 도출한 업무 프로세스를 Actor 흐름으로 정리하고, 각 단계가 어떤 사용자 스토리로 승격됐는지 연결합니다.</div></div>

        <div v-for="(proc,pi) in valueStreamProcesses" :key="'vs-'+proc.id" class="block">
          <h3>{{ sectionNumbers.valueStream }}-{{ pi+1 }}. {{ proc.name }}</h3>
          <p v-if="proc.description" class="desc">{{ proc.description }}</p>
          <p v-if="proc.actors.length" class="desc"><strong>참여 Actor</strong> · {{ proc.actors.join(', ') }}</p>

          <!-- 선형 흐름 요약 (기준 템플릿의 value-stream-flow-card 대응) -->
          <div v-for="(path,idx) in proc.linearPaths" :key="'vsp-'+idx" class="vs-flow">
            <span v-for="(step,si) in path" :key="step.name">
              {{ step.displayName }}<span v-if="step.actor"> ({{ step.actor }})</span><span v-if="si < path.length-1"> → </span>
            </span>
          </div>

          <table class="tbl">
            <thead><tr><th class="c" style="width:40px">순서</th><th style="width:150px">Task</th><th style="width:110px">Actor</th><th>설명</th><th style="width:130px">승격된 User Story</th></tr></thead>
            <tbody>
              <tr v-for="(step,si) in (proc.linearPaths[0]||[])" :key="'vst-'+step.name">
                <td class="c">{{ si+1 }}</td>
                <td class="b">{{ step.displayName }}</td>
                <td>{{ step.actor||'-' }}</td>
                <td class="desc-cell">{{ step.description||'-' }}
                  <div v-if="step.sourceSection" class="toc-dim">{{ step.sourceSection }}</div>
                </td>
                <td>
                  <span v-if="!step.promotedTo.length" class="toc-dim">미승격</span>
                  <div v-for="us in step.promotedTo" :key="us.id"><span class="tag tag--cmd">{{ us.id }}</span></div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="glossaryTerms.length" class="block">
          <h3>{{ sectionNumbers.valueStream }}-{{ valueStreamProcesses.length+1 }}. 도메인 용어집</h3>
          <table class="tbl">
            <thead><tr><th style="width:160px">용어</th><th>설명</th></tr></thead>
            <tbody><tr v-for="(g,gi) in glossaryTerms" :key="'gl-'+gi"><td class="b">{{ g.term||g.name||'-' }}</td><td class="desc-cell">{{ g.definition||g.description||'-' }}</td></tr></tbody>
          </table>
        </div>
      </template>

      <!-- ═══════ 2. Bounded Context ═══════ -->
      <template v-if="selectedSections.boundedContext">
        <div class="page page--section-cover"><div class="sc__num">{{ sectionNumbers.boundedContext }}</div><div class="sc__title">Bounded Context 정의</div><div class="sc__desc">도메인을 구성하는 Bounded Context의 역할, 구성 요소, 상호 관계를 정의합니다.</div></div>

        <!-- 요약 -->
        <div class="block">
          <h3>{{ sectionNumbers.boundedContext }}. Bounded Context 요약</h3>
          <table class="tbl">
            <thead><tr><th>Bounded Context</th><th>도메인 유형</th><th>설명</th><th class="c" style="width:50px">Agg</th><th class="c" style="width:50px">Cmd</th><th class="c" style="width:50px">Evt</th><th class="c" style="width:50px">RM</th><th class="c" style="width:40px">US</th></tr></thead>
            <tbody><tr v-for="ctx in sortedContexts" :key="ctx.id">
              <td class="b">{{ bcName(ctx) }}</td>
              <td><span class="dom" :class="'dom--'+((ctx.domainType||'').replace(/\s/g,''))">{{ ctx.domainType||'-' }}</span></td>
              <td class="desc-cell">{{ ctx.description||bcTree(ctx)?.description||'-' }}</td>
              <td class="c">{{ bcTree(ctx)?.aggregates?.length||0 }}</td>
              <td class="c">{{ bcTree(ctx)?.aggregates?.reduce((s,a)=>s+(a.commands?.length||0),0)||0 }}</td>
              <td class="c">{{ bcTree(ctx)?.aggregates?.reduce((s,a)=>s+(a.events?.length||0),0)||0 }}</td>
              <td class="c">{{ bcTree(ctx)?.readmodels?.length||0 }}</td>
              <td class="c">{{ bcTree(ctx)?.userStories?.length||0 }}</td>
            </tr></tbody>
          </table>
        </div>

        <!-- BC 상세 -->
        <div v-for="(ctx,ci) in sortedContexts" :key="'bcd-'+ctx.id" class="block">
          <h3>{{ sectionNumbers.boundedContext }}-{{ ci+1 }}. {{ bcName(ctx) }}
            <span class="dom dom--inline" :class="'dom--'+((ctx.domainType||'').replace(/\s/g,''))">{{ ctx.domainType }}</span>
          </h3>
          <p v-if="ctx.description||bcTree(ctx)?.description" class="desc">{{ ctx.description||bcTree(ctx)?.description }}</p>
          <div class="bc-element-list">
            <div v-if="bcTree(ctx)?.aggregates?.length" class="bc-el"><strong>Aggregate</strong><span>{{ bcTree(ctx).aggregates.map(a=>a.displayName||a.name).join(', ') }}</span></div>
            <div v-if="bcTree(ctx)?.policies?.filter(p=>p.name).length" class="bc-el"><strong>Policy</strong><span>{{ bcTree(ctx).policies.filter(p=>p.name).map(p=>p.displayName||p.name).join(', ') }}</span></div>
            <div v-if="bcTree(ctx)?.readmodels?.length" class="bc-el"><strong>Read Model</strong><span>{{ bcTree(ctx).readmodels.map(r=>r.displayName||r.name).join(', ') }}</span></div>
            <div v-if="bcTree(ctx)?.uis?.length" class="bc-el"><strong>UI</strong><span>{{ bcTree(ctx).uis.map(u=>u.displayName||u.name).join(', ') }}</span></div>
          </div>
        </div>

        <!-- Cross-BC Policy -->
        <template v-if="crossBCPolicies.length">
          <div v-if="contextMapDef" class="block">
            <h3>{{ sectionNumbers.boundedContext }}-{{ sortedContexts.length+1 }}. 컨텍스트 간 연관 관계</h3>
            <p class="desc">서로 다른 Bounded Context 간 이벤트-Policy-커맨드 연결을 도식화합니다.</p>
            <div ref="contextMapRef" class="ctx-map-wrap"></div>
          </div>
          <div class="block">
            <h3>컨텍스트 간 연관 관계 상세</h3>
            <table class="tbl"><thead><tr><th>발행 BC</th><th>Event</th><th>Policy</th><th>수신 BC</th><th>Command</th></tr></thead>
              <tbody><tr v-for="(r,i) in crossBCPolicies" :key="i"><td class="b">{{ r.fromBC }}</td><td><span class="tag tag--event">{{ r.fromEvent }}</span></td><td>{{ r.policy }}</td><td class="b">{{ r.toBC }}</td><td><span class="tag tag--cmd">{{ r.toCommand }}</span></td></tr></tbody>
            </table>
          </div>
        </template>
      </template>

      <!-- ═══════ 3. 모델 전반 정보 ═══════ -->
      <template v-if="selectedSections.modelOverview">
        <div class="page page--section-cover"><div class="sc__num">{{ sectionNumbers.modelOverview }}</div><div class="sc__title">이벤트 스토밍 모델 전반 정보</div><div class="sc__desc">각 Bounded Context의 Command, Event, Policy, Read Model 구성 요소를 정리합니다.</div></div>

        <!-- Big Picture -->
        <div v-if="swimlanes.length" class="block">
          <h3>{{ sectionNumbers.modelOverview }}-1. 이벤트 흐름 요약</h3>
          <div v-for="lane in swimlanes" :key="lane.bcId" class="flow-lane">
            <h4>{{ lane.bcName }}</h4>
            <div class="flow-events">
              <template v-for="(evt,idx) in lane.events" :key="evt.id">
                <span class="flow-chip">{{ evt.name }}<em v-if="evt.actor"> ({{ evt.actor }})</em></span>
                <span v-if="idx < lane.events.length-1" class="flow-arrow">&rarr;</span>
              </template>
            </div>
          </div>
        </div>

        <!-- Per-BC -->
        <template v-for="(ctx,ci) in sortedContexts" :key="'mo-'+ctx.id">
          <!-- Aggregate -->
          <div v-if="bcTree(ctx)?.aggregates?.length" class="block">
            <h3>{{ bcName(ctx) }} - Aggregate</h3>
            <div v-for="a in bcTree(ctx).aggregates" :key="a.id" class="agg-summary">
              <h4>{{ a.displayName||a.name }} <span v-if="a.rootEntity" class="dim">(Root: {{ a.rootEntity }})</span></h4>
              <div v-if="a.invariants?.length" class="invariants"><strong>비즈니스 규칙 (Invariants)</strong><ul><li v-for="(inv,ii) in a.invariants" :key="ii">{{ inv }}</li></ul></div>
            </div>
          </div>

          <!-- Command -->
          <div v-if="allCmdsForCtx(ctx).length" class="block">
            <h3>{{ bcName(ctx) }} - Command</h3>
            <table class="tbl tbl--sm"><thead><tr><th style="width:140px">이름</th><th style="width:110px">Aggregate</th><th style="width:70px">Actor</th><th>Input Schema</th><th style="width:140px">발생 Event</th></tr></thead>
              <tbody><tr v-for="c in allCmdsForCtx(ctx)" :key="c.id"><td class="b">{{ c.displayName||c.name }}</td><td>{{ c.aggName }}</td><td>{{ c.actor||'-' }}</td><td><div v-for="s in c.schema" :key="s.name" class="prop-line">{{ s.name }} <span class="prop-type">{{ s.type }}</span></div><span v-if="!c.schema?.length">-</span></td><td><span v-for="ev in (c.events||[])" :key="ev.id" class="tag tag--event">{{ ev.displayName||ev.name }}</span><span v-if="!(c.events||[]).length">-</span></td></tr></tbody>
            </table>
          </div>

          <!-- Event -->
          <div v-if="allEvtsForCtx(ctx).length" class="block">
            <h3>{{ bcName(ctx) }} - Event</h3>
            <table class="tbl tbl--sm"><thead><tr><th style="width:160px">이름</th><th style="width:120px">Aggregate</th><th style="width:70px">Version</th><th>Payload</th></tr></thead>
              <tbody><tr v-for="e in allEvtsForCtx(ctx)" :key="e.id"><td class="b">{{ e.displayName||e.name }}</td><td>{{ e.aggName }}</td><td>{{ e.version||'-' }}</td><td><div v-for="f in e.payloadFields" :key="f.name" class="prop-line">{{ f.name }} <span class="prop-type">{{ f.type }}</span></div><span v-if="!e.payloadFields?.length">-</span></td></tr></tbody>
            </table>
          </div>

          <!-- Policy -->
          <div v-if="bcTree(ctx)?.policies?.filter(p=>p.name).length" class="block">
            <h3>{{ bcName(ctx) }} - Policy</h3>
            <table class="tbl tbl--sm"><thead><tr><th style="width:140px">이름</th><th style="width:140px">Trigger Event</th><th style="width:140px">Invoke Command</th><th>설명</th></tr></thead>
              <tbody><tr v-for="p in bcTree(ctx).policies.filter(p=>p.name)" :key="p.id"><td class="b">{{ p.displayName||p.name }}</td><td><span v-if="p.triggerEventId" class="tag tag--event">{{ resolveNodeName(p.triggerEventId) }}</span><span v-else>-</span></td><td><span v-if="p.invokeCommandId" class="tag tag--cmd">{{ resolveNodeName(p.invokeCommandId) }}</span><span v-else>-</span></td><td class="desc-cell">{{ p.description||'-' }}</td></tr></tbody>
            </table>
          </div>

          <!-- ReadModel -->
          <div v-if="bcTree(ctx)?.readmodels?.length" class="block">
            <h3>{{ bcName(ctx) }} - Read Model</h3>
            <table class="tbl tbl--sm"><thead><tr><th style="width:130px">이름</th><th style="width:70px">유형</th><th style="width:70px">Actor</th><th style="width:80px">결과</th><th>설명</th></tr></thead>
              <tbody><tr v-for="r in bcTree(ctx).readmodels" :key="r.id"><td class="b">{{ r.displayName||r.name }}</td><td>{{ r.provisioningType||'-' }}</td><td>{{ r.actor||'-' }}</td><td>{{ r.isMultipleResult||'-' }}</td><td class="desc-cell">{{ r.description||'-' }}</td></tr></tbody>
            </table>
          </div>

          <!-- Edge relations -->
          <div v-if="getEdgeRelationsForBC(ctx.id).length" class="block">
            <h4>{{ bcName(ctx) }} - 이벤트 흐름 관계</h4>
            <table class="tbl tbl--sm"><thead><tr><th>소스</th><th>타입</th><th>관계</th><th>대상</th><th>타입</th></tr></thead>
              <tbody><tr v-for="(r,ri) in getEdgeRelationsForBC(ctx.id)" :key="ri"><td>{{ r.sn }}</td><td><span class="badge" :class="'badge--'+r.st">{{ r.st }}</span></td><td class="c">{{ r.edgeType }}</td><td>{{ r.tn }}</td><td><span class="badge" :class="'badge--'+r.tt">{{ r.tt }}</span></td></tr></tbody>
            </table>
          </div>
        </template>
      </template>

      <!-- ═══════ 4. API 명세 ═══════ -->
      <template v-if="selectedSections.apiSpecification">
        <div class="page page--section-cover"><div class="sc__num">{{ sectionNumbers.apiSpecification }}</div><div class="sc__title">API 명세</div><div class="sc__desc">이벤트 스토밍 모델에서 도출된 Command 및 Read Model의 상세 정보입니다.</div></div>

        <!-- 도출된 Endpoint 계약 — 기준 템플릿의 API 명세 열(경로/메서드/Command/설명/파라미터)을 채운다.
             Command 의 category 와 Aggregate 이름으로 규칙 도출하므로 재실행해도 같은 결과가 나온다. -->
        <template v-if="apiSummary">
          <div class="block">
            <h3>{{ sectionNumbers.apiSpecification }}. Endpoint 계약 요약</h3>
            <p class="desc">{{ apiConvention }}</p>
            <table class="tbl">
              <thead><tr><th>Command</th><th>제공 API</th><th>외부 연동</th><th>조회 API</th><th>파라미터 없음</th><th>경로 충돌 조정</th></tr></thead>
              <tbody><tr>
                <td class="c">{{ apiSummary.commands }}</td>
                <td class="c">{{ apiSummary.inboundCommands }}</td>
                <td class="c">{{ apiSummary.outboundCommands }}</td>
                <td class="c">{{ apiSummary.queries }}</td>
                <td class="c">{{ apiSummary.commandsWithoutParameters }}</td>
                <td class="c">{{ apiSummary.pathCollisionsResolved }}</td>
              </tr></tbody>
            </table>
          </div>

          <template v-for="ctx in sortedContexts" :key="'ep-'+ctx.id">
            <div v-if="apiForCtx(ctx)?.commandEndpoints?.length" class="block">
              <h3>{{ bcName(ctx) }} - Command API</h3>
              <table class="tbl">
                <thead><tr><th style="width:200px">API 경로</th><th style="width:60px">메서드</th><th style="width:130px">Command</th><th>설명</th><th style="width:170px">요청 파라미터</th></tr></thead>
                <tbody><tr v-for="e in apiForCtx(ctx).commandEndpoints" :key="e.commandId">
                  <td class="prop-line">
                    <span v-if="e.direction === 'inbound'">{{ e.path }}</span>
                    <span v-else class="toc-dim">제공 API 아님 (외부 연동 호출)</span>
                  </td>
                  <td class="c"><span v-if="e.method" class="tag tag--cmd">{{ e.method }}</span><span v-else>-</span></td>
                  <td class="b">{{ e.commandDisplayName }}<div class="prop-type">{{ e.category }}</div></td>
                  <td class="desc-cell">{{ e.description||'-' }}
                    <div v-if="e.emits.length" class="toc-dim">→ {{ e.emits.join(', ') }}</div>
                  </td>
                  <td>
                    <div v-for="prm in e.parameters" :key="prm.name" class="prop-line">
                      {{ prm.name }} <span class="prop-type">{{ prm.type }}</span><span v-if="prm.required" class="req">*</span>
                    </div>
                    <span v-if="!e.parameters.length">-</span>
                  </td>
                </tr></tbody>
              </table>
            </div>

            <div v-if="apiForCtx(ctx)?.queryEndpoints?.length" class="block">
              <h3>{{ bcName(ctx) }} - Query API</h3>
              <table class="tbl">
                <thead><tr><th style="width:200px">API 경로</th><th style="width:60px">메서드</th><th style="width:130px">Read Model</th><th>설명</th><th style="width:60px">결과</th></tr></thead>
                <tbody><tr v-for="q in apiForCtx(ctx).queryEndpoints" :key="q.readModelId">
                  <td class="prop-line">{{ q.path }}</td>
                  <td class="c"><span class="tag tag--rm">{{ q.method }}</span></td>
                  <td class="b">{{ q.readModelDisplayName }}</td>
                  <td class="desc-cell">{{ q.description||'-' }}</td>
                  <td class="c">{{ q.resultType }}</td>
                </tr></tbody>
              </table>
            </div>
          </template>
        </template>

        <template v-for="(ctx,ci) in sortedContexts" :key="'api-'+ctx.id">
          <template v-if="bcTree(ctx)">
            <!-- Commands -->
            <div v-if="getCommandsFromTree(bcTree(ctx)).length" class="block">
              <h3>{{ bcName(ctx) }} - Command</h3>
              <table class="tbl"><thead><tr><th style="width:120px">Command</th><th style="width:80px">Aggregate</th><th style="width:70px">Actor</th><th style="width:180px">Input Schema</th><th style="width:120px">발생 Event</th></tr></thead>
                <tbody><tr v-for="c in getCommandsFromTree(bcTree(ctx))" :key="c.id">
                  <td class="b">{{ c.name }}</td><td>{{ c.agg }}</td><td>{{ c.actor||'-' }}</td>
                  <td><div v-for="s in c.schema" :key="s.name" class="prop-line">{{ s.name }} <span class="prop-type">{{ s.type }}</span></div><span v-if="!c.schema.length">-</span></td>
                  <td><span v-for="(ev,i) in c.events" :key="i" class="tag tag--event">{{ ev }}</span><span v-if="!c.events.length">-</span></td>
                </tr></tbody>
              </table>
            </div>

            <!-- ReadModels -->
            <div v-for="rm in getReadModelsFromTree(bcTree(ctx))" :key="rm.id" class="block">
              <h3 v-if="getReadModelsFromTree(bcTree(ctx)).indexOf(rm)===0">{{ bcName(ctx) }} - Read Model</h3>
              <div class="rm-card">
                <div class="rm-header"><strong>{{ rm.name }}</strong><span v-if="rm.pType!=='-'" class="tag tag--rm">{{ rm.pType }}</span><span v-if="rm.actor" class="dim" style="margin-left:8px">Actor: {{ rm.actor }}</span><span v-if="rm.isMultiple" class="dim" style="margin-left:8px">{{ rm.isMultiple }}</span></div>
                <p v-if="rm.desc" class="desc">{{ rm.desc }}</p>
                <div v-if="rm.props.length" class="sub">
                  <h5>속성</h5>
                  <table class="tbl tbl--sm"><thead><tr><th>이름</th><th>타입</th><th>Key</th></tr></thead>
                    <tbody><tr v-for="p in rm.props" :key="p.name||p.id"><td>{{ p.name }}</td><td>{{ p.type||p.dataType||'String' }}</td><td class="c">{{ p.isKey?'Y':'' }}</td></tr></tbody>
                  </table>
                </div>
                <div v-if="rm.ops.length" class="sub">
                  <h5>CQRS Operations</h5>
                  <table class="tbl tbl--sm"><thead><tr><th>Operation</th><th>Trigger Event</th></tr></thead>
                    <tbody><tr v-for="o in rm.ops" :key="o.id"><td>{{ o.operationType||o.operation_type||'-' }}</td><td>{{ o.triggerEventName||'-' }}</td></tr></tbody>
                  </table>
                </div>
              </div>
            </div>
          </template>
        </template>
      </template>

      <!-- ═══════ 5. Aggregate 상세 ═══════ -->
      <template v-if="selectedSections.aggregateDetail">
        <div class="page page--section-cover"><div class="sc__num">{{ sectionNumbers.aggregateDetail }}</div><div class="sc__title">Aggregate 상세</div><div class="sc__desc">각 Aggregate의 속성, Enumeration, Value Object 구조를 정리합니다.</div></div>

        <template v-for="(ctx,ci) in sortedContexts" :key="'ad-'+ctx.id">
          <template v-if="bcTree(ctx)?.aggregates?.length">
            <div v-for="(agg,ai) in bcTree(ctx).aggregates" :key="'ad-a-'+agg.id" class="block">
              <h3>{{ bcName(ctx) }} / {{ agg.displayName||agg.name }}</h3>
              <p v-if="agg.rootEntity" class="meta-line">Root Entity: <strong>{{ agg.rootEntity }}</strong></p>

              <div v-if="agg.properties?.length" class="sub">
                <h4>속성 (Properties)</h4>
                <table class="tbl tbl--sm"><thead><tr><th style="width:140px">필드명</th><th style="width:100px">타입</th><th style="width:36px">Key</th><th style="width:36px">FK</th><th>설명</th></tr></thead>
                  <tbody><tr v-for="p in agg.properties" :key="p.id||p.name"><td class="b">{{ p.name }}</td><td>{{ p.type||p.dataType||'String' }}</td><td class="c">{{ p.isKey?'Y':'' }}</td><td class="c">{{ p.isForeignKey?'Y':'' }}</td><td>{{ p.description||'-' }}</td></tr></tbody>
                </table>
              </div>

              <div v-if="agg.enumerations?.length" class="sub">
                <h4>Enumeration</h4>
                <div v-for="en in agg.enumerations" :key="en.id||en.name" class="enum-item">
                  <strong>{{ en.displayName||en.name }}</strong>
                  <span v-if="en.items?.length" class="enum-vals">{{ en.items.map(i=>typeof i==='string'?i:(i.value||i.name||i)).join(', ') }}</span>
                  <span v-else-if="en.values?.length" class="enum-vals">{{ en.values.map(v=>typeof v==='string'?v:(v.value||v.name||v)).join(', ') }}</span>
                </div>
              </div>

              <div v-if="agg.valueObjects?.length" class="sub">
                <h4>Value Object</h4>
                <div v-for="vo in agg.valueObjects" :key="vo.id||vo.name" class="vo-item">
                  <strong>{{ vo.name }}</strong>
                  <table v-if="(vo.properties||vo.fields||[]).length" class="tbl tbl--sm tbl--nested"><thead><tr><th>필드명</th><th>타입</th></tr></thead>
                    <tbody><tr v-for="vp in (vo.properties||vo.fields||[])" :key="vp.name||vp.id"><td>{{ vp.name }}</td><td>{{ vp.type||vp.dataType||'String' }}</td></tr></tbody>
                  </table>
                </div>
              </div>
            </div>
          </template>
        </template>
      </template>

      <!-- ═══════ 추적성 매트릭스 ═══════ -->
      <template v-if="selectedSections.traceabilityMatrix && traceSummary">
        <div class="page page--section-cover"><div class="sc__num">{{ sectionNumbers.traceabilityMatrix }}</div><div class="sc__title">추적성 매트릭스</div><div class="sc__desc">사용자 스토리별로 매핑된 이벤트 스토밍 요소(Service / Aggregate / Command / Event / Policy / Read Model)를 보여줍니다.</div></div>

        <div class="block">
          <h3>{{ sectionNumbers.traceabilityMatrix }}. 추적성 요약</h3>
          <table class="tbl">
            <thead><tr><th>전체 요소</th><th>직접 매핑</th><th>추론 매핑</th><th>미매핑</th><th>매핑된 User Story</th><th>직접 매핑률</th></tr></thead>
            <tbody><tr>
              <td class="c">{{ traceSummary.elements }}</td>
              <td class="c">{{ traceSummary.directElements }}</td>
              <td class="c">{{ traceSummary.inferredElements }}</td>
              <td class="c">{{ traceSummary.unmappedElements }}</td>
              <td class="c">{{ traceSummary.mappedUserStories }}</td>
              <td class="c">{{ (traceSummary.directRatio * 100).toFixed(1) }}%</td>
            </tr></tbody>
          </table>
        </div>

        <!-- US 별 그룹: 기준 템플릿과 동일하게 좁은 3 컬럼(유형/이름/ID) 표로 나눈다.
             12 컬럼 매트릭스는 문서 폭에서 잘리기 때문. -->
        <div v-for="g in traceGroups" :key="'tg-'+g.us.id" class="block">
          <h3>{{ g.us.id }} <span class="trace-us-name">{{ g.us.name }}</span></h3>
          <table class="tbl tbl--sm">
            <thead><tr><th style="width:90px">유형</th><th>이름</th><th style="width:30%">ID</th></tr></thead>
            <tbody><tr v-for="(r,i) in g.rows" :key="'tr-'+g.us.id+'-'+i">
              <td><span class="badge" :class="'badge--'+r.type.toLowerCase()">{{ traceTypeLabel(r.type) }}</span></td>
              <td>
                <div class="b">{{ r.name||'-' }}</div>
                <div v-if="r.technical && r.technical !== r.name" class="prop-type">{{ r.technical }}</div>
                <div v-if="r.parent" class="toc-dim">↳ {{ r.parent }}</div>
              </td>
              <td class="prop-type">{{ r.id||'-' }}</td>
            </tr></tbody>
          </table>
        </div>

        <!-- 추론 매핑: 직접 근거 없이 상위 Aggregate 매핑을 상속한 요소.
             직접 매핑과 섞으면 한 요소가 BC 의 모든 스토리에 붙은 것처럼 보이므로 분리한다. -->
        <div v-if="traceInferred.length" class="block">
          <h3>추론 매핑 <span class="toc-dim">({{ traceInferred.length }}) — 직접 근거 없이 상위 Aggregate 의 매핑을 상속한 요소</span></h3>
          <table class="tbl tbl--sm">
            <thead><tr><th style="width:90px">유형</th><th>이름</th><th style="width:28%">추론된 User Story</th></tr></thead>
            <tbody><tr v-for="(r,i) in traceInferred" :key="'ti-'+i">
              <td><span class="badge" :class="'badge--'+r.type.toLowerCase()">{{ traceTypeLabel(r.type) }}</span></td>
              <td><div class="b">{{ r.name||'-' }}</div><div v-if="r.parent" class="toc-dim">↳ {{ r.parent }}</div></td>
              <td class="prop-type">{{ r.inferredUs||'-' }}</td>
            </tr></tbody>
          </table>
        </div>

        <!-- 미매핑: 근거를 찾지 못한 요소는 임의로 붙이지 않고 그대로 남긴다. -->
        <div v-if="traceUnmapped.length" class="block">
          <h3>미매핑 요소 <span class="toc-dim">({{ traceUnmapped.length }}) — 어느 사용자 스토리와도 연결되지 않은 요소</span></h3>
          <table class="tbl tbl--sm">
            <thead><tr><th style="width:90px">유형</th><th>이름</th><th style="width:30%">ID</th></tr></thead>
            <tbody><tr v-for="(r,i) in traceUnmapped" :key="'tu-'+i">
              <td><span class="badge" :class="'badge--'+r.type.toLowerCase()">{{ traceTypeLabel(r.type) }}</span></td>
              <td><div class="b">{{ r.name||'-' }}</div><div v-if="r.parent" class="toc-dim">↳ {{ r.parent }}</div></td>
              <td class="prop-type">{{ r.id||'-' }}</td>
            </tr></tbody>
          </table>
        </div>
      </template>

    </template>
  </div>
</template>

<style scoped>
.doc { font-family:'Pretendard',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; color:#1a1a2e; line-height:1.65; font-size:13px; }
.loading-box { display:flex; align-items:center; gap:10px; padding:32px; justify-content:center; color:#6c757d; }
.spinner-sm { width:20px; height:20px; border:2px solid #dee2e6; border-top-color:#228be6; border-radius:50%; animation:spin .7s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }

.section-selector { display:flex; flex-wrap:wrap; gap:16px; padding:14px 20px; background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px; margin-bottom:20px; }
.chk { display:flex; align-items:center; gap:6px; font-size:13px; color:#495057; cursor:pointer; user-select:none; }
.chk input[type="checkbox"] { accent-color:#228be6; }

/* ── Forced full-page (covers, TOC) ── */
.page { background:#fff; border:1px solid #dee2e6; border-radius:8px; padding:28px 32px; margin-bottom:16px; }

/* ── Content block (flows naturally, avoids internal break) ── */
.block { background:#fff; border:1px solid #dee2e6; border-radius:8px; padding:24px 28px; margin-bottom:12px; }

/* Main Cover */
.page--main-cover { text-align:center; padding:100px 40px 60px; background:#fff; }
.main-cover__brand { font-size:16px; font-weight:700; letter-spacing:4px; text-transform:uppercase; color:#228be6; margin-bottom:16px; }
.main-cover__line { width:60px; height:3px; background:#228be6; margin:0 auto 40px; }
.main-cover__title { font-size:32px; font-weight:800; color:#1a1a2e; margin:0 0 12px; letter-spacing:-0.5px; }
.main-cover__sub { font-size:16px; color:#495057; margin:0 0 48px; font-weight:400; }
.main-cover__stats { font-size:13px; color:#868e96; margin-bottom:8px; }
.main-cover__date { font-size:13px; color:#adb5bd; }

/* Section Cover */
.page--section-cover { padding:60px 40px 50px; text-align:center; background:linear-gradient(135deg,#f8f9fa,#e9ecef); }
.sc__num { font-size:56px; font-weight:800; color:#228be6; line-height:1; margin-bottom:12px; }
.sc__title { font-size:24px; font-weight:700; color:#1a1a2e; margin-bottom:10px; }
.sc__desc { font-size:14px; color:#6c757d; max-width:500px; margin:0 auto; }

/* TOC */
.page--toc { padding:28px 36px; }
.toc-heading { font-size:20px; margin:0 0 14px; color:#1a1a2e; }
.toc-list { padding-left:0; list-style:none; }
.toc-list > li { font-size:14px; font-weight:600; padding:5px 0; border-bottom:1px dotted #dee2e6; }
.toc-list ul { list-style:none; padding-left:22px; margin:3px 0; }
.toc-list ul li { font-weight:400; font-size:12.5px; color:#495057; border-bottom:none; padding:1px 0; }
.toc-dim { font-weight:400; font-size:11px; color:#868e96; margin-left:4px; }

/* Headings */
.doc h2 { font-size:20px; font-weight:700; color:#1a1a2e; border-bottom:2px solid #228be6; padding-bottom:6px; margin:0 0 14px; }
.doc h3 { font-size:16px; font-weight:600; color:#16213e; margin:0 0 10px; }
.doc h4 { font-size:13.5px; font-weight:600; color:#495057; margin:14px 0 6px; }
.doc h5 { font-size:12.5px; font-weight:600; color:#6c757d; margin:10px 0 4px; }
.desc { font-size:13px; color:#6c757d; margin:0 0 12px; }
.desc-cell { font-size:12px; color:#6c757d; max-width:240px; }
.meta-line { font-size:13px; color:#495057; margin:4px 0 12px; }
.empty-note { color:#adb5bd; font-style:italic; }
.sub { margin-bottom:14px; }
.dim { font-weight:400; font-size:12px; color:#868e96; }
.agg-summary { margin-bottom:14px; }
.invariants { margin-top:6px; font-size:12.5px; }
.invariants strong { font-size:12px; color:#495057; }
.invariants ul { margin:4px 0 0; padding-left:18px; }
.invariants li { padding:2px 0; color:#495057; line-height:1.5; }
.bc-element-list { margin-top:12px; }
.bc-el { font-size:12.5px; padding:4px 0; display:flex; gap:8px; }
.bc-el strong { min-width:90px; color:#495057; flex-shrink:0; }
.bc-el span { color:#343a40; }

/* Mermaid */
.ctx-map-wrap { overflow-x:auto; margin:16px 0; text-align:center; }
.ctx-map-wrap :deep(svg) { max-width:100%; height:auto; }

/* Domain */
.dom { display:inline-block; font-size:11px; padding:2px 8px; border-radius:4px; font-weight:500; }
.dom--inline { margin-left:6px; vertical-align:middle; }
.dom--CoreDomain { background:#dbe4ff; color:#364fc7; }
.dom--SupportingDomain { background:#fff3bf; color:#e67700; }
.dom--GenericDomain { background:#e9ecef; color:#495057; }

/* Tables */
.tbl { width:100%; border-collapse:collapse; font-size:12.5px; margin:6px 0 14px; }
.tbl th { background:#f1f3f5; color:#495057; font-weight:600; text-align:left; padding:7px 10px; border:1px solid #dee2e6; white-space:nowrap; }
.tbl td { padding:6px 10px; border:1px solid #dee2e6; vertical-align:top; word-break:keep-all; }
.tbl td:first-child { min-width:100px; }
.tbl tbody tr:hover { background:#f8f9fa; }
.tbl--sm th { padding:5px 8px; font-size:12px; }
.tbl--sm td { padding:4px 8px; font-size:12px; }
.tbl--nested { margin:6px 0 2px; font-size:11.5px; }
.tbl--nested th { background:#f8f9fa; }
.c { text-align:center; }
.b { font-weight:600; }

/* Tags */
.badge { display:inline-block; font-size:10.5px; padding:1px 5px; border-radius:3px; font-weight:500; }
.badge--command { background:#dbe4ff; color:#364fc7; }
.badge--event { background:#fff3bf; color:#e67700; }
.badge--policy { background:#fff9db; color:#f08c00; }
.badge--aggregate { background:#e5dbff; color:#6741d9; }
.badge--readmodel { background:#d3f9d8; color:#2b8a3e; }
.tag { display:inline-block; font-size:11px; padding:1px 6px; border-radius:3px; margin:1px 2px; }
.tag--event { background:#fff3bf; color:#e67700; }
.tag--cmd { background:#dbe4ff; color:#364fc7; }
.tag--rm { background:#d3f9d8; color:#2b8a3e; }
.vs-flow { background:#f8f9fa; border:1px solid #dee2e6; border-radius:6px; padding:10px 12px; margin:8px 0 12px; font-size:12.5px; line-height:1.9; }
.trace-us-name { font-size:13px; font-weight:400; color:#6c757d; margin-left:6px; }
.badge--service { background:#e7f5ff; color:#1971c2; }
.badge--command { background:#dbe4ff; color:#364fc7; }
.badge--readmodel { background:#d3f9d8; color:#2b8a3e; }
.req { color:#e03131; font-weight:700; margin-left:2px; }
.prop-line { line-height:1.6; }
.prop-type { color:#868e96; font-size:11px; margin-left:2px; }
.prop-type::before { content:'('; }
.prop-type::after { content:')'; }

/* RM card */
.rm-card { border:1px solid #e9ecef; border-radius:6px; padding:14px 16px; margin-bottom:12px; }
.rm-header { margin-bottom:6px; }

/* Flow */
.flow-lane { margin-bottom:14px; }
.flow-events { display:flex; flex-wrap:wrap; align-items:center; gap:4px; }
.flow-chip { font-size:12.5px; color:#343a40; }
.flow-chip em { font-size:11px; color:#868e96; font-style:normal; }
.flow-arrow { color:#adb5bd; margin:0 2px; }

/* Enum/VO */
.enum-item,.vo-item { font-size:12.5px; padding:3px 0; }
.enum-vals { color:#6c757d; margin-left:6px; }
.enum-vals::before { content:'[ '; }
.enum-vals::after { content:' ]'; }

/* ── Print / Export ── */
@media print {
  .no-print { display:none !important; }
  /* Covers & TOC: forced full page */
  .page { border:none !important; box-shadow:none !important; border-radius:0 !important; margin:0; padding:20px 28px; page-break-after:always; break-after:page; }
  .page:last-child { page-break-after:auto; break-after:auto; }
  /* Content blocks: flow naturally, avoid internal breaks only */
  .block { border:none !important; box-shadow:none !important; border-radius:0 !important; margin:0; padding:16px 28px; page-break-inside:avoid; break-inside:avoid; }
}
</style>
