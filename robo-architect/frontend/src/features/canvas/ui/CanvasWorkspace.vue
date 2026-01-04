<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { createLogger, newOpId } from '@/app/logging/logger'

// Custom Nodes
import CommandNode from './nodes/CommandNode.vue'
import EventNode from './nodes/EventNode.vue'
import PolicyNode from './nodes/PolicyNode.vue'
import AggregateNode from './nodes/AggregateNode.vue'
import BoundedContextNode from './nodes/BoundedContextNode.vue'
import ReadModelNode from './nodes/ReadModelNode.vue'
import UINode from './nodes/UINode.vue'

// Chat Panel
import ChatPanel from '@/features/modelModifier/ui/ChatPanel.vue'

// Inspector Panel (right-side)
// NOTE: implemented in a follow-up TODO; keep lightweight placeholder for now
import InspectorPanel from './InspectorPanel.vue'

const canvasStore = useCanvasStore()
const isDragOver = ref(false)
const log = createLogger({ scope: 'CanvasWorkspace' })

// Sidebar icon click handlers (toggle behavior) - using store methods
function handleToggleChatPanel() {
  canvasStore.toggleChatPanel()
}

function handleToggleInspectorPanel() {
  if (canvasStore.rightPanelMode === 'inspector') {
    canvasStore.closeRightPanel()
  } else {
    // Use currently selected node if any, otherwise show empty inspector
    const selectedNode = canvasStore.selectedNodes[0] || null
    inspectingNodeId.value = selectedNode?.id || null
    inspectingInitialTab.value = 'properties'
    canvasStore.setRightPanelMode('inspector')
  }
}

const chatPanelWidth = ref(360)
const isResizingChat = ref(false)

// Inspector state
const inspectingNodeId = ref(null)
const inspectingInitialTab = ref('properties')

const { fitView, zoomIn, zoomOut } = useVueFlow()

const nodesWithSelection = computed(() => {
  return canvasStore.nodes.map(node => ({
    ...node,
    class: canvasStore.isSelected(node.id) ? 'es-node--selected' : ''
  }))
})

// Vue Flow sometimes relies on reference changes to refresh edges rendering.
// Wrap edges in a computed that returns a new array to ensure updates are picked up.
const edgesForFlow = computed(() => [...canvasStore.edges])

// Node types mapping
const nodeTypes = {
  command: CommandNode,
  event: EventNode,
  policy: PolicyNode,
  aggregate: AggregateNode,
  boundedcontext: BoundedContextNode,
  readmodel: ReadModelNode,
  ui: UINode
}

// MiniMap node color
function getNodeColor(node) {
  const colors = {
    command: '#5c7cfa',
    event: '#fd7e14',
    policy: '#b197fc',
    aggregate: '#fcc419',
    boundedcontext: '#373a40',
    readmodel: '#40c057',
    ui: '#ffffff'
  }
  return colors[node.type] || '#909296'
}

function switchToChatFromInspector(nodeId) {
  canvasStore.setRightPanelMode('chat')
  if (nodeId) {
    canvasStore.selectNode(nodeId)
  }
}

function openInspectorForNode(nodeId) {
  const opId = newOpId('openInspector')
  log.info('inspector_open', 'Opening Inspector for node.', { opId, nodeId, tab: 'properties' })
  console.info('[RAW][CanvasWorkspace][inspector_open]', { opId, nodeId, tab: 'properties' })
  inspectingNodeId.value = nodeId
  inspectingInitialTab.value = 'properties'
  canvasStore.setRightPanelMode('inspector')
}

function openInspectorForNodeTab(nodeId, tab) {
  const opId = newOpId('openInspectorTab')
  log.info('inspector_open', 'Opening Inspector for node with tab.', { opId, nodeId, tab })
  console.info('[RAW][CanvasWorkspace][inspector_open]', { opId, nodeId, tab })
  inspectingNodeId.value = nodeId
  // CQRS tab has been removed; keep this robust for any legacy callers.
  inspectingInitialTab.value = tab === 'preview' ? 'preview' : 'properties'
  canvasStore.setRightPanelMode('inspector')
}

