<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '@/features/terminology/terminology.store'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
const headerText = computed(() => `<< ${terminologyStore.getTerm('UI')} >>`)

// Show template preview indicator
const hasTemplate = computed(() => !!props.data?.template)
</script>

<template>
  <div class="es-node es-node--ui" :class="{ 'has-template': hasTemplate }">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ data?.name }}</div>

      <!-- Attached To Indicator -->
      <div v-if="data?.attachedToName" class="es-node__attached">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
        </svg>
        <span>{{ data.attachedToName }}</span>
      </div>

      <!-- Template status -->
      <div class="es-node__status" :class="{ 'has-template': hasTemplate }">
        <span v-if="hasTemplate">✓ Wireframe</span>
        <span v-else>No wireframe</span>
      </div>
    </div>

    <!-- Connection handles -->
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>

<style scoped>
.es-node--ui {
  background: linear-gradient(180deg, var(--color-ui-light) 0%, #f8f9fa 100%);
  min-width: 120px;
  max-width: 140px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  border: 2px solid #dee2e6;
}

.es-node--ui.has-template {
  border-color: var(--color-readmodel);
}

.es-node--ui:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
}

.es-node__header {
  background: rgba(0, 0, 0, 0.05);
  padding: 4px 10px;
  border-radius: 6px 6px 0 0;
  font-size: 0.6rem;
  font-weight: 500;
  text-align: center;
  color: #495057;
}

.es-node__body {
  padding: 6px 10px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.es-node__name {
  font-size: 0.8rem;
  font-weight: 600;
  color: #212529;
  text-align: center;
  line-height: 1.2;
  word-break: break-word;
}

.es-node__attached {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.6rem;
  color: #868e96;
  padding: 2px 6px;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 10px;
}

.es-node__attached svg {
  flex-shrink: 0;
}

.es-node__attached span {
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.es-node__status {
  font-size: 0.55rem;
  color: #adb5bd;
  padding: 2px 6px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 4px;
}

.es-node__status.has-template {
  color: var(--color-readmodel);
  background: rgba(64, 192, 87, 0.1);
}

/* Handle styling */
::deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: #dee2e6;
  border: 2px solid var(--color-ui);
}

.es-node--ui.has-template :deep(.vue-flow__handle) {
  background: var(--color-readmodel);
  border-color: var(--color-readmodel-dark);
}
</style>


