<script setup>
import { ref, computed, onMounted, watch, markRaw, nextTick } from 'vue'
import { VueFlow, useVueFlow, MarkerType } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { useAggregateViewerStore } from '@/features/canvas/aggregateViewer.store'
import { useModelModifierStore } from '@/features/modelModifier/modelModifier.store'
import AggregateViewerNode from './nodes/AggregateViewerNode.vue'
import EnumViewerNode from './nodes/EnumViewerNode.vue'
import ValueObjectViewerNode from './nodes/ValueObjectViewerNode.vue'
import AggregateContainerNode from './nodes/AggregateContainerNode.vue'
import AggregateViewerInspector from './AggregateViewerInspector.vue'
import ChatPanel from '@/features/modelModifier/ui/ChatPanel.vue'
import StraightEdge from './edges/StraightEdge.vue'
import StepEdge from './edges/StepEdge.vue'

const store = useAggregateViewerStore()
const chatStore = useModelModifierStore()
const { fitView, zoomIn, zoomOut, getNodes, getNode, updateEdge, getViewport } = useVueFlow()

// Track node positions for edge handle updates (updated via onNodesChange)
const nodePositions = ref(new Map())
// Trigger ref to force edges computed to re-run when nodes are dragged
const edgeUpdateTrigger = ref(0)

// Hover state for highlighting connections
const hoveredNodeId = ref(null)
const hoveredEdgeId = ref(null)

// Panel mode: 'none' | 'chat' | 'inspector'
const panelMode = ref('chat')
const chatPanelWidth = ref(360)
const isResizingChat = ref(false)
const inspectorPanelWidth = ref(400)
const isResizingInspector = ref(false)

// Inspector state
const inspectingAggregateId = ref(null)
const inspectingEnumIndex = ref(null)
const inspectingVoIndex = ref(null)

// Watch for data changes and update layout (handled in nodes watch below)

// Drag and drop handlers
const isDragOver = ref(false)

function handleDragOver(event) {
  event.preventDefault()
  isDragOver.value = true
  event.dataTransfer.dropEffect = 'copy'
}

function handleDragLeave() {
  isDragOver.value = false
}

async function handleDrop(event) {
  event.preventDefault()
  isDragOver.value = false
  
  const data = event.dataTransfer.getData('application/json')
  if (!data) return
  
  try {
    const { nodeId, nodeType } = JSON.parse(data)
    
    // Only handle BoundedContext drops
    if (nodeType === 'BoundedContext') {
      await store.fetchAggregatesForBC(nodeId)
      // Auto-layout after data is loaded
      setTimeout(() => {
        fitView({ padding: 0.2 })
      }, 100)
    }
  } catch (error) {
    console.error('Failed to handle drop:', error)
  }
}

// Store BC container positions in localStorage
const STORAGE_KEY = 'aggregateViewer_bcPositions'

function loadBcPositions() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : {}
  } catch {
    return {}
  }
}

function saveBcPosition(containerId, position) {
  try {
    const positions = loadBcPositions()
    positions[containerId] = position
    localStorage.setItem(STORAGE_KEY, JSON.stringify(positions))
  } catch (e) {
    console.warn('Failed to save BC position:', e)
  }
}

