<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useBigPictureStore } from '@/features/canvas/bigpicture.store'

const store = useBigPictureStore()

// DOM refs
const tableContainer = ref(null)
const tableWrapper = ref(null)
const svgContainer = ref(null)

// Local UI state
const showFilterDropdown = ref(false)
const showLegend = ref(true)
const viewMode = ref('timeline') // 'timeline' or 'flow'

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
const SEQUENCE_STEP_WIDTH = 165
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

// Computed: timeline width based on max global sequence
const timelineWidth = computed(() => {
  const maxSeq = store.maxSequence || 1
  return SWIMLANE_HEADER_WIDTH + (maxSeq + 1) * SEQUENCE_STEP_WIDTH + 100
})

// Computed: total height of swimlanes
const totalHeight = computed(() => {
  return store.filteredSwimlanes.reduce((sum, lane) => {
    return sum + (swimlaneHeights.value[lane.bcId] || SWIMLANE_MIN_HEIGHT) + SWIMLANE_GAP
  }, TIMELINE_HEADER_HEIGHT + 60)
})

// Computed: event positions map - stack vertically only when at same sequence
const eventPositions = computed(() => {
  const positions = {}
  let currentY = TIMELINE_HEADER_HEIGHT + 20
  
  store.filteredSwimlanes.forEach((lane, laneIndex) => {
    const laneStartY = currentY
    const laneHeight = swimlaneHeights.value[lane.bcId] || SWIMLANE_MIN_HEIGHT
    
    // Group events by sequence (X position) - stack vertically only at same sequence
    const sequenceGroups = {}
    lane.events.forEach(evt => {
      const seq = evt.sequence || 1
      if (!sequenceGroups[seq]) sequenceGroups[seq] = []
      sequenceGroups[seq].push(evt)
    })
    
    // Position events - stack vertically only when multiple events at same sequence
    Object.entries(sequenceGroups).forEach(([seq, events]) => {
      events.forEach((evt, evtIndex) => {
        // X position based on sequence
        const x = SWIMLANE_HEADER_WIDTH + (evt.sequence) * SEQUENCE_STEP_WIDTH + EVENT_HORIZONTAL_GAP
        
        // Y position: center vertically if single event, stack if multiple at same sequence
        const y = laneStartY + SWIMLANE_PADDING + evtIndex * (EVENT_CARD_HEIGHT + EVENT_VERTICAL_GAP)
        
        positions[evt.id] = {
          x,
          y,
          laneIndex,
          eventIndex: evtIndex,
          sequence: evt.sequence,
          bcId: lane.bcId,
          actor: evt.actor || 'System',
          sequenceIndex: evtIndex
        }
      })
    })
    
    currentY += laneHeight + SWIMLANE_GAP
  })
  
  return positions
})

