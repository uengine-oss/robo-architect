<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useBpmnStore } from '@/features/canvas/bpmn.store'
import { useDebugMode } from '@/app/debug'

const emit = defineEmits(['close'])
const store = useBpmnStore()
const { isDebug } = useDebugMode()

const task = computed(() => store.selectedHybridTask)

// ---------------------------------------------------------------------------
// Agent Reasoning — all SSE state lives in the store (see bpmn.store.js).
// This component is a pure reader. Closing the panel does NOT close the
// EventSource; the store keeps listening so progress events keep flowing and
// the Navigator spinner stays accurate even when the inspector is dismissed.
// ---------------------------------------------------------------------------
const agentEvents = computed(() => store.agentEvents)
// State resolution priority (§8.7):
//  1. If batch ingestion or 🔄 re-retrieval is actively exploring THIS task,
//     show 'running' — so the Inspector button flips to "탐색 중" spinner and
//     the panel shows the "에이전트가 탐색을 시작합니다…" placeholder instead
//     of a misleading "재탐색" button.
//  2. If a recent re-retrieval targeted THIS task, reflect its terminal state
//     (done/error) from the store.
//  3. Otherwise — cached result from Phase 3 at ingestion time.
const agentState = computed(() => {
  const tid = task.value?.id
  if (!tid) return 'idle'
  if (store.activeExploringTaskId === tid) return 'running'
  if (store.agentTaskId === tid) return store.agentState
  return 'cached'
})
const isReasoningExpanded = ref(true)

function agentStepLabel(ev) {
  switch (ev.type) {
    case 'AgentStart': return `🔎 ${ev.process_name || '(프로세스)'} 검색 시작`
    case 'AgentStepModuleSearch': return `📦 모듈 ${ev.candidates?.length || 0}개 후보`
    case 'AgentStepBlSearch': return `⚖️ BL ${ev.candidates?.length || 0}개 후보`
    case 'AgentStepParentLookup': return `🔗 ${ev.rule_id} 호출 체인 조회`
    case 'AgentStepDecision':
      return ev.verdict === 'accept'
        ? `✅ accept · ${ev.rule_id}`
        : `❌ reject · ${ev.rule_id}`
    case 'AgentFinalMatches': return `🎯 최종 매핑 ${ev.rules?.length || 0}개 (${ev.total_ms || '?'}ms)`
    case 'AgentDone': return `✔️ 완료 (${ev.total_ms}ms)`
    case 'AgentError': return `⚠️ 오류`
    default: return ev.type
  }
}

function rerunAgent() {
  if (!task.value || !store.hybridSessionId) return
  store.startAgentStream(store.hybridSessionId, task.value.id)
}

// Panel open NEVER triggers LLM work automatically. Rule mapping happens
// during ingestion (Phase 3); the panel only displays the cached result
// (including tasks with 0 accepted rules — that's a valid cached "no match").
// User must click "🔄 재탐색" to explicitly re-run.
// IMPORTANT: panel close does NOT close the SSE — store keeps listening so
// progress events keep flowing (Navigator spinner stays live) even after the
// user dismisses the inspector. Aborting a re-retrieval would also lose the
// resulting DB writes, which we don't want.
watch(
  () => task.value?.id,
  (newTaskId) => {
    if (!newTaskId) return
    // Only mark as cached if we're not actively streaming for this task.
    if (store.agentTaskId !== newTaskId || store.agentState !== 'running') {
      store.markAgentCached(newTaskId)
    }
  },
  { immediate: true },
)

// Per-rule control menu state — only one menu open at a time.
const openMenuRuleId = ref(null)
function toggleMenu(ruleId) {
  openMenuRuleId.value = openMenuRuleId.value === ruleId ? null : ruleId
}
function closeMenu() {
  openMenuRuleId.value = null
}

// Other tasks the user can move a rule to (excluding the currently selected one).
const otherTasks = computed(() => {
  if (!task.value) return []
  return store.hybridTasks.filter(t => t.id !== task.value.id)
})

async function handleUnassign(rule) {
  if (!task.value) return
  closeMenu()
  await store.unassignRuleFromTask(rule.id, task.value.id)
}

