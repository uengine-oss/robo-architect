<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useBigPictureStore } from '@/features/canvas/bigpicture.store'

const store = useBigPictureStore()

// DOM refs
const tableContainer = ref(null)
const tableWrapper = ref(null)

// Local UI state
const showFilterDropdown = ref(false)

// Pan state (for table panning)
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0 })
const scrollStart = ref({ x: 0, y: 0 })

// Swimlane drag state
const draggingSwimlaneIndex = ref(null)
const swimlaneDragOverIndex = ref(null)

// Event drag state
const draggingEvent = ref(null) // { id, bcId, originalIndex }
const eventDragOverInfo = ref(null) // { bcId, index }

// Layout constants
const SWIMLANE_HEADER_WIDTH = 180
const EVENT_CARD_WIDTH = 130
const EVENT_CARD_HEIGHT = 65
const EVENT_VERTICAL_GAP = 8          // Gap between vertical events in same swimlane
const EVENT_HORIZONTAL_GAP = 10       // Reduced by 50% (was 20 effectively ~75 per sequence step, now ~37)
const SEQUENCE_STEP_WIDTH = 75        // Horizontal step per sequence (reduced by 50%)
const SWIMLANE_PADDING = 10
const SWIMLANE_GAP = 8

// Computed: max events in any swimlane (for swimlane height calculation)
const maxEventsPerLane = computed(() => {
  let max = 1
  store.filteredSwimlanes.forEach(lane => {
    if (lane.events.length > max) max = lane.events.length
  })
  return max
})

// Computed: dynamic swimlane height based on max events (vertical stacking)
const swimlaneHeight = computed(() => {
  return maxEventsPerLane.value * (EVENT_CARD_HEIGHT + EVENT_VERTICAL_GAP) + SWIMLANE_PADDING * 2
})

// Computed: timeline width based on max global sequence (50% reduced spacing)
const timelineWidth = computed(() => {
  const maxSeq = store.maxSequence || 1
  return SWIMLANE_HEADER_WIDTH + maxSeq * SEQUENCE_STEP_WIDTH + 100
})

// Computed: total height of swimlanes
const totalHeight = computed(() => {
  return store.filteredSwimlanes.length * (swimlaneHeight.value + SWIMLANE_GAP) + 40
})

// Computed: event positions map (recalculates when swimlanes change)
// Events stack vertically within swimlane, X position based on sequence (50% reduced)
const eventPositions = computed(() => {
  const positions = {}
  
  let currentY = 20
  
  store.filteredSwimlanes.forEach((lane, laneIndex) => {
    const laneStartY = currentY
    
    lane.events.forEach((evt, evtIndex) => {
      // X position based on global sequence (50% reduced spacing)
      const x = SWIMLANE_HEADER_WIDTH + (evt.sequence - 1) * SEQUENCE_STEP_WIDTH + EVENT_HORIZONTAL_GAP
      
      // Y position: stack vertically within the swimlane
      const y = laneStartY + SWIMLANE_PADDING + evtIndex * (EVENT_CARD_HEIGHT + EVENT_VERTICAL_GAP)
      
      positions[evt.id] = {
        x,
        y,
        laneIndex,
        eventIndex: evtIndex,
        sequence: evt.sequence,
        bcId: lane.bcId
      }
    })
    
    currentY += swimlaneHeight.value + SWIMLANE_GAP
  })
  
  return positions
})

// Computed: SVG paths for cross-BC connections (auto-recalculates)
const connectionPaths = computed(() => {
  const paths = []
  
  store.filteredConnections.forEach(conn => {
    const sourcePos = eventPositions.value[conn.sourceEventId]
    const targetPos = eventPositions.value[conn.targetEventId]
    
    if (!sourcePos || !targetPos) return
    
    const startX = sourcePos.x + EVENT_CARD_WIDTH
    const startY = sourcePos.y + EVENT_CARD_HEIGHT / 2
    const endX = targetPos.x
    const endY = targetPos.y + EVENT_CARD_HEIGHT / 2
    
    // Create curved path
    const controlOffset = Math.abs(endY - startY) * 0.4 + 40
    
    let path
    if (Math.abs(startY - endY) < 10) {
      // Same lane - simple curved line
      const midX = (startX + endX) / 2
      path = `M ${startX} ${startY} Q ${midX} ${startY - 25} ${endX} ${endY}`
    } else {
      // Cross-lane - S-curve
      path = `M ${startX} ${startY} C ${startX + controlOffset} ${startY}, ${endX - controlOffset} ${endY}, ${endX} ${endY}`
    }
    
    const isHighlighted = store.highlightedConnections.some(
      h => h.sourceEventId === conn.sourceEventId && h.targetEventId === conn.targetEventId
    )
    
    paths.push({
      id: `${conn.sourceEventId}-${conn.targetEventId}`,
      path,
      sourceEventId: conn.sourceEventId,
      targetEventId: conn.targetEventId,
      policyName: conn.policyName,
      isHighlighted,
      startX,
      startY,
      endX,
      endY
    })
  })
  
  return paths
})

