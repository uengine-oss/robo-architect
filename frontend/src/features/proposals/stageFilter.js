/**
 * 프로포절 목록 상단 단계 탭의 집계·필터 (lite ⑬, 사용자 2026-11-18).
 *
 * 단계 탭은 "그 단계에 있는 것"만이 아니라 **그 단계를 지난 것까지** 보여 준다 —
 * 완료(ACCEPTED)된 프로포절도 앞 단계 탭에서 사라지지 않는다.
 *   Intent 탭 = 지금 Intent(진행중) + Intent 를 지난 것(완료)
 * 폐기(DESTROYED)는 어느 단계도 완료한 것이 아니므로 단계 탭에 넣지 않는다 —
 * 「전체」와 「DESTROYED」 탭에서만 보인다.
 */

// 라이프사이클 순서. MERGE_FAILED 는 승인 단계에서 merge 가 실패한 것 — 승인 대기와 같은 자리.
export const STAGE_RANK = Object.freeze({
  DRAFT: 0,
  SUBMITTED: 1,
  IMPLEMENTING: 2,
  TESTING: 3,
  PENDING_ACCEPTANCE: 4,
  MERGE_FAILED: 4,
  ACCEPTED: 5,
})

function rankOf(status) {
  return Object.prototype.hasOwnProperty.call(STAGE_RANK, status) ? STAGE_RANK[status] : null
}

/** 그 탭(status 값)에 이 프로포절이 드는가. '' = 전체. */
export function inStageTab(tab, status) {
  if (!tab) return true
  if (tab === 'DESTROYED') return status === 'DESTROYED'
  const t = rankOf(tab)
  const s = rankOf(status)
  if (t === null || s === null) return tab === status
  return s >= t
}

/** 진행중(그 단계에 있음) / 완료(그 단계를 지남) */
export function stagePhase(tab, status) {
  if (!tab || tab === 'DESTROYED') return null
  const t = rankOf(tab)
  const s = rankOf(status)
  if (t === null || s === null) return null
  if (s === t) return 'current'
  return s > t ? 'passed' : null
}

/** 탭에 보일 목록 — 진행중을 먼저, 그다음 완료. 각 묶음 안에서는 원래 순서. */
export function filterForStageTab(proposals, tab) {
  const list = (proposals || []).filter((p) => inStageTab(tab, p.status))
  if (!tab) return list
  const current = list.filter((p) => stagePhase(tab, p.status) !== 'passed')
  const passed = list.filter((p) => stagePhase(tab, p.status) === 'passed')
  return [...current, ...passed]
}

/** 탭 배지 — total = 진행중 + 완료 */
export function countForStageTab(proposals, tab) {
  let current = 0
  let passed = 0
  for (const p of proposals || []) {
    if (!inStageTab(tab, p.status)) continue
    if (stagePhase(tab, p.status) === 'passed') passed += 1
    else current += 1
  }
  return { total: current + passed, current, passed }
}
