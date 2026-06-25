// 040 Proposal Impact Artifact Preview — 앱 셸의 도메인 중립 미리보기 세션.
//
// 한 번에 하나의 Proposal 미리보기가 활성화된다(현재 보고 있는 탭 기준). 뷰어 스토어
// (canvas/eventModeling 피처)는 proposals 를 임포트하지 않고 이 셸 모듈만 참조해
//   (1) fetch base 를 라이브↔미리보기로 분기하고
//   (2) 자기 뷰어가 미리보기 중이면 mutation 을 차단(read-only, US2)
// 한다. App.vue / proposals 가 enter/exit 를 호출한다.

import { reactive, computed } from 'vue'

const state = reactive({
  active: false,
  proposalId: null,
  viewer: null,        // 'data' | 'design' | 'process' | 'processes'
  baseUrl: null,       // 예: '/api/proposals/PRO-001/preview'
  label: null,         // 'PRO-001'
  title: null,         // 대상 노드 제목(배너 보조)
  targetNodeId: null,
  bcId: null,
  notice: null,        // 안내 문구(예: 신규 요소가 이 뷰어엔 표시 안 됨)
})

export function usePreviewSession() {
  return state
}

export function enterPreview(opts = {}) {
  Object.assign(state, {
    active: true,
    proposalId: opts.proposalId || null,
    viewer: opts.viewer || null,
    baseUrl: opts.baseUrl || null,
    label: opts.label || opts.proposalId || null,
    title: opts.title || null,
    targetNodeId: opts.targetNodeId || null,
    bcId: opts.bcId || null,
    notice: opts.notice || null,
  })
}

export function exitPreview() {
  Object.assign(state, {
    active: false, proposalId: null, viewer: null, baseUrl: null,
    label: null, title: null, targetNodeId: null, bcId: null, notice: null,
  })
}

// 주어진 뷰어가 현재 미리보기 대상인가? (fetch 분기·mutation 가드 판정용)
export function isPreviewFor(viewer) {
  return state.active && state.viewer === viewer
}

// 라이브 경로(예: '/api/contexts/BC/full-tree')를 미리보기 경로로 변환.
// 미리보기 비활성/뷰어 불일치면 라이브 경로 그대로.
export function previewUrl(viewer, liveApiPath) {
  if (!isPreviewFor(viewer)) return liveApiPath
  // liveApiPath 는 '/api/...' 형태 → '/api' 를 baseUrl 로 치환.
  const tail = liveApiPath.replace(/^\/api/, '')
  return `${state.baseUrl}${tail}`
}

// 뷰어 store 의 mutation 액션 가드. 미리보기 중이면 true 반환 + 경고(호출부에서 early-return).
export function blockIfPreview(viewer, actionName = 'mutation') {
  if (isPreviewFor(viewer)) {
    // eslint-disable-next-line no-console
    console.warn(`[preview] read-only — '${actionName}' 무시됨 (Proposal ${state.proposalId} 미리보기 중)`)
    return true
  }
  return false
}

export const isAnyPreviewActive = computed(() => state.active)
