<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useUserStoryChangeWorkflowStore } from '@/features/userStories/userStoryChangeWorkflow.store'

const props = defineProps({
  userStory: {
    type: Object,
    default: null
  },
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'saved'])

const changeStore = useUserStoryChangeWorkflowStore()

// Form state - editable fields
const editedRole = ref('')
const editedAction = ref('')
const editedBenefit = ref('')

// Original values for comparison
const originalRole = ref('')
const originalAction = ref('')
const originalBenefit = ref('')

// UI state
const currentStep = ref('edit') // 'edit' | 'analyzing' | 'plan' | 'feedback' | 'applying'
const feedbackText = ref('')
const showPropagationDetails = ref(true)
const showPropagationReview = ref(false)
const propagationViewMode = ref('timeline') // 'timeline' | 'list'

// Computed
const hasChanges = computed(() => {
  return editedRole.value !== originalRole.value ||
    editedAction.value !== originalAction.value ||
    editedBenefit.value !== originalBenefit.value
})

const changedFields = computed(() => {
  const changes = []
  if (editedRole.value !== originalRole.value) {
    changes.push({ field: 'role', from: originalRole.value, to: editedRole.value })
  }
  if (editedAction.value !== originalAction.value) {
    changes.push({ field: 'action', from: originalAction.value, to: editedAction.value })
  }
  if (editedBenefit.value !== originalBenefit.value) {
    changes.push({ field: 'benefit', from: originalBenefit.value, to: editedBenefit.value })
  }
  return changes
})

// Watch for userStory changes
watch(() => props.userStory, (newVal) => {
  if (newVal) {
    editedRole.value = originalRole.value = newVal.role || ''
    editedAction.value = originalAction.value = newVal.action || ''
    editedBenefit.value = originalBenefit.value = newVal.benefit || ''
    currentStep.value = 'edit'
    feedbackText.value = ''
  }
}, { immediate: true })

// Reset when modal closes
watch(() => props.visible, (visible) => {
  if (!visible) {
    currentStep.value = 'edit'
    feedbackText.value = ''
    changeStore.reset()
  }
})

// Close modal on Escape
function handleKeyDown(e) {
  if (e.key === 'Escape') {
    handleClose()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown)
})

// Actions
function handleClose() {
  emit('close')
}

async function analyzeImpact() {
  if (!hasChanges.value) return
  
  currentStep.value = 'analyzing'
  
  try {
    await changeStore.analyzeImpact(props.userStory.id, {
      role: editedRole.value,
      action: editedAction.value,
      benefit: editedBenefit.value,
      changes: changedFields.value
    })
    currentStep.value = 'plan'
  } catch (error) {
    console.error('Failed to analyze impact:', error)
    currentStep.value = 'edit'
  }
}

async function approvePlan() {
  currentStep.value = 'applying'
  
  try {
    await changeStore.applyChanges(props.userStory.id)
    emit('saved')
    handleClose()
  } catch (error) {
    console.error('Failed to apply changes:', error)
    currentStep.value = 'plan'
  }
}

async function requestRevision() {
  currentStep.value = 'feedback'
}

async function submitFeedback() {
  if (!feedbackText.value.trim()) return
  
  currentStep.value = 'analyzing'
  
  try {
    await changeStore.revisePlan(props.userStory.id, feedbackText.value)
    feedbackText.value = ''
    currentStep.value = 'plan'
  } catch (error) {
    console.error('Failed to revise plan:', error)
    currentStep.value = 'feedback'
  }
}

function cancelFeedback() {
  feedbackText.value = ''
  currentStep.value = 'plan'
}

function formatNodeType(type) {
  const icons = {
    Aggregate: '📦',
    Command: '⚡',
    Event: '📣',
    Policy: '📜'
  }
  return icons[type] || '•'
}

function getScopeLabel(scope) {
  const labels = {
    local: 'Local Change',
    cross_bc: 'Cross-BC Connection',
    new_capability: 'New Capability'
  }
  return labels[scope] || scope
}

function getScopeIcon(scope) {
  const icons = {
    local: '🔄',
    cross_bc: '🔗',
    new_capability: '✨'
  }
  return icons[scope] || '📋'
}

function getActionLabel(action) {
  const labels = {
    rename: 'RENAME',
    update: 'UPDATE',
    create: 'CREATE',
    delete: 'DELETE',
    connect: 'CONNECT'
  }
  return labels[action] || action.toUpperCase()
}

function formatStopReason(reason) {
  const labels = {
    disabled: 'Disabled',
    no_seeds: 'No seed nodes',
    fixpoint_no_frontier: 'Fixpoint (no frontier)',
    fixpoint_no_new_confirmed: 'Fixpoint (no new confirmed)',
    max_rounds_reached: 'Max rounds reached',
    max_confirmed_reached: 'Max confirmed reached',
    budget_exhausted: 'Budget exhausted',
    llm_parse_error: 'LLM parse error'
  }
  return labels[reason] || reason || '-'
}

function formatSuggestedType(t) {
  const labels = {
    rename: 'rename',
    update: 'update',
    create: 'create',
    connect: 'connect',
    delete: 'delete',
    unknown: 'unknown'
  }
  return labels[t] || t || 'unknown'
}