// BC color palette for swimlanes
const bcColors = [
  { bg: 'rgba(92, 124, 250, 0.06)', border: 'rgba(92, 124, 250, 0.25)', accent: '#5c7cfa' },
  { bg: 'rgba(253, 126, 20, 0.06)', border: 'rgba(253, 126, 20, 0.25)', accent: '#fd7e14' },
  { bg: 'rgba(177, 151, 252, 0.06)', border: 'rgba(177, 151, 252, 0.25)', accent: '#b197fc' },
  { bg: 'rgba(64, 192, 87, 0.06)', border: 'rgba(64, 192, 87, 0.25)', accent: '#40c057' },
  { bg: 'rgba(252, 196, 25, 0.06)', border: 'rgba(252, 196, 25, 0.25)', accent: '#fcc419' },
  { bg: 'rgba(32, 201, 151, 0.06)', border: 'rgba(32, 201, 151, 0.25)', accent: '#20c997' },
]

function getBcColor(index) {
  return bcColors[index % bcColors.length]
}

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
  // Don't pan if clicking on interactive elements
  if (e.target.closest('.bp-event-card') || 
      e.target.closest('.bp-drag-handle') || 
      e.target.closest('.bp-toolbar') ||
      e.target.closest('.bp-filter-dropdown')) {
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
  // Only clear if leaving the swimlane entirely
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
// Event Drag Handlers
// ==========================================

function handleEventDragStart(e, evt, bcId, index) {
  e.stopPropagation()
  draggingEvent.value = { id: evt.id, bcId, originalIndex: index }
  store.startDraggingEvent(evt.id)
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', evt.id)
  
  // Add dragging class via timeout for visual feedback
  setTimeout(() => {
    const el = e.target
    if (el) el.classList.add('is-dragging')
  }, 0)
}

function handleEventDragOver(e, bcId, index) {
  e.preventDefault()
  e.stopPropagation()
  
  // Only allow dropping in the same swimlane
  if (draggingEvent.value && draggingEvent.value.bcId === bcId) {
    eventDragOverInfo.value = { bcId, index }
    store.setDragOverEventIndex(index)
  }
}

function handleEventDragLeave(e) {
  e.stopPropagation()
}

function handleEventDrop(e, bcId, toIndex) {
  e.preventDefault()
  e.stopPropagation()
  
  if (!draggingEvent.value) return
  
  const { bcId: fromBcId, originalIndex: fromIndex } = draggingEvent.value
  
  // Only allow reorder within same swimlane
  if (fromBcId === bcId && fromIndex !== toIndex) {
    store.reorderEventInSwimlane(bcId, fromIndex, toIndex)
  }
  
  draggingEvent.value = null
  eventDragOverInfo.value = null
  store.stopDraggingEvent()
}

function handleEventDragEnd(e) {
  if (e.target) e.target.classList.remove('is-dragging')
  draggingEvent.value = null
  eventDragOverInfo.value = null
  store.stopDraggingEvent()
}

// Handle dropping on swimlane row (for dropping at end)
function handleSwimlaneRowDrop(e, bcId) {
  e.preventDefault()
  
  if (!draggingEvent.value || draggingEvent.value.bcId !== bcId) return
  
  const lane = store.getSwimlaneByBcId(bcId)
  if (!lane) return
  
  const toIndex = lane.events.length - 1
  const fromIndex = draggingEvent.value.originalIndex
  
  if (fromIndex !== toIndex) {
    store.reorderEventInSwimlane(bcId, fromIndex, toIndex)
  }
  
  draggingEvent.value = null
  eventDragOverInfo.value = null
  store.stopDraggingEvent()
}

// ==========================================
// Zoom and Filter
// ==========================================

function handleWheel(e) {
  // Shift+Wheel for horizontal scroll, otherwise zoom
  if (e.shiftKey) {
    // Allow default horizontal scroll behavior
    return
  }
  
  e.preventDefault()
  if (e.deltaY < 0) {
    store.zoomIn()
  } else {
    store.zoomOut()
  }
}

function toggleFilterDropdown() {
  showFilterDropdown.value = !showFilterDropdown.value
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
  let tooltip = `${evt.name}\n\nCommand: ${evt.commandName || 'N/A'}\nAggregate: ${evt.aggregateName || 'N/A'}`
  
  if (hasTriggeredPolicies(evt)) {
    tooltip += '\n\nTriggers:'
    evt.triggeredPolicies.forEach(p => {
      tooltip += `\n  → ${p.policyName}`
    })
  }
  
  return tooltip
}

function isEventDropTarget(bcId, index) {
  return eventDragOverInfo.value?.bcId === bcId && eventDragOverInfo.value?.index === index
}

function isSwimlaneDropTarget(index) {
  return swimlaneDragOverIndex.value === index && draggingSwimlaneIndex.value !== index
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
      <span>타임라인 로딩 중...</span>
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
      <div class="bp-empty__icon">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <line x1="3" y1="9" x2="21" y2="9"/>
          <line x1="9" y1="21" x2="9" y2="9"/>
        </svg>
      </div>
      <h2>Big Picture</h2>
      <p>이벤트 스토밍 데이터가 없습니다.<br/>요구사항 문서를 업로드하여 분석을 시작하세요.</p>
    </div>

    <!-- Main Timeline View -->
    <template v-else>
      <!-- Toolbar -->
      <div class="bp-toolbar">
        <div class="bp-toolbar__left">
          <div class="bp-toolbar__title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <line x1="3" y1="9" x2="21" y2="9"/>
              <line x1="9" y1="21" x2="9" y2="9"/>
            </svg>
            <span>Big Picture Timeline</span>
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
              <span>Filter{{ store.selectedBcIds.length > 0 ? ` (${store.selectedBcIds.length})` : '' }}</span>
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
                  v-for="bc in store.allBCs" 
                  :key="bc.id"
                  class="bp-filter-item"
                >
                  <input 
                    type="checkbox"
                    :checked="store.selectedBcIds.includes(bc.id)"
                    @change="store.toggleBCFilter(bc.id)"
                  />
                  <span>{{ bc.name }}</span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- Stats moved to TopBar -->

        <div class="bp-toolbar__right">
          <div class="bp-zoom-controls">
            <button @click="store.zoomOut()" title="Zoom Out">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <line x1="8" y1="11" x2="14" y2="11"/>
              </svg>
            </button>
            <span class="bp-zoom-level">{{ Math.round(store.zoomLevel * 100) }}%</span>
            <button @click="store.zoomIn()" title="Zoom In">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <line x1="11" y1="8" x2="11" y2="14"/>
                <line x1="8" y1="11" x2="14" y2="11"/>
              </svg>
            </button>
            <button @click="store.resetZoom()" title="Reset">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                <path d="M3 3v5h5"/>
              </svg>
            </button>
          </div>
          
          <div class="bp-hint">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <span>드래그: BC/이벤트 재정렬</span>
          </div>
        </div>
      </div>

      <!-- Unified Table Container -->
      <div 
        ref="tableWrapper"
        class="bp-table-wrapper"
        :class="{ 'is-panning': isPanning }"
        @mousedown="handlePanStart"
      >
        <!-- Zoomable Table Container -->
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
            class="bp-connections-layer"
            :width="timelineWidth"
            :height="totalHeight"
          >
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#b197fc"/>
              </marker>
              <marker
                id="arrowhead-highlight"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#fcc419"/>
              </marker>
            </defs>
            
            <!-- Connection Paths -->
            <g v-for="conn in connectionPaths" :key="conn.id">
              <path
                :d="conn.path"
                :class="[
                  'bp-connection-path',
                  { 'is-highlighted': conn.isHighlighted }
                ]"
                :marker-end="conn.isHighlighted ? 'url(#arrowhead-highlight)' : 'url(#arrowhead)'"
                @mouseenter="handleConnectionHover(conn)"
                @mouseleave="handleConnectionLeave"
              />
              <!-- Policy label on connection -->
              <text
                v-if="conn.policyName"
                :x="(conn.startX + conn.endX) / 2"
                :y="(conn.startY + conn.endY) / 2 - 6"
                class="bp-connection-label"
                :class="{ 'is-highlighted': conn.isHighlighted }"
              >
                {{ conn.policyName }}
              </text>
            </g>
          </svg>

          <!-- Unified Table -->
          <div class="bp-table">
            <!-- Swimlane Rows -->
            <div 
              v-for="(lane, laneIndex) in store.filteredSwimlanes"
              :key="lane.bcId"
              class="bp-swimlane-row"
              :class="{
                'is-dragging': draggingSwimlaneIndex === laneIndex,
                'is-drop-target': isSwimlaneDropTarget(laneIndex)
              }"
              :style="{
                height: swimlaneHeight + 'px',
                background: getBcColor(laneIndex).bg,
                borderColor: getBcColor(laneIndex).border
              }"
              @dragover="handleSwimlaneeDragOver($event, laneIndex)"
              @dragleave="handleSwimlaneeDragLeave"
              @drop="handleSwimlaneeDrop($event, laneIndex)"
            >
              <!-- Swimlane Header Cell (with drag handle) -->
              <div 
                class="bp-swimlane-header"
                :style="{ 
                  width: SWIMLANE_HEADER_WIDTH + 'px',
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
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="3" y1="6" x2="21" y2="6"/>
                    <line x1="3" y1="12" x2="21" y2="12"/>
                    <line x1="3" y1="18" x2="21" y2="18"/>
                  </svg>
                </div>
                <div class="bp-swimlane-header__content">
                  <div class="bp-swimlane-header__name">{{ lane.bcName }}</div>
                  <div class="bp-swimlane-header__actors">
                    <span 
                      v-for="actor in lane.actors" 
                      :key="actor"
                      class="bp-actor-tag"
                    >
                      {{ actor }}
                    </span>
                  </div>
                  <div class="bp-swimlane-header__count">{{ lane.events.length }} events</div>
                </div>
              </div>

              <!-- Events Cell - events stacked vertically, X position by sequence -->
              <div 
                class="bp-swimlane-events"
                :style="{
                  minWidth: (timelineWidth - SWIMLANE_HEADER_WIDTH) + 'px',
                  height: swimlaneHeight + 'px'
                }"
                @dragover.prevent="handleEventDragOver($event, lane.bcId, lane.events.length)"
                @drop="handleSwimlaneRowDrop($event, lane.bcId)"
              >
                <!-- Event Cards - stacked vertically, positioned by sequence on X axis -->
                <div
                  v-for="(evt, evtIndex) in lane.events"
                  :key="evt.id"
                  class="bp-event-card"
                  :class="{
                    'is-selected': store.selectedEventId === evt.id,
                    'is-hovered': store.hoveredEventId === evt.id,
                    'is-dragging': draggingEvent?.id === evt.id,
                    'is-drop-target': isEventDropTarget(lane.bcId, evtIndex),
                    'has-outgoing': store.hasOutgoingConnections(evt.id),
                    'has-incoming': store.hasIncomingConnections(evt.id)
                  }"
                  :style="{
                    position: 'absolute',
                    left: ((evt.sequence - 1) * SEQUENCE_STEP_WIDTH + EVENT_HORIZONTAL_GAP) + 'px',
                    top: (SWIMLANE_PADDING + evtIndex * (EVENT_CARD_HEIGHT + EVENT_VERTICAL_GAP)) + 'px',
                    width: EVENT_CARD_WIDTH + 'px',
                    height: EVENT_CARD_HEIGHT + 'px'
                  }"
                  :title="getEventTooltip(evt)"
                  draggable="true"
                  @click="handleEventClick($event, evt, lane.bcId)"
                  @mouseenter="handleEventHover(evt)"
                  @mouseleave="handleEventLeave"
                  @dragstart="handleEventDragStart($event, evt, lane.bcId, evtIndex)"
                  @dragover="handleEventDragOver($event, lane.bcId, evtIndex)"
                  @dragleave="handleEventDragLeave"
                  @drop="handleEventDrop($event, lane.bcId, evtIndex)"
                  @dragend="handleEventDragEnd"
                >
                  <div class="bp-event-card__header">
                    <span>Event</span>
                    <span class="bp-event-card__seq">#{{ evt.sequence }}</span>
                  </div>
                  <div class="bp-event-card__name">{{ evt.name }}</div>
                  <div v-if="hasTriggeredPolicies(evt)" class="bp-event-card__badge">
                    <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="22 4 12 14.01 9 11.01"/>
                    </svg>
                    {{ evt.triggeredPolicies.length }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Legend -->
      <div class="bp-legend">
        <div class="bp-legend__title">Legend</div>
        <div class="bp-legend__items">
          <div class="bp-legend__item">
            <div class="bp-legend__color bp-legend__color--event"></div>
            <span>Domain Event</span>
          </div>
          <div class="bp-legend__item">
            <div class="bp-legend__line"></div>
            <span>Policy Trigger</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.big-picture-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #1e1e2e 0%, #1a1b26 100%);
  position: relative;
  overflow: hidden;
  user-select: none;
}

