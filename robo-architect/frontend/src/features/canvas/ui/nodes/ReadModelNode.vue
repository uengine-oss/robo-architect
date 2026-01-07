<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '@/features/terminology/terminology.store'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
const headerText = computed(() => `<< ${terminologyStore.getTerm('ReadModel')} >>`)

const hasProperties = computed(() => props.data?.properties && props.data.properties.length > 0)
const nodeStyle = computed(() => {
  const h = props.data?.dynamicHeight
  if (h && Number(h) > 0) return { height: `${h}px` }
  return {}
})

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

</script>

<template>
  <div class="es-node es-node--readmodel" :style="nodeStyle" :class="{ 'has-properties': hasProperties }">
    <div class="es-node__header">
      {{ headerText }}
      <span class="provisioning-badge" :class="provisioningBadge.class">
        {{ provisioningBadge.text }}
      </span>
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ data?.name }}</div>

      <!-- Properties List -->
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
  font-size: 0.8rem;
  font-weight: 700;
  color: #1b5e20;
  text-align: center;
}

.es-node__props {
  margin-top: 8px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 4px;
  font-size: 0.65rem;
}

.es-node__prop {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 6px;
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