// Group propagation candidates by round for timeline view
function groupByRound(candidates) {
  const groups = {}
  for (const c of candidates) {
    const r = c.round ?? 0
    if (!groups[r]) groups[r] = []
    groups[r].push(c)
  }
  // Return as sorted array of { round, candidates }
  return Object.keys(groups)
    .map(Number)
    .sort((a, b) => a - b)
    .map(round => ({ round, candidates: groups[round] }))
}

// Computed grouped data
const confirmedByRound = computed(() => groupByRound(changeStore.propagationConfirmed))
const reviewByRound = computed(() => groupByRound(changeStore.propagationReview))

// Get total count for a round
function getRoundTotal(round) {
  const confirmed = changeStore.propagationConfirmed.filter(c => (c.round ?? 0) === round).length
  const review = changeStore.propagationReview.filter(c => (c.round ?? 0) === round).length
  return { confirmed, review, total: confirmed + review }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="modal-overlay" @click.self="handleClose">
        <div class="modal-container" :class="{ 'modal-container--wide': currentStep !== 'edit' }">
          <!-- Header -->
          <div class="modal-header">
            <h2 class="modal-title">
              <span class="modal-title__icon">📝</span>
              {{ currentStep === 'edit' ? 'Edit User Story' : 
                 currentStep === 'analyzing' ? 'Analyzing Impact...' :
                 currentStep === 'plan' ? 'Change Plan Review' :
                 currentStep === 'feedback' ? 'Provide Feedback' :
                 'Applying Changes...' }}
            </h2>
            <button class="modal-close" @click="handleClose">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          
          <!-- Content -->
          <div class="modal-content">
            <!-- Step 1: Edit Form -->
            <div v-if="currentStep === 'edit'" class="edit-form">
              <div class="story-id">{{ userStory?.id }}</div>
              
              <div class="form-group">
                <label class="form-label">As a</label>
                <input 
                  v-model="editedRole"
                  type="text"
                  class="form-input"
                  placeholder="user, customer, admin..."
                />
              </div>
              
              <div class="form-group">
                <label class="form-label">I want to</label>
                <textarea 
                  v-model="editedAction"
                  class="form-textarea"
                  rows="3"
                  placeholder="perform some action..."
                ></textarea>
              </div>
              
              <div class="form-group">
                <label class="form-label">So that</label>
                <textarea 
                  v-model="editedBenefit"
                  class="form-textarea"
                  rows="2"
                  placeholder="I can achieve some benefit..."
                ></textarea>
              </div>
              
              <!-- Changes Preview -->
              <div v-if="hasChanges" class="changes-preview">
                <div class="changes-preview__title">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                  </svg>
                  Detected Changes
                </div>
                <div class="changes-list">
                  <div v-for="change in changedFields" :key="change.field" class="change-item">
                    <span class="change-field">{{ change.field }}:</span>
                    <span class="change-from">{{ change.from || '(empty)' }}</span>
                    <span class="change-arrow">→</span>
                    <span class="change-to">{{ change.to || '(empty)' }}</span>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Step 2: Analyzing -->
            <div v-else-if="currentStep === 'analyzing'" class="analyzing-state">
              <div class="spinner-large"></div>
              <p class="analyzing-text">Analyzing impact on connected objects...</p>
              <p class="analyzing-subtext">Identifying affected Aggregates, Commands, and Events</p>
            </div>
            
            <!-- Step 3: Plan Review -->
            <div v-else-if="currentStep === 'plan'" class="plan-review">
              <!-- Scope Analysis Banner -->
              <div class="scope-banner" :class="`scope-banner--${changeStore.changeScope}`">
                <div class="scope-banner__icon">{{ getScopeIcon(changeStore.changeScope) }}</div>
                <div class="scope-banner__content">
                  <div class="scope-banner__title">{{ getScopeLabel(changeStore.changeScope) }}</div>
                  <div class="scope-banner__desc">{{ changeStore.scopeReasoning }}</div>
                </div>
              </div>
              
              <!-- Impact Summary -->
              <div class="impact-summary">
                <div class="impact-summary__header">
                  <span class="impact-summary__icon">🎯</span>
                  <span>Impact Analysis</span>
                </div>
                <div class="impact-stats">
                  <div class="impact-stat">
                    <span class="impact-stat__value">{{ changeStore.impactedNodes.length }}</span>
                    <span class="impact-stat__label">Connected Objects</span>
                  </div>
                  <div class="impact-stat" v-if="changeStore.propagationEnabled">
                    <span class="impact-stat__value">{{ changeStore.propagationConfirmed.length }}</span>
                    <span class="impact-stat__label">Propagation (2nd+ Confirmed)</span>
                  </div>
                  <div class="impact-stat" v-if="changeStore.relatedObjects.length > 0">
                    <span class="impact-stat__value">{{ changeStore.relatedObjects.length }}</span>
                    <span class="impact-stat__label">Related (Other BCs)</span>
                  </div>
                  <div class="impact-stat">
                    <span class="impact-stat__value">{{ changeStore.changePlan.length }}</span>
                    <span class="impact-stat__label">Proposed Changes</span>
                  </div>
                </div>
              </div>

              <!-- Propagation Results -->
              <div class="propagation" v-if="changeStore.propagationEnabled">
                <div class="section-title section-title--row">
                  <div>
                    <span class="section-title__icon">🧭</span>
                    Propagation (2nd~N-th order candidates)
                  </div>
                  <div class="view-mode-toggle">
                    <button 
                      class="toggle-btn" 
                      :class="{ 'toggle-btn--active': propagationViewMode === 'timeline' }"
                      @click="propagationViewMode = 'timeline'"
                      title="Timeline View"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="12" y1="2" x2="12" y2="22"></line>
                        <circle cx="12" cy="6" r="3"></circle>
                        <circle cx="12" cy="18" r="3"></circle>
                      </svg>
                    </button>
                    <button 
                      class="toggle-btn" 
                      :class="{ 'toggle-btn--active': propagationViewMode === 'list' }"
                      @click="propagationViewMode = 'list'"
                      title="List View"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="8" y1="6" x2="21" y2="6"></line>
                        <line x1="8" y1="12" x2="21" y2="12"></line>
                        <line x1="8" y1="18" x2="21" y2="18"></line>
                        <line x1="3" y1="6" x2="3.01" y2="6"></line>
                        <line x1="3" y1="12" x2="3.01" y2="12"></line>
                        <line x1="3" y1="18" x2="3.01" y2="18"></line>
                      </svg>
                    </button>
                    <button class="link-btn" @click="showPropagationDetails = !showPropagationDetails">
                      {{ showPropagationDetails ? 'Hide' : 'Show' }}
                    </button>
                  </div>
                </div>

                <div class="propagation-summary">
                  <div class="propagation-pill">
                    <span class="propagation-pill__label">Rounds</span>
                    <span class="propagation-pill__value">{{ changeStore.propagationRounds }}</span>
                  </div>
                  <div class="propagation-pill">
                    <span class="propagation-pill__label">Stop</span>
                    <span class="propagation-pill__value">{{ formatStopReason(changeStore.propagationStopReason) }}</span>
                  </div>
                  <div class="propagation-pill">
                    <span class="propagation-pill__label">Confirmed</span>
                    <span class="propagation-pill__value">{{ changeStore.propagationConfirmed.length }}</span>
                  </div>
                  <div class="propagation-pill">
                    <span class="propagation-pill__label">Review</span>
                    <span class="propagation-pill__value">{{ changeStore.propagationReview.length }}</span>
                  </div>
                </div>

                <div v-if="showPropagationDetails" class="propagation-details">
                  <div class="propagation-hint">
                    These candidates were discovered by iterative 2-hop expansion (seed = Connected Objects). Evidence paths show why they are linked.
                  </div>

                  <!-- Timeline View -->
                  <div v-if="propagationViewMode === 'timeline'" class="propagation-timeline">
                    <!-- Seed (Round 0) - Connected Objects -->
                    <div class="timeline-round">
                      <div class="timeline-round__header">
                        <div class="timeline-round__marker timeline-round__marker--seed">
                          <span class="timeline-round__number">0</span>
                        </div>
                        <div class="timeline-round__info">
                          <span class="timeline-round__title">Seed (Initial)</span>
                          <span class="timeline-round__count">{{ changeStore.impactedNodes.length }} connected objects</span>
                        </div>
                      </div>
                      <div class="timeline-round__content">
                        <div class="timeline-nodes timeline-nodes--seed">
                          <div 
                            v-for="node in changeStore.impactedNodes.slice(0, 8)" 
                            :key="node.id" 
                            class="timeline-node"
                            :title="`${node.type}: ${node.name}`"
                          >
                            <span class="timeline-node__icon">{{ formatNodeType(node.type) }}</span>
                            <span class="timeline-node__name">{{ node.name }}</span>
                          </div>
                          <div v-if="changeStore.impactedNodes.length > 8" class="timeline-node timeline-node--more">
                            +{{ changeStore.impactedNodes.length - 8 }} more
                          </div>
                        </div>
                      </div>
                      <div class="timeline-connector" v-if="confirmedByRound.length > 0 || reviewByRound.length > 0">
                        <div class="timeline-connector__line"></div>
                        <div class="timeline-connector__arrow">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 16l-6-6h12z"/>
                          </svg>
                        </div>
                      </div>
                    </div>

                    <!-- Propagation Rounds -->
                    <template v-for="(group, groupIdx) in confirmedByRound" :key="'round-' + group.round">
                      <div class="timeline-round">
                        <div class="timeline-round__header">
                          <div class="timeline-round__marker" :class="{ 'timeline-round__marker--confirmed': true }">
                            <span class="timeline-round__number">{{ group.round }}</span>
                          </div>
                          <div class="timeline-round__info">
                            <span class="timeline-round__title">Round {{ group.round }}</span>
                            <span class="timeline-round__count">
                              <span class="timeline-count timeline-count--confirmed">{{ group.candidates.length }} confirmed</span>
                              <span v-if="getRoundTotal(group.round).review > 0" class="timeline-count timeline-count--review">
                                {{ getRoundTotal(group.round).review }} review
                              </span>
                            </span>
                          </div>
                        </div>
                        <div class="timeline-round__content">
                          <div class="timeline-nodes">
                            <div 
                              v-for="c in group.candidates" 
                              :key="c.id" 
                              class="timeline-node timeline-node--confirmed"
                              :title="`${c.type}: ${c.name}\nConfidence: ${Math.round((c.confidence || 0) * 100)}%\n${c.reason || ''}`"
                            >
                              <span class="timeline-node__icon">{{ formatNodeType(c.type) }}</span>
                              <div class="timeline-node__details">
                                <span class="timeline-node__name">{{ c.name || c.id }}</span>
                                <div class="timeline-node__meta">
                                  <span class="timeline-node__conf">{{ Math.round((c.confidence || 0) * 100) }}%</span>
                                  <span class="timeline-node__action">{{ formatSuggestedType(c.suggested_change_type) }}</span>
                                </div>
                              </div>
                            </div>
                          </div>
                          <!-- Show review candidates for this round if any -->
                          <div v-if="getRoundTotal(group.round).review > 0" class="timeline-review-section">
                            <button class="timeline-review-toggle" @click="showPropagationReview = !showPropagationReview">
                              <span class="badge badge--warn badge--sm">REVIEW</span>
                              {{ showPropagationReview ? 'Hide' : 'Show' }} {{ getRoundTotal(group.round).review }} lower confidence
                            </button>
                            <div v-if="showPropagationReview" class="timeline-nodes timeline-nodes--review">
                              <div 
                                v-for="c in changeStore.propagationReview.filter(r => (r.round ?? 0) === group.round)" 
                                :key="c.id" 
                                class="timeline-node timeline-node--review"
                              >
                                <span class="timeline-node__icon">{{ formatNodeType(c.type) }}</span>
                                <div class="timeline-node__details">
                                  <span class="timeline-node__name">{{ c.name || c.id }}</span>
                                  <div class="timeline-node__meta">
                                    <span class="timeline-node__conf timeline-node__conf--low">{{ Math.round((c.confidence || 0) * 100) }}%</span>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                        <div class="timeline-connector" v-if="groupIdx < confirmedByRound.length - 1">
                          <div class="timeline-connector__line"></div>
                          <div class="timeline-connector__arrow">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                              <path d="M12 16l-6-6h12z"/>
                            </svg>
                          </div>
                        </div>
                      </div>
                    </template>

                    <!-- Stop Reason Footer -->
                    <div class="timeline-stop">
                      <div class="timeline-stop__icon">🛑</div>
                      <div class="timeline-stop__text">
                        Stopped: <strong>{{ formatStopReason(changeStore.propagationStopReason) }}</strong>
                      </div>
                    </div>
                  </div>

                  <!-- List View (Original) -->
                  <div v-else class="propagation-list-view">
                    <!-- Confirmed -->
                    <div class="propagation-block">
                      <div class="propagation-block__title">
                        <span class="badge badge--good">CONFIRMED</span>
                        <span>Ready to consider for changes</span>
                      </div>
                      <div v-if="changeStore.propagationConfirmed.length === 0" class="empty-muted">
                        No confirmed candidates found.
                      </div>
                      <div v-else class="propagation-list">
                        <div v-for="c in changeStore.propagationConfirmed" :key="c.id" class="propagation-item">
                          <div class="propagation-item__head">
                            <span class="round-badge">R{{ c.round ?? 0 }}</span>
                            <span class="node-item__icon">{{ formatNodeType(c.type) }}</span>
                            <span class="propagation-item__name">{{ c.name || c.id }}</span>
                            <span class="propagation-item__meta">
                              <span class="pill">ID: {{ c.id }}</span>
                              <span class="pill">BC: {{ c.bcName || 'Unknown' }}</span>
                              <span class="pill">conf: {{ Math.round((c.confidence || 0) * 100) }}%</span>
                              <span class="pill">suggest: {{ formatSuggestedType(c.suggested_change_type) }}</span>
                            </span>
                          </div>
                          <div v-if="c.reason" class="propagation-item__reason">{{ c.reason }}</div>
                          <div v-if="c.evidence_paths && c.evidence_paths.length" class="propagation-item__evidence">
                            <div class="evidence-title">Evidence paths</div>
                            <div v-for="(p, idx) in c.evidence_paths.slice(0, 3)" :key="idx" class="evidence-path">
                              {{ p }}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- Review -->
                    <div class="propagation-block">
                      <div class="propagation-block__title section-title--row">
                        <div>
                          <span class="badge badge--warn">REVIEW</span>
                          <span>Lower confidence (showing up to 20)</span>
                        </div>
                        <button class="link-btn" @click="showPropagationReview = !showPropagationReview">
                          {{ showPropagationReview ? 'Hide' : 'Show' }}
                        </button>
                      </div>
                      <div v-if="showPropagationReview" class="propagation-list">
                        <div v-if="changeStore.propagationReview.length === 0" class="empty-muted">
                          No review candidates.
                        </div>
                        <div v-else>
                          <div v-for="c in changeStore.propagationReview.slice(0, 20)" :key="c.id" class="propagation-item propagation-item--review">
                            <div class="propagation-item__head">
                              <span class="round-badge round-badge--review">R{{ c.round ?? 0 }}</span>
                              <span class="node-item__icon">{{ formatNodeType(c.type) }}</span>
                              <span class="propagation-item__name">{{ c.name || c.id }}</span>
                              <span class="propagation-item__meta">
                                <span class="pill">ID: {{ c.id }}</span>
                                <span class="pill">BC: {{ c.bcName || 'Unknown' }}</span>
                                <span class="pill">conf: {{ Math.round((c.confidence || 0) * 100) }}%</span>
                                <span class="pill">suggest: {{ formatSuggestedType(c.suggested_change_type) }}</span>
                              </span>
                            </div>
                            <div v-if="c.reason" class="propagation-item__reason">{{ c.reason }}</div>
                            <div v-if="c.evidence_paths && c.evidence_paths.length" class="propagation-item__evidence">
                              <div class="evidence-title">Evidence paths</div>
                              <div v-for="(p, idx) in c.evidence_paths.slice(0, 2)" :key="idx" class="evidence-path">
                                {{ p }}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- Connected Nodes -->
              <div class="impacted-nodes" v-if="changeStore.impactedNodes.length > 0">
                <div class="section-title">Connected Objects (Same BC)</div>
                <div class="node-list">
                  <div 
                    v-for="node in changeStore.impactedNodes" 
                    :key="node.id"
                    class="node-item"
                    :class="`node-item--${node.type?.toLowerCase()}`"
                  >
                    <span class="node-item__icon">{{ formatNodeType(node.type) }}</span>
                    <span class="node-item__type">{{ node.type }}</span>
                    <span class="node-item__name">{{ node.name }}</span>
                  </div>
                </div>
              </div>
              
              <!-- Related Objects from Vector Search -->
              <div class="related-objects" v-if="changeStore.relatedObjects.length > 0">
                <div class="section-title">
                  <span class="section-title__icon">🔍</span>
                  Related Objects Found (Other BCs)
                </div>
                <div class="node-list">
                  <div 
                    v-for="obj in changeStore.relatedObjects" 
                    :key="obj.id"
                    class="node-item node-item--related"
                    :class="`node-item--${obj.type?.toLowerCase()}`"
                  >
                    <span class="node-item__icon">{{ formatNodeType(obj.type) }}</span>
                    <div class="node-item__info">
                      <span class="node-item__name">{{ obj.name }}</span>
                      <span class="node-item__bc">BC: {{ obj.bcName || 'Unknown' }}</span>
                    </div>
                    <span class="node-item__score">{{ Math.round(obj.similarity * 100) }}%</span>
                  </div>
                </div>
              </div>
              
              <!-- Change Plan -->
              <div class="change-plan">
                <div class="section-title">Proposed Changes</div>
                <div class="plan-list">
                  <div 
                    v-for="(change, idx) in changeStore.changePlan" 
                    :key="idx"
                    class="plan-item"
                    :class="{ 'plan-item--connect': change.action === 'connect' }"
                  >
                    <div class="plan-item__header">
                      <span class="plan-item__number">{{ idx + 1 }}</span>
                      <span class="plan-item__type" :class="`plan-item__type--${change.action}`">
                        {{ getActionLabel(change.action) }}
                      </span>
                      <span class="plan-item__target">{{ change.targetType }}: {{ change.targetName }}</span>
                      <span v-if="change.targetBcName" class="plan-item__bc">
                        {{ change.targetBcName }}
                      </span>
                    </div>
                    <div class="plan-item__detail">
                      <template v-if="change.action === 'rename'">
                        <span class="plan-from">{{ change.from_value }}</span>
                        <span class="plan-arrow">→</span>
                        <span class="plan-to">{{ change.to_value }}</span>
                      </template>
                      <template v-else-if="change.action === 'connect'">
                        <div class="connection-visual">
                          <span class="connection-source">{{ change.sourceId }}</span>
                          <span class="connection-type">{{ change.connectionType }}</span>
                          <span class="connection-target">{{ change.targetName }}</span>
                        </div>
                      </template>
                      <template v-else>
                        {{ change.description }}
                      </template>
                    </div>
                    <div v-if="change.reason" class="plan-item__reason">
                      <span class="reason-label">Reason:</span> {{ change.reason }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Step 4: Feedback -->
            <div v-else-if="currentStep === 'feedback'" class="feedback-form">
              <div class="feedback-prompt">
                <span class="feedback-prompt__icon">💬</span>
                <p>Please describe how you would like to modify the change plan:</p>
              </div>
              <textarea 
                v-model="feedbackText"
                class="form-textarea feedback-textarea"
                rows="5"
                placeholder="e.g., Don't rename the Event, just update its description..."
                autofocus
              ></textarea>
            </div>
            
            <!-- Step 5: Applying -->
            <div v-else-if="currentStep === 'applying'" class="applying-state">
              <div class="spinner-large"></div>
              <p class="analyzing-text">Applying changes to the graph...</p>
              <div class="applying-progress">
                <div 
                  class="applying-progress__bar" 
                  :style="{ width: `${changeStore.applyProgress}%` }"
                ></div>
              </div>
            </div>
          </div>
          
          <!-- Footer -->
          <div class="modal-footer">
            <template v-if="currentStep === 'edit'">
              <button class="btn btn--secondary" @click="handleClose">Cancel</button>
              <button 
                class="btn btn--primary" 
                :disabled="!hasChanges"
                @click="analyzeImpact"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                  <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
                Analyze Impact
              </button>
            </template>
            
            <template v-else-if="currentStep === 'plan'">
              <button class="btn btn--secondary" @click="handleClose">Cancel</button>
              <button class="btn btn--warning" @click="requestRevision">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
                Request Revision
              </button>
              <button class="btn btn--primary" @click="approvePlan">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                Approve & Apply
              </button>
            </template>
            
            <template v-else-if="currentStep === 'feedback'">
              <button class="btn btn--secondary" @click="cancelFeedback">Back to Plan</button>
              <button 
                class="btn btn--primary" 
                :disabled="!feedbackText.trim()"
                @click="submitFeedback"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="22" y1="2" x2="11" y2="13"></line>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
                Submit Feedback
              </button>
            </template>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Modal Animation */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95) translateY(-20px);
  opacity: 0;
}

