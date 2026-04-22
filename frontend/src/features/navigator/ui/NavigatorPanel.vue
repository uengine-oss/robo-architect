<script setup>
import { computed, onMounted, ref, nextTick, inject, watch } from 'vue'
import { useNavigatorStore } from '@/features/navigator/navigator.store'
import { useTerminologyStore } from '@/features/terminology/terminology.store'
import { useBpmnStore } from '@/features/canvas/bpmn.store'
import { useEventModelingStore } from '@/features/eventModeling/eventModeling.store'
import { useDebugMode } from '@/app/debug'
import TreeNode from './TreeNode.vue'

const { isDebug } = useDebugMode()

const navigatorStore = useNavigatorStore()
const terminologyStore = useTerminologyStore()
const bpmnStore = useBpmnStore()
const emStore = useEventModelingStore()
const activeTab = inject('activeTab', ref('Design'))
const isBpmnMode = computed(() => activeTab.value === 'BPMN')
const isEventModelingMode = computed(() => activeTab.value === 'Event Modeling')
const expandedProcesses = ref(new Set())
// Hybrid Process tree expand/collapse — separate state from Event Modeling.
// Default: expand everything so fresh-ingestion streams reveal tasks live.
const expandedHybridProcesses = ref(new Set())
function toggleHybridProcess(pid) {
  if (expandedHybridProcesses.value.has(pid)) expandedHybridProcesses.value.delete(pid)
  else expandedHybridProcesses.value.add(pid)
  expandedHybridProcesses.value = new Set(expandedHybridProcesses.value)
}
// Auto-expand any newly discovered process so tasks appear without a click.
watch(
  () => bpmnStore.hybridProcesses.map(p => p.id),
  (ids) => {
    const next = new Set(expandedHybridProcesses.value)
    for (const id of ids) next.add(id)
    expandedHybridProcesses.value = next
  },
  { deep: true, immediate: true },
)

// --- Hybrid Process drag + double-click → render that process on canvas ---
function handleHybridProcessDragStart(event, proc) {
  event.dataTransfer.setData('application/json', JSON.stringify({
    type: 'HybridProcess',
    processId: proc.id,
    name: proc.name,
    bpmnXml: proc.bpmn_xml || null,
  }))
  event.dataTransfer.effectAllowed = 'copy'
}
function handleHybridProcessDblClick(proc) {
  bpmnStore.selectHybridProcess(proc.id)
}
function taskRuleCount(task) {
  return task.rules?.length || 0
}
function taskPassageCount(task) {
  return task.document_passages?.length || 0
}
function reviewLabel(item) {
  const task = bpmnStore.hybridTasks.find(t => t.id === item.task_id)
  const rule = bpmnStore.hybridRules.find(r => r.id === item.rule_id)
  const taskName = task?.name || item.task_id
  const ruleName = rule?.source_function || item.rule_id
  return `${taskName} ↔ ${ruleName}`
}
function reviewBc(item) {
  const rule = bpmnStore.hybridRules.find(r => r.id === item.rule_id)
  return rule?.context_cluster || null
}

