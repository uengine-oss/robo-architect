/** 상단 단계 탭 — 진행중 + 지난 단계(완료) 를 함께 센다 (lite ⑬, 사용자 2026-11-18) */
import { expect, test } from '@playwright/test'
import { countForStageTab, filterForStageTab, inStageTab, stagePhase } from '../../src/features/proposals/stageFilter.js'

const P = (id: string, status: string) => ({ id, status })
const ALL = [
  P('A', 'DRAFT'), P('B', 'SUBMITTED'), P('C', 'IMPLEMENTING'), P('D', 'TESTING'),
  P('E', 'PENDING_ACCEPTANCE'), P('F', 'MERGE_FAILED'), P('G', 'ACCEPTED'), P('H', 'DESTROYED'),
]
const ids = (tab: string) => filterForStageTab(ALL, tab).map((p: any) => p.id)

test('전체 = 모두(원래 순서)', () => {
  expect(ids('')).toEqual(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'])
})

test('각 단계 탭 = 그 단계 + 지난 것, 진행중이 먼저 — 완료(ACCEPTED)는 앞 탭에 남는다', () => {
  expect(ids('DRAFT')).toEqual(['A', 'B', 'C', 'D', 'E', 'F', 'G'])
  expect(ids('SUBMITTED')).toEqual(['B', 'C', 'D', 'E', 'F', 'G'])
  expect(ids('IMPLEMENTING')).toEqual(['C', 'D', 'E', 'F', 'G'])
  expect(ids('TESTING')).toEqual(['D', 'E', 'F', 'G'])
  expect(ids('PENDING_ACCEPTANCE')).toEqual(['E', 'F', 'G'])
  expect(ids('ACCEPTED')).toEqual(['G'])
})

test('폐기(DESTROYED)는 단계 탭에 없고 제 탭에서만', () => {
  for (const tab of ['DRAFT', 'SUBMITTED', 'IMPLEMENTING', 'TESTING', 'PENDING_ACCEPTANCE', 'ACCEPTED']) {
    expect(inStageTab(tab, 'DESTROYED')).toBe(false)
  }
  expect(ids('DESTROYED')).toEqual(['H'])
})

test('배지 = 진행중 + 지난 단계', () => {
  expect(countForStageTab(ALL, 'DRAFT')).toEqual({ total: 7, current: 1, passed: 6 })
  expect(countForStageTab(ALL, 'PENDING_ACCEPTANCE')).toEqual({ total: 3, current: 2, passed: 1 })
  expect(countForStageTab(ALL, 'ACCEPTED')).toEqual({ total: 1, current: 1, passed: 0 })
  expect(countForStageTab(ALL, 'DESTROYED')).toEqual({ total: 1, current: 1, passed: 0 })
})

test('진행중/지남 구분 — 진행중이 먼저 오도록 순서를 섞어도', () => {
  const mixed = [P('X', 'ACCEPTED'), P('Y', 'SUBMITTED'), P('Z', 'SUBMITTED')]
  expect(filterForStageTab(mixed, 'SUBMITTED').map((p: any) => p.id)).toEqual(['Y', 'Z', 'X'])
  expect(stagePhase('SUBMITTED', 'ACCEPTED')).toBe('passed')
  expect(stagePhase('SUBMITTED', 'SUBMITTED')).toBe('current')
  expect(stagePhase('SUBMITTED', 'DRAFT')).toBe(null)
  expect(stagePhase('', 'DRAFT')).toBe(null)
})