/* Modal Overlay */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--spacing-lg);
}

.modal-container {
  background: var(--color-bg-secondary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--color-border);
  width: 100%;
  max-width: 520px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-container--wide {
  max-width: 700px;
}

/* Section title row helpers */
.section-title--row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
}

.link-btn {
  background: transparent;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  font-size: 0.825rem;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
}
.link-btn:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-bright);
}

/* Propagation */
.propagation {
  margin-top: var(--spacing-lg);
  padding: var(--spacing-md);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.propagation-summary {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-sm);
}

.propagation-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
  font-size: 0.8rem;
}
.propagation-pill__label {
  color: var(--color-text-light);
}
.propagation-pill__value {
  color: var(--color-text-bright);
  font-weight: 600;
}

.propagation-details {
  margin-top: var(--spacing-md);
}

.propagation-hint {
  font-size: 0.82rem;
  color: var(--color-text-light);
  margin-bottom: var(--spacing-md);
}

.propagation-block {
  margin-top: var(--spacing-md);
}

.propagation-block__title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
  font-weight: 600;
  color: var(--color-text-bright);
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.badge--good {
  background: rgba(46, 204, 113, 0.15);
  color: #2ecc71;
  border: 1px solid rgba(46, 204, 113, 0.35);
}
.badge--warn {
  background: rgba(230, 119, 0, 0.12);
  color: #e67700;
  border: 1px solid rgba(230, 119, 0, 0.35);
}