// Helper function to build nodes from store data
function buildNodes(preserveExistingPositions = false) {
  const result = []
  let x = 100
  const startY = 50
  const xSpacing = 650  // Horizontal spacing between Aggregate containers
  const ySpacing = 100  // Vertical spacing between Aggregate containers
  
  // Load saved BC positions
  const savedPositions = loadBcPositions()
  
  // If preserving positions, also check current nodes
  const currentPositions = preserveExistingPositions 
    ? new Map(nodes.value.map(n => [n.id, n.position]))
    : new Map()
  
  // Node dimensions
  const aggregateBaseWidth = 280
  const aggregateBaseHeight = 200
  const enumVoWidth = 220
  const enumVoHeight = 80
  const containerPadding = 20  // Padding inside container
  const containerHeaderHeight = 50  // BC name header height
  const nodePadding = 20  // Padding between nodes inside container
  
  // Calculate Aggregate height including properties
  function calculateAggregateHeight(agg) {
    const propsCount = (agg.properties || []).length
    const enumsCount = (agg.enumerations || []).length
    const vosCount = (agg.valueObjects || []).length
    const fieldsCount = propsCount + enumsCount + vosCount
    
    // Base height + header + fields
    const baseHeight = 120  // Header + name + rootEntity
    const fieldHeight = 24  // Per field row
    const sectionPadding = 20  // Section dividers
    
    let height = baseHeight
    if (fieldsCount > 0) {
      height += sectionPadding + (fieldsCount * fieldHeight)
    }
    
    return Math.max(aggregateBaseHeight, height)
  }

  // Calculate container dimensions based on content
  function calculateContainerSize(agg) {
    const aggHeight = calculateAggregateHeight(agg)
    
    // Calculate Enum/VO total height
    let enumVoTotalHeight = 0
    agg.enumerations?.forEach((enumItem) => {
      const itemsCount = (enumItem.items || []).length
      const enumNodeHeight = itemsCount > 0 
        ? Math.max(enumVoHeight, 80 + (itemsCount * 24) + 20) 
        : enumVoHeight
      enumVoTotalHeight += enumNodeHeight + nodePadding
    })
    agg.valueObjects?.forEach((vo) => {
      const fieldsCount = (vo.fields || []).length
      const voNodeHeight = fieldsCount > 0
        ? Math.max(enumVoHeight, 80 + (fieldsCount * 24) + 20)
        : enumVoHeight
      enumVoTotalHeight += voNodeHeight + nodePadding
    })
    if (enumVoTotalHeight > 0) {
      enumVoTotalHeight -= nodePadding  // Remove last padding
    }
    
    // Container width: Aggregate + padding + Enum/VO + padding
    const containerWidth = aggregateBaseWidth + containerPadding + enumVoWidth + containerPadding
    // Container height: header + max(Aggregate height, Enum/VO height) + padding
    const containerHeight = containerHeaderHeight + Math.max(aggHeight, enumVoTotalHeight) + containerPadding * 2
    
    return { width: containerWidth, height: containerHeight }
  }

  // Flatten all aggregates from all BCs
  const allAggregates = []
  store.filteredBoundedContexts.forEach((bc) => {
    bc.aggregates?.forEach((agg) => {
      allAggregates.push({ ...agg, bcName: bc.name, bcId: bc.id })
    })
  })

  // Layout aggregates in a grid (2 columns)
  let currentX = x
  let currentY = startY
  const columnsPerRow = 2  // Number of containers per row
  let rowMaxHeight = 0
  
  allAggregates.forEach((agg, aggIdx) => {
    const containerSize = calculateContainerSize(agg)
    const containerId = `agg-container-${agg.id}`
    
    // Check if we need to wrap to next row
    if (aggIdx > 0 && aggIdx % columnsPerRow === 0) {
      currentX = x
      currentY += rowMaxHeight + ySpacing
      rowMaxHeight = 0
    }
    
    // Track max height in current row
    rowMaxHeight = Math.max(rowMaxHeight, containerSize.height)
    
    // Priority: 1) current position (if preserving), 2) saved position, 3) calculated position
    const currentPos = currentPositions.get(containerId)
    const savedPos = savedPositions[containerId]
    const containerPosition = currentPos
      ? { x: currentPos.x, y: currentPos.y }
      : (savedPos 
        ? { x: savedPos.x, y: savedPos.y }
        : { x: currentX, y: currentY })
    
    // Create Aggregate container node
    result.push({
      id: containerId,
      type: 'aggregateContainer',
      position: containerPosition,
      data: {
        bcName: agg.bcName,
        aggregateId: agg.id,
        aggregateName: agg.name,
      },
      style: {
        width: `${containerSize.width}px`,
        height: `${containerSize.height}px`,
      },
      draggable: true,
      selectable: false,
    })
    
    // Calculate positions relative to container (inside container)
    const containerInnerX = containerPadding
    const containerInnerY = containerHeaderHeight + containerPadding
    const aggX = containerInnerX
    const aggY = containerInnerY
    
    // Aggregate node (left side) - Aggregate Root
    result.push({
      id: `agg-${agg.id}`,
      type: 'aggregateViewer',
      position: { x: aggX, y: aggY },
      data: {
        ...agg,
        bcName: agg.bcName,
        type: 'Aggregate',
      },
      parentNode: containerId,
      extent: 'parent',
    })
    
    // Enum/VO nodes (right side)
    const enumVoX = aggX + aggregateBaseWidth + nodePadding
    let enumVoY = containerInnerY
    
    // Enumerations (top right)
    agg.enumerations?.forEach((enumItem, enumIdx) => {
      const itemsCount = (enumItem.items || []).length
      const enumNodeHeight = itemsCount > 0 
        ? Math.max(enumVoHeight, 80 + (itemsCount * 24) + 20) 
        : enumVoHeight
      
      result.push({
        id: `enum-${agg.id}-${enumIdx}`,
        type: 'enumViewer',
        position: { x: enumVoX, y: enumVoY },
        data: {
          ...enumItem,
          aggregateId: agg.id,
          aggregateName: agg.name,
          type: 'Enumeration',
          index: enumIdx,
        },
        parentNode: containerId,
        extent: 'parent',
      })
      enumVoY += enumNodeHeight + nodePadding
    })
    
    // Value Objects (bottom right, below enumerations)
    agg.valueObjects?.forEach((vo, voIdx) => {
      const fieldsCount = (vo.fields || []).length
      const voNodeHeight = fieldsCount > 0
        ? Math.max(enumVoHeight, 80 + (fieldsCount * 24) + 20)
        : enumVoHeight
      
      result.push({
        id: `vo-${agg.id}-${voIdx}`,
        type: 'valueObjectViewer',
        position: { x: enumVoX, y: enumVoY },
        data: {
          ...vo,
          aggregateId: agg.id,
          aggregateName: agg.name,
          type: 'ValueObject',
          index: voIdx,
        },
        parentNode: containerId,
        extent: 'parent',
      })
      enumVoY += voNodeHeight + nodePadding
    })
    
    // Move to next position
    currentX += containerSize.width + xSpacing
  })

  return result
}

// Convert store data to Vue Flow nodes (use ref for stable references)
const nodes = ref([])

// Create edges from Aggregate to Enum/VO (use ref for manual updates)
// Must be defined before watch that calls updateEdges()
const edges = ref([])
// Edge version counter to force Vue Flow to recognize edge updates
const edgeVersion = ref(0)

// Debug flag - set to false to disable verbose logging
const DEBUG_EDGES = true // Temporarily enable to debug handle issues

// Update edges when store data or node positions change
// Must be defined before watch that calls it
function updateEdges() {
  // Increment edge version to force Vue Flow to treat edges as completely new
  edgeVersion.value++
  
  // Force Vue Flow to recognize handle changes by completely replacing the edges array
  // Clear edges first to ensure Vue Flow removes all old edges
  edges.value = []
  
  // Wait for Vue Flow to process the removal, then add new edges
  // Use multiple nextTick calls and setTimeout to ensure Vue Flow has fully processed
  nextTick(() => {
    setTimeout(() => {
      nextTick(() => {
        // Wait for Vue Flow to fully render nodes and their handles
        // CRITICAL: buildEdges() must be called AFTER handles are rendered in DOM
        setTimeout(() => {
          // Build edges now that handles are rendered
          const newEdges = buildEdges()
          
          // Create completely new edge objects with versioned IDs to force Vue Flow to recreate them
          // Store original ID in data for hover/selection logic
          edges.value = newEdges.map(edge => {
            const originalId = edge.id
            const versionedId = `${originalId}-v${edgeVersion.value}`
            
            // CRITICAL: Include sourcePosition/targetPosition for smoothstep routing
            // Create a completely new object (not just a spread)
            // IMPORTANT: Vue Flow requires handle IDs and positions to match exactly what's defined in the node component
            const newEdge = {
              id: versionedId,
              source: edge.source,
              target: edge.target,
              type: edge.type,
              animated: edge.animated,
              style: { ...edge.style },
              markerEnd: { ...edge.markerEnd },
              // CRITICAL: sourcePosition/targetPosition are required for smoothstep to route correctly
              sourceHandle: edge.sourceHandle || undefined,
              sourcePosition: edge.sourcePosition || undefined,
              targetHandle: edge.targetHandle || undefined,
              targetPosition: edge.targetPosition || undefined,
              data: {
                ...(edge.data || {}),
                originalId: originalId, // Store original ID for hover/selection
              }
            }
            // Add optional properties if they exist
            if (edge.label) newEdge.label = edge.label
            if (edge.labelStyle) newEdge.labelStyle = { ...edge.labelStyle }
            return newEdge
          })
          
          // Force Vue Flow to recalculate edge paths
          // Vue Flow's smoothstep edge type should automatically use sourceHandle and targetHandle
          // But we need to ensure edges are recreated to pick up handle changes
          setTimeout(() => {
            // Force Vue Flow to update edges by removing and re-adding them
            // This ensures Vue Flow picks up the handle IDs
            const edgesCopy = edges.value.map(e => ({ ...e }))
            edges.value = []
            nextTick(() => {
              edges.value = edgesCopy
            })
          }, 200)
        }, 500) // Wait 500ms for Vue Flow to fully render nodes and handles (increased for handle registration)
      })
    }, 100) // Wait 100ms for Vue Flow to process edge removal
  })
}

