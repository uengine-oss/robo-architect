<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { useBpmnStore } from '@/features/canvas/bpmn.store'
import BpmnViewer from 'bpmn-js/lib/NavigatedViewer'
import { layoutProcess } from 'bpmn-auto-layout'
import ELK from 'elkjs/lib/elk.bundled.js'
// process-gpt's custom renderer (cream tasks, Korean text wrapping, colored
// events/lanes). Same bpmn-js engine — this is the module that makes their
// diagrams look the way they do; robo now renders identically.
import customBpmnModule from '@/features/canvas/customBpmn'
import BpmnInspectorPanel from './BpmnInspectorPanel.vue'
import HybridTaskInspector from './HybridTaskInspector.vue'
import HybridReviewModal from './HybridReviewModal.vue'
import HybridBcRulesModal from './HybridBcRulesModal.vue'
import PromoteToEsModal from './PromoteToEsModal.vue'
import 'bpmn-js/dist/assets/diagram-js.css'
import 'bpmn-js/dist/assets/bpmn-js.css'
import 'bpmn-js/dist/assets/bpmn-font/css/bpmn-embedded.css'

const store = useBpmnStore()

const bpmnContainer = ref(null)
const isDragOver = ref(false)
const showInspector = computed(() => !!store.selectedNodeData)
const showHybridInspector = computed(() => !!store.selectedHybridTaskId)
let viewer = null

// 현재 렌더링된 flow 탭 목록
const flowTabs = computed(() => store.renderedFlows)

// ── Event Storming promotion (hybrid Phase 5) ──
// BPM 생성 결과를 Event Storming 모델로 승격. 캔버스 플로팅 컨트롤러로 노출.
const esPromoting = ref(false)
const esError = ref('')
const showPromoteModal = ref(false)

// B4 — toast log. Explore/arbitration fire a burst of toasts that overwrite
// each other and vanish in 4s; the store keeps them in `toastHistory` so the
// user can open this panel and review them.
const showToastLog = ref(false)
function fmtToastTime(ts) {
  try { return new Date(ts).toLocaleTimeString() } catch { return '' }
}

function openPromoteModal() {
  const hsid = store.hybridSessionId
  if (!hsid) {
    alert('BPM 을 먼저 생성하세요 (BPMN 탭에서 Hybrid Ingestion 실행).')
    return
  }
  esError.value = ''
  showPromoteModal.value = true
}

async function runPromotion({ displayLanguage, uiGenerationMode }) {
  showPromoteModal.value = false
  const hsid = store.hybridSessionId
  if (!hsid) return
  esPromoting.value = true
  esError.value = ''

  try {
    // Wipe previous + trigger
    await fetch(`/api/ingest/hybrid/${hsid}/promote-to-es`, { method: 'DELETE' })
    const resp = await fetch(`/api/ingest/hybrid/${hsid}/promote-to-es`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        display_language: displayLanguage,
        ui_generation_mode: uiGenerationMode,
      }),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || `${resp.status}`)
    }
    const { ingestion_session_id } = await resp.json()

    // Delegate SSE handling to RequirementsIngestionModal — same infra as normal
    // ingestion: floating progress panel + Event Modeling live mode + navigator updates.
    window.dispatchEvent(new CustomEvent('robo:hybrid-promote', {
      detail: { sessionId: ingestion_session_id },
    }))
    esPromoting.value = false
  } catch (e) {
    esError.value = e.message || String(e)
    esPromoting.value = false
  }
}

onMounted(async () => {
  store.fetchProcessFlows()
  // App.vue triggers rehydrateHybrid at cold-load; if the user refreshed on a
  // non-BPMN tab and then switched here, activeBpmnXml may already be set. The
  // watch below picks it up via `immediate: true`. If rehydrate hasn't run yet
  // (edge case — store was cleared by another tab), fire it now.
  if (store.hybridSessionId && !store.activeBpmnXml && !store.isHybridRehydrating) {
    try { await store.rehydrateHybrid() } catch { /* best-effort */ }
  }
  // If activeBpmnXml was already set before mount, the immediate watch ran at
  // setup time when the viewer container wasn't attached yet. Render now.
  if (store.activeBpmnXml && !viewer) {
    await nextTick()
    renderBpmn(store.activeBpmnXml)
  }
})

onUnmounted(() => {
  if (viewer) {
    viewer.destroy()
    viewer = null
  }
})

