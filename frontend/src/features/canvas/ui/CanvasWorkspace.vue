<script setup>
import { ref, computed, onMounted, onUnmounted, markRaw, nextTick } from 'vue'
import { VueFlow, useVueFlow, MarkerType } from '@vue-flow/core'
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

// Right-side panel mode
// - none: no side panel
// - chat: Model Modifier chat
// - inspector: node inspector (property editor)
const panelMode = ref('chat')

// Sidebar icon click handlers (toggle behavior)
function toggleChatPanel() {
  panelMode.value = panelMode.value === 'chat' ? 'none' : 'chat'
}

function toggleInspectorPanel() {
  if (panelMode.value === 'inspector') {
    panelMode.value = 'none'
  } else {
    // Use currently selected node if any, otherwise show empty inspector
    const selectedNode = canvasStore.selectedNodes[0] || null
    inspectingNodeId.value = selectedNode?.id || null
    inspectingInitialTab.value = 'properties'
    panelMode.value = 'inspector'
  }
}

const chatPanelWidth = ref(360)
const isResizingChat = ref(false)

// Inspector state
const inspectingNodeId = ref(null)
const inspectingInitialTab = ref('properties')

const { fitView, zoomIn, zoomOut, getNodes } = useVueFlow()

// Hover state for highlighting connections
const hoveredNodeId = ref(null)
const hoveredEdgeId = ref(null)

// Get BC ID for a node
const getNodeBcId = (nodeId) => {
  const node = canvasStore.nodes.find(n => n.id === nodeId)
  if (!node) return null
  // BC node itself
  if (node.type === 'boundedcontext') return node.id
  // Node inside a BC
  return node.parentNode || node.data?.bcId || null
}

// Get all connected nodes and edges recursively (follows all relation chains in both directions)
// Only follows actual relation edges (EMITS, TRIGGERS, INVOKES, HAS_COMMAND)
// Excludes Aggregate nodes from the chain (they don't trigger actions, so don't traverse through them)
// When hovering a node, shows:
//   - Previous flow: all nodes that lead to this node (backward traversal)
//   - Next flow: all nodes that this node leads to (forward traversal)
const getAllConnectedNodesAndEdges = (startNodeId) => {
  const connectedNodes = new Set([startNodeId])
  const connectedEdges = new Set()
  const visited = new Set([startNodeId])
  
  // Valid relation edge types (exclude container membership edges)
  const validEdgeTypes = ['EMITS', 'TRIGGERS', 'INVOKES', 'HAS_COMMAND']
  
  // Valid relation edge colors (for backward compatibility)
  const validEdgeColors = ['#fd7e14', '#b197fc', '#5c7cfa', '#fcc419']
  
  // Check if an edge is a valid relation edge
  const isValidRelationEdge = (edge) => {
    const edgeType = edge.data?.edgeType
    
    if (edgeType) {
      return validEdgeTypes.includes(edgeType)
    } else {
      // If edgeType is not stored, be very strict:
      // Must have valid color AND valid label
      const stroke = edge.style?.stroke
      const hasValidLabel = edge.label && ['triggers', 'invokes', 'emits', 'has_command'].includes(edge.label.toLowerCase())
      const hasValidColor = stroke && validEdgeColors.includes(stroke)
      
      return hasValidColor && hasValidLabel
    }
  }
  
  // Recursive function to traverse connected nodes in a specific direction
  // direction: 'forward' (follow edges from source to target) or 'backward' (follow edges from target to source)
  const traverse = (nodeId, direction) => {
    // Find all edges connected to this node
    canvasStore.edges.forEach(edge => {
      // Only follow valid relation edges
      if (!isValidRelationEdge(edge)) {
      return
    }
    
    // Additional check: exclude edges where source or target is a BC node
    const sourceNode = canvasStore.nodes.find(n => n.id === edge.source)
    const targetNode = canvasStore.nodes.find(n => n.id === edge.target)
    if (sourceNode?.type === 'boundedcontext' || targetNode?.type === 'boundedcontext') {
      return
    }
    
    let nextNodeId = null
      let shouldFollow = false
    
      if (direction === 'forward') {
        // Forward: follow edges where this node is the source
        if (edge.source === nodeId) {
      nextNodeId = edge.target
          shouldFollow = true
        }
      } else if (direction === 'backward') {
        // Backward: follow edges where this node is the target
        if (edge.target === nodeId) {
      nextNodeId = edge.source
          shouldFollow = true
        }
    }
    
      // Only proceed if we found a connected node in the right direction
      if (!nextNodeId || !shouldFollow) {
      return
    }
    
      // Always add the edge if it's connected to the current node
    connectedEdges.add(edge.id)
    
      // Skip if already visited (prevent infinite loops)
      if (visited.has(nextNodeId)) {
        return
      }
      
      // Get the next node to check its type
      const nextNode = canvasStore.nodes.find(n => n.id === nextNodeId)
      
      // Skip Aggregate nodes - they don't trigger actions, so don't follow edges through them
      // Don't add Aggregate nodes to the connected set (they're not part of the action flow)
      if (nextNode?.type === 'aggregate') {
        return
      }
      
      // Add node and continue traversing
    connectedNodes.add(nextNodeId)
      visited.add(nextNodeId)
      
      // Recursively traverse in the same direction
      traverse(nextNodeId, direction)
  })
  }
  
  // Traverse both forward (next flow) and backward (previous flow)
  traverse(startNodeId, 'forward')
  traverse(startNodeId, 'backward')
  
  return {
    nodes: connectedNodes,
    edges: Array.from(connectedEdges)
  }
}

