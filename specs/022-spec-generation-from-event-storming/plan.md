# Implementation Plan: DDD Artifact Generation from Event Storming

**Branch**: `022-spec-generation-from-event-storming` | **Date**: 2026-05-13 (amended) | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/022-spec-generation-from-event-storming/spec.md`

> **2026-05-12 amendment**: The spec was extended with stories P5 (frontend framework declaration + `specs/frontend/` artifact set), P6 (PRD.md ↔ CLAUDE.md content split), and P7 (drop per-BC agents; emit role-based agents + `/generate-frontend` slash command). This plan re-baselines the backend feature module (`api/features/ddd_spec/`) and adds a thin packaging seam in `api/features/prd_generation/` to honour the new contracts. No new endpoint, no new env var, no graph mutation. See research.md D7–D10 for the new design decisions.
>
> **2026-05-13 amendment**: P5 deepens with a **viewport-intent check** (FR-025/026, research D11). `WireframeProjection`/`UIFlowEntry`/`MenuEntry` gain a `viewport_class` field; `FrontendCompositionProjection` gains `viewport_summary` + `dominant_viewport`. `framework.md` renders a `## Viewport summary` block; `ui-flow.md` / `menu-structure.md` carry per-entry `[viewport: <class>]` tags; the `frontend-engineer` agent body + `/generate-frontend` command body contain a "Viewport intent check" step that runs BEFORE IA generation and asks the user the mobile/tablet/desktop-first question. Two new warning codes: `frontend_viewport_dominant`, `frontend_viewport_mixed`. Implementation in `api/features/ddd_spec/wireframe_render.py` (`classify_viewport`, `extract_viewport_class`), `repository.py` (aggregation + threshold), `frontend_renderer.py` (warnings + framework.md context), templates (3 files), `prd_artifact_generation.py` (agent + command body). 36 new unit tests in `test_viewport_classification.py`; full suite passes 175/175. No new endpoint, no new env var, no request-body change, no graph mutation.

## Summary

Project the Neo4j event-storming graph into the "DDD for SDD" artifact set — `domain-terms.md` (Ubiquitous Language), `bc-<slug>.md` (Bounded Context Canvas), `aggregate-<slug>.md` × N (Aggregate Design Specs with invariants in EARS), `acl-<system>.md` × M (only when external integrations are modeled), `requirements.md` (User Stories + EARS acceptance criteria + UI wireframes rendered from the stored scene graph), and the system-level `context-map.md`. Output goes under `specs/bounded-contexts/<bc-slug>/` plus the single file `specs/context-map.md`, matching the article's layout. The graph stays the single source of truth; the artifacts are pure projections, regenerable at any time, byte-stable for unchanged input.

The 2026-05-12 amendment widens the scope to own the **consumer-side packaging surface** that the PRD-generation flow zips alongside the DDD artifact set, and adds the **frontend perspective**:

- A new sibling folder `specs/frontend/` containing `framework.md` (declared framework + conventions), `menu-structure.md` (BC-grouped navigation tree), and `ui-flow.md` (cross-BC causal ordering of UIs with relative links back to per-BC `requirements.assets/`). The frontend artifacts live as a sibling of `specs/bounded-contexts/`, never nested inside any BC folder.
- A `PRD.md` ↔ `CLAUDE.md` (or `.cursorrules`) **content split**: PRD is purely compositional (stack table, BC inventory, file index, deployment view); the prescriptive constitution (read-order, DDD principles, EARS translation rules, GWT-test obligations) lives only in the assistant-native file.
- **Drop per-BC agents** (`.claude/agents/<bc_name>_agent.md`). Migrate useful content into the existing skills and slash commands. Emit at most two role-based agents (`.claude/agents/frontend-engineer.md`, `.claude/agents/ddd-specialist.md`), each referencing the skills by relative path rather than restating them.
- A new slash command `.claude/commands/generate-frontend.md` that walks `specs/frontend/` + per-BC `requirements.assets/` and instructs the coding agent to produce one component per wireframe in the declared framework.

