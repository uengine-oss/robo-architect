/**
 * 데스크톱 → 백엔드 요청 헤더 인터셉터 (spec 032 T019 + Neo4j override).
 *
 * `window.fetch` 를 1회 몽키패치해 **동일 출처** 요청에 두 가지를 싣는다:
 *   1. 신원 — `X-User-Name`(UTF-8 percent-encoded) / `X-User-Email` (런처 세션 스토어)
 *   2. Neo4j 연결 — `X-Neo4j-*` (런처에서 고른 활성 연결, 키체인 비번 포함)
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

let installed = false

// 런처 진입 후 해소되는 활성 Neo4j 연결 헤더. 브라우저 모드/미진입 상태에선 null →
// 헤더 없이 나가고 백엔드가 .env 로 폴백한다(계약).
let neo4jHeaders = null

async function resolveNeo4jHeaders() {
  if (neo4jHeaders) return neo4jHeaders
  try {
    const res = await window.desktop?.connections?.resolveActiveForBackend?.()
    const conn = res?.ok ? res.data : null
    if (!conn?.uri) return null
    neo4jHeaders = {
      'X-Neo4j-Uri': conn.uri,
      'X-Neo4j-User': conn.user,
      'X-Neo4j-Password': conn.password,
      ...(conn.database ? { 'X-Neo4j-Database': conn.database } : {}),
    }
    return neo4jHeaders
  } catch {
    return null // bridge 부재(브라우저) — 조용한 실패가 아니라 계약상 정상 폴백
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

        if (touched) nextInit = { ...(init || {}), headers }
      }
    } catch (err) {
      // Never let the interceptor break the request. If the store isn't
      // initialised yet (e.g. very early bootstrap fetches), fall through
      // with the original args.
      // eslint-disable-next-line no-console
      console.warn('[http] backend header interceptor skipped:', err && err.message)
    }

    return original(input, nextInit)
  }
}
