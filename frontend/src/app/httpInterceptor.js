/**
 * Global window.fetch patch — frontend chokepoint for the per-request
 * generation language tag (feature 031).
 *
 * Why patch fetch globally instead of an axios interceptor or a shared
 * apiFetch() helper: the codebase calls window.fetch() directly from
 * ~50 feature-local *.api.js files and inline <script setup> blocks
 * (no axios dep, no shared client). Patching at the platform boundary
 * gives every existing and future caller the Accept-Language header
 * for free, with zero per-caller migration — the same single-chokepoint
 * property the backend's middleware provides at the request boundary.
 *
 * Install once at app bootstrap (main.js) AFTER Pinia is registered
 * AND the language store is initialised. Calling install() more than
 * once is a no-op (the patched fetch detects itself via a sentinel).
 */

import { useLanguageStore } from './language.store'

const PATCH_SENTINEL = Symbol.for('robo.languageFetchPatch.v1')

export function installLanguageFetchInterceptor() {
  if (typeof window === 'undefined') return // SSR / test environments
  const original = window.fetch
  if (!original) return
  if (original[PATCH_SENTINEL]) return // already installed

  const patched = function (input, init) {
    const store = useLanguageStore()
    const tag = store?.language

    if (!tag) {
      return original.call(this, input, init)
    }

    // Merge the header into whatever Headers shape the caller used.
    // A caller who explicitly set Accept-Language wins — we only fill the
    // gap, never overwrite.
    let nextInit = init
    if (input instanceof Request) {
      // For Request objects, we have to build a new Request because Headers
      // on a Request are immutable. Caller-set Accept-Language on the
      // Request itself still wins via `has()`.
      if (!input.headers.has('Accept-Language')) {
        const newHeaders = new Headers(input.headers)
        newHeaders.set('Accept-Language', tag)
        const newRequest = new Request(input, { headers: newHeaders })
        return original.call(this, newRequest, init)
      }
      return original.call(this, input, init)
    }

    const headers = new Headers((init && init.headers) || {})
    if (!headers.has('Accept-Language')) {
      headers.set('Accept-Language', tag)
      nextInit = { ...(init || {}), headers }
    }
    return original.call(this, input, nextInit)
  }

  patched[PATCH_SENTINEL] = true
  window.fetch = patched
}
