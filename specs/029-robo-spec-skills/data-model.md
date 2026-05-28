# Phase 1 Data Model: Robo Spec Skills & MCP Bridge

**Feature**: 029-robo-spec-skills

**Date**: 2026-05-25

This document defines (1) the Neo4j schema delta this feature requires, (2) the on-disk artifacts the skills read and write inside a Claude Code workspace, and (3) the in-process state the MCP server maintains. State transitions and validation rules are inlined per entity.

> Important scope note: For *consumers* of the robo-* skills, the design data model lives in Robo Architect's Neo4j graph and is **not** redefined in any `data-model.md` produced by `/robo-plan`. This document defines the data model only for the **meta-feature that builds the robo-* skill set**, per FR-004 and Principle I (graph remains the single source of truth at runtime).

---

## 1. Neo4j schema delta

### 1.1 `BoundedContext.classification` (new optional property)

| Field          | Type     | Required | Allowed values            | Notes                                                            |
|----------------|----------|----------|---------------------------|------------------------------------------------------------------|
| `classification` | `string` | No       | `"core"` \| `"supporting"` | Drives architecture style choice in `/robo-plan` (FR-005).      |

**Validation rules**:

- If present, value MUST be exactly `"core"` or `"supporting"`. Any other string is rejected at the API layer.
- Absence is meaningful: it signals to `/robo-plan` that the developer should be asked, and the answer should be persisted back.

**State transitions**:

```
(absent) --developer answers via /robo-plan--> "core" | "supporting"
"core"     <--/robo-sync (no-op for this field)--> "core"
"supporting" <--developer toggles via Robo Architect UI--> "core"
```

Classification changes triggered by the developer through the Robo Architect UI are an existing path; this feature does not add a new UI for that, but `/robo-plan` becomes a *secondary* path for first-time classification.

**Schema documentation**:

- Must be reflected in `docs/cypher/schema/03_node_types.cypher` in the same PR that ships the read/write code (Constitution Development Workflow).
- No Cypher constraint is added — `classification` is optional. Validation happens at the FastAPI layer via Pydantic enum.

### 1.2 New node label `:ImplementationFile` (source mapping in the ontology)

Per R5, source mapping lives **only** in the graph — there is no workspace-local mapping file. A single node represents one file in one project's source tree.

| Field        | Type     | Required | Notes                                                                                              |
|--------------|----------|----------|----------------------------------------------------------------------------------------------------|
| `id`         | `string` | Yes      | UUID. Stable across renames; new node only for genuinely new files.                                |
| `projectId`  | `string` | Yes      | Routing key. Same project may be linked to multiple workspaces; mapping is workspace-agnostic.     |
| `path`       | `string` | Yes      | Workspace-relative POSIX path, e.g., `src/order/domain/Order.ts`.                                  |
| `role`       | `string` | Yes      | One of `"primary"`, `"interface-adapter"`, `"infrastructure"`, `"test"`, `"other"`.                |
| `createdAt`  | `string` | Yes      | ISO-8601 timestamp.                                                                                |
| `lastSeenAt` | `string` | Yes      | ISO-8601 timestamp updated by `/robo-implement` and `/robo-sync` whenever the file is observed.    |

**Uniqueness**: `(projectId, path)` is unique. A Cypher unique constraint is added in `docs/cypher/schema/`.

**Validation rules**:

- `path` MUST be a POSIX-relative path; absolute paths and `..` segments are rejected at the API layer.
- `role` MUST be one of the five allowed values; anything else → `422 Unprocessable Entity`.

### 1.3 New relationship `[:IMPLEMENTED_IN]`

Connects design elements to the files that implement them. The relationship itself carries no properties — discriminators live on the `:ImplementationFile` node.

```cypher
(e:Aggregate|Command|Event|ReadModel)-[:IMPLEMENTED_IN]->(:ImplementationFile)
```

