# Contract: MCP Tools Exposed by the Robo Spec Server

**Feature**: 029-robo-spec-skills

**Surface**: MCP server mounted at `<backendUrl>/mcp` (streamable-HTTP transport).

**Audience**: The four `robo-*` skill files under `robo-spec/.claude/skills/`.

**Authority**: The MCP server is the **sole channel** through which the skills read or write Robo Architect data (FR-006). Skills MUST NOT bypass it.

All tools share the same envelope rules:

- Every call carries `projectId: string`. Unknown project IDs return MCP error code `INVALID_PROJECT`.
- Mutating tools return a `proposal` first; the skill calls `apply_proposal` separately (Principle IV).
- Every tool result includes a `correlationId` that matches a `SmartLogger` entry server-side (Principle VII).

---

## T1. `resolve_design_element`

**Purpose**: Resolve a free-form argument from `/robo-plan` (feature id, BC name, or aggregate name) to exactly one design element, or to a disambiguation list.

**Input**:

```json
{
  "projectId": "uuid",
  "query": "Order"
}
```

**Output (resolved)**:

```json
{
  "status": "resolved",
  "element": {
    "kind": "BoundedContext",
    "id": "bc-1",
    "name": "Order",
    "classification": "core",
    "version": 12
  },
  "correlationId": "..."
}
```

**Output (ambiguous)**:

```json
{
  "status": "ambiguous",
  "candidates": [
    { "kind": "BoundedContext", "id": "bc-1", "name": "Order", "version": 12 },
    { "kind": "Aggregate",      "id": "agg-order-7", "name": "Order", "version": 5 }
  ],
  "correlationId": "..."
}
```

**Errors**: `INVALID_PROJECT`, `NOT_FOUND`.

---

## T2. `get_bc_design`

**Purpose**: Read a BoundedContext plus all its aggregates, commands, events, read models, policies, invariants, and user stories **and the implementation files currently linked to each element** — the full slice `/robo-plan`, `/robo-tasks`, `/robo-sync`, and the Design tab all need. There is no separate `lookup_implementation_files` tool; the mapping is returned alongside elements so a single round-trip serves every caller (R5).

**Input**:

```json
{
  "projectId": "uuid",
  "bcId": "bc-1"
}
```

**Output**: A normalized payload that mirrors the existing `GET /api/contexts/{context_id}/tree` response (router.py:57) with three additions:

1. `classification` on the BC node (`"core" | "supporting" | null`).
2. `version` (integer) on every element node, used for optimistic-concurrency checks in `apply_proposal` (T6a).
3. `implementationFiles` (array) on every Aggregate/Command/Event/ReadModel node, each entry `{ id, path, role, lastSeenAt }`. Empty array = not yet implemented.

**Errors**: `INVALID_PROJECT`, `NOT_FOUND`, `INCOMPLETE_DESIGN` (returned only when the BC has zero aggregates — the skill still receives a usable payload but the flag tells it to emit the "design incomplete" plan skeleton; see edge case in spec).

---

## T3. `set_bc_classification`

**Purpose**: Persist a developer's answer when `/robo-plan` had to ask which architecture style to use (FR-005).

**Input**:

```json
{
  "projectId": "uuid",
  "bcId": "bc-1",
  "classification": "core"
}
```

**Output**:

```json
{ "status": "applied", "newVersion": 13, "correlationId": "..." }
```

**Behavior**: This is a *direct* mutation (not propose-then-apply) because the developer's answer is itself the proposal. The endpoint records the change with the developer's identity (when known) for Principle VII observability. Idempotent for the same value.

**Errors**: `INVALID_PROJECT`, `NOT_FOUND`, `INVALID_VALUE` (anything other than `"core"` or `"supporting"`).

---

## T4. `compute_drift`

**Purpose**: Compare the element names + IDs that the local `tasks.md` (and where relevant `plan.md`) currently references against the live graph (R8). Stateless — no local fingerprint is stored or passed in. Called first on every `robo-*` command.

**Input**:

```json
{
  "projectId": "uuid",
  "bcId": "bc-1",
  "references": [
    { "id": "agg-order-7",       "kind": "Aggregate",      "nameSeen": "Order" },
    { "id": "cmd-place-order-2", "kind": "Command",        "nameSeen": "PlaceOrder" },
    { "id": "evt-order-placed-3","kind": "Event",          "nameSeen": "OrderPlaced" }
  ],
  "classificationSeen": "core"
}
```

`references` lists every element ID the local artifacts currently mention along with the *name as locally seen*. `classificationSeen` is the BC classification that `plan.md`'s architecture section was rendered against (omit if `plan.md` does not exist yet).

**Output**:

