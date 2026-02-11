<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { NodeEditSchemas, normalizeNodeLabel, ProvisioningTypeOptions } from './inspectors/nodeEditSchema'
import PropertyEditorTable from './inspectors/PropertyEditorTable.vue'
import VoFieldsTable from './inspectors/VoFieldsTable.vue'
import { createLogger, newOpId } from '@/app/logging/logger'

const props = defineProps({
  nodeId: {
    type: String,
    default: null
  },
  initialTab: {
    type: String,
    default: 'properties' // 'properties' | 'preview'
  }
})

const emit = defineEmits(['close', 'updated', 'request-chat'])

const canvasStore = useCanvasStore()
const log = createLogger({ scope: 'InspectorPanel' })

const node = computed(() => {
  if (!props.nodeId) return null
  return canvasStore.nodes.find(n => n.id === props.nodeId) || null
})

const nodeLabel = computed(() => {
  const n = node.value
  return normalizeNodeLabel(n?.data?.type || n?.type)
})

const schema = computed(() => {
  return NodeEditSchemas[nodeLabel.value]
})

function normalizeInspectorTab(tab, label) {
  if (tab === 'preview' && label === 'UI') return 'preview'
  return 'properties'
}

const activeTab = ref(normalizeInspectorTab(props.initialTab, nodeLabel.value))
watch(
  () => props.initialTab,
  v => {
    if (v) activeTab.value = normalizeInspectorTab(v, nodeLabel.value)
  }
)

const saving = ref(false)
const error = ref(null)
const successMsg = ref(null)

const propertyEditorRef = ref(null)
const propIsDirty = ref(false)
const propHasBlockingErrors = ref(false)

const showPropertyEditor = computed(() => {
  return ['Aggregate', 'Command', 'Event', 'ReadModel'].includes(nodeLabel.value)
})

const showGWTEditor = computed(() => {
  // Policy GWT generation is disabled - only show GWT editor for Commands
  return nodeLabel.value === 'Command'
})

function onPropertyEditorStateChange(s) {
  propIsDirty.value = !!s?.isDirty
  propHasBlockingErrors.value = !!s?.hasBlockingErrors
}

const form = ref({
  name: '',
  description: '',
  template: '',
  actor: '',
  category: '',
  version: '',
  rootEntity: '',
  provisioningType: 'CQRS',
  isMultipleResult: '',
  attachedToId: '',
  attachedToType: '',
  attachedToName: '',
  // GWT fields
  given: null,
  when: null,
  then: null
})

const initial = ref(null)

function templateSummary(v) {
  const s = typeof v === 'string' ? v : v == null ? '' : String(v)
  const len = s.length
  const head = s.slice(0, 200)
  const tail = len > 280 ? s.slice(-80) : ''
  return { len, head, tail }
}

function redactForLog(value, depth = 0) {
  if (depth > 3) return value
  if (Array.isArray(value)) return value.map(v => redactForLog(v, depth + 1))
  if (value && typeof value === 'object') {
    const out = {}
    for (const [k, v] of Object.entries(value)) {
      if (k === 'template') out[k] = templateSummary(v)
      else out[k] = redactForLog(v, depth + 1)
    }
    return out
  }
  return value
}

function snapshotFromNode(n) {
  const data = n?.data || {}
  return {
    name: data.name ?? '',
    description: data.description ?? '',
    template: data.template ?? '',
    actor: data.actor ?? '',
    category: data.category ?? '',
    version: data.version ?? '',
    rootEntity: data.rootEntity ?? '',
    provisioningType: data.provisioningType ?? 'CQRS',
    isMultipleResult: data.isMultipleResult ?? '',
    attachedToId: data.attachedToId ?? '',
    attachedToType: data.attachedToType ?? '',
    attachedToName: data.attachedToName ?? '',
    enumerations: data.enumerations ?? [],
    valueObjects: data.valueObjects ?? [],
    // GWT fields (backward compatibility: use first row if gwtSets exists)
    gwtSets: data.gwtSets || (data.given || data.when || data.then ? [{
      given: data.given ? { ...data.given, fieldValues: data.given.fieldValues || {} } : null,
      when: data.when ? { ...data.when, fieldValues: data.when.fieldValues || {} } : null,
      then: data.then ? { ...data.then, fieldValues: data.then.fieldValues || {} } : null
    }] : []),
    // For backward compatibility
    given: data.given ? { ...data.given, fieldValues: data.given.fieldValues || {} } : null,
    when: data.when ? { ...data.when, fieldValues: data.when.fieldValues || {} } : null,
    then: data.then ? { ...data.then, fieldValues: data.then.fieldValues || {} } : null
  }
}

function resetToNode() {
  if (!node.value) {
    log.info('inspector_reset_empty', 'Reset inspector form (no node).', {
      opId: newOpId('reset'),
      nodeId: props.nodeId,
      initialTab: props.initialTab
    })
    initial.value = null
    form.value = {
      name: '',
      description: '',
      template: '',
      actor: '',
      category: '',
      version: '',
      rootEntity: '',
      provisioningType: 'CQRS',
      isMultipleResult: '',
      attachedToId: '',
      attachedToType: '',
      attachedToName: '',
      gwtSets: [],
      given: null,
      when: null,
      then: null
    }
    return
  }
  const opId = newOpId('reset')
  const snap = snapshotFromNode(node.value)
  log.info('inspector_reset', 'Reset inspector form from node snapshot.', {
    opId,
    nodeId: node.value.id,
    nodeLabel: nodeLabel.value,
    snapshot: redactForLog(snap),
    rawNode: redactForLog({ id: node.value.id, type: node.value.type, data: node.value.data })
  })
  console.info('[RAW][InspectorPanel][inspector_reset]', {
    opId,
    node: redactForLog({ id: node.value.id, type: node.value.type, data: node.value.data }),
    snapshot: redactForLog(snap)
  })
  form.value = { ...form.value, ...snap }
  initial.value = { ...snap }
  error.value = null
  successMsg.value = null

  // Keep Property editor snapshot in sync (node.id doesn't change on updates)
  nextTick(() => {
    if (showPropertyEditor.value) {
      propertyEditorRef.value?.resetFromNode?.(node.value)
    }
  })
}

watch(
  () => props.nodeId,
  () => {
    const opId = newOpId('open')
    log.info('inspector_open', 'Inspector opened / nodeId changed.', {
      opId,
      nodeId: props.nodeId,
      initialTab: props.initialTab,
      node: redactForLog(node.value)
    })
    console.info('[RAW][InspectorPanel][inspector_open]', {
      opId,
      nodeId: props.nodeId,
      initialTab: props.initialTab,
      node: redactForLog(node.value)
    })
    activeTab.value = normalizeInspectorTab(props.initialTab || 'properties', nodeLabel.value)
    resetToNode()
  },
  { immediate: true }
)

const dirtyFields = computed(() => {
  if (!initial.value) return []
  const keys = schema.value?.fields?.map(f => f.key) || []
  const dirty = keys.filter(k => String(form.value[k] ?? '') !== String(initial.value[k] ?? ''))
  
  // Check GWT fields
  if (showGWTEditor.value) {
    const gwtFields = ['given', 'when', 'then']
    gwtFields.forEach(field => {
      const current = form.value[field]
      const original = initial.value[field]
      if (JSON.stringify(current) !== JSON.stringify(original)) {
        dirty.push(field)
      }
    })
  }
  
  return dirty
})

const isDirty = computed(() => dirtyFields.value.length > 0)

