# Contract: Launcher IPC Channels

**Surface**: extensions to the existing `window.desktop` bridge from feature 023. **No raw `ipcRenderer` / Node leak** (preserves 023 FR-021). Every `invoke` returns the existing `IpcResult<T> = {ok:true,data:T} | {ok:false,error:{code,message}}` envelope.

**Error codes** — extend the closed `IpcErrorCode` enum already defined in [desktop/src/shared/ipc-contract.ts](../../../desktop/src/shared/ipc-contract.ts) with:

```ts
// Added in 032
CONNECTION_DUPLICATE: "CONNECTION_DUPLICATE",         // tried to save with a label or uri already in use
CONNECTION_NOT_FOUND: "CONNECTION_NOT_FOUND",         // edit/delete referenced an unknown id
DISCOVERY_UNAVAILABLE: "DISCOVERY_UNAVAILABLE",       // Neo4j Desktop not installed or unreadable (returned as ok:true, []  — only used when caller specifically asks for verbose error)
PROJECT_ROOT_INVALID: "PROJECT_ROOT_INVALID",         // path doesn't exist
PROJECT_ROOT_UNREADABLE: "PROJECT_ROOT_UNREADABLE",   // exists but no read permission
GIT_UNAVAILABLE: "GIT_UNAVAILABLE",                   // git binary not on PATH (non-fatal — identity:resolve returns unknown-fallback instead)
LAUNCHER_ALREADY_ENTERED: "LAUNCHER_ALREADY_ENTERED", // launcher:enter called twice
```

The existing `NEO4J_*` codes from 023 are reused as-is for connection-test outcomes.

---

## Channel index

| Channel | Side effects | Existing in 023? |
|---|---|---|
| `connections:list` | read settings | new |
| `connections:save` | write settings + keychain | new |
| `connections:update` | write settings + keychain | new |
| `connections:delete` | write settings + clear keychain | new |
| `connections:discoverNeo4jDesktop` | read filesystem | new |
| `connections:probeStatus` | network probe | new |
| `connections:test` | network probe (no persist) | **alias of existing `settings:testNeo4jConnection`** |
| `projectRoot:choose` | OS folder dialog | new |
| `projectRoot:listRecent` | read settings | new |
| `projectRoot:validate` | filesystem stat | new |
| `identity:resolve` | spawn `git config` | new |
| `launcher:enter` | write settings + backend env swap | new |
| `launcher:reopen` | navigate renderer back to `/__launcher` (in-app Settings re-entry) | new |

---

## Per-channel signatures

### `connections:list`

Returns all `SavedConnection` entries from `settings.json`, ordered by `lastConnectedAt` descending (nulls last).

```ts
'connections:list': [void, SavedConnection[]]
```

### `connections:save`

Creates a new `SavedConnection`. Main process assigns the `id` (uuid v4) and `createdAt`. Optional `passwordPlaintext` field — when present, is written to OS keychain at `connection.<id>.password` and immediately scrubbed from the IPC payload before logging.

```ts
'connections:save': [
  {
    label: string;
    uri: string;
    user: string;
    database?: string;
    source: Exclude<ConnectionSource, 'bundled' | 'manual-migrated-from-023'>;
    passwordPlaintext?: string;
  },
  SavedConnection   // the persisted form (no password field)
]
```

**Errors**: `VALIDATION` (any field fails the rules in data-model §1), `CONNECTION_DUPLICATE` (same label OR same `(uri, user, database)` tuple as an existing entry).

### `connections:update`

Edit an existing entry. `id` is required and immutable. `passwordPlaintext: null` means "do not change"; `passwordPlaintext: ''` means "clear the stored password"; any non-empty string replaces it.

```ts
'connections:update': [
  {
    id: string;
    label?: string;
    uri?: string;
    user?: string;
    database?: string | null;     // null clears, undefined leaves
    passwordPlaintext?: string | null;
  },
  SavedConnection
]
```

**Errors**: `VALIDATION`, `CONNECTION_NOT_FOUND`, `CONNECTION_DUPLICATE`.

