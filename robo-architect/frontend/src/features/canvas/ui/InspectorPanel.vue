<script setup>
import { computed, ref, watch } from 'vue'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { NodeEditSchemas, normalizeNodeLabel, ProvisioningTypeOptions } from './inspectors/nodeEditSchema'
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

const form = ref({
  name: '',
  description: '',
  template: '',
  actor: '',
  version: '',
  rootEntity: '',
  provisioningType: 'CQRS',
  attachedToId: '',
  attachedToType: '',
  attachedToName: ''
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
    version: data.version ?? '',
    rootEntity: data.rootEntity ?? '',
    provisioningType: data.provisioningType ?? 'CQRS',
    attachedToId: data.attachedToId ?? '',
    attachedToType: data.attachedToType ?? '',
    attachedToName: data.attachedToName ?? ''
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
      version: '',
      rootEntity: '',
      provisioningType: 'CQRS',
      attachedToId: '',
      attachedToType: '',
      attachedToName: ''
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
  return keys.filter(k => String(form.value[k] ?? '') !== String(initial.value[k] ?? ''))
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
  if (!isDirty.value) return

  const opId = newOpId('save')
  saving.value = true
  error.value = null
  successMsg.value = null

  try {
    const changes = []

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

    if (!changes.length) return

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
</script>

<template>
  <div class="inspector-panel">
    <div class="inspector-panel__header">
      <div class="inspector-panel__title">
        <span>Inspector</span>
        <span v-if="node" class="inspector-panel__subtitle">{{ schema.title }} · {{ node.data?.name || node.id }}</span>
      </div>
      <div class="inspector-panel__actions">
        <button class="inspector-panel__btn" @click="resetToNode" title="Reload" :disabled="saving">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-3-6.7"></path>
            <polyline points="21 3 21 9 15 9"></polyline>
          </svg>
        </button>
        <button class="inspector-panel__btn primary" @click="save" title="Save" :disabled="saving || !node || !isDirty">
          <span v-if="saving">저장 중...</span>
          <span v-else>저장</span>
        </button>
        <button class="inspector-panel__btn" @click="emit('close')" title="Close">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>

    <div class="inspector-panel__body">
      <div v-if="!node" class="inspector-panel__empty">
        편집할 노드를 선택하세요.
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

        </div>
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
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-tertiary);
}

.inspector-panel__title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.inspector-panel__subtitle {
  font-size: 0.75rem;
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
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text-bright);
  font-size: 0.8rem;
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
  color: var(--color-text-light);
  font-size: 0.85rem;
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
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.8rem;
}

.inspector-tab.active {
  color: var(--color-text-bright);
  border-color: var(--color-accent);
}

.inspector-alert {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  margin-bottom: var(--spacing-md);
  font-size: 0.8rem;
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
  padding: 10px 12px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 0.8rem;
}

.inspector-kv .k {
  color: var(--color-text-light);
  opacity: 0.8;
}

.inspector-kv .v {
  color: var(--color-text);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 0.75rem;
}

.inspector-field__label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin-bottom: 6px;
}

.inspector-field__dirty {
  color: var(--color-accent);
  font-size: 1.2rem;
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
  padding: 8px 10px;
  font-size: 0.85rem;
}

.inspector-textarea {
  resize: vertical;
}

.inspector-textarea--template {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 0.75rem;
  line-height: 1.35;
  white-space: pre;
}

.inspector-field__help {
  margin-top: 6px;
  color: var(--color-text-light);
  font-size: 0.72rem;
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
  font-size: 0.75rem;
  font-weight: 600;
  margin-bottom: 6px;
}

.inspector-readonly__pre {
  margin: 0;
  max-height: 200px;
  overflow: auto;
  font-size: 0.7rem;
  color: var(--color-text);
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
  font-size: 0.875rem;
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
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin-bottom: 4px;
}

.ui-preview-panel__attached {
  font-size: 0.75rem;
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
  font-size: 0.7rem;
  color: #495057;
  background: #f8f9fa;
  padding: 4px 10px;
  border-radius: 4px;
}

.ui-preview-frame__body {
  padding: 16px;
  min-height: 200px;
  color: #212529;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.ui-preview-frame__body :deep(input),
.ui-preview-frame__body :deep(select),
.ui-preview-frame__body :deep(textarea) {
  display: block;
  width: 100%;
  padding: 8px 12px;
  margin-bottom: 12px;
  border: 2px dashed #adb5bd;
  border-radius: 4px;
  background: #f8f9fa;
  font-size: 0.85rem;
}

.ui-preview-frame__body :deep(button) {
  padding: 8px 16px;
  border: 2px dashed #228be6;
  border-radius: 4px;
  background: #e7f5ff;
  color: #1971c2;
  font-size: 0.85rem;
  cursor: pointer;
  margin: 4px;
}

.ui-preview-frame__body :deep(label) {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  color: #495057;
  margin-bottom: 4px;
}

.ui-preview-frame__body :deep(h1),
.ui-preview-frame__body :deep(h2),
.ui-preview-frame__body :deep(h3) {
  color: #212529;
  margin-bottom: 12px;
}

.ui-preview-frame__body :deep(.form-group) {
  margin-bottom: 16px;
}

.ui-preview-frame__body :deep(.btn-group) {
  display: flex;
  gap: 8px;
  margin-top: 16px;
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
  font-size: 0.875rem;
}

.ui-preview-empty__btn {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ui-preview-empty__btn:hover {
  background: #1c7ed6;
  transform: translateY(-1px);
}
</style>


