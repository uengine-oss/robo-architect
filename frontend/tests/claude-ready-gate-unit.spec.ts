// 코드 셀 명령 주입 시점(readyGate) 순수 로직 단위 검증 — 브라우저 · dev 서버 불필요.
// 회귀 대상: dd688595 — /robo-implement + Enter 가 폴더 신뢰 확인 화면(기본값 'No, exit')에 들어가
// claude 가 꺼지던 문제. 확인 화면이 2.5초 동안 없고 최소 대기가 지난 뒤에만, 한 번, '\r' 을 붙여 보낸다.
// 실행: npx playwright test -c playwright.unit.config.ts
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import { sendWhenReady, CLAUDE_DIALOG_RE, DIALOG_CLEAR_MS, POLL_MS } from '../src/features/claudeCode/model/readyGate.js'

// Claude Code 첫 실행 화면들(요지만) — 정규식이 실제 문구를 잡는지 본다.
const TRUST_SCREEN = [
  'Do you trust the files in this folder?',
  '',
  ' /tmp/proposal-sandbox',
  '',
  'Quick safety check: Is this a project you created or one you trust?',
  '❯ 1. Yes, I trust this folder',
  '  2. No, exit',
  '',
  'Enter to confirm · Esc to cancel',
].join('\n')
const BYPASS_SCREEN = [
  'WARNING: Claude Code running in Bypass Permissions mode',
  '',
  '❯ 1. No, exit',
  '  2. Yes, I accept',
].join('\n')
const THEME_SCREEN = 'Choose the text style that looks best with your terminal'
const NOTES_SCREEN = 'Security notes:\n  1. Claude can make mistakes\nPress Enter to continue…'
const READY_SCREEN = [
  '╭───────────────────────────────────────╮',
  '│ ✻ Welcome to Claude Code!             │',
  '╰───────────────────────────────────────╯',
  '',
  '> ',
  '  ? for shortcuts',
].join('\n')

// 가짜 시계 + 타이머 큐. advance(ms) 동안 때가 된 타이머를 시간 순서대로 돌린다.
function harness({ screen = READY_SCREEN, open = true, startAt = 1_000_000 } = {}) {
  const h = {
    t: startAt,
    screen,
    open,
    sent: [] as string[],
    timers: [] as { at: number; fn: () => void }[],
    sentAt: [] as number[],
    now: () => h.t,
    setTimer: (fn: () => void, ms: number) => { h.timers.push({ at: h.t + ms, fn }) },
    advance(ms: number) {
      const end = h.t + ms
      for (;;) {
        h.timers.sort((a, b) => a.at - b.at)
        const next = h.timers[0]
        if (!next || next.at > end) break
        h.timers.shift()
        h.t = next.at
        next.fn()
      }
      h.t = end
    },
    start(cmd = '/robo-implement CHG-009', minDelay = 6000) {
      sendWhenReady({
        cmd,
        minDelay,
        getScreenText: () => h.screen,
        isOpen: () => h.open,
        send: (data: string) => { h.sent.push(data); h.sentAt.push(h.t) },
        now: h.now,
        setTimer: h.setTimer,
      })
    },
  }
  return h
}

test.describe('CLAUDE_DIALOG_RE — 첫 실행 확인 화면 판별', () => {
  test('폴더 신뢰 · 권한 우회 · 테마 · 안내 화면을 잡는다', () => {
    for (const s of [TRUST_SCREEN, BYPASS_SCREEN, THEME_SCREEN, NOTES_SCREEN]) {
      expect(CLAUDE_DIALOG_RE.test(s), s.slice(0, 40)).toBe(true)
    }
  })

  test('평소 입력 화면은 잡지 않는다', () => {
    expect(CLAUDE_DIALOG_RE.test(READY_SCREEN)).toBe(false)
    expect(CLAUDE_DIALOG_RE.test('')).toBe(false)
  })
})

