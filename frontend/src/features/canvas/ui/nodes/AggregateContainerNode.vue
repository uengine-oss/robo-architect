<script setup>
import { useTerminologyStore } from '@/features/terminology/terminology.store'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
</script>

<template>
  <div class="aggregate-container-node">
    <!-- Aggregate boundary header -->
    <div class="container-header">
      <div class="container-stereotype">&laquo;Aggregate&raquo;</div>
      <div class="bc-name">{{ terminologyStore.ubiquitousLanguageMode ? (data.bcDisplayName || data.bcName) : data.bcName }}</div>
    </div>
    
    <!-- Container content area (children will be positioned here) -->
    <div class="container-content">
      <!-- This area is for child nodes (Aggregate, Enum, VO) -->
    </div>
  </div>
</template>

<style scoped>
.aggregate-container-node {
  width: 100%;
  height: 100%;
  /* Subtle aggregate-yellow tint so the grouping box reads as an aggregate boundary */
  background: color-mix(in srgb, var(--color-bc-bg) 90%, var(--color-aggregate, #fcc419));
  border: 2px solid rgba(252, 196, 25, 0.55);
  border-radius: 12px;
  position: relative;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  overflow: visible;
  display: flex;
  flex-direction: column;
  cursor: move;
  user-select: none;
}

:root.theme-light .aggregate-container-node {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.container-header {
  background: color-mix(in srgb, var(--color-bc-bg) 78%, var(--color-aggregate, #fcc419));
  border-bottom: 2px solid rgba(252, 196, 25, 0.55);
  border-radius: 10px 10px 0 0;
  padding: 8px 16px;
  text-align: center;
  flex-shrink: 0;
  z-index: 1;
  cursor: move;
  user-select: none;
}

.container-stereotype {
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: color-mix(in srgb, var(--color-bc-text) 55%, var(--color-aggregate, #fcc419));
  margin-bottom: 2px;
}

.bc-name {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--color-bc-text);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.container-content {
  position: relative;
  flex: 1;
  width: 100%;
  overflow: visible;
}
</style>
