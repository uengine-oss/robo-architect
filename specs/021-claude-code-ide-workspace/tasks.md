---

description: "Task list for feature 021 — Claude Code IDE Workspace"
---

# Tasks: Claude Code IDE Workspace

**Input**: Design documents from `/specs/021-claude-code-ide-workspace/`
**Prerequisites**: plan.md (✓), spec.md (✓), research.md (✓), data-model.md (✓), contracts/rest-api.md (✓), quickstart.md (✓)

**Tests**: Not requested in spec. Tasks below are implementation-only; manual verification follows quickstart.md.

**Organization**: Tasks are grouped by user story (US1 → US2 → US3) so each story can be implemented, demoed, and shipped independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no dependency on incomplete tasks)
- **[Story]**: Maps task to user story (`[US1]`, `[US2]`, `[US3]`); omitted on Setup, Foundational, and Polish phases.
- File paths are absolute relative to repo root `/Users/uengine/robo-architect/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the one new frontend dependency and scaffold empty files so subsequent tasks can edit rather than create.

- [X] T001 [P] Add CodeMirror 6 dependencies to `frontend/package.json`: `@codemirror/state`, `@codemirror/view`, `@codemirror/commands`, `@codemirror/lang-markdown`, `@codemirror/lang-json`, `@codemirror/lang-yaml`, `@codemirror/lang-python`, `@codemirror/lang-javascript`, `@codemirror/lang-vue`. Run `npm install` so `package-lock.json` is updated.
- [X] T002 [P] Create empty backend file `api/features/claude_code/workspace_fs.py` with module docstring describing the sandboxed-filesystem helper boundary (per research D4).
- [X] T003 [P] Create empty backend file `api/features/claude_code/workspace_schemas.py` with module docstring noting these are the Pydantic models for `/tree`, `/file` GET, and `/file` PUT (per data-model.md).
- [X] T004 [P] Create empty frontend file `frontend/src/features/claudeCode/workspace.api.js` with a header comment listing the three fetch helpers it will export: `fetchTree`, `fetchFile`, `saveFile`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The sandbox helper, Pydantic schemas, and API client skeleton are imported by every user story's endpoints / components. Land them once before any story-specific code begins.

**⚠️ CRITICAL**: No user-story phase can start until Phase 2 is complete.

- [X] T005 Implement `resolve_under_root(root: str, path: str) -> str` in `api/features/claude_code/workspace_fs.py` per research D4: realpath both root and joined path, reject absolute `path`, reject `..` components, verify the resolved path starts with `realpath(root) + os.sep` (or equals it), raise `HTTPException(400, "path escapes project root")` on violation, raise `HTTPException(400, "root is not a directory")` when root is not a dir. Emit a structured WARN via Python `logging` on every violation with `{root, path, resolved}` (per research D5).
- [X] T006 [P] Add `read_text_file(abs_path: str) -> tuple[str | None, int, int, bool]` to `api/features/claude_code/workspace_fs.py` returning `(content_or_None, size, mtime_ns, binary)`. Detect binary by reading the first 8 KB and checking for `0x00` bytes or strict-UTF-8 decode failure (per data-model.md). Raise `HTTPException(413, ...)` when `os.stat().st_size > 2 * 1024 * 1024`.
- [X] T007 [P] Add `write_text_file_atomic(abs_path: str, content: str, expected_mtime_ns: int | None) -> tuple[int, int]` to `api/features/claude_code/workspace_fs.py`: when `expected_mtime_ns is None`, require the file not to exist (else raise `HTTPException(400, "expected_mtime_ns required for existing file")`); when set, compare to `os.stat().st_mtime_ns` and raise `HTTPException(409, ...)` with `{current_mtime_ns, current_size}` on mismatch. Write to `<basename>.tmp.<rand>` in the same directory, `os.fsync`, then `os.rename` to the final path (per contracts atomicity note). Return `(new_size, new_mtime_ns)`.
- [X] T008 [P] Add `list_directory(abs_path: str) -> list[dict]` to `api/features/claude_code/workspace_fs.py` per data-model.md filter rules: skip leading-`.` entries except whitelist `{".claude", ".specify"}`, skip `*.app`, sort directories first then files (case-insensitive), each item is `{"name": str, "type": "file" | "directory"}`. Catch `PermissionError` and re-raise as `HTTPException(403, "permission denied")`; catch `FileNotFoundError` and re-raise as `HTTPException(404, "directory not found")`.
- [X] T009 [P] Define Pydantic models in `api/features/claude_code/workspace_schemas.py` per data-model.md: `TreeChild`, `TreeResponse`, `FileResponse` (note `mtime_ns` serialized as `str` to preserve nanosecond precision — use a Pydantic serializer that converts `int → str`), `FileWriteRequest` (with `expected_mtime_ns: str | None` parsed back to int), `FileWriteResponse`, `ConflictResponse`.
- [X] T010 [P] Implement the three fetch helpers in `frontend/src/features/claudeCode/workspace.api.js`: `fetchTree(root, path) → Promise<TreeResponse>`, `fetchFile(root, path) → Promise<FileResponse>`, `saveFile({root, path, content, expectedMtimeNs}) → Promise<FileWriteResponse>`. Use the same `VITE_API_HOST` / `VITE_API_PORT` resolution pattern as `ClaudeCodeTerminal.vue` (lines 55–57). On non-2xx, throw an error whose `.status` and `.body` are inspectable (so callers can branch on 409/413).

**Checkpoint**: `workspace_fs.py`, `workspace_schemas.py`, and `workspace.api.js` are all importable and tested via `python -c "from api.features.claude_code.workspace_fs import resolve_under_root"` succeeding. User-story phases can now begin in parallel.

---

## Phase 3: User Story 1 — 3-pane VS Code-like workspace (Priority: P1) 🎯 MVP

**Goal**: Click Claude Code button → 3-pane workspace renders. File tree on the left lists root contents; clicking a text file shows its content with syntax highlighting in the middle pane (read-only is fine for this slice — editing arrives in US2). Right pane is the existing terminal, unchanged. Dividers are draggable.

**Independent Test**: Quickstart S1, S2, and S3. After this phase ships, the architect can browse and *view* generated PRDs side-by-side with `claude` running — already a meaningful upgrade over the terminal-only experience.

### Implementation for User Story 1

- [X] T011 [P] [US1] Add `GET /tree` endpoint to `api/features/claude_code/router.py`: query params `root: str` (required), `path: str = ""`. Call `resolve_under_root` then `list_directory`, return `TreeResponse`. Emit a structured INFO log on `path == ""` calls only (per research D5) with `{root, child_count}`.
- [X] T012 [P] [US1] Add `GET /file` endpoint to `api/features/claude_code/router.py`: query params `root: str`, `path: str` (both required). Call `resolve_under_root` then `read_text_file`, build and return `FileResponse` (omit `content` when `binary=True`). Let `HTTPException` from helpers propagate so 400/403/404/413 all surface correctly.
- [X] T013 [P] [US1] Create `frontend/src/features/claudeCode/ui/FileTreePane.vue`: accepts `root: string` prop; on mount calls `fetchTree(root, "")`; renders a list of children where directories are clickable to expand/collapse (lazy-load children via `fetchTree(root, child.path)` on first expand, cache in a `Map<string, TreeNode>`); files emit a `@open(path)` event on click. Show a small spinner per node while its expand request is in flight; show error text on failure. Apply the FR-016 filter on the *frontend display* as a defence-in-depth (server already filters; do not duplicate logic, just sanity-check).
- [X] T014 [P] [US1] Create `frontend/src/features/claudeCode/ui/FileEditorPane.vue` with read-only behavior for this slice: accepts `root: string` and `path: string | null` props; when `path` becomes non-null, calls `fetchFile(root, path)`; mounts a CodeMirror 6 view in `EditorView` with `EditorState.readOnly = true` (editing comes in US2). Choose language extension by file extension: `.md` → markdown, `.json` → json, `.yml`/`.yaml` → yaml, `.py` → python, `.js`/`.ts` → javascript, `.vue` → vue, otherwise plain text. Render an active-tab strip with the basename. Show "binary file — preview not supported" placeholder when response `binary === true`. Show "file too large to edit in browser (X KB)" placeholder when caller catches a 413. Show "Select a file from the tree to open it" when `path === null`.
- [X] T015 [US1] Create `frontend/src/features/claudeCode/ui/ClaudeCodeWorkspace.vue` — the 3-pane shell. Accepts the same `workdir` prop the terminal accepts today (so `App.vue` swap is drop-in). Layout: flex-row with three children: `<FileTreePane :root="workdir" @open="onOpenFile" />`, `<FileEditorPane :root="workdir" :path="activePath" />`, `<ClaudeCodeTerminal :workdir="workdir" />` (imported from `./ClaudeCodeTerminal.vue`, passed through verbatim — FR-015). Implement two draggable vertical dividers (mirror the navigator-resizer pattern in `frontend/src/App.vue` lines 49–69). Each pane has a configurable min-width (suggest 180 / 320 / 320 px for tree / editor / terminal).
- [X] T016 [US1] Add tree-collapse and editor-collapse toggles to `frontend/src/features/claudeCode/ui/ClaudeCodeWorkspace.vue` (FR-004). Persist collapsed state and pane widths in `localStorage` keys `claude_code_workspace_tree_width`, `claude_code_workspace_editor_width`, `claude_code_workspace_tree_collapsed`, `claude_code_workspace_editor_collapsed` (mirror `App.vue` `navigator_panel_width` / `navigator_collapsed` pattern).
- [X] T017 [US1] Modify `frontend/src/App.vue`: import `ClaudeCodeWorkspace` instead of `ClaudeCodeTerminal` for the tab map only. Replace `'Claude Code': markRaw(ClaudeCodeTerminal)` (line 38) with `'Claude Code': markRaw(ClaudeCodeWorkspace)`. The existing `claudeCodeWorkdir` ref and `provide('openClaudeCode', …)` flow stay untouched. **Do not** delete the `ClaudeCodeTerminal` import — it is still used as a child of the new workspace and may be referenced elsewhere.

**Checkpoint**: Click Claude Code button → 3 panes render. Click a `.md` file → it opens read-only with Markdown highlighting. Drag dividers → panes resize. Right pane terminal is unchanged. Quickstart S1, S2, S3 all pass. SC-001 (5,000-file root tree under 1s) and SC-002 (text file under 1MB opens under 500ms) verifiable.

---

## Phase 4: User Story 2 — Edit and save files (Priority: P2)

**Goal**: Editor becomes writable. Architect can type, see a dirty indicator, save with Cmd-S, and see the indicator clear. Switching files or closing the panel with unsaved edits prompts to save / discard / cancel.

**Independent Test**: Quickstart S4 and S5. With US1 already shipped, this story is purely additive — no US1 behavior should regress.

### Implementation for User Story 2

- [X] T018 [P] [US2] Add `PUT /file` endpoint to `api/features/claude_code/router.py`: body `FileWriteRequest`. Call `resolve_under_root` then `write_text_file_atomic(...expected_mtime_ns=int(req.expected_mtime_ns) if req.expected_mtime_ns else None)`. Return `FileWriteResponse` with `mtime_ns` serialized as string. The 409/400/404 paths are already raised as `HTTPException` by the helper — let them propagate. FastAPI body-size limits already cap at 2 MiB by default; if not, set `max_request_body_size` accordingly so 413 fires server-side too.
- [X] T019 [US2] Switch `frontend/src/features/claudeCode/ui/FileEditorPane.vue` from read-only to read-write: drop `EditorState.readOnly`, add an `update` listener that compares current doc to `originalContent` and toggles a `dirty` ref. Render a small "●" before the active tab title when dirty (FR-008).
- [X] T020 [US2] Add a Save action in `frontend/src/features/claudeCode/ui/FileEditorPane.vue`: keyboard binding (Cmd/Ctrl-S via CodeMirror `keymap.of([...])`) and a visible Save button. On save, call `saveFile({root, path, content: currentContent, expectedMtimeNs: mtimeNs})`. On 200, set `originalContent := currentContent`, update `mtimeNs := response.mtime_ns`, clear the dirty indicator, show a brief "Saved" toast/status. On 409, surface the FR-011 conflict banner (the actual reload-or-keep UI lands in US3 — for US2's slice, show a minimal error toast saying "File changed on disk; refresh to continue" so dirty data is *never* lost). On 4xx/5xx other than 409, show a non-blocking error toast and keep the buffer dirty (FR-009 / Story 2 #4).
- [X] T021 [US2] Add the unsaved-changes guard in `frontend/src/features/claudeCode/ui/ClaudeCodeWorkspace.vue` for in-app file switching: when `FileTreePane` emits `@open(newPath)` and the current `EditorBuffer.dirty === true`, intercept and show a confirm modal (Save / Discard / Cancel). Save then switch / Discard then switch / Cancel → no-op. (FR-009)
- [X] T022 [US2] Add the unsaved-changes guard in `frontend/src/features/claudeCode/ui/ClaudeCodeWorkspace.vue` for panel close + tab switch: hook into the App tab change (via the injected `activeTab` from `App.vue`) and into `window.onbeforeunload`. When `activeTab` changes away from `Claude Code` with a dirty buffer, show the same confirm modal; on `beforeunload`, set `event.returnValue` to a non-empty string to trigger the browser's native "leave this page?" prompt. (FR-009)

**Checkpoint**: Open a file, type, save — content lands on disk via 200. Try to switch files / close the panel with dirty buffer — prompted every time. Quickstart S4 and S5 pass. US1 still works (no regression on read-only flows like binary placeholder, oversize placeholder).

---

## Phase 5: User Story 3 — Tree stays in sync with Claude's writes (Priority: P2)

**Goal**: Manual Refresh button on the tree re-reads the directory and surfaces files Claude created in the right pane. If the open file's `mtime_ns` advanced on disk: clean buffers reload silently, dirty buffers show a non-blocking Reload-or-Keep banner. The save-time 409 path is wired into the same banner so "Keep my changes" eventually persists.

**Independent Test**: Quickstart S6 and S7 (sub-A and sub-B).

### Implementation for User Story 3

- [X] T023 [P] [US3] Add a Refresh control to `frontend/src/features/claudeCode/ui/FileTreePane.vue` (a small icon button at the tree's header). On click: re-fetch the root with `fetchTree(root, "")` AND in parallel re-fetch every currently-expanded path. Merge results into the existing `TreeNode` map preserving expand state for paths that still exist; drop nodes whose paths no longer appear; mark nodes with the `error` field surfaced if their re-fetch returned 404/403. Emit a `@externalCheck` event after the refresh completes.
- [X] T024 [P] [US3] Add the external-modification check in `frontend/src/features/claudeCode/ui/FileEditorPane.vue`. Expose a method `checkExternalModification()` that, when a file is open, calls `fetchFile(root, activePath)` and compares the response `mtime_ns` to the buffer's `mtimeNs`:
  - If equal → no-op.
  - If advanced AND buffer is **clean** → silently replace `originalContent` and `currentContent` with the new response content, update `mtimeNs`. Show a subtle "Reloaded from disk" status for ~2s.
  - If advanced AND buffer is **dirty** → set `pendingExternalReload = { newMtimeNs, newSize }` so the banner renders.
- [X] T025 [US3] Wire the tree's `@externalCheck` event from T023 into `FileEditorPane.checkExternalModification()` via `frontend/src/features/claudeCode/ui/ClaudeCodeWorkspace.vue`: when the tree refresh completes, the workspace shell calls the editor's check method (use a `ref` on the `FileEditorPane` component to invoke it).
- [X] T026 [US3] Render the Reload-or-Keep banner in `frontend/src/features/claudeCode/ui/FileEditorPane.vue` whenever `pendingExternalReload !== null`. Two buttons:
  - **Reload from disk** → re-call `fetchFile(root, activePath)`, set `originalContent := currentContent := response.content`, `mtimeNs := response.mtime_ns`, clear `pendingExternalReload` and the dirty flag.
  - **Keep my changes** → clear `pendingExternalReload` only. The buffer stays dirty. Next save will hit the 409 path (handled in T027).
- [X] T027 [US3] Upgrade the save-flow 409 handler in `frontend/src/features/claudeCode/ui/FileEditorPane.vue` (replacing the minimal-toast fallback added in T020): on 409, set `pendingExternalReload = { newMtimeNs: response.body.current_mtime_ns, newSize: response.body.current_size }` so the same banner from T026 appears. The "Keep my changes" branch on a 409 retry must update `mtimeNs := newMtimeNs` and re-`saveFile(...)` exactly once — that second save uses the now-current mtime so it succeeds with 200. Add a guard so the retry happens only once per click to prevent infinite loops if the file is being rewritten in a tight loop.

**Checkpoint**: Quickstart S6 (Claude creates file → refresh → tree updates → file opens) and S7 sub-A (clean buffer auto-reloads silently) and S7 sub-B (dirty buffer shows banner; "Keep my changes" eventually persists via the 409 retry). All US1 and US2 flows still pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T028 [P] Run quickstart S1–S8 end-to-end against a real `claude` CLI in `~/projects/<sample>` and record results. Address any failure before sign-off. Reference: `specs/021-claude-code-ide-workspace/quickstart.md`.
- [ ] T029 [P] Run the feature-015 non-regression block (last section of quickstart.md): terminal latency, Korean/emoji/CJK fidelity, child cleanup on panel close. Confirm SC-006.
- [ ] T030 [P] Verify SC-001 (5,000-file root tree initial paint < 1s) and SC-002 (text file under 1 MB opens < 500ms) and SC-004 (save < 500ms) in the browser's DevTools Performance tab against a synthetic project.
- [ ] T031 [P] Confirm sandbox WARN log fires (research D5) by manually issuing `curl 'http://localhost:8000/api/claude-code/tree?root=/tmp/proj&path=../../etc'` and grepping the backend stdout for the WARN entry.
- [X] T032 [P] Update the user-facing button tooltip in `frontend/src/app/layout/TopBar.vue` (line 148): change `title="Claude Code 터미널 열기"` to something like `title="Claude Code 워크스페이스 열기"` to match the new layout. Pure copy change.
- [X] T033 Verify `CLAUDE.md` speckit block already points to this plan (was updated in `/speckit-plan`). No edit expected — this task is a sanity check before merge.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no deps — start immediately.
- **Phase 2 (Foundational)**: depends on Phase 1. **Blocks all user stories.**
- **Phase 3 (US1, P1)**: depends on Phase 2. **MVP** — ships independently.
- **Phase 4 (US2, P2)**: depends on Phase 2 *and* US1's `FileEditorPane.vue` (US1 creates the file in read-only mode; US2 flips it to read-write). Must come after US1.
- **Phase 5 (US3, P2)**: depends on Phase 2 *and* the editor + save infrastructure US1+US2 built. Must come after US2 (the 409 handler T027 upgrades the toast US2 added in T020).
- **Phase 6 (Polish)**: depends on US1 always, US2/US3 if those stories shipped.

### User Story Dependencies (within Phase 4 & 5)

- US1 → US2: same file (`FileEditorPane.vue`) is edited in both; US2 cannot start before US1 lands the read-only baseline.
- US2 → US3: T027 upgrades the 409 handler from US2's T020. Sequential, not parallel.
- US1 stands alone as MVP.

### Within each story

- Endpoints and components marked `[P]` can run in parallel because they touch different files.
- The shell (`ClaudeCodeWorkspace.vue`) is the integration point — its task (T015) sequences after the panes it composes (T013, T014).
- `App.vue` swap (T017) is sequenced last in US1 because it activates the new shell only after the shell exists.

---

## Parallel Opportunities

### Phase 1 — all parallel

```text
T001  npm install codemirror deps              (frontend/package.json)
T002  scaffold workspace_fs.py                  (api/features/claude_code/)
T003  scaffold workspace_schemas.py             (api/features/claude_code/)
T004  scaffold workspace.api.js                 (frontend/src/features/claudeCode/)
```

### Phase 2 — T005 first, then T006/T007/T008/T009/T010 in parallel

T005 defines the sandbox helper that T006/T007/T008 import. Once T005 lands:

```text
T006  read_text_file        (workspace_fs.py)
T007  write_text_file_atomic (workspace_fs.py)   # same file as T006/T008 — sequence within file
T008  list_directory        (workspace_fs.py)    # same file — sequence
T009  Pydantic schemas      (workspace_schemas.py)  [P with T010]
T010  fetch helpers         (workspace.api.js)     [P with T009]
```

Note: T006/T007/T008 all edit `workspace_fs.py` — do them sequentially in one editor session even though they're conceptually parallel.

### Phase 3 (US1) — backend + frontend in parallel after Phase 2

```text
T011 [P]  GET /tree endpoint   (router.py)         # backend track
T012 [P]  GET /file endpoint   (router.py)         # backend track — sequence with T011 in same file
T013 [P]  FileTreePane.vue                          # frontend track A
T014 [P]  FileEditorPane.vue                        # frontend track B
T015      ClaudeCodeWorkspace.vue                   # blocks on T013 + T014
T016      collapse / persistence                    # same file as T015 — sequence
T017      App.vue tab swap                          # last
```

### Phase 4 (US2) — mostly sequential within FileEditorPane.vue

```text
T018 [P]  PUT /file endpoint   (router.py)
T019      flip editor read-write          (FileEditorPane.vue)
T020      Save shortcut + button         (FileEditorPane.vue)
T021      file-switch unsaved guard      (ClaudeCodeWorkspace.vue)
T022      panel-close / tab-switch guard (ClaudeCodeWorkspace.vue)
```

### Phase 5 (US3)

```text
T023 [P]  Refresh + tree re-fetch        (FileTreePane.vue)
T024 [P]  external-mod check method      (FileEditorPane.vue)
T025      wire tree → editor             (ClaudeCodeWorkspace.vue)
T026      Reload-or-Keep banner UI       (FileEditorPane.vue)
T027      upgrade 409 handler            (FileEditorPane.vue)
```

### Phase 6 — all parallel

T028–T032 are independent verifications; T033 is a sanity check.

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 (Setup) — ~30 min wall-clock with parallel scaffolding.
2. Phase 2 (Foundational) — ~half-day; T005 is the single bottleneck, the rest parallelize.
3. Phase 3 (US1) — bulk of the work; ~1–2 days.
4. **STOP and validate**: run quickstart S1, S2, S3 + non-regression block.
5. Demo: architect can browse and view files alongside `claude`. Already valuable.

### Incremental Delivery

- **Slice 1** (US1 alone): read-only viewer + 3-pane layout. Ship.
- **Slice 2** (US2 added): editing + save + unsaved guards. Ship.
- **Slice 3** (US3 added): tree refresh + reload-or-keep + 409 retry. Ship.

Each slice is independently testable per its quickstart scenarios.

### Parallel Team Strategy

Phase 2 done → split:
- Dev A: backend track (T011 + T012, then T018, then nothing in US3 since refresh is frontend-only).
- Dev B: frontend tree track (T013, then T023).
- Dev C: frontend editor track (T014, then T019/T020, then T024/T026/T027).
- Integration is owned by whoever does T015 / T017 / T021 / T022 / T025 — sequence them as the panes/endpoints land.

---

## Notes

- **No tests requested** in spec — implementation only. Quickstart.md is the verification surface.
- **No new feature module** — every backend file lives under `api/features/claude_code/`, every frontend file under `frontend/src/features/claudeCode/` (Constitution principle V).
- **Right pane unchanged** — `ClaudeCodeTerminal.vue` and `WS /api/claude-code/terminal` are not edited (FR-015, SC-006).
- **`mtime_ns` precision** — all three layers (server response, client buffer, PUT request) treat `mtime_ns` as a string at the JSON boundary. Only `workspace_fs.py` ever does `int(...)` on it.
- **Sandboxing is the security boundary** — every endpoint must call `resolve_under_root` before any other filesystem call. Skipping it is the most likely vulnerability.
- **Single user assumption** inherited from feature 015 — concurrent workspaces against the same root are not supported and not load-tested.
