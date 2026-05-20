# Phase 1 Data Model: DDD Artifact Generation from Event Storming

This feature **introduces no persisted entities** — no new Neo4j nodes, no database rows, no on-disk metadata beyond the generated DDD artifacts themselves. The "data model" is:

1. **Read-side projection types** — internal Pydantic shapes populated by the Neo4j repository from existing graph nodes/relationships. They mirror parts of `docs/cypher/schema/03_node_types.cypher` (and `04_relationships.cypher`); they do not extend the schema.
2. **HTTP request/response shapes** — what the new endpoints accept and return.
3. **SSE event shapes** — what the streaming whole-model endpoint emits.

This document captures (1)–(3) so the contracts and the renderers stay consistent.

## 1. Read-side projection types

Populated by `api/features/ddd_spec/repository.py`. Read-only; never persisted. Defined in `api/features/ddd_spec/projection.py`.

### `BoundedContextProjection`

| Field | Type | Source |
|-------|------|--------|
| `id` | `str` | `BoundedContext.id` |
| `name` | `str` | `BoundedContext.name` |
| `slug` | `str` | Derived from `name` (D5). |
| `description` | `str \| None` | `BoundedContext.description` |
| `purpose` | `str \| None` | `BoundedContext.purpose` if present, else `None` → BC Canvas marks "(not modeled — confirm)". |
| `strategic` | `StrategicClassification \| None` | Domain type / business model / evolution if the graph carries them; else `None` → "(not classified — confirm)". |
| `aggregates` | `list[AggregateProjection]` | Aggregates in this BC. |
| `user_stories` | `list[UserStoryProjection]` | User Stories in this BC (grouped by Aggregate downstream). |
| `external_integrations` | `list[ExternalIntegrationProjection]` | Modeled BC→external links; empty list if none → no `acl-*.md` files. |
| `inbound_flows` | `list[CrossBcFlow]` | Edges where another BC supplies something this BC consumes. |
| `outbound_flows` | `list[CrossBcFlow]` | Edges where this BC supplies something another BC consumes. |
| `key_terms` | `list[str]` | The handful of headline terms for the BC Canvas's "Ubiquitous Language (summary)" — derived (aggregate names + their root entities). |

### `StrategicClassification`

| Field | Type | Notes |
|-------|------|-------|
| `domain_type` | `Literal["Core","Supporting","Generic"] \| None` | If the graph records it. |
| `business_model` | `str \| None` | E.g. "Revenue generator". |
| `evolution` | `str \| None` | E.g. "Custom-built (no off-the-shelf alternative)". |

### `AggregateProjection`

| Field | Type | Source |
|-------|------|--------|
| `id` | `str` | `Aggregate.id` |
| `name` | `str` | `Aggregate.name` |
| `slug` | `str` | Derived from `name` (D5). |
| `description` | `str \| None` | `Aggregate.description` |
| `root_entity` | `str` | The aggregate-root entity name (defaults to `name` if not separately modeled). |
| `member_entities` | `list[MemberEntity]` | Owned entities and value objects (incl. the identity VOs and the status enum) — from `HAS_PROPERTY` / nested-entity modeling where available; minimally derived from attribute types. |
| `attributes` | `list[AggregateAttribute]` | Properties via `(:Aggregate)-[:HAS_PROPERTY]->(:Property)`. |
| `invariants` | `list[str]` | `Aggregate.invariants` string array if present (unconditional invariants). |
| `commands` | `list[CommandProjection]` | Commands operating on this Aggregate. |
| `events` | `list[EventProjection]` | Events emitted by this Aggregate. |
| `policies` | `list[PolicyProjection]` | Policies reacting to this Aggregate's events (→ "Corrective Policies" section). |
| `read_models` | `list[ReadModelProjection]` | ReadModels projecting from this Aggregate. |
| `identity_type` | `str` | Inferred id VO name (e.g. `OrderId`) for the Repository Interface stub. |

### `AggregateAttribute`

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | Field name. |
| `type` | `str` | E.g. `OrderId`, `Money`, `List<OrderItem>`, `OrderStatus`. |
| `mutability` | `str` | E.g. "immutable after creation", "mutable in Draft, immutable after Confirmed", "computed (sum of items × prices)" — from a graph hint if present, else derived ("identifier → immutable", "computed → computed", else "mutable through commands only"). |
| `description` | `str \| None` | |

