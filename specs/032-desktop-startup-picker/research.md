# Phase 0 — Research

Resolves every open technical question from [plan.md](plan.md) before Phase 1 design.

---

## D1 — Launcher render strategy (separate window vs same-window route)

**Decision**: Same `BrowserWindow`, separate Vue route `/__launcher`.

**Rationale**:
- The existing 023 `desktop/src/main/index.ts` already creates exactly one `BrowserWindow` whose URL is the SPA index. Pointing it at a launcher route first costs nothing — no second window object, no `webContents` swap, no double-frame flash on hand-off, no second IPC channel multiplexer.
- The Vue 3 router is already present in `frontend/src/app/`; adding a new route is the same operation as adding any feature page.
- The hand-off ("user clicked Enter") is a renderer-side router navigation from `/__launcher` to `/`. The launcher's session store carries the resolved identity + chosen connection + project root into the main app via Pinia — no main-process message needed beyond the `launcher:enter` ack that persists the new `lastProfile` and triggers the backend swap if the chosen Neo4j changed.
- The main process still needs to know which connection to point the backend at (for backend env injection), which is what the `launcher:enter` IPC carries. But the *visual* hand-off is purely renderer-internal — no flicker.

**Alternatives considered**:
- *Separate splash `BrowserWindow`*: cleaner visual separation, but doubles the surface area for IPC handler registration, requires careful focus management on the swap, and means the launcher and the main app cannot share a Pinia store cheaply. Rejected — no benefit that offsets the complexity.
- *Native splash (`SplashScreen` API)*: not appropriate — the launcher is fully interactive (forms, lists, OS folder dialog), not a 2-second logo.

**Implications for code**:
- `desktop/src/main/index.ts` loads the SPA URL with `#/__launcher` (hash-mode router) or `?launcher=1` if history-mode — the renderer reads this and routes accordingly.
- `frontend/src/app/router.js` adds a navigation guard: any route other than `/__launcher` redirects to `/__launcher` when `window.desktop` is present AND `useSession().entered === false`. Web mode (`window.desktop === undefined`) is unaffected by the guard.

---

## D2 — Neo4j Desktop config layout (macOS + Windows)

**Decision**: Parse `<NeoDeskRoot>/Application/relate.config.json` for the DBMS list, read each DBMS's `dbms-<UUID>/conf/neo4j.conf` for the bolt listen address, fail silently on any unexpected shape.

