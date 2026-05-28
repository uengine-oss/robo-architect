---

description: "Implementation tasks for 032 — Desktop Startup Connection, Identity & Project Picker"
---

# Tasks: Desktop Startup Connection, Identity & Project Picker

**Input**: Design documents from [/specs/032-desktop-startup-picker/](.)

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/launcher-ipc-contract.md](contracts/launcher-ipc-contract.md), [contracts/identity-header-contract.md](contracts/identity-header-contract.md), [quickstart.md](quickstart.md).

**Tests**: Lightweight test coverage is included per the plan's Testing section — Vitest unit tests for main-process logic (settings migration, git resolver, Neo4j Desktop parser, connections CRUD), pytest for the backend identity middleware, and a single Playwright/Spectron-style smoke for the launcher flow. No full TDD ceremony.

**Organization**: Tasks are grouped by user story so each P1/P2/P3 slice can be implemented and demoed independently. MVP = all three P1 stories (US1+US2+US3) since they are tightly coupled for first-real-use.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: `[US1]` … `[US5]` — only on user-story-phase tasks
- Every task includes an exact file path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Land the type surface and module skeletons that every later phase touches. No business logic.

- [X] T001 Extend the closed `IpcErrorCode` enum in [desktop/src/shared/ipc-contract.ts](../../desktop/src/shared/ipc-contract.ts) — add `CONNECTION_DUPLICATE`, `CONNECTION_NOT_FOUND`, `DISCOVERY_UNAVAILABLE`, `PROJECT_ROOT_INVALID`, `PROJECT_ROOT_UNREADABLE`, `GIT_UNAVAILABLE`, `LAUNCHER_ALREADY_ENTERED` per [contracts/launcher-ipc-contract.md](contracts/launcher-ipc-contract.md)
- [X] T002 Create [desktop/src/shared/launcher-contract.ts](../../desktop/src/shared/launcher-contract.ts) with the full type surface from [data-model.md](data-model.md) §1 — `SavedConnection`, `ConnectionSource`, `DiscoveredConnection`, `DiscoveredStatus`, `ProjectRootEntry`, `LaunchProfile`, `SessionUser`, `IdentitySource`, and the new `IpcRequestMap` additions per [contracts/launcher-ipc-contract.md](contracts/launcher-ipc-contract.md)
- [X] T003 [P] Create the launcher module directory at [desktop/src/main/launcher/](../../desktop/src/main/launcher/) with an empty `index.ts` barrel that will re-export every module added in Phases 2–7
- [X] T004 [P] Create the renderer launcher feature directory at [frontend/src/features/desktop-launcher/](../../frontend/src/features/desktop-launcher/) with empty `index.ts`, `components/`, and `stores/` subdirs
- [X] T005 [P] Create the backend platform-identity package at [api/platform/identity/](../../api/platform/identity/) with an empty `__init__.py`, and add a parallel test dir at [tests/platform/](../../tests/platform/) with `__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Settings migration, IPC plumbing, identity middleware, router guard. Every user story below depends on this.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [X] T006 Implement the v1 → v2 settings migration in [desktop/src/main/launcher/settings-migrate.ts](../../desktop/src/main/launcher/settings-migrate.ts) — pure function `migrateSettingsIfNeeded(raw) → {migrated, settings, newSavedConnectionForRekey}`, idempotent on v2 input, defaults-recovery on corrupt input
- [X] T007 [P] Playwright-runner unit test at [desktop/tests/unit/settings-migrate.spec.ts](../../desktop/tests/unit/settings-migrate.spec.ts) — 7 cases covering v1-with-externalNeo4j, v1-with-null, v2 idempotence, v2 gap-fill, non-object recovery, future-version recovery, malformed externalNeo4j. (Used Playwright Test runner — matches 023's existing smoke harness; Vitest not added because no other tests need it.)
- [X] T008 Created [desktop/src/main/settings.ts](../../desktop/src/main/settings.ts) (023 never built a settings load/save module — the existing `data-dir.ts` is filesystem-layout only). Atomic load→migrate→re-key-keychain→save pattern; backup-on-write; recovers from `settings.bak` if primary is unreadable.
- [X] T009 Added the keychain re-key wrapper in [desktop/src/main/launcher/connections.ts](../../desktop/src/main/launcher/connections.ts) (`rekeyLegacyNeo4jPassword`), backed by a new [desktop/src/main/secret-store.ts](../../desktop/src/main/secret-store.ts) using Electron's built-in `safeStorage` (no `keytar` dep — 023's planned hybrid never landed; `safeStorage`-only is sufficient on win+mac).
- [X] T010 Implemented `IdentityMiddleware` + `Actor` dataclass at [api/platform/identity/middleware.py](../../api/platform/identity/middleware.py) + [api/platform/identity/models.py](../../api/platform/identity/models.py). Reads `X-User-Name` (percent-decoded) + `X-User-Email`, falls back to `unknown@<hostname>` with source `unknown-header-missing`, never 401s, logs one `api.identity.actor` line per request via the existing `SmartLogger`.
- [X] T011 [P] Pytest at [tests/platform/test_identity_middleware.py](../../tests/platform/test_identity_middleware.py) — 7 cases, all passing locally (`uv run --extra dev pytest tests/platform/...`). Also added [tests/__init__.py](../../tests/__init__.py) so the `tests/platform/` directory doesn't shadow the stdlib `platform` module during collection.
- [X] T012 Registered `IdentityMiddleware` in [api/main.py](../../api/main.py) right after `_request_id_middleware` so the actor line carries the same correlation id. Verified `api.main` still imports (198 routes intact).
- [X] T013 Launcher state machine at [desktop/src/main/launcher/launcher-state.ts](../../desktop/src/main/launcher/launcher-state.ts) — exports `currentPhase()`, `activeProfile()`, `markEntered(profile)`, `markPending()`, `canEnter()` guard. Full `launcher:enter` handler body lands in US1 T028.
- [X] T014 Stub IPC handlers for every new launcher channel registered via a new [desktop/src/main/launcher/ipc-handlers.ts](../../desktop/src/main/launcher/ipc-handlers.ts) (with skip-set so individual US tasks can opt out and register the real handler). Called from `registerIpcHandlers()` in [desktop/src/main/index.ts](../../desktop/src/main/index.ts). Each stub throws a `VALIDATION` IpcHandlerError naming the gating task.
- [X] T015 Preload bridge at [desktop/src/preload/index.ts](../../desktop/src/preload/index.ts) extended with `connections.*`, `projectRoot.*`, `identity.resolve`, `launcher.*` (composed and exposed as a single merged `window.desktop`). Module augmentation in [desktop/src/shared/launcher-contract.ts](../../desktop/src/shared/launcher-contract.ts) widens both `IpcRequestMap` (for main-side `registerHandler`) and the global `Window.desktop` type (for renderer-side calls).
- [X] T016 **Plan adaptation: no Vue Router.** Vue Router isn't installed in this project — the SPA renders `App.vue` directly. Gating moved to `App.vue` root level: `<LauncherPlaceholder v-if="session.isDesktop && !session.entered" />` else existing `<div class="app-container">`. Web mode is transparent because `session.entered` starts `true` when `window.desktop === undefined`. Foundation placeholder lives at [frontend/src/features/desktop-launcher/LauncherPlaceholder.vue](../../frontend/src/features/desktop-launcher/LauncherPlaceholder.vue) and is replaced by `LauncherView.vue` in US tasks.
- [X] T017 [P] Pinia session store at [frontend/src/features/desktop-launcher/stores/session-store.js](../../frontend/src/features/desktop-launcher/stores/session-store.js) — `user`, `connectionId`, `projectRoot`, `entered`, computed `isDesktop` + `hasIdentity`, actions `setIdentity` / `commitProfile` / `reopenLauncher` / `reset`. JS not TS to match the existing frontend convention.
- [X] T018 [P] Pinia launcher (view-state) store at [frontend/src/features/desktop-launcher/stores/launcher-store.js](../../frontend/src/features/desktop-launcher/stores/launcher-store.js) — `savedConnections`, `discovered`, `selectedConnectionId`, `probeStatusById`, `formMode`, `editing`, `error` + actions.
- [X] T019 [P] **Plan adaptation: monkey-patch `window.fetch`** instead of axios interceptor (no axios in the project; native `fetch` everywhere). [frontend/src/app/http.js](../../frontend/src/app/http.js) exports `installIdentityInterceptor()` which wraps `window.fetch` once; injects `X-User-Name` (percent-encoded) + `X-User-Email` on same-origin requests when `session.user` is populated and source ≠ `'unknown-fallback'`. Cross-origin requests pass through unchanged. Never throws — interceptor failures degrade silently.
- [X] T020 [frontend/src/main.js](../../frontend/src/main.js) imports + calls `installIdentityInterceptor()` after `createPinia()` so the wrap is live before any feature module fires its first fetch.
- [X] T021 **No code change needed.** Existing `desktop/src/main/index.ts` already loads the SPA at `app://app/`; with App.vue's launcher gate, that URL automatically lands on the launcher in Electron mode. Vue Router URLs (the original `#/__launcher` idea) became irrelevant once T016 moved the gate to App.vue level.

