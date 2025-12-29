<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '@/features/terminology/terminology.store'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
const headerText = computed(() => `<< ${terminologyStore.getTerm('Aggregate')} >>`)
</script>

<template>
  <div class="es-node es-node--aggregate">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ data.name }}</div>
      <div v-if="data.rootEntity" class="es-node__root">
        {{ data.rootEntity }}
      </div>
    </div>
    
    <!-- Connection handles -->
    <Handle type="target" :position="Position.Top" />
    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<style scoped>
.es-node--aggregate {
  background: linear-gradient(180deg, #fcc419 0%, #f59f00 100%);
  min-width: 140px;
}

.es-node__header {
  background: rgba(0, 0, 0, 0.1);
  padding: 4px 10px;
  border-radius: 8px 8px 0 0;
  font-size: 0.6rem;
  font-weight: 500;
  text-align: center;
  color: rgba(0, 0, 0, 0.7);
}

.es-node__body {
  padding: 10px 12px 12px;
}

.es-node__name {
  font-size: 0.95rem;
  font-weight: 700;
  color: #212529;
  text-align: center;
}

.es-node__root {
  margin-top: 4px;
  font-size: 0.7rem;
  color: rgba(0, 0, 0, 0.6);
  text-align: center;
}

/* Handle styling */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid #f59f00;
}
</style>