**Technical approach**: The backend feature module `api/features/ddd_spec/` remains unchanged in shape (read-only repo → projection → renderers → atomic write + lock). The **frontend perspective is a new renderer pair** inside that module — `frontend_renderer.py` (`framework.md`, `menu-structure.md`, `ui-flow.md`) — that consumes the same `BoundedContextProjection` set plus a small new `FrontendCompositionProjection` walker over the cross-BC flow edges already loaded for the Context Map (D8). The **consumer-side packaging changes** live in `api/features/prd_generation/`: (a) `prd_export.py` stops emitting per-BC `.claude/agents/<bc_name>_agent.md` files; (b) two new generator functions emit `.claude/agents/frontend-engineer.md` and `.claude/agents/ddd-specialist.md`; (c) one new generator function emits `.claude/commands/generate-frontend.md`; (d) `generate_main_prd` / `generate_claude_md` are restructured so prescriptive content moves out of PRD.md into CLAUDE.md (or `.cursorrules` for Cursor); (e) when `include_frontend=true` AND `spec_format=ddd`, the planning + zip paths additionally invoke a new `api.features.ddd_spec.inproc.render_frontend_spec_to_zip(zip_file, frontend_framework)` that materialises `specs/frontend/{framework,menu-structure,ui-flow}.md`. GWT → EARS is still a deterministic string transform; LLM use is still narrow and optional. UI wireframes are still rendered from `UI.sceneGraph` with **no Figma API and no Figma credential**. The four existing endpoints under `/api/ddd-spec` are **unchanged**; the frontend artifact materialisation is folded into the PRD-generation flow's existing `/api/prd/generate` and `/api/prd/download` endpoints because that flow already runs end-to-end and is the only place a frontend-framework declaration lives.

## Technical Context

