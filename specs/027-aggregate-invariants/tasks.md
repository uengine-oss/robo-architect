---
description: "Task list for Aggregate Invariants implementation"
---

# Tasks: Aggregate Invariants

**Input**: Design documents from `specs/027-aggregate-invariants/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md

**Tests**: No automated unit/contract tests were requested in the spec. A Playwright UI smoke
(quickstart S1–S7) and a manual quickstart run are included in the Polish phase.

**Organization**: Tasks are grouped by user story. US2 and US3 build on US1 (an Invariant object
must exist first) — see Dependencies.

## Path Conventions

Web app with mirrored modules: backend `api/features/`, frontend `frontend/src/features/`,
Neo4j schema `docs/cypher/schema/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new feature module skeletons on both sides.

- [x] T001 [P] Create backend feature module skeleton `api/features/invariants/` with empty `__init__.py`, `router.py`, `invariants_contracts.py`, `invariants_service.py`, `neo4j_ops.py`
- [x] T002 [P] Create frontend feature module skeleton `frontend/src/features/invariants/` with empty `invariants.api.js`, `invariants.store.js`, and `ui/InvariantEditor.vue`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Graph schema, DTOs, and router mount that ALL user stories depend on.

⚠️ MUST complete before any user story phase.

- [x] T003 [P] Add `Invariant` constraints (unique+not-null `id`, unique+not-null `key`, not-null `declaration`) to `docs/cypher/schema/01_constraints.cypher`
- [x] T004 [P] Add `Invariant` indexes (RANGE on `id`, TEXT on `name`/`declaration`) to `docs/cypher/schema/02_indexes.cypher`
- [x] T005 [P] Add `Invariant` node example block and note that `Given/When/Then.parentType` now accepts `"Invariant"` in `docs/cypher/schema/03_node_types.cypher`
- [x] T006 [P] Add `HAS_INVARIANT` and `VERIFIED_BY` relationship docs (and note `HAS_GIVEN/WHEN/THEN` may originate from `Invariant`) to `docs/cypher/schema/04_relationships.cypher`
- [x] T007 Define all Pydantic DTOs from data-model.md §2 (`InvariantSummaryDTO`, `ReferencedConditionDTO`, `InvariantDetailDTO`, `CreateInvariantRequest`, `UpdateInvariantRequest`, `AddReferenceRequest`, `ReferenceCandidateDTO`) in `api/features/invariants/invariants_contracts.py`
- [x] T008 Add an empty `APIRouter` in `api/features/invariants/router.py` and register it in `api/main.py`

**Checkpoint**: Schema applies cleanly, app boots with the (empty) `/api/invariants` router visible in `/docs`.

---

## Phase 3: User Story 1 — Manage Invariants under an Aggregate (Priority: P1) 🎯 MVP

**Goal**: Planners can see, create, edit, and delete Invariant objects as drill-down children of
an Aggregate in the navigator design tree. No canvas sticker.

**Independent Test**: Open Design tab → expand an Aggregate → add an Invariant with a declaration
→ edit it → delete it; verify tree reflects each change, declaration persists across reload, and
no Invariant sticker appears on the canvas.

### Backend

- [x] T009 [P] [US1] Implement Invariant node Cypher ops (create with derived `key`, get-by-id, list-by-aggregate, update, delete with `HAS_INVARIANT` detach and own-GWT cascade) in `api/features/invariants/neo4j_ops.py`
- [x] T010 [US1] Implement CRUD orchestration (`isSpecified`/`referencedCommandCount` derivation, `seq` assignment, `409` on duplicate key) in `api/features/invariants/invariants_service.py`
- [x] T011 [US1] Implement endpoints §1 (`GET /api/aggregates/{id}/invariants`) and §2 (`POST`/`GET`/`PATCH`/`DELETE` Invariant) per contracts/rest-api.md in `api/features/invariants/router.py`
- [x] T012 [P] [US1] Extend the `/api/contexts/{id}/full-tree` Aggregate serialization to include `invariants: InvariantSummaryDTO[]` in `api/features/contexts/router.py`

