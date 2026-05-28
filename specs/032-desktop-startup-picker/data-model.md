# Phase 1 — Data Model

**Scope of this document.** 032 is Electron-side + frontend-side configuration data plus a thin backend `request.state` annotation. **No Neo4j schema change. No new Pydantic request/response models.** The shapes below are TypeScript types living in `desktop/src/shared/launcher-contract.ts` and consumed by both the Electron main process and the renderer SPA, plus one Python dataclass for the identity middleware.

---

## §1 — TypeScript shapes (`desktop/src/shared/launcher-contract.ts`)

### `SavedConnection`

A user-managed Neo4j endpoint persisted in `settings.json`. The password is **not** an attribute — it lives in OS secure storage at key `connection.<id>.password`.

```ts
export type ConnectionSource =
  | 'manual'                        // user-typed in the Add form
  | 'imported-from-neo4j-desktop'   // promoted from a DiscoveredConnection
  | 'bundled'                       // 023 bundled Neo4j (managed by Electron shell)
  | 'manual-migrated-from-023';     // produced by settings v1 → v2 migration

export interface SavedConnection {
  /** Stable id; uuid v4. Never reused after deletion. */
  id: string;
  /** User-chosen short label shown in the list. */
  label: string;
  /** Bolt URI, e.g. `bolt://localhost:7687` or `neo4j+s://example.com`. */
  uri: string;
  /** Neo4j username. */
  user: string;
  /** Optional default database for queries. Empty/undefined = use server default. */
  database?: string;
  /** Provenance — drives UI badging and a few behavioural branches. */
  source: ConnectionSource;
  /** ISO-8601 UTC. Updated by `launcher:enter` and successful `Test`. */
  lastConnectedAt: string | null;
  /** ISO-8601 UTC. Set at creation; never updated. */
  createdAt: string;
}
```

**Validation rules** (enforced in `connections.ts` before persisting):
- `id`: must match `/^[0-9a-f-]{36}$/`; main-process-assigned, renderer cannot set it on create (only on update).
- `label`: 1–60 chars, trimmed.
- `uri`: must start with one of `bolt://`, `bolt+s://`, `bolt+ssc://`, `neo4j://`, `neo4j+s://`, `neo4j+ssc://`. URI parser must accept it.
- `user`: 1–256 chars, no embedded newlines.
- `database`: when present, 1–63 chars, lowercase + digits + dashes only (Neo4j database name rules).
- `source`: must be a value from the enum above.
- `lastConnectedAt`, `createdAt`: must parse as ISO-8601.

### `DiscoveredConnection`

A **transient** view of a DBMS read from a local Neo4j Desktop install. Never persisted. Promoted to a `SavedConnection` only when the user successfully **Test**s it.

```ts
export type DiscoveredStatus = 'running' | 'stopped' | 'unknown';

export interface DiscoveredConnection {
  /** Stable per-scan id derived from the DBMS UUID — same across re-scans. */
  discoveryId: string;
  /** Human name from Neo4j Desktop. */
  dbmsName: string;
  /** Bolt URI assembled from `dbms.connector.bolt.listen_address` (or v5 equivalent). */
  uri: string;
  /** Neo4j version declared by Neo4j Desktop. */
  neo4jVersion: string;
  /** Best-effort run state from Neo4j Desktop's config; may be `unknown` if stale. */
  status: DiscoveredStatus;
  /** Project label from Neo4j Desktop, for grouping in the UI. */
  projectName: string | null;
}
```

**No persistence; no validation beyond shape conformance.**

### `ProjectRootEntry`

A recent project root that the user has selected at least once.

```ts
export interface ProjectRootEntry {
  /** Absolute filesystem path. */
  path: string;
  /** ISO-8601 UTC of last hand-off where this path was the chosen project root. */
  lastUsedAt: string;
}
```

The recent list lives in `settings.recentProjectRoots` as a bare `string[]` (paths) for compact storage; the `ProjectRootEntry` shape is what the renderer sees after the main process zips paths with their last-used timestamps maintained in a parallel map (or, equivalently, stored as `ProjectRootEntry[]` directly — implementation choice during T-tasks, no impact on the contract).

**Validation rules**:
- `path`: must be an absolute path on the current platform (`path.isAbsolute(p) === true`).
- Maximum 5 entries; oldest dropped on overflow (FR-027).
- A path that fails the `fs.access(p, R_OK)` check at validation time is *retained* in the list (so the user can see it and replace it) but reported with `{ valid: false }` by `projectRoot:validate`.

### `LaunchProfile`

The `(connection, project root)` pair the launcher resumes from.

```ts
export interface LaunchProfile {
  connectionId: string;   // points into savedConnections[*].id
  projectRoot: string;    // absolute path
  /** ISO-8601 UTC of the last successful Enter using this exact pair. */
  enteredAt: string;
}
```

There is exactly one `lastProfile` field in settings. A small list of recent profiles MAY be derived from per-connection `lastConnectedAt` + per-projectRoot `lastUsedAt` cross-joined, but is not persisted.

### `SessionUser`

Resolved at launcher open and on every project-root change. **Not persisted.** Carried through Pinia to the http interceptor and forwarded as request headers.

```ts
export type IdentitySource =
  | 'env'                   // GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL set
  | 'project-local-git'     // .git/config inside the selected project root
  | 'global-git'            // ~/.gitconfig (user.name / user.email)
  | 'system-git'            // /etc/gitconfig
  | 'unknown-fallback';     // no git config resolvable

export interface SessionUser {
  name: string;
  email: string;
  source: IdentitySource;
  /** Truncated for UI display; the full `name` is what gets sent in headers. */
  displayName: string;
}
```

