<script setup>
import { ref, computed, watch } from 'vue'
import { createLogger, newOpId } from '@/app/logging/logger'

const props = defineProps({
  enabled: {
    type: Boolean,
    default: true
  },
  readModelId: String,
  readModelData: Object
})

const emit = defineEmits(['updated'])
const log = createLogger({ scope: 'ReadModelCQRSEditor' })

// Loading & Error state
const loading = ref(false)
const error = ref(null)
const saving = ref(false)

// Provisioning type selection (UI only; persistence is handled by Inspector change-apply)
const provisioningType = ref('CQRS')
const provisioningOptions = [
  { value: 'CQRS', label: 'CQRS', description: 'Materialized View로 복제' },
  { value: 'API', label: 'UI Mashup', description: 'API 직접 호출' },
  { value: 'GraphQL', label: 'GraphQL', description: 'GraphQL Federation' },
  { value: 'SharedDB', label: 'Shared DB', description: 'View/Join 사용' }
]

// CQRS Configuration from Graph
const cqrsConfig = ref(null)
const operations = ref([])

// Available events and ReadModel properties
const availableEvents = ref([])
const readModelProperties = ref([])

// New operation form state
const showAddOperation = ref(false)
const newOperationType = ref('INSERT')
const newOperationEventId = ref('')

watch(
  () => [props.enabled, props.readModelId],
  async ([enabled, id]) => {
    if (enabled && id) {
      await loadData()
    }
  },
  { immediate: true }
)

async function loadData() {
  if (!props.readModelId) return
  const opId = newOpId('cqrsLoad')
  loading.value = true
  error.value = null

  try {
    log.info('cqrs_load_start', 'Loading CQRS editor data.', {
      opId,
      readModelId: props.readModelId,
      readModelData: props.readModelData
    })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_load_start]', {
      opId,
      readModelId: props.readModelId,
      readModelData: props.readModelData
    })

    const [eventsRes, propsRes, configRes] = await Promise.all([
      fetch(`/api/readmodel/${props.readModelId}/cqrs/events`),
      fetch(`/api/readmodel/${props.readModelId}/properties`),
      fetch(`/api/readmodel/${props.readModelId}/cqrs`)
    ])

    log.info('cqrs_load_http', 'CQRS editor HTTP responses received.', {
      opId,
      responses: {
        events: { ok: eventsRes.ok, status: eventsRes.status, statusText: eventsRes.statusText },
        properties: { ok: propsRes.ok, status: propsRes.status, statusText: propsRes.statusText },
        config: { ok: configRes.ok, status: configRes.status, statusText: configRes.statusText }
      }
    })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_load_http]', {
      opId,
      events: eventsRes,
      properties: propsRes,
      config: configRes
    })

    if (!eventsRes.ok || !propsRes.ok || !configRes.ok) {
      throw new Error('CQRS API not available')
    }

    availableEvents.value = await eventsRes.json()
    readModelProperties.value = await propsRes.json()
    cqrsConfig.value = await configRes.json()

    operations.value = cqrsConfig.value?.operations || []
    provisioningType.value = props.readModelData?.provisioningType || 'CQRS'

    log.info('cqrs_load_done', 'CQRS editor data loaded.', {
      opId,
      availableEvents: availableEvents.value,
      readModelProperties: readModelProperties.value,
      cqrsConfig: cqrsConfig.value,
      operations: operations.value,
      provisioningType: provisioningType.value
    })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_load_done]', {
      opId,
      availableEvents: availableEvents.value,
      readModelProperties: readModelProperties.value,
      cqrsConfig: cqrsConfig.value,
      operations: operations.value,
      provisioningType: provisioningType.value
    })
  } catch (e) {
    error.value = 'Failed to load CQRS configuration'
    log.error('cqrs_load_error', 'Failed to load CQRS editor data.', {
      opId,
      readModelId: props.readModelId,
      error: String(e)
    })
    console.error('Error loading CQRS config:', e)
    console.error('[RAW][ReadModelCQRSEditor][cqrs_load_error]', { opId, error: e })
  } finally {
    loading.value = false
  }
}

function getEventById(eventId) {
  return availableEvents.value.find((e) => e.id === eventId)
}

function getEventProperties(eventId) {
  const event = getEventById(eventId)
  return event?.properties || []
}