**Rationale**:
- Neo4j Desktop (v1.5+) writes a single top-level config at `<NeoDeskRoot>/Application/relate.config.json` listing every Project + every DBMS belonging to each Project. Schema is stable across recent Neo4j Desktop versions in the parts we need (`projects[].dbmss[]` with `id`, `name`, `version`, `status`).
- The actual bolt port for each DBMS is *not* in `relate.config.json` — it lives in the per-DBMS `conf/neo4j.conf` under `server.bolt.listen_address` (Neo4j 5.x) or `dbms.connector.bolt.listen_address` (Neo4j 4.x). Read both keys, prefer the v5 name.
- File system roots:
  - **macOS**: `~/Library/Application Support/Neo4j Desktop/`
  - **Windows**: `%APPDATA%\Neo4j Desktop\`
  - **Linux**: `~/.config/Neo4j Desktop/` — not a v1 target per CLAUDE.md (mac + win only), but the code path is identical and trivial to add later.
- Everything we touch is read-only. We never write to Neo4j Desktop's directories, never call its CLI (`neo4j-desktop` / `relate`), and never talk to its localhost API. This matches FR-016 / FR-022: passwords are never read from Neo4j Desktop.

**Alternatives considered**:
- *Talk to Neo4j Desktop's local HTTP API (`relate-api`)*: would give us live DBMS status (running/stopped) without filesystem parsing. Rejected — requires the user to have started Neo4j Desktop, depends on an API key the user would have to supply, and is unstable across Neo4j Desktop versions.
- *Probe localhost bolt ports 7687 / 7688 / 7689…*: noisy, races with real services on those ports, can't tell ours-from-Neo4j-Desktop's. Rejected.
- *Skip discovery entirely, leave it as a manual add*: rejected by the spec (US3 P2) — meaningful onboarding win for Neo4j Desktop users.

**Failure modes (all degrade silently per FR-017 / FR-023)**:
- Neo4j Desktop not installed → root directory does not exist → discovery returns `[]`.
- `relate.config.json` exists but unreadable (locked by Neo4j Desktop while it's running) → catch EACCES/EBUSY → return `[]`, log a single info line.
- `relate.config.json` shape changed in a future Neo4j Desktop version → catch JSON or schema mismatch → return `[]`, log a single info line with the version we couldn't parse.
- Per-DBMS `neo4j.conf` missing or unparseable → omit that DBMS from the discovered list, continue with the rest.

**Implications for code**:
- `desktop/src/main/launcher/discovery.ts` exports `discoverNeo4jDesktopDbmss(): Promise<DiscoveredConnection[]>`.
- 2 s soft timeout on the whole operation. After that, return whatever was parsed and abort the rest.
- Discovered connections are *never* automatically saved — they appear in a "Discovered" group and only become a `SavedConnection` when the user successfully **Test**s one (FR-024).

---

## D3 — Git identity resolution mechanism

**Decision**: `child_process.spawn("git", ["config", "--get", "user.name"])` (and `user.email`) with `cwd = selectedProjectRoot`, 2 s timeout per call, no shell.

**Rationale**:
- Git's own precedence (`GIT_AUTHOR_NAME` env > project-local `.git/config` > `--global` `~/.gitconfig` > `--system` `/etc/gitconfig`) is exactly what we want (FR-005). Re-implementing it would be both tedious and wrong-in-edge-cases (include directives, conditional includes, `.gitconfig-<scope>`). Letting `git config` resolve it for us is one line, correct by construction, and works on whatever version of git the user has.
- `cwd` matters: setting it to the *selected* project root means project-local overrides apply (FR-008). When the launcher first opens and no project root is selected yet, we use the parent dir of `process.execPath` as a neutral cwd to get global+system identity for the initial welcome banner.
- `spawn` (not `exec`, not `shell: true`) — passes argv as an array, no shell interpolation, no command-injection risk even if a malicious project root path is set.
- 2 s timeout is generous; `git config --get` is a single syscall + a few file reads.

**Alternatives considered**:
- *Parse `~/.gitconfig` ourselves with an INI parser*: misses env-var overrides, misses includes, misses conditional includes. Rejected.
- *Skip git, default to OS username*: loses the multi-user value entirely (US3). Rejected.
- *libgit2 binding*: dependency creep for what is two lines with `spawn`. Rejected.

**Failure modes** (all map to "unknown user" fallback per FR-007):
- `git` not on PATH → ENOENT from spawn → return `{ source: 'unknown-fallback', name: 'unknown user', email: `unknown@${os.hostname()}` }`.
- `git config --get user.name` exits non-zero (no key configured) → same fallback.
- Timeout → same fallback.
- Permission denied reading `~/.gitconfig` → same fallback.

**Implications for code**:
- `desktop/src/main/launcher/identity.ts` exports `resolveSessionUser(projectRoot: string | null): Promise<SessionUser>`.
- Called by the launcher on open and again on every project-root change (FR-008).
- Never cached across launches — re-resolved every launch so users editing git config see the change immediately (FR-032).

---

## D4 — Settings schemaVersion migration (v1 → v2)

**Decision**: In-place migration on first read after upgrade. v1's `externalNeo4j` (if non-null) becomes the first `SavedConnection`. The legacy keychain entry `neo4j.password` is re-keyed to `connection.<newId>.password`. The `externalNeo4j` field is kept set to `null` in v2 for one release (forward-rollback safety), then removed entirely in v3.

**Rationale**:
- Per FR-027 / FR-033, the user must NOT be prompted to re-enter their connection after upgrade.
- Migration is atomic: read v1 → construct v2 → write v2 to a temp file → fsync → rename. This is the same `data-dir.ts` atomic-write pattern already used by 023.
- Keychain re-keying is the only fragile bit. If it fails (keychain locked, key gone), the migration still completes — the `SavedConnection` is written without a stored password and on first launch the user is asked to re-enter it (the same path as US3 "password missing in keychain" edge case). We do not abort the whole migration on a keychain miss.

**v1 → v2 shape diff**:

| Field | v1 | v2 | Notes |
|---|---|---|---|
| `schemaVersion` | 1 | 2 | bumped |
| `dataSource` | `'bundled' \| 'external'` | unchanged | still drives 023 bundled-Neo4j path when present |
| `externalNeo4j` | `ExternalNeo4jConfig \| null` | kept, always `null` after migration | retained for one release for rollback safety |
| `savedConnections` | — | `SavedConnection[]` | **new**; populated from migrated `externalNeo4j` if present |
| `recentProjectRoots` | — | `string[]` (most-recent first, max 5) | **new** |
| `lastProfile` | — | `{ connectionId: string; projectRoot: string } \| null` | **new** |
| `dataDir` | `string \| null` | unchanged | |
| `llm` | unchanged | unchanged | |
| `update` | unchanged | unchanged | |
| `window` | unchanged | unchanged | |
| `lastPorts` | unchanged | unchanged | |

**Alternatives considered**:
- *Versioned-file approach (write `settings.v2.json` alongside)*: more code, easier rollback. Rejected — the existing 023 design uses a single file with `schemaVersion`, and we should not fork that convention for one feature.
- *Lazy migration (read v1 fields as if they were v2)*: footgun — any code touching `savedConnections` would have to know about the legacy fallback. Rejected.

**Implications for code**:
- `desktop/src/main/launcher/settings-migrate.ts` exports `migrateSettingsIfNeeded(raw: unknown): { migrated: boolean; settings: DesktopSettings }`.
- Called by the existing settings load path in `data-dir.ts`. The load path also writes the migrated form back to disk on detection of `migrated: true`.

---

## D5 — Identity propagation envelope (request to backend)

**Decision**: Two plain HTTP request headers — `X-User-Name` (UTF-8 percent-encoded) and `X-User-Email`. No JWT, no signing, no expiry.

**Rationale**:
- The trust model for this product is "the desktop app is a local single-user tool; git user is the user" (Assumption in spec, also FR-010). Anyone with shell access on the host can already set arbitrary git identity, so signing the headers adds no actual security — it would only make the local tooling more annoying.
- HTTP headers are universally supported by the existing fetch / axios layer; no new transport, no new SDK.
- The headers are set by a renderer-side interceptor (`frontend/src/app/http.ts`) reading from a Pinia store populated at launcher hand-off. The interceptor is the only place that needs to know about identity propagation — no per-feature wiring.
- Backend `IdentityMiddleware` is registered once in `api/main.py`. Every request gets a `request.state.actor` with `{name, email, source}`. Features that want to record the actor (the follow-up history spec) just read `request.state.actor`. Features that don't care simply ignore it. This is the standard FastAPI middleware shape.

**Header format**:
- `X-User-Name`: UTF-8 percent-encoded (per RFC 8187 minus the `UTF-8''` prefix because we always know the charset). Names with non-ASCII chars round-trip correctly.
- `X-User-Email`: ASCII-only by spec (email addresses are 7-bit). Validated lazily — middleware accepts any non-empty string and stores it; it does not enforce RFC 5322.
- Missing both → middleware sets `actor = { name: 'unknown user', email: f'unknown@{socket.gethostname()}', source: 'unknown-fallback' }`. Never raises; never 401s.
- Empty string in either → treated as missing.

**Alternatives considered**:
- *Single `Authorization: Bearer <signed-token>`*: forces a token store, expiry, refresh, and adds a backend signing key — none of which add value for a local single-user tool. Rejected.
- *Session cookie set at launcher hand-off*: forces CSRF protection, cookie-domain wrangling between Electron's `file://` and `http://127.0.0.1:<port>`. Rejected.
- *Custom body field on every request*: requires every endpoint to declare it; couples write surface to identity. Rejected.

