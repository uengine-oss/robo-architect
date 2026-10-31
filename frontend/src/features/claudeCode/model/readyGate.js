// 터미널에 명령을 넣는 시점을 정하는 순수 로직 — 브라우저 · xterm · WebSocket 에 기대지 않는다.
// ClaudeCodeTerminal.vue 가 화면 읽기 · 소켓 전송을 함수로 넘겨 쓰고, 단위 시험은 가짜 시계로 돌린다
// (tests/claude-ready-gate-unit.spec.ts).

// Claude 가 처음 띄울 때 묻는 확인 화면(폴더 신뢰 · 권한 우회 동의 · 테마 · 안내). 떠 있는 동안
// 명령을 보내면 끝의 Enter 가 기본값(No, exit)을 골라 claude 가 꺼진다 → 사람이 답할 때까지 미룬다.
export const CLAUDE_DIALOG_RE = /Enter to confirm|trust this folder|one you trust|Yes, I accept|Bypass Permissions mode|Choose the text style|Press Enter to continue/i

// 확인 화면이 사라진 뒤 이만큼 다시 뜨지 않아야 보낸다(확인 하나에 답한 직후 다음 확인이 뜨는 틈).
export const DIALOG_CLEAR_MS = 2500
// 화면을 다시 살피는 간격.
export const POLL_MS = 500
// claude 기동 + 입력란 그리기에 드는 최소 시간.
export const DEFAULT_MIN_DELAY_MS = 6000

/**
 * 명령을 claude 입력란이 준비된 뒤에 한 번 보낸다 — 최소 minDelay 를 기다리고, 확인 화면이 없는 상태가
 * DIALOG_CLEAR_MS 이어질 때 cmd + '\r' 을 send 로 넘긴다. 살피는 때 소켓이 닫혀 있으면 그만둔다.
 *
 * @param {object} o
 * @param {string} o.cmd 보낼 명령(Enter 는 여기서 붙인다)
 * @param {number} [o.minDelay] 최소 대기(ms)
 * @param {() => string} o.getScreenText 터미널에 지금 보이는 글자
 * @param {() => boolean} o.isOpen 소켓이 열려 있는지
 * @param {(data: string) => void} o.send 입력 전송
 * @param {() => number} [o.now] 시계(기본 Date.now)
 * @param {(fn: () => void, ms: number) => unknown} [o.setTimer] 타이머(기본 setTimeout)
 */
export function sendWhenReady({
  cmd,
  minDelay = DEFAULT_MIN_DELAY_MS,
  getScreenText,
  isOpen,
  send,
  now = Date.now,
  setTimer = setTimeout,
}) {
  const start = now()
  let clearSince = null
  const tick = () => {
    if (!isOpen()) return
    if (CLAUDE_DIALOG_RE.test(getScreenText())) clearSince = null
    else if (clearSince === null) clearSince = now()
    if (now() - start >= minDelay && clearSince !== null && now() - clearSince >= DIALOG_CLEAR_MS) {
      send(cmd + '\r')
      return
    }
    setTimer(tick, POLL_MS)
  }
  tick()
}
