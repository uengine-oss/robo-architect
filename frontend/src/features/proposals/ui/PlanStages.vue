<template>
  <div class="plan-stages">
    <!-- 전략 단계 미완료 가드 -->
    <div v-if="!strategicDone" class="plan-stages__guard">
      먼저 <b>Intent 탭</b>에서 전략 분해(Discover · Decompose · Strategize)를 완료하세요.
    </div>

    <template v-else>
      <!-- 클릭 가능한 스테퍼: 완료 단계를 눌러 이전 결과를 본다 -->
      <div class="plan-stages__stepper">
        <button
          v-for="s in tacticalActive"
          :key="s"
          :class="['plan-stages__step', stepState(s), { clickable: !!artifacts[s] || s === current }]"
          @click="onStepClick(s)"
        >{{ shortLabel(s) }}</button>
      </div>

      <!-- 이전 단계 보기(읽기 전용) -->
      <div v-if="viewing" class="plan-stages__view">
        <div class="plan-stages__view-head">
          <span>{{ longLabel(viewing) }} <em class="ro-tag">읽기 전용</em></span>
          <button class="btn btn--ghost btn--xs" @click="viewing = null">← {{ current ? '현재 단계로' : '돌아가기' }}</button>
        </div>
        <StageReadonly :stage="viewing" :artifact="artifacts[viewing]" />
      </div>

      <!-- 현재 전술 단계 진행 -->
      <StageRunner
        v-else-if="current"
        :key="current"
        :proposalId="proposalId"
        :stage="current"
        @confirmed="afterStage"
        @skipped="afterStage"
      />

      <!-- 전술 완료 → 수렴 -->
      <div v-else class="plan-stages__consolidate">
        <p>전술 단계 완료. 표준 Diff 로 수렴하면 아키텍처 Plan 생성으로 이어집니다.</p>
        <button class="btn btn--primary" :disabled="busy" @click="consolidate">{{ t('proposals.staged.consolidate') }}</button>
      </div>
    </template>

    <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from '../../../app/i18n'
import { useProposalsStore } from '../proposals.store'
import StageRunner from './stages/StageRunner.vue'
import StageReadonly from './stages/StageReadonly.vue'

const props = defineProps({ proposalId: { type: String, required: true } })
const emit = defineEmits(['consolidated'])
const { t } = useI18n()
const store = useProposalsStore()

const STRATEGIC = ['DISCOVER', 'DECOMPOSE', 'STRATEGIZE']
const TACTICAL = ['CONNECT', 'DEFINE', 'TACTICAL']
const LABELS = { CONNECT: 'Connect — 컨텍스트 연동', DEFINE: 'Define — Bounded Context', TACTICAL: 'Tactical — Aggregate 설계' }
const busy = ref(false)
const errorMsg = ref('')
const viewing = ref(null)

const proposal = computed(() => store.currentProposal)
const activeStages = computed(() =>
  (proposal.value?.stagePlan?.stages || []).filter(s => !s.skipped).map(s => s.stage))
const artifacts = computed(() => proposal.value?.stageArtifacts || {})
const strategicActive = computed(() => activeStages.value.filter(s => STRATEGIC.includes(s)))
const tacticalActive = computed(() => activeStages.value.filter(s => TACTICAL.includes(s)))
const strategicDone = computed(() =>
  !!proposal.value?.stagePlan && strategicActive.value.every(s => artifacts.value[s]))
const current = computed(() => tacticalActive.value.find(s => !artifacts.value[s]) || null)

function shortLabel(s) { return { CONNECT: 'Connect', DEFINE: 'Define', TACTICAL: 'Tactical' }[s] }
function longLabel(s) { return LABELS[s] || s }
function stepState(s) {
  if (viewing.value === s) return 'viewing'
  if (artifacts.value[s]) return 'done'
  if (s === current.value) return 'current'
  return 'pending'
}
function onStepClick(s) {
  if (s === current.value) { viewing.value = null; return }   // 현재 단계로
  if (artifacts.value[s]) viewing.value = s                    // 완료 단계 보기
}

// 단계 전환 시 보기 모드 해제.
watch(current, () => { viewing.value = null })

async function afterStage() { await store.fetchProposal(props.proposalId) }

async function consolidate() {
  busy.value = true
  try { await store.consolidateStaged(props.proposalId); emit('consolidated') }
  catch (e) { errorMsg.value = e.message } finally { busy.value = false }
}
</script>

<style scoped>
.plan-stages { padding: 4px 0; }
.plan-stages__guard { font-size: 13px; color: var(--color-text-light); padding: 12px; border: 1px dashed var(--color-border); border-radius: 8px; }
.plan-stages__stepper { display: flex; gap: 6px; margin-bottom: 12px; }
.plan-stages__step { font-size: 11px; padding: 4px 12px; border-radius: 12px; border: none; background: var(--color-bg-tertiary); color: var(--color-text-light); cursor: default; }
.plan-stages__step.clickable { cursor: pointer; }
.plan-stages__step.done { background: var(--color-success); color: #fff; }
.plan-stages__step.current { background: var(--color-accent); color: #fff; }
.plan-stages__step.viewing { outline: 2px solid var(--color-accent); outline-offset: 1px; }
.plan-stages__view-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; font-size: 13px; color: var(--color-text-bright); }
.ro-tag { font-size: 10px; font-weight: 400; font-style: normal; color: var(--color-text-light); border: 1px solid var(--color-border); border-radius: 8px; padding: 1px 6px; margin-left: 6px; }
.plan-stages__consolidate p { font-size: 13px; margin: 8px 0; }
.btn { padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }
.btn--xs { padding: 3px 8px; font-size: 11px; }
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--primary:disabled { opacity: 0.5; }
.btn--ghost { background: transparent; border: 1px solid var(--color-border); color: var(--color-text); }
</style>
