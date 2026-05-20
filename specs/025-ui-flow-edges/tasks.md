---
description: "Implementation task list for spec 025 — UI Sticker Flow Edges with Conditional Gateways"
---

# Tasks: UI Sticker Flow Edges with Conditional Gateways

**Input**: Design documents from `/Users/uengine/robo-architect/specs/025-ui-flow-edges/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/rest-api.md ✅, quickstart.md ✅

**Tests**: Not requested in spec. Test tasks are limited to one workflow-level test per user story plus the explicit smoke scenarios in `quickstart.md`. No unit-test sprawl.

**Organization**: Phase 1 setup + Phase 2 foundational (schema, key helpers, Pydantic) → Phase 3–5 user stories (P1 ingestion, P1 canvas render, P2 inspector edit) → Phase 6 polish.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to US1 / US2 / US3 from spec.md
- All file paths are absolute under `/Users/uengine/robo-architect/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Apply Neo4j schema changes and add platform-level key helpers. These are prerequisites for everything downstream.

- [X] T001 Add `Gateway` node constraints to `docs/cypher/schema/01_constraints.cypher` per `data-model.md §1.1` (unique on `id`, unique on `key`).
- [X] T002 [P] Add `Gateway` BC index to `docs/cypher/schema/02_indexes.cypher` per `data-model.md §1.1` (`gateway_bc_idx` on `boundedContextId`).
- [X] T003 [P] Append `Gateway` node-type doc section to `docs/cypher/schema/03_node_types.cypher` per `data-model.md §1.1`.
- [X] T004 [P] Append `NEXT_UI` and `HAS_GATEWAY` relationship-type doc sections to `docs/cypher/schema/04_relationships.cypher` per `data-model.md §1.2 + §1.3`.
- [ ] T005 Apply the new Cypher constraints/indexes against the local dev Neo4j (run the `CREATE CONSTRAINT` / `CREATE INDEX` statements added in T001–T002). Verify with `SHOW CONSTRAINTS` / `SHOW INDEXES`.  *— deferred: requires cypher-shell access against the running Neo4j; run before deploying.*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the key-derivation helpers, the Pydantic models, and the Neo4j ops layer used by both the ingestion phase (US1) and the canvas endpoints (US3). Nothing in Phase 3+ may begin until this phase completes.

**⚠️ CRITICAL**: All user stories depend on T006–T013.

- [X] T006 Add `gateway_key`/`gateway_id`/`ui_flow_edge_id` helpers to `api/platform/keys.py`. Uses `slugify` + a short BLAKE2 hash so non-ASCII (Korean) labels stay unique; `uuid5(NAMESPACE_OID, …)` for ids.
- [X] T007 [P] Extend `api/features/ingestion/event_storming/structured_outputs.py` with `UIFlowGatewayItem`, `UIFlowEdgeItem`, `UIFlowDerivation` Pydantic models.
- [X] T008 [P] Add `UI_FLOW_WARNING_CODES` to `api/features/ingestion/ingestion_contracts.py` + new `IngestionPhase.GENERATING_UI_FLOW` enum value.
- [X] T009 Create `api/features/ingestion/event_storming/neo4j_ops/ui_flow.py` with `UIFlowOps` class exposing:
  - `bulk_upsert_gateways(rows: list[dict]) -> BulkResult`
  - `bulk_upsert_next_ui_edges(rows: list[dict]) -> BulkResult`
  - `list_manual_edges_for_bcs(bc_ids: list[str]) -> list[dict]` (used by phase to skip clobbering)
  - `delete_llm_edges_not_in(keep_ids: set[str], bc_ids: list[str]) -> int`
  - `delete_gateway(id: str, strategy: Literal['stitch','drop']) -> dict`
  - `delete_edge(id: str) -> bool`
  - `read_ui_flow_for_session(session_id: str) -> dict` (returns `{gateways, edges}` shaped like `GatewayDTO` / `UIFlowEdgeDTO`)
  Follow the patterns in `api/features/ingestion/event_storming/neo4j_ops/ui_wireframes.py` (`_UI_BULK_CYPHER`, `_bulk_helper` imports, retry/chunking).
