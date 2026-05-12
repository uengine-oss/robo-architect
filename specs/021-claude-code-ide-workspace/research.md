# Phase 0 Research: Claude Code IDE Workspace

Five decisions (D1–D5) that the spec deliberately left open or that the implementation needs nailed down before contracts can be drawn.

---

## D1 — In-browser code editor library

**Decision**: CodeMirror 6 (`@codemirror/state`, `@codemirror/view`, plus per-language packs `@codemirror/lang-markdown`, `@codemirror/lang-json`, `@codemirror/lang-yaml`, `@codemirror/lang-python`, `@codemirror/lang-javascript`, `@codemirror/lang-vue`).

**Rationale**:

- Bundle size is roughly 10× smaller than Monaco for the same language coverage RoboArchitect needs (Markdown / JSON / YAML / Python / JS / Vue). Monaco bundles ~3 MB of language services even when most aren't used; CodeMirror lets us load only the language packs we want.
- The frontend is a Vite SPA already shipping xterm.js, mermaid, bpmn-js, vue-flow, opentype, canvaskit-wasm — the bundle is already heavy. Adding ~100 KB of editor (CodeMirror) is acceptable; adding ~3 MB (Monaco) is not.
- CodeMirror 6 has a clean state-based API that maps onto Vue 3's `ref`/`watchEffect` cleanly without needing a bridging package.
- No existing `monaco-editor` or `codemirror` dep in `frontend/package.json` — both options are greenfield from a dependency standpoint, so the cost calculus is bundle size + API ergonomics, not migration.

**Alternatives considered**:

