# Feature Specification: Robo-Architect Desktop Application Packaging

**Feature Branch**: `023-electron-desktop-app`
**Created**: 2026-05-09
**Status**: Draft (clarifications resolved 2026-05-11)
**Input**: User description: "Electron으로 robo-architect를 데스크톱 애플리케이션으로 패키징. 현재는 FastAPI 백엔드(api/) + 프론트엔드(frontend/) + Neo4j 의존성으로 구성된 웹 앱을 사용자가 별도 서버 셋업 없이 단일 실행 파일로 설치/실행할 수 있도록 데스크톱 셸로 감싼다. 백엔드 프로세스를 데스크톱 앱이 자식 프로세스로 spawn해 관리하고, 프론트엔드는 데스크톱 윈도우에서 로드한다. Windows / macOS 타겟 빌드, 자동 업데이트, 로깅, Neo4j 동봉 또는 외부 연결 옵션, 기존 015 Claude Code 터미널 / 021 IDE 워크스페이스 / 016 Figma 바인딩 등 기존 기능과 충돌 없는 동작을 포함."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One-click install and launch (Priority: P1)

A solution architect or business analyst downloads a single installer for their operating system, runs it, and on first launch can immediately start using the full Robo-Architect product (event storming, requirement ingestion, user story authoring, IDE workspace, Figma binding, Claude Code terminal) without installing Python, Node.js, Neo4j, or any other developer tooling separately, and without editing configuration files.

**Why this priority**: This is the entire point of the feature. Today every adopter who is not a developer hits a wall at "set up Neo4j / install uv / start the backend / serve the frontend". Removing that wall is what makes Robo-Architect distributable to its target audience (enterprise architects, PMs, designers) at all. Without P1 the rest of the feature has no value.

**Independent Test**: Given a clean machine with no prior project tooling, downloading and running the installer must produce a working app whose home screen loads, an existing demo project can be opened, and at least one core workflow (e.g., creating a user story or opening the IDE workspace) completes successfully — all without the user opening a terminal.

**Acceptance Scenarios**:

1. **Given** a clean Windows 11 or macOS machine with no Python/Node/Neo4j installed, **When** the user runs the installer and launches the app, **Then** the app window opens within 60 seconds and the home screen is interactive without any setup prompt.
2. **Given** the app is running, **When** the user opens an existing project's event storming canvas, **Then** all data persisted previously by that project is available and editable, identical to the web version.
3. **Given** the user closes the app window, **When** the app is fully exited, **Then** all background processes started by the app are also stopped and no orphan processes remain after 30 seconds.
4. **Given** the user launches the app a second time, **When** the home screen loads, **Then** previously created projects, settings, and authored data from the first session are still present.

---

### User Story 2 - Self-managed updates (Priority: P2)

When a new version of Robo-Architect is released, users on the desktop app are notified and can update to the latest version with a single confirmation, without manually downloading a new installer or losing their local data.

**Why this priority**: The product changes weekly. Without an update channel, every user is stranded on whatever version they first installed, and onboarding documentation rots. This is what makes desktop distribution sustainable for the team. It is P2 because P1 already produces value on day one even with manual updates; auto-update makes that value durable.

**Independent Test**: With the app installed at version N and a published version N+1, launching the app must surface an update prompt; accepting it must result in the app relaunching on N+1 within a few minutes, with all user data preserved.

**Acceptance Scenarios**:

1. **Given** the app is running on version N and version N+1 has been released, **When** the user is online, **Then** the app surfaces an update notification within one launch cycle.
2. **Given** the user accepts an update, **When** the update completes, **Then** the app relaunches automatically on the new version and all locally stored project data, settings, and authored content remain intact.
3. **Given** the user declines or postpones an update, **When** they continue working, **Then** the current version remains fully functional and the prompt does not block or repeat within the same session.

---

### User Story 3 - Choosing where data lives (Priority: P2)

A user can see and choose where their Robo-Architect data (projects, ingested documents, generated artifacts, application logs) is stored on their machine, and can point the app at an existing shared graph database instead of the bundled one when their organization requires it.

**Why this priority**: Enterprise users routinely need data on a controlled disk location (encrypted volume, sync-excluded folder) and architects collaborating on the same domain model need to share a backend. Without this, the desktop app is an island. It is P2 (not P1) because solo users on default settings will still get a working product without ever touching this.