/* Loading State */
.bp-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--color-text-light);
}

.bp-loading__spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Error State */
.bp-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--color-text-light);
  text-align: center;
  padding: 40px;
}

.bp-error svg { color: #fa5252; opacity: 0.8; }
.bp-error h3 { color: var(--color-text-bright); font-size: 1.1rem; margin: 0; }
.bp-error p { font-size: 0.85rem; opacity: 0.7; margin: 0; }

.bp-error__retry {
  margin-top: 8px;
  padding: 8px 20px;
  background: var(--color-accent);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.2s;
}

.bp-error__retry:hover { background: #1c7ed6; }

/* Empty State */
.bp-empty {
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

.bp-empty__icon { opacity: 0.3; animation: float 3s ease-in-out infinite; }

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

.bp-empty h2 { color: var(--color-text-bright); font-size: 1.4rem; margin: 0; }
.bp-empty p { font-size: 0.9rem; line-height: 1.6; max-width: 320px; margin: 0; }

/* Toolbar */
.bp-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border);
  gap: 16px;
  z-index: 10;
  flex-shrink: 0;
}

.bp-toolbar__left, .bp-toolbar__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bp-toolbar__center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.bp-toolbar__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.bp-toolbar__title svg { color: var(--color-accent); }

/* Filter */
.bp-filter-container { position: relative; }

.bp-filter-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  color: var(--color-text);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.bp-filter-btn:hover { border-color: var(--color-accent); }

.bp-filter-btn.has-filter {
  background: rgba(34, 139, 230, 0.15);
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.bp-filter-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 4px;
  min-width: 200px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 100;
  overflow: hidden;
}

.bp-filter-dropdown__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-light);
}

