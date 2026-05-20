# REST API Contracts: DDD Artifact Generation from Event Storming

All new endpoints live under a new `/api/ddd-spec` prefix, registered in `api/main.py` next to the existing feature routers. Nothing here modifies any existing endpoint.

## 1. `POST /api/ddd-spec/generate-bounded-context`

Synchronous. Generates the full DDD artifact folder for one Bounded Context under `specs/bounded-contexts/<bc-slug>/`. Seconds-scale (no network roundtrips except optional, capped, best-effort wireframe SVG renders).

### Request body

```json
{
  "bounded_context_id": "bc-order-management-9a4d",
  "overwrite": false,
  "aliases_to_avoid": "suggest",
  "smooth_ears": true,
  "render_svg": true
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `bounded_context_id` | string | yes | — | Neo4j `BoundedContext.id`. |
| `overwrite` | boolean | no | `false` | Replace existing `.md` / sidecar files; preserve unreferenced `requirements.assets/*` (reported stale). |
| `aliases_to_avoid` | `"omit"` \| `"suggest"` | no | `"suggest"` | `"omit"` → drop the "Aliases to AVOID" line where the graph has none; `"suggest"` → LLM-suggested list marked "(suggested — confirm)" (falls back to omit + warning if LLM unavailable). |
| `smooth_ears` | boolean | no | `true` | LLM grammar smoothing of EARS lines; `false` for fully deterministic output. |
| `render_svg` | boolean | no | `true` | Attempt SVG render of bound wireframes via the open-pencil service. |

### Responses

**`200 OK`** — generated (or partially generated with warnings)

```json
{
  "created": [
    { "kind": "domain_terms",   "path": "specs/bounded-contexts/order-management/domain-terms.md", "bounded_context_id": "bc-order-management-9a4d", "aggregate_id": null },
    { "kind": "bc_canvas",      "path": "specs/bounded-contexts/order-management/bc-order-management.md", "bounded_context_id": "bc-order-management-9a4d", "aggregate_id": null },
    { "kind": "aggregate_spec", "path": "specs/bounded-contexts/order-management/aggregates/aggregate-order.md", "bounded_context_id": "bc-order-management-9a4d", "aggregate_id": "agg-order-7f2c" },
    { "kind": "requirements",   "path": "specs/bounded-contexts/order-management/requirements.md", "bounded_context_id": "bc-order-management-9a4d", "aggregate_id": null },
    { "kind": "scene_json",     "path": "specs/bounded-contexts/order-management/requirements.assets/US-1-checkout.scene.json", "bounded_context_id": "bc-order-management-9a4d", "aggregate_id": null },
    { "kind": "svg",            "path": "specs/bounded-contexts/order-management/requirements.assets/US-1-checkout.svg", "bounded_context_id": "bc-order-management-9a4d", "aggregate_id": null }
  ],
  "skipped": [],
  "warnings": [
    { "code": "no_external_integrations", "message": "No external-system integrations modeled for this BC; no acl-*.md produced.", "target": {"bounded_context_id": "bc-order-management-9a4d"} }
  ],
  "correlation_id": "req-9a4d12"
}
```

**`200 OK` with `skipped`** — folder/files already exist and `overwrite=false`

```json
{
  "created": [],
  "skipped": [
    { "kind": "bounded_context", "id": "bc-order-management-9a4d", "existing_path": "specs/bounded-contexts/order-management/", "reason": "already_exists" }
  ],
  "warnings": [],
  "correlation_id": "req-9a4d12"
}
```

**`400 Bad Request`** — BC has neither Aggregates nor User Stories. Body: `{ "detail": "...", "code": "empty_bounded_context" }`.

**`404 Not Found`** — `bounded_context_id` does not resolve to a node.

**`409 Conflict`** — another generation operation holds the lock. Body includes the holder's `correlation_id`.

**`500 Internal Server Error`** — unexpected failure (graph driver, filesystem). Body: `{ "detail": "...", "correlation_id": "..." }`.

### Side effects

- Creates `specs/bounded-contexts/<bc-slug>/` with `domain-terms.md`, `bc-<bc-slug>.md`, `aggregates/aggregate-<slug>.md` × N, `requirements.md`, `requirements.assets/*.scene.json` (one per bound wireframe), `requirements.assets/*.svg` (best-effort), and `acl-<slug>.md` × M (only if external integrations are modeled).
- Holds `specs/bounded-contexts/.ddd-spec.lock` across scan + create; releases on response.
- Emits SmartLogger JSONL events at phase boundaries, tagged with the returned `correlation_id`.
- Renders each artifact to a temp staging dir, then `os.replace`s into place (per-file atomicity).
- Does **not** modify Neo4j. Does **not** touch `specs/constitution.md` or `specs/NNN-*/`. Makes **no Figma call**.

## 2. `POST /api/ddd-spec/generate-aggregate`

Synchronous. Refreshes just `specs/bounded-contexts/<bc-slug>/aggregates/aggregate-<slug>.md` for one Aggregate; leaves all sibling artifacts untouched.

### Request body

```json
{ "aggregate_id": "agg-order-7f2c", "overwrite": false, "smooth_ears": true }
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `aggregate_id` | string | yes | — | Neo4j `Aggregate.id`. |
| `overwrite` | boolean | no | `false` | Replace just the one Aggregate Spec file. |
| `smooth_ears` | boolean | no | `true` | |

