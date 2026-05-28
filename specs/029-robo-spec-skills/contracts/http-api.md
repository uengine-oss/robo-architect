# Contract: New HTTP Endpoints

**Feature**: 029-robo-spec-skills

**Audience**: Frontend (Design tab + Inspector panel), `setup-project` flow, and external operators inspecting `/docs`.

**Authority**: Every endpoint below MUST appear in the auto-generated Swagger UI at `/docs` (Constitution Development Workflow rule). All request/response shapes MUST be backed by Pydantic models in `api/features/robo_spec/schemas.py`.

---

## E1. `POST /api/claude-code/setup-project` (extended)

**Status**: Extension to the existing endpoint at `api/features/claude_code/router.py:148`. Does not change the existing request shape; adds new behavior to the existing call.

**New behavior**:

1. After the existing PRD ZIP extraction, perform a **verbatim copy** of `<repo-root>/skills/robo-spec/` into `<workspace>/.claude/skills/`. No Jinja, no template substitution (FR-012).
2. Write `<workspace>/.claude/robo-project.json` with the resolved `projectId`, `backendUrl`, and `mcpEndpoint` (per §2.1 of `data-model.md`).
3. Idempotent: re-running on a workspace that already has these files re-copies (overwriting) the skill files and updates `robo-project.json`'s `backendUrl` / `mcpEndpoint` (in case of tunnel rotation). The file `robo-project.json`'s `projectId` MUST NOT change on re-run — if it would, the call returns `409 Conflict` and asks the operator to use a fresh workspace.

**New response fields**:

```json
{
  "roboSpecInstalled": true,
  "roboSpecChecksum": "sha256:..."   // checksum of the copied skills/ subtree; matches a digest of skills/robo-spec/ at release time (SC-006)
}
```

**Failure modes**:

- `skills/robo-spec/` missing in the deployed backend → `500 Internal Server Error` with diagnostic; this is a packaging bug, not a user error.
- Target workspace not writable → `403 Forbidden`.

---

## E2. `GET /api/contexts/{bc_id}/classification`

**Purpose**: Read the BC's `core | supporting` classification (or its absence). Mirrors the MCP `get_bc_design` field but kept as a thin HTTP route so the frontend (Inspector panel) can render the value without going through MCP.

**Response**:

```json
{ "bcId": "bc-1", "classification": "core" }
```

or

```json
{ "bcId": "bc-1", "classification": null }
```

**Errors**: `404 Not Found` when the BC does not exist.

## E3. `PATCH /api/contexts/{bc_id}/classification`

**Purpose**: Write path for the value, used both by the MCP `set_bc_classification` tool (which proxies here) and by a future Robo Architect UI affordance.

**Request body**:

```json
{ "classification": "core" }
```

**Validation**:

- Body MUST be either `{ "classification": "core" }` or `{ "classification": "supporting" }`. Anything else → `422 Unprocessable Entity`.
- Concurrency: `If-Match` header carrying the BC's last-known `version` is supported; missing header is tolerated for v1 (this is a low-churn property) but a future revision will require it.

**Response**: same shape as E2 with the new value.

**Side effect**: Emits a `SmartLogger` event `bc.classification.changed` with the correlation ID, the BC id, and the old/new value.

---

## E4. `POST /api/robo-spec/projects/{project_id}/open-file`

**Purpose**: Frontend trigger for "open implementation file in editor" when a design-tab node is clicked (FR-009). Proxies to MCP `open_file_in_workspace` server-side; exists as an HTTP route so the frontend can stay HTTP-only (no MCP client in the browser). Resolution is **graph-only** — the backend reads `(:Element)-[:IMPLEMENTED_IN]->(:ImplementationFile)` and never consults a workspace-local manifest (because none exists; see R5 / data-model §2.4).

**Request body**:

```json
{
  "elementId": "agg-order-7",
  "preferredRole": "primary"
}
```

**Response variants**:

- `200 OK { "status": "opened", "file": { "path": "src/order/domain/Order.ts", "role": "primary" } }` — the workspace was online and the file exists; the response also triggers a side-channel command to the connected Claude Code workspace to surface the file.
- `200 OK { "status": "not-implemented" }` — the element has zero `[:IMPLEMENTED_IN]` links in the graph; the frontend renders the "not implemented yet" affordance and offers to launch `/robo-implement` for this element.
- `200 OK { "status": "ambiguous", "candidates": [ … ] }` — multiple file candidates; frontend renders a picker.
- `503 Service Unavailable` — at least one link exists but the connected workspace bridge is unreachable; frontend renders the "code link offline" affordance.

**Errors**: `404 Not Found` if the element id does not exist in the project's graph.

---

## E5. `GET /api/robo-spec/projects/{project_id}/progress/stream` (SSE)

**Purpose**: Server-Sent Events stream consumed by the Design tab to render per-node progress badges (FR-008, R6).

**Stream shape**:

```text
event: progress
data: {"items":[{"elementId":"agg-order-7","status":"in-progress","source":"tasks.md"}],"ts":"..."}

event: link-offline
data: {"ts":"..."}
```

**Disconnect behavior**: When the EventSource reconnects after a network hiccup, the server sends a synthetic `progress` event containing the *full current* state for the project before resuming live events (so the UI never shows stale badges after a reconnect).

**Authentication**: same session/cookie scheme used by the rest of the frontend's SSE channels (e.g., the ingestion stream). No new auth surface.

---

## E6. `GET /api/robo-spec/projects/{project_id}/implementation-map`

**Purpose**: Read the source mapping (`[:IMPLEMENTED_IN]` relationships) for every element under a BC, so the Design tab can decorate each node up-front with "implemented / not implemented" affordances before any click happens. The data lives **only** in the graph (R5 / data-model §1.2–1.3); this endpoint is a thin projection of it.

**Query parameters**:

| Param   | Required | Notes                                                                                    |
|---------|----------|------------------------------------------------------------------------------------------|
| `bcId`  | Yes      | The BC whose element map should be returned.                                             |

**Response**:

```json
{
  "projectId": "uuid",
  "bcId": "bc-1",
  "elements": {
    "agg-order-7": {
      "kind": "Aggregate",
      "name": "Order",
      "files": [
        { "path": "src/order/domain/Order.ts", "role": "primary", "lastSeenAt": "..." }
      ]
    },
    "cmd-place-order-2": {
      "kind": "Command",
      "name": "PlaceOrder",
      "files": []
    }
  }
}
```

An empty `files` array means "not implemented yet" (renders as the "not implemented yet" affordance).

**Errors**:

- `404 Not Found` if the BC does not exist in the project's graph.

---

## OpenAPI grouping

All new routes appear in `/docs` under the tag `robo-spec`. The existing routes E1 stays under its original `claude-code` tag with an updated description noting the new robo-spec install step.

## Backwards compatibility

- E2/E3 are additive to `/api/contexts/{bc_id}`; the existing `GET /api/contexts/{bc_id}` and `GET /api/contexts/{bc_id}/tree` responses gain an optional `classification` field, default null. No existing consumer should break.
- E1 is a pure additive extension; no existing field changes.
- E4–E6 are net-new under the new `/api/robo-spec/` prefix.