async function handleMove(rule, toTaskId) {
  if (!task.value || !toTaskId) return
  closeMenu()
  await store.moveRuleBetweenTasks(rule.id, task.value.id, toTaskId)
}

async function handleRoleChange(rule, newRole) {
  if (!newRole || newRole === rule.es_role) return
  await store.setRuleEsRole(rule.id, newRole)
}

// Close the rule-control menu on any document click that isn't inside it.
function handleDocClick(e) {
  if (!openMenuRuleId.value) return
  if (!(e.target instanceof Element)) return
  if (!e.target.closest('.hti-rule__menu')) closeMenu()
}
onMounted(() => document.addEventListener('click', handleDocClick))
onBeforeUnmount(() => document.removeEventListener('click', handleDocClick))

const actors = computed(() => {
  if (!task.value) return []
  const ids = task.value.actor_ids || []
  const byId = new Map(store.hybridActors.map(a => [a.id, a]))
  return ids.map(id => byId.get(id)).filter(Boolean)
})

// Defensive dedup by Rule.id only — never collapse rules that share `when` but
// differ in `then` (legitimate channel/case branches in the source BL).
const rules = computed(() => {
  const raw = task.value?.rules || []
  const seen = new Set()
  const out = []
  for (const r of raw) {
    if (!r.id || seen.has(r.id)) continue
    seen.add(r.id)
    out.push(r)
  }
  return out
})

// BC (context_cluster) pre-tagging was removed from the Inspector UI — it
// added noise without helping the user now that each rule is already
// attributed to ONE Task via the agent. Kept as a Rule field for legacy
// readers; see 개선&재구조화.md §2.B retired items.

const functions = computed(() => task.value?.functions || [])
const passages = computed(() => task.value?.document_passages || [])
const conditions = computed(() => task.value?.conditions || [])

// Phase 2.6 internal role → Event Storming element label + sticky color.
// 5-role taxonomy (2026-04-20): invariant + decision were merged into a single
// `aggregate` role because both live inside the same Aggregate and the sub-split
// confused non-developer designers. Phase 5 can still sub-route by inspecting
// `rule.writes_tables` (WRITES → invariant section, no WRITES → domain rule).
const ROLE_META = {
  aggregate:  { label: 'Aggregate',       esColor: 'aggregate', hint: 'Aggregate 내부 규칙 (상태 변경·값 결정·도메인 규칙 포함)' },
  validation: { label: 'Command',         esColor: 'command',   hint: '요청이 들어왔을 때 수용 여부를 가르는 규칙. Command 사전 가드' },
  policy:     { label: 'Policy',          esColor: 'policy',    hint: '어떤 사건이 발생하면 후속 행동을 트리거하는 반응 규칙' },
  query:      { label: 'ReadModel',       esColor: 'readmodel', hint: '데이터를 조회해서 보여주는 규칙 (쓰기 없음). ReadModel 승격' },
  external:   { label: 'External System', esColor: 'external',  hint: '외부 시스템에 질의·호출하는 규칙. ES 승격 제외' },
}
// Legacy values from pre-merge DB entries — map them so existing sessions
// render correctly without requiring a re-ingestion.
const LEGACY_ROLE_MAP = { invariant: 'aggregate', decision: 'aggregate' }
function roleMeta(role) {
  const normalized = LEGACY_ROLE_MAP[role] || role
  return ROLE_META[normalized] || null
}
</script>

