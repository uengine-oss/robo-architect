# Phase 0 Research: Robo-Architect Desktop Application Packaging

**Feature**: `023-electron-desktop-app` | **Date**: 2026-05-11

This resolves the unknowns flagged in `plan.md` → Technical Context. Each decision is **Decision / Rationale / Alternatives considered**. Items that need a human/legal call are marked **⚠ ESCALATE**.

---

## D1 — Desktop shell stack & security baseline

**Decision**: Electron 31+ with `electron-builder` for packaging and `electron-updater` for updates. The renderer `BrowserWindow` is created with `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`, `webSecurity: true`, a strict `Content-Security-Policy` (no inline script beyond what Vite emits; `connect-src` limited to `http://127.0.0.1:* ws://127.0.0.1:*` plus the external endpoints the product already talks to — Anthropic/OpenAI/Google, Figma), and a `setWindowOpenHandler` that denies new windows and routes external links to the OS browser. The preload script exposes **only** the channels in `contracts/ipc-contract.md` via `contextBridge` — the renderer never sees `ipcRenderer`, `require`, or `process`.

**Rationale**: This is the standard hardened Electron configuration; it directly satisfies FR-021 ("window MUST NOT expose privileged OS capabilities to remote content"). `electron-builder` + `electron-updater` are the de-facto pair for signed cross-platform installers with a self-hosted update feed, which matches the Q3=A decision (direct-download + in-app updater, no app stores). The renderer being the existing untouched Vue SPA means CSP must allow exactly the origins the product already uses — nothing more.

**Alternatives considered**: Tauri (smaller binaries, Rust core) — rejected: would require re-validating the entire feature set (015 terminal, 021 IDE, Figma plugin WebSocket) against a different webview/IPC model, and the user explicitly asked for Electron. NW.js — rejected: smaller ecosystem, weaker updater/signing story. Hand-rolled updater — rejected: signature verification and interrupted-update safety (FR-015) are exactly what `electron-updater` already gets right.

---

## D2 — Neo4j in the default "bundled" mode  ⚠ ESCALATE (licensing)

**Decision (primary)**: Ship Neo4j **Community Edition 5.x** plus a minimal bundled JRE inside the installer's `resources/neo4j/`, started by the Electron main process as a child process on a dynamically chosen free Bolt port, with its data directory under the per-user app-data dir (see D9). **Fallback / phased option**: if GPLv3 redistribution is not cleared in time, ship a *download-on-first-run* shim instead — the installer is DB-free, and on first launch the app downloads the Neo4j Community tarball from Neo4j's official distribution into the user's data dir (no redistribution by us), with a clear progress UI. Either way the **external endpoint** mode (FR-010) is always available and unchanged.

**Rationale**: FR-002 (zero infra setup for normal users) and Constitution I (Neo4j is the non-negotiable source of truth, via the official driver — *not* swappable for an embedded library) together force "the app must produce a working Neo4j without the user doing anything". Bundling is the lowest-friction way; download-on-first-run is the licensing-safe fallback that still hits "zero setup" (one-time download is automatic). The external mode covers teams (Q1=A: shared-backend mode is in scope).

**Alternatives considered**: Embed an alternative graph engine — **rejected, violates Constitution I**. Require Docker / pre-installed Neo4j — rejected, violates FR-002 for the target non-developer audience. Neo4j Enterprise embedded — rejected: licensing cost, still a JVM, and Community is sufficient for single-user. Bundle Neo4j *with* its own JRE vs. require a system Java — bundling the JRE chosen so the user truly needs nothing pre-installed (FR-001/FR-002).

**Open item for the team**: confirm GPLv3 redistribution of Neo4j Community inside our signed installer is acceptable (it is widely done — e.g. Neo4j Desktop ships it — but our distribution terms must say so), OR commit to the download-on-first-run fallback. This is the single biggest scoping fork in the feature; `/speckit-tasks` should branch on it.

---

## D3 — Packaging the Python/FastAPI backend

**Decision**: Build a **self-contained Python runtime** at `desktop/resources/python/<os>` using `python-build-standalone` (a relocatable CPython 3.11) into which `uv` installs the backend's pinned dependencies from `pyproject.toml` / `uv.lock`, plus the `api/` source tree. The Electron main process launches it as `<resources>/python/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port <free-port>` with `cwd` set so relative paths resolve, and with the runtime env populated (Neo4j URI/creds, `LLM_*`, data-dir paths) from Settings. The build script is `desktop/scripts/bundle-backend.(sh|ps1)` and runs per target OS.