// Track BC IDs to detect when BCs are actually added/removed (not just data changes)
const previousBcIds = ref(new Set())
const isRebuilding = ref(false) // Flag to prevent position reset during rebuild

// Update nodes when store data changes - ONLY when BC structure changes
watch(() => store.filteredBoundedContexts, (newBcs) => {
  // Extract BC IDs from new data
  const newBcIds = new Set(newBcs.map(bc => bc.id))
  
  // Check if BCs were actually added/removed (not just data updated)
  const bcAdded = Array.from(newBcIds).some(id => !previousBcIds.value.has(id))
  const bcRemoved = Array.from(previousBcIds.value).some(id => !newBcIds.has(id))
  const bcStructureChanged = bcAdded || bcRemoved
  
  // If BC structure hasn't changed, don't rebuild - just return
  if (!bcStructureChanged && previousBcIds.value.size > 0) {
    return
  }
  
  // Update previous BC IDs
  previousBcIds.value = newBcIds
  
  // Set rebuilding flag
  isRebuilding.value = true
  
  // Before rebuilding, capture current positions from Vue Flow (if available)
  let currentVueFlowPositions = new Map()
  try {
    const vueFlowNodes = getNodes()
    vueFlowNodes.forEach(node => {
      if (node.type === 'aggregateContainer' && node.position) {
        currentVueFlowPositions.set(node.id, { x: node.position.x, y: node.position.y })
        // Save to localStorage immediately
        saveBcPosition(node.id, { x: node.position.x, y: node.position.y })
      }
    })
  } catch (e) {
    // Vue Flow not ready yet, use nodes.value as fallback
    nodes.value.forEach(node => {
      if (node.type === 'aggregateContainer' && node.position) {
        currentVueFlowPositions.set(node.id, { x: node.position.x, y: node.position.y })
        saveBcPosition(node.id, { x: node.position.x, y: node.position.y })
      }
    })
  }
  
  // Preserve existing node positions when rebuilding
  // Pass current positions so buildNodes can use them
  const newNodes = buildNodes(true)
  
  // Apply current Vue Flow positions to new nodes (if they exist)
  // This ensures positions are preserved even if watch triggers
  newNodes.forEach(node => {
    if (node.type === 'aggregateContainer') {
      const currentPos = currentVueFlowPositions.get(node.id)
      if (currentPos) {
        node.position = { x: currentPos.x, y: currentPos.y }
      }
    }
  })
  
  nodes.value = newNodes
  
  // Initialize node positions for new nodes
  nodes.value.forEach(node => {
    if (!nodePositions.value.has(node.id)) {
      nodePositions.value.set(node.id, {
        x: node.position.x,
        y: node.position.y,
        parentNode: node.parentNode
      })
    }
  })
  
  // Clear rebuilding flag after a short delay
  setTimeout(() => {
    isRebuilding.value = false
  }, 100)
  
  // Don't update edges here - wait for onNodesInitialized event
  // This ensures Vue Flow has registered all handles before creating edges
  // Fit view after nodes are created (only if no existing nodes or BC structure changed)
  if (currentVueFlowPositions.size === 0 || bcStructureChanged) {
    setTimeout(() => {
      fitView({ padding: 0.2 })
    }, 200)
  }
}, { immediate: true, deep: false }) // deep: false to prevent unnecessary triggers


// Get connected node IDs for a given node (direct connections only)
const getConnectedNodeIds = (nodeId) => {
  const connectedNodes = new Set([nodeId])
  const connectedEdges = edges.value.filter(edge => 
    edge.source === nodeId || edge.target === nodeId
  )
  connectedEdges.forEach(edge => {
    if (edge.source === nodeId) connectedNodes.add(edge.target)
    if (edge.target === nodeId) connectedNodes.add(edge.source)
  })
  return connectedNodes
}

// Get connected edge IDs for a given node
const getConnectedEdgeIds = (nodeId) => {
  return edges.value
    .filter(edge => edge.source === nodeId || edge.target === nodeId)
    .map(edge => edge.id)
}

// Nodes with hover highlighting
const nodesWithHighlight = computed(() => {
  const connectedNodeIds = hoveredNodeId.value 
    ? getConnectedNodeIds(hoveredNodeId.value)
    : new Set()
  const edgeConnectedNodeIds = hoveredEdgeId.value
    ? new Set([edges.value.find(e => e.id === hoveredEdgeId.value)?.source, 
                edges.value.find(e => e.id === hoveredEdgeId.value)?.target].filter(Boolean))
    : new Set()
  
  return nodes.value.map(node => {
    const isConnected = connectedNodeIds.has(node.id) || edgeConnectedNodeIds.has(node.id)
    
    return {
      ...node,
      class: [
        node.class || '',
        (hoveredNodeId.value === node.id || isConnected) ? 'aggregate-node--highlighted' : '',
        hoveredNodeId.value && !isConnected && hoveredNodeId.value !== node.id ? 'aggregate-node--dimmed' : ''
      ].filter(Boolean).join(' ')
    }
  })
})

// Edges with hover highlighting
const edgesWithHighlight = computed(() => {
  const connectedEdgeIds = hoveredNodeId.value
    ? getConnectedEdgeIds(hoveredNodeId.value)
    : []
  
  return edges.value.map(edge => {
    const isConnected = connectedEdgeIds.includes(edge.id)
    const isHovered = hoveredEdgeId.value === edge.id
    
    return {
      ...edge,
      class: [
        isHovered || isConnected ? 'aggregate-edge--highlighted' : '',
        hoveredNodeId.value && !isConnected && !isHovered ? 'aggregate-edge--dimmed' : ''
      ].filter(Boolean).join(' '),
      style: {
        ...edge.style,
        zIndex: isHovered || isConnected ? 1000 : (hoveredNodeId.value && !isConnected && !isHovered ? 1 : undefined)
      }
    }
  })
})