### Responses

- **`200 OK`** — `GenerationResult` with `created` containing the single `aggregate_spec` entry (and `skipped` containing it instead, with `reason: "already_exists"`, when the file exists and `overwrite=false`). The parent `aggregates/` directory and BC folder are created if absent, without disturbing siblings.
- **`404 Not Found`** — `aggregate_id` does not resolve, or its Bounded Context cannot be determined.
- **`409 Conflict`** — lock held by another operation.
- **`500`** — unexpected failure.

## 3. `POST /api/ddd-spec/generate-context-map`

Synchronous. (Re)generates the single system-level `specs/context-map.md` from all Bounded Contexts and the modeled cross-BC flows.

### Request body

```json
{ "overwrite": false, "infer_patterns_with_llm": false }
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `overwrite` | boolean | no | `false` | Replace `specs/context-map.md`. |
| `infer_patterns_with_llm` | boolean | no | `false` | Layer `llm_assist.infer_relationship_pattern` on top of the heuristic; the "(inferred — confirm)" marker and `relationship_pattern_inferred` warning are emitted regardless. |

### Responses

- **`200 OK`** — `GenerationResult` with a single `context_map` entry in `created` (or in `skipped` with `reason: "already_exists"` when the file exists and `overwrite=false`). `warnings` includes a `relationship_pattern_inferred` entry per edge whose pattern was not read directly from the graph, and a note when there is only one BC (empty Relationships section).
- **`400 Bad Request`** — the graph contains zero Bounded Contexts. Body: `{ "detail": "...", "code": "no_bounded_contexts" }`.
- **`409 Conflict`** — lock held.
- **`500`** — unexpected failure.

## 4. `POST /api/ddd-spec/generate-all`

SSE-streamed. Generates `specs/context-map.md` plus every Bounded Context's full artifact folder.

### Request body

```json
{
  "overwrite": false,
  "aliases_to_avoid": "suggest",
  "smooth_ears": true,
  "render_svg": true,
  "infer_patterns_with_llm": false
}
```

(Field semantics as in the per-BC and context-map endpoints; `overwrite` applies per BC and to the context map.)

### Response

`200 OK` with `Content-Type: text/event-stream`. Events in the order documented in `data-model.md` §3. The final event is always `complete` (at least the context map and/or one BC processed) or `error` (whole-run abort). Example trace for two BCs, one fully OK and one whose wireframe SVG fails:

```text
event: phase
data: {"phase": "loading_model", "message": "Loading all Bounded Contexts from Neo4j"}

event: phase
data: {"phase": "context_map", "message": "Rendering context-map.md"}

event: warning
data: {"code": "relationship_pattern_inferred", "message": "Edge Catalog → Order Management: pattern not modeled; inferred Conformist+ACL", "target": {"from_bc_id": "bc-catalog", "to_bc_id": "bc-order-management-9a4d"}}

event: phase
data: {"phase": "bounded_contexts", "message": "Generating 2 Bounded Context folders"}

event: bc_started
data: {"bounded_context_id": "bc-order-management-9a4d", "bounded_context_name": "Order Management", "index": 1, "total": 2}

event: wireframe_rendered
data: {"bounded_context_id": "bc-order-management-9a4d", "user_story_id": "US-1", "ui_id": "ui-checkout", "scene_json_path": "specs/bounded-contexts/order-management/requirements.assets/US-1-checkout.scene.json", "svg_path": "specs/bounded-contexts/order-management/requirements.assets/US-1-checkout.svg"}

event: bc_completed
data: {"bounded_context_id": "bc-order-management-9a4d", "files": [ ... ArtifactFileInfo[] ... ]}

event: bc_started
data: {"bounded_context_id": "bc-payments", "bounded_context_name": "Payments", "index": 2, "total": 2}