.propagation-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.propagation-item {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-sm);
}
.propagation-item--review {
  opacity: 0.9;
}

.propagation-item__head {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.propagation-item__name {
  font-weight: 600;
  color: var(--color-text-bright);
}

.propagation-item__meta {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-left: auto;
}

.pill {
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text-light);
  white-space: nowrap;
}

.propagation-item__reason {
  margin-top: 6px;
  font-size: 0.82rem;
  color: var(--color-text);
}

.propagation-item__evidence {
  margin-top: 8px;
}
.evidence-title {
  font-size: 0.75rem;
  color: var(--color-text-light);
  margin-bottom: 4px;
}
.evidence-path {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 0.78rem;
  color: var(--color-text-bright);
  background: rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.06);
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  margin-top: 6px;
  overflow-x: auto;
}

.empty-muted {
  font-size: 0.85rem;
  color: var(--color-text-light);
}

/* View Mode Toggle */
.view-mode-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
}

.toggle-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  cursor: pointer;
  transition: all 0.15s;
}

.toggle-btn:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-bright);
}

.toggle-btn--active {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: white;
}

.toggle-btn--active:hover {
  background: #1c7ed6;
}

/* Timeline View */
.propagation-timeline {
  margin-top: var(--spacing-md);
  position: relative;
}

