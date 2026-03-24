<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { useBpmnStore } from '@/features/canvas/bpmn.store'
import BpmnViewer from 'bpmn-js/lib/NavigatedViewer'
import BpmnInspectorPanel from './BpmnInspectorPanel.vue'
import 'bpmn-js/dist/assets/diagram-js.css'
import 'bpmn-js/dist/assets/bpmn-js.css'
import 'bpmn-js/dist/assets/bpmn-font/css/bpmn-embedded.css'

const store = useBpmnStore()

const bpmnContainer = ref(null)
const isDragOver = ref(false)
const showInspector = computed(() => !!store.selectedNodeData)
let viewer = null

// 현재 렌더링된 flow 탭 목록
const flowTabs = computed(() => store.renderedFlows)

onMounted(() => {
  store.fetchProcessFlows()
})

onUnmounted(() => {
  if (viewer) {
    viewer.destroy()
    viewer = null
  }
})

// BPMN XML 변경 감지하여 뷰어 업데이트
watch(() => store.activeBpmnXml, async (xml) => {
  if (!xml) {
    if (viewer) {
      viewer.destroy()
      viewer = null
    }
    return
  }
  await nextTick()
  await renderBpmn(xml)
}, { immediate: true })

async function renderBpmn(xml) {
  if (!bpmnContainer.value) return

  if (viewer) {
    viewer.destroy()
    viewer = null
  }

  viewer = new BpmnViewer({
    container: bpmnContainer.value,
  })

  try {
    await viewer.importXML(xml)
    const canvas = viewer.get('canvas')
    canvas.zoom('fit-viewport')

    // 더블클릭 이벤트 등록
    const eventBus = viewer.get('eventBus')
    eventBus.on('element.dblclick', (e) => {
      const element = e.element
      if (!element || !element.id) return

      // Task (Command) 또는 IntermediateThrowEvent (Event) 만 처리
      const id = element.id
      if (id.startsWith('Task_') || id.startsWith('IntEvent_')) {
        e.originalEvent?.stopPropagation?.()
        store.selectNodeForInspector(id)

        // 선택된 요소 하이라이트
        highlightElement(id)
      }
    })

    // 캔버스 빈 영역 클릭 시 Inspector 닫기
    eventBus.on('canvas.click', () => {
      if (store.selectedNodeData) {
        clearHighlight()
        store.clearInspectorSelection()
      }
    })
  } catch (err) {
    console.error('BPMN render error:', err)
  }
}

function handleZoomIn() {
  if (!viewer) return
  const canvas = viewer.get('canvas')
  canvas.zoom(canvas.zoom() * 1.2)
}

function handleZoomOut() {
  if (!viewer) return
  const canvas = viewer.get('canvas')
  canvas.zoom(canvas.zoom() / 1.2)
}

function handleFitViewport() {
  if (!viewer) return
  const canvas = viewer.get('canvas')
  canvas.zoom('fit-viewport')
}

// Drag & Drop: Navigator에서 프로세스 흐름을 드래그해올 때
function handleDragOver(e) {
  e.preventDefault()
  isDragOver.value = true
  e.dataTransfer.dropEffect = 'copy'
}

function handleDragLeave() {
  isDragOver.value = false
}

async function handleDrop(e) {
  e.preventDefault()
  isDragOver.value = false

  try {
    const raw = e.dataTransfer.getData('application/json')
    if (!raw) return
    const data = JSON.parse(raw)
    if (data.type === 'BpmnFlow' && data.id) {
      await store.addFlow(data.id)
    }
  } catch (err) {
    console.error('Drop error:', err)
  }
}

function selectFlowTab(flowId) {
  store.selectFlow(flowId)
}

function removeFlowTab(flowId) {
  store.removeFlow(flowId)
}

let highlightedElementId = null

function highlightElement(elementId) {
  clearHighlight()
  if (!viewer) return
  try {
    const canvas = viewer.get('canvas')
    canvas.addMarker(elementId, 'bpmn-element-selected')
    highlightedElementId = elementId
  } catch (e) {
    // element may not exist
  }
}

function clearHighlight() {
  if (!viewer || !highlightedElementId) return
  try {
    const canvas = viewer.get('canvas')
    canvas.removeMarker(highlightedElementId, 'bpmn-element-selected')
  } catch (e) {
    // element may have been removed
  }
  highlightedElementId = null
}

function closeInspector() {
  clearHighlight()
  store.clearInspectorSelection()
}
</script>