// Computed: SVG paths for connections with bezier curves
const connectionPaths = computed(() => {
  const paths = []
  
  store.filteredConnections.forEach(conn => {
    const sourcePos = eventPositions.value[conn.sourceEventId]
    const targetPos = eventPositions.value[conn.targetEventId]
    
    if (!sourcePos || !targetPos) return
    
    // Calculate start and end points
    const startX = sourcePos.x + EVENT_CARD_WIDTH
    const startY = sourcePos.y + EVENT_CARD_HEIGHT / 2
    const endX = targetPos.x
    const endY = targetPos.y + EVENT_CARD_HEIGHT / 2
    
    // Determine connection type for styling
    const isCrossBC = conn.type === 'cross-bc'
    const isSameBC = conn.type === 'same-bc'
    
    // Create bezier curve path
    let path
    const dx = endX - startX
    const dy = endY - startY
    
    if (Math.abs(dy) < 30) {
      // Nearly horizontal - simple curve
      const controlOffset = Math.min(50, Math.abs(dx) / 3)
      path = `M ${startX} ${startY} C ${startX + controlOffset} ${startY}, ${endX - controlOffset} ${endY}, ${endX} ${endY}`
    } else if (isCrossBC) {
      // Cross-BC - elegant S-curve going through middle
      const midX = (startX + endX) / 2
      const controlOffset = Math.abs(dx) * 0.4
      path = `M ${startX} ${startY} C ${startX + controlOffset} ${startY}, ${midX} ${startY}, ${midX} ${(startY + endY) / 2} S ${endX - controlOffset} ${endY}, ${endX} ${endY}`
    } else {
      // Same BC - gentle curve
      const controlOffset = Math.min(80, Math.max(40, Math.abs(dy) * 0.5))
      path = `M ${startX} ${startY} C ${startX + controlOffset} ${startY}, ${endX - controlOffset} ${endY}, ${endX} ${endY}`
    }
    
    const isHighlighted = store.highlightedConnections.some(
      h => h.sourceEventId === conn.sourceEventId && h.targetEventId === conn.targetEventId
    )
    
    // Calculate label position (middle of curve)
    const labelX = (startX + endX) / 2 + 10
    const labelY = (startY + endY) / 2 - 8
    
    paths.push({
      id: `${conn.sourceEventId}-${conn.targetEventId}`,
      path,
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
  const maxSeq = store.maxSequence || 1
  
  for (let i = 1; i <= maxSeq; i++) {
    markers.push({
      sequence: i,
      x: SWIMLANE_HEADER_WIDTH + i * SEQUENCE_STEP_WIDTH + SEQUENCE_STEP_WIDTH / 2
    })
  }
  
  return markers
})

// ==========================================
// Event Selection Handlers
// ==========================================

function handleEventClick(event, evt, bcId) {
  event.stopPropagation()
  if (store.selectedEventId === evt.id) {
    store.clearSelection()
  } else {
    store.selectEvent(evt.id)
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
  showFilterDropdown.value = false
}

// ==========================================
// Pan Handling (drag to scroll)
// ==========================================

function handlePanStart(e) {
  if (e.target.closest('.bp-event-card') || 
      e.target.closest('.bp-drag-handle') || 
      e.target.closest('.bp-toolbar') ||
      e.target.closest('.bp-filter-dropdown') ||
      e.target.closest('.bp-legend')) {
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
    if (e.deltaY < 0) {
      store.zoomIn()
    } else {
      store.zoomOut()
    }
  }
}

function toggleFilterDropdown() {
  showFilterDropdown.value = !showFilterDropdown.value
}

function toggleLegend() {
  showLegend.value = !showLegend.value
}

// ==========================================
// Lifecycle
// ==========================================

onMounted(async () => {
  await store.fetchTimeline()
  
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
  let y = TIMELINE_HEADER_HEIGHT + 20
  for (let i = 0; i < laneIndex; i++) {
    const lane = store.filteredSwimlanes[i]
    y += (swimlaneHeights.value[lane.bcId] || SWIMLANE_MIN_HEIGHT) + SWIMLANE_GAP
  }
  return y
}
</script>

<template>
  <div 
    class="big-picture-panel"
    @click="handlePaneClick"
    @wheel="handleWheel"
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
    <div v-else-if="store.swimlanes.length === 0" class="bp-empty">
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
      <p>이벤트 스토밍 데이터가 없습니다.<br/>요구사항 문서를 업로드하여 도메인 분석을 시작하세요.</p>
    </div>

    <!-- Main Timeline View -->
    <template v-else>
      <!-- Toolbar -->
      <div class="bp-toolbar">
        <div class="bp-toolbar__left">
          <div class="bp-toolbar__title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <line x1="3" y1="9" x2="21" y2="9"/>
              <line x1="9" y1="21" x2="9" y2="9"/>
            </svg>
            <span>Value Chain</span>
          </div>
          
          <!-- Filter Dropdown -->
          <div class="bp-filter-container">
            <button 
              class="bp-filter-btn"
              :class="{ 'has-filter': store.selectedBcIds.length > 0 }"
              @click.stop="toggleFilterDropdown"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
              </svg>
              <span>BC Filter{{ store.selectedBcIds.length > 0 ? ` (${store.selectedBcIds.length})` : '' }}</span>
            </button>
            
            <div v-if="showFilterDropdown" class="bp-filter-dropdown" @click.stop>
              <div class="bp-filter-dropdown__header">
                <span>Bounded Context 필터</span>
                <button v-if="store.selectedBcIds.length > 0" @click="store.clearFilters()">
                  초기화
                </button>
              </div>
              <div class="bp-filter-dropdown__list">
                <label 
                  v-for="(bc, idx) in store.allBCs" 
                  :key="bc.id"
                  class="bp-filter-item"
                >
                  <input 
                    type="checkbox"
                    :checked="store.selectedBcIds.includes(bc.id)"
                    @change="store.toggleBCFilter(bc.id)"
                  />
                  <span 
                    class="bp-filter-item__color" 
                    :style="{ background: getBcColor(idx).accent }"
                  ></span>
                  <span>{{ bc.name }}</span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <div class="bp-toolbar__right">
          <!-- Zoom Controls -->
          <div class="bp-zoom-controls">
            <button @click="store.zoomOut()" title="Zoom Out (Ctrl+Scroll)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <line x1="8" y1="11" x2="14" y2="11"/>
              </svg>
            </button>
            <span class="bp-zoom-level">{{ Math.round(store.zoomLevel * 100) }}%</span>
            <button @click="store.zoomIn()" title="Zoom In (Ctrl+Scroll)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <line x1="11" y1="8" x2="11" y2="14"/>
                <line x1="8" y1="11" x2="14" y2="11"/>
              </svg>
            </button>
            <button @click="store.resetZoom()" title="Reset Zoom">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                <path d="M3 3v5h5"/>
              </svg>
            </button>
          </div>
          
          <button class="bp-legend-toggle" @click="toggleLegend" :class="{ active: showLegend }">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2"/>
              <circle cx="8.5" cy="8.5" r="1.5"/>
              <circle cx="8.5" cy="15.5" r="1.5"/>
              <line x1="12" y1="8.5" x2="18" y2="8.5"/>
              <line x1="12" y1="15.5" x2="18" y2="15.5"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Timeline Container -->
      <div 
        ref="tableWrapper"
        class="bp-table-wrapper"
        :class="{ 'is-panning': isPanning }"
        @mousedown="handlePanStart"
      >
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
          <!-- Timeline Header (Sequence Numbers) -->
          <div class="bp-timeline-header" :style="{ width: timelineWidth + 'px' }">
            <div class="bp-timeline-header__label" :style="{ width: SWIMLANE_HEADER_WIDTH + 'px' }">
              <span>Bounded Context</span>
            </div>
            <div class="bp-timeline-header__markers">
              <div 
                v-for="marker in sequenceMarkers"
                :key="marker.sequence"
                class="bp-sequence-marker"
                :style="{ left: marker.x - SWIMLANE_HEADER_WIDTH + 'px' }"
              >
                <span class="bp-sequence-marker__number">{{ marker.sequence }}</span>
                <span class="bp-sequence-marker__label">Step</span>
              </div>
            </div>
          </div>

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
              <marker
                id="arrowhead-policy"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#b197fc"/>
              </marker>
              <marker
                id="arrowhead-policy-highlight"
                markerWidth="12"
                markerHeight="8"
                refX="11"
                refY="4"
                orient="auto"
              >
                <polygon points="0 0, 12 4, 0 8" fill="#fcc419"/>
              </marker>
              <marker
                id="arrowhead-cross-bc"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
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
                  :class="{
                    'is-selected': store.selectedEventId === evt.id,
                    'is-hovered': store.hoveredEventId === evt.id,
                    'has-outgoing': store.hasOutgoingConnections(evt.id),
                    'has-incoming': store.hasIncomingConnections(evt.id)
                  }"
                  :style="{
                    position: 'absolute',
                    left: (eventPositions[evt.id]?.x - SWIMLANE_HEADER_WIDTH || 0) + 'px',
                    top: (eventPositions[evt.id]?.y - getSwimlaneY(laneIndex) || 0) + 'px',
                    width: EVENT_CARD_WIDTH + 'px'
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

      <!-- Legend Panel -->
      <transition name="slide-fade">
        <div v-if="showLegend" class="bp-legend">
          <div class="bp-legend__header">
            <span class="bp-legend__title">범례</span>
            <button class="bp-legend__close" @click="showLegend = false">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          
          <div class="bp-legend__section">
            <div class="bp-legend__section-title">Elements</div>
            <div class="bp-legend__items">
              <div class="bp-legend__item">
                <div class="bp-legend__sample bp-legend__sample--event"></div>
                <span>Domain Event</span>
              </div>
              <div class="bp-legend__item">
                <div class="bp-legend__sample bp-legend__sample--actor"></div>
                <span>Actor/Persona</span>
              </div>
            </div>
          </div>
          
          <div class="bp-legend__hint">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <span>Ctrl+Scroll로 확대/축소, 드래그로 이동</span>
          </div>
        </div>
      </transition>
    </template>
  </div>
</template>

<style scoped>
.big-picture-panel {
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
   Toolbar
   ========================================== */
.bp-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: rgba(30, 31, 42, 0.95);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(8px);
  gap: 20px;
  z-index: 20;
  flex-shrink: 0;
}

.bp-toolbar__left, .bp-toolbar__right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.bp-toolbar__title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.bp-toolbar__title svg { color: var(--color-accent); }

/* Filter */
.bp-filter-container { position: relative; }

.bp-filter-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: var(--color-text);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.bp-filter-btn:hover { 
  border-color: rgba(34, 139, 230, 0.5);
  background: rgba(34, 139, 230, 0.1);
}

.bp-filter-btn.has-filter {
  background: rgba(34, 139, 230, 0.15);
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.bp-filter-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  min-width: 240px;
  background: rgba(30, 31, 42, 0.98);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
  z-index: 100;
  overflow: hidden;
  backdrop-filter: blur(12px);
}

.bp-filter-dropdown__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-text-light);
}

.bp-filter-dropdown__header button {
  background: none;
  border: none;
  color: var(--color-accent);
  font-size: 0.75rem;
  cursor: pointer;
  opacity: 0.8;
}

.bp-filter-dropdown__header button:hover { opacity: 1; }

.bp-filter-dropdown__list {
  padding: 8px;
  max-height: 280px;
  overflow-y: auto;
}

.bp-filter-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--color-text);
  transition: background 0.15s ease;
}

.bp-filter-item:hover { background: rgba(255, 255, 255, 0.06); }

.bp-filter-item input { 
  accent-color: var(--color-accent);
  width: 16px;
  height: 16px;
}

.bp-filter-item__color {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

/* Zoom Controls */
.bp-zoom-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(255, 255, 255, 0.04);
  padding: 4px;
  border-radius: 8px;
}

.bp-zoom-controls button {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.15s ease;
}

.bp-zoom-controls button:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--color-text-bright);
}