**Checkpoint**: Foundation ready. Settings migrate, IPC stubs respond, preload exposes the new surface, identity middleware is live on every backend request, and the renderer routes to `/__launcher` first in desktop mode.

---

## Phase 3: User Story 1 — One-click relaunch with last-used profile (P1) 🎯 MVP slice 1/3

**Goal**: A returning user with seeded `settings.json` lands in the launcher, sees their last connection pre-selected with a live status badge, and can click **Enter** to reach the main app in under 5 seconds.

**Independent Test**: Seed `settings.json` with one valid `SavedConnection` + matching keychain entry + a `lastProfile`. Launch the app. Observe: connection pre-selected, status probe completes ≤3 s with "Connected", `Enter` enabled, one click loads the main app (per quickstart Q2 / SC-001).

### Implementation for User Story 1

- [ ] T022 [US1] Implement the `connections:list` handler in [desktop/src/main/launcher/connections.ts](../../desktop/src/main/launcher/connections.ts) — reads `savedConnections` from settings, returns ordered by `lastConnectedAt` desc (nulls last)
- [ ] T023 [US1] Implement the `connections:probeStatus` handler in [desktop/src/main/launcher/connections.ts](../../desktop/src/main/launcher/connections.ts) — looks up SavedConnection by id, fetches password from keychain, runs an authenticated handshake against Neo4j with a 5-second deadline, returns `{state, serverVersion?, detail?}` per [contracts/launcher-ipc-contract.md](contracts/launcher-ipc-contract.md). On timeout returns `state: 'timeout'`, not an error envelope
- [ ] T024 [US1] Wire `connections:list` and `connections:probeStatus` into the handler registry in [desktop/src/main/ipc.ts](../../desktop/src/main/ipc.ts) (replacing the stubs from T014)
- [ ] T025 [P] [US1] Expose `connections.list()` and `connections.probeStatus()` on `window.desktop` in [desktop/src/preload/index.ts](../../desktop/src/preload/index.ts)
- [ ] T026 [P] [US1] Create [frontend/src/features/desktop-launcher/components/ConnectionList.vue](../../frontend/src/features/desktop-launcher/components/ConnectionList.vue) — renders saved connections sorted by recency, highlights the selected one, shows a status badge per item (driven by `launcher-store.probeStatusById`)
- [ ] T027 [US1] Create [frontend/src/features/desktop-launcher/LauncherView.vue](../../frontend/src/features/desktop-launcher/LauncherView.vue) — top-level launcher screen. On mount: `connections.list()` → populate store; if `lastProfile != null` → pre-select that connection + pre-fill that projectRoot, then `connections.probeStatus()` against it
- [ ] T028 [US1] Implement the `launcher:enter` handler in [desktop/src/main/launcher/launcher-state.ts](../../desktop/src/main/launcher/launcher-state.ts) — validates inputs, runs a final keychain-password probe, on success updates `lastConnectedAt`, pushes the projectRoot to `recentProjectRoots` (max 5, dedup), writes `lastProfile`, atomically persists settings via the 023 atomic-write helper, transitions state machine to `entered`
- [ ] T029 [US1] Modify [desktop/src/main/backend.ts](../../desktop/src/main/backend.ts) to accept a `LaunchProfile` on hand-off and inject the chosen connection's URI/user/password (from keychain) into the backend env, replacing the 023 single-source path
- [ ] T030 [US1] Create [frontend/src/features/desktop-launcher/components/EnterAction.vue](../../frontend/src/features/desktop-launcher/components/EnterAction.vue) and wire it into LauncherView — disabled until (connection selected AND its status is reachable/connected/auth-passed) AND projectRoot is valid; on click invokes `window.desktop.launcher.enter(...)`, on `ok` writes `session-store.commitProfile()` and navigates to `/`
- [ ] T031 [P] [US1] Vitest unit test at [desktop/tests/unit/connections-list.test.ts](../../desktop/tests/unit/connections-list.test.ts) — covers list ordering (recency desc, nulls last), lastProfile resolution, missing connection id handling

