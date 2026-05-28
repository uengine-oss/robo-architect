# Feature Specification: Desktop Startup Connection, Identity & Project Picker

**Feature Branch**: `032-desktop-startup-picker`

**Created**: 2026-05-28

**Status**: Draft

**Input**: User description: "시작때 데스크톱 모드로 떴을 때 (일렉트로너에서 떴을 때) 첫 화면에서 지금 접속할 수 있는 네오포제이 서버에 목록이 뜨고, 목록이 없다면 추가적으로 입력할 수 있게, 혹시 로컬에 네오포제이 데스크톱이 깔려 있다면 네오포제이 데스크톱의 데이터를 확인해서 접속할 수 있는 목록을 띄워 줘도 되고, 보안상 문제가 있으면 못하는 것. 패스워드를 입력하면 우리 DB 툴들처럼 기존에 접속했던 커넥션 목록들이 쭉 나와서 최근에 접속한 게 디폴트로 표시되고, 클릭하면 선택이 되고 접속 상태가 확인됨. 프로젝트 루트에 대한 설정도 여기에서 할 수 있게 해서 Claude가 연결될 수 있는 프로젝트 루트도 선택. 이 두 가지를 선택해서 진입. 데스크톱 버전에 대해서. — 그리고 현재 Git 정보를 Electron에서 확인해서 GitUser 정보를 확인해서 지금 Welcome 메시지를 줄 때 GitUser의 이름을 표시. 로그인이 따로 있는 게 아니라 현재 git user(환경/설정에 잡힌 user.name) 가 곧 유저. — 그래서 로그인된 상태를 보관하고, 로그인된 유저 정보를 기반으로 유저 스토리·어그리거트 등의 변경 이력(누가 어디를 수정했는지)을 남길 필요가 있음(상세 이력 기능은 후속 스펙)."

## Background

The Electron desktop shell (feature 023) currently boots straight into the main SPA, assuming a single backend + data source picked at install/config time. Real users installing the desktop binary on their own machines will already have one or more Neo4j instances they want to point this app at — a personal Neo4j Desktop install, a team server, a docker-compose box, or the bundled instance the installer ships. They also want to point the app at a specific project folder on disk so the Claude integration (the existing `claude` terminal/IDE features) can operate against their actual source tree. And because the desktop app intentionally has no separate login flow, the launcher is also where we establish *who* the session is for — by reading the git identity already configured on the host machine.

This feature adds a **first-screen launcher** that runs only in the Electron desktop build. It:

1. Identifies the user from their host git configuration and welcomes them by name.
2. Lets them pick a Neo4j connection from a list of saved, discovered, and (if the build ships it) bundled instances.
3. Lets them pick a project root that downstream Claude integrations will operate against.
4. Verifies both selections, then hands the user off into the main app.

The session's identity is propagated to every subsequent write so that follow-up work (a separate audit/history feature) can attribute domain edits — user-story changes, aggregate edits, event-storming modifications — to a specific person without ever having added a login screen.

Web/server deployments are unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One-click relaunch with last-used profile (Priority: P1)

A returning user has used the desktop app before and just wants to get back into their work. They double-click the app icon and see the launcher with **"Welcome, Jane"** at the top (read from their git config), their most recent connection and project root already pre-filled and highlighted, and a green "Connected" indicator. They click **Enter**, and the main UI loads with the same data they were looking at yesterday — and any edit they make from there is recorded against "Jane" automatically.

**Why this priority**: This is the daily-driver path. If returning users have to reconfigure on every launch, the desktop build is worse than the web app. Making the recent profile a one-click resume — with implicit identity from git — is the core value of having a launcher at all.

**Independent Test**: With a valid git config on the host, configure one connection + project root in a prior session, quit, relaunch. The launcher must auto-select the last-used entry, run a status probe, display the git user's name in the welcome banner, and let the user enter the main app with a single click. Verifiable on a fresh OS profile by seeding the persisted settings file, setting `git config --global user.name` to a known value, and observing the first frame.

