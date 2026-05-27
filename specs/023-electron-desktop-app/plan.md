# Implementation Plan: Robo-Architect Desktop Application Packaging

**Branch**: `023-electron-desktop-app` | **Date**: 2026-05-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/023-electron-desktop-app/spec.md`

## Summary

Wrap the existing product (FastAPI backend in `api/`, Vue 3 SPA in `frontend/`, Neo4j graph store) in an Electron desktop shell so non-developer users can install and run Robo-Architect from a single signed installer (Windows + macOS) with zero infrastructure setup. The Electron **main process** owns the lifecycle of two child processes — the bundled Python/uvicorn backend and (by default) a bundled Neo4j server — picking free local ports for each, and the **renderer** loads the existing built Vue SPA pointed at `http://127.0.0.1:<backend-port>`. The shell adds: single-instance lock, auto-update (signed), a Settings surface for data-source choice (bundled vs. external Neo4j) and LLM provider/keys (persisted to the OS secure store + the backend's `.env`), crash recovery for the backend child, log-file management with a "Reveal logs" action, and per-user data directories. Web/server deployment continues to be first-class and unchanged; the desktop app is an additional distribution channel. No new FastAPI endpoints and no graph-schema changes — the new surface area is Electron main↔renderer IPC plus a packaging/build pipeline.

## Technical Context

**Language/Version**: TypeScript 5.x (Electron main/preload), Node 20 LTS (Electron 31+ runtime & build tooling); Python 3.11 (unchanged backend, bundled as a self-contained runtime); Vue 3 + Vite 5 (unchanged frontend)
**Primary Dependencies**: Electron 31+, `electron-builder` (packaging — NSIS for Windows, dmg/zip for macOS), `electron-updater` (signed auto-update), Node `get-port`/equivalent (free-port selection), Electron `safeStorage` (+ `keytar` fallback) for secrets; backend deps unchanged (FastAPI, uvicorn, neo4j driver, LangChain/LangGraph); Neo4j Community 5.x + a bundled JRE (for the default bundled-DB mode)
**Storage**: Neo4j (unchanged — single source of truth per Constitution I); bundled per-machine instance by default, configurable external endpoint. Electron-side persisted state (settings, last-used ports, window bounds) in a small JSON file under the per-user app-data dir; secrets in the OS secure store
**Testing**: `pytest` (backend, unchanged); Playwright-for-Electron or Spectron-successor smoke tests for the shell (launch, single-instance, backend-up, clean-shutdown); manual quickstart for packaging/update/signing flows
**Target Platform**: Windows 10/11 (x64), macOS 13+ (Apple Silicon + Intel). Linux out of scope for v1.
**Project Type**: Desktop application (Electron) wrapping a local web service (FastAPI) + SPA (Vue) + bundled database (Neo4j) — a new top-level `desktop/` module alongside `api/` and `frontend/`
**Performance Goals**: First launch (cold, includes Neo4j first-start) interactive < 60 s; subsequent launches interactive < 10 s; clean shutdown leaves 0 app-owned processes after 30 s
**Constraints**: Renderer must not be granted Node integration or remote-content privileges (Constitution-adjacent security requirement FR-021: `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`, strict CSP, `webSecurity: true`); installers & update payloads code-signed (Windows Authenticode, macOS Developer ID + notarization); backend `.env` / provider selection must stay configurable (Constitution VI); SSE/WebSocket from the renderer to `http://127.0.0.1:<port>` must work under the renderer's origin (CORS already permissive backend-side — verify, do not loosen further than needed)
**Scale/Scope**: Single-user-per-installation; one bundled Neo4j per machine; ~handful of new IPC channels; one new top-level module + a build/release pipeline; no change to the ~11 existing backend feature modules or the Vue feature folders

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Graph-as-Source-of-Truth (NON-NEGOTIABLE) | ✅ PASS | Neo4j remains the only model store, accessed only via `api/platform/neo4j.py`. The Electron layer manages the Neo4j *process* and tells the backend which URI to use; it stores **no** domain state. Bundled-vs-external choice is just a connection-string switch. Electron-side JSON state holds only UI/runtime config, never model data. |
| II. Event Storming as Domain Vocabulary | ✅ PASS (N/A) | No new domain concepts, routes, or node labels. The shell is infrastructure. |
| III. Streaming-First UX for Long-Running Work | ✅ PASS | API streaming (SSE/WS) is unchanged; the renderer keeps using `EventSource`/`WebSocket` against the local backend. Design must verify SSE/WS survive the file://-origin → http://127.0.0.1 hop (it does with the existing permissive CORS; a Phase-0 check confirms). No new long-running op is added without streaming. |
| IV. Human-in-the-Loop on Mutations | ✅ PASS (N/A) | No new mutation flows. Existing propose→review→apply endpoints are untouched. |
| V. Feature-Modular Architecture | ✅ PASS (with note) | The Electron shell is **packaging/runtime infrastructure**, not a product feature, so it lives at top level (`desktop/`) the way `docker-compose.yml`, `pyproject.toml`, and `frontend/vite.config.js` do — it does not belong under `api/features/` or `frontend/src/features/`. No cross-feature imports are introduced; the shell talks to the product only over HTTP/WS, exactly like any other client. Recorded in Complexity Tracking for visibility. |
| VI. Provider-Agnostic LLM Runtime | ✅ PASS | `LLM_PROVIDER` / `LLM_MODEL` / `*_API_KEY` stay the configuration mechanism. The Settings UI writes them to the backend's runtime env (and the secrets to the OS secure store); nothing is hardcoded. The bundled backend is the same code reading the same env vars. |
| VII. Observable by Default | ✅ PASS | Backend keeps correlation IDs + `SmartLogger` JSONL. Electron main adds its own structured log file (start/key-decision/error of: port selection, backend spawn, Neo4j spawn, update check/apply, crash/restart). FR-016 surfaces both via "Reveal logs". |