### `connections:delete`

Removes the entry and clears its keychain password.

```ts
'connections:delete': [{ id: string }, { ok: true }]
```

**Errors**: `CONNECTION_NOT_FOUND`.

**Side effect**: if `lastProfile.connectionId === id`, `lastProfile` is set to `null`.

### `connections:discoverNeo4jDesktop`

Reads Neo4j Desktop's filesystem config and returns the list of DBMSs. Always returns `ok: true` even when discovery fails — failure is represented as an empty array per FR-017. (Verbose error reporting is reserved for diagnostic UI; not used in the launcher proper.)

```ts
'connections:discoverNeo4jDesktop': [void, DiscoveredConnection[]]
```

**Errors**: none returned to the renderer — internally any of (`ENOENT`, `EACCES`, JSON parse fail, schema mismatch, timeout > 2 s) is logged as a single info line and returns `ok: true, data: []`.

### `connections:probeStatus`

Live reachability + auth probe for *one* saved connection. Uses the password from the OS keychain — no plaintext crosses the IPC boundary.

```ts
'connections:probeStatus': [
  { id: string },
  {
    state: 'connected' | 'unreachable' | 'auth-failed' | 'stopped' | 'timeout';
    serverVersion?: string;
    /** Short human-readable reason; never a stack trace. */
    detail?: string;
  }
]
```

**Errors**: `CONNECTION_NOT_FOUND` if id is unknown.

**Timing**: bounded ≤ 5 s (SC-005). On timeout, returns `state: 'timeout'`, not a `NEO4J_TIMEOUT` error envelope.

### `connections:test`

**Alias of the existing `settings:testNeo4jConnection`** from 023. Same payload, same response — the launcher uses it under a new name so the launcher contract is self-contained. Implementation just forwards.

```ts
'connections:test': [
  { uri: string; user: string; password: string; database: string },
  { ok: true; serverVersion?: string }
]
```

**Errors**: `NEO4J_UNREACHABLE`, `NEO4J_AUTH_FAILED`, `NEO4J_TIMEOUT`, `NEO4J_TLS_ERROR`, `VALIDATION`.

### `projectRoot:choose`

Opens the native OS folder dialog.

```ts
'projectRoot:choose': [
  void,
  { path: string; valid: boolean; basename: string; parent: string } | { cancelled: true }
]
```

**Errors**: none — cancel is `{ cancelled: true }`, not an error.

### `projectRoot:listRecent`

```ts
'projectRoot:listRecent': [void, ProjectRootEntry[]]   // max 5
```

### `projectRoot:validate`

Cheap stat-only validation; never opens any files.

```ts
'projectRoot:validate': [
  { path: string },
  { valid: boolean; reason?: 'not-found' | 'not-a-directory' | 'unreadable' }
]
```

**Errors**: `VALIDATION` for malformed path (not absolute, not a string). The semantic outcomes (`not-found`, `unreadable`) are `valid: false, reason: ...`, **not** error envelopes — they are normal UI states.

### `identity:resolve`

Resolves the git identity in the context of `cwd = projectRoot`, or in the parent dir of `process.execPath` when `projectRoot === null`.

```ts
'identity:resolve': [
  { projectRoot: string | null },
  SessionUser
]
```

**Errors**: none — git unavailability resolves to `source: 'unknown-fallback'`. The `GIT_UNAVAILABLE` code exists only for future diagnostic UI and is not returned by `identity:resolve` itself.

**Timing**: bounded ≤ 1 s (SC-009). Two parallel `git config --get` spawns (name + email) sharing a single 1 s deadline.

### `launcher:enter`

Hand-off. Transitions the renderer-side launcher state from `pending` to `entered`, persists the new `lastProfile`, updates `lastConnectedAt` and `recentProjectRoots`, and reconfigures the backend env (data source = chosen connection). The renderer follows up with `router.push('/')` after receiving `ok`.

