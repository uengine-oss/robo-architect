import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useBpmnStore = defineStore('bpmn', () => {
  const loading = ref(false)
  const error = ref(null)

  // 프로세스 흐름 목록 (Navigator용)
  const processFlows = ref([])

  // 현재 캔버스에 렌더링된 프로세스 흐름들
  const renderedFlows = ref([]) // [{id, bpmnXml, structured, startCommand, ...}]

  // 선택된 프로세스 흐름 ID
  const selectedFlowId = ref(null)

  // 현재 활성 BPMN XML (Viewer에 표시할 것)
  const activeBpmnXml = ref(null)
  const activeStructured = ref(null)

  // Inspector: 선택된 노드 데이터
  const selectedNodeData = ref(null)
  const selectedNodeUi = ref(null)

  const renderedFlowIds = computed(() => new Set(renderedFlows.value.map(f => f.id)))

  // 프로세스 흐름 목록 조회
  async function fetchProcessFlows() {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/graph/bpmn/process-flows')
      if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`)
      const data = await res.json()
      processFlows.value = data.flows || []
    } catch (e) {
      error.value = e.message
      console.error('Failed to fetch BPMN process flows:', e)
    } finally {
      loading.value = false
    }
  }

  // 특정 프로세스 흐름 데이터 가져오기 + 캔버스에 추가
  async function addFlow(startCommandId) {
    if (renderedFlowIds.value.has(startCommandId)) return

    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/graph/bpmn/process-flow/${startCommandId}`)
      if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`)
      const data = await res.json()

      const flowData = {
        id: startCommandId,
        bpmnXml: data.bpmnXml,
        structured: data.structured,
        startCommand: data.startCommand,
        nodes: data.nodes,
        relations: data.relations,
        uiMap: data.uiMap || {},
      }

      renderedFlows.value.push(flowData)
      selectedFlowId.value = startCommandId
      activeBpmnXml.value = data.bpmnXml
      activeStructured.value = data.structured
    } catch (e) {
      error.value = e.message
      console.error('Failed to fetch BPMN flow:', e)
    } finally {
      loading.value = false
    }
  }

  // 프로세스 흐름 선택 (이미 렌더링된 것 중에서)
  function selectFlow(flowId) {
    const flow = renderedFlows.value.find(f => f.id === flowId)
    if (flow) {
      selectedFlowId.value = flowId
      activeBpmnXml.value = flow.bpmnXml
      activeStructured.value = flow.structured
    }
  }

  // 프로세스 흐름 제거
  function removeFlow(flowId) {
    renderedFlows.value = renderedFlows.value.filter(f => f.id !== flowId)
    if (selectedFlowId.value === flowId) {
      const next = renderedFlows.value[0]
      if (next) {
        selectFlow(next.id)
      } else {
        selectedFlowId.value = null
        activeBpmnXml.value = null
        activeStructured.value = null
      }
    }
  }

  // BPMN 요소 ID로부터 노드 데이터 찾기
  function findNodeByBpmnElementId(bpmnElementId) {
    const flow = renderedFlows.value.find(f => f.id === selectedFlowId.value)
    if (!flow || !flow.nodes) return null

    // Task_{safe_id} → Command, IntEvent_{safe_id} → Event
    let prefix = null
    let safeSuffix = null

    if (bpmnElementId.startsWith('Task_')) {
      prefix = 'Command'
      safeSuffix = bpmnElementId.slice('Task_'.length)
    } else if (bpmnElementId.startsWith('IntEvent_')) {
      prefix = 'Event'
      safeSuffix = bpmnElementId.slice('IntEvent_'.length)
    } else {
      return null
    }

    // 노드의 id를 safe_id로 변환하여 비교
    function toSafeId(id) {
      return id.replace(/-/g, '_').replace(/\./g, '_').replace(/@/g, '_at_').replace(/ /g, '_')
    }

    const node = flow.nodes.find(n => {
      if (n.label !== prefix) return false
      return toSafeId(n.id) === safeSuffix
    })

    return node || null
  }

  // 노드 선택 (더블클릭 시)
  function selectNodeForInspector(bpmnElementId) {
    const node = findNodeByBpmnElementId(bpmnElementId)
    selectedNodeData.value = node
    selectedNodeUi.value = null

    if (!node) {
      console.warn('[BPMN Inspector] No node found for BPMN element:', bpmnElementId)
      return
    }

    // Command인 경우 uiMap에서 UI wireframe 조회
    if (node.label === 'Command') {
      const flow = renderedFlows.value.find(f => f.id === selectedFlowId.value)
      const ui = flow?.uiMap?.[node.id]
      if (ui) {
        selectedNodeUi.value = ui
      } else {
        console.info('[BPMN Inspector] No UI wireframe for command:', node.id, 'uiMap keys:', Object.keys(flow?.uiMap || {}))
      }
    }
  }

  // Inspector 닫기
  function clearInspectorSelection() {
    selectedNodeData.value = null
    selectedNodeUi.value = null
  }

  // 전체 초기화
  function clear() {
    renderedFlows.value = []
    selectedFlowId.value = null
    activeBpmnXml.value = null
    activeStructured.value = null
    selectedNodeData.value = null
    selectedNodeUi.value = null
  }

  return {
    loading,
    error,
    processFlows,
    renderedFlows,
    selectedFlowId,
    activeBpmnXml,
    activeStructured,
    selectedNodeData,
    selectedNodeUi,
    renderedFlowIds,
    fetchProcessFlows,
    addFlow,
    selectFlow,
    removeFlow,
    clear,
    findNodeByBpmnElementId,
    selectNodeForInspector,
    clearInspectorSelection,
  }
})