- **Cardinality**: N:M. One element may have multiple files (e.g., domain model + interface adapter); one file may back multiple elements (e.g., a single migration file for two aggregates).
- **Lifecycle**: created by `/robo-implement` after scaffolding, updated by `/robo-sync` when files move; deleted automatically when the implementation file is removed from disk (detected on the next `/robo-sync` and confirmed by the developer per Principle IV).

**Schema documentation**:

- `:ImplementationFile` and `[:IMPLEMENTED_IN]` MUST be added to `docs/cypher/schema/03_node_types.cypher` and `04_relationships.cypher` in the same PR that ships the code emitting them.

### 1.4 No other node labels or relationships introduced

This feature deliberately introduces only the additions above. Progress state (`tasks.md` checkbox status) lives **outside** Neo4j — it is derived from the workspace's `tasks.md` at request time and pushed over SSE (R6). The graph stores design + source-mapping; not workspace-runtime state.

---

## 2. On-disk artifacts inside the target Claude Code workspace

These files live inside the developer's workspace (not in the Robo Architect repo). They are written and read by the robo-* skills. None of them is a source of truth — they are derived from the graph and can be regenerated.

### 2.1 `<workspace>/.claude/robo-project.json`

Written once by `setup-project` when the workspace is first linked.

```json
{
  "projectId": "uuid-of-robo-architect-project",
  "backendUrl": "http://localhost:8000",
  "mcpEndpoint": "http://localhost:8000/mcp",
  "createdAt": "2026-05-25T12:00:00Z"
}
```

| Field         | Type     | Required | Notes                                                                   |
|---------------|----------|----------|-------------------------------------------------------------------------|
| `projectId`   | `string` | Yes      | Robo Architect project UUID. Used by MCP as the routing key.            |
| `backendUrl`  | `string` | Yes      | Base URL of the Robo Architect backend (may be a tunnel URL).           |
| `mcpEndpoint` | `string` | Yes      | URL the MCP transport is exposed at; mirrors `backendUrl` + `/mcp`.     |
| `createdAt`   | `string` | Yes      | ISO-8601 timestamp. Diagnostic only.                                    |

**Validation**: `projectId` MUST exist in Robo Architect at the time of any MCP tool call. The MCP server rejects calls with an unknown `projectId`.

### 2.2 `<workspace>/specs/<NNN>-<slug>/plan.md`

Markdown file produced by `/robo-plan`. Contains:

- Architecture style chosen (clean for `core`, default-speckit for `supporting`).
- Per-element file-location plan (e.g., "Aggregate `Order` → `src/order/domain/Order.ts`").
- References back to design elements by **name**, not by path. The path mapping lives in §2.4.

This is a derivable artifact. Manual edits are permitted; `/robo-sync` does not parse `plan.md`.

### 2.3 `<workspace>/specs/<NNN>-<slug>/tasks.md`

