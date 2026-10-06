/**
 * 데스크톱 → 백엔드 요청 헤더 인터셉터 (spec 032 T019 + Neo4j override).
 *
 * `window.fetch` 를 1회 몽키패치해 **동일 출처** 요청에 실어 보낸다:
 *   1. 신원 — `X-User-Name`(UTF-8 percent-encoded) / `X-User-Email` (런처 세션 스토어)
 *   2. Neo4j 연결 — `X-Neo4j-*` (런처에서 고른 활성 연결, 키체인 비번 포함)
 *   3. 세션 — `Authorization: Bearer` 와 `X-Project-Graph`
 *
 * 3번을 여기 두는 이유는 호출부가 수백 곳이기 때문이다. 로그인 상태를 각 화면이
 * 챙기게 하면 한 곳만 빠져도 그 경로가 조용히 인증 없이 나간다.
 *
 * 프론트 코드는 native `fetch` 를 그대로 쓴다 — 호출부(수백 곳) 수정 불필요.
 *
 * Neo4j 계약 (analyzer / catalog / data-fabric 과 동일):
 *   헤더 있으면 백엔드가 그 연결을 쓰고, 없으면(브라우저/로컬 테스트) 백엔드 `.env` 폴백.
 *   비번은 **동일 출처(로컬 백엔드)** 요청에만 실린다 — 외부로 새지 않는다.
 *
 * Skips:
 *   - cross-origin requests (CORS preflight pain; backend identity is
 *     same-origin only in this product)
 *   - calls made before the launcher has populated the store (`user === null`)
 *   - calls where the source is `unknown-fallback` (renderer chose not
 *     to send identity; backend will use its own `unknown-header-missing`
 *     fallback)
 *
 * See `specs/032-desktop-startup-picker/contracts/identity-header-contract.md`.
 */

import { useSessionStore } from '@/features/desktop-launcher/stores/session-store.js'
import { useAuthStore } from '@/features/auth/auth.store.js'

let installed = false

// 런처 진입 후 해소되는 활성 Neo4j 연결 헤더. 브라우저 모드/미진입 상태에선 null →
// 헤더 없이 나가고 백엔드가 .env 로 폴백한다(계약).
let neo4jHeaders = null

/**
 * **"없다" 도 기억한다.**
 *
 * 값이 있을 때만 캐시하면, 없는 구성(번들·중앙 DB 처럼 override 가 null 인 구성)에서
 * **요청마다 IPC 를 한 번씩 더 보낸다** — 기동에 60~76회가 그렇게 나갔다(INFRA-1).
 * 그렇다고 영영 기억하면, 사람이 런처에서 연결을 새로 고른 뒤에도 헤더가 안 붙어
 * **조용히 .env 로 돌게 된다.** 그래서 없음만 짧게 기억한다.
 */
const NEGATIVE_TTL_MS = 30_000
let noHeadersUntil = 0

async function resolveNeo4jHeaders() {
  if (neo4jHeaders) return neo4jHeaders
  if (Date.now() < noHeadersUntil) return null
  try {
    const res = await window.desktop?.connections?.resolveActiveForBackend?.()
    const conn = res?.ok ? res.data : null
    if (!conn?.uri) {
      noHeadersUntil = Date.now() + NEGATIVE_TTL_MS
      return null
    }
    neo4jHeaders = {
      'X-Neo4j-Uri': conn.uri,
      'X-Neo4j-User': conn.user,
      'X-Neo4j-Password': conn.password,
      ...(conn.database ? { 'X-Neo4j-Database': conn.database } : {}),
    }
    return neo4jHeaders
  } catch {
    // bridge 부재(브라우저) — 조용한 실패가 아니라 계약상 정상 폴백.
    // 이쪽도 기억한다. 브라우저에서는 영영 없을 값이라 요청마다 물을 이유가 없다.
    noHeadersUntil = Date.now() + NEGATIVE_TTL_MS
    return null
  }
}

function isSameOrigin(url) {
  try {
    const u = new URL(url, window.location.origin)
    return u.origin === window.location.origin
  } catch {
    return true // relative URL or malformed → assume same origin
  }
}

/**
 * Returns the value of `input` as a fetchable URL string. `input` may be a
 * string, URL, or Request — `fetch`'s first-argument types.
 */
function urlOf(input) {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.toString()
  if (input && typeof input === 'object' && 'url' in input) return input.url
  return ''
}

