/**
 * REST + SSE client for /api/figma-binding/* (feature 016).
 *
 * Token storage continues to follow spec 009's pattern: the
 * `figma_api_creds` localStorage entry holds `{ token, fileKey }`.
 * We read it for connect/replace; we never write a separate token store.
 */

const BASE = '/api/figma-binding'

function getStoredFigmaCreds() {
  try {
    return JSON.parse(localStorage.getItem('figma_api_creds') || '{}')
  } catch {
    return {}
  }
}

function setStoredFigmaCreds(creds) {
  try {
    const prev = getStoredFigmaCreds()
    localStorage.setItem('figma_api_creds', JSON.stringify({ ...prev, ...creds }))
  } catch {
    // best-effort
  }
}

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

export async function connect(fileKey, apiToken) {
  const r = await fetch(`${BASE}/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ figmaFileKey: fileKey, apiToken }),
  })
  const data = await asJsonOr404(r)
  if (data) setStoredFigmaCreds({ fileKey, token: apiToken })
  return data
}

export async function disconnect() {
  const r = await fetch(BASE, { method: 'DELETE' })
  if (!r.ok && r.status !== 204) {
    throw new Error(`HTTP ${r.status}`)
  }
}

export async function replace(fileKey, apiToken) {
  const r = await fetch(`${BASE}/replace`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ figmaFileKey: fileKey, apiToken }),
  })
  const data = await asJsonOr404(r)
  if (data) setStoredFigmaCreds({ fileKey, token: apiToken })
  return data
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

export { getStoredFigmaCreds, setStoredFigmaCreds }
