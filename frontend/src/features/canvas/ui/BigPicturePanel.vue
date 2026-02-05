<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useBigPictureStore } from '@/features/canvas/bigpicture.store'
import { useModelModifierStore } from '@/features/modelModifier/modelModifier.store'
import ChatPanel from '@/features/modelModifier/ui/ChatPanel.vue'

const store = useBigPictureStore()
const chatStore = useModelModifierStore()

// DOM refs
const tableContainer = ref(null)
const tableWrapper = ref(null)
const svgContainer = ref(null)

// Local UI state
const viewMode = ref('timeline') // 'timeline' or 'flow'

// Panel mode: 'none' | 'chat'
const panelMode = ref('chat')
const chatPanelWidth = ref(360)
const isResizingChat = ref(false)

// Drag and drop state for BCs from navigator
const isDragOver = ref(false)

// Pan state (for table panning)
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0 })
const scrollStart = ref({ x: 0, y: 0 })

// Swimlane drag state
const draggingSwimlaneIndex = ref(null)
const swimlaneDragOverIndex = ref(null)

// Event drag state
const draggingEvent = ref(null)
const eventDragOverInfo = ref(null)

// Layout constants - optimized for better visualization
const SWIMLANE_HEADER_WIDTH = 200
const TIMELINE_HEADER_HEIGHT = 40
const EVENT_CARD_WIDTH = 140
const EVENT_CARD_HEIGHT = 76
const EVENT_VERTICAL_GAP = 10
const EVENT_HORIZONTAL_GAP = 16
const SEQUENCE_STEP_WIDTH = 220
const SWIMLANE_PADDING = 14
const SWIMLANE_MIN_HEIGHT = 110  // Minimum height for swimlane with single event
const SWIMLANE_GAP = 6

// Colors for different element types
const elementColors = {
  event: { bg: '#fd7e14', dark: '#e8590c', light: '#ff922b' },
  command: { bg: '#5c7cfa', dark: '#4263eb', light: '#748ffc' },
  policy: { bg: '#b197fc', dark: '#9775fa', light: '#d0bfff' },
  aggregate: { bg: '#fcc419', dark: '#f59f00', light: '#ffd43b' },
  actor: { bg: '#20c997', dark: '#12b886', light: '#38d9a9' }
}

// BC color palette for swimlanes - enhanced palette
const bcColors = [
  { bg: 'rgba(92, 124, 250, 0.08)', border: 'rgba(92, 124, 250, 0.35)', accent: '#5c7cfa', headerBg: 'rgba(92, 124, 250, 0.15)' },
  { bg: 'rgba(253, 126, 20, 0.08)', border: 'rgba(253, 126, 20, 0.35)', accent: '#fd7e14', headerBg: 'rgba(253, 126, 20, 0.15)' },
  { bg: 'rgba(177, 151, 252, 0.08)', border: 'rgba(177, 151, 252, 0.35)', accent: '#b197fc', headerBg: 'rgba(177, 151, 252, 0.15)' },
  { bg: 'rgba(64, 192, 87, 0.08)', border: 'rgba(64, 192, 87, 0.35)', accent: '#40c057', headerBg: 'rgba(64, 192, 87, 0.15)' },
  { bg: 'rgba(252, 196, 25, 0.08)', border: 'rgba(252, 196, 25, 0.35)', accent: '#fcc419', headerBg: 'rgba(252, 196, 25, 0.15)' },
  { bg: 'rgba(32, 201, 151, 0.08)', border: 'rgba(32, 201, 151, 0.35)', accent: '#20c997', headerBg: 'rgba(32, 201, 151, 0.15)' },
  { bg: 'rgba(230, 73, 128, 0.08)', border: 'rgba(230, 73, 128, 0.35)', accent: '#e64980', headerBg: 'rgba(230, 73, 128, 0.15)' },
  { bg: 'rgba(34, 139, 230, 0.08)', border: 'rgba(34, 139, 230, 0.35)', accent: '#228be6', headerBg: 'rgba(34, 139, 230, 0.15)' },
]

function getBcColor(index) {
  return bcColors[index % bcColors.length]
}

// Computed: calculate swimlane heights based on max events at same sequence position
const swimlaneHeights = computed(() => {
  const heights = {}
  store.filteredSwimlanes.forEach(lane => {
    // Group events by sequence (X position) - only stack vertically when at same sequence
    const sequenceGroups = {}
    lane.events.forEach(evt => {
      const seq = evt.sequence || 1
      if (!sequenceGroups[seq]) sequenceGroups[seq] = []
      sequenceGroups[seq].push(evt)
    })
    
    // Calculate height based on max events at any single sequence position
    const maxEventsAtSequence = Math.max(1, ...Object.values(sequenceGroups).map(g => g.length))
    heights[lane.bcId] = Math.max(
      SWIMLANE_MIN_HEIGHT,
      maxEventsAtSequence * (EVENT_CARD_HEIGHT + EVENT_VERTICAL_GAP) + SWIMLANE_PADDING * 2
    )
  })
  return heights
})

// Computed: timeline width based on max global sequence from filtered swimlanes
const timelineWidth = computed(() => {
  let maxSeq = 1
  store.filteredSwimlanes.forEach(lane => {
    lane.events.forEach(evt => {
      if (evt.sequence > maxSeq) maxSeq = evt.sequence
    })
  })
  return SWIMLANE_HEADER_WIDTH + (maxSeq + 1) * SEQUENCE_STEP_WIDTH + 100
})

// Computed: total height of swimlanes
const totalHeight = computed(() => {
  return store.filteredSwimlanes.reduce((sum, lane) => {
    return sum + (swimlaneHeights.value[lane.bcId] || SWIMLANE_MIN_HEIGHT) + SWIMLANE_GAP
  }, TIMELINE_HEADER_HEIGHT + 60)
})