async function addOperation() {
  if (!newOperationEventId.value) return

  const opId = newOpId('cqrsAddOp')
  saving.value = true
  try {
    const requestBody = {
      operation_type: newOperationType.value,
      trigger_event_id: newOperationEventId.value
    }
    log.info('cqrs_add_operation_request', 'Adding CQRS operation.', {
      opId,
      readModelId: props.readModelId,
      requestBody
    })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_add_operation_request]', { opId, readModelId: props.readModelId, requestBody })

    const response = await fetch(`/api/readmodel/${props.readModelId}/cqrs/operations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    })

    const body = await response.json().catch(() => null)
    log.info('cqrs_add_operation_response', 'CQRS operation add response.', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: body
    })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_add_operation_response]', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: body
    })

    if (response.ok) {
      const newOp = body
      operations.value.push({
        ...newOp,
        triggerEventName: getEventById(newOperationEventId.value)?.name,
        mappings: [],
        whereConditions: []
      })

      showAddOperation.value = false
      newOperationType.value = 'INSERT'
      newOperationEventId.value = ''

      emit('updated')
    }
  } catch (e) {
    log.error('cqrs_add_operation_error', 'Failed to add CQRS operation.', { opId, error: String(e) })
    console.error('Error adding operation:', e)
    console.error('[RAW][ReadModelCQRSEditor][cqrs_add_operation_error]', { opId, error: e })
  } finally {
    saving.value = false
  }
}

async function deleteOperation(operationId, index) {
  if (!confirm('이 작업과 관련된 모든 매핑을 삭제하시겠습니까?')) return

  const opId = newOpId('cqrsDelOp')
  saving.value = true
  try {
    log.info('cqrs_delete_operation_request', 'Deleting CQRS operation.', { opId, operationId, index })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_delete_operation_request]', { opId, operationId, index })
    const response = await fetch(`/api/cqrs/operation/${operationId}`, {
      method: 'DELETE'
    })

    const body = await response.json().catch(() => null)
    log.info('cqrs_delete_operation_response', 'CQRS operation delete response.', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: body
    })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_delete_operation_response]', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: body
    })

    if (response.ok) {
      operations.value.splice(index, 1)
      emit('updated')
    }
  } catch (e) {
    log.error('cqrs_delete_operation_error', 'Failed to delete CQRS operation.', { opId, operationId, error: String(e) })
    console.error('Error deleting operation:', e)
    console.error('[RAW][ReadModelCQRSEditor][cqrs_delete_operation_error]', { opId, operationId, error: e })
  } finally {
    saving.value = false
  }
}

async function addMapping(operationIndex, sourceType, sourcePropertyId, targetPropertyId, staticValue = null) {
  const operation = operations.value[operationIndex]
  if (!operation || !targetPropertyId) return

  const opId = newOpId('cqrsAddMap')
  saving.value = true
  try {
    const requestBody = {
      target_property_id: targetPropertyId,
      source_property_id: sourceType === 'event' ? sourcePropertyId : null,
      source_type: sourceType,
      static_value: sourceType === 'value' ? staticValue : null
    }
    log.info('cqrs_add_mapping_request', 'Adding CQRS mapping.', {
      opId,
      operationIndex,
      operationId: operation.id,
      requestBody
    })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_add_mapping_request]', { opId, operationIndex, operationId: operation.id, requestBody })

    const response = await fetch(`/api/cqrs/operation/${operation.id}/mappings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    })

    const body = await response.json().catch(() => null)
    log.info('cqrs_add_mapping_response', 'CQRS mapping add response.', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: body
    })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_add_mapping_response]', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: body
    })

    if (response.ok) {
      const newMapping = body

      const targetProp = readModelProperties.value.find((p) => p.id === targetPropertyId)
      const sourceProp =
        sourceType === 'event'
          ? getEventProperties(operation.triggerEventId).find((p) => p.id === sourcePropertyId)
          : null

      if (!operation.mappings) operation.mappings = []
      operation.mappings.push({
        ...newMapping,
        targetPropertyId,
        targetPropertyName: targetProp?.name,
        sourcePropertyId,
        sourcePropertyName: sourceProp?.name,
        staticValue
      })

      emit('updated')
    }
  } catch (e) {
    log.error('cqrs_add_mapping_error', 'Failed to add CQRS mapping.', { opId, error: String(e) })
    console.error('Error adding mapping:', e)
    console.error('[RAW][ReadModelCQRSEditor][cqrs_add_mapping_error]', { opId, error: e })
  } finally {
    saving.value = false
  }
}

