/**
 * Pinia store for the Figma document binding.
 *
 * Connect / replace happen from the Figma plugin (which posts file_key +
 * file_name directly to the backend), so the architect UI only reads
 * binding state and exposes disconnect. No REST API token involved.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from './api'

export const useFigmaBindingStore = defineStore('figmaBinding', () => {
  const binding = ref(null) // null when no active binding
  const isLoading = ref(false)
  const lastError = ref(null)
  const storyboards = ref([])

  // 020: Retroactive full-sync state machine.
  // state: 'idle' | 'running' | 'completed' | 'cancelled' | 'aborted' | 'lockBusy'
  const fullSync = ref({
    state: 'idle',
    runId: null,
    kind: null,
    actor: null,
    startedAt: null,
    progress: {
      storyboardsTotal: 0,
      storyboardsDone: 0,
      uisTotal: 0,
      uisDone: 0,
      currentTarget: null,
    },
    summary: null,
    abortedReason: null,
    abortedMessageKr: null,
    lockHolder: null,
  })
  let _fullSyncCloser = null  // unsubscribe fn from subscribeFullSyncStream

  // 020: Failure list (canonical per-project view, classifier-applied).
  const failures = ref({
    retryable: [],
    nonRetryable: [],
    inFlight: [],
    currentBindingFileKey: null,
    isLoading: false,
  })

  // 020: SyncRun summary rows for History tab.
  const syncRuns = ref({ rows: [], isLoading: false })

  const isActive = computed(
    () => !!binding.value && binding.value.status === 'active'
  )
  const status = computed(() => binding.value?.status || 'disconnected')
  const fileName = computed(() => binding.value?.figmaFileName || '')
  const fileKey = computed(() => binding.value?.figmaFileKey || '')

  // Backward-compat: 016 v1.2 surfaces (ingestion floating panel + Inspector
  // badge) read `syncFailedUis`. Derive from the canonical failures slice so
  // there's only one source of truth.
  const syncFailedUis = computed(() => {
    const list = [
      ...failures.value.retryable,
      ...failures.value.inFlight,
      ...failures.value.nonRetryable,
    ]
    return list.map((f) => ({
      uiId: f.uiId,
      name: f.displayName,
      errorKo: f.lastErrorKr,
      lastAttemptAt: f.lastAttemptAt,
    }))
  })

  async function loadBinding() {
    isLoading.value = true
    lastError.value = null
    try {
      binding.value = await api.getBinding()
    } catch (e) {
      lastError.value = e?.message || String(e)
    } finally {
      isLoading.value = false
    }
  }

  async function disconnect() {
    isLoading.value = true
    lastError.value = null
    try {
      await api.disconnect()
      binding.value = null
      storyboards.value = []
      return true
    } catch (e) {
      lastError.value = e?.message || String(e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function loadStoryboards() {
    if (!isActive.value) {
      storyboards.value = []
      return
    }
    try {
      storyboards.value = await api.listStoryboards()
    } catch (e) {
      // non-fatal — leave previous list in place
      lastError.value = e?.message || String(e)
    }
  }

  // ─── 020: Full-sync actions ─────────────────────────────────────────

  function _resetFullSync() {
    fullSync.value = {
      state: 'idle',
      runId: null,
      kind: null,
      actor: null,
      startedAt: null,
      progress: {
        storyboardsTotal: 0,
        storyboardsDone: 0,
        uisTotal: 0,
        uisDone: 0,
        currentTarget: null,
      },
      summary: null,
      abortedReason: null,
      abortedMessageKr: null,
      lockHolder: null,
    }
  }

  function _handleFullSyncEvent(name, payload) {
    if (name === 'run_started') {
      fullSync.value.state = fullSync.value.state === 'lockBusy' ? 'lockBusy' : 'running'
      fullSync.value.runId = payload.runId
      fullSync.value.kind = payload.kind || 'retroactive-sync'
      fullSync.value.actor = payload.actor || null
      fullSync.value.startedAt = payload.startedAt || null
      fullSync.value.progress.storyboardsTotal = payload.storyboardsTotal || 0
      fullSync.value.progress.uisTotal = payload.uisTotal || 0
    } else if (name === 'progress') {
      const p = fullSync.value.progress
      p.storyboardsTotal = payload.storyboardsTotal ?? p.storyboardsTotal
      p.storyboardsDone = payload.storyboardsDone ?? p.storyboardsDone
      p.uisTotal = payload.uisTotal ?? p.uisTotal
      p.uisDone = payload.uisDone ?? p.uisDone
      p.currentTarget = payload.currentTarget || null
    } else if (name === 'page_ok' || name === 'ui_pushed' || name === 'ui_generated') {
      // Already counted by progress events; nothing to do here for the
      // top-level state. Granular badges could subscribe to these later.
    } else if (name === 'ui_failed' || name === 'page_failed') {
      // Insert/update an entry into the failures list eagerly (server will
      // persist; this keeps the UI snappy).
      if (payload.uiId) {
        const existing = failures.value.retryable.find((r) => r.uiId === payload.uiId)
        if (existing) {
          existing.lastErrorKr = payload.lastErrorKr
        } else {
          failures.value.retryable.push({
            uiId: payload.uiId,
            displayName: payload.displayName,
            lastErrorKr: payload.lastErrorKr,
            lastAttemptAt: new Date().toISOString(),
            retryability: 'retryable',
            nonRetryableReason: null,
            bindingFileKey: fileKey.value || null,
          })
        }
      }
    } else if (name === 'run_completed') {
      fullSync.value.state = 'completed'
      fullSync.value.summary = payload.summary || {}
      // Refresh canonical failure list + sync-runs index for the History tab.
      loadFailures().catch(() => {})
      loadSyncRuns().catch(() => {})
    } else if (name === 'run_cancelled') {
      fullSync.value.state = 'cancelled'
      fullSync.value.summary = payload.summary || {}
      loadFailures().catch(() => {})
      loadSyncRuns().catch(() => {})
    } else if (name === 'run_aborted') {
      fullSync.value.state = 'aborted'
      fullSync.value.summary = payload.summary || {}
      fullSync.value.abortedReason = payload.reason || null
      fullSync.value.abortedMessageKr = payload.messageKr || null
      loadFailures().catch(() => {})
      loadSyncRuns().catch(() => {})
    }
  }

  function _attachFullSyncStream(runId) {
    if (_fullSyncCloser) {
      try { _fullSyncCloser() } catch { /* noop */ }
    }
    _fullSyncCloser = api.subscribeFullSyncStream(runId, {
      onEvent: _handleFullSyncEvent,
      onClose: () => { _fullSyncCloser = null },
      onError: () => { /* keep state; SSE will reconnect */ },
    })
  }

  async function startFullSync() {
    if (fullSync.value.state === 'running') return false
    _resetFullSync()
    try {
      const result = await api.startFullSync()
      if (!result) return false
      if (result.locked) {
        // Another collaborator is running — subscribe as observer.
        fullSync.value.state = 'lockBusy'
        fullSync.value.runId = result.currentRunId
        fullSync.value.lockHolder = result.currentRunHolder
        fullSync.value.abortedMessageKr = result.messageKr
        if (result.currentRunId) _attachFullSyncStream(result.currentRunId)
        return false
      }
      fullSync.value.state = 'running'
      fullSync.value.runId = result.runId
      fullSync.value.kind = result.kind
      fullSync.value.startedAt = result.startedAt
      _attachFullSyncStream(result.runId)
      return true
    } catch (e) {
      lastError.value = e?.message || String(e)
      fullSync.value.state = 'idle'
      return false
    }
  }

  async function cancelFullSync() {
    if (!fullSync.value.runId) return
    try {
      await api.cancelFullSync(fullSync.value.runId)
    } catch (e) {
      lastError.value = e?.message || String(e)
    }
  }

  async function loadFailures() {
    failures.value.isLoading = true
    try {
      const data = await api.listProjectFailures()
      failures.value.retryable = data.retryable || []
      failures.value.nonRetryable = data.nonRetryable || []
      failures.value.inFlight = data.inFlight || []
      failures.value.currentBindingFileKey = data.currentBindingFileKey || null
    } catch (e) {
      lastError.value = e?.message || String(e)
    } finally {
      failures.value.isLoading = false
    }
  }

  async function loadSyncRuns() {
    syncRuns.value.isLoading = true
    try {
      const data = await api.listSyncRuns(20, true)
      syncRuns.value.rows = data.runs || []
    } catch (e) {
      lastError.value = e?.message || String(e)
    } finally {
      syncRuns.value.isLoading = false
    }
  }

  async function retryUi(uiId) {
    if (!uiId) return false
    // Optimistic move: retryable → inFlight.
    const idx = failures.value.retryable.findIndex((r) => r.uiId === uiId)
    let row = null
    if (idx >= 0) {
      row = failures.value.retryable[idx]
      failures.value.retryable.splice(idx, 1)
      failures.value.inFlight.push({ ...row, retryability: 'in-flight' })
    }
    try {
      await api.retrySync([uiId])
    } finally {
      await loadFailures().catch(() => {})
    }
    return true
  }

  async function retryAll() {
    const ids = failures.value.retryable.map((r) => r.uiId)
    if (!ids.length) return
    try {
      await api.retrySync(ids)
    } finally {
      await loadFailures().catch(() => {})
      await loadSyncRuns().catch(() => {})
    }
  }

  return {
    // state
    binding,
    isLoading,
    lastError,
    storyboards,
    fullSync,
    failures,
    syncRuns,
    // computed
    isActive,
    status,
    fileName,
    fileKey,
    syncFailedUis,
    // actions
    loadBinding,
    disconnect,
    loadStoryboards,
    // 020 actions
    startFullSync,
    cancelFullSync,
    loadFailures,
    loadSyncRuns,
    retryUi,
    retryAll,
  }
})
