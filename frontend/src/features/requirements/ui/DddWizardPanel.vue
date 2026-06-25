<script setup>
import { ref, computed } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

/**
 * DDD 발견 마법사 (035 — US1/US2/US4/US6).
 * 프로파일링 4문항 → 추천 단계 조합 → 단계별 진행(SSE) → propose→confirm.
 * 신규 생성기 없이 기존 설계 기계를 오케스트레이션(백엔드). 진실의 원천=그래프.
 */
const props = defineProps({
  scope: { type: String, default: 'greenfield' }, // 'greenfield' | 'epic'
  epicId: { type: String, default: null },
})
const emit = defineEmits(['close', 'done'])

const store = useRequirementsStore()

const PROFILE_Q = [
  { key: 'projectType', label: '프로젝트 유형', options: [
    ['greenfield', '신규(그린필드)'], ['brownfield', '기존 재설계'],
    ['single_feature', '단일 기능'], ['learning', '학습용'] ] },
  { key: 'dddExperience', label: 'DDD 경험', options: [
    ['first_time', '처음'], ['heard', '들어봄'], ['practiced', '적용 경험'], ['expert', '숙련'] ] },
  { key: 'teamSize', label: '팀 규모', options: [
    ['solo', '1~3명'], ['small', '4~10명'], ['multi_team', '2~5팀'], ['large', '6팀+'] ] },
]

const stage = ref('profiling') // profiling | planning | running
const profile = ref({ projectType: 'greenfield', dddExperience: 'first_time', teamSize: 'small', existingArtifacts: [] })
const sessionId = ref(null)
const plan = ref([])
const profileSummary = ref('')
const selectedSteps = ref(new Set())
const errorMsg = ref('')
const busy = ref(false)
const deferredNotes = ref([]) // 이후 단계서 반영 보류된 항목(누적, 정보성)

// 단계 진행 상태
const currentStepIdx = ref(0)
const stepAnswers = ref('') // 자유 텍스트 답변
const pastedDoc = ref('')
const reasoning = ref('')
const proposal = ref(null) // { stepKey, artifactMarkdown, graphChanges:[] }
const acceptedIds = ref(new Set())

const orderedSteps = computed(() => plan.value.filter((s) => selectedSteps.value.has(s.key)))
const currentStep = computed(() => orderedSteps.value[currentStepIdx.value] || null)

