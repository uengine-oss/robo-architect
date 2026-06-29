<template>
  <div class="proposal-detail" v-if="proposal">
    <!-- Header -->
    <div class="detail-header">
      <div class="detail-header__meta">
        <span class="proposal-id">{{ proposal.id }}</span>
        <span :class="['status-badge', `status-badge--${proposal.status.toLowerCase()}`]">
          {{ statusLabel(proposal.status) }}
        </span>
      </div>
      <h2 class="detail-header__title">{{ proposal.title }}</h2>
      <p class="detail-header__prompt">{{ proposal.originalPrompt }}</p>
      <div class="detail-header__info">
        <span>{{ t('proposals.detail.author') }} {{ proposal.author }}</span>
        <span>{{ t('proposals.detail.createdAt') }} {{ formatDate(proposal.createdAt) }}</span>
      </div>
    </div>

    <!-- 041 — Plan stale 배너: Constitution/Strategic 변경 후 재계획 전까지 제출 차단(FR-018) -->
    <div v-if="isDraft && planStale" class="plan-stale-banner">
      <span>{{ t('proposals.detail.planStaleBanner') }}</span>
      <button @click="activeTab = 'plan'" class="btn btn--secondary btn--sm">{{ t('proposals.detail.openPlanStage') }}</button>
    </div>

    <!-- Tabs -->
    <div class="detail-tabs">
      <button
        v-for="tab in availableTabs"
        :key="tab.key"
        @click="activeTab = tab.key"
        :class="['tab-btn', activeTab === tab.key ? 'tab-btn--active' : '']"
      >{{ tab.label }}</button>
    </div>

    <!-- Tab Content -->
    <div class="detail-content">
      <!-- Intent — Strategic Diff 만 (FR-006) -->
      <template v-if="activeTab === 'diff'">
        <!-- 043 — ODA 표준: Intent 탭에 ODA 트랙(정합성·적합성 게이트·산출물) 융합 -->
        <OdaStandardTrack
          v-if="isOda"
          :proposalId="proposal.id"
        />
        <!-- 042 — Detailed DDD: Intent 탭에 전략 단계(Discover·Decompose·Strategize) 융합 -->
        <StrategicStages
          v-else-if="showStrategicStages"
          :proposalId="proposal.id"
          @goto-plan="proceedToPlan"
        />
        <template v-else>
        <IntentDecompositionView
          :strategicDiff="proposal.strategicDiff"
          :proposalId="proposal.id"
        />
        <div v-if="canUpgradeToDetailed" class="diff-actions">
          <button @click="upgradeToDetailed" :disabled="upgrading" class="btn btn--secondary">
            {{ t('proposals.staged.upgradeToDetailed') }}
          </button>
        </div>
        <div v-if="isDraft" class="diff-actions">
          <button @click="showEditDiff = !showEditDiff" class="btn btn--secondary">
            {{ showEditDiff ? t('proposals.detail.diffEditClose') : t('proposals.detail.diffEditOpen') }}
          </button>
          <button @click="showFeedback = !showFeedback" class="btn btn--secondary" :disabled="regenerating">
            {{ showFeedback ? t('proposals.detail.regenClose') : t('proposals.detail.regenOpen') }}
          </button>
        </div>

        <!-- 피드백 → 인텐트 재생성 -->
        <div v-if="showFeedback && isDraft" class="feedback-box">
          <label>{{ t('proposals.detail.feedbackLabel') }}</label>
          <textarea
            v-model="feedbackText"
            rows="3"
            :placeholder="t('proposals.detail.feedbackPlaceholder')"
            class="feedback-box__textarea"
            :disabled="regenerating"
          />
          <div class="feedback-box__actions">
            <button @click="regenerateIntent" :disabled="!feedbackText.trim() || regenerating" class="btn btn--primary">
              {{ regenerating ? t('proposals.detail.regenProgress') : t('proposals.detail.regenSubmit') }}
            </button>
          </div>
          <p v-if="feedbackError" class="error-msg">{{ feedbackError }}</p>

          <!-- 재생성 실시간 narration (이 화면에서 재생성을 시작한 경우에만) -->
          <div v-if="regenerating || hasRegenerated" class="stream-log">
            <div
              v-for="(line, i) in store.intentStream.logLines"
              :key="i"
              :class="['stream-log__line', logLineClass(line)]"
            >{{ line }}</div>
            <div v-if="regenerating && !store.intentStream.logLines?.length" class="stream-log__waiting">
              {{ t('proposals.detail.regenWaiting') }}
            </div>
          </div>
        </div>
        <div v-if="showEditDiff && isDraft" class="diff-editor">
          <label>{{ t('proposals.detail.strategicDesignJson') }}</label>
          <textarea v-model="editStrategicJson" rows="8" class="json-editor" />
          <div class="diff-editor__actions">
            <button @click="saveDiff" :disabled="savingDiff" class="btn btn--primary">
              {{ savingDiff ? t('proposals.common.saving') : t('proposals.detail.saveDiff') }}
            </button>
          </div>
          <p v-if="diffError" class="error-msg">{{ diffError }}</p>
        </div>
        </template>
      </template>

      <!-- Impact Map: 038식 레이어별 구조화 diff 시각화 + 충돌 테이블(보조) -->
      <template v-if="activeTab === 'impact'">
        <ProposalDiffVisualView
          :strategicDiff="proposal.strategicDiff"
          :tacticalDiff="proposal.tacticalDiff"
          :journeys="proposal.journeys"
        />
        <details v-if="proposal.impactMap?.length" class="impact-conflict">
          <summary>충돌 가능성 분석 (Impact Map)</summary>
          <ImpactMapView :impactMap="proposal.impactMap" :proposalId="proposal.id" />
        </details>
      </template>

      <!-- 041 — Plan 단계 (tactical + impact + 아키텍처). Constitution 부재 시
           인터뷰는 PlanView 내부에서 인라인으로 진행된다(보기/수정은 Design 측). -->
      <template v-if="activeTab === 'plan'">
        <!-- 042 — Plan 단계는 SUBMITTED 상태에서. DRAFT 면 Intent 완료 안내(잠금). -->
        <div v-if="planLocked" class="plan-locked">
          🔒 Plan 단계는 Intent(전략 분해)를 완료하고 <b>‘Plan 단계로 진행’</b> 한 뒤에 진행됩니다.
        </div>
        <!-- Detailed DDD: Plan 탭에 전술 단계(Connect·Define·Tactical) 융합 → 수렴 후 기존 PlanView -->
        <PlanStages
          v-else-if="showPlanStages"
          :proposalId="proposal.id"
          @consolidated="onStagedConsolidated"
        />
        <PlanView
          v-else
          :proposalId="proposal.id"
          @confirmed="onPlanConfirmed"
        />
      </template>

      <!-- Sandbox Progress -->
      <template v-if="activeTab === 'sandbox'">
        <SandboxProgressView :proposalId="proposal.id" @validate="activeTab = 'tests'" />
      </template>

      <!-- Test Results -->
      <template v-if="activeTab === 'tests'">
        <TestResultsView :proposalId="proposal.id" />
      </template>

      <!-- Accept / Destroy -->
      <template v-if="activeTab === 'acceptance'">
        <DualMergeView :proposal="proposal" />
      </template>
    </div>

    <!-- Action Bar -->
    <div class="detail-actions">
      <!-- 042 — Intent 완료 = Plan 단계로 진행(제출). -->
      <template v-if="isDraft">
        <button
          @click="proceedToPlan"
          :disabled="!canProceedToPlan || proceeding"
          :title="canProceedToPlan ? '' : t('proposals.detail.noStrategicDesign')"
          class="btn btn--primary"
        >
          {{ proceeding ? t('proposals.detail.submitting') : t('proposals.staged.proceedToPlan') }}
        </button>
      </template>
      <template v-if="canImplement">
        <button @click="activeTab = 'sandbox'" class="btn btn--primary">{{ t('proposals.detail.openSandbox') }}</button>
      </template>
      <span v-else-if="isSubmitted && implementBlockReason" class="detail-actions__hint" :title="implementBlockReason">⚠ {{ implementBlockReason }}</span>
    </div>

    <p v-if="actionError" class="error-msg">{{ actionError }}</p>
  </div>
  <div v-else class="detail-loading">{{ t('proposals.detail.loading') }}</div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from '../../../app/i18n'
