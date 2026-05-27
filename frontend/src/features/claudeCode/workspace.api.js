// Fetch helpers for the Claude Code IDE workspace endpoints.
//
// Three exports:
//   fetchTree(root, path)                          → GET /api/claude-code/tree
//   fetchFile(root, path)                          → GET /api/claude-code/file
//   saveFile({ root, path, content, expectedMtimeNs }) → PUT /api/claude-code/file
//
// All non-2xx responses throw an Error whose `.status` and `.body` are
// inspectable so callers can branch on 409 (conflict) and 413 (too large).

function apiBase() {
  const host = import.meta.env.VITE_API_HOST || window.location.hostname
  const port = import.meta.env.VITE_API_PORT || '8000'
  return `http://${host}:${port}`
}

class WorkspaceApiError extends Error {
  constructor(status, body, message) {
    super(message || `workspace api error: ${status}`)
    this.name = 'WorkspaceApiError'
    this.status = status
    this.body = body
  }
}

async function parseError(response) {
  let body = null
  try {
    body = await response.json()
  } catch {
    // Non-JSON body — keep null.
  }
  return new WorkspaceApiError(response.status, body, body?.detail || `HTTP ${response.status}`)
}

export async function fetchTree(root, path = '') {
  const url = new URL(`${apiBase()}/api/claude-code/tree`)
  url.searchParams.set('root', root)
  if (path) url.searchParams.set('path', path)
  const res = await fetch(url.toString())
  if (!res.ok) throw await parseError(res)
  return res.json()
}

export async function fetchFile(root, path) {
  const url = new URL(`${apiBase()}/api/claude-code/file`)
  url.searchParams.set('root', root)
  url.searchParams.set('path', path)
  const res = await fetch(url.toString())
  if (!res.ok) throw await parseError(res)
  return res.json()
}

export async function saveFile({ root, path, content, expectedMtimeNs }) {
  const res = await fetch(`${apiBase()}/api/claude-code/file`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      root,
      path,
      content,
      expected_mtime_ns: expectedMtimeNs ?? null,
    }),
  })
  if (!res.ok) throw await parseError(res)
  return res.json()
}

export async function deleteEntry({ root, path }) {
  const res = await fetch(`${apiBase()}/api/claude-code/file`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ root, path }),
  })
  if (!res.ok) throw await parseError(res)
  return res.json()
}

export async function moveEntry({ root, fromPath, toPath }) {
  const res = await fetch(`${apiBase()}/api/claude-code/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ root, from_path: fromPath, to_path: toPath }),
  })
  if (!res.ok) throw await parseError(res)
  return res.json()
}

export { WorkspaceApiError }
