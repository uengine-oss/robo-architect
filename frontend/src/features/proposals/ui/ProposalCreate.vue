<template>
  <div class="proposal-create">
    <div class="proposal-create__header">
      <h3>새 Proposal 생성</h3>
      <button @click="$emit('cancel')" class="btn-close" title="닫기">✕</button>
    </div>

    <!-- Step 1: 자연어 입력 -->
    <div v-if="step === 'input'" class="proposal-create__input">
      <textarea
        v-model="promptText"
        placeholder="요구사항을 자연어로 입력하세요. (예: 결제 시스템에 부분 환불 기능을 추가해줘)"
        rows="4"
        class="proposal-create__textarea"
      />
      <div class="proposal-create__actions">
        <button @click="submit" :disabled="!promptText.trim() || loading" class="btn btn--primary">
          {{ loading ? '분석 중...' : 'AI 분석 시작' }}
        </button>
      </div>
    </div>

    <!-- Step 2: 인텐트 분해 진행 -->
    <div v-if="step === 'analyzing'" class="proposal-create__analyzing">
      <div class="analyzing-header">
        <span class="spinner" />
        <span>{{ currentPhase || 'AI가 요구사항을 분석 중입니다...' }}</span>
        <button @click="cancelAnalysis" class="btn-stop" title="분석 중단">■ 중단</button>
      </div>

      <!-- Claude 실시간 스트림 로그 -->
      <div ref="logContainer" class="stream-log">
        <div
          v-for="(line, i) in store.intentStream.logLines"
          :key="i"
          :class="['stream-log__line', logLineClass(line)]"
        >{{ line }}</div>
        <div v-if="!store.intentStream.logLines?.length" class="stream-log__waiting">
          <span class="spinner spinner--sm" /> Claude가 분석을 시작하고 있습니다...
        </div>
      </div>
    </div>

    <!-- Step 3: 명확화 질문 -->
    <div v-if="step === 'clarify'" class="proposal-create__clarify">
      <h4>AI가 몇 가지 사항을 확인하고 싶습니다</h4>
      <div v-for="(q, qi) in clarifyQuestions" :key="qi" class="clarify-question">
        <p class="clarify-question__text">{{ q.text }}</p>
        <div class="clarify-question__options">
          <button
            v-for="(opt, oi) in q.options"
            :key="oi"
            @click="selectAnswer(qi, opt)"
            :class="['btn', answers[qi] === opt ? 'btn--selected' : 'btn--outline']"
          >{{ opt }}</button>
          <input
            v-model="customAnswers[qi]"
            placeholder="직접 입력..."
            class="clarify-question__custom"
          />
        </div>
      </div>
      <div class="proposal-create__actions">
        <button @click="submitAnswers" :disabled="!allAnswered" class="btn btn--primary">
          답변 제출
        </button>
        <button @click="skipClarify" class="btn btn--secondary">현재 정보로 계속</button>
      </div>
    </div>

    <!-- Step 4: 완료 -->
    <div v-if="step === 'done'" class="proposal-create__done">
      <div class="done-icon">✓</div>
      <p>Proposal <strong>{{ createdId }}</strong> 초안이 생성되었습니다.</p>
      <button @click="$emit('created', createdId)" class="btn btn--primary">Proposal 보기</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useProposalsStore } from '../proposals.store'

const emit = defineEmits(['created', 'cancel'])
const store = useProposalsStore()

const promptText = ref('')
const loading = ref(false)
const step = ref('input')
const createdId = ref(null)
const currentPhase = ref('')
const clarifyQuestions = ref([])
const answers = ref({})
const customAnswers = ref({})
const logContainer = ref(null)

const allAnswered = computed(() =>
  clarifyQuestions.value.every((_, i) => answers.value[i] || customAnswers.value[i])
)

async function submit() {
  if (!promptText.value.trim()) return
  loading.value = true
  step.value = 'analyzing'

  const proposal = await store.createProposal(promptText.value.trim())
  if (!proposal) { step.value = 'input'; loading.value = false; return }

  createdId.value = proposal.id

  const es = store.subscribeToIntent(proposal.id)

  // 로그 라인이 추가될 때 자동 스크롤
  watch(() => store.intentStream.logLines?.length, async () => {
    await nextTick()
    if (logContainer.value) logContainer.value.scrollTop = logContainer.value.scrollHeight
  })

  watch(() => store.intentStream.events, (evts) => {
    const last = evts[evts.length - 1]
    if (!last) return
    if (last.type === 'phase') currentPhase.value = last.data.message
    if (last.type === 'clarification_needed') {
      clarifyQuestions.value = store.intentStream.clarificationQuestions || []
      step.value = 'clarify'
      loading.value = false
    }
    if (last.type === 'done' && step.value !== 'clarify') {
      step.value = 'done'
      loading.value = false
    }
  }, { deep: true })
}