// Computed: event positions map - same sequence events at same x position across all BCs
const eventPositions = computed(() => {
  const positions = {}
  let currentY = TIMELINE_HEADER_HEIGHT + 20
  
  // First pass: collect all events grouped by sequence (globally, across all BCs)
  const globalSequenceGroups = {}
  store.filteredSwimlanes.forEach(lane => {
    lane.events.forEach(evt => {
      const seq = evt.sequence || 1
      if (!globalSequenceGroups[seq]) {
        globalSequenceGroups[seq] = []
      }
      globalSequenceGroups[seq].push({ ...evt, bcId: lane.bcId, laneIndex: -1 }) // laneIndex will be set later
    })
  })
  
  // Sort events within each sequence group by BC name, then event name for consistent ordering
  Object.keys(globalSequenceGroups).forEach(seq => {
    globalSequenceGroups[seq].sort((a, b) => {
      const bcCompare = (a.bcId || '').localeCompare(b.bcId || '')
      if (bcCompare !== 0) return bcCompare
      return (a.name || '').localeCompare(b.name || '')
    })
  })
  
  // Second pass: position events within each swimlane
  store.filteredSwimlanes.forEach((lane, laneIndex) => {
    const laneHeight = swimlaneHeights.value[lane.bcId] || SWIMLANE_MIN_HEIGHT
    
    // Group events in this lane by sequence
    const laneSequenceGroups = {}
    lane.events.forEach(evt => {
      const seq = evt.sequence || 1
      if (!laneSequenceGroups[seq]) laneSequenceGroups[seq] = []
      laneSequenceGroups[seq].push(evt)
    })
    
    // Sort sequence groups by sequence number
    const sortedSequences = Object.keys(laneSequenceGroups).map(Number).sort((a, b) => a - b)
    
    // Position events - same sequence = same x position globally, stack vertically
    sortedSequences.forEach(seq => {
      const events = laneSequenceGroups[seq]
      // Sort events within same sequence by name for consistent ordering
      events.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
      
      // X position: same for ALL events at same sequence (globally across all BCs)
      // Center the event card so its middle aligns with the sequence marker
      // Sequence marker is at: SWIMLANE_HEADER_WIDTH + seq * SEQUENCE_STEP_WIDTH + SEQUENCE_STEP_WIDTH / 2
      // Event card center should be at the same position
      // So: x + EVENT_CARD_WIDTH / 2 = SWIMLANE_HEADER_WIDTH + seq * SEQUENCE_STEP_WIDTH + SEQUENCE_STEP_WIDTH / 2
      // Therefore: x = SWIMLANE_HEADER_WIDTH + seq * SEQUENCE_STEP_WIDTH + SEQUENCE_STEP_WIDTH / 2 - EVENT_CARD_WIDTH / 2
      const x = SWIMLANE_HEADER_WIDTH + seq * SEQUENCE_STEP_WIDTH + SEQUENCE_STEP_WIDTH / 2 - EVENT_CARD_WIDTH / 2
      
      // Y position: stack vertically when multiple events at same sequence in this lane
      const totalEventsAtSequence = events.length
      const totalHeight = totalEventsAtSequence * (EVENT_CARD_HEIGHT + EVENT_VERTICAL_GAP) - EVENT_VERTICAL_GAP
      // Calculate relative Y position within the swimlane (from top of swimlane)
      // Center the stack vertically within the swimlane
      const relativeStartY = SWIMLANE_PADDING + Math.max(0, (laneHeight - SWIMLANE_PADDING * 2 - totalHeight) / 2)
      
      events.forEach((evt, evtIndex) => {
        const relativeY = relativeStartY + evtIndex * (EVENT_CARD_HEIGHT + EVENT_VERTICAL_GAP)
        
        positions[evt.id] = {
          x, // Same x for all events at same sequence
          y: relativeY, // Stack vertically: different y for each event
          laneIndex,
          eventIndex: evtIndex,
          sequence: evt.sequence,
          bcId: lane.bcId,
          actor: evt.actor || 'System',
          sequenceIndex: evtIndex
        }
      })
    })
  })
  
  return positions
})