async function deleteMapping(operationIndex, mappingId, mappingIndex) {
  const opId = newOpId('cqrsDelMap')
  saving.value = true
  try {
    log.info('cqrs_delete_mapping_request', 'Deleting CQRS mapping.', { opId, operationIndex, mappingId, mappingIndex })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_delete_mapping_request]', { opId, operationIndex, mappingId, mappingIndex })
    const response = await fetch(`/api/cqrs/mapping/${mappingId}`, {
      method: 'DELETE'
    })

    const body = await response.json().catch(() => null)
    log.info('cqrs_delete_mapping_response', 'CQRS mapping delete response.', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: body
    })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_delete_mapping_response]', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: body
    })

    if (response.ok) {
      operations.value[operationIndex].mappings.splice(mappingIndex, 1)
      emit('updated')
    }
  } catch (e) {
    log.error('cqrs_delete_mapping_error', 'Failed to delete CQRS mapping.', { opId, mappingId, error: String(e) })
    console.error('Error deleting mapping:', e)
    console.error('[RAW][ReadModelCQRSEditor][cqrs_delete_mapping_error]', { opId, mappingId, error: e })
  } finally {
    saving.value = false
  }
}

async function addWhereCondition(operationIndex, targetPropertyId, sourceEventFieldId, operator = '=') {
  const operation = operations.value[operationIndex]
  if (!operation || !targetPropertyId || !sourceEventFieldId) return

  const opId = newOpId('cqrsAddWhere')
  saving.value = true
  try {
    const requestBody = {
      target_property_id: targetPropertyId,
      source_event_field_id: sourceEventFieldId,
      operator
    }
    log.info('cqrs_add_where_request', 'Adding CQRS WHERE condition.', {
      opId,
      operationIndex,
      operationId: operation.id,
      requestBody
    })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_add_where_request]', { opId, operationIndex, operationId: operation.id, requestBody })
    const response = await fetch(`/api/cqrs/operation/${operation.id}/where`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    })

    const body = await response.json().catch(() => null)
    log.info('cqrs_add_where_response', 'CQRS WHERE add response.', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: body
    })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_add_where_response]', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: body
    })

    if (response.ok) {
      const newWhere = body

      const targetProp = readModelProperties.value.find((p) => p.id === targetPropertyId)
      const sourceProp = getEventProperties(operation.triggerEventId).find((p) => p.id === sourceEventFieldId)

      if (!operation.whereConditions) operation.whereConditions = []
      operation.whereConditions.push({
        ...newWhere,
        targetPropertyId,
        targetPropertyName: targetProp?.name,
        sourceEventFieldId,
        sourceEventFieldName: sourceProp?.name
      })

      emit('updated')
    }
  } catch (e) {
    log.error('cqrs_add_where_error', 'Failed to add CQRS WHERE condition.', { opId, error: String(e) })
    console.error('Error adding WHERE condition:', e)
    console.error('[RAW][ReadModelCQRSEditor][cqrs_add_where_error]', { opId, error: e })
  } finally {
    saving.value = false
  }
}

async function deleteWhereCondition(operationIndex, whereId, whereIndex) {
  const opId = newOpId('cqrsDelWhere')
  saving.value = true
  try {
    log.info('cqrs_delete_where_request', 'Deleting CQRS WHERE condition.', { opId, operationIndex, whereId, whereIndex })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_delete_where_request]', { opId, operationIndex, whereId, whereIndex })
    const response = await fetch(`/api/cqrs/where/${whereId}`, {
      method: 'DELETE'
    })

    const body = await response.json().catch(() => null)
    log.info('cqrs_delete_where_response', 'CQRS WHERE delete response.', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: body
    })
    console.info('[RAW][ReadModelCQRSEditor][cqrs_delete_where_response]', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: body
    })

    if (response.ok) {
      operations.value[operationIndex].whereConditions.splice(whereIndex, 1)
      emit('updated')
    }
  } catch (e) {
    log.error('cqrs_delete_where_error', 'Failed to delete CQRS WHERE condition.', { opId, whereId, error: String(e) })
    console.error('Error deleting WHERE condition:', e)
    console.error('[RAW][ReadModelCQRSEditor][cqrs_delete_where_error]', { opId, whereId, error: e })
  } finally {
    saving.value = false
  }
}

const newMappingForms = ref({})
function initMappingForm(opIndex) {
  if (!newMappingForms.value[opIndex]) {
    newMappingForms.value[opIndex] = {
      sourceType: 'event',
      sourcePropertyId: '',
      targetPropertyId: '',
      staticValue: ''
    }
  }
  return newMappingForms.value[opIndex]
}