**Acceptance Scenarios**:

1. **Given** the user has previously entered the app with connection A + project root /work/foo, and `git config user.name` returns "Jane Doe", **When** they launch the desktop app, **Then** the launcher opens with a "Welcome, Jane Doe" header, A pre-selected, /work/foo pre-filled, a live status badge next to A, and the **Enter** button enabled.
2. **Given** the last-used connection is reachable, **When** the launcher's status probe completes, **Then** the badge shows "Connected" within 3 seconds and the **Enter** button remains enabled.
3. **Given** the last-used connection is unreachable (server down, wrong network), **When** the probe fails, **Then** the badge shows "Unreachable" with a **Retry** action and a tooltip explaining the failure; the user can still pick a different saved entry without restarting.
4. **Given** the user clicks **Enter** with a healthy selection, **When** the launcher closes, **Then** the main SPA loads pointed at the chosen Neo4j and the chosen project root, the session is tagged with the resolved git user identity, and the (connection, project root, user) tuple is recorded as the new "last used."

---

### User Story 2 - First-time setup: add a connection and a project (Priority: P1)

A user installing the app for the first time has no saved connections and an empty project history. They see the launcher with the welcome banner showing their git name, an empty connection list with an inline **Add connection** form, and a **Choose folder** picker for project root. They paste their Neo4j Bolt URI, enter user + password, click **Test** to confirm the credentials work, pick a folder from the OS file dialog, and click **Enter**.

**Why this priority**: Without this path, the app is unusable on first install — it has to handle the empty-state gracefully. This is the on-ramp; if it has friction, users uninstall.

**Independent Test**: Wipe the settings file (or use a fresh OS profile), set a known `git config --global user.name`, launch the app, and complete the flow end-to-end without ever leaving the launcher screen. Verifiable by inspecting the persisted settings + keychain afterwards and confirming the entry round-trips on the next launch.

**Acceptance Scenarios**:

1. **Given** no saved connections exist, **When** the launcher opens, **Then** it shows the welcome banner with the git user name, the **Add connection** form expanded by default with empty fields, and the **Enter** button is disabled until both a connection and a project root are valid.
2. **Given** the user fills connection fields and clicks **Test**, **When** credentials are correct, **Then** a "Connection successful" indicator appears within 5 seconds and the entry is saved to the list.
3. **Given** the user fills connection fields and clicks **Test**, **When** credentials are wrong or the host is unreachable, **Then** an inline error explains which part failed (auth vs network vs URI format) without disclosing internal stack traces.
4. **Given** the user clicks the project root picker, **When** they select a folder, **Then** the path appears in the launcher, the launcher validates the path exists and is readable, and shows the folder's basename + truncated parent path.
5. **Given** both a connection is verified and a project root is selected, **When** the user clicks **Enter**, **Then** the main app loads, the session carries the resolved git identity, and the saved entry is paired with that project root for future one-click resume.

---

### User Story 3 - Identity from git, no login screen (Priority: P1)

A user opens the app and is immediately greeted by name — no login form, no signup, no SSO redirect. The name comes from whatever `git config user.name` is set to in their environment. From that point onward, anything they edit in the main app — a user story, an aggregate, an event — carries that name as the modifier. If two coworkers share a machine, switching git identity (via project-local git config or env vars) is enough to switch the attribution; no app-level account management is needed.

**Why this priority**: This is what makes the system multi-user-aware without paying the cost of an auth system. It's a precondition for the follow-up audit/history feature and reframes the launcher from "config screen" to "session start." It must ship with the launcher itself, not later.

**Independent Test**: Launch the app with three different git identities (global config, project-local override inside the selected project root, `GIT_AUTHOR_NAME` env var) and confirm each is reflected in the welcome banner and persisted into the runtime session identity. Verifiable without ever touching the main SPA: read the runtime state directly.

