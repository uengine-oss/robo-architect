---

description: "Task list for DDD Artifact Generation from Event Storming"
---

# Tasks: DDD Artifact Generation from Event Storming

**Input**: Design documents from `/specs/022-spec-generation-from-event-storming/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/rest-api.md, quickstart.md

**Tests**: Unit tests are included where `plan.md` explicitly calls for them (slug/path/lock allocator, GWT→EARS transform, scene-graph element-tree extractor, renderer section-mapping helpers, context-map heuristics). A feature-level integration harness is out of scope per `plan.md`; end-to-end verification is the manual `quickstart.md` smoke (S1–S7). No TDD ordering is mandated — unit tests sit in their story phase alongside the code they cover.

**Organization**: Tasks are grouped by user story. US1 is the MVP; US2 is independent of US1; US3 reuses the Aggregate Spec renderer built in US1; US4 composes US1 + US2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: `[US1]`–`[US4]` for user-story phase tasks only (Setup/Foundational/Polish carry no story label)
- Every task names exact file paths.

## Path Conventions

Web-app backend layout from `plan.md`: the new feature module lives at `api/features/ddd_spec/`; co-located unit tests at `api/features/ddd_spec/tests/`. Generated artifact output (created at runtime, not by these tasks): `specs/bounded-contexts/<bc-slug>/...` and `specs/context-map.md`. Frontend is deferred to a follow-up PR. `api/main.py` is modified to register the router. No new env var; `WIREFRAME_SERVICE_URL` (existing) is the only external-service config touched.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the module skeleton and pull in dependencies.

- [X] T001 Create the `api/features/ddd_spec/` module skeleton: `api/features/ddd_spec/__init__.py`, `api/features/ddd_spec/renderers/__init__.py`, `api/features/ddd_spec/tests/__init__.py`, and an empty `api/features/ddd_spec/templates/` directory.
- [X] T002 Add `python-slugify` to the Python dependencies (`requirements.txt` and the `uv`/`pyproject` config) and pin `Jinja2` explicitly; run `uv sync` (or `pip install -r requirements.txt`) to confirm the install resolves.
- [X] T003 [P] Add the six Jinja2 templates mirroring the "DDD for SDD" article formats, with section anchors and `{% for %}`/`{% if %}` placeholders, under `api/features/ddd_spec/templates/`: `domain-terms.md.j2`, `bc-canvas.md.j2`, `aggregate-spec.md.j2`, `acl-spec.md.j2`, `requirements.md.j2`, `context-map.md.j2`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schemas, projection types, the read-only repository, and the deterministic building blocks (paths/lock, EARS, wireframe extractor, LLM helpers, logging scaffold) that every user story needs.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Define all Pydantic request/response/SSE-event models in `api/features/ddd_spec/schemas.py` per `data-model.md` §2–§3 (`GenerateBoundedContextRequest`, `GenerateAggregateRequest`, `GenerateContextMapRequest`, `GenerateAllRequest`, `ArtifactFileInfo`, `SkippedItem`, `GenerationWarning`, `GenerationResult`, and the SSE event payload shapes).
- [X] T005 [P] Define the internal read-side projection types in `api/features/ddd_spec/projection.py` per `data-model.md` §1 (`BoundedContextProjection`, `StrategicClassification`, `AggregateProjection`, `AggregateAttribute`, `MemberEntity`, `CommandProjection`, `GwtCriterion`, `EventProjection`, `PolicyProjection`, `ReadModelProjection`, `UserStoryProjection`, `WireframeProjection`, `ExternalIntegrationProjection`, `CrossBcFlow`).
- [X] T006 Implement the read-only Neo4j repository in `api/features/ddd_spec/repository.py` using the existing `api/platform/neo4j.py` driver: `load_bounded_context(bc_id) -> BoundedContextProjection`, `load_aggregate(agg_id) -> tuple[BoundedContextProjection, AggregateProjection]`, `load_all_bounded_contexts() -> list[BoundedContextProjection]`, `load_cross_bc_flows() -> list[CrossBcFlow]`. Deliberately do NOT read `UI.figmaFileKey`/`UI.figmaNodeId`. No graph mutation anywhere.
- [X] T007 [P] Implement slug derivation, output-path resolution, the atomic-create file lock, and stale-asset detection in `api/features/ddd_spec/paths.py` per research D5: `python-slugify` with hash-suffix fallback; `realpath` sandbox assertion that every write target is under `specs/`; `fcntl.flock` on `specs/bounded-contexts/.ddd-spec.lock`; staging-directory + `os.replace` write helper; "files under `requirements.assets/` not referenced by the new `requirements.md`" detector.
- [X] T008 [P] Implement the deterministic GWT→EARS transform in `api/features/ddd_spec/ears.py` per research D3: `Given X, When Y, Then Z` → `WHEN Y IF X THEN system SHALL Z`; no-Given → `WHEN Y THEN system SHALL Z`; unconditional invariant `C` → `THE <Aggregate> SHALL <C>`; multi-Given joined with `AND`; multi-Then → one `SHALL` line each; numbered output; expose a hook for optional grammar smoothing that preserves all load-bearing tokens.
- [X] T009 [P] Implement wireframe rendering in `api/features/ddd_spec/wireframe_render.py`: (a) deterministic walk over the open-pencil `SerializedSceneGraph` JSON producing a nested textual element tree (containers with layout role; text nodes with content; buttons/inputs/links with labels/placeholders); (b) writer for the raw `sceneGraph` JSON sidecar; (c) best-effort SVG via `api/platform/open_pencil_client` — if the service has no scene-graph→SVG route, is unreachable, or times out, return `None` plus a `wireframe_service_unavailable`/`svg_render_failed` warning rather than raising. No Figma call anywhere.
- [X] T010 [P] Implement the narrow optional LLM helpers in `api/features/ddd_spec/llm_assist.py` via `api/features/ingestion/ingestion_llm_runtime.py`: `smooth_ears(lines)`, `suggest_aliases_to_avoid(term, context)`, `infer_relationship_pattern(flow, bc_descriptions)`. Each must degrade to a deterministic passthrough (or "omit") plus an `llm_unavailable`/`aliases_to_avoid_unavailable` warning when the LLM runtime is not configured. No direct `openai`/`anthropic`/`google.*` imports.
- [X] T011 Implement the shared service scaffolding in `api/features/ddd_spec/service.py`: a `GenerationContext` that owns the correlation id, the `SmartLogger` instance, the warning accumulator, and the `created`/`skipped` accumulators; helpers to emit the documented phase-boundary log events (`generation_started`, `bc_subgraph_loaded`, `wireframe_rendered`, `templates_rendered`, `files_written`, `warning`, `generation_completed`, `generation_failed`) and to assemble a `GenerationResult`.
- [X] T012 Add `api/features/ddd_spec/router.py` with an `APIRouter(prefix="/api/ddd-spec")` (no endpoints yet) and register it in `api/main.py` alongside the other feature routers; confirm `/docs` shows an empty "ddd-spec" tag and the app still starts with no new env var demanded.

**Checkpoint**: Foundation ready — user story implementation can begin.

---

## Phase 3: User Story 1 — Generate the full DDD artifact set for one Bounded Context (Priority: P1) 🎯 MVP

**Goal**: `POST /api/ddd-spec/generate-bounded-context` writes `specs/bounded-contexts/<bc-slug>/` with `domain-terms.md`, `bc-<slug>.md`, one `aggregates/aggregate-<slug>.md` per Aggregate, `requirements.md` (+ `requirements.assets/*.scene.json`, best-effort `*.svg`), and `acl-<slug>.md` per modeled external integration — all projected from the event-storming graph, with EARS invariants/criteria and scene-graph-rendered wireframes, no Figma access.

**Independent Test**: Pick a fully-populated BC, call the endpoint, and verify every Aggregate/Command/Event/ReadModel/User Story in the graph appears in the right artifact; GWT shows up as EARS lines in both the Aggregate Spec and `requirements.md`; each bound wireframe yields a textual element tree + `.scene.json`; no request hit `api.figma.com`. (quickstart S1–S3)

### Tests for User Story 1

- [X] T013 [P] [US1] Unit tests for the GWT→EARS transform in `api/features/ddd_spec/tests/test_ears.py` (all four mapping cases, multi-Given/multi-Then, numbering, token-preservation under smoothing).
- [X] T014 [P] [US1] Unit tests for slug/path/lock/stale-asset in `api/features/ddd_spec/tests/test_paths.py` (Korean→ASCII slug, empty/collision hash fallback, `realpath` sandbox rejection, `os.replace` atomicity, stale-asset detection).
- [X] T015 [P] [US1] Unit tests for the scene-graph element-tree extractor in `api/features/ddd_spec/tests/test_wireframe_render.py` (containers/text/interactive elements; empty/missing scene graph; SVG-fallback returns `None`+warning when the service is stubbed unavailable).

### Implementation for User Story 1

- [X] T016 [P] [US1] Implement `api/features/ddd_spec/renderers/domain_terms.py` → `domain-terms.md`: one `## Term:` block per Aggregate, Command, Event, ReadModel, and key Property in the BC, each with **Definition / Business Context / Related Terms / Aliases to AVOID**; honor the `aliases_to_avoid` mode (`"omit"` vs `"suggest"`-and-mark via `llm_assist`), emitting `aliases_to_avoid_unavailable` when suggestion falls back.
- [X] T017 [P] [US1] Implement `api/features/ddd_spec/renderers/bc_canvas.py` → `bc-<bc-slug>.md`: Purpose, Strategic Classification (Domain/Business model/Evolution), Inbound Communication table (From context | Channel | Message type | Pattern), Outbound Communication table, Ubiquitous Language summary (pointer to `domain-terms.md` + key terms), Business Decisions, Assumptions; render "(not modeled — confirm)" markers and emit `bc_purpose_missing`/`bc_not_classified` warnings where data is absent; note when no external integrations are modeled (`no_external_integrations`).
- [X] T018 [P] [US1] Implement `api/features/ddd_spec/renderers/aggregate_spec.py` → `aggregates/aggregate-<agg-slug>.md`: Description, Aggregate Root, Member Entities & Value Objects, Properties table (Field | Type | Mutability), Enforced Invariants (numbered EARS via `ears.py`, including unconditional invariants), Corrective Policies (eventual consistency, from the Aggregate's Policies), Commands table (Command | Preconditions | Postconditions | Events emitted), Domain Events Emitted, Repository Interface stub derived from the identity type and Commands; flag GWT-less Commands in an "Open Decisions" note and emit `command_missing_gwt`.
- [X] T019 [P] [US1] Implement `api/features/ddd_spec/renderers/acl_spec.py` → `acl-<external-slug>.md`: Purpose, Boundary (Inside our domain / Outside), Translation Map (inbound), Translation Map (outbound), Error Translation, Idempotency, Forbidden Concepts; produced only when `ExternalIntegrationProjection` entries exist, marking unmodeled sub-tables "(to be defined)".
- [X] T020 [US1] Implement `api/features/ddd_spec/renderers/requirements_md.py` → `requirements.md` plus `requirements.assets/<userStoryId>-<ui-slug>.scene.json` (always) and `...svg` (best-effort): User Stories grouped by Aggregate in priority order (insertion order when no priority), each with narrative, Acceptance Criteria as EARS lines (via `ears.py`), and a wireframe section per bound `UI` node (textual element tree + `.scene.json` link + embedded `<img>` of the `.svg` when one was produced). Depends on T008, T009.
- [X] T021 [US1] Implement `service.generate_bounded_context(req)` in `api/features/ddd_spec/service.py`: validate (empty BC → `empty_bounded_context`/400), acquire the lock (`lock_busy`/409), load the subgraph via `repository.load_bounded_context` (T006), render every artifact to a staging dir (T016–T020), refuse-or-replace per `overwrite` and record `skipped`/`stale_asset`, `os.replace` into `specs/bounded-contexts/<bc-slug>/`, emit phase logs, return `GenerationResult`. Depends on T006, T007, T011, T016–T020.
- [X] T022 [US1] Implement `POST /api/ddd-spec/generate-bounded-context` in `api/features/ddd_spec/router.py`: bind `GenerateBoundedContextRequest`, call `service.generate_bounded_context`, map outcomes to `200` (created or skipped), `400` (`empty_bounded_context`), `404` (`bounded_context_not_found`), `409` (`lock_busy`), `500` (incl. `path_escape`); include `correlation_id` in every body.
- [X] T023 [US1] Run quickstart scenarios S1 (single-BC full set), S2 (EARS fidelity, incl. `smooth_ears:false` byte-stable rerun), and S3 (scene-graph render, confirm zero outbound Figma requests); fix any gaps found.

**Checkpoint**: User Story 1 is fully functional and independently testable — the MVP.

---

## Phase 4: User Story 2 — Regenerate the system-wide Context Map (Priority: P2)

**Goal**: `POST /api/ddd-spec/generate-context-map` writes `specs/context-map.md` — a Mermaid `graph LR` of all BCs and their cross-BC flows, plus a Relationships section per edge with Pattern/Direction/Translation·Reason/Spec-file, heuristically inferring patterns the graph doesn't record and marking each "(inferred — confirm)".

**Independent Test**: With ≥2 BCs and ≥1 cross-BC flow, call the endpoint and verify `specs/context-map.md` has a syntactically valid Mermaid diagram listing every BC, one Relationships block per edge, and inferred patterns flagged + warned. (quickstart S4)

### Tests for User Story 2

- [X] T024 [P] [US2] Unit tests for the context-map relationship-pattern heuristics in `api/features/ddd_spec/tests/test_context_map.py` (Customer-Supplier default, Conformist+ACL when a translation layer is modeled, OHS+Published-Language on high fan-out, ACL to external, "(inferred — confirm)" marking and `relationship_pattern_inferred` warning).

### Implementation for User Story 2

- [X] T025 [P] [US2] Implement `api/features/ddd_spec/renderers/context_map.py` → `specs/context-map.md`: build nodes from BCs and edges from `CrossBcFlow`s; render the ```` ```mermaid ```` `graph LR`; render `### <Upstream> → <Downstream>` blocks with **Pattern** (recorded or heuristically inferred per D6, with optional `llm_assist.infer_relationship_pattern` when requested), **Direction**, **Translation**/**Reason**, **Spec file** (the relevant `acl-*.md` or the downstream `bc-<slug>.md`); single-BC → empty Relationships section with an explanatory note.
- [X] T026 [US2] Implement `service.generate_context_map(req)` in `api/features/ddd_spec/service.py`: load all BCs + flows (T006), `no_bounded_contexts` → 400, acquire lock, render via T025, refuse-or-replace `specs/context-map.md` per `overwrite`, emit `relationship_pattern_inferred` warnings, return `GenerationResult`. Depends on T006, T007, T011, T025.
- [X] T027 [US2] Implement `POST /api/ddd-spec/generate-context-map` in `api/features/ddd_spec/router.py`: bind `GenerateContextMapRequest`, call the service, map to `200` (created/skipped), `400` (`no_bounded_contexts`), `409` (`lock_busy`), `500`.
- [X] T028 [US2] Run quickstart S4 (valid Mermaid, every cross-BC flow has a block, inferred patterns marked + warned); fix any gaps.

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 — Refresh a single Aggregate Design Spec (Priority: P3)

