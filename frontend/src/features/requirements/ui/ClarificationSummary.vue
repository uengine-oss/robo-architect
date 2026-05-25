<script setup>
import { computed } from 'vue'

/**
 * End-of-session summary (spec 030 — US3).
 * Lists every requirement changed during the session with before/after
 * snapshots, exposes per-change revert, and shows the per-category
 * coverage table.
 */
const props = defineProps({
  summary: { type: Object, required: true },
})
const emit = defineEmits(['revert'])

const changed = computed(() => props.summary?.changedRequirements || [])
const coverage = computed(() => props.summary?.coverage || [])

function revert(requirementId) {
  if (!window.confirm('이 변경을 되돌릴까요? 다른 변경은 그대로 유지됩니다.')) return
  emit('revert', requirementId)
}
</script>

<template>
  <section class="cs-root">
    <header class="cs-header">
      <strong>명확화 요약</strong>
      <span class="cs-counts">
        질문 {{ summary.questionsAsked }} · 적용 {{ summary.questionsApplied }} · 건너뜀 {{ summary.questionsSkipped }}
      </span>
    </header>

    <div v-if="!changed.length" class="cs-empty">변경된 요구사항이 없습니다.</div>

    <div v-for="change in changed" :key="change.requirementId + change.questionId" class="cs-change">
      <div class="cs-change-head">
        <code>{{ change.requirementId }}</code> — {{ change.requirementLabel }}
        <button class="cs-revert" @click="revert(change.requirementId)">되돌리기</button>
      </div>
      <div class="cs-diff">
        <div class="cs-diff-col">
          <div class="cs-diff-label">변경 전</div>
          <pre>{{ JSON.stringify(change.before, null, 2) }}</pre>
        </div>
        <div class="cs-diff-col">
          <div class="cs-diff-label">변경 후</div>
          <pre>{{ JSON.stringify(change.after, null, 2) }}</pre>
        </div>
      </div>
    </div>

    <h4 class="cs-coverage-title">범주별 커버리지</h4>
    <table class="cs-coverage">
      <thead>
        <tr><th>범주</th><th>상태</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in coverage" :key="row.category">
          <td>{{ row.category }}</td>
          <td><span class="cs-status" :class="`cs-status--${row.status}`">{{ row.status }}</span></td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.cs-root {
  padding: 8px 0; border-top: 1px solid var(--color-border, #eee);
  margin-top: 10px;
}
.cs-header { display: flex; justify-content: space-between; align-items: center; font-size: 0.82rem; }
.cs-counts { font-size: 0.72rem; color: var(--color-text-light, #888); }
.cs-empty { padding: 12px; color: var(--color-text-light, #888); }
.cs-change { padding: 6px 0; border-top: 1px dashed var(--color-border, #eee); }
.cs-change-head {
  display: flex; align-items: center; gap: 6px; font-size: 0.74rem;
}
.cs-change-head code {
  background: var(--color-bg-tertiary, #f4f4f4);
  padding: 1px 4px; border-radius: 3px;
}
.cs-revert {
  margin-left: auto; font-size: 0.72rem; border: 1px solid var(--color-border, #ccc);
  background: transparent; padding: 2px 8px; border-radius: 4px; cursor: pointer;
}
.cs-revert:hover { background: var(--color-bg-tertiary, #fafafa); }
.cs-diff { display: flex; gap: 6px; padding-top: 4px; }
.cs-diff-col { flex: 1; font-size: 0.72rem; }
.cs-diff-label { font-weight: 700; color: var(--color-text-light, #888); }
.cs-diff-col pre {
  background: var(--color-bg-tertiary, #fafafa); padding: 6px;
  border-radius: 4px; white-space: pre-wrap; word-break: break-word;
  max-height: 200px; overflow: auto;
}
.cs-coverage-title { font-size: 0.78rem; margin: 12px 0 4px; }
.cs-coverage { width: 100%; font-size: 0.74rem; border-collapse: collapse; }
.cs-coverage th, .cs-coverage td { padding: 3px 6px; border-bottom: 1px solid var(--color-border, #eee); text-align: left; }
.cs-status {
  padding: 1px 6px; border-radius: 4px; font-size: 0.7rem;
  background: var(--color-bg-tertiary, #f4f4f4);
}
.cs-status--resolved { background: rgba(64, 192, 87, 0.2); color: #2f9e44; }
.cs-status--deferred { background: rgba(255, 196, 0, 0.25); color: #b87b00; }
.cs-status--outstanding { background: rgba(224, 49, 49, 0.18); color: #c92a2a; }
.cs-status--clear { background: var(--color-bg-tertiary, #f4f4f4); color: var(--color-text-light, #888); }
</style>