```json
{
  "status": "in-sync" | "drift",
  "drift": {
    "renamed":      [{ "id": "...", "oldName": "...", "newName": "..." }],
    "deleted":      [{ "id": "...", "kind": "...", "nameSeen": "..." }],
    "added":        [{ "id": "...", "kind": "...", "name": "..." }],
    "reclassified": [{ "from": "supporting", "to": "core" }]
  },
  "blocking": ["renamed", "deleted", "reclassified"],
  "correlationId": "..."
}
```

`renamed`, `deleted`, and `reclassified` are blocking — the skill MUST stop and report them. `added` is informational; the skill suggests `/robo-tasks` to regenerate `tasks.md` but does not stop.

**Errors**: `INVALID_PROJECT`, `NOT_FOUND` (when `bcId` itself is gone — promoted to `deleted` if any references resolved).

---

## T5. `report_progress`

**Purpose**: Push per-element progress derived from `tasks.md` checkbox state into the backend so it can fan out over SSE to the Design tab (FR-008).

> Note: This is *also* the path the in-backend file-watcher uses internally — the skill calls it to give an authoritative override (e.g., when `/robo-implement` finishes a task) but the watcher already covers passive checkbox toggles. The tool itself is idempotent.

**Input**:

```json
{
  "projectId": "uuid",
  "featureDirectory": "specs/029-robo-spec-skills",
  "items": [
    { "elementId": "agg-order-7", "status": "in-progress" },
    { "elementId": "cmd-place-order-2", "status": "done" }
  ]
}
```

**Output**:

```json
{ "status": "published", "subscribers": 1, "correlationId": "..." }
```

Allowed `status` values: `"todo"`, `"in-progress"`, `"done"`, `"blocked"`, `"orphaned"` (the last returned when the element no longer exists — edge case from spec).