// BPMN XML 변경 감지하여 뷰어 업데이트
watch(() => store.activeBpmnXml, async (xml) => {
  if (!xml) {
    if (viewer) {
      viewer.destroy()
      viewer = null
    }
    return
  }
  await nextTick()
  await renderBpmn(xml)
}, { immediate: true })

// bpmn-auto-layout lays out the process nodes but discards the collaboration's
// Pool/Lane DI, so the swimlane vanishes. Re-inject a Participant (+ Lane) shape
// computed from the bounding box of the laid-out nodes. Best-effort: any failure
// returns the input unchanged.
function reAddLaneDI(layoutedXml) {
  try {
    const doc = new DOMParser().parseFromString(layoutedXml, 'application/xml')
    if (doc.querySelector('parsererror')) return layoutedXml
    const byLocal = (root, name) =>
      [...root.getElementsByTagName('*')].filter(n => n.localName === name)
    const plane = byLocal(doc, 'BPMNPlane')[0]
    if (!plane) return layoutedXml
    const shapes = byLocal(plane, 'BPMNShape')
    if (!shapes.length) return layoutedXml
    if (shapes.some(s => /participant|lane/i.test(s.getAttribute('bpmnElement') || '')))
      return layoutedXml
    const participant = byLocal(doc, 'participant')[0]
    if (!participant) return layoutedXml // plain process, no swimlane to restore
    const lane = byLocal(doc, 'lane')[0]

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const s of shapes) {
      const b = byLocal(s, 'Bounds')[0]
      if (!b) continue
      const x = +b.getAttribute('x'), y = +b.getAttribute('y')
      const w = +b.getAttribute('width'), h = +b.getAttribute('height')
      minX = Math.min(minX, x); minY = Math.min(minY, y)
      maxX = Math.max(maxX, x + w); maxY = Math.max(maxY, y + h)
    }
    if (!isFinite(minX)) return layoutedXml
    const headW = 30, padX = 40, padY = 30
    const px = minX - padX - headW, py = minY - padY
    const pw = (maxX - minX) + padX * 2 + headW, ph = (maxY - minY) + padY * 2

    const DI_NS = shapes[0].namespaceURI
    const DC_NS = byLocal(shapes[0], 'Bounds')[0].namespaceURI
    const mkShape = (elId, x, y, w, h) => {
      const sh = doc.createElementNS(DI_NS, 'bpmndi:BPMNShape')
      sh.setAttribute('bpmnElement', elId)
      sh.setAttribute('isHorizontal', 'true')
      const bd = doc.createElementNS(DC_NS, 'dc:Bounds')
      bd.setAttribute('x', x); bd.setAttribute('y', y)
      bd.setAttribute('width', w); bd.setAttribute('height', h)
      sh.appendChild(bd)
      return sh
    }
    // Participant first so it renders behind the nodes; Lane just inside it.
    const partShape = mkShape(participant.getAttribute('id'), px, py, pw, ph)
    plane.insertBefore(partShape, plane.firstChild)
    if (lane) {
      const laneShape = mkShape(lane.getAttribute('id'), px + headW, py, pw - headW, ph)
      plane.insertBefore(laneShape, partShape.nextSibling)
    }
    return new XMLSerializer().serializeToString(doc)
  } catch (e) {
    console.warn('[BpmnPanel] reAddLaneDI failed', e)
    return layoutedXml
  }
}

// True when the BPMN already carries a usable diagram: every flow node
// (task/gateway/event) has a BPMNShape. The pdf2bpmn facade emits a full
// Sugiyama DI (node positions + orthogonal edge waypoints + lane boundaries —
// the same layout process-gpt renders in production), so we render it verbatim
// instead of re-laying it out and losing it. Returns false for a DI-less
// skeleton or a multi-process combined doc that only carries DI for its first
// process — those still need synthesized layout.
const _FLOW_NODE_TAGS = new Set([
  'task', 'userTask', 'serviceTask', 'manualTask', 'scriptTask',
  'businessRuleTask', 'sendTask', 'receiveTask', 'callActivity', 'subProcess',
  'exclusiveGateway', 'parallelGateway', 'inclusiveGateway',
  'eventBasedGateway', 'complexGateway',
  'startEvent', 'endEvent',
  'intermediateCatchEvent', 'intermediateThrowEvent', 'boundaryEvent',
])
function hasCompleteDI(xml) {
  try {
    const doc = new DOMParser().parseFromString(xml, 'application/xml')
    if (doc.querySelector('parsererror')) return false
    const all = [...doc.getElementsByTagName('*')]
    const shapeFor = new Set(
      all
        .filter(n => n.localName === 'BPMNShape')
        .map(s => s.getAttribute('bpmnElement'))
        .filter(Boolean)
    )
    if (!shapeFor.size) return false
    const nodes = all.filter(n => _FLOW_NODE_TAGS.has(n.localName))
    if (!nodes.length) return false
    // A single flow node without a shape (e.g. a combined multi-process doc)
    // forces a re-layout so nothing renders stacked at the origin.
    return nodes.every(n => shapeFor.has(n.getAttribute('id')))
  } catch {
    return false
  }
}

