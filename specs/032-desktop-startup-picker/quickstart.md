# Quickstart — Manual Smoke Scenarios

8 scenarios covering all P1/P2/P3 user stories and the critical edge cases. Run on both macOS and Windows; mark a scenario "passed" only when both platforms succeed.

**Pre-requisites for every scenario**
- A signed Electron desktop build of robo-architect (032 branch).
- Git installed on the host (except where the scenario specifically tests the no-git fallback).
- For Neo4j-touching scenarios: a reachable Neo4j 5.x instance with known credentials.

---

## Q1 — Cold first-time setup (US2, P1)

**Setup**: Fresh OS profile, no prior install. `git config --global user.name "Jane Doe"`, `git config --global user.email "jane@example.com"`.

**Steps**:
1. Install + launch the desktop app.
2. Observe the launcher appears within 1.5 s of double-click (SC-008).
3. Observe the welcome banner reads `Welcome, Jane Doe` (SC-009).
4. Observe the saved-connections list is empty and the **Add connection** form is expanded by default.
5. Type label="Local Dev", URI=`bolt://localhost:7687`, user=`neo4j`, password=`<known>`, leave database empty.
6. Click **Test**. Confirm "Connection successful" appears within 5 s.
7. Click **Choose folder** and pick `~/work/foo`. Confirm the path appears with basename + truncated parent.
8. Click **Enter**.

**Expected**:
- Launcher closes; main SPA loads pointing at `bolt://localhost:7687` with project root `~/work/foo`.
- `settings.json` now contains exactly one `SavedConnection` with `source: 'manual'`, `lastProfile` set, `recentProjectRoots: ['~/work/foo']` (resolved to absolute path).
- OS keychain contains `connection.<id>.password` (verified via `Keychain Access.app` on mac / `Credential Manager` on win).
- No plaintext password in `settings.json` or any log file under `<dataDir>/logs/`. SC-004.

---

## Q2 — Returning-user one-click resume (US1, P1)

**Setup**: Q1 completed.

**Steps**:
1. Quit the app fully.
2. Relaunch.

**Expected**:
- Launcher shows `Welcome, Jane Doe` at top.
- The "Local Dev" connection is pre-selected with a green "Connected" badge within 3 s.
- The `~/work/foo` project root is pre-filled.
- **Enter** is enabled from the first frame.
- One click on **Enter** loads the main app. Total elapsed from icon click to main-app interactive: **under 5 s** (SC-001).

---

## Q3 — Git identity precedence (US3, P1)

**Setup**: Q1 completed. Add a project-local override: `cd ~/work/foo && git init && git config user.name "Jane (work)" && git config user.email "jane.work@example.com"`.

**Steps**:
1. Relaunch. Observe the welcome banner still says `Welcome, Jane Doe` (initial resolve uses global only because no project root is selected yet).
2. Without clicking Enter, change project root to `~/work/foo`.
3. Observe the welcome banner updates to `Welcome, Jane (work)` within 1 s of the project-root change (FR-008, SC-009).
4. Click **Enter**.
5. In the main app, perform any write (e.g. create a user story).
6. Open the backend log JSONL; find the request line.

**Expected**:
- Log line for that request contains `actor_email=jane.work@example.com` (NOT the global value).
- Backend `request.state.actor.email == jane.work@example.com`. SC-010.

**Then**: with the project root set to a folder *outside* any git repo (e.g. `~/Desktop`), re-launch and confirm the global identity is restored.

---

## Q4 — Unknown-user fallback (US3 scenario 3 + edge case)

**Setup**: On a host with **no** git config set anywhere (`git config --global --unset user.name` + same for email, and ensure no project-local overrides apply). OR: an OS profile where `git` is not installed.

**Steps**:
1. Launch the app.

**Expected**:
- Welcome banner reads `Welcome, unknown user` with an inline notice "Set `git config user.name` to record changes under your name".
- **Enter** is still enabled once connection + project root are valid (FR-029 — unknown identity does not block).
- Backend log for any subsequent write shows `actor_email=unknown@<hostname>`, `actor_source=unknown-header-missing` (because the frontend interceptor sends no identity headers when the SessionUser source is `'unknown-fallback'`).

---

## Q5 — Neo4j Desktop discovery (US4, P2 — mac and win)

**Setup**: A host with Neo4j Desktop installed and at least 2 DBMSs configured under one Project. Fresh settings (no saved connections).