import { useProposalsStore } from '../proposals.store'
import IntentDecompositionView from './IntentDecompositionView.vue'
import ImpactMapView from './ImpactMapView.vue'
import ProposalDiffVisualView from './ProposalDiffVisualView.vue'
import SandboxProgressView from './SandboxProgressView.vue'
import TestResultsView from './TestResultsView.vue'
import DualMergeView from './DualMergeView.vue'
import PlanView from './PlanView.vue'
import StrategicStages from './StrategicStages.vue'
import PlanStages from './PlanStages.vue'
import OdaStandardTrack from './OdaStandardTrack.vue'

const props = defineProps({ proposalId: { type: String, required: true } })
const { t } = useI18n()
const store = useProposalsStore()
const activeTab = ref('diff')
const showEditDiff = ref(false)
const editStrategicJson = ref('')
const savingDiff = ref(false)
const diffError = ref('')
const submitting = ref(false)
const actionError = ref('')
const showFeedback = ref(false)
const feedbackText = ref('')
const feedbackError = ref('')
const regenerating = ref(false)
const hasRegenerated = ref(false)

const proposal = computed(() => store.currentProposal)
// 042 — 상태 표시 라벨(코드 유지, 표시만 단계명): DRAFT=Intent, SUBMITTED=Plan, TESTING=Validating.
function statusLabel(status) {
  return {
    DRAFT: t('proposals.panel.statusDraft'),
    SUBMITTED: t('proposals.panel.statusSubmitted'),
    TESTING: t('proposals.panel.statusTesting'),
    PENDING_ACCEPTANCE: t('proposals.panel.statusPendingAcceptance'),
    MERGE_FAILED: t('proposals.panel.statusMergeFailed'),
  }[status] || status
}
const isDraft = computed(() => proposal.value?.status === 'DRAFT')
const isSubmitted = computed(() => proposal.value?.status === 'SUBMITTED')
// 042 — 라이프사이클: DRAFT=Intent 단계, SUBMITTED=Plan 단계, IMPLEMENTING~ 유지.
const isDetailed = computed(() => proposal.value?.decompositionMode === 'DETAILED_DDD')
// 043 — ODA 표준 모드: Intent 탭에 ODA 트랙(정합성·게이트·산출물) 융합.
const isOda = computed(() => proposal.value?.decompositionMode === 'ODA_STANDARD')
const _hasStrategic = computed(() => {
  const sd = proposal.value?.strategicDiff
  return !!(sd && (sd.epics?.length || sd.userStories?.length || sd.features?.length))
})
const _hasTactical = computed(() => !!proposal.value?.tacticalDiff?.length)
const STRATEGIC_STAGES = ['DISCOVER', 'DECOMPOSE', 'STRATEGIZE']
// 전략(Intent) 단계가 모두 끝났는가 — Detailed 한정(stagePlan 의 비생략 전략 단계 산출물 존재).
const strategicStagesDone = computed(() => {
  const plan = proposal.value?.stagePlan
  if (!plan?.stages?.length) return false
  const arts = proposal.value?.stageArtifacts || {}
  return plan.stages.filter(s => !s.skipped && STRATEGIC_STAGES.includes(s.stage))
    .every(s => arts[s.stage])
})

