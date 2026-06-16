<script setup>
import { computed, ref, watch } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'
import ClarificationSummary from './ClarificationSummary.vue'

/**
 * Clarification session panel (spec 030 — US1 / US2).
 * - Surfaces the prioritized question queue produced by the deep agent.
 * - Drives the per-question answer → propose → apply loop.
 * - Renders the disambiguation re-prompt when the agent can't interpret an answer.
 * - Hands off to ClarificationSummary on session end.
 *
 * Two render modes:
 *   - default (overlay)     — shows title + 닫기 toolbar
 *   - embedded=true         — header trimmed; hosted inside UserStoryDetail tab
 */
const props = defineProps({
  embedded: { type: Boolean, default: false },
})
const store = useRequirementsStore()
const emit = defineEmits(['close'])

const freeTextDraft = ref('')

const session = computed(() => store.clarificationSession)
const proposal = computed(() => store.clarificationProposal)
const summary = computed(() => store.clarificationSummary)

const currentQuestion = computed(() => {
  const qs = session.value?.questions || []
  return qs.find((q) => q.status === 'pending') || null
})

// 편집안(미적용)이 대기 중인지. 이때는 다음 질문으로 넘기지 않고 편집안 검토에 집중.
const hasPendingProposal = computed(
  () => !!(proposal.value && proposal.value.edits && proposal.value.edits.length),
)
// 편집안이 어느 질문에 대한 것인지(답변 직후 currentQuestion은 이미 다음으로 advance됨).
const proposalQuestion = computed(() => {
  const pid = proposal.value?.questionId
  if (!pid) return null
  return (session.value?.questions || []).find((q) => q.questionId === pid) || null
})

const progressLabel = computed(() => {
  if (!session.value) return ''
  const p = session.value.progress || {}
  if (p.message) return p.message
  return p.phase || ''
})

watch(currentQuestion, () => {
  freeTextDraft.value = ''
})

// 재진입(더블클릭) 방지 + 에러를 uncaught로 흘리지 않도록 가드.
// encoding=true 동안엔 답변→편집안 LLM 인코딩 중 — SSE 타이밍에 의존하지 않고
// 로컬 상태로 "인코딩 중" 인디케이터를 확실히 표시한다.
const busy = ref(false)
const encoding = ref(false)
async function _run(fn, { isEncoding = false } = {}) {
  if (busy.value) return
  busy.value = true
  if (isEncoding) encoding.value = true
  try {
    await fn()
  } catch (e) {
    store.clarificationError = `명확화 처리 실패: ${e?.message || e}`
  } finally {
    busy.value = false
    encoding.value = false
  }
}

async function chooseOption(optionKey) {
  if (!currentQuestion.value) return
  await _run(() => store.answerQuestion(currentQuestion.value.questionId, { mode: 'option', optionKey }), { isEncoding: true })
}

async function acceptRecommended() {
  if (!currentQuestion.value) return
  await _run(() => store.answerQuestion(currentQuestion.value.questionId, { mode: 'recommended' }), { isEncoding: true })
}

async function submitFreeText() {
  if (!currentQuestion.value || !freeTextDraft.value.trim()) return
  await _run(() => store.answerQuestion(currentQuestion.value.questionId, {
    mode: 'free_text',
    text: freeTextDraft.value.trim(),
  }), { isEncoding: true })
}

async function skip() {
  if (!currentQuestion.value) return
  await _run(() => store.skipQuestion(currentQuestion.value.questionId))
}

async function applyProposal() {
  if (!proposal.value) return
  await _run(() => store.applyEdit(proposal.value.questionId))
}

async function endSession() {
  await store.endSession()
}

function close() {
  store.closeClarification()
  emit('close')
}
</script>

