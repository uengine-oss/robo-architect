/**
 * 실행 상태를 **사람에게 할 말**로 옮긴다 (spec 058 US1 · T031 · SC-002).
 *
 * ## 왜 .vue 밖에 있나
 *
 * T031 이 요구하는 것은 "서비스를 하나씩 죽여 **모든 경우에** 이름·기능·복구 방법이
 * 나오는지(누락 0건)" 다. 그런데 그 판정이 템플릿 안에 흩어져 있으면 **걸 자리가
 * 없다** — 검사를 쓰려면 앱을 띄우고 서비스를 하나씩 죽여야 하고, 그건 10번을
 * 돌려야 한 바퀴다.
 *
 * 그래서 판정만 여기로 뺀다. 화면은 이것을 **그대로 그린다**. 이 모듈이 비어 있는
 * 답을 주면 화면도 비어 있다 — 그 사실을 검사가 대신 본다.
 *
 * ## 세 가지가 **항상** 있어야 한다 (SC-002)
 *
 * ```
 * 이름   무엇이 문제인가 — 서비스 이름(그리고 id)
 * 기능   그래서 **내가 무엇을 못 하는가** — 기능 이름으로 옮긴다
 * 할 일  그래서 **무엇을 하면 되는가** — 다시 시도 · 로그 보기 · 기다리기
 * ```
 *
 * 하나라도 비면 사용자는 "앱이 안 된다" 로 돌아간다. 그게 058 이 없애려던 그 한
 * 문장이다.
 */

/** 상태를 사람 말로. **모르는 상태는 그대로 보여준다** — 삼키면 디버깅이 막힌다. */
export const STATE_TEXT = {
  ready: '준비됨',
  starting: '준비 중',
  degraded: '일부만 됨',
  failed: '실패',
  stopped: '내려감',
  pending: '확인 전',
}

/** 사람이 **먼저 봐야 할 것**이 먼저 와야 한다. */
const ORDER = { failed: 0, stopped: 1, degraded: 2, starting: 3, pending: 4, ready: 5 }

/** 손댈 수 있는 상태인가 — 다시 시도 버튼을 띄울 자리. */
const RETRYABLE = new Set(['failed', 'stopped', 'degraded'])

/** 문제로 볼 상태인가. `starting`·`pending` 은 **아직 모르는 것**이라 문제가 아니다. */
const BROKEN = new Set(['failed', 'stopped'])

export const stateText = (state) => STATE_TEXT[state] || state

/**
 * 이름은 **메인이 준다**(`runtime-state.DISPLAY_NAMES`). 여기 또 적으면 같은 사실이
 * 두 곳에 생기고, 한쪽만 고친 날 화면과 로그가 다른 이름을 말한다.
 */
export const serviceLabel = (service) => service?.displayName || service?.id || '(이름 없음)'

export function sortedServices(services) {
  return [...(services || [])].sort(
    (a, b) =>
      (ORDER[a.state] ?? 9) - (ORDER[b.state] ?? 9) ||
      serviceLabel(a).localeCompare(serviceLabel(b)),
  )
}

/** 그 행에서 사람이 할 수 있는 것. **막다른 행을 만들지 않는다.** */
export function rowActions(service) {
  const actions = []
  if (RETRYABLE.has(service?.state)) actions.push('retry')
  actions.push('logs', 'folder') // 로그는 어느 상태에서도 읽을 수 있어야 한다
  return actions
}

/** 조사를 **받침으로** 고른다 — `을(를)` 은 읽는 사람에게 기계가 쓴 문장으로 보인다. */
function hasFinalConsonant(word) {
  const last = (word || '').trim().slice(-1)
  if (!last) return null
  const code = last.charCodeAt(0)
  if (code < 0xac00 || code > 0xd7a3) return null // 영문·숫자 끝 — 가릴 수 없다
  return (code - 0xac00) % 28 !== 0
}
export const withObject = (word) => `${word}${hasFinalConsonant(word) === false ? '를' : '을'}`
export const withSubject = (word) => `${word}${hasFinalConsonant(word) === false ? '가' : '이'}`

/**
 * 지금 화면이 **무엇을 말해야 하는가**.
 *
 * 돌려주는 것이 곧 화면의 내용이다 — `names`(이름) · `blocked`(기능) ·
 * `actions`(할 일) · `headline`(한 줄). 문제가 없으면 `noticed: false` 이고 그때는
 * **아무것도 띄우지 않는다**(늘 떠 있는 초록 띠는 며칠이면 안 보이게 된다).
 */
