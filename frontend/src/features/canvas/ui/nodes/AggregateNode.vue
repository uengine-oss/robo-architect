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
const headerText = computed(() => `<< ${terminologyStore.getTerm('Aggregate')} >>`)
const displayLabel = computed(() => terminologyStore.getLabel(props.data))

const hasProperties = computed(() => Array.isArray(props.data?.properties) && props.data.properties.length > 0)
const hasEnumerations = computed(() => Array.isArray(props.data?.enumerations) && props.data.enumerations.length > 0)
const hasValueObjects = computed(() => Array.isArray(props.data?.valueObjects) && props.data.valueObjects.length > 0)
const hasFields = computed(() => hasProperties.value || hasEnumerations.value || hasValueObjects.value)
// Access showDesignLevel directly - Pinia store refs are reactive
const shouldShowFields = computed(() => {
  return canvasStore.showDesignLevel && hasFields.value
})

// Dynamic height based on (a) the number of Commands this Aggregate spans and (b) embedded properties
const nodeStyle = computed(() => {
  // Always compute height based on current showDesignLevel state
  const baseHeight = 80
  let computedHeight = baseHeight
  
  // Add height for fields if they should be shown
  if (shouldShowFields.value && hasFields.value) {
    const propsCount = (props.data?.properties || []).length
    const enumsCount = (props.data?.enumerations || []).length
    const vosCount = (props.data?.valueObjects || []).length
    const totalFields = propsCount + enumsCount + vosCount
    if (totalFields > 0) {
      // Section label (20px) + margin-top (10px) + padding (12px) + each field row (22px)
      const fieldsHeight = 20 + 10 + 12 + (totalFields * 22)
      computedHeight = baseHeight + fieldsHeight
    }
  }
  
  // Use dynamicHeight as base if available, but adjust for current state
  const dynamicHeight = props.data?.dynamicHeight
  if (dynamicHeight && Number(dynamicHeight) > 0) {
    // If fields should be shown but dynamicHeight doesn't account for them, use computed
    if (shouldShowFields.value && hasFields.value) {
      // Ensure height is at least what we computed
      computedHeight = Math.max(computedHeight, Number(dynamicHeight))
    } else if (!canvasStore.showDesignLevel && hasFields.value) {
      // If fields are hidden, reduce from dynamicHeight
      const propsCount = (props.data?.properties || []).length
      const enumsCount = (props.data?.enumerations || []).length
      const vosCount = (props.data?.valueObjects || []).length
      const totalFields = propsCount + enumsCount + vosCount
      if (totalFields > 0) {
        const fieldsHeight = 20 + 10 + 12 + (totalFields * 22)
        computedHeight = Math.max(120, Number(dynamicHeight) - fieldsHeight)
      } else {
        computedHeight = Number(dynamicHeight)
      }
    } else {
      computedHeight = Number(dynamicHeight)
    }
  }
  
  return { height: `${computedHeight}px` }
})
</script>

<template>
  <div class="es-node es-node--aggregate" :style="nodeStyle">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ displayLabel }}</div>
      <div v-if="data.rootEntity" class="es-node__root">
        {{ data.rootEntity }}
      </div>

      <div v-if="shouldShowFields" class="es-node__props">
        <div class="es-node__section-label">Properties</div>
        
        <!-- Regular Properties -->
        <div v-for="prop in (data.properties || [])" :key="prop.id" class="es-node__prop">
          <span class="prop-badges">
            <span v-if="prop.isKey" class="prop-badge prop-badge--key">PK</span>
            <span v-if="prop.isForeignKey" class="prop-badge prop-badge--fk">FK</span>
          </span>
          <span class="prop-name">{{ terminologyStore.ubiquitousLanguageMode ? (prop.displayName || prop.name) : prop.name }}</span>
          <span class="prop-type">{{ prop.type }}</span>
        </div>
        
        <!-- Enumerations as fields -->
        <div v-for="enumItem in (data.enumerations || [])" :key="`enum-${enumItem.name}`" class="es-node__prop">
          <span class="prop-badges"></span>
          <span class="prop-name">{{ terminologyStore.ubiquitousLanguageMode ? (enumItem.displayName || enumItem.name) : enumItem.name }}</span>
          <span class="prop-type">Enum</span>
        </div>
        
        <!-- Value Objects as fields -->
        <div v-for="vo in (data.valueObjects || [])" :key="`vo-${vo.name}`" class="es-node__prop">
          <span class="prop-badges"></span>
          <span class="prop-name">{{ terminologyStore.ubiquitousLanguageMode ? (vo.displayName || vo.name) : vo.name }}</span>
          <span class="prop-type">ValueObject</span>
        </div>
      </div>
    </div>
    
    <!-- Connection handles - Left/Right only for optimal routing -->
    <Handle type="target" :position="Position.Left" id="left-target" />
    <Handle type="source" :position="Position.Left" id="left-source" />
    <Handle type="target" :position="Position.Right" id="right-target" />
    <Handle type="source" :position="Position.Right" id="right-source" />
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
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
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
  min-width: 0;
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

.prop-badge--enum {
  background: rgba(92, 124, 250, 0.2);
  color: rgba(92, 124, 250, 0.9);
}

.prop-badge--vo {
  background: rgba(64, 192, 87, 0.2);
  color: rgba(64, 192, 87, 0.9);
}

.prop-badge--ref {
  background: rgba(253, 126, 20, 0.2);
  color: rgba(253, 126, 20, 0.9);
  font-size: 0.5rem;
}

.prop-name {
  font-weight: 600;
  color: rgba(0, 0, 0, 0.8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  word-break: break-word;
  max-width: 100%;
  min-width: 0;
}

.prop-type {
  color: rgba(0, 0, 0, 0.55);
  font-style: italic;
}

.es-node__section-label {
  font-size: 0.6rem;
  font-weight: 700;
  color: rgba(0, 0, 0, 0.5);
  text-transform: uppercase;
  margin-bottom: 4px;
  padding-bottom: 2px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.15);
}

/* Handle styling */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid #f59f00;
}
</style>