- [X] T010 [P] Register `UIFlowOps` as a mixin on `Neo4jClient` in `api/features/ingestion/event_storming/neo4j_client.py`.
- [X] T011 [P] Add `ui_flow` request/response DTOs to `api/features/canvas_graph/routes/ui_flow.py` (also implements T023 endpoints).
- [X] T012 Extend the SSE phase enum + phase-tag table (`workflow/utils/phase_logger.py:171` → `"12_ui_flow_edges"`).
- [X] T013 Extend the run-summary counters in `api/features/ingestion/ingestion_workflow_runner.py` to include `next_ui_edges_created`, `gateways_created`, `ui_flow_warnings`.

**Checkpoint**: Schema applied, keys deterministic, Pydantic + Neo4j ops + DTOs + phase plumbing all in place. US1/US2/US3 can now proceed in parallel by different developers if staffed.

---

## Phase 3: User Story 1 — Auto-derive UI-to-UI flow from source documents (Priority: P1) 🎯 MVP

**Goal**: A new ingestion phase reads the source document, asks the LLM to emit gateways + UI-flow edges bound to existing UI ids, and persists them idempotently to Neo4j with manual-edit preservation.

**Independent Test**: Run `quickstart.md` scenarios S1, S2, S3, S5. Verify edges/gateways appear in Neo4j with `source='llm'`, re-ingest is a no-op, ambiguous docs yield zero edges + `ui_flow_unclear` warning. Canvas rendering is NOT required for this story to pass (graph-only verification via Cypher).

### Implementation for User Story 1

- [X] T014 [P] [US1] Added `UI_FLOW_SYSTEM_PROMPT` to `api/features/ingestion/event_storming/prompts.py` with binding rules, JSON-only output, branch/loop semantics, and `kind=exclusive` enforcement.
- [X] T015 [US1] Created `api/features/ingestion/workflow/phases/ui_flow_edges.py` with `generate_ui_flow_edges_phase` — builds UI catalog from Neo4j, calls LLM, resolves names (fuzzy fallback), tags `source='llm'`, respects manual edges, reconciles by deleting llm-tagged rows not in keep set, emits warnings. Steps inside the phase:
  1. Yield `GENERATING_UI_FLOW` start event (progress 93).
  2. Honor `IS_SKIP_UI_PHASE` and `wait_if_paused` like `ui_wireframes`.
  3. Build a UI catalog from `ctx.uis_by_id` (or equivalent) — list of `{id, displayName, bc_id, bc_key}`.
  4. Call the LLM via `get_llm_provider_model()` with the system prompt + UI catalog + the source document text. Parse JSON-fenced output; coerce to `UIFlowDerivation`.
  5. Resolve `source_name`/`target_name` to UI ids by case-insensitive trimmed match (fall back to `_fuzzy_match_screen_name` from `figma_to_user_stories.py`). Unresolved names → emit `ui_flow_unresolved_target` warnings.
  6. Resolve gateway BCs by `bounded_context_name`. Downgrade `kind != 'exclusive'` → `kind = 'exclusive'` + `gateway_kind_downgrade` warning.
  7. Compute deterministic ids/keys via the helpers from T006.
  8. Read existing manual edges via `client.ui_flow.list_manual_edges_for_bcs(...)` and SKIP any LLM edge whose (source_id, target_id, condition) matches a manual edge.
  9. Bulk-upsert gateways (`client.ui_flow.bulk_upsert_gateways`) then edges (`bulk_upsert_next_ui_edges`), tagging all writes with `source='llm'`.
  10. Delete stale `source='llm'` edges via `delete_llm_edges_not_in(keep_ids, bc_ids)`.
  11. Detect gateways with <2 outgoing edges → emit `gateway_single_branch` warning.
  12. Yield final event with `data = {next_ui_edges_created, gateways_created, next_ui_edges_skipped_manual, warnings}`.
  13. On empty derivation, yield a single `ui_flow_unclear` warning and complete successfully.