// Helper function to get node's absolute X position (considering parent container)
// Uses Vue Flow's actual node positions for real-time accuracy
function getNodeAbsoluteX(nodeId, nodesList = null) {
  // Prefer Vue Flow's actual nodes if available (most up-to-date)
  let nodesToSearch = nodesList
  if (!nodesToSearch) {
    try {
      // Try to get actual nodes from Vue Flow first
      const vueFlowNodes = getNodes()
      if (vueFlowNodes && vueFlowNodes.length > 0) {
        nodesToSearch = vueFlowNodes
      } else {
        // Fallback to our tracked nodes
        nodesToSearch = nodes.value
      }
    } catch (e) {
      // Vue Flow not ready yet, use our tracked nodes
      nodesToSearch = nodes.value
    }
  }
  
  const node = nodesToSearch.find(n => n.id === nodeId)
  if (!node) {
    console.warn('[AggregatePanel] getNodeAbsoluteX: Node not found', nodeId)
    return null
  }
  
  let x = node.position?.x || 0
  // If node has a parent, add parent's position
  if (node.parentNode) {
    const parent = nodesToSearch.find(n => n.id === node.parentNode)
    if (parent) {
      const parentX = parent.position?.x || 0
      x += parentX
      // Debug log for parent position calculation
      if (nodeId.includes('vo-') || nodeId.includes('enum-')) {
        // Debug log removed - too verbose
      }
    }
  }
  return x
}

// Helper function to get node center X in screen coordinates
function getNodeCenterX(nodeId) {
  const el = document.querySelector(`[data-id="${nodeId}"]`)
  if (!el) return null
  const r = el.getBoundingClientRect()
  return r.left + r.width / 2
}

// Normalize position string to Vue Flow format
function normalizePos(v) {
  const s = String(v || '').toLowerCase()
  if (s.includes('left')) return 'left'
  if (s.includes('right')) return 'right'
  if (s.includes('top')) return 'top'
  if (s.includes('bottom')) return 'bottom'
  return 'right' // fallback
}

// Helper function to get all available handles for a node (including field handles)
// Returns handles with their screen coordinates (for distance comparison)
// CRITICAL: Vue Flow stores handle IDs in data-handleid attribute, not id attribute
function getAllHandlesForNode(nodeId) {
  const nodeEl = document.querySelector(`[data-id="${nodeId}"]`)
  if (!nodeEl) {
    if (DEBUG_EDGES) console.warn('[getAllHandlesForNode] Node element not found in DOM:', nodeId)
    return []
  }
  
  // Get all handle elements with data-handleid attribute
  // Vue Flow uses data-handleid, not id attribute
  const handleEls = Array.from(nodeEl.querySelectorAll('.vue-flow__handle[data-handleid]'))
  
  if (handleEls.length === 0) {
    if (DEBUG_EDGES) console.warn('[getAllHandlesForNode] No handles found for node:', nodeId)
    return []
  }
  
  return handleEls
    .map((el) => {
      // CRITICAL: Use data-handleid, not id attribute
      const handleId = el.getAttribute('data-handleid')
      if (!handleId) {
        if (DEBUG_EDGES) console.warn('[getAllHandlesForNode] Handle without data-handleid found:', el)
        return null
      }
      
      // Get handle position in screen coordinates
      // For distance comparison, screen coordinates work fine (same coordinate system)
      const r = el.getBoundingClientRect()
      return {
        id: handleId,
        // Screen coordinates - fine for distance comparison
        x: r.left + r.width / 2,
        y: r.top + r.height / 2,
        // Normalized position for Vue Flow
        pos: normalizePos(el.getAttribute('data-handlepos')),
        type: el.getAttribute('data-handle-type') || 'unknown',
      }
    })
    .filter(Boolean)
}

// Convert position to Vue Flow format
function toVuePos(p) {
  // Vue Flow expects lowercase position strings
  if (p === 'left') return 'left'
  if (p === 'right') return 'right'
  if (p === 'top') return 'top'
  if (p === 'bottom') return 'bottom'
  return 'right' // fallback
}

// Helper function to determine optimal handles based on actual handle positions
// Rules:
// - Source: only general handles (left-source, right-source) - never field handles
// - Target: field handle if specified, otherwise general handles (left-target, right-target)
// - Use screen coordinates for distance comparison (same coordinate system)
// - Returns handle IDs AND positions for smoothstep routing
function getOptimalHandles(sourceId, targetId, options = {}) {
  const { targetFieldHandle = null } = options
  
  // Get all available handles for both nodes
  const srcAll = getAllHandlesForNode(sourceId)
  const tgtAll = getAllHandlesForNode(targetId)
  
  // Source: only general source handles
  const src = srcAll.filter(h => h.id === 'left-source' || h.id === 'right-source')
  
  // Target: field handle if specified, otherwise general target handles
  let tgt = []
  if (targetFieldHandle) {
    // Use specific field handle if provided
    tgt = tgtAll.filter(h => h.id === targetFieldHandle)
    if (tgt.length === 0) {
      // Fallback: general target handles if field handle not found
      if (DEBUG_EDGES) {
        console.warn('[getOptimalHandles] Field handle not found, falling back to general handles:', {
          targetFieldHandle,
          availableHandles: tgtAll.map(h => h.id)
        })
      }
      tgt = tgtAll.filter(h => h.id === 'left-target' || h.id === 'right-target')
    }
  } else {
    // Use only general target handles
    tgt = tgtAll.filter(h => h.id === 'left-target' || h.id === 'right-target')
  }
  
  // Fallback if no handles found
  if (!src.length || !tgt.length) {
    if (DEBUG_EDGES) {
      console.warn('[getOptimalHandles] No handles found, using defaults:', {
        sourceId,
        targetId,
        sourceHandles: src.length,
        targetHandles: tgt.length,
        allSourceHandles: srcAll.map(h => h.id),
        allTargetHandles: tgtAll.map(h => h.id)
      })
    }
    return {
      sourceHandle: 'right-source',
      sourcePosition: 'right',
      targetHandle: targetFieldHandle || 'left-target',
      targetPosition: 'left',
    }
  }
  
  // Find the closest handle pair using screen coordinates
  // Store full handle objects, not just IDs
  let best = { d: Infinity, s: src[0], t: tgt[0] }
  for (const s of src) {
    for (const t of tgt) {
      const dx = t.x - s.x
      const dy = t.y - s.y
      const d = dx * dx + dy * dy // Squared distance (no need for sqrt for comparison)
      if (d < best.d) {
        best = { d, s, t }
      }
    }
  }
  
  return {
    sourceHandle: best.s.id,
    sourcePosition: toVuePos(best.s.pos),
    targetHandle: best.t.id,
    targetPosition: toVuePos(best.t.pos),
  }
}

