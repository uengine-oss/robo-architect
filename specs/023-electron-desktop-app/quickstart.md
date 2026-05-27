# Quickstart / Manual Smoke: Robo-Architect Desktop Application

**Feature**: `023-electron-desktop-app` | **Date**: 2026-05-11

Run on a **clean** Windows 11 machine and a **clean** macOS 13+ machine (Apple Silicon; an Intel pass is a bonus) — "clean" = no Python, Node, Neo4j, Java, or prior Robo-Architect install. Each scenario maps to spec FRs/SCs in brackets.

---

### Scenario 1 — One-click install & first launch [FR-001, FR-002, FR-005, SC-001, SC-002, FR-019]
1. Download the OS's installer from the release channel; run it. → No SmartScreen/Gatekeeper "unidentified developer" prompt; install completes via the normal OS flow without admin rights (Windows per-user NSIS) and without any "install Python/Neo4j" step.
2. Launch the app. → A "Starting Robo-Architect…" splash appears, then the home screen becomes interactive within **60 s** (cold first launch, includes Neo4j first-start). Time it.
3. No terminal was opened, no env file edited, no config touched. ✅ if all true.

### Scenario 2 — Core workflow parity [FR-006, FR-007, SC-006]
1. From the home screen, create a new project (or open the bundled demo if one ships).
2. Exercise at least: open the event storming canvas, add an Aggregate/Command/Event, author a user story, open the IDE workspace (021) and open/edit/save a file, open the design/Figma tab if the build includes 016. → Each behaves identically to the web app; data persists on save.
3. (macOS) Open the Claude Code terminal (015) → it attaches and accepts input. (Windows) → it shows a clear "Terminal is not available on Windows" message, not a blank pane or a crash (research D-terminal).

### Scenario 3 — Clean shutdown, no orphans [FR-003, SC-003]
1. With the app running, note the backend and Neo4j child PIDs (Settings → "About"/diagnostics, or Activity Monitor / Task Manager).
2. Close the window / Quit. → Within **30 s**, both child processes are gone. Re-check the process list. ✅ if zero app-owned processes remain.

### Scenario 4 — Relaunch, data persists [FR-008, SC-005-adjacent]
1. Relaunch the app. → The project and user story from Scenario 2 are still there; Settings (LLM provider, data source) are as you left them.

### Scenario 5 — Switch to an external Neo4j [FR-010, FR-011, SC-007, US3]
1. Stand up a separate Neo4j (any reachable instance) with some different data.
2. Settings → Data source → "External" → enter URI + user + password + database → "Test connection". → Succeeds (or shows a *typed* error: unreachable / auth failed / timeout / TLS). On success, save. Time the whole flow — target **< 2 min**.
3. → The app warns "you are now viewing a different dataset", the backend restarts (brief splash/banner), and the project list reloads from the external instance (the Scenario-2 project is **not** shown; the external instance's data **is**).
4. Switch back to "Bundled". → The Scenario-2 project reappears; no data was lost on either side.

### Scenario 6 — Change LLM provider/key [FR-020, Constitution VI]
1. Settings → LLM → switch provider and/or model → enter the matching API key. → The key is accepted; reopening Settings shows it as "configured" but never displays the value. Inspect `settings.json` in the data dir → it contains the provider/model but **no key**. The key is in the OS keychain/credential store.
2. Run an LLM-driven feature (e.g. requirements ingestion or model-modifier chat). → It uses the newly configured provider/model (check the backend logs for the provider name; streaming/SSE progress shows as in the web app).

### Scenario 7 — In-app update N → N+1 [FR-012, FR-013, FR-014, SC-004, SC-005, US2]
1. Install version N. Publish version N+1 to the channel.
2. Launch N (or trigger Settings → "Check for updates"). → A non-blocking "Update available" notification appears within one launch cycle.
3. Postpone it → the prompt does not nag again this session and the app keeps working on N.
4. Accept it → the update downloads, then prompts to restart; on restart the app is on N+1 and **all data from earlier scenarios is intact**. If N+1 ships a Neo4j store-format upgrade, it happens automatically without a visible failure.

### Scenario 8 — Interrupted update recovers [FR-015]
1. Start an update download, then kill the network (or the app) mid-download.
2. Relaunch. → The app is still on N (fully functional), and re-checks for the update; nothing is in a half-updated/broken state. Re-attempting the update succeeds.

### Scenario 9 — Port conflict at startup [FR-018, edge case]
1. Occupy a plausible default port (e.g. bind `127.0.0.1:8000` and a Bolt-ish port with `nc`/another app).
2. Launch the app. → It picks free ports automatically and reaches `ready`; no startup failure. (Confirm via the diagnostics panel that the chosen ports differ from the occupied ones.)

### Scenario 10 — Backend crash is recoverable [FR-017, edge case]
1. With the app at `ready`, kill the backend child process (Task Manager / `kill <pid>`).
2. → The window does **not** freeze; a banner appears: "Background service stopped — Retry" (possibly after a brief auto-retry). Click Retry → the backend re-spawns on a fresh port and the app returns to `ready` with state intact. `logs:reveal` shows the crash logged.

### Scenario 11 — Data-dir writability fallback [FR-009, edge case]
1. (Optional, if feasible) Run the app as a user whose default `userData` location is not writable, or pre-create it read-only.
2. Launch. → The app falls back to a writable location or prompts you to choose one; after choosing, it starts normally and Settings shows the chosen path. Data written there persists across relaunch.

### Scenario 12 — Existing-feature non-regression [FR-022, FR-023, FR-024, SC-006]
Inside the packaged app, run the relevant existing quickstarts/smoke checks for the features present in this build:
- **015 Claude Code terminal**: macOS — `WS /terminal` connects, input/resize work, project setup works; Windows — graceful "not available" (no crash).
- **021 IDE workspace**: file tree loads (lazy), open/edit/save with the same mtime-conflict detection and realpath sandboxing as the web version.
- **016 / 009 / 020 Figma binding & sync**: Figma plugin WebSocket connects, bulk-with-binding and bidirectional sync behave as in the web version (requires `FIGMA_API_TOKEN` configured via Settings).
- General: SSE-driven flows (ingestion progress, PRD generation, change planning) stream incrementally — Constitution III holds inside the shell.

✅ The feature is "done" for v1 when Scenarios 1–10 pass on both Windows and macOS, Scenario 12 shows no regressions for the features in the build, and Scenarios 11 has been at least spot-checked.