.timeline-round {
  position: relative;
  padding-left: 48px;
  margin-bottom: 0;
}

.timeline-round__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.timeline-round__marker {
  position: absolute;
  left: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--color-bg-secondary);
  border: 2px solid var(--color-border);
  z-index: 2;
}

.timeline-round__marker--seed {
  background: linear-gradient(135deg, #3498db, #2980b9);
  border-color: #2980b9;
  color: white;
}

.timeline-round__marker--confirmed {
  background: linear-gradient(135deg, #2ecc71, #27ae60);
  border-color: #27ae60;
  color: white;
}

.timeline-round__number {
  font-size: 0.85rem;
  font-weight: 700;
}

.timeline-round__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.timeline-round__title {
  font-weight: 600;
  color: var(--color-text-bright);
  font-size: 0.9rem;
}

.timeline-round__count {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 0.8rem;
}

.timeline-count {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
}

.timeline-count--confirmed {
  background: rgba(46, 204, 113, 0.15);
  color: #2ecc71;
}

.timeline-count--review {
  background: rgba(230, 119, 0, 0.12);
  color: #e67700;
}

.timeline-round__content {
  padding: var(--spacing-sm) 0;
}

.timeline-nodes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.timeline-nodes--seed .timeline-node {
  background: rgba(52, 152, 219, 0.1);
  border-color: rgba(52, 152, 219, 0.3);
}

.timeline-nodes--review {
  margin-top: var(--spacing-sm);
}

.timeline-node {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  transition: all 0.15s;
  cursor: default;
}

.timeline-node:hover {
  border-color: var(--color-accent);
  background: rgba(34, 139, 230, 0.05);
}

.timeline-node--confirmed {
  background: rgba(46, 204, 113, 0.08);
  border-color: rgba(46, 204, 113, 0.25);
}

.timeline-node--confirmed:hover {
  border-color: #2ecc71;
  background: rgba(46, 204, 113, 0.15);
}

.timeline-node--review {
  background: rgba(230, 119, 0, 0.06);
  border-color: rgba(230, 119, 0, 0.2);
  opacity: 0.85;
}

.timeline-node--more {
  background: var(--color-bg-tertiary);
  color: var(--color-text-light);
  font-style: italic;
}

.timeline-node__icon {
  font-size: 1rem;
}

.timeline-node__details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.timeline-node__name {
  font-weight: 500;
  color: var(--color-text-bright);
}

.timeline-node__meta {
  display: flex;
  align-items: center;
  gap: 6px;
}

.timeline-node__conf {
  font-size: 0.7rem;
  font-weight: 600;
  color: #2ecc71;
}

.timeline-node__conf--low {
  color: #e67700;
}

.timeline-node__action {
  font-size: 0.68rem;
  padding: 1px 6px;
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  text-transform: uppercase;
}

/* Timeline Connector */
.timeline-connector {
  position: relative;
  height: 32px;
  margin-left: 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.timeline-connector__line {
  width: 2px;
  flex: 1;
  background: linear-gradient(180deg, var(--color-border) 0%, rgba(46, 204, 113, 0.5) 100%);
}

.timeline-connector__arrow {
  color: var(--color-accent);
}

/* Timeline Review Section */
.timeline-review-section {
  margin-top: var(--spacing-sm);
}

.timeline-review-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: transparent;
  border: 1px dashed rgba(230, 119, 0, 0.4);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  font-size: 0.78rem;
  cursor: pointer;
  transition: all 0.15s;
}

.timeline-review-toggle:hover {
  background: rgba(230, 119, 0, 0.08);
  border-color: rgba(230, 119, 0, 0.6);
}

/* Timeline Stop */
.timeline-stop {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  margin-top: var(--spacing-md);
  margin-left: 48px;
  background: rgba(231, 76, 60, 0.08);
  border: 1px solid rgba(231, 76, 60, 0.25);
  border-radius: var(--radius-md);
}

.timeline-stop__icon {
  font-size: 1rem;
}

.timeline-stop__text {
  font-size: 0.82rem;
  color: var(--color-text);
}

.timeline-stop__text strong {
  color: var(--color-text-bright);
}

/* Round Badge (List View) */
.round-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 20px;
  padding: 0 6px;
  background: linear-gradient(135deg, #2ecc71, #27ae60);
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
  color: white;
  margin-right: 4px;
}

.round-badge--review {
  background: linear-gradient(135deg, #e67700, #d35400);
}

.badge--sm {
  font-size: 0.65rem;
  padding: 1px 6px;
}

.propagation-list-view {
  margin-top: var(--spacing-md);
}

/* Header */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
}

.modal-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-text-bright);
}