<template>
  <div class="clarification-panel" :class="{ 'is-embedded': props.embedded }">
    <div v-if="!props.embedded" class="cp-toolbar">
      <span class="cp-title">요구사항 명확화</span>
      <span v-if="session" class="cp-scope">— {{ session.scope?.scopeName }}</span>
      <span v-if="progressLabel" class="cp-progress">{{ progressLabel }}</span>
      <button class="cp-btn" @click="close">닫기</button>
    </div>
    <div v-else-if="progressLabel" class="cp-embedded-status">{{ progressLabel }}</div>

    <div v-if="store.clarificationError" class="cp-error">
      {{ store.clarificationError }}
    </div>

    <div v-if="!session" class="cp-empty">세션이 시작되지 않았습니다.</div>

    <!-- Analyzing -->
    <div v-else-if="session.status === 'analyzing'" class="cp-section cp-analyzing">
      <div class="cp-spinner">⏳</div>
      <div>딥 에이전트가 모호성을 스캔 중입니다...</div>
      <div class="cp-subtle">{{ progressLabel }}</div>
    </div>

    <!-- No ambiguities -->
    <div
      v-else-if="session.noAmbiguities || (!currentQuestion && (session.status === 'completed' || (session.questions || []).length === 0))"
      class="cp-section cp-clear"
    >
      <div class="cp-clear-icon">✓</div>
      <div>중대한 모호성이 발견되지 않았습니다.</div>
      <div v-if="!summary" class="cp-actions">
        <button class="cp-btn cp-btn--primary" @click="endSession">세션 종료</button>
      </div>
    </div>

    <!-- Awaiting answers — render the current question.
         편집안(미적용)이 대기 중이면 질문을 숨기고 편집안 검토에 집중(질문 사라짐 혼동 방지). -->
    <div v-else-if="currentQuestion && !hasPendingProposal && !encoding" class="cp-section">
      <div v-if="session.deferredNote" class="cp-deferred">⚠ {{ session.deferredNote }}</div>

      <div class="cp-question-meta">
        <span class="cp-pill">{{ currentQuestion.category }}</span>
        <span class="cp-pill cp-pill--priority">P{{ currentQuestion.priority }}</span>
        <span class="cp-progress-text">
          {{ (session.progress?.questionsAnswered ?? 0) + 1 }} / {{ (session.questions || []).length }}
        </span>
      </div>

      <div class="cp-question">{{ currentQuestion.questionText }}</div>
      <div class="cp-refs">
        영향 요구사항:
        <code v-for="rid in currentQuestion.referencedRequirementIds" :key="rid">{{ rid }}</code>
      </div>

      <div class="cp-recommended" v-if="currentQuestion.recommendedAnswer">
        <strong>추천 답변:</strong> {{ currentQuestion.recommendedAnswer }}
      </div>

      <!-- Closed-form options -->
      <div v-if="currentQuestion.questionType === 'closed'" class="cp-options">
        <button
          v-for="opt in currentQuestion.options"
          :key="opt.key"
          class="cp-btn cp-btn--option"
          :disabled="busy"
          @click="chooseOption(opt.key)"
        >{{ opt.label }}</button>
      </div>

      <!-- Short-answer -->
      <div v-else class="cp-shortanswer">
        <input
          v-model="freeTextDraft"
          placeholder="짧은 답변 (≤5단어)"
          @keyup.enter="submitFreeText"
        />
        <button class="cp-btn" :disabled="busy || !freeTextDraft.trim()" @click="submitFreeText">제출</button>
      </div>

      <div class="cp-actions">
        <button
          v-if="currentQuestion.recommendedAnswer"
          class="cp-btn cp-btn--primary"
          :disabled="busy"
          @click="acceptRecommended"
        >추천 답변 수락</button>
        <button class="cp-btn cp-btn--ghost" :disabled="busy" @click="skip">건너뛰기</button>
        <button class="cp-btn cp-btn--ghost" :disabled="busy" @click="endSession">세션 종료</button>
      </div>

      <div v-if="store.clarificationDisambiguation" class="cp-disambig">
        {{ store.clarificationDisambiguation }}
      </div>
    </div>

    <!-- 모든 질문 처리 완료(남은 pending 없음)인데 아직 세션 종료/요약 전 — 빈 화면 방지 -->
    <div
      v-else-if="!currentQuestion && !hasPendingProposal && !encoding && !summary"
      class="cp-section cp-clear"
    >
      <div class="cp-clear-icon">✓</div>
      <div>모든 질문을 처리했습니다.</div>
      <div class="cp-actions">
        <button class="cp-btn cp-btn--primary" :disabled="busy" @click="endSession">세션 종료</button>
        <button class="cp-btn cp-btn--ghost" @click="close">닫기</button>
      </div>
    </div>

    <!-- 답변 → 편집안 인코딩 중 인디케이터 (LLM 지연) -->
    <div v-if="encoding" class="cp-section cp-encoding">
      <span class="cp-spinner">⏳</span> 답변 인코딩 중...
    </div>

    <!-- Encoded proposal — before/after diff + apply -->
    <div v-if="!encoding && hasPendingProposal" class="cp-section cp-proposal">
      <div class="cp-proposal-header">제안된 편집안</div>
      <div v-if="proposalQuestion" class="cp-proposal-q">
        <span class="cp-pill">{{ proposalQuestion.category }}</span>
        {{ proposalQuestion.questionText }}
      </div>
      <div v-if="proposal.edits.length > 1" class="cp-edit-count">
        이 답변은 영향받는 User Story {{ proposal.edits.length }}건에 적용됩니다.
      </div>
      <div v-for="edit in proposal.edits" :key="edit.requirementId" class="cp-edit">
        <div class="cp-edit-id">
          <strong>{{ (edit.after || edit.before)?.role }}: {{ (edit.after || edit.before)?.action }}</strong>
          <div class="cp-edit-fields">{{ edit.fieldsSummary }}</div>
        </div>
        <div class="cp-diff-row">
          <div class="cp-diff-col">
            <div class="cp-diff-label">변경 전</div>
            <pre>{{ JSON.stringify(edit.before, null, 2) }}</pre>
          </div>
          <div class="cp-diff-col">
            <div class="cp-diff-label">변경 후</div>
            <pre>{{ JSON.stringify(edit.after, null, 2) }}</pre>
          </div>
        </div>
      </div>
      <div class="cp-actions">
        <button class="cp-btn cp-btn--primary" :disabled="busy" @click="applyProposal">적용</button>
      </div>
    </div>

    <!-- End-of-session summary -->
    <ClarificationSummary
      v-if="summary"
      :summary="summary"
      @revert="(rid) => store.revertChange(rid)"
    />
  </div>
