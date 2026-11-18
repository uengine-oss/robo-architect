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
  // 043-fix: Command/Event/ReadModel 은 Design(캔버스)에서 연다 — 소속 BC 그래프에 투영해
  // 위치 파악(J1) + 인스펙터로 미리보기 정보 확인/수정(J2). Command/Event 는 소유 Aggregate
  // 안에, ReadModel 은 BC 직속으로 배치(Aggregate 소유 관계 없음). (백엔드 /resolve 가 최종 권위.)
  Command: 'design', Event: 'design', ReadModel: 'design',
  // Policy 는 BC 직속 반응 정책(Event→Policy→Command). Design 캔버스에 BC 그래프를 투영해
  // 호출 Command 왼쪽에 Policy 노드를 표시 + 인스펙터로 미리보기(백엔드 /resolve 가 최종 권위).
  Policy: 'design',
  UI: 'design', Screen: 'design', UiFlow: 'design',
  Process: 'process', BpmnFlow: 'process',
  Journey: 'processes', EventModel: 'processes',
}

export const VIEWER_TO_TAB = { data: 'Data', design: 'Design', process: 'Process', processes: 'Processes' }

// 백엔드에 열기 가능 여부 + 대상 뷰어/BC 를 질의한다.
// returns { renderable, viewer, targetNodeId, bcId, reason }
// nodeTitle: impactMap(충돌 가능성 분석) 항목은 nodeId 가 null 일 수 있어, 백엔드가
//   (nodeLabel, nodeTitle)로 tacticalDiff 의 동일 노드를 찾아 합성 nodeId 를 복원한다.
export async function resolveOpenTarget(proposalId, nodeId, nodeLabel, nodeTitle) {
  const qs = new URLSearchParams()
  if (nodeId) qs.set('nodeId', nodeId)
  if (nodeLabel) qs.set('nodeLabel', nodeLabel)
  if (nodeTitle) qs.set('nodeTitle', nodeTitle)
  const res = await fetch(`${BASE}/${proposalId}/preview/resolve?${qs.toString()}`)
  if (!res.ok) {
    return { renderable: false, viewer: null, targetNodeId: nodeId, bcId: null, reason: `resolve 실패(${res.status})` }
  }
  return res.json()
}

// 임팩트/diff 항목 "열기": 백엔드 resolve → robo:open-preview emit.
// item: { nodeId, nodeLabel, nodeTitle }
export async function openPreview(proposalId, item) {
  const resolved = await resolveOpenTarget(proposalId, item?.nodeId, item?.nodeLabel, item?.nodeTitle)
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
      // 040 — Data 뷰어는 Aggregate 단위로 포커스하므로 백엔드가 해소한 소유 Aggregate id 를 전달.
      // Command/Event/VO 대상이면 targetNodeId(자식 id) 가 아니라 이 값으로 포커스해야 한다.
      aggregateId: resolved.aggregateId || null,
      bcId: resolved.bcId || null,
      nodeLabel: item?.nodeLabel || '',
      label: proposalId,
      title: item?.nodeTitle || item?.nodeId || '',
      notice: resolved.notice || null,
    },
  }))
  return resolved
}

// preview base URL (스토어 setPreviewSource 에 전달).
export function previewBaseUrl(proposalId) {
  return `${BASE}/${proposalId}/preview`
}

// ── B-4 ⑧ 전체 미리보기 ─────────────────────────────────────────────────
// 항목 하나가 아니라 **제안 전체**를 오버레이로 본다. 새 백엔드는 없다 — BC 마다
// 기존 투영 엔드포인트(design graph · data full-tree)를 다시 부른다.

// 제안이 건드리는 BC id 목록(순서 보존 · 중복 제거). 순수 함수 — 단위 시험 대상.
//   ① tacticalDiff(없으면 planDraft.tacticalDiff) 항목의 boundedContextId
//   ② impactMap 의 BoundedContext 항목 nodeId
//   ③ tacticalDiff 의 BoundedContext 항목 nodeId(MODIFY — 라이브 BC)
export function collectPreviewBcIds(proposal) {
  if (!proposal) return []
  const out = []
  const add = (v) => {
    const s = v == null ? '' : String(v).trim()
    if (s && !s.startsWith('PREVIEW:') && !out.includes(s)) out.push(s)
  }
  const tactical = (proposal.tacticalDiff && proposal.tacticalDiff.length)
    ? proposal.tacticalDiff
    : (proposal.planDraft?.tacticalDiff || [])
  for (const it of tactical || []) {
    if (!it || typeof it !== 'object') continue
    add(it.boundedContextId)
    if (it.nodeLabel === 'BoundedContext' && (it.changeType || 'MODIFY') !== 'CREATE') add(it.nodeId)
  }
  for (const e of proposal.impactMap || []) {
    if (e && e.nodeLabel === 'BoundedContext') add(e.nodeId)
  }
  return out
}

// 전체 미리보기 진입 — viewer: 'design' | 'processes'.
// BC 를 하나도 못 찾으면 tactical 항목 몇 개를 resolve 해 bcId 를 얻는다(신규 Command 등).
export async function openFullPreview(proposal, viewer = 'design') {
  if (!proposal?.id) return { ok: false, reason: '제안이 없습니다' }
  let bcIds = collectPreviewBcIds(proposal)
  if (!bcIds.length) {
    const tactical = proposal.tacticalDiff?.length ? proposal.tacticalDiff : (proposal.planDraft?.tacticalDiff || [])
    for (const it of tactical.slice(0, 5)) {
      try {
        const r = await resolveOpenTarget(proposal.id, it?.nodeId, it?.nodeLabel, it?.nodeTitle)
        if (r?.bcId && !bcIds.includes(r.bcId)) bcIds.push(r.bcId)
      } catch { /* best-effort */ }
    }
  }
  if (viewer === 'design' && !bcIds.length) {
    const reason = '미리보기로 그릴 Bounded Context 를 찾지 못했습니다(Plan 을 먼저 돌려 Impact 를 만드세요).'
    window.dispatchEvent(new CustomEvent('robo:open-preview-failed', {
      detail: { proposalId: proposal.id, item: null, reason },
    }))
    return { ok: false, reason }
  }
  window.dispatchEvent(new CustomEvent('robo:open-preview', {
    detail: {
      proposalId: proposal.id,
      viewer,
      full: true,
      bcIds,
      bcId: bcIds[0] || null,
      targetNodeId: null,
      label: proposal.id,
      title: '전체',
      notice: viewer === 'processes'
        ? 'Processes 는 라이브 이벤트 모델을 읽기 전용으로 보여 줍니다 — 제안의 신규 요소는 Design 과 탐색기에서 확인하세요.'
        : null,
    },
  }))
  return { ok: true, bcIds }
}