.bp-filter-dropdown__header button {
  background: none;
  border: none;
  color: var(--color-accent);
  font-size: 0.7rem;
  cursor: pointer;
}

.bp-filter-dropdown__list {
  padding: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.bp-filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  color: var(--color-text);
  transition: background 0.15s;
}

.bp-filter-item:hover { background: var(--color-bg-tertiary); }
.bp-filter-item input { accent-color: var(--color-accent); }

/* Stats */
.bp-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.75rem;
  color: var(--color-text-light);
  background: var(--color-bg-tertiary);
  padding: 6px 14px;
  border-radius: 20px;
}

.bp-stats strong { color: var(--color-text); font-weight: 600; }
.bp-stats__dot { opacity: 0.4; }

/* Zoom Controls */
.bp-zoom-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--color-bg-tertiary);
  padding: 4px;
  border-radius: 6px;
}

.bp-zoom-controls button {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.15s;
}

.bp-zoom-controls button:hover {
  background: var(--color-bg-secondary);
  color: var(--color-text-bright);
}

.bp-zoom-level {
  min-width: 45px;
  text-align: center;
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--color-text-light);
}

/* Hint */
.bp-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.7rem;
  color: var(--color-text-light);
  opacity: 0.7;
}

/* Table Wrapper */
.bp-table-wrapper {
  flex: 1;
  overflow: auto;
  position: relative;
  cursor: grab;
}

