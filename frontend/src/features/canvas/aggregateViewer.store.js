import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAggregateViewerStore = defineStore('aggregateViewer', () => {
  // Data from API
  const boundedContexts = ref([])
  const loading = ref(false)
  const error = ref(null)

  // Selected BC IDs (for filtering)
  const selectedBcIds = ref(new Set())

  // Aggregate-level visibility filter: ids of aggregates currently shown on
  // the canvas. Lets the viewer show a single aggregate, not the whole BC.
  const visibleAggregateIds = ref(new Set())

  // One-shot cross-tab focus intent: { aggregateId, bcId } | null
  const pendingFocus = ref(null)

  // Selected node for editing
  const selectedNodeId = ref(null)
  const selectedNodeType = ref(null) // 'aggregate' | 'enum' | 'valueObject'

  // Load a BC's full tree into state without changing aggregate visibility.
  async function loadBcTree(bcId) {
    const response = await fetch(`/api/contexts/${bcId}/full-tree`)
    if (!response.ok) {
      throw new Error(`Failed to fetch aggregates: ${response.statusText}`)
    }
    const data = await response.json()

    const bc = {
      id: data.id,
      name: data.name,
      displayName: data.displayName || data.name,
      description: data.description,
      aggregates: (data.aggregates || []).map(agg => ({
        id: agg.id,
        name: agg.name,
        displayName: agg.displayName || agg.name,
        rootEntity: agg.rootEntity,
        invariants: agg.invariants || [],
        enumerations: agg.enumerations || [],
        valueObjects: agg.valueObjects || [],
        properties: agg.properties || []
      }))
    }

    const existingIndex = boundedContexts.value.findIndex(b => b.id === bcId)
    if (existingIndex >= 0) {
      boundedContexts.value[existingIndex] = bc
    } else {
      boundedContexts.value.push(bc)
    }
    selectedBcIds.value.add(bcId)
    return bc
  }

  // Resolve the owning BoundedContext id for an aggregate via the graph.
  async function resolveBcId(aggregateId) {
    const response = await fetch(`/api/graph/expand-with-bc/${aggregateId}`)
    if (!response.ok) {
      throw new Error(`Failed to resolve bounded context: ${response.statusText}`)
    }
    const data = await response.json()
    const nodes = data.nodes || []
    const bcNode = nodes.find(n => n.type === 'BoundedContext')
    const aggNode = nodes.find(n => n.id === aggregateId)
    return bcNode?.id || aggNode?.bcId || null
  }

  // Fetch a whole BC and make all of its aggregates visible.
  async function fetchAggregatesForBC(bcId) {
    loading.value = true
    error.value = null
    try {
      const bc = await loadBcTree(bcId)
      bc.aggregates.forEach(agg => {
        if (agg.id) visibleAggregateIds.value.add(agg.id)
      })
      visibleAggregateIds.value = new Set(visibleAggregateIds.value)
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch aggregates:', err)
    } finally {
      loading.value = false
    }
  }

  // Fetch a single aggregate and make only it visible (additive, de-duplicated).
  async function fetchAggregate(aggregateId, bcId = null) {
    if (!aggregateId) return
    loading.value = true
    error.value = null
    try {
      let resolvedBcId = bcId
      if (!resolvedBcId) {
        resolvedBcId = await resolveBcId(aggregateId)
      }
      if (!resolvedBcId) {
        throw new Error('Could not determine the bounded context for this aggregate')
      }

      const alreadyLoaded = boundedContexts.value.find(b => b.id === resolvedBcId)
      const bc = alreadyLoaded || await loadBcTree(resolvedBcId)

      const found = bc.aggregates?.some(a => a.id === aggregateId)
      if (!found) {
        throw new Error('Aggregate not found in its bounded context')
      }

      visibleAggregateIds.value.add(aggregateId)
      visibleAggregateIds.value = new Set(visibleAggregateIds.value)
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch aggregate:', err)
    } finally {
      loading.value = false
    }
  }

  // Set / consume a one-shot cross-tab focus target.
  function focusAggregate(aggregateId, bcId = null) {
    if (!aggregateId) return
    pendingFocus.value = { aggregateId, bcId: bcId || null }
  }

  function consumeFocus() {
    const target = pendingFocus.value
    pendingFocus.value = null
    return target
  }

  // Remove BC from viewer
  function removeBC(bcId) {
    selectedBcIds.value.delete(bcId)
    boundedContexts.value = boundedContexts.value.filter(bc => bc.id !== bcId)
  }

  // Clear all selected BCs
  function clearAllBCs() {
    selectedBcIds.value.clear()
    visibleAggregateIds.value = new Set()
    pendingFocus.value = null
    boundedContexts.value = []
  }

  // Get filtered bounded contexts (selected BCs, aggregates gated by visibility)
  const filteredBoundedContexts = computed(() => {
    if (selectedBcIds.value.size === 0) {
      return []
    }
    return boundedContexts.value
      .filter(bc => selectedBcIds.value.has(bc.id))
      .map(bc => ({
        ...bc,
        aggregates: (bc.aggregates || []).filter(agg => visibleAggregateIds.value.has(agg.id))
      }))
      .filter(bc => bc.aggregates.length > 0)
  })

  // Fetch all aggregates with VO/Enum/Properties (deprecated - use fetchAggregatesForBC instead)
  async function fetchAllAggregates() {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/contexts/aggregates/viewer')
      if (!response.ok) {
        throw new Error(`Failed to fetch aggregates: ${response.statusText}`)
      }
      const data = await response.json()
      boundedContexts.value = data.boundedContexts || []
      // Add all BC IDs to selected
      data.boundedContexts?.forEach(bc => {
        if (bc.id) selectedBcIds.value.add(bc.id)
      })
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch aggregates:', err)
    } finally {
      loading.value = false
    }
  }

  // Update aggregate enumerations and value objects
  async function updateAggregateEnumVo(aggregateId, enumerations, valueObjects) {
    try {
      const response = await fetch(`/api/contexts/aggregates/${aggregateId}/enumerations-valueobjects`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          enumerations: enumerations || [],
          value_objects: valueObjects || [],
        }),
      })
      if (!response.ok) {
        throw new Error(`Failed to update aggregate: ${response.statusText}`)
      }
      const updated = await response.json()
      
      // Update local state
      for (const bc of boundedContexts.value) {
        const agg = bc.aggregates?.find(a => a.id === aggregateId)
        if (agg) {
          agg.enumerations = updated.enumerations || []
          agg.valueObjects = updated.valueObjects || []
          break
        }
      }
      
      return updated
    } catch (err) {
      console.error('Failed to update aggregate:', err)
      throw err
    }
  }

  // Update aggregate properties
  async function updateAggregateProperties(aggregateId, properties) {
    try {
      const response = await fetch(`/api/contexts/aggregates/${aggregateId}/properties`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          properties: properties || [],
        }),
      })
      if (!response.ok) {
        throw new Error(`Failed to update aggregate properties: ${response.statusText}`)
      }
      const updated = await response.json()
      
      // Update local state
      for (const bc of boundedContexts.value) {
        const agg = bc.aggregates?.find(a => a.id === aggregateId)
        if (agg) {
          agg.properties = updated.properties || []
          break
        }
      }
      
      return updated
    } catch (err) {
      console.error('Failed to update aggregate properties:', err)
      throw err
    }
  }

  // Get aggregate by ID
  function getAggregateById(aggregateId) {
    for (const bc of boundedContexts.value) {
      const agg = bc.aggregates?.find(a => a.id === aggregateId)
      if (agg) {
        return { aggregate: agg, boundedContext: bc }
      }
    }
    return null
  }

  // Select node for editing
  function selectNode(nodeId, nodeType) {
    selectedNodeId.value = nodeId
    selectedNodeType.value = nodeType
  }

  function clearSelection() {
    selectedNodeId.value = null
    selectedNodeType.value = null
  }

  // Computed: total aggregates count
  const totalAggregates = computed(() => {
    return boundedContexts.value.reduce((sum, bc) => sum + (bc.aggregates?.length || 0), 0)
  })

  // Computed: total enumerations count
  const totalEnumerations = computed(() => {
    return boundedContexts.value.reduce((sum, bc) => {
      const bcEnums = bc.aggregates?.reduce((aggSum, agg) => {
        return aggSum + (agg.enumerations?.length || 0)
      }, 0) || 0
      return sum + bcEnums
    }, 0)
  })

  // Computed: total value objects count
  const totalValueObjects = computed(() => {
    return boundedContexts.value.reduce((sum, bc) => {
      const bcVos = bc.aggregates?.reduce((aggSum, agg) => {
        return aggSum + (agg.valueObjects?.length || 0)
      }, 0) || 0
      return sum + bcVos
    }, 0)
  })

  return {
    boundedContexts,
    loading,
    error,
    selectedBcIds,
    visibleAggregateIds,
    pendingFocus,
    selectedNodeId,
    selectedNodeType,
    filteredBoundedContexts,
    totalAggregates,
    totalEnumerations,
    totalValueObjects,
    fetchAllAggregates,
    fetchAggregatesForBC,
    fetchAggregate,
    focusAggregate,
    consumeFocus,
    removeBC,
    clearAllBCs,
    updateAggregateEnumVo,
    updateAggregateProperties,
    getAggregateById,
    selectNode,
    clearSelection,
  }
})