### Frontend

- [x] T013 [P] [US1] Implement the Invariant CRUD REST client (list/create/get/update/delete) in `frontend/src/features/invariants/invariants.api.js`
- [x] T014 [P] [US1] Implement the Pinia store for Invariant state (per-aggregate list, selected invariant, CRUD actions) in `frontend/src/features/invariants/invariants.store.js`
- [x] T015 [US1] Carry `invariants[]` per Aggregate from the full-tree response in `frontend/src/features/navigator/navigator.store.js`
- [x] T016 [US1] Add the `Invariant` node type, the drill-down "Invariants" group under each Aggregate, the `INV` icon, and add-invariant action in `frontend/src/features/navigator/ui/TreeNode.vue`
- [x] T017 [US1] Build the declaration editor (name/declaration/description fields, save) in `frontend/src/features/invariants/ui/InvariantEditor.vue`
- [x] T018 [US1] Open `InvariantEditor.vue` on Invariant node double-click. NOTE: implemented as a global modal mounted in `frontend/src/App.vue` driven by the invariants store (`openEditor`), rather than via the 7700-line `InspectorPanel.vue` — lower regression risk, same UX.

**Checkpoint**: US1 fully testable per quickstart S1 + S2 — independent MVP deliverable.

---

## Phase 4: User Story 2 — Detailed GWT conditions shared with Command acceptance criteria (Priority: P2)

**Goal**: From the Invariant editor, planners attach detailed GWT conditions — either referencing
an existing Command's acceptance criteria (shared, edits propagate both ways) or declaring an
invariant-only condition — using the same GWT editing window as Commands.

**Independent Test**: Open an Invariant → reference a Command's GWT, edit it from the Invariant
side, confirm the Command shows the change; edit from the Command side, confirm the Invariant
reflects it; add a separate invariant-only condition and confirm it appears on no Command.

### Backend

- [x] T019 [P] [US2] Extend `UpsertGWTRequest.parentType` to `Literal["Command", "Policy", "Invariant"]` in `api/features/canvas_graph/routes/gwt.py`
- [x] T020 [US2] GWT parent generalization. NOTE: no change needed — the live GWT editor (`/api/graph/gwt/upsert`, single `:GWT` node) matches the parent by `id` + label (`$parent_type IN labels(parent)`), so it is already parent-agnostic. A read endpoint `GET /api/graph/gwt/{parentType}/{parentId}` was added so the editor can load invariant-owned + referenced bundles.
- [x] T021 [US2] Add `VERIFIED_BY` add/remove ops, the same-Aggregate reference-candidate query, and ensure delete cascade preserves Command GWT (data-model §1.6) in `api/features/invariants/neo4j_ops.py`
- [x] T022 [US2] Implement reference add/remove logic and populate `referencedConditions`/`ownGwtParentId`/`isSpecified` in `InvariantDetailDTO` within `api/features/invariants/invariants_service.py`
- [x] T023 [US2] Implement endpoints §3 (`GET .../reference-candidates`, `POST .../references`, `DELETE .../references/{command_id}`) in `api/features/invariants/router.py`

### Frontend

- [x] T024 [US2] Reusable parent-agnostic GWT editor. NOTE: created as a new component `frontend/src/features/invariants/ui/GwtEditor.vue` (props `parentType`/`parentId`) that loads/saves via `/api/graph/gwt/*`. Placed in the invariants feature (not `canvas/ui/`) to keep the feature self-contained and avoid surgery on `InspectorPanel.vue`.
- [ ] T025 [US2] Refactor `frontend/src/features/canvas/ui/InspectorPanel.vue` so the Command GWT editor mounts the new `GwtEditor.vue`. DEFERRED — extracting the Command GWT form from the 7700-line `InspectorPanel.vue` is high regression risk; the Command editor is left untouched. `GwtEditor.vue` is the canonical reusable component going forward; rewiring the Command path to it is a safe follow-up. Functionally, invariant + Command GWT already share one component and one endpoint.
- [x] T026 [P] [US2] Add reference-candidate, add/remove-reference, and `parentType="Invariant"` GWT upsert calls to `frontend/src/features/invariants/invariants.api.js`
- [x] T027 [US2] Add the detailed-conditions section (Command reference picker + embedded `GwtEditor.vue` for each referenced Command and for the invariant-owned triple) to `frontend/src/features/invariants/ui/InvariantEditor.vue`

