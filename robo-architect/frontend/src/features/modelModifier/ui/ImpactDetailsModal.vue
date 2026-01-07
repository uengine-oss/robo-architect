<script setup>
import { computed, ref, watch } from 'vue'
import ImpactAnalysisPanel from '@/features/changeManagement/ui/ImpactAnalysisPanel.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  seedNodes: { type: Array, default: () => [] }, // [{id,name,type}]
  impactSummary: { type: Object, default: null }
})

const emit = defineEmits(['close'])

const hopLoading = ref(false)
const hopError = ref(null)
const hopData = ref(null)

const selectedNodeId = ref(null)

const userStoryLoading = ref(false)
const userStoryError = ref(null)
const selectedUserStoryId = ref(null)
const userStoryImpact = ref(null)

const seedIds = computed(() => {
  const ids = (props.impactSummary?.seedIds || props.seedNodes || []).map(n => (typeof n === 'string' ? n : n?.id))
  return ids.filter(Boolean)
})

async function fetchHopDetails() {
  if (!props.visible) return
  if (!seedIds.value.length) return

  hopLoading.value = true
  hopError.value = null
  try {
    const resp = await fetch('/api/chat/impact-details', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seedIds: seedIds.value })
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) {
      throw new Error(data?.detail || `API error: ${resp.status}`)
    }
    hopData.value = data

    // Default selection: first seed node if present, otherwise first hop node
    const firstSeed = seedIds.value[0]
    const nodes = data?.hopGraph?.nodes || []
    selectedNodeId.value = firstSeed || nodes?.[0]?.id || null
  } catch (e) {
    hopError.value = e.message
  } finally {
    hopLoading.value = false
  }
}

watch(
  () => [props.visible, seedIds.value.join(',')],
  async ([vis]) => {
    if (vis) await fetchHopDetails()
  }
)

const hopNodes = computed(() => hopData.value?.hopGraph?.nodes || [])
const hopRels = computed(() => hopData.value?.hopGraph?.relationships || [])
const propertiesByParentId = computed(() => hopData.value?.propertiesByParentId || {})

const nodesByHop = computed(() => {
  const groups = new Map()
  for (const n of hopNodes.value) {
    const hop = typeof n?.hop === 'number' ? n.hop : null
    const h = hop === null ? 999 : hop
    if (!groups.has(h)) groups.set(h, [])
    groups.get(h).push(n)
  }
  // sort nodes within hop: type then name
  const out = [...groups.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([hop, nodes]) => ({
      hop,
      nodes: nodes.slice().sort((a, b) => `${a?.type || ''}${a?.name || ''}`.localeCompare(`${b?.type || ''}${b?.name || ''}`))
    }))
  return out
})

const selectedNode = computed(() => {
  if (!selectedNodeId.value) return null
  return hopNodes.value.find(n => n.id === selectedNodeId.value) || null
})

const selectedNodeProperties = computed(() => {
  const id = selectedNodeId.value
  if (!id) return []
  return propertiesByParentId.value[id] || []
})

function formatNodeTypeIcon(type) {
  const icons = {
    UserStory: '🧩',
    BoundedContext: '🏷️',
    Aggregate: '📦',
    Command: '⚡',
    ReadModel: '📖',
    Event: '📣',
    Policy: '📜',
    UI: '🖥️',
    Property: '{ }'
  }
  return icons[type] || '•'
}

async function fetchUserStoryImpact(id) {
  if (!id) return
  selectedUserStoryId.value = id
  userStoryImpact.value = null
  userStoryError.value = null
  userStoryLoading.value = true
  try {
    const resp = await fetch(`/api/change/impact/${id}`)
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) {
      throw new Error(data?.detail || `API error: ${resp.status}`)
    }
    userStoryImpact.value = data
  } catch (e) {
    userStoryError.value = e.message
  } finally {
    userStoryLoading.value = false
  }
}