// Computed: SVG paths for connections with bezier curves
const connectionPaths = computed(() => {
  const paths = []
  
  // Get SVG container element to measure actual position
  const svgEl = svgContainer.value
  if (!svgEl) return paths
  
  // Get SVG's bounding rect relative to bp-table-container
  const svgRect = svgEl.getBoundingClientRect()
  const containerEl = svgEl.parentElement // bp-table-container
  if (!containerEl) return paths
  const containerRect = containerEl.getBoundingClientRect()
  
  // CRITICAL: SVG is inside zoomable container with transform: scale()
  // getBoundingClientRect() returns screen coordinates (after scale)
  // SVG coordinate system uses original coordinates (before scale)
  const zoomLevel = store.zoomLevel
  
  // Calculate SVG offset within container (accounts for padding)
  // SVG is position:absolute, left:0, top:0, so it's at container's content edge
  // Convert screen coordinates to SVG coordinates by dividing by zoom level
  const svgOffsetX = (svgRect.left - containerRect.left) / zoomLevel
  const svgOffsetY = (svgRect.top - containerRect.top) / zoomLevel
  
  store.filteredConnections.forEach(conn => {
    const sourcePos = eventPositions.value[conn.sourceEventId]
    const targetPos = eventPositions.value[conn.targetEventId]
    
    if (!sourcePos || !targetPos) return
    
    // Try to get actual DOM positions for cards
    const sourceCardEl = document.querySelector(`[data-event-id="${conn.sourceEventId}"]`)
    const targetCardEl = document.querySelector(`[data-event-id="${conn.targetEventId}"]`)
    
    let sourceCardRightEdge, startY, targetCardLeftEdge, endY
    
    if (sourceCardEl && targetCardEl) {
      // Use actual DOM positions - most accurate method
      const sourceRect = sourceCardEl.getBoundingClientRect()
      const targetRect = targetCardEl.getBoundingClientRect()
      
      // CRITICAL: SVG is inside zoomable container with transform: scale()
      // getBoundingClientRect() returns screen coordinates (after scale)
      // SVG coordinate system uses original coordinates (before scale)
      // Convert screen coordinates to SVG coordinates by dividing by zoom level
      const zoomLevel = store.zoomLevel
      
      // Convert to SVG coordinates (relative to SVG element's top-left)
      // Source: right edge of card (exact pixel)
      // Screen coordinates -> SVG coordinates: divide by zoom level
      sourceCardRightEdge = (sourceRect.right - svgRect.left) / zoomLevel
      startY = (sourceRect.top + sourceRect.height / 2 - svgRect.top) / zoomLevel
      
      // Target: left edge of card (exact pixel where arrow tip should touch)
      targetCardLeftEdge = (targetRect.left - svgRect.left) / zoomLevel
      endY = (targetRect.top + targetRect.height / 2 - svgRect.top) / zoomLevel
    } else {
      // Fallback to calculated positions
    const sourceLaneY = getSwimlaneY(sourcePos.laneIndex)
    const targetLaneY = getSwimlaneY(targetPos.laneIndex)
    
      // Calculate card positions in container coordinates
      // Card DOM: left = eventPositions.x - SWIMLANE_HEADER_WIDTH (relative to bp-swimlane__events)
      // Card absolute in container = SWIMLANE_HEADER_WIDTH + (eventPositions.x - SWIMLANE_HEADER_WIDTH) = eventPositions.x
      // In SVG coordinates: subtract SVG offset
      sourceCardRightEdge = sourcePos.x + EVENT_CARD_WIDTH - svgOffsetX
      startY = sourceLaneY + sourcePos.y + EVENT_CARD_HEIGHT / 2 - svgOffsetY
      
      targetCardLeftEdge = targetPos.x - svgOffsetX
      endY = targetLaneY + targetPos.y + EVENT_CARD_HEIGHT / 2 - svgOffsetY
    }
    
    // Determine connection type for styling
    const isCrossBC = conn.type === 'cross-bc'
    const isSameBC = conn.type === 'same-bc'
    
    // Create bezier curve path with precise arrow positioning
    // SVG marker positioning:
    // - Path ends at a point
    // - Marker origin (0,0) is placed at that point  
    // - refX: distance from marker origin to arrow tip
    // - polygon points="0 0, 10 3.5, 0 7": arrow tip is at x=10
    // - To make arrow tip touch card edge: path must end at (cardEdge - refX)
    // 
    // Using actual DOM positions, so coordinates are pixel-perfect
    // Source has no marker, so path starts exactly at card edge
    // Target has marker, so path ends before card edge, marker extends to card edge
    // 
    // SVG marker with refX=0:
    // - Marker origin (0,0) is at path end
    // - Arrow tip is at x=10 in marker coordinates
    // - So arrow tip is 10px from path end
    // - To make arrow tip touch card edge: path ends at (cardEdge - 10)
    const arrowTipLength = 10  // Distance from marker origin to arrow tip
    const highlightedArrowTipLength = 11
    
    // Path coordinates - using actual DOM positions
    // Source: path starts exactly at source card right edge (no marker)
    const startX = sourceCardRightEdge
    // Target: arrow tip should touch target card left edge exactly
    const endX = targetCardLeftEdge
    // CRITICAL: SVG marker positioning
    // - Path ends at a point
    // - Marker origin (0,0) is placed at that point
    // - refX shifts the marker origin relative to the path end
    // - polygon points="0 0, 10 3.5, 0 7": arrow tip is at x=10 in marker coordinates
    // - With refX=0: marker origin at path end, arrow tip at path end + 10
    // - To make arrow tip touch card edge: path must end at (cardEdge - 10)
    // Now with refX=0, arrow tip extends 10px from path end
    const adjustedEndX = endX - arrowTipLength  // Arrow extends 10px from path end
    
    let path
    const dx = endX - startX
    const dy = endY - startY
    
    // Build path ending at adjustedEndX (marker will extend to endX)
    if (Math.abs(dy) < 30) {
      // Nearly horizontal - simple curve
      const controlOffset = Math.min(50, Math.abs(dx) / 3)
      path = `M ${startX} ${startY} C ${startX + controlOffset} ${startY}, ${adjustedEndX - controlOffset} ${endY}, ${adjustedEndX} ${endY}`
    } else if (isCrossBC) {
      // Cross-BC - elegant S-curve going through middle
      const midX = (startX + adjustedEndX) / 2
      const controlOffset = Math.abs(dx) * 0.4
      path = `M ${startX} ${startY} C ${startX + controlOffset} ${startY}, ${midX} ${startY}, ${midX} ${(startY + endY) / 2} S ${adjustedEndX - controlOffset} ${endY}, ${adjustedEndX} ${endY}`
    } else {
      // Same BC - gentle curve
      const controlOffset = Math.min(80, Math.max(40, Math.abs(dy) * 0.5))
      path = `M ${startX} ${startY} C ${startX + controlOffset} ${startY}, ${adjustedEndX - controlOffset} ${endY}, ${adjustedEndX} ${endY}`
    }
    
    const isHighlighted = store.highlightedConnections.some(
      h => h.sourceEventId === conn.sourceEventId && h.targetEventId === conn.targetEventId
    )
    
    // For highlighted connections, adjust path end for different arrow tip length
    let finalPath = path
    if (isHighlighted) {
      const highlightedAdjustedEndX = endX - highlightedArrowTipLength
      // Replace the last coordinate in the path
      finalPath = path.replace(new RegExp(`${adjustedEndX} ${endY}$`), `${highlightedAdjustedEndX} ${endY}`)
    }
    
    // Calculate label position (middle of curve)
    const labelX = (startX + endX) / 2 + 10
    const labelY = (startY + endY) / 2 - 8
    
    paths.push({
      id: `${conn.sourceEventId}-${conn.targetEventId}`,
      path: finalPath,
      sourceEventId: conn.sourceEventId,
      targetEventId: conn.targetEventId,
      policyName: conn.policyName,
      isHighlighted,
      isCrossBC,
      isSameBC,
      startX,
      startY,
      endX,
      endY,
      labelX,
      labelY
    })
  })
  
  return paths
})

// Computed: sequence markers for timeline header
const sequenceMarkers = computed(() => {
  const markers = []
  // Calculate max sequence from filtered swimlanes
  let maxSeq = 1
  store.filteredSwimlanes.forEach(lane => {
    lane.events.forEach(evt => {
      if (evt.sequence > maxSeq) maxSeq = evt.sequence
    })
  })
  
  for (let i = 1; i <= maxSeq; i++) {
    markers.push({
      sequence: i,
      x: SWIMLANE_HEADER_WIDTH + i * SEQUENCE_STEP_WIDTH + SEQUENCE_STEP_WIDTH / 2
    })
  }
  
  return markers
})

// ==========================================
// Panel Management
// ==========================================

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
    localStorage.setItem('bigpicture_chat_panel_width', String(chatPanelWidth.value))
  } catch {}
}

function stopResizeChat() {
  isResizingChat.value = false
  document.removeEventListener('mousemove', onResizeChat)
  document.removeEventListener('mouseup', stopResizeChat)
}

onMounted(() => {
  try {
    const v = Number(localStorage.getItem('bigpicture_chat_panel_width'))
    if (Number.isFinite(v) && v >= 200) chatPanelWidth.value = v
  } catch {}
})