const elk = new ELK()

const _NODE_SIZE = (tag) =>
  tag.endsWith('Event') ? { w: 36, h: 36 }
    : tag.endsWith('Gateway') ? { w: 50, h: 50 }
      : { w: 100, h: 80 }

function countLanes(xml) {
  try {
    const doc = new DOMParser().parseFromString(xml, 'application/xml')
    return [...doc.getElementsByTagName('*')].filter(n => n.localName === 'lane').length
  } catch { return 0 }
}

// Lay a single-role (one-lane) or branchy process out with ELK's layered
// algorithm. pdf2bpmn packs gateway branches into one row when the process has a
// single role, so branch edges cut straight across the nodes between them. ELK
// gives each branch its own row, keeps the end event last, and routes edges
// orthogonally with no node crossings — the layout process-gpt shows. We rebuild
// the diagram (DI) from ELK's coordinates and wrap the nodes in one pool/lane.
// Returns the input unchanged on any failure.
async function elkLayout(xml) {
  try {
    const doc = new DOMParser().parseFromString(xml, 'application/xml')
    if (doc.querySelector('parsererror')) return xml
    const all = [...doc.getElementsByTagName('*')]
    const nodeEls = all.filter(n => _FLOW_NODE_TAGS.has(n.localName))
    if (!nodeEls.length) return xml
    const sizeOf = new Map()
    for (const n of nodeEls) sizeOf.set(n.getAttribute('id'), _NODE_SIZE(n.localName))
    const flows = all
      .filter(n => n.localName === 'sequenceFlow')
      .map(f => ({ id: f.getAttribute('id'), s: f.getAttribute('sourceRef'), t: f.getAttribute('targetRef') }))
      .filter(f => f.id && sizeOf.has(f.s) && sizeOf.has(f.t))

    const res = await elk.layout({
      id: 'root',
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'RIGHT',
        'elk.edgeRouting': 'ORTHOGONAL',
        'elk.layered.spacing.nodeNodeBetweenLayers': '70',
        'elk.spacing.nodeNode': '45',
        'elk.layered.spacing.edgeNodeBetweenLayers': '25',
      },
      children: [...sizeOf].map(([id, s]) => ({ id, width: s.w, height: s.h })),
      edges: flows.map(f => ({ id: f.id, sources: [f.s], targets: [f.t] })),
    })

    const pos = new Map()
    for (const c of res.children || []) pos.set(c.id, { x: c.x, y: c.y, w: c.width, h: c.height })
    const wp = new Map()
    for (const e of res.edges || []) {
      const sec = (e.sections || [])[0]
      if (sec) wp.set(e.id, [sec.startPoint, ...(sec.bendPoints || []), sec.endPoint])
    }
    if (!pos.size) return xml

    // Rebuild the BPMNPlane DI from ELK's coordinates.
    const byLocal = (root, name) => [...root.getElementsByTagName('*')].filter(n => n.localName === name)
    const plane = byLocal(doc, 'BPMNPlane')[0]
    if (!plane) return xml
    const exShape = byLocal(plane, 'BPMNShape')[0]
    const DI_NS = exShape ? exShape.namespaceURI : 'http://www.omg.org/spec/BPMN/20100524/DI'
    const DC_NS = 'http://www.omg.org/spec/DD/20100524/DC'
    const DI2_NS = 'http://www.omg.org/spec/DD/20100524/DI'
    while (plane.firstChild) plane.removeChild(plane.firstChild)

    const mkBounds = (x, y, w, h) => {
      const b = doc.createElementNS(DC_NS, 'dc:Bounds')
      b.setAttribute('x', x); b.setAttribute('y', y)
      b.setAttribute('width', w); b.setAttribute('height', h)
      return b
    }
    // Pool + lane around the node bounding box.
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const p of pos.values()) {
      minX = Math.min(minX, p.x); minY = Math.min(minY, p.y)
      maxX = Math.max(maxX, p.x + p.w); maxY = Math.max(maxY, p.y + p.h)
    }
    const headW = 30, padX = 40, padY = 30
    const px = minX - padX - headW, py = minY - padY
    const pw = (maxX - minX) + padX * 2 + headW, ph = (maxY - minY) + padY * 2
    const participant = byLocal(doc, 'participant')[0]
    const lane = byLocal(doc, 'lane')[0]
    if (participant) {
      const ps = doc.createElementNS(DI_NS, 'bpmndi:BPMNShape')
      ps.setAttribute('bpmnElement', participant.getAttribute('id'))
      ps.setAttribute('isHorizontal', 'true')
      ps.appendChild(mkBounds(px, py, pw, ph))
      plane.appendChild(ps)
      if (lane) {
        const ls = doc.createElementNS(DI_NS, 'bpmndi:BPMNShape')
        ls.setAttribute('bpmnElement', lane.getAttribute('id'))
        ls.setAttribute('isHorizontal', 'true')
        ls.appendChild(mkBounds(px + headW, py, pw - headW, ph))
        plane.appendChild(ls)
      }
    }
    for (const [id, p] of pos) {
      const sh = doc.createElementNS(DI_NS, 'bpmndi:BPMNShape')
      sh.setAttribute('bpmnElement', id)
      sh.appendChild(mkBounds(p.x, p.y, p.w, p.h))
      plane.appendChild(sh)
    }
    for (const f of flows) {
      const pts = wp.get(f.id)
      if (!pts || pts.length < 2) continue
      const ed = doc.createElementNS(DI_NS, 'bpmndi:BPMNEdge')
      ed.setAttribute('bpmnElement', f.id)
      for (const pt of pts) {
        const w = doc.createElementNS(DI2_NS, 'di:waypoint')
        w.setAttribute('x', pt.x); w.setAttribute('y', pt.y)
        ed.appendChild(w)
      }
      plane.appendChild(ed)
    }
    return new XMLSerializer().serializeToString(doc)
  } catch (e) {
    console.warn('[BpmnPanel] elkLayout failed', e)
    return xml
  }
}