**Technology-constraints check**: `uv` is used to materialise backend deps into the bundled runtime (Constitution: "uv is the primary Python toolchain"). Pydantic request/response models and `docs/cypher/schema/` are untouched. Secrets stay out of git — the shipped `.env` template carries no keys; runtime values come from the Settings UI / OS secure store.

**Development-workflow check**: Spec-driven (this directory). "Every new endpoint in Swagger" — N/A, no new FastAPI endpoints (new surface is IPC, contracted in `contracts/ipc-contract.md`). Graph-schema change — none. Frontend↔backend mirror — N/A, no new feature folder; the renderer reuses the existing `frontend/` build verbatim.

**Result: PASS. No unjustified violations. Proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/023-electron-desktop-app/
├── plan.md                       # This file
├── research.md                   # Phase 0 — decisions D1–D9
├── data-model.md                 # Phase 1 — Electron-side state shapes (no Neo4j changes)
├── quickstart.md                 # Phase 1 — manual smoke (install, run, edit, update, signing, regression)
├── contracts/
│   ├── ipc-contract.md           # Electron main ↔ renderer IPC channels (typed)
│   └── packaging-manifest.md     # build inputs/outputs, signing, update-feed contract
├── checklists/
│   └── requirements.md           # from /speckit-specify (all green)
└── tasks.md                      # Phase 2 — created later by /speckit-tasks
```

### Source Code (repository root)

```text
api/                              # UNCHANGED — bundled as a self-contained runtime at build time
└── ...                           #   (one Phase-0 item: confirm uvicorn entrypoint & env-var contract;
                                  #    a tiny optional health endpoint may be reused — see research.md D5)

frontend/                         # UNCHANGED source; `npm run build` output (frontend/dist) is consumed by the shell
└── ...

desktop/                          # NEW — Electron shell (top-level packaging module)
├── package.json                  # electron, electron-builder, electron-updater, build scripts
├── electron-builder.yml          # win (nsis) + mac (dmg/zip) targets, signing, publish (update feed)
├── tsconfig.json
├── src/
│   ├── main/
│   │   ├── index.ts              # app lifecycle, single-instance lock, BrowserWindow creation
│   │   ├── backend.ts            # spawn/monitor/restart the Python uvicorn child; readiness probe
│   │   ├── neo4j.ts              # bundled Neo4j child lifecycle OR pass-through to external endpoint
│   │   ├── ports.ts              # free-port selection for backend + bolt
│   │   ├── settings.ts           # JSON settings file + OS-secure-store for secrets
│   │   ├── updater.ts            # electron-updater wiring (check/notify/apply, signed)
│   │   ├── logging.ts            # log file location, rotation, "reveal logs"
│   │   ├── data-dir.ts           # resolve per-user data dir; writability fallback/prompt
│   │   └── ipc.ts                # registers IPC handlers from the contract
│   ├── preload/
│   │   └── index.ts              # contextBridge — exposes ONLY the contracted IPC surface to the renderer
│   └── shared/
│       └── ipc-contract.ts       # the TS types that mirror contracts/ipc-contract.md
├── resources/                    # bundled-at-build-time runtime payloads
│   ├── python/                   # self-contained Python + uv-installed backend deps (per-OS)
│   ├── neo4j/                    # Neo4j Community + JRE (per-OS) — present only if "bundled DB" ships (see D2)
│   └── icons/                    # app icons for both platforms
├── scripts/
│   ├── bundle-backend.(sh|ps1)   # build api/ + deps into resources/python via uv
│   ├── bundle-neo4j.(sh|ps1)     # fetch & lay out Neo4j + JRE into resources/neo4j (or download-on-first-run shim)
│   └── build-frontend.(sh|ps1)   # `npm --prefix ../frontend ci && build`, copy dist into the asar payload
└── tests/
    └── smoke.spec.ts             # Playwright-for-Electron: launch, single-instance, backend-up, clean-exit