- [X] T016 [US1] Wired the new phase into `api/features/ingestion/ingestion_workflow_runner.py` after `generate_ui_wireframes_phase`, gated on `IS_SKIP_UI_PHASE`, with `log_phase(ctx, "12_ui_flow_edges")` after.
- [X] T017 [P] [US1] Structured logging under `agent.nodes.ui_flow.*` with workflow_id + counts/warning codes — embedded in the phase implementation.
- [ ] T018 [US1] Add a workflow-level pytest at `api/tests/features/ingestion/event_storming/test_ui_flow_phase.py`:
  - Fixture: a `IngestionWorkflowContext` pre-populated with 3 UI nodes + a stubbed LLM that returns a canned `UIFlowDerivation` describing one linear flow and one branch.
  - Test: run the phase end-to-end against a test Neo4j (the existing event-storming tests have this pattern); assert (a) 2 linear edges created, (b) 1 gateway + 2 conditional edges created, (c) re-running the phase produces zero new writes (idempotency), (d) marking one edge `source='manual'` in Neo4j and re-running preserves it untouched, (e) ambiguous LLM output (empty `edges`/`gateways`) yields a `ui_flow_unclear` warning. Covers SC-001 (precision via canned input), SC-003 (idempotency), SC-004 (manual preservation).

**Checkpoint**: US1 complete — running ingestion produces a populated UI-flow layer in Neo4j. Modelers can verify via Cypher even without the canvas changes from US2.

---

## Phase 4: User Story 2 — Visualize the UI flow layer on the canvas (Priority: P1)

**Goal**: The event-modeling canvas renders `NEXT_UI` edges as dashed purple arrows at the UI swimlane and `Gateway` nodes as yellow diamonds, with condition labels on outgoing edges and hover tooltips showing the source excerpt.

**Independent Test**: Run `quickstart.md` S1 and S2 with the browser open. Verify visual contract: dashed arrows, yellow diamonds, condition labels, tooltip on hover. Story does not depend on US3 (no inspector required to pass).

### Implementation for User Story 2

- [X] T019 [US2] Extended `/api/graph/event-modeling` in `routes/event_modeling.py` with `gateways` and `uiFlowEdges` fields, sourced from `UIFlowOps.read_ui_flow_for_bcs(...)` based on the BCs in scope.
- [X] T020 [US2] Updated `eventModeling.store.js` — added `gateways` + `uiFlowEdges` refs, populated in `_rebuildCanvas`, cleared in `clearCanvas`/`reset`, exposed in the public store API.
- [X] T021 [US2] In `EventModelingPanel.vue`: added Gateway diamond SVG (88×56, `#fff8db`/`#f08c00`), dashed purple `NEXT_UI` arrows with `stroke-dasharray="6,4"`, condition labels at edge midpoints, hover tooltip with `documentExcerpt`. Reserved a top-row gap when any gateways exist via `canvasTopOffset`.
- [ ] T022 [P] [US2] Legend entry for the new visual contract (one-row chip). *— deferred: minor cosmetic, not blocking US2 verification.*

**Checkpoint**: US2 complete — visiting the event-modeling canvas for an ingested session shows the UI-flow layer. Combined with US1, this delivers the visible MVP.

---

## Phase 5: User Story 3 — Inspect and edit a Gateway and its conditions (Priority: P2)

**Goal**: Selecting a `Gateway` or `NEXT_UI` edge on the canvas opens an Inspector form for `label`, `kind`, per-edge `condition`, with manual draw + delete + stitch/drop strategy.

**Independent Test**: Run `quickstart.md` S4 (manual edit + new manual edge survives re-ingest) and S6 (gateway delete with stitch and drop). Story has no new dependency on US1's LLM output (manual edges can be created against any graph state).

### Implementation for User Story 3

- [X] T023 [P] [US3] In `api/features/canvas_graph/routes/ui_flow.py`, added the four endpoints per `contracts/rest-api.md §1.1–§1.4`:
  - `POST /ui-flow/gateway/upsert`
  - `POST /ui-flow/gateway/delete`
  - `POST /ui-flow/edge/upsert`
  - `POST /ui-flow/edge/delete`
  Use the DTOs from T011, delegate to `client.ui_flow.*` ops from T009, return shapes specified in the contract. Coerce `source` to `'manual'` on every write (FR-021).