### `MemberEntity`

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | |
| `kind` | `Literal["entity","value_object","enum","identifier"]` | Drives the "(entity, owned)" / "(value object — …)" annotation in the Aggregate Spec. |
| `note` | `str \| None` | E.g. for an enum: the member list `Draft \| Confirmed \| Fulfilled \| Closed \| Cancelled`. |

### `CommandProjection`

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | |
| `name` | `str` | E.g. `Confirm()`, `AddItem(productId, qty)`. |
| `description` | `str \| None` | |
| `preconditions` | `list[str]` | From the Command's modeled preconditions and/or the `Given` clauses of its GWT. Empty → "none". |
| `postconditions` | `list[str]` | From the Command's modeled postconditions and/or the `Then` clauses of its GWT. |
| `events_emitted` | `list[str]` | Event names this Command emits on success. |
| `gwt` | `list[GwtCriterion]` | Raw criteria; the source for EARS invariants and EARS acceptance criteria. Empty → command flagged in "Open Decisions" + warning `command_missing_gwt`. |
| `user_story_ids` | `list[str]` | User Stories this Command participates in (for grouping AC under stories in `requirements.md`). |

### `GwtCriterion`

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | |
| `given` | `list[str]` | Zero or more state clauses. Joined with `AND` in EARS. |
| `when` | `str` | The trigger clause. |
| `then` | `list[str]` | One or more obligation clauses → one `SHALL` line each. |

### `EventProjection` / `PolicyProjection` / `ReadModelProjection`

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | |
| `name` | `str` | For events, includes the payload tuple where modeled, e.g. `OrderConfirmed(OrderId, TotalAmount, ItemCount, ConfirmedAt)`. |
| `description` | `str \| None` | |
| `effect` | `str \| None` | (Policy only) what the policy does on the eventual-consistency path → renders into "Corrective Policies". |

### `UserStoryProjection`

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | |
| `title` | `str` | |
| `narrative` | `str` | "As a … I want … So that …" if the graph stores that shape; else the raw narrative. |
| `priority` | `Literal["P1","P2","P3","P4","P5"] \| None` | If modeled; else `None` → renderer falls back to insertion order. |
| `aggregate_id` | `str \| None` | The Aggregate this story belongs to (grouping key in `requirements.md`); `None` → grouped under "(unassigned)". |
| `acceptance_criteria` | `list[GwtCriterion]` | The story's own GWT (may overlap with its Commands' GWT — deduped by id within the story). |
| `wireframes` | `list[WireframeProjection]` | UI nodes bound to this story. |

### `WireframeProjection`

| Field | Type | Notes |
|-------|------|-------|
| `ui_id` | `str` | `UI.id` |
| `name` | `str` | `UI.name` / `UI.displayName`. |
| `slug` | `str` | Derived from `name` (D5) — used in the asset filenames. |
| `scene_graph_json` | `str \| None` | `UI.sceneGraph` (open-pencil `SerializedSceneGraph` JSON string). `None` → "no scene graph modeled" note. |
| `template` | `str \| None` | `UI.template` if present (HTML/JSX template) — included as a fenced block when no scene graph is available. |
| `attached_to_type` | `Literal["Command","ReadModel"] \| None` | `UI.attachedToType`. |
| `attached_to_name` | `str \| None` | `UI.attachedToName`. |
| `actor` | `str \| None` | `UI.actor`. |
| `viewport_class` | `Literal["mobile","tablet","desktop"] \| None` | **(2026-05-13)** Computed at projection-load time by `wireframe_render.extract_viewport_class(scene_graph_json)` — finds the primary frame in the scene graph and buckets its **width**: `≤480 → mobile`, `481..1024 → tablet`, `>1024 → desktop`, otherwise `None`. See research D11. |

(Note: `UI.figmaFileKey` / `UI.figmaNodeId` exist on the node but are deliberately **not** read by this feature — no Figma call is ever made.)

### `ExternalIntegrationProjection`