// Helper function to build edges from Aggregate to Enum/VO
function buildEdges() {
  const result = []
  // Use Vue Flow's actual nodes for most up-to-date positions
  let nodesList = nodes.value
  try {
    const vueFlowNodes = getNodes()
    if (vueFlowNodes && vueFlowNodes.length > 0) {
      nodesList = vueFlowNodes
    }
  } catch (e) {
    // Vue Flow not ready, using tracked nodes
  }
  
  store.filteredBoundedContexts.forEach((bc) => {
    bc.aggregates?.forEach((agg) => {
      // Connect Aggregate to Enumerations
      agg.enumerations?.forEach((_, enumIdx) => {
        // Determine optimal handles based on positions FIRST
        const handles = getOptimalHandles(`agg-${agg.id}`, `enum-${agg.id}-${enumIdx}`)
        
        const edge = {
          id: `edge-agg-${agg.id}-enum-${enumIdx}`,
          source: `agg-${agg.id}`,
          target: `enum-${agg.id}-${enumIdx}`,
          type: 'smoothstep',
          animated: false,
          style: { 
            stroke: '#909296', 
            strokeWidth: 1.5,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: '#909296',
          },
          // Specify handles and positions based on node positions for shortest path
          // CRITICAL: sourcePosition/targetPosition are required for smoothstep to route correctly
          sourceHandle: handles.sourceHandle,
          sourcePosition: handles.sourcePosition,
          targetHandle: handles.targetHandle,
          targetPosition: handles.targetPosition,
        }
        
        result.push(edge)
      })

      // Connect Aggregate to Value Objects
      agg.valueObjects?.forEach((_, voIdx) => {
        // Determine optimal handles based on positions
        const handles = getOptimalHandles(`agg-${agg.id}`, `vo-${agg.id}-${voIdx}`)
        
        const edge = {
          id: `edge-agg-${agg.id}-vo-${voIdx}`,
          source: `agg-${agg.id}`,
          target: `vo-${agg.id}-${voIdx}`,
          type: 'smoothstep',
          animated: false,
          style: { 
            stroke: '#909296', 
            strokeWidth: 1.5,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: '#909296',
          },
          // Specify handles and positions based on node positions for shortest path
          // CRITICAL: sourcePosition/targetPosition are required for smoothstep to route correctly
          sourceHandle: handles.sourceHandle,
          sourcePosition: handles.sourcePosition,
          targetHandle: handles.targetHandle,
          targetPosition: handles.targetPosition,
        }
        
        result.push(edge)
      })

      // Connect Value Objects to referenced Aggregates
      agg.valueObjects?.forEach((vo, voIdx) => {
        if (vo.referencedAggregateName) {
          // Find the referenced aggregate
          const refAgg = store.filteredBoundedContexts
            .flatMap(bc => bc.aggregates || [])
            .find(a => a.name === vo.referencedAggregateName)
          
          if (refAgg) {
            // Build label with field reference if available
            let labelText = 'references'
            if (vo.referencedAggregateField) {
              labelText = `→ ${vo.referencedAggregateField}`
            }
            
            // Build edge object
            const edge = {
              id: `edge-vo-${agg.id}-${voIdx}-ref-${refAgg.id}`,
              source: `vo-${agg.id}-${voIdx}`,
              target: `agg-${refAgg.id}`,
              type: 'smoothstep',
              animated: true,
              style: { 
                stroke: '#5c7cfa', 
                strokeWidth: 2, 
                strokeDasharray: '5,5',
              },
              markerEnd: {
                type: MarkerType.ArrowClosed,
                color: '#5c7cfa',
              },
              label: labelText,
              labelStyle: { fill: '#5c7cfa', fontWeight: 500 },
              data: {
                referencedField: vo.referencedAggregateField || null,
                referencedAggregateName: vo.referencedAggregateName,
              },
            }
            
            // If we have a specific field reference, use that field's handle
            if (vo.referencedAggregateField && refAgg.properties) {
              // Try to find property by name (case-insensitive for robustness)
              const targetProp = refAgg.properties.find(
                p => p.name && p.name.toLowerCase() === vo.referencedAggregateField.toLowerCase()
              )
              if (targetProp) {
                // Determine field handle ID - choose left or right target based on source/target positions
                const fieldBase = targetProp.id 
                  ? `field-${String(targetProp.id)}`
                  : (targetProp.name ? `field-${String(targetProp.name)}` : null)
                
                if (!fieldBase) {
                  // Fallback to general handles if field base ID cannot be determined
                  const handles = getOptimalHandles(`vo-${agg.id}-${voIdx}`, `agg-${refAgg.id}`)
                  edge.sourceHandle = handles.sourceHandle
                  edge.sourcePosition = handles.sourcePosition
                  edge.targetHandle = handles.targetHandle
                  edge.targetPosition = handles.targetPosition
                } else {
                  // Determine which side target handle to use based on source/target node positions
                  const sourceX = getNodeCenterX(`vo-${agg.id}-${voIdx}`)
                  const targetX = getNodeCenterX(`agg-${refAgg.id}`)
                  
                  // If source is to the right of target, use right target handle for direct connection
                  // Otherwise use left target handle
                  const fieldHandleId = (sourceX !== null && targetX !== null && sourceX > targetX)
                    ? `${fieldBase}-target-right`
                    : `${fieldBase}-target-left`
                  
                  // Use getOptimalHandles with field handle option
                  // This will find the closest general handle on VO (left-source or right-source)
                  // and the specified field handle on Aggregate
                  const handles = getOptimalHandles(
                    `vo-${agg.id}-${voIdx}`, 
                    `agg-${refAgg.id}`, 
                    { targetFieldHandle: fieldHandleId }
                  )
                  edge.sourceHandle = handles.sourceHandle
                  edge.sourcePosition = handles.sourcePosition
                  edge.targetHandle = handles.targetHandle
                  edge.targetPosition = handles.targetPosition
                  
                  // Store field handle ID in edge data for reroute
                  edge.data.targetFieldHandle = fieldHandleId
                }
              } else {
                // Field not found by name, use position-based handles
                const handles = getOptimalHandles(`vo-${agg.id}-${voIdx}`, `agg-${refAgg.id}`)
                edge.sourceHandle = handles.sourceHandle
                edge.sourcePosition = handles.sourcePosition
                edge.targetHandle = handles.targetHandle
                edge.targetPosition = handles.targetPosition
              }
            } else {
              // No field reference, use position-based handles (Aggregate node's general handles)
              const handles = getOptimalHandles(`vo-${agg.id}-${voIdx}`, `agg-${refAgg.id}`)
              edge.sourceHandle = handles.sourceHandle
              edge.sourcePosition = handles.sourcePosition
              edge.targetHandle = handles.targetHandle
              edge.targetPosition = handles.targetPosition
            }
            
            result.push(edge)
          }
        }
      })
    })
  })
  return result
}


