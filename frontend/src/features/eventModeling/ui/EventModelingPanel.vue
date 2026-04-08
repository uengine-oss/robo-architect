<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useEventModelingStore } from '@/features/eventModeling/eventModeling.store'
import { useModelModifierStore } from '@/features/modelModifier/modelModifier.store'
import ChatPanel from '@/features/modelModifier/ui/ChatPanel.vue'
import InspectorPanel from '@/features/canvas/ui/InspectorPanel.vue'

const store = useEventModelingStore()
const chatStore = useModelModifierStore()

const scrollContainer = ref(null)
const panelMode = ref('chat')  // 'chat' | 'inspector' | 'none'
const inspectingNodeId = ref(null)
const inspectingInitialTab = ref('properties')
const chatPanelWidth = ref(360)
const isResizingChat = ref(false)
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0 })
const scrollStart = ref({ x: 0, y: 0 })

// Layout
const HEADER_W = 160
const SEQ_STEP_W = 280  // Command(좌) + ReadModel(우) 좌우 배치
const CARD_W = 115
const CARD_H = 60
const UI_CARD_H = 52
const SWIMLANE_MIN_H = 100
const SWIMLANE_PAD = 18
const SWIMLANE_GAP = 16
const INTERACTION_BASE_H = 96  // 좌우 배치 기본 높이

// Actor swimlane별 색상
const actorColors = [
  { bg: 'rgba(92,124,250,0.06)', border: 'rgba(92,124,250,0.25)' },
  { bg: 'rgba(253,126,20,0.06)', border: 'rgba(253,126,20,0.25)' },
  { bg: 'rgba(177,151,252,0.06)', border: 'rgba(177,151,252,0.25)' },
  { bg: 'rgba(64,192,87,0.06)', border: 'rgba(64,192,87,0.25)' },
  { bg: 'rgba(32,201,151,0.06)', border: 'rgba(32,201,151,0.25)' },
  { bg: 'rgba(230,73,128,0.06)', border: 'rgba(230,73,128,0.25)' },
  { bg: 'rgba(34,139,230,0.06)', border: 'rgba(34,139,230,0.25)' },
  { bg: 'rgba(252,196,25,0.06)', border: 'rgba(252,196,25,0.25)' },
]

const bcColors = [
  { bg: 'rgba(255,249,196,0.25)', border: 'rgba(255,202,40,0.4)' },
  { bg: 'rgba(255,236,179,0.25)', border: 'rgba(255,183,77,0.4)' },
  { bg: 'rgba(225,245,254,0.25)', border: 'rgba(79,195,247,0.4)' },
  { bg: 'rgba(243,229,245,0.25)', border: 'rgba(186,104,200,0.4)' },
  { bg: 'rgba(232,245,233,0.25)', border: 'rgba(129,199,132,0.4)' },
  { bg: 'rgba(255,224,178,0.25)', border: 'rgba(255,183,77,0.4)' },
  { bg: 'rgba(252,228,236,0.25)', border: 'rgba(244,143,177,0.4)' },
  { bg: 'rgba(224,242,241,0.25)', border: 'rgba(128,203,196,0.4)' },
]

function getColor(palette, idx) { return palette[idx % palette.length] }

// Computed positions
const timelineWidth = computed(() => HEADER_W + store.maxSequence * SEQ_STEP_W + 100)

function seqX(sequence) { return HEADER_W + (sequence - 1) * SEQ_STEP_W + SEQ_STEP_W / 2 }

// Actor swimlane heights
const actorHeights = computed(() => {
  const h = {}
  store.actorSwimlanes.forEach(lane => {
    const groups = {}
    lane.uis.forEach(u => { const s = u.sequence || 1; if (!groups[s]) groups[s] = 0; groups[s]++ })
    const maxStack = Math.max(1, ...Object.values(groups))
    h[lane.actor] = Math.max(SWIMLANE_MIN_H, maxStack * (UI_CARD_H + 8) + SWIMLANE_PAD * 2)
  })
  return h
})

// Interaction swimlane: 동일 시퀀스에 여러 Command/ReadModel이 있을 때 스태킹
const cmdStackIndex = computed(() => {
  const groups = {}
  store.interactionCommands.forEach(c => { (groups[c.sequence] ||= []).push(c.id) })
  const idx = {}
  for (const ids of Object.values(groups)) { ids.forEach((id, i) => { idx[id] = i }) }
  return idx
})
const rmStackIndex = computed(() => {
  const groups = {}
  store.interactionReadModels.forEach(r => { (groups[r.sequence] ||= []).push(r.id) })
  const idx = {}
  for (const ids of Object.values(groups)) { ids.forEach((id, i) => { idx[id] = i }) }
  return idx
})
const INTERACTION_H = computed(() => {
  const cmdGroups = {}, rmGroups = {}
  store.interactionCommands.forEach(c => { cmdGroups[c.sequence] = (cmdGroups[c.sequence] || 0) + 1 })
  store.interactionReadModels.forEach(r => { rmGroups[r.sequence] = (rmGroups[r.sequence] || 0) + 1 })
  const maxCmdStack = Math.max(1, ...Object.values(cmdGroups), 0)
  const maxRmStack = Math.max(1, ...Object.values(rmGroups), 0)
  const maxStack = Math.max(maxCmdStack, maxRmStack)
  return Math.max(INTERACTION_BASE_H, maxStack * (CARD_H + 8) + SWIMLANE_PAD * 2)
})

// BC swimlane heights
const bcHeights = computed(() => {
  const h = {}
  store.systemSwimlanes.forEach(lane => {
    const groups = {}
    lane.events.forEach(e => { const s = e.sequence || 1; if (!groups[s]) groups[s] = 0; groups[s]++ })
    const maxStack = Math.max(1, ...Object.values(groups))
    h[lane.bcId] = Math.max(SWIMLANE_MIN_H, maxStack * (CARD_H + 8) + SWIMLANE_PAD * 2)
  })
  return h
})

// 타입 필터: 보이는 스윔레인만 레이아웃·렌더 (빈 공간 없음)
const showUiLane = computed(() => store.isTypeVisible('ui'))
const showInteractionRow = computed(() => store.isTypeVisible('command') || store.isTypeVisible('readmodel'))
const showEventArea = computed(() => store.isTypeVisible('event'))
const visibleActorSwimlanes = computed(() => (showUiLane.value ? store.actorSwimlanes : []))
const visibleSystemSwimlanes = computed(() => (showEventArea.value ? store.systemSwimlanes : []))

function actorYVisible(idx) {
  let y = 32
  for (let i = 0; i < idx; i++) {
    const lane = visibleActorSwimlanes.value[i]
    y += (actorHeights.value[lane.actor] || SWIMLANE_MIN_H) + SWIMLANE_GAP
  }
  return y
}

const interactionY = computed(() => {
  let y = 32
  visibleActorSwimlanes.value.forEach(lane => {
    y += (actorHeights.value[lane.actor] || SWIMLANE_MIN_H) + SWIMLANE_GAP
  })
  return y
})

function afterInteractionTop() {
  let y = interactionY.value
  if (showInteractionRow.value) y += INTERACTION_H.value + SWIMLANE_GAP
  return y
}

function bcYVisible(idx) {
  let y = afterInteractionTop()
  for (let i = 0; i < idx; i++) {
    const lane = visibleSystemSwimlanes.value[i]
    y += (bcHeights.value[lane.bcId] || SWIMLANE_MIN_H) + SWIMLANE_GAP
  }
  return y
}

const totalHeight = computed(() => {
  let y = afterInteractionTop()
  visibleSystemSwimlanes.value.forEach(lane => {
    y += (bcHeights.value[lane.bcId] || SWIMLANE_MIN_H) + SWIMLANE_GAP
  })
  // Event→ReadModel 엣지가 최하단 이벤트 아래로 확장되는 공간 확보
  const evtRmCount = store.flows.filter(f => f.type === 'event-to-readmodel').length
  const edgeExtension = evtRmCount > 0 ? 20 + evtRmCount * 8 : 0
  return Math.max(y + 40 + edgeExtension, 400)
})

// Card positions
function uiCardPos(ui, visibleActorIdx) {
  const lane = visibleActorSwimlanes.value[visibleActorIdx]
  if (!lane) return { x: 0, y: 0 }
  const sameSeq = lane.uis.filter(u => u.sequence === ui.sequence)
  const stackIdx = sameSeq.indexOf(ui)
  let x = seqX(ui.sequence) - CARD_W / 2
  if (sharedSeqs.value.has(ui.sequence)) {
    // output UI → ReadModel 쪽(우), input UI → Command 쪽(좌)
    x = ui.isOutput ? seqX(ui.sequence) + 4 : seqX(ui.sequence) - CARD_W - 4
  }
  return {
    x,
    y: actorYVisible(visibleActorIdx) + SWIMLANE_PAD + stackIdx * (UI_CARD_H + 8),
  }
}