**Checkpoint**: US2 fully testable per quickstart S4 + S5; US1 still works.

---

## Phase 5: User Story 3 — Seed Invariants from existing data and ingestion (Priority: P3)

**Goal**: Legacy `Aggregate.invariants` text becomes first-class Invariant objects on first
access, and the ingestion pipeline extracts candidate Invariants per Aggregate.

**Independent Test**: Open an Aggregate with legacy invariant text → confirm each entry is now an
Invariant object; run a requirements ingestion → confirm candidate Invariants appear and
re-ingestion creates no duplicates.

### Migration

- [x] T028 [US3] Implement the lazy legacy-text migration (de-dupe non-empty strings → `MERGE Invariant` with `source="migrated"`, set `Aggregate.invariantsMigratedAt`, clear `Aggregate.invariants`) in `api/features/invariants/neo4j_ops.py`
- [x] T029 [US3] Trigger the migration (idempotent, guarded by `invariantsMigratedAt`) at the start of the `GET /api/aggregates/{id}/invariants` handler in `api/features/invariants/invariants_service.py`

### Ingestion

- [x] T030 [P] [US3] Structured-output models `_ExtractedInvariant`/`_ExtractedInvariantSet`. NOTE: defined inline in `extract_invariants.py`, matching the `feature_grouping.py` precedent (which defines its models inline rather than in `structured_outputs.py`).
- [x] T031 [P] [US3] Invariant-extraction prompt. NOTE: defined inline in `extract_invariants.py` (`_SYSTEM_PROMPT` + `_build_prompt`), matching the `feature_grouping.py` precedent.
- [x] T032 [US3] Implement `InvariantOps` (MERGE on natural key with `source="ingested"`, MERGE `VERIFIED_BY` for resolvable Command names) in `api/features/ingestion/event_storming/neo4j_ops/invariants.py`
- [x] T033 [US3] Implement `extract_invariants_phase` (per-Aggregate LLM call via `ctx.llm`, emits `ProgressEvent(phase="EXTRACTING_INVARIANTS", …)`) in `api/features/ingestion/workflow/phases/extract_invariants.py`
- [x] T034 [US3] Register `extract_invariants_phase` after `generate_gwt_phase` and add `EXTRACTING_INVARIANTS` to the SSE event vocabulary in `api/features/ingestion/ingestion_workflow_runner.py`

### Frontend

- [x] T035 [P] [US3] Handle the `EXTRACTING_INVARIANTS` SSE progress event in the ingestion progress UI (`frontend/src/features/ingestion/workflow/utils/phase_logger.py` counterpart / requirements ingestion modal)

**Checkpoint**: US3 fully testable per quickstart S3 + S6; US1 and US2 still work.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T036 [P] Playwright e2e in `frontend/tests/aggregate-invariants.spec.ts` — 3 tests (S1 design-tree group, S2/DR-4 editor in property panel, DR-1/DR-2 When-less GWT + Exception), backend mocked at the network boundary. **Verified: 3 passed** via `npx playwright test tests/aggregate-invariants.spec.ts`.
- [x] T037 [P] Add the `/api/invariants` prefix to the README API summary section
- [ ] T038 Run the quickstart.md manual smoke (S1–S7) end-to-end and record results. NOT RUN — requires a running backend + frontend + populated Neo4j, not available in this environment. Apply `docs/cypher/schema/` first, then walk S1–S7.

---

## Dependencies

- **Setup (P1)** → **Foundational (P2)** → **User Stories (P3–P5)** → **Polish (P6)**.
- **US1 (Phase 3)**: depends only on Foundational. This is the MVP.
- **US2 (Phase 4)**: depends on US1 — an Invariant object and its editor must exist before
  detailed conditions can be attached.