event: warning
data: {"code": "svg_render_failed", "message": "open-pencil service returned 503 for ui-refund; SVG omitted", "target": {"bounded_context_id": "bc-payments", "ui_id": "ui-refund"}}

event: wireframe_rendered
data: {"bounded_context_id": "bc-payments", "user_story_id": "US-9", "ui_id": "ui-refund", "scene_json_path": "specs/bounded-contexts/payments/requirements.assets/US-9-refund.scene.json", "svg_path": null}

event: bc_completed
data: {"bounded_context_id": "bc-payments", "files": [ ... ]}

event: complete
data: {"created": [ ... all files ... ], "skipped": [], "warnings": [ ... ], "correlation_id": "req-allgen-22"}
```

### Error event (whole-run abort)

```text
event: error
data: {"error_code": "no_bounded_contexts", "message": "The graph contains no Bounded Contexts", "correlation_id": "req-allgen-22"}
```

After an `error` event the server closes the stream — terminal state, no further events.

### Side effects

- Same as the per-BC endpoint, applied to every BC, plus the context map.
- A BC pipeline failure emits `bc_failed` and continues; no folder is created for the failed BC.
- Each BC folder write is staged in a temp dir and `os.replace`d into place (atomic per folder's set of files).

## 5. Existing endpoints (unchanged)

This feature does **not** modify any `api/features/figma_binding/*`, `api/features/ingestion/*`, `api/features/claude_code/*`, or any other existing endpoint **except** the PRD-generation endpoints, which receive minor request-validation additions (FR-020) and consumer-side output additions (FR-021–FR-024) — documented in section 7 below. It only *calls* (does not modify) `api/platform/open_pencil_client.py` for best-effort wireframe SVG rendering. No new environment variable is introduced; `WIREFRAME_SERVICE_URL` (already present) is the only external-service config touched.

## 6. Error / warning code reference

| Code | Where | Meaning |
|------|-------|---------|
| `bounded_context_not_found` | 404 | BC id does not resolve. |
| `aggregate_not_found` | 404 | Aggregate id does not resolve (or its BC can't be determined). |
| `no_bounded_contexts` | 400 / SSE `error` | The graph has zero Bounded Contexts. |
| `empty_bounded_context` | 400 | BC has no Aggregates and no User Stories. |
| `already_exists` | 200 (in `skipped`) | Target folder/file exists and `overwrite=false`. |
| `lock_busy` | 409 | Another generation operation holds the lock. |
| `path_escape` | 500 | A computed write path resolved outside `specs/` — hard fail rather than write outside the sandbox. |
| `command_missing_gwt` | warning | A Command has no GWT; flagged in the Aggregate Spec's "Open Decisions" and `requirements.md`. |
| `bc_not_classified` | warning | The BC has no strategic classification; Canvas marks "(not classified — confirm)". |
| `bc_purpose_missing` | warning | The BC has no purpose text; Canvas marks "(not modeled — confirm)". |
| `relationship_pattern_inferred` | warning | A Context-Map edge's pattern was inferred, not read from the graph. |
| `wireframe_service_unavailable` | warning | `WIREFRAME_SERVICE_URL` not reachable; all SVGs skipped this run. |
| `svg_render_failed` | warning | One wireframe's SVG render failed; SVG omitted for that one. |
| `aliases_to_avoid_unavailable` | warning | `aliases_to_avoid="suggest"` requested but LLM unavailable; lines omitted instead. |
| `llm_unavailable` | warning | LLM runtime unavailable; deterministic-only output produced (affects EARS smoothing, alias suggestions, optional pattern inference). |
| `stale_asset` | warning | On overwrite, a file under `requirements.assets/` is no longer referenced by the new `requirements.md` (not deleted). |
| `no_external_integrations` | warning | The BC models no external-system integrations; no `acl-*.md` produced (informational, not a defect). |
| `frontend_framework_required` | 400 (`POST /api/prd/generate`, `POST /api/prd/download`) | `include_frontend=true` but `frontend_framework` is missing or null. |
| `frontend_framework_unsupported` | warning | The declared framework has no curated conventions in the catalog; `specs/frontend/framework.md` renders the "(no curated conventions — confirm)" marker. |
| `ui_flow_no_cross_bc_edges` | warning | The graph has no cross-BC Policy/Event flows to sequence by; `specs/frontend/ui-flow.md` falls back to BC insertion order. |
| `ui_flow_cycle_broken` | warning | The UI-flow topological sort detected a cycle and removed a back-edge to linearise; `target` names the removed edge. |
| `ui_unreferenced_flow` | warning | A bound UI did not participate in any flow chain; rendered at the tail of `ui-flow.md` with "(unreferenced flow — review)". |
| `deprecated_per_bc_agent` | `skipped` reason | A `.claude/agents/<bc_name>_agent.md` from a prior generation is no longer emitted (FR-023); the user is responsible for deleting their local copy. |
| `prd_split_lint_failed` | 500 | The build's PRD↔CLAUDE content-split lint (D9) found prescriptive prose in PRD.md or inventory content in CLAUDE.md / `.cursorrules`. The response body names the offending file + substring. Aborts the zip build — this is a packaging contract, not a degradable warning. |
| `frontend_viewport_dominant` | warning | **(2026-05-13)** One viewport class (`mobile`/`tablet`/`desktop`) covers ≥ 70% of the known-viewport wireframes; `target` carries `{dominant, mobile, tablet, desktop, unknown}` counts. Informational — the generated `framework.md` instructs the `frontend-engineer` agent to ask the user whether to design the whole IA in that direction. See research D11. |
| `frontend_viewport_mixed` | warning | **(2026-05-13)** No viewport class covers ≥ 70%; `target` carries the same counts. The generated `framework.md` reads `Dominant: mixed — ask the user`; the agent asks which class drives the IA. See research D11. |

## 7. `/api/prd/*` — packaging surface additions (2026-05-12 amendment)

The DDD artifact set's *consumer-side packaging* (PRD.md, CLAUDE.md or `.cursorrules`, `.claude/{skills,agents,commands}/*`, `Frontend-PRD.md`, the new `specs/frontend/*.md`) flows through the existing `/api/prd/generate` (plan + file list) and `/api/prd/download` (zip stream) endpoints in `api/features/prd_generation/`. The 2026-05-12 amendment adds the following to those endpoints; no new endpoint is introduced.

### 7.1 Request-body additions (both `/api/prd/generate` and `/api/prd/download`)

The body is `PRDGenerationRequest` (existing), whose `tech_stack: TechStackConfig` field gains a new server-side validation:

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `tech_stack.frontend_framework` | `"vue" \| "react" \| "svelte" \| …` | **conditionally required** | `null` | When `tech_stack.include_frontend=true`, this field MUST be set (FR-020). Server returns HTTP 400 + code `frontend_framework_required` otherwise. The set of accepted values is whatever the catalog enumerates (Svelte added in this amendment; future additions are a downstream task, not a contract change). |
| `tech_stack.include_frontend` | `bool` | no | `false` | When `true` AND `tech_stack.spec_format = "ddd"`, the zip materialises `specs/frontend/{framework,menu-structure,ui-flow}.md` + the new role-based agents + the `/generate-frontend` slash command. When `false`, none of those files appear and the framework field is ignored. |

No other fields change. Existing `node_ids`, `spec_format`, `ai_assistant`, `language`, `framework`, `messaging`, etc. behave exactly as before.

### 7.2 Response additions

`POST /api/prd/generate` returns a JSON plan containing `files_to_generate: string[]`. The 2026-05-12 amendment extends this list when `include_frontend=true` AND `spec_format=ddd`:

```jsonc
{
  "success": true,
  "bounded_contexts": [ /* unchanged */ ],
  "tech_stack": { /* unchanged */ },
  "files_to_generate": [
    "PRD.md",
    "CLAUDE.md",
    "README.md",
    ".cursorrules",
    ".claude/skills/ddd-principles.md",
    ".claude/skills/eventstorming-implementation.md",
    ".claude/skills/gwt-test-generation.md",
    ".claude/skills/<framework>.md",
    ".claude/skills/ddd-spec-implementation.md",        // when spec_format=ddd (existing)
    ".claude/skills/<frontend_framework>.md",            // when include_frontend=true (existing)
    ".claude/commands/implement-ddd-bc.md",              // when spec_format=ddd (existing)
    ".claude/commands/implement-ddd-wireframe.md",       // when spec_format=ddd (existing)
    ".claude/commands/generate-frontend.md",             // NEW — FR-024
    ".claude/agents/frontend-engineer.md",                // NEW — FR-023 (role-based, one per project)
    ".claude/agents/ddd-specialist.md",                   // NEW — FR-023 (role-based, one per project)
    "Frontend-PRD.md",
    "specs/context-map.md",                              // existing
    "specs/bounded-contexts/<bc-slug>/...",              // existing (planned_paths_for_preview)
    "specs/frontend/framework.md",                       // NEW — FR-021
    "specs/frontend/menu-structure.md",                  // NEW — FR-021
    "specs/frontend/ui-flow.md",                         // NEW — FR-021
    "docker-compose.yml",
    "Dockerfile"
  ],
  "download_url": "/api/prd/download"
}
```

**The list MUST NOT contain** any `.claude/agents/<bc_name>_agent.md` entries — FR-023 forbids per-BC agent emission.

`POST /api/prd/download` returns the zip stream with the same file set on disk. Inside the zip, all paths above appear exactly as listed; the disjoint-content contract (PRD vs CLAUDE / .cursorrules) is enforced by the build-time D9 lint, which aborts the zip with HTTP 500 + code `prd_split_lint_failed` if violated.

### 7.3 Server-side behaviours added

- **Precondition validation** (FR-020): when `include_frontend=true` AND `frontend_framework` is missing/null, return 400 with body `{"code": "frontend_framework_required", "detail": "Select a frontend framework before generation (vue / react / svelte / …)."}`. Same applies to `/api/prd/generate` (plan) and `/api/prd/download` (zip).
- **Frontend artifact materialisation** (FR-021): when `include_frontend=true` AND `spec_format=ddd`, the zip path additionally calls `api.features.ddd_spec.inproc.render_frontend_spec_to_zip(zip_file, framework, bcs)` which writes the three `specs/frontend/*.md` files. The renderer never duplicates wireframe assets; it uses relative paths back to `specs/bounded-contexts/<bc>/requirements.assets/*` (SC-010).
- **PRD↔CLAUDE split lint** (FR-022, SC-011, D9): runs at zip build time, after `PRD.md` and `CLAUDE.md` / `.cursorrules` are rendered, before they are written into the archive. Failure aborts the zip and returns 500 + `prd_split_lint_failed`. Success emits a `prd_split_lint_passed` SmartLogger event.
- **Per-BC agent suppression** (FR-023): `generate_agent_config` is no longer called inside the per-BC zip loop. If the user uploads a previous zip's content for a refresh (a future use case), pre-existing per-BC agent files are reported as `SkippedItem(reason="deprecated_per_bc_agent")` rather than refreshed.
- **Role-based agent emission** (FR-023): when `ai_assistant=claude`, the zip always includes `.claude/agents/frontend-engineer.md` (only when `include_frontend=true`) and `.claude/agents/ddd-specialist.md` (always, when `spec_format=ddd`). Each agent body references skills under `.claude/skills/` by relative path; bodies are stable across runs (byte-stable except a `Generated:` timestamp).
- **`/generate-frontend` slash command** (FR-024): when `ai_assistant=claude` AND `spec_format=ddd` AND `include_frontend=true`, the zip includes `.claude/commands/generate-frontend.md`. Its body walks `specs/frontend/framework.md`, `specs/frontend/menu-structure.md`, and `specs/frontend/ui-flow.md`; follows each `ui-flow` entry's relative links to the canonical scene-graph + SVG + element-tree blocks; and instructs the coding agent (via the Frontend Engineer role agent) to produce one component per wireframe in the declared framework.
- **Viewport classification + intent prompt** (FR-025/026, 2026-05-13, research D11): during frontend artifact materialisation, every bound wireframe's primary-frame width is bucketed into `mobile` (≤480), `tablet` (481–1024), `desktop` (>1024), or `unknown`. `specs/frontend/framework.md` carries a `## Viewport summary` block with per-class counts + `Dominant: <class>` (or `mixed — ask the user` when no class covers ≥70% of the known total). The `frontend-engineer` agent body + `/generate-frontend` command body include a "Viewport intent check" step that the agent runs before generating components, asking the user to confirm the dominant direction (or pick one when mixed). Two warning codes added to the response: `frontend_viewport_dominant` (with the counts + dominant) and `frontend_viewport_mixed` (with the counts, no dominant). Neither aborts generation; they are informational signals the user sees in the response and the agent sees in the `framework.md` body.

### 7.4 What is **NOT** changed on `/api/prd/*`

- No new endpoint added.
- No request-shape change beyond conditional validation of `frontend_framework`.
- No env-var added.
- `node_ids`, `spec_format`, `ai_assistant`, `language`, `framework`, `messaging`, `database`, `deployment`, `project_name`, `package_name`, `include_docker`, `include_kubernetes`, `include_tests` — all unchanged.
- Existing zip contents that pre-date this amendment (PRD.md/CLAUDE.md/skills/.cursor/rules/specs/bounded-contexts/...) are still produced; only their *internal content* changes per D9 (split) and the *agent files* change per D10 (role-based replaces per-BC).