async function renderBpmn(xml) {
  if (!bpmnContainer.value) return

  if (viewer) {
    viewer.destroy()
    viewer = null
  }

  viewer = new BpmnViewer({
    container: bpmnContainer.value,
    additionalModules: [customBpmnModule],
  })

  try {
    // Pick a layout. A multi-role process already separates its branches across
    // lanes, so the facade's Sugiyama DI renders cleanly — keep it verbatim. A
    // single-role (one-lane) process packs gateway branches into one row in the
    // facade DI (edges cut across nodes), so re-lay it out with ELK, which gives
    // each branch its own row. ELK also handles a DI-less skeleton. bpmn-auto-
    // layout remains the last resort if ELK can't produce a diagram.
    let toRender = xml
    if (!(hasCompleteDI(xml) && countLanes(xml) >= 2)) {
      const elked = await elkLayout(xml)
      if (elked !== xml) {
        toRender = elked
      } else if (!hasCompleteDI(xml)) {
        try {
          toRender = reAddLaneDI(await layoutProcess(xml))
        } catch (layoutErr) {
          console.warn('[BpmnPanel] auto-layout failed; rendering original DI', layoutErr)
          toRender = xml
        }
      }
    }
    await viewer.importXML(toRender)
    const canvas = viewer.get('canvas')
    canvas.zoom('fit-viewport')

    // 더블클릭 이벤트 등록
    const eventBus = viewer.get('eventBus')
    eventBus.on('element.dblclick', (e) => {
      const element = e.element
      if (!element || !element.id) return

      const id = element.id
      // 1) Try hybrid task first (BPMN element id may match task.id directly,
      //    or be wrapped as `Task_<safe(task.id)>` by the native builder).
      const stripped = id.startsWith('Task_') ? id.slice('Task_'.length) : id
      const hybridTask = store.hybridTasks.find(t => t.id === id || t.id === stripped)
      if (hybridTask) {
        e.originalEvent?.stopPropagation?.()
        store.selectHybridTask(hybridTask.id)
        highlightElement(id)
        return
      }

      // 2) Fallback: legacy BPMN inspector (Task_/IntEvent_)
      if (id.startsWith('Task_') || id.startsWith('IntEvent_')) {
        e.originalEvent?.stopPropagation?.()
        store.selectNodeForInspector(id)
        highlightElement(id)
      }
    })

    // 캔버스 빈 영역 클릭 시 Inspector 닫기
    eventBus.on('canvas.click', () => {
      if (store.selectedNodeData) {
        clearHighlight()
        store.clearInspectorSelection()
      }
      if (store.selectedHybridTaskId) {
        clearHighlight()
        store.clearHybridTaskSelection()
      }
    })
  } catch (err) {
    console.error('BPMN render error:', err)
  }
}

