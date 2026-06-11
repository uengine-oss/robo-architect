<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'
import ChangeDetail from './ChangeDetail.vue'

const store = useRequirementsStore()
const selectedChange = ref(null)
const showCreateDialog = ref(false)
const deleteConfirmId = ref(null)
const filterStatus = ref('')
const createForm = ref({ originalPrompt: '', sourceType: 'PROMPT' })
const createLoading = ref(false)
const autoAnalyzeChangeId = ref(null) // 생성 직후 자동 분석할 CHG id

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
  PLAN_APPROVED: '계획 승인',
  DESIGN_APPLIED: '설계 반영',
  APPROVED: '구현 승인',
  REJECTED: '반려됨',
  IMPLEMENTED: '구현 완료',
}

const statuses = ['', 'DRAFT', 'SUBMITTED', 'PLAN_APPROVED', 'DESIGN_APPLIED', 'APPROVED', 'REJECTED', 'IMPLEMENTED']

const filteredChanges = computed(() =>
  filterStatus.value
    ? store.changes.filter(c => c.status === filterStatus.value)
    : store.changes
)

onMounted(() => store.fetchChanges())

async function onSelectChange(chg) {
  selectedChange.value = await store.fetchChangeById(chg.id)
}

async function onDelete(id) {
  try {
    await store.deleteChange(id)
    if (selectedChange.value?.id === id) selectedChange.value = null
  } catch (e) {
    alert(e.message)
  }
  deleteConfirmId.value = null
}

async function onCreateChange() {
  if (!createForm.value.originalPrompt.trim()) return
  createLoading.value = true
  try {
    const created = await store.createChange({ ...createForm.value })
    showCreateDialog.value = false
    createForm.value = { originalPrompt: '', sourceType: 'PROMPT' }
    // 생성된 Change 자동 선택 → 영향도 분석 진행 상황 바로 표시
    selectedChange.value = created
    // 영향도 탭으로 자동 포커스 (ChangeDetail에 이벤트로 알림)
    autoAnalyzeChangeId.value = created.id
  } finally {
    createLoading.value = false
  }
}

function onChangeUpdated(updated) {
  selectedChange.value = updated
  store.fetchChanges()
}
</script>

<template>
  <div class="cp-root">
    <!-- 좌: 목록 -->
    <div class="cp-list">
      <div class="cp-list__header">
        <span class="cp-list__title">Changes</span>
        <button class="tb-btn tb-btn--primary cp-add-btn" @click="showCreateDialog = true">+ 추가 Change</button>
      </div>

      <div class="cp-filter">
        <select class="cp-select" v-model="filterStatus">
          <option value="">전체 상태</option>
          <option v-for="s in statuses.slice(1)" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>

      <div v-if="store.changesLoading" class="cp-loading">불러오는 중...</div>

      <div class="cp-items" v-if="filteredChanges.length">
        <div
          v-for="chg in filteredChanges"
          :key="chg.id"
          class="cp-item"
          :class="{ 'cp-item--active': selectedChange?.id === chg.id }"
          @click="onSelectChange(chg)"
        >
          <div class="cp-item__top">
            <span class="cp-item__id">{{ chg.id }}</span>
            <span class="cp-item__status" :style="{ background: STATUS_COLORS[chg.status] + '22', color: STATUS_COLORS[chg.status], borderColor: STATUS_COLORS[chg.status] + '55' }">{{ STATUS_LABELS[chg.status] || chg.status }}</span>
            <button class="cp-item__del" @click.stop="deleteConfirmId = chg.id" title="삭제">✕</button>
          </div>
          <div class="cp-item__title">{{ chg.title }}</div>
          <div class="cp-item__author">{{ chg.author }}</div>
        </div>
      </div>
      <div v-else-if="!store.changesLoading" class="cp-empty">Change가 없습니다.</div>
    </div>

    <!-- 우: 상세 -->
    <div class="cp-detail" v-if="selectedChange">
      <ChangeDetail
        :change="selectedChange"
        :auto-analyze="autoAnalyzeChangeId === selectedChange.id"
        @updated="onChangeUpdated"
        @deleted="onDelete"
        @analyzed="autoAnalyzeChangeId = null"
      />
    </div>
    <div v-else class="cp-detail cp-detail--empty">
      <span>Change를 선택하면 상세 정보가 표시됩니다.</span>
    </div>

    <!-- 추가 Change 다이얼로그 -->
    <div v-if="showCreateDialog" class="cp-overlay" @click.self="showCreateDialog = false">
      <div class="cp-dialog">
        <div class="cp-dialog__header">
          <span>추가 Change</span>
          <button class="cp-dialog__close" @click="showCreateDialog = false">✕</button>
        </div>
        <div class="cp-dialog__body">
          <label class="cp-label">변경 내용 설명 <span style="color:var(--color-text-light);font-size:0.62rem">(제목은 AI가 자동 추출)</span></label>
          <textarea
            class="cp-textarea"
            v-model="createForm.originalPrompt"
            placeholder="요구사항 변경 내용을 자연어로 설명하세요.
