/**
 * 프로포절 단계 탭 규칙(D-1 ⑬ + C-2 ③).
 *
 * 예전 availableTabs 는 `slice(0,3)` / `slice(0,4)` 로 순서에 묶여 있었다 — 탭 하나를 옮기면
 * 상태별 노출이 **조용히** 틀어졌다. 여기서 상태마다 어느 탭이 열리고(open) 칩이 무엇인지
 * (state) 표로 못 박는다. 표가 바뀌면 이 시험이 먼저 깨져야 한다.
 */
import { expect, test } from '@playwright/test'

// @ts-expect-error 플레인 JS 모듈
import { STAGE_KEYS, stageTabs, isStageOpen, normalizeStageKey, filterProposals } from '../../src/features/proposals/proposal-stages.js'

type Row = { key: string; state: string; open: boolean }
const view = (rows: Row[]) => Object.fromEntries(rows.map((r) => [r.key, `${r.open ? 'open' : 'shut'}/${r.state}`]))

test('탭은 늘 다섯 개, 이 순서다 — Impact 는 탭이 아니다(Plan 안 섹션)', () => {
  expect(STAGE_KEYS).toEqual(['intent', 'plan', 'sandbox', 'validate', 'accept'])
  for (const s of [null, 'DRAFT', 'SUBMITTED', 'IMPLEMENTING', 'TESTING', 'PENDING_ACCEPTANCE', 'MERGE_FAILED', 'ACCEPTED', 'DESTROYED']) {
    expect(stageTabs(s).map((r: Row) => r.key)).toEqual(STAGE_KEYS)
  }
})

// 상태별 표 — open/shut 은 본문을 그리는가, 뒤는 칩.
const TABLE: Record<string, Record<string, string>> = {
  '(선택 전)': { intent: 'open/locked', plan: 'shut/locked', sandbox: 'shut/locked', validate: 'shut/locked', accept: 'shut/locked' },
  DRAFT: { intent: 'open/active', plan: 'open/locked', sandbox: 'shut/locked', validate: 'shut/locked', accept: 'shut/locked' },
  SUBMITTED: { intent: 'open/done', plan: 'open/active', sandbox: 'open/locked', validate: 'shut/locked', accept: 'shut/locked' },
  IMPLEMENTING: { intent: 'open/done', plan: 'open/done', sandbox: 'open/active', validate: 'shut/locked', accept: 'shut/locked' },
  TESTING: { intent: 'open/done', plan: 'open/done', sandbox: 'open/done', validate: 'open/active', accept: 'open/locked' },
  PENDING_ACCEPTANCE: { intent: 'open/done', plan: 'open/done', sandbox: 'open/done', validate: 'open/done', accept: 'open/active' },
  MERGE_FAILED: { intent: 'open/done', plan: 'open/done', sandbox: 'open/done', validate: 'open/done', accept: 'open/active' },
  ACCEPTED: { intent: 'open/done', plan: 'open/done', sandbox: 'open/done', validate: 'open/done', accept: 'open/done' },
  DESTROYED: { intent: 'open/done', plan: 'open/done', sandbox: 'open/done', validate: 'open/done', accept: 'open/done' },
}

for (const [status, expected] of Object.entries(TABLE)) {
  test(`상태 ${status} — 열림/잠김과 칩`, () => {
    const s = status.startsWith('(') ? null : status
    expect(view(stageTabs(s))).toEqual(expected)
  })
}

test('예전 노출 규칙과 같다 — DRAFT 3탭(Intent·Plan·Impact→Plan), SUBMITTED·IMPLEMENTING +Sandbox, TESTING 이후 전부', () => {
  const openKeys = (s: string | null) => stageTabs(s).filter((r: Row) => r.open).map((r: Row) => r.key)
  expect(openKeys(null)).toEqual(['intent'])
  expect(openKeys('DRAFT')).toEqual(['intent', 'plan'])
  expect(openKeys('SUBMITTED')).toEqual(['intent', 'plan', 'sandbox'])
  expect(openKeys('IMPLEMENTING')).toEqual(['intent', 'plan', 'sandbox'])
  for (const s of ['TESTING', 'PENDING_ACCEPTANCE', 'MERGE_FAILED', 'ACCEPTED', 'DESTROYED']) {
    expect(openKeys(s)).toEqual(STAGE_KEYS)
  }
})

test('SUBMITTED 에서 확정 Plan 이 있으면 Sandbox 칩이 준비됨으로 오른다', () => {
  expect(view(stageTabs('SUBMITTED', { canImplement: true })).sandbox).toBe('open/ready')
  expect(view(stageTabs('SUBMITTED', { canImplement: false })).sandbox).toBe('open/locked')
  // 다른 상태엔 영향 없다
  expect(view(stageTabs('DRAFT', { canImplement: true })).sandbox).toBe('shut/locked')
})

test('모르는 상태는 숨기지 않는다(전부 열림) — 새 상태가 생겨도 화면이 비지 않게', () => {
  expect(stageTabs('SOMETHING_NEW').every((r: Row) => r.open)).toBe(true)
})

test('isStageOpen 은 표와 같다', () => {
  expect(isStageOpen('DRAFT', 'plan')).toBe(true)
  expect(isStageOpen('DRAFT', 'sandbox')).toBe(false)
  expect(isStageOpen('IMPLEMENTING', 'validate')).toBe(false)
  expect(isStageOpen('TESTING', 'accept')).toBe(true)
  expect(isStageOpen('TESTING', 'nope')).toBe(false)
})

test('예전 탭 키는 새 단계 키로 옮긴다', () => {
  expect(normalizeStageKey('diff')).toBe('intent')
  expect(normalizeStageKey('impact')).toBe('plan')
  expect(normalizeStageKey('tests')).toBe('validate')
  expect(normalizeStageKey('acceptance')).toBe('accept')
  expect(normalizeStageKey('sandbox')).toBe('sandbox')
  expect(normalizeStageKey(undefined)).toBe('intent')
  expect(normalizeStageKey('bogus')).toBe('intent')
})

test('목록 필터 — 상태 드롭다운 + 검색(id·제목·작성자, 대소문자 무시)', () => {
  const list = [
    { id: 'PRO-001', status: 'DRAFT', title: '주문 취소', author: 'kim' },
    { id: 'PRO-002', status: 'SUBMITTED', title: 'Refund Flow', author: 'lee' },
    { id: 'PRO-003', status: 'DRAFT', title: '배송 추적', author: 'Park' },
  ]
  const ids = (o: object) => filterProposals(list, o).map((p: { id: string }) => p.id)
  expect(ids({})).toEqual(['PRO-001', 'PRO-002', 'PRO-003'])
  expect(ids({ status: 'DRAFT' })).toEqual(['PRO-001', 'PRO-003'])
  expect(ids({ query: 'refund' })).toEqual(['PRO-002'])
  expect(ids({ query: ' 003 ' })).toEqual(['PRO-003'])
  expect(ids({ query: 'park' })).toEqual(['PRO-003'])
  expect(ids({ status: 'SUBMITTED', query: '취소' })).toEqual([])
})