Markdown file produced by `/robo-tasks`. Each checkbox item carries an HTML-comment marker identifying the **design element** it implements. (These markers are in `tasks.md`, **not** in source code — `/robo-implement` does not write markers into the developer's source files; the user explicitly rejected codegen-time markers, see R7.)

```markdown
- [ ] Implement aggregate invariant "non-negative balance" <!-- @robo elementId="agg-order-7" kind="Aggregate" item="invariant" -->
- [x] Wire OrderPlaced event handler <!-- @robo elementId="evt-order-placed-3" kind="Event" -->
```

**Validation rules**:

- Every checkbox item MUST have exactly one `<!-- @robo elementId="..." kind="..." -->` marker.
- `elementId` MUST resolve to a real element in the graph at progress-reflection time (orphaned IDs surface as the `"orphaned"` status rather than crashing — edge case).
- These markers are **the only** structured annotations the feature introduces. They live in derivable artifacts (regenerable by `/robo-tasks`); the user's "no markers in source code" constraint is satisfied because no analogous markers exist on the codegen side.

**State transitions per item**:

```
todo ([ ])  --developer/skill ticks--> done ([x])
done ([x])  --developer un-ticks--> todo ([ ])
todo ([ ]) + has 'blocked' note  --rendered as--> blocked (UI only)
```

The backend never modifies `tasks.md` — only the skill or the developer does. The backend reads it, parses the markers above, and pushes the derived progress state over SSE.

### 2.4 No `.robo-link.json` (intentionally absent)

Earlier drafts proposed a per-feature `.robo-link.json` to hold element→file mapping and a design fingerprint. **This file does not exist in the final design.** Per R5, source mapping is stored exclusively as `:ImplementationFile` nodes in Neo4j; per R8, drift detection is stateless and recomputed at call time. The only workspace-local persistent state is `.claude/robo-project.json` (§2.1), `plan.md` (§2.2), `tasks.md` (§2.3), and the skill files themselves (§2.5).

### 2.5 `<workspace>/.claude/skills/robo-{plan,tasks,implement,sync}/SKILL.md`

These are the verbatim-copied skill files. Their **on-disk content** is byte-identical to `<repo>/skills/robo-spec/robo-*/SKILL.md`. No template substitution at install time (FR-012). Validation is by checksum (SC-006).

---

## 3. MCP server in-process state

### 3.1 `ProjectSession`

Held in memory per project ID for the lifetime of an MCP connection. Not persisted.

| Field             | Type     | Notes                                                            |
|-------------------|----------|------------------------------------------------------------------|
| `projectId`       | `string` | Routing key; rejected if not present in Neo4j.                   |
| `workspacePath`   | `string` | Absolute path on the host running the backend; resolved per call.|
| `correlationId`   | `string` | Threaded into `SmartLogger` for every tool call (Principle VII). |
| `pendingProposals`| `object` | Map `proposalId → diff` held between `propose_sync` and `apply_proposal`. Expires after 10 minutes. |

No `lastFingerprint` is cached — drift is computed at request time against the live graph (R8).

### 3.2 `WatchedTasksFile`

One per active linked feature directory in any connected workspace.

| Field             | Type      | Notes                                                                 |
|-------------------|-----------|-----------------------------------------------------------------------|
| `path`            | `string`  | Absolute path to a `tasks.md`.                                        |
| `projectId`       | `string`  | Owning project.                                                       |
| `featureDir`      | `string`  | The `specs/<NNN>-<slug>/` directory under workspace.                  |
| `lastCheckedState`| `object`  | `elementId → "todo" | "in-progress" | "done" | "blocked"`.            |

**State transitions** (file-watcher loop):

```
unwatched           --workspace links via setup-project--> watching
watching            --tasks.md change event--> diffing
diffing             --diff is empty--> watching
diffing             --diff is non-empty--> publishing SSE → watching
watching            --workspace unlinks or backend shuts down--> unwatched
```

---

## 4. Cross-cutting validation

- **Project ID coherence**: any disagreement on `projectId` between `<workspace>/.claude/robo-project.json` and an MCP call payload is a hard error. The MCP call is rejected; the skill reports it. (There is no `.robo-link.json` to conflict with — by design, see §2.4.)
- **Element ID resolution**: every `elementId` referenced in `tasks.md` markers MUST resolve to a real node in the graph at request time. Unresolvable IDs surface as `status: "orphaned"` in SSE progress events; they do not crash the watcher (edge case from spec).
- **Source mapping integrity**: every `:ImplementationFile` node MUST satisfy the uniqueness constraint on `(projectId, path)`. `[:IMPLEMENTED_IN]` from an element to a file is created idempotently — a duplicate create is a no-op rather than a constraint violation.
- **Atomicity**: writes to `tasks.md` go through a write-temp-then-rename pattern so the backend file-watcher never reads a half-written file. Mutations to `:ImplementationFile` nodes and their relationships go through Neo4j's existing transactional pathway in `api/platform/neo4j.py`.