**Independent Test**: From a fresh install, a user must be able to (a) see the storage location for their data on first run or in settings, (b) reconfigure the app to use a different graph database endpoint, and (c) verify that switching endpoints reloads the project list from the chosen source.

**Acceptance Scenarios**:

1. **Given** the user opens the app for the first time, **When** they reach the home screen, **Then** the app's data storage location is visible in settings or onboarding and follows OS-conventional per-user paths.
2. **Given** the user has a shared graph database endpoint and credentials, **When** they enter those in settings and confirm, **Then** the app validates the connection and either succeeds (project list refreshes) or shows a clear, actionable error.
3. **Given** the user has been running on the bundled graph database, **When** they switch to an external endpoint, **Then** their previous local-only data is not silently overwritten and they are warned that they are now viewing different data.

---

### Edge Cases

- A required local port for the backend is already occupied by another application — the app must select a free port automatically and proceed, not fail at startup.
- The backend child process crashes mid-session — the app must surface a recoverable error to the user (e.g., "Background service stopped, retry?") rather than freezing the window.
- The user installs the app on a machine where their account does not have permission to write to the default data directory — the app must fall back to a writable location or prompt for one rather than silently losing data.
- The user runs two copies of the installer on the same machine — at most one app instance runs at a time; subsequent launches focus the existing window.
- The user is offline at startup — the app launches and works for all features that do not require external services; features that require network (LLM calls, Figma sync, ingestion of remote sources) show a clear offline state.
- An auto-update is interrupted (network drop, power loss) — the next launch either resumes the update or remains on the prior version cleanly, never in a broken half-updated state.
- The bundled graph database from a previous version is incompatible with a newer app version — the app migrates data forward or, if it cannot, surfaces a clear path (export, contact, retry) instead of starting empty.

## Requirements *(mandatory)*

### Functional Requirements

#### Installation & Launch

- **FR-001**: System MUST be distributable as a single signed installer per supported operating system (Windows and macOS) that completes installation through the user's normal OS install flow without requiring developer tooling.
- **FR-002**: System MUST run with all backend services managed automatically by the application; users MUST NOT need to start a server, configure environment variables, or run any command-line steps for normal usage.
- **FR-003**: Application MUST start all required background services on launch and stop all of them on exit, leaving no orphan processes.
- **FR-004**: Application MUST allow only one running instance per user session; subsequent launch attempts MUST focus the existing window rather than starting a parallel copy.
- **FR-005**: Application MUST start the main window within 60 seconds of launch on a representative target machine (8 GB RAM, SSD).

#### Functional parity with the web version

- **FR-006**: All features available in the current web version MUST function inside the desktop application, including but not limited to: requirements ingestion, event storming canvas and graph navigation, user story authoring, document export, change-impact planning, model-modifier chat, Figma document binding and bidirectional sync (016), Claude Code terminal (015), and IDE workspace (021).
- **FR-007**: Existing project data created in the web version MUST be openable in the desktop version when both point at the same data source, and vice versa.

#### Data, storage, and external connections

- **FR-008**: Application MUST persist user data (projects, settings, ingested artifacts, authored content, logs) across sessions and across application updates.
- **FR-009**: Application MUST store user data by default in an OS-conventional per-user location and MUST surface that path to the user in settings or onboarding.
- **FR-010**: Application MUST allow the user to point at an external graph database endpoint instead of the default bundled storage, and MUST validate the connection before saving the change.
- **FR-011**: Switching between bundled and external data sources MUST NOT silently destroy data on either side; the user MUST be informed that they are now viewing a different data set.

#### Updates

- **FR-012**: Application MUST detect when a newer published version is available and surface this to the user without blocking ongoing work.
- **FR-013**: User MUST be able to apply an update with a single confirmation, after which the application restarts automatically on the new version.
- **FR-014**: User data MUST be preserved across updates; if a data migration is required, the application MUST perform it automatically or guide the user through it.
- **FR-015**: Update artifacts MUST be cryptographically verified (signed) before being applied, and an interrupted update MUST never leave the application in an unusable state.

#### Reliability and observability

- **FR-016**: Application MUST write diagnostic logs to a known location on disk and provide a "Reveal logs" affordance from within the app.
- **FR-017**: When a backend service crashes, the application MUST surface a recoverable error to the user with at least a "Retry" action, instead of freezing the window or exiting silently.
- **FR-018**: Application MUST select a free local port for any internal services rather than failing if a default port is already in use.

