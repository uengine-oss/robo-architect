<template>
  <div class="strat-stages">
    <!-- 스코프 분류 중 -->
    <div v-if="phase === 'scoping'" class="strat-stages__scoping">
      <span class="spinner" /> {{ t('proposals.staged.scoping') }}
      <pre v-if="logText" class="strat-stages__log">{{ logText }}</pre>
    </div>

    <!-- 스테이지 플랜 확인 -->
    <StagePlanReview v-else-if="phase === 'plan'" :plan="proposedPlan" @confirm="onConfirmPlan" />

    <!-- 전략 단계 진행 -->
    <template v-else-if="phase === 'stages'">
      <div class="strat-stages__stepper">
        <button
          v-for="s in strategicActive"
          :key="s"
          :class="['strat-stages__step', stepState(s), { clickable: !!artifacts[s] || s === current }]"
          @click="onStepClick(s)"
        >{{ shortLabel(s) }}</button>
      </div>

      <!-- 이전 단계 보기(읽기 전용) -->
      <div v-if="viewing" class="strat-stages__view">
        <div class="strat-stages__view-head">
          <span>{{ longLabel(viewing) }} <em class="ro-tag">읽기 전용</em></span>
          <button class="btn btn--ghost btn--xs" @click="viewing = null">← {{ current ? '현재 단계로' : '돌아가기' }}</button>
        </div>
        <StageReadonly :stage="viewing" :artifact="artifacts[viewing]" />
      </div>

      <StageRunner
        v-else-if="current"
        :key="current"
        :proposalId="proposalId"
        :stage="current"
        @confirmed="afterStage"
        @skipped="afterStage"
      />
    </template>

    <!-- 전략 분해 완료 — 확정된 단계 결과를 읽기 전용으로 계속 표시 -->
    <div v-else-if="phase === 'done'" class="strat-stages__done">
      <div class="strat-stages__done-head">
        <div class="strat-stages__done-badge">✓ 전략 분해 완료</div>
        <p class="strat-stages__done-note"><b>Plan 탭</b>에서 전술 단계(Connect · Define · Tactical)를 이어가세요.</p>
      </div>
      <div v-for="s in completedStrategic" :key="s" class="strat-stages__ro">
        <h5 class="strat-stages__ro-title">{{ longLabel(s) }} <span class="strat-stages__ro-tag">읽기 전용</span></h5>
        <StageReadonly :stage="s" :artifact="artifacts[s]" />
      </div>
      <div class="strat-stages__continue">
        <button class="btn btn--primary" @click="$emit('goto-plan')">
          {{ nextStageLabel ? `Plan 탭 — ${nextStageLabel} 단계로 계속 →` : 'Plan 탭에서 전술 단계 계속 →' }}
        </button>
      </div>
    </div>

    <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from '../../../app/i18n'
import { useProposalsStore } from '../proposals.store'
import StagePlanReview from './StagePlanReview.vue'
import StageRunner from './stages/StageRunner.vue'
import StageReadonly from './stages/StageReadonly.vue'

const props = defineProps({ proposalId: { type: String, required: true } })
defineEmits(['goto-plan'])
const { t } = useI18n()
const store = useProposalsStore()

const STRATEGIC = ['DISCOVER', 'DECOMPOSE', 'STRATEGIZE']
const TACTICAL = ['CONNECT', 'DEFINE', 'TACTICAL']
const viewing = ref(null)
const phase = ref('init')        // init | scoping | plan | stages | done
const proposedPlan = ref(null)
const errorMsg = ref('')

const proposal = computed(() => store.currentProposal)
const logText = computed(() => (store.stagedStream.logLines || []).join('\n'))
const activeStages = computed(() =>
  (proposal.value?.stagePlan?.stages || []).filter(s => !s.skipped).map(s => s.stage))
const strategicActive = computed(() => activeStages.value.filter(s => STRATEGIC.includes(s)))
const artifacts = computed(() => proposal.value?.stageArtifacts || {})
const current = computed(() => strategicActive.value.find(s => !artifacts.value[s]) || null)

function shortLabel(s) { return { DISCOVER: 'Discover', DECOMPOSE: 'Decompose', STRATEGIZE: 'Strategize' }[s] }
function longLabel(s) {
  return { DISCOVER: 'Discover — 이벤트 발굴', DECOMPOSE: 'Decompose — 서브도메인',
           STRATEGIZE: 'Strategize — Core/Supporting/Generic' }[s] || s
}
function stepState(s) {
  if (viewing.value === s) return 'viewing'
  if (artifacts.value[s]) return 'done'
  if (s === current.value) return 'current'
  return 'pending'
}