**Rationale**: `uv` is mandated as the primary Python toolchain by the constitution, so the bundle must be uv-built — `python-build-standalone` + `uv` keeps the dependency resolution identical to dev. Launching real `uvicorn` (rather than freezing into one binary) keeps the backend behaviour bit-for-bit identical to the web/server deployment (Q1=A: both modes first-class), and keeps `api/` completely untouched. PyMuPDF and the LangChain stack have native wheels that are far more reliable under a real interpreter than under a PyInstaller freeze.

**Alternatives considered**: PyInstaller `--onedir`/`--onefile` — rejected: chronic pain with PyMuPDF / native deps / dynamic imports in LangChain; harder to keep parity with the server build. Bundle the user's system Python — rejected: violates FR-001/FR-002 (the user must need nothing). Run the backend in WSL/Docker on Windows — rejected: heavyweight, defeats the point.

---

## D4 — Renderer ↔ local backend wiring; SSE/WebSocket over the local origin

**Decision**: The renderer loads the built Vue SPA from a custom `app://` protocol (registered in main, serving `frontend/dist` from the asar) — *not* `file://`, so the origin is stable and CSP-able. The main process injects the chosen backend port into the renderer **before first paint** via the preload bridge (`app:getRuntimeState` returns `{ backendPort, ... }`); the SPA reads it and points its API/SSE/WS base at `http://127.0.0.1:<backendPort>`. Phase-0 verification confirms: `EventSource` and `WebSocket` from the `app://` origin to `http://127.0.0.1:<port>` work because the backend already sets permissive CORS (`CORSMiddleware`) and SSE/WS are not blocked by CSP `connect-src` once `http://127.0.0.1:* ws://127.0.0.1:*` is allowlisted. **Small touch on `frontend/`**: the SPA currently relies on Vite's dev proxy (`/api → 127.0.0.1:8000`); for the packaged build it must read the injected base URL instead of assuming a same-origin `/api`. This is a minimal, isolated change (a runtime config read) and is the *only* `frontend/` change in scope.

**Rationale**: Constitution III (streaming-first) means SSE/WS must keep working — this is the highest-risk integration point, so it's verified in Phase 0, not assumed. Using `app://` instead of `file://` avoids the well-known `file://`-origin quirks (opaque origin, `EventSource` edge cases, CSP weirdness). Injecting the port via the preload bridge (vs. an env var or query string) keeps it inside the contracted, type-checked surface.

**Alternatives considered**: Serve the SPA from the FastAPI backend itself (`StaticFiles` mount) so everything is same-origin `http://127.0.0.1:<port>` — viable and even simpler for CORS, but it changes the backend's responsibilities and the server deployment (which serves the SPA separately today); kept as a fallback if `app://` proves troublesome, but the default keeps `api/` untouched. Hardcode a port — rejected (FR-018). Pass the port as a URL query param — rejected: leaks into history/links, not type-checked.

---

## D5 — Backend readiness probe, crash detection, restart policy

**Decision**: After spawning the backend, main polls `GET http://127.0.0.1:<port>/health` (the existing `health` feature router — confirm path; if absent, the readiness signal is the first successful TCP connect + a 200 from any known route) with backoff up to a 60 s budget; the renderer shows a "Starting Robo-Architect…" splash until ready (FR-005). Main attaches to the child's `exit`/`error` events and to a periodic liveness ping; on unexpected exit it (a) logs the exit code + tail of backend stderr, (b) emits `app:onBackendStatus = "crashed"` to the renderer, which shows a recoverable banner ("Background service stopped — Retry"), and (c) on user "Retry" (or up to N automatic quick retries with backoff) re-spawns on a *fresh* free port. Neo4j gets the same treatment. On window close / `before-quit`, main sends graceful shutdown (SIGTERM / Neo4j `stop`), waits a grace period, then SIGKILL, guaranteeing FR-003 / SC-003.

**Rationale**: FR-017 mandates a recoverable error on backend crash rather than a frozen window; FR-003/SC-003 mandate zero orphans on exit; FR-005 mandates < 60 s to interactive. A readiness probe + explicit lifecycle hooks are the minimal mechanism that delivers all three. Re-spawning on a *new* free port avoids "port still in TIME_WAIT" flakiness.

