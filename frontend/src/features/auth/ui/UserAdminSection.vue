<script setup>
/**
 * 사용자 승인·역할 관리. 관리자에게만 보인다.
 *
 * 화면에서 숨기는 것만으로는 막히지 않는다 — 서버가 403 을 낸다. 여기서 숨기는
 * 것은 관리자가 아닌 사람에게 쓸모없는 자리를 보여 주지 않기 위해서다.
 *
 * 자기 계정은 바꿀 수 없다. 자기 승격과, 마지막 관리자가 스스로를 내려 아무도
 * 승인할 수 없게 되는 길을 함께 막는다 — 서버도 같은 이유로 403 을 낸다.
 */
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../auth.store.js'

const auth = useAuthStore()
const users = ref([])
const counts = ref({})
const approvalRequired = ref(false)
const filter = ref('pending')
const loading = ref(false)
const error = ref('')

const FILTERS = [
  { key: 'pending', label: '승인 대기' },
  { key: 'approved', label: '사용 중' },
  { key: 'rejected', label: '거절됨' },
  { key: '', label: '전체' },
]

const shown = computed(() =>
  filter.value ? users.value.filter(u => (u.status || 'approved') === filter.value) : users.value,
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await fetch('/api/accounts')
    if (!r.ok) throw new Error(r.status === 403 ? '관리자만 볼 수 있습니다.' : `조회 실패 (${r.status})`)
    const body = await r.json()
    users.value = body.users || []
    counts.value = body.counts || {}
    approvalRequired.value = !!body.approvalRequired
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function change(uid, path, payload) {
  error.value = ''
  try {
    const r = await fetch(`/api/accounts/${encodeURIComponent(uid)}/${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!r.ok) {
      const b = await r.json().catch(() => ({}))
      throw new Error(b.detail || `변경 실패 (${r.status})`)
    }
    await load()
  } catch (e) {
    error.value = e.message
  }
}

const isSelf = (uid) => uid === (auth.user || {}).uid

onMounted(load)
</script>

<template>
  <div class="settings-section">
    <div class="settings-section__header">
      <h3 class="settings-section__title">사용자 관리</h3>
      <span class="settings-section__description">
        승인 대기 {{ counts.pending || 0 }}명 · 사용 중 {{ counts.approved || 0 }}명
        <template v-if="!approvalRequired"> — 승인제가 꺼져 있어 새 사용자가 바로 들어옵니다</template>
      </span>
    </div>

    <div class="ua">
      <div class="ua__tabs">
        <button v-for="f in FILTERS" :key="f.key" class="ua__tab"
                :class="{ 'ua__tab--on': filter === f.key }" @click="filter = f.key">
          {{ f.label }}
        </button>
        <button class="ua__refresh" :disabled="loading" @click="load">새로고침</button>
      </div>

      <p v-if="error" class="ua__error">{{ error }}</p>
      <p v-else-if="loading" class="ua__empty">불러오는 중…</p>
      <p v-else-if="!shown.length" class="ua__empty">해당하는 사용자가 없습니다.</p>

      <table v-else class="ua__table">
        <thead>
          <tr><th>사번</th><th>이름</th><th>부서</th><th>상태</th><th>역할</th><th class="ua__r">처리</th></tr>
        </thead>
        <tbody>
          <tr v-for="u in shown" :key="u.uid">
            <td class="ua__b">{{ u.uid }}</td>
            <td>{{ u.displayName || '-' }}</td>
            <td>{{ u.department || '-' }}</td>
            <td><span class="ua__badge" :class="`ua__badge--${u.status || 'approved'}`">
              {{ u.status || 'approved' }}</span></td>
            <td>{{ u.role || 'member' }}</td>
            <td class="ua__r">
              <template v-if="isSelf(u.uid)">
                <span class="ua__self">본인</span>
              </template>
              <template v-else>
                <button v-if="(u.status || 'approved') !== 'approved'" class="ua__act"
                        @click="change(u.uid, 'status', { status: 'approved' })">승인</button>
                <button v-if="(u.status || 'approved') !== 'rejected'" class="ua__act ua__act--warn"
                        @click="change(u.uid, 'status', { status: 'rejected' })">거절</button>
                <button v-if="(u.role || 'member') !== 'admin'" class="ua__act"
                        @click="change(u.uid, 'role', { role: 'admin' })">관리자로</button>
                <button v-else class="ua__act"
                        @click="change(u.uid, 'role', { role: 'member' })">관리자 해제</button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.ua { margin-top:10px; }
.ua__tabs { display:flex; gap:6px; align-items:center; margin-bottom:10px; }
.ua__tab { padding:4px 10px; border:1px solid #dee2e6; border-radius:14px; background:#fff;
  font-size:12px; color:#495057; cursor:pointer; }
.ua__tab--on { background:#228be6; border-color:#228be6; color:#fff; }
.ua__refresh { margin-left:auto; padding:4px 10px; border:1px solid #dee2e6; border-radius:6px;
  background:#fff; font-size:12px; color:#868e96; cursor:pointer; }
.ua__table { width:100%; border-collapse:collapse; font-size:12.5px; }
.ua__table th { text-align:left; padding:6px 8px; background:#f1f3f5; color:#495057;
  font-weight:600; border-bottom:1px solid #dee2e6; }
.ua__table td { padding:6px 8px; border-bottom:1px solid #f1f3f5; color:#343a40; }
.ua__b { font-weight:600; }
.ua__r { text-align:right; white-space:nowrap; }
.ua__act { margin-left:4px; padding:3px 8px; border:1px solid #ced4da; border-radius:5px;
  background:#fff; font-size:11.5px; color:#343a40; cursor:pointer; }
.ua__act--warn { color:#c92a2a; border-color:#ffc9c9; }
.ua__self { font-size:11.5px; color:#adb5bd; }
.ua__badge { padding:1px 7px; border-radius:10px; font-size:11px; }
.ua__badge--approved { background:#d3f9d8; color:#2b8a3e; }
.ua__badge--pending { background:#fff3bf; color:#e67700; }
.ua__badge--rejected { background:#ffe3e3; color:#c92a2a; }
.ua__empty, .ua__error { font-size:12.5px; color:#868e96; padding:10px 2px; }
.ua__error { color:#c92a2a; }
</style>
