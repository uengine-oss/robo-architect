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

const hasProperties = computed(() => Array.isArray(props.data?.properties) && props.data.properties.length > 0)
const nodeStyle = computed(() => {
  const h = props.data?.dynamicHeight
  if (h && Number(h) > 0) return { height: `${h}px` }
  return {}
})
</script>

<template>
  <div class="es-node es-node--command" :style="nodeStyle">
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

/* Handle styling */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid #4263eb;
}
</style>

