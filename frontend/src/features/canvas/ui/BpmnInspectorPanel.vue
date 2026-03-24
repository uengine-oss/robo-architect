<script setup>
import { computed } from 'vue'
import { useBpmnStore } from '@/features/canvas/bpmn.store'
import './wireframe-preview.css'

const emit = defineEmits(['close'])
const store = useBpmnStore()

const node = computed(() => store.selectedNodeData)
const uiNode = computed(() => store.selectedNodeUi)
const isCommand = computed(() => node.value?.label === 'Command')
const isEvent = computed(() => node.value?.label === 'Event')

const nodeTypeLabel = computed(() => {
  if (isCommand.value) return 'Task (Command)'
  if (isEvent.value) return 'Output Message (Event)'
  return node.value?.label || ''
})

const nodeTypeColor = computed(() => {
  if (isCommand.value) return '#5c7cfa'
  if (isEvent.value) return '#fd7e14'
  return '#868e96'
})

const currentFlowName = computed(() => {
  const flow = store.renderedFlows.find(f => f.id === store.selectedFlowId)
  if (!flow) return '-'
  return flow.startCommand?.displayName || flow.startCommand?.name || flow.id
})

function close() {
  store.clearInspectorSelection()
  emit('close')
}
</script>

<template>
  <div class="bpmn-inspector">
    <!-- Header -->
    <div class="bpmn-inspector__header">
      <div class="bpmn-inspector__title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <span>Process Inspector</span>
      </div>
      <button class="bpmn-inspector__close" @click="close" title="Close">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>

    <div v-if="!node" class="bpmn-inspector__empty">
      <p>BPMN 요소를 더블클릭하여 상세 정보를 확인하세요.</p>
    </div>

    <div v-else class="bpmn-inspector__body">
      <!-- Node Type Badge -->
      <div class="bpmn-inspector__type-badge" :style="{ '--badge-color': nodeTypeColor }">
        {{ nodeTypeLabel }}
      </div>

      <!-- Basic Info -->
      <div class="bpmn-inspector__section">
        <h3 class="bpmn-inspector__section-title">기본 정보</h3>

        <div class="bpmn-inspector__field">
          <span class="bpmn-inspector__label">이름</span>
          <span class="bpmn-inspector__value">{{ node.displayName || node.name }}</span>
        </div>

        <div v-if="node.displayName && node.name !== node.displayName" class="bpmn-inspector__field">
          <span class="bpmn-inspector__label">기술 이름</span>
          <span class="bpmn-inspector__value bpmn-inspector__value--mono">{{ node.name }}</span>
        </div>

        <div v-if="node.description" class="bpmn-inspector__field">
          <span class="bpmn-inspector__label">설명</span>
          <span class="bpmn-inspector__value bpmn-inspector__value--desc">{{ node.description }}</span>
        </div>
      </div>

      <!-- Command-specific info -->
      <template v-if="isCommand">
        <div class="bpmn-inspector__section">
          <h3 class="bpmn-inspector__section-title">실행 정보</h3>

          <div v-if="node.actor" class="bpmn-inspector__field">
            <span class="bpmn-inspector__label">Actor (실행 주체)</span>
            <span class="bpmn-inspector__value">
              <span class="bpmn-inspector__actor-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                  <circle cx="12" cy="7" r="4"></circle>
                </svg>
              </span>
              {{ node.actor }}
            </span>
          </div>

          <div v-if="node.aggregateName" class="bpmn-inspector__field">
            <span class="bpmn-inspector__label">Aggregate</span>
            <span class="bpmn-inspector__value">{{ node.aggregateName }}</span>
          </div>

          <div v-if="node.bcName" class="bpmn-inspector__field">
            <span class="bpmn-inspector__label">Bounded Context</span>
            <span class="bpmn-inspector__value">{{ node.bcName }}</span>
          </div>
        </div>

        <!-- UI Wireframe Section -->
        <div class="bpmn-inspector__section">
          <h3 class="bpmn-inspector__section-title">UI Wireframe</h3>

          <div v-if="uiNode && uiNode.template" class="bpmn-inspector__wireframe">
            <div class="bpmn-inspector__wireframe-name">{{ uiNode.displayName || uiNode.name }}</div>
            <div class="bpmn-inspector__wireframe-frame">
              <div class="bpmn-inspector__browser-bar">
                <div class="browser-dots"><span></span><span></span><span></span></div>
                <div class="browser-url">preview://{{ uiNode.name }}</div>
              </div>
              <div class="bpmn-inspector__wireframe-body wireframe-preview-body" v-html="uiNode.template"></div>
            </div>
          </div>

          <div v-else class="bpmn-inspector__no-wireframe">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
              <rect x="2" y="3" width="20" height="18" rx="2" />
              <line x1="2" y1="7" x2="22" y2="7" />
            </svg>
            <span>연결된 UI Wireframe이 없습니다.</span>
          </div>
        </div>
      </template>

      <!-- Event-specific info -->
      <template v-if="isEvent">
        <div class="bpmn-inspector__section">
          <h3 class="bpmn-inspector__section-title">이벤트 정보</h3>

          <div class="bpmn-inspector__field">
            <span class="bpmn-inspector__label">발행 유형</span>
            <span class="bpmn-inspector__value">Domain Event</span>
          </div>

          <div v-if="node.version" class="bpmn-inspector__field">
            <span class="bpmn-inspector__label">Version</span>
            <span class="bpmn-inspector__value">v{{ node.version }}</span>
          </div>
        </div>
      </template>

      <!-- Flow Context -->
      <div class="bpmn-inspector__section bpmn-inspector__section--muted">
        <h3 class="bpmn-inspector__section-title">프로세스 흐름 위치</h3>
        <div class="bpmn-inspector__field">
          <span class="bpmn-inspector__label">Flow</span>
          <span class="bpmn-inspector__value">{{ currentFlowName }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bpmn-inspector {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 360px;
  background: var(--color-bg-secondary);
  border-left: 1px solid var(--color-border);
  flex-shrink: 0;
}

.bpmn-inspector__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-tertiary);
}