function generateChangeId(prefix = 'inspector') {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

async function safeJson(response) {
  try {
    return await response.json()
  } catch {
    return null
  }
}

async function save() {
  if (!node.value || !initial.value) return
  if (!isDirty.value && !propIsDirty.value) return
  if (propHasBlockingErrors.value) {
    error.value = 'Property 입력 오류를 수정한 뒤 저장하세요.'
    return
  }

  const opId = newOpId('save')
  saving.value = true
  error.value = null
  successMsg.value = null

  try {
    const changes = []
    const shouldSaveGWTBundle = showGWTEditor.value && JSON.stringify(form.value.gwtSets || []) !== JSON.stringify(initial.value.gwtSets || [])

    // Property drafts (create/update/rename/delete)
    if (showPropertyEditor.value) {
      const propRes = propertyEditorRef.value?.buildDraftChanges?.() || { drafts: [], errors: [] }
      const propErrors = Array.isArray(propRes?.errors) ? propRes.errors : []
      if (propErrors.length) {
        throw new Error(propErrors.join('\n'))
      }
      const propDrafts = Array.isArray(propRes?.drafts) ? propRes.drafts : []
      propDrafts.forEach(d => changes.push(d))
    }

    // rename (name)
    if (String(form.value.name) !== String(initial.value.name)) {
      changes.push({
        changeId: generateChangeId('rename'),
        action: 'rename',
        targetId: node.value.id,
        targetName: String(form.value.name || ''),
        targetType: nodeLabel.value,
        updates: {}
      })
    }

    // update (other fields)
    const updates = {}
    for (const f of schema.value.fields) {
      if (f.key === 'name') continue
      const next = form.value[f.key]
      const prev = initial.value[f.key]
      if (String(next ?? '') !== String(prev ?? '')) {
        updates[f.key] = next
      }
    }
    
    // NOTE: GWT is saved via /api/graph/gwt/upsert (single bundle node), not via /api/chat/confirm.
    
    if (Object.keys(updates).length) {
      changes.push({
        changeId: generateChangeId('update'),
        action: 'update',
        targetId: node.value.id,
        targetName: String(form.value.name || ''),
        targetType: nodeLabel.value,
        updates
      })
    }

    // Save GWT bundle first (so UI doesn't lose decision-table edits)
    if (shouldSaveGWTBundle) {
      const first = (form.value.gwtSets || [])[0] || {}
      const given = first?.given || null
      const when = first?.when || null
      const then = first?.then || null

      const payload = {
        parentType: nodeLabel.value,
        parentId: node.value.id,
        givenRef: given
          ? {
              referencedNodeId: given.referencedNodeId,
              referencedNodeType: given.referencedNodeType,
              name: given.name
            }
          : null,
        whenRef: when
          ? {
              referencedNodeId: when.referencedNodeId,
              referencedNodeType: when.referencedNodeType,
              name: when.name
            }
          : null,
        thenRef: then
          ? {
              referencedNodeId: then.referencedNodeId,
              referencedNodeType: then.referencedNodeType,
              name: then.name
            }
          : null,
        testCases: (form.value.gwtSets || []).map(row => ({
          scenarioDescription: getGWTDescription(row) || null,
          givenFieldValues: (row?.given?.fieldValues || {}),
          whenFieldValues: (row?.when?.fieldValues || {}),
          thenFieldValues: (row?.then?.fieldValues || {})
        }))
      }

      const gwtRes = await fetch('/api/graph/gwt/upsert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const gwtData = await safeJson(gwtRes)
      if (!gwtRes.ok || !gwtData?.success) {
        throw new Error(gwtData?.detail || 'GWT 저장 실패')
      }
    }

    if (!changes.length) {
      // Only GWT was saved
      initial.value = { ...form.value }
      successMsg.value = '저장되었습니다.'
      emit('updated')
      return
    }

    const payload = {
      drafts: changes,
      approvedChangeIds: changes.map(c => c.changeId)
    }

    log.info('inspector_save_request', 'Submitting change-apply confirm payload from Inspector.', {
      opId,
      nodeId: node.value.id,
      nodeLabel: nodeLabel.value,
      dirtyFields: dirtyFields.value,
      initial: redactForLog(initial.value),
      form: redactForLog(form.value),
      changes: redactForLog(changes),
      payload: redactForLog(payload)
    })
    console.info('[RAW][InspectorPanel][inspector_save_request]', {
      opId,
      nodeId: node.value.id,
      changes: redactForLog(changes),
      payload: redactForLog(payload)
    })

    const response = await fetch('/api/chat/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    const data = await safeJson(response)
    log.info('inspector_save_response', 'Received response from /api/chat/confirm.', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: redactForLog(data)
    })
    console.info('[RAW][InspectorPanel][inspector_save_response]', {
      opId,
      http: { ok: response.ok, status: response.status, statusText: response.statusText },
      responseBody: redactForLog(data)
    })
    if (!response.ok) {
      throw new Error(data?.detail || `API error: ${response.status}`)
    }
    if (!data?.success) {
      const reason = Array.isArray(data?.errors) && data.errors.length ? data.errors.join('\n') : '알 수 없는 오류'
      throw new Error(reason)
    }

    const applied = data?.appliedChanges || []
    if (applied.length) {
      log.info('inspector_save_sync_start', 'Applying appliedChanges to canvas store.', {
        opId,
        appliedChanges: redactForLog(applied)
      })
      console.info('[RAW][InspectorPanel][inspector_save_sync_start]', { opId, appliedChanges: redactForLog(applied) })
      canvasStore.syncAfterChanges(applied)
      log.info('inspector_save_sync_done', 'Canvas store synced after Inspector save.', {
        opId,
        nodeId: node.value.id,
        currentNode: canvasStore.nodes.find(n => n.id === node.value.id) || null
      })
      console.info('[RAW][InspectorPanel][inspector_save_sync_done]', {
        opId,
        nodeId: node.value.id,
        currentNode: canvasStore.nodes.find(n => n.id === node.value.id) || null
      })

      // resync form/initial from store snapshot (server may normalize template)
      const latest = canvasStore.nodes.find(n => n.id === node.value.id) || null
      if (latest) {
        const snap = snapshotFromNode(latest)
        form.value = { ...form.value, ...snap }
        initial.value = { ...snap }

        // resync properties editor to store snapshot (keeps order stable while editing; sorts only after save)
        nextTick(() => {
          if (showPropertyEditor.value) {
            propertyEditorRef.value?.resetFromNode?.(latest)
          }
        })
      } else {
        // fallback: do not lose user's edits
        initial.value = { ...form.value }
      }
    } else {
      // reset dirty state based on current form values (do not lose user's edits)
      initial.value = { ...form.value }
    }

    successMsg.value = '저장되었습니다.'
    log.info('inspector_save_done', 'Inspector save completed.', { opId, nodeId: node.value.id })
    console.info('[RAW][InspectorPanel][inspector_save_done]', { opId, nodeId: node.value.id })
    emit('updated')
  } catch (e) {
    log.error('inspector_save_error', 'Inspector save failed.', {
      opId,
      nodeId: node.value?.id,
      nodeLabel: nodeLabel.value,
      error: e?.message || String(e),
      form: redactForLog(form.value),
      initial: redactForLog(initial.value)
    })
    console.error('[RAW][InspectorPanel][inspector_save_error]', {
      opId,
      error: e,
      form: redactForLog(form.value),
      initial: redactForLog(initial.value)
    })
    error.value = e?.message || String(e)
  } finally {
    saving.value = false
  }
}

function requestChat() {
  if (!node.value) return
  emit('request-chat', node.value.id)
}

function addGWT() {
  // Legacy function - use addGWTSet instead
  addGWTSet()
}

function addGWTSet() {
  // Get the referenced nodes from the first set (if exists) or from node data
  const firstSet = form.value.gwtSets[0]
  const nodeData = node.value?.data
  
  // Use referenced nodes from first set if available, otherwise create new
  // All rows share the same referenced nodes, only fieldValues differ
  const newRow = {
    given: firstSet?.given ? { 
      ...firstSet.given, 
      fieldValues: {} // Empty fieldValues for new test case
    } : (nodeData?.given ? { 
      ...nodeData.given, 
      fieldValues: {} 
    } : null),
    when: firstSet?.when ? { 
      ...firstSet.when, 
      fieldValues: {} 
    } : (nodeData?.when ? { 
      ...nodeData.when, 
      fieldValues: {} 
    } : null),
    then: firstSet?.then ? { 
      ...firstSet.then, 
      fieldValues: {} 
    } : (nodeData?.then ? { 
      ...nodeData.then, 
      fieldValues: {} 
    } : null)
  }
  
  form.value.gwtSets.push(newRow)
  
  // Update backward compatibility fields (use first row)
  if (form.value.gwtSets.length === 1) {
    if (newRow.given) {
      form.value.given = newRow.given
    }
    if (newRow.when) {
      form.value.when = newRow.when
    }
    if (newRow.then) {
      form.value.then = newRow.then
    }
  }
}

function removeGWTSet(rowIndex) {
  if (rowIndex >= 0 && rowIndex < form.value.gwtSets.length) {
    form.value.gwtSets.splice(rowIndex, 1)
    
    // Update backward compatibility fields
    if (form.value.gwtSets.length > 0) {
      const firstSet = form.value.gwtSets[0]
      form.value.given = firstSet.given
      form.value.when = firstSet.when
      form.value.then = firstSet.then
    } else {
      form.value.given = null
      form.value.when = null
      form.value.then = null
    }
  }
}

// Get properties from referenced node (including enumerations and value objects)
function getReferencedNodeProperties(referencedNodeId, referencedNodeType) {
  if (!referencedNodeId || !referencedNodeType) return []
  
  // Try to find node in canvas store
  const canvasNode = canvasStore.nodes.find(n => n.id === referencedNodeId)
  if (!canvasNode || !canvasNode.data) return []
  
  const data = canvasNode.data
  const result = []
  
  // Add regular properties
  const props = Array.isArray(data.properties) ? data.properties : []
  props.forEach(p => {
    result.push({
      id: String(p?.id || ''),
      name: String(p?.name ?? ''),
      type: String(p?.type ?? ''),
      description: String(p?.description ?? ''),
      isKey: Boolean(p?.isKey),
      isForeignKey: Boolean(p?.isForeignKey),
      isRequired: Boolean(p?.isRequired),
      isReadOnly: false,
      fieldType: 'property',
      parentType: String(p?.parentType ?? data?.type ?? ''),
      parentId: String(p?.parentId ?? referencedNodeId ?? '')
    })
  })
  
  // Add enumerations (read-only)
  const enums = Array.isArray(data.enumerations) ? data.enumerations : []
  enums.forEach((e, idx) => {
    if (e && e.name) {
      result.push({
        id: `enum-${e.name}-${idx}`,
        name: String(e.name ?? ''),
        type: 'Enum',
        description: String(e.alias ?? ''),
        isKey: false,
        isForeignKey: false,
        isRequired: false,
        isReadOnly: true,
        fieldType: 'enum',
        parentType: String(data?.type ?? ''),
        parentId: String(referencedNodeId ?? ''),
        enumItems: Array.isArray(e.items) ? e.items : []
      })
    }
  })
  
  // Add value objects (read-only)
  const vos = Array.isArray(data.valueObjects) ? data.valueObjects : []
  vos.forEach((vo, idx) => {
    if (vo && vo.name) {
      result.push({
        id: `vo-${vo.name}-${idx}`,
        name: String(vo.name ?? ''),
        type: 'ValueObject',
        description: String(vo.alias ?? ''),
        isKey: false,
        isForeignKey: false,
        isRequired: false,
        isReadOnly: true,
        fieldType: 'valueObject',
        referencedAggregateName: vo.referencedAggregateName || null,
        parentType: String(data?.type ?? ''),
        parentId: String(referencedNodeId ?? ''),
        voFields: Array.isArray(vo.fields) ? vo.fields : []
      })
    }
  })
  
  return result
}

// Get available properties for a GWT type (given/when/then)
function getGWTDescription(gwtSet) {
  // Extract scenario description from the first Given's description
  // The scenario description is stored at the beginning of the description
  // Only show if it looks like a business flow description (not fallback/hardcoded)
  if (!gwtSet || !gwtSet.given || !gwtSet.given.description) return null
  
  const desc = gwtSet.given.description
  // If description contains newline, take the first part (scenario description)
  const lines = desc.split('\n')
  const firstLine = lines[0].trim()
  
  if (!firstLine) return null
  
  // Filter out hardcoded fallback descriptions
  const fallbackPatterns = [
    /^Command .+ is available$/i,
    /^Aggregate .+ handles this command$/i,
    /^Event .+ is emitted$/i,
    /^Event .+ triggers this policy$/i,
    /^Aggregate .+ handles the invoked command$/i,
    /^Event .+ is emitted by the invoked command$/i,
  ]
  
  // Check if it matches any fallback pattern
  const isFallback = fallbackPatterns.some(pattern => pattern.test(firstLine))
  if (isFallback) return null
  
  // Check if it looks like a business flow description
  // Business flow descriptions are typically longer and more descriptive
  // They often contain words like "Happy path", "Scenario", "When", "User", etc.
  const businessFlowIndicators = [
    /happy path/i,
    /scenario/i,
    /when .+ then/i,
    /user .+ successfully/i,
    /policy triggers when/i,
    /successfully invokes/i,
  ]
  
  const looksLikeBusinessFlow = businessFlowIndicators.some(pattern => pattern.test(firstLine))
  
  // If it's short and doesn't look like business flow, it's probably just a technical description
  if (firstLine.length < 30 && !looksLikeBusinessFlow) return null
  
  return firstLine
}

function getAvailableProperties(gwtSet, type) {
  const gwt = gwtSet[type]
  if (!gwt || !gwt.referencedNodeId || !gwt.referencedNodeType) return []
  
  return getReferencedNodeProperties(gwt.referencedNodeId, gwt.referencedNodeType)
}

// Cache for Policy relationship data
const policyRelationsCache = ref({})

// Fetch Policy relationships from API
async function fetchPolicyRelations(policyId) {
  if (policyRelationsCache.value[policyId]) {
    return policyRelationsCache.value[policyId]
  }
  
  try {
    const response = await fetch(`/api/graph/expand/${policyId}`)
    if (!response.ok) return null
    
    const data = await response.json()
    const policyNode = data.nodes?.find(n => n.id === policyId && n.type === 'Policy')
    if (!policyNode) return null
    
    // Extract relationships from the response
    const relationships = data.relationships || []
    const triggerEvents = relationships
      .filter(r => r.target === policyId && r.type === 'TRIGGERS')
      .map(r => {
        const eventNode = data.nodes?.find(n => n.id === r.source && n.type === 'Event')
        return eventNode?.name || null
      })
      .filter(Boolean)
    
    const invokeRel = relationships.find(r => r.source === policyId && r.type === 'INVOKES')
    const commandNode = invokeRel ? data.nodes?.find(n => n.id === invokeRel.target && n.type === 'Command') : null
    
    const hasCommandRel = commandNode ? relationships.find(r => r.target === commandNode.id && r.type === 'HAS_COMMAND') : null
    const aggregateNode = hasCommandRel ? data.nodes?.find(n => n.id === hasCommandRel.source && n.type === 'Aggregate') : null
    
    const emitsRel = commandNode ? relationships.find(r => r.source === commandNode.id && r.type === 'EMITS') : null
    const eventNode = emitsRel ? data.nodes?.find(n => n.id === emitsRel.target && n.type === 'Event') : null
    
    const result = {
      triggerEvents,
      aggregateName: aggregateNode?.name || null,
      eventName: eventNode?.name || null
    }
    
    policyRelationsCache.value[policyId] = result
    return result
  } catch (error) {
    console.error('Failed to fetch Policy relations:', error)
    return null
  }
}

// Get Policy mapped objects from API (when GWT not yet generated)
const policyMappedGiven = ref(null)
const policyMappedWhen = ref(null)
const policyMappedThen = ref(null)

watch(() => node.value?.id, async (policyId) => {
  if (nodeLabel.value === 'Policy' && policyId) {
    const relations = await fetchPolicyRelations(policyId)
    if (relations) {
      policyMappedGiven.value = relations.triggerEvents.length > 0 
        ? relations.triggerEvents.map(name => `Event: ${name}`).join(', ')
        : null
      policyMappedWhen.value = relations.aggregateName ? `Aggregate: ${relations.aggregateName}` : null
      policyMappedThen.value = relations.eventName ? `Event: ${relations.eventName}` : null
    } else {
      policyMappedGiven.value = null
      policyMappedWhen.value = null
      policyMappedThen.value = null
    }
  } else {
    policyMappedGiven.value = null
    policyMappedWhen.value = null
    policyMappedThen.value = null
  }
}, { immediate: true })

function getPolicyMappedGiven() {
  return policyMappedGiven.value
}

function getPolicyMappedWhen() {
  return policyMappedWhen.value
}

function getPolicyMappedThen() {
  return policyMappedThen.value
}

// Get properties that are already in fieldValues
function getUsedProperties(gwtSet, type) {
  const gwt = gwtSet[type]
  if (!gwt || !gwt.fieldValues) return []
  return Object.keys(gwt.fieldValues)
}

// Get unused properties (available but not yet used)
function getUnusedProperties(gwtSet, type) {
  const available = getAvailableProperties(gwtSet, type)
  const used = getUsedProperties(gwtSet, type)
  return available.filter(prop => !used.includes(prop.name))
}

// Get all field names from Given/When/Then (union of all)
function getAllFieldNames(gwtSet) {
  const fields = new Set()
  
  if (gwtSet.given?.fieldValues) {
    Object.keys(gwtSet.given.fieldValues).forEach(f => fields.add(f))
  }
  if (gwtSet.when?.fieldValues) {
    Object.keys(gwtSet.when.fieldValues).forEach(f => fields.add(f))
  }
  if (gwtSet.then?.fieldValues) {
    Object.keys(gwtSet.then.fieldValues).forEach(f => fields.add(f))
  }
  
  return Array.from(fields).sort()
}

// Get all available properties from all referenced nodes (Given/When/Then)
function getAllAvailableProperties(gwtSet) {
  const allProps = new Set()
  
  const givenProps = getAvailableProperties(gwtSet, 'given')
  const whenProps = getAvailableProperties(gwtSet, 'when')
  const thenProps = getAvailableProperties(gwtSet, 'then')
  
  givenProps.forEach(p => allProps.add(p.name))
  whenProps.forEach(p => allProps.add(p.name))
  thenProps.forEach(p => allProps.add(p.name))
  
  return Array.from(allProps)
}

// Check if there are unused properties
function hasUnusedProperties(gwtSet) {
  const allAvailable = getAllAvailableProperties(gwtSet)
  const allUsed = getAllFieldNames(gwtSet)
  return allAvailable.some(prop => !allUsed.includes(prop))
}

// Add all fields to the set (adds to all Given/When/Then that have the property)
function addAllFieldsToSet(gwtSet) {
  const allAvailable = getAllAvailableProperties(gwtSet)
  const allUsed = getAllFieldNames(gwtSet)
  const unused = allAvailable.filter(prop => !allUsed.includes(prop))
  
  // Add to Given if it exists
  if (gwtSet.given) {
    if (!gwtSet.given.fieldValues) gwtSet.given.fieldValues = {}
    const givenProps = getAvailableProperties(gwtSet, 'given')
    givenProps.forEach(prop => {
      if (unused.includes(prop.name) && !gwtSet.given.fieldValues[prop.name]) {
        gwtSet.given.fieldValues[prop.name] = ''
      }
    })
  }
  
  // Add to When if it exists
  if (gwtSet.when) {
    if (!gwtSet.when.fieldValues) gwtSet.when.fieldValues = {}
    const whenProps = getAvailableProperties(gwtSet, 'when')
    whenProps.forEach(prop => {
      if (unused.includes(prop.name) && !gwtSet.when.fieldValues[prop.name]) {
        gwtSet.when.fieldValues[prop.name] = ''
      }
    })
  }
  
  // Add to Then if it exists
  if (gwtSet.then) {
    if (!gwtSet.then.fieldValues) gwtSet.then.fieldValues = {}
    const thenProps = getAvailableProperties(gwtSet, 'then')
    thenProps.forEach(prop => {
      if (unused.includes(prop.name) && !gwtSet.then.fieldValues[prop.name]) {
        gwtSet.then.fieldValues[prop.name] = ''
      }
    })
  }
  
  // If no properties available at all, add a generic field
  if (unused.length === 0 && getAllFieldNames(gwtSet).length === 0) {
    const fieldName = `field_${Date.now()}`
    if (gwtSet.given) {
      if (!gwtSet.given.fieldValues) gwtSet.given.fieldValues = {}
      gwtSet.given.fieldValues[fieldName] = ''
    }
  }
}

// Remove field from all Given/When/Then
function removeFieldFromSet(gwtSet, fieldName) {
  if (gwtSet.given?.fieldValues) {
    delete gwtSet.given.fieldValues[fieldName]
  }
  if (gwtSet.when?.fieldValues) {
    delete gwtSet.when.fieldValues[fieldName]
  }
  if (gwtSet.then?.fieldValues) {
    delete gwtSet.then.fieldValues[fieldName]
  }
}

// Update field value safely
function updateFieldValue(gwtSet, type, fieldName, value) {
  if (!gwtSet[type]) {
    gwtSet[type] = { fieldValues: {} }
  }
  if (!gwtSet[type].fieldValues) {
    gwtSet[type].fieldValues = {}
  }
  gwtSet[type].fieldValues[fieldName] = value
}

function addFieldValue(gwtType) {
  const gwt = form.value[gwtType]
  if (!gwt) return
  if (!gwt.fieldValues) {
    gwt.fieldValues = {}
  }
  const newKey = `field_${Object.keys(gwt.fieldValues).length + 1}`
  gwt.fieldValues[newKey] = ''
}

function removeFieldValue(gwtType, key) {
  const gwt = form.value[gwtType]
  if (!gwt || !gwt.fieldValues) return
  delete gwt.fieldValues[key]
}

function removeGWT() {
  // Remove all GWT sets
  form.value.gwtSets = []
  form.value.given = null
  form.value.when = null
  form.value.then = null
}

// Format field value for display (handle objects, arrays, etc.)
function formatFieldValue(value) {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return JSON.stringify(value)
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

// Get appropriate input type based on property type
function getInputTypeForProperty(prop) {
  if (!prop) return 'text'
  
  // Check if it's an Enum (fieldType or type)
  if (prop.fieldType === 'enum' || (prop.type && String(prop.type).toLowerCase() === 'enum')) {
    return 'select'
  }
  
  // Check if it's a ValueObject
  if (prop.fieldType === 'valueObject' || (prop.type && String(prop.type).toLowerCase() === 'valueobject')) {
    return 'text' // ValueObject will be displayed as JSON string with edit button
  }
  
  if (!prop.type) return 'text'
  
  const type = String(prop.type).toLowerCase()
  
  if (type.includes('int') || type.includes('long') || type === 'integer') {
    return 'number'
  }
  if (type.includes('decimal') || type.includes('bigdecimal') || type.includes('double') || type.includes('float')) {
    return 'number'
  }
  if (type.includes('boolean') || type === 'bool') {
    return 'checkbox'
  }
  if (type.includes('date') && !type.includes('time')) {
    return 'date'
  }
  if (type.includes('datetime') || type.includes('timestamp') || (type.includes('date') && type.includes('time'))) {
    return 'datetime-local'
  }
  if (type.includes('time') && !type.includes('date')) {
    return 'time'
  }
  
  return 'text'
}

// Format field value for input (preserve type for number inputs)
function formatFieldValueForInput(value, prop) {
  if (value === null || value === undefined) return ''
  
  // Check if it's a ValueObject
  if (prop?.fieldType === 'valueObject' || (prop?.type && String(prop.type).toLowerCase() === 'valueobject')) {
    // ValueObject should be displayed as JSON string
    if (typeof value === 'object') {
      return JSON.stringify(value, null, 2)
    }
    if (typeof value === 'string') {
      // Try to parse and reformat if it's already JSON
      try {
        const parsed = JSON.parse(value)
        return JSON.stringify(parsed, null, 2)
      } catch {
        return value
      }
    }
    return String(value)
  }
  
  const type = prop?.type ? String(prop.type).toLowerCase() : ''
  
  // For number types, preserve as number string (no quotes)
  if (type.includes('int') || type.includes('long') || type === 'integer' || 
      type.includes('decimal') || type.includes('bigdecimal') || type.includes('double') || type.includes('float')) {
    if (typeof value === 'number') return String(value)
    if (typeof value === 'string') {
      // Remove quotes if present
      const unquoted = value.replace(/^["']|["']$/g, '')
      // Try to parse as number
      const num = parseFloat(unquoted)
      if (!isNaN(num)) return String(num)
      return unquoted
    }
    return String(value)
  }
  
  // For boolean, convert to boolean string
  if (type.includes('boolean') || type === 'bool') {
    if (typeof value === 'boolean') return value
    if (typeof value === 'string') {
      const lower = value.toLowerCase().replace(/^["']|["']$/g, '')
      return lower === 'true' ? 'true' : 'false'
    }
    return String(value)
  }
  
  // For date/datetime, format appropriately
  if (type.includes('date') || type.includes('time')) {
    if (typeof value === 'string') {
      // Remove quotes if present
      return value.replace(/^["']|["']$/g, '')
    }
    return String(value)
  }
  
  // For strings and others, use formatFieldValue
  return formatFieldValue(value)
}

// Get placeholder based on property type
function getPlaceholderForProperty(prop) {
  if (!prop || !prop.type) return 'N/A'
  
  // Check if it's an Enum
  if (prop.fieldType === 'enum' || String(prop.type).toLowerCase() === 'enum') {
    const items = Array.isArray(prop.enumItems) && prop.enumItems.length > 0 
      ? prop.enumItems.join(', ') 
      : 'enum value'
    return `Select: ${items}`
  }
  
  // Check if it's a ValueObject
  if (prop.fieldType === 'valueObject' || String(prop.type).toLowerCase() === 'valueobject') {
    const fields = Array.isArray(prop.voFields) && prop.voFields.length > 0
      ? prop.voFields.map(f => `${f.name || ''}: ${f.type || ''}`).join(', ')
      : 'fields'
    return `JSON: {"${fields}"}`
  }
  
  const type = String(prop.type).toLowerCase()
  
  if (type.includes('int') || type.includes('long') || type === 'integer') {
    return '123'
  }
  if (type.includes('decimal') || type.includes('bigdecimal') || type.includes('double') || type.includes('float')) {
    return '100.50'
  }
  if (type.includes('boolean') || type === 'bool') {
    return 'true/false'
  }
  if (type.includes('date') && !type.includes('time')) {
    return '2024-01-15'
  }
  if (type.includes('datetime') || type.includes('timestamp')) {
    return '2024-01-15T10:30:00'
  }
  if (type.includes('uuid')) {
    return '550e8400-e29b-41d4-a716-446655440000'
  }
  
  return 'N/A'
}

// Parse boolean value from various formats
function parseBooleanValue(value) {
  if (value === null || value === undefined) return false
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const lower = value.toLowerCase().replace(/^["']|["']$/g, '')
    return lower === 'true' || lower === '1'
  }
  if (typeof value === 'number') return value !== 0
  return Boolean(value)
}

const showGWTDetailModal = ref(false)
const selectedGWTSetIndex = ref(0)

// ValueObject editor modal state
const voEditorModal = ref({
  open: false,
  gwtSet: null,
  gwtType: null, // 'given', 'when', 'then'
  propName: null,
  prop: null, // prop object with voFields
  currentValue: null, // current JSON value
  fieldValues: {} // field name -> value mapping for editing
})

function openGWTDetailModal(setIndex = null) {
  if (setIndex !== null) {
    selectedGWTSetIndex.value = setIndex
  }
  
  // If GWT sets are empty but this is a Policy, initialize from relationships
  if (nodeLabel.value === 'Policy' && (!form.value.gwtSets || form.value.gwtSets.length === 0)) {
    const givenName = getPolicyMappedGiven()
    const whenName = getPolicyMappedWhen()
    const thenName = getPolicyMappedThen()
    
    if (givenName || whenName || thenName) {
      // Find nodes from relationships
      const nodeId = node.value.id
      
      // Find trigger events
      const triggerEdges = canvasStore.edges.filter(e => {
        const isTarget = e.target === nodeId
        const isTriggers = e.data?.edgeType === 'TRIGGERS' || 
                           e.label?.toLowerCase() === 'triggers' ||
                           e.data?.type === 'TRIGGERS'
        return isTarget && isTriggers
      })
      
      // Find invoke command
      const invokeEdge = canvasStore.edges.find(e => {
        const isSource = e.source === nodeId
        const isInvokes = e.data?.edgeType === 'INVOKES' || 
                          e.label?.toLowerCase() === 'invokes' ||
                          e.data?.type === 'INVOKES'
        return isSource && isInvokes
      })
      
      const commandNode = invokeEdge ? canvasStore.nodes.find(n => {
        const nodeType = normalizeNodeLabel(n?.data?.type || n?.type)
        return n.id === invokeEdge.target && nodeType === 'Command'
      }) : null
      
      // Find aggregate
      const hasCommandEdge = commandNode ? canvasStore.edges.find(e => {
        const isTarget = e.target === commandNode.id
        const isHasCommand = e.data?.edgeType === 'HAS_COMMAND' || 
                            e.label?.toLowerCase() === 'has_command' ||
                            e.data?.type === 'HAS_COMMAND'
        return isTarget && isHasCommand
      }) : null
      
      const aggregateNode = hasCommandEdge ? canvasStore.nodes.find(n => {
        const nodeType = normalizeNodeLabel(n?.data?.type || n?.type)
        return n.id === hasCommandEdge.source && nodeType === 'Aggregate'
      }) : null
      
      // Find emitted event
      const emitsEdge = commandNode ? canvasStore.edges.find(e => {
        const isSource = e.source === commandNode.id
        const isEmits = e.data?.edgeType === 'EMITS' || 
                       e.label?.toLowerCase() === 'emits' ||
                       e.data?.type === 'EMITS'
        return isSource && isEmits
      }) : null
      
      const eventNode = emitsEdge ? canvasStore.nodes.find(n => {
        const nodeType = normalizeNodeLabel(n?.data?.type || n?.type)
        return n.id === emitsEdge.target && nodeType === 'Event'
      }) : null
      
      // Create initial GWT set from relationships
      const firstTriggerEvent = triggerEdges.length > 0 ? canvasStore.nodes.find(n => {
        const nodeType = normalizeNodeLabel(n?.data?.type || n?.type)
        return n.id === triggerEdges[0].source && nodeType === 'Event'
      }) : null
      
      form.value.gwtSets = [{
        given: firstTriggerEvent ? {
          name: firstTriggerEvent.data?.name || firstTriggerEvent.name,
          referencedNodeId: firstTriggerEvent.id,
          referencedNodeType: 'Event',
          fieldValues: {}
        } : null,
        when: aggregateNode ? {
          name: aggregateNode.data?.name || aggregateNode.name,
          referencedNodeId: aggregateNode.id,
          referencedNodeType: 'Aggregate',
          fieldValues: {}
        } : null,
        then: eventNode ? {
          name: eventNode.data?.name || eventNode.name,
          referencedNodeId: eventNode.id,
          referencedNodeType: 'Event',
          fieldValues: {}
        } : null
      }]
    }
  }
  
  showGWTDetailModal.value = true
}

function closeGWTDetailModal() {
  showGWTDetailModal.value = false
  selectedGWTSetIndex.value = 0
}

// Open ValueObject editor modal
function openVoEditor(gwtSet, gwtType, propName, prop) {
  const currentValue = gwtSet[gwtType]?.fieldValues?.[propName]
  let fieldValues = {}
  
  // Parse current JSON value to field values
  if (currentValue) {
    try {
      const parsed = typeof currentValue === 'string' ? JSON.parse(currentValue) : currentValue
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        fieldValues = parsed
      }
    } catch (e) {
      // If parsing fails, start with empty object
    }
  }
  
  // Get VO fields from prop.voFields
  const voFields = (prop?.voFields && Array.isArray(prop.voFields) && prop.voFields.length > 0) 
    ? prop.voFields 
    : []
  
  // Initialize field values for all VO fields (preserve existing, set defaults for new)
  const initializedFieldValues = {}
  voFields.forEach(field => {
    const fieldName = field.name || ''
    if (fieldName) {
      if (fieldValues.hasOwnProperty(fieldName)) {
        // Preserve existing value
        initializedFieldValues[fieldName] = fieldValues[fieldName]
      } else {
        // Set default value based on type
        const fieldType = (field.type || 'String').toLowerCase()
        if (fieldType.includes('int') || fieldType.includes('long') || fieldType === 'integer') {
          initializedFieldValues[fieldName] = 0
        } else if (fieldType.includes('decimal') || fieldType.includes('bigdecimal') || fieldType.includes('double') || fieldType.includes('float')) {
          initializedFieldValues[fieldName] = 0.0
        } else if (fieldType.includes('boolean') || fieldType === 'bool') {
          initializedFieldValues[fieldName] = false
        } else {
          initializedFieldValues[fieldName] = ''
        }
      }
    }
  })
  
  voEditorModal.value = {
    open: true,
    gwtSet,
    gwtType,
    propName,
    prop,
    currentValue,
    fieldValues: initializedFieldValues
  }
}

// Close ValueObject editor modal
function closeVoEditor() {
  voEditorModal.value.open = false
}

// Save ValueObject editor changes
function saveVoEditor() {
  if (!voEditorModal.value.gwtSet || !voEditorModal.value.gwtType || !voEditorModal.value.propName) return
  
  // Convert fieldValues to JSON object
  const voObject = { ...voEditorModal.value.fieldValues }
  
  // Update fieldValues
  updateFieldValue(
    voEditorModal.value.gwtSet,
    voEditorModal.value.gwtType,
    voEditorModal.value.propName,
    JSON.stringify(voObject)
  )
  
  closeVoEditor()
}

// Get input type for VO field based on field type
function getVoFieldInputType(fieldType) {
  if (!fieldType) return 'text'
  const type = String(fieldType).toLowerCase()
  
  if (type.includes('int') || type.includes('long') || type === 'integer') {
    return 'number'
  }
  if (type.includes('decimal') || type.includes('bigdecimal') || type.includes('double') || type.includes('float')) {
    return 'number'
  }
  if (type.includes('boolean') || type === 'bool') {
    return 'checkbox'
  }
  if (type.includes('date') && !type.includes('time')) {
    return 'date'
  }
  if (type.includes('datetime') || type.includes('timestamp') || (type.includes('date') && type.includes('time'))) {
    return 'datetime-local'
  }
  if (type.includes('time') && !type.includes('date')) {
    return 'time'
  }
  
  return 'text'
}

// Format VO field value for input
function formatVoFieldValueForInput(value, fieldType) {
  if (value === null || value === undefined) return ''
  
  const type = fieldType ? String(fieldType).toLowerCase() : ''
  
  // For number types
  if (type.includes('int') || type.includes('long') || type === 'integer' || 
      type.includes('decimal') || type.includes('bigdecimal') || type.includes('double') || type.includes('float')) {
    if (typeof value === 'number') return String(value)
    if (typeof value === 'string') {
      const num = parseFloat(value)
      if (!isNaN(num)) return String(num)
    }
    return String(value)
  }
  
  // For boolean
  if (type.includes('boolean') || type === 'bool') {
    if (typeof value === 'boolean') return value
    if (typeof value === 'string') {
      const lower = value.toLowerCase()
      return lower === 'true' || lower === '1'
    }
    return Boolean(value)
  }
  
  // For date/datetime
  if (type.includes('date') || type.includes('time')) {
    if (typeof value === 'string') {
      return value.replace(/^["']|["']$/g, '')
    }
    return String(value)
  }
  
  return String(value)
}

// Update VO field value
function updateVoFieldValue(fieldName, value) {
  if (!voEditorModal.value.fieldValues) {
    voEditorModal.value.fieldValues = {}
  }
  
  const field = (voEditorModal.value.prop?.voFields || []).find(f => f.name === fieldName)
  if (!field) return
  
  const fieldType = (field.type || 'String').toLowerCase()
  
  // Convert value based on type
  let convertedValue = value
  if (fieldType.includes('int') || fieldType.includes('long') || fieldType === 'integer') {
    convertedValue = value === '' ? 0 : parseInt(value, 10)
    if (isNaN(convertedValue)) convertedValue = 0
  } else if (fieldType.includes('decimal') || fieldType.includes('bigdecimal') || fieldType.includes('double') || fieldType.includes('float')) {
    convertedValue = value === '' ? 0.0 : parseFloat(value)
    if (isNaN(convertedValue)) convertedValue = 0.0
  } else if (fieldType.includes('boolean') || fieldType === 'bool') {
    convertedValue = typeof value === 'boolean' ? value : (value === true || value === 'true' || value === '1')
  }
  
  voEditorModal.value.fieldValues[fieldName] = convertedValue
}
</script>

<template>
  <div class="inspector-panel">
    <div class="inspector-panel__header">
      <div class="inspector-panel__title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
        <span>Inspector</span>
        <span v-if="node" class="inspector-panel__subtitle">· {{ schema.title }} · {{ node.data?.name || node.id }}</span>
      </div>
      <div class="inspector-panel__actions">
        <button class="inspector-panel__btn" @click="resetToNode" title="Reload" :disabled="saving">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-3-6.7"></path>
            <polyline points="21 3 21 9 15 9"></polyline>
          </svg>
        </button>
        <button
          class="inspector-panel__btn primary"
          @click="save"
          title="Save"
          :disabled="saving || !node || (!isDirty && !propIsDirty) || propHasBlockingErrors"
        >
          <span v-if="saving">저장 중...</span>
          <span v-else>저장</span>
        </button>
      </div>
    </div>

    <div class="inspector-panel__body">
      <div v-if="!node" class="inspector-panel__empty">
        <div class="inspector-panel__empty-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
          </svg>
        </div>
        <div class="inspector-panel__empty-text">선택된 객체가 없습니다.</div>
        <div class="inspector-panel__empty-hint">캔버스에서 객체를 선택하세요</div>
      </div>
      <div v-else class="inspector-panel__content">
        <div class="inspector-tabs">
          <button
            v-if="nodeLabel === 'UI'"
            class="inspector-tab"
            :class="{ active: activeTab === 'preview' }"
            @click="activeTab = 'preview'"
          >
            UI Preview
          </button>
          <button
            class="inspector-tab"
            :class="{ active: activeTab === 'properties' }"
            @click="activeTab = 'properties'"
          >
            Properties
          </button>
        </div>

        <div v-if="error" class="inspector-alert error">{{ error }}</div>
        <div v-else-if="successMsg" class="inspector-alert success">{{ successMsg }}</div>

        <div v-if="activeTab === 'preview' && nodeLabel === 'UI'" class="inspector-ui-preview">
          <div class="ui-preview-panel__header">
            <div class="ui-preview-panel__title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="3" width="20" height="18" rx="2" />
                <line x1="2" y1="7" x2="22" y2="7" />
              </svg>
              <span>UI Preview</span>
            </div>
            <div class="ui-preview-panel__actions">
              <button class="ui-preview-panel__btn" @click="requestChat" title="Edit with AI">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
              </button>
            </div>
          </div>

          <div class="ui-preview-panel__info">
            <div class="ui-preview-panel__name">{{ node.data?.name }}</div>
            <div v-if="node.data?.attachedToName" class="ui-preview-panel__attached">
              <span class="label">Attached to:</span>
              <span class="value">{{ node.data?.attachedToName }}</span>
            </div>
          </div>

          <div class="ui-preview-panel__content">
            <div v-if="node.data?.template" class="ui-preview-frame">
              <div class="ui-preview-frame__browser-bar">
                <div class="browser-dots">
                  <span></span><span></span><span></span>
                </div>
                <div class="browser-url">preview://{{ node.data?.name }}</div>
              </div>
              <div class="ui-preview-frame__body" v-html="node.data?.template"></div>
            </div>
            <div v-else class="ui-preview-empty">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
                <rect x="2" y="3" width="20" height="18" rx="2" />
                <line x1="2" y1="7" x2="22" y2="7" />
                <rect x="4" y="9" width="7" height="3" rx="0.5" stroke-dasharray="2 1" />
                <rect x="4" y="14" width="16" height="2" rx="0.5" stroke-dasharray="2 1" />
              </svg>
              <p>No wireframe template yet</p>
              <button class="ui-preview-empty__btn" @click="requestChat">Generate with AI</button>
            </div>
          </div>
        </div>

        <div v-if="activeTab === 'properties'" class="inspector-form">
          <div class="inspector-kv">
            <div class="k">id</div>
            <div class="v">{{ node.id }}</div>
          </div>
          <div class="inspector-kv">
            <div class="k">type</div>
            <div class="v">{{ nodeLabel }}</div>
          </div>

          <div v-for="field in schema.fields" :key="field.key" class="inspector-field">
            <label class="inspector-field__label">
              {{ field.label }}
              <span v-if="dirtyFields.includes(field.key)" class="inspector-field__dirty">•</span>
            </label>

            <input
              v-if="field.input === 'text'"
              class="inspector-input"
              type="text"
              :placeholder="field.placeholder"
              v-model="form[field.key]"
              :disabled="saving"
            />

            <textarea
              v-else-if="field.input === 'textarea'"
            class="inspector-textarea"
            :class="{ 'inspector-textarea--template': field.key === 'template' }"
              :placeholder="field.placeholder"
              v-model="form[field.key]"
              :disabled="saving"
            :rows="field.key === 'template' ? 16 : 5"
            />

            <select
              v-else-if="field.input === 'select'"
              class="inspector-select"
              v-model="form[field.key]"
              :disabled="saving"
            >
              <option v-for="opt in (field.options || ProvisioningTypeOptions)" :key="opt" :value="opt">
                {{ opt }}
              </option>
            </select>

            <div v-if="field.helpText" class="inspector-field__help">{{ field.helpText }}</div>
          </div>

          <PropertyEditorTable
            v-if="showPropertyEditor"
            ref="propertyEditorRef"
            :node="node"
            :disabled="saving"
            @state-change="onPropertyEditorStateChange"
          />

          <!-- GWT Editor Section -->
          <div v-if="showGWTEditor" class="inspector-gwt-section">
            <div class="inspector-section__header">
              <h3 class="inspector-section__title">Given / When / Then</h3>
            </div>

            <!-- GWT Mapped Objects Display (Read-only) -->
            <div v-if="form.gwtSets && form.gwtSets.length > 0" class="inspector-gwt-mapped-objects">
              <div class="gwt-preview-item">
                <span class="gwt-preview-label">Given:</span>
                <span class="gwt-preview-value">{{ form.gwtSets[0]?.given?.name || 'Not set' }}</span>
              </div>
              <div class="gwt-preview-item">
                <span class="gwt-preview-label">When:</span>
                <span class="gwt-preview-value">{{ form.gwtSets[0]?.when?.name || 'Not set' }}</span>
              </div>
              <div class="gwt-preview-item">
                <span class="gwt-preview-label">Then:</span>
                <span class="gwt-preview-value">{{ form.gwtSets[0]?.then?.name || 'Not set' }}</span>
              </div>
              <div v-if="form.gwtSets.length > 1" class="gwt-test-cases-count">
                <span class="gwt-test-cases-count-text">{{ form.gwtSets.length }} test cases</span>
              </div>
              <div class="gwt-preview-actions">
                <button
                  class="inspector-section__btn"
                  @click="openGWTDetailModal()"
                  :disabled="saving"
                  title="Edit GWT Details"
                >
                  Detail
                </button>
              </div>
            </div>
            
            <!-- Policy Mapped Objects from Relationships (when GWT not yet generated) -->
            <div v-else-if="nodeLabel === 'Policy'" class="inspector-gwt-mapped-objects">
              <div class="gwt-preview-item">
                <span class="gwt-preview-label">Given:</span>
                <span class="gwt-preview-value">{{ getPolicyMappedGiven() || 'Not set' }}</span>
              </div>
              <div class="gwt-preview-item">
                <span class="gwt-preview-label">When:</span>
                <span class="gwt-preview-value">{{ getPolicyMappedWhen() || 'Not set' }}</span>
              </div>
              <div class="gwt-preview-item">
                <span class="gwt-preview-label">Then:</span>
                <span class="gwt-preview-value">{{ getPolicyMappedThen() || 'Not set' }}</span>
              </div>
              <div class="gwt-preview-actions">
                <button
                  class="inspector-section__btn"
                  @click="openGWTDetailModal()"
                  :disabled="saving"
                  title="Open GWT Detail Modal"
                >
                  Detail
                </button>
              </div>
            </div>
            
            <!-- Empty State (for Command) -->
            <div v-else class="inspector-gwt-empty">
              <div class="gwt-empty-message">No GWT test cases defined</div>
              <button
                class="inspector-section__btn"
                @click="openGWTDetailModal()"
                :disabled="saving"
                title="Open GWT Detail Modal"
              >
                Detail
              </button>
            </div>

            <!-- Full GWT Editor (hidden, will be moved to modal) -->
            <div v-if="false && (form.given || form.when || form.then)" class="inspector-gwt-editor">
              <!-- Given -->
              <div class="gwt-field">
                <label class="gwt-field__label">
                  Given
                  <span v-if="dirtyFields.includes('given')" class="inspector-field__dirty">•</span>
                </label>
                <input
                  class="inspector-input"
                  type="text"
                  placeholder="e.g., Command: CancelOrder or Event: OrderCancelled"
                  v-model="form.given.name"
                  :disabled="saving"
                />
                <textarea
                  class="inspector-textarea"
                  rows="2"
                  placeholder="Given description (optional)"
                  v-model="form.given.description"
                  :disabled="saving"
                />
                <!-- Field Values -->
                <div v-if="form.given" class="gwt-field-values">
                  <label class="gwt-field-values__label">Field Values</label>
                  <div v-for="(value, key) in form.given.fieldValues" :key="key" class="gwt-field-value-row">
                    <input
                      class="inspector-input gwt-field-value-key"
                      type="text"
                      :value="key"
                      @input="form.given.fieldValues[$event.target.value] = form.given.fieldValues[key]; if ($event.target.value !== key) delete form.given.fieldValues[key]"
                      placeholder="Property name"
                      :disabled="saving"
                    />
                    <span class="gwt-field-value-separator">:</span>
                    <input
                      class="inspector-input gwt-field-value-value"
                      type="text"
                      v-model="form.given.fieldValues[key]"
                      placeholder="Test value"
                      :disabled="saving"
                    />
                    <button
                      class="gwt-field-value-remove"
                      @click="removeFieldValue('given', key)"
                      :disabled="saving"
                      title="Remove field"
                    >
                      ×
                    </button>
                  </div>
                  <button
                    class="gwt-field-value-add"
                    @click="addFieldValue('given')"
                    :disabled="saving"
                    title="Add field value"
                  >
                    + Add Field Value
                  </button>
                </div>
                <div class="gwt-field__actions">
                  <button
                    class="gwt-field__btn"
                    @click="removeGWT('given')"
                    :disabled="saving"
                    title="Remove Given"
                  >
                    Remove
                  </button>
                </div>
              </div>

              <!-- When -->
              <div class="gwt-field">
                <label class="gwt-field__label">
                  When
                  <span v-if="dirtyFields.includes('when')" class="inspector-field__dirty">•</span>
                </label>
                <input
                  class="inspector-input"
                  type="text"
                  placeholder="e.g., Aggregate: Order"
                  v-model="form.when.name"
                  :disabled="saving"
                />
                <textarea
                  class="inspector-textarea"
                  rows="2"
                  placeholder="When description (optional)"
                  v-model="form.when.description"
                  :disabled="saving"
                />
                <!-- Field Values -->
                <div v-if="form.when" class="gwt-field-values">
                  <label class="gwt-field-values__label">Field Values</label>
                  <div v-for="(value, key) in form.when.fieldValues" :key="key" class="gwt-field-value-row">
                    <input
                      class="inspector-input gwt-field-value-key"
                      type="text"
                      :value="key"
                      @input="form.when.fieldValues[$event.target.value] = form.when.fieldValues[key]; if ($event.target.value !== key) delete form.when.fieldValues[key]"
                      placeholder="Property name"
                      :disabled="saving"
                    />
                    <span class="gwt-field-value-separator">:</span>
                    <input
                      class="inspector-input gwt-field-value-value"
                      type="text"
                      v-model="form.when.fieldValues[key]"
                      placeholder="Test value"
                      :disabled="saving"
                    />
                    <button
                      class="gwt-field-value-remove"
                      @click="removeFieldValue('when', key)"
                      :disabled="saving"
                      title="Remove field"
                    >
                      ×
                    </button>
                  </div>
                  <button
                    class="gwt-field-value-add"
                    @click="addFieldValue('when')"
                    :disabled="saving"
                    title="Add field value"
                  >
                    + Add Field Value
                  </button>
                </div>
                <div class="gwt-field__actions">
                  <button
                    class="gwt-field__btn"
                    @click="removeGWT('when')"
                    :disabled="saving"
                    title="Remove When"
                  >
                    Remove
                  </button>
                </div>
              </div>

              <!-- Then -->
              <div class="gwt-field">
                <label class="gwt-field__label">
                  Then
                  <span v-if="dirtyFields.includes('then')" class="inspector-field__dirty">•</span>
                </label>
                <input
                  class="inspector-input"
                  type="text"
                  placeholder="e.g., Event: OrderCancelled"
                  v-model="form.then.name"
                  :disabled="saving"
                />
                <textarea
                  class="inspector-textarea"
                  rows="2"
                  placeholder="Then description (optional)"
                  v-model="form.then.description"
                  :disabled="saving"
                />
                <!-- Field Values -->
                <div v-if="form.then" class="gwt-field-values">
                  <label class="gwt-field-values__label">Field Values</label>
                  <div v-for="(value, key) in form.then.fieldValues" :key="key" class="gwt-field-value-row">
                    <input
                      class="inspector-input gwt-field-value-key"
                      type="text"
                      :value="key"
                      @input="form.then.fieldValues[$event.target.value] = form.then.fieldValues[key]; if ($event.target.value !== key) delete form.then.fieldValues[key]"
                      placeholder="Property name"
                      :disabled="saving"
                    />
                    <span class="gwt-field-value-separator">:</span>
                    <input
                      class="inspector-input gwt-field-value-value"
                      type="text"
                      v-model="form.then.fieldValues[key]"
                      placeholder="Test value"
                      :disabled="saving"
                    />
                    <button
                      class="gwt-field-value-remove"
                      @click="removeFieldValue('then', key)"
                      :disabled="saving"
                      title="Remove field"
                    >
                      ×
                    </button>
                  </div>
                  <button
                    class="gwt-field-value-add"
                    @click="addFieldValue('then')"
                    :disabled="saving"
                    title="Add field value"
                  >
                    + Add Field Value
                  </button>
                </div>
                <div class="gwt-field__actions">
                  <button
                    class="gwt-field__btn"
                    @click="removeGWT('then')"
                    :disabled="saving"
                    title="Remove Then"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
    
    <!-- GWT Detail Modal -->
    <div v-if="showGWTDetailModal" class="gwt-detail-modal-overlay" @click.self="closeGWTDetailModal">
      <div class="gwt-detail-modal">
        <div class="gwt-detail-modal__header">
          <h3 class="gwt-detail-modal__title">Given / When / Then Details</h3>
          <button class="gwt-detail-modal__close" @click="closeGWTDetailModal" title="Close">
            ×
          </button>
        </div>
        
        <div class="gwt-detail-modal__content">
          <!-- Business Flow Description -->
          <div v-if="form.gwtSets.length > 0 && (form.gwtSets[0].scenarioDescription || getGWTDescription(form.gwtSets[0]))" class="gwt-description-header">
            <div class="gwt-description__label">Business Flow:</div>
            <div class="gwt-description__text">{{ form.gwtSets[0].scenarioDescription || getGWTDescription(form.gwtSets[0]) }}</div>
          </div>
          
          <!-- Single GWT Table: Properties as columns, Test cases as rows -->
          <div v-if="form.gwtSets.length > 0" class="gwt-unified-table">
            <table class="gwt-decision-table">
              <thead>
                <!-- Section Header Row: Given/When/Then groups -->
                <tr>
                  <th class="gwt-decision-table__row-header-col" rowspan="2"></th>
                  <!-- Given Section Header -->
                  <th 
                    v-if="form.gwtSets[0]?.given"
                    :colspan="Math.max(getAvailableProperties(form.gwtSets[0], 'given').length, 1)"
                    class="gwt-decision-table__section-header gwt-decision-table__section-header--given"
                  >
                    <div class="gwt-decision-table__section-title">Given</div>
                    <div class="gwt-decision-table__section-subtitle">
                      {{ nodeLabel === 'Policy' ? (getPolicyMappedGiven() || form.gwtSets[0].given.name) : form.gwtSets[0].given.name }}
                    </div>
                  </th>
                  <!-- When Section Header -->
                  <th 
                    v-if="form.gwtSets[0]?.when"
                    :colspan="Math.max(getAvailableProperties(form.gwtSets[0], 'when').length, 1)"
                    class="gwt-decision-table__section-header gwt-decision-table__section-header--when"
                  >
                    <div class="gwt-decision-table__section-title">When</div>
                    <div class="gwt-decision-table__section-subtitle">{{ form.gwtSets[0].when.name }}</div>
                  </th>
                  <!-- Then Section Header -->
                  <th 
                    v-if="form.gwtSets[0]?.then"
                    :colspan="Math.max(getAvailableProperties(form.gwtSets[0], 'then').length, 1)"
                    class="gwt-decision-table__section-header gwt-decision-table__section-header--then"
                  >
                    <div class="gwt-decision-table__section-title">Then</div>
                    <div class="gwt-decision-table__section-subtitle">{{ form.gwtSets[0].then.name }}</div>
                  </th>
                  <th class="gwt-decision-table__action-col" rowspan="2"></th>
                </tr>
                <!-- Field Names Row -->
                <tr>
                  <!-- Given Field Names -->
                  <template v-if="form.gwtSets[0]?.given">
                    <template v-if="getAvailableProperties(form.gwtSets[0], 'given').length > 0">
                      <th 
                        v-for="prop in getAvailableProperties(form.gwtSets[0], 'given')" 
                        :key="`given-${prop.name}`"
                        class="gwt-decision-table__property-col"
                      >
                        {{ prop.name }}
                      </th>
                    </template>
                    <th v-else class="gwt-decision-table__property-col">
                      (No properties)
                    </th>
                  </template>
                  <!-- When Field Names -->
                  <template v-if="form.gwtSets[0]?.when">
                    <th 
                      v-for="prop in getAvailableProperties(form.gwtSets[0], 'when')" 
                      :key="`when-${prop.name}`"
                      class="gwt-decision-table__property-col"
                    >
                      {{ prop.name }}
                    </th>
                  </template>
                  <!-- Then Field Names -->
                  <template v-if="form.gwtSets[0]?.then">
                    <th 
                      v-for="prop in getAvailableProperties(form.gwtSets[0], 'then')" 
                      :key="`then-${prop.name}`"
                      class="gwt-decision-table__property-col"
                    >
                      {{ prop.name }}
                    </th>
                  </template>
                </tr>
              </thead>
              <tbody>
                <tr 
                  v-for="(gwtSet, rowIndex) in form.gwtSets" 
                  :key="rowIndex"
                  class="gwt-decision-table__row"
                >
                  <td class="gwt-decision-table__row-header-cell">{{ rowIndex + 1 }}</td>
                  <!-- Given Values -->
                  <template v-if="form.gwtSets[0]?.given">
                    <template v-if="getAvailableProperties(form.gwtSets[0], 'given').length > 0">
                      <td 
                        v-for="prop in getAvailableProperties(form.gwtSets[0], 'given')" 
                        :key="`given-${prop.name}-${rowIndex}`"
                        class="gwt-decision-table__value-cell"
                      >
                        <!-- Enum: Use select dropdown -->
                        <select
                          v-if="gwtSet.given && gwtSet.given.fieldValues && getInputTypeForProperty(prop) === 'select'"
                          class="gwt-decision-table__input"
                          :value="formatFieldValueForInput(gwtSet.given.fieldValues[prop.name], prop)"
                          @change="updateFieldValue(gwtSet, 'given', prop.name, $event.target.value)"
                          :disabled="saving"
                        >
                          <option value="">-- Select --</option>
                          <option 
                            v-for="item in (prop.enumItems || [])" 
                            :key="item" 
                            :value="item"
                          >
                            {{ item }}
                          </option>
                        </select>
                        <!-- Checkbox for boolean -->
                        <input
                          v-else-if="gwtSet.given && gwtSet.given.fieldValues && getInputTypeForProperty(prop) === 'checkbox'"
                          class="gwt-decision-table__input"
                          type="checkbox"
                          :checked="parseBooleanValue(gwtSet.given.fieldValues[prop.name])"
                          @change="updateFieldValue(gwtSet, 'given', prop.name, $event.target.checked)"
                          :disabled="saving"
                        />
                        <!-- ValueObject: Show button to open editor modal -->
                        <div
                          v-else-if="gwtSet.given && gwtSet.given.fieldValues && (prop.fieldType === 'valueObject' || String(prop.type).toLowerCase() === 'valueobject')"
                          class="gwt-vo-editor-wrapper"
                        >
                          <textarea
                            class="gwt-decision-table__input gwt-decision-table__textarea"
                            :value="formatFieldValueForInput(gwtSet.given.fieldValues[prop.name], prop)"
                            @input="updateFieldValue(gwtSet, 'given', prop.name, $event.target.value)"
                            :disabled="saving"
                            :placeholder="getPlaceholderForProperty(prop)"
                            rows="2"
                            readonly
                          />
                          <button
                            class="gwt-vo-editor-btn"
                            @click="openVoEditor(gwtSet, 'given', prop.name, prop)"
                            :disabled="saving"
                            title="ValueObject 구조 편집"
                          >
                            ✏️
                          </button>
                        </div>
                        <!-- Other input types -->
                        <input
                          v-else-if="gwtSet.given && gwtSet.given.fieldValues"
                          class="gwt-decision-table__input"
                          :type="getInputTypeForProperty(prop)"
                          :value="formatFieldValueForInput(gwtSet.given.fieldValues[prop.name], prop)"
                          @input="updateFieldValue(gwtSet, 'given', prop.name, $event.target.value)"
                          :disabled="saving"
                          :placeholder="getPlaceholderForProperty(prop)"
                          :step="prop.type && (prop.type.includes('Decimal') || prop.type.includes('BigDecimal') || prop.type.includes('Double') || prop.type.includes('Float')) ? '0.01' : undefined"
                        />
                        <span v-else class="gwt-decision-table__empty">-</span>
                      </td>
                    </template>
                    <td v-else class="gwt-decision-table__value-cell">
                      <span class="gwt-decision-table__empty">No properties available</span>
                    </td>
                  </template>
                  <!-- When Values -->
                  <template v-if="form.gwtSets[0]?.when">
                    <td 
                      v-for="prop in getAvailableProperties(form.gwtSets[0], 'when')" 
                      :key="`when-${prop.name}-${rowIndex}`"
                      class="gwt-decision-table__value-cell"
                    >
                      <!-- Enum: Use select dropdown -->
                      <select
                        v-if="gwtSet.when && gwtSet.when.fieldValues && getInputTypeForProperty(prop) === 'select'"
                        class="gwt-decision-table__input"
                        :value="formatFieldValueForInput(gwtSet.when.fieldValues[prop.name], prop)"
                        @change="updateFieldValue(gwtSet, 'when', prop.name, $event.target.value)"
                        :disabled="saving"
                      >
                        <option value="">-- Select --</option>
                        <option 
                          v-for="item in (prop.enumItems || [])" 
                          :key="item" 
                          :value="item"
                        >
                          {{ item }}
                        </option>
                      </select>
                      <!-- Checkbox for boolean -->
                      <input
                        v-else-if="gwtSet.when && gwtSet.when.fieldValues && getInputTypeForProperty(prop) === 'checkbox'"
                        class="gwt-decision-table__input"
                        type="checkbox"
                        :checked="parseBooleanValue(gwtSet.when.fieldValues[prop.name])"
                        @change="updateFieldValue(gwtSet, 'when', prop.name, $event.target.checked)"
                        :disabled="saving"
                      />
                      <!-- ValueObject: Show button to open editor modal -->
                      <div
                        v-else-if="gwtSet.when && gwtSet.when.fieldValues && (prop.fieldType === 'valueObject' || String(prop.type).toLowerCase() === 'valueobject')"
                        class="gwt-vo-editor-wrapper"
                      >
                        <textarea
                          class="gwt-decision-table__input gwt-decision-table__textarea"
                          :value="formatFieldValueForInput(gwtSet.when.fieldValues[prop.name], prop)"
                          @input="updateFieldValue(gwtSet, 'when', prop.name, $event.target.value)"
                          :disabled="saving"
                          :placeholder="getPlaceholderForProperty(prop)"
                          rows="2"
                          readonly
                        />
                        <button
                          class="gwt-vo-editor-btn"
                          @click="openVoEditor(gwtSet, 'when', prop.name, prop)"
                          :disabled="saving"
                          title="ValueObject 구조 편집"
                        >
                          ✏️
                        </button>
                      </div>
                      <!-- Other input types -->
                      <input
                        v-else-if="gwtSet.when && gwtSet.when.fieldValues"
                        class="gwt-decision-table__input"
                        :type="getInputTypeForProperty(prop)"
                        :value="formatFieldValueForInput(gwtSet.when.fieldValues[prop.name], prop)"
                        @input="updateFieldValue(gwtSet, 'when', prop.name, $event.target.value)"
                        :disabled="saving"
                        :placeholder="getPlaceholderForProperty(prop)"
                        :step="prop.type && (prop.type.includes('Decimal') || prop.type.includes('BigDecimal') || prop.type.includes('Double') || prop.type.includes('Float')) ? '0.01' : undefined"
                      />
                      <span v-else class="gwt-decision-table__empty">-</span>
                    </td>
                  </template>
                  <!-- Then Values -->
                  <template v-if="form.gwtSets[0]?.then">
                    <td 
                      v-for="prop in getAvailableProperties(form.gwtSets[0], 'then')" 
                      :key="`then-${prop.name}-${rowIndex}`"
                      class="gwt-decision-table__value-cell"
                    >
                      <!-- Enum: Use select dropdown -->
                      <select
                        v-if="gwtSet.then && gwtSet.then.fieldValues && getInputTypeForProperty(prop) === 'select'"
                        class="gwt-decision-table__input"
                        :value="formatFieldValueForInput(gwtSet.then.fieldValues[prop.name], prop)"
                        @change="updateFieldValue(gwtSet, 'then', prop.name, $event.target.value)"
                        :disabled="saving"
                      >
                        <option value="">-- Select --</option>
                        <option 
                          v-for="item in (prop.enumItems || [])" 
                          :key="item" 
                          :value="item"
                        >
                          {{ item }}
                        </option>
                      </select>
                      <!-- Checkbox for boolean -->
                      <input
                        v-else-if="gwtSet.then && gwtSet.then.fieldValues && getInputTypeForProperty(prop) === 'checkbox'"
                        class="gwt-decision-table__input"
                        type="checkbox"
                        :checked="parseBooleanValue(gwtSet.then.fieldValues[prop.name])"
                        @change="updateFieldValue(gwtSet, 'then', prop.name, $event.target.checked)"
                        :disabled="saving"
                      />
                      <!-- ValueObject: Show button to open editor modal -->
                      <div
                        v-else-if="gwtSet.then && gwtSet.then.fieldValues && (prop.fieldType === 'valueObject' || String(prop.type).toLowerCase() === 'valueobject')"
                        class="gwt-vo-editor-wrapper"
                      >
                        <textarea
                          class="gwt-decision-table__input gwt-decision-table__textarea"
                          :value="formatFieldValueForInput(gwtSet.then.fieldValues[prop.name], prop)"
                          @input="updateFieldValue(gwtSet, 'then', prop.name, $event.target.value)"
                          :disabled="saving"
                          :placeholder="getPlaceholderForProperty(prop)"
                          rows="2"
                          readonly
                        />
                        <button
                          class="gwt-vo-editor-btn"
                          @click="openVoEditor(gwtSet, 'then', prop.name, prop)"
                          :disabled="saving"
                          title="ValueObject 구조 편집"
                        >
                          ✏️
                        </button>
                      </div>
                      <!-- Other input types -->
                      <input
                        v-else-if="gwtSet.then && gwtSet.then.fieldValues"
                        class="gwt-decision-table__input"
                        :type="getInputTypeForProperty(prop)"
                        :value="formatFieldValueForInput(gwtSet.then.fieldValues[prop.name], prop)"
                        @input="updateFieldValue(gwtSet, 'then', prop.name, $event.target.value)"
                        :disabled="saving"
                        :placeholder="getPlaceholderForProperty(prop)"
                        :step="prop.type && (prop.type.includes('Decimal') || prop.type.includes('BigDecimal') || prop.type.includes('Double') || prop.type.includes('Float')) ? '0.01' : undefined"
                      />
                      <span v-else class="gwt-decision-table__empty">-</span>
                    </td>
                  </template>
                  <td class="gwt-decision-table__action-cell">
                    <button
                      class="gwt-decision-table__remove"
                      @click="removeGWTSet(rowIndex)"
                      :disabled="saving || form.gwtSets.length === 1"
                      title="Remove test case"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      </svg>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
            
            <!-- Add Row Button -->
            <div class="gwt-decision-table__add">
              <button
                class="gwt-decision-table__add-btn"
                @click="addGWTSet"
                :disabled="saving"
                title="Add new test case row"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="12" y1="5" x2="12" y2="19"></line>
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
                Add Row
              </button>
            </div>
          </div>
          
          <!-- Empty State -->
          <div v-else class="gwt-empty-state">
            <div class="gwt-empty-message">No GWT test cases. Click "Add Row" to create one.</div>
            <button
              class="inspector-section__btn"
              @click="addGWTSet"
              :disabled="saving"
              title="Add first test case row"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
              Add Row
            </button>
          </div>
        </div>
        
        <div class="gwt-detail-modal__footer">
          <button class="inspector-section__btn" @click="closeGWTDetailModal">Close</button>
        </div>
      </div>
    </div>
  </div>

  <!-- ValueObject Editor Modal -->
  <div v-if="voEditorModal.open" class="vo-editor-modal-overlay" @click.self="closeVoEditor">
    <div class="vo-editor-modal">
      <div class="vo-editor-modal__header">
        <h3 class="vo-editor-modal__title">
          ValueObject 편집: {{ voEditorModal.propName }}
        </h3>
        <button class="vo-editor-modal__close" @click="closeVoEditor">×</button>
      </div>
      <div class="vo-editor-modal__content">
        <div v-if="!voEditorModal.prop?.voFields || voEditorModal.prop.voFields.length === 0" class="vo-editor-empty">
          <p>ValueObject 필드 정보가 없습니다.</p>
        </div>
        <div v-else class="vo-editor-fields">
          <div 
            v-for="field in voEditorModal.prop.voFields" 
            :key="field.name"
            class="vo-editor-field"
          >
            <label class="vo-editor-field__label">
              <span class="vo-editor-field__name">{{ field.name }}</span>
              <span class="vo-editor-field__type">{{ field.type || 'String' }}</span>
            </label>
            <!-- Checkbox for boolean -->
            <input
              v-if="getVoFieldInputType(field.type) === 'checkbox'"
              class="vo-editor-field__input"
              type="checkbox"
              :checked="formatVoFieldValueForInput(voEditorModal.fieldValues[field.name], field.type)"
              @change="updateVoFieldValue(field.name, $event.target.checked)"
              :disabled="saving"
            />
            <!-- Number input -->
            <input
              v-else-if="getVoFieldInputType(field.type) === 'number'"
              class="vo-editor-field__input"
              type="number"
              :value="formatVoFieldValueForInput(voEditorModal.fieldValues[field.name], field.type)"
              @input="updateVoFieldValue(field.name, $event.target.value)"
              :disabled="saving"
              :step="field.type && (field.type.includes('Decimal') || field.type.includes('BigDecimal') || field.type.includes('Double') || field.type.includes('Float')) ? '0.01' : undefined"
            />
            <!-- Date input -->
            <input
              v-else-if="getVoFieldInputType(field.type) === 'date'"
              class="vo-editor-field__input"
              type="date"
              :value="formatVoFieldValueForInput(voEditorModal.fieldValues[field.name], field.type)"
              @input="updateVoFieldValue(field.name, $event.target.value)"
              :disabled="saving"
            />
            <!-- Datetime input -->
            <input
              v-else-if="getVoFieldInputType(field.type) === 'datetime-local'"
              class="vo-editor-field__input"
              type="datetime-local"
              :value="formatVoFieldValueForInput(voEditorModal.fieldValues[field.name], field.type)"
              @input="updateVoFieldValue(field.name, $event.target.value)"
              :disabled="saving"
            />
            <!-- Time input -->
            <input
              v-else-if="getVoFieldInputType(field.type) === 'time'"
              class="vo-editor-field__input"
              type="time"
              :value="formatVoFieldValueForInput(voEditorModal.fieldValues[field.name], field.type)"
              @input="updateVoFieldValue(field.name, $event.target.value)"
              :disabled="saving"
            />
            <!-- Text input -->
            <input
              v-else
              class="vo-editor-field__input"
              type="text"
              :value="formatVoFieldValueForInput(voEditorModal.fieldValues[field.name], field.type)"
              @input="updateVoFieldValue(field.name, $event.target.value)"
              :disabled="saving"
            />
          </div>
        </div>
      </div>
      <div class="vo-editor-modal__footer">
        <button class="vo-editor-modal__btn vo-editor-modal__btn--cancel" @click="closeVoEditor">
          취소
        </button>
        <button 
          class="vo-editor-modal__btn vo-editor-modal__btn--save" 
          @click="saveVoEditor"
          :disabled="saving"
        >
          저장
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.inspector-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-bg-secondary);
  border-left: 1px solid var(--color-border);
}

.inspector-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  padding-left: calc(var(--spacing-md) + 20px);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-tertiary);
}

.inspector-panel__title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.inspector-panel__subtitle {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--color-text-light);
}

.inspector-panel__btn {
  background: none;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.inspector-panel__btn:hover {
  background: var(--color-bg);
  color: var(--color-text);
}

.inspector-panel__btn.primary {
  padding: 5px 8px;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text-bright);
  font-size: 0.7rem;
  font-weight: 600;
}

.inspector-panel__btn.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.inspector-panel__body {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md);
}

.inspector-panel__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: var(--color-text-light);
}

.inspector-panel__empty-icon {
  margin-bottom: var(--spacing-md);
}

.inspector-panel__empty-text {
  font-size: 0.75rem;
  line-height: 1.5;
  margin-bottom: var(--spacing-sm);
}

.inspector-panel__empty-hint {
  font-size: 0.65rem;
  opacity: 0.7;
  max-width: 200px;
}

.inspector-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: var(--spacing-md);
}

.inspector-tab {
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text-light);
  padding: 5px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.7rem;
}

.inspector-tab.active {
  color: var(--color-text-bright);
  border-color: var(--color-accent);
}

.inspector-alert {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  margin-bottom: var(--spacing-md);
  font-size: 0.7rem;
  white-space: pre-wrap;
}

.inspector-alert.error {
  background: rgba(255, 107, 107, 0.08);
  border-color: rgba(255, 107, 107, 0.25);
  color: #ff6b6b;
}

.inspector-alert.success {
  background: rgba(64, 192, 87, 0.08);
  border-color: rgba(64, 192, 87, 0.25);
  color: #40c057;
}

.inspector-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.inspector-kv {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 0.7rem;
}

.inspector-kv .k {
  color: var(--color-text-light);
  opacity: 0.8;
}

.inspector-kv .v {
  color: var(--color-text);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 0.65rem;
}

.inspector-field__label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin-bottom: 5px;
}

.inspector-field__dirty {
  color: var(--color-accent);
  font-size: 1rem;
  line-height: 0;
}

.inspector-input,
.inspector-textarea,
.inspector-select {
  width: 100%;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text);
  border-radius: var(--radius-sm);
  padding: 6px 8px;
  font-size: 0.75rem;
}

