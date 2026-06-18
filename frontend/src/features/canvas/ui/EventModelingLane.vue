<script setup>
/**
 * Event Modeling 형식 경량 렌더러 (spec 042 — US4).
 *
 * spec-039 `GET /api/graph/bpm-task/{id}/design-trace`의 `{nodes, relationships}`를
 * **가로 레인**(좌→우: UI → Command → Event → ReadModel, 정책은 Event 뒤)으로 렌더한다.
 * requirements 탭의 `DesignTraceCanvas`(DDD 컬럼 그래프)와 달리, event-modeling 흐름
 * 순서를 그대로 따른다. 노드 컴포넌트는 캔버스 것 그대로 재사용.
 */
import { computed } from 'vue'
import { VueFlow, MarkerType } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { markRaw } from 'vue'
import CommandNode from '@/features/canvas/ui/nodes/CommandNode.vue'
import EventNode from '@/features/canvas/ui/nodes/EventNode.vue'
import PolicyNode from '@/features/canvas/ui/nodes/PolicyNode.vue'
import ReadModelNode from '@/features/canvas/ui/nodes/ReadModelNode.vue'
import UINode from '@/features/canvas/ui/nodes/UINode.vue'

const props = defineProps({
  trace: { type: Object, default: () => ({ nodes: [], relationships: [], empty: false }) },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['node-click'])

const nodeTypes = {
  command: markRaw(CommandNode),
  event: markRaw(EventNode),
  policy: markRaw(PolicyNode),
  readmodel: markRaw(ReadModelNode),
  ui: markRaw(UINode),
}

// Event Modeling 흐름 순서: UI(액션) → Command → Event → ReadModel → UI(결과).
const COLUMN = { UI: 0, Command: 1, Event: 2, ReadModel: 3, Policy: 4 }
const RESULT_UI_COL = 5  // ReadModel의 결과 화면(042) — 맨 오른쪽.
const COL_W = 300
const ROW_H = 220

// 결과 UI = ReadModel→UI 관계(RESULT_UI/DISPLAYED_ON)의 타깃. 액션 UI(좌측)와 구분해 우측 배치.
const resultUiIds = computed(() => {
  const s = new Set()
  for (const r of props.trace?.relationships || []) {
    if (r.type === 'RESULT_UI' || r.type === 'DISPLAYED_ON') s.add(r.target)
  }
  return s
})

function colOf(n) {
  if ((n.type === 'UI') && resultUiIds.value.has(n.id)) return RESULT_UI_COL
  return COLUMN[n.type || 'Command'] ?? 1
}

// 043 US3 — ReadModel을 screen/inline/system 으로 분류(읽기측 설계 가시화).
//  screen = 자체 결과 화면(RESULT_UI), inline = 소비 화면에 표시(DISPLAYED_ON),
//  system = 사람 화면 없음(둘 다 없음). design_trace의 응답 관계 타입으로 판정.
const rmClassById = computed(() => {
  const out = {}
  const rels = props.trace?.relationships || []
  for (const n of props.trace?.nodes || []) {
    if ((n.type || '') !== 'ReadModel') continue
    const outs = rels.filter((r) => r.source === n.id)
    if (outs.some((r) => r.type === 'DISPLAYED_ON')) out[n.id] = 'inline'
    else if (outs.some((r) => r.type === 'RESULT_UI')) out[n.id] = 'screen'
    else out[n.id] = 'system'
  }
  return out
})

const flowNodes = computed(() => {
  const perColumn = {}
  return (props.trace?.nodes || [])
    .filter((n) => COLUMN[n.type || 'Command'] !== undefined)
    .map((n) => {
      const type = n.type || 'Command'
      const col = colOf(n)
      const row = perColumn[col] || 0
      perColumn[col] = row + 1
      const rmCls = type === 'ReadModel' ? rmClassById.value[n.id] : null
      return {
        id: n.id,
        type: type.toLowerCase(),
        position: { x: col * COL_W, y: row * ROW_H },
        data: { ...n, label: n.displayName || n.name || n.id },
        class: rmCls ? `rm-${rmCls}` : undefined,
      }
    })
})

const colById = computed(() => {
  const m = {}
  for (const n of props.trace?.nodes || []) m[n.id] = colOf(n)
  return m
})

// 관계 타입별 엣지 스타일/라벨 — screen(RESULT_UI)·inline(DISPLAYED_ON)을 색·점선·라벨로 변별.
const EDGE_STYLE = {
  RESULT_UI: { stroke: '#37b24d' },                       // screen 결과 화면 — 초록 실선
  DISPLAYED_ON: { stroke: '#f59f00', strokeDasharray: '5 3' }, // inline 표시 — 주황 점선
  ATTACHED_TO: { stroke: '#868e96', strokeDasharray: '4 3' },
}
const EDGE_LABEL = { RESULT_UI: '결과 화면', DISPLAYED_ON: '표시(inline)' }

const flowEdges = computed(() =>
  (props.trace?.relationships || []).map((r, i) => {
    const srcCol = colById.value[r.source] ?? 0
    const tgtCol = colById.value[r.target] ?? 0
    const forward = tgtCol >= srcCol
    const baseStyle = EDGE_STYLE[r.type] || { stroke: '#868e96' }
    const label = EDGE_LABEL[r.type]
    return {
      id: `e${i}-${r.source}-${r.target}`,
      source: r.source,
      target: r.target,
      sourceHandle: forward ? 'right-source' : 'left-source',
      targetHandle: forward ? 'left-target' : 'right-target',
      markerEnd: MarkerType.ArrowClosed,
      style: baseStyle,
      label,
      labelStyle: label ? { fontSize: '10px', fill: baseStyle.stroke, fontWeight: 700 } : undefined,
      labelBgStyle: label ? { fill: '#1a1b1e', fillOpacity: 0.9 } : undefined,
      labelBgPadding: label ? [4, 2] : undefined,
      labelBgBorderRadius: 3,
    }
  }),
)

const isEmpty = computed(() => props.trace?.empty || (props.trace?.nodes || []).length === 0)

function onNodeClick({ node }) {
  if (node) emit('node-click', { id: node.id, type: node.data?.type, name: node.data?.name })
}
</script>

<template>
  <div class="em-lane">
    <div v-if="loading" class="em-lane__overlay">불러오는 중…</div>
    <div v-else-if="isEmpty" class="em-lane__overlay">이 task에 귀속된 설계 요소가 없습니다.</div>
    <VueFlow
      v-else
      :nodes="flowNodes"
      :edges="flowEdges"
      :node-types="nodeTypes"
      :fit-view-on-init="true"
      :nodes-draggable="false"
      class="em-lane__flow"
      @node-click="onNodeClick"
    >
      <Background />
    </VueFlow>
    <div v-if="!loading && !isEmpty" class="em-lane__legend">
      <span class="em-lane__lg em-lane__lg--screen">screen — 자체 결과 화면</span>
      <span class="em-lane__lg em-lane__lg--inline">inline — 소비 화면에 표시</span>
      <span class="em-lane__lg em-lane__lg--system">system — 화면 없음</span>
    </div>
  </div>
</template>

<style scoped>
@import '@vue-flow/core/dist/style.css';
@import '@vue-flow/core/dist/theme-default.css';

.em-lane { position: relative; width: 100%; height: 100%; min-height: 200px; }
.em-lane__flow { width: 100%; height: 100%; }
.em-lane__overlay {
  display: flex; align-items: center; justify-content: center;
  width: 100%; height: 100%; color: var(--color-text-light); font-size: 0.85rem;
}

/* 043 US3 — ReadModel 3분류 색 링 (노드 래퍼에 적용) */
.em-lane__flow :deep(.vue-flow__node.rm-screen) { box-shadow: 0 0 0 2px #37b24d; border-radius: 10px; }
.em-lane__flow :deep(.vue-flow__node.rm-inline) { box-shadow: 0 0 0 2px #f59f00; border-radius: 10px; }
.em-lane__flow :deep(.vue-flow__node.rm-system) { box-shadow: 0 0 0 2px #868e96; border-radius: 10px; opacity: 0.82; }

/* 분류 범례 */
.em-lane__legend {
  position: absolute; left: 12px; bottom: 12px; z-index: 5;
  display: flex; gap: 10px; flex-wrap: wrap;
  padding: 6px 10px; border-radius: 8px;
  background: rgba(26, 27, 30, 0.88); border: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 0.72rem; color: var(--color-text-light);
}
.em-lane__lg { display: inline-flex; align-items: center; }
.em-lane__lg::before {
  content: ''; width: 10px; height: 10px; margin-right: 5px; border-radius: 3px;
}
.em-lane__lg--screen::before { background: #37b24d; }
.em-lane__lg--inline::before { background: #f59f00; }
.em-lane__lg--system::before { background: #868e96; }
</style>
