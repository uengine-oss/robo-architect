/**
 * B-3 ⑪ — Intent 인수조건 "검증에 쓰임" 배지의 집계.
 */
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import { countIntentCriteria, summarizeStrategicResults } from '../../src/features/proposals/gwtUsage.js'

test('strategicDiff 의 인수조건 수를 센다(문자열 JSON 도)', () => {
  const sd = { userStories: [{ acceptanceCriteria: ['a', 'b'] }, { acceptanceCriteria: [] }, {}] }
  expect(countIntentCriteria(sd)).toBe(2)
  expect(countIntentCriteria(JSON.stringify(sd))).toBe(2)
  expect(countIntentCriteria(null)).toBe(0)
  expect(countIntentCriteria('{깨진')).toBe(0)
})

test('Intent 인수조건(strategic)으로 잰 항목만 집계한다', () => {
  const r = {
    proposalId: 'PRO-1',
    items: [
      { criterionSource: 'strategic', result: 'PASS' },
      { criterionSource: 'strategic', result: 'FAIL' },
      { criterionSource: 'strategic', result: 'SKIPPED' },
      { criterionSource: 'tactical', result: 'FAIL' },
      { category: 'structural', result: 'FAIL' },
    ],
  }
  expect(summarizeStrategicResults(r, 'PRO-1')).toEqual({ pass: 1, fail: 1, skip: 1 })
})

test('다른 Proposal 의 결과이거나 strategic 항목이 없으면 null', () => {
  expect(summarizeStrategicResults({ proposalId: 'PRO-2', items: [{ criterionSource: 'strategic', result: 'PASS' }] }, 'PRO-1')).toBeNull()
  expect(summarizeStrategicResults({ proposalId: 'PRO-1', items: [{ criterionSource: 'tactical', result: 'PASS' }] }, 'PRO-1')).toBeNull()
  expect(summarizeStrategicResults(null)).toBeNull()
})