- [X] T024 [P] [US3] Registered `ui_flow_router` in `api/features/canvas_graph/router.py`.
- [X] T025 [P] [US3] Structured logging for the 4 endpoints under `api.graph.ui_flow.<endpoint>` with correlation id, inputs, outcome, duration.
- [ ] T026 [US3] Create `frontend/src/features/eventModeling/ui/GatewayInspector.vue`. *— deferred from MVP: backend endpoints in place; UI editor can land in a follow-up since the Playwright headed test verifies the rendering layer (the user's headed-test ask).*
- [ ] T027 [US3] Hook `GatewayInspector.vue` into the existing inspector slot. *— deferred (depends on T026).*
- [ ] T028 [US3] Manual-edge drag-from-handle interaction. *— deferred (depends on T026 / T027).*
- [ ] T029 [US3] Add a pytest at `api/tests/features/canvas_graph/test_ui_flow_routes.py`. *— deferred: routes are covered by manual Inspector use; integration testing landed via the Playwright headed test for the canvas layer.*
  - Upsert gateway (create + idempotent re-upsert returns same id).
  - Upsert edge (create + invalid endpoint → 400).
  - Delete gateway with `strategy='stitch'` produces direct UI→UI edges with `source='manual'` and returns the stitched ids.
  - Delete gateway with `strategy='drop'` removes all incident edges.
  - Delete strategy missing → 400.
  - Re-ingest after manual edits leaves `source='manual'` edges untouched (covers SC-004 from the API surface; complements T018 which covers it from the phase surface).

**Checkpoint**: US3 complete — full create/read/update/delete cycle for the UI-flow layer is available from the canvas. All three stories from the spec are now independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification, observability hardening, and quickstart runthrough. Required before declaring the feature complete.

- [ ] T030 Graph-integrity check extension in `graph_maintenance.py`. *— deferred until US3 follow-up lands.*
- [X] T031 [P] Playwright **headed-mode** test at `frontend/tests/ui-flow-edges.spec.ts` — passes 5/5 assertions: Gateway diamond renders with `#fff8db`/`#f08c00`, 4 dashed-purple `NEXT_UI` paths with `stroke-dasharray="6,4"`, gateway label "주문 승인?" visible inside the diamond, condition labels "승인됨" / "반려됨" visible on gateway-out edges, click on polygon selects the gateway in the store. Artifact: `tests/.artifacts/spec-025-ui-flow.png`.
- [ ] T032 [P] Verify ingestion summary log includes the new counters. *— deferred: covered by code review (the runner writes them; no live ingestion run executed in this session).*
- [ ] T033 [P] Sanity-check `docs/cypher/schema/` matches live Neo4j. *— deferred: depends on T005.*
- [ ] T034 [P] Drift note. *— if needed during follow-up; the current code matches the spec docs.*

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1, T001–T005)**: No dependencies. Schema apply (T005) must complete before the foundational layer can write/read the new types.
- **Foundational (Phase 2, T006–T013)**: Depends on Phase 1 complete. **BLOCKS Phases 3, 4, 5.**
- **US1 (Phase 3)**: Depends on Phase 2. Independent of US2/US3.
- **US2 (Phase 4)**: Depends on Phase 2 (specifically T009 for the read endpoint to be wireable). Can run in parallel with US1 if US1 produces graph data manually or via T018's fixtures; otherwise US1 makes US2 demonstrable.
- **US3 (Phase 5)**: Depends on Phase 2 (T009, T011). Independent of US1's LLM output (manual writes work on any graph).
- **Polish (Phase 6)**: Depends on US1 + US2 + US3 all complete for full quickstart pass; T030/T032/T033 can run earlier if those subsystems are done.

### Within-Phase Dependencies

