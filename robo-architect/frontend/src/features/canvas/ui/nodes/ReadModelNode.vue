<script setup>
import { computed, ref, inject } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '@/features/terminology/terminology.store'

const props = defineProps({
  id: String,
  data: Object
})

// Inject the modal handler from CanvasWorkspace
const openCqrsConfigModal = inject('openCqrsConfigModal', null)

const terminologyStore = useTerminologyStore()
const headerText = computed(() => `<< ${terminologyStore.getTerm('ReadModel')} >>`)

const showProperties = ref(false)
const hasProperties = computed(() => props.data?.properties && props.data.properties.length > 0)

// Get provisioning type badge
const provisioningType = computed(() => props.data?.provisioningType || 'CQRS')
const provisioningBadge = computed(() => {
  const badges = {
    CQRS: { text: 'CQRS', class: 'badge--cqrs' },
    API: { text: 'API', class: 'badge--api' },
    GraphQL: { text: 'GQL', class: 'badge--graphql' },
    SharedDB: { text: 'DB', class: 'badge--shareddb' }
  }
  return badges[provisioningType.value] || badges.CQRS
})

function toggleProperties(e) {
  e.stopPropagation()
  showProperties.value = !showProperties.value
}

function openCqrsConfig(e) {
  e.stopPropagation()
  if (openCqrsConfigModal) {
    openCqrsConfigModal(props.id, props.data)
  }
}
</script>

<template>
  <div class="es-node es-node--readmodel" :class="{ 'has-properties': hasProperties }">
    <div class="es-node__header">
      {{ headerText }}
      <span class="provisioning-badge" :class="provisioningBadge.class">
        {{ provisioningBadge.text }}
      </span>
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ data?.name }}</div>
      <div v-if="data?.description" class="es-node__description">
        {{ data.description.slice(0, 50) }}{{ data.description.length > 50 ? '...' : '' }}
      </div>

      <!-- CQRS Config Button (only for CQRS type) -->
      <div v-if="provisioningType === 'CQRS'" class="es-node__cqrs-btn" @click="openCqrsConfig">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
        <span>설정</span>
      </div>

      <!-- Properties Toggle -->
      <div v-if="hasProperties" class="es-node__props-toggle" @click="toggleProperties">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline v-if="!showProperties" points="9 18 15 12 9 6"></polyline>
          <polyline v-else points="18 15 12 9 6 15"></polyline>
        </svg>
        <span>{{ data.properties.length }} fields</span>
      </div>

      <!-- Properties List -->
      <div v-if="hasProperties && showProperties" class="es-node__props">
        <div v-for="prop in data.properties" :key="prop.id" class="es-node__prop">
          <span class="prop-name">{{ prop.name }}</span>
          <span class="prop-type">{{ prop.type }}</span>
        </div>
      </div>
    </div>

    <!-- Connection handles -->
    <Handle type="target" :position="Position.Left" id="left" />
    <Handle type="source" :position="Position.Right" id="right" />
  </div>
</template>

<style scoped>
.es-node--readmodel {
  background: linear-gradient(180deg, var(--color-readmodel-light) 0%, var(--color-readmodel) 100%);
  min-width: 160px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(64, 192, 87, 0.3);
}

.es-node--readmodel.has-properties {
  min-width: 180px;
}

.es-node__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(0, 0, 0, 0.1);
  padding: 4px 10px;
  border-radius: 8px 8px 0 0;
  font-size: 0.6rem;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.7);
}

.provisioning-badge {
  font-size: 0.55rem;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 3px;
  text-transform: uppercase;
}

.badge--cqrs {
  background: rgba(0, 0, 0, 0.15);
  color: #1b5e20;
}

.badge--api {
  background: rgba(92, 124, 250, 0.2);
  color: #1a237e;
}

.badge--graphql {
  background: rgba(233, 30, 99, 0.15);
  color: #880e4f;
}

.badge--shareddb {
  background: rgba(255, 193, 7, 0.2);
  color: #795548;
}

.es-node__body {
  padding: 10px 12px 12px;
}

.es-node__name {
  font-size: 0.95rem;
  font-weight: 700;
  color: #1b5e20;
  text-align: center;
}

.es-node__description {
  margin-top: 4px;
  font-size: 0.65rem;
  color: rgba(0, 0, 0, 0.6);
  text-align: center;
  line-height: 1.3;
}

.es-node__cqrs-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 8px;
  padding: 4px 8px;
  background: rgba(27, 94, 32, 0.15);
  border-radius: 4px;
  font-size: 0.65rem;
  color: #1b5e20;
  cursor: pointer;
  transition: background 0.15s;
}

.es-node__cqrs-btn:hover {
  background: rgba(27, 94, 32, 0.25);
}

.es-node__props-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 8px;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  font-size: 0.65rem;
  color: rgba(0, 0, 0, 0.7);
  cursor: pointer;
  transition: background 0.15s;
}

.es-node__props-toggle:hover {
  background: rgba(0, 0, 0, 0.15);
}

.es-node__props {
  margin-top: 8px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 4px;
  font-size: 0.65rem;
  max-height: 120px;
  overflow-y: auto;
}

.es-node__prop {
  display: flex;
  justify-content: space-between;
  padding: 2px 4px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

.es-node__prop:last-child {
  border-bottom: none;
}

.prop-name {
  font-weight: 600;
  color: #1b5e20;
}

.prop-type {
  color: rgba(0, 0, 0, 0.6);
  font-style: italic;
}

/* Handle styling */
::deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  background: white;
  border: 2px solid var(--color-readmodel);
}
</style>


