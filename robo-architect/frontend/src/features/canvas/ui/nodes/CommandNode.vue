<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '@/features/terminology/terminology.store'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
const headerText = computed(() => `<< ${terminologyStore.getTerm('Command')} >>`)
</script>

<template>
  <div class="es-node es-node--command">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ data.name }}</div>
      <div v-if="data.actor" class="es-node__actor">
        <!-- Stick Figure Actor -->
        <svg class="es-node__actor-icon" viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="4" r="3" fill="none" stroke="currentColor" stroke-width="1.5"/>
          <line x1="12" y1="7" x2="12" y2="15" stroke="currentColor" stroke-width="1.5"/>
          <line x1="12" y1="15" x2="8" y2="22" stroke="currentColor" stroke-width="1.5"/>
          <line x1="12" y1="15" x2="16" y2="22" stroke="currentColor" stroke-width="1.5"/>
          <line x1="6" y1="11" x2="18" y2="11" stroke="currentColor" stroke-width="1.5"/>
        </svg>
        <span>{{ data.actor }}</span>
      </div>
    </div>
    
    <!-- Connection handles -->
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>

<style scoped>
.es-node--command {
  background: linear-gradient(180deg, #5c7cfa 0%, #4263eb 100%);
  min-width: 130px;
}

.es-node__header {
  background: rgba(0, 0, 0, 0.15);
  padding: 4px 10px;
  border-radius: 8px 8px 0 0;
  font-size: 0.6rem;
  font-weight: 500;
  text-align: center;
  color: rgba(255, 255, 255, 0.85);
}

.es-node__body {
  padding: 10px 12px 12px;
}

.es-node__name {
  font-size: 0.9rem;
  font-weight: 600;
  color: white;
  text-align: center;
}

.es-node__actor {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.8);
}

.es-node__actor-icon {
  width: 20px;
  height: 20px;
}

/* Handle styling */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid #4263eb;
}
</style>