export function screenTells(state) {
  const services = state?.services || []
  const capabilities = state?.capabilities || []
  const dockerAvailable = state?.dockerAvailable ?? null
  const guard = state?.graphGuard || null

  const broken = services.filter((s) => BROKEN.has(s.state))
  const degraded = services.filter((s) => s.state === 'degraded')
  const stuck = [...broken, ...degraded]
  const blocked = capabilities.filter((c) => c.state !== 'available')
  const guardLocked = guard ? guard.separated === false : false

  // **도커가 없으면 그것부터다.** 서비스 열 개가 전부 실패로 보이지만 원인은 하나다.
  if (dockerAvailable === false) {
    return {
      noticed: true,
      tone: 'bad',
      cause: 'docker',
      names: ['컨테이너 실행 환경(Docker)'],
      blocked: blocked.map((c) => c.displayName || c.id),
      actions: ['docker-start', 'wait'],
      headline:
        'Docker Desktop 이 꺼져 있어 서비스를 띄울 수 없습니다 — 실행하면 앱이 스스로 이어서 올립니다.',
    }
  }

  if (stuck.length === 0 && !guardLocked) {
    return { noticed: false, tone: 'ok', cause: null, names: [], blocked: [], actions: [], headline: '' }
  }

  const names = stuck.map(serviceLabel)
  const who = names.join(' · ')
  const blockedNames = blocked.map((c) => c.displayName || c.id)
  const headline = blockedNames.length
    ? `지금 ${withObject(blockedNames.join(' · '))} 쓸 수 없습니다 — ${withSubject(who || '일부 서비스')} 준비되지 않았습니다.`
    : `${withSubject(who || '일부 서비스')} 준비되지 않았습니다 — 쓰는 기능에 따라 영향이 없을 수도 있습니다.`

  return {
    noticed: true,
    tone: broken.length > 0 ? 'bad' : 'warn',
    cause: guardLocked && stuck.length === 0 ? 'graph-guard' : 'service',
    names: guardLocked ? [...names, '설계·분석 저장소 분리'] : names,
    blocked: blockedNames,
    actions: stuck.some((s) => RETRYABLE.has(s.state)) ? ['retry', 'logs'] : ['logs', 'wait'],
    headline: guardLocked && stuck.length === 0
      ? '설계와 분석이 같은 저장소를 가리켜 레거시 코드 탐색을 잠갔습니다.'
      : headline,
  }
}

/**
 * **빠진 것을 센다** (SC-002 누락 0건).
 *
 * 문제가 있다고 말하면서 이름·기능·할 일 중 하나라도 비어 있으면 그 사실을 돌려준다.
 * 검사는 이 배열이 **비어 있는지**만 본다 — 그래야 서비스나 상태가 늘어도 자동으로
 * 걸린다("모든 경우에" 를 사람이 다시 세지 않는다).
 */
export function missingTells(state) {
  const told = screenTells(state)
  if (!told.noticed) return []
  const missing = []
  if (told.names.length === 0) missing.push('이름')
  if (!told.headline) missing.push('한 줄 설명')
  if (told.actions.length === 0) missing.push('할 일')
  // 기능이 비는 것은 **정상일 수 있다** — 그 서비스가 막는 기능이 없으면 그렇다.
  // 그래서 "기능" 은 누락으로 세지 않고, 대신 한 줄 설명이 그 사실을 말해야 한다.
  if (told.blocked.length === 0 && !/영향이 없을 수도|스스로 이어서|잠갔습니다/.test(told.headline)) {
    missing.push('기능 영향 설명')
  }
  return missing
}

/**
 * 긴 덩이는 **머리만** 보여준다.
 *
 * 2026-10-08 실측 — 스택을 붙여 주자 고른 줄 하나가 **40줄**이 됐다. 그걸 그대로
 * 그리면 패널이 로그 벽이 되고, **원인이 그 벽에 묻힌다.** 원인은 첫 줄에 있다
 * (`NoResourceFoundException: No static resource …`) — 스택은 "전문" 에서 본다.
 */
export const HEAD_LINES = 3

export function headOf(row, limit = HEAD_LINES) {
  const lines = String(row ?? '').split('\n')
  if (lines.length <= limit) return row
  const rest = lines.length - limit
  return [...lines.slice(0, limit), `    … 그리고 ${rest}줄 더 (전문에서 봅니다)`].join('\n')
}
