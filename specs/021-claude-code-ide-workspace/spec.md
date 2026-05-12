# Feature Specification: Claude Code IDE Workspace

**Feature Branch**: `021-claude-code-ide-workspace`
**Created**: 2026-05-09
**Status**: Draft
**Input**: User description: "지금 클로드 코드라고 한 버튼을 클릭했을 때 그 오른쪽 왼쪽 부분에는 파일 트리가 나오고 일종의 VS 코드의 레이아웃처럼 중간에는 파일을 선택하면 파일을 편집하는 편집기가 소스코드를 편집하는 편집기가 들어오고 맨 우측에는 클로드 코드 기존에 있던 클로드 코드가 뜨게끔 그렇게 해줘 그렇게 해서 생성된 파일을 선택해서 볼 수도 있고 맨 우측에서 클로드 코드를 통해서 편집도 할 수 있고"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 3-pane VS Code-like workspace appears on Claude Code button click (Priority: P1)

The architect clicks the existing **Claude Code** button in the top bar. Instead of a terminal-only view, RoboArchitect now opens a three-pane workspace that mirrors the VS Code layout:

- **Left pane** — a file tree rooted at the chosen working directory (the same directory the existing folder picker selects).
- **Middle pane** — an empty editor area with a placeholder ("Select a file from the tree to open it"). When the architect clicks any file in the tree, that file's contents load into the editor with syntax highlighting and the file name shows as an active tab.
- **Right pane** — the existing Claude Code terminal, unchanged in behavior, sized to fill its column.

The three panes are arranged horizontally and each border between panes is draggable so the architect can resize columns to taste. The right pane keeps the same WebSocket terminal session that the current button opens today.

**Why this priority**: This is the structural change the user asked for. Without it, the rest of the feature (editing, refreshing on Claude output) has nothing to live in. Delivering just this layout — even with a read-only editor — is already a usable upgrade because the architect can browse generated files alongside Claude.

**Independent Test**: Click the Claude Code button after this story ships. Verify (a) the panel opens with three visible columns in the order tree → editor → terminal, (b) clicking a file in the tree displays that file's content in the middle, (c) the right column still drives `claude` exactly as it does today, and (d) dragging a divider resizes the adjacent columns.

**Acceptance Scenarios**:

1. **Given** the architect has not yet picked a working directory, **When** they click the Claude Code button, **Then** the same folder picker that exists today appears first; once a directory is chosen, the three-pane workspace renders with that directory as the file tree root and that same directory as the terminal `cwd`.
2. **Given** the workspace is open, **When** the architect clicks a text file in the left tree, **Then** the file opens in the middle editor with appropriate syntax highlighting (e.g. Markdown, JSON, Python, TypeScript, YAML) and an active-tab label showing the file name.
3. **Given** the workspace is open, **When** the architect clicks a folder in the tree, **Then** the folder expands/collapses in place without affecting the editor or terminal panes.
4. **Given** the workspace is open, **When** the architect drags the divider between tree and editor, **Then** both panes resize live and the terminal column is unaffected; the same applies to the divider between editor and terminal.
5. **Given** the architect closes and reopens the Claude Code panel, **When** the workspace reopens against the same working directory, **Then** the panel restores in three-pane layout (the previously focused file does not need to be restored in v1 — see Assumptions).

---

### User Story 2 - Edit and save files from the middle editor (Priority: P2)

After opening a file in the middle editor, the architect can type into it and save. Saving writes the buffer back to disk in the working directory. An unsaved indicator (e.g. a dot on the tab) shows whenever the buffer differs from disk; the indicator clears once the save succeeds.

**Why this priority**: Read-only viewing already delivers value (Story 1), but the user explicitly asked for an editor — so editing is the natural next slice. It is P2 rather than P1 because the architect can fall back to "ask Claude to edit it" via the terminal pane if the editor is read-only.

**Independent Test**: Open a `.md` file from the tree, type a new line, press the save shortcut (or click a Save button), and verify (a) the on-disk file now contains the new line, (b) the unsaved indicator clears, and (c) re-opening the same file shows the saved content.

**Acceptance Scenarios**:

