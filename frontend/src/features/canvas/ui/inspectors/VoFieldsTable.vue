<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  fields: {
    type: Array,
    default: () => []
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:fields'])

const IconTrash = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>`

const IconChevronDown = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>`

const IconClipboard = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>`

const TYPE_OPTIONS = ['Integer', 'String', 'Boolean', 'Float', 'Double', 'Long', 'Date', 'BigDecimal']

const localFields = ref([])

watch(() => props.fields, (newFields) => {
  localFields.value = (newFields || []).map(f => ({
    name: String(f?.name || ''),
    type: String(f?.type || '')
  }))
}, { immediate: true, deep: true })

watch(localFields, (newFields) => {
  emit('update:fields', newFields.map(f => ({ name: f.name, type: f.type })))
}, { deep: true })

const visibleFields = computed(() => {
  return localFields.value || []
})

const duplicateNameMap = computed(() => {
  const map = new Map()
  for (const field of visibleFields.value) {
    const key = String(field?.name || '').trim()
    if (!key) continue
    map.set(key, (map.get(key) || 0) + 1)
  }
  return map
})

const fieldIssues = computed(() => {
  const issues = {}
  for (let i = 0; i < visibleFields.value.length; i++) {
    const field = visibleFields.value[i]
    const name = String(field?.name || '').trim()
    const type = String(field?.type || '').trim()
    issues[i] = { errors: [], warnings: [] }
    
    if (!name) {
      issues[i].errors.push('name은 필수입니다.')
    } else if ((duplicateNameMap.value.get(name) || 0) > 1) {
      issues[i].errors.push(`중복 name: "${name}"`)
    }
    
    if (!type) {
      issues[i].errors.push('type은 필수입니다.')
    }
  }
  return issues
})

const hasBlockingErrors = computed(() => {
  return Object.values(fieldIssues.value).some(v => (v?.errors || []).length > 0)
})

const typeDropdown = ref({
  openRowIndex: null
})

function toggleTypeDropdown(rowIndex) {
  if (props.disabled) return
  if (typeDropdown.value.openRowIndex === rowIndex) {
    typeDropdown.value.openRowIndex = null
  } else {
    typeDropdown.value.openRowIndex = rowIndex
  }
}

function selectType(rowIndex, type) {
  localFields.value[rowIndex].type = type
  typeDropdown.value.openRowIndex = null
}

function closeTypeDropdown() {
  typeDropdown.value.openRowIndex = null
}

function handleGlobalClick(e) {
  if (typeDropdown.value.openRowIndex !== null && !e.target.closest('.prop-combobox')) {
    typeDropdown.value.openRowIndex = null
  }
}

function addRow() {
  localFields.value.push({ name: '', type: '' })
  nextTick(() => {
    const inputs = document.querySelectorAll('.vo-fields-table tbody .prop-input')
    if (inputs.length) {
      inputs[inputs.length - 2]?.focus() // name input of last row
    }
  })
}

function removeRow(index) {
  localFields.value.splice(index, 1)
}

function handleRowKeydown(e, rowIndex, fieldName) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    const rows = visibleFields.value
    if (fieldName === 'name' && rowIndex < rows.length) {
      // Move to type input of same row
      const currentRow = e.target.closest('tr')
      const typeInput = currentRow?.querySelector('.prop-combobox__input')
      typeInput?.focus()
    } else if (rowIndex === rows.length - 1) {
      // Last row: add new row
      addRow()
    } else {
      // Move to next row's name input
      const nextInput = e.target.closest('tr')?.nextElementSibling?.querySelector('.prop-input')
      nextInput?.focus()
    }
  } else if (e.key === 'Escape') {
    e.target.blur()
    closeTypeDropdown()
  }
}

defineExpose({
  hasBlockingErrors
})

// Add global click listener
onMounted(() => {
  document.addEventListener('click', handleGlobalClick)
})
onUnmounted(() => {
  document.removeEventListener('click', handleGlobalClick)
})
</script>

<template>
  <div class="prop-editor">
    <div class="prop-editor__header">
      <div class="prop-editor__title">Fields</div>
      <button class="prop-editor__add" :disabled="disabled" @click="addRow">+ Add</button>
    </div>

    <div v-if="hasBlockingErrors" class="prop-editor__alert error">
      Field 입력 오류가 있습니다. (중복 name / name·type 필수)
    </div>

    <div class="prop-editor__table-wrap">
      <table class="prop-editor__table vo-fields-table">
        <thead>
          <tr>
            <th class="col-name">name</th>
            <th class="col-type">type</th>
            <th class="col-actions"></th>
          </tr>
        </thead>
        <tbody>
          <tr 
            v-for="(field, rowIndex) in visibleFields" 
            :key="rowIndex"
            class="prop-row"
          >
            <td>
              <input
                class="prop-input"
                type="text"
                v-model="localFields[rowIndex].name"
                :disabled="disabled"
                placeholder="ex) orderId"
                @keydown="handleRowKeydown($event, rowIndex, 'name')"
              />
              <div v-if="fieldIssues[rowIndex]?.errors?.length" class="prop-issue error">
                {{ fieldIssues[rowIndex].errors.find(e => e.includes('name')) || '' }}
              </div>
            </td>

            <td>
              <div class="prop-combobox">
                <input
                  class="prop-input prop-combobox__input"
                  type="text"
                  v-model="localFields[rowIndex].type"
                  :disabled="disabled"
                  placeholder="String"
                  @focus="typeDropdown.openRowIndex = rowIndex"
                  @keydown="handleRowKeydown($event, rowIndex, 'type')"
                />
                <button
                  class="prop-combobox__toggle"
                  :disabled="disabled"
                  @click.stop="toggleTypeDropdown(rowIndex)"
                  v-html="IconChevronDown"
                  aria-label="Type 선택"
                ></button>
                <div 
                  v-if="typeDropdown.openRowIndex === rowIndex" 
                  class="prop-combobox__dropdown"
                >
                  <div
                    v-for="t in TYPE_OPTIONS"
                    :key="t"
                    class="prop-combobox__option"
                    :class="{ active: localFields[rowIndex].type === t }"
                    @mousedown.prevent="selectType(rowIndex, t)"
                  >
                    {{ t }}
                  </div>
                </div>
              </div>
              <div v-if="fieldIssues[rowIndex]?.errors?.length" class="prop-issue error">
                {{ fieldIssues[rowIndex].errors.find(e => e.includes('type')) || '' }}
              </div>
            </td>

            <td class="center">
              <button
                class="prop-icon-btn prop-icon-btn--delete prop-action"
                :disabled="disabled"
                @click="removeRow(rowIndex)"
                v-html="IconTrash"
                aria-label="Delete field"
                title="삭제"
              ></button>
            </td>
          </tr>

          <tr v-if="visibleFields.length === 0">
            <td class="prop-empty" colspan="3">
              <div class="prop-empty__icon" v-html="IconClipboard"></div>
              <div class="prop-empty__text">아직 field가 없습니다</div>
              <button 
                class="prop-empty__btn" 
                :disabled="disabled" 
                @click="addRow"
              >
                + 첫 번째 field 추가하기
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

.col-name { width: 50%; }
.col-type { width: 42%; }
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

.prop-combobox {
  position: relative;
  display: flex;
  align-items: center;
}

.prop-combobox__input {
  flex: 1;
  padding-right: 24px;
}

.prop-combobox__toggle {
  position: absolute;
  right: 2px;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  color: var(--color-text-light);
  padding: 2px 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.prop-combobox__toggle:hover:not(:disabled) {
  color: var(--color-text);
}

.prop-combobox__dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 100;
  max-height: 180px;
  overflow-y: auto;
  margin-top: 2px;
}

.prop-combobox__option {
  padding: 6px 8px;
  font-size: 0.65rem;
  color: var(--color-text);
  cursor: pointer;
  transition: background 0.1s ease;
}
.prop-combobox__option:hover {
  background: var(--color-bg-tertiary);
}
.prop-combobox__option.active {
  background: var(--color-accent);
  color: white;
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
