<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { createLogger, newOpId } from '@/app/logging/logger'
import { useTerminologyStore } from '@/features/terminology/terminology.store'

const log = createLogger({ scope: 'PropertyEditorTable' })
const terminologyStore = useTerminologyStore()

// ============================================
// SVG Icons (inline)
// ============================================
const IconTrash = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>`

const IconEdit = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`

const IconKey = `<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>`

const IconLink = `<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>`

const IconCheck = `<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`

const IconChevronDown = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>`

const IconClipboard = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>`

const TYPE_OPTIONS = ['Integer', 'String', 'Boolean', 'Float', 'Double', 'Long', 'Date', 'BigDecimal']

const props = defineProps({
  node: {
    type: Object,
    default: null
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['state-change'])

function toBool(v) {
  return !!v
}

function normalizeName(v) {
  return String(v ?? '').trim()
}

function generateTempId() {
  return `prop-temp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function isCamelCase(name) {
  const s = normalizeName(name)
  if (!s) return true
  return /^[a-z][a-zA-Z0-9]*$/.test(s)
}

function recommendedIdStyle(name, row) {
  const s = normalizeName(name)
  if (!s) return null
  if (row?.isKey || row?.isForeignKey) {
    if (s === 'id') return null
    if (s.endsWith('Id') && s.length > 2) return null
    return 'Key/FK 속성은 id 또는 xxxId 형태를 권장합니다.'
  }
  return null
}

function snapshotPropsFromNode(n) {
  const data = n?.data || {}
  const props = Array.isArray(data?.properties) ? data.properties : []
  const enums = Array.isArray(data?.enumerations) ? data.enumerations : []
  const vos = Array.isArray(data?.valueObjects) ? data.valueObjects : []
  
  const result = []
  
  // Add regular properties (editable) - first
  props.forEach(p => {
    result.push({
    id: String(p?.id || ''),
    name: String(p?.name ?? ''),
    displayName: String(p?.displayName ?? ''),
    type: String(p?.type ?? ''),
    description: String(p?.description ?? ''),
    isKey: toBool(p?.isKey),
    isForeignKey: toBool(p?.isForeignKey),
    isRequired: toBool(p?.isRequired),
      isReadOnly: false,
      fieldType: 'property',
    parentType: String(p?.parentType ?? data?.type ?? ''),
    parentId: String(p?.parentId ?? n?.id ?? '')
    })
  })
  
  // Add enumerations (read-only) - after properties
  enums.forEach((e, idx) => {
    if (e && e.name) {
      result.push({
        id: `enum-${e.name}-${idx}`,
        name: String(e.name ?? ''),
        displayName: String(e.displayName ?? ''),
        type: 'Enum',
        description: String(e.alias ?? ''),
        isKey: false,
        isForeignKey: false,
        isRequired: false,
        isReadOnly: true,
        fieldType: 'enum',
        parentType: String(data?.type ?? ''),
        parentId: String(n?.id ?? '')
      })
    }
  })
  
  // Add value objects (read-only) - after enumerations
  vos.forEach((vo, idx) => {
    if (vo && vo.name) {
      result.push({
        id: `vo-${vo.name}-${idx}`,
        name: String(vo.name ?? ''),
        displayName: String(vo.displayName ?? ''),
        type: 'ValueObject',
        description: String(vo.alias ?? ''),
        isKey: false,
        isForeignKey: false,
        isRequired: false,
        isReadOnly: true,
        fieldType: 'valueObject',
        referencedAggregateName: vo.referencedAggregateName || null,
        parentType: String(data?.type ?? ''),
        parentId: String(n?.id ?? '')
      })
    }
  })
  
  return result
}

const state = reactive({
  initial: [],
  rows: [],
  deletedIds: new Set(),
  confirmDelete: {
    open: false,
    rowId: null,
    rowName: '',
    loading: false,
    failed: false,
    errorMessage: '',
    refs: []
  }
})

// ============================================
// Popover state for description editing
// ============================================
const descPopover = reactive({
  open: false,
  rowId: null,
  value: '',
  position: { top: 0, left: 0 }
})
const descTextareaRef = ref(null)

function openDescPopover(row, event) {
  if (props.disabled) return
  const rect = event.currentTarget.getBoundingClientRect()
  const popoverWidth = 280
  const popoverHeight = 160 // approximate height
  const margin = 8
  
  // Calculate position with boundary checking
  let left = rect.left
  let top = rect.bottom + 4
  
  // Check right boundary
  if (left + popoverWidth > window.innerWidth - margin) {
    left = window.innerWidth - popoverWidth - margin
  }
  
  // Check left boundary
  if (left < margin) {
    left = margin
  }
  
  // Check bottom boundary - if not enough space below, show above
  if (top + popoverHeight > window.innerHeight - margin) {
    top = rect.top - popoverHeight - 4
  }
  
  // Ensure top is not negative
  if (top < margin) {
    top = margin
  }
  
  descPopover.open = true
  descPopover.rowId = row.id
  descPopover.value = row.description || ''
  descPopover.position = { top, left }
  
  nextTick(() => {
    descTextareaRef.value?.focus()
  })
}

function closeDescPopover() {
  if (!descPopover.open) return
  // Save value back to row
  const row = state.rows.find(r => r.id === descPopover.rowId)
  if (row) {
    row.description = descPopover.value
  }
  descPopover.open = false
  descPopover.rowId = null
  descPopover.value = ''
}

function handleDescKeydown(e) {
  if (e.key === 'Escape') {
    closeDescPopover()
  }
}

// ============================================
// Type Combobox state
// ============================================
const typeDropdown = reactive({
  openRowId: null
})

function toggleTypeDropdown(rowId) {
  if (props.disabled) return
  if (typeDropdown.openRowId === rowId) {
    typeDropdown.openRowId = null
  } else {
    typeDropdown.openRowId = rowId
  }
}

function selectType(row, type) {
  row.type = type
  typeDropdown.openRowId = null
}

function closeTypeDropdown() {
  typeDropdown.openRowId = null
}

// Close dropdown when clicking outside
function handleGlobalClick(e) {
  if (typeDropdown.openRowId && !e.target.closest('.prop-combobox')) {
    typeDropdown.openRowId = null
  }
}

// ============================================
// Core logic (unchanged)
// ============================================
function resetFromNode(n) {
  const opId = newOpId('propReset')
  const snap = snapshotPropsFromNode(n)
  state.initial = snap
  state.rows = snap.map(p => ({ ...p }))
  state.deletedIds = new Set()
  state.confirmDelete = {
    open: false,
    rowId: null,
    rowName: '',
    loading: false,
    failed: false,
    errorMessage: '',
    refs: []
  }
  log.info('property_editor_reset', 'Reset property editor state from node.', {
    opId,
    nodeId: n?.id,
    count: snap.length
  })
}

watch(
  () => props.node?.id,
  () => {
    resetFromNode(props.node)
  },
  { immediate: true }
)

const visibleRows = computed(() => {
  const deleted = state.deletedIds
  return (state.rows || []).filter(r => r && r.id && !deleted.has(r.id))
})

const duplicateNameMap = computed(() => {
  const map = new Map()
  const rows = visibleRows.value
  for (const r of rows) {
    const key = normalizeName(r?.name)
    if (!key) continue
    map.set(key, (map.get(key) || 0) + 1)
  }
  return map
})

const rowIssues = computed(() => {
  const issues = {}
  for (const r of visibleRows.value) {
    const id = r.id
    issues[id] = { errors: [], warnings: [] }

    const name = normalizeName(r.name)
    const type = String(r.type ?? '').trim()

    if (!name) issues[id].errors.push('name은 필수입니다.')
    if (!type) issues[id].errors.push('type은 필수입니다.')

    if (name && (duplicateNameMap.value.get(name) || 0) > 1) {
      issues[id].errors.push(`중복 name: "${name}"`)
    }

    if (name && !isCamelCase(name)) {
      issues[id].warnings.push('camelCase를 권장합니다.')
    }
    const idHint = recommendedIdStyle(name, r)
    if (idHint) issues[id].warnings.push(idHint)

    if (r.isKey && !r.isRequired) {
      issues[id].errors.push('isKey=true인 경우 isRequired는 반드시 true여야 합니다.')
    }
  }
  return issues
})

const hasBlockingErrors = computed(() => {
  return Object.values(rowIssues.value).some(v => (v?.errors || []).length > 0)
})

function findInitialById(id) {
  return (state.initial || []).find(p => p.id === id) || null
}

function buildDraftChanges() {
  const parentId = props.node?.id
  const parentType = props.node?.data?.type
  if (!parentId || !parentType) {
    return { drafts: [], errors: [] }
  }

  const errors = []
  if (hasBlockingErrors.value) {
    errors.push('Property 입력값 오류를 먼저 수정해주세요.')
  }

  const drafts = []

  for (const id of Array.from(state.deletedIds || [])) {
    const init = findInitialById(id)
    if (!init) continue
    drafts.push({
      changeId: `delete-${id}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      action: 'delete',
      targetId: id,
      targetType: 'Property',
      targetName: init.name,
      updates: {}
    })
  }

  for (const r of visibleRows.value) {
    const isNew = String(r.id || '').startsWith('prop-temp-')
    const name = normalizeName(r.name)
    const type = String(r.type ?? '').trim()
    const description = String(r.description ?? '').trim() || name

    const displayName = String(r.displayName ?? '').trim()
    const normalizedRow = {
      ...r,
      name,
      displayName: displayName || undefined,
      type,
      description,
      isKey: toBool(r.isKey),
      isForeignKey: toBool(r.isForeignKey),
      isRequired: toBool(r.isRequired),
      parentType,
      parentId
    }

    if (isNew) {
      if (!name || !type) continue
      drafts.push({
        changeId: `create-${r.id}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        action: 'create',
        targetId: r.id,
        targetType: 'Property',
        targetName: name,
        updates: {
          name,
          displayName: displayName || undefined,
          type,
          description,
          isKey: normalizedRow.isKey,
          isForeignKey: normalizedRow.isForeignKey,
          isRequired: normalizedRow.isRequired,
          parentType,
          parentId
        }
      })
      continue
    }

    const init = findInitialById(r.id)
    if (!init) continue

    if (normalizeName(init.name) !== name) {
      drafts.push({
        changeId: `rename-${r.id}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        action: 'rename',
        targetId: r.id,
        targetType: 'Property',
        targetName: name,
        updates: {}
      })
    }

    const updates = {}
    if (String(init.type ?? '') !== type) updates.type = type
    if (String(init.description ?? '') !== description) updates.description = description
    if (String(init.displayName ?? '') !== displayName) updates.displayName = displayName || undefined
    if (toBool(init.isKey) !== normalizedRow.isKey) updates.isKey = normalizedRow.isKey
    if (toBool(init.isForeignKey) !== normalizedRow.isForeignKey) updates.isForeignKey = normalizedRow.isForeignKey
    if (toBool(init.isRequired) !== normalizedRow.isRequired) updates.isRequired = normalizedRow.isRequired

    if (Object.keys(updates).length) {
      drafts.push({
        changeId: `update-${r.id}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        action: 'update',
        targetId: r.id,
        targetType: 'Property',
        targetName: name,
        updates
      })
    }
  }

  return { drafts, errors }
}

const isDirty = computed(() => {
  const res = buildDraftChanges()
  return (res.drafts || []).length > 0
})

watch(
  () => [isDirty.value, hasBlockingErrors.value],
  () => {
    emit('state-change', {
      isDirty: isDirty.value,
      hasBlockingErrors: hasBlockingErrors.value
    })
  },
  { immediate: true }
)

function addRow() {
  const parentId = props.node?.id
  const parentType = props.node?.data?.type
  if (!parentId || !parentType) return
  const id = generateTempId()
  state.rows.push({
    id,
    name: '',
    type: '',
    description: '',
    isKey: false,
    isForeignKey: false,
    isRequired: false,
    parentType,
    parentId
  })
  // Focus the new row's name input
  nextTick(() => {
    const inputs = document.querySelectorAll('.prop-editor__table tbody .prop-input')
    if (inputs.length) {
      inputs[inputs.length - 3]?.focus() // name input of last row
    }
  })
}

// ============================================
// Toggle badge handlers
// ============================================
function toggleKey(row) {
  if (props.disabled) return
  row.isKey = !row.isKey
  if (row.isKey) {
    row.isRequired = true
  }
}

function toggleFK(row) {
  if (props.disabled) return
  row.isForeignKey = !row.isForeignKey
}

function toggleReq(row) {
  if (props.disabled || row.isKey) return
  row.isRequired = !row.isRequired
}

// ============================================
// Keyboard navigation
// ============================================
function handleRowKeydown(e, row, rowIndex) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    const rows = visibleRows.value
    if (rowIndex === rows.length - 1) {
      // Last row: add new row
      addRow()
    } else {
      // Move to next row's name input
      const nextInput = e.target.closest('tr')?.nextElementSibling?.querySelector('.prop-input')
      nextInput?.focus()
    }
  } else if (e.key === 'Escape') {
    e.target.blur()
    closeDescPopover()
    closeTypeDropdown()
  }
}

// ============================================
// Delete logic
// ============================================
async function safeJson(response) {
  try {
    return await response.json()
  } catch {
    return null
  }
}

async function openDeleteConfirm(row) {
  if (!row) return

  const isNew = String(row.id || '').startsWith('prop-temp-')
  if (isNew) {
    state.rows = state.rows.filter(r => r?.id !== row.id)
    return
  }

  const opId = newOpId('cqrsRef')
  try {
    log.info('property_delete_check_start', 'Checking CQRS references for property delete.', { opId, propertyId: row.id })
    const resp = await fetch(`/api/cqrs/property/${row.id}/references`)
    const data = await safeJson(resp)
    if (!resp.ok) {
      throw new Error(data?.detail || `API error: ${resp.status}`)
    }
    const refs = Array.isArray(data?.references) ? data.references : []
    log.info('property_delete_check_done', 'CQRS references resolved for property delete.', {
      opId,
      propertyId: row.id,
      refCount: refs.length
    })

    if (!refs.length) {
      state.deletedIds.add(row.id)
      return
    }

    state.confirmDelete.open = true
    state.confirmDelete.rowId = row.id
    state.confirmDelete.rowName = normalizeName(row.name) || '(unnamed)'
    state.confirmDelete.loading = false
    state.confirmDelete.failed = false
    state.confirmDelete.errorMessage = ''
    state.confirmDelete.refs = refs
  } catch (e) {
    state.confirmDelete.open = true
    state.confirmDelete.rowId = row.id
    state.confirmDelete.rowName = normalizeName(row.name) || '(unnamed)'
    state.confirmDelete.loading = false
    state.confirmDelete.failed = true
    state.confirmDelete.errorMessage = e?.message || String(e)
    state.confirmDelete.refs = []
    log.error('property_delete_check_error', 'CQRS reference check failed.', {
      opId,
      propertyId: row.id,
      error: e?.message || String(e)
    })
  }
}

function closeDeleteConfirm() {
  state.confirmDelete.open = false
}

function forceDeleteConfirmed() {
  const id = state.confirmDelete.rowId
  if (id) state.deletedIds.add(id)
  closeDeleteConfirm()
}

const deleteModalTitle = computed(() => {
  if (state.confirmDelete.failed) return '참조 확인 실패'
  if ((state.confirmDelete.refs || []).length) return 'CQRS 참조가 있습니다'
  return '삭제 확인'
})

const deleteModalBody = computed(() => {
  if (state.confirmDelete.failed) {
    return {
      kind: 'failed',
      message: `CQRS 참조 확인에 실패했습니다.\n(${state.confirmDelete.errorMessage || 'unknown'})\n\n삭제를 진행하거나 취소할 수 있습니다.`
    }
  }
  const refs = state.confirmDelete.refs || []
  if (!refs.length) {
    return { kind: 'none', message: 'CQRS 참조가 발견되지 않았습니다. 삭제를 진행할까요?' }
  }
  return { kind: 'list', message: null }
})

const groupedRefs = computed(() => {
  const refs = state.confirmDelete.refs || []
  const map = new Map()
  for (const r of refs) {
    const rm = String(r?.readmodelName || r?.readmodelId || '')
    if (!map.has(rm)) map.set(rm, [])
    map.get(rm).push(r)
  }
  return Array.from(map.entries())
})

// ============================================
// Truncate description for preview
// ============================================
function truncateDesc(desc, maxLen = 20) {
  const s = String(desc || '').trim()
  if (!s) return '(없음)'
  if (s.length <= maxLen) return s
  return s.slice(0, maxLen) + '...'
}

defineExpose({
  resetFromNode,
  buildDraftChanges,
  isDirty,
  hasBlockingErrors
})

onMounted(() => {
  emit('state-change', { isDirty: isDirty.value, hasBlockingErrors: hasBlockingErrors.value })
  document.addEventListener('click', handleGlobalClick)
})
</script>

<template>
  <div v-if="node" class="prop-editor">
    <div class="prop-editor__header">
      <div class="prop-editor__title">Properties</div>
      <button class="prop-editor__add" :disabled="disabled" @click="addRow">+ Add</button>
    </div>

    <div v-if="hasBlockingErrors" class="prop-editor__alert error">
      Property 입력 오류가 있습니다. (중복 name / name·type 필수)
    </div>

    <div class="prop-editor__table-wrap">
      <table class="prop-editor__table">
        <thead>
          <tr>
            <th class="col-name">name</th>
            <th class="col-display-name">표시 이름</th>
            <th class="col-type">type</th>
            <th class="col-desc">description</th>
            <th class="col-badges">속성</th>
            <th class="col-actions"></th>
          </tr>
        </thead>
        <tbody>
          <tr 
            v-for="(row, rowIndex) in visibleRows" 
            :key="row.id"
            class="prop-row"
            :class="{ 'prop-row--readonly': row.isReadOnly }"
          >
            <!-- Name (technical) -->
            <td>
              <input
                v-if="!row.isReadOnly"
                class="prop-input"
                type="text"
                v-model="row.name"
                :disabled="disabled"
                placeholder="ex) orderId"
                @keydown="handleRowKeydown($event, row, rowIndex)"
              />
              <span v-else class="prop-readonly">{{ row.name }}</span>
              <div v-if="!row.isReadOnly && rowIssues[row.id]?.errors?.length" class="prop-issue error">
                {{ rowIssues[row.id].errors[0] }}
              </div>
              <div v-else-if="!row.isReadOnly && rowIssues[row.id]?.warnings?.length" class="prop-issue warn">
                {{ rowIssues[row.id].warnings[0] }}
              </div>
            </td>

            <!-- Display name (UI label) -->
            <td class="col-display-name">
              <input
                v-if="!row.isReadOnly"
                class="prop-input"
                type="text"
                v-model="row.displayName"
                :disabled="disabled"
                placeholder="UI 라벨"
                @keydown="handleRowKeydown($event, row, rowIndex)"
              />
              <span v-else class="prop-readonly">{{ terminologyStore.ubiquitousLanguageMode ? (row.displayName || row.name) : row.name }}</span>
            </td>

            <!-- Type (Combobox) -->
            <td>
              <div v-if="!row.isReadOnly" class="prop-combobox">
                <input
                  class="prop-input prop-combobox__input"
                  type="text"
                  v-model="row.type"
                  :disabled="disabled"
                  placeholder="String"
                  @focus="typeDropdown.openRowId = row.id"
                  @keydown="handleRowKeydown($event, row, rowIndex)"
                />
                <button
                  class="prop-combobox__toggle"
                  :disabled="disabled"
                  @click.stop="toggleTypeDropdown(row.id)"
                  v-html="IconChevronDown"
                  aria-label="Type 선택"
                ></button>
                <div 
                  v-if="typeDropdown.openRowId === row.id" 
                  class="prop-combobox__dropdown"
                >
                  <div
                    v-for="t in TYPE_OPTIONS"
                    :key="t"
                    class="prop-combobox__option"
                    :class="{ active: row.type === t }"
                    @mousedown.prevent="selectType(row, t)"
                  >
                    {{ t }}
                  </div>
                </div>
              </div>
              <span v-else class="prop-readonly">{{ row.type }}</span>
            </td>

            <!-- Description (preview + edit button) -->
            <td>
              <div class="prop-desc-cell">
                <span 
                  class="prop-desc-preview" 
                  :title="row.description || '(설명 없음)'"
                >{{ truncateDesc(row.description) }}</span>
                <button
                  v-if="!row.isReadOnly"
                  class="prop-icon-btn prop-action"
                  :disabled="disabled"
                  @click="openDescPopover(row, $event)"
                  v-html="IconEdit"
                  aria-label="설명 편집"
                  title="설명 편집"
                ></button>
              </div>
            </td>

            <!-- Badges (Key, FK, Req, Enum, VO) -->
            <td>
              <div class="prop-badges">
                <!-- Read-only badges for Enum/VO -->
                <span v-if="row.fieldType === 'enum'" class="prop-badge prop-badge--enum-readonly">Enum</span>
                <span v-if="row.fieldType === 'valueObject'" class="prop-badge prop-badge--vo-readonly">
                  VO<span v-if="row.referencedAggregateName"> (→ {{ row.referencedAggregateName }})</span>
                </span>
                
                <!-- Editable badges for properties -->
                <template v-if="!row.isReadOnly">
                <button
                  class="prop-badge"
                  :class="{ 'prop-badge--key': row.isKey }"
                  :disabled="disabled"
                  @click="toggleKey(row)"
                  title="Primary Key"
                >
                  <span class="prop-badge__icon" v-html="IconKey"></span>
                  <span class="prop-badge__label">Key</span>
                </button>
                <button
                  class="prop-badge"
                  :class="{ 'prop-badge--fk': row.isForeignKey }"
                  :disabled="disabled"
                  @click="toggleFK(row)"
                  title="Foreign Key"
                >
                  <span class="prop-badge__icon" v-html="IconLink"></span>
                  <span class="prop-badge__label">FK</span>
                </button>
                <button
                  class="prop-badge"
                  :class="{ 'prop-badge--req': row.isRequired, 'prop-badge--locked': row.isKey }"
                  :disabled="disabled || row.isKey"
                  @click="toggleReq(row)"
                  title="Required"
                >
                  <span class="prop-badge__icon" v-html="IconCheck"></span>
                  <span class="prop-badge__label">Req</span>
                </button>
                </template>
              </div>
            </td>

            <!-- Delete (trash icon) -->
            <td class="center">
              <button
                v-if="!row.isReadOnly"
                class="prop-icon-btn prop-icon-btn--delete prop-action"
                :disabled="disabled"
                @click="openDeleteConfirm(row)"
                v-html="IconTrash"
                aria-label="Delete property"
                title="삭제"
              ></button>
            </td>
          </tr>

          <!-- Empty state -->
          <tr v-if="visibleRows.length === 0">
            <td class="prop-empty" colspan="5">
              <div class="prop-empty__icon" v-html="IconClipboard"></div>
              <div class="prop-empty__text">아직 속성이 없습니다</div>
              <button 
                class="prop-empty__btn" 
                :disabled="disabled" 
                @click="addRow"
              >
                + 첫 번째 속성 추가하기
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Description Popover -->
    <Teleport to="body">
      <div 
        v-if="descPopover.open" 
        class="prop-popover__backdrop"
        @click="closeDescPopover"
      >
        <div 
          class="prop-popover"
          :style="{ top: descPopover.position.top + 'px', left: descPopover.position.left + 'px' }"
          @click.stop
        >
          <div class="prop-popover__header">
            <span>설명 편집</span>
            <button class="prop-popover__close" @click="closeDescPopover">×</button>
          </div>
          <textarea
            ref="descTextareaRef"
            class="prop-popover__textarea"
            v-model="descPopover.value"
            placeholder="속성에 대한 설명을 입력하세요..."
            rows="4"
            @keydown="handleDescKeydown"
            @blur="closeDescPopover"
          ></textarea>
          <div class="prop-popover__hint">Escape로 닫기 (자동 저장)</div>
        </div>
      </div>
    </Teleport>

    <!-- Delete confirm modal -->
    <div v-if="state.confirmDelete.open" class="prop-modal__backdrop">
      <div class="prop-modal">
        <div class="prop-modal__header">
          <div class="prop-modal__title">{{ deleteModalTitle }}</div>
          <button class="prop-modal__close" @click="closeDeleteConfirm">×</button>
        </div>

        <div class="prop-modal__body">
          <div v-if="deleteModalBody?.message" class="prop-modal__message">
            {{ deleteModalBody.message }}
          </div>

          <div v-else class="prop-modal__refs">
            <div class="prop-modal__hint">
              아래 CQRS 참조가 있어 삭제 시 일부 CQRS 설정이 깨질 수 있습니다. (자동 정리 없음)
            </div>
            <div v-for="[rm, items] in groupedRefs" :key="rm" class="prop-modal__rm">
              <div class="prop-modal__rm-title">{{ rm }}</div>
              <ul class="prop-modal__list">
                <li v-for="it in items" :key="it.refId" class="prop-modal__item">
                  <span class="tag">{{ it.refType }}</span>
                  <span class="tag">{{ it.role }}</span>
                  <span class="mono">ref={{ it.refId }}</span>
                  <span class="mono">op={{ it.operationType }} ({{ it.operationId }})</span>
                  <span v-if="it.triggerEventName" class="mono">evt={{ it.triggerEventName }}</span>
                  <span v-if="it.refType === 'mapping'" class="mono">
                    {{ it.sourcePropertyName || 'null' }} → {{ it.targetPropertyName || 'null' }}
                  </span>
                  <span v-else class="mono">
                    {{ it.sourceEventFieldName || 'null' }} {{ it.operator || '=' }} {{ it.targetPropertyName || 'null' }}
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div class="prop-modal__footer">
          <button class="btn" @click="closeDeleteConfirm">취소</button>
          <button class="btn danger" @click="forceDeleteConfirmed">삭제 강행</button>
        </div>
      </div>
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

.col-name { width: 20%; }
.col-display-name { width: 18%; }
.col-type { width: 16%; }
.col-desc { width: 22%; }
.col-badges { width: 18%; }
.col-actions { width: 8%; }

.center {
  text-align: center;
}

/* Row hover effect */
.prop-row {
  transition: background 0.15s ease;
}
.prop-row:hover {
  background: var(--color-bg-tertiary);
}
.prop-row--readonly {
  background: var(--color-bg-tertiary);
  opacity: 0.9;
}
.prop-row--readonly:hover {
  background: var(--color-bg-tertiary);
}

/* Hover actions - show on row hover */
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

.prop-readonly {
  display: inline-block;
  padding: 4px 6px;
  font-size: 0.65rem;
  color: var(--color-text);
  font-weight: 500;
}

.prop-issue {
  margin-top: 4px;
  font-size: 0.6rem;
  line-height: 1.2;
}
.prop-issue.error {
  color: #ff6b6b;
}
.prop-issue.warn {
  color: #fcc419;
}

/* ============================================
   Combobox
   ============================================ */
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

/* ============================================
   Description cell
   ============================================ */
.prop-desc-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.prop-desc-preview {
  flex: 1;
  color: var(--color-text-light);
  font-size: 0.62rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ============================================
   Icon Button
   ============================================ */
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

/* ============================================
   Toggle Badges
   ============================================ */
.prop-badges {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.prop-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text-light);
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 0.58rem;
  cursor: pointer;
  transition: all 0.15s ease;
  opacity: 0.6;
}
.prop-badge:hover:not(:disabled) {
  opacity: 1;
  border-color: var(--color-text-light);
}
.prop-badge:disabled {
  cursor: not-allowed;
}

.prop-badge__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.prop-badge__label {
  font-weight: 500;
}

/* Key active */
.prop-badge--key {
  background: rgba(252, 196, 25, 0.2);
  border-color: #fcc419;
  color: #fcc419;
  opacity: 1;
}

/* FK active */
.prop-badge--fk {
  background: rgba(92, 124, 250, 0.2);
  border-color: #5c7cfa;
  color: #5c7cfa;
  opacity: 1;
}

/* Req active */
.prop-badge--req {
  background: rgba(255, 107, 107, 0.2);
  border-color: #ff6b6b;
  color: #ff6b6b;
  opacity: 1;
}

/* Req locked (when isKey is true) */
.prop-badge--locked {
  opacity: 0.7;
}

/* Read-only badges for Enum/VO */
.prop-badge--enum-readonly {
  background: rgba(92, 124, 250, 0.2);
  border-color: #5c7cfa;
  color: #5c7cfa;
  opacity: 1;
  cursor: default;
}

.prop-badge--vo-readonly {
  background: rgba(64, 192, 87, 0.2);
  border-color: #40c057;
  color: #40c057;
  opacity: 1;
  cursor: default;
}

.prop-badge--ref-readonly {
  background: rgba(253, 126, 20, 0.2);
  border-color: #fd7e14;
  color: #fd7e14;
  opacity: 1;
  cursor: default;
  font-size: 0.6rem;
}

/* ============================================
   Empty State
   ============================================ */
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

/* ============================================
   Description Popover
   ============================================ */
.prop-popover__backdrop {
  position: fixed;
  inset: 0;
  z-index: 9998;
}

.prop-popover {
  position: fixed;
  width: 280px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 9999;
}

.prop-popover__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-border);
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.prop-popover__close {
  border: none;
  background: transparent;
  color: var(--color-text-light);
  font-size: 1rem;
  cursor: pointer;
  padding: 0 4px;
}
.prop-popover__close:hover {
  color: var(--color-text);
}

.prop-popover__textarea {
  width: 100%;
  border: none;
  background: var(--color-bg);
  color: var(--color-text);
  padding: 10px;
  font-size: 0.68rem;
  font-family: inherit;
  resize: vertical;
  min-height: 80px;
}
.prop-popover__textarea:focus {
  outline: none;
}

.prop-popover__hint {
  padding: 6px 10px;
  font-size: 0.58rem;
  color: var(--color-text-light);
  border-top: 1px solid var(--color-border);
}

/* ============================================
   Modal (unchanged)
   ============================================ */
.prop-modal__backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.prop-modal {
  width: min(720px, 92vw);
  max-height: 82vh;
  overflow: hidden;
  border-radius: 10px;
  border: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
}

.prop-modal__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-tertiary);
}

.prop-modal__title {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-text-bright);
}

.prop-modal__close {
  border: none;
  background: transparent;
  color: var(--color-text-light);
  font-size: 1.1rem;
  cursor: pointer;
}

.prop-modal__body {
  padding: 12px;
  overflow: auto;
  max-height: calc(82vh - 110px);
}

.prop-modal__message {
  white-space: pre-wrap;
  font-size: 0.7rem;
  color: var(--color-text);
}

.prop-modal__hint {
  font-size: 0.65rem;
  color: var(--color-text-light);
  margin-bottom: 10px;
}

.prop-modal__rm {
  margin-bottom: 12px;
}

.prop-modal__rm-title {
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--color-text-bright);
  margin-bottom: 6px;
}

.prop-modal__list {
  margin: 0;
  padding-left: 18px;
}

.prop-modal__item {
  font-size: 0.65rem;
  color: var(--color-text);
  margin-bottom: 4px;
}

.tag {
  display: inline-block;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  padding: 1px 6px;
  border-radius: 999px;
  margin-right: 6px;
  font-size: 0.6rem;
  color: var(--color-text-light);
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 0.62rem;
  color: var(--color-text-light);
  margin-left: 6px;
}

.prop-modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-tertiary);
}

.btn {
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 0.65rem;
  cursor: pointer;
}
.btn.danger {
  border-color: rgba(255, 107, 107, 0.35);
  background: rgba(255, 107, 107, 0.15);
  color: #ff6b6b;
}
</style>