.modal-title__icon {
  font-size: 1.25rem;
}

.modal-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.modal-close:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-bright);
}

/* Content */
.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
}

/* Footer */
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--color-border);
  background: var(--color-bg);
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 10px 18px;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: var(--radius-md);
  border: none;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}

.btn:active {
  transform: scale(0.98);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn--primary {
  background: var(--color-accent);
  color: white;
}

.btn--primary:hover:not(:disabled) {
  background: #1c7ed6;
}

.btn--secondary {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}

.btn--secondary:hover {
  background: var(--color-border);
}

.btn--warning {
  background: #e67700;
  color: white;
}

.btn--warning:hover {
  background: #d9480f;
}

/* Form */
.edit-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.story-id {
  display: inline-block;
  padding: 4px 10px;
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-text-light);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.form-input,
.form-textarea {
  padding: 10px 14px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-bright);
  font-size: 0.95rem;
  font-family: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px rgba(34, 139, 230, 0.2);
}

.form-textarea {
  resize: vertical;
  min-height: 60px;
}

/* Changes Preview */
.changes-preview {
  background: rgba(230, 119, 0, 0.1);
  border: 1px solid rgba(230, 119, 0, 0.3);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}

.changes-preview__title {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: 0.8rem;
  font-weight: 600;
  color: #e67700;
  margin-bottom: var(--spacing-sm);
}

