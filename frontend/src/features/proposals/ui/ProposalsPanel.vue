<template>
  <div class="proposals-panel">
    <!-- Toolbar -->
    <div class="panel-toolbar">
      <h3 class="panel-toolbar__title">Proposals</h3>
      <button @click="showCreate = true" class="btn btn--primary btn--sm">+ 새 Proposal</button>
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
        <div v-if="store.loading" class="list-loading">로딩 중...</div>
        <div v-else-if="!filteredProposals.length" class="list-empty">Proposal이 없습니다</div>
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
          </div>
          <div class="proposal-item__title">{{ p.title }}</div>
          <div class="proposal-item__meta">
            <span>{{ p.author }}</span>
            <span>{{ formatDate(p.createdAt) }}</span>
            <span v-if="p.impactMap">{{ p.impactMap.length || 0 }}개 영향</span>
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
          Proposal을 선택하면 상세가 표시됩니다
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useProposalsStore } from '../proposals.store'
import ProposalDetail from './ProposalDetail.vue'
import ProposalCreate from './ProposalCreate.vue'

const store = useProposalsStore()
const filterStatus = ref('')
const selectedId = ref(null)
const showCreate = ref(false)

// 활성(IMPLEMENTING/TESTING) Proposal의 tasks.md 진행 상태를 가볍게 폴링해
// "진행 중 vs 정체(임계 초과)"를 구분한다(정체면 스피너를 숨김).
const STALE_SECONDS = 90
const progressById = ref({})

const statusOptions = [
  { value: '', label: '전체' },
  { value: 'DRAFT', label: 'DRAFT' },
  { value: 'SUBMITTED', label: 'SUBMITTED' },
  { value: 'IMPLEMENTING', label: 'IMPLEMENTING' },
  { value: 'TESTING', label: 'TESTING' },
  { value: 'PENDING_ACCEPTANCE', label: '승인 대기' },
  { value: 'ACCEPTED', label: 'ACCEPTED' },
  { value: 'DESTROYED', label: 'DESTROYED' },
]

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
    if (stale) out[p.id] = { label: '정체', spinner: false, tone: 'stale' }
    else if (allDone) out[p.id] = { label: '완료', spinner: false, tone: 'done' }
    else out[p.id] = { label: '진행 중', spinner: true, tone: 'running' }
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
    PENDING_ACCEPTANCE: '승인 대기',
    MERGE_FAILED: 'Merge 실패',
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
.proposal-item__id { font-family: monospace; font-size: 11px; color: var(--color-text-light); }
.proposal-item__title { font-weight: 500; font-size: 12px; color: var(--color-text-bright); margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.proposal-item__meta { display: flex; gap: 8px; font-size: 11px; color: var(--color-text-light); flex-wrap: wrap; }
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
</style>