**Language/Version**: Python 3.11+ (backend only this PR; the frontend deliverable is a *spec set the engineer reads*, not new frontend code in this repo).
**Primary Dependencies**: FastAPI (existing), Pydantic v2 (existing), Neo4j Python driver via `api/platform/neo4j.py` (existing), `httpx` (existing — `open_pencil_client`), `Jinja2` (existing — already pinned for the DDD templates), `python-slugify` (existing — added by feature 022 v1). LLM access via existing `api/features/ingestion/ingestion_llm_runtime.py`. **No new external-service credential.** **No new dependency added by the 2026-05-12 amendment.**
**Storage**: No new persistent store. Reads from Neo4j (source of truth). Writes only to the local filesystem under `specs/bounded-contexts/`, the file `specs/context-map.md`, the new sibling folder `specs/frontend/` (when `include_frontend=true`), and the consumer-side files inside the downloaded PRD zip (`PRD.md`, `CLAUDE.md` / `.cursorrules`, `Frontend-PRD.md`, `.claude/{skills,agents,commands}/*`, `.cursor/rules/*`). The graph is never mutated (FR-016). The existing `specs/NNN-*/` SpecKit folders are never touched.
**Testing**: Unit tests for (existing) slug/path allocator, GWT→EARS transform, scene-graph extractor, and (new in this amendment) the frontend renderer's UI-flow ordering algorithm (deterministic; topological sort over the cross-BC flow DAG with insertion-order fallback for islands) and the PRD↔CLAUDE content-split linter (asserts no prescriptive imperative survives in PRD.md). Integration test deferred — manual smoke per `quickstart.md` (now 10 scenarios) covers happy path and degraded paths against a real graph and a running/stopped wireframe service.
**Target Platform**: Linux/macOS host (POSIX paths). Single-tenant — concurrent generation against the same BC/Aggregate is still serialised via the existing `specs/bounded-contexts/.ddd-spec.lock`; the new `specs/frontend/*.md` materialisation reuses the same lock.
**Project Type**: Web application — backend feature module + a thin packaging hook in another backend feature. The "frontend perspective" added in this amendment is a *spec artifact* (markdown for a human/AI engineer to consume), not new frontend code in this repo's `frontend/src/...`.
**Performance Goals**: Single-BC generation < 60 s for ≤ 10 Aggregates and ≤ 30 User Stories including SVG renders (SC-001 — unchanged). Whole-model generation streams progress (SC unchanged). Frontend-spec materialisation is a few markdown files and is bounded by the time the Context Map computation already takes (it reuses the same cross-BC edge load); budget is "imperceptible" relative to BC generation, so no separate SC.
**Constraints**: Byte-stable output for unchanged input (SC-005 — extended to cover `specs/frontend/*.md` as well). No Figma API, no Figma token (FR-012). Never mutate Neo4j (FR-016). Never touch `specs/constitution.md` or `specs/NNN-*/` (FR-018). Path safety — every write target must `realpath` under `specs/` (extended to `specs/frontend/` after the amendment). Graceful degradation on every partial-data and service-unavailable case (FR-014). PRD↔CLAUDE content-split: no prescriptive imperative ("MUST", "SHALL", "Before starting") in `PRD.md`; no inventory / stack-table content in `CLAUDE.md` / `.cursorrules` (FR-022 + SC-011). Per-BC agent files are not written (FR-023); previous per-BC files in the user's working copy are surfaced under `skipped` with reason `deprecated_per_bc_agent` (edge-case spec section).
**Scale/Scope**: Designed for ~10 Aggregates and ~30 User Stories per BC and a few dozen BCs per model. The path allocator is O(existing entries under `specs/bounded-contexts/`). The new UI-flow topological sort is O(V + E) where V is the count of BC × bound-UI pairs and E is the count of cross-BC Policy/Event edges — fine at this scale.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Graph-as-Source-of-Truth** | ✅ PASS | Unchanged from v1. Generation is still a strict read-only projection from Neo4j onto the filesystem. The new `specs/frontend/*.md` files (P5) are derived from the same projection data; no new persistent store; no graph mutation (FR-016). The new role-based agents and `/generate-frontend` command (P7) are *generator output*, not graph mutations. PRD↔CLAUDE split (P6) is content relocation inside generator output. The artifacts remain regenerable at any time, by construction (FR-015, SC-005 — extended to cover `specs/frontend/`). |
| **II. Event Storming Vocabulary** | ✅ PASS | Still stronger than usual. The frontend artifacts use Event-Storming terms throughout — `ui-flow.md` orders UIs by the *Policy → Event → Command → UI* causal chain; `menu-structure.md` groups routes by Bounded Context; `framework.md` references Aggregates by name. The `/generate-frontend` slash command's body and the Frontend Engineer agent's body both speak in DDD terms (Aggregate, User Story, ReadModel) rather than in CRUD-flavoured names. |
| **III. Streaming-First UX for Long-Running Work** | ✅ PASS | Unchanged. The new frontend renderer runs inside the existing per-BC + context-map work (sub-second relative to wireframe SVG renders), so it does not introduce a new long-running endpoint. The whole-model `generate-all` SSE event vocabulary is unchanged; the new frontend artifacts are written as part of the consumer-side packaging flow (`/api/prd/download`), which is already a single-shot zip stream — the PRD-flow's existing UX is the right place for the frontend-framework declaration form, not a new SSE channel. |
| **IV. Human-in-the-Loop on Mutations** | ✅ PASS | Unchanged. Generation is purely user-triggered; the new frontend perspective is opt-in via the PRD UI's `include_frontend` toggle, gated on the user's `frontend_framework` declaration (FR-020). Output is on-disk markdown the human reviews before feeding it to downstream coding agents. The new "(inferred / not-modeled)" markers introduced by the frontend renderer for unsupported-framework conventions and unreferenced UIs are themselves human-in-the-loop checkpoints. |
| **V. Feature-Modular Architecture** | ✅ PASS (with a noted seam) | The frontend renderer lives inside `api/features/ddd_spec/` (the rendering owner); the packaging seam (per-BC agent drop, role-based agents, `/generate-frontend` command emission, PRD↔CLAUDE content rebalance, frontend-spec materialisation into the zip) lives inside `api/features/prd_generation/`. **Two sibling features cross paths**, but the crossing is the same shape as the existing one (the `spec_format=ddd` selector already lets `prd_generation` call `ddd_spec.inproc.pack_ddd_artifacts_to_zip`). The amendment extends `ddd_spec.inproc` with one new public function `render_frontend_spec_to_zip` consumed by `prd_export.py`; no direct cross-feature import of internals. The earlier note about a deferred frontend mirror under `frontend/src/features/dddSpec/` *still applies* — it is unrelated to the frontend *spec set* this amendment adds. Recorded under Complexity Tracking. |
| **VI. Provider-Agnostic LLM Runtime** | ✅ PASS | Unchanged. LLM use is still narrow (EARS smoothing, Aliases-to-AVOID suggestions, optional Context-Map pattern inference). The frontend renderer adds **no LLM call** — UI-flow ordering is a deterministic topological sort over modeled flow edges; framework conventions come from the static catalog already in `prd_generation`. |
| **VII. Observable by Default** | ✅ PASS | Unchanged. The frontend renderer reuses the same correlation-id middleware. New `SmartLogger` events at the seam: `frontend_spec_render_started`, `ui_flow_sequenced` (with edge count + island count), `frontend_spec_files_written`, plus `frontend_framework_unsupported_warning` and `ui_unreferenced_flow_warning`. The PRD↔CLAUDE split adds `prd_split_lint_passed` and (on failure) `prd_split_lint_failed` with the offending substring for triage. |