// Intent 탭(DRAFT): Detailed 면 전략 단계 stepper, 아니면 IntentDecompositionView.
const showStrategicStages = computed(() => isDetailed.value && isDraft.value)
// Plan 탭은 SUBMITTED(=Plan 단계)에서만. DRAFT 면 잠금.
const planLocked = computed(() => isDraft.value)
// Plan 탭(SUBMITTED): Detailed 이고 전술(tacticalDiff) 미수렴이면 전술 단계 stepper, 아니면 PlanView.
const showPlanStages = computed(() =>
  isDetailed.value && isSubmitted.value && !_hasTactical.value && !!proposal.value?.stagePlan)
const showPlanView = computed(() => !isDraft.value && !showPlanStages.value)

const canUpgradeToDetailed = computed(() =>
  proposal.value?.decompositionMode === 'SIMPLIFIED' && isDraft.value &&
  !proposal.value?.implementationPlan)
const upgrading = ref(false)
async function upgradeToDetailed() {
  upgrading.value = true
  try { await store.upgradeMode(props.proposalId); activeTab.value = 'diff' }
  catch (e) { actionError.value = e.message } finally { upgrading.value = false }
}

// 042 — Intent 완료 = 제출(Plan 단계로 진행). Detailed=전략 단계 완료, Simplified=strategicDiff 존재.
const canProceedToPlan = computed(() =>
  isDraft.value && (isDetailed.value ? strategicStagesDone.value : _hasStrategic.value))