.inspector-textarea {
  resize: vertical;
}

.inspector-textarea--template {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 0.65rem;
  line-height: 1.35;
  white-space: pre;
}

.inspector-field__help {
  margin-top: 5px;
  color: var(--color-text-light);
  font-size: 0.62rem;
  line-height: 1.3;
}

.inspector-readonly {
  margin-top: 10px;
  background: var(--color-bg);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  padding: 10px 12px;
}

.inspector-readonly__label {
  color: var(--color-text-light);
  font-size: 0.65rem;
  font-weight: 600;
  margin-bottom: 5px;
}

.inspector-readonly__pre {
  margin: 0;
  max-height: 200px;
  overflow: auto;
  font-size: 0.6rem;
  color: var(--color-text);
}

.inspector-readonly__section {
  margin-top: var(--spacing-md);
}

.inspector-readonly__section:first-child {
  margin-top: 0;
}

.inspector-readonly__item {
  padding: 4px 0;
  border-bottom: 1px solid var(--color-border);
}

.inspector-readonly__item:last-child {
  border-bottom: none;
}

.inspector-readonly__ref {
  color: var(--color-text-light);
  font-size: 0.7rem;
  margin-left: 4px;
}

.inspector-ui-preview {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.ui-preview-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-tertiary);
}

.ui-preview-panel__title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.ui-preview-panel__actions {
  display: flex;
  gap: 4px;
}