#### Security

- **FR-019**: Installers and update payloads MUST be code-signed for their respective operating systems so users do not see "unidentified developer" warnings on a default-trust machine.
- **FR-020**: Secrets and credentials entered by the user (e.g., external graph database password, API keys) MUST be stored in the OS keychain or equivalent secure store, not in plaintext config files.
- **FR-021**: The application window MUST NOT expose privileged operating-system capabilities to remote content; only locally bundled application code may invoke privileged actions.

#### Existing-feature compatibility

- **FR-022**: The Claude Code terminal feature (015) MUST continue to attach to and control terminal sessions in the desktop application, including any spawned subprocess used for code interaction.
- **FR-023**: The IDE workspace feature (021) MUST continue to read, edit, and save files on the user's local disk from the desktop application, with the same conflict-detection and sandboxing semantics as the web version.
- **FR-024**: The Figma binding and sync features (009, 016, 020) MUST continue to communicate with Figma's plugin and external endpoints from the desktop application.

### Key Entities *(include if feature involves data)*

- **Desktop Installation**: A user's local install of the application on one machine, which has its own bundled-or-external data source choice, settings, and logs.
- **User Data Store**: The graph database that holds the user's projects and authored content; can be the bundled per-machine instance or a configured external instance.
- **Application Update Channel**: The mechanism that maps an installed version to the latest published version and delivers a verified update artifact.
- **Settings & Secrets**: Per-user, per-installation configuration including data source endpoint, credentials, and feature toggles, with secrets stored in the OS secure store.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with no prior developer tooling on their machine can go from downloading the installer to a working home screen in under 5 minutes, on both Windows and macOS, in 95% of attempts.
- **SC-002**: Time-to-interactive (window open, home screen interactive) on launch is under 10 seconds on a representative target machine after the first launch, and under 60 seconds on first launch.
- **SC-003**: Closing the application leaves zero application-owned background processes running after 30 seconds, on 100% of clean shutdowns.
- **SC-004**: When a new version is released, at least 80% of active users are running it within 7 days without any manual intervention beyond clicking the in-app update prompt.
- **SC-005**: 0 data-loss incidents are observed across application updates in a normal release cycle; any required migration completes without user-visible failure or surfaces a clear recovery path.
- **SC-006**: All features that exist in the current web version pass their existing acceptance scenarios when run inside the desktop application — measured by a periodic regression pass.
- **SC-007**: Users who choose to point the app at an external shared data store can do so end-to-end (enter endpoint, validate, switch) in under 2 minutes from settings.
- **SC-008**: Support requests of the form "I can't get Robo-Architect to start / install dependencies / connect to Neo4j" drop by at least 70% within one quarter of the desktop app's general availability, compared to the prior web-only distribution.

## Assumptions

- The desktop application is an additional distribution channel that coexists indefinitely with the existing web/server deployment; both are first-class. The same product code runs in either mode, the team continues to support both, and a "shared backend" mode (desktop app pointing at an external graph data store used by web/server users) is in scope (see FR-010, FR-011). Any feature added going forward is expected to work in both modes, and a periodic regression pass covers both (see SC-006).
- Initial supported operating systems are Windows (10/11, 64-bit) and macOS (Apple Silicon and Intel, current and one prior major version). Linux is out of scope for v1.
- The bundled graph database is the default for solo users; pointing at an external instance is opt-in for teams.
- LLM and other external service calls (Anthropic, ingestion sources, Figma) continue to require network access — the desktop app is not an offline-capable AI product; offline use is limited to features that do not call external services.
- The desktop application does not introduce its own user-account / login concept. In bundled mode it inherits the local OS user identity; in shared-backend mode the external graph data store's existing access controls and credentials apply (credentials stored in the OS secure store per FR-020). Multi-user accounts and SSO/SAML/OIDC are explicitly out of scope for this feature.
- Distribution for v1 uses signed installers downloaded from a known location plus an in-app update channel. OS app stores (Microsoft Store, Mac App Store) and their review/sandboxing/signing constraints are out of scope for v1; they may be revisited later but no work toward them is included here.
- Existing feature work (015 Claude Code terminal, 016/020 Figma binding & recovery, 021 IDE workspace) is treated as an external constraint, not an in-scope rebuild — this feature must not regress them.
- Telemetry/usage analytics, crash reporting, and any privacy-policy commitments are handled at the product level and are not introduced or expanded by this feature.