async function onNodeDoubleClick(event) {
  const opId = newOpId('dblclick')
  const node = event.node
  const nativeEvent = event.event
  log.info('node_double_click', 'Node double-click received.', {
    opId,
    node: { id: node?.id, type: node?.type, data: node?.data },
    input: {
      shiftKey: !!nativeEvent?.shiftKey,
      ctrlKey: !!nativeEvent?.ctrlKey,
      metaKey: !!nativeEvent?.metaKey,
      altKey: !!nativeEvent?.altKey,
      button: nativeEvent?.button,
      detail: nativeEvent?.detail
    },
    panelMode: canvasStore.rightPanelMode
  })
  // Raw event + node data (best-effort; MouseEvent is not JSON-serializable)
  console.info('[RAW][CanvasWorkspace][node_double_click]', { opId, node, nativeEvent })

  if (node.type === 'ui') {
    canvasStore.selectNode(node.id)
    openInspectorForNodeTab(node.id, 'preview')
    return
  }

  // Event node: Shift+double click expands triggered policies; otherwise open Inspector
  if (node.type === 'event' && nativeEvent?.shiftKey) {
    log.info('event_expand_triggers_start', 'Expanding Event triggers (Shift+double click).', {
      opId,
      eventId: node.id,
      nodeData: node.data
    })
    console.info('[RAW][CanvasWorkspace][event_expand_triggers_start]', { opId, eventId: node.id, nodeData: node.data })
    try {
      const newNodes = await canvasStore.expandEventTriggers(node.id)
      log.info('event_expand_triggers_done', 'Expanded Event triggers.', { opId, eventId: node.id, newNodes })
      console.info('[RAW][CanvasWorkspace][event_expand_triggers_done]', { opId, eventId: node.id, newNodes })
    } catch (e) {
      log.error('event_expand_triggers_error', 'Failed to expand Event triggers.', { opId, eventId: node.id, error: String(e) })
      console.error('[RAW][CanvasWorkspace][event_expand_triggers_error]', { opId, eventId: node.id, error: e })
    }
    return
  }

  // Default: open Inspector
  canvasStore.selectNode(node.id)
  openInspectorForNode(node.id)
}

// CQRS editor has been removed from the UI; keep Inspector as the single entry point.

// Handle drop from navigator
async function handleDrop(event) {
  event.preventDefault()
  isDragOver.value = false
  
  const data = event.dataTransfer.getData('application/json')
  if (!data) return
  
  try {
    const { nodeId } = JSON.parse(data)
    
    // Use the new API that includes BC context
    const response = await fetch(`/api/graph/expand-with-bc/${nodeId}`)
    const expandedData = await response.json()
    
    // Track new node IDs for cross-BC relation finding
    const newNodeIds = expandedData.nodes.map(n => n.id)
    
    canvasStore.addNodesWithLayout(
      expandedData.nodes, 
      expandedData.relationships, 
      expandedData.bcContext
    )
    
    // Find cross-BC relations (Event → TRIGGERS → Policy between BCs)
    await canvasStore.findCrossBCRelations(newNodeIds)
    
    // Also find any other relations
    await canvasStore.findAndAddRelations()
    
    // Fit view after adding nodes
    setTimeout(() => fitView({ padding: 0.3 }), 150)
  } catch (error) {
    console.error('Failed to handle drop:', error)
  }
}

function handleDragOver(event) {
  event.preventDefault()
  isDragOver.value = true
  event.dataTransfer.dropEffect = 'copy'
}

function handleDragLeave() {
  isDragOver.value = false
}

// Watch for node changes and update positions
function onNodesChange(changes) {
  changes.forEach(change => {
    if (change.type === 'position' && change.position) {
      canvasStore.updateNodePosition(change.id, change.position)
    }
  })
}

function onNodeClick(event) {
  const nodeId = event.node.id

  // Don't select BC containers
  if (event.node.type === 'boundedcontext') {
    return
  }

  // Multi select
  if (event.event.ctrlKey || event.event.metaKey) {
    canvasStore.toggleNodeSelection(nodeId)
  } else if (event.event.shiftKey) {
    canvasStore.addToSelection(nodeId)
  } else {
    canvasStore.selectNode(nodeId)
  }
}

function onPaneClick() {
  canvasStore.clearSelection()
  // Close right panel (Model Modifier / Inspector) when clicking on canvas background
  canvasStore.closeRightPanel()
}

function startResizeChat(e) {
  isResizingChat.value = true
  e.preventDefault()
  document.addEventListener('mousemove', onResizeChat)
  document.addEventListener('mouseup', stopResizeChat)
}