// 읽기 전용 표시용 헬퍼.
const completedStrategic = computed(() => strategicActive.value.filter(s => artifacts.value[s]))
function onStepClick(s) {
  if (s === current.value) { viewing.value = null; return }
  if (artifacts.value[s]) viewing.value = s
}
watch(current, () => { viewing.value = null })
// 이어갈 다음 전술 단계 라벨(currentStage 우선, 없으면 첫 미완료 전술 단계).
const nextStageLabel = computed(() => {
  const tacticalActive = activeStages.value.filter(s => TACTICAL.includes(s))
  const next = (proposal.value?.currentStage && tacticalActive.includes(proposal.value.currentStage))
    ? proposal.value.currentStage
    : tacticalActive.find(s => !artifacts.value[s])
  return next ? { CONNECT: 'Connect', DEFINE: 'Define', TACTICAL: 'Tactical' }[next] : null
})

onMounted(start)

async function start() {
  if (proposal.value?.stagePlan?.stages?.length) { goStagesOrDone(); return }
  // 스코프 제안을 이미 받아둔 적 있으면 재실행하지 않고 복원(탭 전환 보존).
  const draftPlan = store.getStageDraft(props.proposalId, 'SCOPE')
  if (draftPlan) { proposedPlan.value = draftPlan; phase.value = 'plan'; return }
  phase.value = 'scoping'
  try {
    proposedPlan.value = await store.subscribeToScope(props.proposalId)
    store.setStageDraft(props.proposalId, 'SCOPE', proposedPlan.value)
    phase.value = 'plan'
  } catch (e) { errorMsg.value = e.message }
}

async function onConfirmPlan(stages) {
  try {
    await store.confirmStagePlan(props.proposalId, stages)
    store.clearStageDraft(props.proposalId, 'SCOPE')
    goStagesOrDone()
  } catch (e) { errorMsg.value = e.message }
}

function goStagesOrDone() {
  phase.value = current.value ? 'stages' : 'done'
}

async function afterStage() {
  await store.fetchProposal(props.proposalId)
  goStagesOrDone()
}
</script>

<style scoped>
.strat-stages { padding: 4px 0; }
.strat-stages__scoping { display: flex; align-items: center; gap: 8px; color: var(--color-text-light); font-size: 13px; }
.strat-stages__log { background: #0f172a; color: #cbd5e1; font-size: 11px; padding: 8px; border-radius: 6px; max-height: 160px; overflow-y: auto; white-space: pre-wrap; width: 100%; }
.strat-stages__stepper { display: flex; gap: 6px; margin-bottom: 10px; }
.strat-stages__step { font-size: 11px; padding: 4px 12px; border-radius: 12px; border: none; background: var(--color-bg-tertiary); color: var(--color-text-light); cursor: default; }
.strat-stages__step.clickable { cursor: pointer; }
.strat-stages__step.done { background: var(--color-success); color: #fff; }
.strat-stages__step.current { background: var(--color-accent); color: #fff; }
.strat-stages__step.viewing { outline: 2px solid var(--color-accent); outline-offset: 1px; }
.strat-stages__view-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; font-size: 13px; color: var(--color-text-bright); }
.ro-tag { font-size: 10px; font-weight: 400; font-style: normal; color: var(--color-text-light); border: 1px solid var(--color-border); border-radius: 8px; padding: 1px 6px; margin-left: 6px; }
.btn--xs { padding: 3px 8px; font-size: 11px; }
.btn--ghost { background: transparent; border: 1px solid var(--color-border); color: var(--color-text); }
.strat-stages__done-head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--color-border); }
.strat-stages__done-badge { font-size: 14px; font-weight: 600; color: var(--color-success); }
.strat-stages__done-note { font-size: 12px; color: var(--color-text-light); margin: 0; }
.strat-stages__ro { margin-bottom: 16px; }
.strat-stages__ro-title { font-size: 13px; color: var(--color-text-bright); margin: 0 0 6px; display: flex; align-items: center; gap: 8px; }
.strat-stages__ro-tag { font-size: 10px; font-weight: 400; color: var(--color-text-light); border: 1px solid var(--color-border); border-radius: 8px; padding: 1px 6px; }
.strat-stages__ro-viz { border: none; padding: 0; margin: 0; min-width: 0; pointer-events: none; opacity: 0.92; }
.strat-stages__continue { margin-top: 10px; }
.btn { padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }
.btn--primary { background: var(--color-accent); color: #fff; }
</style>
