<script setup>
import { ref, computed, watch } from 'vue'
import { useAggregateViewerStore } from '@/features/canvas/aggregateViewer.store'
import { useTerminologyStore } from '@/features/terminology/terminology.store'
import PropertyEditorTable from './inspectors/PropertyEditorTable.vue'
import EnumItemsTable from './inspectors/EnumItemsTable.vue'
import VoFieldsTable from './inspectors/VoFieldsTable.vue'

const props = defineProps({
  aggregateId: String,
  enumIndex: Number,
  voIndex: Number,
})

const emit = defineEmits(['close'])

const store = useAggregateViewerStore()
const terminologyStore = useTerminologyStore()

// Get current aggregate data
const aggregateData = computed(() => {
  if (!props.aggregateId) return null
  const result = store.getAggregateById(props.aggregateId)
  return result?.aggregate || null
})

// Current editing target
const editingEnum = computed(() => {
  if (props.enumIndex === null || props.enumIndex === undefined) return null
  return aggregateData.value?.enumerations?.[props.enumIndex] || null
})

const editingVo = computed(() => {
  if (props.voIndex === null || props.voIndex === undefined) return null
  return aggregateData.value?.valueObjects?.[props.voIndex] || null
})

// Enum items editing
const enumItems = ref([])
const enumItemsTableRef = ref(null)
const enumItemsHasErrors = ref(false)

watch(editingEnum, (enumItem) => {
  if (enumItem) {
    enumItems.value = [...(enumItem.items || [])]
  }
}, { immediate: true })

watch(() => enumItemsTableRef.value?.hasBlockingErrors, (hasErrors) => {
  enumItemsHasErrors.value = hasErrors || false
}, { immediate: true })

async function saveEnumItems() {
  if (!editingEnum.value || !props.aggregateId) return
  if (enumItemsHasErrors.value) {
    alert('Item 입력 오류를 수정한 뒤 저장하세요.')
    return
  }
  
  const updatedEnumerations = [...(aggregateData.value.enumerations || [])]
  updatedEnumerations[props.enumIndex] = {
    ...editingEnum.value,
    items: [...enumItems.value],
  }
  
  await store.updateAggregateEnumVo(
    props.aggregateId,
    updatedEnumerations,
    aggregateData.value.valueObjects
  )
  
  alert('저장되었습니다.')
}

// VO fields editing
const voFields = ref([])
const voFieldsTableRef = ref(null)
const voFieldsHasErrors = ref(false)
const voReferencedAggregateName = ref(null)
const voReferencedAggregateField = ref(null)

// Get all aggregates for reference selection
const allAggregatesForReference = computed(() => {
  return store.boundedContexts.flatMap(bc => 
    (bc.aggregates || []).map(agg => ({
      id: agg.id,
      name: agg.name,
      bcName: bc.name,
      properties: agg.properties || []
    }))
  )
})

// Get properties of selected referenced aggregate
const referencedAggregateProperties = computed(() => {
  if (!voReferencedAggregateName.value) return []
  const selectedAgg = allAggregatesForReference.value.find(
    agg => agg.name === voReferencedAggregateName.value
  )
  return selectedAgg?.properties || []
})

watch(editingVo, (vo) => {
  if (vo) {
    voFields.value = (vo.fields || []).map(f => ({
      name: String(f?.name || ''),
      type: String(f?.type || '')
    }))
    voReferencedAggregateName.value = vo.referencedAggregateName || null
    voReferencedAggregateField.value = vo.referencedAggregateField || null
  }
}, { immediate: true })

// Reset field selection when aggregate changes
watch(voReferencedAggregateName, (newName) => {
  if (!newName) {
    voReferencedAggregateField.value = null
  }
  // Check if current field is still valid
  if (voReferencedAggregateField.value) {
    const props = referencedAggregateProperties.value
    const fieldExists = props.some(p => p.name === voReferencedAggregateField.value)
    if (!fieldExists) {
      voReferencedAggregateField.value = null
    }
  }
})

watch(() => voFieldsTableRef.value?.hasBlockingErrors, (hasErrors) => {
  voFieldsHasErrors.value = hasErrors || false
}, { immediate: true })

