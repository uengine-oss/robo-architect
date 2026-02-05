<script setup>
import { computed } from 'vue'
import { getSmoothStepPath } from '@vue-flow/core'

const props = defineProps([
  'id',
  'sourceX', 'sourceY',
  'targetX', 'targetY',
  'sourcePosition', 'targetPosition',
  'data', 'markerEnd', 'style',
])

// path는 그대로 smoothstep 사용
const path = computed(() => {
  const [p] = getSmoothStepPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
    sourcePosition: props.sourcePosition,
    targetPosition: props.targetPosition,
  })
  return p
})

// 핵심: 실제로 Vue Flow가 사용하는 앵커 좌표 출력
if (import.meta.env.DEV) {
  console.log('[DebugEdge]', props.id, {
    source: { x: props.sourceX, y: props.sourceY, pos: props.sourcePosition },
    target: { x: props.targetX, y: props.targetY, pos: props.targetPosition },
    data: props.data,
  })
}
</script>

<template>
  <path class="vue-flow__edge-path" :d="path" :style="style" :marker-end="markerEnd" />
</template>
