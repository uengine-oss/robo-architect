# Implementation Plan: Desktop Startup Connection, Identity & Project Picker

**Branch**: `032-desktop-startup-picker` | **Date**: 2026-05-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/032-desktop-startup-picker/spec.md`

## Summary

032 adds the **first user-visible screen of the Electron desktop build**: a launcher that (1) resolves the session user from `git config`, welcomes them by name, (2) lists saved + discovered Neo4j connections with status badges and supports add/edit/delete, (3) lets the user pick a project root, and (4) hands off the chosen `(connection, project root, user identity)` triple to the main SPA. Identity is then propagated to every backend write via two HTTP headers, laying the foundation for a follow-up audit/history feature.

**Technical approach in one paragraph.** The launcher reuses the existing Electron `BrowserWindow` from feature 023; instead of loading the main SPA route on startup, the main process loads a launcher route (`/__launcher`) inside the same renderer. The Vue launcher view is a new feature module (`frontend/src/features/desktop-launcher/`). It calls new IPC channels (`launcher:*`, `connections:*`, `projectRoot:*`, `identity:*`) added to the existing `window.desktop` bridge. Saved connections + recent project roots live in the existing `DesktopSettings` JSON (schemaVersion 1 → 2 with migration of the existing `externalNeo4j` into the saved list). Passwords stay in the existing OS keychain via `SecretRef`. Neo4j Desktop discovery is a read-only filesystem scan of Neo4j Desktop's well-known per-user config directory on macOS and Windows. Git identity comes from spawning `git config --get user.name` / `user.email` with `cwd = selectedProjectRoot`. After **Enter**, the renderer navigates to the main app route and a session-wide Pinia store holds the resolved identity, which a fetch/axios interceptor attaches to every outgoing request as `X-User-Name` + `X-User-Email`. A small FastAPI middleware in `api/platform/identity/` reads those headers into `request.state.actor` (logged, not yet persisted — that's the follow-up history spec).

## Technical Context

**Language/Version**: TypeScript 5.x (Electron main + preload + renderer-side shared types), Vue 3 + Vite (renderer SPA), Python 3.11+ (FastAPI middleware addition only).

**Primary Dependencies**: Existing — Electron 31 + `electron-builder` + `electron-updater` (from 023), Vue 3 + Vue Router + Pinia, FastAPI. New runtime dependencies: **none** (`safeStorage`/`keytar` already in 023 for secrets; `child_process.spawn` for git; native `fs/promises` for Neo4j Desktop config; native `dialog.showOpenDialog` for the folder picker). New dev dependency: none (Vitest already present from 023).

**Storage**: No Neo4j schema change. Persisted desktop settings (`<dataDir>/settings.json`) gain new fields `savedConnections`, `recentProjectRoots`, `lastProfile`; `schemaVersion` bumps to 2 with migration of pre-existing `externalNeo4j`. Passwords remain in OS secure storage indexed by a new `SecretId` family (`connection.<id>.password`).

**Testing**: Vitest for main-process unit tests (git resolver, Neo4j Desktop config parser, settings migration), Playwright/Spectron-style smoke for the launcher flow (existing 023 smoke-test skeleton extended), pytest for the FastAPI identity middleware. No new contract-test framework.

**Target Platform**: Electron desktop build, Windows 10+ and macOS 12+ (per 023). Web/server mode unchanged — launcher is gated by `process.versions.electron` presence in main and by `window.desktop` presence in renderer.

**Project Type**: Desktop application slice (Electron main + preload) feeding an existing Vue 3 SPA, plus a small backend platform middleware.

**Performance Goals**:
- Launcher interactive ≤ 1.5 s of cold-process spawn on reference hardware (SC-008).
- Status probe completes/times out in ≤ 5 s (SC-005).
- Git identity resolved ≤ 1 s of launcher paint (SC-009).
- Neo4j Desktop discovery returns or fails-silently in ≤ 2 s.

**Constraints**:
- **No new HTTP endpoint** on the backend for launcher behavior itself (FR-034). Identity middleware is platform plumbing, not a feature endpoint.
- **No raw `ipcRenderer` / Node leak** to the renderer — extend `window.desktop` only (preserves 023's FR-021).
- **No plaintext password** anywhere on disk or in logs (FR-019, SC-004).
- **Single-instance lock** (existing 023 design) — launcher must not double-render.
- **Web mode untouched** — `frontend/src/main.js` must not import launcher code in a way that pulls Electron deps into the web bundle.

**Scale/Scope**: Per-user; typical user has 1–10 saved connections, 1–20 recent project roots. Neo4j Desktop discovery typically returns < 10 DBMSs. No multi-tenant concerns.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Graph-as-Source-of-Truth | ✅ Pass | Saved connections + project-root history are *configuration*, not domain state — they live in the user's `settings.json`, not in a parallel domain store. No Neo4j writes are added by 032. |
| II. Event Storming as Domain Vocabulary | ✅ N/A | Launcher is infra/identity; no domain-modeling surface. |
| III. Streaming-First UX for Long-Running Work | ✅ Pass | Launcher operations (probe, test, discovery, identity resolve) are all bounded ≤ 5 s. Streaming would be ceremony without value. |
| IV. Human-in-the-Loop on Mutations | ✅ Pass | The launcher *is* the human-in-the-loop for choosing connection + project root. The identity middleware propagates an attribution but does not auto-mutate. |
| V. Feature-Modular Architecture | ✅ Pass | Frontend code under `frontend/src/features/desktop-launcher/`. Electron code under `desktop/src/main/launcher/` + sibling modules. Backend has **no new feature** — only a platform-layer middleware under `api/platform/identity/`, which is the constitutionally correct location for cross-cutting concerns. |
| VI. Provider-Agnostic LLM Runtime | ✅ N/A | No LLM access in 032. |
| VII. Observable by Default | ✅ Pass | Launcher emits JSONL events via the existing `desktop/src/main/logging.ts` at: launcher-open, identity-resolved, discovery-attempt, connection-test, enter. Identity middleware logs the resolved actor on each backend request with the existing correlation ID. |
| VIII. Figma SceneGraph Generation Pipeline | ✅ N/A | No Figma sceneGraphs. |
| IX. Plugin ↔ Backend Dev-Loop Discipline | ✅ N/A | No Figma plugin code. |

**Result**: All gates pass. No Complexity Tracking entry required.

### Cross-cutting note: platform-layer middleware

Adding `api/platform/identity/middleware.py` is the correct shape under Principle V — it's a cross-cutting concern (every feature's writes need attribution) and the constitution explicitly says cross-feature dependencies go through `api/platform/` rather than direct sibling imports. The middleware is registered once in `api/main.py`; individual feature routers do not import it. This avoids creating a "032 feature module" on the backend side just to hold one middleware file.

## Project Structure

### Documentation (this feature)

```text
specs/032-desktop-startup-picker/
├── plan.md                              # This file
├── spec.md                              # Feature spec (already exists)
├── research.md                          # Phase 0 — decisions on Neo4j Desktop discovery, git resolution, launcher-render strategy
├── data-model.md                        # Phase 1 — SavedConnection, DiscoveredConnection, ProjectRootEntry, LaunchProfile, SessionUser, settings v2 migration
├── quickstart.md                        # Phase 1 — manual smoke scenarios across mac + win
├── contracts/
│   ├── launcher-ipc-contract.md        # New IPC channels: connections:*, projectRoot:*, identity:*, launcher:*
│   └── identity-header-contract.md     # X-User-Name / X-User-Email request envelope
├── checklists/
│   └── requirements.md                  # already created by /speckit-specify
└── tasks.md                             # Phase 2 — created by /speckit-tasks
```

### Source Code (repository root)

```text
desktop/                                  # Existing 023 module — EXTENDED
├── src/
│   ├── main/
│   │   ├── index.ts                     # MODIFIED — load launcher route first, register new IPC handlers, single-instance refocus
│   │   ├── backend.ts                   # MODIFIED — accept LaunchProfile on hand-off; expose chosen Neo4j to backend env
│   │   ├── ipc.ts                       # MODIFIED — register launcher/connections/projectRoot/identity handlers
│   │   ├── data-dir.ts                  # unchanged (used as-is)
│   │   ├── logging.ts                   # unchanged
│   │   ├── ports.ts                     # unchanged
│   │   └── launcher/                    # NEW
│   │       ├── connections.ts           # SavedConnection CRUD + OS-keychain glue
│   │       ├── discovery.ts             # Neo4j Desktop read-only filesystem scan
│   │       ├── identity.ts              # git config resolver
│   │       ├── project-root.ts          # folder picker + validation + recent history
│   │       ├── settings-migrate.ts      # schemaVersion 1 → 2 migration (externalNeo4j → first SavedConnection)
│   │       └── launcher-state.ts        # in-memory state machine: pending → entered
│   ├── preload/
│   │   └── index.ts                     # MODIFIED — extend window.desktop with launcher / connections / projectRoot / identity surfaces
│   └── shared/
│       ├── ipc-contract.ts              # MODIFIED — bump schemaVersion type, add new IpcRequestMap entries
│       └── launcher-contract.ts         # NEW — SavedConnection, DiscoveredConnection, ProjectRootEntry, LaunchProfile, SessionUser types
└── tests/
    ├── unit/
    │   ├── identity.test.ts             # NEW — git config parsing + precedence
    │   ├── discovery.test.ts            # NEW — Neo4j Desktop relate.config.json parsing
    │   ├── settings-migrate.test.ts     # NEW — v1 → v2 migration shapes
    │   └── connections.test.ts          # NEW — CRUD round-trip
    └── smoke/
        └── launcher-flow.smoke.ts       # NEW — Playwright/Spectron-style end-to-end happy path

