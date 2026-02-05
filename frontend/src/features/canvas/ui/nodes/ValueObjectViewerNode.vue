<script setup>
import { Handle, Position } from '@vue-flow/core'

const props = defineProps({
  id: String,
  data: Object
})
</script>

<template>
  <div class="vo-viewer-node">
    <div class="node-header">
      <span class="node-type-badge">ValueObject</span>
      <span v-if="data.referencedAggregateName" class="node-ref-badge">
        → {{ data.referencedAggregateName }}
        <span v-if="data.referencedAggregateField">.{{ data.referencedAggregateField }}</span>
      </span>
    </div>
    <div class="node-name">{{ data.name }}</div>
    <div v-if="data.alias" class="node-alias">{{ data.alias }}</div>
    
    <div class="node-section">
      <div class="section-divider"></div>
      <div class="section-label">Fields</div>
      <div v-if="data.fields && data.fields.length > 0" class="node-fields-list">
        <div v-for="(field, idx) in data.fields" :key="idx" class="node-field">
          <span class="field-name">{{ field.name }}</span>
          <span class="field-type">: {{ field.type }}</span>
        </div>
      </div>
      <div v-else class="node-fields-placeholder">
        <span class="placeholder-text">Click to edit fields</span>
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
.vo-viewer-node {
  background: #fff9e6;
  border: 2px solid #fcc419;
  border-radius: 8px;
  min-width: 160px;
  max-width: 220px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.vo-viewer-node:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 6px 6px 0 0;
  font-size: 0.65rem;
  gap: 6px;
}

.node-type-badge {
  font-weight: 600;
  color: rgba(30, 30, 46, 0.8);
}

.node-ref-badge {
  font-size: 0.6rem;
  color: rgba(30, 30, 46, 0.7);
  font-weight: 500;
}

.node-name {
  padding: 10px 12px 6px;
  font-size: 1rem;
  font-weight: 700;
  color: #1e1e2e;
  text-align: center;
}

.node-alias {
  padding: 0 12px 8px;
  font-size: 0.75rem;
  color: rgba(30, 30, 46, 0.7);
  text-align: center;
  font-style: italic;
}

.node-section {
  padding: 4px 0;
}

.section-divider {
  height: 1px;
  background: rgba(30, 30, 46, 0.2);
  margin: 4px 12px;
}

.section-label {
  padding: 4px 12px;
  font-size: 0.7rem;
  font-weight: 600;
  color: rgba(30, 30, 46, 0.7);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.node-fields-list {
  padding: 4px 0;
}

.node-field {
  padding: 4px 12px;
  font-size: 0.85rem;
  color: #1e1e2e;
  display: flex;
  gap: 6px;
}

.field-name {
  font-weight: 500;
}

.field-type {
  color: rgba(30, 30, 46, 0.7);
  font-style: italic;
}

.node-fields-placeholder {
  padding: 8px 12px;
  text-align: center;
}

.placeholder-text {
  font-size: 0.75rem;
  color: rgba(30, 30, 46, 0.6);
  font-style: italic;
}
</style>