.ui-preview-panel__btn {
  background: none;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.ui-preview-panel__btn:hover {
  background: var(--color-bg);
  color: var(--color-text);
}

.ui-preview-panel__info {
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
}

.ui-preview-panel__name {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin-bottom: 3px;
}

.ui-preview-panel__attached {
  font-size: 0.65rem;
  color: var(--color-text-light);
}

.ui-preview-panel__attached .label {
  opacity: 0.7;
}

.ui-preview-panel__attached .value {
  color: var(--color-accent);
  margin-left: 4px;
}

.ui-preview-panel__content {
  overflow-y: auto;
  padding: var(--spacing-md);
}

.ui-preview-frame {
  background: #ffffff;
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.ui-preview-frame__browser-bar {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: 8px 12px;
  background: #e9ecef;
  border-bottom: 1px solid #dee2e6;
}

.browser-dots {
  display: flex;
  gap: 6px;
}

.browser-dots span {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #adb5bd;
}

.browser-dots span:first-child { background: #ff6b6b; }
.browser-dots span:nth-child(2) { background: #ffd43b; }
.browser-dots span:last-child { background: #69db7c; }

.browser-url {
  flex: 1;
  font-size: 0.6rem;
  color: #495057;
  background: #f8f9fa;
  padding: 3px 8px;
  border-radius: 4px;
}

.ui-preview-frame__body {
  padding: 12px;
  min-height: 180px;
  color: #212529;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 0.72rem;
}

.ui-preview-frame__body :deep(input),
.ui-preview-frame__body :deep(select),
.ui-preview-frame__body :deep(textarea) {
  display: block;
  width: 100%;
  padding: 6px 10px;
  margin-bottom: 10px;
  border: 2px dashed #adb5bd;
  border-radius: 4px;
  background: #f8f9fa;
  font-size: 0.72rem;
}

.ui-preview-frame__body :deep(button) {
  padding: 6px 12px;
  border: 2px dashed #228be6;
  border-radius: 4px;
  background: #e7f5ff;
  color: #1971c2;
  font-size: 0.72rem;
  cursor: pointer;
  margin: 3px;
}

.ui-preview-frame__body :deep(label) {
  display: block;
  font-size: 0.65rem;
  font-weight: 600;
  color: #495057;
  margin-bottom: 3px;
}

.ui-preview-frame__body :deep(h1) {
  color: #212529;
  margin-bottom: 10px;
  font-size: 1rem;
}

.ui-preview-frame__body :deep(h2) {
  color: #212529;
  margin-bottom: 8px;
  font-size: 0.9rem;
}

.ui-preview-frame__body :deep(h3) {
  color: #212529;
  margin-bottom: 6px;
  font-size: 0.8rem;
}

.ui-preview-frame__body :deep(.form-group) {
  margin-bottom: 12px;
}

.ui-preview-frame__body :deep(.btn-group) {
  display: flex;
  gap: 6px;
  margin-top: 12px;
}

.ui-preview-frame__body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.7rem;
}

.ui-preview-frame__body :deep(th),
.ui-preview-frame__body :deep(td) {
  padding: 4px 6px;
  text-align: left;
  font-size: 0.68rem;
}

.ui-preview-frame__body :deep(th) {
  font-weight: 600;
}

.ui-preview-frame__body :deep(p) {
  font-size: 0.72rem;
  margin-bottom: 8px;
}

.ui-preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 260px;
  text-align: center;
  color: var(--color-text-light);
}

.ui-preview-empty p {
  margin: var(--spacing-md) 0;
  font-size: 0.75rem;
}

.ui-preview-empty__btn {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ui-preview-empty__btn:hover {
  background: #1c7ed6;
  transform: translateY(-1px);
}

/* GWT Editor Section */
.inspector-gwt-section {
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-border);
}

/* GWT Sets Container */
.inspector-gwt-sets {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.gwt-set-preview {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.gwt-set-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

.gwt-set-number {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.gwt-set-actions {
  display: flex;
  gap: 6px;
}

.inspector-gwt-empty {
  padding: 20px;
  text-align: center;
  background: var(--color-bg);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
}

.inspector-gwt-add-set {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
}

.gwt-test-cases-count {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
  text-align: center;
}

.gwt-test-cases-count-text {
  font-size: 0.65rem;
  color: var(--color-text-light);
}

.gwt-empty-message {
  font-size: 0.7rem;
  color: var(--color-text-light);
  margin-bottom: 12px;
}

/* GWT Detail Modal */
.gwt-detail-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.gwt-detail-modal {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  width: 95%;
  max-width: 1200px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.gwt-detail-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
}

.gwt-detail-modal__title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0;
}

.gwt-detail-modal__close {
  width: 32px;
  height: 32px;
  padding: 0;
  background: transparent;
  border: none;
  color: var(--color-text);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.gwt-detail-modal__close:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-bright);
}

.gwt-detail-modal__content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.gwt-description-header {
  padding: 16px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: 20px;
}

.gwt-description__label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}

.gwt-description__text {
  font-size: 0.9rem;
  color: var(--color-text);
  line-height: 1.5;
}

.gwt-mapped-objects-header {
  padding: 16px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: 20px;
}

.gwt-mapped-object {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.gwt-mapped-object:last-child {
  margin-bottom: 0;
}

.gwt-mapped-object__label {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--color-text-bright);
  min-width: 60px;
}

.gwt-mapped-object__value {
  font-size: 0.75rem;
  color: var(--color-text);
}

.gwt-detail-sets {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.gwt-detail-set {
  padding: 16px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.gwt-detail-set__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}

.gwt-detail-set__title {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.gwt-detail-set__remove {
  padding: 4px 8px;
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid rgba(255, 107, 107, 0.3);
  border-radius: var(--radius-sm);
  color: #ff6b6b;
  font-size: 0.65rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.gwt-detail-set__remove:hover:not(:disabled) {
  background: rgba(255, 107, 107, 0.2);
  border-color: #ff6b6b;
}

/* Unified GWT Decision Table */
.gwt-unified-table {
  margin-top: 16px;
}

.gwt-decision-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.gwt-decision-table thead {
  background: var(--color-bg-tertiary);
}

.gwt-decision-table th {
  padding: 12px;
  text-align: left;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--color-text-bright);
  border-bottom: 2px solid var(--color-border);
}

.gwt-decision-table__row-header-col {
  width: 40px;
  min-width: 40px;
  text-align: center;
}

.gwt-decision-table__property-col {
  width: 150px;
  min-width: 150px;
  text-align: center;
}

.gwt-decision-table__value-col {
  width: 150px;
  min-width: 150px;
  padding: 8px;
}

.gwt-decision-table__action-col {
  width: 40px;
  min-width: 40px;
  text-align: center;
}

.gwt-decision-table__section-header {
  padding: 12px;
  text-align: center;
  border-right: 2px solid var(--color-border);
  background: var(--color-bg-tertiary);
}

.gwt-decision-table__section-header--given {
  background: rgba(92, 124, 250, 0.1);
  border-color: rgba(92, 124, 250, 0.3);
}

.gwt-decision-table__section-header--when {
  background: rgba(253, 126, 20, 0.1);
  border-color: rgba(253, 126, 20, 0.3);
}

.gwt-decision-table__section-header--then {
  background: rgba(253, 126, 20, 0.1);
  border-color: rgba(253, 126, 20, 0.3);
}

.gwt-decision-table__section-title {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-text-bright);
  margin-bottom: 4px;
}

.gwt-decision-table__section-subtitle {
  font-size: 0.65rem;
  color: var(--color-text-light);
  font-weight: normal;
}

.gwt-decision-table__property-col {
  padding: 8px 12px;
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--color-text);
  background: var(--color-bg-tertiary);
  border-right: 1px solid var(--color-border);
  text-align: center;
}

.gwt-decision-table__row {
  border-bottom: 1px solid var(--color-border);
}

.gwt-decision-table__row:last-child {
  border-bottom: none;
}

.gwt-decision-table__row:hover {
  background: var(--color-bg-tertiary);
}

.gwt-decision-table__row-header-cell {
  padding: 10px 8px;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--color-text-light);
  background: var(--color-bg-tertiary);
  border-right: 1px solid var(--color-border);
  text-align: center;
}

.gwt-decision-table__value-cell {
  padding: 8px 12px;
}

.gwt-decision-table__input {
  width: 100%;
  padding: 6px 8px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  font-size: 0.7rem;
  transition: border-color 0.15s ease;
  text-align: left;
}

.gwt-decision-table__input::placeholder {
  color: var(--color-text-light);
  font-style: italic;
}

.gwt-decision-table__input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.gwt-decision-table__input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.gwt-decision-table__textarea {
  min-height: 60px;
  resize: vertical;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', 'source-code-pro', monospace;
  font-size: 0.7rem;
  line-height: 1.4;
}

.gwt-vo-editor-wrapper {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 4px;
}

.gwt-vo-editor-wrapper .gwt-decision-table__textarea {
  flex: 1;
  min-height: 50px;
}

.gwt-vo-editor-btn {
  flex-shrink: 0;
  padding: 4px 8px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.gwt-vo-editor-btn:hover:not(:disabled) {
  background: var(--color-bg-tertiary);
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.gwt-vo-editor-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ValueObject Editor Modal */
.vo-editor-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.vo-editor-modal {
  background: var(--color-bg);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.vo-editor-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
}

.vo-editor-modal__title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0;
}

.vo-editor-modal__close {
  background: transparent;
  border: none;
  color: var(--color-text-light);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s ease;
}

.vo-editor-modal__close:hover {
  color: var(--color-text);
}

.vo-editor-modal__content {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.vo-editor-modal__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
}

.vo-editor-modal__btn {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 1px solid var(--color-border);
}

.vo-editor-modal__btn--cancel {
  background: var(--color-bg);
  color: var(--color-text);
}

.vo-editor-modal__btn--cancel:hover:not(:disabled) {
  background: var(--color-bg-tertiary);
  border-color: var(--color-text-light);
}

.vo-editor-modal__btn--save {
  background: var(--color-accent);
  color: white;
  border-color: var(--color-accent);
}

.vo-editor-modal__btn--save:hover:not(:disabled) {
  background: var(--color-accent-dark);
  border-color: var(--color-accent-dark);
}

.vo-editor-modal__btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.vo-editor-empty {
  padding: 40px 20px;
  text-align: center;
  color: var(--color-text-light);
}

.vo-editor-fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.vo-editor-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.vo-editor-field__label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--color-text-bright);
}

.vo-editor-field__name {
  font-weight: 600;
}

.vo-editor-field__type {
  font-size: 0.7rem;
  color: var(--color-text-light);
  font-weight: normal;
  padding: 2px 6px;
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-sm);
}

