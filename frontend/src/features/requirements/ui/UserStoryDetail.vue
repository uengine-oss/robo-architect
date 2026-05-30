<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'
import ClarificationPanel from './ClarificationPanel.vue'
import ClarityRadar from './ClarityRadar.vue'
import EditHistoryPanel from './EditHistoryPanel.vue'

const props = defineProps({
  userStory: { type: Object, default: null },
})

const store = useRequirementsStore()

const kindLabel = { given: 'Given', when: 'When', then: 'Then' }

const hasStory = computed(() => !!props.userStory)
const criteria = computed(() => props.userStory?.acceptanceCriteria || [])

// ── Source business rules (hybrid US only — empty for rfp/figma) ─────
const sourceRules = ref([])

async function fetchSourceRules(usId) {
  if (!usId) {
    sourceRules.value = []
    return
  }
  try {
    const response = await fetch(`/api/graph/traceability/userstory/${encodeURIComponent(usId)}/source-rules`)
    if (!response.ok) {
      sourceRules.value = []
      return
    }
    const data = await response.json()
    sourceRules.value = Array.isArray(data?.rules) ? data.rules : []
  } catch (e) {
    sourceRules.value = []
  }
}

// ── Tabs (spec 030) ─────────────────────────────────────────────────
// "overview" = the existing detail view; "clarification" = the new
// per-UserStory clarification surface that lives inside this panel.
const activeTab = ref('overview')

const ambiguityFlag = computed(() => {
  const id = props.userStory?.id
  if (!id) return null
  return store.clarificationFlags[id] || null
})

// When the user opens a new story, reset to overview unless the new story
// is flagged — then jump straight to the clarification tab so the user
// sees the "needs attention" surface immediately.
watch(() => props.userStory?.id, (id) => {
  if (id) {
    fetchSourceRules(id)
    if (store.clarificationFlags[id]) {
      onSelectTab('clarification')
    } else {
      activeTab.value = 'overview'
    }
  } else {
    sourceRules.value = []
    activeTab.value = 'overview'
  }
}, { immediate: true })

// The clarification tab is "live" for the current user story even when no
// session has started yet — selecting the tab fires a single-story session
// the first time (or re-uses an existing one for this scope).
const isCurrentSession = computed(() => {
  const sess = store.clarificationSession
  const id = props.userStory?.id
  return !!(sess && id && sess.scope?.scopeType === 'user_story' && sess.scope?.scopeId === id)
})

async function startClarificationHere() {
  if (!props.userStory?.id) return
  if (isCurrentSession.value) return
  try {
    await store.startClarification('user_story', props.userStory.id)
  } catch (e) {
    window.alert(`명확화 시작 실패: ${e?.message || e}`)
  }
}

function onSelectTab(name) {
  activeTab.value = name
  if (name === 'clarification' && props.userStory?.id && !isCurrentSession.value) {
    startClarificationHere()
  }
  if (name === 'history' && props.userStory?.id) {
    store.fetchHistory(props.userStory.id)
  }
  if (name === 'edit' && props.userStory) {
    resetEditForm()
  }
}

// ── Edit form (spec 033) ─────────────────────────────────────────────────

const editForm = reactive({ role: '', action: '', benefit: '', priority: 'medium', status: 'draft' })
const editNotice = ref(null)

function resetEditForm() {
  const us = props.userStory
  if (!us) return
  editForm.role = us.role || ''
  editForm.action = us.action || ''
  editForm.benefit = us.benefit || ''
  editForm.priority = us.priority || 'medium'
  editForm.status = us.status || 'draft'
  editNotice.value = null
}

async function saveEdit() {
  if (!props.userStory?.id) return
  editNotice.value = null
  try {
    await store.updateUserStory(props.userStory.id, {
      role: editForm.role,
      action: editForm.action,
      benefit: editForm.benefit,
      priority: editForm.priority,
      status: editForm.status,
    })
    editNotice.value = { type: 'success', text: '저장되었습니다.' }
    activeTab.value = 'overview'
  } catch (e) {
    editNotice.value = { type: 'error', text: e.message || '저장 실패' }
  }
}
</script>