async function saveVoFields() {
  if (!editingVo.value || !props.aggregateId) return
  if (voFieldsHasErrors.value) {
    alert('Field 입력 오류를 수정한 뒤 저장하세요.')
    return
  }
  
  const updatedValueObjects = [...(aggregateData.value.valueObjects || [])]
  updatedValueObjects[props.voIndex] = {
    ...editingVo.value,
    fields: [...voFields.value],
    referencedAggregateName: voReferencedAggregateName.value || null,
    referencedAggregateField: voReferencedAggregateField.value || null,
  }
  
  await store.updateAggregateEnumVo(
    props.aggregateId,
    aggregateData.value.enumerations,
    updatedValueObjects
  )
  
  alert('저장되었습니다.')
}

// Aggregate-level editing
const editingEnumerations = ref([])
const editingValueObjects = ref([])

watch(aggregateData, (agg) => {
  if (agg) {
    editingEnumerations.value = JSON.parse(JSON.stringify(agg.enumerations || []))
    editingValueObjects.value = JSON.parse(JSON.stringify(agg.valueObjects || []))
  }
}, { immediate: true, deep: true })

async function saveAggregateEnumVo() {
  if (!props.aggregateId) return
  
  await store.updateAggregateEnumVo(
    props.aggregateId,
    editingEnumerations.value,
    editingValueObjects.value
  )
}

function addEnumeration() {
  editingEnumerations.value.push({
    name: '',
    alias: '',
    items: [],
  })
}

function removeEnumeration(index) {
  editingEnumerations.value.splice(index, 1)
}

function addValueObject() {
  editingValueObjects.value.push({
    name: '',
    alias: '',
    referencedAggregateName: null,
    fields: [],
  })
}

function removeValueObject(index) {
  editingValueObjects.value.splice(index, 1)
}

// PropertyEditorTable integration
const propertyEditorRef = ref(null)
const isPropertyDirty = ref(false)
const propertyHasBlockingErrors = ref(false)

// Create a node-like object for PropertyEditorTable
const aggregateNodeForPropertyEditor = computed(() => {
  if (!aggregateData.value) return null
  return {
    id: aggregateData.value.id,
    data: {
      type: 'Aggregate',
      name: aggregateData.value.name,
      properties: aggregateData.value.properties || [],
      enumerations: aggregateData.value.enumerations || [],
      valueObjects: aggregateData.value.valueObjects || [],
    }
  }
})

function onPropertyEditorStateChange(state) {
  isPropertyDirty.value = state?.isDirty || false
  propertyHasBlockingErrors.value = state?.hasBlockingErrors || false
}

async function saveAggregateProperties() {
  if (!aggregateData.value || !propertyEditorRef.value) return
  if (propertyHasBlockingErrors.value) {
    alert('Property 입력 오류를 수정한 뒤 저장하세요.')
    return
  }
  
  // Get draft changes from PropertyEditorTable
  const propRes = propertyEditorRef.value?.buildDraftChanges?.() || { drafts: [], errors: [] }
  if (propRes.errors?.length) {
    alert(propRes.errors.join('\n'))
    return
  }
  
  const drafts = propRes.drafts || []
  if (!drafts.length) return
  
  try {
    // Use model_modifier API (same as Design viewer)
    const response = await fetch('/api/chat/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        drafts: drafts,
        approvedChangeIds: drafts.map(c => c.changeId)
      })
    })
    
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data?.detail || `API error: ${response.status}`)
    }
    
    const data = await response.json()
    if (!data?.success) {
      const reason = Array.isArray(data?.errors) && data.errors.length 
        ? data.errors.join('\n') 
        : '알 수 없는 오류'
      throw new Error(reason)
    }
    
    // Refresh aggregate data
    await store.fetchAllAggregates()
    
    // Reset PropertyEditorTable state
    propertyEditorRef.value?.resetFromNode?.(aggregateNodeForPropertyEditor.value)
    
    alert('저장되었습니다.')
  } catch (err) {
    console.error('Failed to save properties:', err)
    alert(`저장 실패: ${err.message || String(err)}`)
  }
}
</script>