.changes-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.change-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: 0.85rem;
  flex-wrap: wrap;
}

.change-field {
  font-weight: 600;
  color: var(--color-text-light);
  text-transform: capitalize;
}

.change-from {
  color: #fa5252;
  text-decoration: line-through;
}

.change-arrow {
  color: var(--color-text-light);
}

.change-to {
  color: #40c057;
}

/* Analyzing State */
.analyzing-state,
.applying-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl) 0;
  text-align: center;
}

.spinner-large {
  width: 48px;
  height: 48px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: var(--spacing-md);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.analyzing-text {
  font-size: 1rem;
  color: var(--color-text-bright);
  margin-bottom: var(--spacing-xs);
}

.analyzing-subtext {
  font-size: 0.85rem;
  color: var(--color-text-light);
}

/* Plan Review */
.plan-review {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.impact-summary {
  background: linear-gradient(135deg, rgba(34, 139, 230, 0.1), rgba(32, 201, 151, 0.1));
  border: 1px solid rgba(34, 139, 230, 0.3);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}

.impact-summary__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-weight: 600;
  color: var(--color-text-bright);
  margin-bottom: var(--spacing-md);
}

.impact-summary__icon {
  font-size: 1.25rem;
}

.impact-stats {
  display: flex;
  gap: var(--spacing-lg);
}

.impact-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.impact-stat__value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-accent);
}

