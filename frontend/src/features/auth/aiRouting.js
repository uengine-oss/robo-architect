/**
 * AI 호출 경로 표 — 어느 줄을 보이고 "어디로" 를 어떻게 부르나(AiRoutingSection.vue).
 *
 * 판에 없는 갈래는 감춘다(2026-11-18). 서버가 `shipped` 로 알려 주고, 서버가 모르는
 * Claude Code 는 화면 빌드(VITE_DISABLE_CLAUDE_TERMINAL)가 정한다.
 */

export const CLAUDE_PATH = 'claude-code-pty'

export const STATUS_LABEL = Object.freeze({
  routed: '게이트웨이',
  default: '직접',
  'config-only': '별도 설정',
  direct: '직접',
  unroutable: '못 옮김',
})

/** 이 판에 있는 갈래인가. */
export function isShippedPath(p, { claudeAvailable }) {
  if (!p) return false
  if (p.status === 'not-shipped') return false // 옛 백엔드
  if (p.shipped === false) return false
  if (p.id === CLAUDE_PATH) return !!claudeAvailable
  return true
}

export function visiblePaths(state, opts) {
  return ((state || {}).paths || []).filter((p) => isShippedPath(p, opts))
}

/** "어디로" — 사람이 읽는 말. 주소·환경변수는 「자세히」에 둔다. */
export function destinationLabel(p, gatewayName) {
  switch (p.status) {
    case 'routed': return gatewayName
    case 'default': return 'OpenAI'
    case 'config-only': return '분석기 설정을 따름'
    case 'direct': return p.target === 'anthropic' ? 'Anthropic' : (p.target || '—')
    case 'unroutable': return '게이트웨이로 못 보냄'
    default: return p.target || '—'
  }
}