// Get connected node IDs for a given node (legacy, kept for compatibility)
const getConnectedNodeIds = (nodeId) => {
  const { nodes } = getAllConnectedNodesAndEdges(nodeId)
  return nodes
}

// Get connected edge IDs for a given node (including all chain connections)
const getConnectedEdgeIds = (nodeId) => {
  const { edges } = getAllConnectedNodesAndEdges(nodeId)
  return edges
}

// Get cross-BC connected node IDs (nodes in other BCs connected via edges)
const getCrossBcConnectedNodeIds = (nodeId) => {
  const nodeBcId = getNodeBcId(nodeId)
  const { nodes } = getAllConnectedNodesAndEdges(nodeId)
  
  // Filter to only nodes in different BCs
  const crossBcNodes = new Set()
  nodes.forEach(nodeId => {
    const nodeBc = getNodeBcId(nodeId)
    if (nodeBc !== nodeBcId && nodeBc !== null) {
      crossBcNodes.add(nodeId)
    }
  })
  
  return crossBcNodes
}

const nodesWithSelection = computed(() => {
  // Check if hovered node is a BC node or Aggregate node - if so, don't highlight anything
  const hoveredNode = hoveredNodeId.value ? canvasStore.nodes.find(n => n.id === hoveredNodeId.value) : null
  const isHoveredBcNode = hoveredNode?.type === 'boundedcontext'
  const isHoveredAggregateNode = hoveredNode?.type === 'aggregate'
  
  // If hovering over BC node or Aggregate node, don't apply any highlighting
  if (isHoveredBcNode || isHoveredAggregateNode) {
    return canvasStore.nodes.map(node => ({
      ...node,
      class: canvasStore.isSelected(node.id) ? 'es-node--selected' : ''
    }))
  }
  
  const connectedNodeIds = hoveredNodeId.value 
    ? getConnectedNodeIds(hoveredNodeId.value)
    : new Set()
  const crossBcConnectedNodeIds = hoveredNodeId.value
    ? getCrossBcConnectedNodeIds(hoveredNodeId.value)
    : new Set()
  const connectedEdgeIds = hoveredNodeId.value
    ? getConnectedEdgeIds(hoveredNodeId.value)
    : []
  const edgeConnectedNodeIds = hoveredEdgeId.value
    ? new Set([canvasStore.edges.find(e => e.id === hoveredEdgeId.value)?.source, 
                canvasStore.edges.find(e => e.id === hoveredEdgeId.value)?.target].filter(Boolean))
    : new Set()
  
  return canvasStore.nodes.map(node => {
    // Skip highlighting for BC nodes themselves
    if (node.type === 'boundedcontext') {
      return {
        ...node,
        class: canvasStore.isSelected(node.id) ? 'es-node--selected' : ''
      }
    }
    
    const isConnected = connectedNodeIds.has(node.id) || edgeConnectedNodeIds.has(node.id)
    const isCrossBcConnected = crossBcConnectedNodeIds.has(node.id)
    
    return {
      ...node,
      class: [
        canvasStore.isSelected(node.id) ? 'es-node--selected' : '',
        (hoveredNodeId.value === node.id || isConnected || isCrossBcConnected) ? 'es-node--highlighted' : '',
        hoveredNodeId.value && !isConnected && !isCrossBcConnected && hoveredNodeId.value !== node.id ? 'es-node--dimmed' : ''
      ].filter(Boolean).join(' ')
    }
  })
})