.impact-stat__label {
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.section-title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--color-text-light);
  margin-bottom: var(--spacing-sm);
}

/* Scope Banner */
.scope-banner {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-md);
}

.scope-banner--local {
  background: rgba(32, 201, 151, 0.1);
  border: 1px solid rgba(32, 201, 151, 0.3);
}

.scope-banner--cross_bc {
  background: rgba(230, 119, 0, 0.1);
  border: 1px solid rgba(230, 119, 0, 0.3);
}

.scope-banner--new_capability {
  background: rgba(156, 39, 176, 0.1);
  border: 1px solid rgba(156, 39, 176, 0.3);
}

.scope-banner__icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.scope-banner__content {
  flex: 1;
}

.scope-banner__title {
  font-weight: 600;
  color: var(--color-text-bright);
  margin-bottom: 4px;
}

.scope-banner__desc {
  font-size: 0.85rem;
  color: var(--color-text);
  line-height: 1.4;
}

/* Impacted Nodes */
.node-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.node-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
}

.node-item--related {
  flex-direction: row;
  padding: 8px 12px;
}

.node-item--aggregate { border-left: 3px solid var(--color-aggregate); }
.node-item--command { border-left: 3px solid var(--color-command); }
.node-item--event { border-left: 3px solid var(--color-event); }
.node-item--policy { border-left: 3px solid var(--color-policy); }

.node-item__icon {
  font-size: 1rem;
}

.node-item__type {
  font-size: 0.7rem;
  text-transform: uppercase;
  color: var(--color-text-light);
}

.node-item__name {
  font-weight: 500;
  color: var(--color-text-bright);
}

.node-item__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.node-item__bc {
  font-size: 0.7rem;
  color: var(--color-text-light);
}

.node-item__score {
  font-size: 0.7rem;
  padding: 2px 6px;
  background: rgba(34, 139, 230, 0.2);
  color: var(--color-accent);
  border-radius: var(--radius-sm);
  font-weight: 600;
}

/* Related Objects Section */
.related-objects {
  margin-top: var(--spacing-md);
}

.section-title__icon {
  margin-right: var(--spacing-xs);
}

/* Change Plan */
.plan-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.plan-item {
  background: var(--color-bg);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  border: 1px solid var(--color-border);
}

.plan-item__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-xs);
}

.plan-item__number {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-tertiary);
  border-radius: 50%;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-light);
}

.plan-item__type {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
}

.plan-item__type--rename {
  background: rgba(34, 139, 230, 0.2);
  color: var(--color-accent);
}

.plan-item__type--update {
  background: rgba(32, 201, 151, 0.2);
  color: #20c997;
}

.plan-item__type--create {
  background: rgba(64, 192, 87, 0.2);
  color: #40c057;
}

.plan-item__type--delete {
  background: rgba(250, 82, 82, 0.2);
  color: #fa5252;
}

.plan-item__type--connect {
  background: rgba(230, 119, 0, 0.2);
  color: #e67700;
}

.plan-item--connect {
  border: 1px solid rgba(230, 119, 0, 0.3);
  background: linear-gradient(135deg, rgba(230, 119, 0, 0.05), transparent);
}

.plan-item__bc {
  font-size: 0.7rem;
  padding: 2px 8px;
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  margin-left: auto;
}

.plan-item__target {
  font-size: 0.85rem;
  color: var(--color-text-bright);
  font-weight: 500;
}

.plan-item__detail {
  font-size: 0.9rem;
  color: var(--color-text);
  margin-bottom: var(--spacing-xs);
}

.plan-from {
  color: #fa5252;
  text-decoration: line-through;
}

.plan-arrow {
  color: var(--color-text-light);
  margin: 0 var(--spacing-xs);
}

.plan-to {
  color: #40c057;
  font-weight: 500;
}

/* Connection Visual */
.connection-visual {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) 0;
}

.connection-source {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--color-text-light);
}

.connection-type {
  padding: 2px 8px;
  background: rgba(230, 119, 0, 0.2);
  border-radius: var(--radius-sm);
  font-size: 0.7rem;
  font-weight: 600;
  color: #e67700;
}

.connection-target {
  font-weight: 500;
  color: var(--color-text-bright);
}

.plan-item__reason {
  font-size: 0.8rem;
  color: var(--color-text-light);
  font-style: italic;
}

.reason-label {
  font-weight: 600;
  font-style: normal;
}

/* Feedback Form */
.feedback-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.feedback-prompt {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  color: var(--color-text);
}

.feedback-prompt__icon {
  font-size: 1.5rem;
}

.feedback-prompt p {
  margin-top: 4px;
}

.feedback-textarea {
  min-height: 120px;
}

/* Applying Progress */
.applying-progress {
  width: 200px;
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
  margin-top: var(--spacing-md);
}

.applying-progress__bar {
  height: 100%;
  background: var(--color-accent);
  border-radius: 2px;
  transition: width 0.3s ease;
}
</style>