**Checkpoint**: A seeded returning user can land in the launcher and one-click into the main app. The other two P1 stories may still be missing (no Add form yet, no welcome banner) but the resume path works.

---

## Phase 4: User Story 2 — First-time setup (P1) 🎯 MVP slice 2/3

**Goal**: A user with empty `settings.json` sees the Add-connection form expanded, can test + save a connection, pick a project root via OS dialog, and Enter — all without leaving the launcher screen.

**Independent Test**: Wipe `settings.json` + clear keychain entries; launch; complete the form (per quickstart Q1) and verify the entry round-trips on the next launch.

### Implementation for User Story 2

- [ ] T032 [US2] Implement `connections:save` in [desktop/src/main/launcher/connections.ts](../../desktop/src/main/launcher/connections.ts) — validates per data-model §1 rules, rejects duplicates (`CONNECTION_DUPLICATE`), assigns uuid + `createdAt`, writes the password to OS keychain at `connection.<id>.password` (immediately scrubs `passwordPlaintext` from the IPC payload before logging), atomic settings write
- [ ] T033 [US2] Implement `connections:test` as a thin alias forwarder to the existing `settings:testNeo4jConnection` handler from 023 (in [desktop/src/main/ipc.ts](../../desktop/src/main/ipc.ts)) — same request/response shape, no new backend code
- [ ] T034 [US2] Implement `projectRoot:choose` in [desktop/src/main/launcher/project-root.ts](../../desktop/src/main/launcher/project-root.ts) — `dialog.showOpenDialog(mainWindow, { properties: ['openDirectory', 'dontAddToRecent'] })`, returns `{ path, valid, basename, parent } | { cancelled: true }`
- [ ] T035 [US2] Implement `projectRoot:validate` in [desktop/src/main/launcher/project-root.ts](../../desktop/src/main/launcher/project-root.ts) — `fs.access(path, R_OK)` + `fs.stat` for directory check; returns `{ valid, reason? }`
- [ ] T036 [US2] Implement `projectRoot:listRecent` in [desktop/src/main/launcher/project-root.ts](../../desktop/src/main/launcher/project-root.ts) — zips `settings.recentProjectRoots` paths with their `lastUsedAt` (derived from `lastProfile.enteredAt` history or stored alongside; pick whichever the impl chooses but keep the contract shape from [data-model.md](data-model.md))
- [ ] T037 [US2] Wire `connections:save`, `connections:test`, `projectRoot:choose`, `projectRoot:validate`, `projectRoot:listRecent` into [desktop/src/main/ipc.ts](../../desktop/src/main/ipc.ts) (replacing T014 stubs)
- [ ] T038 [P] [US2] Expose `connections.save`, `connections.test`, `projectRoot.choose`, `projectRoot.validate`, `projectRoot.listRecent` on `window.desktop` in [desktop/src/preload/index.ts](../../desktop/src/preload/index.ts)
- [ ] T039 [P] [US2] Create [frontend/src/features/desktop-launcher/components/ConnectionForm.vue](../../frontend/src/features/desktop-launcher/components/ConnectionForm.vue) — fields: label, URI, user, database (optional), password; **Test** button calls `connections.test()` with distinct outcome rendering for success / wrong-creds / unreachable / URI-malformed / db-not-found; **Save** button calls `connections.save()` only after successful Test (or with "save without testing" advanced option)
- [ ] T040 [P] [US2] Create [frontend/src/features/desktop-launcher/components/ProjectRootPicker.vue](../../frontend/src/features/desktop-launcher/components/ProjectRootPicker.vue) — shows currently-selected projectRoot (basename + truncated parent), **Choose folder** button calls `projectRoot.choose()`, dropdown lists recent roots from `projectRoot.listRecent()`, displays inline validity error from `projectRoot.validate()`
- [ ] T041 [US2] Update [frontend/src/features/desktop-launcher/LauncherView.vue](../../frontend/src/features/desktop-launcher/LauncherView.vue) — when `savedConnections.length === 0` expand the ConnectionForm by default; render ProjectRootPicker; keep Enter disabled until both connection + projectRoot are valid (per FR-029)
- [ ] T042 [US2] Append save+validation tests to [desktop/tests/unit/connections-list.test.ts](../../desktop/tests/unit/connections-list.test.ts) (or split into `connections-save.test.ts`) — cover: label/URI/user/database validation rules, duplicate detection by label, duplicate detection by (uri,user,database) tuple, keychain write invoked, payload scrubbing before log emission

