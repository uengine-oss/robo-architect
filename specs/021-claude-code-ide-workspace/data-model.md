# Phase 1 Data Model: Claude Code IDE Workspace

This feature **does not introduce any persisted entities** — no Neo4j nodes, no database rows, no on-disk metadata. The "data model" is entirely transient state held in (a) the FastAPI request handlers and (b) the Vue components in the browser. This document captures the shapes that cross those layers so the contracts and the frontend stay consistent.

## Backend (FastAPI / Pydantic)

### `TreeChild` (response item from `GET /tree`)

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | Basename only — never includes `/`. |
| `type` | `Literal["file", "directory"]` | Frontend uses this to decide expand-vs-open behavior. |

Filtering rules applied server-side (FR-016):

- Reject any entry whose name starts with `.` **except** `.claude` and `.specify` (whitelist).
- Reject any entry whose name ends with `.app` (macOS bundles).
- Sort case-insensitively, directories first then files (matches the existing folder-picker UX).

### `TreeResponse` (response from `GET /tree`)

| Field | Type | Notes |
|-------|------|-------|
| `root` | `str` | Echo of the resolved-realpath project root. |
| `path` | `str` | Echo of the relative path requested (`""` for root). |
| `children` | `list[TreeChild]` | One level only. |

### `FileResponse` (response from `GET /file`)

| Field | Type | Notes |
|-------|------|-------|
| `path` | `str` | Relative path under the project root. |
| `size` | `int` | Bytes on disk. |
| `mtime_ns` | `int` | `os.stat().st_mtime_ns` — used for FR-011 conflict detection on save. |
| `binary` | `bool` | `True` if the file failed UTF-8 decode or contains a NUL byte in the first 8 KB. |
| `content` | `str \| None` | `None` when `binary=True`; otherwise the full UTF-8 text. |
| `encoding` | `Literal["utf-8"]` | We only ship UTF-8 content. Future-proofing field for v2. |

Limits enforced server-side:

- `size > 2_097_152` (2 MiB) → respond `413 Payload Too Large` with `{detail, size}` instead of returning content (FR-014).
- Binary detection: first 8 KB read; if it contains a `0x00` byte or fails strict UTF-8 decode, mark `binary=True` and omit `content` (FR-013).

### `FileWriteRequest` (body of `PUT /file`)

| Field | Type | Notes |
|-------|------|-------|
| `root` | `str` | Absolute path to the project root (sandbox anchor). |
| `path` | `str` | Relative path under the root. |
| `content` | `str` | Full UTF-8 text to write. |
| `expected_mtime_ns` | `int \| None` | If provided, server compares to current `os.stat().st_mtime_ns` and returns `409 Conflict` on mismatch (FR-011). `None` means "first save of a new file" — server requires the file not to exist. |

### `FileWriteResponse` (response from `PUT /file`)

| Field | Type | Notes |
|-------|------|-------|
| `path` | `str` | Echo. |
| `size` | `int` | New on-disk size after write. |
| `mtime_ns` | `int` | New `mtime_ns` — frontend stores this as the buffer's new "last-known" value. |

### `ConflictResponse` (body of `409` from `PUT /file`)

| Field | Type | Notes |
|-------|------|-------|
| `detail` | `str` | Human-readable message. |
| `current_mtime_ns` | `int` | What the file's mtime is *now* (so frontend knows what version exists on disk). |
| `current_size` | `int` | Same purpose for size. |

## Frontend (Vue / browser, in-memory only)

### `WorkspaceState` (held by `ClaudeCodeWorkspace.vue`)

| Field | Type | Notes |
|-------|------|-------|
| `root` | `string` | Absolute project-root path, sourced from the existing `claudeCodeWorkdir` ref in `App.vue`. |
| `treeNodes` | `Map<string, TreeNode>` | Keyed by relative path (`""` for root). Built lazily as the user expands. |
| `expandedPaths` | `Set<string>` | Which directory paths are currently expanded in the UI. |
| `activeFile` | `EditorBuffer \| null` | The file currently shown in the middle pane. v1 supports a single open file; tabs hold one entry. |

### `TreeNode` (browser-side)

| Field | Type | Notes |
|-------|------|-------|
| `name` | `string` | From server `TreeChild.name`. |
| `type` | `"file" \| "directory"` | From server. |
| `path` | `string` | Relative path (built from parent + name). |
| `children` | `TreeNode[] \| null` | `null` until expanded; `[]` after expand of an empty dir. |
| `loading` | `boolean` | True while the expand request is in flight (shows spinner). |
| `error` | `string \| null` | Sandbox-violation or permission-denied surface text. |

### `EditorBuffer` (browser-side)

| Field | Type | Notes |
|-------|------|-------|
| `path` | `string` | Relative path. |
| `originalContent` | `string` | Last content fetched from disk OR last successfully saved. |
| `currentContent` | `string` | What the editor view currently holds. |
| `mtimeNs` | `number \| bigint` | Last-known `mtime_ns` from server (use BigInt or string to avoid 53-bit precision loss; see FR notes below). |
| `dirty` | `computed boolean` | `originalContent !== currentContent`. Drives FR-008 unsaved indicator. |
| `binary` | `boolean` | `true` → editor shows the FR-013 placeholder, no editing surface mounted. |
| `language` | `string` | Inferred from extension at open time; passed to CodeMirror. |
| `pendingExternalReload` | `{ newMtimeNs, newSize } \| null` | Set when a refresh detects external mtime advance — drives the FR-011 reload-or-keep banner. |

**`mtime_ns` precision note**: nanosecond mtime exceeds JavaScript `Number` safe-integer range. The frontend stores it as a string and forwards it verbatim to the backend on PUT — only the backend ever does arithmetic on it. This keeps the data flow exact across the boundary.

## State transitions

### File buffer lifecycle

```text
(no file open)  --click file in tree-->  loading
loading         --GET /file 200 -->     clean (originalContent = currentContent, dirty=false)
loading         --GET /file 413 -->     too-large-banner (no buffer mounted)
loading         --GET /file binary-->   binary-placeholder (no editor mounted)

clean           --user types  -->       dirty
dirty           --PUT /file 200-->      clean (originalContent := currentContent, mtimeNs := response.mtime_ns)
dirty           --PUT /file 409-->      conflict-prompt (offer "reload" or "keep & overwrite")

clean           --refresh detects mtime advance--> auto-reloaded (silently re-fetch)
dirty           --refresh detects mtime advance--> reload-or-keep banner

(any)           --user picks different file with dirty buffer--> save/discard prompt
(any)           --user closes panel with dirty buffer-->        save/discard prompt
```

### Tree node lifecycle

```text
(unloaded)      --user clicks expand-->  loading
loading         --GET /tree 200-->        expanded (children populated)
loading         --GET /tree 4xx-->        error (banner on the node, retry available)
expanded        --user clicks collapse--> collapsed (children kept in memory for snappy re-expand)
expanded        --user clicks Refresh on root--> all expanded paths re-fetched in parallel
```

## What is **NOT** modeled

- **No persistence** of which file was open across page reloads (Assumption: out of scope for v1).
- **No multi-tab editor** (one open file at a time in v1; tab strip can hold one entry).
- **No undo history beyond CodeMirror's own** (CodeMirror has built-in undo; we don't persist it).
- **No FS-watch subscription**, no event stream, no SSE — manual refresh only (Assumption).
- **No graph nodes** — the workspace is a filesystem view; the graph remains source of truth for domain artifacts.
