/**
 * D-2 ⑭ ② 「고치고 다시 검증」 루프 — 셀 주입 → 커밋 감지 → 그 항목만 재검증, 상한·중단.
 */
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import { runFixLoop, DEFAULT_MAX_ATTEMPTS } from '../../src/features/proposals/fixLoop.js'

const failing = { scenarioId: 'SC-002', result: 'FAIL', reason: '환불 API 없음' }

/** HEAD 를 흉내 낸다: commit() 을 부르면 다음 조회부터 새 값. */
function fakeRepo() {
  let n = 0
  return {
    commit() { n += 1 },
    head: async () => `sha-${n}`,
  }
}

test('기본 상한은 3회다', () => {
  expect(DEFAULT_MAX_ATTEMPTS).toBe(3)
})

test('커밋을 감지하면 그 항목만 재검증하고, 통과하면 멈춘다', async () => {
  const repo = fakeRepo()
  const injected: number[] = []
  const revalidated: string[] = []
  const phases: string[] = []
  const verdicts = ['FAIL', 'PASS']

  const res = await runFixLoop({
    item: failing,
    inject: (_item: unknown, round: number) => { injected.push(round); repo.commit() },
    getHead: repo.head,
    revalidate: async (id: string) => {
      revalidated.push(id)
      const result = verdicts.shift()
      return { ...failing, result, reason: result === 'PASS' ? null : '아직 없음' }
    },
    isStopped: () => false,
    sleep: async () => {},
    onState: (s: { phase: string }) => phases.push(s.phase),
  })

  expect(res.outcome).toBe('passed')
  expect(res.rounds).toBe(2)
  expect(injected).toEqual([1, 2])
  expect(revalidated).toEqual(['SC-002', 'SC-002'])
  expect(phases).toContain('waiting-commit')
  expect(phases.at(-1)).toBe('passed')
})

test('회차마다 최신 사유로 다시 주입한다', async () => {
  const repo = fakeRepo()
  const reasons: string[] = []
  await runFixLoop({
    item: failing,
    maxAttempts: 2,
    inject: (item: { reason: string }) => { reasons.push(item.reason); repo.commit() },
    getHead: repo.head,
    revalidate: async () => ({ ...failing, reason: '두 번째 사유' }),
    isStopped: () => false,
    sleep: async () => {},
  })
  expect(reasons).toEqual(['환불 API 없음', '두 번째 사유'])
})

test('상한에 닿으면 exhausted 로 끝난다', async () => {
  const repo = fakeRepo()
  let calls = 0
  const res = await runFixLoop({
    item: failing,
    inject: () => repo.commit(),
    getHead: repo.head,
    revalidate: async () => { calls += 1; return { ...failing } },
    isStopped: () => false,
    sleep: async () => {},
  })
  expect(res.outcome).toBe('exhausted')
  expect(res.rounds).toBe(3)
  expect(calls).toBe(3)
})

test('커밋을 기다리는 중에 중단하면 재검증하지 않는다', async () => {
  const repo = fakeRepo()
  let stopped = false
  let revalidated = 0
  let polls = 0
  const res = await runFixLoop({
    item: failing,
    inject: () => { /* 커밋 안 함 */ },
    getHead: repo.head,
    revalidate: async () => { revalidated += 1; return null },
    isStopped: () => stopped,
    sleep: async () => { polls += 1; if (polls === 2) stopped = true },
  })
  expect(res.outcome).toBe('stopped')
  expect(revalidated).toBe(0)
})

test('커밋이 끝내 안 오면 no-commit 으로 접는다', async () => {
  const repo = fakeRepo()
  let t = 0
  const res = await runFixLoop({
    item: failing,
    commitTimeoutMs: 1000,
    pollMs: 400,
    inject: () => {},
    getHead: repo.head,
    revalidate: async () => null,
    isStopped: () => false,
    sleep: async (ms: number) => { t += ms },
    now: () => t,
  })
  expect(res.outcome).toBe('no-commit')
  expect(res.rounds).toBe(1)
})

test('재검증이 던지면 error 로 끝나고 사유를 싣는다', async () => {
  const repo = fakeRepo()
  const res = await runFixLoop({
    item: failing,
    inject: () => repo.commit(),
    getHead: repo.head,
    revalidate: async () => { throw new Error('연결 끊김') },
    isStopped: () => false,
    sleep: async () => {},
  })
  expect(res.outcome).toBe('error')
  expect(res.error).toBe('연결 끊김')
})