**Checkpoint**: A first-time user can complete quickstart Q1 end-to-end. The launcher is functional in isolation; identity (US3) is still absent so the welcome banner shows raw username or nothing.

---

## Phase 5: User Story 3 — Identity from git, no login screen (P1) 🎯 MVP slice 3/3

**Goal**: The launcher resolves the session user from git, displays "Welcome, &lt;name&gt;", re-resolves on project-root change, and propagates the identity to every backend write after Enter.

**Independent Test**: Set distinct git identities at three precedence levels (env, project-local, global). Launch with each and confirm the welcome banner reflects the right one. After Enter, sample any write in the backend log and confirm `actor_email` matches (quickstart Q3 / SC-009 / SC-010).

### Implementation for User Story 3

- [ ] T043 [US3] Implement the git identity resolver in [desktop/src/main/launcher/identity.ts](../../desktop/src/main/launcher/identity.ts) — exports `resolveSessionUser(projectRoot: string | null): Promise<SessionUser>`; spawns two parallel `git config --get user.name` / `user.email` with `cwd = projectRoot ?? path.dirname(process.execPath)`, shared 1 s deadline, no shell, detects ENOENT (git not on PATH) → fallback, non-zero exit → fallback, timeout → fallback. Fallback shape: `{ name: 'unknown user', email: \`unknown@${os.hostname()}\`, source: 'unknown-fallback', displayName: 'unknown user' }`. Truncates `displayName` to 40 chars with ellipsis
- [ ] T044 [US3] Implement the `identity:resolve` IPC handler and wire it into [desktop/src/main/ipc.ts](../../desktop/src/main/ipc.ts)
- [ ] T045 [P] [US3] Expose `identity.resolve()` on `window.desktop` in [desktop/src/preload/index.ts](../../desktop/src/preload/index.ts)
- [ ] T046 [P] [US3] Create [frontend/src/features/desktop-launcher/components/WelcomeBanner.vue](../../frontend/src/features/desktop-launcher/components/WelcomeBanner.vue) — shows "Welcome, &lt;displayName&gt;" with a subtle source badge; when source === `'unknown-fallback'` shows the inline notice "Set `git config user.name` to record changes under your name"
- [ ] T047 [US3] Wire WelcomeBanner into [frontend/src/features/desktop-launcher/LauncherView.vue](../../frontend/src/features/desktop-launcher/LauncherView.vue) — call `identity.resolve({ projectRoot: null })` on mount; call `identity.resolve({ projectRoot })` again on every projectRoot change; store the result in `session-store.user` so the banner is reactive
- [ ] T048 [US3] Modify the `launcher:enter` handler in [desktop/src/main/launcher/launcher-state.ts](../../desktop/src/main/launcher/launcher-state.ts) (extending T028) — after persisting settings, re-resolve identity with `cwd = projectRoot` (the renderer's snapshot may be stale if project-local git config changed) and return the authoritative SessionUser in the response per [contracts/launcher-ipc-contract.md](contracts/launcher-ipc-contract.md)
- [ ] T049 [US3] Update [frontend/src/features/desktop-launcher/stores/session-store.ts](../../frontend/src/features/desktop-launcher/stores/session-store.ts) and the EnterAction wiring (T030) so that after `launcher.enter()` returns ok, the authoritative `identity` from the response is what's written to the store (not the renderer's pre-Enter value). The http interceptor (T019) then reads this on every subsequent request
- [ ] T050 [P] [US3] Vitest unit test at [desktop/tests/unit/identity.test.ts](../../desktop/tests/unit/identity.test.ts) — mock `child_process.spawn`; cover: name+email both resolved → SessionUser with right source, git not on PATH (ENOENT) → unknown fallback, name resolved but email missing → unknown fallback (we require both), timeout → unknown fallback, displayName truncation at 40 chars
- [ ] T051 [US3] Small update to [frontend/src/app/layout/TopBar.vue](../../frontend/src/app/layout/TopBar.vue) — in desktop mode (`window.desktop !== undefined`), show `session.user.displayName` in the top-right (read-only); web mode unchanged