function submitMapping(opIndex) {
  const form = newMappingForms.value[opIndex]
  if (!form?.targetPropertyId) return

  addMapping(opIndex, form.sourceType, form.sourcePropertyId, form.targetPropertyId, form.staticValue)
  newMappingForms.value[opIndex] = {
    sourceType: 'event',
    sourcePropertyId: '',
    targetPropertyId: '',
    staticValue: ''
  }
}

const newWhereForms = ref({})
function initWhereForm(opIndex) {
  if (!newWhereForms.value[opIndex]) {
    newWhereForms.value[opIndex] = {
      targetPropertyId: '',
      sourceEventFieldId: '',
      operator: '='
    }
  }
  return newWhereForms.value[opIndex]
}

function submitWhere(opIndex) {
  const form = newWhereForms.value[opIndex]
  if (!form?.targetPropertyId || !form?.sourceEventFieldId) return

  addWhereCondition(opIndex, form.targetPropertyId, form.sourceEventFieldId, form.operator)
  newWhereForms.value[opIndex] = {
    targetPropertyId: '',
    sourceEventFieldId: '',
    operator: '='
  }
}

const showCqrsConfig = computed(() => provisioningType.value === 'CQRS')

const groupedEvents = computed(() => {
  const groups = {}
  for (const evt of availableEvents.value) {
    const bcName = evt.bcName || 'Unknown'
    if (!groups[bcName]) {
      groups[bcName] = { name: bcName, events: [] }
    }
    groups[bcName].events.push(evt)
  }
  return Object.values(groups)
})
</script>