**Validation rules**:
- `name`: any non-empty string when source ≠ `'unknown-fallback'`; `'unknown user'` when source === `'unknown-fallback'`.
- `email`: any non-empty string when source ≠ `'unknown-fallback'`; `'unknown@<hostname>'` when source === `'unknown-fallback'`.
- `displayName`: `name` truncated at 40 chars with ellipsis if longer.

---

## §2 — Persisted `DesktopSettings` v2

Extends the 023 schema. The full v2 shape (additions in **bold**):

```ts
export interface DesktopSettingsV2 {
  schemaVersion: 2;                                  // bumped from 1
  dataSource: 'bundled' | 'external';                // unchanged
  externalNeo4j: ExternalNeo4jConfig | null;         // kept; always null after migration; removed in v3
  dataDir: string | null;                            // unchanged
  llm: { provider: LlmProvider; model: string };     // unchanged
  update: { autoCheck: boolean; lastCheckedAt: string | null };  // unchanged
  window: { bounds: WindowBounds | null; maximized: boolean };   // unchanged
  lastPorts: { backend: number | null; bolt: number | null };    // unchanged
  // ---------- new in v2 ----------
  savedConnections: SavedConnection[];               // **new** — ordered most-recently-used first
  recentProjectRoots: string[];                      // **new** — absolute paths, most-recent first, max 5
  lastProfile: LaunchProfile | null;                 // **new**
}
```

**Atomicity & corruption handling** — unchanged from 023's existing pattern: write to `settings.tmp`, fsync, rename. On read failure or schema-version mismatch we cannot recover from, fall back to `settings.bak`; if neither, regenerate defaults.

---

## §3 — OS keychain key naming

| Key | Value | Lifecycle |
|---|---|---|
| `connection.<id>.password` | UTF-8 plaintext password | Set by `connections:save` after successful Test. Cleared by `connections:delete`. Re-keyed by v1 → v2 migration (the old `neo4j.password` becomes `connection.<migratedId>.password` and is deleted). |
| `neo4j.password` *(legacy, 023)* | UTF-8 plaintext password | Read once during migration, deleted after re-key. Never re-introduced in v2+ writes. |
| `llm.openai.apiKey`, `llm.anthropic.apiKey`, `llm.google.apiKey`, `figma.apiToken` *(existing, 023)* | unchanged | unchanged |

**Provider**: existing 023 `safeStorage` (Electron) primary, `keytar` fallback. 032 adds no new provider.

**Never logged**: keychain reads and writes log only the key name, never the value. `setSecret` IPC explicitly redacts the value field in the log line.

---

## §4 — Settings v1 → v2 migration table

Source of truth: `desktop/src/main/launcher/settings-migrate.ts`.

| v1 input | v2 output | Notes |
|---|---|---|
| `schemaVersion: 1` | `schemaVersion: 2` | bumped |
| `externalNeo4j: { uri, user, database }` (non-null) | Inserted as `savedConnections[0]` with `id = <new uuid>`, `label = "Migrated from settings"`, `source = 'manual-migrated-from-023'`, `lastConnectedAt = null`, `createdAt = now()`. Then `externalNeo4j` field is set to `null`. | Keychain re-keyed: `neo4j.password` → `connection.<newId>.password`. |
| `externalNeo4j: null` | `savedConnections: []` | nothing to migrate |
| `dataSource: 'bundled'` (with no external config) | `savedConnections: []`, `lastProfile: null` | The bundled Neo4j entry (if 023 ships it) is synthesized at runtime; not persisted as a SavedConnection. |
| (absent) | `recentProjectRoots: []`, `lastProfile: null` | first run after upgrade has no history yet — populated as the user uses the launcher |

**Idempotency**: migration runs only when `schemaVersion === 1`. Re-running it on a v2 file is a no-op (early return).

**Forward-rollback note**: keeping `externalNeo4j: null` in v2 means a v1 build can still read the file (it'll see a null and treat the user as un-configured). Acceptable single-version regression for any user who downgrades — they re-enter on launch and get a working v1 setup.

---

## §5 — Python middleware shape

`api/platform/identity/models.py`:

```python
from dataclasses import dataclass
from typing import Literal

IdentitySource = Literal[
    "env",
    "project-local-git",
    "global-git",
    "system-git",
    "unknown-fallback",
    "unknown-header-missing",   # backend-side fallback when headers absent
]

@dataclass(frozen=True)
class Actor:
    name: str
    email: str
    source: IdentitySource
```

`request.state.actor: Actor` is set by `IdentityMiddleware` on every request. Features that want attribution read it; features that don't, ignore it.

**No persistence in 032.** The follow-up history spec is what writes Actor data into Neo4j `:ChangeEvent` nodes.

---

## §6 — Cross-references

| Concern | Lives in | Read by | Written by |
|---|---|---|---|
| Saved connections list | `settings.json` (`savedConnections`) | renderer (via `connections:list`) | main (via `connections:save/update/delete`) |
| Connection passwords | OS keychain | main (on Test / backend env injection) | main (on save / update) |
| Discovered DBMSs | transient (in-memory only) | renderer (via `connections:discoverNeo4jDesktop`) | main (every call re-scans) |
| Recent project roots | `settings.json` (`recentProjectRoots`) | renderer | main (after Enter) |
| Last profile | `settings.json` (`lastProfile`) | renderer (for default selection) | main (after Enter) |
| Session user | Pinia store (renderer) + `window.desktop.identity.resolve()` cache | renderer (interceptor) | main (re-resolved on identity:resolve calls) |
| Session user → backend | HTTP request headers `X-User-Name`/`X-User-Email` | backend `IdentityMiddleware` | frontend `http.ts` interceptor |
| Actor on backend | `request.state.actor` | feature routers (read-only) | `IdentityMiddleware` |