.bp-zoom-level {
  min-width: 50px;
  text-align: center;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-light);
}

.bp-legend-toggle {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.2s ease;
}

.bp-legend-toggle:hover { background: rgba(255, 255, 255, 0.1); }
.bp-legend-toggle.active { 
  background: rgba(34, 139, 230, 0.15);
  border-color: var(--color-accent);
  color: var(--color-accent);
}

/* ==========================================
   Table Wrapper
   ========================================== */
.bp-table-wrapper {
  flex: 1;
  overflow: auto;
  position: relative;
  cursor: grab;
}

.bp-table-wrapper.is-panning {
  cursor: grabbing;
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
   Legend Panel
   ========================================== */
.bp-legend {
  position: absolute;
  bottom: 20px;
  right: 20px;
  background: rgba(26, 27, 38, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 0;
  min-width: 240px;
  z-index: 20;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(12px);
  overflow: hidden;
}

.bp-legend__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.bp-legend__title {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-light);
}

.bp-legend__close {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: var(--color-text-light);
  cursor: pointer;
  transition: all 0.15s;
}

.bp-legend__close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--color-text);
}

.bp-legend__section {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.bp-legend__section:last-of-type {
  border-bottom: none;
}

.bp-legend__section-title {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-light);
  margin-bottom: 10px;
  opacity: 0.7;
}

.bp-legend__items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bp-legend__item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.75rem;
  color: var(--color-text);
}

.bp-legend__sample {
  width: 20px;
  height: 14px;
  border-radius: 4px;
}

.bp-legend__sample--event { background: var(--color-event); }
.bp-legend__sample--actor { background: #20c997; }

.bp-legend__hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 0.7rem;
  color: var(--color-text-light);
  background: rgba(0, 0, 0, 0.2);
  opacity: 0.8;
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