| Field | Type | Notes |
|-------|------|-------|
| `id` | `str` | |
| `external_system_name` | `str` | E.g. "Stripe". |
| `slug` | `str` | → `acl-<slug>.md`. |
| `direction` | `Literal["inbound","outbound","bidirectional"]` | |
| `our_concepts` | `list[str]` | Names inside our domain (the "Inside (our domain)" boundary list). |
| `external_concepts` | `list[str]` | Names from the external system (the "Outside" boundary list). |
| `inbound_field_map` | `list[tuple[str,str,str]]` | (external field, our field, translation) rows — if modeled; else empty → ACL marks the map "(to be defined)". |
| `outbound_call_map` | `list[tuple[str,str,str]]` | (our command, external API call, notes) rows — if modeled. |
| `error_map` | `list[tuple[str,str]]` | (external code, our exception) rows — if modeled. |
| `forbidden_concepts` | `list[str]` | External names that must not leak into the core — if modeled. |

### `CrossBcFlow`

| Field | Type | Notes |
|-------|------|-------|
| `from_bc_id` | `str` | Upstream BC. |
| `from_bc_name` | `str` | |
| `to_bc_id` | `str` | Downstream BC. |
| `to_bc_name` | `str` | |
| `channel` | `str` | E.g. "Event bus", "HTTP API". |
| `message` | `str` | E.g. `OrderConfirmed`, `CreateOrderCommand`. |
| `recorded_pattern` | `str \| None` | The DDD relationship pattern if the graph records it; else `None` → inferred (D6) and marked "(inferred — confirm)". |

## 2. HTTP request / response shapes

Defined in `api/features/ddd_spec/schemas.py` (Pydantic v2).

### `GenerateBoundedContextRequest` (body of `POST /generate-bounded-context`)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `bounded_context_id` | `str` | required | |
| `overwrite` | `bool` | `false` | Replace existing `.md` / sidecar files in the BC folder; preserve unreferenced `requirements.assets/*` (reported stale). |
| `aliases_to_avoid` | `Literal["omit","suggest"]` | `"suggest"` | `"omit"` → `domain-terms.md` entries drop the "Aliases to AVOID" line when the graph has none; `"suggest"` → an LLM-suggested list marked "(suggested — confirm)" (deterministic fallback: omit + warning if LLM unavailable). |
| `smooth_ears` | `bool` | `true` | LLM grammar smoothing of EARS lines; `false` for fully deterministic regeneration. |
| `render_svg` | `bool` | `true` | Attempt SVG render of bound wireframes via the open-pencil service; `false` → textual tree + `.scene.json` only. |

### `GenerateAggregateRequest` (body of `POST /generate-aggregate`)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `aggregate_id` | `str` | required | |
| `overwrite` | `bool` | `false` | Replace just `aggregates/aggregate-<slug>.md`. |
| `smooth_ears` | `bool` | `true` | |

### `GenerateContextMapRequest` (body of `POST /generate-context-map`)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `overwrite` | `bool` | `false` | Replace `specs/context-map.md`. |
| `infer_patterns_with_llm` | `bool` | `false` | Use `llm_assist.infer_relationship_pattern` on top of the heuristic; the "(inferred — confirm)" marker and warning stay regardless. |

### `GenerateAllRequest` (body of `POST /generate-all`, SSE)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `overwrite` | `bool` | `false` | Per-BC; existing folders skipped unless `true`. Also applies to `context-map.md`. |
| `aliases_to_avoid` | `Literal["omit","suggest"]` | `"suggest"` | |
| `smooth_ears` | `bool` | `true` | |
| `render_svg` | `bool` | `true` | |
| `infer_patterns_with_llm` | `bool` | `false` | |

### `ArtifactFileInfo` (one entry in a result)

| Field | Type | Notes |
|-------|------|-------|
| `kind` | `Literal["domain_terms","bc_canvas","aggregate_spec","acl_spec","requirements","context_map","scene_json","svg"]` | |
| `path` | `str` | Repo-relative, e.g. `specs/bounded-contexts/order-management/aggregates/aggregate-order.md`. |
| `bounded_context_id` | `str \| None` | `None` for `context_map`. |
| `aggregate_id` | `str \| None` | Set for `aggregate_spec`. |

### `SkippedItem`

