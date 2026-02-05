<script setup>
import { computed } from 'vue'
import { getStraightPath } from '@vue-flow/core'

const props = defineProps([
  'id',
  'sourceX', 'sourceY',
  'targetX', 'targetY',
  'sourcePosition', 'targetPosition',
  'data', 'markerEnd', 'style',
])

// Use straight path for shortest distance
const path = computed(() => {
  const [p] = getStraightPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
  })
  return p
})
</script>

<template>
  <path class="vue-flow__edge-path" :d="path" :style="style" :marker-end="markerEnd" />
</template>