function close() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="modal-overlay" @click.self="close">
        <div class="modal-container">
          <div class="modal-header">
            <div class="modal-title">
              <span class="modal-title__icon">🧪</span>
              영향도 분석 상세
            </div>
            <button class="modal-close" @click="close" title="닫기">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <ImpactAnalysisPanel
              v-if="impactSummary"
              title="Propagation (confirmed only)"
              :connected-nodes="seedNodes"
              :propagation-enabled="true"
              :propagation-confirmed="impactSummary.propagationConfirmed || []"
              :propagation-review="[]"
              :propagation-rounds="impactSummary.propagationRounds || 0"
              :propagation-stop-reason="impactSummary.propagationStopReason || ''"
              :show-review="false"
            />

            <div class="section">
              <div class="section__header">
                <div class="section__title">Hop 영향도 (K-hop, whitelist)</div>
                <div class="section__meta">
                  <span class="pill">K: {{ hopData?.k ?? impactSummary?.k ?? '-' }}</span>
                  <span class="pill">rels: {{ (hopData?.whitelist || impactSummary?.whitelist || []).length }}</span>
                  <span class="pill">nodes: {{ hopNodes.length }}</span>
                  <span class="pill">edges: {{ hopRels.length }}</span>
                </div>
              </div>

              <div v-if="hopLoading" class="muted">로딩 중...</div>
              <div v-else-if="hopError" class="error">{{ hopError }}</div>
              <div v-else class="hop-layout">
                <div class="hop-list">
                  <div v-for="g in nodesByHop" :key="g.hop" class="hop-group">
                    <div class="hop-group__title">
                      Hop {{ g.hop === 999 ? '?' : g.hop }} ({{ g.nodes.length }})
                    </div>
                    <button
                      v-for="n in g.nodes"
                      :key="n.id"
                      class="hop-node"
                      :class="{ 'hop-node--active': n.id === selectedNodeId }"
                      @click="selectedNodeId = n.id"
                      :title="`${n.type}: ${n.name || n.id}`"
                    >
                      <span class="hop-node__icon">{{ formatNodeTypeIcon(n.type) }}</span>
                      <span class="hop-node__name">{{ n.name || n.id }}</span>
                      <span class="hop-node__meta">{{ n.type }}</span>
                      <span v-if="n.bcName" class="hop-node__meta">· {{ n.bcName }}</span>
                    </button>
                  </div>
                </div>

                <div class="hop-details">
                  <div v-if="!selectedNode" class="muted">노드를 선택하세요.</div>
                  <div v-else>
                    <div class="details-title">
                      <span class="details-title__icon">{{ formatNodeTypeIcon(selectedNode.type) }}</span>
                      <span class="details-title__name">{{ selectedNode.name || selectedNode.id }}</span>
                      <span class="details-title__meta">{{ selectedNode.type }}</span>
                      <span v-if="selectedNode.bcName" class="details-title__meta">· {{ selectedNode.bcName }}</span>
                      <span v-if="typeof selectedNode.hop === 'number'" class="details-title__meta">· hop {{ selectedNode.hop }}</span>
                    </div>

                    <div v-if="selectedNode.description" class="details-desc">
                      {{ selectedNode.description }}
                    </div>

                    <div class="subsection">
                      <div class="subsection__title">Properties / REFERENCES</div>
                      <div v-if="selectedNodeProperties.length === 0" class="muted">속성이 없습니다.</div>
                      <div v-else class="prop-list">
                        <div v-for="p in selectedNodeProperties" :key="p.id" class="prop-item">
                          <div class="prop-item__head">
                            <span class="prop-item__name">{{ p.name }}</span>
                            <span class="prop-item__type">{{ p.type }}</span>
                            <span class="prop-item__flags">
                              <span class="flag" :class="{ 'flag--on': p.isKey }">PK</span>
                              <span class="flag" :class="{ 'flag--on': p.isForeignKey }">FK</span>
                              <span class="flag" :class="{ 'flag--on': p.isRequired }">REQ</span>
                            </span>
                          </div>
                          <div v-if="p.description" class="prop-item__desc">{{ p.description }}</div>
                          <div v-if="p.references && p.references.length" class="prop-item__refs">
                            <div class="prop-item__refs-title">REFERENCES</div>
                            <div v-for="r in p.references" :key="r.id" class="ref-item">
                              <span class="ref-item__name">{{ r.name }}</span>
                              <span class="ref-item__meta">({{ r.parentType }}/{{ r.parentId }})</span>
                              <span v-if="r.isKey" class="ref-item__meta">· PK</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="impactSummary?.userStoryIds?.length" class="section">
              <div class="section__header">
                <div class="section__title">UserStory 영향도 (propagation에 등장한 US만)</div>
                <div class="section__meta">
                  <span class="pill">US: {{ impactSummary.userStoryIds.length }}</span>
                </div>
              </div>

              <div class="us-list">
                <button
                  v-for="id in impactSummary.userStoryIds"
                  :key="id"
                  class="us-item"
                  :class="{ 'us-item--active': id === selectedUserStoryId }"
                  @click="fetchUserStoryImpact(id)"
                >
                  {{ id }}
                </button>
              </div>

              <div v-if="userStoryLoading" class="muted">로딩 중...</div>
              <div v-else-if="userStoryError" class="error">{{ userStoryError }}</div>
              <div v-else-if="userStoryImpact?.userStory" class="us-impact">
                <div class="us-impact__header">
                  <div class="us-impact__title">{{ userStoryImpact.userStory.id }}</div>
                  <div class="us-impact__desc">
                    As a {{ userStoryImpact.userStory.role }}, I want to {{ userStoryImpact.userStory.action }},
                    so that {{ userStoryImpact.userStory.benefit }}
                  </div>
                </div>

                <ImpactAnalysisPanel
                  title="UserStory Impact (connected objects)"
                  :connected-nodes="userStoryImpact.impactedNodes || []"
                  :propagation-enabled="false"
                  :propagation-confirmed="[]"
                  :propagation-review="[]"
                  :propagation-rounds="0"
                  propagation-stop-reason=""
                  :show-review="false"
                  :related-count="null"
                  :proposed-changes-count="null"
                />
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn" @click="close">닫기</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1200;
}