| Field | Type | Notes |
|-------|------|-------|
| `kind` | `Literal["bounded_context","aggregate","context_map","artifact_file"]` | |
| `id` | `str \| None` | BC / Aggregate id where applicable. |
| `existing_path` | `str` | The pre-existing path that prevented the write. |
| `reason` | `Literal["already_exists","empty_bounded_context"]` | Machine-readable; a human string is also returned. |

### `GenerationWarning`

| Field | Type | Notes |
|-------|------|-------|
| `code` | `str` | E.g. `command_missing_gwt`, `bc_not_classified`, `relationship_pattern_inferred`, `wireframe_service_unavailable`, `svg_render_failed`, `aliases_to_avoid_unavailable`, `llm_unavailable`, `stale_asset`, `no_external_integrations`. |
| `message` | `str` | Human-readable. |
| `target` | `dict[str,str]` | Identifying fields, e.g. `{"command_id": "...", "aggregate_id": "..."}`. |

### `GenerationResult` (response of the three sync endpoints; also the payload of the SSE `complete` event)

| Field | Type | Notes |
|-------|------|-------|
| `created` | `list[ArtifactFileInfo]` | Every file written. |
| `skipped` | `list[SkippedItem]` | |
| `warnings` | `list[GenerationWarning]` | |
| `correlation_id` | `str` | Same id on the SmartLogger trace — lets the user grep the JSONL log. |

## 3. SSE event shapes (`POST /generate-all`)

Same envelope as other SSE endpoints in the repo (`event: <name>` line + `data: <json>` line; see `api/features/ingestion/router.py`).

| Event | Payload | Emitted when |
|-------|---------|--------------|
| `phase` | `{ "phase": "loading_model" \| "context_map" \| "bounded_contexts", "message": "..." }` | At each top-level phase. |
| `bc_started` | `{ "bounded_context_id": str, "bounded_context_name": str, "index": int, "total": int }` | Before processing each BC. |
| `wireframe_rendered` | `{ "bounded_context_id": str, "user_story_id": str, "ui_id": str, "scene_json_path": str, "svg_path": str \| null }` | After each wireframe's sidecars are written (`svg_path` null if SVG skipped). |
| `bc_completed` | `{ "bounded_context_id": str, "files": list[ArtifactFileInfo] }` | When a BC's folder is fully written. |
| `bc_failed` | `{ "bounded_context_id": str, "error_code": str, "message": str }` | When a BC's pipeline fails. The run continues. |
| `warning` | `GenerationWarning` shape | Anywhere, for a non-fatal degradation. |
| `complete` | `GenerationResult` shape | Last event; closes the stream. |
| `error` | `{ "error_code": str, "message": str, "correlation_id": str }` | Last event when the whole run aborts (e.g. lock acquisition failed, no BCs in the graph). Stream closes after. |

## 4. Filesystem outputs

Per generated Bounded Context (under `specs/bounded-contexts/<bc-slug>/`):

```text
domain-terms.md
bc-<bc-slug>.md
aggregates/aggregate-<agg-slug>.md            # one per Aggregate
acl-<external-slug>.md                         # 0..N — only if external integrations are modeled
requirements.md
requirements.assets/<userStoryId>-<ui-slug>.scene.json   # always, for each bound wireframe
requirements.assets/<userStoryId>-<ui-slug>.svg          # only when the wireframe service rendered one
```

Plus the system-level `specs/context-map.md`.

These outputs are not entities the system tracks afterward — once written they belong to the human reviewer and version control. Re-running with `overwrite=true` against an unchanged graph reproduces the same `.md` files (excluding the `Generated:` timestamp line) and preserves any pre-existing files under `requirements.assets/` (unreferenced ones reported as `stale_asset`).

## 5. Graph schema impact

**None.** This feature reads the existing schema in `docs/cypher/schema/03_node_types.cypher` / `04_relationships.cypher` and adds nothing. If a needed property turns out to be unmodeled (e.g. a Bounded Context's strategic classification, or a relationship's DDD pattern), the artifact renders an explicit "(not modeled — confirm)" / "(inferred — confirm)" marker rather than the generator inventing data or a parallel store; the long-term fix for a recurring gap is to extend the relevant event-storming ingestion phase to capture it.

## 6. Frontend perspective additions (2026-05-12 amendment; 2026-05-13 viewport extension)