**Gate result**: PASS. The deferred frontend *mirror* (Vue components calling these endpoints) remains in Complexity Tracking. The cross-feature seam between `ddd_spec` and `prd_generation` is added explicitly and justified (single public function, same shape as the existing seam). Two minor justified deviations from the source article (BC-level `requirements.md`; heuristic relationship patterns) are preserved from v1.

## Project Structure

### Documentation (this feature)

```text
specs/022-spec-generation-from-event-storming/
├── spec.md              # Feature spec (DDD artifact generation + P5–P7 frontend perspective; authored via /speckit-specify)
├── plan.md              # This file
├── research.md          # Phase 0: D1–D6 (v1) + D7–D10 (2026-05-12) + D11 (2026-05-13 viewport classification + dominant-viewport agent prompt)
├── data-model.md        # Pydantic shapes (request/response + internal projection + SSE events) + §6 frontend additions (incl. 2026-05-13 viewport fields)
├── quickstart.md        # 12 manual smoke scenarios (7 original + S8–S10 frontend + S11–S12 viewport intent)
├── contracts/
│   └── rest-api.md      # /api/ddd-spec endpoints (unchanged) + /api/prd/* contract additions for frontend_framework + consumer-side file contract
├── checklists/
│   └── requirements.md  # /speckit-specify quality checklist (PASS, re-validated 2026-05-12)
└── tasks.md             # /speckit-tasks output (NOT created here; will need regeneration to cover FR-020 through FR-024)
```

### Source Code (repository root)

