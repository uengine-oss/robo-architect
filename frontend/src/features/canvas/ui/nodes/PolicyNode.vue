<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '@/features/terminology/terminology.store'
import { useCanvasStore } from '@/features/canvas/canvas.store'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
const canvasStore = useCanvasStore()
const headerText = computed(() => `<< ${terminologyStore.getTerm('Policy')} >>`)

const hasGWT = computed(() => !!(props.data?.given || props.data?.when || props.data?.then))
const shouldShowGWT = computed(() => {
  return canvasStore.showDesignLevel && hasGWT.value
})

const nodeStyle = computed(() => {
  const baseHeight = 60
  let computedHeight = baseHeight
  
  // Add height for GWT if it should be shown
  if (shouldShowGWT.value && hasGWT.value) {
    const gwtCount = [props.data?.given, props.data?.when, props.data?.then].filter(Boolean).length
    const gwtHeight = 10 + 12 + (gwtCount * 24)
    computedHeight = baseHeight + gwtHeight
  }
  
  return { height: `${computedHeight}px` }
})
</script>

<template>
  <div class="es-node es-node--policy" :style="nodeStyle">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ data.name }}</div>

      <!-- GWT Section (Given/When/Then) -->
      <div v-if="shouldShowGWT" class="es-node__gwt">
        <div v-if="data.given" class="gwt-item gwt-item--given">
          <span class="gwt-label">Given:</span>
          <span class="gwt-value">{{ data.given.name }}</span>
        </div>
        <div v-if="data.when" class="gwt-item gwt-item--when">
          <span class="gwt-label">When:</span>
          <span class="gwt-value">{{ data.when.name }}</span>
        </div>
        <div v-if="data.then" class="gwt-item gwt-item--then">
          <span class="gwt-label">Then:</span>
          <span class="gwt-value">{{ data.then.name }}</span>
        </div>
      </div>
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

/* GWT Section */
.es-node__gwt {
  margin-top: 10px;
  padding: 6px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 6px;
  font-size: 0.7rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.gwt-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.gwt-item:last-child {
  border-bottom: none;
}

.gwt-label {
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
  min-width: 50px;
  font-size: 0.65rem;
}

.gwt-value {
  flex: 1;
  color: rgba(255, 255, 255, 0.85);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  word-break: break-word;
}

/* Handle styling */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid #9775fa;
}
</style>