**Checkpoint**: All three P1 stories complete. MVP is shippable: returning users one-click resume, new users complete first-time setup, every session is identity-tagged and every backend write carries `X-User-Name`/`X-User-Email`.

---

## Phase 6: User Story 4 — Discover connections from local Neo4j Desktop (P2)

**Goal**: On a host with Neo4j Desktop installed, the launcher's "Discovered" section auto-populates with the user's DBMSs. On hosts without Neo4j Desktop, the launcher is visually identical to the empty-state path with no errors.

**Independent Test**: Per quickstart Q5 — populated discovery on a Neo4j-Desktop host, silent on a host without it.

### Implementation for User Story 4

- [ ] T052 [US4] Implement the Neo4j Desktop config parser at [desktop/src/main/launcher/discovery.ts](../../desktop/src/main/launcher/discovery.ts) — exports `discoverNeo4jDesktopDbmss(): Promise<DiscoveredConnection[]>`. macOS path `~/Library/Application Support/Neo4j Desktop/Application/relate.config.json`; Windows path `%APPDATA%\Neo4j Desktop\Application\relate.config.json`. Reads `projects[].dbmss[]` for {id, name, version, status}, then reads each `dbmss/dbms-<id>/conf/neo4j.conf` and parses both `server.bolt.listen_address` (Neo4j 5.x preferred) and `dbms.connector.bolt.listen_address` (Neo4j 4.x fallback) to assemble the bolt URI. 2-second overall soft timeout. Any failure mode (ENOENT, EACCES, EBUSY, JSON parse error, schema mismatch, missing per-DBMS conf) → returns whatever was successfully parsed, never throws. Logs **one** info line per launch with the count and the Neo4j Desktop version it saw (or "not installed")
- [ ] T053 [US4] Implement the `connections:discoverNeo4jDesktop` IPC handler and wire it into [desktop/src/main/ipc.ts](../../desktop/src/main/ipc.ts) — wraps `discoverNeo4jDesktopDbmss()`, always returns `ok: true` (errors are represented as empty arrays per FR-017)
- [ ] T054 [P] [US4] Expose `connections.discoverNeo4jDesktop()` on `window.desktop` in [desktop/src/preload/index.ts](../../desktop/src/preload/index.ts)
- [ ] T055 [P] [US4] Create [frontend/src/features/desktop-launcher/components/DiscoveredSection.vue](../../frontend/src/features/desktop-launcher/components/DiscoveredSection.vue) — renders the discovered list grouped by `projectName`, with `{dbmsName, uri-host:port, neo4jVersion}` and a status badge from `DiscoveredStatus`. Stopped DBMSs render with a hint to start them in Neo4j Desktop first
- [ ] T056 [US4] Update [frontend/src/features/desktop-launcher/LauncherView.vue](../../frontend/src/features/desktop-launcher/LauncherView.vue) — on mount call `connections.discoverNeo4jDesktop()` in parallel with `connections.list()`; render DiscoveredSection only when discovery returned a non-empty array
- [ ] T057 [US4] Wire promote-to-saved flow — when the user clicks a discovered DBMS, open ConnectionForm pre-filled with that DBMS's URI + a default user (`neo4j`) + an empty password field, with the "source" hint set to `imported-from-neo4j-desktop`. Successful Test + Save (reuses T032) inserts it as a normal SavedConnection. **Never** read or send a password from Neo4j Desktop (FR-016, FR-022)
- [ ] T058 [P] [US4] Vitest at [desktop/tests/unit/discovery.test.ts](../../desktop/tests/unit/discovery.test.ts) — use fixture files at [desktop/tests/unit/fixtures/neo4j-desktop/](../../desktop/tests/unit/fixtures/neo4j-desktop/) for both v4-style and v5-style configs; cover: happy-path parse, missing relate.config.json → `[]`, malformed JSON → `[]`, per-DBMS conf missing → that DBMS omitted but others succeed, neither v4 nor v5 bolt address key present → that DBMS omitted