<template>
  <aside v-if="task" class="hti-panel">
    <header class="hti-header">
      <div class="hti-header__title">
        <span class="hti-header__idx">{{ (task.sequence_index ?? 0) + 1 }}</span>
        <span class="hti-header__name" :title="task.name">{{ task.name }}</span>
        <button
          v-if="agentState !== 'running'"
          class="hti-rerun"
          :title="agentState === 'cached' ? '재탐색 — 이 Task 에 한해 Agent 재실행' : 'Agent 탐색 시작'"
          @click.stop="rerunAgent"
        >🔄 재탐색</button>
        <span v-else class="hti-rerun hti-rerun--running">
          <span class="hti-rerun__dot"></span> 탐색 중
        </span>
      </div>
      <button class="hti-close" @click="emit('close')" title="닫기">✕</button>
    </header>

    <div class="hti-stats">
      <span class="hti-stat"><b>{{ rules.length }}</b> Rules</span>
      <span class="hti-stat"><b>{{ functions.length }}</b> Functions</span>
      <span class="hti-stat"><b>{{ passages.length }}</b> Passages</span>
      <span class="hti-stat"><b>{{ conditions.length }}</b> Conditions</span>
      <span v-if="isDebug" class="hti-stat hti-stat--debug" title="?debug=1 활성화됨 — 편집 UI 표시 중">DEBUG</span>
    </div>

    <div class="hti-body">
      <!-- Agent Reasoning — live stream of the hierarchical retrieval -->
      <section class="hti-agent hti-section">
        <header
          class="hti-agent__head"
          :class="{ 'is-running': agentState === 'running' }"
          @click="isReasoningExpanded = !isReasoningExpanded"
        >
          <span class="hti-agent__chev" :class="{ 'is-open': isReasoningExpanded }">▸</span>
          <span class="hti-agent__title">Agent Reasoning</span>
          <span v-if="agentState === 'running'" class="hti-agent__badge hti-agent__badge--live">
            진행 중
            <span class="hti-agent__dot"></span>
          </span>
          <span v-else-if="agentState === 'done'" class="hti-agent__badge hti-agent__badge--done">완료</span>
          <span v-else-if="agentState === 'cached'" class="hti-agent__badge hti-agent__badge--cached">캐시됨</span>
          <span v-else-if="agentState === 'error'" class="hti-agent__badge hti-agent__badge--err">오류</span>
        </header>
        <div v-if="isReasoningExpanded" class="hti-agent__body">
          <div v-if="agentState === 'cached' && !agentEvents.length" class="hti-agent__cached">
            <div class="hti-agent__cached-msg">
              <template v-if="rules.length">
                이 Task 의 탐색은 ingestion 중 이미 완료되었습니다. 각 rule 아래 "근거"로 판정 이유가 표시됩니다. 헤더의 🔄 로 재실행 가능합니다.
              </template>
              <template v-else>
                이 Task 에는 ingestion 중 Agent 가 매칭된 rule 을 찾지 못했습니다. 헤더의 🔄 로 재실행 가능합니다.
              </template>
            </div>
          </div>
          <div v-else-if="!agentEvents.length && agentState === 'idle'" class="hti-empty">
            (대기 중)
          </div>
          <div v-else-if="!agentEvents.length && agentState === 'running'" class="hti-agent__starting">
            에이전트가 탐색을 시작합니다…
          </div>
          <div
            v-for="(ev, i) in agentEvents"
            :key="i"
            class="hti-agent__step"
            :class="`hti-agent__step--${ev.type}`"
          >
            <div class="hti-agent__step-title">{{ agentStepLabel(ev) }}</div>
            <div
              v-if="ev.type === 'AgentStepModuleSearch' && ev.candidates"
              class="hti-agent__list"
            >
              <div
                v-for="c in ev.candidates"
                :key="c.fqn"
                class="hti-agent__mod"
                :title="c.summary"
              >
                <span class="hti-agent__mod-score">{{ (c.score * 100).toFixed(0) }}</span>
                <code class="hti-agent__mod-name">{{ c.name }}</code>
              </div>
            </div>
            <div
              v-else-if="ev.type === 'AgentStepBlSearch' && ev.candidates"
              class="hti-agent__list"
            >
              <div
                v-for="c in ev.candidates"
                :key="c.rule_id"
                class="hti-agent__bl"
              >
                <code class="hti-agent__bl-fn">{{ c.source_function || c.rule_id }}</code>
                <span v-if="c.title" class="hti-agent__bl-title">{{ c.title }}</span>
              </div>
            </div>
            <div
              v-else-if="ev.type === 'AgentStepDecision'"
              class="hti-agent__rationale"
              :class="`hti-agent__rationale--${ev.verdict}`"
            >{{ ev.rationale }}</div>
            <div
              v-else-if="ev.type === 'AgentError'"
              class="hti-agent__error"
            >{{ ev.error }}</div>
          </div>
        </div>
      </section>

      <!-- 설명 -->
      <section v-if="task.description" class="hti-section">
        <div class="hti-label">설명</div>
        <div class="hti-text">{{ task.description }}</div>
      </section>

      <!-- Actor + 출처 -->
      <section class="hti-section hti-meta-row">
        <div class="hti-meta">
          <div class="hti-label">수행자</div>
          <div v-if="actors.length" class="hti-chips">
            <span
              v-for="a in actors"
              :key="a.id"
              class="hti-actor-chip"
              :title="a.description || a.name"
            >👤 {{ a.name }}</span>
          </div>
          <div v-else class="hti-empty">미지정</div>
        </div>
        <div v-if="task.source_page || task.source_section" class="hti-meta">
          <div class="hti-label">문서 위치</div>
          <div class="hti-text">
            <span v-if="task.source_section">§ {{ task.source_section }}</span>
            <span v-if="task.source_page" class="hti-badge">p.{{ task.source_page }}</span>
          </div>
        </div>
      </section>

      <!-- 문서 근거 -->
      <section class="hti-section">
        <div class="hti-label">📄 문서 근거 구절</div>
        <div v-if="passages.length" class="hti-stack">
          <article
            v-for="p in passages"
            :key="p.id"
            class="hti-passage"
            :class="{ 'is-low': p.low_confidence }"
          >
            <header class="hti-passage__head">
              <span v-if="p.heading" class="hti-passage__heading">{{ p.heading }}</span>
              <span v-if="p.page != null" class="hti-badge">p.{{ p.page }}</span>
              <span v-if="p.low_confidence" class="hti-badge hti-badge--warn">약한 근거</span>
            </header>
            <p class="hti-passage__body">{{ p.text }}</p>
          </article>
        </div>
        <div v-else class="hti-empty">문서 근거가 아직 없음</div>
      </section>

      <!-- 비즈니스 규칙 (GWT) — flat list; agent already attributed each rule
           to this task so cluster sub-grouping just adds visual noise -->
      <section class="hti-section">
        <div class="hti-label">⚖️ 비즈니스 규칙 (Given-When-Then)</div>
        <div v-if="rules.length" class="hti-stack">
          <article v-for="r in rules" :key="r.id" class="hti-rule">
            <header v-if="r.source_function || r.es_role" class="hti-rule__head">
              <!-- Role badge: always visible. Dropdown to change it: debug only. -->
              <div v-if="roleMeta(r.es_role) && isDebug" class="hti-role-select-wrap">
                <span
                  class="hti-role-badge"
                  :class="`hti-role-badge--${roleMeta(r.es_role).esColor}`"
                  :title="roleMeta(r.es_role).hint"
                >{{ roleMeta(r.es_role).label }}</span>
                <select
                  class="hti-role-select"
                  :value="LEGACY_ROLE_MAP[r.es_role] || r.es_role"
                  :title="'승격 대상 변경 — ' + roleMeta(r.es_role).hint"
                  @change="handleRoleChange(r, $event.target.value)"
                  @click.stop
                >
                  <option value="aggregate">Aggregate</option>
                  <option value="validation">Command</option>
                  <option value="policy">Policy</option>
                  <option value="query">ReadModel</option>
                  <option value="external">External System</option>
                </select>
              </div>
              <span
                v-else-if="roleMeta(r.es_role)"
                class="hti-role-badge"
                :class="`hti-role-badge--${roleMeta(r.es_role).esColor}`"
                :title="roleMeta(r.es_role).hint"
              >{{ roleMeta(r.es_role).label }}</span>
              <code v-if="r.source_function" class="hti-rule__fn">{{ r.source_function }}</code>
              <span v-if="r.source_module" class="hti-rule__mod">{{ r.source_module }}</span>

              <!-- Control menu (move/remove) — DEBUG ONLY (§2.D) -->
              <div v-if="isDebug" class="hti-rule__menu" @click.stop>
                <button
                  class="hti-menu-btn"
                  :class="{ 'is-open': openMenuRuleId === r.id }"
                  title="BL 제어"
                  @click="toggleMenu(r.id)"
                >⋯</button>
                <div v-if="openMenuRuleId === r.id" class="hti-menu-pop">
                  <div class="hti-menu-section">
                    <div class="hti-menu-label">다른 Task로 이동</div>
                    <button
                      v-for="t in otherTasks"
                      :key="t.id"
                      class="hti-menu-item"
                      @click="handleMove(r, t.id)"
                    >{{ t.name }}</button>
                    <div v-if="!otherTasks.length" class="hti-menu-empty">이동할 Task 없음</div>
                  </div>
                  <div class="hti-menu-section hti-menu-section--danger">
                    <button class="hti-menu-item hti-menu-item--danger" @click="handleUnassign(r)">
                      이 Task에서 제거
                    </button>
                  </div>
                </div>
              </div>
            </header>
            <p v-if="r.title" class="hti-rule__title">{{ r.title }}</p>
            <p
              v-if="r.rationale"
              class="hti-rule__rationale"
              :title="r.evidence_refs?.join(', ')"
            >
              <span class="hti-rule__rationale-label">근거</span>
              {{ r.rationale }}
            </p>
            <dl class="hti-gwt">
              <div v-if="r.given" class="hti-gwt__row">
                <dt>GIVEN</dt><dd>{{ r.given }}</dd>
              </div>
              <div v-if="r.when" class="hti-gwt__row">
                <dt>WHEN</dt><dd>{{ r.when }}</dd>
              </div>
              <div v-if="r.then" class="hti-gwt__row">
                <dt>THEN</dt><dd>{{ r.then }}</dd>
              </div>
            </dl>
          </article>
        </div>
        <div v-else class="hti-empty">매핑된 규칙 없음</div>
      </section>

      <!-- 매핑된 함수 -->
      <section class="hti-section">
        <div class="hti-label">🔧 매핑된 함수</div>
        <div v-if="functions.length" class="hti-stack">
          <article v-for="fn in functions" :key="fn.id || fn.name" class="hti-fn">
            <div class="hti-fn__row">
              <code class="hti-fn__name">{{ fn.name }}</code>
              <span v-if="fn.module" class="hti-fn__mod">{{ fn.module }}</span>
            </div>
            <p v-if="fn.summary" class="hti-fn__summary">{{ fn.summary }}</p>
          </article>
        </div>
        <div v-else class="hti-empty">매핑된 함수 없음</div>
      </section>

      <!-- 통합 조건 -->
      <section class="hti-section">
        <div class="hti-label">✅ 통합 조건</div>
        <ol v-if="conditions.length" class="hti-conds">
          <li
            v-for="(c, i) in conditions"
            :key="i"
            class="hti-cond"
          >{{ typeof c === 'string' ? c : (c.expression || c.text) }}</li>
        </ol>
        <div v-else class="hti-empty">조건이 추출되지 않음</div>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.hti-panel {
  width: 420px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-elevated, #1b1f2a);
  border-left: 1px solid var(--color-border, rgba(255,255,255,0.08));
  overflow: hidden;
}

