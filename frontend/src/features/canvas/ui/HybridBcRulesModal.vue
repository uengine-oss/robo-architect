<script setup>
/**
 * BC(Bounded Context) 별 Rule 관리 모달.
 *
 * Navigator 의 "Rules by Context" 행을 클릭하면 열리고, 해당 BC 에 속한 모든
 * Rule 을 나열한다. 각 행에서 역할 변경·Task 재배치·Task 에서 제거 까지 수행
 * 가능해 BC 단위 일괄 정리에 쓰는 미니 Rule Manager 역할.
 */
import { computed } from 'vue'
import { useBpmnStore } from '@/features/canvas/bpmn.store'

const store = useBpmnStore()

const cluster = computed(() => store.bcRulesModalCluster)
const isOpen = computed(() => !!cluster.value)

const rules = computed(() => {
  if (!cluster.value) return []
  return store.hybridRules.filter(
    r => (r.context_cluster || '미분류') === cluster.value,
  )
})

// For each rule, which tasks does it currently belong to?
// We scan hybridTasks.rules[] because that's the live-source-of-truth after
// user moves/unassigns via optimistic update.
const taskIdsByRuleId = computed(() => {
  const map = {}
  for (const t of store.hybridTasks) {
    for (const r of (t.rules || [])) {
      if (!map[r.id]) map[r.id] = []
      map[r.id].push(t.id)
    }
  }
  return map
})

const taskById = computed(() => {
  const m = {}
  for (const t of store.hybridTasks) m[t.id] = t
  return m
})

const ROLE_OPTIONS = [
  { value: 'aggregate',  label: 'Aggregate' },
  { value: 'validation', label: 'Command' },
  { value: 'policy',     label: 'Policy' },
  { value: 'query',      label: 'ReadModel' },
  { value: 'external',   label: 'External System' },
]
const LEGACY_ROLE_MAP = { invariant: 'aggregate', decision: 'aggregate' }
function normalizedRole(r) {
  return LEGACY_ROLE_MAP[r] || r || ''
}

async function onRoleChange(rule, newRole) {
  if (!newRole || normalizedRole(rule.es_role) === newRole) return
  await store.setRuleEsRole(rule.id, newRole)
}

async function onUnassign(rule, taskId) {
  await store.unassignRuleFromTask(rule.id, taskId)
}

async function onMove(rule, fromTaskId, toTaskId) {
  if (!toTaskId || toTaskId === fromTaskId) return
  await store.moveRuleBetweenTasks(rule.id, fromTaskId, toTaskId)
}

async function onAssign(rule, taskId) {
  if (!taskId) return
  await store.assignRuleToTask(rule.id, taskId)
}

function close() {
  store.closeBcRulesModal()
}
</script>