.modal-container {
  width: min(1100px, 92vw);
  max-height: 88vh;
  overflow: hidden;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-tertiary);
}

.modal-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-weight: 700;
  color: var(--color-text-bright);
}

.modal-close {
  background: transparent;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--radius-sm);
}

.modal-close:hover {
  background: var(--color-bg);
  color: var(--color-text-bright);
}

.modal-body {
  padding: var(--spacing-lg);
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.modal-footer {
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--color-border);
  display: flex;
  justify-content: flex-end;
}

.btn {
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  cursor: pointer;
}

.btn:hover {
  background: var(--color-bg);
}

.section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.section__title {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--color-text-bright);
}

.section__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pill {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.hop-layout {
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: var(--spacing-md);
  min-height: 360px;
}

.hop-list {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-sm);
  background: var(--color-bg);
  overflow: auto;
}

.hop-group {
  margin-bottom: var(--spacing-md);
}

.hop-group__title {
  font-size: 0.75rem;
  color: var(--color-text-light);
  margin-bottom: 6px;
  font-weight: 700;
}

.hop-node {
  width: 100%;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--color-text);
  cursor: pointer;
}

.hop-node:hover {
  background: rgba(34, 139, 230, 0.08);
  border-color: rgba(34, 139, 230, 0.18);
}

.hop-node--active {
  background: rgba(34, 139, 230, 0.12);
  border-color: rgba(34, 139, 230, 0.28);
}

.hop-node__icon {
  width: 20px;
  flex-shrink: 0;
}

.hop-node__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hop-node__meta {
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.hop-details {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  background: var(--color-bg);
  overflow: auto;
}

.details-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: var(--spacing-sm);
}

.details-title__name {
  font-weight: 800;
  color: var(--color-text-bright);
}

.details-title__meta {
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.details-desc {
  color: var(--color-text);
  font-size: 0.85rem;
  margin-bottom: var(--spacing-md);
}

.subsection__title {
  font-size: 0.75rem;
  font-weight: 800;
  color: var(--color-text-light);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-bottom: 6px;
}

.prop-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.prop-item {
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  border-radius: 12px;
  padding: 10px;
}

.prop-item__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.prop-item__name {
  font-weight: 800;
  color: var(--color-text-bright);
}

.prop-item__type {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.prop-item__flags {
  margin-left: auto;
  display: flex;
  gap: 6px;
}

.flag {
  font-size: 0.65rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  padding: 1px 6px;
  border-radius: 999px;
  color: var(--color-text-light);
}

.flag--on {
  color: var(--color-text-bright);
  border-color: rgba(34, 139, 230, 0.28);
  background: rgba(34, 139, 230, 0.12);
}

.prop-item__desc {
  margin-top: 6px;
  font-size: 0.8rem;
  color: var(--color-text);
}

.prop-item__refs {
  margin-top: 8px;
}

.prop-item__refs-title {
  font-size: 0.7rem;
  font-weight: 800;
  color: var(--color-text-light);
  margin-bottom: 4px;
}

.ref-item {
  font-size: 0.8rem;
  color: var(--color-text);
  font-family: var(--font-mono);
}

.ref-item__meta {
  color: var(--color-text-light);
  margin-left: 6px;
}

.us-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.us-item {
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: var(--color-text);
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.us-item--active {
  border-color: rgba(34, 139, 230, 0.28);
  background: rgba(34, 139, 230, 0.12);
}

.muted {
  color: var(--color-text-light);
  font-size: 0.85rem;
}

.error {
  color: #ff6464;
  font-size: 0.85rem;
}

.us-impact__header {
  padding: var(--spacing-sm) 0;
}

.us-impact__title {
  font-weight: 800;
  color: var(--color-text-bright);
  margin-bottom: 4px;
}

.us-impact__desc {
  color: var(--color-text);
  font-size: 0.85rem;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>