**Acceptance Scenarios**:

1. **Given** `git config --global user.name` is "Jane Doe", **When** the launcher opens, **Then** the welcome banner reads "Welcome, Jane Doe" and the runtime session identity equals "Jane Doe" + the corresponding email.
2. **Given** the selected project root has a project-local git config that overrides `user.name` to "Jane (work)", **When** the user clicks **Enter** after selecting that project root, **Then** the identity propagated into the main app is "Jane (work)", not the global value.
3. **Given** no git config is set anywhere (no global, no local, no env), **When** the launcher opens, **Then** the welcome banner shows "Welcome, unknown user" together with an inline notice "Set `git config user.name` to record changes under your name"; the user can still proceed but their edits will be attributed to `unknown@<hostname>`.
4. **Given** the user switches the project root mid-session to one with a different project-local git config, **When** the launcher re-resolves identity, **Then** the welcome banner updates and the new identity is the one carried into the main app on **Enter**.

---

### User Story 4 - Discover connections from local Neo4j Desktop (Priority: P2)

A user who runs Neo4j Desktop on their machine launches our app for the first time. Instead of staring at an empty list, they see their existing Neo4j Desktop DBMSs listed under a **Discovered** section ("Detected from Neo4j Desktop"). They click one, are prompted to enter the password for that DBMS (we don't read passwords from Neo4j Desktop), it verifies, and they continue.

**Why this priority**: Substantial quality-of-life win for the most likely first-time user (someone who already uses Neo4j locally). Not blocking — they can always add manually — but cuts onboarding from minutes to seconds.

**Independent Test**: On a host with Neo4j Desktop installed and at least one DBMS configured, launch the app with empty saved-connections state. The discovered DBMSs must appear in the launcher list, distinguishable from manually-added entries, and selectable. On a host without Neo4j Desktop, the launcher must behave identically to Story 2 (empty state) with no errors.

**Acceptance Scenarios**:

1. **Given** Neo4j Desktop is installed and the user has at least one DBMS configured, **When** the launcher opens, **Then** discovered DBMSs appear in a clearly labeled "Discovered (Neo4j Desktop)" group with their DBMS name + bolt port + Neo4j version.
2. **Given** Neo4j Desktop is not installed, OR its config is unreadable, OR the user has zero DBMSs, **When** the launcher opens, **Then** no "Discovered" section appears and no error or warning is shown — discovery fails silently.
3. **Given** the user selects a discovered DBMS, **When** they click **Test** after entering a password, **Then** the entry behaves identically to a manually-added connection and is persisted to the saved list under the user's control (the original Neo4j Desktop config is never modified).
4. **Given** discovery succeeded but a particular DBMS is stopped, **When** the user views it, **Then** it appears with a "Stopped" badge and a hint that they need to start it in Neo4j Desktop first; the launcher does not attempt to start it.

---

### User Story 5 - Manage saved connections (Priority: P3)

A user wants to rename a saved connection, fix a typo in its URI, or remove an old one. From the launcher, they can hover/right-click a saved entry to **Edit** or **Delete** it, with confirmation on delete.

**Why this priority**: Necessary for long-term usability but not blocking initial value. A user could survive without it by editing the settings file or by adding a new entry and ignoring the old one.

**Independent Test**: With at least two saved connections, edit one's label and delete the other. Relaunch and confirm both changes persist.

**Acceptance Scenarios**:

1. **Given** a saved connection exists, **When** the user opens its context menu and chooses **Edit**, **Then** the **Add connection** form opens pre-filled with that entry's values (except the password, which must be re-entered or left unchanged via a "keep existing" option).
2. **Given** a saved connection exists, **When** the user chooses **Delete** and confirms, **Then** the entry is removed from the list and its password is removed from the OS keychain.
3. **Given** the user deletes the last-used entry, **When** they relaunch, **Then** the launcher selects the next-most-recently-used entry as default, or falls back to empty state if none remain.

---

### Edge Cases

- **Web/server mode unaffected**: When the same SPA is served from `uvicorn` over HTTP outside Electron, the launcher never renders — first paint is the existing app shell. Detection of "desktop mode" must not break web mode. Identity in web mode falls back to whatever existing mechanism web mode uses (anonymous / future SSO); it does not read git config from the server host.
- **Bundled Neo4j (when feature 023 ships it)**: If the desktop build includes the bundled Neo4j path, the bundled instance appears as a special "Bundled (this app)" entry in the list, always pinned to the top, with its lifecycle managed by the existing Electron shell rather than user-configured credentials.
- **Stale project root**: A saved project root that has been deleted or moved → launcher marks it "Folder not found" and disables **Enter** until the user picks a new one or browses to the relocated path.
- **Project root with no read permission**: Detect at validation time and surface a clear "cannot read folder" error before the user clicks **Enter**, not after the main app fails to load.
- **Connection probe timeout**: The status probe must be bounded (≤ 5 s) so the launcher never appears frozen; on timeout, show "Unreachable" with **Retry**.
- **Password missing in keychain**: A saved entry whose password is no longer in the OS keychain (e.g. user wiped keychain, reinstalled OS) → prompt the user to re-enter the password inline; do not silently fail or lose the URI.
- **Multiple Electron instances**: Single-instance lock (per existing 023 design) means a second launch focuses the existing window; the launcher never appears twice simultaneously.
- **Quit from launcher**: Closing the launcher window (X button, Cmd+Q) without selecting → quits the application cleanly without writing partial state.
- **Neo4j Desktop config encrypted or locked**: Discovery attempt fails → silently skipped, no popup, no log spam beyond a single info-level entry per launch.
- **Saved connection that was discovered from Neo4j Desktop, but Neo4j Desktop has since been uninstalled**: The persisted manual copy still works (it's a normal saved entry now); discovery section just disappears.
- **First-launch with Settings already populated by 023's existing single-source picker**: Pre-existing config is treated as the first saved entry on migration; user is not forced to re-enter it.
- **Git not installed on host**: If `git` is not on PATH at all, identity falls back to "unknown user" with the same inline notice as US3 scenario 3; the launcher does not require git to be installed to function.
- **Git config name contains unusual characters / extremely long**: Identity name is displayed truncated to a sane width (≈ 40 chars) but the full value is what's persisted into the runtime session and used for attribution.

## Requirements *(mandatory)*

### Functional Requirements

**Mode detection & lifecycle**

- **FR-001**: The launcher screen MUST be shown only when the app is running inside the Electron desktop shell, never when the SPA is served over HTTP outside Electron.
- **FR-002**: The launcher MUST be the first user-visible UI in the desktop build, rendered before the main SPA is loaded.
- **FR-003**: The main SPA MUST NOT initiate any data fetches against Neo4j or the project filesystem until the user has completed the launcher and clicked **Enter**.
- **FR-004**: Closing the launcher window without entering MUST quit the application cleanly.

**Identity from git**

- **FR-005**: On launcher open, the desktop shell MUST resolve the user identity by reading git config in the standard precedence order (env vars `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL` > project-local config inside the *selected* project root > global git config > system git config).
- **FR-006**: The launcher MUST display the resolved identity name in a welcome banner ("Welcome, &lt;name&gt;") as the very first text the user sees.
- **FR-007**: If no git identity can be resolved anywhere, the launcher MUST display "Welcome, unknown user" together with an inline notice instructing the user how to set `git config user.name`, and MUST still allow the user to proceed with an attribution of `unknown@<hostname>`.
- **FR-008**: When the user changes the selected project root in the launcher, the desktop shell MUST re-resolve the identity (because a different project-local git config may now apply) and update the welcome banner before the user clicks **Enter**.
- **FR-009**: On **Enter**, the resolved identity (name + email) MUST be propagated into the main app's session state and MUST accompany every subsequent backend write the main app makes, so that follow-up audit / history features can attribute changes without any further user input.
- **FR-010**: There MUST NOT be any separate login, signup, password, SSO, or token entry for identity — git config is the only identity source.

**Connection list**

- **FR-011**: The launcher MUST display all saved Neo4j connections in a list, ordered with most-recently-used first.
- **FR-012**: When at least one saved connection exists, the launcher MUST pre-select the most-recently-used entry as the default.
- **FR-013**: The launcher MUST run a background reachability + auth status probe against the selected connection on open, and surface the result as a status badge (Connected / Unreachable / Auth failed / Stopped) within 5 seconds.
- **FR-014**: When the saved list is empty, the launcher MUST show the **Add connection** form expanded by default so the user is not faced with a blank screen.
- **FR-015**: Each saved entry MUST expose **Edit** and **Delete** actions; Delete MUST require explicit confirmation and MUST also remove the associated password from the OS keychain.

**Add / edit connection**

- **FR-016**: The **Add connection** form MUST accept a user-supplied label, a Bolt URI, a username, an optional default database name, and a password.
- **FR-017**: The form MUST provide a **Test** action that performs an authenticated handshake against the supplied connection without persisting it, and surfaces a distinct outcome for each of: success / wrong credentials / host unreachable / URI malformed / database not found.
- **FR-018**: Only after a successful **Test** (or explicit "save without testing" for advanced users) MAY the entry be added to the saved list.
- **FR-019**: Passwords MUST be stored in the OS secure storage (the existing `SecretRef` mechanism from feature 023) and MUST NEVER be written to settings files, logs, or any plaintext location on disk.

**Neo4j Desktop discovery**

- **FR-020**: On launch, the desktop shell MUST attempt to discover Neo4j DBMSs configured in a locally-installed Neo4j Desktop, if any, by reading Neo4j Desktop's configuration from its standard per-user data directory.
- **FR-021**: Discovered DBMSs MUST appear in a clearly labeled, visually distinct "Discovered (Neo4j Desktop)" section above or alongside the saved list, never silently mixed in.
- **FR-022**: Discovery MUST NEVER read or import passwords from Neo4j Desktop, regardless of whether they would be technically accessible. The user MUST enter the password themselves the first time they select a discovered DBMS.
- **FR-023**: If Neo4j Desktop is not installed, its config is unreadable, encrypted, locked, or otherwise inaccessible, discovery MUST fail silently — no popup, no error toast, no blocking UI, and at most a single info-level log line per launch.
- **FR-024**: A user-selected discovered DBMS, once successfully tested, MUST be persisted as a normal saved entry under the user's control and continue to work even if Neo4j Desktop is later uninstalled or its config moves.

**Project root**

- **FR-025**: The launcher MUST provide a project-root picker that opens the native OS folder selection dialog.
- **FR-026**: The launcher MUST display the most-recently-used project root pre-filled and validate that it currently exists and is readable.
- **FR-027**: The launcher MUST recall up to N recent project roots (N ≥ 5) and let the user pick from history without reopening the OS dialog.
- **FR-028**: A project root that no longer exists or is unreadable MUST surface a clear inline error and MUST block **Enter** until the user resolves it.

**Enter / handoff**

- **FR-029**: The **Enter** button MUST be enabled only when (a) a connection is selected, (b) that connection has either passed a recent **Test** or has a verified credential cache and a reachable status badge, AND (c) a valid project root is selected. The git identity does NOT need to be successfully resolved (the unknown-user fallback is acceptable).
- **FR-030**: Clicking **Enter** MUST hand off the chosen connection identity, project root, and resolved git user identity to the main app and the Claude integration, and MUST persist the (connection, project root) pair as the new "last used" so the next launch resumes it.
- **FR-031**: After **Enter**, the main app's runtime state MUST reflect the chosen Neo4j, project root, and the session's user identity, and any Claude/terminal sessions spawned afterward MUST inherit the same identity.

**Persistence & compatibility**

- **FR-032**: All persisted launcher state (saved connections list, last-used pair, recent project roots) MUST live in the existing per-user desktop settings file from feature 023 and MUST round-trip across app upgrades. The git user identity itself is NOT persisted by the launcher — it is re-resolved from git on every launch, so changing git config takes effect immediately.
- **FR-033**: On first launch after upgrading from a version that had only a single data-source setting (the pre-launcher 023 state), the existing single configuration MUST be migrated into the saved-connections list as the first entry without prompting the user.
- **FR-034**: The launcher MUST NOT introduce any new HTTP API endpoint on the backend; all launcher behavior is implemented in the Electron main process + renderer, calling the existing backend only via existing endpoints (notably the connection-test endpoint already present from 023). Identity propagation to backend writes MAY require extending an existing request envelope (e.g. an `X-User-Name` + `X-User-Email` header) but MUST NOT require new endpoints.

### Key Entities

- **Session User**: The identity established by the launcher at hand-off and carried for the rest of the app session. Attributes: name, email, source (`env` / `project-local-git` / `global-git` / `system-git` / `unknown-fallback`). Re-resolved at every launch; not persisted by this feature.
- **Saved Connection**: A user-managed Neo4j endpoint. Attributes: stable id, user-chosen label, Bolt URI, username, optional default database name, source (`manual` / `imported-from-neo4j-desktop` / `bundled`), `lastConnectedAt` timestamp. The password is **not** an attribute — it lives in OS secure storage referenced by id.
- **Discovered Connection**: A transient, non-persisted view of a DBMS read from Neo4j Desktop's local configuration. Attributes: DBMS name, Bolt URI, declared Neo4j version, current run state if available. Promoted to a Saved Connection once the user successfully tests it.
- **Project Root**: A local filesystem path that Claude integrations operate against. Attributes: absolute path, last-used timestamp, current validity flag (exists + readable at probe time).
- **Launch Profile** (implicit, not user-named): The (SavedConnection, ProjectRoot) pair that the launcher resumes from. There is exactly one "last used" profile; the launcher may surface a small list of recent pairings as quick-pick shortcuts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A returning user with a healthy last-used profile reaches the main app in under 5 seconds of clicking the dock/taskbar icon, with one click on **Enter** as the only required interaction, and sees the welcome banner display their name from the first paint.
- **SC-002**: A first-time user with no Neo4j Desktop install can configure a working connection + project root and enter the app in under 3 minutes, without leaving the launcher screen, without reading documentation, and without using the OS file system to inspect settings.
- **SC-003**: When Neo4j Desktop is installed with at least one DBMS, the user reaches a verified connection in under 30 seconds (discovery → password entry → test → enter) on first launch.
- **SC-004**: Zero occurrences of plaintext passwords in the settings file, logs, crash reports, or any user-readable on-disk artifact, verified by scanning a representative install after a full launcher round-trip including failed-credential attempts.
- **SC-005**: The launcher's connection status probe completes (success, failure, or timeout) in under 5 seconds in 99% of cases; the UI never appears frozen.
- **SC-006**: Discovery failure on hosts without Neo4j Desktop is invisible to the user — zero error toasts, zero modal dialogs, and the launcher's empty-state behavior is indistinguishable from the no-discovery path.
- **SC-007**: When the user upgrades from a pre-launcher build (existing 023 single-source config), they are not prompted to re-enter their connection on the first post-upgrade launch — the existing config becomes the default saved entry automatically.
- **SC-008**: The launcher adds ≤ 1.5 seconds to the cold-start time on a healthy reference machine compared to a hypothetical "no launcher" build, measured from process spawn to launcher-interactive.
- **SC-009**: Git identity resolution succeeds and the name is on screen within 1 second of the launcher window appearing in 99% of cases on hosts where git is installed; the no-git / no-identity fallback path activates within the same 1-second budget and never blocks the launcher.
- **SC-010**: Every write performed by the main app *after* the launcher hand-off carries the resolved session identity in its request envelope, verified by inspecting backend access logs across a representative workflow that touches user stories, aggregates, and event-modeling artifacts.

## Out of Scope

The following are explicitly out of scope for this feature and are expected to be addressed in follow-up specs:

- **Change history storage and querying**: This feature *enables* attributing edits to a session user by propagating identity to every write, but the actual persistence model for change history (where in Neo4j the events live, what shape they take, retention policy) and the UI for browsing it ("who changed this aggregate, and when?") are not part of 032. They belong to a dedicated history/audit spec.
- **Web-mode identity**: The web/server deployment continues to use whatever identity model it already has (or none). Wiring SSO / OAuth / API tokens into the web variant is unrelated.
- **Account / profile management**: There is intentionally no concept of a registered account, profile picture, role, team membership, or invitation flow. Identity is whatever git says it is on the host at the time of launch.
- **Per-connection access control**: All saved connections are equally available to anyone using the desktop app on that host machine. Multi-tenant separation of saved connections is out of scope.
- **Importing passwords from Neo4j Desktop**: Explicitly never done, even if technically possible. Passwords are always entered fresh by the user the first time a discovered DBMS is used.

## Assumptions

- **Desktop mode is the only mode affected.** The launcher is implemented entirely inside the Electron shell (main + renderer) and is opt-in by build target. The same SPA served as a web app from `uvicorn` keeps its current first-paint behavior and continues to use whatever identity mechanism it already has.
- **Git identity is sufficient.** The product accepts the trade-off that anyone able to set `git config user.name` on the host can claim any identity. This matches how `git commit` already works on the host and is acceptable because the desktop app is a local single-user tool, not a multi-tenant server.
- **Each saved connection has its own password.** There is no master "vault password" gating access to the saved list. Each entry's password lives in OS secure storage indexed by entry id.
- **A launch profile is (connection × project root) paired.** The user described both as a single "two-things-to-select" gesture, so the most-recently-used pair is what the launcher resumes from. Saved connections and recent project roots are also tracked independently to support cross-pairings.
- **Bundled Neo4j coexists.** If the desktop build ships with a bundled Neo4j (per feature 023's GPLv3 decision in T050), it appears as a special pinned entry "Bundled (this app)"; otherwise no such entry appears and the list is purely user-managed.
- **Neo4j Desktop discovery is read-only, filesystem-based, best-effort.** The shell reads Neo4j Desktop's well-known per-user config directory on macOS and Windows, never writes to it, never reads passwords from it, and never depends on Neo4j Desktop's local HTTP API or any running service. Failure modes (not installed, locked, schema changed across Neo4j Desktop versions) all degrade silently.
- **Connection-test transport reuses existing backend endpoint.** The `Test` action invokes the existing connection-test IPC command from feature 023 (`settings:testNeo4jConnection`), which already proxies to the backend's Neo4j probe. No new HTTP endpoint, no new Pydantic models.
- **Project root is a local filesystem directory.** It is the same notion of "workspace" already consumed by the Claude integration (features 015 / 021), per-launch-profile rather than global.
- **Identity propagation uses request headers.** The chosen mechanism for carrying the session user from the SPA to the backend on every write is an existing-or-newly-added pair of HTTP request headers (e.g. `X-User-Name`, `X-User-Email`); this is not a new endpoint and does not change any Pydantic model on the request side.
- **No backend write is rejected for missing identity.** Backend behavior on missing identity headers is to attribute the change to `unknown@<hostname>`, matching the launcher's unknown-user fallback. The launcher does not gate Enter on identity resolution succeeding.
- **The follow-up history feature is a separate spec.** This feature only lays the foundation (identity capture + propagation). The mechanism for persisting and querying who-changed-what in Neo4j is deliberately deferred.