<template>
  <div class="cqrs-editor">
    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>설정을 불러오는 중...</span>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-state">
      {{ error }}
      <button @click="loadData">다시 시도</button>
    </div>

    <template v-else>
      <!-- Provisioning Type Selection (display only) -->
      <div class="section">
        <h4>데이터 프로비저닝 방식</h4>
        <div class="provisioning-options">
          <label
            v-for="option in provisioningOptions"
            :key="option.value"
            class="provisioning-option"
            :class="{ selected: provisioningType === option.value }"
          >
            <input type="radio" :value="option.value" v-model="provisioningType" />
            <div class="option-content">
              <span class="option-label">{{ option.label }}</span>
              <span class="option-desc">{{ option.description }}</span>
            </div>
          </label>
        </div>
      </div>

      <!-- CQRS Configuration -->
      <div v-if="showCqrsConfig" class="section cqrs-section">
        <div class="section-header">
          <h4>CQRS 오퍼레이션</h4>
          <button class="btn-add" @click="showAddOperation = true" :disabled="saving">
            + 오퍼레이션 추가
          </button>
        </div>

        <!-- Add Operation Form -->
        <div v-if="showAddOperation" class="add-operation-form">
          <div class="form-row">
            <select v-model="newOperationType" class="type-select">
              <option value="INSERT">INSERT</option>
              <option value="UPDATE">UPDATE</option>
              <option value="DELETE">DELETE</option>
            </select>

            <span class="when-label">WHEN</span>

            <select v-model="newOperationEventId" class="event-select">
              <option value="">이벤트 선택</option>
              <optgroup v-for="bc in groupedEvents" :key="bc.name" :label="bc.name">
                <option v-for="evt in bc.events" :key="evt.id" :value="evt.id">
                  {{ evt.name }}
                </option>
              </optgroup>
            </select>

            <button class="btn-confirm" @click="addOperation" :disabled="!newOperationEventId || saving">
              확인
            </button>
            <button class="btn-cancel-form" @click="showAddOperation = false">취소</button>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="operations.length === 0 && !showAddOperation" class="empty-rules">
          CQRS 오퍼레이션이 없습니다. 오퍼레이션을 추가하여 이벤트를 ReadModel에 매핑하세요.
        </div>

        <!-- Operations List -->
        <div
          v-for="(op, opIdx) in operations"
          :key="op.id"
          class="cqrs-operation"
          :class="op.operationType?.toLowerCase()"
        >
          <div class="operation-header">
            <span class="operation-type">{{ op.operationType }}</span>
            <span class="when-text">WHEN</span>
            <span class="event-name">{{ op.triggerEventName || getEventById(op.triggerEventId)?.name }}</span>
            <button class="btn-delete-op" @click="deleteOperation(op.id, opIdx)" :disabled="saving">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path
                  d="m19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
                ></path>
              </svg>
            </button>
          </div>

          <!-- Field Mappings Section -->
          <div class="mapping-section">
            <div class="section-label">SET (필드 매핑)</div>

            <div v-for="(mapping, mapIdx) in op.mappings" :key="mapping.id" class="mapping-row">
              <span class="target-field">{{ mapping.targetPropertyName || '?' }}</span>
              <span class="equals">=</span>
              <span class="source-field" v-if="mapping.sourceType === 'event'">
                event.{{ mapping.sourcePropertyName || '?' }}
              </span>
              <span class="source-field static" v-else>"{{ mapping.staticValue }}"</span>
              <button class="btn-remove-mapping" @click="deleteMapping(opIdx, mapping.id, mapIdx)" :disabled="saving">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>

            <div class="add-mapping-form">
              <select
                :value="initMappingForm(opIdx).targetPropertyId"
                @change="newMappingForms[opIdx].targetPropertyId = $event.target.value"
                class="field-select"
              >
                <option value="">ReadModel 필드</option>
                <option v-for="prop in readModelProperties" :key="prop.id" :value="prop.id">
                  {{ prop.name }} ({{ prop.type }})
                </option>
              </select>

              <span class="equals">=</span>

              <select
                :value="newMappingForms[opIdx]?.sourceType"
                @change="newMappingForms[opIdx].sourceType = $event.target.value"
                class="source-type-select"
              >
                <option value="event">event</option>
                <option value="value">value</option>
              </select>

              <template v-if="newMappingForms[opIdx]?.sourceType === 'event'">
                <select
                  :value="newMappingForms[opIdx]?.sourcePropertyId"
                  @change="newMappingForms[opIdx].sourcePropertyId = $event.target.value"
                  class="field-select"
                >
                  <option value="">Event 필드</option>
                  <option v-for="prop in getEventProperties(op.triggerEventId)" :key="prop.id" :value="prop.id">
                    {{ prop.name }} ({{ prop.type }})
                  </option>
                </select>
              </template>
              <template v-else>
                <input
                  type="text"
                  :value="newMappingForms[opIdx]?.staticValue"
                  @input="newMappingForms[opIdx].staticValue = $event.target.value"
                  class="value-input"
                  placeholder="정적 값"
                />
              </template>

              <button class="btn-add-small" @click="submitMapping(opIdx)" :disabled="saving">+</button>
            </div>
          </div>

          <!-- WHERE Section (for UPDATE/DELETE) -->
          <div v-if="op.operationType !== 'INSERT'" class="where-section">
            <div class="section-label">WHERE (조건)</div>

            <div v-for="(where, whereIdx) in op.whereConditions" :key="where.id" class="where-row">
              <span class="target-field">{{ where.targetPropertyName || '?' }}</span>
              <span class="operator">{{ where.operator }}</span>
              <span class="source-field">event.{{ where.sourceEventFieldName || '?' }}</span>
              <button class="btn-remove-mapping" @click="deleteWhereCondition(opIdx, where.id, whereIdx)" :disabled="saving">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>

            <div class="add-where-form">
              <select
                :value="initWhereForm(opIdx).targetPropertyId"
                @change="newWhereForms[opIdx].targetPropertyId = $event.target.value"
                class="field-select"
              >
                <option value="">ReadModel 필드</option>
                <option v-for="prop in readModelProperties" :key="prop.id" :value="prop.id">
                  {{ prop.name }}
                </option>
              </select>

              <select
                :value="newWhereForms[opIdx]?.operator"
                @change="newWhereForms[opIdx].operator = $event.target.value"
                class="operator-select"
              >
                <option value="=">=</option>
                <option value="!=">!=</option>
                <option value=">">></option>
                <option value="<"><</option>
              </select>

              <select
                :value="newWhereForms[opIdx]?.sourceEventFieldId"
                @change="newWhereForms[opIdx].sourceEventFieldId = $event.target.value"
                class="field-select"
              >
                <option value="">Event 필드</option>
                <option v-for="prop in getEventProperties(op.triggerEventId)" :key="prop.id" :value="prop.id">
                  {{ prop.name }}
                </option>
              </select>

              <button class="btn-add-small" @click="submitWhere(opIdx)" :disabled="saving">+</button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="saving" class="saving-indicator">저장 중...</div>
    </template>
  </div>
</template>

<style scoped>
.cqrs-editor {
  display: block;
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  gap: 12px;
  color: #808080;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #2d2d4d;
  border-top-color: #40c057;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.section {
  margin-bottom: 24px;
}

