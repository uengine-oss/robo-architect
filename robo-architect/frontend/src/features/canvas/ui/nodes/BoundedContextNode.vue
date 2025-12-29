<script setup>
import { computed } from 'vue'

const props = defineProps({
  id: String,
  data: Object
})

// Get the display name
const displayName = computed(() => {
  return props.data?.name || props.id?.replace('BC-', '') || 'Context'
})
</script>

<template>
  <div class="bc-container">
    <!-- Header -->
    <div class="bc-container__header">
      <span class="bc-container__name">{{ displayName.toLowerCase() }}</span>
    </div>
    
    <!-- Body - children will be rendered by Vue Flow inside this -->
    <div class="bc-container__body">
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
}

.bc-container__header {
  padding: 12px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.2);
  border-radius: 14px 14px 0 0;
}

.bc-container__name {
  font-size: 1rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
  letter-spacing: 0.02em;
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