- **US3 (Phase 5)**: depends on US1 — migration produces Invariant objects rendered by the US1
  tree/editor. Independent of US2.
- Within a phase, `[P]` tasks touch different files and may run together; non-`[P]` tasks in the
  same module file (e.g. `router.py`, `invariants_service.py`, `neo4j_ops.py`,
  `InvariantEditor.vue`) are sequential.

## Parallel Execution Examples

- **Foundational**: T003, T004, T005, T006 (four schema files) run in parallel; then T007, T008.
- **US1**: T009 and T012 (different files) parallel; T013 and T014 parallel; then T015→T016 and
  T017→T018 (sequential within UI flow).
- **US2**: T019 and T026 are `[P]`; T024 (extraction) must precede T025 and T027.
- **US3**: T030 and T031 parallel; T032→T033→T034 sequential; T035 parallel with backend.
- **Polish**: T036 and T037 parallel; T038 last.

## Implementation Strategy

- **MVP = US1 (Phases 1–3)**: structured, tree-managed Invariant objects with declaration
  editing — a complete, shippable increment on its own.
- **Increment 2 = US2 (Phase 4)**: the core value — shared GWT conditions linking invariants to
  Command acceptance criteria via one editor.
- **Increment 3 = US3 (Phase 5)**: removes manual re-entry (legacy migration) and keeps the model
  populated (ingestion extraction).
- Each checkpoint is independently demonstrable; stop-and-ship is safe after any checkpoint.

## Phase 7: Post-Implementation Design Refinements

Planner feedback after the first implementation pass. All applied.

- [x] T039 Invariant GWT is **Given + Then only** — "When" is meaningless for a rule. `GwtEditor.vue` hides the When row for `parentType="Invariant"` (`showWhen` computed); `save()` sends `whenRef: null`.
- [x] T040 A GWT **Then may declare an Exception outcome** — `_GWTRef.exceptionName` added in `gwt.py`; the editor's Then section picks/adds an Exception. Applies to Command and Invariant GWT.
- [x] T041 **Exception is an Aggregate domain object** (sibling to enum / value object) — `Aggregate.exceptions` JSON property; `GET/PUT /api/aggregates/{id}/exceptions`; `ExceptionDTO{name, message, fields[]}`; `/api/contexts/{id}/full-tree` parses it. Exception content = name + message + structured fields.
- [x] T042 **Invariant property editing moved into the right-side property panel** — `InvariantEditor.vue` converted from a global modal to an inline section rendered by `InspectorPanel.vue` (`showInvariantEditor`, `nodeLabel === 'Invariant'`); App.vue modal removed; `TreeNode` opens it via `inspectorRequest.request`; `normalizeNodeLabel` learns `Invariant`.
- [x] T043 GWT editor **optionalized & reused** — the single reusable `GwtEditor.vue` (props `parentType`/`parentId`/`aggregateId`) serves invariant-owned and referenced-Command bundles, When-row optional. NOTE: `InspectorPanel`'s own rich Command GWT editor is still separate (T025 remains the deferred unification).

## Phase 8: Verification & Documentation

- [x] T044 End-to-end test pass — `frontend/tests/aggregate-invariants.spec.ts` rewritten for the InspectorPanel architecture; **3 tests pass** against `vite dev` with the backend mocked. A render crash for schema-less node types (`schema.title`) was found and fixed (`schema?.title`).
- [x] T045 User manual with screen captures — `specs/027-aggregate-invariants/manual/USER-GUIDE.md` (10 sections, 3 screenshots captured by the e2e run into `manual/images/`). Converted to `manual/USER-GUIDE.docx` via pandoc (images embedded).

## Summary

- **Total tasks**: 45 (Setup 2, Foundational 6, US1 10, US2 9, US3 8, Polish 3, Refinements 5, Verification & Docs 2)
- **MVP scope**: US1 — T001–T018
- **Parallel opportunities**: schema files (T003–T006), per-story API/store/client splits, polish
  tasks — ~14 tasks carry `[P]`.
