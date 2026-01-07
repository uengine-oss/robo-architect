<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '@/features/terminology/terminology.store'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
const headerText = computed(() => `<< ${terminologyStore.getTerm('Event')} >>`)

const hasProperties = computed(() => Array.isArray(props.data?.properties) && props.data.properties.length > 0)
const nodeStyle = computed(() => {
  const h = props.data?.dynamicHeight
  if (h && Number(h) > 0) return { height: `${h}px` }
  return {}
})
</script>

<template>
  <div class="es-node es-node--event" :style="nodeStyle" title="더블클릭: Inspector 열기 · Shift+더블클릭: Triggered Policy 확장">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ data.name }}</div>
      <div v-if="data.version" class="es-node__version">
        v{{ data.version }}
      </div>

      <div v-if="hasProperties" class="es-node__props">
        <div v-for="prop in data.properties" :key="prop.id" class="es-node__prop">
          <span class="prop-badges">
            <span v-if="prop.isKey" class="prop-badge prop-badge--key">PK</span>
            <span v-if="prop.isForeignKey" class="prop-badge prop-badge--fk">FK</span>
          </span>
          <span class="prop-name">{{ prop.name }}</span>
          <span class="prop-type">{{ prop.type }}</span>
        </div>
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

.es-node__props {
  margin-top: 10px;
  padding: 6px;
  background: rgba(0, 0, 0, 0.12);
  border-radius: 6px;
  font-size: 0.7rem;
}

.es-node__prop {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 6px;
  padding: 3px 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
}

.es-node__prop:last-child {
  border-bottom: none;
}

.prop-badges {
  display: inline-flex;
  gap: 4px;
}

.prop-badge {
  font-size: 0.55rem;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.18);
  color: rgba(255, 255, 255, 0.9);
}

.prop-badge--key {
  background: rgba(255, 255, 255, 0.22);
}

.prop-badge--fk {
  background: rgba(255, 255, 255, 0.14);
}

.prop-name {
  font-weight: 600;
  color: rgba(255, 255, 255, 0.95);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prop-type {
  color: rgba(255, 255, 255, 0.75);
  font-style: italic;
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

