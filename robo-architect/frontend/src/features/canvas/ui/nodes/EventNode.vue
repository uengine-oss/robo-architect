<script setup>
import { ref, computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { useTerminologyStore } from '@/features/terminology/terminology.store'

const props = defineProps({
  id: String,
  data: Object
})

const canvasStore = useCanvasStore()
const terminologyStore = useTerminologyStore()
const isExpanding = ref(false)
const headerText = computed(() => `<< ${terminologyStore.getTerm('Event')} >>`)

// Double-click to expand triggered policies
async function handleDoubleClick() {
  if (isExpanding.value) return
  
  isExpanding.value = true
  try {
    const newNodes = await canvasStore.expandEventTriggers(props.id)
    if (newNodes.length > 0) {
      console.log(`Expanded ${newNodes.length} nodes from event triggers`)
    }
  } finally {
    isExpanding.value = false
  }
}
</script>

<template>
  <div 
    class="es-node es-node--event"
    :class="{ 'is-expanding': isExpanding }"
    @dblclick="handleDoubleClick"
  >
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ data.name }}</div>
      <div v-if="data.version" class="es-node__version">
        v{{ data.version }}
      </div>
      <div v-if="isExpanding" class="es-node__loading">
        Expanding...
      </div>
    </div>
    
    <!-- Connection handles -->
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>

<style scoped>
.es-node--event {
  background: linear-gradient(180deg, #fd7e14 0%, #e8590c 100%);
  min-width: 130px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.es-node--event:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(253, 126, 20, 0.4);
}

.es-node--event.is-expanding {
  opacity: 0.7;
  pointer-events: none;
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

.es-node__version {
  margin-top: 4px;
  font-size: 0.65rem;
  color: rgba(255, 255, 255, 0.7);
  text-align: center;
}

.es-node__loading {
  margin-top: 6px;
  font-size: 0.6rem;
  color: rgba(255, 255, 255, 0.8);
  text-align: center;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

/* Handle styling */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid #e8590c;
}
</style>

