import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAggregateViewerStore = defineStore('aggregateViewer', () => {
  // Data from API
  const boundedContexts = ref([])
  const loading = ref(false)
  const error = ref(null)

  // Selected BC IDs (for filtering)
  const selectedBcIds = ref(new Set())

  // Selected node for editing
  const selectedNodeId = ref(null)
  const selectedNodeType = ref(null) // 'aggregate' | 'enum' | 'valueObject'

  // Fetch aggregates for a specific BC
  async function fetchAggregatesForBC(bcId) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`/api/contexts/${bcId}/full-tree`)
      if (!response.ok) {
        throw new Error(`Failed to fetch aggregates: ${response.statusText}`)
      }
      const data = await response.json()
      
      // Extract BC info and aggregates
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
      
      // Add or update BC in boundedContexts
      const existingIndex = boundedContexts.value.findIndex(b => b.id === bcId)
      if (existingIndex >= 0) {
        boundedContexts.value[existingIndex] = bc
      } else {
        boundedContexts.value.push(bc)
      }
      
      // Add to selected BCs
      selectedBcIds.value.add(bcId)
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch aggregates:', err)
    } finally {
      loading.value = false
    }
  }

  // Remove BC from viewer
  function removeBC(bcId) {
    selectedBcIds.value.delete(bcId)
    boundedContexts.value = boundedContexts.value.filter(bc => bc.id !== bcId)
  }

  // Clear all selected BCs
  function clearAllBCs() {
    selectedBcIds.value.clear()
    boundedContexts.value = []
  }

  // Get filtered bounded contexts (only selected ones)
  const filteredBoundedContexts = computed(() => {
    if (selectedBcIds.value.size === 0) {
      return []
    }
    return boundedContexts.value.filter(bc => selectedBcIds.value.has(bc.id))
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
    selectedNodeId,
    selectedNodeType,
    filteredBoundedContexts,
    totalAggregates,
    totalEnumerations,
    totalValueObjects,
    fetchAllAggregates,
    fetchAggregatesForBC,
    removeBC,
    clearAllBCs,
    updateAggregateEnumVo,
    updateAggregateProperties,
    getAggregateById,
    selectNode,
    clearSelection,
  }
})
