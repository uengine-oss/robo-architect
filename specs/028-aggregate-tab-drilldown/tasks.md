---
description: "Task list for Aggregate Tab Drill-Down & Canvas UX"
---

# Tasks: Aggregate Tab Drill-Down & Canvas UX

**Input**: Design documents from `/specs/028-aggregate-tab-drilldown/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contract.md, quickstart.md

**Tests**: No automated test tasks — the repo has no frontend unit-test harness for canvas features; verification is manual via `quickstart.md` (consistent with specs 024–027).

**Organization**: Tasks are grouped by user story. This is a **frontend-only** feature — no backend (`api/`), no Neo4j schema changes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: User story the task serves (US1–US4)
- Exact file paths are included in every task

## Path Conventions

All paths are under `frontend/src/features/canvas/` (the existing `canvas` feature module). Repo root: `/Users/uengine/robo-architect/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project structure or dependencies are needed (existing Vue 3 + Pinia + Vue Flow app). Only environment readiness.

- [X] T001 Start backend (`uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`) and frontend (`npm run dev` in `frontend/`) per `specs/028-aggregate-tab-drilldown/quickstart.md`; confirm the graph has at least one Bounded Context with ≥ 2 aggregates for iterative verification

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend the `aggregateViewer` Pinia store so it can show a single aggregate (not just a whole Bounded Context) and carry cross-tab focus intent. **Blocks US1, US2, US3.** (US4 is independent and does not depend on this phase.)

**⚠️ CRITICAL**: All Phase 2 tasks edit the same file (`aggregateViewer.store.js`) and MUST be done sequentially. US1/US2/US3 work cannot begin until this phase is complete.

- [X] T002 In `frontend/src/features/canvas/aggregateViewer.store.js`: add `visibleAggregateIds` (`ref(new Set())`) state; change the `filteredBoundedContexts` computed so each returned BC's `aggregates` array is filtered to entries whose `id ∈ visibleAggregateIds` (omit BCs left with zero visible aggregates); clear `visibleAggregateIds` inside `clearAllBCs`; add `visibleAggregateIds` to the store's return object
- [X] T003 In `frontend/src/features/canvas/aggregateViewer.store.js`: update `fetchAggregatesForBC(bcId)` so that, after the BC tree is loaded, every aggregate id of that BC is added to `visibleAggregateIds` (preserves the existing "show all aggregates of a dropped BC" behavior — FR-011)
- [X] T004 In `frontend/src/features/canvas/aggregateViewer.store.js`: add a `fetchAggregate(aggregateId, bcId)` action — if `bcId` is missing, resolve it via `GET /api/graph/expand-with-bc/{aggregateId}` (parent `BoundedContext` node in `nodes[]`); load the owning BC tree via `GET /api/contexts/{bcId}/full-tree` only if that BC is not already in `boundedContexts`; add **only** `aggregateId` to `visibleAggregateIds`; set the existing `error` ref if the aggregate is absent from the fetched tree (FR-015); export `fetchAggregate`
- [X] T005 In `frontend/src/features/canvas/aggregateViewer.store.js`: add `pendingFocus` (`ref(null)`) state plus `focusAggregate(aggregateId, bcId)` (sets `pendingFocus = { aggregateId, bcId }`) and `consumeFocus()` (returns and nulls `pendingFocus`) actions; clear `pendingFocus` inside `clearAllBCs`; export `focusAggregate` and `consumeFocus`

**Checkpoint**: Store can load/display a single aggregate and carry a one-shot focus target. US1/US2/US3 can now begin.

---

## Phase 3: User Story 1 - Drill into an aggregate from the Design tab (Priority: P1) 🎯 MVP

**Goal**: A "View Detail" action in the Design-tab aggregate property panel switches to the Aggregate tab and shows the selected aggregate's detail, focused.

**Independent Test**: In the Design tab, select an aggregate, open its property panel, click "View Detail" → the app switches to the Aggregate tab with that aggregate loaded and centered (quickstart S1, S2).

### Implementation for User Story 1

