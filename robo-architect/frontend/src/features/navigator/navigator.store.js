import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createLogger, newOpId } from '@/app/logging/logger'

export const useNavigatorStore = defineStore('navigator', () => {
  const log = createLogger({ scope: 'NavigatorStore' })
  const contexts = ref([])
  const contextTrees = ref({})
  const userStories = ref([])  // Unassigned user stories at root level
  const loading = ref(false)
  const error = ref(null)
  
  // Expanded state for tree nodes
  const expandedNodes = ref(new Set())
  
  // Newly added items (for animation highlighting)
  const newlyAddedIds = ref(new Set())
  
  // Track user story assignments (for animation)
  const userStoryAssignments = ref({})  // { usId: bcId }
  
  // Fetch unassigned user stories
  async function fetchUserStories() {
    try {
      const response = await fetch('/api/user-stories/unassigned')
      if (!response.ok) throw new Error('Failed to fetch user stories')
      userStories.value = await response.json()
    } catch (e) {
      log.error(
        'navigator_fetch_user_stories_failed',
        'Failed to fetch unassigned user stories; Navigator root list may be stale.',
        { errorMessage: e?.message || String(e) }
      )
    }
  }
  
  // Fetch all bounded contexts
  async function fetchContexts() {
    loading.value = true
    error.value = null
    
    try {
      const response = await fetch('/api/contexts')
      if (!response.ok) throw new Error('Failed to fetch contexts')
      contexts.value = await response.json()
    } catch (e) {
      error.value = e.message
      log.error(
        'navigator_fetch_contexts_failed',
        'Failed to fetch bounded contexts; Navigator may be incomplete.',
        { errorMessage: e?.message || String(e) }
      )
    } finally {
      loading.value = false
    }
  }
  
  // Fetch tree for a specific context
  async function fetchContextTree(contextId, forceRefresh = false) {
    if (!forceRefresh && contextTrees.value[contextId]) {
      return contextTrees.value[contextId]
    }
    
    try {
      const response = await fetch(`/api/contexts/${contextId}/full-tree`)
      if (!response.ok) throw new Error('Failed to fetch context tree')
      const tree = await response.json()
      contextTrees.value[contextId] = tree
      return tree
    } catch (e) {
      log.error(
        'navigator_fetch_context_tree_failed',
        'Failed to fetch context tree; this bounded context may appear empty until retry.',
        { contextId, forceRefresh, errorMessage: e?.message || String(e) }
      )
      return null
    }
  }
  
  // Add a user story to root level (during ingestion)
  function addUserStory(usData) {
    const exists = userStories.value.some(us => us.id === usData.id)
    if (!exists) {
      userStories.value.push({
        id: usData.id,
        role: usData.role,
        action: usData.action,
        benefit: usData.benefit,
        priority: usData.priority,
        type: 'UserStory',
        name: usData.name || `${usData.role}: ${usData.action?.substring(0, 30)}...`
      })
      
      // Mark as newly added
      markAsNew(usData.id)
    }
  }

  function ensureTree(bcId) {
    if (!contextTrees.value[bcId]) {
      contextTrees.value[bcId] = {
        id: bcId,
        aggregates: [],
        policies: [],
        userStories: [],
        readmodels: [],
        uis: []
      }
    } else {
      const t = contextTrees.value[bcId]
      if (!t.aggregates) t.aggregates = []
      if (!t.policies) t.policies = []
      if (!t.userStories) t.userStories = []
      if (!t.readmodels) t.readmodels = []
      if (!t.uis) t.uis = []
    }
    return contextTrees.value[bcId]
  }
  
  // Dynamically add a context (used during ingestion)
  function addContext(contextData) {
    // Check if context already exists
    const exists = contexts.value.some(c => c.id === contextData.id)
    if (!exists) {
      contexts.value.push({
        id: contextData.id,
        name: contextData.name,
        description: contextData.description,
        aggregateCount: 0,
        userStoryCount: 0,
        userStoryIds: contextData.userStoryIds || []
      })
      
      // Mark as newly added for animation
      markAsNew(contextData.id)
      
      // Auto-expand the new context
      expandedNodes.value.add(contextData.id)
      expandedNodes.value = new Set(expandedNodes.value)
    }
  }
  
  // Assign user story to a BC (move from root to BC)
  function assignUserStoryToBC(usId, bcId, bcName) {
    // Track the assignment
    userStoryAssignments.value[usId] = bcId
    
    // Remove from root level user stories
    const usIndex = userStories.value.findIndex(us => us.id === usId)
    if (usIndex !== -1) {
      userStories.value.splice(usIndex, 1)
    }
    
    // Update BC's userStoryCount
    const bc = contexts.value.find(c => c.id === bcId)
    if (bc) {
      bc.userStoryCount = (bc.userStoryCount || 0) + 1
    }
    
    // Mark the user story as newly added (will appear under BC)
    markAsNew(usId)
  }
  
  // Helper to mark item as newly added
  function markAsNew(itemId) {
    newlyAddedIds.value.add(itemId)
    newlyAddedIds.value = new Set(newlyAddedIds.value)
    
    // Clear the flag after animation
    setTimeout(() => {
      newlyAddedIds.value.delete(itemId)
      newlyAddedIds.value = new Set(newlyAddedIds.value)
    }, 2000)
  }
  
  // Dynamically add an Aggregate to a BC's tree (used during ingestion)
  function addAggregate(aggregateData) {
    const bcId = aggregateData.parentId
    
    // Ensure the tree exists
    ensureTree(bcId)
    
    // Check if already exists
    const tree = contextTrees.value[bcId]
    const exists = tree.aggregates?.some(a => a.id === aggregateData.id)
    if (!exists) {
      if (!tree.aggregates) tree.aggregates = []
      tree.aggregates.push({
        id: aggregateData.id,
        name: aggregateData.name,
        type: 'Aggregate',
        commands: [],
        events: []
      })
      
      // Force reactivity update
      contextTrees.value = { ...contextTrees.value }
      
      // Update BC's aggregate count
      const bc = contexts.value.find(c => c.id === bcId)
      if (bc) {
        bc.aggregateCount = (bc.aggregateCount || 0) + 1
      }
      
      // Mark as newly added and expand BC
      markAsNew(aggregateData.id)
      expandedNodes.value.add(bcId)
      expandedNodes.value = new Set(expandedNodes.value)
    }
  }
  
  // Dynamically add a Command to an Aggregate (used during ingestion)
  function addCommand(commandData) {
    const aggId = commandData.parentId
    
    // Find the aggregate in any BC's tree
    for (const bcId in contextTrees.value) {
      const tree = contextTrees.value[bcId]
      const aggregate = tree.aggregates?.find(a => a.id === aggId)
      
      if (aggregate) {
        const exists = aggregate.commands?.some(c => c.id === commandData.id)
        if (!exists) {
          if (!aggregate.commands) aggregate.commands = []
          aggregate.commands.push({
            id: commandData.id,
            name: commandData.name,
            type: 'Command',
            events: []
          })
          
          // Force reactivity update
          contextTrees.value = { ...contextTrees.value }
          
          // Mark as newly added and expand aggregate
          markAsNew(commandData.id)
          expandedNodes.value.add(aggId)
          expandedNodes.value = new Set(expandedNodes.value)
        }
        break
      }
    }
  }
  
  // Dynamically add an Event to a Command or Aggregate (used during ingestion)
  function addEvent(eventData) {
    const parentId = eventData.parentId  // Can be command ID or aggregate ID
    
    // Find the parent (command or aggregate) in any BC's tree
    for (const bcId in contextTrees.value) {
      const tree = contextTrees.value[bcId]
      
      for (const aggregate of (tree.aggregates || [])) {
        // Check if parentId is a command
        const command = aggregate.commands?.find(c => c.id === parentId)
        if (command) {
          const exists = command.events?.some(e => e.id === eventData.id)
          if (!exists) {
            if (!command.events) command.events = []
            command.events.push({
              id: eventData.id,
              name: eventData.name,
              type: 'Event'
            })
            
            // Also add to aggregate's events for better visibility
            if (!aggregate.events) aggregate.events = []
            if (!aggregate.events.some(e => e.id === eventData.id)) {
              aggregate.events.push({
                id: eventData.id,
                name: eventData.name,
                type: 'Event'
              })
            }
            
            // Force reactivity update
            contextTrees.value = { ...contextTrees.value }
            
            markAsNew(eventData.id)
            expandedNodes.value.add(parentId)
            expandedNodes.value = new Set(expandedNodes.value)
          }
          return
        }
        
        // Check if parentId is the aggregate itself
        if (aggregate.id === parentId) {
          const exists = aggregate.events?.some(e => e.id === eventData.id)
          if (!exists) {
            if (!aggregate.events) aggregate.events = []
            aggregate.events.push({
              id: eventData.id,
              name: eventData.name,
              type: 'Event'
            })
            
            // Force reactivity update
            contextTrees.value = { ...contextTrees.value }
            
            markAsNew(eventData.id)
          }
          return
        }
      }
    }
  }
  
  // Dynamically add a Policy to a BC (used during ingestion)
  function addPolicy(policyData) {
    const bcId = policyData.parentId
    
    // Ensure the tree exists
    ensureTree(bcId)
    
    const tree = contextTrees.value[bcId]
    const exists = tree.policies?.some(p => p.id === policyData.id)
    if (!exists) {
      if (!tree.policies) tree.policies = []
      tree.policies.push({
        id: policyData.id,
        name: policyData.name,
        type: 'Policy'
      })
      
      // Force reactivity update
      contextTrees.value = { ...contextTrees.value }
      
      markAsNew(policyData.id)
    }

  // Dynamically add a ReadModel to a BC's tree (used during ingestion / streaming)
  function addReadModel(readModelData) {
    const bcId = readModelData.parentId || readModelData.bcId
    if (!bcId) return

    const tree = ensureTree(bcId)
    const exists = tree.readmodels?.some(rm => rm.id === readModelData.id)
    if (!exists) {
      tree.readmodels.push({
        id: readModelData.id,
        name: readModelData.name,
        type: 'ReadModel',
        description: readModelData.description,
        provisioningType: readModelData.provisioningType || 'CQRS',
        properties: readModelData.properties || [],
        operations: readModelData.operations || []
      })
      contextTrees.value = { ...contextTrees.value }
      markAsNew(readModelData.id)
    }
  }

  // Dynamically add a UI wireframe to a BC's tree (used during ingestion / streaming)
  function addUI(uiData) {
    const bcId = uiData.parentId || uiData.bcId
    if (!bcId) return

    const tree = ensureTree(bcId)
    const exists = tree.uis?.some(u => u.id === uiData.id)
    if (!exists) {
      tree.uis.push({
        id: uiData.id,
        name: uiData.name,
        type: 'UI',
        description: uiData.description,
        template: uiData.template,
        attachedToId: uiData.attachedToId,
        attachedToType: uiData.attachedToType,
        attachedToName: uiData.attachedToName,
        userStoryId: uiData.userStoryId
      })
      contextTrees.value = { ...contextTrees.value }
      markAsNew(uiData.id)
    }
  }

  // Dynamically add a CQRS Operation to a ReadModel (used during ingestion / streaming)
  function addCQRSOperation(operationData) {
    const readModelId = operationData.parentId || operationData.readModelId || operationData.readmodelId
    if (!readModelId) return

    // Find the ReadModel in any BC's tree
    for (const bcId in contextTrees.value) {
      const tree = contextTrees.value[bcId]
      const readModel = tree.readmodels?.find(rm => rm.id === readModelId)
      if (readModel) {
        if (!readModel.operations) readModel.operations = []
        const exists = readModel.operations.some(op => op.id === operationData.id)
        if (!exists) {
          readModel.operations.push({
            id: operationData.id,
            type: 'CQRSOperation',
            operationType: operationData.operationType || operationData.operation_type,
            triggerEventId: operationData.triggerEventId || operationData.trigger_event_id,
            triggerEventName: operationData.triggerEventName
          })
          contextTrees.value = { ...contextTrees.value }
          markAsNew(operationData.id)
        }
        break
      }
    }
  }

  // Dynamically add a Property to an object (Aggregate, Command, Event, ReadModel)
  function addProperty(propertyData) {
    const parentId = propertyData.parentId
    const parentType = propertyData.parentType
    if (!parentId || !parentType) return

    // Find parent in any BC's tree
    for (const bcId in contextTrees.value) {
      const tree = contextTrees.value[bcId]

      // Aggregate properties
      const agg = tree.aggregates?.find(a => a.id === parentId)
      if (agg) {
        if (!agg.properties) agg.properties = []
        if (!agg.properties.some(p => p.id === propertyData.id)) {
          agg.properties.push({ ...propertyData, dataType: propertyData.dataType || propertyData.type, type: 'Property' })
          contextTrees.value = { ...contextTrees.value }
          markAsNew(propertyData.id)
        }
        return
      }

      // Command properties
      for (const a of (tree.aggregates || [])) {
        const cmd = a.commands?.find(c => c.id === parentId)
        if (cmd) {
          if (!cmd.properties) cmd.properties = []
          if (!cmd.properties.some(p => p.id === propertyData.id)) {
            cmd.properties.push({ ...propertyData, dataType: propertyData.dataType || propertyData.type, type: 'Property' })
            contextTrees.value = { ...contextTrees.value }
            markAsNew(propertyData.id)
          }
          return
        }
      }

      // Event properties
      for (const a of (tree.aggregates || [])) {
        const evt = a.events?.find(e => e.id === parentId)
        if (evt) {
          if (!evt.properties) evt.properties = []
          if (!evt.properties.some(p => p.id === propertyData.id)) {
            evt.properties.push({ ...propertyData, dataType: propertyData.dataType || propertyData.type, type: 'Property' })
            contextTrees.value = { ...contextTrees.value }
            markAsNew(propertyData.id)
          }
          return
        }
      }

      // ReadModel properties
      const rm = tree.readmodels?.find(r => r.id === parentId)
      if (rm) {
        if (!rm.properties) rm.properties = []
        if (!rm.properties.some(p => p.id === propertyData.id)) {
          rm.properties.push({ ...propertyData, dataType: propertyData.dataType || propertyData.type, type: 'Property' })
          contextTrees.value = { ...contextTrees.value }
          markAsNew(propertyData.id)
        }
        return
      }
    }
  }
  }
  
  // Generic add item to tree (legacy, for backwards compatibility)
  function addItemToTree(contextId, item) {
    markAsNew(item.id)
  }
  
  // Check if an item is newly added (for highlighting)
  function isNewlyAdded(nodeId) {
    return newlyAddedIds.value.has(nodeId)
  }
  
  // Refresh all contexts and trees
  async function refreshAll(meta = {}) {
    const opId = meta.opId || newOpId('nav_refresh')
    const trigger = meta.trigger || 'unknown'
    const userStoryId = meta.userStoryId || null

    const t0 = (globalThis.performance && performance.now) ? performance.now() : Date.now()
    log.info(
      'navigator_refresh_started',
      'Starting Navigator refresh: will reload unassigned user stories, contexts, and per-context trees.',
      {
        opId,
        trigger,
        userStoryId,
        before: {
          contextsCount: contexts.value.length,
          unassignedUserStoriesCount: userStories.value.length,
          contextTreesCount: Object.keys(contextTrees.value).length,
          loading: !!loading.value,
          error: error.value
        }
      }
    )

    loading.value = true
    error.value = null
    
    try {
      // Fetch unassigned user stories
      log.debug(
        'navigator_refresh_step_start',
        'Refreshing unassigned user stories.',
        { opId, step: 'fetchUserStories' }
      )
      await fetchUserStories()
      log.info(
        'navigator_refresh_step_completed',
        'Unassigned user stories refreshed.',
        { opId, step: 'fetchUserStories', unassignedUserStoriesCount: userStories.value.length }
      )
      
      // Fetch contexts
      log.debug(
        'navigator_refresh_step_start',
        'Refreshing bounded contexts list.',
        { opId, step: 'fetchContexts' }
      )
      const response = await fetch('/api/contexts')
      if (!response.ok) {
        throw new Error(`Failed to fetch contexts (http ${response.status})`)
      }
      contexts.value = await response.json()
      log.info(
        'navigator_refresh_step_completed',
        'Bounded contexts refreshed.',
        { opId, step: 'fetchContexts', contextsCount: contexts.value.length }
      )
      
      // Clear old trees and fetch new ones
      contextTrees.value = {}
      userStoryAssignments.value = {}
      
      log.info(
        'navigator_refresh_tree_reload_started',
        'Reloading per-context trees (full-tree) after clearing cached trees.',
        { opId, contextsToFetch: contexts.value.length }
      )

      let okCount = 0
      let failCount = 0
      for (const ctx of contexts.value) {
        log.debug(
          'navigator_refresh_tree_fetch_attempt',
          'Fetching context tree.',
          { opId, contextId: ctx.id, contextName: ctx.name }
        )

        const tree = await fetchContextTree(ctx.id, true)
        if (tree) okCount += 1
        else failCount += 1
      }

      log.info(
        'navigator_refresh_tree_reload_completed',
        'Per-context tree reload finished.',
        { opId, okCount, failCount, contextTreesCount: Object.keys(contextTrees.value).length }
      )
      
      // Auto-expand all for better visibility
      expandAll()
      log.debug(
        'navigator_refresh_expand_all_completed',
        'Auto-expanded Navigator nodes for visibility.',
        { opId, expandedNodesCount: expandedNodes.value?.size ?? 0 }
      )
      
    } catch (e) {
      error.value = e.message
      const durationMs = Math.round(((globalThis.performance && performance.now) ? performance.now() : Date.now()) - t0)
      log.error(
        'navigator_refresh_failed',
        'Navigator refresh failed; UI may be partially updated.',
        { opId, trigger, userStoryId, durationMs, errorMessage: e?.message || String(e) }
      )
    } finally {
      loading.value = false
      const durationMs = Math.round(((globalThis.performance && performance.now) ? performance.now() : Date.now()) - t0)
      if (!error.value) {
        log.info(
          'navigator_refresh_completed',
          'Navigator refresh completed successfully.',
          {
            opId,
            trigger,
            userStoryId,
            durationMs,
            after: {
              contextsCount: contexts.value.length,
              unassignedUserStoriesCount: userStories.value.length,
              contextTreesCount: Object.keys(contextTrees.value).length,
              expandedNodesCount: expandedNodes.value?.size ?? 0
            }
          }
        )
      }
    }
  }
  
  // Clear all data (for new ingestion)
  function clearAll() {
    contexts.value = []
    contextTrees.value = {}
    userStories.value = []
    userStoryAssignments.value = {}
    expandedNodes.value = new Set()
    newlyAddedIds.value = new Set()
  }
  
  // Toggle expanded state
  function toggleExpanded(nodeId) {
    if (expandedNodes.value.has(nodeId)) {
      expandedNodes.value.delete(nodeId)
    } else {
      expandedNodes.value.add(nodeId)
    }
    // Force reactivity
    expandedNodes.value = new Set(expandedNodes.value)
  }
  
  function isExpanded(nodeId) {
    return expandedNodes.value.has(nodeId)
  }
  
  function expandAll() {
    // Expand all context nodes
    contexts.value.forEach(ctx => {
      expandedNodes.value.add(ctx.id)
      const tree = contextTrees.value[ctx.id]
      if (tree) {
        tree.aggregates?.forEach(agg => {
          expandedNodes.value.add(agg.id)
        })
      }
    })
    expandedNodes.value = new Set(expandedNodes.value)
  }
  
  function collapseAll() {
    expandedNodes.value.clear()
    expandedNodes.value = new Set()
  }
  
  return {
    contexts,
    contextTrees,
    userStories,
    userStoryAssignments,
    loading,
    error,
    expandedNodes,
    newlyAddedIds,
    fetchContexts,
    fetchContextTree,
    fetchUserStories,
    addContext,
    addUserStory,
    assignUserStoryToBC,
    addAggregate,
    addCommand,
    addEvent,
    addPolicy,
    addReadModel,
    addUI,
    addCQRSOperation,
    addProperty,
    addItemToTree,
    isNewlyAdded,
    refreshAll,
    clearAll,
    toggleExpanded,
    isExpanded,
    expandAll,
    collapseAll
  }
})