const proceeding = ref(false)
async function proceedToPlan() {
  proceeding.value = true
  actionError.value = ''
  try {
    await store.proceedToPlan(props.proposalId)   // 전략 수렴 + DRAFT→SUBMITTED
    activeTab.value = 'plan'
  } catch (e) { actionError.value = e.message } finally { proceeding.value = false }
}
// StrategicStages 의 "Plan 단계로 진행" 버튼 → 제출 + Plan 탭.
function onStagedConsolidated() { /* PlanStages 가 전술 수렴 후 호출 — PlanView 로 자연 전환 */
  store.fetchProposal(props.proposalId)
}

const REIMPLEMENTABLE = ['SUBMITTED', 'IMPLEMENTING', 'TESTING', 'PENDING_ACCEPTANCE', 'MERGE_FAILED']
// 041 — staleness.
const planStale = computed(() => !!proposal.value?.planStale)
const hasConfirmedPlan = computed(() => !!proposal.value?.implementationPlan)
// 042 — 구현 가능: SUBMITTED~ 이고, (첫 구현이면) 확정 non-stale Plan 필요. Plan 게이트는 여기로 이동.
const canImplement = computed(() => {
  if (!REIMPLEMENTABLE.includes(proposal.value?.status)) return false
  if (proposal.value?.status === 'SUBMITTED') return hasConfirmedPlan.value && !planStale.value
  return true   // IMPLEMENTING/TESTING/… 재구현은 이미 plan 있음
})
const implementBlockReason = computed(() => {
  if (proposal.value?.status === 'SUBMITTED' && !hasConfirmedPlan.value) return t('proposals.detail.noPlan')
  if (proposal.value?.status === 'SUBMITTED' && planStale.value) return t('proposals.detail.stalePlan')
  return ''
})

// 041 — 스테이지 순서: Intent → Plan → Impact → Submit.
// (Constitution 보기/수정은 Proposals 탭이 아니라 Design 측에서 관리한다.
//  Plan 단계에서 Constitution 이 없으면 인터뷰가 인라인으로 진행된다.)
const allTabs = computed(() => [
  { key: 'diff', label: t('proposals.detail.tabIntent') },
  { key: 'plan', label: t('proposals.detail.tabPlan') },
  { key: 'impact', label: t('proposals.detail.tabImpact') },
  { key: 'sandbox', label: t('proposals.detail.tabSandbox') },
  { key: 'tests', label: t('proposals.detail.tabTests') },
  { key: 'acceptance', label: t('proposals.detail.tabAcceptance') },
])

const availableTabs = computed(() => {
  const s = proposal.value?.status
  const tabs = allTabs.value
  if (!s) return [tabs[0]]
  // DRAFT: Intent / Plan / Impact 까지 노출(제출 전 스테이지).
  if (s === 'DRAFT') return tabs.slice(0, 3)
  if (s === 'SUBMITTED' || s === 'IMPLEMENTING') return tabs.slice(0, 4)
  // TESTING = 구현 완료. 검증을 아직(또는 통과)하지 않았더라도 PO가 Accept/Destroy
  // 탭으로 넘어갈 수 있어야 하므로 검증·Accept/Destroy 탭을 모두 노출한다.
  return tabs
})