- [X] T006 [P] [US1] In `frontend/src/features/canvas/ui/AggregatePanel.vue`: add an `onMounted` focus-consume routine that calls `aggregateViewerStore.consumeFocus()`; when it returns a target `{ aggregateId, bcId }`, ensure the aggregate is loaded (call `fetchAggregate` if `aggregateId ∉ visibleAggregateIds`) and then `fitView({ nodes: ['agg-container-' + aggregateId], padding: 0.3 })`, sequencing the `fitView` after the existing node-build/`nodes-initialized` settle (mirror the existing post-drop `setTimeout(fitView, …)` pattern)
- [X] T007 [US1] In `frontend/src/features/canvas/ui/InspectorPanel.vue`: `inject('activeTab')`; import/use the `aggregateViewer` store; render a "View Detail" button in the aggregate property panel section (near the `PropertyEditorTable` shown when `showPropertyEditor` is true), visible/enabled **only** when the selected node is an Aggregate (`nodeLabel === 'Aggregate'`) — FR-006
- [X] T008 [US1] In `frontend/src/features/canvas/ui/InspectorPanel.vue`: implement the "View Detail" click handler — resolve `bcId` from the selected node (`node.parentNode`, else `node.data.bcId`, else leave undefined for `fetchAggregate`'s fallback); call `aggregateViewerStore.focusAggregate(aggregateId, bcId)`; set the injected `activeTab.value = 'Aggregate'`

**Checkpoint**: US1 fully functional — drill-down from Design tab works end to end.

---

## Phase 4: User Story 2 - Selection carries over when switching tabs manually (Priority: P2)

**Goal**: With exactly one aggregate selected in the Design tab, switching to the Aggregate tab via the tab bar auto-loads and focuses that aggregate.

**Independent Test**: Select one aggregate in the Design tab, click the Aggregate tab in the tab bar → that aggregate is loaded and focused with no extra action; with zero/multiple/non-aggregate selection, nothing is forced (quickstart S3, S4).

### Implementation for User Story 2

- [X] T009 [US2] In `frontend/src/features/canvas/ui/AggregatePanel.vue`: extend the `onMounted` focus-consume routine (from T006) — when `consumeFocus()` returns `null`, fall back to the Design canvas selection (`useCanvasStore().selectedNodes`); if **exactly one** selected node has `data?.type === 'Aggregate'`, derive `{ aggregateId: node.id, bcId: node.parentNode }` and treat it as the focus target; for zero, multiple, or non-aggregate selections do nothing (FR-008)

**Checkpoint**: US1 and US2 both work — explicit drill-down and implicit tab-switch carry-over.

---

## Phase 5: User Story 3 - Drop an aggregate directly onto the Aggregate tab canvas (Priority: P2)

**Goal**: Dragging an aggregate item from the navigator onto the Aggregate canvas shows that aggregate's detail; additive and de-duplicated; Bounded Context drop unchanged.

**Independent Test**: On the Aggregate tab, drag an aggregate from the navigator onto the canvas → its detail appears; drop a second → both shown; re-drop the first → no duplicate; drop a Bounded Context → all its aggregates still appear (quickstart S5, S6).

### Implementation for User Story 3

- [X] T010 [US3] In `frontend/src/features/canvas/ui/AggregatePanel.vue`: extend `handleDrop` — add a branch for `nodeType === 'Aggregate'` that resolves `aggregateId` from the drag payload (`nodeId`) and `bcId` from `nodeData` if present, calls `aggregateViewerStore.fetchAggregate(aggregateId, bcId)`, then `fitView({ nodes: ['agg-container-' + aggregateId], padding: 0.3 })` after the layout settles; leave the existing `nodeType === 'BoundedContext'` branch unchanged (FR-009, FR-010, FR-011)
- [X] T011 [US3] In `frontend/src/features/canvas/ui/AggregatePanel.vue`: update the empty-state hint text (`aggregate-viewer__empty` block, currently "Drag a Bounded Context from the navigator…") to also mention dragging an aggregate

**Checkpoint**: US1, US2, US3 all independently functional.

---

## Phase 6: User Story 4 - Aggregate boundary is visually identifiable (Priority: P3)

**Goal**: The aggregate grouping box has a subtle yellow tint and an `«Aggregate»` stereotype label, legible in both themes.

**Independent Test**: Load any aggregate on the Aggregate canvas → grouping box shows a subtle yellow tint and an `«Aggregate»` stereotype; toggle light/dark theme → both stay legible (quickstart S7). **This story does not depend on Phase 2** and can be done at any time.

### Implementation for User Story 4

- [X] T012 [US4] In `frontend/src/features/canvas/ui/nodes/AggregateContainerNode.vue`: replace the neutral fill (`background: var(--color-bc-bg)`, dark `#373a40` header, `--color-bc-border`) with a subtle aggregate-yellow tint derived from `--color-aggregate` (low-opacity body tint, slightly stronger header tint, yellow border); provide explicit values under both `:root.theme-light` and `:root.theme-dark` so inner cards stay legible in each theme (FR-012, FR-014)
- [X] T013 [US4] In `frontend/src/features/canvas/ui/nodes/AggregateContainerNode.vue`: add an `«Aggregate»` stereotype indicator (small/uppercase) in the `container-header` label region, alongside the existing name text (FR-013)
- [X] T014 [P] [US4] In `frontend/src/features/canvas/ui/AggregatePanel.vue`: align the minimap `getNodeColor` mapping for `aggregateContainer` to the yellow family for visual consistency (optional polish)

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation and regression confirmation.

- [X] T015 Run all `quickstart.md` scenarios S1–S8 against the running app and confirm each behaves as specified
- [X] T016 Regression check — confirm Bounded Context drop still shows all aggregates (S6) and no aggregate ever appears twice when reached via drop + drill + tab-switch on the same aggregate (S5, FR-005/FR-010)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks US1, US2, US3.** Does NOT block US4.
- **US1 (Phase 3)**: Depends on Phase 2 (needs `consumeFocus`, `fetchAggregate`, `focusAggregate`, visibility filter).
- **US2 (Phase 4)**: Depends on Phase 2 AND on T006 (extends the same `onMounted` routine introduced in US1).
- **US3 (Phase 5)**: Depends on Phase 2. Logically independent of US1/US2 but edits the same file (`AggregatePanel.vue`).
- **US4 (Phase 6)**: Depends only on Setup — independent of Phase 2 and all other stories.
- **Polish (Phase 7)**: Depends on all desired user stories being complete.

### Within Each User Story

- US1: T006 (AggregatePanel) and T007 (InspectorPanel) touch different files. T007 → T008 are sequential (same file).
- US2: T009 extends T006's routine — sequential after US1.
- US3: T010 → T011 sequential (same file).
- US4: T012 → T013 sequential (same file); T014 is a different file.

### Parallel Opportunities

- **US4 can run fully in parallel with Phase 2 and with US1/US2/US3** — it only touches `AggregateContainerNode.vue` (+ optional `getNodeColor`), with no store dependency.
- Within US1: **T006 [P] and T007** can run in parallel (different files).
- Within US4: **T014 [P]** can run alongside T012/T013 (different file).
- **Caution**: US1, US2, US3 (and T014) all edit `AggregatePanel.vue`. They are logically independent but should be implemented sequentially, or by one developer, to avoid merge conflicts in that file. They are NOT safe to parallelize across developers.
- Phase 2 tasks (T002–T005) all edit `aggregateViewer.store.js` — strictly sequential, no `[P]`.

---

## Parallel Example

```bash
# US4 styling can proceed immediately, in parallel with Phase 2 store work:
Task: "T012 [US4] Yellow tint on AggregateContainerNode.vue"
Task: "T013 [US4] «Aggregate» stereotype on AggregateContainerNode.vue"

# Within US1, after Phase 2 completes — different files, run together:
Task: "T006 [US1] onMounted focus-consume routine in AggregatePanel.vue"
Task: "T007 [US1] View Detail button in InspectorPanel.vue"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (T001).
2. Phase 2: Foundational (T002–T005) — **critical, blocks US1**.
3. Phase 3: US1 (T006–T008).
4. **STOP and VALIDATE**: quickstart S1 + S2 — drill-down works.
5. Demo MVP.

### Incremental Delivery

1. Setup + Foundational → store ready.
2. US1 → validate S1/S2 → demo (MVP).
3. US2 → validate S3/S4 → demo.
4. US3 → validate S5/S6 → demo.
5. US4 → validate S7 → demo (can also be delivered first, independently).
6. Polish (T015–T016) → full quickstart pass.

### Notes

- `[P]` = different files, no incomplete dependency.
- `[Story]` label maps each task to its user story for traceability.
- No backend, no Neo4j schema, no new endpoints — `expand-with-bc` and `full-tree` are reused as-is.
- Commit after each task or logical group; verify against quickstart at each checkpoint.
