/**
 * Debug mode toggle — gates manual editing UI (BL move/assign, ES role
 * dropdown, BC Rules Modal, unmapped pool editing) behind an opt-in flag.
 *
 * Design intent (docs/legacy-ingestion/개선&재구조화.md §2.D):
 *  - default (non-debug) UX shows Task Inspector with approve/reject only
 *    → minimises cognitive load for the end user
 *  - debug mode exposes everything the old Inspector had → QA/dev use
 *
 * Enable:
 *  - Append `?debug=1` to the URL (sticky — stored in localStorage)
 *  - Or run `window.__setDebug(true)` in the console
 * Disable:
 *  - `?debug=0` or `window.__setDebug(false)`
 */
import { computed, ref } from 'vue'

const LS_KEY = 'hybrid.debug_mode'

function readQueryFlag() {
  try {
    const qs = new URLSearchParams(window.location.search)
    const v = qs.get('debug')
    if (v === '1' || v === 'true') return true
    if (v === '0' || v === 'false') return false
  } catch { /* SSR-safe */ }
  return null
}

function readStored() {
  try { return localStorage.getItem(LS_KEY) === '1' } catch { return false }
}

function _initial() {
  const q = readQueryFlag()
  if (q === null) return readStored()
  // URL query overrides; also persist so it survives navigation.
  try { localStorage.setItem(LS_KEY, q ? '1' : '0') } catch {}
  return q
}

const _debug = ref(_initial())

// Expose a console affordance so devs can flip the flag without reloading.
if (typeof window !== 'undefined') {
  // @ts-ignore — deliberate global.
  window.__setDebug = (v) => {
    _debug.value = !!v
    try { localStorage.setItem(LS_KEY, v ? '1' : '0') } catch {}
  }
}

export function useDebugMode() {
  return {
    isDebug: computed(() => _debug.value),
    setDebug(v) {
      _debug.value = !!v
      try { localStorage.setItem(LS_KEY, v ? '1' : '0') } catch {}
    },
  }
}