frontend/                                 # Existing Vue 3 SPA — EXTENDED
├── src/
│   ├── app/
│   │   ├── router.js                    # MODIFIED — add `/__launcher` route, gate main routes behind `useSession().entered`
│   │   ├── http.ts                      # NEW (or MODIFIED if a fetch wrapper already exists) — request interceptor injecting X-User-Name / X-User-Email
│   │   └── layout/TopBar.vue            # MODIFIED (small) — display session user name on top-right when desktop mode
│   ├── features/
│   │   └── desktop-launcher/            # NEW
│   │       ├── LauncherView.vue         # Top-level launcher screen
│   │       ├── components/
│   │       │   ├── WelcomeBanner.vue
│   │       │   ├── ConnectionList.vue
│   │       │   ├── ConnectionForm.vue
│   │       │   ├── DiscoveredSection.vue
│   │       │   ├── ProjectRootPicker.vue
│   │       │   └── EnterAction.vue
│   │       └── stores/
│   │           ├── launcher-store.ts    # Pinia store for launcher state
│   │           └── session-store.ts     # Pinia store for hand-off identity + connection + project root (read by http.ts interceptor)
│   └── main.js                          # MODIFIED — install session store + http interceptor; conditionally route to /__launcher when window.desktop

api/                                      # Existing FastAPI backend — MINIMALLY EXTENDED
├── main.py                              # MODIFIED — register IdentityMiddleware
└── platform/
    └── identity/                        # NEW (platform-layer, not a feature)
        ├── __init__.py
        ├── middleware.py                # Reads X-User-Name / X-User-Email → request.state.actor; falls back to unknown@<hostname>
        └── models.py                    # Actor pydantic model (name, email, source)