// Node types
const nodeTypes = {
  aggregateViewer: markRaw(AggregateViewerNode),
  enumViewer: markRaw(EnumViewerNode),
  valueObjectViewer: markRaw(ValueObjectViewerNode),
  aggregateContainer: markRaw(AggregateContainerNode),
}

// Edge types - use straight/step for shortest path routing
// Same BC connections: step (clean right-angle routing)
// Cross-aggregate connections: straight (direct shortest path)
const edgeTypes = {
  straight: markRaw(StraightEdge),
  step: markRaw(StepEdge),
}

// Node click handler (single click - no action)
// Panel management
function toggleChatPanel() {
  panelMode.value = panelMode.value === 'chat' ? 'none' : 'chat'
}

function startResizeChat(e) {
  isResizingChat.value = true
  document.addEventListener('mousemove', onResizeChat)
  document.addEventListener('mouseup', stopResizeChat)
}

function onResizeChat(e) {
  if (!isResizingChat.value) return
  const next = window.innerWidth - e.clientX
  chatPanelWidth.value = Math.max(280, Math.min(640, next))
  try {
    localStorage.setItem('aggregate_chat_panel_width', String(chatPanelWidth.value))
  } catch {}
}

function stopResizeChat() {
  isResizingChat.value = false
  document.removeEventListener('mousemove', onResizeChat)
  document.removeEventListener('mouseup', stopResizeChat)
}

function onNodeClick(event) {
  const node = event.node
  if (!node) return
  
  // Update Model Modifier with selected node
  const nodeData = node.data || {}
  const selectedNode = {
    id: node.id,
    name: nodeData.name || node.id,
    type: node.type === 'aggregateViewer' ? 'Aggregate' : 
         node.type === 'enumViewer' ? 'Enum' : 
         node.type === 'valueObjectViewer' ? 'ValueObject' : node.type,
    bcId: nodeData.bcId,
    bcName: nodeData.bcName,
    aggregateId: nodeData.aggregateId,
    aggregateName: nodeData.aggregateName,
    rootEntity: nodeData.rootEntity,
    ...nodeData
  }
  chatStore.setSelectedNodes([selectedNode])
  // Single click does nothing - use double click to open inspector
}

// Node double click handler
function onNodeDoubleClick(event) {
  const node = event.node
  // Don't open inspector for container nodes
  if (node.type === 'aggregateContainer') {
    return
  }
  if (node.type === 'aggregateViewer') {
    inspectingAggregateId.value = node.data.id
    inspectingEnumIndex.value = null
    inspectingVoIndex.value = null
    panelMode.value = 'inspector'
  } else if (node.type === 'enumViewer') {
    inspectingAggregateId.value = node.data.aggregateId
    inspectingEnumIndex.value = node.data.index
    inspectingVoIndex.value = null
    panelMode.value = 'inspector'
  } else if (node.type === 'valueObjectViewer') {
    inspectingAggregateId.value = node.data.aggregateId
    inspectingEnumIndex.value = null
    inspectingVoIndex.value = node.data.index
    panelMode.value = 'inspector'
  }
}