.bpmn-inspector__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.bpmn-inspector__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  background: none;
  border: none;
  border-radius: 4px;
  color: var(--color-text-light);
  cursor: pointer;
  transition: all 0.15s;
}

.bpmn-inspector__close:hover {
  background: var(--color-bg);
  color: var(--color-text);
}

.bpmn-inspector__empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: var(--color-text-light);
  font-size: 0.75rem;
  text-align: center;
}

.bpmn-inspector__body {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
}

.bpmn-inspector__type-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  color: white;
  background: var(--badge-color);
  margin-bottom: 14px;
}

.bpmn-inspector__section {
  margin-bottom: 18px;
}

.bpmn-inspector__section--muted {
  opacity: 0.7;
}

.bpmn-inspector__section-title {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--color-text-light);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 10px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--color-border);
}

.bpmn-inspector__field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 10px;
}

.bpmn-inspector__label {
  font-size: 0.65rem;
  font-weight: 500;
  color: var(--color-text-light);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.bpmn-inspector__value {
  font-size: 0.8rem;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: 4px;
}

.bpmn-inspector__value--mono {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.bpmn-inspector__value--desc {
  font-size: 0.75rem;
  line-height: 1.5;
  color: var(--color-text);
  white-space: pre-wrap;
}

.bpmn-inspector__actor-icon {
  display: flex;
  align-items: center;
  color: var(--color-text-light);
}

/* Wireframe Preview */
.bpmn-inspector__wireframe {
  margin-top: 6px;
}

.bpmn-inspector__wireframe-name {
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--color-text);
  margin-bottom: 6px;
}

.bpmn-inspector__wireframe-frame {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
  background: white;
}

.bpmn-inspector__browser-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
}

.browser-dots {
  display: flex;
  gap: 4px;
}

.browser-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ccc;
}

.browser-url {
  font-size: 0.6rem;
  color: #999;
  font-family: monospace;
}

.bpmn-inspector__wireframe-body {
  padding: 8px;
  max-height: 300px;
  overflow-y: auto;
  font-size: 0.75rem;
}

.bpmn-inspector__no-wireframe {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 16px;
  color: var(--color-text-light);
  font-size: 0.7rem;
  text-align: center;
}
</style>
