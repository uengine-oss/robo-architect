/**
 * Identity-header HTTP interceptor (spec 032 T019).
 *
 * Monkey-patches `window.fetch` once to add `X-User-Name` (UTF-8
 * percent-encoded) and `X-User-Email` to every same-origin request,
 * sourced from the launcher's session store. Frontend code keeps using
 * native `fetch` — no per-call wrapping needed.
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

export function installIdentityInterceptor() {
  if (installed) return
  installed = true

  const original = window.fetch.bind(window)

  window.fetch = async (input, init) => {
    let nextInit = init

    try {
      const session = useSessionStore()
      const user = session.user
      const url = urlOf(input)
      if (user && user.source !== 'unknown-fallback' && isSameOrigin(url)) {
        const headers = new Headers((init && init.headers) || (input && input.headers) || undefined)
        headers.set('X-User-Name', encodeURIComponent(user.name))
        headers.set('X-User-Email', user.email)
        nextInit = { ...(init || {}), headers }
      }
    } catch (err) {
      // Never let the interceptor break the request. If the store isn't
      // initialised yet (e.g. very early bootstrap fetches), fall through
      // with the original args.
      // eslint-disable-next-line no-console
      console.warn('[http] identity interceptor skipped:', err && err.message)
    }

    return original(input, nextInit)
  }
}