export function installBackendHeaderInterceptor() {
  if (installed) return
  installed = true

  const original = window.fetch.bind(window)

  window.fetch = async (input, init) => {
    let nextInit = init

    try {
      const url = urlOf(input)
      if (isSameOrigin(url)) {
        const headers = new Headers((init && init.headers) || (input && input.headers) || undefined)
        let touched = false

        const user = useSessionStore().user
        if (user && user.source !== 'unknown-fallback') {
          headers.set('X-User-Name', encodeURIComponent(user.name))
          headers.set('X-User-Email', user.email)
          touched = true
        }

        // Electron 이 고른 Neo4j 연결 → 이 요청이 그 DB 를 쓰게 한다.
        const neo4j = await resolveNeo4jHeaders()
        if (neo4j) {
          for (const [key, value] of Object.entries(neo4j)) headers.set(key, value)
          touched = true
        }

        // 세션. 이미 Authorization 을 실은 요청은 건드리지 않는다 — 호출부가
        // 일부러 다른 자격을 쓰는 경우가 있을 수 있다.
        const auth = useAuthStore()
        if (auth.token && !headers.has('Authorization')) {
          headers.set('Authorization', `Bearer ${auth.token}`)
          touched = true
        }
        if (auth.projectGraph && !headers.has('X-Project-Graph')) {
          headers.set('X-Project-Graph', auth.projectGraph)
          touched = true
        }

        if (touched) nextInit = { ...(init || {}), headers }
      }
    } catch (err) {
      // Never let the interceptor break the request. If the store isn't
      // initialised yet (e.g. very early bootstrap fetches), fall through
      // with the original args.
      // eslint-disable-next-line no-console
      console.warn('[http] backend header interceptor skipped:', err && err.message)
    }

    const response = await original(input, nextInit)
    noteProjectError(response)
    noteGraphError(response)
    return response
  }
}

// 프로젝트 때문에 막힌 응답의 코드. 백엔드 `BindingDenied.code` 와 같은 값이다.
const PROJECT_CODES = new Set(['PROJECT_NOT_SELECTED', 'PROJECT_FORBIDDEN'])

// 그래프가 이 PC 의 설정 때문에 거절한 것. 백엔드 `graph_errors.py` 와 같은 값이다.
const GRAPH_FAULT_CODE = 'GRAPH_ROLE_AUTH_FAILED'

// 그래프를 실제로 읽는 길. 여기가 200 이면 설정은 멀쩡하다 — 그때만 안내를 지운다.
const GRAPH_PATHS = ['/api/graph', '/api/ingest', '/api/requirements', '/api/collab']

/**
 * 503 **하나만** 해석한다 — "이 PC 의 계정 비밀 값이 서버와 다르다".
 *
 * 이것을 화면마다 해석하게 두면 한 곳도 안 해석한다(지금까지 그랬다). 사람이 보는
 * 것은 "서버 오류" 이고, 정작 원인은 **이 PC 의 설치 설정**이라 서버를 아무리 봐도
 * 안 나온다. 403 을 한 곳에서 보는 것과 같은 이유로 여기 둔다.
 */
function noteGraphError(response) {
  if (!response) return
  try {
    if (!isSameOrigin(response.url || '')) return
  } catch {
    return
  }
  if (response.ok) {
    // 그래프를 읽는 길이 성공했으면 설정은 멀쩡하다.
    try {
      const path = new URL(response.url, window.location.origin).pathname
      if (GRAPH_PATHS.some((p) => path.startsWith(p))) useAuthStore().setGraphOk()
    } catch {
      /* 주소를 못 읽으면 아무 말도 하지 않는다 */
    }
    return
  }
  if (response.status !== 503) return
  response.clone().json().then((body) => {
    if (body && body.code === GRAPH_FAULT_CODE) {
      useAuthStore().setGraphError({ code: body.code, detail: body.detail || '' })
    }
  }).catch(() => {
    /* 본문이 JSON 이 아니면 우리 것이 아니다 */
  })
}

/**
 * 403 을 **한 곳에서** 해석한다.
 *
 * 스토어마다 따로 해석하게 두면 빠뜨린 곳이 생기고, 그 화면은 403 을 "서버 연결
 * 실패"로 옮긴다 — 백엔드가 멀쩡한데 죽었다고 말하는 것이라 사람이 엉뚱한 데를
 * 본다. 프로젝트가 하나도 없는 사용자에게 실제로 그렇게 나왔다.
 *
 * 본문은 복제해서 읽는다. 원본을 읽으면 호출부가 같은 응답을 다시 못 읽는다.
 */
function noteProjectError(response) {
  if (!response || response.status !== 403) return
  try {
    if (!isSameOrigin(response.url || '')) return
  } catch {
    return
  }
  response.clone().json().then((body) => {
    const code = body && body.code
    if (PROJECT_CODES.has(code)) useAuthStore().setProjectError(code)
  }).catch(() => {
    /* 본문이 JSON 이 아니면 우리 것이 아니다 — 아무 말도 하지 않는다 */
  })
}