function handleZoomIn() {
  if (!viewer) return
  const canvas = viewer.get('canvas')
  canvas.zoom(canvas.zoom() * 1.2)
}

function handleZoomOut() {
  if (!viewer) return
  const canvas = viewer.get('canvas')
  canvas.zoom(canvas.zoom() / 1.2)
}

function handleFitViewport() {
  if (!viewer) return
  const canvas = viewer.get('canvas')
  canvas.zoom('fit-viewport')
}

function handleClearCanvas() {
  // Clear hybrid selection + the generic canvas XML + any ES-bpmn flows.
  store.clearHybridProcessSelection()
  store.activeBpmnXml = null
  store.hybridBpmnXml = null
  store.renderedFlows = []
  store.selectedFlowId = null
  store.activeStructured = null
}

// Drag & Drop: Navigator에서 프로세스 흐름을 드래그해올 때
function handleDragOver(e) {
  e.preventDefault()
  isDragOver.value = true
  e.dataTransfer.dropEffect = 'copy'
}

function handleDragLeave() {
  isDragOver.value = false
}

async function handleDrop(e) {
  e.preventDefault()
  isDragOver.value = false

  try {
    const raw = e.dataTransfer.getData('application/json')
    if (!raw) return
    const data = JSON.parse(raw)
    if (data.type === 'BpmnFlow' && data.id) {
      await store.addFlow(data.id)
    } else if (data.type === 'HybridProcess' && data.processId) {
      store.selectHybridProcess(data.processId)
    }
  } catch (err) {
    console.error('Drop error:', err)
  }
}

function selectFlowTab(flowId) {
  store.selectFlow(flowId)
}

function removeFlowTab(flowId) {
  store.removeFlow(flowId)
}

let highlightedElementId = null

function highlightElement(elementId) {
  clearHighlight()
  if (!viewer) return
  try {
    const canvas = viewer.get('canvas')
    canvas.addMarker(elementId, 'bpmn-element-selected')
    highlightedElementId = elementId
  } catch (e) {
    // element may not exist
  }
}

function clearHighlight() {
  if (!viewer || !highlightedElementId) return
  try {
    const canvas = viewer.get('canvas')
    canvas.removeMarker(highlightedElementId, 'bpmn-element-selected')
  } catch (e) {
    // element may have been removed
  }
  highlightedElementId = null
}

function closeInspector() {
  clearHighlight()
  store.clearInspectorSelection()
}
</script>