<template>
  <div class="bpmn-panel-wrapper">
    <div
      class="bpmn-panel"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
      :class="{ 'is-drag-over': isDragOver }"
    >
      <!-- Flow Tabs -->
      <div v-if="flowTabs.length > 0" class="flow-tabs">
        <button
          v-for="flow in flowTabs"
          :key="flow.id"
          class="flow-tab"
          :class="{ 'is-active': store.selectedFlowId === flow.id }"
          @click="selectFlowTab(flow.id)"
        >
          <span class="flow-tab__name">{{ flow.startCommand?.displayName || flow.startCommand?.name || flow.id }}</span>
          <span class="flow-tab__close" @click.stop="removeFlowTab(flow.id)" title="Remove">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </span>
        </button>
      </div>

      <!-- Zoom Controls -->
      <div class="bpmn-controls" v-if="store.activeBpmnXml">
        <button class="ctrl-btn" @click="handleZoomIn" title="Zoom In">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
            <line x1="11" y1="8" x2="11" y2="14" />
            <line x1="8" y1="11" x2="14" y2="11" />
          </svg>
        </button>
        <button class="ctrl-btn" @click="handleZoomOut" title="Zoom Out">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
            <line x1="8" y1="11" x2="14" y2="11" />
          </svg>
        </button>
        <button class="ctrl-btn" @click="handleFitViewport" title="Fit to Screen">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
          </svg>
        </button>
      </div>

      <!-- BPMN Viewer Container -->
      <div ref="bpmnContainer" class="bpmn-canvas" />

      <!-- Empty State -->
      <div v-if="!store.activeBpmnXml && !store.loading" class="bpmn-empty">
        <div class="empty-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <path d="M14 17h7M17.5 14v7" />
          </svg>
        </div>
        <p class="empty-title">BPMN Process Viewer</p>
        <p class="empty-desc">좌측 네비게이터에서 프로세스 흐름을 더블클릭하거나<br>캔버스로 드래그하여 BPMN 다이어그램을 확인하세요.</p>
      </div>

      <!-- Loading -->
      <div v-if="store.loading" class="bpmn-loading">
        <div class="loading-spinner" />
        <span>Loading process flow...</span>
      </div>

      <!-- Drag Over Overlay -->
      <div v-if="isDragOver" class="drag-overlay">
        <div class="drag-overlay__content">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          <span>프로세스 흐름을 여기에 놓으세요</span>
        </div>
      </div>
    </div>

    <!-- BPMN Inspector Panel (right side) -->
    <transition name="slide-inspector">
      <BpmnInspectorPanel
        v-if="showInspector"
        @close="closeInspector"
      />
    </transition>
  </div>
</template>

<style scoped>
.bpmn-panel-wrapper {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
}

.bpmn-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  background: var(--color-bg);
}

/* Inspector slide transition */
.slide-inspector-enter-active,
.slide-inspector-leave-active {
  transition: all 0.25s ease;
}

.slide-inspector-enter-from,
.slide-inspector-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.bpmn-panel.is-drag-over {
  outline: 2px dashed var(--color-accent);
  outline-offset: -2px;
}

/* Flow Tabs */
.flow-tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 8px 0;
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border);
  overflow-x: auto;
  flex-shrink: 0;
}

.flow-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: 6px 6px 0 0;
  font-size: 0.7rem;
  color: var(--color-text-light);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  max-width: 200px;
}

.flow-tab:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}

.flow-tab.is-active {
  background: var(--color-bg);
  border-color: var(--color-border);
  color: var(--color-text-bright);
  font-weight: 600;
}

.flow-tab__name {
  overflow: hidden;
  text-overflow: ellipsis;
}

.flow-tab__close {
  display: flex;
  align-items: center;
  padding: 2px;
  border-radius: 3px;
  color: var(--color-text-light);
  opacity: 0;
  transition: opacity 0.15s, background 0.15s;
}

.flow-tab:hover .flow-tab__close {
  opacity: 1;
}

.flow-tab__close:hover {
  background: rgba(255, 80, 80, 0.2);
  color: #ff5050;
}

/* Zoom Controls */
.bpmn-controls {
  position: absolute;
  top: 50px;
  right: 12px;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 4px;
}

.ctrl-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--color-text-light);
  cursor: pointer;
  transition: all 0.15s;
}

.ctrl-btn:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}

/* BPMN Canvas */
.bpmn-canvas {
  flex: 1;
  width: 100%;
  min-height: 0;
}

/* bpmn-js overrides */
.bpmn-canvas :deep(.djs-container) {
  background: var(--color-bg) !important;
}

.bpmn-canvas :deep(.djs-palette) {
  display: none !important;
}

.bpmn-canvas :deep(.djs-element:hover .djs-outline) {
  stroke: #3949AB !important;
  stroke-width: 2px !important;
}

.bpmn-canvas :deep(.bpmn-element-selected .djs-outline) {
  visibility: visible !important;
  stroke: #1565C0 !important;
  stroke-width: 2.5px !important;
  stroke-dasharray: none !important;
}

.bpmn-canvas :deep(text) {
  fill: #212121 !important;
}

.bpmn-canvas :deep(.djs-label text) {
  fill: #212121 !important;
}

/* Empty State */
.bpmn-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
  pointer-events: none;
}

.empty-icon {
  color: var(--color-text-light);
}

.empty-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text);
}

.empty-desc {
  font-size: 0.7rem;
  color: var(--color-text-light);
  line-height: 1.5;
}

/* Loading */
.bpmn-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--color-text-light);
  font-size: 0.75rem;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Drag Overlay */
.drag-overlay {
  position: absolute;
  inset: 0;
  background: rgba(34, 139, 230, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
  pointer-events: none;
}

.drag-overlay__content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--color-accent);
  font-size: 0.8rem;
  font-weight: 500;
}
</style>