function onResizeChat(e) {
  if (!isResizingChat.value) return
  // Right-side panel width from viewport right edge
  const next = Math.round(window.innerWidth - e.clientX)
  chatPanelWidth.value = Math.max(280, Math.min(640, next))
  try {
    localStorage.setItem('canvas_chat_panel_width', String(chatPanelWidth.value))
  } catch {}
}

function stopResizeChat() {
  isResizingChat.value = false
  document.removeEventListener('mousemove', onResizeChat)
  document.removeEventListener('mouseup', stopResizeChat)
}

onMounted(() => {
  try {
    const v = Number(localStorage.getItem('canvas_chat_panel_width'))
    if (Number.isFinite(v) && v >= 200) chatPanelWidth.value = v
  } catch {}
})

onUnmounted(() => {
  stopResizeChat()
})
</script>

<template>
  <div class="right-panel-container">
    <div 
      class="right-panel"
      :class="{ 'drop-zone-active': isDragOver }"
      @drop="handleDrop"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
    >
      <div class="canvas-container">
        <div v-if="canvasStore.nodes.length === 0" class="canvas-empty">
          <div class="canvas-empty__icon">📋</div>
          <div class="canvas-empty__text">Canvas is empty</div>
          <div class="canvas-empty__hint">
            Drag items from the navigator or double-click to add
          </div>
        </div>

        <VueFlow
          v-else
          :nodes="nodesWithSelection"
          :edges="edgesForFlow"
          :node-types="nodeTypes"
          :default-viewport="{ zoom: 0.8, x: 50, y: 50 }"
          :min-zoom="0.2"
          :max-zoom="2"
          :snap-to-grid="true"
          :snap-grid="[10, 10]"
          :nodes-draggable="true"
          :nodes-connectable="false"
          :pan-on-drag="true"
          :zoom-on-scroll="true"
          :prevent-scrolling="true"
          fit-view-on-init
          @nodes-change="onNodesChange"
          @node-click="onNodeClick"
          @node-double-click="onNodeDoubleClick"
          @pane-click="onPaneClick"
        >
          <Background pattern-color="#2a2a3a" :gap="20" />
          <Controls position="bottom-left" />
          <MiniMap 
            :node-color="getNodeColor"
            :node-stroke-width="3"
            pannable
            zoomable
          />
        </VueFlow>
      </div>

      <div v-if="canvasStore.selectedNodes.length > 0" class="selection-badge">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 11 12 14 22 4"></polyline>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
        </svg>
        <span>{{ canvasStore.selectedNodes.length }} selected</span>
        <button class="selection-badge__clear" @click="canvasStore.clearSelection()">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div v-if="canvasStore.nodes.length > 0" class="canvas-toolbar">
        <button class="canvas-toolbar__btn" @click="zoomIn()" title="Zoom In">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            <line x1="11" y1="8" x2="11" y2="14"></line>
            <line x1="8" y1="11" x2="14" y2="11"></line>
          </svg>
        </button>

        <button class="canvas-toolbar__btn" @click="zoomOut()" title="Zoom Out">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            <line x1="8" y1="11" x2="14" y2="11"></line>
          </svg>
        </button>

        <button class="canvas-toolbar__btn" @click="fitView({ padding: 0.3 })" title="Fit View">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
          </svg>
        </button>

        <div class="canvas-toolbar__divider"></div>

        <button class="canvas-toolbar__btn" @click="canvasStore.findAndAddRelations()" title="Find Relations">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="18" cy="5" r="3"></circle>
            <circle cx="6" cy="12" r="3"></circle>
            <circle cx="18" cy="19" r="3"></circle>
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
          </svg>
        </button>

        <button class="canvas-toolbar__btn" @click="canvasStore.clearCanvas()" title="Clear Canvas">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      </div>
    </div>

    <!-- Resizer (between canvas and right-side panel) -->
    <div
      v-if="canvasStore.rightPanelMode !== 'none'"
      class="chat-panel-resizer"
      @mousedown="startResizeChat"
      title="드래그하여 패널 너비 조절"
    ></div>

    <!-- Right-side Panel Wrapper -->
    <div v-if="canvasStore.rightPanelMode !== 'none'" class="side-panel-wrapper" :style="{ width: chatPanelWidth + 'px' }">
      <div v-if="canvasStore.rightPanelMode === 'chat'" class="chat-panel-wrapper">
        <ChatPanel />
      </div>

      <!-- UI Preview Panel -->
      <!-- Inspector Panel (placeholder) -->
      <div v-else-if="canvasStore.rightPanelMode === 'inspector'" class="inspector-wrapper">
        <InspectorPanel
          :node-id="inspectingNodeId"
          :initial-tab="inspectingInitialTab"
          @updated="() => {}"
          @request-chat="switchToChatFromInspector"
        />
      </div>
    </div>

    <!-- Right Sidebar Icons (always visible) -->
    <div class="right-sidebar">
      <button 
        class="right-sidebar__icon"
        :class="{ 'is-active': canvasStore.rightPanelMode === 'chat' }"
        @click="handleToggleChatPanel"
        title="Model Modifier"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
      </button>
      <button 
        class="right-sidebar__icon"
        :class="{ 'is-active': canvasStore.rightPanelMode === 'inspector' }"
        @click="handleToggleInspectorPanel"
        title="Inspector"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
      </button>
    </div>
  </div>