**Alternatives considered**: Assume the backend is up after a fixed sleep — rejected: races on slow machines, wastes time on fast ones. No auto-restart, only manual — rejected: a transient crash shouldn't require the user to understand what happened; a couple of silent quick retries first, then surface it. Detach the children so they outlive the window — rejected: directly violates FR-003.

---

## D6 — Settings & secrets storage; where env vars are injected

**Decision**: Non-secret settings (data-source choice, external Neo4j URI + username, `LLM_PROVIDER`, `LLM_MODEL`, window bounds, last-used ports) live in a single JSON file in the per-user app-data dir. Secrets (external Neo4j password, `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY`, `FIGMA_API_TOKEN` if present) are stored via Electron `safeStorage` (which uses the OS keychain/DPAPI under the hood); `keytar` is the fallback only if `safeStorage` is unavailable on a given platform build. When main spawns the backend, it materialises these into the child's **environment variables** (not a written-to-disk `.env` containing keys — the shipped `.env.example`/`.env` stays key-free), exactly the names the backend already reads (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `LLM_PROVIDER`, `LLM_MODEL`, `*_API_KEY`, …). The Settings UI in the renderer round-trips through `settings:get`/`settings:set`; `settings:testNeo4jConnection` asks main to dial the endpoint and report success/typed error before persisting (FR-010).

**Rationale**: FR-020 requires secrets in the OS secure store, not plaintext config. Constitution VI requires provider/model/keys to stay env-configurable and not hardcoded — injecting them as env vars into the unchanged backend satisfies both, and means the backend code needs *no* awareness it's running under Electron. Validating the Neo4j connection before saving (FR-010) prevents the app from getting stuck pointed at a dead endpoint.

**Alternatives considered**: Write a full `.env` (with keys) into the data dir — rejected, violates FR-020. Keep secrets in the JSON settings file — rejected, same. Have the backend read settings directly from the Electron settings file — rejected: couples the backend to the shell and breaks Constitution V's boundary; env vars are the existing, clean contract.

---

## D7 — Free-port selection & single-instance handshake

**Decision**: On launch, main calls `app.requestSingleInstanceLock()`; if it loses the lock it focuses the existing window and exits (FR-004). The winner picks two free TCP ports on `127.0.0.1` (one for uvicorn, one for Neo4j Bolt) by binding ephemeral sockets and immediately releasing them, then passes them to the respective child spawns; the chosen ports are recorded in `RuntimeState` and surfaced to the renderer via `app:getRuntimeState`. If a child fails to bind its assigned port (lost a race), main retries with a fresh port up to a small limit before surfacing an error (FR-018).

**Rationale**: FR-004 (single instance, focus existing) and FR-018 (free-port selection, never fail on a busy default) are both explicit; `requestSingleInstanceLock` + ephemeral-bind port discovery is the standard, minimal implementation.

**Alternatives considered**: A fixed port with "is it the same app? then focus it" detection — rejected: brittle, and FR-018 forbids fixed ports. A file-lock-based single-instance scheme — rejected: Electron's built-in lock handles the second-launch → focus-first-window flow for free.

---

## D8 — Auto-update channel, signing, notarization, interrupted-update safety

**Decision**: `electron-updater` checking a self-hosted update feed (the "known location" from Q3=A — e.g. an HTTPS bucket/site holding `latest.yml` / `latest-mac.yml` + the installers). On launch (and on a periodic timer) main checks for a newer version; if found, it emits `update:onAvailable` and the renderer shows a non-blocking notification; on user confirm, `electron-updater` downloads (resumable), **verifies the signature**, and stages it, then prompts to restart-and-install (FR-012/FR-013/FR-015). Windows builds are Authenticode-signed; macOS builds are Developer ID-signed **and notarized + stapled** so Gatekeeper shows no "unidentified developer" warning (FR-019). An interrupted download leaves the running version fully intact (electron-updater stages into a temp area and only swaps on a verified, complete payload), and the next launch simply re-checks — never a half-updated state (FR-015).

**Rationale**: Q3=A picked direct-download + in-app updater with no app stores — `electron-updater` is exactly that. FR-015's "cryptographically verified" and "never unusable after interruption" are core electron-updater behaviours. FR-019's "no unidentified-developer warning" requires Authenticode on Windows and Developer-ID-**plus-notarization** on macOS (signing alone is insufficient on modern macOS).

