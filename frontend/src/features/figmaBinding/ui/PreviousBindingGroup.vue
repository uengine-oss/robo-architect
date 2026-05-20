<script setup>
/**
 * 020: Collapsible "이전 바인딩" group inside the FigmaBindingModal History tab.
 * Renders previous-binding sync runs + non-retryable failures whose
 * nonRetryableReason === '이전 바인딩'. All retry controls are disabled inside
 * this group (HistoryFailureRow already disables them when retryability is
 * non-retryable, and HistorySyncRunRow has no retry control at all).
 */
import { computed, ref } from 'vue'
import HistoryFailureRow from './HistoryFailureRow.vue'
import HistorySyncRunRow from './HistorySyncRunRow.vue'

const props = defineProps({
  syncRuns: { type: Array, default: () => [] },
  failures: { type: Array, default: () => [] },
})

const expanded = ref(false)

const total = computed(() => props.syncRuns.length + props.failures.length)
</script>

<template>
  <div v-if="total > 0" class="pbg">
    <button class="pbg__header" @click="expanded = !expanded">
      <span class="pbg__caret">{{ expanded ? '▾' : '▸' }}</span>
      이전 바인딩 ({{ total }}건)
    </button>
    <div v-if="expanded" class="pbg__body">
      <HistoryFailureRow
        v-for="f in failures"
        :key="`pbg-f-${f.uiId}`"
        :failure="f"
      />
      <HistorySyncRunRow
        v-for="r in syncRuns"
        :key="`pbg-r-${r.runId}`"
        :run="r"
      />
    </div>
  </div>
</template>

<style scoped>
.pbg { margin-top: 12px; padding-top: 8px; border-top: 1px dashed var(--color-border, #2a2e3d); }
.pbg__header { background: transparent; border: none; color: var(--color-text-light, #aaa); cursor: pointer; padding: 4px 0; font-size: 0.76rem; display: flex; align-items: center; gap: 6px; }
.pbg__header:hover { color: var(--color-text, #e6e8ee); }
.pbg__caret { font-size: 0.7rem; }
.pbg__body { padding-left: 12px; padding-top: 4px; }
</style>