These shapes back stories P5–P7. They live alongside the existing types in the same module — no new package. The frontend artifact set under `specs/frontend/` is materialised by the new `api/features/ddd_spec/frontend_renderer.py` consumed via `inproc.render_frontend_spec_to_zip` from the PRD-generation flow's `prd_export.py`.

**2026-05-13 amendment**: extends `WireframeProjection`, `UIFlowEntry`, `MenuEntry`, and `FrontendCompositionProjection` with viewport-classification fields (research D11, spec FR-025/026). No graph schema change; no request-body change. The classification is computed during projection load via `api.features.ddd_spec.wireframe_render.extract_viewport_class(scene_graph_json)`.

### 6.1 Read-side projection additions

#### `FrontendCompositionProjection`

Top-level projection passed to the frontend renderer. Populated by a small new walker in `api/features/ddd_spec/repository.py` that reuses the cross-BC flow query the Context Map already issues, then layers the User Story / UI bindings on top.

| Field | Type | Source |
|-------|------|--------|
| `framework` | `FrontendFramework` | Echoed verbatim from the request (`framework.md` line 1). |
| `framework_conventions` | `FrameworkConventions \| None` | From the static catalog in `prd_tech_stack_catalog`; `None` when the catalog has no entry → `framework.md` renders "(no curated conventions — confirm)" and a warning is emitted. |
| `bounded_contexts` | `list[BoundedContextProjection]` | Reused verbatim from §1. |
| `menu` | `list[MenuEntry]` | Hierarchical menu tree grouped by BC; see D7. |
| `ui_flow` | `list[UIFlowEntry]` | Linearised cross-BC narrative; see D8. |
| `unreferenced_uis` | `list[UIFlowEntry]` | Bound UIs that ended up as DAG islands; rendered at the tail of `ui-flow.md` with "(unreferenced flow — review)". |
| `cycle_broken_edges` | `list[tuple[str,str]]` | Edges the topological sort removed to break a cycle, if any; one `ui_flow_cycle_broken` warning per entry. |
| `viewport_summary` | `dict[str,int]` | **(2026-05-13)** Per-class counts across `ui_flow + unreferenced_uis`: keys `"mobile"`, `"tablet"`, `"desktop"`, `"unknown"`. Drives the `## Viewport summary` block in `framework.md`. |
| `dominant_viewport` | `Literal["mobile","tablet","desktop"] \| None` | **(2026-05-13)** The single class covering ≥ 70% of `mobile + tablet + desktop` (unknown excluded). `None` ⇒ mixed; rendered as `Dominant: mixed — ask the user`. Threshold lives in `repository.DOMINANT_VIEWPORT_THRESHOLD`. |

#### `FrameworkConventions`

| Field | Type | Notes |
|-------|------|-------|
| `framework` | `FrontendFramework` | `vue` / `react` / `svelte` / … |
| `component_file_shape` | `str` | E.g. "single-file `.vue` component (template / script setup / style scoped)" / "function component in `.tsx`" / "`.svelte` SFC". |
| `state_default` | `str` | E.g. "Pinia store under `src/stores/`" / "Zustand store under `src/stores/`" / "Svelte writable store in `$lib/stores/`". |
| `routing_default` | `str` | "Vue Router 4 with `<router-view>`" / "React Router 6 with `<Outlet>`" / "SvelteKit file-based routing under `src/routes/`". |
| `styling_default` | `str` | "scoped CSS in the SFC" / "CSS Modules per component" / "scoped CSS in the `.svelte` file". |

#### `MenuEntry`

**(Shape revised in implementation: flat inventory, not a hierarchy.)** One bound UI surfaced as a *hint* to the frontend-engineer agent. The agent designs the actual menu IA from `ui-flow.md` (the user-journey order); BC fields here are traceability metadata only — they do NOT group the menu. Entry-point and unreferenced flags tell the agent which UIs are natural top-level / island candidates.

