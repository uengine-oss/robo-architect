// Fetch helpers for the Claude Code IDE workspace endpoints.
//
// Three exports:
//   fetchTree(root, path)                          → GET /api/claude-code/tree
//   fetchFile(root, path)                          → GET /api/claude-code/file
//   saveFile({ root, path, content, expectedMtimeNs }) → PUT /api/claude-code/file
//
// All non-2xx responses throw an Error whose `.status` and `.body` are
// inspectable so callers can branch on 409 (conflict) and 413 (too large).

// In Electron, window.location.hostname is 'app' (custom app:// protocol) — not a
// real network host. Resolve once per session using window.desktop.app.getRuntimeState()
// so every fetch goes to http://127.0.0.1:<dynamicPort> instead of http://app:8000.
let _apiBasePromise = null

async function apiBase() {
  if (!_apiBasePromise) {
    _apiBasePromise = (async () => {
      if (window.desktop) {
        try {
          const result = await window.desktop.app.getRuntimeState()
          if (result.ok && result.data.backendPort) {
            return `http://127.0.0.1:${result.data.backendPort}`
          }
        } catch {}
      }
      const host = import.meta.env.VITE_API_HOST || window.location.hostname
      const port = import.meta.env.VITE_API_PORT || '8000'
      return `http://${host}:${port}`
    })()
  }
  return _apiBasePromise
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
  const base = await apiBase()
  const url = new URL(`${base}/api/claude-code/tree`)
  url.searchParams.set('root', root)
  if (path) url.searchParams.set('path', path)
  const res = await fetch(url.toString())
  if (!res.ok) throw await parseError(res)
  return res.json()
}

export async function fetchFile(root, path) {
  const base = await apiBase()
  const url = new URL(`${base}/api/claude-code/file`)
  url.searchParams.set('root', root)
  url.searchParams.set('path', path)
  const res = await fetch(url.toString())
  if (!res.ok) throw await parseError(res)
  return res.json()
}

export async function saveFile({ root, path, content, expectedMtimeNs }) {
  const base = await apiBase()
  const res = await fetch(`${base}/api/claude-code/file`, {
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
  const base = await apiBase()
  const res = await fetch(`${base}/api/claude-code/file`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ root, path }),
  })
  if (!res.ok) throw await parseError(res)
  return res.json()
}

export async function moveEntry({ root, fromPath, toPath }) {
  const base = await apiBase()
  const res = await fetch(`${base}/api/claude-code/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ root, from_path: fromPath, to_path: toPath }),
  })
  if (!res.ok) throw await parseError(res)
  return res.json()
}

// Build the URL for the live filesystem-change SSE stream. Returned as a string
// so the caller can hand it straight to `new EventSource(url)`. Resolves the
// Electron backend port the same way every other workspace fetch does.
export async function fsEventsUrl(root) {
  const base = await apiBase()
  const url = new URL(`${base}/api/claude-code/fs-events`)
  url.searchParams.set('root', root)
  return url.toString()
}

// Explicitly terminate a backend PTY session (× close). A ws disconnect only
// DETACHES (keeps claude alive so a reload can re-attach), so closing a tab for
// good must call this. Best-effort — failures are non-fatal.
export async function closeTerminalSession(sessionId) {
  if (!sessionId) return
  try {
    const base = await apiBase()
    const url = new URL(`${base}/api/claude-code/terminal/session`)
    url.searchParams.set('session_id', sessionId)
    await fetch(url.toString(), { method: 'DELETE' })
  } catch {
    // ignore — session may already be gone / backend unreachable
  }
}

// Global (~/.claude/skills) install status — checked when the Code tab opens so
// the interactive claude cell can resolve the project's robo-* slash commands.
// The backend remembers a successful check for the rest of the server session.
export async function fetchGlobalSkillsStatus() {
  const base = await apiBase()
  const res = await fetch(`${base}/api/claude-code/global-skills/status`)
  if (!res.ok) throw await parseError(res)
  return res.json()
}

export async function installGlobalSkills() {
  const base = await apiBase()
  const res = await fetch(`${base}/api/claude-code/global-skills/install`, {
    method: 'POST',
  })
  if (!res.ok) throw await parseError(res)
  return res.json()
}

export { WorkspaceApiError }