1. **Given** a file is open and unmodified, **When** the architect types any character, **Then** an unsaved-changes indicator appears on the file's tab.
2. **Given** there are unsaved changes, **When** the architect triggers Save (keyboard shortcut and/or visible button), **Then** the buffer is persisted to disk under the same path and the indicator clears.
3. **Given** there are unsaved changes, **When** the architect attempts to switch to a different file in the tree, **Then** the system warns ("You have unsaved changes — discard or save?") and only switches after the architect chooses save or discard.
4. **Given** the file's parent directory was deleted out-of-band (e.g. by Claude in the terminal pane), **When** the architect tries to save, **Then** the save fails with a clear error and the buffer remains unsaved so no work is silently lost.
5. **Given** a file is opened that exceeds a sane size limit (see Assumptions), **When** the architect tries to open it, **Then** the editor refuses to load it and shows a "file too large to edit in browser" message instead of locking the UI.

---

### User Story 3 - File tree stays in sync with files Claude Code creates or modifies (Priority: P2)

When Claude (driven from the right-pane terminal) creates, renames, or deletes files in the working directory, the architect can see those changes in the left tree without having to fully reopen the workspace. At minimum a manual **Refresh** affordance on the tree re-reads the directory; ideally the tree auto-refreshes when files change. If a currently-open file is modified on disk by Claude, the editor either reloads it (when the buffer is clean) or warns the architect (when the buffer is dirty) so they can choose.

**Why this priority**: This is what makes the three-pane layout feel "live" — the user explicitly mentioned wanting to "see generated files." A manual refresh button is sufficient for v1; live watch is a polish item.

**Independent Test**: With the workspace open against an empty directory, run `claude` in the right pane and ask it to create a new file. Click the tree's Refresh control (or wait if auto-watch is implemented). Verify the new file appears in the tree and is openable in the editor with the content Claude wrote.

**Acceptance Scenarios**:

1. **Given** Claude creates `foo.md` in the working directory via the terminal, **When** the architect refreshes the tree, **Then** `foo.md` appears in the correct directory node.
2. **Given** an already-open file is rewritten on disk by Claude, **When** the architect's local buffer is clean, **Then** the editor silently reloads the new content; **when** the local buffer is dirty, **Then** a non-blocking banner appears offering "Reload from disk" or "Keep my changes."
3. **Given** Claude deletes an open file, **When** the architect refreshes the tree, **Then** the tree node disappears and the editor tab shows a "file no longer exists on disk" indicator while still letting the architect save-as a new path.

### Edge Cases