**Goal**: `POST /api/ddd-spec/generate-aggregate` rewrites only `specs/bounded-contexts/<bc-slug>/aggregates/aggregate-<slug>.md` for one Aggregate, leaving every sibling artifact untouched.

**Independent Test**: Generate a BC folder, modify one Aggregate in the graph, call the endpoint, and verify only that one Aggregate Spec file changed (and reflects the new state); `domain-terms.md`, `bc-<slug>.md`, `requirements.md`, and the other aggregate specs are byte-unchanged. (quickstart S5)

### Implementation for User Story 3

- [X] T029 [US3] Implement `service.generate_aggregate(req)` in `api/features/ddd_spec/service.py`: load the single Aggregate and its owning BC via `repository.load_aggregate` (T006), `aggregate_not_found` → 404, acquire lock, render only `aggregate-<slug>.md` via `renderers/aggregate_spec.py` (T018), create the parent `aggregates/` dir (and BC dir) if absent without touching siblings, refuse-or-replace per `overwrite`, return `GenerationResult` with the single `aggregate_spec` entry. Depends on T006, T007, T011, T018.
- [X] T030 [US3] Implement `POST /api/ddd-spec/generate-aggregate` in `api/features/ddd_spec/router.py`: bind `GenerateAggregateRequest`, call the service, map to `200` (created/skipped), `404` (`aggregate_not_found`), `409` (`lock_busy`), `500`.
- [X] T031 [US3] Run quickstart S5 (only the one aggregate file changes; siblings byte-unchanged); fix any gaps.

