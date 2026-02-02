<script setup>
import { computed, onMounted, ref, nextTick } from 'vue'
import { useNavigatorStore } from '@/features/navigator/navigator.store'
import { useTerminologyStore } from '@/features/terminology/terminology.store'
import TreeNode from './TreeNode.vue'

const navigatorStore = useNavigatorStore()
const terminologyStore = useTerminologyStore()
const localLoading = ref(true)
const isLoading = computed(() => localLoading.value || navigatorStore.loading)

// Service name editing
const serviceName = ref('My Service Name')
const isEditingName = ref(false)
const nameInput = ref(null)

function startEditName() {
  isEditingName.value = true
  nextTick(() => {
    nameInput.value?.focus()
    nameInput.value?.select()
  })
}

function finishEditName() {
  isEditingName.value = false
  if (!serviceName.value.trim()) {
    serviceName.value = 'My Service Name'
  }
}

function handleNameKeydown(event) {
  if (event.key === 'Enter') {
    finishEditName()
  } else if (event.key === 'Escape') {
    isEditingName.value = false
  }
}

onMounted(async () => {
  await loadData()
})

async function loadData() {
  localLoading.value = true
  try {
    // Fetch both user stories and contexts
    await Promise.all([
      navigatorStore.fetchUserStories(),
      navigatorStore.fetchContexts()
    ])
    
    // Auto-fetch trees for all contexts
    for (const ctx of navigatorStore.contexts) {
      await navigatorStore.fetchContextTree(ctx.id)
    }
  } finally {
    localLoading.value = false
  }
}

async function handleRefresh() {
  localLoading.value = true
  try {
    await navigatorStore.refreshAll()
  } finally {
    localLoading.value = false
  }
}
</script>

<template>
  <aside class="left-panel">
    <div class="panel-header">
      <div class="service-name-container">
        <input 
          v-if="isEditingName"
          ref="nameInput"
          v-model="serviceName"
          class="service-name-input"
          @blur="finishEditName"
          @keydown="handleNameKeydown"
          placeholder="Service Name"
        />
        <span 
          v-else 
          class="service-name-display"
          @click="startEditName"
          title="Click to edit service name"
        >
          {{ serviceName }}
          <svg class="edit-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </span>
      </div>
    </div>
    
    <div class="panel-content">
      <div v-if="isLoading" class="loading-state">
        <div class="loading-spinner"></div>
        <span>Loading contexts...</span>
      </div>
      
      <div v-else-if="navigatorStore.error" class="error-state">
        {{ navigatorStore.error }}
      </div>
      
      <div v-else-if="navigatorStore.contexts.length === 0 && navigatorStore.userStories.length === 0" class="empty-state">
        No data found
      </div>
      
      <template v-else>
        <!-- Unassigned User Stories (root level) -->
        <div v-if="navigatorStore.userStories.length > 0" class="section-group">
          <div class="section-header">
            <span class="section-title">Requirements</span>
            <span class="section-count">{{ navigatorStore.userStories.length }}</span>
          </div>
          <TransitionGroup name="tree-item">
            <TreeNode
              v-for="us in navigatorStore.userStories"
              :key="us.id"
              :node="{ ...us, type: 'UserStory', name: us.name || `${us.role}: ${us.action?.substring(0, 25)}...` }"
            />
          </TransitionGroup>
        </div>
        
        <!-- Bounded Contexts -->
        <div v-if="navigatorStore.contexts.length > 0" class="section-group">
          <div class="section-header section-header--with-actions">
            <div class="section-header__left">
              <span class="section-title">{{ terminologyStore.getTerm('BoundedContext') }}s</span>
              <span class="section-count">{{ navigatorStore.contexts.length }}</span>
            </div>
            <div class="section-header__actions">
              <button 
                class="tree-action-btn"
                :class="{ 'is-spinning': isLoading }"
                @click="handleRefresh"
                title="Refresh"
                :disabled="isLoading"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="23 4 23 10 17 10"></polyline>
                  <polyline points="1 20 1 14 7 14"></polyline>
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                </svg>
              </button>
              <button 
                class="tree-action-btn"
                @click="navigatorStore.expandAll()"
                title="Expand All"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
              <button 
                class="tree-action-btn"
                @click="navigatorStore.collapseAll()"
                title="Collapse All"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="18 15 12 9 6 15"></polyline>
                </svg>
              </button>
            </div>
          </div>
          <TransitionGroup name="tree-item">
            <TreeNode
              v-for="ctx in navigatorStore.contexts"
              :key="ctx.id"
              :node="{ ...ctx, type: 'BoundedContext', domainType: ctx.domainType }"
              :tree="navigatorStore.contextTrees[ctx.id]"
            />
          </TransitionGroup>
        </div>
      </template>
    </div>
    
    <!-- Legend -->
    <div class="panel-legend">
      <div class="legend-item">
        <span class="legend-color legend-color--userstory"></span>
        <span>UserStory</span>
      </div>
      <div class="legend-item">
        <span class="legend-color legend-color--aggregate"></span>
        <span>{{ terminologyStore.getTerm('Aggregate') }}</span>
      </div>
      <div class="legend-item">
        <span class="legend-color legend-color--command"></span>
        <span>{{ terminologyStore.getTerm('Command') }}</span>
      </div>
      <div class="legend-item">
        <span class="legend-color legend-color--event"></span>
        <span>{{ terminologyStore.getTerm('Event') }}</span>
      </div>
      <div class="legend-item">
        <span class="legend-color legend-color--policy"></span>
        <span>{{ terminologyStore.getTerm('Policy') }}</span>
      </div>
      <div class="legend-item">
        <span class="legend-color legend-color--readmodel"></span>
        <span>{{ terminologyStore.getTerm('ReadModel') }}</span>
      </div>
      <div class="legend-item">
        <span class="legend-color legend-color--ui"></span>
        <span>{{ terminologyStore.getTerm('UI') }}</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
