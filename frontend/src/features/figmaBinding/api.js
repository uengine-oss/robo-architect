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

export { getStoredFigmaCreds, setStoredFigmaCreds }