| Field | Type | Notes |
|-------|------|-------|
| `bc_id` | `str` | Owning Bounded Context id (traceability). |
| `bc_slug` | `str` | For path composition into `requirements.assets/`. |
| `bc_name` | `str` | Display name for citation comments. |
| `user_story_id` | `str` | |
| `user_story_title` | `str` | |
| `wireframe_slug` | `str` | Used to build the `requirements.assets/<userStoryId>-<ui-slug>.{scene.json,svg}` paths. |
| `wireframe_name` | `str` | |
| `actor` | `str \| None` | If the wireframe records an actor. |
| `attached_to_type` | `Literal["Command","ReadModel"] \| None` | The DDD object the wireframe binds to. |
| `attached_to_name` | `str \| None` | |
| `is_entry_point` | `bool` | `True` when the UI has no upstream trigger in the flow DAG (natural top-level navigation candidate). |
| `is_unreferenced` | `bool` | `True` for DAG-island UIs the agent must ask the user to place. |
| `viewport_class` | `Literal["mobile","tablet","desktop"] \| None` | **(2026-05-13)** Inherited from the owning `WireframeProjection` (D11). Rendered in `menu-structure.md` as `[viewport: <class>]` next to the entry heading and as a `Viewport:` field in the bullet list. |

#### `UIFlowEntry`

A single screen in the narrative. The renderer numbers these 1..N in `ui-flow.md` according to the topological sort tiebreaker (D8).

| Field | Type | Notes |
|-------|------|-------|
| `position` | `int` | 1-based ordinal in the final ordering. |
| `bounded_context_id` | `str` | Owning BC; the entry links into that BC's `requirements.md`. |
| `bounded_context_slug` | `str` | For path composition. |
| `user_story_id` | `str` | |
| `user_story_title` | `str` | |
| `wireframe_ui_id` | `str` | |
| `wireframe_slug` | `str` | Used to build the `requirements.assets/<userStoryId>-<ui-slug>.{scene.json,svg}` relative paths. |
| `triggered_by` | `TriggerOrigin \| None` | What caused the user to arrive here in the causal chain; `None` for entry points. |
| `is_unreferenced` | `bool` | `true` for DAG islands rendered with "(unreferenced flow — review)". |
| `viewport_class` | `Literal["mobile","tablet","desktop"] \| None` | **(2026-05-13)** Inherited from the owning `WireframeProjection` (D11). `None` ⇒ unknown viewport. Surfaced in `ui-flow.md` as `[viewport: <class>]` after the entry heading. |

#### `TriggerOrigin`

