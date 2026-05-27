# Contract: Electron Main ↔ Renderer IPC

**Feature**: `023-electron-desktop-app` | **Date**: 2026-05-11

This is the **only** new external interface this feature adds (there are no new HTTP endpoints — the renderer talks to the bundled FastAPI exactly as the web app does today, at `http://127.0.0.1:<backendPort>`). The surface below is exposed to the renderer via `contextBridge` in `desktop/src/preload/index.ts` as `window.desktop`; the renderer **never** receives raw `ipcRenderer`, `require`, `process`, or any Node API (FR-021). The TypeScript mirror of these types lives in `desktop/src/shared/ipc-contract.ts` and is the single source of truth for both sides.

Conventions:
- **invoke/handle** (request→response, `ipcRenderer.invoke` ↔ `ipcMain.handle`) for queries and commands.
- **subscribe** (`on(channel, cb)` returning an unsubscribe fn) for main→renderer pushes.
- Every `invoke` resolves to `{ ok: true; data: T } | { ok: false; error: { code: string; message: string } }` — never throws across the bridge; the renderer always gets a typed result.
- All `code` values come from a closed enum (below) so the renderer can branch on them.

---

## Queries

### `app:getRuntimeState` → `RuntimeState`
Returns the current `RuntimeState` (see data-model.md): `appVersion`, `backendPort`, `boltPort`, `status`, `dataSource`, `dataDir`, `updateState`. The renderer calls this **before first API call** to learn `backendPort`. Always resolves (even mid-startup, with `status: "initializing"` and `backendPort: null`).

### `settings:get` → `DesktopSettings`
Returns the current non-secret settings. Never includes secret values; secret *presence* is reported as booleans under a `secretsPresent` map (e.g. `{ "llm.openai.apiKey": true, ... }`) so the UI can show "configured / not configured".

### `dataDir:get` → `{ path: string; writable: boolean; isDefault: boolean }`
The resolved data directory, whether it's writable, and whether it's the OS-default location (FR-009).

---

## Commands

### `settings:set(patch: Partial<DesktopSettingsWritable>) → DesktopSettings`
Applies a partial update and returns the new settings. Validation errors resolve `ok: false` with `code: "VALIDATION"`. Changing `dataSource` to `"external"` requires `externalNeo4j` to be present and to have passed `settings:testNeo4jConnection` in this session, else `code: "NEO4J_UNVERIFIED"`. On a successful change that affects the backend (data source, LLM provider/model), main restarts the backend child (renderer sees `status` cycle through `restarting → ready`) — the command resolves only once the new settings are persisted, not necessarily after the restart completes (restart progress comes via `app:onBackendStatus`).

### `settings:setSecret({ id: SecretId; value: string }) → { ok: true }`
Writes a secret to the OS secure store. `value` is never logged, never returned, never written to `settings.json`. Clearing a secret: pass `value: ""`. Unknown `id` → `code: "UNKNOWN_SECRET"`.

### `settings:testNeo4jConnection({ uri: string; user: string; password: string; database: string }) → { ok: true; serverVersion?: string }`
Main dials the endpoint (short timeout) and reports reachability/auth. Failure resolves `ok: false` with a typed `code`: `NEO4J_UNREACHABLE` | `NEO4J_AUTH_FAILED` | `NEO4J_TIMEOUT` | `NEO4J_TLS_ERROR` | `VALIDATION`. The password passed here is used only for the probe; it is **not** persisted by this call (use `settings:setSecret` to persist).

### `dataDir:choose() → { path: string; writable: boolean } | { cancelled: true }`
Opens the OS folder picker; if the user picks a writable directory, main persists it (FR-009 edge case) and restarts the backend pointed at the new location (status cycles). A non-writable pick resolves `ok: false`, `code: "DATA_DIR_NOT_WRITABLE"`.

### `backend:retry() → { ok: true }`
User-initiated recovery after a `backend-crashed` / `db-crashed` banner (FR-017). Main re-spawns the crashed child on a fresh free port; progress via `app:onBackendStatus`. No-op (still `ok: true`) if status is already `ready`.

### `logs:reveal() → { ok: true }`
Opens the data dir's `logs/` folder in the OS file manager (FR-016). Always `ok: true` (creates the folder if missing).

### `update:check() → { state: UpdateState; version?: string }`
Manually triggers an update check (the periodic auto-check uses the same path when `settings.update.autoCheck`). Resolves with the resulting `updateState`.

### `update:apply() → { ok: true }`
Tells the (already-downloaded, signature-verified) update to install on the next quit; main then prompts/quits-and-relaunches. `ok: false`, `code: "UPDATE_NOT_READY"` if no verified update is staged. Interrupted earlier downloads never reach this state (FR-015).

### `app:openExternal({ url: string }) → { ok: true }`
Opens an http(s) URL in the OS browser (used by the renderer for "open docs / release notes" links). Non-http(s) schemes → `ok: false`, `code: "BLOCKED_SCHEME"`. (External-link handling is also enforced by `setWindowOpenHandler` in main as defense-in-depth.)

---

## Subscriptions (main → renderer)

### `app:onBackendStatus(cb: (s: { status: RuntimeState["status"]; backendPort: number \| null; boltPort: number \| null; detail?: string }) => void) → unsubscribe`
Fires on every backend/Neo4j lifecycle transition: `initializing → starting-db → starting-backend → ready`, and on crash/restart (`backend-crashed`/`db-crashed` → `restarting` → `ready`), and on `fatal`. `detail` carries a short human-readable reason on crash/fatal (never a stack trace or secret). Drives the splash, the recoverable banner + Retry button, and the fatal error screen.

### `app:onUpdateState(cb: (s: { state: UpdateState; version?: string; progressPercent?: number }) => void) → unsubscribe`
Fires on update lifecycle: `idle → checking → available → downloading (with progressPercent) → ready-to-install`, or `→ error`. `available` and `ready-to-install` are non-blocking — the renderer shows a dismissible notification (FR-012/FR-013); declining/postponing does not repeat within the session and never blocks work.

### `app:onDataSourceChanged(cb: (s: { dataSource: "bundled" \| "external"; dataDir: string }) => void) → unsubscribe`
Fires when the effective data source or data dir changes (via Settings). The renderer uses this to (a) re-load the project list from the now-current backend, and (b) show the "you are now viewing a different dataset" warning (FR-011).

---

## Error code enum (closed set)

```
VALIDATION
NEOJ4_UNVERIFIED            // settings:set with external mode but no successful test this session
NEO4J_UNREACHABLE | NEO4J_AUTH_FAILED | NEO4J_TIMEOUT | NEO4J_TLS_ERROR
DATA_DIR_NOT_WRITABLE
UNKNOWN_SECRET
UPDATE_NOT_READY
BLOCKED_SCHEME
INTERNAL                    // catch-all; main has logged details, renderer shows "see logs"
```

## Non-goals for this contract

- No channel exposes a filesystem path the renderer can read/write arbitrarily, no `exec`/`spawn`, no env-var access — the renderer's only "system" reach is the enumerated commands above.
- No channel carries domain data (projects, aggregates, …) — that's all over HTTP to the bundled backend, unchanged.
- The 015 terminal's existing `WS /terminal` and `/browse-directory` / `/setup-project` HTTP endpoints are **unchanged** and are not part of this IPC surface; they continue to be served by the bundled backend and reached by the renderer over `http(s)`/`ws` to `127.0.0.1:<backendPort>` exactly as today.