- **Binary files** (images, archives, PDFs) — the editor must not attempt to render them as text. It should detect binary content and show a "binary file — preview not supported" placeholder.
- **Symlinks and hidden files** — the tree should follow the same filtering rules as the existing folder picker (no leading `.`, no `*.app` bundles) for consistency, but `.claude/` and `.specify/` are explicit exceptions because the architect needs them visible.
- **Very deep directory trees** — the tree must lazy-load children when a folder is expanded rather than walking the entire tree on open.
- **Permission-denied folders** — a folder the user can list metadata for but not enter should still appear in the tree with a clear "no access" indicator instead of breaking expansion.
- **Files renamed in-flight** — if a file is renamed by Claude while open in the editor, the editor's tab should still hold the old path's buffer and warn on save (covered in Story 2 #4 pattern).
- **Concurrent editor + terminal edits to the same file** — the tree-refresh / reload-prompt flow described in Story 3 #2 is the only conflict-resolution mechanism; the system does not attempt three-way merging.
- **Workspace closed mid-edit** — closing the Claude Code panel with unsaved changes must prompt the same warning as switching files (Story 2 #3) so work is not lost on accidental close.
- **Pane collapse** — the architect should be able to collapse the tree or editor pane to maximize the terminal (mirroring the existing terminal-only experience), and re-expand them via a visible toggle.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Claude Code button MUST open a three-pane workspace with a file tree on the left, a code editor in the middle, and the existing Claude Code terminal on the right, in that left-to-right order.
- **FR-002**: The file tree MUST be rooted at the working directory the architect chooses via the existing folder picker, and that same directory MUST be passed as `cwd` to the Claude Code terminal session in the right pane.
- **FR-003**: The vertical dividers between panes MUST be drag-resizable, with each pane honouring a minimum width that keeps it usable; dragging one divider MUST NOT collapse or push another pane below its minimum.
- **FR-004**: The architect MUST be able to collapse the tree pane and/or the editor pane to maximize the terminal, and re-expand them, without losing the terminal session or the editor's open file.
- **FR-005**: Clicking a file node in the tree MUST load that file's text content into the middle editor and surface the file's name as an active tab; clicking a folder node MUST toggle expand/collapse in place.
- **FR-006**: The editor MUST provide syntax highlighting for the file types produced by RoboArchitect's PRD generator and by Claude Code (at minimum: Markdown, JSON, YAML, Python, TypeScript/JavaScript, Vue, plain text).
- **FR-007**: The editor MUST allow the architect to modify the open file's buffer and persist it to disk via an explicit save action (keyboard shortcut and/or visible Save control).
- **FR-008**: The editor MUST display an unsaved-changes indicator on the active tab whenever the in-memory buffer differs from disk, and clear it on a successful save.
- **FR-009**: When the architect attempts to switch files, close the Claude Code panel, or close the workspace browser tab while there are unsaved changes, the system MUST prompt before discarding the buffer.
- **FR-010**: The file tree MUST expose a manual Refresh control that re-reads the working directory and updates visible nodes (additions, deletions, renames) without losing the editor's currently open buffer.
- **FR-011**: When a file currently open in the editor is modified on disk by an external actor (typically Claude in the terminal pane), the system MUST either silently reload it (clean buffer) or surface a non-blocking reload-or-keep prompt (dirty buffer); it MUST NOT silently overwrite the architect's unsaved edits.
- **FR-012**: The tree MUST lazy-load directory contents on expand (not walk the entire tree on workspace open) so deep project trees do not stall the UI.
- **FR-013**: Binary files MUST be detected on open and rendered as a "binary file — preview not supported" placeholder rather than as garbled text.
- **FR-014**: Files larger than a defined limit (see Assumptions) MUST be refused with a clear message rather than loaded into the browser.
- **FR-015**: The right-hand terminal pane MUST preserve every behavior of the current Claude Code terminal: PTY-backed `claude` (with shell fallback), JSON-input/raw-output WebSocket protocol, resize forwarding, and clean teardown on disconnect (i.e. no behavioral regression from feature 015).
- **FR-016**: The tree MUST hide the same noisy entries the current folder picker hides (leading `.`, `*.app`) **except** for `.claude/` and `.specify/` directories, which MUST remain visible because they are first-class outputs of RoboArchitect.

### Key Entities *(include if feature involves data)*

- **Workspace session** — the in-browser state for one open Claude Code panel: working directory, expanded tree nodes, currently active file, dirty buffers per open file.
- **File tree node** — a `{path, name, type: file | directory, children?: lazy}` record used by the left pane; children are populated only when the node is expanded.
- **Editor buffer** — the in-memory contents of one open file plus a `dirty` flag and a last-known disk timestamp/hash used to detect external modifications.
- **Existing PTY session** — unchanged from feature 015; the right pane continues to own this and is not aware of the tree or editor.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Opening a project directory of up to ~5,000 files renders the workspace's initial tree (root level only, lazy children) in under one second on a modern laptop.
- **SC-002**: Selecting a text file under 1 MB displays its contents in the editor in under 500 ms from click to first paint.
- **SC-003**: When Claude generates a new file via the terminal pane, the architect can see that file in the tree and open it in the editor in under five seconds (manual-refresh worst case).
- **SC-004**: Saving a file under 1 MB completes in under 500 ms and the unsaved indicator clears within the same paint cycle.
- **SC-005**: 100% of accidental "close panel with unsaved changes" attempts surface the save/discard prompt — i.e. zero silent data loss in user testing of Story 2.
- **SC-006**: The right-hand terminal continues to satisfy every success criterion from feature 015 (latency, UTF-8 fidelity, clean teardown) — verifying via the existing Story 1 / SC-001..SC-003 tests of feature 015 still pass.

## Assumptions

- The Claude Code panel remains a single tab inside the existing right-hand panel area (the same place the terminal lives today). It does not become a full-screen modal in v1.
- The existing folder picker (feature 015's `GET /api/claude-code/browse-directory`) is reused for choosing the workspace root; no new folder-picking UX is introduced.
- Workspace state (which file was active, dirty buffers) does **not** need to survive a page reload in v1 — closing the tab discards in-memory buffers after the unsaved-changes prompt.
- The "max file size to load into the editor" threshold is set at a reasonable default (e.g. 2 MB) for v1; tuning is a polish concern.
- Live filesystem watching (auto-refresh on Claude writes) is **out of scope for v1**; manual refresh is sufficient. Auto-watch can be added in a follow-up.
- The architect is the only person editing a given working directory at a time (single-user / self-hosted assumption inherited from feature 015); no multi-cursor collaborative editing.
- The existing terminal session's WebSocket lifecycle is not changed — it still tears down when the panel closes, and re-opens fresh on the next click.
- The host OS is POSIX (macOS or Linux), inheriting the same constraint as feature 015's terminal.
- Syntax highlighting uses an embeddable in-browser editor capable of the file types listed in FR-006; the choice of editor library is a planning-phase concern, not a spec concern.