// 같은 시퀀스에 Command + ReadModel 공존 여부 → 공존 시만 좌우 오프셋
const sharedSeqs = computed(() => {
  const cmdSeqs = new Set(store.interactionCommands.map(c => c.sequence))
  const rmSeqs = new Set(store.interactionReadModels.map(r => r.sequence))
  const shared = new Set()
  cmdSeqs.forEach(s => { if (rmSeqs.has(s)) shared.add(s) })
  return shared
})

function cmdCardPos(cmd) {
  // 공존 시퀀스: 좌측 오프셋, 그 외: Event와 동일 X 중심
  if (sharedSeqs.value.has(cmd.sequence)) {
    return { x: seqX(cmd.sequence) - CARD_W - 4 }
  }
  return { x: seqX(cmd.sequence) - CARD_W / 2 }
}

function rmCardPos(rm) {
  // 공존 시퀀스: 우측 오프셋, 그 외: Event와 동일 X 중심
  if (sharedSeqs.value.has(rm.sequence)) {
    return { x: seqX(rm.sequence) + 4 }
  }
  return { x: seqX(rm.sequence) - CARD_W / 2 }
}

function evtCardPos(evt, visibleBcIdx) {
  const lane = visibleSystemSwimlanes.value[visibleBcIdx]
  if (!lane) return { x: 0, y: 0 }
  const sameSeq = lane.events.filter(e => e.sequence === evt.sequence)
  const stackIdx = sameSeq.indexOf(evt)
  let x = seqX(evt.sequence) - CARD_W / 2
  if (sharedSeqs.value.has(evt.sequence)) {
    // Event는 Command에서 emit → Command 쪽(좌) 정렬
    x = seqX(evt.sequence) - CARD_W - 4
  }
  return {
    x,
    y: bcYVisible(visibleBcIdx) + SWIMLANE_PAD + stackIdx * (CARD_H + 8),
  }
}

function rectCenter(x, y, w, h) {
  return { x: x + w / 2, y: y + h / 2 }
}

/**
 * 윗변·아랫변 중심 중 (px, py)에 더 가까운 쪽 (거리² 최소).
 * @returns {{ x: number, y: number, side: 'T' | 'B' }}
 */
function closestHorizontalEdge(x, y, w, h, px, py) {
  const midX = x + w / 2
  const ty = y
  const by = y + h
  const dT = (px - midX) ** 2 + (py - ty) ** 2
  const dB = (px - midX) ** 2 + (py - by) ** 2
  if (dT <= dB) return { x: midX, y: ty, side: 'T' }
  return { x: midX, y: by, side: 'B' }
}

/**
 * 직각 꺾임 경로: 수직 → 수평 → 수직.
 * midYOffset으로 같은 구간의 수평선을 분리하여 겹침 방지.
 */
function stepPath(x1, y1, x2, y2, midYOffset = 0) {
  const R = 6  // 모서리 둥글기
  if (Math.abs(x1 - x2) < 1) return `M ${x1} ${y1} L ${x2} ${y2}`
  const midY = Math.round((y1 + y2) / 2 + midYOffset)
  const dy1 = midY > y1 ? 1 : -1  // 첫 번째 수직 방향
  const dy2 = y2 > midY ? 1 : -1  // 두 번째 수직 방향
  const dx = x2 > x1 ? 1 : -1     // 수평 방향
  const r1 = Math.min(R, Math.abs(midY - y1) / 2, Math.abs(x2 - x1) / 2)
  const r2 = Math.min(R, Math.abs(y2 - midY) / 2, Math.abs(x2 - x1) / 2)
  return [
    `M ${x1} ${y1}`,
    `L ${x1} ${midY - dy1 * r1}`,
    `Q ${x1} ${midY}, ${x1 + dx * r1} ${midY}`,
    `L ${x2 - dx * r2} ${midY}`,
    `Q ${x2} ${midY}, ${x2} ${midY + dy2 * r2}`,
    `L ${x2} ${y2}`,
  ].join(' ')
}

/**
 * 수평 직각 경로 (Event→Command policy chain): 수평 → 수직 → 수평.
 */
function hStepPath(x1, y1, x2, y2, midXOffset = 0) {
  const R = 6
  const midX = Math.round((x1 + x2) / 2 + midXOffset)
  const dx1 = midX > x1 ? 1 : -1
  const dx2 = x2 > midX ? 1 : -1
  const dy = y2 > y1 ? 1 : -1
  const r1 = Math.min(R, Math.abs(midX - x1) / 2, Math.abs(y2 - y1) / 2)
  const r2 = Math.min(R, Math.abs(x2 - midX) / 2, Math.abs(y2 - y1) / 2)
  if (Math.abs(y1 - y2) < 1) return `M ${x1} ${y1} L ${x2} ${y2}`
  return [
    `M ${x1} ${y1}`,
    `L ${midX - dx1 * r1} ${y1}`,
    `Q ${midX} ${y1}, ${midX} ${y1 + dy * r1}`,
    `L ${midX} ${y2 - dy * r2}`,
    `Q ${midX} ${y2}, ${midX + dx2 * r2} ${y2}`,
    `L ${x2} ${y2}`,
  ].join(' ')
}

/**
 * SVG connections — 직각 꺾임 경로 + midY 분산으로 겹침 방지
 */
const paths = computed(() => {
  if (!showInteractionRow.value) return []

  const intBaseY = interactionY.value + SWIMLANE_PAD
  const visA = visibleActorSwimlanes.value
  const visBc = visibleSystemSwimlanes.value

  function cmdY(cmdId) { return intBaseY + (cmdStackIndex.value[cmdId] || 0) * (CARD_H + 8) }
  function rmY(rmId) { return intBaseY + (rmStackIndex.value[rmId] || 0) * (CARD_H + 8) }

  function findEvt(evtId) {
    for (let i = 0; i < visBc.length; i++) {
      const e = visBc[i].events.find(ev => ev.id === evtId)
      if (e) return evtCardPos(e, i)
    }
    return null
  }

  // ── Phase 1: 연결 수집 ──────────────────────────────────────
  const conns = []

  if (store.isTypeVisible('ui') && store.isTypeVisible('command')) {
    store.flows.filter(f => f.type === 'ui-to-command').forEach(f => {
      const aIdx = visA.findIndex(a => a.uis.some(u => u.id === f.sourceId))
      if (aIdx < 0) return
      const ui = visA[aIdx].uis.find(u => u.id === f.sourceId)
      const cmd = store.interactionCommands.find(c => c.id === f.targetId)
      if (!ui || !cmd) return
      const sp = uiCardPos(ui, aIdx)
      conns.push({ id: f.sourceId + f.targetId, srcId: f.sourceId, tgtId: f.targetId, x1: sp.x + CARD_W / 2, y1: sp.y + UI_CARD_H, x2: cmdCardPos(cmd).x + CARD_W / 2, y2: cmdY(cmd.id), color: '#5c7cfa', marker: 'em-arr-blue', corridor: 'actor-int' })
    })
  }

  // Command→Event: Event 상단 진입 / Event→ReadModel: Event 하단 출발
  if (store.isTypeVisible('command') && store.isTypeVisible('event')) {
    store.flows.filter(f => f.type === 'command-to-event').forEach(f => {
      const cmd = store.interactionCommands.find(c => c.id === f.sourceId)
      const ep = findEvt(f.targetId)
      if (!cmd || !ep) return
      conns.push({ id: f.sourceId + f.targetId, srcId: f.sourceId, tgtId: f.targetId, x1: cmdCardPos(cmd).x + CARD_W / 2, y1: cmdY(cmd.id) + CARD_H, x2: ep.x + CARD_W / 2, y2: ep.y, color: '#fd7e14', marker: 'em-arr-orange', corridor: 'int-bc' })
    })
  }

  if (store.isTypeVisible('readmodel') && store.isTypeVisible('ui')) {
    store.flows.filter(f => f.type === 'readmodel-to-ui').forEach(f => {
      const rm = store.interactionReadModels.find(r => r.id === f.sourceId)
      if (!rm) return
      const aIdx = visA.findIndex(a => a.uis.some(u => u.id === f.targetId))
      if (aIdx < 0) return
      const ui = visA[aIdx].uis.find(u => u.id === f.targetId)
      if (!ui) return
      const tp = uiCardPos(ui, aIdx)
      conns.push({ id: 'rm-ui-' + f.sourceId + f.targetId, srcId: f.sourceId, tgtId: f.targetId, x1: rmCardPos(rm).x + CARD_W / 2, y1: rmY(rm.id), x2: tp.x + CARD_W / 2, y2: tp.y + UI_CARD_H, color: '#20c997', marker: 'em-arr-teal', corridor: 'int-actor' })
    })
  }

  // ── Phase 2: 같은 구간(corridor)에서 midY 분산 → 직각 경로 생성 ─
  // corridor별로 그룹핑하여 수평 구간이 겹치지 않도록 midY 오프셋
  const corridorCount = {}, corridorIdx = {}
  conns.forEach(c => { corridorCount[c.corridor] = (corridorCount[c.corridor] || 0) + 1 })

  const SPREAD_GAP = 8  // 같은 corridor 내 수평선 간격
  const result = []

  for (const c of conns) {
    const idx = corridorIdx[c.corridor] || 0
    corridorIdx[c.corridor] = idx + 1
    const total = corridorCount[c.corridor]
    const midYOff = total > 1 ? (idx - (total - 1) / 2) * SPREAD_GAP : 0

    result.push({
      id: c.id, srcId: c.srcId, tgtId: c.tgtId,
      d: stepPath(c.x1, c.y1, c.x2, c.y2, midYOff),
      color: c.color, marker: c.marker,
    })
  }

  // Event → ReadModel: Event 하단 출발 → 아래로 꺾어서 ReadModel 상단 진입
  if (store.isTypeVisible('event') && store.isTypeVisible('readmodel')) {
    const evtRmFlows = store.flows.filter(f => f.type === 'event-to-readmodel')
    evtRmFlows.forEach((f, i) => {
      const ep = findEvt(f.sourceId)
      const rm = store.interactionReadModels.find(r => r.id === f.targetId)
      if (!ep || !rm) return
      const y1 = ep.y + CARD_H          // Event 하단
      const y2 = rmY(rm.id) + CARD_H + 2  // ReadModel 하단 바로 아래 (화살표 가시성)
      const belowY = y1 + 20 + i * 8    // Event 아래로 내려감
      const x1 = ep.x + CARD_W / 2
      const x2 = rmCardPos(rm).x + CARD_W / 2
      const R = 6
      const d = Math.abs(x1 - x2) < 1
        ? `M ${x1} ${y1} L ${x1} ${belowY} L ${x2} ${belowY} L ${x2} ${y2}`
        : [
          `M ${x1} ${y1}`,
          `L ${x1} ${belowY - R}`,
          `Q ${x1} ${belowY}, ${x1 + (x2 > x1 ? R : -R)} ${belowY}`,
          `L ${x2 - (x2 > x1 ? R : -R)} ${belowY}`,
          `Q ${x2} ${belowY}, ${x2} ${belowY - R}`,
          `L ${x2} ${y2}`,
        ].join(' ')
      result.push({ id: 'evt-rm-' + f.sourceId + f.targetId, srcId: f.sourceId, tgtId: f.targetId, d, color: '#40c057', marker: 'em-arr-green' })
    })
  }

  // Event → Command (policy chain): 수평 직각 경로
  if (store.isTypeVisible('event') && store.isTypeVisible('command')) {
    const chainFlows = store.flows.filter(f => f.type === 'event-to-command')
    const chainCount = chainFlows.length
    chainFlows.forEach((f, i) => {
      const ep = findEvt(f.sourceId)
      const cmd = store.interactionCommands.find(c => c.id === f.targetId)
      if (!ep || !cmd) return
      const midXOff = chainCount > 1 ? (i - (chainCount - 1) / 2) * SPREAD_GAP : 0
      result.push({
        id: 'chain-' + f.sourceId + f.targetId, srcId: f.sourceId, tgtId: f.targetId,
        d: hStepPath(ep.x + CARD_W, ep.y + CARD_H / 2, cmdCardPos(cmd).x, cmdY(cmd.id) + CARD_H / 2, midXOff),
        color: '#e57373', marker: 'em-arr-chain', chain: true,
      })
    })
  }

  return result
})