**Implications for code**:
- `frontend/src/app/http.ts` — new file (or extension of the existing one if `axios` is already wired in `App.vue`). Adds a request interceptor that reads `useSession().user` and sets headers.
- `api/platform/identity/middleware.py` — Starlette `BaseHTTPMiddleware` reading the two headers + populating `request.state.actor`. Logs one line per request via the existing structured logger.

---

## D6 — Folder picker behavior (macOS + Windows)

**Decision**: `dialog.showOpenDialog(mainWindow, { properties: ['openDirectory', 'dontAddToRecent'] })` on both targets. No special entitlements required.

**Rationale**:
- Electron's `dialog.showOpenDialog` inherits the calling user's filesystem permissions; there is no sandbox restriction for unsigned/signed Electron apps on either target outside of macOS App Store sandboxing (which 023 does not target — distribution is direct DMG / signed installer per 023 packaging-manifest).
- `dontAddToRecent` keeps the OS-level "Recent Folders" menu clean — we maintain our own per-app recents list (FR-027) which is more useful than polluting the OS history.
- Validation (`exists && readable`) is a separate post-pick step using `fs.promises.access(path, constants.R_OK)` — fast and unambiguous.

**Alternatives considered**:
- *Custom in-renderer folder browser*: reinvents the wheel, doesn't match OS look-and-feel, can't access folders outside the renderer's reach. Rejected.
- *Drag-and-drop a folder onto the launcher*: nice-to-have, not in spec, deferred.