function logLineClass(line) {
  if (line.startsWith('[tool]')) return 'stream-log__line--tool'
  if (/^\[.+\]/.test(line)) return 'stream-log__line--tag'
  if (line.startsWith('{') || line.startsWith('"') || line === '}' || line === ']') return 'stream-log__line--json'
  return ''
}

function cancelAnalysis() {
  store.stopIntent()
  loading.value = false
  step.value = 'input'
}

function selectAnswer(qi, opt) {
  answers.value = { ...answers.value, [qi]: opt }
}

async function submitAnswers() {
  const formattedAnswers = clarifyQuestions.value.map((_, i) => ({
    questionIndex: i,
    answer: answers.value[i] || customAnswers.value[i] || '',
  }))
  await store.answerClarification(createdId.value, formattedAnswers)
  step.value = 'analyzing'
  store.subscribeToIntent(createdId.value)
}

function skipClarify() {
  step.value = 'done'
}

function eventSummary(evt) {
  if (evt.type === 'phase') return evt.data.message
  if (evt.type === 'strategic_diff') return 'Strategic Diff 생성 완료'
  if (evt.type === 'tactical_diff') return 'Tactical Diff 생성 완료'
  if (evt.type === 'impact_map') return `Impact Map: ${evt.data.impactMap?.length || 0}개 영향 노드`
  if (evt.type === 'done') return '분석 완료'
  return evt.type
}
</script>

<style scoped>
.proposal-create { padding: 16px; height: 100%; box-sizing: border-box; }
.proposal-create__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.proposal-create__header h3 { margin: 0; font-size: 15px; font-weight: 600; color: var(--color-text-bright); }
.btn-close { background: none; border: none; cursor: pointer; color: var(--color-text-light); font-size: 16px; padding: 2px 6px; border-radius: 4px; line-height: 1; }
.btn-close:hover { background: var(--color-bg-tertiary); color: var(--color-text); }
.proposal-create__textarea { width: 100%; resize: vertical; padding: 8px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 14px; background: var(--color-bg-secondary); color: var(--color-text); }
.proposal-create__actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; }
.btn { padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--primary:disabled { opacity: 0.5; cursor: default; }
.btn--secondary { background: var(--color-bg-tertiary); color: var(--color-text); }
.btn--outline { background: transparent; border: 1px solid var(--color-border); color: var(--color-text); }
.btn--selected { background: var(--status-blue-bg); border: 1px solid var(--color-accent); color: var(--status-blue-fg); }
.analyzing-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-size: 14px; }
.spinner { width: 16px; height: 16px; border: 2px solid var(--color-border); border-top-color: var(--color-accent); border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0; }
.spinner--sm { width: 10px; height: 10px; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }
.btn-stop { margin-left: auto; background: var(--color-bg-tertiary); color: var(--color-text); border: none; border-radius: 4px; padding: 3px 10px; font-size: 11px; cursor: pointer; flex-shrink: 0; }
.btn-stop:hover { background: var(--color-danger); color: #fff; }
.stream-log { background: #0f172a; border-radius: 6px; padding: 10px 12px; height: 260px; overflow-y: auto; font-family: monospace; font-size: 11px; color: #cbd5e1; }
.stream-log__line { padding: 1px 0; white-space: pre-wrap; word-break: break-all; line-height: 1.5; }
.stream-log__line--tag { color: #86efac; font-weight: 600; }
.stream-log__line--tool { color: #7dd3fc; }
.stream-log__line--json { color: #64748b; font-size: 10px; }
.stream-log__waiting { color: #64748b; display: flex; align-items: center; gap: 6px; }
.clarify-question { margin-bottom: 16px; }
.clarify-question__text { font-size: 14px; font-weight: 500; margin-bottom: 8px; color: var(--color-text); }
.clarify-question__options { display: flex; flex-wrap: wrap; gap: 6px; }
.clarify-question__custom { border: 1px solid var(--color-border); border-radius: 4px; padding: 4px 8px; font-size: 13px; background: var(--color-bg-secondary); color: var(--color-text); }
.done-icon { font-size: 32px; color: var(--color-success); margin-bottom: 8px; }
.proposal-create__done { text-align: center; padding: 24px; }
</style>
