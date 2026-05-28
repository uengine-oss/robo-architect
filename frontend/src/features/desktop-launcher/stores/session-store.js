/**
 * Session store (spec 032 T017).
 *
 * Holds the resolved `SessionUser` + chosen `(connection, projectRoot)` pair
 * for the duration of the renderer session. Populated by the launcher's
 * Enter hand-off. The HTTP interceptor (`@/app/http.js`) reads `user` on
 * every outgoing fetch to inject `X-User-Name` / `X-User-Email` headers.
 *
 * Not persisted — settings persistence (lastProfile, savedConnections) lives
 * on the main-process side and is replayed on each launch.
 *
 * Web mode: `window.desktop === undefined` → store stays at defaults
 * (entered: true so the App.vue gate doesn't block), but `user` stays null
 * so the interceptor skips header injection. Backend's
 * IdentityMiddleware falls back to `unknown-header-missing`.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const IS_DESKTOP = typeof window !== 'undefined' && !!window.desktop

export const useSessionStore = defineStore('session', () => {
  /** @type {import('vue').Ref<import('../../../../../desktop/src/shared/launcher-contract').SessionUser | null>} */
  const user = ref(null)
  const connectionId = ref(null)
  const projectRoot = ref(null)
  // In web mode the launcher never runs, so `entered` is true from the start.
  // In desktop mode it starts false and flips after launcher:enter succeeds.
  const entered = ref(!IS_DESKTOP)

  const isDesktop = computed(() => IS_DESKTOP)
  const hasIdentity = computed(() => user.value !== null && user.value.source !== 'unknown-fallback')

  /** Called by the launcher on `identity:resolve` ack to update the welcome banner. */
  function setIdentity(nextUser) {
    user.value = nextUser
  }

  /** Called by EnterAction after `launcher.enter()` returns ok. */
  function commitProfile({ identity, activeConnectionId, projectRoot: root }) {
    user.value = identity
    connectionId.value = activeConnectionId
    projectRoot.value = root
    entered.value = true
  }

  /** Called by `launcher.reopen()` flow (US5) to send the user back to launcher. */
  function reopenLauncher() {
    entered.value = false
  }

  function reset() {
    user.value = null
    connectionId.value = null
    projectRoot.value = null
    entered.value = !IS_DESKTOP
  }

  return {
    user,
    connectionId,
    projectRoot,
    entered,
    isDesktop,
    hasIdentity,
    setIdentity,
    commitProfile,
    reopenLauncher,
    reset,
  }
})