// Selected item lookups
const selectedReadModel = computed(() => {
  if (store.selectedItemType !== 'readmodel') return null
  return store.interactionReadModels.find(r => r.id === store.selectedItemId)
})
const selectedCommand = computed(() => {
  if (store.selectedItemType !== 'command') return null
  return store.interactionCommands.find(c => c.id === store.selectedItemId)
})
const selectedEvent = computed(() => {
  if (store.selectedItemType !== 'event') return null
  for (const lane of store.systemSwimlanes) {
    const evt = lane.events.find(e => e.id === store.selectedItemId)
    if (evt) return evt
  }
  return null
})

// Event drag & drop (insert-shift 방식)
const dragOverEventId = ref(null)
const dropIndicatorSeq = ref(null)   // 시퀀스 이동 인디케이터 (세로선)
const dropIndicatorParallel = ref(null) // 병렬 배치 인디케이터 { seq, bcId }
const dropTargetBcId = ref(null)     // 크로스-BC 드롭 대상

function onEvtDragStart(e, evt) {
  store.draggingEventId = evt.id
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', evt.id)
}

/**
 * Event 카드 위에 드래그 →
 *   - 좌/우 영역: 시퀀스 insert-shift (앞/뒤)
 *   - 하단 영역: 같은 시퀀스에 병렬 배치 (스택)
 */
function onEvtDragOver(e, evt, bcIdx) {
  e.preventDefault()
  e.stopPropagation()                       // 캔버스의 onCanvasDragOver가 dropEffect를 'copy'로 덮어쓰는 것 방지
  e.dataTransfer.dropEffect = 'move'        // effectAllowed='move'와 일치시켜야 drop 이벤트 발생
  dragOverEventId.value = evt.id

  const rect = e.currentTarget.getBoundingClientRect()
  const relY = (e.clientY - rect.top) / rect.height  // 0~1 (위→아래)
  const midX = rect.left + rect.width / 2

  if (relY > 0.65) {
    // 하단 35% 영역 → 병렬 배치 (같은 시퀀스에 스택)
    dropIndicatorSeq.value = null
    dropIndicatorParallel.value = { seq: evt.sequence, bcId: visibleSystemSwimlanes.value[bcIdx]?.bcId }
  } else {
    // 상단·좌우 영역 → 시퀀스 이동
    dropIndicatorParallel.value = null
    if (e.clientX < midX) {
      dropIndicatorSeq.value = evt.sequence      // 앞에 삽입
    } else {
      dropIndicatorSeq.value = evt.sequence + 1  // 뒤에 삽입
    }
  }
}

function onEvtDrop(targetEvt, bcIdx) {
  const srcId = store.draggingEventId
  if (!srcId) return

  const targetLane = visibleSystemSwimlanes.value[bcIdx]

  // 크로스-BC 이동 체크
  let srcBcId = null
  for (const lane of store.systemSwimlanes) {
    if (lane.events.some(e => e.id === srcId)) { srcBcId = lane.bcId; break }
  }
  if (srcBcId && targetLane && srcBcId !== targetLane.bcId) {
    store.moveEventToBC(srcId, targetLane.bcId)
  }

  if (dropIndicatorParallel.value && srcId !== targetEvt.id) {
    // 병렬 배치: 같은 시퀀스로 설정 (shift 없이)
    store.stackEventParallel(srcId, dropIndicatorParallel.value.seq)
  } else if (dropIndicatorSeq.value !== null && srcId !== targetEvt.id) {
    // 시퀀스 이동: insert-shift
    store.moveEventToPosition(srcId, dropIndicatorSeq.value)
  }

  _clearDragState()
}

/** BC 스윔레인 빈 영역에 드롭 → 크로스-BC 이동 */
function onBcLaneDragOver(e, lane) {
  if (!store.draggingEventId) return
  e.preventDefault()
  e.dataTransfer.dropEffect = 'move'        // effectAllowed='move'와 일치
  dropTargetBcId.value = lane.bcId
}
function onBcLaneDragLeave(lane) {
  if (dropTargetBcId.value === lane.bcId) dropTargetBcId.value = null
}
function onBcLaneDrop(e, lane) {
  e.preventDefault()
  const srcId = store.draggingEventId
  if (!srcId) return

  let srcBcId = null
  for (const l of store.systemSwimlanes) {
    if (l.events.some(ev => ev.id === srcId)) { srcBcId = l.bcId; break }
  }
  if (srcBcId && srcBcId !== lane.bcId) {
    store.moveEventToBC(srcId, lane.bcId)
  }

  _clearDragState()
}

function onEvtDragEnd() { _clearDragState() }

function _clearDragState() {
  store.draggingEventId = null
  dragOverEventId.value = null
  dropIndicatorSeq.value = null
  dropIndicatorParallel.value = null
  dropTargetBcId.value = null
}

// ── Palette (노드 추가/삭제) ────────────────────────────────
const paletteNodeTypes = [
  { type: 'event', label: 'Event', color: '#fd7e14' },
  { type: 'command', label: 'Command', color: '#5c7cfa' },
  { type: 'readmodel', label: 'ReadModel', color: '#40c057' },
  { type: 'ui', label: 'UI', color: '#9e9e9e' },
]

function onPaletteDragStart(e, nodeType) {
  e.dataTransfer.setData('application/em-palette', nodeType)
  e.dataTransfer.effectAllowed = 'copy'
}