/* Header ------------------------------------------------ */
.hti-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border, rgba(255,255,255,0.08));
  background: linear-gradient(180deg, rgba(92,124,250,0.14), rgba(92,124,250,0.06));
}
.hti-header__title {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  overflow: hidden;
}
.hti-header__idx {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--color-command, #5c7cfa);
  background: rgba(92, 124, 250, 0.25);
  border-radius: 50%;
}
.hti-header__name {
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--color-text-bright, #fff);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hti-close {
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: var(--color-text-dim);
  cursor: pointer;
  font-size: 1rem;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  line-height: 1;
}
.hti-close:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-text-bright);
}

/* Re-search button (next to task name) */
.hti-rerun {
  flex-shrink: 0;
  margin-left: 8px;
  padding: 3px 8px;
  font-size: 0.65rem;
  font-weight: 600;
  background: rgba(92, 124, 250, 0.15);
  color: #9cb2ff;
  border: 1px solid rgba(92, 124, 250, 0.35);
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
}
.hti-rerun:hover { background: rgba(92, 124, 250, 0.28); }
.hti-rerun--running {
  background: rgba(92, 124, 250, 0.25);
  color: #9cb2ff;
  cursor: default;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.hti-rerun__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #e03131;
  animation: pulse 1s ease-in-out infinite;
}