// ---- Rules by BC (Phase 2.5 distribution summary) --------------------
// Shows the cluster-level breakdown so the user can see at a glance
// whether the BC tagging looks right before diving into a specific Task.
const rulesByBc = computed(() => {
  const counts = new Map()
  for (const r of bpmnStore.hybridRules) {
    const k = r.context_cluster || '미분류'
    counts.set(k, (counts.get(k) || 0) + 1)
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
})

// ---- Unified "미매핑 / Review" pool -------------------------------------
// Merges two sources:
//   1. hybridReviewQueue — pipeline's θ-band suggestions (task_id, rule_id, score)
//   2. hybridUnassignedRuleIds — rules with no REALIZED_BY anywhere
// Items are normalized to a common shape so the template renders uniformly.
const unifiedPool = computed(() => {
  const ruleById = new Map(bpmnStore.hybridRules.map(r => [r.id, r]))
  const items = []

  // Review queue items first (have a specific task suggestion)
  for (const item of bpmnStore.hybridReviewQueue) {
    const rule = ruleById.get(item.rule_id)
    const task = bpmnStore.hybridTasks.find(t => t.id === item.task_id)
    items.push({
      kind: 'review',
      key: `rv-${item.task_id}-${item.rule_id}`,
      rule_id: item.rule_id,
      task_id: item.task_id,
      score: item.score,
      rule,
      suggested_task_name: task?.name || item.task_id,
      source_fn: rule?.source_function || item.rule_id,
      bc: rule?.context_cluster || null,
      es_role: rule?.es_role || null,
      _item: item, // keep original for modal trigger
    })
  }

  // Unassigned rules — no task suggestion at all
  for (const ruleId of bpmnStore.hybridUnassignedRuleIds) {
    const rule = ruleById.get(ruleId)
    if (!rule) continue
    items.push({
      kind: 'unassigned',
      key: `un-${ruleId}`,
      rule_id: ruleId,
      task_id: null,
      score: null,
      rule,
      suggested_task_name: null,
      source_fn: rule.source_function || ruleId,
      bc: rule.context_cluster || null,
      es_role: rule.es_role || null,
    })
  }

  return items
})

// Drive a simple "attach to task" inline selector on each pool item.
const poolAttachChoice = ref({}) // { [item.key]: taskIdSelected }

async function attachPoolItem(item) {
  const toTaskId = poolAttachChoice.value[item.key]
  if (!toTaskId) return
  await bpmnStore.assignRuleToTask(item.rule_id, toTaskId)
  poolAttachChoice.value = { ...poolAttachChoice.value, [item.key]: null }
}

function openReviewItem(item) {
  if (item.kind === 'review') {
    bpmnStore.openReviewModal(item._item)
  }
}
const localLoading = ref(true)
const isLoading = computed(() => localLoading.value || navigatorStore.loading)

// Service name editing
const serviceName = ref('My Service Name')
const isEditingName = ref(false)
const nameInput = ref(null)

function startEditName() {
  isEditingName.value = true
  nextTick(() => {
    nameInput.value?.focus()
    nameInput.value?.select()
  })
}

function finishEditName() {
  isEditingName.value = false
  if (!serviceName.value.trim()) {
    serviceName.value = 'My Service Name'
  }
}

function handleNameKeydown(event) {
  if (event.key === 'Enter') {
    finishEditName()
  } else if (event.key === 'Escape') {
    isEditingName.value = false
  }
}

onMounted(async () => {
  await loadData()
})

async function loadData() {
  localLoading.value = true
  try {
    // Fetch both user stories and contexts
    await Promise.all([
      navigatorStore.fetchUserStories(),
      navigatorStore.fetchContexts()
    ])
    
    // Auto-fetch trees for all contexts
    for (const ctx of navigatorStore.contexts) {
      await navigatorStore.fetchContextTree(ctx.id)
    }
  } finally {
    localLoading.value = false
  }
}

async function handleRefresh() {
  localLoading.value = true
  try {
    await navigatorStore.refreshAll()
  } finally {
    localLoading.value = false
  }
}

// BPMN flow handlers
function handleBpmnFlowDragStart(event, flow) {
  event.dataTransfer.setData('application/json', JSON.stringify({
    id: flow.id,
    type: 'BpmnFlow',
    name: flow.name,
  }))
  event.dataTransfer.effectAllowed = 'copy'
}

async function handleBpmnFlowDblClick(flow) {
  if (bpmnStore.renderedFlowIds.has(flow.id)) {
    bpmnStore.selectFlow(flow.id)
    return
  }
  await bpmnStore.addFlow(flow.id)
}

// Event Modeling: 탭 진입 시 프로세스 목록 자동 로드
watch(isEventModelingMode, (active) => {
  if (active && !emStore.processChains.length && !emStore.loading) {
    emStore.fetchProcessList()
  }
}, { immediate: true })

function handleProcessDblClick(proc) {
  emStore.toggleProcessOnCanvas(proc.id)
}

function handleProcessDragStart(event, proc) {
  event.dataTransfer.setData('application/json', JSON.stringify({
    type: 'EventModelingProcess',
    processId: proc.id,
    name: proc.name,
  }))
  event.dataTransfer.effectAllowed = 'copy'
}
</script>

<template>
  <aside class="left-panel">
    <div class="panel-header">
      <div class="service-name-container">
        <input 
          v-if="isEditingName"
          ref="nameInput"
          v-model="serviceName"
          class="service-name-input"
          @blur="finishEditName"
          @keydown="handleNameKeydown"
          placeholder="Service Name"
        />
        <span 
          v-else 
          class="service-name-display"
          @click="startEditName"
          title="Click to edit service name"
        >
          {{ serviceName }}
          <svg class="edit-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </span>
      </div>
    </div>
    
    <div class="panel-content">
      <!-- BPMN Mode: Process Flow List -->
      <template v-if="isBpmnMode">
        <!-- Business Processes — document-derived BPM process tree -->
        <div
          v-if="bpmnStore.hybridActive || bpmnStore.hybridProcessTrees.length"
          class="section-group"
        >
          <div class="section-header">
            <span class="section-title">
              Business Processes
              <span v-if="bpmnStore.hybridActive" class="hybrid-live-dot" title="Live"></span>
            </span>
            <span class="section-count">{{ bpmnStore.hybridProcessTrees.length }}</span>
          </div>
          <!-- §8.7 — cross-process arbitration banner. Appears while Step 4
               is resolving duplicate rule claims across processes. -->
          <div v-if="bpmnStore.isArbitrating" class="hybrid-arbitration-banner">
            <span class="hybrid-arbitration-banner__icon">⚖️</span>
            <div class="hybrid-arbitration-banner__body">
              <div class="hybrid-arbitration-banner__title">중복 rule 우선순위 검증 중</div>
              <div class="hybrid-arbitration-banner__sub">
                {{ bpmnStore.arbitratingTaskIds.length }} 개 task 의 경쟁 rule 을 LLM 이 최종 귀속 결정 중
              </div>
            </div>
          </div>
          <TransitionGroup name="tree-item" tag="div">
            <div
              v-for="proc in bpmnStore.hybridProcessTrees"
              :key="proc.id"
              class="hybrid-process-item"
              :class="{ 'is-active': bpmnStore.activeHybridProcessId === proc.id }"
              :draggable="!!proc.bpmn_xml"
              @dragstart="handleHybridProcessDragStart($event, proc)"
            >
              <div
                class="hybrid-process-item__header"
                @click="toggleHybridProcess(proc.id)"
                @dblclick.stop="handleHybridProcessDblClick(proc)"
                :title="proc.bpmn_xml ? '더블클릭 → 캔버스에 표시 · 드래그 → 캔버스로' : proc.source_pdf_name || proc.name"
              >
                <svg
                  class="hybrid-process-item__chevron"
                  :class="{ 'is-open': expandedHybridProcesses.has(proc.id) }"
                  width="10" height="10" viewBox="0 0 24 24"
                  fill="none" stroke="currentColor" stroke-width="2.5"
                >
                  <polyline points="9 18 15 12 9 6"></polyline>
                </svg>
                <span class="hybrid-process-item__name">{{ proc.name || '(이름 없음)' }}</span>
                <span
                  v-if="bpmnStore.activeHybridProcessId === proc.id"
                  class="hybrid-process-item__active-mark"
                  title="현재 캔버스에 표시 중"
                >●</span>
                <span class="hybrid-process-item__count">T {{ proc.tasks.length }}</span>
              </div>
              <div v-if="expandedHybridProcesses.has(proc.id)" class="hybrid-process-item__body">
                <!-- Domain keywords — internal retrieval metadata, DEBUG ONLY -->
                <div
                  v-if="isDebug && proc.domain_keywords && proc.domain_keywords.length"
                  class="hybrid-process-kw"
                  title="Phase 3 Agent가 analyzer MODULE 검색에 사용하는 쿼리 용어"
                >
                  <span
                    v-for="kw in proc.domain_keywords"
                    :key="kw"
                    class="hybrid-process-kw__chip"
                  >{{ kw }}</span>
                </div>
                <!-- Actors for this process -->
                <div v-if="proc.actors && proc.actors.length" class="hybrid-actors">
                  <span
                    v-for="a in proc.actors"
                    :key="a.id"
                    class="hybrid-actor-chip"
                    :title="a.description || a.name"
                  >👤 {{ a.name }}</span>
                </div>
                <!-- Tasks of this process (primary content — 먼저 노출) -->
                <div
                  v-for="task in proc.tasks"
                  :key="task.id"
                  class="hybrid-task-item"
                  :class="{
                    'is-selected': bpmnStore.selectedHybridTaskId === task.id,
                    'is-exploring': bpmnStore.activeExploringTaskId === task.id,
                    'is-arbitrating': bpmnStore.arbitratingTaskIds.includes(task.id),
                  }"
                  :title="
                    bpmnStore.arbitratingTaskIds.includes(task.id)
                      ? '⚖️ 중복 rule 우선순위 검증 중'
                      : (task.description || task.name)
                  "
                  @dblclick.stop="bpmnStore.selectHybridTask(task.id)"
                >
                  <span class="hybrid-task-item__idx">{{ (task.sequence_index ?? 0) + 1 }}</span>
                  <span class="hybrid-task-item__name">{{ task.name }}</span>
                  <span
                    v-if="bpmnStore.activeExploringTaskId === task.id"
                    class="hybrid-task-item__spinner"
                    title="Agent 탐색 진행 중"
                  >
                    <span class="hybrid-task-item__dot"></span>
                    <span class="hybrid-task-item__dot"></span>
                    <span class="hybrid-task-item__dot"></span>
                  </span>
                  <span
                    v-else-if="taskRuleCount(task) > 0"
                    class="hybrid-task-item__count"
                    :title="`Rules ${taskRuleCount(task)} · Passages ${taskPassageCount(task)}`"
                  >R {{ taskRuleCount(task) }}</span>
                </div>
                <div v-if="!proc.tasks.length" class="hybrid-process-empty">
                  (아직 Task 가 없습니다)
                </div>
                <!-- Domain glossary terms — 보조 참고용으로 Tasks 아래에 -->
                <div v-if="proc.glossary && proc.glossary.length" class="hybrid-process-glossary">
                  <div class="hybrid-process-glossary__label">용어</div>
                  <div class="hybrid-process-glossary__list">
                    <div
                      v-for="term in proc.glossary"
                      :key="term.term"
                      class="hybrid-process-glossary__item"
                      :title="(term.aliases || []).join(', ')"
                    >
                      <span class="hybrid-process-glossary__term">{{ term.term }}</span>
                      <span
                        v-for="c in (term.code_candidates || []).slice(0, 3)"
                        :key="c"
                        class="hybrid-process-glossary__code"
                      >{{ c }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </TransitionGroup>
        </div>

        <!-- Hybrid: Rules by BC (Phase 2.5 distribution summary) — DEBUG ONLY -->
        <div v-if="isDebug && rulesByBc.length" class="section-group">
          <div class="section-header">
            <span class="section-title">Rules by Context</span>
            <span class="section-count">{{ bpmnStore.hybridRules.length }}</span>
          </div>
          <div class="hybrid-bc-list">
            <div
              v-for="bc in rulesByBc"
              :key="bc.name"
              class="hybrid-bc-item"
              :class="{ 'is-unclassified': bc.name === '미분류' }"
              :title="`클릭 → ${bc.name} 범주 Rule 관리 (${bc.count}개)`"
              @click="bpmnStore.openBcRulesModal(bc.name)"
            >
              <span class="hybrid-bc-item__name">{{ bc.name }}</span>
              <span class="hybrid-bc-item__count">{{ bc.count }}</span>
            </div>
          </div>
        </div>

        <!-- Hybrid: Unified 미매핑 / Review pool — DEBUG ONLY (§2.D) -->
        <!-- review: pipeline's θ-band suggestion (has task_id). unassigned: no REALIZED_BY anywhere. -->
        <div v-if="isDebug && unifiedPool.length" class="section-group">
          <div class="section-header">
            <span class="section-title">미매핑 / Review</span>
            <span class="section-count">{{ unifiedPool.length }}</span>
          </div>
          <div class="hybrid-pool">
            <div
              v-for="item in unifiedPool"
              :key="item.key"
              class="hybrid-pool-item"
              :class="`hybrid-pool-item--${item.kind}`"
            >
              <div class="hybrid-pool-item__head">
                <span
                  class="hybrid-pool-item__kind"
                  :title="item.kind === 'review'
                    ? `파이프라인 제안 (score ${(item.score * 100).toFixed(0)}%) — 클릭하여 검토`
                    : '어느 Task에도 붙지 않은 규칙 — 수동 연결 필요'"
                >{{ item.kind === 'review' ? '🔍 제안' : '❔ 미매핑' }}</span>
                <span v-if="item.bc" class="hybrid-pool-item__bc">{{ item.bc }}</span>
                <span v-if="item.es_role" class="hybrid-pool-item__role">{{ item.es_role }}</span>
              </div>
              <div class="hybrid-pool-item__body">
                <code class="hybrid-pool-item__fn">{{ item.source_fn }}</code>
                <div v-if="item.rule?.title" class="hybrid-pool-item__title">{{ item.rule.title }}</div>
              </div>
              <div
                v-if="item.kind === 'review'"
                class="hybrid-pool-item__suggested"
                @click="openReviewItem(item)"
                :title="`제안 Task 클릭 → 모달에서 승인/거부`"
              >
                <span class="hybrid-pool-item__score">{{ (item.score * 100).toFixed(0) }}%</span>
                <span>→ {{ item.suggested_task_name }}</span>
              </div>
              <div class="hybrid-pool-item__attach">
                <select
                  class="hybrid-pool-item__select"
                  :value="poolAttachChoice[item.key] || ''"
                  @change="poolAttachChoice = { ...poolAttachChoice, [item.key]: $event.target.value }"
                >
                  <option value="">Task 선택</option>
                  <option
                    v-for="t in bpmnStore.hybridTasks"
                    :key="t.id"
                    :value="t.id"
                  >{{ t.name }}</option>
                </select>
                <button
                  class="hybrid-pool-item__btn"
                  :disabled="!poolAttachChoice[item.key]"
                  @click="attachPoolItem(item)"
                >연결</button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="bpmnStore.loading" class="loading-state">
          <div class="loading-spinner"></div>
          <span>Loading business processes...</span>
        </div>
        <div v-else-if="bpmnStore.error" class="error-state">
          {{ bpmnStore.error }}
        </div>
        <div
          v-else-if="bpmnStore.processFlows.length === 0 && !bpmnStore.hybridTasks.length"
          class="empty-state"
        >
          No business processes found
        </div>
        <template v-else-if="!bpmnStore.hybridProcessTrees.length">
          <div class="section-group">
            <div class="section-header section-header--with-actions">
              <div class="section-header__left">
                <span class="section-title">Business Processes</span>
                <span class="section-count">{{ bpmnStore.processFlows.length }}</span>
              </div>
              <div class="section-header__actions">
                <button
                  class="tree-action-btn"
                  :class="{ 'is-spinning': bpmnStore.loading }"
                  @click="bpmnStore.fetchProcessFlows()"
                  title="Refresh"
                  :disabled="bpmnStore.loading"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="23 4 23 10 17 10"></polyline>
                    <polyline points="1 20 1 14 7 14"></polyline>
                    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                  </svg>
                </button>
              </div>
            </div>
            <div
              v-for="flow in bpmnStore.processFlows"
              :key="flow.id"
              class="bpmn-flow-item"
              :class="{ 'is-on-canvas': bpmnStore.renderedFlowIds.has(flow.id) }"
              :draggable="true"
              @dragstart="handleBpmnFlowDragStart($event, flow)"
              @dblclick="handleBpmnFlowDblClick(flow)"
              :title="`${flow.name}\nActors: ${flow.actors?.join(', ') || 'System'}\nBC: ${flow.bcName || '-'}`"
            >
              <span class="bpmn-flow-item__icon">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="5" cy="12" r="3" />
                  <line x1="8" y1="12" x2="16" y2="12" />
                  <circle cx="19" cy="12" r="3" />
                </svg>
              </span>
              <div class="bpmn-flow-item__content">
                <span class="bpmn-flow-item__name">{{ flow.startCommandName || flow.name }}</span>
              </div>
              <span v-if="flow.nodeCount > 0" class="bpmn-flow-item__chip">{{ flow.nodeCount }}</span>
              <span v-if="bpmnStore.renderedFlowIds.has(flow.id)" class="bpmn-flow-item__check">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </span>
            </div>
          </div>
        </template>
      </template>

      <!-- Event Modeling Mode: Process Flows Only -->
      <template v-else-if="isEventModelingMode">
        <div class="section-group">
          <div class="section-header section-header--with-actions">
            <div class="section-header__left">
              <span class="section-title">Process Flows</span>
              <span v-if="emStore.processChains.length" class="section-count">{{ emStore.processChains.length }}</span>
            </div>
            <div class="section-header__actions">
              <button class="tree-action-btn" @click="emStore.fetchEventModeling()" title="Load All" :disabled="emStore.loading">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                  <path d="M3 9h18M9 3v18"/>
                </svg>
              </button>
              <button class="tree-action-btn" :class="{ 'is-spinning': emStore.loading }" @click="emStore.fetchProcessList()" title="Refresh" :disabled="emStore.loading">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="23 4 23 10 17 10"></polyline>
                  <polyline points="1 20 1 14 7 14"></polyline>
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                </svg>
              </button>
            </div>
          </div>

          <div v-if="emStore.loading" class="loading-state" style="padding:16px">
            <div class="loading-spinner"></div>
            <span>Loading...</span>
          </div>
          <div v-else-if="emStore.processChains.length === 0" class="empty-state" style="padding:16px">
            <span>프로세스 데이터가 없습니다.</span>
          </div>
          <template v-else>
            <div v-for="proc in emStore.processChains" :key="proc.id"
                 class="em-process-item"
                 :class="{ 'is-on-canvas': emStore.canvasProcessIds.has(proc.id) }"
                 :draggable="true"
                 @dragstart="handleProcessDragStart($event, proc)"
                 @dblclick="handleProcessDblClick(proc)">
              <div class="em-process-item__header" @click.stop="expandedProcesses.has(proc.id) ? expandedProcesses.delete(proc.id) : expandedProcesses.add(proc.id)">
                <svg class="em-process-item__chevron" :class="{ 'is-open': expandedProcesses.has(proc.id) }" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <polyline points="9 18 15 12 9 6"></polyline>
                </svg>
                <span class="em-process-item__name" :title="proc.name">{{ proc.name }}</span>
                <span class="em-process-item__chip">{{ proc.stepCount }}</span>
                <span v-if="emStore.canvasProcessIds.has(proc.id)" class="em-process-item__check">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                </span>
              </div>
              <div v-if="expandedProcesses.has(proc.id)" class="em-process-item__steps">
                <div v-for="step in proc.steps" :key="step.id"
                     class="em-process-step"
                     @click.stop="emStore.selectItem(step.id, step.type)"
                     :class="{ 'is-selected': emStore.selectedItemId === step.id }">
                  <span class="em-process-step__dot" :class="'em-process-step__dot--' + step.type"></span>
                  <span class="em-process-step__name">{{ step.name }}</span>
                </div>
              </div>
            </div>
          </template>
        </div>
      </template>

      <!-- Default Mode: BC Tree -->
      <template v-else>
        <div v-if="isLoading" class="loading-state">
          <div class="loading-spinner"></div>
          <span>Loading contexts...</span>
        </div>

        <div v-else-if="navigatorStore.error" class="error-state">
          {{ navigatorStore.error }}
        </div>

        <div v-else-if="navigatorStore.contexts.length === 0 && navigatorStore.userStories.length === 0" class="empty-state">
          No data found
        </div>

        <template v-else>
          <!-- Unassigned User Stories (root level) -->
          <div v-if="navigatorStore.userStories.length > 0" class="section-group">
            <div class="section-header">
              <span class="section-title">Requirements</span>
              <span class="section-count">{{ navigatorStore.userStories.length }}</span>
            </div>
            <TransitionGroup name="tree-item">
              <TreeNode
                v-for="us in navigatorStore.userStories"
                :key="us.id"
                :node="{ ...us, type: 'UserStory', name: us.name || `${us.role}: ${us.action?.substring(0, 25)}...` }"
              />
            </TransitionGroup>
          </div>

          <!-- Bounded Contexts -->
          <div v-if="navigatorStore.contexts.length > 0" class="section-group">
            <div class="section-header section-header--with-actions">
              <div class="section-header__left">
                <span class="section-title">{{ terminologyStore.getTerm('BoundedContext') }}s</span>
                <span class="section-count">{{ navigatorStore.contexts.length }}</span>
              </div>
              <div class="section-header__actions">
                <button
                  class="tree-action-btn"
                  :class="{ 'is-spinning': isLoading }"
                  @click="handleRefresh"
                  title="Refresh"
                  :disabled="isLoading"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="23 4 23 10 17 10"></polyline>
                    <polyline points="1 20 1 14 7 14"></polyline>
                    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                  </svg>
                </button>
                <button
                  class="tree-action-btn"
                  @click="navigatorStore.expandAll()"
                  title="Expand All"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </button>
                <button
                  class="tree-action-btn"
                  @click="navigatorStore.collapseAll()"
                  title="Collapse All"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="18 15 12 9 6 15"></polyline>
                  </svg>
                </button>
              </div>
            </div>
            <TransitionGroup name="tree-item">
              <TreeNode
                v-for="ctx in navigatorStore.contexts"
                :key="ctx.id"
                :node="{ ...ctx, type: 'BoundedContext', domainType: ctx.domainType }"
                :tree="navigatorStore.contextTrees[ctx.id]"
              />
            </TransitionGroup>
          </div>
        </template>
      </template>
    </div>
    
    <!-- Legend -->
    <div class="panel-legend">
      <template v-if="isBpmnMode">
        <div class="legend-item">
          <span class="legend-color legend-color--command"></span>
          <span>Activity (Command)</span>
        </div>
        <div class="legend-item">
          <span class="legend-color legend-color--event"></span>
          <span>Event</span>
        </div>
        <div class="legend-item">
          <span class="legend-color" style="background: #20c997;"></span>
          <span>Swimlane (Actor)</span>
        </div>
      </template>
      <template v-else-if="isEventModelingMode">
        <div class="legend-item">
          <span class="legend-color legend-color--command"></span>
          <span>Command</span>
        </div>
        <div class="legend-item">
          <span class="legend-color legend-color--event"></span>
          <span>Event</span>
        </div>
        <div class="legend-item">
          <span class="legend-color legend-color--readmodel"></span>
          <span>ReadModel</span>
        </div>
      </template>
      <template v-else>
        <div class="legend-item">
          <span class="legend-color legend-color--userstory"></span>
          <span>UserStory</span>
        </div>
        <div class="legend-item">
          <span class="legend-color legend-color--aggregate"></span>
          <span>{{ terminologyStore.getTerm('Aggregate') }}</span>
        </div>
        <div class="legend-item">
          <span class="legend-color legend-color--command"></span>
          <span>{{ terminologyStore.getTerm('Command') }}</span>
        </div>
        <div class="legend-item">
          <span class="legend-color legend-color--event"></span>
          <span>{{ terminologyStore.getTerm('Event') }}</span>
        </div>
        <div class="legend-item">
          <span class="legend-color legend-color--policy"></span>
          <span>{{ terminologyStore.getTerm('Policy') }}</span>
        </div>
        <div class="legend-item">
          <span class="legend-color legend-color--readmodel"></span>
          <span>{{ terminologyStore.getTerm('ReadModel') }}</span>
        </div>
        <div class="legend-item">
          <span class="legend-color legend-color--ui"></span>
          <span>{{ terminologyStore.getTerm('UI') }}</span>
        </div>
      </template>
    </div>
  </aside>
</template>

<style scoped>
/* Service Name Editing */
.service-name-container {
  display: flex;
  align-items: center;
  width: 100%;
}

.service-name-display {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-bright);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  transition: background 0.15s, color 0.15s;
  width: 100%;
}

