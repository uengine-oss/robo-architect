# Feature Specification: Embedded Claude Code Terminal

**Feature Branch**: `015-claude-code-terminal`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/claude_code/router.py`, `frontend/src/features/claudeCode/ui/ClaudeCodeTerminal.vue`, `api/features/prd_generation/prd_artifact_generation.py` (referenced helpers)

## User Scenarios & Testing

### User Story 1 - Run Claude Code inside the architect UI (Priority: P1)

The architect opens the Claude Code terminal panel inside RoboArchitect, picks a working directory, and clicks "Open Terminal". The backend forks a PTY, `chdir`s into the chosen directory, and `execvpe`s the `claude` CLI (falling back to `$SHELL` / `/bin/zsh` if `claude` is missing). Browser keystrokes are forwarded through a WebSocket as JSON `{type: "input", data}`; PTY output is streamed back as raw text frames batched at ~50 Hz with safe UTF-8 boundary handling. Resizes from xterm.js are propagated via `{type: "resize", cols, rows}` which calls `TIOCSWINSZ` and sends `SIGWINCH` to the child.

**Why this priority**: This is the entire feature surface — the terminal is the only way the architect drives Claude Code inside the app.

**Independent Test**: Connect to `WS /api/claude-code/terminal?workdir=/tmp` from a WebSocket client, send `{"type":"input","data":"echo hi\n"}`, and observe `hi` echoed back in raw text frames. Send `{"type":"resize","cols":120,"rows":40}` and confirm no error.

**Acceptance Scenarios**:

1. **Given** the host is POSIX and `claude` is on `PATH`, **When** the WebSocket is opened, **Then** the child process runs `claude` with `TERM=xterm-256color` and `COLORTERM=truecolor` in the requested working directory.
2. **Given** `claude` is not installed, **When** the child `execvpe` fails, **Then** the child silently falls through to `$SHELL` (or `/bin/zsh`) so the user still gets a usable terminal.
3. **Given** the host is non-POSIX (e.g. Windows), **When** a client connects, **Then** the server accepts, sends `{type: "error", message: "Claude Code terminal is only supported on POSIX hosts."}`, and closes with code `1011`.
4. **Given** the user closes the browser tab, **When** the WebSocket disconnects, **Then** the server cancels the read task, closes the master FD, sends `SIGTERM` to the child, and reaps it via `waitpid(WNOHANG)`.
5. **Given** Korean or emoji output crosses a 16 KB read boundary, **When** the read loop forwards data, **Then** the partial multi-byte UTF-8 sequence is buffered until completion so xterm.js never receives mojibake.

### User Story 2 - Browse the filesystem to choose a workdir (Priority: P2)

Before opening the terminal, the user needs a folder picker. They start at `~`, navigate into directories, and the backend returns a flat list of subdirectory names plus the parent path. Hidden entries (`.git`, dotfiles) and macOS bundles (`*.app`) are filtered out so the picker stays focused on real project folders.

**Why this priority**: The terminal works without the picker (the user could type the path manually) but the picker dramatically improves the bootstrapping UX.

**Independent Test**: `GET /api/claude-code/browse-directory?path=~` and assert the response includes `current_path` (absolute), `parent_path`, and a `directories` array with no entry starting with `.` or ending in `.app`.

**Acceptance Scenarios**:

1. **Given** the user passes a path that exists, **When** they call `/browse-directory`, **Then** they receive every non-hidden, non-`.app` subdirectory sorted case-insensitively.
2. **Given** the user passes a non-existent path, **When** they call the endpoint, **Then** the backend resolves to the path's parent if that exists, otherwise falls back to `~`.
3. **Given** the resolved path is `/`, **When** they call the endpoint, **Then** `parent_path` is `null`.
4. **Given** the resolved path is unreadable, **When** they call the endpoint, **Then** `directories` is empty (the `PermissionError` is swallowed) instead of failing.

### User Story 3 - Materialize a generated PRD into a project directory (Priority: P2)

After designing the architecture in RoboArchitect, the user clicks "Set up project for Claude Code". The backend gathers Bounded Contexts from Neo4j, regenerates the full PRD bundle (CLAUDE.md, `.claude/skills/*`, `.claude/agents/*`, `PRD.md`, `.cursorrules`, optional Docker files, per-BC specs, optional Frontend-PRD, README) into an in-memory ZIP, and extracts every entry into the chosen project directory so the user can immediately `cd` into it from the embedded terminal and prompt Claude.

**Why this priority**: This is what makes the terminal architectural rather than generic — it pre-stages the docs and agent configs that let Claude understand the project.

**Independent Test**: With at least one BC in Neo4j, `POST /api/claude-code/setup-project` with a writable `project_path` and a valid `PRDGenerationRequest`, then assert the returned `files_extracted` list matches the on-disk file tree under that path.

**Acceptance Scenarios**:

1. **Given** `tech_stack.ai_assistant == CLAUDE`, **When** setup runs, **Then** `CLAUDE.md`, `.claude/skills/ddd-principles.md`, `eventstorming-implementation.md`, `gwt-test-generation.md`, `<framework>.md`, and per-BC `.claude/agents/<bc>_agent.md` files all appear on disk.
2. **Given** `tech_stack.ai_assistant == CURSOR`, **When** setup runs, **Then** `.cursor/rules/*.mdc` and `.cursorrules` are written instead of the `.claude/` tree.
3. **Given** `include_frontend == true` with a frontend framework, **When** setup runs, **Then** `Frontend-PRD.md` and the appropriate frontend skill/rule are also written.
4. **Given** no Bounded Contexts exist in Neo4j, **When** setup runs, **Then** the response is `404 No Bounded Contexts found`.
5. **Given** the destination directory does not exist, **When** setup runs, **Then** it is created via `os.makedirs(..., exist_ok=True)` along with every nested `.claude/` and `specs/` subdirectory.

### Edge Cases

- The user passes a `~` or relative path — both `setup-project` and `browse-directory` `expanduser` then `abspath` to a deterministic absolute path before any I/O.
- A second WebSocket connects to `/terminal` while the first is still alive — both spawn independent PTY/child pairs; there is no cross-session locking.
- The PTY reports `EIO` (errno 5) because the child exited — the read loop flushes any buffered bytes and returns cleanly.
- The user resizes the terminal before any output has arrived — `_set_pty_size` runs `TIOCSWINSZ` and `SIGWINCH` even on an idle PTY; `ProcessLookupError` is swallowed if the child already died.
- The user picks a working directory that does not exist — the WebSocket still opens; `cwd` defaults to `None` so the child inherits the server's CWD.
- BCs in Neo4j contain forbidden filename characters — `bc_name` is lowercased and spaces replaced with `_` to keep ZIP entry paths safe.

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose `WS /api/claude-code/terminal?workdir=<path>` that bridges a forked PTY (running `claude` with shell fallback) to the WebSocket as a JSON-input / raw-output channel.
- **FR-002**: WebSocket input messages MUST be JSON of the form `{type: "input", data: "<keystrokes>"}` or `{type: "resize", cols: N, rows: N}`; output frames MUST be raw UTF-8 text.
- **FR-003**: The PTY child MUST run with `TERM=xterm-256color`, `COLORTERM=truecolor`, and `cwd` set when the supplied `workdir` resolves to an existing directory.
- **FR-004**: The PTY read loop MUST drain available bytes in 16 KB chunks every ~20 ms, batch them into a single WebSocket frame, and preserve multi-byte UTF-8 boundaries by buffering up to 4 trailing bytes for the next iteration.
- **FR-005**: Resize messages MUST call `fcntl.ioctl(fd, TIOCSWINSZ, ...)` and send `SIGWINCH` to the child; `ProcessLookupError` MUST be swallowed.
- **FR-006**: On WebSocket disconnect (or any exception), the server MUST cancel the read task, close the master FD, send `SIGTERM` to the child PID, and `waitpid(pid, WNOHANG)` to reap it.
- **FR-007**: On non-POSIX hosts the server MUST accept the WebSocket, emit `{type: "error", message: "Claude Code terminal is only supported on POSIX hosts."}`, and close with code `1011` instead of crashing.
- **FR-008**: System MUST expose `GET /api/claude-code/browse-directory?path=<path>` returning `{current_path, parent_path, directories}`, filtering out hidden entries (leading `.`) and `*.app` bundles, sorted case-insensitively.
- **FR-009**: The browse endpoint MUST resolve `~` and relative paths via `expanduser` + `abspath`, fall back to the parent if the path does not exist, and finally to `~` if the parent does not exist either.
- **FR-010**: System MUST expose `POST /api/claude-code/setup-project` accepting `{project_path, prd_request: PRDGenerationRequest}`, build the PRD bundle in-memory as a ZIP, and extract every entry into `project_path` (created if missing).
- **FR-011**: The setup endpoint MUST return `404 "No Bounded Contexts found"` when `get_bcs_from_nodes(None)` is empty, and otherwise return `{success: true, project_path, files_extracted: [...]}`.
- **FR-012**: The bundle MUST branch on `tech_stack.ai_assistant`: `CLAUDE` writes `CLAUDE.md`, `.claude/skills/*`, `.claude/agents/<bc>_agent.md`; `CURSOR` writes `.cursor/rules/*.mdc`. Both always emit `PRD.md`, `.cursorrules`, per-BC `specs/<bc>_spec.md`, and `README.md`.
- **FR-013**: When `tech_stack.include_frontend` is true and `frontend_framework` is set, the bundle MUST include a frontend skill or cursor rule plus `Frontend-PRD.md`.
- **FR-014**: When `tech_stack.include_docker` is true, the bundle MUST include `docker-compose.yml` and `Dockerfile`.
- **FR-015**: All file writes MUST go through `zipfile.ZipFile` first (in-memory) and then be extracted to disk so the on-disk layout exactly mirrors the ZIP that the existing PRD download endpoint produces.

### Key Entities

- **PTY session** (in-process): a `(master_fd, slave_fd, pid)` triple created by `pty.openpty()` + `os.fork()`; lifetime is bound to a single WebSocket.
- **SetupProjectRequest** (Pydantic): `{project_path, prd_request: PRDGenerationRequest}` — the contract for project materialization.
- **PRDGenerationRequest / TechStack / AIAssistant** (existing PRD generation contracts): drive which artifacts the setup endpoint produces.
- **BoundedContext** (Neo4j-derived dict via `get_bcs_from_nodes`): each yields a per-BC `specs/<bc>_spec.md` and, under Claude, a `.claude/agents/<bc>_agent.md`.
- **ClaudeCodeTerminal** (Vue component at `frontend/src/features/claudeCode/ui/ClaudeCodeTerminal.vue`): the xterm.js front-end that hosts the WebSocket and resize wiring.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user can launch the terminal, run `claude` in a chosen directory, and see input/output round-tripped with no perceptible latency above ~100 ms over localhost.
- **SC-002**: Korean characters, emoji, and CJK output stream through the terminal without rendering as replacement characters under any 16 KB read alignment.
- **SC-003**: Closing the browser tab terminates the underlying `claude`/shell process within one second, leaving no orphaned PTY children.
- **SC-004**: `setup-project` produces an on-disk file tree that matches, byte-for-byte, the entries the equivalent PRD ZIP download would contain — verifying via a recursive `diff` shows zero differences.
- **SC-005**: The folder picker returns at most a few hundred entries per directory and never exposes hidden / `.app` items, regardless of how the user navigates.

## Assumptions

- The host is POSIX (macOS or Linux); Windows support is explicitly out of scope and gracefully refused.
- The `claude` CLI is either on `PATH` or the user is comfortable with the shell fallback.
- The user has filesystem permission to create and write under `project_path`; the endpoint does not run any safety check beyond `os.makedirs`.
- Neo4j already contains Bounded Contexts produced by the upstream architecture-design flow; this feature does not seed them.
- Only one user drives the backend at a time (single-user / self-hosted assumption); concurrent terminals are technically possible but not load-tested.
- The xterm.js client correctly batches its keystrokes into the JSON `input` envelope; partial JSON is not buffered server-side.
- The PRD generation helpers (`generate_claude_md`, `generate_cursor_rules`, etc.) are pure functions of `(bcs, config)` and do not depend on any per-request state beyond what is supplied.