<template>
  <div class="aggregate-viewer-inspector">
    <div class="inspector-header">
      <h3 class="inspector-title">
        <span v-if="editingEnum">Edit Enumeration</span>
        <span v-else-if="editingVo">Edit Value Object</span>
        <span v-else-if="aggregateData">Edit Aggregate</span>
        <span v-else>Inspector</span>
      </h3>
      <button class="inspector-close" @click="emit('close')">×</button>
    </div>

    <div class="inspector-content">
      <!-- Enum Editor -->
      <div v-if="editingEnum" class="inspector-section">
        <div class="section-header">
          <h4>{{ editingEnum.name }}</h4>
        </div>
        
        <div class="form-group">
          <label>Name</label>
          <input v-model="editingEnum.name" type="text" class="form-input" />
        </div>
        
        <div class="form-group">
          <label>Alias</label>
          <input v-model="editingEnum.alias" type="text" class="form-input" />
        </div>

        <!-- Items Editor (using EnumItemsTable) -->
        <EnumItemsTable
          ref="enumItemsTableRef"
          v-model:items="enumItems"
          :disabled="false"
        />
        
        <div class="inspector-actions">
          <button 
            class="btn-save" 
            @click="saveEnumItems" 
            :disabled="enumItemsHasErrors"
          >
            Save Items
          </button>
        </div>
      </div>

      <!-- Value Object Editor -->
      <div v-else-if="editingVo" class="inspector-section">
        <div class="section-header">
          <h4>{{ editingVo.name }}</h4>
        </div>
        
        <div class="form-group">
          <label>Name</label>
          <input v-model="editingVo.name" type="text" class="form-input" />
        </div>
        
        <div class="form-group">
          <label>Alias</label>
          <input v-model="editingVo.alias" type="text" class="form-input" />
        </div>

        <div class="form-group">
          <label>Referenced Aggregate</label>
          <select 
            v-model="voReferencedAggregateName" 
            class="form-input"
          >
            <option :value="null">None (no reference)</option>
            <option 
              v-for="agg in allAggregatesForReference" 
              :key="agg.id" 
              :value="agg.name"
            >
              {{ agg.name }} ({{ agg.bcName }})
            </option>
          </select>
        </div>

        <div v-if="voReferencedAggregateName" class="form-group">
          <label>Referenced Field</label>
          <select 
            v-model="voReferencedAggregateField" 
            class="form-input"
          >
            <option :value="null">None (reference aggregate only)</option>
            <option 
              v-for="prop in referencedAggregateProperties" 
              :key="prop.id || prop.name" 
              :value="prop.name"
            >
              {{ terminologyStore.ubiquitousLanguageMode ? (prop.displayName || prop.name) : prop.name }}: {{ prop.type }}
            </option>
          </select>
          <small class="form-help-text">
            Select which field in the referenced aggregate this VO references
          </small>
        </div>

        <!-- Fields Editor (using VoFieldsTable) -->
        <VoFieldsTable
          ref="voFieldsTableRef"
          v-model:fields="voFields"
          :disabled="false"
        />
        
        <div class="inspector-actions">
          <button 
            class="btn-save" 
            @click="saveVoFields" 
            :disabled="voFieldsHasErrors"
          >
            Save Fields
          </button>
        </div>
      </div>

      <!-- Aggregate Editor -->
      <div v-else-if="aggregateData" class="inspector-section">
        <div class="section-header">
          <h4>{{ terminologyStore.ubiquitousLanguageMode ? (aggregateData.displayName || aggregateData.name) : aggregateData.name }}</h4>
          <span class="section-subtitle">{{ aggregateData.rootEntity }}</span>
        </div>

        <!-- Properties Editor (using PropertyEditorTable) -->
        <PropertyEditorTable
          ref="propertyEditorRef"
          :node="aggregateNodeForPropertyEditor"
          :disabled="false"
          @state-change="onPropertyEditorStateChange"
        />
        
        <div class="inspector-actions">
          <button 
            class="btn-save" 
            @click="saveAggregateProperties" 
            :disabled="!isPropertyDirty || propertyHasBlockingErrors"
          >
            Save Properties
          </button>
        </div>

        <!-- Enumerations -->
        <div class="form-group">
          <div class="form-group-header">
            <label>Enumerations</label>
            <button class="btn-add-small" @click="addEnumeration">+ Add</button>
          </div>
          <div v-for="(enumItem, idx) in editingEnumerations" :key="idx" class="item-row">
            <span class="item-value">{{ terminologyStore.ubiquitousLanguageMode ? (enumItem.displayName || enumItem.name || '(unnamed)') : (enumItem.name || '(unnamed)') }}</span>
            <button class="item-remove" @click="removeEnumeration(idx)">×</button>
          </div>
        </div>

        <!-- Value Objects -->
        <div class="form-group">
          <div class="form-group-header">
            <label>Value Objects</label>
            <button class="btn-add-small" @click="addValueObject">+ Add</button>
          </div>
          <div v-for="(vo, idx) in editingValueObjects" :key="idx" class="item-row">
            <span class="item-value">
              {{ terminologyStore.ubiquitousLanguageMode ? (vo.displayName || vo.name || '(unnamed)') : (vo.name || '(unnamed)') }}
              <span v-if="vo.referencedAggregateName" class="item-ref">→ {{ vo.referencedAggregateName }}</span>
            </span>
            <button class="item-remove" @click="removeValueObject(idx)">×</button>
          </div>
        </div>

        <button class="btn-save" @click="saveAggregateEnumVo">Save Enum/VO Changes</button>
      </div>

      <!-- Empty state -->
      <div v-else class="inspector-empty">
        <p>Select a node to edit</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.aggregate-viewer-inspector {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #252836;
  color: var(--color-text-bright);
}

