<script setup>
/**
 * 020: Single failure row inside the FigmaBindingModal History tab.
 * Shows display name + last Korean error + last attempt time, with one of:
 *   - 다시 시도 (when retryability === 'retryable' and binding active)
 *   - "재시도 중" pill (when 'in-flight')
 *   - "재시도 불가 — <reason>" pill (when 'non-retryable')
 *
 * The retry button is also disabled (with tooltip) when the binding is
 * not active — FR-011.
 */
import { computed } from 'vue'
import { useFigmaBindingStore } from '../figmaBinding.store'

const props = defineProps({
  failure: { type: Object, required: true },
})

const store = useFigmaBindingStore()

const isActive = computed(() => store.isActive)
const isRetryable = computed(() => props.failure.retryability === 'retryable')
const isInFlight = computed(() => props.failure.retryability === 'in-flight')
const isNonRetryable = computed(() => props.failure.retryability === 'non-retryable')

const disabledReason = computed(() => {
  if (!isActive.value) return 'binding 해제됨'
  return ''
})

async function onRetry() {
  if (!isActive.value || !isRetryable.value) return
  await store.retryUi(props.failure.uiId)
}
</script>

<template>
  <div class="hfr">
    <div class="hfr__main">
      <span class="hfr__name">{{ failure.displayName || failure.uiId }}</span>
      <span class="hfr__error" v-if="failure.lastErrorKr">{{ failure.lastErrorKr }}</span>
    </div>
    <div class="hfr__meta">
      <time v-if="failure.lastAttemptAt" class="hfr__time">{{ failure.lastAttemptAt }}</time>
      <button
        v-if="isRetryable"
        class="hfr__retry"
        :disabled="!isActive"
        :title="disabledReason"
        @click="onRetry"
      >다시 시도</button>
      <span v-else-if="isInFlight" class="hfr__pill hfr__pill--inflight">재시도 중</span>
      <span v-else-if="isNonRetryable" class="hfr__pill hfr__pill--nonretry" :title="failure.nonRetryableReason || ''">
        재시도 불가<span v-if="failure.nonRetryableReason"> — {{ failure.nonRetryableReason }}</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.hfr { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--color-border, #2a2e3d); font-size: 0.78rem; }
.hfr__main { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.hfr__name { font-weight: 500; color: var(--color-text, #e6e8ee); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hfr__error { color: #e06b6b; font-size: 0.74rem; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hfr__meta { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.hfr__time { font-size: 0.7rem; color: var(--color-text-light, #aaa); }
.hfr__retry { padding: 4px 10px; font-size: 0.74rem; border-radius: 4px; border: 1px solid #0acf83; background: transparent; color: #0acf83; cursor: pointer; }
.hfr__retry:hover:not([disabled]) { background: rgba(10,207,131,0.08); }
.hfr__retry[disabled] { opacity: 0.4; cursor: not-allowed; }
.hfr__pill { padding: 2px 8px; border-radius: 999px; font-size: 0.7rem; }
.hfr__pill--inflight { background: rgba(94,163,255,0.12); color: #5ea3ff; }
.hfr__pill--nonretry { background: rgba(170,170,170,0.12); color: var(--color-text-light, #aaa); }
</style>