**Checkpoint**: User Stories 1–3 are all independently functional.

---

## Phase 6: User Story 4 — Bootstrap DDD artifacts for the whole model (Priority: P4)

**Goal**: `POST /api/ddd-spec/generate-all` (SSE) regenerates `specs/context-map.md` and every Bounded Context's full artifact folder, streaming progress (`phase`, `bc_started`, `wireframe_rendered`, `bc_completed`/`bc_failed`, `warning`, terminal `complete`/`error`), best-effort per BC, skipping existing folders unless `overwrite`.

**Independent Test**: With N BCs, call the endpoint and verify a well-formed SSE trace, N BC folders + `specs/context-map.md`, a `complete` summary listing everything, existing folders reported in `skipped` when `overwrite` is omitted, and a BC whose wireframe SVG fails still gets its textual artifacts + `.scene.json` with a warning. (quickstart S6–S7)

### Implementation for User Story 4

- [X] T032 [US4] Implement `service.generate_all(req)` as an async generator in `api/features/ddd_spec/service.py`: emit `phase: loading_model`; `no_bounded_contexts` → terminal `error`; emit `phase: context_map` and regenerate the context map via `generate_context_map` internals (forwarding `relationship_pattern_inferred` warnings); emit `phase: bounded_contexts`; for each BC, emit `bc_started`, run the `generate_bounded_context` pipeline (forwarding `wireframe_rendered`/`warning` events and per-BC `skipped` on existing+`overwrite=false`), emit `bc_completed` or — on failure — `bc_failed` and continue; emit terminal `complete` with the aggregated `GenerationResult`. Hold the lock per critical section, not for the whole stream. Depends on T021, T026.
- [X] T033 [US4] Implement `POST /api/ddd-spec/generate-all` in `api/features/ddd_spec/router.py` as a `text/event-stream` response that drains the `service.generate_all` async generator into SSE `event:`/`data:` lines, closing after `complete` or `error`.
- [X] T034 [US4] Run quickstart S6 (SSE trace, conflict-reported-not-clobbered, overwrite regenerates + flags stale assets) and S7 (wireframe service down → textual artifacts + `.scene.json` still produced, SVGs omitted + warned); fix any gaps.