async function submitProfile() {
  busy.value = true
  errorMsg.value = ''
  try {
    const res = await store.startDddWizard({ scope: props.scope, epicId: props.epicId, profile: profile.value })
    sessionId.value = res.sessionId
    plan.value = res.recommendedPlan || []
    profileSummary.value = res.profileSummary || ''
    selectedSteps.value = new Set(plan.value.filter((s) => s.recommended).map((s) => s.key))
    stage.value = 'planning'
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}

function toggleStep(key, required) {
  if (required) return
  const s = new Set(selectedSteps.value)
  s.has(key) ? s.delete(key) : s.add(key)
  selectedSteps.value = s
}

function beginSteps() {
  currentStepIdx.value = 0
  deferredNotes.value = [] // 새 실행 시작 — 이전 보류 누적 초기화(v-show로 컴포넌트 유지되므로)
  stage.value = 'running'
  runStep()
}

function runStep() {
  proposal.value = null
  acceptedIds.value = new Set()
  reasoning.value = ''
  stepAnswers.value = ''
  pastedDoc.value = ''
}

async function generateProposal() {
  if (!currentStep.value) return
  busy.value = true
  errorMsg.value = ''
  try {
    // 답변/문서를 먼저 제출(answer) → 그 다음 동기 제안.
    const p = await store.answerDddWizard(sessionId.value, {
      stepKey: currentStep.value.key,
      answers: stepAnswers.value ? { notes: stepAnswers.value } : {},
      pastedDocument: pastedDoc.value || null,
    })
    proposal.value = p
    acceptedIds.value = new Set((p.graphChanges || []).map((c) => c.changeId)) // 기본 전체 수락
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}

function toggleChange(id) {
  const s = new Set(acceptedIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  acceptedIds.value = s
}

async function confirmStep() {
  busy.value = true
  errorMsg.value = ''
  try {
    const res = await store.confirmDddWizardStep(
      sessionId.value, currentStep.value.key, Array.from(acceptedIds.value),
    )
    // 보류(deferred)=방법론 순서상 정상 → 인라인 누적 안내(오류처럼 안 보이게).
    if (res && Array.isArray(res.deferred) && res.deferred.length) {
      deferredNotes.value = [...deferredNotes.value, ...res.deferred]
    }
    // 실패(errors)=진짜 문제 → 인라인 오류 표시 + 다음 단계로 넘어가지 않음
    // (사용자가 확인/재시도하거나 '건너뛰기'로 진행하도록).
    if (res && Array.isArray(res.errors) && res.errors.length) {
      errorMsg.value = `일부 변경이 적용되지 않았습니다 (${res.errors.length}건): ` +
        res.errors.join(' / ') + ' — 수정 후 다시 확정하거나 건너뛰세요.'
      return
    }
    // 다음 단계로
    if (currentStepIdx.value < orderedSteps.value.length - 1) {
      currentStepIdx.value += 1
      runStep()
    } else {
      emit('done')
      stage.value = 'profiling'
    }
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}

function skipStep() {
  if (currentStepIdx.value < orderedSteps.value.length - 1) {
    currentStepIdx.value += 1
    runStep()
  } else {
    emit('done')
    stage.value = 'profiling'
  }
}
</script>

<template>
  <div class="ddd-wizard">
    <div class="dw-head">
      <h3>🧭 DDD 발견 마법사</h3>
      <span class="dw-sub">{{ scope === 'epic' ? '에픽 추가' : '맨땅에서 시작' }}</span>
      <span class="dw-spacer" />
      <button class="dw-x" @click="emit('close')">✕</button>
    </div>

    <p v-if="errorMsg" class="dw-error">{{ errorMsg }}</p>

    <!-- 보류 항목(정보성): 이후 단계서 반영될 것들 — 오류 아님. 접을 수 있음(기본 접힘) -->
    <details v-if="deferredNotes.length" class="dw-deferred">
      <summary class="dw-deferred-title">ℹ 이후 단계에서 반영될 항목 ({{ deferredNotes.length }})</summary>
      <ul><li v-for="(n, i) in deferredNotes" :key="i">{{ n }}</li></ul>
    </details>

    <!-- 1) 프로파일링 -->
    <section v-if="stage === 'profiling'" class="dw-stage">
      <p class="dw-lead">상황을 알려주시면 거칠 단계를 추천합니다.</p>
      <div v-for="q in PROFILE_Q" :key="q.key" class="dw-q">
        <div class="dw-q-label">{{ q.label }}</div>
        <div class="dw-opts">
          <button
            v-for="[val, lbl] in q.options" :key="val"
            class="dw-opt" :class="{ on: profile[q.key] === val }"
            @click="profile[q.key] = val"
          >{{ lbl }}</button>
        </div>
      </div>
      <button class="dw-primary" :disabled="busy" @click="submitProfile">추천 받기 →</button>
    </section>

    <!-- 2) 단계 선택 -->
    <section v-else-if="stage === 'planning'" class="dw-stage">
      <p class="dw-lead">{{ profileSummary }}</p>
      <p class="dw-hint">수행할 단계를 고르세요(필수 단계는 해제 불가).</p>
      <ul class="dw-plan">
        <li v-for="s in plan" :key="s.key" class="dw-step" :class="{ on: selectedSteps.has(s.key) }">
          <label>
            <input type="checkbox" :checked="selectedSteps.has(s.key)" :disabled="!s.optional"
                   @change="toggleStep(s.key, !s.optional)" />
            <span class="dw-step-title">{{ s.title }}</span>
            <span v-if="!s.optional" class="dw-req">필수</span>
            <span v-else-if="s.recommended" class="dw-rec">추천</span>
          </label>
        </li>
      </ul>
      <button class="dw-primary" :disabled="busy || !selectedSteps.size" @click="beginSteps">시작 →</button>
    </section>

    <!-- 3) 단계 진행 -->
    <section v-else-if="stage === 'running' && currentStep" class="dw-stage">
      <div class="dw-progress">단계 {{ currentStepIdx + 1 }} / {{ orderedSteps.length }}</div>
      <h4 class="dw-step-name">{{ currentStep.title }}</h4>

      <div v-if="currentStep.questions && currentStep.questions.length" class="dw-questions">
        <div class="dw-questions-title">이 단계에서 생각해볼 질문</div>
        <ul>
          <li v-for="(q, i) in currentStep.questions" :key="i">{{ q }}</li>
        </ul>
      </div>

      <p class="dw-fields-help">
        둘 중 편한 쪽(또는 둘 다) 사용 — <strong>①</strong> 위 질문에 직접 답하거나,
        <strong>②</strong> 이미 있는 원본 문서를 붙여넣으면 LLM이 추출합니다.
      </p>
      <label class="dw-field"><span>① 질문에 대한 답변 (직접 입력)</span>
        <textarea v-model="stepAnswers" rows="3" placeholder="위 질문들에 답하거나 이 단계의 핵심 결정을 적어주세요" /></label>
      <label class="dw-field"><span>② 기존 문서 (선택 · 참고자료 붙여넣기)</span>
        <textarea v-model="pastedDoc" rows="3" placeholder="기획서·RFP·회의록 등 원본을 붙여넣으면 분석에 활용 (최대 4000자)" /></label>

      <div class="dw-actions">
        <button class="dw-primary" :disabled="busy" @click="generateProposal">산출물 생성</button>
        <button class="dw-ghost" :disabled="busy" @click="skipStep">이 단계 건너뛰기</button>
      </div>

      <p v-if="reasoning" class="dw-reasoning">{{ reasoning }}</p>

      <!-- 제안 -->
      <div v-if="proposal" class="dw-proposal">
        <h5>산출물 (초안)</h5>
        <pre class="dw-artifact">{{ proposal.artifactMarkdown }}</pre>
        <div v-if="proposal.graphChanges?.length" class="dw-changes">
          <h5>그래프 변경안 (확인 시에만 반영)</h5>
          <label v-for="c in proposal.graphChanges" :key="c.changeId" class="dw-change">
            <input type="checkbox" :checked="acceptedIds.has(c.changeId)" @change="toggleChange(c.changeId)" />
            <span class="dw-change-action">{{ c.action }}</span>
            <span class="dw-change-type">{{ c.targetType }}</span>
            <span>{{ c.label }}</span>
          </label>
        </div>
        <p v-else class="dw-hint">이 단계의 그래프 변경안이 없습니다(문서만 생성).</p>
        <div class="dw-actions">
          <button class="dw-primary" :disabled="busy" @click="confirmStep">
            확인 후 다음 → ({{ acceptedIds.size }}건 반영)
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.ddd-wizard { padding: 14px 16px; height: 100%; overflow-y: auto; box-sizing: border-box; }
.dw-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.dw-head h3 { margin: 0; font-size: 1rem; }
.dw-sub { font-size: 0.66rem; padding: 2px 6px; border-radius: 4px; background: rgba(92,124,250,0.18); color: #5c7cfa; }
.dw-spacer { flex: 1; }
.dw-x { border: none; background: transparent; cursor: pointer; font-size: 0.9rem; color: var(--color-text-light); }
.dw-lead { font-size: 0.86rem; margin: 4px 0 10px; }
.dw-hint { font-size: 0.76rem; color: var(--color-text-light); }
.dw-q { margin-bottom: 12px; }
.dw-q-label { font-size: 0.74rem; font-weight: 700; margin-bottom: 5px; }
.dw-opts { display: flex; flex-wrap: wrap; gap: 6px; }
.dw-opt { border: 1px solid var(--color-border); background: var(--color-bg-tertiary); color: var(--color-text); border-radius: 14px; font-size: 0.74rem; padding: 4px 10px; cursor: pointer; }
.dw-opt.on { border-color: var(--color-accent); background: rgba(34,139,230,0.14); color: var(--color-accent); }
.dw-primary { border: 1px solid var(--color-accent); background: var(--color-accent); color: #fff; border-radius: 6px; font-size: 0.78rem; padding: 6px 14px; cursor: pointer; margin-top: 8px; }
.dw-primary:disabled { opacity: 0.5; cursor: default; }
.dw-ghost { border: 1px solid var(--color-border); background: transparent; color: var(--color-text-light); border-radius: 6px; font-size: 0.78rem; padding: 6px 12px; cursor: pointer; margin-top: 8px; }
.dw-plan { list-style: none; margin: 8px 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.dw-step { border: 1px solid var(--color-border); border-radius: 6px; padding: 6px 8px; }
.dw-step.on { border-color: var(--color-accent); background: rgba(34,139,230,0.06); }
.dw-step label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.dw-step-title { flex: 1; font-size: 0.82rem; }
.dw-req { font-size: 0.6rem; color: #e03131; font-weight: 700; }
.dw-rec { font-size: 0.6rem; color: var(--color-accent); font-weight: 700; }
.dw-progress { font-size: 0.7rem; color: var(--color-text-light); }
.dw-step-name { margin: 4px 0 10px; font-size: 0.92rem; }
.dw-field { display: block; margin-bottom: 8px; }
.dw-field span { display: block; font-size: 0.7rem; color: var(--color-text-light); margin-bottom: 3px; }
.dw-field textarea { width: 100%; box-sizing: border-box; font-size: 0.82rem; padding: 5px 7px; border: 1px solid var(--color-border); border-radius: 6px; background: var(--color-bg); color: var(--color-text); resize: vertical; }
.dw-fields-help { font-size: 0.72rem; color: var(--color-text-light); margin: 4px 0 6px; line-height: 1.4; }
.dw-questions { background: var(--color-bg-tertiary); border: 1px solid var(--color-border); border-radius: 6px; padding: 8px 10px; margin: 6px 0; }
.dw-questions-title { font-size: 0.74rem; font-weight: 700; margin-bottom: 4px; }
.dw-questions ul { margin: 0; padding-left: 16px; }
.dw-questions li { font-size: 0.78rem; line-height: 1.5; color: var(--color-text); }
.dw-deferred { background: var(--color-bg-tertiary); border: 1px solid var(--color-border); border-radius: 6px; padding: 7px 10px; margin: 4px 0; }
.dw-deferred-title { font-size: 0.72rem; font-weight: 700; color: var(--color-text-light); margin-bottom: 3px; cursor: pointer; user-select: none; }
.dw-deferred[open] .dw-deferred-title { margin-bottom: 5px; }
.dw-deferred ul { margin: 0; padding-left: 16px; }
.dw-deferred li { font-size: 0.74rem; line-height: 1.45; color: var(--color-text-light); }
.dw-actions { display: flex; gap: 8px; }
.dw-reasoning { font-size: 0.78rem; color: var(--color-text-light); font-style: italic; }
.dw-proposal { margin-top: 12px; border-top: 1px solid var(--color-border); padding-top: 10px; }
.dw-proposal h5 { margin: 8px 0 4px; font-size: 0.72rem; text-transform: uppercase; color: var(--color-text-light); }
.dw-artifact { background: var(--color-bg-tertiary); padding: 8px; border-radius: 6px; font-size: 0.74rem; white-space: pre-wrap; max-height: 220px; overflow-y: auto; }
.dw-change { display: flex; align-items: center; gap: 6px; font-size: 0.78rem; padding: 3px 0; }
.dw-change-action { font-size: 0.6rem; font-weight: 700; color: var(--color-accent); text-transform: uppercase; }
.dw-change-type { font-size: 0.6rem; padding: 1px 5px; border-radius: 3px; background: rgba(92,124,250,0.18); color: #5c7cfa; }
.dw-error { color: #e03131; font-size: 0.78rem; }
</style>