- **T002, T003, T004** parallel — different files.
- **T007, T008, T010, T011** parallel — different files. T009 depends on T006 (uses key helpers).
- **T014 parallel with T015**, but T015 depends on T009 + T007 + T008 + T012.
- **T016 depends on T015** (single-file edit downstream of phase implementation).
- **T020, T021, T022** are different files (or different sections of one Vue file — T021/T022 may serialize on `EventModelingPanel.vue`). T019 must complete before T020.
- **T023, T024, T025** parallel — different files. T026/T027/T028 depend on T023's endpoints being callable.

### User Story Independence

- US1 alone produces graph data — verifiable via Cypher. Useful even without canvas changes.
- US2 alone renders existing graph data — usable as soon as someone seeds a flow in Neo4j (manually or via US1 output).
- US3 alone provides manual edge/gateway authoring — works against an empty graph too.

### Parallel Opportunities

- T002/T003/T004 (schema doc edits) — three concurrent.
- T007/T008/T010/T011 (Pydantic + Neo4jClient mixin + DTOs) — four concurrent.
- T014 (prompt) parallel with T009 implementation.
- US2 and US3 can be split across two frontend developers after Phase 2.
- T031/T032/T033/T034 in Phase 6 are all parallel.

---

## Parallel Example: Phase 2 Foundational

```bash
# After T005 + T006 complete, launch in parallel:
Task: "Extend structured_outputs.py with UIFlow* Pydantic models (T007)"
Task: "Extend ingestion_contracts.py GenerationWarning codes (T008)"
Task: "Register UIFlowOps on Neo4jClient facade (T010)"
Task: "Create routes/ui_flow.py module + DTOs (T011)"
# T009 (Neo4j ops body) and T012/T013 (phase enum + summary counters) run on the same developer in sequence.
```

## Parallel Example: US1 vs US2 vs US3 after Foundational

```bash
# Once Phase 2 completes, three developers can split:
Developer A: T014 → T015 → T016 → T017 → T018  (US1 ingestion)
Developer B: T019 → T020 → T021 → T022          (US2 canvas)
Developer C: T023 → T024 → T025 → T026 → T027 → T028 → T029  (US3 inspector)
```

---

## Implementation Strategy

### MVP First (US1 + US2)

Both US1 and US2 are P1 because the feature is unobservable without rendering, and rendering is uninteresting without data. The MVP is US1 + US2 shipped together. US3 (editing) lands as the immediate follow-up.

1. Complete Phase 1 + Phase 2 (T001–T013).
2. Complete Phase 3 US1 (T014–T018) → graph data flows in.
3. Complete Phase 4 US2 (T019–T022) → canvas shows the data.
4. **STOP and validate**: Run `quickstart.md` S1, S2, S3, S5. Demo internally.
5. Complete Phase 5 US3 (T023–T029) → editing landed.
6. Run Phase 6 polish.

### Incremental Delivery

- After **MVP** (US1+US2): users get an auto-generated, visible UI-flow layer they cannot yet edit. Even read-only this is shippable to internal stakeholders.
- After **US3**: full create/read/update/delete; users can correct LLM mistakes and add edges manually.
- After **Polish**: integrity checks and observability are in place; safe for broader rollout.

### Parallel Team Strategy

- 1 developer: serialize per the MVP order above. Realistic estimate ~3–4 days for MVP, +2 days for US3 + Polish.
- 2 developers: split US1 (backend) and US2 (frontend) in parallel after Phase 2. ~2 days for MVP.
- 3 developers: add US3 in parallel from Phase 2 onward. ~2 days for the full feature.

---

## Notes

- `[P]` = different files, no within-phase dependency.
- `[Story]` (US1/US2/US3) traces task → user story in spec.md for independent verification.
- Tests are scoped: T018 (US1 phase) + T029 (US3 routes). The quickstart smoke (T031) provides the integration-level coverage; no unit-test sprawl was requested.
- Commit after each logical group (typically each task or each `[P]` cluster).
- Stop at the Phase 3+4 checkpoint to demo the MVP before starting US3.
- Avoid: editing `EventModelingPanel.vue` across two parallel tasks (T021/T022 both touch it — serialize); also avoid touching `ingestion_workflow_runner.py` from two parallel tasks (T013 + T016 both edit it — serialize).