</template>

<style>
@import '@vue-flow/core/dist/style.css';
@import '@vue-flow/core/dist/theme-default.css';
@import '@vue-flow/controls/dist/style.css';
@import '@vue-flow/minimap/dist/style.css';

/* Container for canvas + chat */
.right-panel-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.chat-panel-resizer {
  width: 6px;
  cursor: col-resize;
  background: transparent;
  position: relative;
}

.chat-panel-resizer:hover {
  background: rgba(34, 139, 230, 0.12);
}

/* Vue Flow custom background */
.vue-flow {
  background: #1a1b26 !important;
}

/* BC Group Node styling */
.vue-flow__node-boundedcontext {
  padding: 0 !important;
  border-radius: 16px !important;
  background: transparent !important;
  border: none !important;
}

/* Ensure child nodes are visible above parent */
.vue-flow__node {
  z-index: 1;
}

.vue-flow__node-boundedcontext {
  z-index: 0 !important;
}

/* Selected node styling */
.vue-flow__node.es-node--selected {
  outline: 3px solid var(--color-accent) !important;
  outline-offset: 3px !important;
  box-shadow: 0 0 20px rgba(34, 139, 230, 0.4) !important;
}

/* Vue Flow Minimap custom styles */
.vue-flow__minimap {
  background: var(--color-bg-secondary) !important;
  border: 1px solid var(--color-border) !important;
  border-radius: var(--radius-md) !important;
}

/* Vue Flow Controls custom styles */
.vue-flow__controls {
  background: var(--color-bg-secondary) !important;
  border: 1px solid var(--color-border) !important;
  border-radius: var(--radius-md) !important;
  box-shadow: var(--shadow-md) !important;
}

.vue-flow__controls-button {
  background: transparent !important;
  border: none !important;
  color: var(--color-text) !important;
}

.vue-flow__controls-button:hover {
  background: var(--color-bg-tertiary) !important;
}

.vue-flow__controls-button svg {
  fill: var(--color-text) !important;
}

/* Edge labels */
.vue-flow__edge-textbg {
  fill: #1a1b26 !important;
}

.vue-flow__edge-text {
  fill: #c1c2c5 !important;
}

/* Selection Badge */
.selection-badge {
  position: absolute;
  top: var(--spacing-md);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-md);
  background: var(--color-accent);
  color: white;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 500;
  box-shadow: var(--shadow-md);
  z-index: 10;
  animation: slideDown 0.2s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

.selection-badge__clear {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  cursor: pointer;
  transition: background 0.15s ease;
}

.selection-badge__clear:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* Chat Panel Wrapper */
.chat-panel-wrapper {
  height: 100%;
  overflow: hidden;
  animation: slideIn 0.2s ease;
}

/* UI Preview Panel Wrapper */
.side-panel-wrapper {
  flex-shrink: 0;
  width: 360px;
  height: 100%;
  overflow: hidden;
  animation: slideIn 0.2s ease;
}

.inspector-wrapper {
  height: 100%;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* Right Sidebar Icons */
.right-sidebar {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 6px;
  background: var(--color-bg-secondary);
  border-left: 1px solid var(--color-border);
}

.right-sidebar__icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  cursor: pointer;
  transition: all 0.15s ease;
}

.right-sidebar__icon:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}

.right-sidebar__icon.is-active {
  background: var(--color-accent);
  color: white;
}

.right-sidebar__icon.is-active:hover {
  background: #1c7ed6;
}
</style>
