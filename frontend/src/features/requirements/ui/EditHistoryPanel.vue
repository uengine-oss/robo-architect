<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const FIELD_LABELS = {
  role: '역할 (As a)',
  action: '목적 (I want)',
  benefit: '혜택 (so that)',
  priority: '우선순위',
  status: '상태',
}

function formatTs(iso) {
  if (!iso) return ''
  try {
    return new Intl.DateTimeFormat('ko-KR', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

function changedFields(changes) {
  return Object.entries(changes || {}).map(([field, diff]) => ({
    label: FIELD_LABELS[field] || field,
    before: diff.before ?? '',
    after: diff.after ?? '',
  }))
}

const hasItems = computed(() => props.items.length > 0)
</script>

<template>
  <div class="edit-history">
    <div v-if="loading" class="edit-history__loading">이력 로딩 중…</div>
    <div v-else-if="!hasItems" class="edit-history__empty">편집 이력이 없습니다.</div>
    <ul v-else class="edit-history__list">
      <li v-for="item in items" :key="item.id" class="history-item">
        <div class="history-item__meta">
          <span class="history-item__user" :title="item.userEmail">{{ item.userName }}</span>
          <span class="history-item__time">{{ formatTs(item.timestamp) }}</span>
        </div>
        <ul class="history-item__changes">
          <li v-for="f in changedFields(item.changes)" :key="f.label" class="change-row">
            <span class="change-row__field">{{ f.label }}</span>
            <span class="change-row__before">{{ f.before || '(없음)' }}</span>
            <span class="change-row__arrow">→</span>
            <span class="change-row__after">{{ f.after || '(없음)' }}</span>
          </li>
        </ul>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.edit-history { display: flex; flex-direction: column; gap: 8px; }
.edit-history__loading,
.edit-history__empty {
  font-size: 0.8rem; color: var(--color-text-light); padding: 8px 0;
}
.edit-history__list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }

.history-item {
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--color-bg-tertiary);
  border-left: 3px solid var(--color-accent, #228be6);
}
.history-item__meta {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 6px;
}
.history-item__user { font-size: 0.78rem; font-weight: 600; color: var(--color-text); }
.history-item__time { font-size: 0.72rem; color: var(--color-text-light); }

.history-item__changes {
  list-style: none; padding: 0; margin: 0;
  display: flex; flex-direction: column; gap: 4px;
}
.change-row {
  display: grid;
  grid-template-columns: 90px 1fr auto 1fr;
  align-items: baseline;
  gap: 6px;
  font-size: 0.78rem;
}
.change-row__field {
  font-weight: 600; color: var(--color-text-light);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.change-row__before { color: #e03131; text-decoration: line-through; word-break: break-all; }
.change-row__arrow { color: var(--color-text-light); flex-shrink: 0; }
.change-row__after { color: #2f9e44; word-break: break-all; }
</style>
