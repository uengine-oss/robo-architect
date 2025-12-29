import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * Store for managing User Story change workflow with human-in-the-loop.
 * 
 * Workflow:
 * 1. User edits a User Story
 * 2. System analyzes impact on connected objects (Aggregate/Command/Event)
 * 3. LLM generates a change plan
 * 4. User reviews and approves OR provides feedback
 * 5. If feedback provided, LLM revises the plan
 * 6. Once approved, changes are applied to Neo4j
 */
export const useUserStoryChangeWorkflowStore = defineStore('userStoryChangeWorkflow', () => {
  // State
  const isAnalyzing = ref(false)
  const isApplying = ref(false)
  const error = ref(null)
  
  // Current change context
  const currentUserStoryId = ref(null)
  const originalUserStory = ref(null)
  const editedUserStory = ref(null)
  
  // Impact analysis results
  const impactedNodes = ref([])
  
  // Scope analysis from LangGraph workflow
  const changeScope = ref(null) // 'local', 'cross_bc', 'new_capability'
  const scopeReasoning = ref('')
  const searchKeywords = ref([])
  const relatedObjects = ref([]) // Objects found via vector search in other BCs
  
  // Change plan from LLM
  const changePlan = ref([])
  const planSummary = ref('')
  const planRevisions = ref([]) // History of plan revisions

  // Propagation results (2nd~Nth order candidates)
  // shape: { enabled, rounds, stopReason, confirmed, review, debug }
  const propagation = ref(null)
  
  // Apply progress
  const applyProgress = ref(0)
  const appliedChanges = ref([])
  
  // Computed
  const hasImpact = computed(() => impactedNodes.value.length > 0)
  const hasPlan = computed(() => changePlan.value.length > 0)

  const propagationEnabled = computed(() => Boolean(propagation.value?.enabled))
  const propagationRounds = computed(() => propagation.value?.rounds ?? 0)
  const propagationStopReason = computed(() => propagation.value?.stopReason ?? '')
  const propagationConfirmed = computed(() => propagation.value?.confirmed ?? [])
  const propagationReview = computed(() => propagation.value?.review ?? [])
  const propagationDebug = computed(() => propagation.value?.debug ?? null)
  
  /**
   * Analyze the impact of a user story change
   */
  async function analyzeImpact(userStoryId, editedData) {
    isAnalyzing.value = true
    error.value = null
    currentUserStoryId.value = userStoryId
    editedUserStory.value = editedData
    
    try {
      // Step 1: Get impacted nodes from the API
      const impactResponse = await fetch(`/api/change/impact/${userStoryId}`)
      if (!impactResponse.ok) {
        throw new Error('Failed to fetch impact analysis')
      }
      const impactData = await impactResponse.json()
      
      impactedNodes.value = impactData.impactedNodes || []
      originalUserStory.value = impactData.userStory
      
      // Step 2: Generate change plan using LLM
      const planResponse = await fetch('/api/change/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          userStoryId,
          originalUserStory: originalUserStory.value,
          editedUserStory: editedData,
          impactedNodes: impactedNodes.value,
          feedback: null
        })
      })
      
      if (!planResponse.ok) {
        throw new Error('Failed to generate change plan')
      }
      
      const planData = await planResponse.json()
      
      // Extract scope analysis from LangGraph workflow
      changeScope.value = planData.scope || 'local'
      scopeReasoning.value = planData.scopeReasoning || ''
      searchKeywords.value = planData.keywords || []
      relatedObjects.value = planData.relatedObjects || []
      changePlan.value = planData.changes || []
      planSummary.value = planData.summary || ''
      propagation.value = planData.propagation || null
      
      // Store in revision history
      planRevisions.value = [{
        timestamp: new Date().toISOString(),
        plan: changePlan.value,
        feedback: null,
        scope: changeScope.value
      }]
      
      return {
        impactedNodes: impactedNodes.value,
        changePlan: changePlan.value,
        changeScope: changeScope.value,
        relatedObjects: relatedObjects.value
      }
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      isAnalyzing.value = false
    }
  }
  
  /**
   * Revise the change plan based on user feedback
   */
  async function revisePlan(userStoryId, feedback) {
    isAnalyzing.value = true
    error.value = null
    
    try {
      const response = await fetch('/api/change/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          userStoryId,
          originalUserStory: originalUserStory.value,
          editedUserStory: editedUserStory.value,
          impactedNodes: impactedNodes.value,
          feedback,
          previousPlan: changePlan.value
        })
      })
      
      if (!response.ok) {
        throw new Error('Failed to revise change plan')
      }
      
      const planData = await response.json()
      
      // Update with revised plan data
      if (planData.scope) changeScope.value = planData.scope
      if (planData.scopeReasoning) scopeReasoning.value = planData.scopeReasoning
      if (planData.relatedObjects) relatedObjects.value = planData.relatedObjects
      changePlan.value = planData.changes || []
      if (planData.summary) planSummary.value = planData.summary

      // Keep existing propagation unless the server returns meaningful updated propagation
      if (planData.propagation) {
        const next = planData.propagation
        const hasMeaningful =
          (next.rounds && next.rounds > 0) ||
          (Array.isArray(next.confirmed) && next.confirmed.length > 0) ||
          (Array.isArray(next.review) && next.review.length > 0)
        if (hasMeaningful) {
          propagation.value = next
        }
      }
      
      // Add to revision history
      planRevisions.value.push({
        timestamp: new Date().toISOString(),
        plan: changePlan.value,
        feedback,
        scope: changeScope.value
      })
      
      return changePlan.value
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      isAnalyzing.value = false
    }
  }
  
  /**
   * Apply the approved changes to Neo4j
   */
  async function applyChanges(userStoryId) {
    isApplying.value = true
    error.value = null
    applyProgress.value = 0
    appliedChanges.value = []
    
    try {
      const response = await fetch('/api/change/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          userStoryId,
          editedUserStory: editedUserStory.value,
          changePlan: changePlan.value
        })
      })
      
      if (!response.ok) {
        throw new Error('Failed to apply changes')
      }
      
      // Simulate progress (the actual API call is atomic)
      const totalChanges = changePlan.value.length + 1 // +1 for user story update
      for (let i = 0; i <= totalChanges; i++) {
        await new Promise(resolve => setTimeout(resolve, 200))
        applyProgress.value = Math.round((i / totalChanges) * 100)
      }
      
      const result = await response.json()
      appliedChanges.value = result.appliedChanges || []
      
      return result
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      isApplying.value = false
    }
  }
  
  /**
   * Reset the store state
   */
  function reset() {
    isAnalyzing.value = false
    isApplying.value = false
    error.value = null
    currentUserStoryId.value = null
    originalUserStory.value = null
    editedUserStory.value = null
    impactedNodes.value = []
    changeScope.value = null
    scopeReasoning.value = ''
    searchKeywords.value = []
    relatedObjects.value = []
    changePlan.value = []
    planSummary.value = ''
    planRevisions.value = []
    propagation.value = null
    applyProgress.value = 0
    appliedChanges.value = []
  }
  
  return {
    // State
    isAnalyzing,
    isApplying,
    error,
    currentUserStoryId,
    originalUserStory,
    editedUserStory,
    impactedNodes,
    changeScope,
    scopeReasoning,
    searchKeywords,
    relatedObjects,
    changePlan,
    planSummary,
    planRevisions,
    propagation,
    propagationEnabled,
    propagationRounds,
    propagationStopReason,
    propagationConfirmed,
    propagationReview,
    propagationDebug,
    applyProgress,
    appliedChanges,
    
    // Computed
    hasImpact,
    hasPlan,
    
    // Actions
    analyzeImpact,
    revisePlan,
    applyChanges,
    reset
  }
})