```text
api/features/ddd_spec/                         # Backend feature module — v1 stays; new files marked NEW
├── __init__.py
├── router.py                                  # /api/ddd-spec endpoints — UNCHANGED
├── schemas.py                                 # Pydantic request/response/SSE models — UNCHANGED
├── service.py                                 # Orchestration — UNCHANGED
├── repository.py                              # Read-only Neo4j Cypher — UNCHANGED (already loads cross-BC flow edges for the Context Map)
├── projection.py                              # Internal projection types — EXTEND with FrontendCompositionProjection (D7, data-model.md §6.1)
├── paths.py                                   # Slug + path resolution + lock — EXTEND to whitelist specs/frontend/ as a valid write root
├── ears.py                                    # GWT→EARS transform — UNCHANGED
├── wireframe_render.py                        # scene-graph → element tree + optional SVG — UNCHANGED
├── llm_assist.py                              # Optional LLM passes — UNCHANGED (frontend renderer adds no LLM use)
├── frontend_renderer.py                       # NEW — emits specs/frontend/{framework,menu-structure,ui-flow}.md from FrontendCompositionProjection (D7, D8)
├── inproc.py                                  # In-process helpers consumed by prd_generation — EXTEND with render_frontend_spec_to_zip(zip_file, framework, bcs) and planned_paths_for_preview() updates
├── renderers/
│   ├── __init__.py
│   ├── domain_terms.py                        # UNCHANGED
│   ├── bc_canvas.py                           # UNCHANGED
│   ├── aggregate_spec.py                      # UNCHANGED
│   ├── acl_spec.py                            # UNCHANGED
│   ├── requirements_md.py                     # UNCHANGED
│   └── context_map.py                         # UNCHANGED (its cross-BC edge loader is reused by frontend_renderer)
├── templates/                                 # Jinja2 templates
│   ├── domain-terms.md.j2                     # UNCHANGED
│   ├── bc-canvas.md.j2                        # UNCHANGED
│   ├── aggregate-spec.md.j2                   # UNCHANGED
│   ├── acl-spec.md.j2                         # UNCHANGED
│   ├── requirements.md.j2                     # UNCHANGED
│   ├── context-map.md.j2                      # UNCHANGED
│   ├── frontend-framework.md.j2               # NEW
│   ├── frontend-menu.md.j2                    # NEW
│   └── frontend-ui-flow.md.j2                 # NEW
└── tests/                                     # Existing unit tests + NEW tests for UI-flow ordering and the frontend renderer

api/features/prd_generation/                    # Packaging seam — files marked MODIFY / NEW
├── prd_api_contracts.py                       # MODIFY — add Svelte to FrontendFramework enum (Vue, React, Svelte minimum) per spec P5
├── prd_artifact_generation.py                 # MODIFY — split generate_main_prd: PRD.md keeps composition only (FR-022). Move constitution-like prose into generate_claude_md (Claude) / generate_cursor_rules (Cursor). Delete generate_agent_config (per-BC). ADD generate_role_agent_frontend_engineer, generate_role_agent_ddd_specialist, generate_claude_command_generate_frontend.
├── prd_model_data.py                          # UNCHANGED (read-side helpers)
├── prd_tech_stack_catalog.py                  # MODIFY — register Svelte conventions stub (D7)
├── router.py                                  # UNCHANGED
└── routes/
    ├── prd_export.py                          # MODIFY — when include_frontend=true require frontend_framework (FR-020 — 400 if missing); when spec_format=ddd AND include_frontend=true call ddd_spec.inproc.render_frontend_spec_to_zip; emit role-based agents (FR-023) instead of per-BC agents; emit /generate-frontend command (FR-024); stop calling generate_agent_config for each BC.
    └── tech_stacks.py                         # UNCHANGED

api/main.py                                    # UNCHANGED — no new router registered (the frontend perspective rides on existing /api/prd/* and /api/ddd-spec/* endpoints)

# NOT touched: api/features/figma_binding/* (unchanged), .env.example (no new var), api/platform/open_pencil_client.py (called, not modified),
#              specs/constitution.md (never generated), specs/NNN-*/ (read-only — including this very feature's own files outside /spec.md, /plan.md, etc. authored via SpecKit).

# Frontend mirror — STILL DEFERRED to a follow-up PR per the Constitution Check note.
# The user's "frontend perspective" added in this amendment is a *spec set the engineer reads*,
# not new Vue/React/Svelte code in this repo's frontend/src/. The canvas/inspector buttons that
# would call /api/ddd-spec/* endpoints from frontend/src/features/dddSpec/ remain deferred.
```

