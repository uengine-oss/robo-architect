<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '@/features/terminology/terminology.store'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
const headerText = computed(() => `<< ${terminologyStore.getTerm('Policy')} >>`)
const displayLabel = computed(() => terminologyStore.getLabel(props.data))

const nodeStyle = computed(() => {
  const baseHeight = 60
  return { height: `${baseHeight}px` }
})
</script>

<template>
  <div class="es-node es-node--policy" :style="nodeStyle">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ displayLabel }}</div>
    </div>
    
    <!-- Connection handles - Left/Right for optimal routing -->
    <Handle type="target" :position="Position.Left" id="left-target" />
    <Handle type="source" :position="Position.Left" id="left-source" />
    <Handle type="target" :position="Position.Right" id="right-target" />
    <Handle type="source" :position="Position.Right" id="right-source" />
  </div>
</template>

<style scoped>
.es-node--policy {
  background: linear-gradient(180deg, #b197fc 0%, #9775fa 100%);
  min-width: 120px;
}

.es-node__header {
  background: rgba(0, 0, 0, 0.12);
  padding: 4px 10px;
  border-radius: 8px 8px 0 0;
  font-size: 0.6rem;
  font-weight: 500;
  text-align: center;
  color: rgba(255, 255, 255, 0.85);
}

.es-node__body {
  padding: 8px 12px 10px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.es-node__name {
  font-size: 0.85rem;
  font-weight: 600;
  color: white;
  text-align: center;
}

/* Handle styling */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid #9775fa;
}
</style>

