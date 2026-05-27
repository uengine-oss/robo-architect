---
description: "Task list for 023-electron-desktop-app implementation"
---

# Tasks: Robo-Architect Desktop Application Packaging

**Input**: Design documents from `specs/023-electron-desktop-app/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: No TDD was requested. The only automated test in scope is the Playwright-for-Electron **smoke test** (`desktop/tests/smoke.spec.ts`) named in plan.md / contracts/packaging-manifest.md — it is an implementation task, not a test-first block. All other verification is the manual `quickstart.md`.

**Organization**: Tasks are grouped by user story (US1 P1 = MVP, US2/US3 P2). The `desktop/` module is a new top-level packaging module; `api/` is **unmodified** (bundled as a runtime); `frontend/` gets exactly one functional change (read the injected backend base URL) plus a few Electron-only UI overlays.

**The D2 fork**: Neo4j Community is GPLv3. US1 contains two mutually exclusive variant tasks for how the bundled DB ships — **T021 (VARIANT A: bundle inside the installer)** vs **T022 (VARIANT B: download on first run)**. Implement one; T050 in Polish resolves the choice and deletes the other. Everything else is variant-independent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task in the same phase)
- **[Story]**: US1 / US2 / US3 — user-story phase tasks only

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the new `desktop/` module.

- [x] T001 Create the `desktop/` module structure per plan.md — directories `desktop/src/main/`, `desktop/src/preload/`, `desktop/src/shared/`, `desktop/resources/python/`, `desktop/resources/neo4j/`, `desktop/resources/icons/`, `desktop/scripts/`, `desktop/tests/`
- [x] T002 Initialize `desktop/package.json` — deps: `electron@^31`, `electron-builder`, `electron-updater`, `typescript`, `@playwright/test` (+ Electron support), `get-port`; scripts: `dev`, `build` (tsc), `pack`, `dist` (electron-builder), `test` (playwright)
- [x] T003 [P] Create `desktop/tsconfig.json` — `target: ES2022`, `module: CommonJS`, `strict: true`, separate `outDir` for `src/main` & `src/preload`, include `src/shared`
- [x] T004 [P] Create base `desktop/electron-builder.yml` — `appId`, `productName: "Robo-Architect"`, `directories.output`, `win: { target: nsis }` (per-user, no admin), `mac: { target: [dmg, zip] }`, `asarUnpack: [resources/python/**, resources/neo4j/**]`; signing & `publish` blocks added in later phases
- [x] T005 [P] Create `desktop/src/shared/ipc-contract.ts` — TS types mirroring `contracts/ipc-contract.md`: `DesktopSettings`/`DesktopSettingsWritable`, `RuntimeState` (incl. the `status` & `updateState` enums from data-model.md), `SecretId` union, the per-channel request/response signatures, the closed `IpcErrorCode` enum, and the `{ ok: true; data: T } | { ok: false; error: { code: IpcErrorCode; message: string } }` envelope
- [x] T006 [P] Configure lint/format for `desktop/` — ESLint + Prettier (or reuse the repo's conventions) in `desktop/.eslintrc.cjs` / `desktop/package.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Main-process skeleton, logging, data-dir resolution, IPC plumbing, preload bridge — needed by **every** user story.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [x] T007 Implement the Electron app-lifecycle skeleton in `desktop/src/main/index.ts` — `app.whenReady`, `window-all-closed`, `before-quit`, `activate`; placeholder hooks for startup orchestration (filled in US1)
- [x] T008 [P] Implement `desktop/src/main/logging.ts` — resolve `<dataDir>/logs/`, a structured JSONL log writer with size-based rotation, `revealLogs()` (opens the folder in the OS file manager); used by all subsystems
- [x] T009 [P] Implement `desktop/src/main/data-dir.ts` (basic) — default data root = `app.getPath('userData')`; ensure `logs/` and `neo4j/` subdirs exist; export `getDataDir()`. (Writability fallback + `choose()` land in US1/US3.)
- [x] T010 Implement IPC plumbing in `desktop/src/main/ipc.ts` — `registerHandlers()` that wraps every `ipcMain.handle` in the `{ ok, data } | { ok: false, error }` envelope and maps thrown errors to `IpcErrorCode` (`INTERNAL` fallback, always logged); a `pushToRenderer(channel, payload)` helper for subscription channels. Concrete handlers are registered by their owning story.
- [x] T011 [P] Implement `desktop/src/preload/index.ts` — `contextBridge.exposeInMainWorld('desktop', …)` exposing **only** the contracted channels from `contracts/ipc-contract.md`; subscription channels return an unsubscribe function; no `ipcRenderer`/`require`/`process`/Node API leaks to the renderer
- [x] T012 [P] Add `desktop/tests/smoke.spec.ts` skeleton — Playwright-for-Electron: launch the (dev) app and assert a window opens; assertions are fleshed out in T030

**Checkpoint**: Module skeleton runs; `npm --prefix desktop run dev` opens an empty hardened window.

---

## Phase 3: User Story 1 — One-click install & launch (Priority: P1) 🎯 MVP

**Goal**: A clean-machine user installs a single signed installer (Windows/macOS) and launches a fully working Robo-Architect — backend + Neo4j managed automatically, no infra setup, no terminal, < 60 s to interactive — with the existing product feature set intact, single-instance, clean shutdown, crash-recoverable.

**Independent Test**: On a clean Windows 11 and a clean macOS 13+ machine: run the installer (no "unidentified developer" prompt) → app interactive < 60 s → open an existing project / do one core workflow → close → 0 app-owned processes after 30 s → relaunch → data persists. (quickstart.md Scenarios 1–4, 9, 10, 12.)

### Implementation for User Story 1

- [ ] T013 [P] [US1] Implement `desktop/src/main/ports.ts` — pick N free TCP ports on `127.0.0.1` via ephemeral bind+release; `pickFreePort()` + a small retry helper for "lost the race" re-picks (FR-018)
- [ ] T014 [US1] Implement single-instance behaviour in `desktop/src/main/index.ts` — `app.requestSingleInstanceLock()`; on `second-instance` focus/restore the existing window; if the lock is lost, quit immediately (FR-004)
- [ ] T015 [US1] Implement `BrowserWindow` creation + the `app://` custom protocol in `desktop/src/main/index.ts` — register `app://` to serve `frontend/dist` from the asar; create the window with `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`, `webSecurity: true`, a strict CSP (`connect-src 'self' http://127.0.0.1:* ws://127.0.0.1:*` + Anthropic/OpenAI/Google + Figma origins the product already uses), and `setWindowOpenHandler` that denies new windows and routes http(s) links to the OS browser (FR-021)
- [ ] T016 [P] [US1] Implement `desktop/scripts/build-frontend.sh` and `desktop/scripts/build-frontend.ps1` — `npm --prefix ../frontend ci && npm --prefix ../frontend run build`, then copy `frontend/dist` into the location the asar packs from
- [ ] T017 [US1] Minimal `frontend/` change — introduce a runtime backend base-URL read (new `frontend/src/app/apiBase.js`): if `window.desktop` is present, fetch the port via `window.desktop.app.getRuntimeState()` and use `http://127.0.0.1:<port>`; otherwise keep the dev-time same-origin `/api` (Vite proxy). Route the SPA's `fetch`/`EventSource`/`WebSocket` construction through it. This is the **only** functional `frontend/` change in scope.
- [ ] T018 [P] [US1] Implement `desktop/scripts/bundle-backend.sh` and `desktop/scripts/bundle-backend.ps1` — for each target OS-arch: lay down a relocatable CPython 3.11 (`python-build-standalone`), run `uv` to install deps from the repo `pyproject.toml` + `uv.lock`, copy the `api/` source tree, into `desktop/resources/python/<os-arch>/` (research D3; `api/` itself unmodified)
- [ ] T019 [US1] Implement `desktop/src/main/backend.ts` — spawn `<resources>/python/.../python -m uvicorn api.main:app --host 127.0.0.1 --port <freePort>` with `cwd` set and `env` populated (Neo4j URI/creds from the runtime config, data-dir paths); pipe stdout/stderr into the JSONL log; readiness probe = `GET http://127.0.0.1:<port>/health` with backoff inside a 60 s budget (fall back to TCP-connect + first 200 from any known route if `/health` is absent); emit `starting-backend → ready` (research D5, FR-005)
- [ ] T020 [US1] Implement backend crash detection + restart policy in `desktop/src/main/backend.ts` — on unexpected `exit`/`error`: log the exit code + a tail of stderr, emit `backend-crashed`, attempt ≤ N quick auto-retries on a **fresh** free port (backoff), then surface to the user; `retry()` re-spawns on user request; on app quit do graceful SIGTERM → grace period → SIGKILL (FR-003, FR-017, SC-003)
- [ ] T021 [US1] **[VARIANT A — bundle in installer]** Implement `desktop/scripts/bundle-neo4j.sh` and `.ps1` — fetch Neo4j Community 5.x + a minimal JRE into `desktop/resources/neo4j/<os-arch>/`; add a header comment recording the GPLv3 redistribution sign-off requirement (research D2 ⚠). *Do not implement together with T022 — pick one.*
- [ ] T022 [US1] **[VARIANT B — download on first run]** Implement a first-run Neo4j fetcher in `desktop/src/main/neo4j.ts` + a no-op `desktop/scripts/bundle-neo4j.*` shim — installer ships no DB; on first launch download Neo4j Community + JRE from Neo4j's official distribution into `<dataDir>/neo4j-runtime/`, with a progress UI and checksum verification (research D2). *Do not implement together with T021 — pick one.*
- [ ] T023 [US1] Implement `desktop/src/main/neo4j.ts` (bundled mode core) — on first run generate a random local password and store it via the secure store (interim: a file under the data dir if `settings.ts`/secret store isn't built yet, replaced in US3); spawn the bundled/downloaded Neo4j on a free Bolt port (`ports.ts`) with data dir `<dataDir>/neo4j/`; wait-for-ready by Bolt connect; graceful `neo4j stop` on quit; expose `{ uri: "bolt://127.0.0.1:<port>", user, password, database }` for backend env injection. Emit `starting-db → (then backend can start)` and `db-crashed`/`restarting` analogues of T020
- [ ] T024 [US1] Implement full writability handling in `desktop/src/main/data-dir.ts` — on launch verify the data root is writable; if not, fall back to a writable alternative; if none, prompt the user with a folder picker and persist the choice; (re)ensure subdirs (FR-009 edge case)
- [ ] T025 [US1] Wire startup orchestration in `desktop/src/main/index.ts` — sequence: resolve data dir (T024) → start Neo4j bundled mode (T023) (external-mode pass-through is a stub here, completed in US3) → pick backend port (T013) → start backend (T019) → on backend `ready` load the `app://` window; show a splash overlay until `status === 'ready'`; on `fatal` show the error screen (FR-005, SC-002)
- [ ] T026 [US1] Implement IPC handlers `app:getRuntimeState`, `backend:retry`, `logs:reveal` and push channel `app:onBackendStatus` in `desktop/src/main/ipc.ts`; expose them in `desktop/src/preload/index.ts` (FR-016, FR-017)
- [ ] T027 [US1] Renderer: Electron-only startup overlay in `frontend/src/app/` — a "Starting Robo-Architect…" splash while `status !== 'ready'`; a "Background service stopped — Retry" banner on `backend-crashed`/`db-crashed` (calls `window.desktop.backend.retry()`); a fatal screen with a "Reveal logs" button on `fatal`; subscribes via `window.desktop.app.onBackendStatus`. No-ops when `window.desktop` is absent (web mode)
- [ ] T028 [US1] Finalize `desktop/electron-builder.yml` to produce installers — Windows NSIS (per-user, no admin) + macOS dmg+zip, app icons from `resources/icons/`, `asarUnpack` for `resources/python/**` & `resources/neo4j/**`; wire `desktop/scripts/build-frontend.*`, `bundle-backend.*`, `bundle-neo4j.*` into the `pack`/`dist` npm scripts (run before `electron-builder`)
- [ ] T029 [US1] Add code-signing config to `desktop/electron-builder.yml` — Windows Authenticode (cert from env) + macOS Developer ID **plus notarization + staple** (Apple API key from env); document in `docs/desktop/README.md` (created in T049) that release builds require these secrets. External dependency: certs/Apple API key must exist in the CI secret store (FR-019, SC-001)
- [ ] T030 [US1] Flesh out `desktop/tests/smoke.spec.ts` — launch the packaged app and assert: only one instance runs (second launch focuses the first), backend reaches `ready`, the `app://` window loads the SPA, a clean quit leaves **0** app-owned child processes after the grace period (SC-003)

**Checkpoint**: MVP — a signed installer that, on a clean machine, launches a fully working Robo-Architect. **STOP and run quickstart Scenarios 1–4, 9, 10, 12** before moving on.

---

## Phase 4: User Story 2 — Self-managed updates (Priority: P2)

**Goal**: Users are notified of new releases and can update with one confirmation; the app relaunches on the new version; local data (incl. the bundled Neo4j store) is preserved across updates; interrupted updates never break the install.

**Independent Test**: Install version N, publish N+1 → launch N → "Update available" notification within one launch cycle → postpone (no nag this session) → accept → app relaunches on N+1 with all data intact → (separately) kill mid-download → next launch is still N and re-checks cleanly. (quickstart.md Scenarios 7–8.)

### Implementation for User Story 2

- [ ] T031 [US2] Implement `desktop/src/main/updater.ts` — `electron-updater` wiring against the release feed: check, download (resumable, staged in temp), verify sha512 + code signature, stage; emit `updateState` transitions `idle → checking → available → downloading (progressPercent) → ready-to-install` / `error` (research D8, FR-012, FR-015)
- [ ] T032 [US2] Add the `publish`/feed config to `desktop/electron-builder.yml` — channel root (the "known location" from Q3=A), `latest.yml` / `latest-mac.yml` generation, retention of current + previous artifacts, per `contracts/packaging-manifest.md`
- [ ] T033 [US2] Implement IPC handlers `update:check`, `update:apply` and push channel `app:onUpdateState` in `desktop/src/main/ipc.ts`; expose in `desktop/src/preload/index.ts` (FR-013)
- [ ] T034 [US2] Add the periodic auto-update check in `desktop/src/main/index.ts` — on launch + on an interval; for now unconditionally on (the `settings.update.autoCheck` gate is wired in T046 once `settings.ts` exists)
- [ ] T035 [US2] Renderer: non-blocking update UI in `frontend/src/app/` — "Update available" toast (postpone = no repeat this session, never blocks work), "Restart to update" action (calls `window.desktop.update.apply()`), download progress; subscribes via `window.desktop.app.onUpdateState` (FR-012, FR-013)
- [ ] T036 [US2] Neo4j cross-version migration hook in `desktop/src/main/neo4j.ts` — version-tag the bundled Neo4j data dir; on app upgrade, if the shipped Neo4j major needs a store-format upgrade, run Neo4j's documented upgrade automatically; on failure surface a clear recovery action ("export data / retry / contact") rather than starting empty (FR-014, edge case)
- [ ] T037 [US2] Interrupted-update safety verification — extend `desktop/tests/smoke.spec.ts` (or add a scripted manual step in `quickstart.md`) to confirm that interrupting a download leaves the running version fully intact and the next launch re-checks cleanly (FR-015)

**Checkpoint**: US1 + US2 work; updates flow end-to-end with data preserved.

---

## Phase 5: User Story 3 — Choosing where data lives (Priority: P2)

**Goal**: Users can see and change where their data is stored, point the app at an external shared Neo4j (with connection validation), and configure the LLM provider/model/keys — secrets stored in the OS secure store, never in plaintext config; switching data sources never destroys data and warns the user.

**Independent Test**: From a fresh install: open Settings → data-dir path visible → switch to External Neo4j → enter endpoint + creds → "Test connection" (typed success/error) → save → "viewing a different dataset" warning + project list reloads from the external instance → switch back → original data intact; also: change LLM provider/key → `settings.json` contains provider/model but no key (key is in the OS store) → an LLM feature uses the new provider. (quickstart.md Scenarios 5–6, 11.)

### Implementation for User Story 3

- [ ] T038 [US3] Implement `desktop/src/main/settings.ts` — read/write `<dataDir>/settings.json` (the `DesktopSettings` shape from data-model.md), `schemaVersion` migration on read, atomic write (temp file + rename), corrupt-file → back up to `settings.json.bak` + recreate defaults; never blocks launch
- [ ] T039 [US3] Implement OS-secure-store access in `desktop/src/main/settings.ts` (or a new `desktop/src/main/secrets.ts`) — `safeStorage` primary, `keytar` fallback; `getSecret(id)`/`setSecret(id, value)`/`clearSecret(id)` for the `SecretId` enum; values never logged, never returned to the renderer, never written to `settings.json` (FR-020)
- [ ] T040 [US3] Extend backend env injection in `desktop/src/main/backend.ts` — assemble the child `env` from `settings.ts` + secrets: in external mode `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`/`NEO4J_DATABASE`; `LLM_PROVIDER`/`LLM_MODEL`; `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`GOOGLE_API_KEY`; `FIGMA_API_TOKEN` if present — exactly the names `api/` already reads (Constitution VI). In bundled mode use the locally-generated Neo4j creds from T023. Replace T023's interim password storage with the secure store
- [ ] T041 [US3] Implement external-Neo4j mode in `desktop/src/main/neo4j.ts` — when `settings.dataSource === 'external'`, do **not** spawn the bundled DB; pass the configured endpoint through to backend env; implement `testNeo4jConnection({ uri, user, password, database })` — dial with a short timeout, return typed result mapped to `NEO4J_UNREACHABLE | NEO4J_AUTH_FAILED | NEO4J_TIMEOUT | NEO4J_TLS_ERROR | VALIDATION`; the probe password is not persisted by this call (FR-010)
- [ ] T042 [US3] Implement `choose()` in `desktop/src/main/data-dir.ts` — OS folder picker, validate writable (`DATA_DIR_NOT_WRITABLE` if not), persist to settings, restart the backend pointed at the new location (status cycles via `app:onBackendStatus`) (FR-009)
- [ ] T043 [US3] Implement IPC handlers `settings:get`, `settings:set`, `settings:setSecret`, `settings:testNeo4jConnection`, `dataDir:get`, `dataDir:choose`, `app:openExternal` and push channel `app:onDataSourceChanged` in `desktop/src/main/ipc.ts`; expose in `desktop/src/preload/index.ts`; enforce the `NEOJ4_UNVERIFIED` rule (`settings:set` to external mode requires a successful `testNeo4jConnection` in this session); `app:openExternal` rejects non-http(s) schemes (`BLOCKED_SCHEME`)
- [ ] T044 [US3] Renderer: Settings panel in `frontend/src/app/` (Electron-only) — Data source toggle (Bundled | External) + external Neo4j form (uri/user/password/database + "Test connection" surfacing typed errors) + data-dir display + "Change…" picker + LLM provider/model/key fields (keys display as "configured" / "not configured", never the value) + "Reveal logs" + "Check for updates" + an "About / diagnostics" section (app version, backend & Bolt ports, PIDs, data dir). Round-trips via `window.desktop.settings.*` / `window.desktop.dataDir.*`. No-ops/hidden when `window.desktop` is absent
- [ ] T045 [US3] Renderer: on `app:onDataSourceChanged`, show the "you are now viewing a different dataset" warning and reload the project list from the (now-current) backend; ensure switching modes never deletes either side's data — bundled data stays in `<dataDir>/neo4j/`, external is untouched (FR-011)
- [ ] T046 [US3] Wire the `settings.update.autoCheck` flag into the periodic update check in `desktop/src/main/index.ts` — closes the loop left open in T034
- [ ] T047 [US3] Update `.env.example` — document the desktop-mode env contract (which vars the Electron main process injects into the backend child; that no secrets are stored in this file; secrets live in the OS secure store). No new secret names introduced

**Checkpoint**: US1 + US2 + US3 all work independently; the Settings surface, external Neo4j, and secret handling are complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Release pipeline, docs, the GPLv3 resolution, performance/security review, full quickstart pass.

- [ ] T048 [P] Add a CI "desktop" job — run `desktop/scripts/build-frontend.*`, `bundle-backend.*`, `bundle-neo4j.*`; `tsc`; `desktop/tests/smoke.spec.ts`; `electron-builder` for the CI runner's OS; on a tagged release, sign + (macOS) notarize + publish artifacts and `latest*.yml` to the feed. Build/signing secrets only from the CI vault, never the repo (`contracts/packaging-manifest.md`). Existing backend/frontend CI jobs untouched
- [ ] T049 [P] Write `docs/desktop/README.md` — the desktop build & release runbook: prerequisites, per-OS build steps, signing/notarization setup, publishing a release, rollback (re-point `latest*.yml`)
- [ ] T050 Resolve the Neo4j GPLv3 question (research D2) — confirm redistribution sign-off OR commit to download-on-first-run; keep **either T021 (VARIANT A) or T022 (VARIANT B)**, delete the other variant's task + code path, and record the decision + rationale in `specs/023-electron-desktop-app/research.md` and `plan.md` Complexity Tracking
- [ ] T051 Performance pass — measure cold first-launch (target < 60 s) and warm launch (target < 10 s) to interactive on a representative machine (8 GB RAM, SSD); if needed, start Neo4j and backend concurrently and tune the readiness backoff (FR-005, SC-002)
- [ ] T052 Security review — audit the CSP, `contextIsolation`/`sandbox`/`webSecurity`/`nodeIntegration` settings, the preload surface (confirm no Node/`ipcRenderer` leak, only the contracted channels), `setWindowOpenHandler`, and secret handling (no secret in logs / `settings.json` / IPC); confirm no domain data crosses the IPC boundary (FR-020, FR-021)
- [ ] T053 [P] Update the worktree `CLAUDE.md` if the delivered structure drifts from `plan.md` — keep the `<!-- SPECKIT START/END -->` block and artifact summary accurate
- [ ] T054 Run the full `quickstart.md` — all 12 scenarios on Windows + macOS; file any regressions in 015 Claude Code terminal / 021 IDE workspace / 016 Figma binding (FR-022, FR-023, FR-024, SC-006)
- [ ] T055 Verify the remaining success criteria — clean-machine install timing (SC-001), update-adoption mechanics (SC-004), and wire up whatever tracking is needed for the post-GA support-ticket-reduction metric (SC-008)

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories**.
- **US1 (Phase 3, P1)**: depends on Foundational. This is the MVP.
- **US2 (Phase 4, P2)**: depends on Foundational; in practice builds on US1's `electron-builder` config (signing in T029) and on `neo4j.ts` (T036 migration hook), but the *update flow itself* is independently testable.
- **US3 (Phase 5, P2)**: depends on Foundational; uses US1's `backend.ts`/`neo4j.ts`/`data-dir.ts` (extends them — T040/T041/T042 replace US1's interim stubs). US1 ships with the bundled-mode interim password storage; US3 swaps in the secure store. US3 is independently testable once US1 exists.
- **Polish (Phase 6)**: after the desired user stories. T050 (GPLv3 resolution) can happen any time but **must** happen before release.

### User-story independence

- **US1** stands alone — it's the full desktop app in bundled mode with auto-restart, just with manual updates and no Settings UI for switching data sources.
- **US2** adds the update channel on top of US1.
- **US3** adds the Settings surface (data source, external Neo4j, LLM config, data-dir picker) on top of US1.
- US2 and US3 do not depend on each other and can be built in parallel by different people once US1 is done. The only shared touch-point is `desktop/src/main/index.ts` (T034/T046 — the auto-check gate) and `frontend/src/app/` UI overlays — coordinate edits there.

### Within each story

- `desktop/src/main/*` modules before the orchestration that wires them (T013/T019/T023/T024 before T025).
- IPC handler tasks (T026, T033, T043) before the renderer UI that calls them (T027, T035, T044).
- Build scripts (T016, T018, T021/T022) before `electron-builder` finalization (T028).

### Parallel opportunities

- **Phase 1**: T003, T004, T005, T006 in parallel after T001/T002.
- **Phase 2**: T008, T009, T011, T012 in parallel after T007/T010.
- **Phase 3 (US1)**: T013, T016, T018 in parallel early; T021 **or** T022 (not both); the renderer overlay (T027) in parallel with backend work once T026 exists.
- **Across stories**: after Phase 3, US2 (Phase 4) and US3 (Phase 5) in parallel.
- **Phase 6**: T048, T049, T053 in parallel.

---

## Parallel Example: User Story 1 (after Foundational)

```bash
# Build-pipeline scripts and the ports helper have no interdependencies:
Task: "Implement desktop/src/main/ports.ts (free-port selection)"
Task: "Implement desktop/scripts/build-frontend.{sh,ps1}"
Task: "Implement desktop/scripts/bundle-backend.{sh,ps1}"

# Pick exactly one Neo4j-bundling variant (the GPLv3 fork):
Task: "[VARIANT A] desktop/scripts/bundle-neo4j.{sh,ps1} — bundle Neo4j+JRE into resources/"
#   -- or --
Task: "[VARIANT B] first-run Neo4j fetcher in desktop/src/main/neo4j.ts + shim bundle-neo4j.*"
```

---

## Implementation Strategy

### MVP first (US1 only)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1).
2. **STOP and validate**: run quickstart Scenarios 1–4, 9, 10, 12 on Windows + macOS.
3. Resolve the GPLv3 fork (T050) — needed before shipping the installer.
4. Ship the MVP: signed installer, bundled DB, auto-restart, manual updates, no Settings-UI data-source switching.

### Incremental delivery

1. Setup + Foundational → skeleton.
2. + US1 → **MVP installer** (validate Scenarios 1–4, 9, 10, 12).
3. + US2 → in-app updates (validate Scenarios 7–8).
4. + US3 → Settings / external Neo4j / LLM config / data-dir picker (validate Scenarios 5–6, 11).
5. + Polish → CI pipeline, runbook, perf/security review, full quickstart pass on both OSes.

### Parallel team strategy

- Whole team: Setup + Foundational together.
- Then: Dev A → US1 (the critical path); once US1's `backend.ts`/`neo4j.ts`/`electron-builder.yml` stabilize, Dev B → US2, Dev C → US3. Coordinate edits to `desktop/src/main/index.ts` and `frontend/src/app/` overlays.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task in the same phase.
- `api/` is **not modified** — it is bundled as a runtime; if anything seems to need a backend code change, re-check the design (the env-var contract should cover it).
- `frontend/` gets exactly one functional change (T017, the base-URL read) plus Electron-only UI overlays (T027/T035/T044/T045) that no-op in web mode — web/server deployment stays first-class.
- No new Neo4j schema, no new Pydantic API models, no new HTTP endpoints — the new surface is the IPC contract only.
- Commit after each task or logical group. Stop at any checkpoint to validate a story independently.