.inspector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #373a40;
}

.inspector-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.inspector-close {
  background: none;
  border: none;
  color: var(--color-text-light);
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
}

.inspector-close:hover {
  background: rgba(255, 255, 255, 0.1);
}

.inspector-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.inspector-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-header {
  margin-bottom: 8px;
}

.section-header h4 {
  margin: 0 0 4px;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.section-subtitle {
  font-size: 0.85rem;
  color: var(--color-text-light);
  font-style: italic;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-group label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--color-text-light);
  margin-bottom: 4px;
}

.form-input {
  padding: 8px 12px;
  background: #1e1e2e;
  border: 1px solid #373a40;
  border-radius: 6px;
  color: var(--color-text-bright);
  font-size: 0.9rem;
}

.form-input:focus {
  outline: none;
  border-color: var(--color-aggregate);
}

select.form-input {
  cursor: pointer;
}

.form-help-text {
  display: block;
  margin-top: 4px;
  font-size: 0.75rem;
  color: var(--color-text-light);
  font-style: italic;
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.item-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #1e1e2e;
  border: 1px solid #373a40;
  border-radius: 6px;
}

.item-value {
  font-size: 0.9rem;
  color: var(--color-text-bright);
}

.item-ref {
  font-size: 0.8rem;
  color: #5c7cfa;
  margin-left: 8px;
}

.item-remove {
  background: none;
  border: none;
  color: var(--color-text-light);
  font-size: 20px;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
}

.item-remove:hover {
  background: rgba(255, 0, 0, 0.1);
  color: #ff6b6b;
}

.item-add {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.item-add .form-input {
  flex: 1;
}

.btn-add,
.btn-add-small {
  padding: 6px 12px;
  background: var(--color-aggregate);
  color: #1e1e2e;
  border: none;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}

.btn-add-small {
  padding: 4px 8px;
  font-size: 0.75rem;
}

.btn-add:hover,
.btn-add-small:hover {
  opacity: 0.9;
}

.btn-save {
  padding: 10px 16px;
  background: #40c057;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  margin-top: 8px;
}

.btn-save:hover {
  background: #37b24d;
}

.inspector-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--color-text-light);
}

.property-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  background: #1e1e2e;
  border: 1px solid #373a40;
  border-radius: 6px;
  margin-bottom: 8px;
}

.property-fields {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.property-input {
  width: 100%;
}

.property-checkboxes {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.8rem;
  color: var(--color-text-light);
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  cursor: pointer;
}

.empty-state {
  padding: 12px;
  text-align: center;
  color: var(--color-text-light);
  font-size: 0.85rem;
  font-style: italic;
}

.inspector-actions {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #373a40;
}
</style>