/** 캔버스 빈 영역에 팔레트 노드 드롭 → 새 노드 생성 */
async function onCanvasDropPalette(e) {
  const paletteType = e.dataTransfer.getData('application/em-palette')
  if (!paletteType) return

  e.preventDefault()

  // 드롭 위치에서 sequence 추정
  const canvasRect = scrollContainer.value?.getBoundingClientRect()
  if (!canvasRect) return
  const xInCanvas = (e.clientX - canvasRect.left + (scrollContainer.value?.scrollLeft || 0)) / store.zoomLevel
  const dropSeq = Math.max(1, Math.round((xInCanvas - HEADER_W) / SEQ_STEP_W) + 1)

  // 가장 가까운 BC 결정 (event용)
  let closestBcId = store.systemSwimlanes[0]?.bcId || null

  if (paletteType === 'event' || paletteType === 'command' || paletteType === 'readmodel') {
    // Y 위치로 어떤 BC에 드롭했는지 판단
    const yInCanvas = (e.clientY - canvasRect.top + (scrollContainer.value?.scrollTop || 0)) / store.zoomLevel
    for (let i = 0; i < visibleSystemSwimlanes.value.length; i++) {
      const laneTop = bcYVisible(i)
      const laneH = bcHeights.value[visibleSystemSwimlanes.value[i].bcId] || SWIMLANE_MIN_H
      if (yInCanvas >= laneTop && yInCanvas <= laneTop + laneH) {
        closestBcId = visibleSystemSwimlanes.value[i].bcId
        break
      }
    }
  }

  const name = `New${paletteType.charAt(0).toUpperCase() + paletteType.slice(1)}`
  const payload = {
    type: paletteType,
    name,
    displayName: name,
    bcId: closestBcId,
    sequence: dropSeq,
    actor: 'User',
  }

  await store.addNode(payload)
}

/** 노드 삭제 (컨텍스트 메뉴) */
const contextMenu = ref({ show: false, x: 0, y: 0, nodeId: null, nodeType: null })

function onNodeContextMenu(e, nodeId, nodeType) {
  e.preventDefault()
  contextMenu.value = { show: true, x: e.clientX, y: e.clientY, nodeId, nodeType }
}

function closeContextMenu() {
  contextMenu.value = { show: false, x: 0, y: 0, nodeId: null, nodeType: null }
}

function deleteSelectedNode() {
  if (contextMenu.value.nodeId && contextMenu.value.nodeType) {
    store.deleteNode(contextMenu.value.nodeId, contextMenu.value.nodeType)
  }
  closeContextMenu()
}

// 캔버스 클릭으로 컨텍스트 메뉴 닫기
function onCanvasClick() {
  if (contextMenu.value.show) closeContextMenu()
  if (store.connectingFrom) store.cancelConnecting()
}

// ── 관계 연결 모드 ────────────────────────────────────────────
const isConnectMode = ref(false)

function toggleConnectMode() {
  isConnectMode.value = !isConnectMode.value
  if (!isConnectMode.value) store.cancelConnecting()
}

/** 노드 커넥터 도트 클릭 → 연결 시작 */
function onConnectorMouseDown(e, nodeId, nodeType) {
  if (!isConnectMode.value) return
  e.stopPropagation()
  e.preventDefault()
  store.startConnecting(nodeId, nodeType)
}

/** 연결 모드 중 마우스 이동 → 라이브 라인 업데이트 */
function onConnectMouseMove(e) {
  if (!store.connectingFrom) return
  const canvasRect = scrollContainer.value?.getBoundingClientRect()
  if (!canvasRect) return
  const x = (e.clientX - canvasRect.left + (scrollContainer.value?.scrollLeft || 0)) / store.zoomLevel
  const y = (e.clientY - canvasRect.top + (scrollContainer.value?.scrollTop || 0)) / store.zoomLevel
  store.updateConnectingPos(x, y)
}

/** 타겟 노드에서 마우스 업 → 관계 생성 */
function onConnectorMouseUp(e, nodeId, nodeType) {
  if (!store.connectingFrom || store.connectingFrom.id === nodeId) {
    store.cancelConnecting()
    return
  }
  e.stopPropagation()
  store.createRelation(nodeId, nodeType)
}

/** 연결 시작 노드의 위치 (SVG 라이브 라인 시작점) */
const connectLineStart = computed(() => {
  if (!store.connectingFrom) return null
  const src = store.connectingFrom
  // Command
  const cmd = store.interactionCommands.find(c => c.id === src.id)
  if (cmd) {
    const pos = cmdCardPos(cmd)
    return { x: pos.x + CARD_W, y: interactionY.value + SWIMLANE_PAD + (cmdStackIndex.value[cmd.id] || 0) * (CARD_H + 8) + CARD_H / 2 }
  }
  // ReadModel
  const rm = store.interactionReadModels.find(r => r.id === src.id)
  if (rm) {
    const pos = rmCardPos(rm)
    return { x: pos.x + CARD_W, y: interactionY.value + SWIMLANE_PAD + (rmStackIndex.value[rm.id] || 0) * (CARD_H + 8) + CARD_H / 2 }
  }
  // Event
  for (let i = 0; i < visibleSystemSwimlanes.value.length; i++) {
    const evt = visibleSystemSwimlanes.value[i].events.find(e => e.id === src.id)
    if (evt) {
      const pos = evtCardPos(evt, i)
      return { x: pos.x + CARD_W, y: pos.y + CARD_H / 2 }
    }
  }
  // UI
  for (let i = 0; i < visibleActorSwimlanes.value.length; i++) {
    const ui = visibleActorSwimlanes.value[i].uis.find(u => u.id === src.id)
    if (ui) {
      const pos = uiCardPos(ui, i)
      return { x: pos.x + CARD_W, y: pos.y + UI_CARD_H / 2 }
    }
  }
  return null
})

/** Path 우클릭 → 관계 삭제 컨텍스트 메뉴 */
const pathContextMenu = ref({ show: false, x: 0, y: 0, sourceId: null, targetId: null, flowType: null })

function onPathContextMenu(e, p) {
  e.preventDefault()
  e.stopPropagation()
  // flow에서 flowType 찾기
  const flow = store.flows.find(f =>
    (f.sourceId + f.targetId === p.id) ||
    ('rm-ui-' + f.sourceId + f.targetId === p.id) ||
    ('evt-rm-' + f.sourceId + f.targetId === p.id) ||
    ('chain-' + f.sourceId + f.targetId === p.id)
  )
  if (!flow) return
  pathContextMenu.value = { show: true, x: e.clientX, y: e.clientY, sourceId: p.srcId, targetId: p.tgtId, flowType: flow.type }
}

function closePathContextMenu() {
  pathContextMenu.value = { show: false, x: 0, y: 0, sourceId: null, targetId: null, flowType: null }
}

function deleteSelectedRelation() {
  const { sourceId, targetId, flowType } = pathContextMenu.value
  if (sourceId && targetId && flowType) {
    store.deleteRelation(sourceId, targetId, flowType)
  }
  closePathContextMenu()
}

/** 연결 가능한 타겟 타입 (시각 피드백용) */
const CONNECTABLE_TARGETS = {
  command: ['event'],
  event: ['readmodel', 'command'],
  ui: ['command', 'readmodel'],
}

function isValidDropTarget(targetType) {
  if (!store.connectingFrom) return false
  const allowed = CONNECTABLE_TARGETS[store.connectingFrom.type]
  return allowed?.includes(targetType) || false
}

const selectedNodeWarnings = computed(() => {
  if (!store.selectedItemId) return []
  return store.validationWarnings.filter(w => w.nodeId === store.selectedItemId)
})

const filterCounts = computed(() => ({
  event: store.totalEvents,
  command: store.totalCommands,
  readmodel: store.interactionReadModels.length,
  ui: store.actorSwimlanes.reduce((n, lane) => n + lane.uis.length, 0),
}))

function warningsFor(nodeId) {
  return store.validationWarnings.filter(w => w.nodeId === nodeId)
}

function warningLine(w) {
  if (w.type === 'no-emits') return 'EMITS 연결 없음'
  if (w.type === 'no-ui') return 'UI 없음'
  if (w.type === 'no-cqrs') return 'ReadModel 미연결'
  return w.type
}

function isHl(id) { return store.highlightedIds.has(id) }
function isPathHl(p) { return p.srcId === store.hoveredItemId }

// 패널 토글 (Design 탭과 동일)
function toggleChatPanel() {
  panelMode.value = panelMode.value === 'chat' ? 'none' : 'chat'
}
function toggleInspectorPanel() {
  panelMode.value = panelMode.value === 'inspector' ? 'none' : 'inspector'
}

// 노드 타입 판별
function getNodeType(nodeId) {
  if (store.interactionCommands.some(c => c.id === nodeId)) return 'command'
  if (store.interactionReadModels.some(r => r.id === nodeId)) return 'readmodel'
  for (const lane of store.systemSwimlanes) { if (lane.events.some(e => e.id === nodeId)) return 'event' }
  for (const lane of store.actorSwimlanes) { if (lane.uis.some(u => u.id === nodeId)) return 'ui' }
  return 'unknown'
}

