<script setup>
/**
 * 020: Summary row for one :SyncRun in the FigmaBindingModal History tab.
 * Format: "YYYY-MM-DD HH:MM — 전체 동기화: 페이지 X건 / 프레임 Y건 성공[, Z건 실패]"
 * Special-case "변경 없음" when all summary counters are zero.
 */
import { computed } from 'vue'

const props = defineProps({
  run: { type: Object, required: true },
})

const summary = computed(() => props.run.summary || {})

const noChanges = computed(() => {
  const s = summary.value
  return (
    (s.pagesCreated || 0) === 0
    && (s.framesPushed || 0) === 0
    && (s.generated || 0) === 0
    && (s.overwrites || 0) === 0
    && (s.failures || 0) === 0
  )
})

const kindLabel = computed(() =>
  props.run.kind === 'manual-retry' ? '전체 다시 시도' : '전체 동기화'
)

function fmtTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    const yyyy = d.getFullYear()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const mi = String(d.getMinutes()).padStart(2, '0')
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
  } catch {
    return iso
  }
}

const statusClass = computed(() => `hsr__status--${props.run.status || 'unknown'}`)
const statusLabel = computed(() => {
  switch (props.run.status) {
    case 'succeeded': return '성공'
    case 'partially-succeeded': return '일부 성공'
    case 'cancelled': return '취소됨'
    case 'aborted-binding-unreachable': return '중단됨'
    case 'running': return '진행 중'
    default: return ''
  }
})
</script>

<template>
  <div class="hsr">
    <span class="hsr__time">{{ fmtTime(run.startedAt) }}</span>
    <span class="hsr__kind">{{ kindLabel }}:</span>
    <span class="hsr__body">
      <template v-if="noChanges">변경 없음</template>
      <template v-else>
        페이지 {{ summary.pagesCreated || 0 }}건 / 프레임 {{ summary.framesPushed || 0 }}건 성공<span
          v-if="summary.failures">, {{ summary.failures }}건 실패</span>
      </template>
    </span>
    <span v-if="statusLabel" class="hsr__status" :class="statusClass">{{ statusLabel }}</span>
  </div>
</template>

<style scoped>
.hsr { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 0.76rem; border-bottom: 1px solid var(--color-border-soft, #1f2230); }
.hsr__time { color: var(--color-text-light, #aaa); white-space: nowrap; }
.hsr__kind { font-weight: 500; }
.hsr__body { flex: 1; }
.hsr__status { font-size: 0.7rem; padding: 1px 6px; border-radius: 999px; }
.hsr__status--succeeded { background: rgba(10,207,131,0.15); color: #0acf83; }
.hsr__status--partially-succeeded { background: rgba(216,164,14,0.15); color: #d8a40e; }
.hsr__status--cancelled { background: rgba(170,170,170,0.15); color: var(--color-text-light, #aaa); }
.hsr__status--aborted-binding-unreachable { background: rgba(224,107,107,0.15); color: #e06b6b; }
.hsr__status--running { background: rgba(94,163,255,0.15); color: #5ea3ff; }
</style>
