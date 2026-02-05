<script setup>
import { computed } from 'vue'

const props = defineProps([
  'id',
  'sourceX', 'sourceY',
  'targetX', 'targetY',
  'sourcePosition', 'targetPosition',
  'data', 'markerEnd', 'style',
])

// Calculate step path (right-angle turns) manually
// This creates a path with one horizontal and one vertical segment
const path = computed(() => {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition } = props
  
  // Determine the step point (midpoint)
  // For step path, we use the midpoint between source and target
  const midX = (sourceX + targetX) / 2
  const midY = (sourceY + targetY) / 2
  
  // Create step path: source -> midpoint (horizontal) -> target (vertical)
  // Or: source -> midpoint (vertical) -> target (horizontal) depending on positions
  let stepX, stepY
  
  // Determine step direction based on source and target positions
  if (sourcePosition === 'right' && targetPosition === 'left') {
    // Source on right, target on left: go horizontal first, then vertical
    stepX = midX
    stepY = sourceY
  } else if (sourcePosition === 'left' && targetPosition === 'right') {
    // Source on left, target on right: go horizontal first, then vertical
    stepX = midX
    stepY = sourceY
  } else {
    // Default: use midpoint
    stepX = midX
    stepY = midY
  }
  
  // Create path with right-angle turn
  return `M ${sourceX},${sourceY} L ${stepX},${stepY} L ${targetX},${targetY}`
})
</script>

<template>
  <path class="vue-flow__edge-path" :d="path" :style="style" :marker-end="markerEnd" />
</template>