// Vue Flow sometimes relies on reference changes to refresh edges rendering.
// Wrap edges in a computed that returns a new array to ensure updates are picked up.
const edgesForFlow = computed(() => {
  // Check if hovered node is a BC node or Aggregate node - if so, don't highlight anything
  const hoveredNode = hoveredNodeId.value ? canvasStore.nodes.find(n => n.id === hoveredNodeId.value) : null
  const isHoveredBcNode = hoveredNode?.type === 'boundedcontext'
  const isHoveredAggregateNode = hoveredNode?.type === 'aggregate'
  
  // If hovering over BC node or Aggregate node, don't apply any highlighting
  if (isHoveredBcNode || isHoveredAggregateNode) {
    return canvasStore.edges.map(edge => ({ ...edge }))
  }
  
  const connectedEdgeIds = hoveredNodeId.value
    ? getConnectedEdgeIds(hoveredNodeId.value)
    : []
  
  // Check if edge is cross-BC
  const isCrossBcEdge = (edge) => {
    const sourceBcId = getNodeBcId(edge.source)
    const targetBcId = getNodeBcId(edge.target)
    return sourceBcId !== null && targetBcId !== null && sourceBcId !== targetBcId
  }
  
  return canvasStore.edges.map(edge => {
    const isConnected = connectedEdgeIds.includes(edge.id)
    const isHovered = hoveredEdgeId.value === edge.id
    const isCrossBc = isCrossBcEdge(edge)
    const isHighlighted = isHovered || isConnected
    
    return {
      ...edge,
      class: [
        isHighlighted ? 'vue-flow__edge--highlighted' : '',
        isCrossBc && isHighlighted ? 'vue-flow__edge--cross-bc' : '',
        hoveredNodeId.value && !isConnected && !isHovered ? 'vue-flow__edge--dimmed' : ''
      ].filter(Boolean).join(' '),
      // Increase z-index for highlighted edges to appear above dimmed nodes
      style: {
        ...edge.style,
        zIndex: isHighlighted ? 20 : (hoveredNodeId.value && !isConnected && !isHovered ? 1 : undefined)
      }
    }
  })
})

// Node types mapping (use markRaw to prevent reactive wrapping)
const nodeTypes = {
  command: markRaw(CommandNode),
  event: markRaw(EventNode),
  policy: markRaw(PolicyNode),
  aggregate: markRaw(AggregateNode),
  boundedcontext: markRaw(BoundedContextNode),
  readmodel: markRaw(ReadModelNode),
  ui: markRaw(UINode)
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
  panelMode.value = 'chat'
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
  panelMode.value = 'inspector'
}