// 노드 선택 시 Inspector 모드이면 자동 반영
watch(() => store.selectedItemId, (id) => {
  if (id) {
    inspectingNodeId.value = id
    inspectingInitialTab.value = getNodeType(id) === 'ui' ? 'preview' : 'properties'
  } else {
    inspectingNodeId.value = null
  }
})

// 더블클릭 → Inspector 강제 열기
function openInspector(nodeId, tab = 'properties') {
  inspectingNodeId.value = nodeId
  inspectingInitialTab.value = tab
  panelMode.value = 'inspector'
}
function closeInspector() {
  inspectingNodeId.value = null
  store.clearSelection()
  panelMode.value = 'chat'
}
function truncate(t, n = 14) { return !t ? '' : t.length > n ? t.slice(0, n) + '…' : t }

// Pan & zoom
function startPan(e) {
  if (e.button !== 0 || e.target.closest('.em-card') || e.target.closest('.em-connector') || isConnectMode.value) return
  isPanning.value = true
  panStart.value = { x: e.clientX, y: e.clientY }
  if (scrollContainer.value) scrollStart.value = { x: scrollContainer.value.scrollLeft, y: scrollContainer.value.scrollTop }
  e.preventDefault()
}
function onPan(e) { if (!isPanning.value || !scrollContainer.value) return; scrollContainer.value.scrollLeft = scrollStart.value.x - (e.clientX - panStart.value.x); scrollContainer.value.scrollTop = scrollStart.value.y - (e.clientY - panStart.value.y); syncSwimlaneHeaders() }
function stopPan() { isPanning.value = false }
function handleWheel(e) { if (e.ctrlKey || e.metaKey) { e.preventDefault(); store.setZoom(store.zoomLevel + (e.deltaY > 0 ? -0.05 : 0.05)) } }

// 스윔레인 헤더 고정: 좌우 스크롤 시 translateX로 보정
function syncSwimlaneHeaders() {
  if (!scrollContainer.value) return
  const scrollLeft = scrollContainer.value.scrollLeft
  const scale = store.zoomLevel
  const offset = scrollLeft / scale
  scrollContainer.value.querySelectorAll('.em-swimlane__hdr').forEach(el => {
    el.style.transform = `translateX(${offset}px)`
  })
}
function onScrollSync() { syncSwimlaneHeaders() }
function startResizeChat(e) { isResizingChat.value = true; e.preventDefault(); document.addEventListener('mousemove', onResizeChat); document.addEventListener('mouseup', stopResizeChat) }
function onResizeChat(e) { if (!isResizingChat.value) return; chatPanelWidth.value = Math.max(280, Math.min(600, window.innerWidth - e.clientX)) }
function stopResizeChat() { isResizingChat.value = false; document.removeEventListener('mousemove', onResizeChat); document.removeEventListener('mouseup', stopResizeChat) }


onMounted(() => {
  // 탭 진입 시 캔버스 비어있는 상태 유지 (live 모드 제외)
  if (!store.isLiveMode) store.clearCanvas()
  document.addEventListener('mousemove', onPan)
  document.addEventListener('mouseup', stopPan)
})
onUnmounted(() => { document.removeEventListener('mousemove', onPan); document.removeEventListener('mouseup', stopPan); stopResizeChat() })

// 스윔레인 헤더 고정용 scroll 이벤트 등록 (scrollContainer가 렌더된 뒤)
watch(scrollContainer, (el) => {
  if (el) {
    el.addEventListener('scroll', onScrollSync)
    nextTick(() => syncSwimlaneHeaders())
  }
}, { immediate: false })

// 프로세스 드래그 앤 드롭 수신 + 팔레트 노드 드롭
function onCanvasDragOver(e) {
  e.preventDefault()
  // 이벤트 드래그 중에는 'move', 팔레트/프로세스 드래그는 'copy'
  e.dataTransfer.dropEffect = store.draggingEventId ? 'move' : 'copy'
}
function onCanvasDrop(e) {
  e.preventDefault()
  // 팔레트 노드 드롭 처리
  if (e.dataTransfer.getData('application/em-palette')) {
    onCanvasDropPalette(e)
    return
  }
  try {
    const data = JSON.parse(e.dataTransfer.getData('application/json'))
    if (data.type === 'EventModelingProcess' && data.processId) {
      store.addProcessToCanvas(data.processId)
    }
  } catch { /* ignore */ }
}
</script>