onUnmounted(() => {
  stopResizeChat()
})

// ==========================================
// Event Selection Handlers
// ==========================================

function handleEventClick(event, evt, bcId) {
  event.stopPropagation()
  if (store.selectedEventId === evt.id) {
    store.clearSelection()
    // Clear selection in Model Modifier
    chatStore.clearSelection()
  } else {
    store.selectEvent(evt.id)
    // Update Model Modifier with selected event
    const selectedEventNode = {
      id: evt.id,
      name: evt.name,
      type: 'Event',
      bcId: bcId,
      commandId: evt.commandId,
      commandName: evt.commandName,
      aggregateId: evt.aggregateId,
      aggregateName: evt.aggregateName,
      actor: evt.actor,
      version: evt.version
    }
    chatStore.setSelectedNodes([selectedEventNode])
  }
}

function handleEventHover(evt) {
  if (!draggingEvent.value) {
    store.setHoveredEvent(evt.id)
  }
}

function handleEventLeave() {
  store.clearHover()
}

function handleConnectionHover(conn) {
  store.setHoveredConnection(conn.id)
}

function handleConnectionLeave() {
  store.clearConnectionHover()
}

function handlePaneClick() {
  store.clearSelection()
}

// ==========================================
// Pan Handling (drag to scroll)
// ==========================================

function handlePanStart(e) {
  if (e.target.closest('.bp-event-card') || 
      e.target.closest('.bp-drag-handle') || 
      false) {
    return
  }
  
  isPanning.value = true
  panStart.value = { x: e.clientX, y: e.clientY }
  scrollStart.value = {
    x: tableWrapper.value?.scrollLeft || 0,
    y: tableWrapper.value?.scrollTop || 0
  }
}

function handlePanMove(e) {
  if (!isPanning.value) return
  
  const dx = e.clientX - panStart.value.x
  const dy = e.clientY - panStart.value.y
  
  if (tableWrapper.value) {
    tableWrapper.value.scrollLeft = scrollStart.value.x - dx
    tableWrapper.value.scrollTop = scrollStart.value.y - dy
  }
}

function handlePanEnd() {
  isPanning.value = false
}

// ==========================================
// Swimlane Drag Handlers
// ==========================================

function handleSwimlaneeDragStart(e, index, bcId) {
  draggingSwimlaneIndex.value = index
  store.startDraggingSwimlane(bcId)
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', bcId)
}

function handleSwimlaneeDragOver(e, index) {
  e.preventDefault()
  swimlaneDragOverIndex.value = index
  store.setDragOverSwimlane(store.filteredSwimlanes[index]?.bcId)
}

function handleSwimlaneeDragLeave(e) {
  if (!e.currentTarget.contains(e.relatedTarget)) {
    swimlaneDragOverIndex.value = null
  }
}

function handleSwimlaneeDrop(e, toIndex) {
  e.preventDefault()
  const fromIndex = draggingSwimlaneIndex.value
  
  if (fromIndex !== null && fromIndex !== toIndex) {
    const fromBcId = store.filteredSwimlanes[fromIndex]?.bcId
    const toBcId = store.filteredSwimlanes[toIndex]?.bcId
    
    if (fromBcId && toBcId) {
      store.reorderSwimlane(fromBcId, toBcId)
    }
  }
  
  draggingSwimlaneIndex.value = null
  swimlaneDragOverIndex.value = null
  store.stopDraggingSwimlane()
}

function handleSwimlaneeDragEnd() {
  draggingSwimlaneIndex.value = null
  swimlaneDragOverIndex.value = null
  store.stopDraggingSwimlane()
}

// ==========================================
// Zoom and Filter
// ==========================================

function handleWheel(e) {
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault()
    // Use deltaY to calculate smooth zoom like VueFlow
    // Normalize deltaY to a reasonable zoom step (typically -120 to 120 per wheel notch)
    // Use smaller step for smoother zoom experience
    const zoomStep = -e.deltaY / 1000 // Negative because deltaY < 0 means scroll up (zoom in)
    const newZoom = Math.max(0.3, Math.min(2.5, store.zoomLevel + zoomStep))
    store.setZoom(newZoom)
  }
}


// ==========================================
// Lifecycle
// ==========================================

// ==========================================
// Drag and Drop Handlers for BCs from Navigator
// ==========================================

function handleDragOver(e) {
  // Check if dragging a BC from navigator
  // During dragover, we can only check types, not data
  if (e.dataTransfer?.types?.includes('application/json')) {
    e.preventDefault()
    e.stopPropagation()
    isDragOver.value = true
  }
}

function handleDragLeave(e) {
  // Only clear if we're actually leaving the drop zone
  if (!e.currentTarget.contains(e.relatedTarget)) {
    isDragOver.value = false
  }
}

async function handleDrop(e) {
  e.preventDefault()
  e.stopPropagation()
  isDragOver.value = false

  const dragData = e.dataTransfer?.getData('application/json')
  if (!dragData) return

  try {
    const data = JSON.parse(dragData)
    if (data.type === 'BoundedContext' && data.id) {
      await store.addBCWithOutboundFlow(data.id)
    }
  } catch (err) {
    console.error('Failed to handle BC drop:', err)
  }
}

// Handle double-click on empty canvas to add BC
function handleCanvasDoubleClick(e) {
  // This can be used for future enhancement (e.g., show BC selection dialog)
  // For now, we rely on drag and drop or double-click from navigator
}

// Fit view - scroll to show all content
function fitView() {
  if (tableWrapper.value) {
    tableWrapper.value.scrollTo({
      left: 0,
      top: 0,
      behavior: 'smooth'
    })
    // Reset zoom to 1
    store.resetZoom()
  }
}

onMounted(async () => {
  // Don't fetch all timeline data on mount - start empty
  // await store.fetchTimeline()
  
  document.addEventListener('mouseup', handlePanEnd)
  document.addEventListener('mousemove', handlePanMove)
})

onUnmounted(() => {
  document.removeEventListener('mouseup', handlePanEnd)
  document.removeEventListener('mousemove', handlePanMove)
})

// ==========================================
// Helpers
// ==========================================

function hasTriggeredPolicies(evt) {
  return evt.triggeredPolicies && evt.triggeredPolicies.length > 0
}