/* Stats strip ------------------------------------------- */
.hti-stats {
  display: flex;
  gap: 14px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--color-border, rgba(255,255,255,0.06));
  background: rgba(255,255,255,0.02);
  font-size: 0.68rem;
  color: var(--color-text-dim);
}
.hti-stat b {
  color: var(--color-text-bright);
  font-weight: 700;
  margin-right: 3px;
}

/* Body -------------------------------------------------- */
.hti-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.hti-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.hti-meta-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.hti-meta {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.hti-label {
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-dim);
}
.hti-text {
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--color-text);
  word-break: break-word;
}
.hti-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.hti-actor-chip {
  font-size: 0.68rem;
  padding: 3px 9px;
  border-radius: 11px;
  background: rgba(32, 201, 151, 0.15);
  color: var(--color-text-bright);
}
.hti-empty {
  font-size: 0.72rem;
  font-style: italic;
  color: var(--color-text-dim);
  opacity: 0.65;
  padding: 2px 0;
}
.hti-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 0.6rem;
  background: rgba(255,255,255,0.08);
  color: var(--color-text-dim);
}
.hti-badge--warn {
  background: rgba(255, 190, 100, 0.18);
  color: #ffb464;
}

/* BC (context_cluster) badge --------------------------- */
.hti-bc-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 11px;
  font-size: 0.68rem;
  font-weight: 600;
  background: rgba(92, 124, 250, 0.20);
  color: #9cb2ff;
  border: 1px solid rgba(92, 124, 250, 0.28);
}
.hti-bc-badge--unclassified {
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-dim);
  border-color: rgba(255, 255, 255, 0.1);
}

