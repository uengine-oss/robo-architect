<script setup>
import { computed } from 'vue'

/**
 * "요구사항 생성 엔진" 이 실제로 무엇을 돌렸는지 보이는 배지 (B-2).
 * claude-ide 를 골라도 실패하면 백엔드가 in-process(또는 결정적 초안)로 넘어간다 —
 * 그 폴백이 조용하면 "동작하는지 모르겠다" 가 된다. 요청과 실제가 다르면 경고색 + 까닭.
 * 입력: 응답의 { engineRequested, engineUsed, engineFallbackReason }.
 */
const props = defineProps({
  requested: { type: String, default: '' },
  used: { type: String, default: '' },
  reason: { type: String, default: '' },
})

const NAMES = {
  'claude-ide': 'Claude IDE',
  'in-process': 'in-process LLM',
  deterministic: 'LLM 없이 만든 초안',
  none: '생성 실패',
}

const fellBack = computed(() => !!props.used && !!props.requested && props.used !== props.requested)
const label = computed(() => {
  const u = NAMES[props.used] || props.used
  if (!fellBack.value) return `엔진: ${u}`
  return `엔진: ${u} (${NAMES[props.requested] || props.requested} 에서 폴백)`
})
</script>

<template>
  <span
    v-if="used"
    class="engine-badge"
    :class="{ 'engine-badge--warn': fellBack || used === 'none' }"
    :title="reason || label"
    data-testid="engine-used-badge"
  >{{ label }}</span>
  <span v-if="used && reason" class="engine-badge__reason">{{ reason }}</span>
</template>

<style scoped>
.engine-badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 0.7rem;
  background: var(--color-bg-tertiary);
  color: var(--color-text-light);
  border: 1px solid var(--color-border);
}
.engine-badge--warn {
  background: rgba(245, 158, 11, 0.14);
  color: #b45309;
  border-color: rgba(245, 158, 11, 0.5);
}
.engine-badge__reason {
  display: block;
  margin-top: 2px;
  font-size: 0.68rem;
  color: var(--color-text-light);
}
</style>