**Structure Decision**: Keep the `api/features/ddd_spec/` module as the rendering owner; add **one new public function** (`render_frontend_spec_to_zip`) at the module boundary so `api/features/prd_generation/routes/prd_export.py` can consume it. This mirrors the existing `pack_ddd_artifacts_to_zip` seam — same shape, same direction, same Constitution V escape hatch. The PRD↔CLAUDE content split is a local refactor inside `prd_artifact_generation.py` (no new module). The per-BC agent removal is a deletion of one function plus the two call sites in `prd_export.py`. The role-based agents and `/generate-frontend` command are three new generator functions co-located with the existing skill/command generators in `prd_artifact_generation.py`. The Jinja2 templates for the three frontend `.md` files are vendored alongside the existing DDD templates so the renderer set is internally consistent.

## Complexity Tracking

> Filled because Constitution Check has one explicitly-deferred item, one feature-crossing seam, plus two justified deviations from the source article preserved from v1.

| Item | Why | Simpler/strict alternative rejected because |
|------|-----|----------------------------------------------|
| Frontend mirror (canvas/inspector buttons calling /api/ddd-spec/*) not delivered in this PR | Same justification as v1 — backend-first; UI follow-up committed-to in the spec. The 2026-05-12 amendment does **not** change this: the "frontend perspective" added here is a *spec set for the downstream coding agent to consume*, not new Vue code in this repo. | Bundling canvas/inspector UI here roughly doubles scope without changing capability; the UI cannot land before the backend exists. Follow-up PR is still committed-to. |
| Cross-feature seam: `ddd_spec.inproc` exposes one new function consumed by `prd_generation.routes.prd_export` (`render_frontend_spec_to_zip`); `prd_generation` also takes the per-BC agent drop + PRD↔CLAUDE split + role-based agent emission + `/generate-frontend` command emission | The PRD-generation flow is the only place a `frontend_framework` declaration lives (the form is in its UI). It already produces the downloaded zip that the consumer engineer extracts. Materialising `specs/frontend/*.md` into that zip is one extra call at the same seam (`pack_ddd_artifacts_to_zip` already exists). Splitting this into a separate `/api/ddd-spec/generate-frontend` endpoint would mean two zips and a second user step — strictly worse UX. | Owning the frontend renderer in `ddd_spec` keeps rendering logic together; owning the packaging in `prd_generation` keeps the user-facing form and zip together. The crossing is exactly one public function, same direction as the existing seam. A third top-level feature module would just refactor the crossing without removing it. |
| Per-BC `.claude/agents/<bc_name>_agent.md` files removed | FR-023. The previous output created N copies of essentially the same skill-reference list and imposed a sandboxing model ("agent X only touches BC X") that the codebase does not enforce. Collapsing to role-based agents + skills + commands is the lighter primitive. | Keeping per-BC agents alongside role-based ones would double the agent file count and make it ambiguous which agent a coding session should adopt. Useful content (skills lists, scope statements) is migrated into skills/commands (FR-023, edge case + acceptance scenario 4 of P7); nothing is lost. |
| `requirements.md` is generated **per Bounded Context**, not "per feature" | Preserved from v1 — our graph has no "feature" node to slice on. BC-level `requirements.md` (stories grouped by Aggregate) is faithful to the data. | Inventing a feature-grouping that doesn't exist in the model is guessing; the article itself flags this as human-authored. |
| Context-Map relationship patterns are **inferred heuristically** and marked "(inferred — confirm)" | Preserved from v1 — graph doesn't record DDD patterns today; the article treats them as human-reviewed. | Refusing to emit until patterns are modeled would block a useful scaffold indefinitely. |
| `acl-*.md` files produced **only when** external integrations are modeled | Preserved from v1 — zero files is the correct output when nothing is modeled. | Emitting stub ACL files would be noise; refusing the BC folder would be wrong (ACLs aren't missing, they're not applicable). |