/* ES element badge (Phase 2.6 → ES promotion target) ------
 * Uses the project's Event Storming sticky palette so the badge color
 * matches what the Rule will look like after Phase 5 promotion.
 */
.hti-role-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  border: 1px solid transparent;
}
.hti-role-badge--aggregate {
  background: rgba(252, 196, 25, 0.20);
  color: var(--color-aggregate, #fcc419);
  border-color: rgba(252, 196, 25, 0.45);
}
.hti-role-badge--command {
  background: rgba(92, 124, 250, 0.22);
  color: var(--color-command-light, #748ffc);
  border-color: rgba(92, 124, 250, 0.45);
}
.hti-role-badge--policy {
  background: rgba(177, 151, 252, 0.20);
  color: var(--color-policy-light, #d0bfff);
  border-color: rgba(177, 151, 252, 0.45);
}
.hti-role-badge--readmodel {
  background: rgba(64, 192, 87, 0.20);
  color: var(--color-readmodel-light, #51cf66);
  border-color: rgba(64, 192, 87, 0.45);
}
.hti-role-badge--external {
  background: rgba(230, 73, 128, 0.18);
  color: #f783ac;
  border-color: rgba(230, 73, 128, 0.45);
}

/* Role dropdown — invisible <select> overlay on top of the badge.
 * Lets the user pick a different es_role without an extra button UI. */
.hti-role-select-wrap {
  position: relative;
  display: inline-flex;
  cursor: pointer;
}
.hti-role-select-wrap:hover .hti-role-badge {
  filter: brightness(1.2);
  outline: 1px dashed currentColor;
  outline-offset: 1px;
}
.hti-role-select {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
  appearance: none;
  background: transparent;
  border: none;
  font: inherit;
  color: inherit;
}

/* Per-rule "⋯" menu */
.hti-rule__menu {
  position: relative;
  margin-left: auto;
}
.hti-menu-btn {
  width: 22px;
  height: 22px;
  padding: 0;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 5px;
  color: var(--color-text-dim);
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  transition: background 0.12s, border-color 0.12s;
}
.hti-menu-btn:hover,
.hti-menu-btn.is-open {
  background: rgba(255,255,255,0.06);
  border-color: rgba(255,255,255,0.12);
  color: var(--color-text-bright);
}
.hti-menu-pop {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  min-width: 220px;
  max-width: 300px;
  background: var(--color-bg-elevated, #242936);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 6px;
  box-shadow: 0 10px 28px rgba(0,0,0,0.35);
  padding: 6px 0;
  z-index: 50;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.hti-menu-section {
  display: flex;
  flex-direction: column;
  padding: 4px 0;
}
.hti-menu-section + .hti-menu-section {
  border-top: 1px solid rgba(255,255,255,0.06);
  margin-top: 2px;
}
.hti-menu-label {
  padding: 3px 10px 4px;
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-dim);
}
.hti-menu-item {
  text-align: left;
  padding: 5px 10px;
  background: transparent;
  border: none;
  font-size: 0.72rem;
  color: var(--color-text);
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hti-menu-item:hover {
  background: rgba(92, 124, 250, 0.18);
}
.hti-menu-item--danger {
  color: #ff8a8a;
}
.hti-menu-item--danger:hover {
  background: rgba(230, 73, 73, 0.18);
}
.hti-menu-empty {
  padding: 4px 10px;
  font-size: 0.68rem;
  color: var(--color-text-dim);
  font-style: italic;
}
.hti-rule-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 0 4px;
  border-top: 1px dashed rgba(255, 255, 255, 0.05);
}
.hti-rule-group:first-child {
  padding-top: 0;
  border-top: none;
}
.hti-rule-group__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}
.hti-rule-group__count {
  font-size: 0.62rem;
  color: var(--color-text-dim);
}
.hti-rule__title {
  font-size: 0.74rem;
  color: var(--color-text);
  margin: 0 0 6px;
  line-height: 1.45;
  word-break: keep-all;
}

.hti-stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Passage ---------------------------------------------- */
.hti-passage {
  padding: 8px 10px;
  background: rgba(100, 190, 255, 0.07);
  border-left: 3px solid #64beff;
  border-radius: 4px;
}
.hti-passage.is-low {
  border-left-color: rgba(100, 190, 255, 0.35);
  opacity: 0.85;
}
.hti-passage__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
.hti-passage__heading {
  font-weight: 600;
  font-size: 0.7rem;
  color: #64beff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 260px;
}
.hti-passage__body {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.55;
  color: var(--color-text);
  word-break: break-word;
  white-space: pre-wrap;
}

/* Rule GWT --------------------------------------------- */
.hti-rule {
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(245, 180, 65, 0.18);
  border-left: 3px solid var(--color-policy, #f5b441);
  border-radius: 4px;
}
.hti-rule__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px dashed rgba(255,255,255,0.08);
}
.hti-rule__fn {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 0.74rem;
  color: var(--color-text-bright);
  font-weight: 600;
}
.hti-rule__mod {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 0.6rem;
  color: var(--color-text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}
.hti-gwt {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hti-gwt__row {
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: 8px;
  align-items: start;
}
.hti-gwt__row dt {
  font-weight: 700;
  font-size: 0.62rem;
  letter-spacing: 0.08em;
  color: var(--color-policy, #f5b441);
  padding-top: 2px;
}
.hti-gwt__row dd {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.5;
  color: var(--color-text);
  word-break: break-word;
}

/* Function --------------------------------------------- */
.hti-fn {
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
}
.hti-fn__row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.hti-fn__name {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 0.76rem;
  color: var(--color-text-bright);
  font-weight: 600;
}
.hti-fn__mod {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 0.6rem;
  color: var(--color-text-dim);
}
.hti-fn__summary {
  margin: 6px 0 0;
  font-size: 0.7rem;
  color: var(--color-text-dim);
  line-height: 1.5;
}

/* Debug mode marker */
.hti-stat--debug {
  font-size: 0.58rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(230, 73, 128, 0.2);
  color: #f783ac;
  letter-spacing: 0.08em;
}

/* Agent Reasoning ------------------------------------- */
.hti-agent {
  border: 1px solid rgba(92, 124, 250, 0.2);
  border-radius: 4px;
  background: rgba(92, 124, 250, 0.04);
  overflow: hidden;
}
.hti-agent__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--color-text-dim);
}
.hti-agent__head:hover { color: var(--color-text-bright); }
.hti-agent__head.is-running { color: #9cb2ff; }
.hti-agent__chev {
  display: inline-block;
  font-size: 0.6rem;
  color: var(--color-text-dim);
  transition: transform 0.15s;
}
.hti-agent__chev.is-open { transform: rotate(90deg); }
.hti-agent__title { flex: 1; }
.hti-agent__badge {
  font-size: 0.55rem;
  padding: 1px 8px;
  border-radius: 10px;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.hti-agent__badge--live {
  background: rgba(92, 124, 250, 0.25);
  color: #9cb2ff;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.hti-agent__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #e03131;
  animation: pulse 1s ease-in-out infinite;
}
.hti-agent__badge--done {
  background: rgba(64, 192, 87, 0.22);
  color: #8ce3a0;
}
.hti-agent__badge--err {
  background: rgba(230, 73, 73, 0.22);
  color: #ff9a9a;
}
.hti-agent__body {
  padding: 4px 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  /* Cap the height when live event stream gets long; panel scroll handles overflow */
  max-height: 360px;
  overflow-y: auto;
}
.hti-agent__starting {
  font-size: 0.68rem;
  color: var(--color-text-dim);
  font-style: italic;
  padding: 4px 0;
}
.hti-agent__cached {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px 2px;
}
.hti-agent__cached-msg {
  font-size: 0.68rem;
  color: var(--color-text-dim);
  line-height: 1.45;
}
.hti-agent__rerun-icon {
  margin-left: 4px;
  padding: 2px 6px;
  font-size: 0.7rem;
  line-height: 1;
  background: transparent;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 4px;
  color: var(--color-text-dim);
  cursor: pointer;
  transition: background 0.12s, color 0.12s, border-color 0.12s;
}
.hti-agent__rerun-icon:hover {
  background: rgba(92, 124, 250, 0.18);
  color: #9cb2ff;
  border-color: rgba(92, 124, 250, 0.4);
}
.hti-agent__badge--cached {
  background: rgba(255, 255, 255, 0.08);
  color: var(--color-text-dim);
}
.hti-agent__step {
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
  border-left: 2px solid rgba(92, 124, 250, 0.45);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hti-agent__step--AgentFinalMatches,
.hti-agent__step--AgentDone {
  border-left-color: rgba(64, 192, 87, 0.6);
}
.hti-agent__step--AgentError {
  border-left-color: rgba(230, 73, 73, 0.6);
}
.hti-agent__step-title {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--color-text-bright);
}
.hti-agent__list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-left: 6px;
}
.hti-agent__mod {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.66rem;
}
.hti-agent__mod-score {
  min-width: 22px;
  font-weight: 700;
  color: #9cb2ff;
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 0.6rem;
}
.hti-agent__mod-name {
  font-family: 'SF Mono', Menlo, monospace;
  color: var(--color-text);
}
.hti-agent__bl {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 0.66rem;
  overflow: hidden;
}
.hti-agent__bl-fn {
  font-family: 'SF Mono', Menlo, monospace;
  color: var(--color-text);
  flex-shrink: 0;
}
.hti-agent__bl-title {
  color: var(--color-text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hti-agent__rationale {
  font-size: 0.72rem;
  line-height: 1.5;
  color: var(--color-text);
  padding: 4px 8px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.04);
}
.hti-agent__rationale--accept {
  background: rgba(64, 192, 87, 0.1);
  color: #c6e9cf;
}
.hti-agent__rationale--reject {
  background: rgba(255, 255, 255, 0.04);
  color: var(--color-text-dim);
  text-decoration: line-through wavy rgba(230, 73, 73, 0.4);
}
.hti-agent__error {
  font-size: 0.7rem;
  color: #ff9a9a;
  padding: 2px 4px;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* Rule rationale — cached Agent output surfaced under each rule title */
.hti-rule__rationale {
  margin: 0 0 8px;
  padding: 6px 9px;
  border-radius: 3px;
  background: rgba(64, 192, 87, 0.08);
  border-left: 2px solid rgba(64, 192, 87, 0.45);
  font-size: 0.72rem;
  line-height: 1.5;
  color: var(--color-text);
  word-break: break-word;
}
.hti-rule__rationale-label {
  display: inline-block;
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #8ce3a0;
  margin-right: 6px;
}

/* Conditions ------------------------------------------- */
.hti-conds {
  margin: 0;
  padding: 0 0 0 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hti-cond {
  font-size: 0.78rem;
  line-height: 1.55;
  color: var(--color-text);
  padding-left: 4px;
}
.hti-cond::marker {
  color: var(--color-text-dim);
  font-weight: 600;
}
</style>