<template>
  <div class="bpmn-panel-wrapper">
    <div
      class="bpmn-panel"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
      :class="{ 'is-drag-over': isDragOver }"
    >
      <!-- Flow Tabs -->
      <div v-if="flowTabs.length > 0" class="flow-tabs">
        <button
          v-for="flow in flowTabs"
          :key="flow.id"
          class="flow-tab"
          :class="{ 'is-active': store.selectedFlowId === flow.id }"
          @click="selectFlowTab(flow.id)"
        >
          <span class="flow-tab__name">{{ flow.startCommand?.displayName || flow.startCommand?.name || flow.id }}</span>
          <span class="flow-tab__close" @click.stop="removeFlowTab(flow.id)" title="Remove">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </span>
        </button>
      </div>

      <!-- Zoom Controls -->
      <div class="bpmn-controls" v-if="store.activeBpmnXml">
        <button class="ctrl-btn" @click="handleZoomIn" title="Zoom In">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
            <line x1="11" y1="8" x2="11" y2="14" />
            <line x1="8" y1="11" x2="14" y2="11" />
          </svg>
        </button>
        <button class="ctrl-btn" @click="handleZoomOut" title="Zoom Out">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
            <line x1="8" y1="11" x2="14" y2="11" />
          </svg>
        </button>
        <button class="ctrl-btn" @click="handleFitViewport" title="Fit to Screen">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
          </svg>
        </button>
        <button
          class="ctrl-btn ctrl-btn--danger"
          @click="handleClearCanvas"
          title="캔버스 비우기"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
            <line x1="10" y1="11" x2="10" y2="17" />
            <line x1="14" y1="11" x2="14" y2="17" />
          </svg>
        </button>
      </div>

      <!-- Event Storming promote — floating controller (BPMN tab only).
           BPM(A2A 생성분)이 있을 때만 노출. ES 승격은 BPM tasks가 전제(promote-to-es는
           BPM 없으면 400)이므로, 문서 업로드 BPM이 없으면 버튼을 숨긴다. -->
      <button
        v-if="store.hybridActive || store.hybridProcessTrees.length > 0"
        class="es-promote-fab"
        :class="{ 'is-error': !!esError }"
        :disabled="esPromoting"
        @click="openPromoteModal"
        title="이벤트 스토밍 모델 생성 (BPM 기반)"
      >
        <template v-if="esPromoting">
          <span class="es-spinner"></span>
          <span>시작 중...</span>
        </template>
        <template v-else-if="esError">
          <span>❌ {{ esError.slice(0, 30) }}</span>
        </template>
        <template v-else>
          <span>✨ 이벤트 스토밍 생성</span>
        </template>
      </button>

      <!-- BPMN Viewer Container -->
      <div ref="bpmnContainer" class="bpmn-canvas" />

      <!-- Empty State -->
      <div v-if="!store.activeBpmnXml && !store.loading" class="bpmn-empty">
        <div class="empty-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <path d="M14 17h7M17.5 14v7" />
          </svg>
        </div>
        <p class="empty-title">BPMN Process Viewer</p>
        <p class="empty-desc">좌측 네비게이터에서 프로세스 흐름을 더블클릭하거나<br>캔버스로 드래그하여 BPMN 다이어그램을 확인하세요.</p>
      </div>

      <!-- Loading -->
      <div v-if="store.loading" class="bpmn-loading">
        <div class="loading-spinner" />
        <span>Loading process flow...</span>
      </div>

      <!-- Drag Over Overlay -->
      <div v-if="isDragOver" class="drag-overlay">
        <div class="drag-overlay__content">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          <span>프로세스 흐름을 여기에 놓으세요</span>
        </div>
      </div>
    </div>

    <!-- BPMN Inspector Panel (right side) -->
    <transition name="slide-inspector">
      <BpmnInspectorPanel
        v-if="showInspector"
        @close="closeInspector"
      />
    </transition>

    <!-- Hybrid Task Inspector (right side, opens on nav dblclick) -->
    <transition name="slide-inspector">
      <HybridTaskInspector
        v-if="showHybridInspector"
        @close="store.clearHybridTaskSelection"
      />
    </transition>

    <!-- Hybrid Review Modal (centered overlay; self-contained via Teleport) -->
    <HybridReviewModal />

    <!-- BC-scoped rules management modal (opened from Navigator's Rules by Context) -->
    <HybridBcRulesModal />

    <!-- ES Promotion modal — collects display_language + ui_generation_mode -->
    <PromoteToEsModal
      :visible="showPromoteModal"
      @close="showPromoteModal = false"
      @submit="runPromotion"
    />

    <!-- Arbitration toast — fires when post-explore arbitration moves/rejects a rule -->
    <Transition name="bpmn-toast">
      <div v-if="store.toast" :key="store.toast.id"
           class="bpmn-toast" :class="'bpmn-toast--' + store.toast.type">
        {{ store.toast.message }}
      </div>
    </Transition>

    <!-- B4 — toast/알림 이력. Burst toasts (탐색 완료 → rule 이동들) overwrite each
         other and vanish; this log lets the user expand and review them. -->
    <div v-if="store.toastHistory.length" class="bpmn-log">
      <button class="bpmn-log__btn" :title="showToastLog ? '알림 이력 접기' : '알림 이력 보기'"
              @click="showToastLog = !showToastLog">
        🔔 알림 <span class="bpmn-log__badge">{{ store.toastHistory.length }}</span>
      </button>
      <div v-if="showToastLog" class="bpmn-log__panel">
        <header class="bpmn-log__head">
          <span>알림 이력 ({{ store.toastHistory.length }})</span>
          <button class="bpmn-log__clear" @click="store.clearToastHistory()">비우기</button>
        </header>
        <ul class="bpmn-log__list">
          <li v-for="t in store.toastHistory" :key="t.id"
              class="bpmn-log__item" :class="'bpmn-log__item--' + t.type">
            <span class="bpmn-log__time">{{ fmtToastTime(t.ts) }}</span>
            <span class="bpmn-log__msg">{{ t.message }}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bpmn-panel-wrapper {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
}

.bpmn-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  background: var(--color-bg);
}

