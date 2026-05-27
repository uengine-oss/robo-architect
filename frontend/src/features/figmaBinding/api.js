/**
 * REST + SSE client for /api/figma-binding/*.
 *
 * Connect / replace happen from the Figma plugin (which posts file_key +
 * file_name directly to the backend) — no API token, no localStorage
 * credential cache. The architect UI only reads binding state and exposes
 * disconnect.
 */

const BASE = '/api/figma-binding'

async function asJsonOr404(resp) {
  if (resp.status === 404) return null
  if (!resp.ok) {
    let detail = ''
    try {
      const data = await resp.json()
      detail = data?.detail || JSON.stringify(data)
    } catch {
      detail = await resp.text().catch(() => '')
    }
    const err = new Error(detail || `HTTP ${resp.status}`)
    err.status = resp.status
    throw err
  }
  return resp.json()
}

export async function getBinding() {
  const r = await fetch(BASE)
  return asJsonOr404(r)
}

export async function disconnect() {
  const r = await fetch(BASE, { method: 'DELETE' })
  if (!r.ok && r.status !== 204) {
    throw new Error(`HTTP ${r.status}`)
  }
}

export async function getHistory(limit = 50) {
  const r = await fetch(`${BASE}/history?limit=${encodeURIComponent(limit)}`)
  const data = await asJsonOr404(r)
  return data?.items || []
}

export async function listStoryboards() {
  const r = await fetch(`${BASE}/storyboards`)
  return (await asJsonOr404(r)) || []
}

// ─── 020: Retroactive full-sync ──────────────────────────────────────────

/**
 * Start a retroactive full-sync. Returns one of:
 *   { runId, kind, startedAt, streamUrl }                         on 202
 *   { locked: true, currentRunId, currentRunHolder, streamUrl }   on 409
 * Throws on 404/502.
 */
export async function startFullSync() {
  const r = await fetch(`${BASE}/full-sync`, { method: 'POST' })
  if (r.status === 409) {
    let body
    try { body = await r.json() } catch { body = {} }
    const detail = body?.detail || body || {}
    return {
      locked: true,
      currentRunId: detail.currentRunId,
      currentRunHolder: detail.currentRunHolder,
      messageKr: detail.messageKr || '다른 사용자가 동기화 중입니다',
      streamUrl: detail.streamUrl,
    }
  }
  return asJsonOr404(r)
}

export async function cancelFullSync(runId) {
  const r = await fetch(`${BASE}/full-sync/${encodeURIComponent(runId)}/cancel`, {
    method: 'POST',
  })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

/**
 * Subscribe to a full-sync's SSE progress stream. Returns a closer fn.
 * Each event is delivered as { name, payload } to onEvent.
 */
export function subscribeFullSyncStream(runId, { onEvent, onClose, onError } = {}) {
  const url = `${BASE}/full-sync/${encodeURIComponent(runId)}/stream`
  const es = new EventSource(url)
  const eventNames = [
    'run_started', 'progress', 'page_ok', 'page_failed',
    'ui_generated', 'ui_pushed', 'ui_failed',
    'run_completed', 'run_cancelled', 'run_aborted', 'error',
  ]
  for (const name of eventNames) {
    es.addEventListener(name, (ev) => {
      let payload = {}
      try { payload = JSON.parse(ev.data) } catch { /* keep empty */ }
      onEvent && onEvent(name, payload)
      if (name === 'run_completed' || name === 'run_cancelled' || name === 'run_aborted') {
        es.close()
        onClose && onClose(name, payload)
      }
    })
  }
  es.onerror = (ev) => {
    onError && onError(ev)
  }
  return () => { try { es.close() } catch { /* noop */ } }
}

export async function listSyncRuns(limit = 20, includePreviousBinding = true) {
  const url = `${BASE}/sync-runs?limit=${encodeURIComponent(limit)}&includePreviousBinding=${includePreviousBinding ? 'true' : 'false'}`
  const r = await fetch(url)
  return (await asJsonOr404(r)) || { currentBindingFileKey: null, runs: [] }
}

export async function listProjectFailures() {
  const r = await fetch(`${BASE}/failures`)
  return (await asJsonOr404(r)) || {
    currentBindingFileKey: null, retryable: [], nonRetryable: [], inFlight: [],
  }
}

// ─── 016 v1.2 retry-sync (extended in 020 with dedupe + classifier server-side) ──

/**
 * Trigger a retry of one or more failed UIs. uiIds=null/empty → retry all.
 * Returns the synchronous summary { sessionId, syncedCount, failedCount, events, summary }.
 */
export async function retrySync(uiIds = null) {
  const r = await fetch(`${BASE}/retry-sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ uiIds: uiIds && uiIds.length ? uiIds : null }),
  })
  return asJsonOr404(r)
}

// ─── 024: Bound-file component library ───────────────────────────────────

/**
 * Persist a plugin-pushed component scan. The Figma plugin walks
 * ``figma.root.findAll(COMPONENT|COMPONENT_SET)``, exports each node's
 * PNG with ``node.exportAsync({format:'PNG'})``, and posts the batch
 * here. ``components`` is the array of
 * ``{figmaNodeId, name, pageName, widthPx, heightPx, pngBase64}``.
 *
 * Exposed for completeness; in practice the plugin itself calls this
 * endpoint, not the architect UI.
 */
export async function scanComponents(components) {
  const r = await fetch(`${BASE}/components/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ components: components || [] }),
  })
  return asJsonOr404(r)
}

export async function listComponents() {
  const r = await fetch(`${BASE}/components`)
  return (await asJsonOr404(r)) || { components: [], componentCount: 0 }
}

export async function clearComponents() {
  const r = await fetch(`${BASE}/components`, { method: 'DELETE' })
  if (!r.ok && r.status !== 204) throw new Error(`HTTP ${r.status}`)
}

/**
 * Subscribe to the active (or most recent) component scan's progress stream.
 * Fires `onEvent(name, payload)` for `snapshot`, `progress`, `done`, `error`.
 * Returns a closer fn that tears down the EventSource.
 */
export function subscribeComponentsScanStream({ onEvent, onClose, onError } = {}) {
  const es = new EventSource(`${BASE}/components/scan/stream`)
  const handle = (name) => (ev) => {
    let payload = {}
    try { payload = JSON.parse(ev.data) } catch { /* keep empty */ }
    onEvent && onEvent(name, payload)
    if (name === 'done' || name === 'error') {
      es.close()
      onClose && onClose(name, payload)
    }
  }
  es.addEventListener('snapshot', handle('snapshot'))
  es.addEventListener('progress', handle('progress'))
  es.addEventListener('done', handle('done'))
  es.addEventListener('error', handle('error'))
  // Some browsers also fire es.onerror on network blips. We don't auto-close
  // there — the EventSource auto-reconnects and snapshot will resync state.
  es.onerror = (ev) => { onError && onError(ev) }
  return () => { try { es.close() } catch { /* noop */ } }
}