# UNCHANGED top-level: docker-compose.yml, pyproject.toml, uv.lock, README.md, docs/, .env.example
# .env.example gains documentation of the desktop-mode env contract (no new secrets)
```

**Structure Decision**: A new top-level `desktop/` module mirroring how `frontend/` and `api/` already coexist. The shell is a pure client of the product over HTTP/WS — it imports nothing from `api/` or `frontend/` source; it consumes their *build outputs* (`frontend/dist`, a uv-built `api/` runtime). This keeps the feature-modular boundary intact (Constitution V) and means the desktop feature can be added/removed without touching a single product feature module. CI gains a "desktop build" job; the existing backend/frontend builds are untouched.

## Complexity Tracking

| Item | Why Needed | Simpler Alternative Rejected Because |
|------|------------|-------------------------------------|
| New top-level `desktop/` module (outside `api/features/**` and `frontend/src/features/**`) | Electron packaging is cross-cutting runtime infrastructure that wraps the *entire* product; it is not a product feature with its own router/services/graph nodes | Placing it under a feature folder would (a) imply a domain concept that doesn't exist, (b) tempt cross-feature imports, and (c) break the "features mirror across api/ and frontend/" invariant. Top-level placement matches existing precedent (`docker-compose.yml`, `pyproject.toml`, `frontend/`). |
| Bundling a Neo4j server + JRE inside the installer (default mode) | FR-002 requires zero infra setup for normal use; Constitution I forbids swapping Neo4j for an embedded alternative | "Require Docker / external Neo4j" violates FR-002's zero-setup promise for the target non-developer audience. "Embedded graph library" violates Constitution I (Neo4j via official driver is non-negotiable). Bundling (or first-run-download — see research D2) is the only path that satisfies both. GPLv3 redistribution implications are escalated as a Phase-0 decision, not silently absorbed. |
| Two managed child processes (backend + Neo4j) under the Electron main process, each on a dynamically chosen free port | A desktop app cannot assume fixed ports are free; FR-018 mandates free-port selection; both processes must be started/stopped in lockstep with the window | "Fixed ports + fail if taken" violates FR-018. "Single combined process" is impossible — Neo4j is a separate JVM server and the backend is a separate Python process by design. Lifecycle coupling is inherent, not accidental. |

## Phase Outputs

- **Phase 0 → `research.md`**: decisions D1 (Electron + electron-builder + electron-updater stack & security baseline), D2 (Neo4j: bundle-in-installer vs. download-on-first-run vs. external-only — incl. GPLv3 call), D3 (Python backend packaging: python-build-standalone + uv vs. PyInstaller), D4 (renderer ↔ local-backend wiring & SSE/WS-over-local-origin verification), D5 (backend readiness probe + crash detection/restart policy), D6 (settings & secrets: `safeStorage` vs `keytar`, where the `.env`/env vars are injected), D7 (free-port selection & single-instance handshake), D8 (auto-update channel, signing, notarization, interrupted-update safety), D9 (data-dir resolution, writability fallback, bundled-Neo4j data migration across app versions). Each as Decision / Rationale / Alternatives.
- **Phase 1 → `data-model.md`**: Electron-side persisted/runtime shapes only — `DesktopSettings` (dataSource: bundled|external, externalNeo4j {uri, user}, llm {provider, model}), `RuntimeState` (backendPort, boltPort, backendPid, neo4jPid, status enum), `SecretRef` (which keys live in the secure store). Explicit statement: **no Neo4j schema change, no new Pydantic API models** (per `docs/cypher/schema/` unchanged).
- **Phase 1 → `contracts/ipc-contract.md`**: the typed `main ↔ renderer` channels — e.g. `app:getRuntimeState`, `app:onBackendStatus` (push: starting|ready|crashed|restarting), `settings:get` / `settings:set` / `settings:testNeo4jConnection`, `update:check` / `update:onAvailable` / `update:apply`, `logs:reveal`, `dataDir:get` / `dataDir:choose`. Exposed via `contextBridge` only; renderer gets no Node/`ipcRenderer` raw access.
- **Phase 1 → `contracts/packaging-manifest.md`**: build inputs (frontend/dist, uv-built backend runtime, optional neo4j+JRE, icons), outputs (`.exe`/NSIS, `.dmg`+`.zip`), signing requirements (Authenticode cert, Apple Developer ID + notarization), and the update-feed contract electron-updater consumes (channel layout, `latest.yml`/`latest-mac.yml`, signature verification).
- **Phase 1 → `quickstart.md`**: manual smoke — (1) clean-machine install+launch < 60 s, (2) open existing project / core workflow, (3) close → 0 orphan processes, (4) relaunch → data persists, (5) Settings → switch to external Neo4j → project list reloads, (6) Settings → change LLM provider/key → ingestion uses it, (7) update N→N+1 with data preserved, (8) interrupted update recovers, (9) port-conflict at startup auto-recovers, (10) backend-crash shows recoverable error, (11) signed installer shows no "unidentified developer" warning, (12) 015 terminal / 021 IDE workspace / 016 Figma binding non-regression inside the shell (Windows-PTY limitation noted per research D-terminal).
- **Phase 1 → `CLAUDE.md`** (worktree): SPECKIT markers updated to point at this plan.

## Stop Point

This command stops after Phase 1 design + Phase 2 planning notes above. `tasks.md` is produced by `/speckit-tasks`, not here.