/* Inspector slide transition */
.slide-inspector-enter-active,
.slide-inspector-leave-active {
  transition: all 0.25s ease;
}

.slide-inspector-enter-from,
.slide-inspector-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.bpmn-panel.is-drag-over {
  outline: 2px dashed var(--color-accent);
  outline-offset: -2px;
}

/* Flow Tabs */
.flow-tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 8px 0;
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border);
  overflow-x: auto;
  flex-shrink: 0;
}

.flow-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: 6px 6px 0 0;
  font-size: 0.7rem;
  color: var(--color-text-light);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  max-width: 200px;
}

.flow-tab:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}

.flow-tab.is-active {
  background: var(--color-bg);
  border-color: var(--color-border);
  color: var(--color-text-bright);
  font-weight: 600;
}

.flow-tab__name {
  overflow: hidden;
  text-overflow: ellipsis;
}

.flow-tab__close {
  display: flex;
  align-items: center;
  padding: 2px;
  border-radius: 3px;
  color: var(--color-text-light);
  opacity: 0;
  transition: opacity 0.15s, background 0.15s;
}

.flow-tab:hover .flow-tab__close {
  opacity: 1;
}

.flow-tab__close:hover {
  background: rgba(255, 80, 80, 0.2);
  color: #ff5050;
}

/* Zoom Controls */
.bpmn-controls {
  position: absolute;
  top: 50px;
  right: 12px;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 4px;
}

.ctrl-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--color-text-light);
  cursor: pointer;
  transition: all 0.15s;
}

.ctrl-btn:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}

.ctrl-btn--danger:hover {
  background: rgba(230, 73, 73, 0.18);
  color: #ff8a8a;
}

/* Event Storming promote — floating controller (top-center) */
.es-promote-fab {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  background: var(--color-accent);
  border: none;
  border-radius: 6px;
  color: #fff;
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transition: transform 0.15s, box-shadow 0.15s, opacity 0.2s, filter 0.15s;
  white-space: nowrap;
}

.es-promote-fab:hover:not(:disabled) {
  transform: translateX(-50%) translateY(-1px);
  filter: brightness(1.08);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.22);
}

.es-promote-fab:disabled {
  opacity: 0.7;
  cursor: default;
}

.es-promote-fab.is-error {
  background: #e03131;
}

.es-spinner {
  display: inline-block;
  width: 11px;
  height: 11px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: es-spin 0.7s linear infinite;
}

@keyframes es-spin {
  to { transform: rotate(360deg); }
}

/* BPMN Canvas */
.bpmn-canvas {
  flex: 1;
  width: 100%;
  min-height: 0;
}

/* bpmn-js overrides */
/* Canvas backdrop follows robo's theme (dark in dark mode). The diagram elements
   themselves (cream tasks, blue lanes) are drawn light by the renderer and stay
   readable on the dark backdrop — no need to force the whole canvas white. */
.bpmn-canvas :deep(.djs-container) {
  background: var(--color-bg) !important;
}

.bpmn-canvas :deep(.djs-palette) {
  display: none !important;
}

.bpmn-canvas :deep(.djs-element:hover .djs-outline) {
  stroke: #3949AB !important;
  stroke-width: 2px !important;
}

.bpmn-canvas :deep(.bpmn-element-selected .djs-outline) {
  visibility: visible !important;
  stroke: #1565C0 !important;
  stroke-width: 2.5px !important;
  stroke-dasharray: none !important;
}

