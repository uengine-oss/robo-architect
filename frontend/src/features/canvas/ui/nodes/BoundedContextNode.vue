<script setup>
import { computed } from 'vue'
import { useCanvasStore } from '../../canvas.store'

const props = defineProps({
  id: String,
  data: Object
})

const canvasStore = useCanvasStore()

// Get the display name
const displayName = computed(() => {
  return props.data?.name || props.data?.label || props.id || 'Context'
})

// Check if BC is collapsed
const isCollapsed = computed(() => {
  return canvasStore.isBCCollapsed(props.id)
})

// Toggle collapse state
function toggleCollapse(event) {
  event.stopPropagation()
  canvasStore.toggleBCCollapse(props.id)
}

// Close (remove) BC
function closeBC(event) {
  event.stopPropagation()
  canvasStore.removeBC(props.id)
}
</script>

<template>
  <div class="bc-container" :class="{ 'bc-container--collapsed': isCollapsed }">
    <!-- Header -->
    <div class="bc-container__header">
      <span class="bc-container__name">{{ displayName.toLowerCase() }}</span>
      
      <!-- Header Actions -->
      <div class="bc-container__actions">
        <!-- Collapse/Expand Button -->
        <button 
          class="bc-container__action-btn"
          @click="toggleCollapse"
          :title="isCollapsed ? 'Expand' : 'Collapse'"
        >
          <svg v-if="isCollapsed" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="18 15 12 9 6 15"></polyline>
          </svg>
        </button>
        
        <!-- Close Button -->
        <button 
          class="bc-container__action-btn bc-container__action-btn--close"
          @click="closeBC"
          title="Close"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>
    
    <!-- Body - children will be rendered by Vue Flow inside this -->
    <div class="bc-container__body" v-show="!isCollapsed">
      <!-- Child nodes are automatically placed here by Vue Flow -->
    </div>
  </div>
</template>

<style scoped>
.bc-container {
  width: 100%;
  height: 100%;
  background: rgba(40, 42, 54, 0.6);
  border: 2px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  overflow: visible;
  box-shadow: 
    0 4px 24px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
  transition: height 0.2s ease-out;
}

.bc-container--collapsed {
  overflow: hidden;
}

.bc-container__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.2);
  border-radius: 14px 14px 0 0;
}

.bc-container--collapsed .bc-container__header {
  border-bottom: none;
  border-radius: 14px;
}

.bc-container__name {
  font-size: 1rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
  letter-spacing: 0.02em;
}

.bc-container__actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.bc-container__action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  transition: all 0.15s ease;
}

.bc-container__action-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.9);
}

.bc-container__action-btn--close:hover {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.bc-container__body {
  position: relative;
  width: 100%;
  height: calc(100% - 48px);
  padding: 16px;
}

/* Make the node draggable only from header */
:deep(.vue-flow__node) {
  cursor: default;
}

.bc-container__header {
  cursor: grab;
}

.bc-container__header:active {
  cursor: grabbing;
}
</style>