- **Monaco Editor** — best-in-class IntelliSense, full VS Code parity. Rejected on bundle size; the architect doesn't need IntelliSense for the file types RoboArchitect generates (PRDs are Markdown, agent configs are Markdown, BC specs are Markdown). The "feels like VS Code" UX value is in the *layout*, not the editor's autocomplete depth.
- **Ace Editor** — older, smaller than Monaco. Rejected on API ergonomics (event-emitter pattern fights Vue's reactivity) and a smaller modern community than CodeMirror 6.
- **`<textarea>` + Prism.js for highlighting** — minimum viable but no live highlighting in the editing surface. Rejected because users will be editing Markdown and copying code blocks; Prism-on-display + plain-textarea-on-edit is a notable UX downgrade vs. live highlighting.

---

## D2 — File tree API shape (single endpoint, lazy-expand)

**Decision**: One endpoint `GET /api/claude-code/tree?root=<abs-path>&path=<rel-path>` returns one level of children for the directory at `root + path`. Children come back as `{name, type: "file" | "directory"}[]`. The frontend calls it once on workspace open (`path=""`), then once per directory expand.

**Rationale**:

- Lazy loading (FR-012) means we *cannot* return the whole tree on first call. A flat per-directory call is the simplest shape that satisfies that.
- Splitting `root` (the project sandbox) from `path` (the relative subfolder being expanded) lets the backend enforce the sandbox in one place: `realpath(root + path)` must remain inside `realpath(root)`. Anything else returns 400.
- We deliberately do **not** return file size, mtime, or content type from the tree endpoint. Those add server cost on directories with thousands of files and are only needed when a file is actually opened. The file-open endpoint returns size + binary detection at that point.
- The endpoint is GET (idempotent, cacheable per HTTP semantics) — no need for POST.

**Alternatives considered**:

- **Recursive single-shot tree** (return entire tree on workspace open). Rejected on FR-012 + SC-001: a 5,000-file project would do thousands of `stat()` calls before the user sees anything.
- **Filesystem watcher subscription via WebSocket** that pushes deltas. Rejected: this is the v2 "live watch" feature explicitly scoped out in the spec assumptions. Forcing it into v1 doubles surface area.
- **Reuse `/browse-directory`** which already exists. Rejected: that endpoint filters out *all* dotfiles including `.claude/` and `.specify/`, but FR-016 says those *must* be visible in the tree. The browse endpoint also returns directories only, no files. Different contract → different endpoint.

---

## D3 — File read/write semantics + external-modification detection

**Decision**:

- `GET /api/claude-code/file?root=<abs>&path=<rel>` returns `{path, content, size, mtime_ns, encoding, binary}`. If `binary=true`, `content` is omitted (FR-013). If `size > 2 MB`, returns 413 (FR-014).
- `PUT /api/claude-code/file` body `{root, path, content, expected_mtime_ns}`. Server compares the file's current `mtime_ns` to `expected_mtime_ns`. If they differ → return 409 with the current `{mtime_ns, size}` so the frontend can show the reload-or-keep prompt (FR-011). If equal → write and return new `mtime_ns`.
- The frontend additionally re-reads `mtime_ns` on a manual tree refresh (Story 3) and shows the reload prompt when an open file's `mtime_ns` has advanced beyond the buffer's last-known value.

**Rationale**:

- `mtime_ns` (nanosecond mtime from `os.stat`) is the canonical "did the file change on disk?" signal on POSIX and is cheap (~1 syscall). It is monotonically advancing per write on every modern filesystem RoboArchitect runs on (APFS, ext4, btrfs, xfs).
- Sending `expected_mtime_ns` on PUT turns the save into an optimistic-concurrency check — exactly what FR-011 calls for. We don't need a full content hash because `mtime_ns` collisions essentially require deliberate malice (resetting mtime via `utimensat`), which doesn't happen in this single-user workflow.
- 413 (Payload Too Large) is the right HTTP semantic for "file too big to load" — frontend translates it into the FR-014 error message.
- 409 (Conflict) is the right HTTP semantic for "the file changed since you read it" — frontend translates it into the FR-011 reload-or-keep prompt.

**Alternatives considered**:

- **Content hash (SHA-1 of content) instead of mtime**. Rejected: requires reading + hashing the file on every save (adds ~10ms per MB) and on every external-modification check. mtime is O(1).
- **Last-write-wins (no concurrency check)**. Rejected: explicitly violates FR-011 ("MUST NOT silently overwrite the architect's unsaved edits"). This would be the simplest implementation but loses the user's work the first time Claude rewrites a file the architect was editing.
- **Locking the file on open**. Rejected: would prevent Claude (the right pane) from writing it, which is the whole point of the integration.

---

## D4 — Path sandboxing (the project root never leaks)

**Decision**: One helper `resolve_under_root(root: str, path: str) -> str` used by every tree/file endpoint. It computes `os.path.realpath(os.path.join(root, path))`, then verifies the result starts with `os.path.realpath(root) + os.sep` (or equals it). Any mismatch → `HTTPException(400, "path escapes project root")`. The helper also rejects absolute paths in `path` and any `..` component before `realpath` for clarity in error messages, even though `realpath` would also catch them.

**Rationale**:

- `realpath` follows symlinks, so a malicious symlink inside the project root that points to `/etc/passwd` is caught (the realpath of the link target is outside the root and the prefix check fails).
- `realpath` collapses `..` and `.` components, so `path="../../etc/passwd"` is caught even though the joined path contains valid path components.
- We use the realpath of `root` too because `root` itself may be a symlink — we need to compare resolved-to-resolved.
- The helper is the only filesystem-touching surface in the new code; everything else (read_text, write_text, list_dir) takes the already-resolved absolute path. This keeps the sandbox check in exactly one place that's easy to audit.
- `os.sep` suffix on the prefix check prevents the `/var/lib` vs. `/var/library` false-positive (without the separator, `startswith` would treat the second as inside the first).

**Alternatives considered**:

- **`os.path.commonpath([root, resolved]) == root`**. Functionally equivalent and slightly more readable, but it doesn't handle symlinks unless we realpath both first — which is what the chosen approach does anyway. Either is fine; we prefer the explicit-prefix form because it gives a clearer error message ("path X escapes root Y").
- **Chroot the FastAPI process**. Rejected: kills the rest of the app (which legitimately reads PRD templates, ingestion files, etc. outside the workspace root) and requires root privileges in production.
- **No sandbox — trust the user**. Rejected: the user picks a project root, but the *frontend* sends `path` on every request; a compromised tab or browser extension could craft `path=../../../etc` payloads. Single-user assumption doesn't extend to "the user's tab is uncompromised."

---

## D5 — When to log

**Decision**: One structured WARN log at the sandbox-violation site (D4 helper), one INFO at the workspace-tree-list root call (capture root path + child count for post-mortem on "why is my project empty?" reports). No logs on the per-keystroke save or per-expand tree calls — they would drown the log.

**Rationale**:

- Constitution principle VII calls for phase-boundary logging on multi-step pipelines. Filesystem CRUD has no phases; logs at every read/write/list would emit thousands of lines per minute under normal use, hiding the sandbox-violation signal under noise.
- Sandbox violations are the only "non-obvious cross-boundary failure" — they happen because frontend code or a malicious payload sent a path that escaped the root. WARN-level with the offending root + path captured is exactly what a security post-mortem needs.
- The "tree root listed" INFO gives one-line-per-workspace-open context: which project, how big, did it succeed. This is enough to debug "the user opened the panel and saw nothing" without per-call overhead.

**Alternatives considered**:

- **Full SmartLogger correlation-ID instrumentation** on every endpoint. Rejected per Constitution PARTIAL note: the principle exists for multi-step pipelines, not synchronous CRUD. The cost (code + log volume) outweighs the benefit (correlated traces of single-call operations).
- **No logs at all**. Rejected: sandbox violations are silent in production without them, and that's a security-relevant signal.

---

## Cross-cutting note: terminal pane is untouched

The existing `ClaudeCodeTerminal.vue` (763 lines) and the `/terminal` WebSocket endpoint stay byte-for-byte unchanged. The new `ClaudeCodeWorkspace.vue` shell embeds the terminal component as a child in the right pane, passing through the same `workdir` prop the parent already provides today via `provide('openClaudeCode', ...)` from `App.vue`. This means:

- Feature 015's success criteria (SC-001/002/003 from that spec) automatically still hold (FR-015, SC-006).
- The folder-picker UX inside the terminal component continues to work as today; the architect can either pick the directory before clicking Claude Code (existing flow) or pick it inside the terminal pane itself. The workspace shell reads the chosen workdir from the same `claudeCodeWorkdir` ref in `App.vue` so the tree pane always has the same root the terminal session uses.