.bp-table-wrapper.is-panning {
  cursor: grabbing;
}

/* Table Container (zoomable) */
.bp-table-container {
  position: relative;
  padding: 20px;
}

/* Unified Table */
.bp-table {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* Swimlane Row */
.bp-swimlane-row {
  display: flex;
  align-items: stretch;
  border: 1px solid;
  border-radius: 8px;
  transition: all 0.2s ease;
  position: relative;
}

.bp-swimlane-row.is-dragging {
  opacity: 0.5;
}

.bp-swimlane-row.is-drop-target {
  border-color: var(--color-accent) !important;
  box-shadow: 0 0 0 2px rgba(34, 139, 230, 0.3);
}

.bp-swimlane-row.is-drop-target::before {
  content: '';
  position: absolute;
  top: -4px;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--color-accent);
  border-radius: 2px;
}

/* Swimlane Header */
.bp-swimlane-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  border-left: 4px solid;
  border-right: 1px solid var(--color-border);
  background: rgba(0, 0, 0, 0.15);
  flex-shrink: 0;
}

.bp-drag-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  color: var(--color-text-light);
  cursor: grab;
  transition: all 0.15s;
  flex-shrink: 0;
}

.bp-drag-handle:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--color-text);
}

.bp-drag-handle:active {
  cursor: grabbing;
}