.service-name-display:hover {
  background: var(--color-bg-tertiary);
}

.service-name-display .edit-icon {
  color: var(--color-text-light);
  width: 10px;
  height: 10px;
  flex-shrink: 0;
}

.service-name-input {
  flex: 1;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-bright);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  padding: 2px 6px;
  outline: none;
  width: 100%;
}

.service-name-input::placeholder {
  color: var(--color-text-light);
  font-weight: 400;
}

/* Tree Action Buttons */
.tree-action-btn {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.tree-action-btn:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-bright);
}

.tree-action-btn.is-spinning svg {
  animation: spin 1s linear infinite;
}

.tree-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Section Groups */
.section-group {
  margin-bottom: var(--spacing-sm);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px var(--spacing-xs);
  margin-bottom: 2px;
}

.section-header--with-actions {
  padding: 4px var(--spacing-xs);
}

.section-header__left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.section-header__actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.section-title {
  font-size: 0.6rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-light);
}

.section-count {
  font-size: 0.55rem;
  padding: 1px 4px;
  background: var(--color-bg-tertiary);
  border-radius: 8px;
  color: var(--color-text-light);
}

/* Tree item transitions */
.tree-item-enter-active {
  animation: slideInLeft 0.3s ease-out;
}

.tree-item-leave-active {
  animation: slideOutRight 0.3s ease-out;
}

