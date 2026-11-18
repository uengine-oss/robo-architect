/**
 * 명확화 레이더 (lite ⑯) — "모름"을 "맑음"으로 그리지 않는다.
 */
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import { flagCoverageMismatch, isScanned, radialScore, summarize } from '../../src/features/requirements/ui/clarityRadarModel.js'

const CATS = [
  'functional_scope', 'domain_data_model', 'interaction_flow', 'non_functional',
  'integration_dependencies', 'edge_cases', 'constraints_tradeoffs', 'terminology',
  'completion_signals', 'misc_placeholders',
]
const unscanned = (c: string) => ({ category: c, score: null, status: null, scanned: false, flaggedCount: 0, resolvedCount: 0 })

test('미스캔 축은 면적 0 — 1.0 으로 그리지 않는다', () => {
  const row = unscanned('terminology')
  expect(isScanned(row)).toBe(false)
  expect(radialScore(row)).toBe(0)
  // 옛 응답처럼 score 가 1.0 으로 와도 scanned=false 면 0
  expect(radialScore({ ...row, score: 1.0 })).toBe(0)
})

test('스캔된 축은 점수 그대로', () => {
  expect(radialScore({ category: 'x', score: 0.5, status: 'deferred', scanned: true })).toBe(0.5)
  // 옛 응답(scanned 없음): status 가 있으면 스캔된 것
  expect(isScanned({ category: 'x', score: 1, status: 'clear' })).toBe(true)
  expect(isScanned({ category: 'x', score: 1, status: null })).toBe(false)
})

test('한 번도 스캔 안 한 프로젝트는 "스캔 안 함" — 퍼센트 없음', () => {
  const s = summarize({ totalUserStories: 4, flaggedUserStories: 0, overallScore: null, scores: CATS.map(unscanned) })
  expect(s.state).toBe('unscanned')
  expect(s.pct).toBeNull()
})

test('total==0 은 "대상 요구사항 없음" — 퍼센트 숨김', () => {
  const s = summarize({ totalUserStories: 0, overallScore: null, scores: CATS.map(unscanned) })
  expect(s.state).toBe('empty')
  expect(s.pct).toBeNull()
})

test('일부만 스캔 — partial, 백엔드 overallScore 를 쓴다', () => {
  const rows = CATS.map(unscanned)
  rows[0] = { category: CATS[0], score: 1, status: 'clear', scanned: true, flaggedCount: 0, resolvedCount: 0 } as any
  const s = summarize({ totalUserStories: 2, overallScore: 0.1, scores: rows })
  expect(s.state).toBe('partial')
  expect(s.pct).toBe(10)
  expect(s.scannedCount).toBe(1)
})

test('옛 응답(overallScore 없음)은 미스캔을 0 으로 쳐서 평균', () => {
  const rows = CATS.map(unscanned)
  rows[0] = { category: CATS[0], score: 1, status: 'clear' } as any
  delete (rows[0] as any).scanned
  const s = summarize({ totalUserStories: 2, scores: rows })
  expect(s.pct).toBe(10)
})

test('flags 와 coverage 가 어긋나면 그 축을 돌려준다', () => {
  const rows = CATS.map((c) => ({ category: c, score: 1, status: 'clear', scanned: true, flaggedCount: 0, resolvedCount: 0 }))
  rows[3] = { ...rows[3], flaggedCount: 2 }
  expect(flagCoverageMismatch({ totalUserStories: 3, flaggedUserStories: 2, overallScore: 1, scores: rows })).toEqual(['non_functional'])
})

test('100% 인데 모호가 있으면 머리 경고(*)', () => {
  const rows = CATS.map((c) => ({ category: c, score: 1, status: 'clear', scanned: true, flaggedCount: 0, resolvedCount: 0 }))
  expect(flagCoverageMismatch({ totalUserStories: 3, flaggedUserStories: 3, overallScore: 1, scores: rows })).toEqual(['*'])
})

test('맞으면 경고 없음', () => {
  const rows = CATS.map((c) => ({ category: c, score: 1, status: 'clear', scanned: true, flaggedCount: 0, resolvedCount: 0 }))
  rows[3] = { ...rows[3], status: 'outstanding', score: 0, flaggedCount: 1 }
  expect(flagCoverageMismatch({ totalUserStories: 3, flaggedUserStories: 1, overallScore: 0.9, scores: rows })).toEqual([])
  expect(flagCoverageMismatch({ totalUserStories: 3, flaggedUserStories: 0, overallScore: null, scores: CATS.map(unscanned) })).toEqual([])
})