.bp-swimlane-header__content {
  flex: 1;
  min-width: 0;
}

.bp-swimlane-header__name {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-text-bright);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bp-swimlane-header__actors {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-bottom: 4px;
}

.bp-actor-tag {
  display: inline-flex;
  padding: 1px 6px;
  background: rgba(32, 201, 151, 0.15);
  border: 1px solid rgba(32, 201, 151, 0.3);
  border-radius: 8px;
  font-size: 0.6rem;
  color: #20c997;
}

.bp-swimlane-header__count {
  font-size: 0.65rem;
  color: var(--color-text-light);
}

/* Swimlane Events */
.bp-swimlane-events {
  flex: 1;
  position: relative;
  min-height: 100%;
}

/* Event Cards */
.bp-event-card {
  flex-shrink: 0;
  background: var(--color-event);
  border-radius: 6px;
  cursor: grab;
  transition: all 0.15s ease;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
  overflow: hidden;
  position: relative;
}

.bp-event-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(253, 126, 20, 0.3);
}

.bp-event-card.is-selected {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
  box-shadow: 0 4px 16px rgba(34, 139, 230, 0.4);
}

.bp-event-card.is-dragging {
  opacity: 0.5;
  cursor: grabbing;
}

.bp-event-card.is-drop-target {
  outline: 2px dashed var(--color-accent);
  outline-offset: 2px;
}

.bp-event-card.is-drop-target::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--color-accent);
  border-radius: 2px;
}

.bp-event-card.has-outgoing::after {
  content: '';
  position: absolute;
  right: -5px;
  top: 50%;
  transform: translateY(-50%);
  width: 10px;
  height: 10px;
  background: #b197fc;
  border-radius: 50%;
  border: 2px solid #1e1e2e;
}

.bp-event-card.has-incoming::before {
  content: '';
  position: absolute;
  left: -5px;
  top: 50%;
  transform: translateY(-50%);
  width: 10px;
  height: 10px;
  background: #b197fc;
  border-radius: 50%;
  border: 2px solid #1e1e2e;
  z-index: 1;
}

.bp-event-card__header {
  padding: 3px 8px;
  background: var(--color-event-dark);
  font-size: 0.55rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgba(255, 255, 255, 0.85);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.bp-event-card__seq {
  font-size: 0.5rem;
  font-weight: 600;
  opacity: 0.7;
  text-transform: none;
  letter-spacing: normal;
}

.bp-event-card__name {
  padding: 6px 8px;
  font-size: 0.75rem;
  font-weight: 600;
  color: white;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.bp-event-card__badge {
  position: absolute;
  bottom: 4px;
  right: 4px;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 1px 5px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  font-size: 0.55rem;
  color: white;
}

/* Connections Layer */
.bp-connections-layer {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
  z-index: 5;
}

.bp-connection-path {
  fill: none;
  stroke: #b197fc;
  stroke-width: 2;
  stroke-dasharray: 5 3;
  opacity: 0.5;
  pointer-events: stroke;
  cursor: pointer;
  transition: all 0.2s;
}

.bp-connection-path:hover,
.bp-connection-path.is-highlighted {
  stroke: #fcc419;
  stroke-width: 2.5;
  opacity: 1;
  stroke-dasharray: none;
}

.bp-connection-label {
  font-size: 9px;
  fill: var(--color-text-light);
  text-anchor: middle;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s;
}

.bp-connection-label.is-highlighted {
  opacity: 1;
  fill: #fcc419;
  font-weight: 600;
}

/* Legend */
.bp-legend {
  position: absolute;
  bottom: 16px;
  right: 16px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 10px 14px;
  z-index: 10;
}

.bp-legend__title {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-light);
  margin-bottom: 8px;
}

.bp-legend__items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bp-legend__item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.7rem;
  color: var(--color-text);
}

.bp-legend__color {
  width: 14px;
  height: 14px;
  border-radius: 3px;
}

.bp-legend__color--event { background: var(--color-event); }

.bp-legend__line {
  width: 18px;
  height: 2px;
  background: repeating-linear-gradient(
    90deg,
    #b197fc,
    #b197fc 3px,
    transparent 3px,
    transparent 6px
  );
}
</style>