function openInspectorForNodeTab(nodeId, tab) {
  const opId = newOpId('openInspectorTab')
  log.info('inspector_open', 'Opening Inspector for node with tab.', { opId, nodeId, tab })
  console.info('[RAW][CanvasWorkspace][inspector_open]', { opId, nodeId, tab })
  inspectingNodeId.value = nodeId
  // CQRS tab has been removed; keep this robust for any legacy callers.
  inspectingInitialTab.value = tab === 'preview' ? 'preview' : 'properties'
  panelMode.value = 'inspector'
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
    panelMode: panelMode.value
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

// Node hover handlers
function onNodeMouseEnter(event) {
  // Skip highlighting for BC nodes and Aggregate nodes (they don't trigger actions)
  if (event.node.type === 'boundedcontext' || event.node.type === 'aggregate') {
    return
  }
  hoveredNodeId.value = event.node.id
}

function onNodeMouseLeave() {
  hoveredNodeId.value = null
}

// Edge hover handlers
function onEdgeMouseEnter(event) {
  hoveredEdgeId.value = event.edge.id
}

function onEdgeMouseLeave() {
  hoveredEdgeId.value = null
}

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
    
    // CRITICAL: Before adding nodes, sync ALL BC positions from Vue Flow to preserve user-adjusted positions
    // This must happen BEFORE addNodesWithLayout to prevent position reset
    // Use both getNodes() and DOM to ensure we get the actual rendered positions
    try {
      const vueFlowNodes = getNodes()
      vueFlowNodes.forEach(node => {
        if (node.type === 'boundedcontext' && node.position) {
          const storeNode = canvasStore.nodes.find(n => n.id === node.id)
          if (storeNode) {
            // Also check DOM for actual rendered position (more reliable)
            try {
              const nodeEl = document.querySelector(`[data-id="${node.id}"]`)
              if (nodeEl) {
                const transform = nodeEl.style.transform
                if (transform) {
                  const match = transform.match(/translate\(([^,]+)px,\s*([^)]+)px\)/)
                  if (match) {
                    const x = parseFloat(match[1])
                    const y = parseFloat(match[2])
                    if (!isNaN(x) && !isNaN(y)) {
                      storeNode.position = { x, y }
                      console.log(`[CanvasWorkspace] Synced BC position from DOM: ${node.id} -> (${x}, ${y})`)
                      return
                    }
                  }
                }
              }
            } catch (e) {
              // Fall through to use Vue Flow position
            }
            // Fallback: use Vue Flow's position
            storeNode.position = { x: node.position.x, y: node.position.y }
            console.log(`[CanvasWorkspace] Synced BC position from Vue Flow: ${node.id} -> (${node.position.x}, ${node.position.y})`)
          }
        }
      })
    } catch (e) {
      console.error('[CanvasWorkspace] Failed to sync BC positions before addNodes:', e)
    }
    
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
// Handle node position changes - only update position, not edges
// IMPORTANT: Do NOT update BC container positions here - they are managed by Vue Flow
// Only update child node positions (which need to update BC size)
function onNodesChange(changes) {
  changes.forEach(change => {
    if (change.type === 'position') {
      const node = change.node
      if (node && change.position) {
        // Skip BC containers - their positions are managed by Vue Flow directly
        // Updating them here can cause position reset issues
        if (node.type === 'boundedcontext') {
          return
        }
        canvasStore.updateNodePosition(node.id, change.position)
      }
    }
  })
}

