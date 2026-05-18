<script setup>
import { computed } from 'vue'

/**
 * Non-blocking impact report panel (026 — US5).
 * Shows duplicate / conflict / design-impact findings after an add/move/delete.
 * Hidden entirely when there are no findings.
 */
const props = defineProps({
  report: { type: Object, default: null },
})
const emit = defineEmits(['dismiss'])

const running = computed(() => props.report?.status === 'running')
const findings = computed(() => props.report?.findings || [])
const visible = computed(
  () => !!props.report && (running.value || findings.value.length > 0 || props.report.status === 'failed'),
)
const kindLabel = { duplicate: '중복', conflict: '충돌', design_impact: '설계 영향' }
</script>

<template>
  <div v-if="visible" class="impact-panel">
    <div class="impact-panel__head">
      <span class="impact-panel__title">영향도 분석</span>
      <span v-if="running" class="impact-panel__status">분석 중...</span>
      <button class="impact-panel__close" @click="emit('dismiss')">×</button>
    </div>
    <div class="impact-panel__body">
      <p v-if="running" class="impact-panel__hint">백그라운드에서 분석 중입니다. 작업을 계속하세요.</p>
      <p v-else-if="report.status === 'failed'" class="impact-panel__hint">분석에 실패했습니다.</p>
      <ul v-else>
        <li v-for="(f, i) in findings" :key="i" class="finding" :class="`finding--${f.severity}`">
          <span class="finding__kind">{{ kindLabel[f.kind] || f.kind }}</span>
          <span class="finding__msg">{{ f.message }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.impact-panel {
  position: absolute; right: 16px; bottom: 16px; width: 320px; max-height: 260px;
  background: var(--color-bg-secondary); border: 1px solid var(--color-border);
  border-radius: 8px; box-shadow: 0 6px 24px rgba(0, 0, 0, 0.25); z-index: 40;
  display: flex; flex-direction: column; overflow: hidden;
}
.impact-panel__head {
  display: flex; align-items: center; gap: 8px; padding: 8px 10px;
  border-bottom: 1px solid var(--color-border);
}
.impact-panel__title { font-size: 0.78rem; font-weight: 700; }
.impact-panel__status { font-size: 0.68rem; color: var(--color-text-light); }
.impact-panel__close {
  margin-left: auto; border: none; background: transparent; cursor: pointer;
  font-size: 1rem; color: var(--color-text-light);
}
.impact-panel__body { padding: 8px 10px; overflow-y: auto; }
.impact-panel__hint { font-size: 0.75rem; color: var(--color-text-light); }
.impact-panel__body ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.finding { font-size: 0.74rem; padding: 6px 8px; border-radius: 6px; background: var(--color-bg-tertiary); }
.finding--warning { border-left: 3px solid #fd7e14; }
.finding--info { border-left: 3px solid #5c7cfa; }
.finding__kind { font-weight: 700; margin-right: 6px; }
</style>