**Alternatives considered**: Mac App Store / Microsoft Store auto-update — explicitly out of scope per Q3=A. A custom updater — rejected (see D1). Squirrel.Windows directly — rejected: `electron-updater` wraps it with better cross-platform ergonomics and signature checks. Differential updates — nice-to-have, not required for v1; can be enabled later via the same feed.

---

## D9 — Data directory resolution, writability fallback, bundled-Neo4j migration across app versions

**Decision**: The default data root is the OS-conventional per-user location (`app.getPath('userData')` → e.g. `%APPDATA%/Robo-Architect` on Windows, `~/Library/Application Support/Robo-Architect` on macOS), holding: `neo4j/` (bundled DB data, if in bundled mode), `logs/`, `settings.json`. The path is shown in Settings (FR-009). On launch main checks the dir is writable; if not (locked-down account, read-only volume), it falls back to a writable alternative and, if none, prompts the user to choose one, persisting the choice (FR-009 edge case). The bundled Neo4j data dir is **version-tagged**; on app upgrade, if the new app ships a Neo4j major that needs a store-format upgrade, main runs Neo4j's documented upgrade path automatically; if that fails it surfaces a clear recovery action ("export data / retry / contact") rather than starting empty (FR-014, edge case). Switching between bundled and external modes never deletes either side's data and warns the user they're now viewing a different dataset (FR-011).

**Rationale**: FR-008/FR-009 (persist across sessions & updates, surface the location), FR-011 (no silent data loss on mode switch), FR-014 (data preserved across updates, guided migration) and the writability + migration edge cases all point at: a well-known per-user dir, a writability guard with fallback, and a version-aware Neo4j data dir with an explicit upgrade step. Using Electron's `getPath('userData')` gives the OS-conventional location for free.

**Alternatives considered**: Store data next to the app install (`Program Files` / `/Applications`) — rejected: not writable for standard users, blown away on uninstall/upgrade. A single opaque blob instead of a directory — rejected: makes "Reveal logs", manual backup, and migration impossible. Auto-migrate with no failure path — rejected: a failed store upgrade must not look like "all your projects vanished".

---

## D-terminal — 015 Claude Code terminal on Windows (known limitation)

**Decision**: The 015 terminal feature uses POSIX `pty`/`os.fork` and is already gated by `IS_UNIX_PTY_SUPPORTED = os.name == "posix"` in `api/features/claude_code/router.py`. The desktop app **preserves current behaviour**: the terminal works on macOS and is unavailable on Windows in v1 — FR-022 says "continue to" attach/control terminal sessions, i.e. no regression, not new platform support. The Windows-PTY gap (would need `pywinpty`/ConPTY) is recorded as a known limitation and a candidate for a follow-up spec; the quickstart's Windows pass explicitly checks the rest of the product works and the terminal degrades gracefully (clear "not available on Windows" message), not silently.

**Rationale**: Adding Windows PTY support is its own piece of work touching the backend feature, not the packaging feature; the spec's compatibility requirements are about *not regressing*, which this satisfies. Flagging it keeps the limitation visible instead of surprising a Windows user.

**Alternatives considered**: Block the Windows build until PTY parity exists — rejected: the other ~10 features are valuable on Windows now; one feature being macOS-only shouldn't gate the whole desktop offering. Quietly hide the terminal on Windows — rejected: a clear "not available on this platform" message is better UX and matches the spec's "clear offline/unavailable state" pattern.

---

## Resolved unknowns summary

| Technical-Context unknown | Resolved by |
|---------------------------|-------------|
| Desktop shell framework & security config | D1 |
| How Neo4j ships in "bundled" mode (+ licensing) | D2 ⚠ |
| How the Python backend is packaged | D3 |
| Renderer ↔ local backend wiring; SSE/WS over local origin | D4 |
| Backend readiness / crash / restart / shutdown | D5 |
| Settings & secrets storage; env-var injection | D6 |
| Free-port selection & single-instance | D7 |
| Auto-update, signing, notarization, interrupted-update safety | D8 |
| Data dir, writability fallback, Neo4j cross-version migration | D9 |
| 015 terminal on Windows | D-terminal |

**One escalation outstanding (D2 — Neo4j GPLv3 redistribution).** `/speckit-tasks` should produce two task variants for the DB-bundling slice (bundle-in-installer vs. download-on-first-run) and let the team pick once licensing is confirmed. Everything else is decided.