**Steps**:
1. Launch the app.
2. Observe a "Discovered (Neo4j Desktop)" section appears above/alongside the (empty) saved list.
3. Confirm both DBMSs are listed with their names + bolt port + version.
4. Click one of them. The Add-connection form opens pre-filled with URI + user but no password.
5. Enter the password. Click **Test**.
6. On success, observe the discovered DBMS moves into the Saved section with `source: imported-from-neo4j-desktop`.

**Expected**:
- Discovery completes within 2 s of launcher open.
- Neo4j Desktop's own files are unmodified (compare mtimes of `relate.config.json` before and after).
- The newly-saved entry survives uninstalling Neo4j Desktop (test: uninstall Neo4j Desktop, relaunch our app, confirm the saved entry still works — only the "Discovered" section disappears).

**Negative test**: on a host with no Neo4j Desktop, repeat Q1. The launcher must behave identically — no "Discovered" section, no error toast, no warning. SC-006.

---

## Q6 — Manage saved connections (US5, P3)

**Setup**: Two saved connections, "Local Dev" and "Staging".

**Steps**:
1. Right-click / hover-menu on "Staging" → **Edit**. Confirm the form opens pre-filled (password field shows "Keep existing"). Change the label to "Staging-EU". Save.
2. Confirm the list now shows "Local Dev" + "Staging-EU".
3. Right-click "Staging-EU" → **Delete**. Confirm the dialog asks for confirmation. Confirm.
4. Confirm only "Local Dev" remains.
5. Verify in the OS keychain that `connection.<staging-eu-id>.password` is gone.
6. Relaunch and confirm both changes persisted.

**Expected**: All steps succeed; keychain cleanup verified.

---

## Q7 — Web-mode unaffected

**Setup**: Run the backend + frontend in web mode (`uvicorn api.main:app --reload --port 8000` + `npm run dev` in `frontend/`).

**Steps**:
1. Open `http://localhost:5173` in a regular browser.

**Expected**:
- No launcher screen. First paint is the existing main app shell (whichever route is the web-mode default).
- No console errors about `window.desktop` being undefined.
- Any write performed shows `actor_source=unknown-header-missing` in backend logs (no identity headers — the http interceptor skips them when `useSession().user === null`, which is the case in web mode since the launcher never runs).

---

## Q8 — Settings v1 → v2 migration (FR-027, FR-033)

**Setup**: A v1 `settings.json` from a pre-032 build (manually constructed if needed, matching the 023 v1 shape with `externalNeo4j` set to a valid config and `neo4j.password` in the keychain).

**Steps**:
1. Launch the new build.
2. Without doing anything, quit and re-open the settings file.

**Expected**:
- `schemaVersion: 2`.
- `externalNeo4j: null` (kept for one version, value cleared).
- `savedConnections` has exactly one entry, copied from the v1 `externalNeo4j` config, with `source: 'manual-migrated-from-023'`, a fresh uuid, `label: "Migrated from settings"`.
- OS keychain has `connection.<newId>.password` with the value previously at `neo4j.password`.
- The legacy `neo4j.password` keychain entry is deleted.
- On the very first launcher open, the migrated entry appears in the Saved list and a status probe runs against it (SC-007).
- User is NOT prompted to re-enter their connection. SC-007.

---

## Pass criteria

A scenario passes only when **both** macOS and Windows targets succeed. Any failure logs are pasted into the scenario's row in this checklist:

| # | Scenario | macOS | Windows |
|---|---|---|---|
| Q1 | Cold first-time setup | ☐ | ☐ |
| Q2 | Returning-user one-click resume | ☐ | ☐ |
| Q3 | Git identity precedence | ☐ | ☐ |
| Q4 | Unknown-user fallback | ☐ | ☐ |
| Q5 | Neo4j Desktop discovery | ☐ | ☐ |
| Q6 | Manage saved connections | ☐ | ☐ |
| Q7 | Web-mode unaffected | ☐ | ☐ |
| Q8 | Settings v1 → v2 migration | ☐ | ☐ |

---

## Out-of-band checks (run once per release, not per platform)

- **Password leak scan**: After completing Q1 through Q5 on a fresh profile, grep `<dataDir>/logs/*.jsonl` and `<dataDir>/settings.json` for the test password literal. Expected: zero hits. SC-004.
- **Cold-start budget**: instrument the renderer for `performance.now()` between `document.readyState === 'interactive'` and the launcher's first paint. Median over 10 runs ≤ 1.5 s. SC-008.
- **Identity propagation audit**: across a 5-minute representative session touching user stories, aggregates, and events, sample 50 requests from the backend log. ≥ 49 must carry the resolved identity (the only legitimate exceptions are background polls before the launcher hand-off completes). SC-010.