function getEventTooltip(evt) {
  let tooltip = `${evt.name}`
  
  if (evt.actor) tooltip += `\n\nActor: ${evt.actor}`
  if (evt.commandName) tooltip += `\nCommand: ${evt.commandName}`
  if (evt.aggregateName) tooltip += `\nAggregate: ${evt.aggregateName}`
  
  if (hasTriggeredPolicies(evt)) {
    tooltip += '\n\n🔗 Triggers:'
    evt.triggeredPolicies.forEach(p => {
      tooltip += `\n  → ${p.policyName}`
      if (p.targetEventName) tooltip += ` → ${p.targetEventName}`
    })
  }
  
  return tooltip
}

function isSwimlaneDropTarget(index) {
  return swimlaneDragOverIndex.value === index && draggingSwimlaneIndex.value !== index
}

function getActorsDisplay(actors) {
  if (!actors || actors.length === 0) return 'System'
  if (actors.length <= 2) return actors.join(', ')
  return `${actors[0]}, ${actors[1]} +${actors.length - 2}`
}

function getSwimlaneY(laneIndex) {
  // Calculate absolute Y position of swimlane within bp-table-container
  // SVG is at top: 0, so we need absolute positions
  // bp-swimlanes has margin-top: 20px, and each swimlane has its own height
  let y = TIMELINE_HEADER_HEIGHT + 20  // Header height + swimlanes margin-top
  for (let i = 0; i < laneIndex; i++) {
    const lane = store.filteredSwimlanes[i]
    y += (swimlaneHeights.value[lane.bcId] || SWIMLANE_MIN_HEIGHT) + SWIMLANE_GAP
  }
  return y
}
</script>