**Errors**: `INVALID_PROJECT`, `INVALID_FEATURE_DIR` (the path isn't a `specs/<NNN>-<slug>/` under a linked workspace), `INVALID_STATUS`.

---

## T6. `propose_sync` and T6a. `apply_proposal`

**Purpose**: `/robo-sync`'s propose→apply pair (Principle IV). The skill performs **full AST extraction** locally (per R7) and ships the normalized structural extract; the MCP server diffs against the graph.

### T6. `propose_sync`

**Input**:

```json
{
  "projectId": "uuid",
  "bcId": "bc-1",
  "extracts": [
    {
      "elementId": "agg-order-7",
      "kind": "Aggregate",
      "version": 5,
      "extractedAt": "2026-05-25T12:00:00Z",
      "fromFiles": ["src/order/domain/Order.ts"],
      "fields": [
        { "name": "customerEmail", "type": "string" },
        { "name": "placedAt",      "type": "DateTime" }
      ]
    }
  ]
}
```

Each entry is the AST-extracted structural shape of the element as it currently exists in source. `version` is the version the skill saw when it last fetched the design via T2 — used for optimistic concurrency in T6a. `fromFiles` is purely diagnostic.

**Output**:

```json
{
  "proposalId": "prop-abc123",
  "diff": {
    "elements": [
      {
        "elementId": "agg-order-7",
        "added":    [{ "name": "placedAt", "type": "DateTime" }],
        "modified": [],
        "removed":  []
      }
    ]
  },
  "renameCandidates": [
    {
      "elementId": "agg-order-7",
      "from": { "name": "customerEmail", "type": "string" },
      "to":   { "name": "customerContact", "type": "string" },
      "confidence": 0.82,
      "rationale": "type matches; names share 70% character overlap"
    }
  ],
  "requiresConfirmation": ["agg-order-7:removed", "agg-order-7:rename:customerEmail->customerContact"],
  "correlationId": "..."
}
```

Notes on the new fields:

- `renameCandidates` enumerates removed-here / added-here pairs that *look like* renames (R7). The server may use the configured LLM runtime to rank these by structural and lexical similarity; `confidence` and `rationale` are advisory. The developer makes the final call.
- `requiresConfirmation` enumerates every destructive operation (deletions and rename pairs). When empty, `apply_proposal` may proceed without an extra prompt.

### T6a. `apply_proposal`

**Input**:

```json
{
  "projectId": "uuid",
  "proposalId": "prop-abc123",
  "confirmed": [
    "agg-order-7:removed",
    "agg-order-7:rename:customerEmail->customerContact"
  ]
}
```

**Output**:

```json
{
  "status": "applied",
  "applied": [{ "elementId": "agg-order-7", "newVersion": 6 }],
  "rejected": [],
  "correlationId": "..."
}
```

**Conflict behavior**: If any of the elements named in the proposal had their `version` bumped in Neo4j between `propose_sync` and `apply_proposal` (Robo Architect was edited concurrently), the call returns `status: "conflict"` with the conflicting elements and applies *nothing*. The skill must re-propose. This satisfies the "never silently overwrite" guarantee in US5 / SC-005.

**Errors**: `INVALID_PROJECT`, `UNKNOWN_PROPOSAL` (expired or unknown ID; proposals expire after 10 minutes per data-model §3.1), `CONFLICT`.

---

## T6b. `register_implementation_files`

**Purpose**: Create or update `[:IMPLEMENTED_IN]` relationships when `/robo-implement` scaffolds files or `/robo-sync` discovers moved files. The user's "source mapping in the ontology only" rule means there is **no** local mapping file — every link goes through this tool (R5).

**Input**:

```json
{
  "projectId": "uuid",
  "links": [
    {
      "elementId": "agg-order-7",
      "files": [
        { "path": "src/order/domain/Order.ts",          "role": "primary" },
        { "path": "src/order/interface/OrderController.ts", "role": "interface-adapter" }
      ]
    }
  ],
  "mode": "replace" | "merge"
}
```

`mode = "replace"` clears the existing `[:IMPLEMENTED_IN]` relationships for each `elementId` before recreating them — used by `/robo-sync` when reconciling moved files. `mode = "merge"` only adds new links and is the default for `/robo-implement`'s incremental writes.

**Output**:

```json
{
  "status": "applied",
  "applied": [
    { "elementId": "agg-order-7", "filesNow": 2 }
  ],
  "correlationId": "..."
}
```

**Errors**: `INVALID_PROJECT`, `NOT_FOUND` (element id), `INVALID_PATH` (absolute or `..`-containing paths are rejected — see data-model §1.2).

---

## T7. `open_file_in_workspace`

**Purpose**: Backend → workspace editor "open this file" trigger (FR-009). Called by the Design tab when the developer clicks an element. Resolves the file via `(:Element)-[:IMPLEMENTED_IN]->(:ImplementationFile)` in the graph — no workspace-local manifest is consulted.

> Although this is consumed *from the frontend*, it lives in the MCP tool surface because the same operation is what `/robo-implement` uses ("now look at this file") and what the workspace bridge needs to authorize. Frontend access goes through the HTTP contract in `http-api.md`, which proxies into this tool.

**Input**:

```json
{
  "projectId": "uuid",
  "elementId": "agg-order-7",
  "preferredRole": "primary"
}
```

**Output**:

```json
{
  "status": "opened" | "not-implemented" | "ambiguous" | "offline",
  "file": { "path": "src/order/domain/Order.ts", "role": "primary" },
  "candidates": [ /* present when status="ambiguous"; each entry {path, role} */ ],
  "correlationId": "..."
}
```

Status decision:
- `"not-implemented"` — element has zero `[:IMPLEMENTED_IN]` links in the graph.
- `"ambiguous"` — element has multiple links and `preferredRole` did not pick a unique one.
- `"offline"` — element has at least one link, but the connected workspace bridge is unreachable.
- `"opened"` — exactly one file resolved and the bridge delivered the open command.

**Errors**: `INVALID_PROJECT`, `NOT_FOUND` (element id).

---

## T8. `subscribe_progress`

**Purpose**: SSE subscription for the Design tab's per-node badges (R6).

**Input** (stream open):

```json
{ "projectId": "uuid" }
```

**Stream events**:

```json
{
  "type": "progress",
  "items": [
    { "elementId": "agg-order-7", "status": "in-progress", "source": "tasks.md" }
  ],
  "ts": "2026-05-25T12:00:00Z"
}
```

```json
{ "type": "link-offline", "ts": "2026-05-25T12:00:01Z" }
```

`link-offline` is emitted when the watched workspace path becomes unreachable (FR-008 fallback rule). The frontend uses it to switch every progress badge in that project to the "code link offline" affordance.

---

## Versioning

Tool schemas are versioned via the standard MCP capability negotiation. v1 ships with **nine** tools: T1, T2, T3, T4, T5, T6, T6a, T6b, T7, T8 (T6/T6a/T6b counted together with T6). Any field added to a tool's output is backwards-compatible. Removing or repurposing a field requires a major version bump and a coordinated update of every `robo-*` skill file under `robo-spec/`.

## Out of scope: skill inheritance

The MCP server is **not** the carrier of the robo-* → speckit-* inheritance relationship (R11). Inheritance is achieved entirely at the SKILL.md level — each robo-* skill is a thin delegation-and-override markdown file that references the upstream speckit-* skill present in the same workspace. The MCP server does **not** ship skill text, does **not** evaluate overrides, and does **not** know which speckit version is installed in the workspace. Keeping inheritance out of the transport layer means an MCP-server outage cannot leave a workspace with broken skills, and a speckit upgrade does not require an MCP redeploy.
