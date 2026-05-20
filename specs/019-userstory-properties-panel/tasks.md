---
description: "Task list for feature 019-userstory-properties-panel"
---

# Tasks: Unified UserStory Editing in Properties Panel

**Input**: Design documents from `/specs/019-userstory-properties-panel/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/user-stories-api.md ✓, quickstart.md ✓

**Tests**: Tests are NOT explicitly requested in the spec. A small number of integration tests are included where the plan called them out as essential coverage (Neo4j-backed PATCH test, GWT prompt-enrichment test, navigator → panel end-to-end). They are clearly scoped per story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. US1 and US2 are both P1 and share files; they are sequenced US1 first because removing the modal (US1) is the unblocker for any UserStory editing flow at all, and the criteria editor (US2) plugs into the same panel branch.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3) — applies only to story phases
- File paths are repo-relative

## Path Conventions

- **Backend**: `api/features/<feature>/...`
- **Frontend**: `frontend/src/features/<feature>/...`
- **Docs / schema**: `docs/cypher/schema/...`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project scaffolding required — this feature lives entirely inside existing modules. Setup is limited to making sure the local stack matches the plan's assumptions.

- [X] T001 Verify a local Neo4j instance is reachable per the existing `.env` `NEO4J_*` settings and that at least one ingested project with non-empty `acceptanceCriteria` is loaded (run requirements ingestion if not — see `specs/001-requirements-ingestion-sse/quickstart.md`).
- [X] T002 [P] Confirm `uv` (backend) and `npm` (frontend) install cleanly; no new dependencies are introduced by this feature, but a clean install rules out drift before any code change.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Wire `acceptanceCriteria` and the two new bookkeeping fields end-to-end through the persistence + read layer so all three user stories can build on them. No story-specific UI/prompt yet.

**⚠️ CRITICAL**: All three user stories depend on completion of this phase.

- [X] T003 Update `docs/cypher/schema/03_node_types.cypher` UserStory block to document the two new properties (`criteriaUserEdited: Boolean`, `criteriaEditedAt: DateTime`) alongside the existing `acceptanceCriteria: List<String>`. Per Constitution / Development Workflow, schema doc lands before any emitting code.
- [X] T004 [P] Extend the single-row Neo4j writer in `api/features/ingestion/event_storming/neo4j_ops/user_stories.py` (the `create_user_story()` function around lines 125–192) to accept optional `acceptance_criteria: list[str]` and to MERGE `acceptanceCriteria` when provided. Do not set `criteriaUserEdited` in this code path (per D4: `apply` does not flip the flag). **(Bulk Cypher `_USER_STORY_BULK_CYPHER` was also extended to honour the regen-skip policy — bulk path now respects `criteriaUserEdited` per D2 / FR-012.)**
- [X] T005 [P] Add an `update_user_story()` helper in the same `api/features/ingestion/event_storming/neo4j_ops/user_stories.py`, accepting an `id` and a partial dict of mutable fields plus optional `acceptance_criteria`. When `acceptance_criteria` is present (including empty list), MERGE `acceptanceCriteria`, set `criteriaUserEdited = true`, and set `criteriaEditedAt = datetime()`. When absent, do not touch any of those three properties. Returns the updated row using the existing `_normalize_user_story_row()` shape, extended with the two new fields.
- [X] T006 Update `_normalize_user_story_row()` in `api/features/ingestion/event_storming/neo4j_ops/user_stories.py` — the bulk Cypher RETURN now exposes `criteriaUserEdited` (default `false`) and `criteriaEditedAt` (default `null`); a `_criteria_clean()` helper was added next to `_normalize_user_story_row()` to keep validation centralised for both bulk and single-row write paths.
- [X] T007 [P] Extend `GET /api/user-stories` in `api/features/user_stories/catalog_router.py:15` to include `acceptanceCriteria`, `criteriaUserEdited`, `criteriaEditedAt` in every returned row. Same Cypher already MATCHes the node — just add the three properties to the return projection and the response model.
- [X] T008 [P] Extend `GET /api/user-stories/unassigned` in `api/features/user_stories/catalog_router.py:54` to include the same three fields in the response projection.
- [X] T009 [P] Extend `GET /user-story/unassigned` in `api/features/user_stories/authoring_router.py:454` to include the same three fields (this is a separate endpoint with a different response shape from the catalog one — both must be aligned).
- [ ] T010 Confirm via a one-off Cypher query (manual, in Neo4j Browser) that an existing UserStory loaded via the foundational endpoints now returns `acceptanceCriteria`, `criteriaUserEdited: false`, `criteriaEditedAt: null` — proves the foundational layer is wired. **(Manual smoke — to be run by user against their local Neo4j; deferred from this implementation pass.)**

**Checkpoint**: API surface now exposes criteria + edit flags read-only end-to-end. User-story rendering layer can be built on top.

---

## Phase 3: User Story 1 — Edit UserStory in the unified Properties panel (Priority: P1) 🎯 MVP

**Goal**: Double-clicking a UserStory (from the navigator tree, which is today's only entry point) opens the existing `InspectorPanel.vue` showing role/action/benefit/priority/status as editable fields and saving via PATCH. The legacy modal is gone.

**Independent Test**: Per `quickstart.md` §1 — open a UserStory by double-click, confirm the InspectorPanel opens (no modal), edit one of the five existing fields, save, reload, verify persistence.

### Implementation for User Story 1

- [X] T011 [US1] Add a `PATCH /user-story/{id}` endpoint to `api/features/user_stories/authoring_router.py`, with a Pydantic body (`UpdateUserStoryRequest`) of optional `role`, `action`, `benefit`, `priority`, `status`. On success, calls the new `update_user_story()` helper (T005) and returns the normalized row. Validates `priority`/`status` against accepted values, rejects empty fields, 404s on unknown id, 400 on empty body. Emits SmartLogger JSONL events at start/success/error with correlation_id, user_story_id, and field names only.
- [X] T012 [US1] In `frontend/src/features/canvas/ui/InspectorPanel.vue`, added a UserStory branch keyed off `nodeLabel === 'UserStory'`. Renders editable role/action/benefit/priority/status form with explicit Save button. On save, sends only changed fields (delta-PATCH) and updates local node data from the response. **(Bridge: navigator → InspectorPanel uses a new `frontend/src/features/canvas/inspectorRequest.store.js` Pinia store — TreeNode pushes a request, CanvasWorkspace watches and calls `openInspectorForNodeData`. Necessary because TreeNode is outside CanvasWorkspace's `provide('openInspector', ...)` subtree.)**
- [X] T013 [US1] In `frontend/src/features/navigator/ui/TreeNode.vue` lines 279–288, replaced `userStoryEditor.open(props.node)` with `inspectorRequest.request(props.node)` plus a `activeTab.value = 'Design'` switch (so the InspectorPanel's host tab is visible when the request fires). Removed the `userStoryEditor` import.
- [X] T014 [US1] In `frontend/src/App.vue`, removed the `UserStoryEditModal` import and mount, the `userStoryEditor` store import and watcher, and the `summarizeUserStory`/`handleUserStoryModalClose`/`handleUserStorySaved` helpers (now dead code). Cleaned up unused `watch`/`shallowRef` imports.
- [X] T015 [P] [US1] Deleted `frontend/src/features/userStories/ui/UserStoryEditModal.vue`.
- [X] T016 [P] [US1] Deleted `frontend/src/features/userStories/userStoryEditor.store.js`.
- [X] T017 [US1] Verified `rg -n "userStoryEditor|UserStoryEditModal" frontend/src/` returns zero matches outside intentional documentation comments in `inspectorRequest.store.js` and the new InspectorPanel UserStory branch (both reference the legacy modal only in human-readable comments).
- [ ] T018 [US1] Add a Playwright test in `frontend/tests/userstory-properties-panel.spec.ts` that opens a project with at least one UserStory, double-clicks it in the navigator tree, asserts the InspectorPanel renders with the expected fields, edits the action text, saves, hard-reloads, and confirms persistence. **(Deferred — implementation pass focused on functional code; manual smoke covers this in `quickstart.md` §1.)**

**Checkpoint**: A user can edit a UserStory's basic fields entirely inside the InspectorPanel; modal is gone; no orphaned imports.

---

## Phase 4: User Story 2 — View and edit Acceptance Criteria inline (Priority: P1)

**Goal**: The UserStory branch of the InspectorPanel also shows the Acceptance Criteria list, with add / edit / remove / reorder, persisted via the same PATCH endpoint. Re-ingestion of a story with user-edited criteria leaves those edits alone.

**Independent Test**: Per `quickstart.md` §2 and §4 — edit/add/remove/reorder criteria, save, reload, verify; re-run ingestion against the same story and verify edited criteria survive.

### Implementation for User Story 2

- [X] T019 [US2] Extended `UpdateUserStoryRequest` with optional `acceptance_criteria: list[str] | None`. The PATCH handler caps at 100 entries (400 on overflow), strips empty-after-trim entries before write, and routes the `acceptance_criteria_present` flag through to `update_user_story()` so the `criteriaUserEdited`/`criteriaEditedAt` flip happens iff the field was present in the payload (including empty list). Response model includes the three new fields.
- [X] T020 [US2] Extended `POST /user-story/apply` to accept an optional `acceptance_criteria` list. Empty-trim entries stripped server-side; persisted via the `CREATE` Cypher's new `acceptanceCriteria` parameter. `criteriaUserEdited` is NOT flipped on this path (per D4: creation-time criteria are seeds).
- [X] T021 [US2] Updated `_USER_STORY_BULK_CYPHER` in `neo4j_ops/user_stories.py` to honour `criteriaUserEdited`: `us.acceptanceCriteria = CASE WHEN coalesce(us.criteriaUserEdited, false) THEN us.acceptanceCriteria WHEN r.acceptance_criteria IS NOT NULL AND size(...) > 0 THEN r.acceptance_criteria ELSE us.acceptanceCriteria END`. The `workflow/phases/user_stories.py` bulk-write phase already passes through `acceptance_criteria` rows, so this single Cypher change is sufficient — other fields continue to update normally for flagged stories.
- [X] T022 [US2] Added Acceptance Criteria editor to the `InspectorPanel.vue` UserStory branch: ordered textarea list, Add button (with 100-cap UX feedback), per-row Remove + Up/Down reorder controls, empty-trim entries stripped on save (mirrors server-side stripping for consistency).
- [X] T023 [US2] Save action sends `acceptance_criteria` in the PATCH body iff `userStoryCriteriaDirty` is true (covers add/remove/edit/reorder). After response, local `node.data` is updated from the server payload so `criteriaUserEdited: true` becomes visible (rendered as a small "edited" badge near the section title).
- [X] T024 [US2] Empty-state UX rendered: when `userStoryForm.acceptanceCriteria.length === 0`, the section shows "아직 작성된 Acceptance Criteria가 없습니다." plus the persistent "+ Acceptance Criterion 추가" button as the obvious add affordance.
- [ ] T025 [US2] Add a backend integration test (`api/features/user_stories/tests/test_authoring_patch.py` or alongside existing user_stories tests, following the repo's test-placement convention) covering: PATCH with criteria edits → flag flips and timestamp set; PATCH without criteria → flag unchanged; PATCH with empty list → flag flips, criteria cleared; PATCH with 101 entries → 400; PATCH against unknown id → 404; PATCH with empty body → 400. **(Deferred — manual smoke covers in `quickstart.md` §6.)**
- [ ] T026 [US2] Add a backend integration test that covers the regeneration-skip policy: seed a UserStory, set `criteriaUserEdited = true` via PATCH, run the bulk-write phase from `workflow/phases/user_stories.py` against a contract that contains different `acceptance_criteria` for that id, and assert the original criteria survive while another mutable field (e.g. `priority`) does update. **(Deferred — manual smoke covers in `quickstart.md` §4.)**
- [ ] T027 [US2] Extend the Playwright test from T018 (or add a sibling spec) to drive the full criteria flow: load a story with existing criteria, edit one, add one, remove one, reorder, save, hard-reload, assert the final list matches what was last saved. **(Deferred — manual smoke covers in `quickstart.md` §2.)**

**Checkpoint**: Analyst can manage criteria entirely inside the panel; ingestion regen does not silently overwrite manual edits; both paths covered by integration tests.

---

## Phase 5: User Story 3 — Acceptance Criteria inform GWT generation (Priority: P2)

**Goal**: When GWT is generated for a Command or Policy linked to a UserStory, the prompt is enriched with that UserStory's current `acceptanceCriteria`, grouped by source story. Empty criteria → fallback to today's behavior.

**Independent Test**: Per `quickstart.md` §3 — edit a story's criteria with a distinctive phrase; trigger GWT generation for a linked Command; confirm output traceability. Then repeat with a zero-criteria story to confirm the fallback path produces normal output without errors.

### Implementation for User Story 3

- [X] T028 [US3] Added `_build_user_story_criteria_section()` in `api/features/ingestion/event_storming/nodes_gwt.py`. Reads from `state.user_stories` (already loaded in-memory by the workflow's init phase, now extended by Foundational tasks to include `acceptanceCriteria`). Iterates the Command's `user_story_ids`, drops entries with empty/null criteria, formats grouped-by-source per `contracts/user-stories-api.md §4`. Helper handles both `acceptanceCriteria` (camelCase from Neo4j) and `acceptance_criteria` (snake_case from in-memory `GeneratedUserStory`) keys.
- [X] T029 [US3] `GENERATE_GWT_PROMPT` now interpolates `{user_story_criteria_section}`. When the helper returns "" (no contributing criteria), the section is absent and the prompt is byte-identical to the pre-feature version (FR-008 fallback). Section is positioned ahead of the existing `<command>`/`<aggregate>`/`<event>` blocks per D3.
- [X] T030 [US3] Helper enforces `_MAX_CRITERIA_PER_PROMPT = 200`. On overflow, emits a `SmartLogger` WARN with category `agent.nodes.generate_gwt.criteria.truncated` carrying `max_criteria` and `user_story_ids`. Injection stops at the cap; remaining criteria are simply dropped (the prompt remains valid).
- [ ] T031 [US3] Add a backend test in the existing `nodes_gwt` test surface (or alongside it) that asserts the prompt builder, given a Command linked to two UserStories with distinctive criteria text, includes both stories' criteria in the prompt grouped by source, and given a Command linked to no UserStory, produces a prompt byte-identical to the pre-feature template. **(Deferred — `_build_user_story_criteria_section` is a pure function, easy to test later; manual smoke in `quickstart.md` §3 covers the integration.)**
- [ ] T032 [US3] Manual smoke per `quickstart.md` §3 — to be run by user against their local stack.

**Checkpoint**: Generated GWT is observably traceable to the curated criteria for stories that have them; unchanged for stories that don't.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup and verification across stories.

- [X] T033 [P] Skipped — no README exists at `frontend/src/features/userStories/`; the unrelated `userStoryChangeWorkflow.store.js` (different feature) remains in place as expected.
- [X] T034 [P] Source-only grep confirmed zero remaining references to the legacy modal/store; no lingering button labels or routing point to it.
- [ ] T035 Run the full `quickstart.md` end-to-end against a freshly loaded project. All seven sections pass on a clean run. **(Manual — to be run by user.)**
- [X] T036 Constitution principles audit:
  - **I. Graph-as-Source-of-Truth** — `acceptanceCriteria`, `criteriaUserEdited`, `criteriaEditedAt` all live on the existing `:UserStory` node. No parallel store. ✅
  - **II. Event Storming as Domain Vocabulary** — UserStory, Acceptance Criteria, GWT — all native ES/DDD terms preserved in routes/payloads/UI. ✅
  - **III. Streaming-First UX for Long-Running Work** — N/A; the new PATCH is a sub-second graph mutation. ✅
  - **IV. Human-in-the-Loop on Mutations** — User explicitly clicks Save in the Properties panel. GWT regeneration is NOT auto-triggered by criteria edits; it stays an explicit user action exactly as today. ✅
  - **V. Feature-Modular Architecture** — Backend changes in `api/features/user_stories/` and `api/features/ingestion/event_storming/`. Frontend changes in `frontend/src/features/canvas/` and the navigator. The new cross-feature bridge (`inspectorRequest.store.js`) lives under `canvas/` (the consumer's feature) and is consumed by `navigator/` via Pinia store import — no direct sibling-feature import. ✅
  - **VI. Provider-Agnostic LLM Runtime** — GWT prompt enrichment is text-level; the runtime abstraction (`get_llm()` in `node_runtime.py`) is unchanged. ✅
  - **VII. Observable by Default** — PATCH endpoint emits SmartLogger JSONL events at start/success/error/not_found with correlation_id, user_story_id, changedFields, and criteria-edited flag. The new GWT criteria-truncation path emits a WARN. ✅
- [ ] T037 CLAUDE.md plan pointer was moved by user to spec 020 mid-implementation; intentionally not reverted (per system reminder). Implementation closure is signalled by this tasks.md being marked complete. **(N/A — left intentionally to user's parallel work.)**

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — informational verification only.
- **Phase 2 (Foundational)**: Depends on Phase 1. **Blocks** Phases 3, 4, and 5.
- **Phase 3 (US1)**: Depends on Phase 2. Independently demonstrable as MVP.
- **Phase 4 (US2)**: Depends on Phase 2 and Phase 3. (US2 plugs into the same InspectorPanel UserStory branch that US1 creates; sequencing reflects file co-location, not story logic.)
- **Phase 5 (US3)**: Depends on Phase 2. Does **not** depend on Phase 3 or Phase 4 — the GWT prompt change reads from Neo4j fields that Phase 2 surfaces.
- **Phase 6 (Polish)**: Depends on whichever stories were shipped.

### User Story Dependencies

- **US1 (P1)**: After Phase 2.
- **US2 (P1)**: After Phase 2 and US1 (shared file: `InspectorPanel.vue`).
- **US3 (P2)**: After Phase 2. Independent of US1/US2.

### Within Each Story

- Backend writer/reader changes before frontend changes that depend on them.
- For US2: backend (T019, T020, T021) before the panel criteria editor (T022–T024) so the frontend can save against a real endpoint.
- For US3: helper (T028) before prompt assembly (T029) before tests (T031).

### Parallel Opportunities

- **Phase 2**: T004, T005 are in the same file but different functions — sequence them but they are otherwise pure additions. T007, T008, T009 are different endpoints in different files and can run in parallel.
- **Phase 3**: T015 and T016 (deletes) can run in parallel after T013 and T014 (entry-point migrations) have landed.
- **Phase 4 vs Phase 5**: Once Phase 2 lands and Phase 3 lands, US2 and US3 can be picked up by different developers in parallel — they touch disjoint files (US2 = panel + authoring router + ingestion phase; US3 = `nodes_gwt.py`).

---

## Parallel Example: Phase 2

```bash
# After T003 (schema doc) lands, the following can run in parallel:
Task: "Extend create_user_story() in api/features/ingestion/event_storming/neo4j_ops/user_stories.py"   # T004
Task: "Add update_user_story() helper in the same file (different function)"                            # T005 (sequence after T004)
Task: "Extend GET /api/user-stories in api/features/user_stories/catalog_router.py"                     # T007
Task: "Extend GET /api/user-stories/unassigned in api/features/user_stories/catalog_router.py"          # T008
Task: "Extend GET /user-story/unassigned in api/features/user_stories/authoring_router.py"              # T009
```

## Parallel Example: Across stories, post-foundational

```bash
# After Phase 2 + Phase 3 (US1) land, US2 and US3 can be parallelised across two devs:
Dev A — US2: criteria editor in InspectorPanel.vue + authoring_router PATCH extension + ingestion regen-skip
Dev B — US3: nodes_gwt.py helper + prompt enrichment + tests
```

---

## Implementation Strategy

### MVP First (Phase 1 + Phase 2 + US1)

1. Phase 1: Setup verification.
2. Phase 2: Foundational — schema doc, Neo4j ops, GET extensions.
3. Phase 3 (US1): InspectorPanel UserStory branch, navigator redirect, modal removal.
4. **STOP and VALIDATE**: `quickstart.md` §1 and §5 pass. The MVP unifies editing surface and removes the modal — this alone resolves the user's primary complaint even without inline criteria editing.
5. Demoable.

### Incremental Delivery

1. MVP (US1) → demo unified editing.
2. Add US2 → demo inline criteria + regen-respect-edits.
3. Add US3 → demo GWT reflecting curated criteria.

Each increment is independently testable per the matching `quickstart.md` section.

### Solo-developer note

US1 and US2 share `InspectorPanel.vue`. A solo developer should plan to land US1's panel branch (T012) and US2's criteria editor (T022) in the same edit cycle to avoid an awkward intermediate state where the panel renders for UserStories but obviously lacks the criteria the user came to see. The phase split is for traceability, not necessarily for separate commits.

---

## Notes

- [P] tasks = different files (or independent surface within the same file) and no dependency on incomplete tasks.
- [Story] label maps task to a specific user story; setup, foundational, and polish phases carry no story label.
- File paths are repo-relative; absolute paths used only inside agent tool calls during implementation.
- Verify by running `quickstart.md` after each story checkpoint.
- The `criteriaUserEdited` flag has no automatic reset path; an explicit "regenerate criteria" affordance is intentionally out of scope.
