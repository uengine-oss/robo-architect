// D-2 ⑭ ② 「고치고 다시 검증」 루프 — 검증 FAIL·SKIP 한 항목을 통과할 때까지(상한 N회) 돌린다.
//
//   셀 주입(그 항목만 고쳐라 / 고친 뒤 커밋) → 커밋 감지(샌드박스 HEAD 가 바뀜) →
//   그 항목만 부분 재검증 → PASS 면 끝, 아니면 **새 사유로** 다시 주입.
//
// ⚠ 상한과 중단은 필수다 — LLM 이 같은 자리에서 계속 실패하면 사람이 끊어야 한다.
// ⚠ "코드를 설계에 맞춘다" 가 전제다. 설계가 틀린 경우는 이 루프로 못 고친다(Plan 재실행이 따로다).
//
// 화면과 떨어진 순수 로직이다 — 의존(주입·HEAD 조회·재검증·대기)은 모두 인자로 받는다.
// 그래서 단위 시험이 실제 셀·서버 없이 돈다.

export const DEFAULT_MAX_ATTEMPTS = 3
export const DEFAULT_POLL_MS = 3000
// 커밋을 이만큼 기다려도 안 오면 그 회차를 접는다(셀이 멈췄거나 커밋을 안 했다).
export const DEFAULT_COMMIT_TIMEOUT_MS = 15 * 60 * 1000

export class FixLoopStopped extends Error {
  constructor() { super('stopped'); this.name = 'FixLoopStopped' }
}

const isPass = (r) => String(r || '').toUpperCase() === 'PASS'

/**
 * @param {object} o
 * @param {object} o.item                  시작 항목(scenarioId·result·reason …)
 * @param {(item, round) => void|Promise} o.inject   셀에 고치라는 명령을 넣는다
 * @param {() => Promise<string|null>} o.getHead    샌드박스 HEAD
 * @param {(scenarioId) => Promise<object|null>} o.revalidate  그 항목만 재검증 → 갱신된 항목
 * @param {() => boolean} o.isStopped      중단 단추가 눌렸나
 * @param {(ms) => Promise} [o.sleep]
 * @param {(state) => void} [o.onState]    { phase, round, max, item, error? }
 * @param {number} [o.maxAttempts]
 * @param {number} [o.pollMs]
 * @param {number} [o.commitTimeoutMs]
 * @param {() => number} [o.now]
 * @returns {Promise<{ outcome: 'passed'|'exhausted'|'stopped'|'no-commit'|'error', rounds: number, item, error? }>}
 */
export async function runFixLoop(o) {
  const max = Math.max(1, Number(o.maxAttempts) || DEFAULT_MAX_ATTEMPTS)
  const pollMs = o.pollMs ?? DEFAULT_POLL_MS
  const commitTimeoutMs = o.commitTimeoutMs ?? DEFAULT_COMMIT_TIMEOUT_MS
  const sleep = o.sleep || ((ms) => new Promise((r) => setTimeout(r, ms)))
  const now = o.now || (() => Date.now())
  const emit = (s) => { try { o.onState?.(s) } catch { /* 화면 갱신 실패가 루프를 막지 않는다 */ } }
  const guard = () => { if (o.isStopped?.()) throw new FixLoopStopped() }

  let item = o.item
  let round = 0
  try {
    while (round < max) {
      guard()
      round += 1
      const baseHead = await o.getHead()
      guard()
      emit({ phase: 'injecting', round, max, item })
      await o.inject(item, round)

      // 커밋 감지 — HEAD 가 시작 값에서 바뀔 때까지 폴링.
      emit({ phase: 'waiting-commit', round, max, item })
      const started = now()
      let head = baseHead
      while (head === baseHead) {
        guard()
        if (now() - started > commitTimeoutMs) {
          emit({ phase: 'no-commit', round, max, item })
          return { outcome: 'no-commit', rounds: round, item }
        }
        await sleep(pollMs)
        guard()
        head = await o.getHead()
      }

      emit({ phase: 'revalidating', round, max, item })
      const updated = await o.revalidate(item.scenarioId)
      guard()
      if (updated) item = updated
      if (isPass(item.result)) {
        emit({ phase: 'passed', round, max, item })
        return { outcome: 'passed', rounds: round, item }
      }
    }
    emit({ phase: 'exhausted', round, max, item })
    return { outcome: 'exhausted', rounds: round, item }
  } catch (e) {
    if (e instanceof FixLoopStopped) {
      emit({ phase: 'stopped', round, max, item })
      return { outcome: 'stopped', rounds: round, item }
    }
    emit({ phase: 'error', round, max, item, error: e?.message || String(e) })
    return { outcome: 'error', rounds: round, item, error: e?.message || String(e) }
  }
}