<template>
  <div class="us-detail">
    <div v-if="!hasStory" class="us-detail__empty">
      <p class="us-detail__empty-hint">왼쪽 트리에서 User Story를 선택하세요.</p>
      <ClarityRadar v-if="store.clarityScores" :scores="store.clarityScores" />
    </div>
    <template v-else>
      <!-- Tab bar (spec 030 + 033) ──────────────────────────────────── -->
      <div class="us-tabs">
        <button class="us-tab" :class="{ 'is-active': activeTab === 'overview' }" @click="onSelectTab('overview')">개요</button>
        <button class="us-tab" :class="{ 'is-active': activeTab === 'edit' }" @click="onSelectTab('edit')">편집</button>
        <button class="us-tab" :class="{ 'is-active': activeTab === 'clarification' }" @click="onSelectTab('clarification')">
          명확화
          <span v-if="ambiguityFlag" class="tab-badge" :title="ambiguityFlag.categories.join(', ')">
            ❓ {{ (ambiguityFlag.questionIds || []).length }}
          </span>
        </button>
        <button class="us-tab" :class="{ 'is-active': activeTab === 'history' }" @click="onSelectTab('history')">이력</button>
      </div>

      <!-- Overview tab ──────────────────────────────────────────── -->
      <div v-if="activeTab === 'overview'" class="us-tab-body">
        <div class="us-detail__statement">
          <span class="frag frag--role">As a {{ userStory.role || '사용자' }}</span>
          <span class="frag frag--action">I want {{ userStory.action }}</span>
          <span v-if="userStory.benefit" class="frag frag--benefit">so that {{ userStory.benefit }}</span>
        </div>

        <div class="us-detail__meta">
          <span class="badge">우선순위: {{ userStory.priority || 'medium' }}</span>
          <span class="badge">상태: {{ userStory.status || 'draft' }}</span>
          <span v-if="userStory.commandName" class="badge badge--cmd">
            Command: {{ userStory.commandName }}
          </span>
        </div>

        <div v-if="sourceRules.length > 0" class="source-rules">
          <div class="source-rules__title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
            </svg>
            Source Business Rules ({{ sourceRules.length }})
          </div>
          <ul class="source-rules__list">
            <li v-for="rule in sourceRules" :key="rule.rule_id" class="source-rule-item">
              <span v-if="rule.local_id" class="source-rule-seq">{{ rule.local_id }}</span>
              <span class="source-rule-stmt">{{ rule.statement }}</span>
              <code v-if="rule.source_function" class="source-rule-fn">{{ rule.source_function }}</code>
            </li>
          </ul>
        </div>

        <div class="us-detail__criteria">
          <h4>인수조건 (Acceptance Criteria)</h4>
          <p v-if="!criteria.length" class="us-detail__no-criteria">
            {{ userStory.commandId ? '인수조건 없음' : '연결된 Command가 없어 인수조건을 표시할 수 없습니다.' }}
          </p>
          <ul v-else>
            <li v-for="(c, i) in criteria" :key="i">
              <span class="gwt-kind" :class="`gwt-kind--${c.kind}`">{{ kindLabel[c.kind] }}</span>
              <span class="gwt-name">{{ c.name }}</span>
              <span v-if="c.description" class="gwt-desc">— {{ c.description }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- Edit tab (spec 033) ──────────────────────────────────── -->
      <div v-else-if="activeTab === 'edit'" class="us-tab-body">
        <div v-if="editNotice" class="edit-notice" :class="`edit-notice--${editNotice.type}`">
          {{ editNotice.text }}
        </div>
        <div class="edit-form">
          <label class="edit-field">
            <span class="edit-field__label">역할 (As a)</span>
            <input v-model="editForm.role" class="edit-input" placeholder="법정대리인" />
          </label>
          <label class="edit-field">
            <span class="edit-field__label">목적 (I want)</span>
            <textarea v-model="editForm.action" class="edit-textarea" rows="3" placeholder="업무처리 동의 또는 확인을 한다" />
          </label>
          <label class="edit-field">
            <span class="edit-field__label">혜택 (so that)</span>
            <textarea v-model="editForm.benefit" class="edit-textarea" rows="2" placeholder="미성년자 또는 대리 동의가 필요한 고객의 회원가입 및 관련 업무가 적법하게 처리된다" />
          </label>
          <div class="edit-row">
            <label class="edit-field edit-field--half">
              <span class="edit-field__label">우선순위</span>
              <select v-model="editForm.priority" class="edit-select">
                <option value="high">high</option>
                <option value="medium">medium</option>
                <option value="low">low</option>
              </select>
            </label>
            <label class="edit-field edit-field--half">
              <span class="edit-field__label">상태</span>
              <select v-model="editForm.status" class="edit-select">
                <option value="draft">draft</option>
                <option value="ready">ready</option>
                <option value="done">done</option>
              </select>
            </label>
          </div>
          <div class="edit-actions">
            <button class="btn btn--secondary" @click="onSelectTab('overview')">취소</button>
            <button class="btn btn--primary" :disabled="store.editSaving" @click="saveEdit">
              {{ store.editSaving ? '저장 중…' : '저장' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Clarification tab (spec 030) ─────────────────────────── -->
      <div v-else-if="activeTab === 'clarification'" class="us-tab-body us-tab-body--clarification">
        <ClarificationPanel embedded />
      </div>

      <!-- History tab (spec 033) ───────────────────────────────── -->
      <div v-else-if="activeTab === 'history'" class="us-tab-body">
        <EditHistoryPanel :items="store.editHistory" :loading="store.editHistoryLoading" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.us-detail { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.us-detail__empty {
  display: flex; flex-direction: column; align-items: center; gap: 16px;
  color: var(--color-text-light); font-size: 0.85rem; padding: 16px;
  overflow-y: auto;
}
.us-detail__empty-hint { margin: 0; padding-top: 8px; }

/* Tab bar */
.us-tabs {
  display: flex; align-items: center; gap: 4px;
  padding: 6px 12px 0; flex-shrink: 0;
  border-bottom: 1px solid var(--color-border);
}
.us-tab {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px;
  font-size: 0.78rem; font-weight: 600;
  background: transparent; border: 1px solid transparent;
  border-bottom: 2px solid transparent;
  color: var(--color-text-light); cursor: pointer;
  border-radius: 6px 6px 0 0;
}
.us-tab:hover { color: var(--color-text); }
.us-tab.is-active {
  color: var(--color-text);
  border-bottom-color: var(--color-accent, #228be6);
  background: var(--color-bg-tertiary);
}
.tab-badge {
  font-size: 0.66rem; padding: 1px 6px; border-radius: 4px;
  background: rgba(255, 196, 0, 0.25); color: #8a6500;
}

/* Edit form */
.edit-form { display: flex; flex-direction: column; gap: 12px; }
.edit-field { display: flex; flex-direction: column; gap: 4px; }
.edit-field--half { flex: 1; }
.edit-field__label { font-size: 0.72rem; font-weight: 600; color: var(--color-text-light); }
.edit-input,
.edit-textarea,
.edit-select {
  font-size: 0.85rem;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
  color: var(--color-text);
  width: 100%;
  box-sizing: border-box;
}
.edit-textarea { resize: vertical; font-family: inherit; }
.edit-row { display: flex; gap: 12px; }
.edit-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
.btn { padding: 6px 18px; border-radius: 6px; font-size: 0.82rem; font-weight: 600; cursor: pointer; border: none; }
.btn--primary { background: var(--color-accent, #228be6); color: #fff; }
.btn--primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn--secondary { background: var(--color-bg-tertiary); color: var(--color-text); }
.edit-notice {
  padding: 8px 12px; border-radius: 6px; font-size: 0.8rem; margin-bottom: 4px;
}
.edit-notice--success { background: rgba(47, 158, 68, 0.15); color: #2f9e44; }
.edit-notice--error { background: rgba(224, 49, 49, 0.15); color: #e03131; }

.us-tab-body {
  flex: 1; overflow-y: auto;
  padding: 16px;
}
.us-tab-body--clarification {
  padding: 8px;
}

.us-detail__statement {
  display: flex; flex-direction: column; gap: 4px;
  padding: 14px; border-radius: 8px; background: var(--color-bg-tertiary);
}
.frag { font-size: 0.95rem; }
.frag--role { color: var(--color-text-light); }
.frag--action { font-weight: 700; color: var(--color-text); font-size: 1.05rem; }
.frag--benefit { color: var(--color-text-light); font-style: italic; }
.us-detail__meta { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
.badge {
  font-size: 0.68rem; padding: 2px 8px; border-radius: 10px;
  background: var(--color-bg-tertiary); color: var(--color-text-light);
}
.badge--cmd { background: rgba(92, 124, 250, 0.15); color: #5c7cfa; }
.source-rules {
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.25);
  border-radius: 8px;
  padding: 12px;
  margin: 12px 0;
}
.source-rules__title {
  display: flex; align-items: center; gap: 6px;
  font-size: 0.8rem; font-weight: 600; color: #4338ca;
  margin-bottom: 8px;
}
.source-rules__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.source-rule-item { display: flex; align-items: baseline; gap: 6px; font-size: 0.85rem; line-height: 1.4; flex-wrap: wrap; }
.source-rule-seq {
  flex-shrink: 0;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, monospace);
  font-size: 0.75rem; font-weight: 600;
  color: #4338ca; background: rgba(99, 102, 241, 0.15);
  padding: 1px 6px; border-radius: 4px; min-width: 28px; text-align: center;
}
.source-rule-stmt { flex: 1 1 auto; color: var(--color-text); word-break: keep-all; }
.source-rule-fn {
  flex-shrink: 0;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, monospace);
  font-size: 0.75rem; color: var(--color-text-light);
  background: rgba(0, 0, 0, 0.04); padding: 1px 6px; border-radius: 4px;
}
.us-detail__criteria h4 { font-size: 0.8rem; margin: 8px 0; color: var(--color-text); }
.us-detail__no-criteria { font-size: 0.8rem; color: var(--color-text-light); }
.us-detail__criteria ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.us-detail__criteria li {
  font-size: 0.82rem; padding: 8px 10px; border-radius: 6px;
  background: var(--color-bg-tertiary); display: flex; gap: 6px; flex-wrap: wrap;
}
.gwt-kind {
  font-weight: 700; font-size: 0.66rem; padding: 1px 6px; border-radius: 4px;
  text-transform: uppercase;
}
.gwt-kind--given { background: rgba(64, 192, 87, 0.2); color: #40c057; }
.gwt-kind--when { background: rgba(253, 126, 20, 0.2); color: #fd7e14; }
.gwt-kind--then { background: rgba(92, 124, 250, 0.2); color: #5c7cfa; }
.gwt-name { font-weight: 600; color: var(--color-text); }
.gwt-desc { color: var(--color-text-light); }
</style>