<template>
  <transition name="bc-modal">
    <div v-if="isOpen" class="bc-modal-backdrop" @click.self="close">
      <div class="bc-modal" role="dialog" aria-modal="true">
        <header class="bc-modal__header">
          <div class="bc-modal__title">
            <span class="bc-modal__cluster">{{ cluster }}</span>
            <span class="bc-modal__count">{{ rules.length }} rules</span>
          </div>
          <button class="bc-modal__close" @click="close" title="닫기">✕</button>
        </header>

        <div class="bc-modal__body">
          <div v-if="rules.length === 0" class="bc-modal__empty">
            이 범주에 속한 Rule 이 없습니다.
          </div>

          <article
            v-for="r in rules"
            :key="r.id"
            class="bc-rule"
          >
            <header class="bc-rule__head">
              <select
                class="bc-rule__role"
                :value="normalizedRole(r.es_role)"
                @change="onRoleChange(r, $event.target.value)"
              >
                <option
                  v-for="opt in ROLE_OPTIONS"
                  :key="opt.value"
                  :value="opt.value"
                >{{ opt.label }}</option>
              </select>
              <code class="bc-rule__fn">{{ r.source_function }}</code>
            </header>

            <p v-if="r.title" class="bc-rule__title">{{ r.title }}</p>

            <div class="bc-rule__mappings">
              <div class="bc-rule__mappings-label">연결된 Task</div>
              <div v-if="(taskIdsByRuleId[r.id] || []).length === 0" class="bc-rule__empty">
                어느 Task 에도 붙어있지 않음 (미매핑)
              </div>
              <div
                v-for="taskId in (taskIdsByRuleId[r.id] || [])"
                :key="taskId"
                class="bc-rule__mapping"
              >
                <span class="bc-rule__task-name">{{ taskById[taskId]?.name || taskId }}</span>
                <select
                  class="bc-rule__move"
                  value=""
                  @change="onMove(r, taskId, $event.target.value); $event.target.value = ''"
                >
                  <option value="">이동…</option>
                  <option
                    v-for="t in store.hybridTasks.filter(t => t.id !== taskId)"
                    :key="t.id"
                    :value="t.id"
                  >{{ t.name }}</option>
                </select>
                <button
                  class="bc-rule__remove"
                  @click="onUnassign(r, taskId)"
                  title="이 Task 에서 제거"
                >제거</button>
              </div>

              <div class="bc-rule__add">
                <select
                  class="bc-rule__add-select"
                  value=""
                  @change="onAssign(r, $event.target.value); $event.target.value = ''"
                >
                  <option value="">다른 Task 에 추가…</option>
                  <option
                    v-for="t in store.hybridTasks.filter(
                      t => !(taskIdsByRuleId[r.id] || []).includes(t.id),
                    )"
                    :key="t.id"
                    :value="t.id"
                  >{{ t.name }}</option>
                </select>
              </div>
            </div>
          </article>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.bc-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9000;
}
.bc-modal {
  width: min(720px, 92vw);
  max-height: 82vh;
  background: var(--color-bg-elevated, #1b1f2a);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

/* Header */
.bc-modal__header {
  display: flex;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  gap: 12px;
}
.bc-modal__title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex: 1;
  min-width: 0;
}
.bc-modal__cluster {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-text-bright);
}
.bc-modal__count {
  font-size: 0.72rem;
  color: var(--color-text-dim);
}
.bc-modal__close {
  width: 28px;
  height: 28px;
  padding: 0;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: var(--color-text-dim);
  cursor: pointer;
  font-size: 0.9rem;
  line-height: 1;
}
.bc-modal__close:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-bright);
}

/* Body */
.bc-modal__body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.bc-modal__empty {
  font-size: 0.8rem;
  color: var(--color-text-dim);
  font-style: italic;
  text-align: center;
  padding: 30px 0;
}

/* Rule card */
.bc-rule {
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.bc-rule__head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.bc-rule__role {
  padding: 3px 8px;
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 5px;
  color: var(--color-text);
  cursor: pointer;
}
.bc-rule__fn {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 0.72rem;
  color: var(--color-text-bright);
  font-weight: 600;
}
.bc-rule__title {
  margin: 0;
  font-size: 0.78rem;
  color: var(--color-text);
  line-height: 1.45;
}

/* Mappings */
.bc-rule__mappings {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 6px;
  border-top: 1px dashed rgba(255, 255, 255, 0.08);
}
.bc-rule__mappings-label {
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-dim);
}
.bc-rule__empty {
  font-size: 0.68rem;
  font-style: italic;
  color: var(--color-text-dim);
  opacity: 0.7;
}
.bc-rule__mapping {
  display: flex;
  align-items: center;
  gap: 6px;
}
.bc-rule__task-name {
  flex: 1;
  min-width: 0;
  font-size: 0.72rem;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bc-rule__move,
.bc-rule__add-select {
  padding: 3px 6px;
  font-size: 0.64rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  color: var(--color-text);
  cursor: pointer;
}
.bc-rule__remove {
  padding: 3px 9px;
  font-size: 0.64rem;
  background: rgba(230, 73, 73, 0.14);
  color: #ff9a9a;
  border: 1px solid rgba(230, 73, 73, 0.3);
  border-radius: 4px;
  cursor: pointer;
}
.bc-rule__remove:hover {
  background: rgba(230, 73, 73, 0.28);
}
.bc-rule__add {
  margin-top: 2px;
}

/* Transition */
.bc-modal-enter-active,
.bc-modal-leave-active {
  transition: opacity 0.15s ease;
}
.bc-modal-enter-active .bc-modal,
.bc-modal-leave-active .bc-modal {
  transition: transform 0.15s ease;
}
.bc-modal-enter-from,
.bc-modal-leave-to {
  opacity: 0;
}
.bc-modal-enter-from .bc-modal,
.bc-modal-leave-to .bc-modal {
  transform: translateY(12px);
}
</style>