.vo-editor-field__input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 0.75rem;
  transition: border-color 0.15s ease;
}

.vo-editor-field__input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.vo-editor-field__input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.vo-editor-field__input[type="checkbox"] {
  width: auto;
  cursor: pointer;
}

.gwt-decision-table__empty {
  color: var(--color-text-light);
  font-size: 0.7rem;
  font-style: italic;
}

.gwt-decision-table__action-cell {
  padding: 8px;
  text-align: center;
}

.gwt-decision-table__remove {
  width: 28px;
  height: 28px;
  padding: 0;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.gwt-decision-table__remove:hover:not(:disabled) {
  background: rgba(255, 107, 107, 0.1);
  border-color: rgba(255, 107, 107, 0.3);
  color: #ff6b6b;
}

.gwt-decision-table__add {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}

.gwt-decision-table__add-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.gwt-decision-table__add-btn:hover:not(:disabled) {
  background: var(--color-bg);
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.gwt-empty-state {
  padding: 40px 20px;
  text-align: center;
  background: var(--color-bg);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
}

.gwt-empty-message {
  font-size: 0.75rem;
  color: var(--color-text-light);
  margin-bottom: 16px;
}

.gwt-field-values-table__header {
  display: grid;
  grid-template-columns: 1fr 2fr 32px;
  gap: 8px;
  padding: 8px;
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-sm);
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--color-text-light);
}

