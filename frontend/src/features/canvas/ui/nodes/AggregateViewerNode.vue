<script setup>
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '@/features/terminology/terminology.store'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
</script>

<template>
  <div class="aggregate-viewer-node">
    <div class="node-header">
      <span class="node-type-badge">Aggregate Root</span>
      <!-- <span class="node-bc-name">{{ data.bcName }}</span> -->
    </div>
    <div class="node-name">{{ terminologyStore.ubiquitousLanguageMode ? (data.displayName || data.name) : data.name }}</div>
    <div v-if="data.rootEntity" class="node-root-entity">
      {{ data.rootEntity }}
    </div>
    
    <div v-if="data.properties && data.properties.length > 0" class="node-section">
      <div class="section-divider"></div>
      <div v-for="prop in data.properties" :key="prop.id || prop.name" class="node-field node-field-with-handle">
        <!-- Left side target handle for incoming edges -->
        <Handle 
          :id="prop.id ? `field-${String(prop.id)}-target-left` : (prop.name ? `field-${String(prop.name)}-target-left` : `field-unknown-${prop.id || prop.name}-target-left`)"
          type="target" 
          :position="Position.Left"
          class="field-handle field-handle--left"
        />
        <!-- Right side target handle for incoming edges (allows connections from right side) -->
        <Handle 
          :id="prop.id ? `field-${String(prop.id)}-target-right` : (prop.name ? `field-${String(prop.name)}-target-right` : `field-unknown-${prop.id || prop.name}-target-right`)"
          type="target" 
          :position="Position.Right"
          class="field-handle field-handle--right"
        />
        <!-- Right side source handle for outgoing edges -->
        <Handle 
          :id="prop.id ? `field-${String(prop.id)}-source` : (prop.name ? `field-${String(prop.name)}-source` : `field-unknown-${prop.id || prop.name}-source`)"
          type="source" 
          :position="Position.Right"
          class="field-handle field-handle--right"
        />
        <span class="field-badges">
          <span v-if="prop.isKey" class="badge badge--key">PK</span>
          <span v-if="prop.isForeignKey" class="badge badge--fk">FK</span>
        </span>
        <span class="field-name">{{ terminologyStore.ubiquitousLanguageMode ? (prop.displayName || prop.name) : prop.name }}</span>
        <span class="field-type">: {{ prop.type }}</span>
      </div>
    </div>

    <div v-if="data.enumerations && data.enumerations.length > 0" class="node-section">
      <div class="section-divider"></div>
      <div class="section-label">Enumerations</div>
      <div v-for="enumItem in data.enumerations" :key="`enum-${enumItem.name}`" class="node-field">
        <span class="field-name">{{ terminologyStore.ubiquitousLanguageMode ? (enumItem.displayName || enumItem.name) : enumItem.name }}</span>
        <span class="field-type">: Enum</span>
      </div>
    </div>

    <div v-if="data.valueObjects && data.valueObjects.length > 0" class="node-section">
      <div class="section-divider"></div>
      <div class="section-label">Value Objects</div>
      <div v-for="vo in data.valueObjects" :key="`vo-${vo.name}`" class="node-field">
        <span class="field-name">{{ terminologyStore.ubiquitousLanguageMode ? (vo.displayName || vo.name) : vo.name }}</span>
        <span class="field-type">: ValueObject</span>
        <span v-if="vo.referencedAggregateName" class="field-ref">
          → {{ vo.referencedAggregateName }}
          <span v-if="vo.referencedAggregateField">.{{ vo.referencedAggregateField }}</span>
        </span>
      </div>
    </div>

    <!-- Handles: both source and target on each side for bidirectional connections -->
    <!-- IMPORTANT: Each handle must have a unique ID for Vue Flow to identify them correctly -->
    <Handle type="source" :position="Position.Left" id="left-source" />
    <Handle type="target" :position="Position.Left" id="left-target" />
    <Handle type="source" :position="Position.Right" id="right-source" />
    <Handle type="target" :position="Position.Right" id="right-target" />
  </div>
</template>

<style scoped>
.aggregate-viewer-node {
  background: linear-gradient(180deg, #fcc419 0%, #f59f00 100%);
  border: 2px solid #e8590c;
  border-radius: 8px;
  min-width: 200px;
  max-width: 280px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.aggregate-viewer-node:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.node-header {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 6px 10px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 6px 6px 0 0;
  font-size: 0.65rem;
}

.node-type-badge {
  font-weight: 600;
  color: rgba(0, 0, 0, 0.8);
}

.node-bc-name {
  font-size: 0.6rem;
  color: rgba(0, 0, 0, 0.6);
  font-weight: 500;
}

.node-name {
  padding: 10px 12px 6px;
  font-size: 1.1rem;
  font-weight: 700;
  color: #212529;
  text-align: center;
}

.node-root-entity {
  padding: 0 12px 8px;
  font-size: 0.75rem;
  color: rgba(0, 0, 0, 0.7);
  text-align: center;
  font-style: italic;
}

.node-section {
  padding: 4px 0;
}

.section-divider {
  height: 1px;
  background: rgba(0, 0, 0, 0.15);
  margin: 4px 12px;
}

.section-label {
  padding: 4px 12px;
  font-size: 0.7rem;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.node-field {
  display: flex;
  align-items: center;
  padding: 3px 12px;
  font-size: 0.85rem;
  color: #212529;
  gap: 6px;
}

.node-field-with-handle {
  position: relative;
}

/* Vue Flow Handle styling for field connection points */
.node-field-with-handle :deep(.vue-flow__handle) {
  position: absolute;
  top: 50% !important;
  transform: translateY(-50%) !important;
  width: 6px !important;
  height: 6px !important;
  background: #5c7cfa !important;
  border: 1.5px solid white !important;
  border-radius: 50% !important;
  opacity: 1 !important;
  transition: all 0.2s !important;
  z-index: 10 !important;
  cursor: pointer;
}

/* Left side handle */
.node-field-with-handle :deep(.field-handle--left) {
  left: -8px !important;
}

/* Right side handle */
.node-field-with-handle :deep(.field-handle--right) {
  right: -8px !important;
}

.node-field-with-handle:hover :deep(.vue-flow__handle) {
  width: 8px !important;
  height: 8px !important;
  background: #4263eb !important;
  box-shadow: 0 0 4px rgba(92, 124, 250, 0.6) !important;
}

.field-badges {
  display: flex;
  gap: 4px;
  min-width: 40px;
}

.badge {
  font-size: 0.6rem;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 600;
}

.badge--key {
  background: #40c057;
  color: white;
}

.badge--fk {
  background: #5c7cfa;
  color: white;
}

.field-name {
  font-weight: 500;
  flex: 1;
}

.field-type {
  color: rgba(0, 0, 0, 0.6);
  font-style: italic;
}

.field-ref {
  font-size: 0.75rem;
  color: #5c7cfa;
  font-weight: 500;
}
</style>
