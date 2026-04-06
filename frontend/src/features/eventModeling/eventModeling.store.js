import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useEventModelingStore = defineStore('eventModeling', () => {
  const loading = ref(false)
  const error = ref(null)

  // Swimlane data (캔버스 렌더용 — 선택된 프로세스만)
  const actorSwimlanes = ref([])
  const interactionCommands = ref([])
  const interactionReadModels = ref([])
  const systemSwimlanes = ref([])
  const flows = ref([])
  const maxSequence = ref(1)

  // 전체 API 응답 (Navigator 프로세스 목록용)
  const _allResponse = ref(null)
  const canvasProcessIds = ref(new Set())

  // Ingestion live mode
  const isLiveMode = ref(false)
  const liveEventCount = ref(0)

  // Visibility filter
  const visibleTypes = ref(new Set(['event', 'command', 'readmodel', 'ui']))

  // UI state
  const zoomLevel = ref(1)
  const selectedItemId = ref(null)
  const selectedItemType = ref(null)
  const selectedItemDetail = ref(null)
  const hoveredItemId = ref(null)

  const allActors = computed(() => actorSwimlanes.value.map(a => a.actor))
  const totalCommands = computed(() => interactionCommands.value.length)
  const totalEvents = computed(() =>
    systemSwimlanes.value.reduce((sum, s) => sum + s.events.length, 0)
  )

  // ── 검증: 누락 흐름 감지 ───────────────────────────────────
  const validationWarnings = computed(() => {
    const warnings = []
    // EMITS 없는 Command
    const cmdEvtFlows = new Set(flows.value.filter(f => f.type === 'command-to-event').map(f => f.sourceId))
    for (const cmd of interactionCommands.value) {
      if (!cmdEvtFlows.has(cmd.id)) {
        warnings.push({ type: 'no-emits', nodeType: 'command', nodeId: cmd.id, name: cmd.displayName || cmd.name })
      }
    }
    // UI 없는 Command
    const cmdUiFlows = new Set(flows.value.filter(f => f.type === 'ui-to-command').map(f => f.targetId))
    for (const cmd of interactionCommands.value) {
      if (!cmdUiFlows.has(cmd.id)) {
        warnings.push({ type: 'no-ui', nodeType: 'command', nodeId: cmd.id, name: cmd.displayName || cmd.name })
      }
    }
    // CQRS 없는 Event (ReadModel에 연결되지 않은)
    const evtRmFlows = new Set(flows.value.filter(f => f.type === 'event-to-readmodel').map(f => f.sourceId))
    const allEvtIds = new Set()
    for (const lane of systemSwimlanes.value) {
      for (const evt of lane.events) allEvtIds.add(evt.id)
    }
    for (const evtId of allEvtIds) {
      if (!evtRmFlows.has(evtId)) {
        let evtName = ''
        for (const lane of systemSwimlanes.value) {
          const e = lane.events.find(ev => ev.id === evtId)
          if (e) { evtName = e.displayName || e.name; break }
        }
        warnings.push({ type: 'no-cqrs', nodeType: 'event', nodeId: evtId, name: evtName })
      }
    }
    return warnings
  })

  const warningNodeIds = computed(() => new Set(validationWarnings.value.map(w => w.nodeId)))

  // ── 프로세스 체인 빌더 (공용) ────────────────────────────────
  function _buildProcessChains(data) {
    if (!data) return []
    const { interactionCommands: cmds, interactionReadModels: rms, systemSwimlanes: sysLanes, flows: flowList, actorSwimlanes: actorLanes } = data

    const policyInvokedCmds = new Set(
      flowList.filter(f => f.type === 'event-to-command').map(f => f.targetId)
    )
    const entryCmds = cmds.filter(c => !policyInvokedCmds.has(c.id))

    // flow 인덱스
    const cmdToEvts = {}, evtToNextCmds = {}, evtToRms = {}, cmdToUis = {}, rmToUis = {}
    flowList.forEach(f => {
      if (f.type === 'command-to-event') { (cmdToEvts[f.sourceId] ||= []).push(f.targetId) }
      else if (f.type === 'event-to-command') { (evtToNextCmds[f.sourceId] ||= []).push(f.targetId) }
      else if (f.type === 'event-to-readmodel') { (evtToRms[f.sourceId] ||= []).push(f.targetId) }
      else if (f.type === 'ui-to-command') { (cmdToUis[f.targetId] ||= []).push(f.sourceId) }
      else if (f.type === 'readmodel-to-ui') { (rmToUis[f.sourceId] ||= []).push(f.targetId) }
    })

    // 노드 룩업
    const evtById = {}, cmdById = {}, rmById = {}, uiById = {}
    sysLanes.forEach(lane => { lane.events.forEach(e => { evtById[e.id] = e }) })
    cmds.forEach(c => { cmdById[c.id] = c })
    rms.forEach(r => { rmById[r.id] = r })
    if (actorLanes) actorLanes.forEach(lane => { lane.uis.forEach(u => { uiById[u.id] = u }) })

    const chains = []
    for (const entryCmd of entryCmds) {
      const steps = [], visited = new Set(), queue = [entryCmd.id]
      let minSeq = Infinity, maxSeq = 0

      while (queue.length > 0) {
        const cmdId = queue.shift()
        if (visited.has(cmdId)) continue
        visited.add(cmdId)
        const cmd = cmdById[cmdId]
        if (!cmd) continue

        // UI (input) → Command
        for (const uiId of (cmdToUis[cmdId] || [])) {
          const ui = uiById[uiId]
          if (ui) steps.push({ id: ui.id, name: ui.displayName || ui.name, type: 'ui', sequence: ui.sequence || cmd.sequence })
        }

        steps.push({ id: cmd.id, name: cmd.displayName || cmd.name, type: 'command', sequence: cmd.sequence })
        minSeq = Math.min(minSeq, cmd.sequence); maxSeq = Math.max(maxSeq, cmd.sequence)

        for (const evtId of (cmdToEvts[cmdId] || [])) {
          const evt = evtById[evtId]
          if (evt) {
            steps.push({ id: evt.id, name: evt.displayName || evt.name, type: 'event', sequence: evt.sequence })
            maxSeq = Math.max(maxSeq, evt.sequence)
          }
          for (const rmId of (evtToRms[evtId] || [])) {
            const rm = rmById[rmId]
            if (rm) {
              steps.push({ id: rm.id, name: rm.displayName || rm.name, type: 'readmodel', sequence: rm.sequence })
              // ReadModel → UI (output)
              for (const uiId of (rmToUis[rmId] || [])) {
                const ui = uiById[uiId]
                if (ui) steps.push({ id: ui.id, name: ui.displayName || ui.name, type: 'ui', sequence: ui.sequence || rm.sequence })
              }
            }
          }
          for (const nextCmdId of (evtToNextCmds[evtId] || [])) {
            if (!visited.has(nextCmdId)) queue.push(nextCmdId)
          }
        }
      }

      // 중복 제거 (같은 UI가 여러 경로에서 참조될 수 있음)
      const seen = new Set()
      const uniqueSteps = steps.filter(s => { if (seen.has(s.id)) return false; seen.add(s.id); return true })
      uniqueSteps.sort((a, b) => a.sequence - b.sequence)

      chains.push({ id: entryCmd.id, name: entryCmd.displayName || entryCmd.name, actor: entryCmd.actor, steps: uniqueSteps, minSeq, maxSeq, stepCount: uniqueSteps.length })
    }
    chains.sort((a, b) => a.minSeq - b.minSeq)
    return chains
  }

  // ── 프로세스 체인 (Navigator — _allResponse 기반) ───────────
  const processChains = computed(() => _buildProcessChains(_allResponse.value))

  const highlightedIds = computed(() => {
    if (!hoveredItemId.value) return new Set()
    const ids = new Set([hoveredItemId.value])
    flows.value.forEach(f => {
      if (f.sourceId === hoveredItemId.value) {
        ids.add(f.targetId)
      }
    })
    return ids
  })

  // ── Live mode: Ingestion 중 실시간 노드 추가 ────────────────

  function startLiveMode() {
    isLiveMode.value = true
    liveEventCount.value = 0
    // 기존 데이터 클리어
    actorSwimlanes.value = []
    interactionCommands.value = []
    interactionReadModels.value = []
    systemSwimlanes.value = []
    flows.value = []
    maxSequence.value = 1
  }

  function stopLiveMode() {
    isLiveMode.value = false
  }

  /** Event 노드 추가 (Ingestion SSE에서 호출) */
  function addLiveEvent(obj) {
    // obj: { id, name, type:'Event', userStoryId, sequence, parentId(bcId) }
    const seq = obj.sequence || (maxSequence.value + 1)
    if (seq > maxSequence.value) maxSequence.value = seq

    const bcId = obj.parentId || obj.bcId || '__unassigned'
    const bcName = obj.bcName || bcId

    // System swimlane 찾거나 생성
    let lane = systemSwimlanes.value.find(s => s.bcId === bcId)
    if (!lane) {
      lane = { bcId, bcName, bcDisplayName: bcName, events: [] }
      systemSwimlanes.value.push(lane)
    }

    // 중복 체크
    if (lane.events.some(e => e.id === obj.id)) return

    lane.events.push({
      id: obj.id,
      name: obj.name,
      displayName: obj.displayName || obj.name,
      commandName: '',
      actor: obj.actor || '',
      bcId,
      sequence: seq,
    })
    lane.events.sort((a, b) => a.sequence - b.sequence)
    liveEventCount.value++
  }

  /** BC 할당: unassigned 이벤트들을 BC swimlane으로 이동 */
  function assignEventToBC(eventId, bcId, bcName) {
    // unassigned lane에서 제거
    const unassigned = systemSwimlanes.value.find(s => s.bcId === '__unassigned')
    if (!unassigned) return
    const evtIdx = unassigned.events.findIndex(e => e.id === eventId)
    if (evtIdx < 0) return
    const [evt] = unassigned.events.splice(evtIdx, 1)
    evt.bcId = bcId

    // 대상 BC lane 찾거나 생성
    let lane = systemSwimlanes.value.find(s => s.bcId === bcId)
    if (!lane) {
      lane = { bcId, bcName, bcDisplayName: bcName, events: [] }
      systemSwimlanes.value.push(lane)
    }
    lane.events.push(evt)
    lane.events.sort((a, b) => a.sequence - b.sequence)

    // unassigned lane이 비었으면 제거
    if (unassigned.events.length === 0) {
      systemSwimlanes.value = systemSwimlanes.value.filter(s => s.bcId !== '__unassigned')
    }
  }

  /** Command 노드 추가 */
  function addLiveCommand(obj) {
    if (interactionCommands.value.some(c => c.id === obj.id)) return
    const seq = obj.sequence || maxSequence.value
    interactionCommands.value.push({
      id: obj.id,
      name: obj.name,
      displayName: obj.displayName || obj.name,
      actor: obj.actor || '',
      aggregateName: obj.aggregateName || '',
      bcId: obj.parentId || obj.bcId || '',
      sequence: seq,
    })
    interactionCommands.value.sort((a, b) => a.sequence - b.sequence)
  }

  /** ReadModel 노드 추가 */
  function addLiveReadModel(obj) {
    if (interactionReadModels.value.some(r => r.id === obj.id)) return
    interactionReadModels.value.push({
      id: obj.id,
      name: obj.name,
      displayName: obj.displayName || obj.name,
      actor: obj.actor || 'user',
      bcId: obj.parentId || obj.bcId || '',
      sequence: obj.sequence || maxSequence.value,
    })
  }

  /** UI 노드 추가 (Actor swimlane) */
  function addLiveUI(obj) {
    const actor = obj.actor || 'user'
    let lane = actorSwimlanes.value.find(a => a.actor === actor)
    if (!lane) {
      lane = { actor, uis: [] }
      actorSwimlanes.value.push(lane)
      actorSwimlanes.value.sort((a, b) => a.actor.localeCompare(b.actor))
    }
    if (lane.uis.some(u => u.id === obj.id)) return
    lane.uis.push({
      id: obj.id,
      name: obj.name,
      displayName: obj.displayName || obj.name,
      actor,
      sequence: obj.sequence || 1,
      commandId: obj.commandId || obj.attachedToId,
    })
    lane.uis.sort((a, b) => a.sequence - b.sequence)
  }

  /** BC swimlane 추가 (BC 식별 시) */
  function addLiveBC(obj) {
    const bcId = obj.id
    if (systemSwimlanes.value.some(s => s.bcId === bcId)) return
    systemSwimlanes.value.push({
      bcId,
      bcName: obj.name,
      bcDisplayName: obj.displayName || obj.name,
      events: [],
    })
  }

  // ── Visibility filter ──────────────────────────────────────

  function toggleTypeVisibility(type) {
    if (visibleTypes.value.has(type)) visibleTypes.value.delete(type)
    else visibleTypes.value.add(type)
    // trigger reactivity
    visibleTypes.value = new Set(visibleTypes.value)
  }

  function isTypeVisible(type) {
    return visibleTypes.value.has(type)
  }

  // ── Selection / Hover / Zoom ───────────────────────────────

  async function selectItem(id, type) {
    if (selectedItemId.value === id) {
      selectedItemId.value = null; selectedItemType.value = null; selectedItemDetail.value = null
      return
    }
    selectedItemId.value = id; selectedItemType.value = type; selectedItemDetail.value = null
    if (type === 'readmodel') {
      try {
        const res = await fetch(`/api/readmodel/${id}/cqrs`)
        if (res.ok) selectedItemDetail.value = await res.json()
      } catch (e) { /* silent */ }
    }
  }
  function clearSelection() { selectedItemId.value = null; selectedItemType.value = null; selectedItemDetail.value = null }
  function setHoveredItem(id) { hoveredItemId.value = id }
  function clearHover() { hoveredItemId.value = null }
  function zoomIn() { zoomLevel.value = Math.min(zoomLevel.value + 0.1, 2.5) }
  function zoomOut() { zoomLevel.value = Math.max(zoomLevel.value - 0.1, 0.3) }
  function resetZoom() { zoomLevel.value = 1 }
  function setZoom(v) { zoomLevel.value = Math.max(0.3, Math.min(2.5, v)) }

  // ── Event 드래그 순서 변경 ──────────────────────────────────

  const draggingEventId = ref(null)

  /** 두 Event의 sequence를 스왑하고 Neo4j에 반영 */
  async function swapEventSequence(eventIdA, eventIdB) {
    // 캔버스에서 sequence 찾기
    let evtA = null, evtB = null
    for (const lane of systemSwimlanes.value) {
      for (const e of lane.events) {
        if (e.id === eventIdA) evtA = e
        if (e.id === eventIdB) evtB = e
      }
    }
    if (!evtA || !evtB) return

    // 스왑
    const tmpSeq = evtA.sequence
    evtA.sequence = evtB.sequence
    evtB.sequence = tmpSeq

    // 정렬
    for (const lane of systemSwimlanes.value) {
      lane.events.sort((a, b) => a.sequence - b.sequence)
    }

    // Neo4j 반영
    try {
      await fetch('/api/graph/event-modeling/reorder', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          orders: [
            { eventId: evtA.id, sequence: evtA.sequence },
            { eventId: evtB.id, sequence: evtB.sequence },
          ]
        }),
      })
    } catch (e) { /* silent */ }
  }

  // ── 프로세스 단위 캔버스 제어 ────────────────────────────────

  /** 프로세스를 캔버스에 추가 */
  function addProcessToCanvas(procId) {
    canvasProcessIds.value = new Set([...canvasProcessIds.value, procId])
    _rebuildCanvas()
  }

  /** 프로세스를 캔버스에서 제거 */
  function removeProcessFromCanvas(procId) {
    const s = new Set(canvasProcessIds.value)
    s.delete(procId)
    canvasProcessIds.value = s
    _rebuildCanvas()
  }

  /** 프로세스 토글 (더블클릭용) */
  function toggleProcessOnCanvas(procId) {
    if (canvasProcessIds.value.has(procId)) removeProcessFromCanvas(procId)
    else addProcessToCanvas(procId)
  }

  /** 선택된 프로세스 기반으로 캔버스 재구성 */
  function _rebuildCanvas() {
    const data = _allResponse.value
    if (!data) return

    const selected = processChains.value.filter(p => canvasProcessIds.value.has(p.id))
    if (selected.length === 0) {
      clearCanvas(); return
    }

    // ── 1. 선택된 프로세스의 노드 ID 수집 ───────────────────
    const cmdIds = new Set(), evtIds = new Set(), rmIds = new Set(), uiIds = new Set()
    for (const proc of selected) {
      for (const step of proc.steps) {
        if (step.type === 'command') cmdIds.add(step.id)
        else if (step.type === 'event') evtIds.add(step.id)
        else if (step.type === 'readmodel') rmIds.add(step.id)
        else if (step.type === 'ui') uiIds.add(step.id)
      }
    }

    // flows 기반으로 추가 UI 보완 (프로세스 체인에서 누락된 경우)
    data.flows.forEach(f => {
      if (f.type === 'ui-to-command' && cmdIds.has(f.targetId)) uiIds.add(f.sourceId)
      if (f.type === 'readmodel-to-ui' && rmIds.has(f.sourceId)) uiIds.add(f.targetId)
    })

    // ── 2. deep clone으로 캔버스 데이터 구성 (원본 보호) ─────
    const filteredCmds = data.interactionCommands
      .filter(c => cmdIds.has(c.id))
      .map(c => ({ ...c }))

    const filteredRms = data.interactionReadModels
      .filter(r => rmIds.has(r.id))
      .map(r => ({ ...r }))

    const filteredSysLanes = data.systemSwimlanes
      .map(lane => ({
        ...lane,
        events: lane.events.filter(e => evtIds.has(e.id)).map(e => ({ ...e }))
      }))
      .filter(lane => lane.events.length > 0)

    const filteredActorLanes = data.actorSwimlanes
      .map(lane => ({
        ...lane,
        uis: lane.uis.filter(u => uiIds.has(u.id)).map(u => ({ ...u }))
      }))
      .filter(lane => lane.uis.length > 0)

    const allIds = new Set([...cmdIds, ...evtIds, ...rmIds, ...uiIds])
    const filteredFlows = data.flows
      .filter(f => allIds.has(f.sourceId) && allIds.has(f.targetId))
      .map(f => ({ ...f }))

    // ── 3. 시퀀스 압축: 빈 구간 없이 1부터 연속 번호로 재매핑 ──
    const usedSeqs = new Set()
    filteredCmds.forEach(c => usedSeqs.add(c.sequence))
    filteredRms.forEach(r => usedSeqs.add(r.sequence))
    filteredSysLanes.forEach(l => l.events.forEach(e => usedSeqs.add(e.sequence)))
    filteredActorLanes.forEach(l => l.uis.forEach(u => usedSeqs.add(u.sequence)))

    const sortedSeqs = [...usedSeqs].sort((a, b) => a - b)
    const seqRemap = {}
    sortedSeqs.forEach((seq, i) => { seqRemap[seq] = i + 1 })

    filteredCmds.forEach(c => { c.sequence = seqRemap[c.sequence] ?? c.sequence })
    filteredRms.forEach(r => { r.sequence = seqRemap[r.sequence] ?? r.sequence })
    filteredSysLanes.forEach(l => l.events.forEach(e => { e.sequence = seqRemap[e.sequence] ?? e.sequence }))
    filteredActorLanes.forEach(l => l.uis.forEach(u => { u.sequence = seqRemap[u.sequence] ?? u.sequence }))

    // ── 4. 캔버스 refs 갱신 ─────────────────────────────────
    interactionCommands.value = filteredCmds
    interactionReadModels.value = filteredRms
    systemSwimlanes.value = filteredSysLanes
    actorSwimlanes.value = filteredActorLanes
    flows.value = filteredFlows
    maxSequence.value = sortedSeqs.length || 1

    selectedItemId.value = null
    selectedItemType.value = null
    selectedItemDetail.value = null
  }

  /** 캔버스 비우기 (_allResponse 유지) */
  function clearCanvas() {
    canvasProcessIds.value = new Set()
    actorSwimlanes.value = []
    interactionCommands.value = []
    interactionReadModels.value = []
    systemSwimlanes.value = []
    flows.value = []
    maxSequence.value = 1
    selectedItemId.value = null
    selectedItemType.value = null
    selectedItemDetail.value = null
  }

  // ── API fetch ──────────────────────────────────────────────

  /** Navigator용: 프로세스 목록만 로드 (캔버스 변경 없음) */
  async function fetchProcessList() {
    loading.value = true; error.value = null
    try {
      const res = await fetch('/api/graph/event-modeling')
      if (!res.ok) throw new Error(res.statusText)
      _allResponse.value = await res.json()
    } catch (e) {
      error.value = e.message
    } finally { loading.value = false }
  }

  /** 전체 로드 → 캔버스에 모두 표시 (툴바 새로고침) */
  async function fetchEventModeling() {
    await fetchProcessList()
    if (_allResponse.value) {
      canvasProcessIds.value = new Set(processChains.value.map(p => p.id))
      _rebuildCanvas()
    }
  }

  function reset() {
    _allResponse.value = null; canvasProcessIds.value = new Set()
    actorSwimlanes.value = []; interactionCommands.value = []; interactionReadModels.value = []
    systemSwimlanes.value = []; flows.value = []; maxSequence.value = 1
    zoomLevel.value = 1; selectedItemId.value = null; hoveredItemId.value = null
    selectedItemDetail.value = null; isLiveMode.value = false; liveEventCount.value = 0
    loading.value = false; error.value = null
    visibleTypes.value = new Set(['event', 'command', 'readmodel', 'ui'])
  }

  return {
    loading, error,
    actorSwimlanes, interactionCommands, interactionReadModels, systemSwimlanes,
    flows, maxSequence,
    isLiveMode, liveEventCount, visibleTypes,
    zoomLevel, selectedItemId, selectedItemType, selectedItemDetail, hoveredItemId,
    allActors, totalCommands, totalEvents, highlightedIds, validationWarnings, warningNodeIds,
    processChains, canvasProcessIds,
    // Drag reorder
    draggingEventId, swapEventSequence,
    // Live mode
    startLiveMode, stopLiveMode,
    addLiveEvent, assignEventToBC, addLiveCommand, addLiveReadModel, addLiveUI, addLiveBC,
    // Visibility
    toggleTypeVisibility, isTypeVisible,
    // Selection
    selectItem, clearSelection, setHoveredItem, clearHover,
    zoomIn, zoomOut, resetZoom, setZoom,
    addProcessToCanvas, removeProcessFromCanvas, toggleProcessOnCanvas,
    clearCanvas, fetchProcessList, fetchEventModeling, reset,
  }
})