tests/                                    # MINIMALLY EXTENDED
└── platform/
    └── test_identity_middleware.py      # NEW — header parsing, fallback, log-line presence
```

**Structure Decision**: Extend the existing 023 Electron module + the existing Vue 3 SPA in place. No new feature directory on the backend; the only backend addition is a single platform middleware under `api/platform/identity/`, consistent with constitution Principle V's "cross-feature dependencies go through the platform layer." Identity is cross-cutting (every feature's writes need attribution), so it belongs in `platform/`, not in a 032-named feature folder that would mislead future readers into thinking 032 owns history persistence (it doesn't — that's a follow-up spec).

## Phase 0: Outline & Research

Research questions resolved in [research.md](research.md):

1. **Launcher render strategy** — separate `BrowserWindow` vs same-window route. **Decision: same-window Vue route** (`/__launcher`), navigated to `/` after **Enter**. Reuses existing renderer, simpler hand-off, no second window flash.
2. **Neo4j Desktop config layout (macOS + Windows)** — schema of `relate.config.json` and per-DBMS `neo4j.conf`, what's stable across Neo4j Desktop versions, what's read-only-safe. **Decision: parse `relate.config.json` for DBMS list, read per-DBMS `neo4j.conf` for `dbms.connector.bolt.listen_address`; fail silently on any schema mismatch or unreadable file.**
3. **Git identity resolution mechanism** — `child_process.spawn("git", ["config", "--get", "user.name"])` vs reading `.gitconfig` files directly. **Decision: spawn `git config` with explicit `cwd` = selected project root + 2 s timeout; bounded, respects all precedence rules natively, no need to re-implement git's config algorithm.**
4. **Settings schemaVersion migration** — v1 (existing 023) has `externalNeo4j: ExternalNeo4jConfig | null`. v2 introduces `savedConnections: SavedConnection[]`, `recentProjectRoots: string[]`, `lastProfile: { connectionId, projectRoot } | null`. **Decision: in-place migration on first read after upgrade; pre-existing `externalNeo4j` becomes a SavedConnection with `source: 'manual-migrated-from-023'` and the existing keychain entry `neo4j.password` is re-keyed to `connection.<newId>.password`. The legacy `externalNeo4j` field is kept (as null) for one version for forward-rollback safety, then removed in v3.**
5. **Identity propagation envelope** — header pair vs JWT vs structured cookie. **Decision: two plain HTTP request headers `X-User-Name` (UTF-8 percent-encoded), `X-User-Email`. Simplest possible; no token, no expiry, no signing — matches the trust model that "git user is the user" (anyone with shell access can already lie).**
6. **Folder picker behavior across mac + win** — sandbox/permissions implications. **Decision: `dialog.showOpenDialog({ properties: ['openDirectory'] })` is sufficient on both targets; Electron 31 inherits the calling-user's filesystem permissions, no special entitlements required.**
7. **What happens to the existing `Settings` panel from 023 once the launcher exists?** **Decision: Settings panel stays accessible inside the main app for *changing* the active connection (re-opening launcher modally) and for LLM key entry. The launcher is the entry point; Settings is the in-app re-entry. No code duplication — Settings invokes the same launcher store.**

## Phase 1: Design & Contracts

**Prerequisites:** Phase 0 [research.md](research.md) complete.

Artifacts produced in this phase:

- [data-model.md](data-model.md) — concrete TypeScript shapes for `SavedConnection`, `DiscoveredConnection`, `ProjectRootEntry`, `LaunchProfile`, `SessionUser`; updated `DesktopSettings` v2 schema + migration table; OS-keychain key naming convention.
- [contracts/launcher-ipc-contract.md](contracts/launcher-ipc-contract.md) — every new IPC channel: name, request type, response type, error codes (extends the closed `IpcErrorCode` enum). Marks which channels are pure reads vs writes vs filesystem-touching.
- [contracts/identity-header-contract.md](contracts/identity-header-contract.md) — `X-User-Name` / `X-User-Email` wire format, encoding rules, middleware fallback rule (`unknown@<hostname>`), what gets logged.
- [quickstart.md](quickstart.md) — 8 manual smoke scenarios spanning mac + win covering US1–US5, web-mode-unaffected, schemaVersion migration, and unknown-user fallback.

**Agent context update**: `CLAUDE.md` (project root) currently points its "active feature plan" at the 023 plan. After this phase the marker between `<!-- SPECKIT START -->` and `<!-- SPECKIT END -->` (or the existing pointer line) is updated to reference [specs/032-desktop-startup-picker/plan.md](plan.md). The line currently reads "Active feature plan: [specs/023-electron-desktop-app/plan.md](specs/023-electron-desktop-app/plan.md)" — replace with the 032 pointer.

### Re-evaluated Constitution Check (post-design)

After Phase 1 artifacts:

- **Principle I (Graph-as-Source-of-Truth)**: still ✅ — no domain writes added by 032; identity middleware annotates `request.state.actor` but does not persist anything to Neo4j (that's the follow-up history spec).
- **Principle V (Feature-Modular)**: still ✅ — the backend addition is platform-layer only (`api/platform/identity/`), and `api/main.py` is the canonical place to register middleware (every other middleware lives there). No cross-feature import added.
- **Principle VII (Observable)**: design adds three new JSONL events from `desktop/src/main/launcher/*` and one log line per request from the identity middleware — all carrying the existing correlation ID. ✅

No new violations. No Complexity Tracking entries needed.

## Complexity Tracking

*Not applicable — Constitution Check passes with zero violations.*
