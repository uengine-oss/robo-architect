<template>
  <span :class="opClass(entry.op)">{{ entry.op }}</span>
  <span class="diff-entry__title">{{ entry.entityTitle }}</span>
  <template v-if="entry.acceptanceCriteria?.length">
    <ul class="ac-list">
      <li v-for="(ac, i) in entry.acceptanceCriteria" :key="i">{{ ac }}</li>
    </ul>
  </template>
  <template v-if="entry.fields">
    <div v-for="(v, k) in entry.fields" :key="k" class="diff-entry__field">
      <span class="field-key">{{ k }}:</span>
      <span class="field-before">{{ v?.before ?? '—' }}</span>
      <span class="arrow">→</span>
      <span class="field-after">{{ v?.after ?? '—' }}</span>
    </div>
  </template>
</template>

<script setup>
// Strategic Diff 항목 하나를 op/title/acceptanceCriteria/fields 기준으로
// 제네릭하게 렌더한다. Process(1급) 및 프로젝트별 미지 카테고리에서 공용 사용.
defineProps({
  entry: { type: Object, required: true },
  opClass: { type: Function, required: true },
})
</script>

<style scoped>
.diff-entry__title { font-weight: 500; color: var(--color-text); }
.diff-entry__field { font-size: 12px; color: var(--color-text-light); margin-top: 4px; display: flex; gap: 6px; align-items: center; }
.field-key { font-weight: 600; color: var(--color-text); }
.field-before { color: var(--color-danger); text-decoration: line-through; }
.arrow { color: var(--color-text-light); }
.field-after { color: var(--color-success); }
.ac-list { margin: 4px 0 0 16px; padding: 0; font-size: 12px; color: var(--color-text); }
.ac-list li { margin-bottom: 2px; }
.op-badge { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px; text-transform: uppercase; }
.op-badge--create { background: var(--status-green-bg); color: var(--status-green-fg); }
.op-badge--modify { background: var(--status-amber-bg); color: var(--status-amber-fg); }
.op-badge--delete { background: var(--status-red-bg); color: var(--status-red-fg); }
</style>