**Checkpoint**: All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T035 [P] Unit tests for the renderer section-mapping helpers (`domain_terms`, `bc_canvas`, `aggregate_spec`, `acl_spec`, `requirements_md`) in `api/features/ddd_spec/tests/test_renderers.py` — fixture projections in → expected markdown sections out, including all "(not modeled — confirm)"/"Open Decisions" branches.
- [X] T036 [P] Update the README API-summary section (and confirm Swagger `/docs`) to list the new `/api/ddd-spec` prefix and its four endpoints; note in `docs/` that DDD artifacts are generated under `specs/bounded-contexts/` (distinct from the `specs/NNN-*/` SpecKit folders).
- [X] T037 Add a static guard test in `api/features/ddd_spec/tests/test_module_boundaries.py`: no direct `openai`/`anthropic`/`google.*` imports anywhere under `api/features/ddd_spec/` (Principle VI), and no imports from sibling `api/features/*` modules except via `api/platform/*` (Principle V).
- [X] T038 Add a determinism test in `api/features/ddd_spec/tests/test_determinism.py`: generating the same BC twice with `smooth_ears=false` against an unchanged graph fixture produces byte-identical `.md` files (excluding the `Generated:` timestamp line) — SC-005.
- [X] T039 Run the full `quickstart.md` end-to-end (S1–S7 plus the non-regression checklist — ingestion SSE, figma_binding WS, claude_code `/tree`, `/docs`, `specs/NNN-*/` and `specs/constitution.md` untouched) and fix anything that surfaces.
- [X] T040 Confirm `plan.md`'s Complexity Tracking is accurate post-implementation (frontend mirror still deferred; `requirements.md` per-BC; heuristic relationship patterns; ACL-only-when-modeled) and open a follow-up issue for the deferred frontend module `frontend/src/features/dddSpec/`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories**.
- **US1 (Phase 3)**: depends on all of Phase 2. This is the MVP.
- **US2 (Phase 4)**: depends on Phase 2 only — independent of US1; can run in parallel with US1 once Phase 2 is done.
- **US3 (Phase 5)**: depends on Phase 2 + T018 (the Aggregate Spec renderer, built in US1's phase). Sequence US3 after T018 lands; otherwise independent of the rest of US1.
- **US4 (Phase 6)**: depends on T021 (US1's `generate_bounded_context`) and T026 (US2's `generate_context_map`) — sequence after US1 and US2.
- **Polish (Phase 7)**: depends on all user stories being complete.

### Within Each User Story

- Renderers (`renderers/*.py`) before the service method that composes them, before the router endpoint that calls the service, before the manual quickstart verification task.
- `requirements_md.py` (T020) depends on `ears.py` (T008) and `wireframe_render.py` (T009).
- Unit tests for a story's building blocks can be written in parallel with — or before — the building blocks; no strict TDD ordering is mandated.

### Parallel Opportunities

- Phase 1: T003 is `[P]` (independent of T001/T002 once the dir exists — pair it after T001).
- Phase 2: T005, T007, T008, T009, T010 are all `[P]` (separate files, only depend on Setup); T004 and T006 are sequential-ish (repository may reference schema/projection shapes); T011 and T012 after T004.
- Phase 3: the three unit-test tasks (T013–T015) are `[P]`; the four leaf renderers (T016, T017, T018, T019) are `[P]` with each other; T020 then T021 then T022 then T023 are sequential.
- Phase 4: T024 `[P]`; T025 then T026 then T027 then T028 sequential.
- Across stories: once Phase 2 completes, US1 and US2 can be developed in parallel by different people; US3 joins after T018; US4 joins after T021 + T026.
- Phase 7: T035, T036, T037 (and T038's test file) are `[P]` with each other.

---

## Parallel Example: User Story 1

```bash
# After Phase 2, launch US1's unit tests together:
Task: "Unit tests for GWT→EARS in api/features/ddd_spec/tests/test_ears.py"
Task: "Unit tests for slug/path/lock in api/features/ddd_spec/tests/test_paths.py"
Task: "Unit tests for scene-graph extractor in api/features/ddd_spec/tests/test_wireframe_render.py"

# Launch the four leaf renderers together:
Task: "renderers/domain_terms.py → domain-terms.md"
Task: "renderers/bc_canvas.py → bc-<slug>.md"
Task: "renderers/aggregate_spec.py → aggregates/aggregate-<slug>.md"
Task: "renderers/acl_spec.py → acl-<external-slug>.md"
# Then T020 (requirements_md.py) → T021 (service) → T022 (endpoint) → T023 (quickstart S1–S3)
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup.
2. Phase 2: Foundational (blocks everything).
3. Phase 3: US1 — `generate-bounded-context`.
4. **STOP and VALIDATE**: run quickstart S1–S3; confirm zero Figma calls; confirm the artifact set matches the "DDD for SDD" formats.
5. Demo / use it to bootstrap one real BC's artifact folder.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → quickstart S1–S3 → demo (MVP: one BC's full DDD artifact set).
3. US2 → quickstart S4 → demo (system-wide Context Map).
4. US3 → quickstart S5 → demo (single Aggregate Spec refresh).
5. US4 → quickstart S6–S7 → demo (whole-model bootstrap with streamed progress).
6. Polish (Phase 7): renderer/boundary/determinism tests, README/Swagger, full quickstart + non-regression, frontend follow-up issue.

### Parallel Team Strategy

After Phase 2: Developer A on US1, Developer B on US2 (independent). Once T018 lands, Developer C can take US3. US4 is picked up after US1 + US2 land. Polish is shared.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- `[USn]` labels map tasks to spec.md user stories for traceability.
- This feature writes only under `specs/bounded-contexts/` and the single file `specs/context-map.md`; it never touches `specs/NNN-*/` or `specs/constitution.md`, and never mutates Neo4j, and never calls a Figma API.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
- Avoid: vague tasks, two tasks editing the same file in parallel, cross-story dependencies beyond the ones noted above.

---

# 2026-05-12 Amendment — Tasks for Stories P5–P7

The 2026-05-12 spec amendment adds three user stories (P5–P7) that extend the consumer-side packaging surface and add the frontend perspective. Tasks T001–T040 are unchanged (US1–US4 + initial Polish, all completed). New phases continue with T041+.

**Tests for the amendment**: Unit tests are included where `plan.md` (2026-05-12) explicitly calls for them — the UI-flow topological sort (deterministic tiebreaker), the menu builder grouping, the PRD↔CLAUDE split lint, and the framework-conventions catalog dispatch. End-to-end verification is the manual `quickstart.md` smoke S8–S10 added in the same amendment.

**Cross-feature seam reminder**: The amendment renderers live in `api/features/ddd_spec/` (`frontend_renderer.py`, new templates, an extended `inproc.py`); the packaging changes live in `api/features/prd_generation/` (`prd_api_contracts.py`, `prd_artifact_generation.py`, `prd_tech_stack_catalog.py`, `routes/prd_export.py`). The seam is exactly one new public function `api.features.ddd_spec.inproc.render_frontend_spec_to_zip` consumed by `prd_export.py` — mirrors the existing `pack_ddd_artifacts_to_zip` shape.

### Path Conventions (amendment)

The earlier note "Frontend is deferred to a follow-up PR" applies only to the *frontend canvas/inspector mirror* (Vue components at `frontend/src/features/dddSpec/` that call `/api/ddd-spec/*` from the canvas UI), which remains deferred. The "frontend perspective" added in this amendment is a *spec set* the downstream coding agent consumes — written by the backend into `specs/frontend/` (sibling of `specs/bounded-contexts/`, never nested) and into the PRD-generation zip's consumer-side files (`.claude/agents/{frontend-engineer,ddd-specialist}.md`, `.claude/commands/generate-frontend.md`). No new endpoint; the new files ride on `/api/prd/generate` (plan) and `/api/prd/download` (zip).

---

## Phase 8: User Story 5 — Declare the frontend framework and generate `specs/frontend/` (Priority: P5)

**Goal**: When the user toggles `include_frontend=true` in the PRD-generation UI and declares a frontend framework (Vue / React / Svelte / …), the system (a) refuses the request with `frontend_framework_required` (400) if the framework is missing, and (b) on success, materialises `specs/frontend/framework.md`, `specs/frontend/menu-structure.md`, and `specs/frontend/ui-flow.md` into the downloaded zip. `ui-flow.md`'s ordering is the deterministic causal sort over the cross-BC Policy/Event chain (D8); `menu-structure.md` groups routes by BC; `framework.md` records the chosen framework and its conventions from the catalog.

**Independent Test**: From the PRD UI, attempt generation with `include_frontend=true` and no framework — expect HTTP 400. Pick Vue, re-run — the zip carries the three `specs/frontend/*.md` files; `ui-flow.md` lists the upstream BC's UI before the downstream BC's; each `ui-flow` entry links to a real `requirements.assets/<story>-<ui>.scene.json` under the owning BC; SC-010 verified. Repeat with React and Svelte. (quickstart S8 + S9 partial + S10 cases 1–3)

### Tests for User Story 5

- [X] T041 [P] [US5] Unit tests for the UI-flow topological sort in `api/features/ddd_spec/tests/test_ui_flow_sequencer.py`: (a) two-BC causal chain — upstream UI ranks before downstream UI; (b) cycle detection breaks the highest-tiebreaker back-edge and emits `ui_flow_cycle_broken`; (c) single-BC graph → fallback to BC insertion order + `ui_flow_no_cross_bc_edges`; (d) island UI appended at the tail with `is_unreferenced=true`; (e) tiebreaker determinism — same input → same ordering across 100 shuffled invocations (SC-005/SC-010).
- [X] T042 [P] [US5] Unit tests for the menu/route builder in `api/features/ddd_spec/tests/test_menu_builder.py`: top-level grouping by BC insertion order; within a BC, leaves ordered by User Story priority (P1→P5) with insertion-order fallback; route paths derived from User Story id + UI slug; assertion that the rendered bullet tree never references a non-existent `requirements.assets/*` path.
- [X] T043 [P] [US5] Unit tests for `FrameworkConventions` dispatch in `api/features/ddd_spec/tests/test_framework_conventions.py`: vue/react/svelte each resolve to the right catalog entry (`component_file_shape`, `state_default`, `routing_default`, `styling_default`); unknown framework returns `None` and triggers a `frontend_framework_unsupported` warning when the renderer is invoked.

### Implementation for User Story 5

- [X] T044 [P] [US5] Extend `api/features/ddd_spec/projection.py` with the new projection types per data-model.md §6.1: `FrontendCompositionProjection`, `FrameworkConventions`, `MenuEntry`, `UIFlowEntry`, `TriggerOrigin`. All Pydantic v2; no DB persistence.
- [X] T045 [P] [US5] Extend `api/features/ddd_spec/schemas.py` per data-model.md §6.3: add `frontend_framework`, `frontend_menu`, `frontend_ui_flow` to the `ArtifactKind` literal union; add `deprecated_per_bc_agent` to `SkippedItem.reason` (used by US7); document the new `GenerationWarning.code` values (`frontend_framework_unsupported`, `ui_flow_no_cross_bc_edges`, `ui_flow_cycle_broken`, `ui_unreferenced_flow`, `prd_split_lint_failed`).
- [X] T046 [US5] Extend `api/features/ddd_spec/repository.py` with `load_frontend_composition(framework: FrontendFramework, bcs: list[BoundedContextProjection], flows: list[CrossBcFlow]) -> FrontendCompositionProjection`: walks each User Story's bound UIs, attaches `triggered_by` from `flows` (cross-BC) and intra-story sequence, and hands the raw node/edge sets off to T047 for sequencing. No new Cypher query — reuses the existing BC subgraph + cross-BC flow loaders.
- [X] T047 [P] [US5] Implement `api/features/ddd_spec/ui_flow_sequencer.py`: the deterministic topological sort per research D8. Public entry `sequence_ui_flow(nodes, intra_story_edges, intra_bc_edges, cross_bc_edges, tiebreaker_key_fn) -> (ordered: list[UIFlowEntry], islands: list[UIFlowEntry], cycle_broken: list[tuple[str,str]])`. Kahn's algorithm; tiebreaker = `(bc_insertion_index, user_story_priority, user_story_insertion_index, ui_order_in_story)`. Cycle: remove the back-edge with the largest tiebreaker key and record it. No LLM.
- [X] T048 [P] [US5] Implement `api/features/ddd_spec/menu_builder.py`: builds `list[MenuEntry]` from `bcs` + per-BC User Story bound UIs; top-level entries are `kind="bc_group"` in BC insertion order; leaves are `kind="route"` carrying `route`, `user_story_id`, `wireframe_slug`. Pure function, deterministic, no LLM.
- [X] T049 [US5] Implement `api/features/ddd_spec/frontend_renderer.py` with three sub-renderers driven by `FrontendCompositionProjection`:
  - `render_framework_md(comp) -> str` → `specs/frontend/framework.md` (Jinja2 `frontend-framework.md.j2`); first non-heading line is `Framework: <name>`; emits `frontend_framework_unsupported` warning + "(no curated conventions — confirm)" body when `comp.framework_conventions is None`.
  - `render_menu_md(comp) -> str` → `specs/frontend/menu-structure.md` (Jinja2 `frontend-menu.md.j2`); hierarchical bullet list grouped by BC; each leaf names `route`, `user_story_id`, `wireframe_slug`, and the relative path to the canonical `requirements.assets/<story>-<ui>.scene.json`.
  - `render_ui_flow_md(comp) -> str` → `specs/frontend/ui-flow.md` (Jinja2 `frontend-ui-flow.md.j2`); numbered entries; each links back to `../bounded-contexts/<bc>/requirements.md` (the Wireframe block) + `../bounded-contexts/<bc>/requirements.assets/<userStoryId>-<ui-slug>.scene.json` + `.svg` (when present); islands rendered at the tail with `is_unreferenced=true` label. Depends on T044, T047, T048.
- [X] T050 [P] [US5] Add the three Jinja2 templates `api/features/ddd_spec/templates/frontend-framework.md.j2`, `frontend-menu.md.j2`, `frontend-ui-flow.md.j2`. Mirror the markdown shape documented in research D7 (machine-readable `Framework: ...` preamble in framework.md; BC-grouped bullet tree in menu-structure.md; numbered causal sections in ui-flow.md).
- [X] T051 [US5] Extend `api/features/ddd_spec/paths.py` to whitelist `specs/frontend/` as a valid `realpath`-sandbox target alongside `specs/bounded-contexts/` and `specs/context-map.md`; share the existing `.ddd-spec.lock` for the critical section (no second lock).
- [X] T052 [US5] Extend `api/features/ddd_spec/inproc.py` with `render_frontend_spec_to_zip(zip_file: zipfile.ZipFile, framework: FrontendFramework, bcs: list[dict]) -> list[ArtifactFileInfo]`: loads the projection (`repository.load_frontend_composition`), renders the three files via T049, writes them into the zip at `specs/frontend/{framework,menu-structure,ui-flow}.md`, and returns the `ArtifactFileInfo` list (kinds `frontend_framework`, `frontend_menu`, `frontend_ui_flow`). Also extend `planned_paths_for_preview()` to return those three paths when `include_frontend=true` AND `spec_format=ddd`.
- [X] T053 [P] [US5] Extend `api/features/prd_generation/prd_api_contracts.py`: add `SVELTE = "svelte"` to `FrontendFramework`. The enum's docstring lists Vue / React / Svelte as the v1-supported set; downstream additions are documented as a catalog change.
- [X] T054 [P] [US5] Extend `api/features/prd_generation/prd_tech_stack_catalog.py` with a static `FRAMEWORK_CONVENTIONS: dict[FrontendFramework, FrameworkConventions]` containing entries for `VUE`, `REACT`, `SVELTE` matching data-model.md §6.1 (`component_file_shape`, `state_default`, `routing_default`, `styling_default`). Unknown framework → `None`.
- [X] T055 [US5] Modify `api/features/prd_generation/routes/prd_export.py`:
  - In both `POST /api/prd/generate` and `POST /api/prd/download`, before any rendering: if `config.include_frontend and config.frontend_framework is None`, raise `HTTPException(400, detail={"code": "frontend_framework_required", "message": "Select a frontend framework before generation (vue / react / svelte / …)."})`.
  - In the planning path (`generate`), when `include_frontend=true AND spec_format=ddd`, extend `files_to_generate` with `specs/frontend/framework.md`, `specs/frontend/menu-structure.md`, `specs/frontend/ui-flow.md`, `.claude/commands/generate-frontend.md`, `.claude/agents/frontend-engineer.md`, `.claude/agents/ddd-specialist.md` (the last three lines also drive US7 — keep them additive here, not duplicated).
  - In the zip path (`download`), when `include_frontend=true AND spec_format=ddd`, after `pack_ddd_artifacts_to_zip(zip_file)`, call `from api.features.ddd_spec.inproc import render_frontend_spec_to_zip; render_frontend_spec_to_zip(zip_file, config.frontend_framework, bcs)`. The role-based agent + slash command zip writes are added by US7 (T064–T065).
- [ ] T056 [US5] Run quickstart S8 (framework precondition refusal + supplying any of vue/react/svelte unblocks the call) and the S9 frontend-folder portions (zip contains the three `specs/frontend/*.md`; `framework.md` line 1 is `Framework: <name>`; each `ui-flow` link resolves to a real `.scene.json`); fix gaps. Also run S10 case 1 (single-BC fallback emits `ui_flow_no_cross_bc_edges`), case 2 (unsupported framework emits `frontend_framework_unsupported`), case 3 (unreferenced UI lands at the tail with `ui_unreferenced_flow`).

**Checkpoint**: US5 fully functional — framework declaration is enforced, three frontend artifacts materialise per run, and the cross-BC causal ordering is verified end-to-end.

---

## Phase 9: User Story 6 — Split PRD.md (composition) from CLAUDE.md / `.cursorrules` (constitution) (Priority: P6)

**Goal**: `PRD.md` becomes purely compositional (technology-stack table, BC inventory, file index, deployment view, pointers); the prescriptive constitution (read-order injunctions, DDD principles, EARS-translation rules, GWT-test obligations, "🚨 CRITICAL"-style imperative blocks) moves into `CLAUDE.md` (when `ai_assistant=claude`) or `.cursorrules` (when `ai_assistant=cursor`). A build-time lint enforces disjointness; lint failure aborts the zip with HTTP 500 + `prd_split_lint_failed`.

**Independent Test**: Generate a package with `ai_assistant=claude` AND `spec_format=ddd`. `grep -E -i '\b(MUST|SHALL|Before starting|🚨|CRITICAL)\b'` on `PRD.md` returns empty; `grep -E '## Technology Stack|## Bounded Contexts'` on `CLAUDE.md` returns empty (CLAUDE may reference them, must not restate them). Repeat with `ai_assistant=cursor`: the same disjointness holds between `PRD.md` and `.cursorrules`, and no `CLAUDE.md` is produced. (quickstart S9 steps 3–4)

### Tests for User Story 6

- [X] T057 [P] [US6] Unit tests for the PRD↔CLAUDE split lint in `api/features/prd_generation/tests/test_prd_split_lint.py`: (a) prescriptive imperative regex hits in PRD.md body → fail with offending substring + offset; (b) imperatives inside fenced code blocks or markdown table cells → allowed (no fail); (c) Technology Stack / Bounded Contexts table header in CLAUDE.md / .cursorrules → fail; (d) clean disjoint files → pass; (e) pointer lines ("See PRD.md for ...") in either file → allowed.

### Implementation for User Story 6

- [X] T058 [US6] Refactor `api/features/prd_generation/prd_artifact_generation.py::generate_main_prd` per research D9: keep project name + technology stack table + Bounded Contexts inventory + project-file index + deployment view + pointer lines; **delete** "🚨 CRITICAL: Before Starting Implementation", "⚠️ Important: Read All Reference Files", and every other "you MUST" / "Before starting" / DDD-principle prescription. Move the deleted content into the generators for `CLAUDE.md` / `.cursorrules` (T059–T060).
- [X] T059 [US6] Refactor `api/features/prd_generation/prd_artifact_generation.py::generate_claude_md` to absorb the prescriptive content removed in T058 — DDD principles read-order, EARS-translation rules, GWT-test obligation, "do not invent domain concepts", per-BC artifact read-order, plus the existing project-context paragraph. CLAUDE.md must **not** restate the Technology Stack table or the Bounded Contexts inventory (it may name them with a one-line pointer). All "read these skills" references stay relative-path to `.claude/skills/*`.
- [X] T060 [US6] Refactor `api/features/prd_generation/prd_artifact_generation.py::generate_cursor_rules` to absorb the prescriptive content removed in T058 when `ai_assistant=cursor` is selected. Same disjointness rule against PRD.md — `.cursorrules` carries the imperatives, PRD.md does not.
- [X] T061 [US6] Implement `api/features/prd_generation/prd_split_lint.py` with `lint_disjoint(prd_text: str, constitution_text: str, constitution_filename: str) -> None` (raises `PrdSplitLintError(code="prd_split_lint_failed", offending_file, offending_substring, offset)` on violation). Regex per research D9: `(?i)\b(MUST|SHALL|MUST NOT|SHALL NOT|REQUIRED|Before starting|🚨|CRITICAL)\b` against PRD.md (skipping fenced code blocks and table cells via a markdown-aware tokenizer); table-header regex against constitution text. Emits a `prd_split_lint_passed` `SmartLogger` event on success.
- [X] T062 [US6] Wire `prd_split_lint.lint_disjoint` into `api/features/prd_generation/routes/prd_export.py::download_prd_zip` immediately after `PRD.md` and `CLAUDE.md` (or `.cursorrules`) are rendered, **before** they are written into the zip. On `PrdSplitLintError`, raise `HTTPException(500, detail={"code": "prd_split_lint_failed", "file": e.offending_file, "substring": e.offending_substring, "offset": e.offset})` and abort the zip; the existing SmartLogger trace at this seam already captures the failure with the correlation id.
- [X] T063 [US6] Run quickstart S9 steps 3–4 (both regex assertions return empty on the generated `PRD.md` and `CLAUDE.md`) and S10 case 5 (the deliberate lint failure aborts with the right code); fix gaps. Repeat once with `ai_assistant=cursor` to confirm `.cursorrules` carries the imperatives and `PRD.md` does not.

**Checkpoint**: US6 fully functional — PRD↔CLAUDE / PRD↔.cursorrules content is provably disjoint; the lint stops drift at the zip build seam.

---

## Phase 10: User Story 7 — Drop per-BC agents; emit role-based agents + `/generate-frontend` (Priority: P7)

**Goal**: Stop emitting `.claude/agents/<bc_name>_agent.md` per Bounded Context. Migrate the four kinds of useful per-BC agent content (skills-reference list, scope/boundary statement, key-component recap, responsibilities checklist) into the existing skills and slash commands per research D10. Emit exactly two role-based agent files at fixed names: `.claude/agents/frontend-engineer.md` (only when `include_frontend=true`) and `.claude/agents/ddd-specialist.md` (always, when `spec_format=ddd`). Emit a new slash command `.claude/commands/generate-frontend.md` that walks `specs/frontend/` + per-BC `requirements.assets/` and instructs the coding agent to produce frontend components in the declared framework.

**Independent Test**: Generate a zip with `ai_assistant=claude`, `spec_format=ddd`, `include_frontend=true`, framework = vue. Verify `unzip -l pkg.zip | grep '\.claude/agents/'` lists exactly `frontend-engineer.md` and `ddd-specialist.md` and **no** `<bc_name>_agent.md`. Verify `.claude/commands/generate-frontend.md` exists and its body references `specs/frontend/{framework,menu-structure,ui-flow}.md`. Drop a fake pre-existing per-BC agent file into the working copy; the response's `skipped` array contains it with `reason: "deprecated_per_bc_agent"`. (quickstart S9 steps 2 + S10 case 4)

### Tests for User Story 7

- [X] T064 [P] [US7] Unit tests for the role-based agent generators in `api/features/prd_generation/tests/test_role_based_agents.py`: (a) `generate_role_agent_frontend_engineer` body contains at least one relative-path reference to a file under `.claude/skills/` for each of (ddd-principles, eventstorming-implementation, gwt-test-generation) and for the chosen frontend framework skill; (b) it contains **no** restated skill content (body length under N tokens; no markdown headings matching the skill files' own H2/H3 patterns); (c) same checks for `generate_role_agent_ddd_specialist`; (d) the "When invoked" section in each agent lists the slash commands that may invoke it.
- [X] T065 [P] [US7] Unit tests for the `/generate-frontend` command generator in `api/features/prd_generation/tests/test_generate_frontend_command.py`: body contains read references to `specs/frontend/framework.md`, `specs/frontend/menu-structure.md`, `specs/frontend/ui-flow.md`; body walks each `ui-flow` entry's `requirements.assets/<story>-<ui>.scene.json` link; body names the declared framework verbatim; body invokes `@.claude/agents/frontend-engineer.md`.

### Implementation for User Story 7

- [X] T066 [US7] Remove `generate_agent_config` and its two call sites in `api/features/prd_generation/routes/prd_export.py` (the loops at the legacy-flat-spec path and the ddd-spec path). The function definition in `prd_artifact_generation.py` is deleted in the same commit (no dead code). Useful content from the deleted function is migrated per T067–T070.
- [X] T067 [US7] Migrate the skills-reference list (per-BC agent content kind (a) per research D10) into the bodies of the two role-based agent generators added in T070–T071. One skills list per role-based agent, not N per BC.
- [X] T068 [US7] Migrate the scope/boundary statement (per-BC agent content kind (b)) into the body of `.claude/commands/implement-ddd-bc.md` (existing — `generate_claude_command_implement_ddd_bc` in `prd_artifact_generation.py`): the command takes a `<bc-slug>` arg and already states "modify only files within the BC's module"; reinforce the boundary statement so the per-BC nuance lives in the spec folder the command points at, not in an agent file.
- [X] T069 [US7] Migrate the responsibilities checklist (per-BC agent content kind (d)) into `.claude/skills/ddd-spec-implementation.md`'s "verification checklist" section (existing — `generate_claude_skill_ddd_spec_implementation` in `prd_artifact_generation.py`). The `/implement-ddd-bc` command's "Done criteria" continues to point at this checklist.
- [X] T070 [P] [US7] Implement `generate_role_agent_frontend_engineer(config: TechStackConfig) -> str` in `api/features/prd_generation/prd_artifact_generation.py`: returns the body of `.claude/agents/frontend-engineer.md` per research D10. Role paragraph; skills references (relative path) to `.claude/skills/{ddd-principles,eventstorming-implementation,gwt-test-generation,<frontend_framework>}.md`; "When invoked" lists `/generate-frontend` (and future commands). Body contains no restated skill content; under N tokens.
- [X] T071 [P] [US7] Implement `generate_role_agent_ddd_specialist(config: TechStackConfig) -> str` in `api/features/prd_generation/prd_artifact_generation.py`: returns the body of `.claude/agents/ddd-specialist.md` per research D10. Role paragraph; skills references to `.claude/skills/{ddd-spec-implementation,ddd-principles,eventstorming-implementation,gwt-test-generation,<framework>}.md`; "When invoked" lists `/implement-ddd-bc`, `/implement-ddd-wireframe`. Body contains no restated skill content; under N tokens.
- [X] T072 [US7] Implement `generate_claude_command_generate_frontend(config: TechStackConfig) -> str` in `api/features/prd_generation/prd_artifact_generation.py`: returns the body of `.claude/commands/generate-frontend.md`. The command opens `specs/frontend/framework.md` (parsing the `Framework:` line), `specs/frontend/menu-structure.md`, and `specs/frontend/ui-flow.md`; for each numbered `ui-flow` entry it follows the link to `../bounded-contexts/<bc>/requirements.assets/<story>-<ui>.scene.json` + `.svg` + the `requirements.md` element-tree block; instructs the coding agent to invoke `@.claude/agents/frontend-engineer.md` and produce one component per wireframe in the declared framework. Mirror the shape of the existing `generate_claude_command_implement_ddd_*` functions.
- [X] T073 [US7] Modify `api/features/prd_generation/routes/prd_export.py::download_prd_zip` and the planning path:
  - When `ai_assistant=claude` AND `spec_format=ddd`: write `.claude/agents/ddd-specialist.md` (via T071); when `include_frontend=true` also write `.claude/agents/frontend-engineer.md` (via T070) and `.claude/commands/generate-frontend.md` (via T072).
  - In the planning path, ensure `files_to_generate` lists the role-based agents and `generate-frontend.md` per the contracts §7.2; ensure no `.claude/agents/<bc_name>_agent.md` entries appear (regression check vs T055 + T066).
- [X] T074 [US7] Implement deprecated-per-BC-agent reporting: when the response builder detects a `.claude/agents/<file>` that matches `<bc_name>_agent.md` for any BC the request will produce, append a `SkippedItem(kind="artifact_file", id=None, existing_path=...,  reason="deprecated_per_bc_agent", message="Per-BC agent files are deprecated; delete your local copy. Useful content was migrated to .claude/skills/* and .claude/commands/*.")` to the response. This is detection-on-emit (the new zip simply omits the file); we don't scan the user's filesystem.
- [X] T075 [US7] Run quickstart S9 step 2 (exactly two role-based agent files, no per-BC agents, `/generate-frontend` body references) and S10 case 4 (deprecated per-BC agent listed in `skipped`); fix gaps.

**Checkpoint**: US7 fully functional — per-BC agent emission is gone, role-based agents are in place, the `/generate-frontend` slash command is wired, and migration paths are complete.

---

## Phase 11: Polish & Cross-Cutting (amendment)

- [X] T076 [P] Add a static guard test in `api/features/ddd_spec/tests/test_module_boundaries.py` (extending the existing T037 test or a new file): the frontend renderer / sequencer / menu builder MUST NOT import from any sibling `api/features/*` except via `api/platform/*` or the documented `prd_generation` seam (`inproc.render_frontend_spec_to_zip` is exposed by `ddd_spec`, not consumed from prd_generation into ddd_spec's internals).
- [X] T077 [P] Extend the determinism test (`api/features/ddd_spec/tests/test_determinism.py`): generate the same package twice (same graph, same `include_frontend=true`, same framework) and verify the three `specs/frontend/*.md` are byte-identical except the `Generated:` timestamp line (SC-009/SC-010 byte-stability extension).
- [X] T078 [P] Add a packaging-disjointness test in `api/features/prd_generation/tests/test_prd_split_disjoint.py`: render the PRD package end-to-end against a fixture graph for both `ai_assistant=claude` and `ai_assistant=cursor`; run the lint over the rendered files; assert no `prd_split_lint_failed` regression for either path (SC-011).
- [X] T079 [P] Add an agent-emission test in `api/features/prd_generation/tests/test_role_based_emission.py`: a generated zip (in-memory `io.BytesIO`) contains exactly one of each role-based agent (when applicable), zero `<bc_name>_agent.md` entries, and exactly one `/generate-frontend.md` when `include_frontend=true` (SC-012/SC-013).
- [X] T080 Update `README.md`'s API summary + project structure section to describe the new `specs/frontend/` sibling folder (per FR-021), the new role-based agents + `/generate-frontend` slash command, and the PRD↔CLAUDE content-split rule. Note the deprecated per-BC agent files and link to the migration guidance in the new SkippedItem reason.
- [X] T081 Run the full `quickstart.md` end-to-end against a real graph + open-pencil service: S1–S7 (unchanged) plus S8–S10 (new); plus the non-regression checklist. Confirm the existing `/api/ddd-spec/*` endpoints behave exactly as v1 (no contract drift for stories US1–US4), and `/api/prd/{generate,download}` honour the new precondition + zip additions without breaking the pre-amendment flow.
- [X] T082 Confirm `plan.md`'s Complexity Tracking is still accurate post-implementation (frontend mirror canvas/inspector UI still deferred; the cross-feature seam `render_frontend_spec_to_zip` lives at `api/features/ddd_spec/inproc.py`; per-BC agents removed and content migrated; PRD↔CLAUDE lint is a hard abort). Open a follow-up issue for the deferred canvas/inspector frontend mirror at `frontend/src/features/dddSpec/`.

---

## Dependencies & Execution Order (amendment)

### Phase Dependencies

- **Phase 7 (existing Polish)** is complete — does not block the amendment.
- **Phase 8 (US5)** depends on Phase 2 foundational work (already complete). All US5 work can start in parallel by file: T041–T043 (tests) `[P]` and T044, T045, T047, T048, T050, T053, T054 are all `[P]` (separate files). T046 sequential after T044/T045. T049 after T047/T048/T050. T051 small edit to `paths.py`. T052 after T049 (it calls into the renderer). T055 after T052 + T053 + T054 (it ties the prd_export seam together). T056 last (quickstart smoke).
- **Phase 9 (US6)** is independent of Phase 8 except they both touch `prd_export.py`. Order: T057 `[P]`; T058 → T059 → T060 sequential (same file `prd_artifact_generation.py`); T061 `[P]`; T062 after T061 + T058–T060; T063 last (quickstart smoke).
- **Phase 10 (US7)** depends on US5 + US6 partially: T066 (drop call sites in `prd_export.py`) coordinates with T055 (US5's edit) and T062 (US6's edit) — same file, do as one rebase-friendly commit train. T067–T069 (content migration) can run `[P]`. T070–T072 are `[P]` (three independent generator functions). T073 after T070–T072 (zip writer). T074 after T073. T075 last (quickstart smoke).
- **Phase 11 (Polish 2)**: depends on US5 + US6 + US7 all complete. T076–T079 `[P]`; T080–T082 sequential at the end.

### Cross-phase parallelism

- Once Phase 2 is done (already), Developer A on US5, Developer B on US6, Developer C on US7 — coordinated only at `prd_export.py` (T055 + T062 + T066 + T073 land as one train) and at `prd_artifact_generation.py` (T058–T060 train for US6; T070–T072 train for US7; T066 deletes a function — coordinate first).
- Developer D on Polish 2 once US5 + US6 + US7 commits land on the branch.

### File-coordination hotspots

| File | Tasks that touch it | Coordination |
|------|---------------------|--------------|
| `api/features/ddd_spec/projection.py` | T044 (US5) | single edit, additive |
| `api/features/ddd_spec/schemas.py` | T045 (US5) | single edit, additive |
| `api/features/ddd_spec/repository.py` | T046 (US5) | single edit, additive |
| `api/features/ddd_spec/paths.py` | T051 (US5) | single edit, additive |
| `api/features/ddd_spec/inproc.py` | T052 (US5) | single edit, additive |
| `api/features/prd_generation/prd_api_contracts.py` | T053 (US5) | single edit, additive |
| `api/features/prd_generation/prd_tech_stack_catalog.py` | T054 (US5) | single edit, additive |
| `api/features/prd_generation/prd_artifact_generation.py` | T058, T059, T060 (US6) and T066, T067, T068, T069, T070, T071, T072 (US7) | **two trains** — US6 first (refactor split), US7 second (delete `generate_agent_config`, add role-based generators + `/generate-frontend`). Rebase US7 onto US6. |
| `api/features/prd_generation/routes/prd_export.py` | T055 (US5), T062 (US6), T066/T073 (US7) | **single train** — land these as one rebased sequence to avoid three-way conflict on the zip orchestration. |

### Parallel Opportunities (amendment)

- US5 unit tests T041–T043 `[P]` with each other.
- US5 leaf implementations T044, T045, T047, T048, T050, T053, T054 `[P]` with each other.
- US6 unit tests T057 `[P]` with US5 tests.
- US7 generators T070, T071, T072 `[P]` with each other.
- Polish 2 tests T076–T079 `[P]` with each other.

---

## Implementation Strategy (amendment)

### Order of value delivery

1. **US5 first** — the frontend perspective is the biggest visible delivery and a precondition for `/generate-frontend` to do anything useful (US7 references it).
2. **US6 second** — the PRD↔CLAUDE split is a pure refactor that fits cleanly into `prd_artifact_generation.py` once US5's file-list extensions have landed.
3. **US7 third** — per-BC agent removal + role-based emission + `/generate-frontend` command. US7's `/generate-frontend` body references `specs/frontend/*.md` (US5) and `.claude/skills/*` (US6 keeps the skills layout). Land last.
4. **Polish 2** — boundary/determinism/disjointness/emission tests, README updates, full S1–S10 smoke.

### Validation milestones

- **After US5**: `curl -X POST /api/prd/generate` with `include_frontend=true` & no framework → 400 with `frontend_framework_required`; same with `frontend_framework=vue` → 200 + `specs/frontend/*.md` in the file list; `download` zip contains the three files; quickstart S8 + parts of S9 + S10 cases 1–3 pass.
- **After US6**: `unzip -p pkg.zip PRD.md` clean of imperatives; `unzip -p pkg.zip CLAUDE.md` clean of inventory tables; deliberate lint failure aborts with `prd_split_lint_failed`; quickstart S9 steps 3–4 + S10 case 5 pass.
- **After US7**: zero `<bc_name>_agent.md`, exactly one each of `frontend-engineer.md` and `ddd-specialist.md`, `generate-frontend.md` present; deprecated per-BC agent reporting works; quickstart S9 step 2 + S10 case 4 pass.
- **After Polish 2**: full S1–S10 + non-regression suite green; all FRs (FR-001 through FR-024) and SCs (SC-001 through SC-013) verified.

### Notes specific to the amendment

- The cross-feature seam (`render_frontend_spec_to_zip`) is the only new public function crossing the `ddd_spec` ↔ `prd_generation` boundary. Keep it that way — internal helpers stay private.
- The per-BC agent deletion is permanent; no migration toggle. The user's stale-file warning in `SkippedItem` is the only backward-compat affordance.
- The PRD↔CLAUDE lint is a hard abort by design (research D9). Do not add a "warn-only" mode — that defeats P6.
- The UI-flow topological sort's tiebreaker is the only place "ordering" is decided. Adding a request-level override (e.g. "manual ordering") would be a future spec change, not part of this amendment.