.gwt-field-values-table__row {
  display: grid;
  grid-template-columns: 1fr 2fr 32px;
  gap: 8px;
  align-items: center;
}

.gwt-field-values-table__field {
  font-size: 0.7rem;
  color: var(--color-text);
  font-weight: 500;
}

.gwt-field-values-table__input {
  padding: 6px 8px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  font-size: 0.7rem;
}

.gwt-field-values-table__input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.gwt-field-values-table__remove {
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.gwt-field-values-table__remove:hover:not(:disabled) {
  background: rgba(255, 107, 107, 0.1);
  border-color: rgba(255, 107, 107, 0.3);
  color: #ff6b6b;
}

.gwt-field-values-table__add {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
}

.gwt-field-values-table__add-btn {
  padding: 6px 12px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.gwt-field-values-table__add-btn:hover:not(:disabled) {
  background: var(--color-bg);
  border-color: var(--color-accent);
}

.gwt-detail-add-set {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border);
}

.gwt-detail-modal__footer {
  padding: 16px 20px;
  border-top: 1px solid var(--color-border);
  display: flex;
  justify-content: flex-end;
}

/* GWT Preview (Simple Display) */
.inspector-gwt-preview {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.gwt-preview-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 0.7rem;
}

.gwt-preview-label {
  font-weight: 600;
  color: var(--color-text-bright);
  min-width: 50px;
  flex-shrink: 0;
}

.gwt-preview-value {
  color: var(--color-text);
  flex: 1;
  word-break: break-word;
}

.gwt-preview-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
}