예: 결제 완료 후 영수증 이메일 자동 발송 기능을 추가해야 합니다."
            rows="5"
            autofocus
          />
          <div v-if="createForm.originalPrompt.trim()" class="cp-hint">
            ✓ 생성 즉시 Stories / Processes / Design 영향도 분석이 자동 실행됩니다.
          </div>
        </div>
        <div class="cp-dialog__footer">
          <button class="tb-btn" @click="showCreateDialog = false">취소</button>
          <button class="tb-btn tb-btn--primary"
            :disabled="!createForm.originalPrompt.trim() || createLoading"
            @click="onCreateChange">
            {{ createLoading ? '생성 중...' : '생성 + 분석 시작' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 삭제 확인 -->
    <div v-if="deleteConfirmId" class="cp-overlay" @click.self="deleteConfirmId = null">
      <div class="cp-dialog cp-dialog--sm">
        <div class="cp-dialog__header">
          <span>Change 삭제</span>
          <button class="cp-dialog__close" @click="deleteConfirmId = null">✕</button>
        </div>
        <div class="cp-dialog__body">
          <p>삭제하면 EFFECT 관계도 함께 제거됩니다. 계속하시겠습니까?</p>
        </div>
        <div class="cp-dialog__footer">
          <button class="tb-btn" @click="deleteConfirmId = null">취소</button>
          <button class="tb-btn tb-btn--danger" @click="onDelete(deleteConfirmId)">삭제</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cp-root {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* 좌측 목록 */
.cp-list {
  width: 320px;
  min-width: 260px;
  flex-shrink: 0;
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.cp-list__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}
.cp-list__title {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-text);
  flex: 1;
}
.cp-add-btn {
  font-size: 0.7rem;
  padding: 3px 8px;
}
.cp-filter {
  padding: 6px 12px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}
.cp-select {
  width: 100%;
  padding: 4px 8px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  color: var(--color-text);
  font-size: 0.72rem;
}
.cp-loading {
  padding: 12px;
  font-size: 0.72rem;
  color: var(--color-text-light);
}
.cp-items {
  overflow-y: auto;
  flex: 1;
}
.cp-item {
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  transition: background 0.15s;
}
.cp-item:hover { background: var(--color-bg-tertiary); }
.cp-item--active { background: rgba(34, 139, 230, 0.12); }
.cp-item__top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 3px;
}
.cp-item__id {
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--color-text-light);
  font-family: monospace;
}
.cp-item__status {
  font-size: 0.62rem;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 3px;
  border: 1px solid;
  letter-spacing: 0.02em;
}
.cp-item__del {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  font-size: 0.7rem;
  padding: 2px 4px;
  border-radius: 3px;
  opacity: 0;
  transition: opacity 0.15s;
}
.cp-item:hover .cp-item__del { opacity: 1; }
.cp-item__del:hover { background: rgba(250, 82, 82, 0.2); color: #fa5252; }
.cp-item__title {
  font-size: 0.73rem;
  font-weight: 500;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cp-item__author {
  font-size: 0.65rem;
  color: var(--color-text-light);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}
.cp-empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 0.72rem;
  color: var(--color-text-light);
}

/* 우측 상세 */
.cp-detail {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.cp-detail--empty {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  color: var(--color-text-light);
}

/* 다이얼로그 */
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
  overflow: hidden;
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
  padding: 2px 4px;
}
.cp-dialog__body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cp-dialog__body p {
  font-size: 0.75rem;
  color: var(--color-text);
  margin: 0;
}
.cp-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
}
.cp-label {
  font-size: 0.7rem;
  color: var(--color-text-light);
  margin-bottom: 2px;
}
.cp-input, .cp-textarea {
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  color: var(--color-text);
  padding: 6px 10px;
  font-size: 0.75rem;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;
}
.cp-input:focus, .cp-textarea:focus {
  border-color: var(--color-accent);
}
.cp-textarea { min-height: 80px; }
.cp-hint {
  font-size: 0.68rem;
  color: #40c057;
  padding: 4px 6px;
  background: rgba(64,192,87,0.08);
  border: 1px solid rgba(64,192,87,0.2);
  border-radius: 4px;
}
</style>