.section h4 {
  margin: 0 0 12px 0;
  font-size: 0.9rem;
  color: #c0c0c0;
}

.provisioning-options {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.provisioning-option {
  flex: 1;
  min-width: 140px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  background: #252540;
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.provisioning-option:hover {
  background: #2d2d50;
}

.provisioning-option.selected {
  border-color: #40c057;
  background: rgba(64, 192, 87, 0.1);
}

.provisioning-option input {
  margin-top: 2px;
  accent-color: #40c057;
}

.option-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.option-label {
  font-weight: 600;
  color: #e0e0e0;
  font-size: 0.85rem;
}

.option-desc {
  font-size: 0.7rem;
  color: #707090;
}

.cqrs-section {
  background: #1e1e35;
  border-radius: 8px;
  padding: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h4 {
  margin: 0;
}

.btn-add {
  background: linear-gradient(135deg, #40c057 0%, #2f9e44 100%);
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.btn-add:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(64, 192, 87, 0.3);
}

.btn-add:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.add-operation-form {
  background: #252540;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.type-select {
  background: #1a1a2e;
  border: 1px solid #3d3d6d;
  color: #e0e0e0;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 600;
}

.when-label {
  color: #707090;
  font-size: 0.8rem;
}

.event-select {
  flex: 1;
  min-width: 200px;
  background: #1a1a2e;
  border: 1px solid #3d3d6d;
  color: #e0e0e0;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
}

.btn-confirm {
  background: #40c057;
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
}

.btn-confirm:disabled {
  opacity: 0.5;
}

.btn-cancel-form {
  background: #3d3d6d;
  color: #a0a0a0;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
}

.empty-rules {
  text-align: center;
  color: #505070;
  padding: 32px;
  font-size: 0.85rem;
  background: #252540;
  border-radius: 8px;
}

.cqrs-operation {
  background: #252540;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 12px;
  border-left: 4px solid #40c057;
}

.cqrs-operation.update {
  border-left-color: #5c7cfa;
}

.cqrs-operation.delete {
  border-left-color: #ff6b6b;
}

.operation-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #3d3d6d;
}

.operation-type {
  background: #40c057;
  color: #fff;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 700;
}

.cqrs-operation.update .operation-type {
  background: #5c7cfa;
}

.cqrs-operation.delete .operation-type {
  background: #ff6b6b;
}

.when-text {
  color: #707090;
  font-size: 0.8rem;
}

.event-name {
  color: #fd7e14;
  font-weight: 600;
  font-size: 0.9rem;
}

.btn-delete-op {
  margin-left: auto;
  background: none;
  border: none;
  color: #ff6b6b;
  cursor: pointer;
  padding: 4px;
  opacity: 0.6;
  transition: opacity 0.2s;
}

.btn-delete-op:hover {
  opacity: 1;
}

.mapping-section,
.where-section {
  margin-top: 12px;
}

.section-label {
  font-size: 0.75rem;
  color: #707090;
  font-weight: 600;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.mapping-row,
.where-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #1a1a2e;
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 0.85rem;
}

.target-field {
  color: #40c057;
  font-weight: 500;
}

.equals,
.operator {
  color: #707090;
}

.source-field {
  color: #fd7e14;
}

.source-field.static {
  color: #fcc419;
}

.btn-remove-mapping {
  margin-left: auto;
  background: none;
  border: none;
  color: #505070;
  cursor: pointer;
  padding: 2px;
}

.btn-remove-mapping:hover {
  color: #ff6b6b;
}

.add-mapping-form,
.add-where-form {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: rgba(64, 192, 87, 0.05);
  border: 1px dashed #3d3d6d;
  border-radius: 6px;
  margin-top: 8px;
}

.field-select,
.source-type-select,
.operator-select {
  background: #1a1a2e;
  border: 1px solid #3d3d6d;
  color: #c0c0c0;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 0.8rem;
}

.field-select {
  flex: 1;
  min-width: 120px;
}

.source-type-select {
  width: 80px;
}

.operator-select {
  width: 50px;
}

.value-input {
  flex: 1;
  background: #1a1a2e;
  border: 1px solid #3d3d6d;
  color: #c0c0c0;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 0.8rem;
}

.btn-add-small {
  background: #40c057;
  color: #fff;
  border: none;
  width: 28px;
  height: 28px;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-add-small:disabled {
  opacity: 0.5;
}

.saving-indicator {
  color: #40c057;
  font-size: 0.85rem;
  margin-top: 12px;
}
</style>