onMounted(async () => {
  await store.fetchProposal(props.proposalId)
  if (proposal.value) {
    editStrategicJson.value = JSON.stringify(proposal.value.strategicDiff || {}, null, 2)
  }
  // 041 — Constitution 존재 여부를 미리 조회(탭/버튼 라벨 + Amend 진입점 판단).
  store.getConstitution(props.proposalId)
})

async function saveDiff() {
  diffError.value = ''
  savingDiff.value = true
  try {
    const sd = JSON.parse(editStrategicJson.value)
    // 041 — Intent 단계는 Strategic 만 편집. tacticalDiff 는 Plan 단계에서 관리한다.
    await store.updateDiff(props.proposalId, { strategicDiff: sd })
    showEditDiff.value = false
  } catch (e) {
    diffError.value = t('proposals.detail.draftSaveFailed', { msg: e.message })
  } finally {
    savingDiff.value = false
  }
}

// 041 — Plan 확정 후 proposal(특히 planStale)을 재조회한다.
async function onPlanConfirmed() {
  await store.fetchProposal(props.proposalId)
}

// 피드백을 등록한 뒤 인텐트 SSE를 다시 구독해 재분해한다. done이면 새 diff가
// currentProposal에 반영되고 편집기 텍스트도 갱신한다.
async function regenerateIntent() {
  feedbackError.value = ''
  regenerating.value = true
  try {
    await store.submitIntentFeedback(props.proposalId, feedbackText.value.trim())
    hasRegenerated.value = true
    store.subscribeToIntent(props.proposalId)
  } catch (e) {
    feedbackError.value = e.message
    regenerating.value = false
  }
}

// 재생성 SSE 완료/실패 감지 → 상태 해제 + 편집기 동기화.
watch(() => store.intentStream.active, (active, was) => {
  if (!regenerating.value || active || !was) return
  regenerating.value = false
  if (store.intentStream.error) {
    feedbackError.value = store.intentStream.error
    return
  }
  feedbackText.value = ''
  if (proposal.value) {
    editStrategicJson.value = JSON.stringify(proposal.value.strategicDiff || {}, null, 2)
  }
})

function logLineClass(line) {
  if (line.startsWith('[tool]')) return 'stream-log__line--tool'
  if (/^\[.+\]/.test(line)) return 'stream-log__line--tag'
  if (line.startsWith('{') || line.startsWith('"') || line === '}' || line === ']') return 'stream-log__line--json'
  return ''
}

async function submitProposal() {
  actionError.value = ''
  submitting.value = true
  try {
    await store.submitProposal(props.proposalId)
    activeTab.value = 'sandbox'
  } catch (e) {
    actionError.value = e.message
  } finally {
    submitting.value = false
  }
}

// 구현 시작/완료/재구현 흐름은 SandboxProgressView(샌드박스 탭)가 tasks.md
// 진행 상태로 직접 처리한다. 여기서는 탭만 연다(위 "샌드박스 구현 열기" 버튼).

function formatDate(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleString('ko-KR')
}
</script>

