<template>
  <div class="reverse-track">
    <!-- 헤더: 제목 + 선택 요약 + 실행 -->
    <div class="rt-head">
      <div class="rt-head__title">
        <h4>{{ t('proposals.reverse.title') }}</h4>
        <p class="rt-head__sub">{{ t('proposals.reverse.pickHint') }}</p>
      </div>
      <div class="rt-head__actions">
        <span v-if="!running" class="rt-count-sel">{{ selectedCount }}/{{ groups.length }}</span>
        <button v-if="!running && groups.length" type="button" class="btn btn--ghost" @click="toggleAll">
          {{ allSelected ? t('proposals.reverse.deselectAll') : t('proposals.reverse.selectAll') }}
        </button>
        <button
          type="button"
          class="btn btn--primary"
          :disabled="running || selectedCount === 0"
          @click="run"
        >
          <span v-if="running" class="spinner spinner--sm" />
          {{ running ? (rs.phase || t('proposals.reverse.running')) : t('proposals.reverse.run') }}
        </button>
      </div>
    </div>

    <p v-if="rs.error" class="rt-error" role="alert">{{ rs.error }}</p>
    <p v-if="loadError" class="rt-error" role="alert">{{ loadError }}</p>

    <!-- 로딩 -->
    <div v-if="loading" class="rt-loading"><span class="spinner spinner--sm" /> {{ t('proposals.reverse.loadingGroups') }}</div>

    <!-- 선택 가능한 그룹 카드 목록 -->
    <ul v-else class="rt-groups" role="list">
      <li v-for="g in groups" :key="g.table" class="rt-card" :class="{ 'rt-card--off': !isSelected(g.table) && !running }">
        <label class="rt-card__head">
          <input
            type="checkbox"
            class="rt-check"
            :checked="isSelected(g.table)"
            :disabled="running"
            @change="toggle(g.table)"
          />
          <span class="rt-card__title">{{ g.title }}</span>
          <span class="rt-badge" :class="'rt-badge--' + g.kind">{{ g.kindLabel }}</span>
          <span class="rt-badge rt-badge--st">{{ g.stereotypeLabel }}</span>
          <span class="rt-card__count">{{ t('proposals.reverse.opCount', { n: g.opCount }) }}</span>
        </label>
        <ul class="rt-ops" role="list">
          <li v-for="(o, i) in g.ops" :key="i">{{ o.logicalName }}</li>
        </ul>
      </li>
    </ul>

    <!-- 실행 진행 로그 -->
    <div v-if="running && rs.logLines.length" ref="logEl" class="rt-log">
      <div v-for="(l, i) in rs.logLines" :key="i" class="rt-log__line">{{ l }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch, nextTick } from 'vue'
import { useI18n } from '../../../app/i18n'
import { useProposalsStore } from '../proposals.store'

const props = defineProps({ proposalId: { type: String, required: true } })
const { t } = useI18n()
const store = useProposalsStore()

const rs = computed(() => store.reverseStream)
const running = computed(() => rs.value.active)
const groups = ref([])
const selected = ref(new Set())
const loading = ref(true)
const loadError = ref('')
const logEl = ref(null)

onMounted(async () => {
  try {
    groups.value = await store.fetchReverseGroups(props.proposalId)
    selected.value = new Set(groups.value.map(g => g.table)) // 기본값 = 전체 선택
  } catch (e) {
    loadError.value = t('proposals.reverse.loadFail')
  } finally {
    loading.value = false
  }
})

const selectedCount = computed(() => selected.value.size)
const allSelected = computed(() => groups.value.length > 0 && selected.value.size === groups.value.length)
function isSelected(table) { return selected.value.has(table) }
function toggle(table) {
  const s = new Set(selected.value)
  s.has(table) ? s.delete(table) : s.add(table)
  selected.value = s
}
function toggleAll() {
  selected.value = allSelected.value ? new Set() : new Set(groups.value.map(g => g.table))
}
function run() {
  if (!selectedCount.value) return
  store.subscribeToReverseIntent(props.proposalId, [...selected.value])
}

watch(() => rs.value.logLines?.length, async () => {
  await nextTick()
  if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight
})
</script>

<style scoped>
.reverse-track { padding: 12px; }

/* 헤더 */
.rt-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.rt-head__title h4 { margin: 0; font-size: 14px; font-weight: 600; color: var(--color-text-bright); }
.rt-head__sub { margin: 2px 0 0; font-size: 12px; color: var(--color-text-light); }
.rt-head__actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.rt-count-sel { font-size: 12px; color: var(--color-text-light); font-variant-numeric: tabular-nums; }

.btn { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }
.btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--primary:disabled { opacity: 0.5; cursor: default; }
.btn--ghost { background: transparent; border: 1px solid var(--color-border); color: var(--color-text); }
.btn--ghost:hover { background: var(--color-bg-tertiary); }

.rt-error { color: var(--color-danger); font-size: 13px; margin: 6px 0; }
.rt-loading { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--color-text-light); padding: 8px 0; }

.spinner { width: 16px; height: 16px; border: 2px solid var(--color-border); border-top-color: var(--color-accent); border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0; }
.spinner--sm { width: 12px; height: 12px; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spinner { animation-duration: 2s; } }

/* 그룹 카드 목록 */
.rt-groups { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.rt-card { border: 1px solid var(--color-border); border-radius: 8px; padding: 10px 12px; background: var(--color-bg-secondary); transition: opacity 0.15s, border-color 0.15s; }
.rt-card--off { opacity: 0.5; }

/* ★고정 그리드 정렬(지그재그 0): [체크박스] [제목] [배지..] [작업수] — 모든 행 동일 트랙 */
.rt-card__head { display: grid; grid-template-columns: auto 1fr auto auto auto; align-items: center; gap: 8px; cursor: pointer; }
.rt-check { width: 15px; height: 15px; accent-color: var(--color-accent); cursor: pointer; margin: 0; }
.rt-check:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
.rt-card__title { font-size: 13px; font-weight: 600; color: var(--color-text-bright); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rt-card__count { font-size: 11px; color: var(--color-text-light); font-variant-numeric: tabular-nums; white-space: nowrap; }

.rt-badge { font-size: 10px; padding: 1px 8px; border-radius: 10px; white-space: nowrap; }
.rt-badge--write { background: var(--status-blue-bg); color: var(--status-blue-fg); }
.rt-badge--read { background: var(--color-bg-tertiary); color: var(--color-text); }
.rt-badge--logic { background: var(--color-bg-tertiary); color: var(--color-text-light); }
.rt-badge--st { background: transparent; border: 1px solid var(--color-border); color: var(--color-text-light); }

.rt-ops { list-style: disc; margin: 8px 0 0; padding-left: 30px; }
.rt-ops li { font-size: 12px; color: var(--color-text); line-height: 1.55; }

.rt-log { background: #0f172a; border-radius: 6px; padding: 10px 12px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 11px; color: #cbd5e1; margin-top: 12px; }
.rt-log__line { padding: 1px 0; white-space: pre-wrap; word-break: break-all; }
</style>