```ts
'launcher:enter': [
  {
    connectionId: string;
    projectRoot: string;
    /** Snapshot of identity as the renderer sees it; main re-resolves and uses its own answer if they differ (e.g. project-local-git changed). */
    identity: SessionUser;
  },
  {
    /** Authoritative identity after main's re-resolution. */
    identity: SessionUser;
    /** Echoes the connection actually loaded into backend env (id might differ from request if main hit a race condition). */
    activeConnectionId: string;
  }
]
```

**Errors**:
- `VALIDATION` — connectionId not in savedConnections, projectRoot not absolute.
- `CONNECTION_NOT_FOUND` — savedConnection deleted between renderer read and enter call.
- `PROJECT_ROOT_INVALID` / `PROJECT_ROOT_UNREADABLE` — validation failed at enter time (race with filesystem changes).
- `LAUNCHER_ALREADY_ENTERED` — `launcher:enter` called twice without an intervening `launcher:reopen`.

**Side effects** (in order, all atomic from the renderer's perspective):
1. Probe connection one last time with keychain password; if `auth-failed` or `unreachable`, return the corresponding error envelope without persisting.
2. Update `connection.lastConnectedAt = now()` in savedConnections.
3. Push projectRoot to `recentProjectRoots` (dedupe, keep max 5).
4. Set `lastProfile = { connectionId, projectRoot, enteredAt: now() }`.
5. Write settings atomically.
6. Re-resolve `SessionUser` with `cwd = projectRoot` (project-local git config may now apply).
7. Inject the active connection's URI + user + password (from keychain) into the backend env via the existing 023 `backend.ts` swap path.
8. Resolve the IPC with the authoritative identity + activeConnectionId.

### `launcher:reopen`

Mid-session: re-show the launcher (e.g. from a Settings button). Transitions `entered` → `pending`. Does NOT clear settings — the user can cancel the modal and go back to where they were.

```ts
'launcher:reopen': [void, { ok: true }]
```

---

## Renderer-side surface (`window.desktop` extensions)

```ts
declare global {
  interface Window {
    desktop?: DesktopBridge & {
      connections: {
        list(): Promise<IpcResult<SavedConnection[]>>;
        save(input: ConnectionsSaveInput): Promise<IpcResult<SavedConnection>>;
        update(input: ConnectionsUpdateInput): Promise<IpcResult<SavedConnection>>;
        delete(input: { id: string }): Promise<IpcResult<{ ok: true }>>;
        discoverNeo4jDesktop(): Promise<IpcResult<DiscoveredConnection[]>>;
        probeStatus(input: { id: string }): Promise<IpcResult<ProbeStatusResult>>;
        test(input: TestNeo4jConnectionParams): Promise<IpcResult<TestNeo4jConnectionData>>;
      };
      projectRoot: {
        choose(): Promise<IpcResult<ProjectRootChooseResult>>;
        listRecent(): Promise<IpcResult<ProjectRootEntry[]>>;
        validate(input: { path: string }): Promise<IpcResult<ProjectRootValidateResult>>;
      };
      identity: {
        resolve(input: { projectRoot: string | null }): Promise<IpcResult<SessionUser>>;
      };
      launcher: {
        enter(input: LauncherEnterInput): Promise<IpcResult<LauncherEnterResult>>;
        reopen(): Promise<IpcResult<{ ok: true }>>;
      };
    };
  }
}
```

---

## Logging contract

Every channel above logs **one** JSONL line per call to the existing JSONL logger (`desktop/src/main/logging.ts`):

```jsonl
{"t":"2026-05-28T...","level":"info","channel":"connections:save","durationMs":12,"correlationId":"...","outcome":"ok","fields":{"id":"...","source":"manual"}}
{"t":"...","channel":"identity:resolve","outcome":"ok","fields":{"source":"global-git","name_len":8}}
{"t":"...","channel":"connections:test","outcome":"error","errorCode":"NEO4J_AUTH_FAILED","fields":{"uri_host":"localhost","uri_port":7687}}
```

**Never logged**: any password, any keychain value, any full file path inside the user's home dir beyond what's needed (paths are logged with `~/` substitution).
