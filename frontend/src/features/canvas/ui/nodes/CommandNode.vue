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
const headerText = computed(() => `<< ${terminologyStore.getTerm('Command')} >>`)
const displayLabel = computed(() => terminologyStore.getLabel(props.data))

const hasProperties = computed(() => Array.isArray(props.data?.properties) && props.data.properties.length > 0)
const hasGWT = computed(() => !!(props.data?.given || props.data?.when || props.data?.then))
// Access showDesignLevel directly - Pinia store refs are reactive
const shouldShowFields = computed(() => {
  return canvasStore.showDesignLevel && hasProperties.value
})
const shouldShowGWT = computed(() => {
  return canvasStore.showDesignLevel && hasGWT.value
})
const nodeStyle = computed(() => {
  // Always compute height based on current showDesignLevel state
  const baseHeight = 80
  let computedHeight = baseHeight
  
  // Add height for properties if they should be shown
  if (shouldShowFields.value && hasProperties.value) {
    // Actual height: margin-top (10px) + padding (12px) + (rows * 22px)
    const propsHeight = 10 + 12 + (props.data.properties.length * 22)
    computedHeight = baseHeight + propsHeight
  }
  
  // Add height for GWT if it should be shown
  if (shouldShowGWT.value && hasGWT.value) {
    const gwtCount = [props.data?.given, props.data?.when, props.data?.then].filter(Boolean).length
    const gwtHeight = 10 + 12 + (gwtCount * 24) // Similar to props height calculation
    computedHeight = baseHeight + gwtHeight
  }
  
  // Use dynamicHeight as base if available, but adjust for current state
  const h = props.data?.dynamicHeight
  if (h && Number(h) > 0) {
    // If fields should be shown but dynamicHeight doesn't account for them, use computed
    if (shouldShowFields.value && hasProperties.value) {
      // Ensure height is at least what we computed
      computedHeight = Math.max(computedHeight, Number(h))
    } else if (!canvasStore.showDesignLevel && hasProperties.value) {
      // If fields are hidden, reduce from dynamicHeight
      const propsHeight = 10 + 12 + (props.data.properties.length * 22)
      computedHeight = Math.max(baseHeight, Number(h) - propsHeight)
    } else {
      computedHeight = Number(h)
    }
  }
  
  return { height: `${computedHeight}px` }
})
</script>

<template>
  <div class="es-node es-node--command" :style="nodeStyle">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ displayLabel }}</div>
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

      <div v-if="shouldShowFields" class="es-node__props">
        <div v-for="prop in data.properties" :key="prop.id" class="es-node__prop">
          <span class="prop-badges">
            <span v-if="prop.isKey" class="prop-badge prop-badge--key">PK</span>
            <span v-if="prop.isForeignKey" class="prop-badge prop-badge--fk">FK</span>
          </span>
          <span class="prop-name">{{ terminologyStore.ubiquitousLanguageMode ? (prop.displayName || prop.name) : prop.name }}</span>
          <span class="prop-type">{{ prop.type }}</span>
        </div>
      </div>

      <!-- GWT Section (Given/When/Then) -->
      <div v-if="data.given || data.when || data.then" class="es-node__gwt">
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
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
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
  word-break: break-word;
  max-width: 100%;
  min-width: 0;
}

.prop-type {
  color: rgba(255, 255, 255, 0.75);
  font-style: italic;
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

.gwt-item--given .gwt-label {
  color: rgba(255, 255, 255, 0.95);
}

.gwt-item--when .gwt-label {
  color: rgba(255, 255, 255, 0.95);
}

.gwt-item--then .gwt-label {
  color: rgba(255, 255, 255, 0.95);
}

/* Handle styling */
:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid #4263eb;
}
</style>

