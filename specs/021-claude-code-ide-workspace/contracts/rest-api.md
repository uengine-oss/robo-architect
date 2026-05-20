# REST API Contracts: Claude Code IDE Workspace

All new endpoints live under the existing `/api/claude-code` prefix (registered in `api/main.py` line 218). The existing `WS /api/claude-code/terminal`, `GET /api/claude-code/browse-directory`, and `POST /api/claude-code/setup-project` are **unchanged** and not duplicated here — see `api/features/claude_code/router.py` for their current contracts.

## 1. `GET /api/claude-code/tree`

List one level of children under a directory inside the project root.

### Query parameters

| Name | Type | Required | Notes |
|------|------|----------|-------|
| `root` | string | yes | Absolute path to the project root the architect picked. The sandbox anchor — every other path must resolve under this. |
| `path` | string | no (default `""`) | Relative path under `root`. Empty string lists the root itself. |

### Responses

**`200 OK`**

```json
{
  "root": "/Users/architect/projects/foo",
  "path": "",
  "children": [
    { "name": ".claude", "type": "directory" },
    { "name": "specs",    "type": "directory" },
    { "name": "CLAUDE.md", "type": "file" },
    { "name": "PRD.md",   "type": "file" }
  ]
}
```

- Sort: directories first (case-insensitive), then files (case-insensitive).
- Filtering: leading-`.` entries removed **except** `.claude` and `.specify` (FR-016). `*.app` bundles removed.
- An empty directory returns `children: []`.

**`400 Bad Request`** — sandbox violation (`path` escapes `root`):

```json
{ "detail": "path escapes project root" }
```

**`404 Not Found`** — `root` is not a directory or `path` does not exist under it:

```json
{ "detail": "directory not found" }
```

**`403 Forbidden`** — permission denied while listing:

```json
{ "detail": "permission denied" }
```

The handler catches `PermissionError` from `os.scandir` and returns 403; the frontend renders the FR edge-case "no access" indicator.

---

## 2. `GET /api/claude-code/file`

Read a single file's content + metadata.

### Query parameters

| Name | Type | Required | Notes |
|------|------|----------|-------|
| `root` | string | yes | Absolute project root. |
| `path` | string | yes | Relative path under `root`. |

### Responses

**`200 OK` (text file)**

```json
{
  "path": "CLAUDE.md",
  "size": 2487,
  "mtime_ns": "1715269200123456789",
  "binary": false,
  "content": "# Project ...",
  "encoding": "utf-8"
}
```

`mtime_ns` is sent as a JSON **string** (see data-model.md note on JS `Number` precision). The frontend echoes it verbatim on `PUT`.

**`200 OK` (binary file)**

```json
{
  "path": "logo.png",
  "size": 12345,
  "mtime_ns": "1715269200123456789",
  "binary": true,
  "content": null,
  "encoding": "utf-8"
}
```

`content` is omitted (FR-013); the frontend shows the binary-file placeholder.

**`413 Payload Too Large`** — file exceeds 2 MiB cap (FR-014):

```json
{ "detail": "file too large to edit in browser", "size": 5242880 }
```

**`400 Bad Request`** — sandbox violation: same shape as `/tree` 400.
**`404 Not Found`** — file does not exist under `root`.
**`403 Forbidden`** — permission denied on read.

---

## 3. `PUT /api/claude-code/file`

Save the file's contents back to disk with optimistic-concurrency check.

### Request body

```json
{
  "root": "/Users/architect/projects/foo",
  "path": "CLAUDE.md",
  "content": "# Project ...\n\nNew line added by architect.\n",
  "expected_mtime_ns": "1715269200123456789"
}
```

`expected_mtime_ns` is **required** for existing files. Pass `null` only when creating a new file (the server then requires the file not yet exist).

### Responses

**`200 OK`** — write succeeded:

```json
{
  "path": "CLAUDE.md",
  "size": 2530,
  "mtime_ns": "1715269245678912345"
}
```

The frontend stores the new `mtime_ns` on the buffer.

**`409 Conflict`** — disk has changed since the buffer was loaded (FR-011):

```json
{
  "detail": "file changed on disk since last read",
  "current_mtime_ns": "1715269230999000000",
  "current_size": 2510
}
```

The frontend shows the reload-or-keep banner. To force-overwrite, the user can choose "Keep my changes," at which point the frontend re-reads the current `mtime_ns` and re-PUTs with that value (i.e. there is no separate "force" flag — overwriting is just a second save with the now-current mtime).

**`400 Bad Request`** — sandbox violation, OR `expected_mtime_ns` is `null` but the file already exists:

```json
{ "detail": "expected_mtime_ns required for existing file" }
```

**`404 Not Found`** — parent directory does not exist (the architect or Claude deleted it out-of-band, FR scenario from spec). Returned when `expected_mtime_ns != null` (i.e. updating an existing file) but the file path no longer exists. The save fails clearly so the buffer is preserved (FR-009 / Story 2 #4).

**`403 Forbidden`** — permission denied on write.
**`413 Payload Too Large`** — request body exceeds the 2 MiB cap (mirror of GET).

### Atomicity

Writes go through a temp file: write to `<path>.tmp.<rand>`, `os.fsync`, `os.rename` to final path. The rename is atomic on POSIX, so a crash mid-save never leaves a half-written file. The temp suffix is hidden from the tree by the leading-`.` filter (it would not appear anyway because we generate it without a leading dot — but if the rename fails for any reason, the cleanup branch unlinks the temp and surfaces 500).

---

## Endpoints **NOT** changed by this feature

| Endpoint | Status | Why |
|----------|--------|-----|
| `WS /api/claude-code/terminal` | unchanged | The right pane embeds it as-is (FR-015). |
| `GET /api/claude-code/browse-directory` | unchanged | Still drives the initial folder picker. |
| `POST /api/claude-code/setup-project` | unchanged | Still extracts the PRD bundle into the project root before the architect first opens the workspace. |

## Error envelope conventions (all endpoints)

- 4xx errors return `{ "detail": "<human-readable>" }` plus optional structured fields (`size`, `current_mtime_ns`, etc.). This is FastAPI's default `HTTPException` shape and matches every other endpoint in `api/features/claude_code/router.py`.
- 5xx errors are not normalized — they bubble up as FastAPI's default 500 page. The frontend treats any non-2xx as "operation failed; show toast" except for the explicit semantic codes documented above (400 / 403 / 404 / 409 / 413).