test.describe('sendWhenReady — 확인 화면이 답해질 때까지 명령을 보류', () => {
  test('확인 화면이 떠 있는 동안은 아무것도 보내지 않는다', () => {
    const h = harness({ screen: TRUST_SCREEN })
    h.start()
    h.advance(60_000)
    expect(h.sent).toEqual([])
    // 계속 살피고 있다(포기하지 않는다)
    expect(h.timers.length).toBe(1)
  })

  test('확인 화면이 사라진 지 2.5초가 안 됐으면 보내지 않는다', () => {
    const h = harness({ screen: TRUST_SCREEN })
    h.start()
    h.advance(10_000) // 최소 대기(6초)는 이미 지남
    h.screen = READY_SCREEN // 사용자가 신뢰에 답함
    h.advance(DIALOG_CLEAR_MS - POLL_MS) // 2.0초
    expect(h.sent).toEqual([])
  })

  test('신뢰에 답한 직후 1초 안에 권한 우회 확인이 뜨면 여전히 보내지 않는다', () => {
    const h = harness({ screen: TRUST_SCREEN })
    h.start()
    h.advance(10_000)
    h.screen = READY_SCREEN // 신뢰 답함
    h.advance(1_000)
    h.screen = BYPASS_SCREEN // 곧바로 다음 확인
    h.advance(5_000) // 신뢰 답한 뒤 6초 — 첫 '맑음' 기준이면 이미 보냈을 시점
    expect(h.sent).toEqual([])

    const answeredAt = h.t
    h.screen = READY_SCREEN // 권한 우회도 답함
    h.advance(10_000)
    expect(h.sent).toEqual(['/robo-implement CHG-009\r'])
    // 두 번째 확인이 사라진 때부터 다시 2.5초를 센다
    expect(h.sentAt[0] - answeredAt).toBeGreaterThanOrEqual(DIALOG_CLEAR_MS)
  })

  test('2.5초 이상 맑고 최소 대기가 지나면 \\r 을 붙여 정확히 한 번 보낸다', () => {
    const h = harness({ screen: READY_SCREEN })
    const t0 = h.t
    h.start('/robo-implement CHG-009', 6000)
    h.advance(5_500)
    expect(h.sent).toEqual([]) // 맑지만 최소 대기 전
    h.advance(1_000)
    expect(h.sent).toEqual(['/robo-implement CHG-009\r'])
    expect(h.sentAt[0] - t0).toBeGreaterThanOrEqual(6000)
    // 보낸 뒤 더 살피지 않는다 → 다시 보내는 일 없음
    expect(h.timers.length).toBe(0)
    h.advance(60_000)
    expect(h.sent.length).toBe(1)
  })

  test('minDelay 가 0 이어도 맑은 상태 2.5초는 지켜야 보낸다(기존 셀에 명령 주입)', () => {
    const h = harness({ screen: READY_SCREEN })
    const t0 = h.t
    h.start('/robo-implement CHG-010', 0)
    expect(h.sent).toEqual([])
    h.advance(DIALOG_CLEAR_MS)
    expect(h.sent).toEqual(['/robo-implement CHG-010\r'])
    expect(h.sentAt[0] - t0).toBe(DIALOG_CLEAR_MS)
  })

  test('소켓이 닫혀 있으면 보내지 않고 더 살피지도 않는다', () => {
    const h = harness({ screen: READY_SCREEN, open: false })
    h.start()
    h.advance(60_000)
    expect(h.sent).toEqual([])
    expect(h.timers.length).toBe(0)
  })

  test('기다리는 도중 소켓이 닫히면 보내지 않는다', () => {
    const h = harness({ screen: TRUST_SCREEN })
    h.start()
    h.advance(8_000)
    h.open = false
    h.screen = READY_SCREEN
    h.advance(60_000)
    expect(h.sent).toEqual([])
    expect(h.timers.length).toBe(0)
  })

  test('시계가 0 에서 시작해도 맑음 시작 시각을 놓치지 않는다', () => {
    const h = harness({ screen: READY_SCREEN, startAt: 0 })
    h.start('/x', 0)
    h.advance(DIALOG_CLEAR_MS)
    expect(h.sent).toEqual(['/x\r'])
  })
})