<template>
  <div class="big-picture-panel">
    <div 
      class="bp-main-content"
      @click="handlePaneClick"
      @wheel="handleWheel"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
    <!-- Loading State -->
    <div v-if="store.loading" class="bp-loading">
      <div class="bp-loading__spinner"></div>
      <span>타임라인 데이터 로딩 중...</span>
    </div>

    <!-- Error State -->
    <div v-else-if="store.error" class="bp-error">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      <h3>데이터 로드 실패</h3>
      <p>{{ store.error }}</p>
      <button class="bp-error__retry" @click="store.fetchTimeline()">다시 시도</button>
    </div>

    <!-- Empty State -->
    <div 
      v-else-if="store.swimlanes.length === 0" 
      class="bp-empty"
      :class="{ 'drop-zone-active': isDragOver }"
      @drop="handleDrop"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @dblclick="handleCanvasDoubleClick"
    >
      <div class="bp-empty__visual">
        <div class="bp-empty__icon">
          <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <line x1="3" y1="9" x2="21" y2="9"/>
            <line x1="9" y1="21" x2="9" y2="9"/>
          </svg>
        </div>
        <div class="bp-empty__flow">
          <div class="bp-empty__node bp-empty__node--event">Event</div>
          <div class="bp-empty__arrow">→</div>
          <div class="bp-empty__node bp-empty__node--policy">Policy</div>
          <div class="bp-empty__arrow">→</div>
          <div class="bp-empty__node bp-empty__node--command">Command</div>
        </div>
      </div>
      <h2>Value Chain</h2>
      <p>Bounded Context를 드래그하거나 더블클릭하여 Value Chain을 시작하세요.<br/>연결된 BC들이 자동으로 포함됩니다.</p>
    </div>

    <!-- Main Timeline View -->
    <template v-else>
      <!-- Timeline Container -->
      <div 
        ref="tableWrapper"
        class="bp-table-wrapper"
        :class="{ 'is-panning': isPanning, 'drop-zone-active': isDragOver }"
        @mousedown="handlePanStart"
        @drop="handleDrop"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
      >
        <!-- Timeline Header (Sequence Numbers) - Fixed outside zoomable container -->
        <div class="bp-timeline-header" :style="{ width: (timelineWidth * store.zoomLevel) + 'px' }">
          <div class="bp-timeline-header__label" :style="{ width: (SWIMLANE_HEADER_WIDTH * store.zoomLevel) + 'px' }">
              <span>Bounded Context</span>
            </div>
            <div class="bp-timeline-header__markers">
              <div 
                v-for="marker in sequenceMarkers"
                :key="marker.sequence"
                class="bp-sequence-marker"
              :style="{ left: (marker.x - SWIMLANE_HEADER_WIDTH) * store.zoomLevel + 'px' }"
              >
                <span class="bp-sequence-marker__number">{{ marker.sequence }}</span>
                <span class="bp-sequence-marker__label">Step</span>
              </div>
            </div>
          </div>

        <!-- Zoomable Container -->
        <div 
          ref="tableContainer"
          class="bp-table-container"
          :style="{
            transform: `scale(${store.zoomLevel})`,
            transformOrigin: 'top left',
            width: timelineWidth + 'px',
            minHeight: totalHeight + 'px'
          }"
        >

          <!-- SVG Layer for Connections -->
          <svg 
            ref="svgContainer"
            class="bp-connections-layer"
            :width="timelineWidth"
            :height="totalHeight"
          >
            <defs>
              <!-- Gradient for cross-BC connections -->
              <linearGradient id="crossBcGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color:#fd7e14;stop-opacity:1" />
                <stop offset="50%" style="stop-color:#b197fc;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#fd7e14;stop-opacity:1" />
              </linearGradient>
              
              <!-- Arrow markers -->
              <!-- SVG marker positioning:
                   - polygon points="0 0, 10 3.5, 0 7": arrow tip is at (10, 3.5)
                   - refX: distance from marker origin (path end) to arrow tip
                   - refX=10 means arrow tip is 10px from marker origin
                   - To make arrow tip touch card edge: path ends at (cardEdge - refX)
                   - markerWidth must be >= refX to contain the arrow
              -->
              <marker
                id="arrowhead-policy"
                markerWidth="10"
                markerHeight="7"
                refX="0"
                refY="3.5"
                orient="auto"
                markerUnits="userSpaceOnUse"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#b197fc"/>
              </marker>
              <marker
                id="arrowhead-policy-highlight"
                markerWidth="11"
                markerHeight="8"
                refX="0"
                refY="4"
                orient="auto"
                markerUnits="userSpaceOnUse"
              >
                <polygon points="0 0, 11 4, 0 8" fill="#fcc419"/>
              </marker>
              <marker
                id="arrowhead-cross-bc"
                markerWidth="10"
                markerHeight="7"
                refX="0"
                refY="3.5"
                orient="auto"
                markerUnits="userSpaceOnUse"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#e64980"/>
              </marker>
            </defs>
            
            <!-- Grid lines for sequences -->
            <g class="bp-grid-lines">
              <line 
                v-for="marker in sequenceMarkers"
                :key="'grid-' + marker.sequence"
                :x1="marker.x"
                :y1="TIMELINE_HEADER_HEIGHT"
                :x2="marker.x"
                :y2="totalHeight"
                class="bp-grid-line"
              />
            </g>
            
            <!-- Connection Paths -->
            <g class="bp-connections">
              <g v-for="conn in connectionPaths" :key="conn.id" class="bp-connection-group">
                <!-- Shadow/glow for highlighted connections -->
                <path
                  v-if="conn.isHighlighted"
                  :d="conn.path"
                  class="bp-connection-glow"
                />
                <!-- Main path -->
                <path
                  :d="conn.path"
                  :class="[
                    'bp-connection-path',
                    { 
                      'is-highlighted': conn.isHighlighted,
                      'is-cross-bc': conn.isCrossBC,
                      'is-same-bc': conn.isSameBC
                    }
                  ]"
                  :marker-end="conn.isHighlighted ? 'url(#arrowhead-policy-highlight)' : (conn.isCrossBC ? 'url(#arrowhead-cross-bc)' : 'url(#arrowhead-policy)')"
                  @mouseenter="handleConnectionHover(conn)"
                  @mouseleave="handleConnectionLeave"
                />
                <!-- Policy label on connection -->
                <g v-if="conn.policyName" class="bp-connection-label-group">
                  <rect
                    :x="conn.labelX - 4"
                    :y="conn.labelY - 10"
                    :width="conn.policyName.length * 5.5 + 16"
                    height="16"
                    rx="8"
                    :class="['bp-connection-label-bg', { 'is-highlighted': conn.isHighlighted }]"
                  />
                  <text
                    :x="conn.labelX + 4"
                    :y="conn.labelY"
                    :class="['bp-connection-label', { 'is-highlighted': conn.isHighlighted }]"
                  >
                    <tspan class="bp-connection-label__icon">⚡</tspan>
                    <tspan>{{ conn.policyName }}</tspan>
                  </text>
                </g>
              </g>
            </g>
          </svg>

          <!-- Swimlanes -->
          <div class="bp-swimlanes">
            <div 
              v-for="(lane, laneIndex) in store.filteredSwimlanes"
              :key="lane.bcId"
              class="bp-swimlane"
              :class="{
                'is-dragging': draggingSwimlaneIndex === laneIndex,
                'is-drop-target': isSwimlaneDropTarget(laneIndex)
              }"
              :style="{
                height: swimlaneHeights[lane.bcId] + 'px',
                background: getBcColor(laneIndex).bg,
                borderColor: getBcColor(laneIndex).border
              }"
              @dragover="handleSwimlaneeDragOver($event, laneIndex)"
              @dragleave="handleSwimlaneeDragLeave"
              @drop="handleSwimlaneeDrop($event, laneIndex)"
            >
              <!-- Swimlane Header -->
              <div 
                class="bp-swimlane__header"
                :style="{ 
                  width: SWIMLANE_HEADER_WIDTH + 'px',
                  background: getBcColor(laneIndex).headerBg,
                  borderLeftColor: getBcColor(laneIndex).accent
                }"
              >
                <div 
                  class="bp-drag-handle"
                  draggable="true"
                  @dragstart="handleSwimlaneeDragStart($event, laneIndex, lane.bcId)"
                  @dragend="handleSwimlaneeDragEnd"
                  title="드래그하여 순서 변경"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="9" cy="5" r="1"/>
                    <circle cx="9" cy="12" r="1"/>
                    <circle cx="9" cy="19" r="1"/>
                    <circle cx="15" cy="5" r="1"/>
                    <circle cx="15" cy="12" r="1"/>
                    <circle cx="15" cy="19" r="1"/>
                  </svg>
                </div>
                
                <div class="bp-swimlane__info">
                  <div class="bp-swimlane__name">
                    <span 
                      class="bp-swimlane__color-dot"
                      :style="{ background: getBcColor(laneIndex).accent }"
                    ></span>
                    {{ lane.bcName }}
                  </div>
                  
                  <div class="bp-swimlane__actors">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                      <circle cx="12" cy="7" r="4"/>
                    </svg>
                    <span>{{ getActorsDisplay(lane.actors) }}</span>
                  </div>
                  
                  <div class="bp-swimlane__meta">
                    <span class="bp-swimlane__event-count">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                      </svg>
                      {{ lane.events.length }} events
                    </span>
                  </div>
                </div>
              </div>

              <!-- Events Area -->
              <div 
                class="bp-swimlane__events"
                :style="{
                  minWidth: (timelineWidth - SWIMLANE_HEADER_WIDTH) + 'px'
                }"
              >
                <!-- Event Cards -->
                <div
                  v-for="(evt, evtIndex) in lane.events"
                  :key="evt.id"
                  class="bp-event-card"
                  :data-event-id="evt.id"
                  :class="{
                    'is-selected': store.selectedEventId === evt.id,
                    'is-hovered': store.hoveredEventId === evt.id,
                    'has-outgoing': store.hasOutgoingConnections(evt.id),
                    'has-incoming': store.hasIncomingConnections(evt.id)
                  }"
                  :style="{
                    position: 'absolute',
                    left: (eventPositions[evt.id]?.x - SWIMLANE_HEADER_WIDTH || 0) + 'px',
                    top: (eventPositions[evt.id]?.y || 0) + 'px',
                    width: EVENT_CARD_WIDTH + 'px',
                    zIndex: 10
                  }"
                  :title="getEventTooltip(evt)"
                  @click="handleEventClick($event, evt, lane.bcId)"
                  @mouseenter="handleEventHover(evt)"
                  @mouseleave="handleEventLeave"
                >
                  <div class="bp-event-card__header">
                    <span class="bp-event-card__type">Event</span>
                    <span class="bp-event-card__seq">#{{ evt.sequence }}</span>
                  </div>
                  
                  <div class="bp-event-card__body">
                    <div class="bp-event-card__name">{{ evt.name }}</div>
                    
                    <div v-if="evt.actor" class="bp-event-card__actor">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                        <circle cx="12" cy="7" r="4"/>
                      </svg>
                      <span>{{ evt.actor }}</span>
                    </div>
                  </div>
                  
                  <!-- Triggered policies badge -->
                  <div v-if="hasTriggeredPolicies(evt)" class="bp-event-card__triggers">
                    <span class="bp-event-card__trigger-badge">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                      </svg>
                      {{ evt.triggeredPolicies.length }}
                    </span>
                  </div>
                  
                  <!-- Connection indicators -->
                  <div v-if="store.hasOutgoingConnections(evt.id)" class="bp-event-card__connector bp-event-card__connector--out"></div>
                  <div v-if="store.hasIncomingConnections(evt.id)" class="bp-event-card__connector bp-event-card__connector--in"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

    </template>

    <!-- Canvas Control Toolbar (Bottom) -->
    <div v-if="store.swimlanes.length > 0" class="bp-canvas-toolbar">
      <button class="bp-canvas-toolbar__btn" @click="store.zoomIn()" title="Zoom In">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          <line x1="11" y1="8" x2="11" y2="14"></line>
          <line x1="8" y1="11" x2="14" y2="11"></line>
        </svg>
      </button>

      <button class="bp-canvas-toolbar__btn" @click="store.zoomOut()" title="Zoom Out">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          <line x1="8" y1="11" x2="14" y2="11"></line>
        </svg>
      </button>

      <button class="bp-canvas-toolbar__btn" @click="fitView()" title="Fit View">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
        </svg>
      </button>

      <div class="bp-canvas-toolbar__divider"></div>

      <button class="bp-canvas-toolbar__btn" @click="store.clearAllBCs()" title="Clear Canvas">
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
      class="bp-chat-panel-resizer"
      @mousedown="startResizeChat"
      title="드래그하여 패널 너비 조절"
    ></div>

    <!-- Right-side Panel Wrapper -->
    <div v-if="panelMode !== 'none'" class="bp-side-panel-wrapper" :style="{ width: chatPanelWidth + 'px' }">
      <div v-if="panelMode === 'chat'" class="bp-chat-panel-wrapper">
        <ChatPanel />
      </div>
    </div>

    <!-- Right Sidebar Icons (always visible) -->
    <div class="bp-right-sidebar">
      <button 
        class="bp-right-sidebar__icon"
        :class="{ 'is-active': panelMode === 'chat' }"
        @click="toggleChatPanel"
        title="Model Modifier"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.big-picture-panel {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.bp-main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: linear-gradient(145deg, #13141a 0%, #1a1b26 50%, #1e1f2e 100%);
  position: relative;
  overflow: hidden;
  user-select: none;
}

/* ==========================================
   Loading State
   ========================================== */
.bp-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  color: var(--color-text-light);
}

