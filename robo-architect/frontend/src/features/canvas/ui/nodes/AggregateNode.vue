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

const hasProperties = computed(() => Array.isArray(props.data?.properties) && props.data.properties.length > 0)

// Dynamic height based on (a) the number of Commands this Aggregate spans and (b) embedded properties
const nodeStyle = computed(() => {
  const dynamicHeight = props.data?.dynamicHeight
  if (dynamicHeight && Number(dynamicHeight) > 0) {
    return { height: `${dynamicHeight}px` }
  }
  return {}
})
</script>

<template>
  <div class="es-node es-node--aggregate" :style="nodeStyle">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ data.name }}</div>
      <div v-if="data.rootEntity" class="es-node__root">
        {{ data.rootEntity }}
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

.es-node__props {
  margin-top: 10px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 6px;
  font-size: 0.7rem;
}

.es-node__prop {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 6px;
  padding: 3px 4px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
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
  background: rgba(0, 0, 0, 0.12);
  color: rgba(0, 0, 0, 0.75);
}

.prop-name {
  font-weight: 600;
  color: rgba(0, 0, 0, 0.8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prop-type {
  color: rgba(0, 0, 0, 0.55);
  font-style: italic;
}

/* Handle styling */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid #f59f00;
}
</style>