/* Service Name Editing */
.service-name-container {
  display: flex;
  align-items: center;
  width: 100%;
}

.service-name-display {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-bright);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  transition: background 0.15s, color 0.15s;
  width: 100%;
}

.service-name-display:hover {
  background: var(--color-bg-tertiary);
}

.service-name-display .edit-icon {
  color: var(--color-text-light);
  width: 10px;
  height: 10px;
  flex-shrink: 0;
}

.service-name-input {
  flex: 1;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-bright);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  padding: 2px 6px;
  outline: none;
  width: 100%;
}

.service-name-input::placeholder {
  color: var(--color-text-light);
  font-weight: 400;
}

/* Tree Action Buttons */
.tree-action-btn {
  width: 20px;
  height: 20px;
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

.tree-action-btn:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-bright);
}

.tree-action-btn.is-spinning svg {
  animation: spin 1s linear infinite;
}

.tree-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Section Groups */
.section-group {
  margin-bottom: var(--spacing-sm);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px var(--spacing-xs);
  margin-bottom: 2px;
}

.section-header--with-actions {
  padding: 4px var(--spacing-xs);
}

.section-header__left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.section-header__actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.section-title {
  font-size: 0.6rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-light);
}

.section-count {
  font-size: 0.55rem;
  padding: 1px 4px;
  background: var(--color-bg-tertiary);
  border-radius: 8px;
  color: var(--color-text-light);
}

/* Tree item transitions */
.tree-item-enter-active {
  animation: slideInLeft 0.3s ease-out;
}

.tree-item-leave-active {
  animation: slideOutRight 0.3s ease-out;
}

.tree-item-move {
  transition: transform 0.3s ease;
}

@keyframes slideInLeft {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes slideOutRight {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(20px);
  }
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  color: var(--color-text-light);
  font-size: 0.875rem;
  text-align: center;
  gap: var(--spacing-sm);
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.panel-legend {
  padding: var(--spacing-sm);
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.65rem;
  color: var(--color-text-light);
}

.legend-color {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.legend-color--userstory { background: #20c997; }
.legend-color--command { background: var(--color-command); }
.legend-color--event { background: var(--color-event); }
.legend-color--policy { background: var(--color-policy); }
.legend-color--aggregate { background: var(--color-aggregate); }
.legend-color--readmodel { background: var(--color-readmodel); }
.legend-color--ui { background: var(--color-ui-light); border: 1px solid var(--color-ui); }
</style>

