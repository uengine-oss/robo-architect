<template>
  <div class="proposal-detail" v-if="proposal">
    <!-- Header -->
    <div class="detail-header">
      <div class="detail-header__meta">
        <span class="proposal-id">{{ proposal.id }}</span>
        <span :class="['status-badge', `status-badge--${proposal.status.toLowerCase()}`]">
          {{ proposal.status }}
        </span>
      </div>
      <h2 class="detail-header__title">{{ proposal.title }}</h2>
      <p class="detail-header__prompt">{{ proposal.originalPrompt }}</p>
      <div class="detail-header__info">
        <span>작성자: {{ proposal.author }}</span>
        <span>생성일: {{ formatDate(proposal.createdAt) }}</span>
      </div>
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
      <!-- Strategic + Tactical Diff -->
      <template v-if="activeTab === 'diff'">
        <IntentDecompositionView
          :strategicDiff="proposal.strategicDiff"
          :tacticalDiff="proposal.tacticalDiff"
          :proposalId="proposal.id"
        />
        <div v-if="isDraft" class="diff-actions">
          <button @click="showEditDiff = !showEditDiff" class="btn btn--secondary">
            {{ showEditDiff ? 'Diff 편집 닫기' : 'Diff 직접 수정' }}
          </button>
          <button @click="showFeedback = !showFeedback" class="btn btn--secondary" :disabled="regenerating">
            {{ showFeedback ? '재생성 닫기' : '의도가 다른가요? 피드백 후 재생성' }}
          </button>
        </div>

        <!-- 피드백 → 인텐트 재생성 -->
        <div v-if="showFeedback && isDraft" class="feedback-box">
          <label>잘못 분석된 부분을 알려주시면 다시 분해합니다.</label>
          <textarea
            v-model="feedbackText"
            rows="3"
            placeholder="예: 부분 환불이 아니라 전액 환불 취소 기능입니다. 환불 Aggregate가 아니라 주문 Aggregate를 바꿔야 합니다."
            class="feedback-box__textarea"
            :disabled="regenerating"
          />
          <div class="feedback-box__actions">
            <button @click="regenerateIntent" :disabled="!feedbackText.trim() || regenerating" class="btn btn--primary">
              {{ regenerating ? '재생성 중...' : '피드백 반영해 재생성' }}
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
              Claude가 다시 분석을 시작하고 있습니다...
            </div>
          </div>
        </div>
        <div v-if="showEditDiff && isDraft" class="diff-editor">
          <label>Strategic Diff (JSON)</label>
          <textarea v-model="editStrategicJson" rows="6" class="json-editor" />
          <label>Tactical Diff (JSON)</label>
          <textarea v-model="editTacticalJson" rows="6" class="json-editor" />
          <div class="diff-editor__actions">
            <button @click="saveDiff" :disabled="savingDiff" class="btn btn--primary">
              {{ savingDiff ? '저장 중...' : 'Diff 저장' }}
            </button>
          </div>
          <p v-if="diffError" class="error-msg">{{ diffError }}</p>
        </div>
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
      <template v-if="isDraft">
        <button
          @click="submitProposal"
          :disabled="!hasMinDiff || submitting"
          class="btn btn--primary"
        >
          {{ submitting ? '제출 중...' : 'Proposal 제출 (SUBMIT)' }}
        </button>
      </template>
      <template v-if="canImplement">
        <button @click="activeTab = 'sandbox'" class="btn btn--primary">샌드박스 구현 열기</button>
      </template>
    </div>

    <p v-if="actionError" class="error-msg">{{ actionError }}</p>
  </div>
  <div v-else class="detail-loading">Proposal을 불러오는 중...</div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useProposalsStore } from '../proposals.store'
import IntentDecompositionView from './IntentDecompositionView.vue'
import ImpactMapView from './ImpactMapView.vue'
import ProposalDiffVisualView from './ProposalDiffVisualView.vue'
import SandboxProgressView from './SandboxProgressView.vue'
import TestResultsView from './TestResultsView.vue'
import DualMergeView from './DualMergeView.vue'

const props = defineProps({ proposalId: { type: String, required: true } })
const store = useProposalsStore()
const activeTab = ref('diff')
const showEditDiff = ref(false)
const editStrategicJson = ref('')
const editTacticalJson = ref('')
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
const isDraft = computed(() => proposal.value?.status === 'DRAFT')
const isSubmitted = computed(() => proposal.value?.status === 'SUBMITTED')
const REIMPLEMENTABLE = ['SUBMITTED', 'IMPLEMENTING', 'TESTING', 'PENDING_ACCEPTANCE', 'MERGE_FAILED']
// 실제 구현 시작/완료/재구현 컨트롤은 SandboxProgressView(샌드박스 탭)가 tasks.md
// 진행 상태로 노출한다. 여기서는 "샌드박스 구현 열기" 버튼 노출 여부만 판단한다.
const canImplement = computed(() => REIMPLEMENTABLE.includes(proposal.value?.status))
const hasMinDiff = computed(() =>
  proposal.value?.strategicDiff || proposal.value?.tacticalDiff
)

const allTabs = [
  { key: 'diff', label: 'Strategic + Tactical Diff' },
  { key: 'impact', label: 'Impact Map' },
  { key: 'sandbox', label: '샌드박스 구현' },
  { key: 'tests', label: '검증' },
  { key: 'acceptance', label: 'Accept / Destroy' },
]

const availableTabs = computed(() => {
  const s = proposal.value?.status
  if (!s) return [allTabs[0]]
  if (s === 'DRAFT') return allTabs.slice(0, 2)
  if (s === 'SUBMITTED') return allTabs.slice(0, 3)
  if (s === 'IMPLEMENTING') return allTabs.slice(0, 3)
  // TESTING = 구현 완료. 검증을 아직(또는 통과)하지 않았더라도 PO가 Accept/Destroy
  // 탭으로 넘어갈 수 있어야 하므로 검증·Accept/Destroy 탭을 모두 노출한다.
  return allTabs
})

onMounted(async () => {
  await store.fetchProposal(props.proposalId)
  if (proposal.value) {
    editStrategicJson.value = JSON.stringify(proposal.value.strategicDiff || {}, null, 2)
    editTacticalJson.value = JSON.stringify(proposal.value.tacticalDiff || [], null, 2)
  }
})

async function saveDiff() {
  diffError.value = ''
  savingDiff.value = true
  try {
    const sd = JSON.parse(editStrategicJson.value)
    const td = JSON.parse(editTacticalJson.value)
    await store.updateDiff(props.proposalId, { strategicDiff: sd, tacticalDiff: td })
    showEditDiff.value = false
  } catch (e) {
    diffError.value = `Diff 저장 실패: ${e.message}`
  } finally {
    savingDiff.value = false
  }
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
    editTacticalJson.value = JSON.stringify(proposal.value.tacticalDiff || [], null, 2)
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
.detail-actions { margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--color-border); display: flex; gap: 8px; }
.btn { padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--primary:disabled { opacity: 0.5; cursor: default; }
.btn--secondary { background: var(--color-bg-tertiary); color: var(--color-text); }
.error-msg { color: var(--color-danger); font-size: 12px; margin-top: 6px; }
.impact-conflict { margin-top: 14px; border-top: 1px solid var(--color-border); padding-top: 10px; }
.impact-conflict summary { font-size: 12px; font-weight: 600; color: var(--color-text-light); cursor: pointer; }
</style>