/* Element colors (cream tasks, colored events, Korean text wrapping) are drawn
   by CustomBpmnRenderer (ported from process-gpt) — NOT CSS. Do not re-add
   task/event fill overrides here; they would fight the renderer.

   EXCEPTION — pool/lane: bpmn-js draws lanes with a low fill-opacity (transparent
   so the canvas shows through), so the renderer's #f4f8fc fill doesn't take and
   the lane looks dark in dark mode (canvas bleeds through). Force it opaque +
   fixed light so the lane background is identical in both themes. */
.bpmn-canvas :deep(.djs-shape[data-element-id*="Participant"] .djs-visual > rect),
.bpmn-canvas :deep(.djs-shape[data-element-id*="Lane"] .djs-visual > rect) {
  fill: #f4f8fc !important;
  fill-opacity: 1 !important;
}

/* Empty State */
.bpmn-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
  pointer-events: none;
}

.empty-icon {
  color: var(--color-text-light);
}

.empty-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text);
}

.empty-desc {
  font-size: 0.7rem;
  color: var(--color-text-light);
  line-height: 1.5;
}

/* Loading */
.bpmn-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--color-text-light);
  font-size: 0.75rem;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Drag Overlay */
.drag-overlay {
  position: absolute;
  inset: 0;
  background: rgba(34, 139, 230, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
  pointer-events: none;
}

.drag-overlay__content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--color-accent);
  font-size: 0.8rem;
  font-weight: 500;
}

/* Arbitration toast — bottom-center, auto-fade */
.bpmn-toast {
  position: fixed;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  padding: 12px 22px;
  border-radius: 8px;
  font-size: 0.78rem;
  font-weight: 600;
  color: #fff;
  white-space: pre-line;
  max-width: 540px;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.4);
  pointer-events: none;
}
.bpmn-toast--info { background: rgba(34, 139, 230, 0.92); }
.bpmn-toast--warn { background: rgba(253, 126, 20, 0.92); }

.bpmn-toast-enter-active,
.bpmn-toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.bpmn-toast-enter-from,
.bpmn-toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 8px);
}

/* B4 — toast/알림 이력 log (bottom-right) */
.bpmn-log {
  position: absolute;
  right: 16px;
  bottom: 16px;
  z-index: 30;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}
.bpmn-log__btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 0.78rem;
  border: 1px solid var(--color-border, rgba(255,255,255,0.12));
  border-radius: 18px;
  background: var(--color-bg-elevated, #1b1f2a);
  color: var(--color-text, #e6e6e6);
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.bpmn-log__btn:hover { border-color: rgba(34,139,230,0.6); }
.bpmn-log__badge {
  min-width: 18px;
  padding: 0 5px;
  font-size: 0.66rem;
  font-weight: 700;
  text-align: center;
  border-radius: 9px;
  background: rgba(34,139,230,0.9);
  color: #fff;
}
.bpmn-log__panel {
  width: 360px;
  max-height: 320px;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border, rgba(255,255,255,0.12));
  border-radius: 8px;
  background: var(--color-bg-elevated, #1b1f2a);
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  overflow: hidden;
}
.bpmn-log__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 0.74rem;
  font-weight: 600;
  border-bottom: 1px solid var(--color-border, rgba(255,255,255,0.08));
  color: var(--color-text, #e6e6e6);
}
.bpmn-log__clear {
  font-size: 0.68rem;
  padding: 2px 8px;
  border: 1px solid var(--color-border, rgba(255,255,255,0.12));
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-dim, #9aa0aa);
  cursor: pointer;
}
.bpmn-log__list {
  margin: 0;
  padding: 4px 0;
  list-style: none;
  overflow-y: auto;
}
.bpmn-log__item {
  display: flex;
  gap: 8px;
  padding: 6px 12px;
  font-size: 0.74rem;
  line-height: 1.4;
  border-left: 3px solid transparent;
}
.bpmn-log__item--info { border-left-color: rgba(34,139,230,0.9); }
.bpmn-log__item--warn { border-left-color: rgba(253,126,20,0.9); }
.bpmn-log__time {
  flex-shrink: 0;
  color: var(--color-text-dim, #9aa0aa);
  font-variant-numeric: tabular-nums;
  font-size: 0.66rem;
  padding-top: 1px;
}
.bpmn-log__msg { color: var(--color-text, #e6e6e6); word-break: break-word; }
</style>
