// 040 Proposal Impact Artifact Preview — 프런트 오케스트레이션 진입점.
//
// proposals 피처는 뷰어 스토어(canvas/eventModeling)를 직접 임포트하지 않는다
// (Constitution V). 대신 앱 레벨 커스텀 이벤트를 emit 하고, App.vue 가 수신해
// 탭 전환 + 대상 store.setPreviewSource + 노드 포커스를 오케스트레이션한다.
// (기존 'robo:switch-tab' / 'claude-terminal-open' 패턴과 동일.)

const BASE = '/api/proposals'

// nodeLabel → viewer 매핑(프런트 측 1차 추정). 백엔드 /resolve 가 최종 권위.
export const LABEL_TO_VIEWER = {
  Aggregate: 'data', ValueObject: 'data', Enum: 'data', Enumeration: 'data',
  Command: 'data', Event: 'data',
  UI: 'design', Screen: 'design', UiFlow: 'design',
  Process: 'process', BpmnFlow: 'process',
  Journey: 'processes', EventModel: 'processes', ReadModel: 'processes',
}

export const VIEWER_TO_TAB = { data: 'Data', design: 'Design', process: 'Process', processes: 'Processes' }

// 백엔드에 열기 가능 여부 + 대상 뷰어/BC 를 질의한다.
// returns { renderable, viewer, targetNodeId, bcId, reason }
export async function resolveOpenTarget(proposalId, nodeId, nodeLabel) {
  const qs = new URLSearchParams()
  if (nodeId) qs.set('nodeId', nodeId)
  if (nodeLabel) qs.set('nodeLabel', nodeLabel)
  const res = await fetch(`${BASE}/${proposalId}/preview/resolve?${qs.toString()}`)
  if (!res.ok) {
    return { renderable: false, viewer: null, targetNodeId: nodeId, bcId: null, reason: `resolve 실패(${res.status})` }
  }
  return res.json()
}

// 임팩트/diff 항목 "열기": 백엔드 resolve → robo:open-preview emit.
// item: { nodeId, nodeLabel, nodeTitle }
export async function openPreview(proposalId, item) {
  const resolved = await resolveOpenTarget(proposalId, item?.nodeId, item?.nodeLabel)
  if (!resolved.renderable) {
    window.dispatchEvent(new CustomEvent('robo:open-preview-failed', {
      detail: { proposalId, item, reason: resolved.reason },
    }))
    return resolved
  }
  window.dispatchEvent(new CustomEvent('robo:open-preview', {
    detail: {
      proposalId,
      viewer: resolved.viewer,
      targetNodeId: resolved.targetNodeId || item?.nodeId,
      bcId: resolved.bcId || null,
      nodeLabel: item?.nodeLabel || '',
      label: proposalId,
      title: item?.nodeTitle || item?.nodeId || '',
    },
  }))
  return resolved
}

// preview base URL (스토어 setPreviewSource 에 전달).
export function previewBaseUrl(proposalId) {
  return `${BASE}/${proposalId}/preview`
}