<style scoped>
.proposal-detail { padding: 16px; }
.detail-loading { color: var(--color-text-light); padding: 24px; }
.detail-header { margin-bottom: 16px; }
.detail-header__meta { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.proposal-id { font-family: monospace; font-size: 12px; color: var(--color-text-light); background: var(--color-bg-tertiary); padding: 2px 6px; border-radius: 3px; }
.detail-header__title { font-size: 18px; font-weight: 600; margin: 0 0 4px; color: var(--color-text-bright); }
.detail-header__prompt { font-size: 13px; color: var(--color-text-light); margin: 0 0 8px; }
.detail-header__info { display: flex; gap: 16px; font-size: 12px; color: var(--color-text-light); }
.status-badge { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 9999px; text-transform: uppercase; }
.status-badge--draft { background: var(--status-neutral-bg); color: var(--status-neutral-fg); }
.status-badge--submitted { background: var(--status-blue-bg); color: var(--status-blue-fg); }
.status-badge--implementing { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.status-badge--testing { background: var(--status-orange-bg); color: var(--status-orange-fg); }
.status-badge--pending_acceptance { background: var(--status-purple-bg); color: var(--status-purple-fg); }
.status-badge--accepted { background: var(--status-green-bg); color: var(--status-green-fg); }
.status-badge--destroyed { background: var(--status-red-bg); color: var(--status-red-fg); }
.status-badge--merge_failed { background: var(--status-red-bg); color: var(--status-red-fg); }
.detail-tabs { display: flex; gap: 4px; border-bottom: 2px solid var(--color-border); margin-bottom: 16px; flex-wrap: wrap; }
.tab-btn { background: none; border: none; padding: 8px 14px; font-size: 13px; cursor: pointer; color: var(--color-text-light); border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab-btn--active { color: var(--color-accent); border-bottom-color: var(--color-accent); font-weight: 600; }
.detail-content { min-height: 200px; }
.diff-actions { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
.btn:disabled { opacity: 0.5; cursor: default; }
.feedback-box { margin-top: 12px; border: 1px solid var(--color-border); border-radius: 6px; padding: 12px; background: var(--color-bg-secondary); }
.feedback-box label { display: block; font-size: 12px; font-weight: 600; color: var(--color-text); margin-bottom: 6px; }
.feedback-box__textarea { width: 100%; resize: vertical; font-size: 13px; border: 1px solid var(--color-border); border-radius: 4px; padding: 6px; background: var(--color-bg); color: var(--color-text); box-sizing: border-box; }
.feedback-box__actions { margin-top: 8px; }
.stream-log { margin-top: 10px; background: #0f172a; border-radius: 6px; padding: 10px 12px; max-height: 240px; overflow-y: auto; font-family: monospace; font-size: 11px; color: #cbd5e1; }
.stream-log__line { padding: 1px 0; white-space: pre-wrap; word-break: break-all; line-height: 1.5; }
.stream-log__line--tag { color: #86efac; font-weight: 600; }
.stream-log__line--tool { color: #7dd3fc; }
.stream-log__line--json { color: #64748b; font-size: 10px; }
.stream-log__waiting { color: #64748b; }
.diff-editor { margin-top: 12px; }
.diff-editor label { display: block; font-size: 12px; font-weight: 600; color: var(--color-text); margin-bottom: 4px; margin-top: 8px; }
.json-editor { width: 100%; font-family: monospace; font-size: 12px; border: 1px solid var(--color-border); border-radius: 4px; padding: 6px; background: var(--color-bg-secondary); color: var(--color-text); }
.diff-editor__actions { margin-top: 8px; }
.detail-actions { margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--color-border); display: flex; gap: 8px; align-items: center; }
.detail-actions__hint { font-size: 12px; color: var(--status-amber-fg); }
.plan-locked { font-size: 13px; color: var(--color-text-light); padding: 14px; border: 1px dashed var(--color-border); border-radius: 8px; }
.btn { padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }
.btn--sm { padding: 4px 10px; font-size: 12px; }
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--primary:disabled { opacity: 0.5; cursor: default; }
.btn--secondary { background: var(--color-bg-tertiary); color: var(--color-text); }
.error-msg { color: var(--color-danger); font-size: 12px; margin-top: 6px; }
.plan-stale-banner { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; padding: 8px 12px; border-radius: 6px; font-size: 12px; background: var(--status-amber-bg); color: var(--status-amber-fg); }
.impact-conflict { margin-top: 14px; border-top: 1px solid var(--color-border); padding-top: 10px; }
.impact-conflict summary { font-size: 12px; font-weight: 600; color: var(--color-text-light); cursor: pointer; }
</style>