.bp-loading__spinner {
  width: 48px;
  height: 48px;
  border: 3px solid rgba(255, 255, 255, 0.1);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ==========================================
   Error State
   ========================================== */
.bp-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--color-text-light);
  text-align: center;
  padding: 40px;
}

.bp-error svg { color: #fa5252; opacity: 0.9; }
.bp-error h3 { color: var(--color-text-bright); font-size: 1.2rem; margin: 0; font-weight: 600; }
.bp-error p { font-size: 0.9rem; opacity: 0.7; margin: 0; }

.bp-error__retry {
  margin-top: 12px;
  padding: 10px 24px;
  background: linear-gradient(135deg, var(--color-accent) 0%, #1c7ed6 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.bp-error__retry:hover { 
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(34, 139, 230, 0.4);
}

/* ==========================================
   Empty State
   ========================================== */
.bp-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24px;
  color: var(--color-text-light);
  text-align: center;
  padding: 40px;
  transition: all 0.2s ease;
  border-radius: 8px;
  border: 2px dashed transparent;
}

.bp-empty.drop-zone-active {
  border-color: rgba(92, 124, 250, 0.5);
  background: rgba(92, 124, 250, 0.05);
}

.bp-empty__visual {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
}

.bp-empty__icon { 
  opacity: 0.25; 
  animation: float 4s ease-in-out infinite;
}

.bp-empty__flow {
  display: flex;
  align-items: center;
  gap: 8px;
  opacity: 0.6;
}

.bp-empty__node {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 500;
}

.bp-empty__node--event { background: rgba(253, 126, 20, 0.3); color: #fd7e14; }
.bp-empty__node--policy { background: rgba(177, 151, 252, 0.3); color: #b197fc; }
.bp-empty__node--command { background: rgba(92, 124, 250, 0.3); color: #5c7cfa; }

.bp-empty__arrow {
  color: var(--color-text-light);
  opacity: 0.5;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-12px); }
}

.bp-empty h2 { color: var(--color-text-bright); font-size: 1.6rem; margin: 0; font-weight: 600; }
.bp-empty p { font-size: 1rem; line-height: 1.7; max-width: 400px; margin: 0; opacity: 0.7; }


/* ==========================================
   Table Wrapper
   ========================================== */
.bp-table-wrapper {
  flex: 1;
  overflow: auto;
  position: relative;
  cursor: grab;
  transition: all 0.2s ease;
}

.bp-table-wrapper.is-panning {
  cursor: grabbing;
}

.bp-table-wrapper.drop-zone-active {
  border: 2px dashed rgba(92, 124, 250, 0.5);
  background: rgba(92, 124, 250, 0.02);
  border-radius: 8px;
}

.bp-table-container {
  position: relative;
  padding: 0 20px 40px 20px;
}

/* ==========================================
   Timeline Header
   ========================================== */
.bp-timeline-header {
  position: sticky;
  top: 0;
  z-index: 15;
  display: flex;
  height: 40px;
  background: rgba(26, 27, 38, 0.95);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(8px);
}

.bp-timeline-header__label {
  display: flex;
  align-items: center;
  padding: 0 20px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-light);
  background: rgba(0, 0, 0, 0.2);
  flex-shrink: 0;
}

.bp-timeline-header__markers {
  position: relative;
  flex: 1;
}

.bp-sequence-marker {
  position: absolute;
  top: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  transform: translateX(-50%);
}

.bp-sequence-marker__number {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--color-text);
}

.bp-sequence-marker__label {
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-light);
  opacity: 0.6;
}

/* ==========================================
   SVG Connections Layer
   ========================================== */
.bp-connections-layer {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
  z-index: 10;
}

.bp-grid-line {
  stroke: rgba(255, 255, 255, 0.04);
  stroke-width: 1;
  stroke-dasharray: 4 4;
}