<template>
  <div class="em-panel">
    <div class="em-canvas-area">
      <!-- Loading / Error / Empty -->
      <div v-if="store.loading" class="em-state"><div class="em-spinner"></div>로딩 중...</div>
      <div v-else-if="store.error" class="em-state">{{ store.error }}<button class="canvas-toolbar__btn" @click="store.fetchEventModeling()">재시도</button></div>
      <div v-else-if="!store.actorSwimlanes.length && !store.systemSwimlanes.length" class="em-state em-state--droppable"
           @dragover="onCanvasDragOver" @drop="onCanvasDrop">
        프로세스를 더블클릭하거나 드래그하여 캔버스에 추가하세요.
      </div>

      <div v-else ref="scrollContainer" class="em-scroll" @mousedown="startPan" @wheel="handleWheel" @dragover="onCanvasDragOver" @drop="onCanvasDrop" @click="onCanvasClick" @mousemove="onConnectMouseMove" :class="{ 'is-panning': isPanning, 'is-connecting': isConnectMode }">
        <div class="em-canvas" :style="{ width: timelineWidth+'px', height: totalHeight+'px', transform: `scale(${store.zoomLevel})`, transformOrigin: '0 0' }">

          <!-- SVG -->
          <svg class="em-svg" :width="timelineWidth" :height="totalHeight">
            <defs>
              <marker id="em-arr-blue" markerWidth="12" markerHeight="9" refX="11" refY="4.5" orient="auto" markerUnits="userSpaceOnUse">
                <polygon points="0 0,12 4.5,0 9" fill="#5c7cfa"/>
              </marker>
              <marker id="em-arr-orange" markerWidth="12" markerHeight="9" refX="11" refY="4.5" orient="auto" markerUnits="userSpaceOnUse">
                <polygon points="0 0,12 4.5,0 9" fill="#fd7e14"/>
              </marker>
              <marker id="em-arr-green" markerWidth="12" markerHeight="9" refX="11" refY="4.5" orient="auto" markerUnits="userSpaceOnUse">
                <polygon points="0 0,12 4.5,0 9" fill="#40c057"/>
              </marker>
              <marker id="em-arr-chain" markerWidth="12" markerHeight="9" refX="11" refY="4.5" orient="auto" markerUnits="userSpaceOnUse">
                <polygon points="0 0,12 4.5,0 9" fill="#e57373"/>
              </marker>
              <marker id="em-arr-teal" markerWidth="12" markerHeight="9" refX="11" refY="4.5" orient="auto" markerUnits="userSpaceOnUse">
                <polygon points="0 0,12 4.5,0 9" fill="#20c997"/>
              </marker>
            </defs>
            <!-- Grid -->
            <line v-for="s in store.maxSequence" :key="'g'+s" :x1="HEADER_W+(s-1)*SEQ_STEP_W" y1="0" :x2="HEADER_W+(s-1)*SEQ_STEP_W" :y2="totalHeight" stroke="rgba(200,200,200,0.12)" stroke-dasharray="4,4"/>
            <!-- Paths (visible) -->
            <path v-for="p in paths" :key="p.id" :d="p.d" :stroke="p.color" fill="none"
                  :stroke-width="store.hoveredItemId && isPathHl(p) ? 3 : (p.chain ? 3 : 1.5)"
                  :marker-end="'url(#' + (p.marker || 'em-arr-orange') + ')'"
                  :opacity="store.hoveredItemId ? (isPathHl(p) ? 1 : 0.08) : 0.7"/>
            <!-- Paths (invisible wide hit area for right-click) -->
            <path v-for="p in paths" :key="'hit-'+p.id" :d="p.d" stroke="transparent" fill="none"
                  stroke-width="12" style="pointer-events:stroke; cursor:pointer"
                  @contextmenu="onPathContextMenu($event, p)"/>
            <!-- Live connection line -->
            <line v-if="connectLineStart && store.connectingToPos"
                  :x1="connectLineStart.x" :y1="connectLineStart.y"
                  :x2="store.connectingToPos.x" :y2="store.connectingToPos.y"
                  stroke="#228be6" stroke-width="2" stroke-dasharray="6,4" opacity="0.8"/>
          </svg>

          <!-- ===== ACTOR SWIMLANES (상단) ===== -->
          <div v-for="(lane, ai) in visibleActorSwimlanes" :key="'a-'+lane.actor"
               class="em-swimlane" :style="{ top: actorYVisible(ai)+'px', width: timelineWidth+'px',
               height: (actorHeights[lane.actor]||SWIMLANE_MIN_H)+'px',
               background: getColor(actorColors,ai).bg, borderColor: getColor(actorColors,ai).border }">
            <div class="em-swimlane__hdr" :style="{ width: HEADER_W+'px' }">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              <span>{{ lane.actor }}</span>
            </div>
            <!-- UI cards -->
            <div v-for="ui in lane.uis" :key="ui.id" class="em-card" :class="[ui.isOutput?'em-card--rm-ui':'em-card--ui', { 'is-hl': isHl(ui.id), 'is-dimmed': store.hoveredItemId && !isHl(ui.id) && store.hoveredItemId !== ui.id }]"
                 :style="{ left: uiCardPos(ui,ai).x+'px', top: uiCardPos(ui,ai).y - actorYVisible(ai)+'px', width: CARD_W+'px', height: UI_CARD_H+'px' }"
                 @click="store.selectItem(ui.id,'ui')" @dblclick="openInspector(ui.id,'preview')" @mouseenter="store.setHoveredItem(ui.id)" @mouseleave="store.clearHover()"
                 @contextmenu="onNodeContextMenu($event, ui.id, 'ui')"
                 :title="ui.displayName||ui.name">
              <div class="em-card__icon">
                <svg width="18" height="14" viewBox="0 0 24 20" fill="none" stroke="#666" stroke-width="1.5"><rect x="2" y="2" width="20" height="14" rx="2"/><path d="M2 6h20"/></svg>
              </div>
              <div class="em-card__name">{{ truncate(ui.displayName||ui.name) }}</div>
              <!-- Connector dots -->
              <div v-if="isConnectMode" class="em-connector em-connector--right"
                   :class="{ 'is-valid-target': isValidDropTarget('ui') }"
                   @mousedown="onConnectorMouseDown($event, ui.id, 'ui')"
                   @mouseup="onConnectorMouseUp($event, ui.id, 'ui')"></div>
            </div>
          </div>

          <!-- ===== INTERACTION SWIMLANE (중간) ===== -->
          <div v-show="showInteractionRow" class="em-swimlane em-swimlane--interaction" :style="{ top: interactionY+'px', width: timelineWidth+'px', height: INTERACTION_H+'px' }">
            <div class="em-swimlane__hdr em-swimlane__hdr--int" :style="{ width: HEADER_W+'px' }">
              <span>Interactions</span>
            </div>
            <!-- Commands (좌측) -->
            <div v-for="cmd in store.interactionCommands" v-show="store.isTypeVisible('command')" :key="cmd.id" class="em-card em-card--command" :class="{ 'is-hl': isHl(cmd.id), 'is-dimmed': store.hoveredItemId && !isHl(cmd.id) && store.hoveredItemId !== cmd.id }"
                 :style="{ left: cmdCardPos(cmd).x+'px', top: SWIMLANE_PAD + (cmdStackIndex[cmd.id] || 0) * (CARD_H + 8) + 'px', width: CARD_W+'px', height: CARD_H+'px' }"
                 @click="store.selectItem(cmd.id,'command')" @dblclick="openInspector(cmd.id)" @mouseenter="store.setHoveredItem(cmd.id)" @mouseleave="store.clearHover()"
                 @contextmenu="onNodeContextMenu($event, cmd.id, 'command')"
                 :title="(cmd.displayName||cmd.name)+' ('+cmd.actor+')'">
              <div v-if="store.hoveredItemId === cmd.id && warningsFor(cmd.id).length" class="em-card__warnings" role="tooltip">
                <div v-for="w in warningsFor(cmd.id)" :key="w.type">{{ warningLine(w) }}</div>
              </div>
              <div class="em-card__title">{{ truncate(cmd.displayName||cmd.name) }}</div>
              <div class="em-card__sub">{{ cmd.actor }}</div>
              <div v-if="isConnectMode" class="em-connector em-connector--right"
                   :class="{ 'is-valid-target': isValidDropTarget('command') }"
                   @mousedown="onConnectorMouseDown($event, cmd.id, 'command')"
                   @mouseup="onConnectorMouseUp($event, cmd.id, 'command')"></div>
            </div>
            <!-- ReadModels (우측) -->
            <div v-for="(rm, ri) in store.interactionReadModels" v-show="store.isTypeVisible('readmodel')" :key="rm.id" class="em-card em-card--readmodel" :class="{ 'is-hl': isHl(rm.id), 'is-dimmed': store.hoveredItemId && !isHl(rm.id) && store.hoveredItemId !== rm.id }"
                 :style="{ left: rmCardPos(rm).x+'px', top: SWIMLANE_PAD + (rmStackIndex[rm.id] || 0) * (CARD_H + 8) + 'px', width: CARD_W+'px', height: CARD_H+'px' }"
                 @click="store.selectItem(rm.id,'readmodel')" @dblclick="openInspector(rm.id)" @mouseenter="store.setHoveredItem(rm.id)" @mouseleave="store.clearHover()"
                 @contextmenu="onNodeContextMenu($event, rm.id, 'readmodel')"
                 :title="rm.displayName||rm.name">
              <div class="em-card__title">{{ truncate(rm.displayName||rm.name) }}</div>
              <div class="em-card__sub">{{ rm.actor }}</div>
              <div v-if="isConnectMode" class="em-connector em-connector--right"
                   :class="{ 'is-valid-target': isValidDropTarget('readmodel') }"
                   @mousedown="onConnectorMouseDown($event, rm.id, 'readmodel')"
                   @mouseup="onConnectorMouseUp($event, rm.id, 'readmodel')"></div>
            </div>
          </div>

          <!-- ===== SYSTEM SWIMLANES (하단) ===== -->
          <div v-for="(lane, bi) in visibleSystemSwimlanes" :key="'bc-'+lane.bcId"
               class="em-swimlane em-swimlane--system"
               :class="{ 'is-bc-drop-target': dropTargetBcId === lane.bcId }"
               :style="{ top: bcYVisible(bi)+'px', width: timelineWidth+'px',
               height: (bcHeights[lane.bcId]||SWIMLANE_MIN_H)+'px',
               background: getColor(bcColors,bi).bg, borderColor: getColor(bcColors,bi).border }"
               @dragover="onBcLaneDragOver($event, lane)"
               @dragleave="onBcLaneDragLeave(lane)"
               @drop="onBcLaneDrop($event, lane)">
            <div class="em-swimlane__hdr" :style="{ width: HEADER_W+'px' }">
              <span>{{ lane.bcDisplayName||lane.bcName }}</span>
            </div>
            <!-- Events -->
            <div v-for="evt in lane.events" :key="evt.id"
                 class="em-card em-card--event"
                 :class="{ 'is-hl': isHl(evt.id), 'is-dimmed': store.hoveredItemId && !isHl(evt.id) && store.hoveredItemId !== evt.id, 'is-dragging': store.draggingEventId === evt.id, 'is-drop-target': dragOverEventId === evt.id && !dropIndicatorParallel, 'is-drop-parallel': dragOverEventId === evt.id && !!dropIndicatorParallel }"
                 :style="{ left: evtCardPos(evt,bi).x+'px', top: evtCardPos(evt,bi).y - bcYVisible(bi)+'px', width: CARD_W+'px', height: CARD_H+'px' }"
                 draggable="true"
                 @dragstart="onEvtDragStart($event, evt)"
                 @dragover="onEvtDragOver($event, evt, bi)"
                 @dragleave="dragOverEventId = null"
                 @drop.stop.prevent="onEvtDrop(evt, bi)"
                 @dragend="onEvtDragEnd"
                 @click="store.selectItem(evt.id,'event')" @dblclick="openInspector(evt.id)"
                 @mouseenter="store.setHoveredItem(evt.id)" @mouseleave="store.clearHover()"
                 @contextmenu="onNodeContextMenu($event, evt.id, 'event')"
                 :title="(evt.displayName||evt.name)+'\n'+evt.commandName">
              <div v-if="store.hoveredItemId === evt.id && warningsFor(evt.id).length" class="em-card__warnings" role="tooltip">
                <div v-for="w in warningsFor(evt.id)" :key="w.type">{{ warningLine(w) }}</div>
              </div>
              <div class="em-card__title">{{ truncate(evt.displayName||evt.name) }}</div>
              <div class="em-card__sub">{{ truncate(evt.commandName, 12) }}</div>
              <div v-if="isConnectMode" class="em-connector em-connector--right"
                   :class="{ 'is-valid-target': isValidDropTarget('event') }"
                   @mousedown="onConnectorMouseDown($event, evt.id, 'event')"
                   @mouseup="onConnectorMouseUp($event, evt.id, 'event')"></div>
            </div>
            <!-- Drop indicator: 시퀀스 이동 (세로선) -->
            <div v-if="store.draggingEventId && dropIndicatorSeq"
                 class="em-drop-indicator em-drop-indicator--seq"
                 :style="{ left: (seqX(dropIndicatorSeq) - SEQ_STEP_W/2 - 2) + 'px' }"></div>
            <!-- Drop indicator: 병렬 배치 (가로선) -->
            <div v-if="store.draggingEventId && dropIndicatorParallel && dropIndicatorParallel.bcId === lane.bcId"
                 class="em-drop-indicator em-drop-indicator--parallel"
                 :style="{ left: (seqX(dropIndicatorParallel.seq) - CARD_W/2 - 8) + 'px',
                            width: (CARD_W + 16) + 'px',
                            top: (lane.events.filter(e => e.sequence === dropIndicatorParallel.seq).length * (CARD_H + 8) + SWIMLANE_PAD) + 'px' }"></div>
          </div>
        </div>
      </div>

      <!-- Floating toolbar (하단 중앙) -->
      <div class="canvas-toolbar">
        <!-- Zoom -->
        <button class="canvas-toolbar__btn" @click="store.zoomOut()" title="축소">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/>
          </svg>
        </button>
        <span class="canvas-toolbar__zoom-pct">{{ Math.round(store.zoomLevel * 100) }}%</span>
        <button class="canvas-toolbar__btn" @click="store.zoomIn()" title="확대">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>
          </svg>
        </button>
        <button class="canvas-toolbar__btn" @click="store.resetZoom()" title="줌 초기화">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
          </svg>
        </button>

        <div class="canvas-toolbar__divider"></div>

        <!-- Filters (+ 노드 개수) -->
        <button class="canvas-toolbar__btn em-filter-btn" :class="{ 'is-active': store.isTypeVisible('event') }" @click="store.toggleTypeVisibility('event')" title="Event 표시">
          <span class="em-filter-btn__lbl em-filter-btn__lbl--event">E</span>
          <span class="em-filter-btn__cnt">{{ filterCounts.event }}</span>
        </button>
        <button class="canvas-toolbar__btn em-filter-btn" :class="{ 'is-active': store.isTypeVisible('command') }" @click="store.toggleTypeVisibility('command')" title="Command 표시">
          <span class="em-filter-btn__lbl em-filter-btn__lbl--command">C</span>
          <span class="em-filter-btn__cnt">{{ filterCounts.command }}</span>
        </button>
        <button class="canvas-toolbar__btn em-filter-btn" :class="{ 'is-active': store.isTypeVisible('readmodel') }" @click="store.toggleTypeVisibility('readmodel')" title="ReadModel 표시">
          <span class="em-filter-btn__lbl em-filter-btn__lbl--readmodel">R</span>
          <span class="em-filter-btn__cnt">{{ filterCounts.readmodel }}</span>
        </button>
        <button class="canvas-toolbar__btn em-filter-btn" :class="{ 'is-active': store.isTypeVisible('ui') }" @click="store.toggleTypeVisibility('ui')" title="UI 표시">
          <span class="em-filter-btn__lbl em-filter-btn__lbl--ui">UI</span>
          <span class="em-filter-btn__cnt">{{ filterCounts.ui }}</span>
        </button>

        <div class="canvas-toolbar__divider"></div>

        <!-- Actions -->
        <button class="canvas-toolbar__btn" @click="store.clearCanvas()" title="캔버스 비우기">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
        <button class="canvas-toolbar__btn" @click="store.fetchEventModeling()" title="새로고침">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
          </svg>
        </button>
        <span v-if="store.isLiveMode" class="em-live-badge" style="margin-left:4px">LIVE {{ store.liveEventCount }}</span>

        <div class="canvas-toolbar__divider"></div>

        <!-- Connect mode toggle -->
        <button class="canvas-toolbar__btn" :class="{ 'is-active': isConnectMode }" @click="toggleConnectMode" title="노드 연결 모드">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
          </svg>
        </button>
        <!-- Palette toggle -->
        <button class="canvas-toolbar__btn" :class="{ 'is-active': store.paletteOpen }" @click="store.togglePalette()" title="노드 팔레트">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>
          </svg>
        </button>
      </div>

      <!-- Palette Panel (좌측 하단) -->
      <div v-if="store.paletteOpen" class="em-palette" @click.stop>
        <div class="em-palette__title">노드 추가</div>
        <div class="em-palette__items">
          <div v-for="item in paletteNodeTypes" :key="item.type"
               class="em-palette__item"
               :style="{ '--palette-color': item.color }"
               draggable="true"
               @dragstart="onPaletteDragStart($event, item.type)">
            <span class="em-palette__item-dot" :style="{ background: item.color }"></span>
            <span class="em-palette__item-label">{{ item.label }}</span>
          </div>
        </div>
        <div class="em-palette__hint">드래그하여 캔버스에 추가</div>
      </div>

      <!-- Context Menu (우클릭) -->
      <Teleport to="body">
        <div v-if="contextMenu.show" class="em-context-menu" :style="{ left: contextMenu.x+'px', top: contextMenu.y+'px' }" @click.stop>
          <button class="em-context-menu__item em-context-menu__item--delete" @click="deleteSelectedNode">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
            삭제
          </button>
        </div>
        <div v-if="contextMenu.show" class="em-context-menu__backdrop" @click="closeContextMenu"></div>
        <!-- Path (관계) 삭제 컨텍스트 메뉴 -->
        <div v-if="pathContextMenu.show" class="em-context-menu" :style="{ left: pathContextMenu.x+'px', top: pathContextMenu.y+'px' }" @click.stop>
          <button class="em-context-menu__item em-context-menu__item--delete" @click="deleteSelectedRelation">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
            연결 삭제
          </button>
        </div>
        <div v-if="pathContextMenu.show" class="em-context-menu__backdrop" @click="closePathContextMenu"></div>
      </Teleport>
    </div>

    <!-- Resizer -->
    <div v-if="panelMode !== 'none'" class="chat-panel-resizer" @mousedown="startResizeChat"></div>

    <!-- Right Panel -->
    <div v-if="panelMode !== 'none'" class="side-panel-wrapper" :style="{ width: chatPanelWidth+'px' }">
      <!-- 패널 접기 버튼 -->
      <div class="right-panel-controls">
        <button class="right-panel-toggle" @click="panelMode = 'none'" title="패널 접기">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </button>
      </div>

      <div v-if="panelMode === 'chat'" class="chat-panel-wrapper">
        <ChatPanel />
      </div>
      <div v-else-if="panelMode === 'inspector' && inspectingNodeId" class="inspector-wrapper">
        <InspectorPanel
          :node-id="inspectingNodeId"
          :initial-tab="inspectingInitialTab"
          @close="closeInspector"
          @updated="() => {}"
        />
      </div>
    </div>

    <!-- Right Sidebar Icons (항상 표시) -->
    <div class="em-right-sidebar">
      <button class="em-right-sidebar__icon" :class="{ 'is-active': panelMode === 'chat' }" @click="toggleChatPanel" title="Chat">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
      </button>
      <button class="em-right-sidebar__icon" :class="{ 'is-active': panelMode === 'inspector' }" @click="toggleInspectorPanel" title="Inspector">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.em-panel { display:flex; height:100%; background:var(--color-bg-primary,#1a1b26); overflow:hidden }
.em-canvas-area { flex:1; display:flex; flex-direction:column; overflow:hidden; position:relative }
.em-live-badge { font-size:.55rem; font-weight:700; color:#e53935; background:rgba(229,57,53,.12); border:1px solid rgba(229,57,53,.3); border-radius:4px; padding:2px 8px; animation:pulse 1.5s infinite }
.em-filter-btn { display:inline-flex; align-items:center; gap:3px; padding:4px 8px !important; min-width:auto; height:auto !important; min-height:36px }
.em-filter-btn__lbl { font-size:.65rem; font-weight:700; line-height:1 }
.em-filter-btn__lbl--event { color:var(--color-event,#fd7e14) }
.em-filter-btn__lbl--command { color:var(--color-command,#5c7cfa) }
.em-filter-btn__lbl--readmodel { color:var(--color-readmodel,#40c057) }
.em-filter-btn__lbl--ui { color:var(--color-text,#c0caf5) }
.em-filter-btn__cnt { font-size:.55rem; font-weight:600; color:var(--color-text-light,#a9b1d6); min-width:1ch }
/* 활성(파란 배경)일 때 타입·숫자 모두 명확한 대비 */
.em-filter-btn.is-active .em-filter-btn__lbl,
.em-filter-btn.is-active .em-filter-btn__cnt {
  color:#fff;
  opacity:1;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.6} }
.em-state { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px; color:var(--color-text-light); font-size:.85rem }
.em-state--droppable { border:2px dashed transparent; transition:border-color .2s }
.em-state--droppable:hover, .em-state--droppable.dragover { border-color:var(--color-accent,#228be6) }
.em-spinner { width:24px; height:24px; border:2px solid var(--color-border); border-top-color:var(--color-accent,#228be6); border-radius:50%; animation:spin .8s linear infinite }
@keyframes spin { to { transform:rotate(360deg) } }
.em-scroll { flex:1; overflow:auto; cursor:grab; position:relative }
.em-scroll.is-panning { cursor:grabbing; user-select:none }
.em-canvas { position:relative; min-width:100%; min-height:100% }
.em-svg { position:absolute; top:0; left:0; pointer-events:none; z-index:5 }
.em-svg path[stroke="transparent"] { pointer-events:stroke }

/* Swimlane */
.em-swimlane { position:absolute; left:0; display:flex; border:1px solid var(--color-border,#414868); border-radius:4px }
.em-swimlane--interaction { background:rgba(76,175,80,.04); border:2px solid rgba(76,175,80,.25) }
.em-swimlane--system { border-style:solid }
.em-swimlane__hdr { display:flex; align-items:center; gap:6px; padding:0 10px; flex-shrink:0; border-right:1px solid var(--color-border,#414868); position:relative; left:0; z-index:10; background:inherit; font-size:.65rem; font-weight:600; color:var(--color-text,#c0caf5); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; will-change:transform }
.em-swimlane__hdr--int { background:rgba(76,175,80,.08) }
.em-swimlane__hdr svg { opacity:.5; flex-shrink:0 }

/* Cards */
.em-card { position:absolute; border-radius:6px; padding:5px 8px; cursor:pointer; z-index:8; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,.2); transition:all .15s }
.em-card:hover { transform:translateY(-1px); box-shadow:0 3px 8px rgba(0,0,0,.3); z-index:12 }
.em-card.is-hl { box-shadow:0 0 0 2px rgba(255,255,255,.6),0 3px 10px rgba(0,0,0,.4); z-index:11; transform:translateY(-1px) }
.em-card.is-dimmed { opacity:.15; pointer-events:auto }
.em-card__warnings {
  position:absolute;
  bottom:calc(100% + 6px);
  left:50%;
  transform:translateX(-50%);
  min-width:max-content;
  max-width:200px;
  padding:5px 8px;
  background:rgba(22,22,30,.96);
  border:1px solid #e53935;
  border-radius:4px;
  font-size:.5rem;
  font-weight:600;
  color:#ffcdd2;
  z-index:35;
  pointer-events:none;
  line-height:1.4;
  text-align:left;
  box-shadow:0 4px 12px rgba(0,0,0,.45);
}
.em-card.is-dragging { opacity:.4; transform:scale(.95) }
.em-card.is-drop-target { box-shadow:0 0 0 3px #228be6,0 4px 12px rgba(34,139,230,.4); transform:translateY(-2px) }
.em-card.is-drop-parallel { box-shadow:0 0 0 3px #40c057,0 4px 12px rgba(64,192,87,.4); transform:translateY(-2px) }
.em-card--ui { background:#fff; border:1px solid #bdbdbd }
.em-card--rm-ui { background:#e8eaf6; border:1px solid #9fa8da }
.em-card--command { background:var(--color-command,#5c7cfa); border:1px solid var(--color-command-dark,#4263eb); color:#fff }
.em-card--event { background:var(--color-event,#fd7e14); border:1px solid var(--color-event-dark,#e8590c); color:#fff }
.em-card--readmodel { background:var(--color-readmodel,#40c057); border:1px solid var(--color-readmodel-dark,#2f9e44); color:#fff }
.em-card__icon { margin-bottom:2px }
.em-card__name { font-size:.55rem; font-weight:500; color:#333; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:100% }
.em-card__title { font-size:.6rem; font-weight:600; line-height:1.2; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:100% }
.em-card__sub { font-size:.5rem; opacity:.8; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:100% }

/* Side panel */
/* Right panel (Design viewer 동일 패턴) */
.chat-panel-resizer { width:4px; cursor:col-resize; background:transparent; flex-shrink:0; transition:background .2s }
.chat-panel-resizer:hover { background:rgba(34,139,230,.3) }
.side-panel-wrapper { flex-shrink:0; height:100%; overflow:hidden; position:relative; border-left:1px solid var(--color-border) }
.right-panel-controls { display:flex; align-items:flex-start; flex-shrink:0; position:absolute; left:0; top:0; z-index:10; pointer-events:none }
.right-panel-toggle { width:20px; height:40px; display:flex; align-items:center; justify-content:center; background:transparent; border:none; color:var(--color-text-light); cursor:pointer; transition:all .15s; padding:0; position:relative; z-index:10; pointer-events:auto }
.right-panel-toggle.is-collapsed { background:var(--color-bg-secondary); border:1px solid var(--color-border); border-radius:6px 0 0 6px }
.right-panel-toggle:hover { color:var(--color-text) }
.right-panel-toggle.is-collapsed:hover { background:var(--color-bg-tertiary) }
.right-panel-controls-collapsed { display:flex; align-items:flex-start; flex-shrink:0 }

/* Inspector / Chat wrapper */
.chat-panel-wrapper, .inspector-wrapper { height:100%; overflow:hidden; display:flex; flex-direction:column }

/* Right Sidebar (Design 탭과 동일) */
.em-right-sidebar { display:flex; flex-direction:column; align-items:center; padding:8px 4px; gap:4px; border-left:1px solid var(--color-border); background:var(--color-bg-primary) }
.em-right-sidebar__icon { width:36px; height:36px; display:flex; align-items:center; justify-content:center; background:transparent; border:none; border-radius:var(--radius-sm); color:var(--color-text-light); cursor:pointer; transition:all .15s }
.em-right-sidebar__icon:hover { background:var(--color-bg-tertiary); color:var(--color-text) }
.em-right-sidebar__icon.is-active { background:var(--color-accent); color:#fff }

/* Connect mode */
.em-scroll.is-connecting { cursor:crosshair }
.em-scroll.is-connecting .em-card { cursor:crosshair }
.em-connector { position:absolute; width:10px; height:10px; border-radius:50%; background:rgba(34,139,230,.7); border:2px solid #228be6; cursor:crosshair; z-index:15; transition:all .15s }
.em-connector--right { right:-5px; top:50%; transform:translateY(-50%) }
.em-connector:hover { transform:translateY(-50%) scale(1.4); background:#228be6 }
.em-connector.is-valid-target { background:rgba(64,192,87,.7); border-color:#40c057; animation:connector-pulse 1s infinite }
@keyframes connector-pulse { 0%,100% { box-shadow:0 0 0 0 rgba(34,139,230,.4) } 50% { box-shadow:0 0 0 4px rgba(34,139,230,.15) } }

/* Palette */
.em-palette { position:absolute; left:12px; bottom:60px; z-index:40; background:var(--color-bg-secondary,#24283b); border:1px solid var(--color-border,#414868); border-radius:8px; padding:10px 12px; min-width:140px; box-shadow:0 4px 16px rgba(0,0,0,.35) }
.em-palette__title { font-size:.6rem; font-weight:700; color:var(--color-text-light,#a9b1d6); margin-bottom:8px; text-transform:uppercase; letter-spacing:.5px }
.em-palette__items { display:flex; flex-direction:column; gap:4px }
.em-palette__item { display:flex; align-items:center; gap:8px; padding:6px 10px; border-radius:6px; cursor:grab; transition:background .15s; border:1px solid transparent }
.em-palette__item:hover { background:rgba(255,255,255,.06); border-color:var(--palette-color) }
.em-palette__item:active { cursor:grabbing }
.em-palette__item-dot { width:10px; height:10px; border-radius:2px; flex-shrink:0 }
.em-palette__item-label { font-size:.65rem; font-weight:600; color:var(--color-text,#c0caf5) }
.em-palette__hint { font-size:.5rem; color:var(--color-text-light,#a9b1d6); margin-top:8px; opacity:.7 }

/* Context Menu */
.em-context-menu { position:fixed; z-index:9999; background:var(--color-bg-secondary,#24283b); border:1px solid var(--color-border,#414868); border-radius:6px; padding:4px; min-width:120px; box-shadow:0 4px 16px rgba(0,0,0,.4) }
.em-context-menu__item { display:flex; align-items:center; gap:6px; width:100%; padding:6px 10px; border:none; background:none; color:var(--color-text,#c0caf5); font-size:.65rem; font-weight:500; border-radius:4px; cursor:pointer; text-align:left }
.em-context-menu__item:hover { background:rgba(255,255,255,.08) }
.em-context-menu__item--delete:hover { background:rgba(229,57,53,.15); color:#ef5350 }
.em-context-menu__backdrop { position:fixed; inset:0; z-index:9998 }

/* Drop indicator */
.em-drop-indicator { position:absolute; z-index:20; pointer-events:none; animation:drop-pulse .8s ease-in-out infinite }
.em-drop-indicator--seq { top:8px; bottom:8px; width:3px; background:#228be6; border-radius:2px }
.em-drop-indicator--parallel { height:3px; background:#40c057; border-radius:2px }
@keyframes drop-pulse { 0%,100% { opacity:1 } 50% { opacity:.4 } }

/* BC swimlane drop target highlight */
.em-swimlane--system.is-bc-drop-target { box-shadow:inset 0 0 0 2px #228be6; background:rgba(34,139,230,.08) !important }
</style>