.inspector-section__btn--danger {
  background: rgba(255, 107, 107, 0.1);
  border-color: rgba(255, 107, 107, 0.3);
  color: #ff6b6b;
}

.inspector-section__btn--danger:hover:not(:disabled) {
  background: rgba(255, 107, 107, 0.2);
  border-color: #ff6b6b;
}

.inspector-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-sm);
}

.inspector-section__title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin: 0;
}

.inspector-section__btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  font-size: 0.65rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.inspector-section__btn:hover:not(:disabled) {
  background: var(--color-bg-tertiary);
  border-color: var(--color-accent);
}

.inspector-section__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.inspector-gwt-editor {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.gwt-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.gwt-field__label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.gwt-field__actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}

.gwt-field__btn {
  padding: 4px 8px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  font-size: 0.65rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.gwt-field__btn:hover:not(:disabled) {
  background: rgba(255, 107, 107, 0.1);
  border-color: rgba(255, 107, 107, 0.3);
  color: #ff6b6b;
}

.gwt-field__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.gwt-field-values {
  margin-top: 8px;
  padding: 8px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.gwt-field-values__label {
  display: block;
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--color-text-light);
  margin-bottom: 6px;
}

.gwt-field-value-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.gwt-field-value-key {
  flex: 1;
  min-width: 0;
  font-size: 0.7rem;
}

.gwt-field-value-separator {
  color: var(--color-text-light);
  font-size: 0.7rem;
  flex-shrink: 0;
}

.gwt-field-value-value {
  flex: 1;
  min-width: 0;
  font-size: 0.7rem;
}

.gwt-field-value-remove {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.gwt-field-value-remove:hover:not(:disabled) {
  background: rgba(255, 107, 107, 0.1);
  border-color: rgba(255, 107, 107, 0.3);
  color: #ff6b6b;
}

.gwt-field-value-remove:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.gwt-field-value-add {
  width: 100%;
  padding: 6px 8px;
  background: var(--color-bg);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  font-size: 0.65rem;
  cursor: pointer;
  transition: all 0.15s ease;
  margin-top: 4px;
}

.gwt-field-value-add:hover:not(:disabled) {
  background: var(--color-bg-tertiary);
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.gwt-field-value-add:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>


