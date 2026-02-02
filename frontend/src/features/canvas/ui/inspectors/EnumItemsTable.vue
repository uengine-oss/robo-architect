<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:items'])

const IconTrash = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>`

const IconClipboard = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>`

const localItems = ref([])

watch(() => props.items, (newItems) => {
  localItems.value = [...(newItems || [])]
}, { immediate: true, deep: true })

watch(localItems, (newItems) => {
  emit('update:items', [...newItems])
}, { deep: true })

const visibleItems = computed(() => {
  return localItems.value || []
})

const duplicateMap = computed(() => {
  const map = new Map()
  for (const item of visibleItems.value) {
    const key = String(item || '').trim()
    if (!key) continue
    map.set(key, (map.get(key) || 0) + 1)
  }
  return map
})

const itemIssues = computed(() => {
  const issues = {}
  for (let i = 0; i < visibleItems.value.length; i++) {
    const item = String(visibleItems.value[i] || '').trim()
    issues[i] = { errors: [], warnings: [] }
    
    if (!item) {
      issues[i].errors.push('값은 필수입니다.')
    } else if ((duplicateMap.value.get(item) || 0) > 1) {
      issues[i].errors.push(`중복 값: "${item}"`)
    }
  }
  return issues
})

const hasBlockingErrors = computed(() => {
  return Object.values(itemIssues.value).some(v => (v?.errors || []).length > 0)
})

function addRow() {
  localItems.value.push('')
  nextTick(() => {
    const inputs = document.querySelectorAll('.enum-items-table tbody .prop-input')
    if (inputs.length) {
      inputs[inputs.length - 1]?.focus()
    }
  })
}

function removeRow(index) {
  localItems.value.splice(index, 1)
}

function handleRowKeydown(e, rowIndex) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    const rows = visibleItems.value
    if (rowIndex === rows.length - 1) {
      addRow()
    } else {
      const nextInput = e.target.closest('tr')?.nextElementSibling?.querySelector('.prop-input')
      nextInput?.focus()
    }
  } else if (e.key === 'Escape') {
    e.target.blur()
  }
}

defineExpose({
  hasBlockingErrors
})
</script>

<template>
  <div class="prop-editor">
    <div class="prop-editor__header">
      <div class="prop-editor__title">Items</div>
      <button class="prop-editor__add" :disabled="disabled" @click="addRow">+ Add</button>
    </div>

    <div v-if="hasBlockingErrors" class="prop-editor__alert error">
      Item 입력 오류가 있습니다. (중복 값 / 값 필수)
    </div>

    <div class="prop-editor__table-wrap">
      <table class="prop-editor__table enum-items-table">
        <thead>
          <tr>
            <th class="col-value">value</th>
            <th class="col-actions"></th>
          </tr>
        </thead>
        <tbody>
          <tr 
            v-for="(item, rowIndex) in visibleItems" 
            :key="rowIndex"
            class="prop-row"
          >
            <td>
              <input
                class="prop-input"
                type="text"
                v-model="localItems[rowIndex]"
                :disabled="disabled"
                placeholder="ex) PENDING"
                @keydown="handleRowKeydown($event, rowIndex)"
              />
              <div v-if="itemIssues[rowIndex]?.errors?.length" class="prop-issue error">
                {{ itemIssues[rowIndex].errors[0] }}
              </div>
            </td>
            <td class="center">
              <button
                class="prop-icon-btn prop-icon-btn--delete prop-action"
                :disabled="disabled"
                @click="removeRow(rowIndex)"
                v-html="IconTrash"
                aria-label="Delete item"
                title="삭제"
              ></button>
            </td>
          </tr>

          <tr v-if="visibleItems.length === 0">
            <td class="prop-empty" colspan="2">
              <div class="prop-empty__icon" v-html="IconClipboard"></div>
              <div class="prop-empty__text">아직 item이 없습니다</div>
              <button 
                class="prop-empty__btn" 
                :disabled="disabled" 
                @click="addRow"
              >
                + 첫 번째 item 추가하기
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.prop-editor {
  margin-top: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  overflow: hidden;
}

.prop-editor__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-tertiary);
}

.prop-editor__title {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--color-text-bright);
}

.prop-editor__add {
  font-size: 0.65rem;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text);
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}
.prop-editor__add:hover:not(:disabled) {
  background: var(--color-bg-tertiary);
  border-color: var(--color-accent);
  color: var(--color-accent);
}
.prop-editor__add:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.prop-editor__alert {
  padding: 8px 10px;
  font-size: 0.65rem;
  border-bottom: 1px solid var(--color-border);
}
.prop-editor__alert.error {
  background: rgba(255, 107, 107, 0.08);
  color: #ff6b6b;
}

.prop-editor__table-wrap {
  overflow: auto;
  max-height: 320px;
}

.prop-editor__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.65rem;
}

.prop-editor__table th,
.prop-editor__table td {
  border-bottom: 1px solid var(--color-border);
  padding: 6px 8px;
  vertical-align: middle;
}

.prop-editor__table th {
  position: sticky;
  top: 0;
  background: var(--color-bg-secondary);
  color: var(--color-text-light);
  font-weight: 600;
  text-align: left;
  z-index: 1;
}

.col-value { width: 92%; }
.col-actions { width: 8%; }

.center {
  text-align: center;
}

.prop-row {
  transition: background 0.15s ease;
}
.prop-row:hover {
  background: var(--color-bg-tertiary);
}

.prop-action {
  opacity: 0;
  transition: opacity 0.15s ease;
}
.prop-row:hover .prop-action {
  opacity: 1;
}

.prop-input {
  width: 100%;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text);
  border-radius: var(--radius-sm);
  padding: 4px 6px;
  font-size: 0.65rem;
  transition: border-color 0.15s ease;
}
.prop-input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.prop-issue {
  margin-top: 4px;
  font-size: 0.6rem;
  line-height: 1.2;
}
.prop-issue.error {
  color: #ff6b6b;
}

.prop-icon-btn {
  border: none;
  background: transparent;
  color: var(--color-text-light);
  padding: 4px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}
.prop-icon-btn:hover:not(:disabled) {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}
.prop-icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.prop-icon-btn--delete:hover:not(:disabled) {
  background: rgba(255, 107, 107, 0.15);
  color: #ff6b6b;
  transform: scale(1.1);
}

.prop-empty {
  padding: 32px 16px;
  text-align: center;
}

.prop-empty__icon {
  color: var(--color-text-light);
  opacity: 0.4;
  margin-bottom: 12px;
  display: inline-block;
}

.prop-empty__text {
  font-size: 0.75rem;
  color: var(--color-text-light);
  margin-bottom: 16px;
}

.prop-empty__btn {
  font-size: 0.68rem;
  border: 1px dashed var(--color-border);
  background: transparent;
  color: var(--color-accent);
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}
.prop-empty__btn:hover:not(:disabled) {
  background: rgba(34, 139, 230, 0.1);
  border-color: var(--color-accent);
}
.prop-empty__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