// Node hover handlers
function onNodeMouseEnter(event) {
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

// Handle nodes initialization - called when Vue Flow has registered all handles
function onNodesInitialized() {
  // Wait a bit more to ensure handles are fully registered
  setTimeout(() => {
    // Update edges now that handles are registered
    updateEdges()
  }, 500) // Increased delay to ensure DOM is ready
}

// Handle node position changes - only update position, not edges
function onNodesChange(changes) {
  // Skip if we're rebuilding (to prevent position reset)
  if (isRebuilding.value) {
    return
  }
  
  changes.forEach(change => {
    if (change.type === 'position') {
      const node = change.node
      if (node) {
        // Update node position in nodes array
        const nodeIndex = nodes.value.findIndex(n => n.id === node.id)
        if (nodeIndex >= 0) {
          nodes.value[nodeIndex] = {
            ...nodes.value[nodeIndex],
            position: { x: node.position.x, y: node.position.y }
          }
        }
        
        // Save BC container positions to localStorage immediately
        if (node.type === 'aggregateContainer') {
          saveBcPosition(node.id, { x: node.position.x, y: node.position.y })
        }
      }
    }
  })
}

// Handle node drag stop - update edges when drag ends
function onNodeDragStop(e) {
  const node = e.node
  if (!node) return
  
  // Skip if we're rebuilding
  if (isRebuilding.value) {
    return
  }
  
  if (node.type === 'aggregateContainer') {
    // Container drag: include all child nodes for reroute
    const childIds = nodes.value
      .filter(n => n.parentNode === node.id)
      .map(n => n.id)
    
    rerouteEdgesForMovedNodes([node.id, ...childIds])
  } else {
    // Regular node drag
    rerouteEdgesForMovedNodes([node.id])
  }
}

// Recompute field handle left/right based on current node positions
function recomputeFieldHandle(edge) {
  const th = edge.data?.targetFieldHandle
  if (!th) return null
  
  // field-xxx-target-left/right 형태라면 base 추출
  const match = th.match(/^(.+)-target-(left|right)$/)
  if (!match) return th
  
  const base = match[1]
  const sourceX = getNodeCenterX(edge.source)
  const targetX = getNodeCenterX(edge.target)
  
  if (sourceX == null || targetX == null) return th
  
  // Source가 target보다 오른쪽에 있으면 right, 왼쪽에 있으면 left
  const side = sourceX > targetX ? 'right' : 'left'
  return `${base}-target-${side}`
}

// Update edges for moved nodes - only recalculate handles for affected edges
function rerouteEdgesForMovedNodes(movedNodeIds) {
  // Wait for DOM to update with new positions
  nextTick(() => {
    setTimeout(() => {
      const updatedEdges = edges.value.map(edge => {
        // Only update edges connected to moved nodes
        const touchesMoved = movedNodeIds.includes(edge.source) || movedNodeIds.includes(edge.target)
        if (!touchesMoved) return edge
        
        // Recompute field handle left/right if it exists
        const nextFieldHandle = recomputeFieldHandle(edge)
        
        // Recalculate optimal handles for this edge
        const handles = getOptimalHandles(edge.source, edge.target, {
          targetFieldHandle: nextFieldHandle
        })
        
        // Only update if handles or positions changed
        if (edge.sourceHandle !== handles.sourceHandle || 
            edge.targetHandle !== handles.targetHandle ||
            edge.sourcePosition !== handles.sourcePosition ||
            edge.targetPosition !== handles.targetPosition) {
          
          return {
            ...edge,
            sourceHandle: handles.sourceHandle,
            sourcePosition: handles.sourcePosition,
            targetHandle: handles.targetHandle,
            targetPosition: handles.targetPosition,
            data: {
              ...edge.data,
              targetFieldHandle: nextFieldHandle // Update field handle if recomputed
            }
          }
        }
        
        return edge
      })
      
      // Update edges array
      edges.value = updatedEdges
    }, 50) // Small delay to ensure DOM is updated
  })
}

// Pane click handler
function onPaneClick() {
  // Clear selection when clicking on empty canvas
  chatStore.clearSelection()
  panelMode.value = 'none'
  inspectingAggregateId.value = null
  inspectingEnumIndex.value = null
  inspectingVoIndex.value = null
  hoveredNodeId.value = null
  hoveredEdgeId.value = null
}

// Inspector panel resize
function startResizeInspector(e) {
  isResizingInspector.value = true
  e.preventDefault()
  document.addEventListener('mousemove', onResizeInspector)
  document.addEventListener('mouseup', stopResizeInspector)
}

function onResizeInspector(e) {
  if (!isResizingInspector.value) return
  const next = Math.round(e.clientX - window.innerWidth + inspectorPanelWidth.value)
  inspectorPanelWidth.value = Math.max(300, Math.min(600, next))
  try {
    localStorage.setItem('aggregate_viewer_inspector_width', String(inspectorPanelWidth.value))
  } catch {}
}

function stopResizeInspector() {
  isResizingInspector.value = false
  document.removeEventListener('mousemove', onResizeInspector)
  document.removeEventListener('mouseup', stopResizeInspector)
}

// Load saved inspector width
onMounted(() => {
  try {
    const saved = localStorage.getItem('aggregate_viewer_inspector_width')
    if (saved) {
      inspectorPanelWidth.value = parseInt(saved, 10)
    }
  } catch {}
})

// MiniMap node color
function getNodeColor(node) {
  const colors = {
    aggregateViewer: '#fcc419',
    enumViewer: '#fff9e6',
    valueObjectViewer: '#fff9e6',
    aggregateContainer: '#373a40',
  }
  return colors[node.type] || '#909296'
}
</script>

<template>
  <div class="aggregate-viewer">
    <div class="aggregate-main-content">
      <!-- Loading state -->
      <div v-if="store.loading" class="aggregate-viewer__loading">
        <div class="loading-spinner"></div>
        <div class="loading-text">Loading aggregates...</div>
      </div>

      <!-- Error state -->
      <div v-else-if="store.error" class="aggregate-viewer__error">
        <div class="error-icon">⚠️</div>
        <div class="error-text">{{ store.error }}</div>
        <button class="error-retry" @click="store.fetchAllAggregates">Retry</button>
      </div>

      <!-- Main viewer -->
      <div v-else class="aggregate-viewer__content">
      <div 
        class="aggregate-viewer__canvas" 
        :class="{ 'drop-zone-active': isDragOver }"
        @drop="handleDrop"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
      >
        <div v-if="nodes.length === 0" class="aggregate-viewer__empty">
          <div class="empty-icon">📦</div>
          <div class="empty-text">No aggregates selected</div>
          <div class="empty-hint">Drag a Bounded Context from the navigator to view its aggregates</div>
        </div>

        <VueFlow
          v-else
          :nodes="nodes"
          :edges="edgesWithHighlight"
          :node-types="nodeTypes"
          :connection-radius="40"
          connection-mode="loose"
          :edge-types="edgeTypes"
          :default-viewport="{ zoom: 0.8, x: 50, y: 50 }"
          @nodes-initialized="onNodesInitialized"
          :min-zoom="0.2"
          :max-zoom="2"
          :snap-to-grid="true"
          :snap-grid="[10, 10]"
          :nodes-draggable="true"
          :nodes-connectable="false"
          @node-mouseenter="onNodeMouseEnter"
          @node-mouseleave="onNodeMouseLeave"
          @edge-mouseenter="onEdgeMouseEnter"
          @edge-mouseleave="onEdgeMouseLeave"
          :pan-on-drag="true"
          :zoom-on-scroll="true"
          :prevent-scrolling="true"
          fit-view-on-init
          @node-click="onNodeClick"
          @node-double-click="onNodeDoubleClick"
          @pane-click="onPaneClick"
          @nodes-change="onNodesChange"
          @node-drag-stop="onNodeDragStop"
        >
          <Background pattern-color="#2a2a3a" :gap="20" />
          <MiniMap 
            :node-color="getNodeColor"
            :node-stroke-width="3"
            pannable
            zoomable
          />
        </VueFlow>

        <!-- Canvas Control Toolbar (Bottom) -->
        <div v-if="nodes.length > 0" class="aggregate-canvas-toolbar">
          <button class="aggregate-canvas-toolbar__btn" @click="zoomIn()" title="Zoom In">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              <line x1="11" y1="8" x2="11" y2="14"></line>
              <line x1="8" y1="11" x2="14" y2="11"></line>
            </svg>
          </button>

          <button class="aggregate-canvas-toolbar__btn" @click="zoomOut()" title="Zoom Out">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              <line x1="8" y1="11" x2="14" y2="11"></line>
            </svg>
          </button>

          <button class="aggregate-canvas-toolbar__btn" @click="fitView({ padding: 0.3 })" title="Fit View">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
            </svg>
          </button>

          <div class="aggregate-canvas-toolbar__divider"></div>

          <button class="aggregate-canvas-toolbar__btn" @click="store.clearAllBCs()" title="Clear Canvas">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
          </button>
        </div>
      </div>
    </div>
    </div>

    <!-- Resizer (between canvas and right-side panel) -->
    <div
      v-if="panelMode !== 'none'"
      class="aggregate-chat-panel-resizer"
      @mousedown="panelMode === 'chat' ? startResizeChat() : startResizeInspector($event)"
      title="드래그하여 패널 너비 조절"
    ></div>

    <!-- Right-side Panel Wrapper -->
    <div v-if="panelMode !== 'none'" class="aggregate-side-panel-wrapper" :style="{ width: (panelMode === 'chat' ? chatPanelWidth : inspectorPanelWidth) + 'px' }">
      <div v-if="panelMode === 'chat'" class="aggregate-chat-panel-wrapper">
        <ChatPanel />
      </div>

      <!-- Inspector Panel -->
      <div v-else-if="panelMode === 'inspector'" class="aggregate-viewer__inspector">
        <AggregateViewerInspector
          :aggregate-id="inspectingAggregateId"
          :enum-index="inspectingEnumIndex"
          :vo-index="inspectingVoIndex"
          @close="panelMode = 'none'"
        />
      </div>
    </div>

    <!-- Right Sidebar Icons (always visible) -->
    <div class="aggregate-right-sidebar">
      <button 
        class="aggregate-right-sidebar__icon"
        :class="{ 'is-active': panelMode === 'chat' }"
        @click="toggleChatPanel"
        title="Model Modifier"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
      </button>
      <button 
        class="aggregate-right-sidebar__icon"
        :class="{ 'is-active': panelMode === 'inspector' }"
        @click="panelMode = panelMode === 'inspector' ? 'none' : 'inspector'"
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

<style scoped>
.aggregate-viewer {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.aggregate-main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #1e1e2e;
  position: relative;
  overflow: hidden;
}

.aggregate-viewer__loading,
.aggregate-viewer__error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--color-text-light);
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(252, 196, 25, 0.2);
  border-top-color: var(--color-aggregate);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-icon {
  font-size: 48px;
}

