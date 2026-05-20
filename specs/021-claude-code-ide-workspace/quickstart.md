# Quickstart: Claude Code IDE Workspace

Manual smoke test for feature 021. Run after the implementation lands; verifies the spec's acceptance scenarios end-to-end.

## Prerequisites

- macOS or Linux host (POSIX-only, inherited from feature 015).
- `claude` CLI on `PATH` (or shell fallback acceptable).
- Backend running (`uv run uvicorn api.main:app --reload --port 8000`).
- Frontend running (`cd frontend && npm run dev`).
- A sample project directory with a few files of mixed types (`.md`, `.json`, `.py`, plus one image / binary).

## Scenarios

### S1 — Three-pane layout opens (Story 1, FR-001)

1. Click the **Claude Code** button in the top bar.
2. If you haven't picked a working directory yet, pick one in the folder picker (existing flow).
3. **Expect**: the panel opens with three columns — file tree on the left, empty editor in the middle, terminal on the right. The terminal prompt should already be at the project root and `claude` (or shell fallback) is running.

✅ Pass when: all three columns are visible in the documented order and the terminal is functional.

---

### S2 — Open a file in the editor (Story 1, FR-005, FR-006)

1. In the left tree, expand a directory by clicking it.
2. Click any `.md` file.
3. **Expect**: middle pane shows the file's content with Markdown syntax highlighting; the file's name appears as an active tab; cursor is active in the editor.
4. Click a `.json` file — switching loads new content with JSON highlighting; tab updates.

✅ Pass when: highlighting differs between Markdown and JSON, and switching files loads the new content correctly.

---

### S3 — Resize and collapse panes (FR-003, FR-004)

1. Drag the divider between the tree and editor — both resize live; terminal column does not move.
2. Drag the divider between editor and terminal — terminal width shrinks, editor grows.
3. Click the tree-collapse toggle — tree pane disappears, editor expands into the freed space.
4. Click again — tree pane returns at its previous width.
5. Repeat 3–4 for the editor pane.

✅ Pass when: dragging and collapsing both work; collapsing the tree never tears down the terminal session (verify by typing in the terminal after each toggle).

---

### S4 — Edit and save (Story 2, FR-007, FR-008)

1. Open a `.md` file. Type a new line.
2. **Expect**: dirty indicator (dot) appears on the tab.
3. Press the save shortcut (Ctrl/Cmd-S) or click the visible Save button.
4. **Expect**: dirty indicator clears; toast or status confirms save.
5. In a separate terminal (outside the workspace), `cat` the file — the new line is on disk.
6. Reopen the file in the workspace — content matches what you saved.

✅ Pass when: round-trips cleanly and the on-disk content is exactly the buffer.

---

### S5 — Switch / close with unsaved changes (FR-009)

1. Open a file, type changes, do **not** save.
2. Click a different file in the tree.
3. **Expect**: a save / discard prompt appears. Choose **Discard**.
4. The first file's edits are gone; the second file opens.
5. Repeat with **Save** chosen instead — the first file's edits are persisted before the second file opens.
6. With unsaved changes, click outside to close the Claude Code panel (or switch tabs in the top bar).
7. **Expect**: same prompt fires.

✅ Pass when: every navigation away with a dirty buffer triggers the prompt; Discard truly discards, Save persists then continues.

---

### S6 — Claude creates a file → tree refresh (Story 3, FR-010)

1. Open the workspace against an empty directory.
2. In the right pane (terminal), run `claude` and ask it to "create a file foo.md with the content 'hello world'".
3. After Claude reports done, click the tree's **Refresh** control.
4. **Expect**: `foo.md` appears in the tree. Click it — the editor shows `hello world`.

✅ Pass when: Refresh surfaces the new file and it opens cleanly.

---

### S7 — Claude rewrites the open file (Story 3, FR-011)

**Sub-scenario A: clean buffer (silent reload)**

1. Open `foo.md` from S6 — buffer is clean.
2. In the terminal, ask Claude to rewrite the file with new content.
3. After Claude finishes, click Refresh.
4. **Expect**: the editor silently reloads to show Claude's new content. No prompt because the buffer was clean.

**Sub-scenario B: dirty buffer (reload-or-keep banner)**

1. Open `foo.md`. Type local edits — buffer is dirty.
2. In the terminal, ask Claude to rewrite the file again.
3. Click Refresh.
4. **Expect**: a non-blocking banner appears offering **Reload from disk** (discards local edits) and **Keep my changes** (retains the buffer; next save will conflict-detect).
5. Click **Keep my changes**, then save.
6. **Expect**: 409 conflict path triggers the same banner; choose **Keep my changes** again. The frontend re-fetches mtime and re-PUTs, this time succeeding.

✅ Pass when: clean buffer auto-reloads silently; dirty buffer shows the banner; "keep" path eventually persists without losing user edits.

---

### S8 — Edge cases (FR-012, FR-013, FR-014, FR-016)

**Lazy load (FR-012)**: Open the workspace against a directory with thousands of files. Verify SC-001 — first paint of the tree's root level is < 1s. Expand a deep folder; only that folder's children load.

**Binary file (FR-013)**: Click an image (`.png`, `.jpg`) in the tree. Editor shows "binary file — preview not supported"; no garbled text.

**Oversize file (FR-014)**: Create a > 2 MB file in the project (`dd if=/dev/urandom of=big.bin bs=1M count=3`). Click it. Editor shows "file too large to edit in browser"; no UI freeze.

**Hidden but whitelisted (FR-016)**: Verify that `.claude/` and `.specify/` directories are visible in the tree, while `.git/`, `.DS_Store`, etc. are hidden.

**Sandbox (D4)**: With the browser's network tab open, manually issue a request `GET /api/claude-code/tree?root=<your-root>&path=../../../etc` — backend returns 400 with `"detail":"path escapes project root"`.

✅ Pass when: every sub-case behaves as documented and no UI lockup occurs.

---

## Non-regression check on feature 015

Re-run the SC-001/002/003 from `specs/015-claude-code-terminal/spec.md`:

- Terminal latency over localhost is still ~100ms (type, see echo).
- Korean / emoji / CJK output streams cleanly across 16 KB chunk boundaries.
- Closing the panel kills the underlying `claude`/shell child within one second (verify with `ps -ef | grep claude` after close).

✅ Pass when: feature 015's SCs all still hold (FR-015, SC-006).