.tree-item-move {
  transition: transform 0.3s ease;
}

@keyframes slideInLeft {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes slideOutRight {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(20px);
  }
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  color: var(--color-text-light);
  font-size: 0.875rem;
  text-align: center;
  gap: var(--spacing-sm);
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.panel-legend {
  padding: var(--spacing-sm);
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.65rem;
  color: var(--color-text-light);
}

.legend-color {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.legend-color--userstory { background: #20c997; }
.legend-color--command { background: var(--color-command); }
.legend-color--event { background: var(--color-event); }
.legend-color--policy { background: var(--color-policy); }
.legend-color--aggregate { background: var(--color-aggregate); }
.legend-color--readmodel { background: var(--color-readmodel); }
.legend-color--ui { background: var(--color-ui-light); border: 1px solid var(--color-ui); }

/* BPMN Flow Items */
.bpmn-flow-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  cursor: pointer;
  transition: background 0.15s;
  border-radius: var(--radius-sm);
  margin: 1px 4px;
}

.bpmn-flow-item:hover {
  background: var(--color-bg-tertiary);
}

.bpmn-flow-item.is-on-canvas {
  background: rgba(34, 139, 230, 0.1);
}

.bpmn-flow-item.is-on-canvas:hover {
  background: rgba(34, 139, 230, 0.15);
}

.bpmn-flow-item__icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: rgba(92, 124, 250, 0.15);
  color: var(--color-command);
}

.bpmn-flow-item__content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.bpmn-flow-item__name {
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bpmn-flow-item__chip {
  flex-shrink: 0;
  font-size: 0.55rem;
  font-weight: 600;
  min-width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 5px;
  background: var(--color-bg-tertiary);
  color: var(--color-text-light);
  border-radius: 9px;
}

.bpmn-flow-item__check {
  flex-shrink: 0;
  color: var(--color-accent);
  display: flex;
  align-items: center;
}

/* Event Modeling Process Items */
.em-process-item {
  margin: 1px 4px;
  cursor: grab;
}

.em-process-item.is-on-canvas {
  background: rgba(34, 139, 230, 0.08);
  border-radius: var(--radius-sm);
}

.em-process-item__header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background 0.15s;
}

.em-process-item__header:hover {
  background: var(--color-bg-tertiary);
}

.em-process-item__chevron {
  flex-shrink: 0;
  color: var(--color-text-light);
  transition: transform 0.15s;
}

.em-process-item__chevron.is-open {
  transform: rotate(90deg);
}

.em-process-item__name {
  flex: 1;
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.em-process-item__chip {
  flex-shrink: 0;
  font-size: 0.55rem;
  font-weight: 600;
  min-width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 5px;
  background: var(--color-bg-tertiary);
  color: var(--color-text-light);
  border-radius: 9px;
}

.em-process-item__steps {
  padding-left: 18px;
}

.em-process-step {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background 0.15s;
}

.em-process-step:hover {
  background: var(--color-bg-tertiary);
}

.em-process-step.is-selected {
  background: rgba(34, 139, 230, 0.15);
}

.em-process-step__dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}

.em-process-step__dot--command { background: var(--color-command, #5c7cfa); }
.em-process-step__dot--event { background: var(--color-event, #fd7e14); }
.em-process-step__dot--readmodel { background: var(--color-readmodel, #40c057); }
.em-process-step__dot--ui { background: #bdbdbd; border: 1px solid #999; }

.em-process-step__name {
  font-size: 0.65rem;
  color: var(--color-text-light);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.em-process-item__check {
  flex-shrink: 0;
  color: var(--color-accent);
  display: flex;
  align-items: center;
}

/* Hybrid Process tree (root rows) */
.hybrid-process-item {
  margin: 2px 4px;
  border-radius: var(--radius-sm);
  background: rgba(176, 120, 240, 0.06);
  border-left: 3px solid rgba(176, 120, 240, 0.5);
  cursor: grab;
}
.hybrid-process-item.is-active {
  background: rgba(176, 120, 240, 0.18);
  border-left-color: rgba(176, 120, 240, 1);
}
.hybrid-process-item:active { cursor: grabbing; }
.hybrid-process-item__active-mark {
  color: rgba(176, 120, 240, 1);
  font-size: 0.6rem;
  line-height: 1;
}
.hybrid-process-item__header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  cursor: pointer;
  user-select: none;
}
.hybrid-process-item__header:hover {
  background: rgba(176, 120, 240, 0.12);
}
.hybrid-process-item__chevron {
  flex-shrink: 0;
  color: var(--color-text-light);
  transition: transform 0.15s;
}
.hybrid-process-item__chevron.is-open { transform: rotate(90deg); }
.hybrid-process-item__name {
  flex: 1;
  min-width: 0;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--color-text-bright);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hybrid-process-item__count {
  flex-shrink: 0;
  font-size: 0.55rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(176, 120, 240, 0.18);
  color: #c4a5ee;
}
.hybrid-process-item__body {
  padding: 4px 4px 6px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hybrid-process-kw {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  padding: 2px 4px;
}
.hybrid-process-kw__chip {
  font-size: 0.55rem;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(176, 120, 240, 0.15);
  color: #c4a5ee;
}
.hybrid-process-empty {
  font-size: 0.6rem;
  color: var(--color-text-dim);
  font-style: italic;
  padding: 4px 8px;
}

/* Per-process glossary (domain terms that match this process's keywords) */
.hybrid-process-glossary {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 2px 4px;
}
.hybrid-process-glossary__label {
  font-size: 0.55rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-dim);
  padding: 0 4px;
}
.hybrid-process-glossary__list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.hybrid-process-glossary__item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  border-radius: var(--radius-sm);
  background: rgba(176, 120, 240, 0.06);
  font-size: 0.6rem;
}
.hybrid-process-glossary__term {
  font-weight: 600;
  color: var(--color-text-bright);
  margin-right: 4px;
}
.hybrid-process-glossary__code {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 0.54rem;
  color: #b078f0;
  background: rgba(176, 120, 240, 0.15);
  padding: 1px 5px;
  border-radius: 6px;
}

/* Hybrid ingestion live list */
.hybrid-live-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #e03131;
  margin-left: 6px;
  animation: pulse 1s ease-in-out infinite;
  vertical-align: middle;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.hybrid-actors {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 4px 8px;
}
.hybrid-actor-chip {
  font-size: 0.6rem;
  padding: 2px 6px;
  border-radius: 10px;
  background: rgba(32, 201, 151, 0.15);
  color: var(--color-text-bright);
}
.hybrid-task-item {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 1px 4px;
  padding: 5px 8px;
  border-radius: var(--radius-sm);
  background: rgba(92, 124, 250, 0.08);
  cursor: pointer;
  user-select: none;
}
.hybrid-task-item:hover {
  background: rgba(92, 124, 250, 0.16);
}
.hybrid-task-item.is-selected {
  background: rgba(92, 124, 250, 0.28);
  outline: 1px solid rgba(92, 124, 250, 0.45);
}
.hybrid-task-item__idx {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.55rem;
  font-weight: 700;
  color: var(--color-command);
  background: rgba(92, 124, 250, 0.2);
  border-radius: 50%;
}
.hybrid-task-item__name {
  flex: 1;
  min-width: 0;
  font-size: 0.7rem;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hybrid-task-item__count {
  flex-shrink: 0;
  font-size: 0.55rem;
  font-weight: 700;
  color: var(--color-text-dim);
  background: rgba(255, 255, 255, 0.08);
  padding: 1px 6px;
  border-radius: 8px;
}
/* Agent exploration badge — pulsing 3-dot indicator on tasks under 🔄 재탐색.
   Paired with `.is-exploring` wash on the task row so it's visible at a glance. */
.hybrid-task-item.is-exploring {
  background: rgba(255, 196, 92, 0.18);
  outline: 1px solid rgba(255, 196, 92, 0.55);
}
/* Cross-process arbitration highlight — purple/violet wash so it's visibly
   different from the warm yellow "exploring" state. Shown during Step 4 when
   multiple tasks compete for the same rule. */
.hybrid-task-item.is-arbitrating {
  background: rgba(168, 120, 248, 0.22);
  outline: 1px solid rgba(168, 120, 248, 0.6);
  animation: hybrid-arbitration-pulse 1.4s ease-in-out infinite;
}
@keyframes hybrid-arbitration-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(168, 120, 248, 0.0); }
  50%      { box-shadow: 0 0 0 3px rgba(168, 120, 248, 0.25); }
}
/* Banner shown above the process tree while arbitration runs. */
.hybrid-arbitration-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 4px 4px;
  padding: 8px 10px;
  background: rgba(168, 120, 248, 0.14);
  border: 1px solid rgba(168, 120, 248, 0.5);
  border-radius: var(--radius-sm);
}
.hybrid-arbitration-banner__icon {
  font-size: 1.1rem;
}
.hybrid-arbitration-banner__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.hybrid-arbitration-banner__title {
  font-size: 0.72rem;
  font-weight: 600;
  color: rgb(205, 185, 245);
}
.hybrid-arbitration-banner__sub {
  font-size: 0.62rem;
  color: var(--color-text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hybrid-task-item__spinner {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 0 4px;
}
.hybrid-task-item__dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 196, 92, 0.95);
  animation: hybrid-task-dot 1s infinite ease-in-out;
}
.hybrid-task-item__dot:nth-child(2) { animation-delay: 0.15s; }
.hybrid-task-item__dot:nth-child(3) { animation-delay: 0.3s; }
@keyframes hybrid-task-dot {
  0%, 80%, 100% { opacity: 0.25; transform: scale(0.8); }
  40%           { opacity: 1;    transform: scale(1.15); }
}

/* Rules by Context (Phase 2.5 summary) ----------------- */
.hybrid-bc-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 4px;
}
.hybrid-bc-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 9px;
  margin: 0 4px;
  border-radius: var(--radius-sm);
  background: rgba(92, 124, 250, 0.08);
  font-size: 0.66rem;
  cursor: pointer;
  transition: background 0.12s;
}
.hybrid-bc-item:hover {
  background: rgba(92, 124, 250, 0.20);
}
.hybrid-bc-item.is-unclassified {
  background: rgba(255, 255, 255, 0.04);
  color: var(--color-text-dim);
}
.hybrid-bc-item.is-unclassified:hover {
  background: rgba(255, 255, 255, 0.09);
}
.hybrid-bc-item__name {
  font-weight: 600;
  color: #c6d2ff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hybrid-bc-item.is-unclassified .hybrid-bc-item__name {
  color: var(--color-text-dim);
}
.hybrid-bc-item__count {
  flex-shrink: 0;
  font-weight: 700;
  color: var(--color-text-dim);
}

/* Review queue BC badge ------------------------------- */
.hybrid-review-item__bc {
  flex-shrink: 0;
  font-size: 0.55rem;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(92, 124, 250, 0.18);
  color: #9cb2ff;
  margin-left: auto;
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hybrid-task-section {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.hybrid-task-section__label {
  font-size: 0.55rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--color-text-dim);
}
.hybrid-task-section__text {
  font-size: 0.66rem;
  line-height: 1.4;
  color: var(--color-text);
  word-break: break-word;
}
.hybrid-task-section__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}
.hybrid-task-section__empty {
  font-size: 0.6rem;
  color: var(--color-text-dim);
  font-style: italic;
  opacity: 0.7;
}
.hybrid-task-section__badge {
  margin-left: 6px;
  padding: 1px 5px;
  border-radius: 8px;
  font-size: 0.55rem;
  background: rgba(255,255,255,0.08);
  color: var(--color-text-dim);
}
.hybrid-task-section__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hybrid-rule-item {
  padding: 4px 6px;
  background: rgba(255,255,255,0.04);
  border-left: 2px solid var(--color-policy, #f5b441);
  border-radius: 3px;
  font-size: 0.62rem;
  line-height: 1.35;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.hybrid-rule-item__kw {
  font-weight: 700;
  color: var(--color-policy, #f5b441);
  margin-right: 4px;
}
.hybrid-rule-item__src {
  font-size: 0.55rem;
  color: var(--color-text-dim);
  margin-top: 2px;
}
.hybrid-rule-item__conf {
  margin-left: 6px;
  padding: 0 4px;
  border-radius: 6px;
  background: rgba(32, 201, 151, 0.18);
  color: var(--color-text-bright);
  font-size: 0.52rem;
  font-weight: 600;
}
.hybrid-fn-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.62rem;
  color: var(--color-text);
  padding: 2px 4px;
}
.hybrid-fn-item__name {
  font-family: 'SF Mono', Menlo, monospace;
}
.hybrid-cond-item {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 0.6rem;
  color: var(--color-text);
  padding: 2px 4px;
  background: rgba(255,255,255,0.04);
  border-radius: 3px;
}
.hybrid-es-chip {
  font-size: 0.55rem;
  padding: 1px 6px;
  border-radius: 8px;
  font-weight: 600;
}
.hybrid-es-chip--command { background: rgba(92,124,250,0.25); color: var(--color-command); }
.hybrid-es-chip--event { background: rgba(245,180,65,0.25); color: #f5b441; }
.hybrid-es-chip--policy { background: rgba(176,120,240,0.25); color: #b078f0; }
.hybrid-es-chip--aggregate { background: rgba(32,201,151,0.25); color: #20c997; }
.hybrid-rule-row {
  margin: 2px 4px;
  padding: 5px 8px;
  border-radius: var(--radius-sm);
  background: rgba(245, 180, 65, 0.06);
  border-left: 2px solid var(--color-policy, #f5b441);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.hybrid-rule-row__fn {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.64rem;
  font-family: 'SF Mono', Menlo, monospace;
  color: var(--color-text-bright);
}
.hybrid-rule-row__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-policy, #f5b441);
  flex-shrink: 0;
}
.hybrid-rule-row__fn-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hybrid-rule-row__gwt {
  font-size: 0.6rem;
  line-height: 1.35;
  color: var(--color-text);
  padding-left: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hybrid-glossary {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 2px 6px;
}
.hybrid-glossary-item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  border-radius: var(--radius-sm);
  background: rgba(176, 120, 240, 0.08);
  font-size: 0.62rem;
}
.hybrid-glossary-item__term {
  font-weight: 600;
  color: var(--color-text-bright);
  margin-right: 4px;
}
.hybrid-glossary-item__code {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 0.55rem;
  color: #b078f0;
  background: rgba(176, 120, 240, 0.15);
  padding: 1px 5px;
  border-radius: 6px;
}
.hybrid-review {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 6px;
}
.hybrid-review-item {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 4px 6px;
  border-radius: var(--radius-sm);
  background: rgba(255, 180, 65, 0.07);
  font-size: 0.62rem;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s ease;
}
.hybrid-review-item:hover {
  background: rgba(255, 180, 65, 0.18);
}
.hybrid-review-item__score {
  font-weight: 700;
  color: #f5b441;
  min-width: 28px;
}
.hybrid-review-item__pair {
  font-family: 'SF Mono', Menlo, monospace;
  color: var(--color-text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Unified 미매핑 / Review pool --------------------------- */
.hybrid-pool {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 2px 6px;
}
.hybrid-pool-item {
  padding: 6px 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-left: 3px solid rgba(245, 180, 65, 0.5);
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hybrid-pool-item--unassigned {
  border-left-color: rgba(255, 120, 120, 0.5);
}
.hybrid-pool-item__head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.hybrid-pool-item__kind {
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 1px 5px;
  border-radius: 8px;
  background: rgba(245, 180, 65, 0.12);
  color: #f5c77a;
}
.hybrid-pool-item--unassigned .hybrid-pool-item__kind {
  background: rgba(255, 120, 120, 0.14);
  color: #ff9a9a;
}
.hybrid-pool-item__bc,
.hybrid-pool-item__role {
  font-size: 0.55rem;
  padding: 1px 6px;
  border-radius: 8px;
  font-weight: 600;
}
.hybrid-pool-item__bc {
  background: rgba(92, 124, 250, 0.18);
  color: #9cb2ff;
}
.hybrid-pool-item__role {
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-dim);
}
.hybrid-pool-item__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.hybrid-pool-item__fn {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 0.66rem;
  color: var(--color-text-bright);
}
.hybrid-pool-item__title {
  font-size: 0.66rem;
  color: var(--color-text);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hybrid-pool-item__suggested {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 6px;
  background: rgba(92, 124, 250, 0.08);
  border-radius: 3px;
  font-size: 0.62rem;
  color: var(--color-text-dim);
  cursor: pointer;
}
.hybrid-pool-item__suggested:hover {
  background: rgba(92, 124, 250, 0.18);
  color: var(--color-text-bright);
}
.hybrid-pool-item__score {
  font-weight: 700;
  color: #f5c77a;
}
.hybrid-pool-item__attach {
  display: flex;
  gap: 4px;
  align-items: center;
}
.hybrid-pool-item__select {
  flex: 1;
  min-width: 0;
  padding: 3px 5px;
  font-size: 0.62rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  color: var(--color-text);
}
.hybrid-pool-item__btn {
  padding: 3px 9px;
  font-size: 0.62rem;
  font-weight: 700;
  background: rgba(64, 192, 87, 0.18);
  color: #8ce3a0;
  border: 1px solid rgba(64, 192, 87, 0.35);
  border-radius: 3px;
  cursor: pointer;
}
.hybrid-pool-item__btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.hybrid-pool-item__btn:not(:disabled):hover {
  background: rgba(64, 192, 87, 0.3);
}

.hybrid-passage-item {
  padding: 5px 6px;
  background: rgba(100, 190, 255, 0.06);
  border-left: 2px solid #64beff;
  border-radius: 3px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.hybrid-passage-item.is-low {
  border-left-color: rgba(100, 190, 255, 0.4);
  opacity: 0.75;
}
.hybrid-passage-item__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  font-size: 0.58rem;
}
.hybrid-passage-item__heading {
  font-weight: 600;
  color: #64beff;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hybrid-passage-item__body {
  font-size: 0.62rem;
  line-height: 1.4;
  color: var(--color-text);
  max-height: 5.6em;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  text-overflow: ellipsis;
  word-break: break-word;
}
</style>