| Field | Type | Notes |
|-------|------|-------|
| `kind` | `Literal["event","story_internal","entry_point"]` | `event` → cross-BC Policy/Event arrival; `story_internal` → previous UI in the same User Story; `entry_point` → no incoming edge in the DAG. |
| `event_name` | `str \| None` | Only when `kind="event"`. |
| `from_bounded_context_id` | `str \| None` | Only when `kind="event"`. |
| `from_user_story_id` | `str \| None` | Only when `kind="story_internal"` (the previous UI's story — usually the same story but reified for clarity). |

### 6.2 Request-shape additions

The new contract surface is on `/api/prd/generate` and `/api/prd/download` (not a new `/api/ddd-spec` endpoint — see plan.md Complexity Tracking row 2 for the rationale). The existing `TechStackConfig` (in `api/features/prd_generation/prd_api_contracts.py`) is extended:

#### `TechStackConfig` (modified — diff vs. current)

| Field | Type | Default | Status | Notes |
|-------|------|---------|--------|-------|
| `frontend_framework` | `FrontendFramework \| None` | `None` | unchanged shape, new validation | When `include_frontend=true`, the request body MUST set this field (FR-020). Server-side validation refuses with HTTP 400 + code `frontend_framework_required` otherwise — even if a previous run sent the field, it is not remembered. |
| `include_frontend` | `bool` | `false` | unchanged | When `true` + `spec_format=ddd`, the zip materialises `specs/frontend/*.md` + `.claude/commands/generate-frontend.md` + role-based agents. |

#### `FrontendFramework` (modified enum)

| Member | Status | Notes |
|--------|--------|-------|
| `VUE = "vue"` | unchanged | |
| `REACT = "react"` | unchanged | |
| `SVELTE = "svelte"` | **new** | Per spec P5 — the user named Vue/React/Svelte by example. |

(Catalog entries in `prd_tech_stack_catalog` follow the enum; Svelte gains a `FrameworkConventions` stub at minimum.)

### 6.3 Response-shape additions

#### `ArtifactKind` (extended literal union)

The `kind` field on `ArtifactFileInfo` (data-model.md §2 / `api/features/ddd_spec/schemas.py`) gains three values:

| New value | Path it describes |
|-----------|-------------------|
| `frontend_framework` | `specs/frontend/framework.md` |
| `frontend_menu` | `specs/frontend/menu-structure.md` |
| `frontend_ui_flow` | `specs/frontend/ui-flow.md` |

#### `SkippedItem.reason` (extended literal union)

| New value | When |
|-----------|------|
| `deprecated_per_bc_agent` | A `.claude/agents/<bc_name>_agent.md` file was found in the previous output path (the user's working copy or a prior zip) but is no longer emitted (FR-023). The `existing_path` field names the deprecated file. |

#### `GenerationWarning.code` (added codes)

| Code | Meaning |
|------|---------|
| `frontend_framework_unsupported` | The declared framework has no curated conventions in the catalog; `framework.md` renders the "(no curated conventions — confirm)" marker and generation continues. |
| `ui_flow_no_cross_bc_edges` | The graph has no cross-BC Policy/Event flows to sequence by; `ui-flow.md` falls back to BC insertion order (D8 step 8). |
| `ui_flow_cycle_broken` | The topological sort detected a cycle and removed a back-edge to linearise; `target` names the removed edge. |
| `ui_unreferenced_flow` | A bound UI did not participate in any flow chain; it is rendered at the tail of `ui-flow.md` with the "(unreferenced flow — review)" label. |
| `prd_split_lint_failed` | The PRD↔CLAUDE content-split lint (D9) failed; the build aborts with this code in the response. |
| `frontend_viewport_dominant` | **(2026-05-13)** A single viewport class covers ≥ 70% of the known-viewport wireframes; `target` carries `{dominant, mobile, tablet, desktop, unknown}` counts. Informational — the agent reads `framework.md` and asks the user to confirm mobile/tablet/desktop-first direction. |
| `frontend_viewport_mixed` | **(2026-05-13)** No single viewport class covers ≥ 70%; `target` carries the same counts. The agent reads `framework.md` and asks the user which viewport drives the IA. |

### 6.4 Filesystem output additions

When `include_frontend=true` AND `spec_format=ddd`:

```text
specs/frontend/                    # sibling of specs/bounded-contexts/, never nested
├── framework.md                   # FrontendCompositionProjection.framework + .framework_conventions
├── menu-structure.md              # FrontendCompositionProjection.menu (hierarchical bullet list grouped by BC)
└── ui-flow.md                     # FrontendCompositionProjection.ui_flow (numbered, causal order; .unreferenced_uis appended at the tail)
```

Plus, inside the downloaded PRD zip only (consumer-side, not under `specs/`):

```text
.claude/agents/frontend-engineer.md           # Role-based — one per project (D10)
.claude/agents/ddd-specialist.md              # Role-based — one per project (D10)
.claude/commands/generate-frontend.md         # New slash command (FR-024)
# .claude/agents/<bc_name>_agent.md           # NOT emitted (FR-023); pre-existing files trigger SkippedItem(reason="deprecated_per_bc_agent")
```

`PRD.md` and `CLAUDE.md` (or `.cursorrules`) are rebuilt per the D9 partition; both files exist inside the zip but their content shapes are disjoint (no inventory in CLAUDE; no imperatives in PRD).

### 6.5 Byte-stability extension

SC-005 / SC-010 require byte-stable output across runs against an unchanged graph. The three new frontend files honour this because:

- The topological sort tiebreaker is fully deterministic (`(bc_insertion_index, user_story_priority, user_story_insertion_index, ui_order_in_story)`) — no time, no random, no LLM in the loop.
- `framework.md`'s conventions come from a static catalog dict, not from LLM text.
- Relative path generation is deterministic given the BC/Story/UI slugs from §1 (`AggregateProjection.slug` etc.).
- **(2026-05-13)** The `## Viewport summary` block is computed from `viewport_summary` (count aggregation) + a fixed 70% threshold — same scene graphs ⇒ same counts ⇒ same dominant. Viewport tags on `ui-flow.md` / `menu-structure.md` entries are derived per-wireframe from the primary-frame width, so they are also stable.

The only volatile content is the `Generated:` timestamp line (excluded from byte-stability by FR-015, same as the v1 artifacts).