</template>

<style scoped>
.clarification-panel {
  display: flex; flex-direction: column; gap: 8px;
  padding: 8px 12px; overflow: auto; max-height: 100%;
  background: var(--color-bg-secondary, #fff);
  border: 1px solid var(--color-border, #e5e5e5);
  border-radius: 6px;
}
/* Embedded inside the UserStoryDetail clarification tab — drop the visual
 * frame and toolbar; the tab provides its own context. */
.clarification-panel.is-embedded {
  padding: 4px 4px 16px;
  background: transparent;
  border: none;
  border-radius: 0;
}
.cp-embedded-status {
  font-size: 0.72rem; color: var(--color-text-light, #888);
  padding: 0 4px 4px;
}
.cp-toolbar { display: flex; align-items: center; gap: 8px; }
.cp-title { font-weight: 700; font-size: 0.85rem; }
.cp-scope { font-size: 0.78rem; color: var(--color-text-light, #888); }
.cp-progress { margin-left: auto; font-size: 0.72rem; color: var(--color-text-light, #888); }
.cp-error { color: #e03131; font-size: 0.78rem; padding: 4px 6px; }
.cp-deferred { color: #b6781f; font-size: 0.78rem; }
.cp-empty, .cp-analyzing, .cp-clear { padding: 16px; text-align: center; }
.cp-spinner { font-size: 1.4rem; }
.cp-clear-icon { font-size: 1.8rem; color: #40c057; }
.cp-section { padding: 6px 0; }
.cp-encoding { padding: 14px; text-align: center; color: var(--color-text-light); font-size: 0.85rem; }
.cp-proposal-q { font-size: 0.82rem; color: var(--color-text); margin: 4px 0 8px; display: flex; gap: 6px; align-items: baseline; }
.cp-edit-count { font-size: 0.76rem; color: var(--color-text-light); margin-bottom: 6px; }
.cp-edit-fields { font-size: 0.74rem; color: var(--color-text-light); margin-top: 2px; }
.cp-question-meta { display: flex; gap: 6px; align-items: center; font-size: 0.72rem; margin-bottom: 6px; }
.cp-pill { background: var(--color-bg-tertiary, #f4f4f4); padding: 1px 6px; border-radius: 4px; }
.cp-pill--priority { color: #5c7cfa; }
.cp-progress-text { margin-left: auto; color: var(--color-text-light, #888); }
.cp-question { font-size: 0.92rem; font-weight: 600; margin: 4px 0; }
.cp-refs { font-size: 0.72rem; color: var(--color-text-light, #888); }
.cp-refs code { margin-right: 4px; background: var(--color-bg-tertiary, #f4f4f4); padding: 1px 4px; border-radius: 3px; }
.cp-recommended { font-size: 0.82rem; padding: 4px 0; }
.cp-options { display: flex; flex-direction: column; gap: 4px; padding: 6px 0; }
.cp-shortanswer { display: flex; gap: 4px; padding: 6px 0; }
.cp-shortanswer input { flex: 1; padding: 4px 6px; }
.cp-actions { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
.cp-btn {
  padding: 4px 10px; border: 1px solid var(--color-border, #ccc);
  border-radius: 4px; background: var(--color-bg-tertiary, #fafafa);
  color: var(--color-text, #222); font-size: 0.78rem; cursor: pointer;
}
.cp-btn:hover { filter: brightness(1.05); }
.cp-btn--primary { background: var(--color-accent, #228be6); color: #fff; border-color: transparent; }
.cp-btn--option { text-align: left; }
.cp-btn--ghost { background: transparent; }
.cp-disambig { color: #e03131; font-size: 0.78rem; margin-top: 6px; }
.cp-proposal-header { font-weight: 700; font-size: 0.82rem; margin-top: 8px; }
.cp-edit { padding: 6px 0; border-top: 1px dashed var(--color-border, #eee); }
.cp-edit-id { font-size: 0.74rem; margin-bottom: 4px; }
.cp-diff-row { display: flex; gap: 6px; }
.cp-diff-col { flex: 1; font-size: 0.72rem; }
.cp-diff-label { font-weight: 700; color: var(--color-text-light, #888); }
.cp-diff-col pre {
  background: var(--color-bg-tertiary, #fafafa); padding: 6px;
  border-radius: 4px; white-space: pre-wrap; word-break: break-word;
  max-height: 240px; overflow: auto;
}
</style>
