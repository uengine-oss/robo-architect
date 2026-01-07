import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useBigPictureStore = defineStore('bigpicture', () => {
  // Loading and error state
  const loading = ref(false)
  const error = ref(null)
  
  // Swimlanes data (each swimlane represents a Bounded Context)
  const swimlanes = ref([])
  
  // All BCs for filter dropdown
  const allBCs = ref([])
  
  // Selected BC IDs for filtering
  const selectedBcIds = ref([])
  
  // Connections between events across BCs
  const connections = ref([])
  
  // Zoom level
  const zoomLevel = ref(1)
  
  // Selection state
  const selectedEventId = ref(null)
  const hoveredEventId = ref(null)
  const hoveredConnectionId = ref(null)
  
  // Drag state for swimlanes
  const draggingSwimlaneId = ref(null)
  const dragOverSwimlaneId = ref(null)
  
  // Drag state for events
  const draggingEventId = ref(null)
  const dragOverEventIndex = ref(null)
  
  // View mode
  const viewMode = ref('timeline') // 'timeline' or 'flow'
  
  // Computed: filtered swimlanes based on selected BCs
  const filteredSwimlanes = computed(() => {
    if (selectedBcIds.value.length === 0) {
      return swimlanes.value
    }
    return swimlanes.value.filter(lane => selectedBcIds.value.includes(lane.bcId))
  })
  
  // Computed: max sequence number across all events
  const maxSequence = computed(() => {
    let max = 1
    swimlanes.value.forEach(lane => {
      lane.events.forEach(evt => {
        if (evt.sequence > max) max = evt.sequence
      })
    })
    return max
  })
  
  // Computed: filtered connections (only show connections between visible swimlanes)
  const filteredConnections = computed(() => {
    const visibleBcIds = new Set(filteredSwimlanes.value.map(lane => lane.bcId))
    return connections.value.filter(conn => {
      const sourceEvent = findEventById(conn.sourceEventId)
      const targetEvent = findEventById(conn.targetEventId)
      if (!sourceEvent || !targetEvent) return false
      return visibleBcIds.has(sourceEvent.bcId) && visibleBcIds.has(targetEvent.bcId)
    })
  })
  
  // Computed: cross-BC connections (connections between different BCs)
  const crossBcConnections = computed(() => {
    return connections.value.filter(conn => conn.type === 'cross-bc')
  })
  
  // Computed: same-BC connections
  const sameBcConnections = computed(() => {
    return connections.value.filter(conn => conn.type === 'same-bc')
  })
  
  // Computed: total events count
  const totalEvents = computed(() => {
    return swimlanes.value.reduce((sum, lane) => sum + lane.events.length, 0)
  })
  
  // Computed: events grouped by actor across all BCs
  const eventsByActor = computed(() => {
    const actorMap = {}
    swimlanes.value.forEach(lane => {
      lane.events.forEach(evt => {
        const actor = evt.actor || 'System'
        if (!actorMap[actor]) {
          actorMap[actor] = []
        }
        actorMap[actor].push({
          ...evt,
          bcId: lane.bcId,
          bcName: lane.bcName
        })
      })
    })
    return actorMap
  })
  
  // Computed: all unique actors
  const allActors = computed(() => {
    const actors = new Set()
    swimlanes.value.forEach(lane => {
      (lane.actors || []).forEach(actor => actors.add(actor))
      lane.events.forEach(evt => {
        if (evt.actor) actors.add(evt.actor)
      })
    })
    return Array.from(actors).sort()
  })
  
  // Computed: highlighted connections (when hovering over an event)
  const highlightedConnections = computed(() => {
    if (!hoveredEventId.value) return []
    return connections.value.filter(conn => 
      conn.sourceEventId === hoveredEventId.value || 
      conn.targetEventId === hoveredEventId.value
    )
  })
  
  // Computed: event chain from a source event (Event → Policy → Command → Event)
  const getEventChain = computed(() => {
    return (eventId) => {
      const chain = []
      const visited = new Set()
      
      function traverse(id) {
        if (visited.has(id)) return
        visited.add(id)
        
        const outgoing = connections.value.filter(c => c.sourceEventId === id)
        outgoing.forEach(conn => {
          chain.push(conn)
          if (conn.targetEventId) {
            traverse(conn.targetEventId)
          }
        })
      }
      
      traverse(eventId)
      return chain
    }
  })
  
  // Helper function to find event by ID
  function findEventById(eventId) {
    for (const lane of swimlanes.value) {
      const event = lane.events.find(evt => evt.id === eventId)
      if (event) {
        return { ...event, bcId: lane.bcId, bcName: lane.bcName }
      }
    }
    return null
  }
  
  // Get swimlane by BC ID
  function getSwimlaneByBcId(bcId) {
    return swimlanes.value.find(lane => lane.bcId === bcId)
  }
  
  // Check if event has outgoing connections
  function hasOutgoingConnections(eventId) {
    return connections.value.some(conn => conn.sourceEventId === eventId)
  }
  
  // Check if event has incoming connections
  function hasIncomingConnections(eventId) {
    return connections.value.some(conn => conn.targetEventId === eventId)
  }
  
  // Get connected events for an event
  function getConnectedEvents(eventId) {
    const connected = {
      outgoing: [],
      incoming: []
    }
    
    connections.value.forEach(conn => {
      if (conn.sourceEventId === eventId && conn.targetEventId) {
        const targetEvt = findEventById(conn.targetEventId)
        if (targetEvt) {
          connected.outgoing.push({
            event: targetEvt,
            policyName: conn.policyName,
            type: conn.type
          })
        }
      }
      if (conn.targetEventId === eventId && conn.sourceEventId) {
        const sourceEvt = findEventById(conn.sourceEventId)
        if (sourceEvt) {
          connected.incoming.push({
            event: sourceEvt,
            policyName: conn.policyName,
            type: conn.type
          })
        }
      }
    })
    
    return connected
  }
  
  // Selection actions
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
  
  // Zoom actions
  function zoomIn() {
    zoomLevel.value = Math.min(zoomLevel.value + 0.1, 2.5)
  }
  
  function zoomOut() {
    zoomLevel.value = Math.max(zoomLevel.value - 0.1, 0.3)
  }
  
  function resetZoom() {
    zoomLevel.value = 1
  }
  
  function setZoom(level) {
    zoomLevel.value = Math.max(0.3, Math.min(2.5, level))
  }
  
  // Filter actions
  function toggleBCFilter(bcId) {
    const index = selectedBcIds.value.indexOf(bcId)
    if (index === -1) {
      selectedBcIds.value.push(bcId)
    } else {
      selectedBcIds.value.splice(index, 1)
    }
  }
  
  function clearFilters() {
    selectedBcIds.value = []
  }
  
  function setFilters(bcIds) {
    selectedBcIds.value = [...bcIds]
  }
  
  // Swimlane drag actions
  function startDraggingSwimlane(bcId) {
    draggingSwimlaneId.value = bcId
  }
  
  function setDragOverSwimlane(bcId) {
    dragOverSwimlaneId.value = bcId
  }
  
  function stopDraggingSwimlane() {
    draggingSwimlaneId.value = null
    dragOverSwimlaneId.value = null
  }
  
  function reorderSwimlane(fromBcId, toBcId) {
    const fromIndex = swimlanes.value.findIndex(lane => lane.bcId === fromBcId)
    const toIndex = swimlanes.value.findIndex(lane => lane.bcId === toBcId)
    
    if (fromIndex === -1 || toIndex === -1) return
    
    const [removed] = swimlanes.value.splice(fromIndex, 1)
    swimlanes.value.splice(toIndex, 0, removed)
  }
  
  // Event drag actions
  function startDraggingEvent(eventId) {
    draggingEventId.value = eventId
  }
  
  function setDragOverEventIndex(index) {
    dragOverEventIndex.value = index
  }
  
  function stopDraggingEvent() {
    draggingEventId.value = null
    dragOverEventIndex.value = null
  }
  
  function reorderEventInSwimlane(bcId, fromIndex, toIndex) {
    const lane = swimlanes.value.find(l => l.bcId === bcId)
    if (!lane) return
    
    if (fromIndex < 0 || fromIndex >= lane.events.length) return
    if (toIndex < 0 || toIndex >= lane.events.length) return
    
    const [removed] = lane.events.splice(fromIndex, 1)
    lane.events.splice(toIndex, 0, removed)
    
    // Update sequence numbers after reorder
    lane.events.forEach((evt, idx) => {
      evt.sequence = idx + 1
    })
  }
  
  // View mode
  function setViewMode(mode) {
    viewMode.value = mode
  }
  
  // Fetch timeline data from API
  async function fetchTimeline() {
    loading.value = true
    error.value = null
    
    try {
      const response = await fetch('/api/graph/bigpicture-timeline')
      
      if (!response.ok) {
        throw new Error(`Failed to fetch timeline: ${response.statusText}`)
      }
      
      const data = await response.json()
      
      // Update store with fetched data
      swimlanes.value = data.swimlanes || []
      connections.value = data.connections || []
      allBCs.value = data.allBCs || swimlanes.value.map(lane => ({
        id: lane.bcId,
        name: lane.bcName
      }))
      
      // Sort events within each swimlane by sequence
      swimlanes.value.forEach(lane => {
        lane.events.sort((a, b) => a.sequence - b.sequence)
      })
      
    } catch (err) {
      console.error('Error fetching big picture timeline:', err)
      error.value = err.message || 'Failed to load timeline data'
    } finally {
      loading.value = false
    }
  }
  
  // Get statistics
  function getStatistics() {
    return {
      totalBCs: swimlanes.value.length,
      filteredBCs: filteredSwimlanes.value.length,
      totalEvents: totalEvents.value,
      crossBcConnections: crossBcConnections.value.length,
      sameBcConnections: sameBcConnections.value.length,
      totalConnections: connections.value.length,
      actors: allActors.value.length,
      maxSequence: maxSequence.value
    }
  }
  
  // Reset store
  function reset() {
    swimlanes.value = []
    connections.value = []
    allBCs.value = []
    selectedBcIds.value = []
    zoomLevel.value = 1
    selectedEventId.value = null
    hoveredEventId.value = null
    hoveredConnectionId.value = null
    loading.value = false
    error.value = null
    viewMode.value = 'timeline'
  }
  
  return {
    // State
    loading,
    error,
    swimlanes,
    allBCs,
    selectedBcIds,
    connections,
    zoomLevel,
    selectedEventId,
    hoveredEventId,
    hoveredConnectionId,
    draggingSwimlaneId,
    dragOverSwimlaneId,
    draggingEventId,
    dragOverEventIndex,
    viewMode,
    
    // Computed
    filteredSwimlanes,
    maxSequence,
    filteredConnections,
    crossBcConnections,
    sameBcConnections,
    totalEvents,
    eventsByActor,
    allActors,
    highlightedConnections,
    getEventChain,
    
    // Methods
    findEventById,
    getSwimlaneByBcId,
    hasOutgoingConnections,
    hasIncomingConnections,
    getConnectedEvents,
    selectEvent,
    clearSelection,
    setHoveredEvent,
    clearHover,
    setHoveredConnection,
    clearConnectionHover,
    zoomIn,
    zoomOut,
    resetZoom,
    setZoom,
    toggleBCFilter,
    clearFilters,
    setFilters,
    startDraggingSwimlane,
    setDragOverSwimlane,
    stopDraggingSwimlane,
    reorderSwimlane,
    startDraggingEvent,
    setDragOverEventIndex,
    stopDraggingEvent,
    reorderEventInSwimlane,
    setViewMode,
    fetchTimeline,
    getStatistics,
    reset
  }
})
