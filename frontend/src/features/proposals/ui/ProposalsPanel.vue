<template>
  <div class="proposals-panel">
    <!-- Toolbar -->
    <div class="panel-toolbar">
      <h3 class="panel-toolbar__title">Proposals</h3>
      <button @click="showCreate = true" class="btn btn--primary btn--sm">{{ t('proposals.panel.newProposal') }}</button>
    </div>

    <!-- Status filter tabs -->
    <div class="status-tabs">
      <button
        v-for="s in statusOptions"
        :key="s.value"
        @click="filterStatus = s.value"
        :class="['status-tab', filterStatus === s.value ? 'status-tab--active' : '']"
      >
        {{ s.label }}
        <span v-if="s.value" class="count-badge">{{ countByStatus(s.value) }}</span>
      </button>
    </div>

    <!-- List + Detail split -->
    <div class="panel-body">
      <!-- List -->
      <div class="proposal-list">
        <div v-if="store.loading" class="list-loading">{{ t('proposals.common.loading') }}</div>
        <div v-else-if="!filteredProposals.length" class="list-empty">{{ t('proposals.panel.empty') }}</div>
        <div
          v-for="p in filteredProposals"
          :key="p.id"
          @click="selectProposal(p)"
          :class="['proposal-item', selectedId === p.id ? 'proposal-item--active' : '']"
        >
          <div class="proposal-item__header">
            <span class="proposal-item__id">{{ p.id }}</span>
            <span :class="['status-badge', `status-badge--${p.status.toLowerCase()}`]">
              {{ statusLabel(p.status) }}
            </span>
            <button
              class="proposal-item__delete"
              :title="t('proposals.panel.deleteTitle')"
              :aria-label="t('proposals.panel.deleteAria')"
              @click.stop="askDelete(p)"
            >🗑</button>
          </div>
          <div class="proposal-item__title">{{ p.title }}</div>
          <div class="proposal-item__meta">
            <span>{{ p.author }}</span>
            <span>{{ formatDate(p.createdAt) }}</span>
            <span v-if="p.impactMap">{{ t('proposals.panel.impactCount', { n: p.impactMap.length || 0 }) }}</span>
            <span v-if="legacyReferenceCount(p.legacyReferences)" class="proposal-item__legacy">
              ⛓{{ legacyReferenceCount(p.legacyReferences) }}
            </span>
            <span
              v-if="activityById[p.id]"
              :class="['active-indicator', `active-indicator--${activityById[p.id].tone}`]"
            >
              <span v-if="activityById[p.id].spinner" class="spinner" />{{ activityById[p.id].label }}
            </span>
          </div>
        </div>
      </div>

      <!-- Detail pane -->
      <div class="proposal-detail-pane">
        <ProposalCreate
          v-if="showCreate"
          @created="onCreated"
          @cancel="showCreate = false"
        />
        <ProposalDetail
          v-else-if="selectedId"
          :proposalId="selectedId"
        />
        <div v-else class="detail-empty">
          {{ t('proposals.panel.selectHint') }}
        </div>
      </div>
    </div>

    <!-- 삭제 확인 — Proposal id 를 그대로 입력해야 확정된다 -->
    <div v-if="deleteTarget" class="overlay" @click.self="cancelDelete">
      <div class="dialog">
        <h4>{{ t('proposals.panel.deleteConfirmTitle') }}</h4>
        <p class="dialog__note">{{ t('proposals.panel.deleteConfirmNote', { id: deleteTarget.id }) }}</p>
        <input
          v-model="deleteConfirmText"
          class="dialog__input"
          :placeholder="t('proposals.panel.deleteInputPlaceholder')"
          autofocus
          @keyup.enter="deleteConfirmText === deleteTarget.id && confirmDelete()"
        />
        <p v-if="deleteError" class="error-msg">{{ deleteError }}</p>
        <div class="dialog__actions">
          <button @click="cancelDelete" class="btn btn--secondary" :disabled="deleting">{{ t('proposals.common.cancel') }}</button>
          <button
            @click="confirmDelete"
            :disabled="deleting || deleteConfirmText !== deleteTarget.id"
            class="btn btn--danger"
          >{{ deleting ? t('proposals.panel.deleting') : t('proposals.panel.deleteConfirm') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useProposalsStore } from '../proposals.store'
import { useI18n } from '../../../app/i18n'
import ProposalDetail from './ProposalDetail.vue'
import ProposalCreate from './ProposalCreate.vue'
import { legacyReferenceCount } from '../legacy-reference'

const { t } = useI18n()

const store = useProposalsStore()
const filterStatus = ref('')
const selectedId = ref(null)
const showCreate = ref(false)

// 삭제 확인 다이얼로그 — id 를 입력받아 일치할 때만 영구 삭제한다.
const deleteTarget = ref(null)
const deleteConfirmText = ref('')
const deleting = ref(false)
const deleteError = ref(null)

function askDelete(p) {
  deleteTarget.value = p
  deleteConfirmText.value = ''
  deleteError.value = null
}

function cancelDelete() {
  if (deleting.value) return
  deleteTarget.value = null
  deleteConfirmText.value = ''
  deleteError.value = null
}

async function confirmDelete() {
  if (!deleteTarget.value || deleteConfirmText.value !== deleteTarget.value.id) return
  deleting.value = true
  deleteError.value = null
  try {
    const id = deleteTarget.value.id
    await store.deleteProposal(id, deleteConfirmText.value)
    if (selectedId.value === id) selectedId.value = null
    deleteTarget.value = null
    deleteConfirmText.value = ''
  } catch (e) {
    deleteError.value = e.message
  } finally {
    deleting.value = false
  }
}

// 활성(IMPLEMENTING/TESTING) Proposal의 tasks.md 진행 상태를 가볍게 폴링해
// "진행 중 vs 정체(임계 초과)"를 구분한다(정체면 스피너를 숨김).
const STALE_SECONDS = 90
const progressById = ref({})

const statusOptions = computed(() => [
  { value: '', label: t('proposals.panel.statusAll') },
  // 042 — 라이프사이클 라벨: DRAFT=Intent 단계, SUBMITTED=Plan 단계, TESTING=Validating.
  { value: 'DRAFT', label: statusLabel('DRAFT') },
  { value: 'SUBMITTED', label: statusLabel('SUBMITTED') },
  { value: 'IMPLEMENTING', label: 'IMPLEMENTING' },
  { value: 'TESTING', label: statusLabel('TESTING') },
  { value: 'PENDING_ACCEPTANCE', label: t('proposals.panel.statusPendingAcceptance') },
  { value: 'ACCEPTED', label: 'ACCEPTED' },
  { value: 'DESTROYED', label: 'DESTROYED' },
])

const filteredProposals = computed(() =>
  filterStatus.value
    ? store.proposals.filter(p => p.status === filterStatus.value)
    : store.proposals
)

function countByStatus(status) {
  return store.proposals.filter(p => p.status === status).length
}

function isActive(status) {
  return status === 'IMPLEMENTING' || status === 'TESTING'
}

// 활성 아이템별 진행 표시: 진행 중(스피너) / 정체(스피너 없음) / 완료.
const activityById = computed(() => {
  const out = {}
  for (const p of store.proposals) {
    if (!isActive(p.status)) continue
    const pr = progressById.value[p.id]
    const allDone = pr && pr.total > 0 && pr.done >= pr.total
    const stale = pr && pr.exists && pr.secondsSinceUpdate != null
      && pr.secondsSinceUpdate > STALE_SECONDS && !allDone
    if (stale) out[p.id] = { label: t('proposals.panel.activityStale'), spinner: false, tone: 'stale' }
    else if (allDone) out[p.id] = { label: t('proposals.panel.activityDone'), spinner: false, tone: 'done' }
    else out[p.id] = { label: t('proposals.panel.activityRunning'), spinner: true, tone: 'running' }
  }
  return out
})

let _pollTimer = null
async function pollActiveProgress() {
  const active = store.proposals.filter((p) => isActive(p.status))
  await Promise.all(active.map(async (p) => {
    try {
      const pr = await store.fetchProgress(p.id)
      progressById.value = { ...progressById.value, [p.id]: pr }
    } catch { /* 폴링 — 일시 오류 무시 */ }
  }))
}

function statusLabel(status) {
  const map = {
    // 042 — 라이프사이클 라벨: 코드(DRAFT/SUBMITTED/TESTING)는 유지, 표시만 단계명으로.
    DRAFT: t('proposals.panel.statusDraft'),
    SUBMITTED: t('proposals.panel.statusSubmitted'),
    TESTING: t('proposals.panel.statusTesting'),
    PENDING_ACCEPTANCE: t('proposals.panel.statusPendingAcceptance'),
    MERGE_FAILED: t('proposals.panel.statusMergeFailed'),
  }
  return map[status] || status
}

function formatDate(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleDateString('ko-KR')
}

async function selectProposal(p) {
  showCreate.value = false
  selectedId.value = p.id
  await store.fetchProposal(p.id)
}

function onCreated(id) {
  showCreate.value = false
  selectedId.value = id
  store.fetchProposals()
}

onMounted(async () => {
  await store.fetchProposals()
  pollActiveProgress()
  _pollTimer = setInterval(pollActiveProgress, 8000)
})
onUnmounted(() => { if (_pollTimer) clearInterval(_pollTimer) })
</script>

<style scoped>
.proposals-panel { display: flex; flex-direction: column; height: 100%; font-size: 13px; }
.panel-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--color-border); }
.panel-toolbar__title { font-size: 15px; font-weight: 600; margin: 0; color: var(--color-text-bright); }
.btn { padding: 5px 12px; border-radius: 4px; border: none; cursor: pointer; font-size: 12px; }
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--sm { padding: 4px 10px; }
.status-tabs { display: flex; overflow-x: auto; padding: 6px 14px; gap: 4px; border-bottom: 1px solid var(--color-border); }
.status-tab { background: none; border: 1px solid transparent; border-radius: 14px; padding: 3px 10px; font-size: 11px; cursor: pointer; color: var(--color-text-light); white-space: nowrap; display: flex; align-items: center; gap: 4px; }
.status-tab--active { background: var(--status-blue-bg); color: var(--status-blue-fg); border-color: transparent; }
.count-badge { background: var(--status-neutral-bg); color: var(--status-neutral-fg); border-radius: 9999px; padding: 0 5px; font-size: 10px; }
.panel-body { display: flex; flex: 1; overflow: hidden; }
.proposal-list { width: 280px; min-width: 220px; overflow-y: auto; border-right: 1px solid var(--color-border); }
.list-loading, .list-empty { color: var(--color-text-light); padding: 16px; font-size: 12px; }
.proposal-item { padding: 10px 14px; border-bottom: 1px solid var(--color-border); cursor: pointer; transition: background 0.1s; }
.proposal-item:hover { background: var(--color-bg-secondary); }
.proposal-item--active { background: var(--ccw-active); }
.proposal-item__header { display: flex; align-items: center; gap: 6px; margin-bottom: 2px; }
.proposal-item__delete { margin-left: auto; background: none; border: none; cursor: pointer; font-size: 12px; padding: 2px 4px; border-radius: 4px; opacity: 0; transition: opacity 0.1s, background 0.1s; line-height: 1; }
.proposal-item:hover .proposal-item__delete { opacity: 0.55; }
.proposal-item__delete:hover { opacity: 1; background: var(--status-red-bg); }
.proposal-item__id { font-family: monospace; font-size: 11px; color: var(--color-text-light); }
.proposal-item__title { font-weight: 500; font-size: 12px; color: var(--color-text-bright); margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.proposal-item__meta { display: flex; gap: 8px; font-size: 11px; color: var(--color-text-light); flex-wrap: wrap; }
.proposal-item__legacy { color: #7d8bf5; font-weight: 700; }
.status-badge { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 9999px; }
.status-badge--draft { background: var(--status-neutral-bg); color: var(--status-neutral-fg); }
.status-badge--submitted { background: var(--status-blue-bg); color: var(--status-blue-fg); }
.status-badge--implementing { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.status-badge--testing { background: var(--status-orange-bg); color: var(--status-orange-fg); }
.status-badge--pending_acceptance { background: var(--status-purple-bg); color: var(--status-purple-fg); }
.status-badge--accepted { background: var(--status-green-bg); color: var(--status-green-fg); }
.status-badge--destroyed { background: var(--status-red-bg); color: var(--status-red-fg); }
.status-badge--merge_failed { background: var(--status-red-bg); color: var(--status-red-fg); }
.active-indicator { display: flex; align-items: center; gap: 4px; color: var(--color-warning); }
.active-indicator--stale { color: var(--status-red-fg, #c0392b); }
.active-indicator--done { color: var(--status-green-fg, #2e7d32); }
.spinner { width: 10px; height: 10px; border: 1.5px solid var(--color-border); border-top-color: var(--color-warning); border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }
.proposal-detail-pane { flex: 1; overflow-y: auto; }
.detail-empty { display: flex; height: 100%; align-items: center; justify-content: center; color: var(--color-text-light); font-size: 13px; }
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.dialog { background: var(--color-bg, #fff); border: 1px solid var(--color-border); border-radius: 8px; padding: 20px; width: 360px; max-width: 90vw; box-shadow: 0 8px 32px rgba(0,0,0,0.25); }
.dialog h4 { margin: 0 0 8px; font-size: 14px; color: var(--color-text-bright); }
.dialog__note { font-size: 12px; color: var(--color-text-light); margin: 0 0 12px; line-height: 1.5; }
.dialog__input { width: 100%; box-sizing: border-box; padding: 7px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-family: monospace; font-size: 12px; background: var(--color-bg-secondary); color: var(--color-text-bright); }
.dialog__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.btn--secondary { background: var(--color-bg-secondary); color: var(--color-text); border: 1px solid var(--color-border); }
.btn--danger { background: var(--color-danger, #c0392b); color: #fff; }
.btn--danger:disabled { opacity: 0.5; cursor: not-allowed; }
.error-msg { color: var(--status-red-fg, #c0392b); font-size: 12px; margin: 8px 0 0; }
</style>