.error-retry {
  padding: 8px 16px;
  background: var(--color-aggregate);
  color: #1e1e2e;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
}

.error-retry:hover {
  opacity: 0.9;
}

.aggregate-viewer__content {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.aggregate-viewer__canvas {
  flex: 1;
  position: relative;
}

.aggregate-viewer__empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--color-text-light);
}

.aggregate-viewer__canvas.drop-zone-active {
  background: rgba(252, 196, 25, 0.05);
  border: 2px dashed rgba(252, 196, 25, 0.3);
}

/* ==========================================
   Canvas Control Toolbar (Bottom)
   ========================================== */
.aggregate-canvas-toolbar {
  position: absolute;
  bottom: var(--spacing-md, 16px);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: var(--spacing-xs, 8px);
  background: rgba(30, 31, 42, 0.95);
  padding: var(--spacing-xs, 8px);
  border-radius: var(--radius-md, 8px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.1);
  z-index: 10;
  backdrop-filter: blur(8px);
}

.aggregate-canvas-toolbar__btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm, 6px);
  color: var(--color-text, #e4e4e7);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.aggregate-canvas-toolbar__btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--color-text-bright, #ffffff);
}

.aggregate-canvas-toolbar__btn:active {
  background: rgba(255, 255, 255, 0.15);
}

.aggregate-canvas-toolbar__divider {
  width: 1px;
  background: rgba(255, 255, 255, 0.1);
  margin: var(--spacing-xs, 8px) 0;
}

.empty-icon {
  font-size: 64px;
  opacity: 0.5;
}

.empty-text {
  font-size: 1.2rem;
  font-weight: 500;
  color: var(--color-text-bright);
}

.empty-hint {
  font-size: 0.9rem;
  opacity: 0.7;
}

.aggregate-viewer__inspector {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #252836;
  overflow-y: auto;
}

.inspector-resizer {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 6px;
  cursor: col-resize;
  background: transparent;
}

.inspector-resizer:hover {
  background: rgba(92, 124, 250, 0.12);
}

/* ==========================================
   Chat Panel (same structure as Design Viewer)
   ========================================== */
.aggregate-chat-panel-resizer {
  width: 6px;
  cursor: col-resize;
  background: transparent;
  position: relative;
}

.aggregate-chat-panel-resizer:hover {
  background: rgba(34, 139, 230, 0.12);
}

.aggregate-side-panel-wrapper {
  flex-shrink: 0;
  background: var(--color-bg-secondary);
  border-left: 1px solid var(--color-border);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: slideIn 0.2s ease;
}

/* ==========================================
   Node and Edge Hover Highlighting
   ========================================== */

/* Highlighted node (hovered or connected) */
.vue-flow__node.aggregate-node--highlighted {
  outline: 3px solid #fcc419 !important;
  outline-offset: 3px !important;
  box-shadow: 0 0 20px rgba(252, 196, 25, 0.5) !important;
  z-index: 10 !important;
  transition: all 0.2s ease !important;
}

/* Dimmed node (not connected to hovered node) */
.vue-flow__node.aggregate-node--dimmed {
  opacity: 0.6 !important;
  transition: opacity 0.2s ease !important;
  z-index: 1 !important;
}

/* Highlighted edge (hovered or connected to hovered node) */
.vue-flow__edge.aggregate-edge--highlighted {
  z-index: 1000 !important;
  position: relative;
  pointer-events: auto !important;
}

.vue-flow__edge.aggregate-edge--highlighted .vue-flow__edge-path {
  stroke-width: 5 !important;
  filter: 
    drop-shadow(0 0 8px currentColor) 
    drop-shadow(0 0 4px rgba(252, 196, 25, 1))
    drop-shadow(0 0 2px rgba(255, 255, 255, 1));
  z-index: 1000 !important;
  transition: all 0.2s ease !important;
  paint-order: stroke fill;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-opacity: 1;
}

.vue-flow__edge.aggregate-edge--highlighted .vue-flow__edge-text {
  font-weight: 600 !important;
  font-size: 11px !important;
}

/* Dimmed edge (not connected to hovered node) */
.vue-flow__edge.aggregate-edge--dimmed {
  z-index: 1 !important;
}

.vue-flow__edge.aggregate-edge--dimmed .vue-flow__edge-path {
  opacity: 0.3 !important;
  transition: opacity 0.2s ease !important;
}

/* Ensure edges layer is above nodes */
.vue-flow__edges {
  z-index: 5 !important;
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

.aggregate-chat-panel-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Right Sidebar Icons (always visible) */
.aggregate-right-sidebar {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 6px;
  background: var(--color-bg-secondary);
  border-left: 1px solid var(--color-border);
}

.aggregate-right-sidebar__icon {
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

.aggregate-right-sidebar__icon:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}

.aggregate-right-sidebar__icon.is-active {
  background: var(--color-accent);
  color: white;
}

.aggregate-right-sidebar__icon.is-active:hover {
  background: #1c7ed6;
}
</style>