// Handle node drag stop - update edges when drag ends
function onNodeDragStop(e) {
  const node = e.node
  if (!node) return
  
  // CRITICAL: For BC nodes, save the final position to nodes.value
  // This prevents position reset when new nodes are added
  if (node.type === 'boundedcontext' && node.position) {
    const storeNode = canvasStore.nodes.find(n => n.id === node.id)
    if (storeNode) {
      storeNode.position = { x: node.position.x, y: node.position.y }
      console.log(`[CanvasWorkspace] Saved BC position after drag: ${node.id} -> (${node.position.x}, ${node.position.y})`)
    }
  }
  
  // Update edges for the dragged node
  canvasStore.rerouteEdgesForMovedNodes([node.id])
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
          :connection-radius="40"
          connection-mode="loose"
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
          @node-drag-stop="onNodeDragStop"
          @node-click="onNodeClick"
          @node-double-click="onNodeDoubleClick"
          @node-mouse-enter="onNodeMouseEnter"
          @node-mouse-leave="onNodeMouseLeave"
          @edge-mouse-enter="onEdgeMouseEnter"
          @edge-mouse-leave="onEdgeMouseLeave"
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
      v-if="panelMode !== 'none'"
      class="chat-panel-resizer"
      @mousedown="startResizeChat"
      title="드래그하여 패널 너비 조절"
    ></div>

    <!-- Right-side Panel Wrapper -->
    <div v-if="panelMode !== 'none'" class="side-panel-wrapper" :style="{ width: chatPanelWidth + 'px' }">
      <div v-if="panelMode === 'chat'" class="chat-panel-wrapper">
        <ChatPanel />
      </div>

      <!-- UI Preview Panel -->
      <!-- Inspector Panel (placeholder) -->
      <div v-else-if="panelMode === 'inspector'" class="inspector-wrapper">
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
        :class="{ 'is-active': panelMode === 'chat' }"
        @click="toggleChatPanel"
        title="Model Modifier"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
      </button>
      <button 
        class="right-sidebar__icon"
        :class="{ 'is-active': panelMode === 'inspector' }"
        @click="toggleInspectorPanel"
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

/* Highlighted node (hovered or connected) */
.vue-flow__node.es-node--highlighted {
  outline: 3px solid #fcc419 !important;
  outline-offset: 3px !important;
  box-shadow: 0 0 20px rgba(252, 196, 25, 0.5) !important;
  z-index: 10 !important;
  transition: all 0.2s ease !important;
}

/* Ensure edges layer is above nodes */
.vue-flow__edges {
  z-index: 5 !important;
}

/* Dimmed node (not connected to hovered node) */
.vue-flow__node.es-node--dimmed {
  opacity: 0.6 !important;
  transition: opacity 0.2s ease !important;
  z-index: 1 !important;
}

/* Highlighted edge (hovered or connected to hovered node) - ensure it's above everything */
.vue-flow__edge.vue-flow__edge--highlighted {
  z-index: 1000 !important;
  position: relative;
  pointer-events: auto !important;
}

.vue-flow__edge.vue-flow__edge--highlighted .vue-flow__edge-path {
  stroke-width: 7 !important;
  filter: 
    drop-shadow(0 0 10px currentColor) 
    drop-shadow(0 0 6px rgba(252, 196, 25, 1))
    drop-shadow(0 0 3px rgba(255, 255, 255, 1));
  z-index: 1000 !important;
  transition: all 0.2s ease !important;
  paint-order: stroke fill;
  stroke-linecap: round;
  stroke-linejoin: round;
  /* Add a white outline effect for better visibility over nodes */
  stroke: currentColor;
  stroke-opacity: 1;
}

.vue-flow__edge.vue-flow__edge--highlighted .vue-flow__edge-text {
  font-weight: 600 !important;
  font-size: 11px !important;
}

/* Dimmed edge (not connected to hovered node) */
.vue-flow__edge.vue-flow__edge--dimmed {
  z-index: 1 !important;
}

.vue-flow__edge.vue-flow__edge--dimmed .vue-flow__edge-path {
  opacity: 0.3 !important;
  transition: opacity 0.2s ease !important;
}

/* Cross-BC edge highlight */
.vue-flow__edge.vue-flow__edge--cross-bc .vue-flow__edge-path {
  stroke-width: 3 !important;
  stroke-dasharray: 8 4 !important;
  filter: drop-shadow(0 0 6px #fcc419);
}

/* Edge hover effect */
.vue-flow__edge:hover .vue-flow__edge-path {
  stroke-width: 3 !important;
  filter: drop-shadow(0 0 3px currentColor);
  cursor: pointer;
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
