<script setup>
import { computed, markRaw } from 'vue'
import { VueFlow, MarkerType } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import CommandNode from '@/features/canvas/ui/nodes/CommandNode.vue'
import EventNode from '@/features/canvas/ui/nodes/EventNode.vue'
import PolicyNode from '@/features/canvas/ui/nodes/PolicyNode.vue'
import AggregateNode from '@/features/canvas/ui/nodes/AggregateNode.vue'
import UINode from '@/features/canvas/ui/nodes/UINode.vue'

/**
 * Embedded design-trace canvas (026 — US2).
 * Renders the UI→command→aggregate→event→policy trajectory returned by
 * /api/requirements/user-story/{id}/design-trace. Stickers reuse the exact
 * Design-tab node components, so colours, layout, and property lists render
 * identically. Clicking a node emits `node-click` to open the inspector.
 */
const props = defineProps({
  trace: { type: Object, default: () => ({ nodes: [], relationships: [], empty: false }) },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['node-click'])

// Reuse the Design tab's node components verbatim.
const nodeTypes = {
  command: markRaw(CommandNode),
  event: markRaw(EventNode),
  policy: markRaw(PolicyNode),
  aggregate: markRaw(AggregateNode),
  ui: markRaw(UINode),
}

// Type → column index — same left-to-right order as the Design tab:
// UI → Command → Aggregate → Event (→ Policy).
const COLUMN = { UI: 0, Command: 1, Aggregate: 2, Event: 3, Policy: 4 }
const COL_W = 280
const ROW_H = 240

const flowNodes = computed(() => {
  const perColumn = {}
  return (props.trace?.nodes || []).map((n) => {
    const type = n.type || 'Command'
    const col = COLUMN[type] ?? 1
    const row = perColumn[col] || 0
    perColumn[col] = row + 1
    return {
      id: n.id,
      type: type.toLowerCase(),
      position: { x: col * COL_W, y: row * ROW_H },
      // Full node payload — node components read name/displayName/actor/properties/…
      data: { ...n, label: n.displayName || n.name || n.id },
    }
  })
})

// Column of each node, for choosing which handles an edge connects to.
const colById = computed(() => {
  const m = {}
  for (const n of props.trace?.nodes || []) {
    m[n.id] = COLUMN[n.type || 'Command'] ?? 1
  }
  return m
})

const flowEdges = computed(() =>
  (props.trace?.relationships || []).map((r, i) => {
    const srcCol = colById.value[r.source] ?? 0
    const tgtCol = colById.value[r.target] ?? 0
    const forward = tgtCol >= srcCol
    return {
      id: `e${i}-${r.source}-${r.target}`,
      source: r.source,
      target: r.target,
      sourceHandle: forward ? 'right-source' : 'left-source',
      targetHandle: forward ? 'left-target' : 'right-target',
      markerEnd: MarkerType.ArrowClosed,
      style: {
        stroke: '#868e96',
        strokeDasharray: r.type === 'ATTACHED_TO' ? '4 3' : undefined,
      },
    }
  }),
)

const isEmpty = computed(
  () => props.trace?.empty || (props.trace?.nodes || []).length === 0,
)

function onNodeClick({ node }) {
  if (node) emit('node-click', { id: node.id, type: node.data?.type, name: node.data?.name })
}
</script>

<template>
  <div class="trace-canvas">
    <div v-if="loading" class="trace-canvas__overlay">설계 괘적을 불러오는 중...</div>
    <div v-else-if="isEmpty" class="trace-canvas__overlay">
      연결된 설계가 없습니다.
    </div>
    <VueFlow
      v-else
      :nodes="flowNodes"
      :edges="flowEdges"
      :node-types="nodeTypes"
      :fit-view-on-init="true"
      :nodes-draggable="false"
      class="trace-canvas__flow"
      @node-click="onNodeClick"
    >
      <Background />
    </VueFlow>
  </div>
</template>

<style scoped>
@import '@vue-flow/core/dist/style.css';
@import '@vue-flow/core/dist/theme-default.css';

.trace-canvas { position: relative; width: 100%; height: 100%; min-height: 200px; }
.trace-canvas__flow { width: 100%; height: 100%; }
.trace-canvas__overlay {
  display: flex; align-items: center; justify-content: center;
  width: 100%; height: 100%; color: var(--color-text-light); font-size: 0.85rem;
}
</style>
