<script setup>
import { computed, inject, ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'
import { useSessionStore } from '@/features/desktop-launcher/stores/session-store.js'
import ChangeImpactView from './ChangeImpactView.vue'
import ChangeTasksView from './ChangeTasksView.vue'
import DesignChangesView from './DesignChangesView.vue'
import RegressionTab from './RegressionTab.vue'

const props = defineProps({
  change: { type: Object, required: true },
  autoAnalyze: { type: Boolean, default: false },
})
const emit = defineEmits(['updated', 'deleted', 'analyzed'])

const store = useRequirementsStore()
const session = useSessionStore()
const openClaudeCode = inject('openClaudeCode', null)
const claudeCodeWorkdir = inject('claudeCodeWorkdir', null)
const activeTab = ref('info')

// 생성 직후 자동 영향도 탭 오픈 + 분석 트리거
import { onMounted, watch } from 'vue'
onMounted(() => {
  if (props.autoAnalyze) {
    activeTab.value = 'impact'
  }
})
watch(() => props.autoAnalyze, (v) => {
  if (v) activeTab.value = 'impact'
})
const rejectDialog = ref(false)
const rejectComment = ref('')
const approveComment = ref('')
const approveDialog = ref(false)
const preflightDialog = ref(false)
const preflight = ref(null)
const implementing = ref(false)
const actionLoading = ref(false)

const STATUS_COLORS = {
  DRAFT: '#909296',
  SUBMITTED: '#228be6',
  PLAN_APPROVED: '#ae3ec9',
  DESIGN_APPLIED: '#f59f00',
  APPROVED: '#40c057',
  REJECTED: '#fa5252',
  IMPLEMENTED: '#868e96',
}

const STATUS_LABELS = {
  DRAFT: '작성 중',
  SUBMITTED: '검토 요청',
  PLAN_APPROVED: '계획 승인 (1차)',
  DESIGN_APPLIED: '설계 반영 완료',
  APPROVED: '구현 승인 (2차)',
  REJECTED: '반려됨',
  IMPLEMENTED: '구현 완료',
}

const currentUser = computed(() => session.user?.email || '')
// isOtherUser는 UI 힌트용으로만 유지 (승인 가능 여부는 백엔드 권한 체계가 결정)
const isOtherUser = computed(() => props.change.author !== currentUser.value)

// 단계별 가능 액션
// ※ 승인/반려 버튼은 상태 조건만 확인. 자기 승인 허용 여부는 백엔드가 결정
//   (ProductOwner 역할이 있으면 자기 승인 가능 — 기본값으로 모든 사용자에게 부여됨)
const canSubmit      = computed(() => props.change.status === 'DRAFT')
const canApprove1    = computed(() => props.change.status === 'SUBMITTED')
const canApplyDesign = computed(() => props.change.status === 'PLAN_APPROVED')
const canApprove2    = computed(() => props.change.status === 'DESIGN_APPLIED')
const canImplement   = computed(() => props.change.status === 'APPROVED')
const canReject      = computed(() =>
  props.change.status === 'SUBMITTED' || props.change.status === 'DESIGN_APPLIED'
)

// 승인 다이얼로그 구분
const approveStage = ref(1) // 1 = 1차 승인, 2 = 2차 승인

async function onSubmit() {
  actionLoading.value = true
  try {
    const updated = await store.submitChange(props.change.id)
    emit('updated', updated)
  } finally { actionLoading.value = false }
}

function openApproveDialog(stage) {
  approveStage.value = stage
  approveComment.value = ''
  approveDialog.value = true
}

async function onApprove() {
  actionLoading.value = true
  try {
    let updated
    if (approveStage.value === 1) {
      updated = await store.approveChange(props.change.id, approveComment.value || null)
      // 1차 승인 후 자동으로 설계 반영 탭으로 이동
      activeTab.value = 'design'
    } else {
      updated = await store.approveImpl(props.change.id, approveComment.value || null)
    }
    approveDialog.value = false
    approveComment.value = ''
    emit('updated', updated)
  } catch (e) {
    alert(e.message)
  } finally { actionLoading.value = false }
}

async function onReject() {
  if (!rejectComment.value.trim()) return
  actionLoading.value = true
  try {
    const updated = await store.rejectChange(props.change.id, rejectComment.value)
    rejectDialog.value = false
    rejectComment.value = ''
    emit('updated', updated)
  } finally { actionLoading.value = false }
}

function onDesignApplied() {
  store.fetchChangeById(props.change.id).then(updated => emit('updated', updated))
}

function onDesignUndone() {
  // DESIGN_APPLIED → PLAN_APPROVED 복원 후 상태 갱신
  store.fetchChangeById(props.change.id).then(updated => emit('updated', updated))
}

async function onStartImplement() {
  const workdir = claudeCodeWorkdir?.value || ''
  const command = `/robo-implement ${props.change.id}`
  if (openClaudeCode) {
    openClaudeCode(workdir, command)
  }
}

function startImplementation(includePriorChangeIds) {
  preflightDialog.value = false
  implementing.value = true
  activeTab.value = 'tasks'
}

const FLOW_ORDER = ['DRAFT','SUBMITTED','PLAN_APPROVED','DESIGN_APPLIED','APPROVED','IMPLEMENTED']
function isStepDone(step) {
  const cur = FLOW_ORDER.indexOf(props.change.status)
  return FLOW_ORDER.indexOf(step) < cur
}
function isStepFuture(step) {
  const cur = FLOW_ORDER.indexOf(props.change.status)
  return FLOW_ORDER.indexOf(step) > cur
}

function formatDate(d) {
  return d ? new Date(d).toLocaleString('ko-KR') : ''
}
</script>

<template>
  <div class="cd-root">
    <!-- 헤더 -->
    <div class="cd-header">
      <span class="cd-id">{{ change.id }}</span>
      <span class="cd-status" :style="{ background: STATUS_COLORS[change.status] + '22', color: STATUS_COLORS[change.status], borderColor: STATUS_COLORS[change.status] + '55' }">
        {{ STATUS_LABELS[change.status] || change.status }}
      </span>
      <span class="cd-source">{{ change.sourceType }}</span>
      <div class="cd-actions">
        <!-- DRAFT -->
        <button v-if="canSubmit" class="tb-btn" style="color:#228be6;border-color:#228be650" :disabled="actionLoading" @click="onSubmit">제출</button>
        <!-- SUBMITTED: 1차 승인 -->
        <button v-if="canApprove1" class="tb-btn" style="color:#ae3ec9;border-color:#ae3ec950" :disabled="actionLoading" @click="openApproveDialog(1)">1차 승인</button>
        <!-- PLAN_APPROVED: 설계 반영 -->
        <button v-if="canApplyDesign" class="tb-btn" style="color:#f59f00;border-color:#f59f0050" :disabled="actionLoading" @click="activeTab='design'">설계 반영 →</button>
        <!-- DESIGN_APPLIED: 2차 승인 -->
        <button v-if="canApprove2" class="tb-btn" style="color:#40c057;border-color:#40c05750" :disabled="actionLoading" @click="openApproveDialog(2)">2차 승인 (구현 허가)</button>
        <!-- 반려 -->
        <button v-if="canReject" class="tb-btn" style="color:#fa5252;border-color:#fa525250" :disabled="actionLoading" @click="rejectDialog = true">반려</button>
        <!-- APPROVED: 구현 시작 -->
        <button v-if="canImplement" class="tb-btn" style="color:#40c057;border-color:#40c05750;font-weight:700" :disabled="actionLoading" @click="onStartImplement">구현 시작 →</button>
      </div>
    </div>

    <!-- 2단계 승인 흐름 표시 -->
    <div class="cd-flow">
      <div v-for="(step, i) in ['DRAFT','SUBMITTED','PLAN_APPROVED','DESIGN_APPLIED','APPROVED','IMPLEMENTED']" :key="step"
           class="cd-flow__step"
           :class="{
             'cd-flow__step--done': isStepDone(step),
             'cd-flow__step--current': change.status === step,
             'cd-flow__step--future': isStepFuture(step),
           }">
        <span class="cd-flow__dot" />
        <span class="cd-flow__label">{{ STATUS_LABELS[step] }}</span>
        <span v-if="i < 5" class="cd-flow__arrow">›</span>
      </div>
    </div>

    <div class="cd-title">{{ change.title }}</div>
    <div class="cd-meta">작성자: {{ change.author }} · {{ formatDate(change.createdAt) }}</div>

    <!-- 탭 -->
    <div class="cd-tabs">
      <button class="cd-tab" :class="{ 'cd-tab--active': activeTab === 'info' }" @click="activeTab = 'info'">정보</button>
      <button class="cd-tab" :class="{ 'cd-tab--active': activeTab === 'impact' }" @click="activeTab = 'impact'">영향도</button>
      <button
        v-if="['PLAN_APPROVED','DESIGN_APPLIED','APPROVED','IMPLEMENTED'].includes(change.status)"
        class="cd-tab"
        :class="{ 'cd-tab--active': activeTab === 'design' }"
        @click="activeTab = 'design'"
      >설계 반영</button>
      <button v-if="implementing || change.status === 'IMPLEMENTED'" class="cd-tab" :class="{ 'cd-tab--active': activeTab === 'tasks' }" @click="activeTab = 'tasks'">구현</button>
      <button class="cd-tab" :class="{ 'cd-tab--active': activeTab === 'regression' }" @click="activeTab = 'regression'">회귀 테스트</button>
      <button class="cd-tab" :class="{ 'cd-tab--active': activeTab === 'history' }" @click="activeTab = 'history'">이력</button>
    </div>

    <div class="cd-body">
      <!-- 정보 탭 -->
      <div v-if="activeTab === 'info'">
        <div class="cd-section-label">원본 프롬프트</div>
        <div class="cd-prompt">{{ change.originalPrompt || '(없음)' }}</div>
        <div v-if="change.changeSetId" class="cd-meta" style="margin-top:8px">ChangeSet: {{ change.changeSetId }}</div>
      </div>

      <!-- 영향도 탭 -->
      <div v-else-if="activeTab === 'impact'">
        <ChangeImpactView
          :change-id="change.id"
          :initial-effects="change.effects"
          :auto-analyze="autoAnalyze"
          @analyzed="$emit('analyzed')"
        />
      </div>

      <!-- 설계 반영 탭 -->
      <div v-else-if="activeTab === 'design'">
        <DesignChangesView
          :change-id="change.id"
          :status="change.status"
          :auto-apply="change.status === 'PLAN_APPROVED'"
          @applied="onDesignApplied"
          @undone="onDesignUndone"
        />
      </div>

      <!-- 구현 탭 -->
      <div v-else-if="activeTab === 'tasks'">
        <ChangeTasksView
          :change-id="change.id"
          :auto-start="implementing"
          @started="implementing = false"
          @done="$emit('updated', { ...change, status: 'IMPLEMENTED' })"
        />
      </div>

      <!-- 회귀 테스트 탭 -->
      <div v-else-if="activeTab === 'regression'">
        <RegressionTab :change-id="change.id" />
      </div>

      <!-- 이력 탭 -->
      <div v-else-if="activeTab === 'history'">
        <div v-if="change.statusHistory?.length" class="cd-history">
          <div v-for="(h, i) in change.statusHistory" :key="i" class="cd-history__item">
            <div class="cd-history__badge">{{ h.fromStatus }} → {{ h.toStatus }}</div>
            <div class="cd-history__actor">{{ h.actor }}</div>
            <div class="cd-history__time">{{ formatDate(h.at) }}</div>
            <div v-if="h.comment" class="cd-history__comment">{{ h.comment }}</div>
          </div>
        </div>
        <div v-else class="cd-empty">상태 이력이 없습니다.</div>
      </div>
    </div>

    <!-- 승인 다이얼로그 (1차/2차 공용) -->
    <div v-if="approveDialog" class="cp-overlay" @click.self="approveDialog = false">
      <div class="cp-dialog cp-dialog--sm">
        <div class="cp-dialog__header">
          {{ approveStage === 1 ? '1차 승인 — 영향도 계획 승인' : '2차 승인 — 구현 허가' }}
          <button class="cp-dialog__close" @click="approveDialog = false">✕</button>
        </div>
        <div class="cp-dialog__body">
          <p v-if="approveStage === 1" style="font-size:0.72rem;color:var(--color-text-light);margin:0 0 8px">
            승인 시 AI가 Stories/Process/Design 노드에 변경사항을 자동 반영합니다.
          </p>
          <p v-else style="font-size:0.72rem;color:var(--color-text-light);margin:0 0 8px">
            설계 반영 결과를 검토하셨습니까? 승인 후 구현(Code 탭)으로 이동합니다.
          </p>
          <label class="cp-label">코멘트 (선택)</label>
          <textarea class="cp-textarea" v-model="approveComment" rows="2" />
        </div>
        <div class="cp-dialog__footer">
          <button class="tb-btn" @click="approveDialog = false">취소</button>
          <button class="tb-btn" :style="approveStage === 1 ? 'color:#ae3ec9;border-color:#ae3ec950' : 'color:#40c057;border-color:#40c05750'"
                  :disabled="actionLoading" @click="onApprove">
            {{ approveStage === 1 ? '1차 승인' : '2차 승인 (구현 허가)' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 반려 다이얼로그 -->
    <div v-if="rejectDialog" class="cp-overlay" @click.self="rejectDialog = false">
      <div class="cp-dialog cp-dialog--sm">
        <div class="cp-dialog__header">Change 반려 <button class="cp-dialog__close" @click="rejectDialog = false">✕</button></div>
        <div class="cp-dialog__body">
          <label class="cp-label">반려 사유 *</label>
          <textarea class="cp-textarea" v-model="rejectComment" rows="2" />
        </div>
        <div class="cp-dialog__footer">
          <button class="tb-btn" @click="rejectDialog = false">취소</button>
          <button class="tb-btn tb-btn--danger" :disabled="!rejectComment.trim() || actionLoading" @click="onReject">반려</button>
        </div>
      </div>
    </div>

    <!-- Preflight 다이얼로그 -->
    <div v-if="preflightDialog" class="cp-overlay" @click.self="preflightDialog = false">
      <div class="cp-dialog">
        <div class="cp-dialog__header">선행 Change 확인 <button class="cp-dialog__close" @click="preflightDialog = false">✕</button></div>
        <div class="cp-dialog__body">
          <p>아래 선행 Change들이 미반영 상태입니다. 함께 반영하시겠습니까?</p>
          <div class="cd-prior-list">
            <div v-for="pc in preflight?.pendingPriorChanges" :key="pc.id" class="cd-prior-item">
              <span class="cd-id">{{ pc.id }}</span> {{ pc.title }}
            </div>
          </div>
        </div>
        <div class="cp-dialog__footer">
          <button class="tb-btn" @click="startImplementation([])">현재 Change만</button>
          <button class="tb-btn tb-btn--primary" @click="startImplementation(preflight?.pendingPriorChanges.map(p => p.id))">모두 함께 반영</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cd-root { display: flex; flex-direction: column; height: 100%; }

/* 2단계 승인 흐름 표시 */
.cd-flow {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
  padding: 6px 0;
  margin-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}
.cd-flow__step {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.6rem;
  color: var(--color-text-light);
  opacity: 0.4;
}
.cd-flow__step--done { opacity: 0.6; }
.cd-flow__step--done .cd-flow__dot { background: #40c057; }
.cd-flow__step--current { opacity: 1; font-weight: 700; color: var(--color-accent); }
.cd-flow__step--current .cd-flow__dot { background: var(--color-accent); box-shadow: 0 0 0 2px rgba(34,139,230,0.3); }
.cd-flow__dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--color-border);
  flex-shrink: 0;
}
.cd-flow__label { white-space: nowrap; }
.cd-flow__arrow { color: var(--color-border); font-size: 0.7rem; }

.cd-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.cd-id {
  font-family: monospace;
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--color-text-light);
}
.cd-status {
  font-size: 0.62rem;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 3px;
  border: 1px solid;
  letter-spacing: 0.02em;
}
.cd-source {
  font-size: 0.62rem;
  color: var(--color-text-light);
  background: var(--color-bg-tertiary);
  padding: 1px 5px;
  border-radius: 3px;
}
.cd-actions { margin-left: auto; display: flex; gap: 6px; }