.bp-connection-glow {
  fill: none;
  stroke: #fcc419;
  stroke-width: 8;
  opacity: 0.3;
  filter: blur(4px);
}

.bp-connection-path {
  fill: none;
  stroke: #b197fc;
  stroke-width: 2;
  stroke-dasharray: 6 4;
  opacity: 0.6;
  pointer-events: stroke;
  cursor: pointer;
  transition: all 0.2s ease;
}

.bp-connection-path.is-cross-bc {
  stroke: #e64980;
  stroke-width: 2.5;
  opacity: 0.7;
}

.bp-connection-path.is-same-bc {
  stroke: #b197fc;
  opacity: 0.5;
}

.bp-connection-path:hover,
.bp-connection-path.is-highlighted {
  stroke: #fcc419;
  stroke-width: 3;
  opacity: 1;
  stroke-dasharray: none;
}

.bp-connection-label-bg {
  fill: rgba(26, 27, 38, 0.9);
  stroke: rgba(177, 151, 252, 0.3);
  stroke-width: 1;
}

.bp-connection-label-bg.is-highlighted {
  fill: rgba(252, 196, 25, 0.15);
  stroke: #fcc419;
}

.bp-connection-label {
  font-size: 9px;
  fill: var(--color-text-light);
  pointer-events: none;
  opacity: 0.7;
}

.bp-connection-label.is-highlighted {
  fill: #fcc419;
  font-weight: 600;
  opacity: 1;
}

.bp-connection-label__icon {
  font-size: 8px;
}

/* ==========================================
   Swimlanes
   ========================================== */
.bp-swimlanes {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 20px;
}

.bp-swimlane {
  display: flex;
  border: 1px solid;
  border-radius: 12px;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}

.bp-swimlane.is-dragging {
  opacity: 0.5;
}

.bp-swimlane.is-drop-target {
  border-color: var(--color-accent) !important;
  box-shadow: 0 0 0 3px rgba(34, 139, 230, 0.2);
}

.bp-swimlane__header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border-left: 4px solid;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.bp-drag-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: var(--color-text-light);
  cursor: grab;
  transition: all 0.15s ease;
  flex-shrink: 0;
  opacity: 0.5;
}

.bp-drag-handle:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--color-text);
  opacity: 1;
}

.bp-swimlane__info {
  flex: 1;
  min-width: 0;
}

.bp-swimlane__name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin-bottom: 8px;
}

.bp-swimlane__color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.bp-swimlane__actors {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: #20c997;
  margin-bottom: 6px;
}

.bp-swimlane__actors svg { opacity: 0.8; }

.bp-swimlane__meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bp-swimlane__event-count {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.7rem;
  color: var(--color-text-light);
  opacity: 0.7;
}

.bp-swimlane__events {
  flex: 1;
  position: relative;
  min-height: 100%;
}

/* ==========================================
   Event Cards
   ========================================== */
.bp-event-card {
  background: linear-gradient(135deg, var(--color-event) 0%, var(--color-event-dark) 100%);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(253, 126, 20, 0.2);
  overflow: hidden;
}

.bp-event-card:hover {
  transform: translateY(-3px) scale(1.02);
  box-shadow: 0 8px 24px rgba(253, 126, 20, 0.35);
  z-index: 5;
}

.bp-event-card.is-selected {
  outline: 3px solid var(--color-accent);
  outline-offset: 2px;
  box-shadow: 0 8px 24px rgba(34, 139, 230, 0.4);
  z-index: 6;
}

.bp-event-card.is-hovered {
  box-shadow: 0 8px 24px rgba(253, 126, 20, 0.4);
  z-index: 5;
}

.bp-event-card__header {
  padding: 5px 10px;
  background: rgba(0, 0, 0, 0.2);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.bp-event-card__type {
  font-size: 0.6rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.8);
}

.bp-event-card__seq {
  font-size: 0.6rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.6);
}

.bp-event-card__body {
  padding: 10px 12px;
}

.bp-event-card__name {
  font-size: 0.8rem;
  font-weight: 600;
  color: white;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  margin-bottom: 6px;
}

.bp-event-card__actor {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.75);
}

.bp-event-card__triggers {
  position: absolute;
  top: 6px;
  right: 6px;
}

.bp-event-card__trigger-badge {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 2px 6px;
  background: rgba(177, 151, 252, 0.9);
  border-radius: 10px;
  font-size: 0.6rem;
  font-weight: 600;
  color: white;
}

/* Connection indicators */
.bp-event-card__connector {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid rgba(26, 27, 38, 0.9);
}

.bp-event-card__connector--out {
  right: -6px;
  top: 50%;
  transform: translateY(-50%);
  background: #b197fc;
}

.bp-event-card__connector--in {
  left: -6px;
  top: 50%;
  transform: translateY(-50%);
  background: #e64980;
}


/* ==========================================
   Canvas Control Toolbar (Bottom)
   ========================================== */
.bp-canvas-toolbar {
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

.bp-canvas-toolbar__btn {
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

.bp-canvas-toolbar__btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--color-text-bright, #ffffff);
}

.bp-canvas-toolbar__btn:active {
  background: rgba(255, 255, 255, 0.15);
}

.bp-canvas-toolbar__divider {
  width: 1px;
  background: rgba(255, 255, 255, 0.1);
  margin: var(--spacing-xs, 8px) 0;
}

/* ==========================================
   Chat Panel (same structure as Design Viewer)
   ========================================== */
.bp-chat-panel-resizer {
  width: 6px;
  cursor: col-resize;
  background: transparent;
  position: relative;
}

.bp-chat-panel-resizer:hover {
  background: rgba(34, 139, 230, 0.12);
}

.bp-side-panel-wrapper {
  background: var(--color-bg-secondary);
  border-left: 1px solid var(--color-border);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.bp-chat-panel-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Container for canvas + chat */
.big-picture-panel {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Right Sidebar Icons (always visible) */
.bp-right-sidebar {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 6px;
  background: var(--color-bg-secondary);
  border-left: 1px solid var(--color-border);
}

.bp-right-sidebar__icon {
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

.bp-right-sidebar__icon:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}

.bp-right-sidebar__icon.is-active {
  background: var(--color-accent);
  color: white;
}

.bp-right-sidebar__icon.is-active:hover {
  background: #1c7ed6;
}

/* Transitions */
.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.3s ease;
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
