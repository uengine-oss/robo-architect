import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useBigPictureStore = defineStore('bigpicture', () => {
  // Timeline data
  const swimlanes = ref([])
  const crossBcConnections = ref([])
  
  // Swimlane order (array of bcIds) - used for drag reorder
  const swimlaneOrder = ref([])
  
  // Loading state
  const loading = ref(false)
  const error = ref(null)
  
  // Selection state
  const selectedEventId = ref(null)
  const hoveredEventId = ref(null)
  const hoveredConnectionId = ref(null)
  
  // Drag state
  const draggingSwimlaneId = ref(null)
  const draggingEventId = ref(null)
  const dragOverSwimlaneId = ref(null)
  const dragOverEventIndex = ref(null)
  
  // Filter state
  const selectedBcIds = ref([]) // Empty = show all
  const selectedActors = ref([]) // Empty = show all
  
  // Zoom/pan state
  const zoomLevel = ref(1)
  const panOffset = ref({ x: 0, y: 0 })
  
  // Summary statistics
  const summary = ref({
    totalBCs: 0,
    totalEvents: 0,
    totalPolicies: 0,
    bcStats: []
  })
  
  // Computed: ordered swimlanes based on swimlaneOrder
  const orderedSwimlanes = computed(() => {
    if (swimlaneOrder.value.length === 0) {
      return swimlanes.value
    }
    
    // Sort swimlanes by their position in swimlaneOrder
    const orderMap = new Map(swimlaneOrder.value.map((id, idx) => [id, idx]))
    return [...swimlanes.value].sort((a, b) => {
      const orderA = orderMap.get(a.bcId) ?? 999
      const orderB = orderMap.get(b.bcId) ?? 999
      return orderA - orderB
    })
  })
  
  // Computed: filtered and ordered swimlanes based on selection
  const filteredSwimlanes = computed(() => {
    let result = orderedSwimlanes.value
    
    if (selectedBcIds.value.length === 0 && selectedActors.value.length === 0) {
      return result
    }
    
    return result.filter(lane => {
      // Filter by BC
      if (selectedBcIds.value.length > 0 && !selectedBcIds.value.includes(lane.bcId)) {
        return false
      }
      
      // Filter by actors
      if (selectedActors.value.length > 0) {
        const hasMatchingActor = lane.actors.some(actor => 
          selectedActors.value.includes(actor)
        )
        if (!hasMatchingActor) return false
      }
      
      return true
    })
  })
  
  // Computed: all unique actors across swimlanes
  const allActors = computed(() => {
    const actors = new Set()
    swimlanes.value.forEach(lane => {
      lane.actors.forEach(actor => actors.add(actor))
    })
    return Array.from(actors).sort()
  })
  
  // Computed: all BCs for filter dropdown
  const allBCs = computed(() => {
    return swimlanes.value.map(lane => ({
      id: lane.bcId,
      name: lane.bcName
    }))
  })
  
  // Computed: total events count
  const totalEvents = computed(() => {
    return swimlanes.value.reduce((sum, lane) => sum + lane.events.length, 0)
  })
  
  // Computed: max sequence number (for timeline width calculation)
  const maxSequence = computed(() => {
    let max = 0
    swimlanes.value.forEach(lane => {
      lane.events.forEach(evt => {
        if (evt.sequence > max) max = evt.sequence
      })
    })
    return max
  })
  
  // Computed: filtered cross-BC connections
  const filteredConnections = computed(() => {
    if (selectedBcIds.value.length === 0) {
      return crossBcConnections.value
    }
    
    return crossBcConnections.value.filter(conn => {
      // Show connection only if both source and target BCs are visible
      return selectedBcIds.value.includes(conn.sourceBcId) && 
             selectedBcIds.value.includes(conn.targetBcId)
    })
  })
  
  // Computed: connections related to selected/hovered event
  const highlightedConnections = computed(() => {
    const targetId = selectedEventId.value || hoveredEventId.value
    if (!targetId) return []
    
    return crossBcConnections.value.filter(conn => 
      conn.sourceEventId === targetId || conn.targetEventId === targetId
    )
  })
  
  // Fetch timeline data from API
  async function fetchTimeline() {
    loading.value = true
    error.value = null
    
    try {
      const response = await fetch('/api/graph/bigpicture/timeline')
      if (!response.ok) {
        throw new Error(`Failed to fetch timeline: ${response.status}`)
      }
      
      const data = await response.json()
      swimlanes.value = data.swimlanes || []
      crossBcConnections.value = data.crossBcConnections || []
      
      // Initialize swimlane order
      swimlaneOrder.value = swimlanes.value.map(lane => lane.bcId)
      
      console.log(`[BigPicture] Loaded ${swimlanes.value.length} swimlanes, ${totalEvents.value} events, ${crossBcConnections.value.length} cross-BC connections`)
    } catch (e) {
      error.value = e.message
      console.error('[BigPicture] Failed to fetch timeline:', e)
    } finally {
      loading.value = false
    }
  }
  
  // Fetch summary statistics
  async function fetchSummary() {
    try {
      const response = await fetch('/api/graph/bigpicture/summary')
      if (!response.ok) {
        throw new Error(`Failed to fetch summary: ${response.status}`)
      }
      
      summary.value = await response.json()
    } catch (e) {
      console.error('[BigPicture] Failed to fetch summary:', e)
    }
  }
  
  // ==========================================
  // Swimlane Reorder Actions
  // ==========================================
  
  function startDraggingSwimlane(bcId) {
    draggingSwimlaneId.value = bcId
  }
  
  function stopDraggingSwimlane() {
    draggingSwimlaneId.value = null
    dragOverSwimlaneId.value = null
  }
  
  function setDragOverSwimlane(bcId) {
    dragOverSwimlaneId.value = bcId
  }
  
  function reorderSwimlane(fromBcId, toBcId) {
    if (fromBcId === toBcId) return
    
    const fromIndex = swimlaneOrder.value.indexOf(fromBcId)
    const toIndex = swimlaneOrder.value.indexOf(toBcId)
    
    if (fromIndex === -1 || toIndex === -1) return
    
    // Remove from old position and insert at new position
    const newOrder = [...swimlaneOrder.value]
    newOrder.splice(fromIndex, 1)
    newOrder.splice(toIndex, 0, fromBcId)
    
    swimlaneOrder.value = newOrder
    console.log('[BigPicture] Reordered swimlanes:', newOrder)
  }
  
  function moveSwimlaneToIndex(bcId, newIndex) {
    const currentIndex = swimlaneOrder.value.indexOf(bcId)
    if (currentIndex === -1 || currentIndex === newIndex) return
    
    const newOrder = [...swimlaneOrder.value]
    newOrder.splice(currentIndex, 1)
    newOrder.splice(newIndex, 0, bcId)
    
    swimlaneOrder.value = newOrder
  }
  
  // ==========================================
  // Event Reorder Actions
  // ==========================================
  
  function startDraggingEvent(eventId) {
    draggingEventId.value = eventId
  }
  
  function stopDraggingEvent() {
    draggingEventId.value = null
    dragOverEventIndex.value = null
  }
  
  function setDragOverEventIndex(index) {
    dragOverEventIndex.value = index
  }
  
  function reorderEventInSwimlane(bcId, fromIndex, toIndex) {
    if (fromIndex === toIndex) return
    
    const lane = swimlanes.value.find(l => l.bcId === bcId)
    if (!lane) return
    
    // Reorder events array
    const events = [...lane.events]
    const [moved] = events.splice(fromIndex, 1)
    events.splice(toIndex, 0, moved)
    
    // Update sequence numbers
    events.forEach((evt, idx) => {
      evt.sequence = idx + 1
    })
    
    lane.events = events
    
    // Trigger reactivity
    swimlanes.value = [...swimlanes.value]
    
    console.log(`[BigPicture] Reordered events in ${bcId}:`, events.map(e => e.name))
  }
  
  function moveEventToPosition(eventId, bcId, newSequence) {
    const lane = swimlanes.value.find(l => l.bcId === bcId)
    if (!lane) return
    
    const eventIndex = lane.events.findIndex(e => e.id === eventId)
    if (eventIndex === -1) return
    
    const targetIndex = Math.max(0, Math.min(newSequence - 1, lane.events.length - 1))
    
    if (eventIndex !== targetIndex) {
      reorderEventInSwimlane(bcId, eventIndex, targetIndex)
    }
  }
  
  // Move event by drag delta (for smooth dragging)
  function updateEventSequenceByDrag(eventId, bcId, deltaX, eventWidth) {
    const lane = swimlanes.value.find(l => l.bcId === bcId)
    if (!lane) return
    
    const eventIndex = lane.events.findIndex(e => e.id === eventId)
    if (eventIndex === -1) return
    
    // Calculate how many positions to move based on deltaX
    const positions = Math.round(deltaX / eventWidth)
    if (positions === 0) return
    
    const newIndex = Math.max(0, Math.min(eventIndex + positions, lane.events.length - 1))
    if (newIndex !== eventIndex) {
      reorderEventInSwimlane(bcId, eventIndex, newIndex)
    }
  }
  
  // ==========================================
  // Selection actions
  // ==========================================
  
  function selectEvent(eventId) {
    selectedEventId.value = eventId
  }
  
  function clearSelection() {
    selectedEventId.value = null
  }
  
  function setHoveredEvent(eventId) {
    hoveredEventId.value = eventId
  }
  
  function clearHover() {
    hoveredEventId.value = null
  }
  
  function setHoveredConnection(connectionId) {
    hoveredConnectionId.value = connectionId
  }
  
  function clearConnectionHover() {
    hoveredConnectionId.value = null
  }
  
  // Filter actions
  function setSelectedBCs(bcIds) {
    selectedBcIds.value = bcIds || []
  }
  
  function toggleBCFilter(bcId) {
    const idx = selectedBcIds.value.indexOf(bcId)
    if (idx >= 0) {
      selectedBcIds.value.splice(idx, 1)
    } else {
      selectedBcIds.value.push(bcId)
    }
    selectedBcIds.value = [...selectedBcIds.value]
  }
  
  function setSelectedActors(actors) {
    selectedActors.value = actors || []
  }
  
  function toggleActorFilter(actor) {
    const idx = selectedActors.value.indexOf(actor)
    if (idx >= 0) {
      selectedActors.value.splice(idx, 1)
    } else {
      selectedActors.value.push(actor)
    }
    selectedActors.value = [...selectedActors.value]
  }
  
  function clearFilters() {
    selectedBcIds.value = []
    selectedActors.value = []
  }
  
  // Zoom actions
  function setZoom(level) {
    zoomLevel.value = Math.max(0.25, Math.min(2, level))
  }
  
  function zoomIn() {
    setZoom(zoomLevel.value + 0.1)
  }
  
  function zoomOut() {
    setZoom(zoomLevel.value - 0.1)
  }
  
  function resetZoom() {
    zoomLevel.value = 1
    panOffset.value = { x: 0, y: 0 }
  }
  
  function setPan(offset) {
    panOffset.value = offset
  }
  
  // Get event by ID
  function getEventById(eventId) {
    for (const lane of swimlanes.value) {
      const event = lane.events.find(e => e.id === eventId)
      if (event) return { event, bcId: lane.bcId, bcName: lane.bcName }
    }
    return null
  }
  
  // Get swimlane by BC ID
  function getSwimlaneByBcId(bcId) {
    return swimlanes.value.find(lane => lane.bcId === bcId)
  }
  
  // Get swimlane index in display order
  function getSwimlaneDisplayIndex(bcId) {
    return filteredSwimlanes.value.findIndex(lane => lane.bcId === bcId)
  }
  
  // Get event index within its swimlane
  function getEventIndexInSwimlane(eventId) {
    for (const lane of swimlanes.value) {
      const index = lane.events.findIndex(e => e.id === eventId)
      if (index !== -1) {
        return { bcId: lane.bcId, index }
      }
    }
    return null
  }
  
  // Check if an event triggers cross-BC policies
  function hasOutgoingConnections(eventId) {
    return crossBcConnections.value.some(conn => conn.sourceEventId === eventId)
  }
  
  // Check if an event is triggered by cross-BC policies
  function hasIncomingConnections(eventId) {
    return crossBcConnections.value.some(conn => conn.targetEventId === eventId)
  }
  
  // Clear all data
  function clearData() {
    swimlanes.value = []
    crossBcConnections.value = []
    swimlaneOrder.value = []
    selectedEventId.value = null
    hoveredEventId.value = null
    draggingSwimlaneId.value = null
    draggingEventId.value = null
    error.value = null
    clearFilters()
    resetZoom()
  }
  
  return {
    // State
    swimlanes,
    crossBcConnections,
    swimlaneOrder,
    loading,
    error,
    selectedEventId,
    hoveredEventId,
    hoveredConnectionId,
    draggingSwimlaneId,
    draggingEventId,
    dragOverSwimlaneId,
    dragOverEventIndex,
    selectedBcIds,
    selectedActors,
    zoomLevel,
    panOffset,
    summary,
    
    // Computed
    orderedSwimlanes,
    filteredSwimlanes,
    filteredConnections,
    highlightedConnections,
    allActors,
    allBCs,
    totalEvents,
    maxSequence,
    
    // Swimlane Reorder Actions
    startDraggingSwimlane,
    stopDraggingSwimlane,
    setDragOverSwimlane,
    reorderSwimlane,
    moveSwimlaneToIndex,
    
    // Event Reorder Actions
    startDraggingEvent,
    stopDraggingEvent,
    setDragOverEventIndex,
    reorderEventInSwimlane,
    moveEventToPosition,
    updateEventSequenceByDrag,
    
    // Other Actions
    fetchTimeline,
    fetchSummary,
    selectEvent,
    clearSelection,
    setHoveredEvent,
    clearHover,
    setHoveredConnection,
    clearConnectionHover,
    setSelectedBCs,
    toggleBCFilter,
    setSelectedActors,
    toggleActorFilter,
    clearFilters,
    setZoom,
    zoomIn,
    zoomOut,
    resetZoom,
    setPan,
    getEventById,
    getSwimlaneByBcId,
    getSwimlaneDisplayIndex,
    getEventIndexInSwimlane,
    hasOutgoingConnections,
    hasIncomingConnections,
    clearData
  }
})