.cd-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 4px;
}
.cd-meta {
  font-size: 0.65rem;
  color: var(--color-text-light);
  margin-bottom: 12px;
}

/* 탭 */
.cd-tabs {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 12px;
}
.cd-tab {
  padding: 5px 10px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--color-text-light);
  font-size: 0.72rem;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.cd-tab:hover { color: var(--color-text); }
.cd-tab--active { color: var(--color-accent); border-bottom-color: var(--color-accent); font-weight: 600; }

.cd-body { flex: 1; overflow-y: auto; }

.cd-section-label {
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--color-text-light);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 6px;
}
.cd-prompt {
  font-size: 0.75rem;
  color: var(--color-text);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 8px 10px;
  line-height: 1.5;
  white-space: pre-wrap;
}

/* 이력 */
.cd-history { display: flex; flex-direction: column; gap: 8px; }
.cd-history__item {
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 8px 10px;
}
.cd-history__badge {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 2px;
}
.cd-history__actor { font-size: 0.65rem; color: var(--color-accent); }
.cd-history__time { font-size: 0.62rem; color: var(--color-text-light); }
.cd-history__comment { font-size: 0.68rem; color: var(--color-text); margin-top: 4px; font-style: italic; }

.cd-empty {
  font-size: 0.72rem;
  color: var(--color-text-light);
  padding: 16px 0;
}
.cd-prior-list { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
.cd-prior-item { font-size: 0.72rem; color: var(--color-text); }

/* 공유 다이얼로그 스타일 (scoped이므로 여기 복사) */
.cp-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.cp-dialog {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  width: 440px;
  max-width: 95vw;
}
.cp-dialog--sm { width: 360px; }
.cp-dialog__header {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-text);
}
.cp-dialog__close {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  font-size: 0.9rem;
}
.cp-dialog__body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cp-dialog__body p { font-size: 0.75rem; color: var(--color-text); margin: 0; }
.cp-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
}
.cp-label { font-size: 0.7rem; color: var(--color-text-light); }
.cp-textarea {
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  color: var(--color-text);
  padding: 6px 10px;
  font-size: 0.75rem;
  resize: vertical;
  outline: none;
  min-height: 60px;
}
.cp-textarea:focus { border-color: var(--color-accent); }
</style>