**Checkpoint**: US4 complete. Discovery quietly improves onboarding for Neo4j Desktop users without harming the empty-state path for everyone else.

---

## Phase 7: User Story 5 — Manage saved connections (P3)

**Goal**: Users can edit and delete saved connections from the launcher, with keychain cleanup on delete, and re-open the launcher mid-session from in-app Settings.

**Independent Test**: Per quickstart Q6 — edit one connection, delete another, verify keychain cleanup, relaunch and confirm persistence.

### Implementation for User Story 5

- [ ] T059 [US5] Implement `connections:update` in [desktop/src/main/launcher/connections.ts](../../desktop/src/main/launcher/connections.ts) — accepts partial updates; `passwordPlaintext: undefined` = leave, `null` = clear keychain entry, non-empty string = replace; re-runs validation rules from data-model §1; re-checks duplicate detection excluding the target id
- [ ] T060 [US5] Implement `connections:delete` in [desktop/src/main/launcher/connections.ts](../../desktop/src/main/launcher/connections.ts) — removes the entry from `savedConnections`, clears `connection.<id>.password` from the OS keychain, and if `lastProfile.connectionId === id` sets `lastProfile = null`
- [ ] T061 [US5] Wire `connections:update`, `connections:delete`, and `launcher:reopen` into [desktop/src/main/ipc.ts](../../desktop/src/main/ipc.ts) (replacing the T014 stubs)
- [ ] T062 [P] [US5] Expose `connections.update()`, `connections.delete()`, and `launcher.reopen()` on `window.desktop` in [desktop/src/preload/index.ts](../../desktop/src/preload/index.ts)
- [ ] T063 [US5] Add Edit/Delete actions to [frontend/src/features/desktop-launcher/components/ConnectionList.vue](../../frontend/src/features/desktop-launcher/components/ConnectionList.vue) — context menu (right-click) or hover-revealed buttons; Edit emits an event to LauncherView to open ConnectionForm in edit mode; Delete opens a confirm dialog
- [ ] T064 [US5] Extend [frontend/src/features/desktop-launcher/components/ConnectionForm.vue](../../frontend/src/features/desktop-launcher/components/ConnectionForm.vue) to support edit mode — when given an existing SavedConnection prop, pre-fills all fields and adds a "Keep existing password" option for the password field (translates to `passwordPlaintext: undefined` on `connections.update()`)
- [ ] T065 [US5] Implement `launcher:reopen` handler in [desktop/src/main/launcher/launcher-state.ts](../../desktop/src/main/launcher/launcher-state.ts) — transitions state machine `entered` → `pending`. Renderer pairs this with a `router.push('/__launcher')` (or modal-launcher mount) to make the launcher visible again mid-session. Reuses every existing component
- [ ] T066 [US5] Add a "Manage connections" entry point in the existing 023 Settings panel (or, if Settings panel isn't yet wired, a small "Connections" link in [frontend/src/app/layout/TopBar.vue](../../frontend/src/app/layout/TopBar.vue) in desktop mode) — clicking it calls `window.desktop.launcher.reopen()` and navigates to `/__launcher`

**Checkpoint**: All five user stories complete. Full launcher behavior with management UX.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Test coverage of CRUD, end-to-end smoke, observability discipline, manual QA, doc updates.

- [ ] T067 [P] Comprehensive Vitest CRUD coverage at [desktop/tests/unit/connections.test.ts](../../desktop/tests/unit/connections.test.ts) — covers `save` + `update` + `delete` + keychain integration (mocked `safeStorage`/`keytar`); merges or supersedes T042 if T042 was placed in the same file
- [ ] T068 [P] End-to-end launcher smoke test at [desktop/tests/smoke/launcher-flow.smoke.ts](../../desktop/tests/smoke/launcher-flow.smoke.ts) — Playwright/Spectron-style; covers happy paths from quickstart Q1 (cold first-time setup) and Q2 (returning-user resume). Skipped in CI on hosts without an Electron runtime
- [ ] T069 [P] Add JSONL logging at every IPC channel under [desktop/src/main/launcher/](../../desktop/src/main/launcher/) per the logging contract in [contracts/launcher-ipc-contract.md](contracts/launcher-ipc-contract.md) — one line per call with `channel`, `outcome`, `durationMs`, `correlationId`, and non-sensitive `fields`. Verify by code review that no password, no keychain value, and no absolute home-dir path is logged
- [ ] T070 [P] Add a short "Launcher" section to [desktop/README.md](../../desktop/README.md) (or create the file) — links back to this spec, lists the new IPC channels, documents the settings v2 shape change, and notes the identity-header contract
- [ ] T071 Run quickstart.md scenarios Q1–Q8 on a macOS reference machine; record pass/fail per scenario in the table in [quickstart.md](quickstart.md); attach any failure logs
- [ ] T072 Run quickstart.md scenarios Q1–Q8 on a Windows reference machine; record results in the same table
- [ ] T073 Run the out-of-band checks at the bottom of [quickstart.md](quickstart.md) — password-leak grep (SC-004), cold-start budget median ≤ 1.5 s over 10 runs (SC-008), identity-propagation audit ≥ 49/50 (SC-010)
- [ ] T074 Update phase progress in [CLAUDE.md](../../CLAUDE.md) under the `<!-- SPECKIT START -->` block — mark Phases 0–7 ✅, Phase 8 polish ✅, and note the smoke-test platform coverage achieved

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no deps — start immediately.
- **Phase 2 (Foundational)**: depends on Phase 1. **Blocks every user story.**
- **Phase 3 (US1)**, **Phase 4 (US2)**, **Phase 5 (US3)**: each depends only on Phase 2. Can run in parallel by different developers if staffed.
- **Phase 6 (US4)**: depends on Phase 2; also softly depends on US2 because the promote-to-saved flow (T057) reuses the ConnectionForm and `connections:save` from US2. If US2 isn't done, US4 can land discovery + display only and defer T057.
- **Phase 7 (US5)**: depends on Phase 2; soft-depends on US2 (Edit reuses ConnectionForm).
- **Phase 8 (Polish)**: depends on whichever stories are in-scope for the release.

### Within each story

- Main-process IPC handler → preload bridge → renderer component → wiring into LauncherView.
- Within those, `[P]`-marked tasks (different files) can run truly in parallel.

### Parallel opportunities (single-developer, batched commits)

Phase 1: T003, T004, T005 in parallel after T001+T002.
Phase 2: T007, T011, T017, T018, T019 in parallel.
Phase 3: T025, T026, T031 in parallel.
Phase 4: T038, T039, T040 in parallel.
Phase 5: T045, T046, T050 in parallel.
Phase 6: T054, T055, T058 in parallel.
Phase 7: T062 in parallel with T063 / T064.
Phase 8: T067, T068, T069, T070 in parallel; T071 and T072 in parallel (different OSes).

---

## Implementation Strategy

### MVP scope

MVP requires **all three P1 stories** (US1 + US2 + US3) because they are coupled in real first-use: without US2 there's no way to set up the first connection; without US1 returning users have to reconfigure on every launch; without US3 the implicit-user model the rest of the system will lean on isn't established. Recommended sequence:

1. Phases 1 + 2 (Setup + Foundational) — single developer, sequential where required.
2. Phase 4 (US2 — first-time setup) — **start here**; everything else degrades to "empty state" if US2 isn't done.
3. Phase 5 (US3 — identity) — adds the welcome banner and identity propagation.
4. Phase 3 (US1 — one-click resume) — depends on US2 to have ever saved a connection.
5. **STOP and validate**: run quickstart Q1, Q2, Q3, Q4. Demo-ready MVP.

Note: US3 is sequenced **before** US1 here even though US1 is "the daily driver story" — because once US3 lands, the resume in US1 already comes with identity attached. Doing US1 first would mean a brief window where the resume path didn't carry identity in backend writes.

### Incremental delivery beyond MVP

1. MVP (US1 + US2 + US3) — ship.
2. Add US4 (Neo4j Desktop discovery) — opt-in onboarding boost. No risk to MVP.
3. Add US5 (manage saved connections) — long-term usability. Includes the in-app re-open path.
4. Polish phase items in any order.

### Parallel team strategy

- Day 1: shared completion of Phases 1 + 2.
- Day 2 onwards (with 3 developers):
  - Dev A: US2 (Phase 4) — first-time setup
  - Dev B: US3 (Phase 5) — identity from git
  - Dev C: US1 (Phase 3) — one-click resume (will block briefly on Dev A's `connections:save` for end-to-end test seeding; that's the only cross-story dep)
- Day N: integrate, run Phase 8 polish + quickstart on real mac + win hosts.

---

## Notes

- `[P]` tasks = different files, no incomplete deps.
- Every task here references a concrete file path so it's directly executable by an LLM.
- The settings v1 → v2 migration in T006 is the only foundational task with rollback risk — it modifies the user's existing config file. Keep T007 (its test) as the very next task so the migration's behavior is locked down before T008 wires it into the load path.
- The closed `IpcErrorCode` enum extension in T001 is a single-character correctness gate: if you add a new code in a later task without updating it here first, TypeScript will catch the omission across every handler.
- 023's existing `desktop/tests/smoke/` skeleton from T012 (per 023 phase progress) is the parent of T068 — extend that file rather than creating a parallel smoke harness.
- Web mode (no `window.desktop`) MUST stay first-class — the router guard (T016) is the gate; verify by serving `frontend/` standalone via `npm run dev` after each phase that touches the renderer.
