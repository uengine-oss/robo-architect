<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useTerminologyStore } from '@/features/terminology/terminology.store'
import { useCanvasStore } from '@/features/canvas/canvas.store'

const props = defineProps({
  id: String,
  data: Object
})

const terminologyStore = useTerminologyStore()
const canvasStore = useCanvasStore()
const headerText = computed(() => `<< ${terminologyStore.getTerm('Event')} >>`)

const hasProperties = computed(() => Array.isArray(props.data?.properties) && props.data.properties.length > 0)
const displayLabel = computed(() => terminologyStore.getLabel(props.data))
// Access showDesignLevel directly - Pinia store refs are reactive
const shouldShowFields = computed(() => {
  return canvasStore.showDesignLevel && hasProperties.value
})

// Fetch outbound policy count from API (not just from canvas edges)
const outboundPolicyCount = ref(-1) // -1 means not loaded yet, 0 means no policies, >0 means has policies
const isLoadingPolicies = ref(false)

async function fetchOutboundPolicyCount() {
  if (isLoadingPolicies.value) return
  isLoadingPolicies.value = true
  try {
    const response = await fetch(`/api/graph/event-triggers/${props.id}`)
    if (response.ok) {
      const data = await response.json()
      // Count unique policies from relationships
      const policyIds = new Set()
      if (data.relationships) {
        data.relationships.forEach(rel => {
          if (rel.type === 'TRIGGERS' && rel.source === props.id) {
            policyIds.add(rel.target)
          }
        })
      }
      outboundPolicyCount.value = policyIds.size
    } else {
      // API call failed, but don't fallback to canvas edges (they require BC on canvas)
      // Keep previous value or set to -1 to indicate unknown
      if (outboundPolicyCount.value === -1) {
        outboundPolicyCount.value = 0
      }
    }
  } catch (error) {
    console.error('Failed to fetch outbound policies:', error)
    // API call failed, but don't fallback to canvas edges
    // Keep previous value or set to 0 to indicate no policies found
    if (outboundPolicyCount.value === -1) {
      outboundPolicyCount.value = 0
    }
  } finally {
    isLoadingPolicies.value = false
  }
}

// Use API count (always prefer API over canvas edges)
const finalPolicyCount = computed(() => {
  // If API hasn't loaded yet, return 0 to avoid showing badge prematurely
  if (outboundPolicyCount.value === -1) {
    return 0
  }
  return outboundPolicyCount.value
})

const hasOutboundPolicies = computed(() => finalPolicyCount.value > 0)

// Fetch on mount and when event ID changes
onMounted(() => {
  fetchOutboundPolicyCount()
})

watch(() => props.id, () => {
  fetchOutboundPolicyCount()
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
  <div class="es-node es-node--event" :style="nodeStyle" title="더블클릭: Inspector 열기 + Policy BC 자동 확장 · Shift+더블클릭: Triggered Policy 확장">
    <div class="es-node__header">
      {{ headerText }}
    </div>
    <div class="es-node__body">
      <div class="es-node__name">{{ displayLabel }}</div>
      <div v-if="data.version" class="es-node__version">
        v{{ data.version }}
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
    </div>
    
    <!-- Outbound policies badge -->
    <div v-if="hasOutboundPolicies" class="es-node__triggers">
      <span class="es-node__trigger-badge" :title="`${finalPolicyCount}개의 Policy를 트리거합니다`">
        policy: {{ finalPolicyCount }}
      </span>
    </div>
    
    <!-- Connection handles - Left/Right for optimal routing -->
    <Handle type="target" :position="Position.Left" id="left-target" />
    <Handle type="source" :position="Position.Left" id="left-source" />
    <Handle type="target" :position="Position.Right" id="right-target" />
    <Handle type="source" :position="Position.Right" id="right-source" />
  </div>
</template>

<style scoped>
.es-node--event {
  background: linear-gradient(180deg, #fd7e14 0%, #e8590c 100%);
  min-width: 130px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  position: relative;
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

/* Outbound policies badge */
.es-node__triggers {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 10;
}

.es-node__trigger-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 10px;
  font-size: 0.65rem;
  font-weight: 700;
  color: #e8590c;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  cursor: help;
}

.es-node__trigger-badge svg {
  flex-shrink: 0;
  stroke: #e8590c;
}
</style>