**Implications for code**:
- `desktop/src/main/launcher/project-root.ts` exports `chooseProjectRoot()`, `validateProjectRoot(path)`, `listRecentProjectRoots()`.

---

## D7 — Relationship to the existing 023 Settings panel

**Decision**: Launcher is the entry point; the in-app Settings panel from 023 (when shipped) becomes a re-entry point — it re-opens the launcher modally for changing the active connection / project root mid-session, and continues to own LLM key entry. No duplication: Settings invokes the same `connections:*` and `projectRoot:*` IPC channels and reuses the same Vue components from `frontend/src/features/desktop-launcher/`.

**Rationale**:
- Users will want to switch connection without restarting the app. Re-opening the launcher modally (as a Settings sub-view) is the simplest UX and uses identical code.
- LLM key entry is unrelated to launcher concerns and stays where 023 puts it.

**Alternatives considered**:
- *Force quit-and-relaunch to switch connection*: hostile UX. Rejected.
- *Move all of Settings into the launcher*: bloats the launcher's purpose ("first screen") into "everything-screen". Rejected.

**Implications for code**:
- No code change in this phase beyond ensuring the launcher view is mountable both as a route (`/__launcher`) and as a modal — Vue components are inherently both.

---

## Summary of decisions

| ID | Question | Decision | Status |
|---|---|---|---|
| D1 | Launcher window strategy | Same `BrowserWindow`, Vue route `/__launcher` | ✅ |
| D2 | Neo4j Desktop discovery | Read-only filesystem parse of `relate.config.json` + per-DBMS `neo4j.conf` | ✅ |
| D3 | Git identity resolution | `git config --get` spawn with `cwd=projectRoot`, 2 s timeout | ✅ |
| D4 | Settings v1 → v2 migration | In-place, atomic, externalNeo4j → first SavedConnection, keychain re-keyed | ✅ |
| D5 | Identity envelope to backend | `X-User-Name` + `X-User-Email` headers, no signing | ✅ |
| D6 | Folder picker | `dialog.showOpenDialog` with `openDirectory` + `dontAddToRecent` | ✅ |
| D7 | Relationship to 023 Settings | Settings re-opens launcher modally; LLM keys stay in Settings | ✅ |

Zero `NEEDS CLARIFICATION` items remain. Proceeding to Phase 1.
