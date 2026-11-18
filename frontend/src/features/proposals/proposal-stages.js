// 프로포절 단계 탭 규칙 — 상단 한 줄(Intent · Plan · Sandbox · Validate · Accept).
//
// 예전엔 상태별로 `tabs.slice(0, 3)` / `slice(0, 4)` 로 잘라 탭을 **숨겼다** — 순서에 묶여 있어
// 탭 하나를 옮기면 노출 규칙이 조용히 틀어졌다. 이제 탭은 늘 다섯 개가 보이고, 탭마다
//   state  : 칩이 말하는 단계 상태  — done(완료) · active(진행중) · ready(준비됨) · locked(잠김)
//   open   : 본문을 그리는가        — false 면 본문 대신 "아직 열리지 않았다" 안내
// 를 **키 기준 허용목록**으로 정한다(`OPEN_BY_STATUS`). 순서와 노출이 서로 묶이지 않는다.
//
// Impact 는 따로 탭이 아니다 — Plan 단계의 산출물(tacticalDiff·impactMap)이라 Plan 탭 안의
// 접힌 섹션으로 들어갔다.

export const STAGE_KEYS = ['intent', 'plan', 'sandbox', 'validate', 'accept']

// 상태 → 지금 진행 중인 단계. ACCEPTED/DESTROYED 는 끝났다(모두 완료).
const CURRENT_STAGE = {
  DRAFT: 'intent',
  SUBMITTED: 'plan',
  IMPLEMENTING: 'sandbox',
  TESTING: 'validate',
  PENDING_ACCEPTANCE: 'accept',
  MERGE_FAILED: 'accept',
}
const FINISHED = new Set(['ACCEPTED', 'DESTROYED'])

// 상태 → 본문을 여는 단계(허용목록). 예전 노출 규칙을 그대로 옮겼다.
//   DRAFT                  Intent · Plan(Plan 은 자체 잠금 안내를 보여 준다)
//   SUBMITTED·IMPLEMENTING Intent · Plan · Sandbox
//   TESTING 이후           전부 — 구현이 끝났으면 검증 전이라도 Accept/Destroy 로 갈 수 있다
const ALL = STAGE_KEYS
const OPEN_BY_STATUS = {
  DRAFT: ['intent', 'plan'],
  SUBMITTED: ['intent', 'plan', 'sandbox'],
  IMPLEMENTING: ['intent', 'plan', 'sandbox'],
  TESTING: ALL,
  PENDING_ACCEPTANCE: ALL,
  MERGE_FAILED: ALL,
  ACCEPTED: ALL,
  DESTROYED: ALL,
}

/**
 * @param {string|null|undefined} status  프로포절 상태(없으면 선택 전)
 * @param {{ canImplement?: boolean }} [opts]  canImplement — SUBMITTED 에서 확정 Plan 이 있어
 *        구현을 시작할 수 있으면 Sandbox 칩을 '준비됨'으로 올린다
 * @returns {{ key: string, state: 'done'|'active'|'ready'|'locked', open: boolean }[]}
 */
export function stageTabs(status, opts = {}) {
  const open = new Set(status ? (OPEN_BY_STATUS[status] || ALL) : ['intent'])
  const finished = FINISHED.has(status)
  const current = CURRENT_STAGE[status]
  const curIdx = current ? STAGE_KEYS.indexOf(current) : (finished ? STAGE_KEYS.length : -1)
  return STAGE_KEYS.map((key, i) => {
    let state
    if (!status) state = 'locked'
    else if (i < curIdx) state = 'done'
    else if (i === curIdx) state = 'active'
    else if (key === 'sandbox' && status === 'SUBMITTED' && opts.canImplement) state = 'ready'
    else state = 'locked'
    return { key, state, open: open.has(key) }
  })
}

export function isStageOpen(status, key, opts = {}) {
  return !!stageTabs(status, opts).find((s) => s.key === key)?.open
}

// 예전 탭 키(diff·impact·tests·acceptance)로 들어오는 값을 새 단계 키로 옮긴다.
const LEGACY_KEY = { diff: 'intent', impact: 'plan', tests: 'validate', acceptance: 'accept' }
export function normalizeStageKey(key) {
  if (STAGE_KEYS.includes(key)) return key
  return LEGACY_KEY[key] || 'intent'
}

/**
 * 목록 필터 — 상태 드롭다운 + 검색어(id·제목·작성자, 대소문자 무시).
 */
export function filterProposals(list, { status = '', query = '' } = {}) {
  const q = String(query || '').trim().toLowerCase()
  return (list || []).filter((p) => {
    if (status && p.status !== status) return false
    if (!q) return true
    return [p.id, p.title, p.author].some((v) => String(v || '').toLowerCase().includes(q))
  })
}
