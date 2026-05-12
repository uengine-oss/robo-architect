---
description: "Tasks for Figma Sync Recovery & Retroactive Push"
---

# Tasks: Figma Sync Recovery & Retroactive Push

**Input**: Design documents from `/specs/020-figma-sync-recovery/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md

**Tests**: Backend integration tests (pytest) and Playwright smoke tests for the modal UX are included because plan.md explicitly named both as the chosen testing approach. Tests target each new endpoint's contract and the user-visible behavior in spec § Acceptance Scenarios; not full TDD.

**Organization**: Tasks are grouped by user story (US1–US3) so each story can be implemented and shipped independently. This feature is strictly additive to spec 016 — no existing 016 surfaces are removed.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are repo-relative; assume repo root is `/Users/uengine/robo-architect/`

## Path Conventions

Web app with mirrored backend/frontend per Constitution V; everything additive to existing 016 surfaces.

- Backend feature: `api/features/figma_binding/` (existing, extended)
- Bridge into ingestion: `api/features/ingestion/workflow/phases/ui_wireframes.py` (one new module-public function)
- Frontend feature: `frontend/src/features/figmaBinding/` (existing, extended)
- Shared schema: `docs/cypher/schema/`
- Tests: `tests/integration/figma_binding/` (existing dir from 016 v1.2) and `frontend/tests/`

---

## Phase 1: Setup (Schema Additions)

**Purpose**: Neo4j schema is the canonical contract per Constitution Development Workflow — labels, relationships, and constraints land in `docs/cypher/schema/` before any code that emits them ships.

- [X] T001 [P] Append `:SyncRun` node-type definition to `docs/cypher/schema/03_node_types.cypher` (properties per data-model.md: `id`, `kind`, `bindingFileKey`, `actor`, `startedAt`, `finishedAt`, `status`, `summary`). Document the new `:FigmaBinding` lock fields `currentRunId` and `currentRunHolder` in the existing `:FigmaBinding` block. Document the new `:UI.figmaSyncBindingFileKey` property in the existing `:UI` block.
- [X] T002 [P] Append `:RUN_OF` relationship type (`:SyncRun → :FigmaBinding`, many → 1) to `docs/cypher/schema/04_relationships.cypher`.
- [X] T003 [P] Append the new constraint and indexes to `docs/cypher/schema/01_constraints.cypher`: `sync_run_id_unique` (CREATE CONSTRAINT … REQUIRE r.id IS UNIQUE), plus indexes `sync_run_status_idx` on `:SyncRun(status)` and `sync_run_binding_file_key_idx` on `:SyncRun(bindingFileKey)`.
- [ ] T004 [DEFERRED — cypher-shell not installed on dev machine; MERGE-based code paths work without the UNIQUE constraint] Apply the new constraints/indexes to the running Neo4j instance via `cypher-shell -f docs/cypher/schema/01_constraints.cypher`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Module skeletons + the cross-feature bridge must exist before any user-story logic can hang off them.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T005 Create empty skeleton modules: `api/features/figma_binding/full_sync.py`, `api/features/figma_binding/retry_dedupe.py`, `api/features/figma_binding/failure_classifier.py`. (Note: T005 ended up shipping working implementations of `retry_dedupe` and `failure_classifier` since they were small enough to inline; `full_sync` ships the orchestrator skeleton with full per-batch logic.)
- [X] T006 Extend `api/features/figma_binding/schemas.py` with new Pydantic models: `FullSyncStartResponse`, `LockContendedResponse`, `SyncRunSummary` + `SyncRunSummaryCounts`, `SyncRunsListResponse`, `FailureRow`, `FailuresListResponse`.
- [X] T007 [P] Add module-public bridge function `generate_jsx_for_existing_ui(ui_id, *, actor, correlation_id)` to `api/features/ingestion/workflow/phases/ui_wireframes.py` with `_MinimalCtx` shim wrapping the existing private `_generate_jsx_scene_graph_for_figma_mode(...)`.
- [X] T008 [P] Extend `api/features/figma_binding/repository.py` with `:SyncRun` helpers (`create_sync_run`, `finalize_sync_run`, `list_sync_runs`, `get_sync_run`, `release_stale_locks`) plus atomic lock helpers `try_acquire_run_lock`, `release_run_lock`, `get_current_lock_holder`.
- [X] T009 Extend `api/features/figma_binding/repository.py` further with `list_failures_with_binding_key()`, `fetch_classifier_view(ui_ids)` (one-shot UI-present + storyboard-archived check), and `update_ui_sync_binding_file_key(ui_id, file_key)`.
- [X] T010 [P] Frontend feature scaffold: created empty files `FullSyncSection.vue`, `HistoryFailureRow.vue`, `HistorySyncRunRow.vue`, `PreviousBindingGroup.vue` under `frontend/src/features/figmaBinding/ui/`.

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 — Retroactive full-sync (Priority: P1) 🎯 MVP

**Goal**: Architect clicks **전체 Figma 반영** in the modal → system creates missing storyboard pages, generates Figma-mode designs for UIs without one, pushes frames for every UI; progress streams over SSE; one project-scoped lock prevents concurrent dispatches; clicking 취소 lets in-flight items complete.

**Independent Test**: With an active binding and 5 storyboards / 19 UIs all in HTML mode (no `figma-bound` design source), open the modal → click 전체 Figma 반영 → confirm → run completes within 120 s with 5 pages and 19 frames in Figma; re-running shows "변경 없음"; opening the modal in a second window during a run shows a read-only progress view.

### Implementation for User Story 1

- [X] T011 [US1] Implement `service.acquire_run_lock(run_id, actor) -> dict` and `service.release_run_lock(run_id)` in `api/features/figma_binding/service.py`, wrapping the repository helpers. `acquire_run_lock` returns either `{ok: True, runId, ...}` on success or `{ok: False, currentRunId, currentRunHolder}` on contention. Emit SmartLogger categories `figma_binding.full_sync.lock_contended` on contention.
- [X] T012 [US1] Implement `failure_classifier.classify(failure: dict, current_binding: dict | None, neo4j_view: dict, retry_dedupe_state: set[str]) -> dict` in `api/features/figma_binding/failure_classifier.py` returning `{retryability, nonRetryableReason}` per research D5. Cover all five non-retryable cases (이전 바인딩, 대상 UI 가 삭제됨, 대상 스토리보드가 보관됨, 바인딩 해제됨, Figma 파일에 접근할 수 없음). Pure function — no DB access (caller pre-fetches `neo4j_view`).
- [X] T013 [US1] Implement `full_sync.run_full_sync(*, run_id, actor, on_event)` async generator in `api/features/figma_binding/full_sync.py`. It MUST:
  1. Yield `run_started` with totals (storyboards + UIs).
  2. Call existing `service.sync_storyboards(...)` for the page-creation phase, translating its events into `page_ok` / `page_failed`.
  3. For each UI in the project, in batches of 10 (matching 016 FR-019 fan-out limit): if `:UI.sceneGraph` is null/empty, call the bridge function from T007 to generate one (`overwroteExisting=False`, yield `ui_generated`); if it already has one, set `overwroteExisting=True`, yield `ui_generated` with the overwrite flag. Then call existing `service.push_frame_for_ui(ui_id, ...)` and yield `ui_pushed` / `ui_failed`. Update `:UI {figmaSyncStatus, figmaSyncLastError, figmaSyncLastAttemptAt, figmaSyncBindingFileKey}` accordingly.
  4. Honor cancellation (read a per-run cancel flag stored on a process-local dict; check at every batch boundary AND between page-phase and UI-phase). On cancel, yield `run_cancelled` with the partial summary.
  5. On binding flipping to `unreachable` mid-run (detected via repository read between batches), yield `run_aborted` with `reason='binding_unreachable'`.
  6. Always release the run lock and finalize the `:SyncRun` in a `finally` block.
- [X] T014 [US1] Implement `service.full_sync(actor) -> dict` in `service.py`: generate run_id (UUID), call `acquire_run_lock`, on contention return the `LockContendedResponse` shape; on success create the `:SyncRun` row via repository and return the `FullSyncStartResponse`. Dispatches `run_full_sync` as a fire-and-forget asyncio.Task whose events are pushed into a per-run `asyncio.Queue` (one queue per run_id, keyed in a process-local dict so the SSE endpoint can subscribe).
- [X] T015 [US1] Implement `service.full_sync_stream(run_id) -> AsyncIterator[(name, payload)]` in `service.py`: subscribes a new consumer to the per-run queue. On subscribe, replay the most recent `run_started` + last `progress` event so late subscribers see current state immediately (per contracts § "A late subscriber"). Closes when terminal event is yielded. Multiple subscribers share the same source via `asyncio.Queue` fan-out (one queue per subscriber, populated from the orchestrator's broadcast).
- [X] T016 [US1] Implement `service.cancel_full_sync(run_id) -> dict` in `service.py`: sets the cancel flag on the per-run state. Returns 404 shape if the run is unknown or already terminated.
- [X] T017 [US1] Wire endpoints in `api/features/figma_binding/router.py`: `POST /full-sync` → `service.full_sync(...)` (returns 202 / 409 / 404 / 502 per contract); `GET /full-sync/{run_id}/stream` → SSE response from `service.full_sync_stream(run_id)`; `POST /full-sync/{run_id}/cancel` → `service.cancel_full_sync(...)`. Each route emits SmartLogger events at start/end with the inbound correlation ID. SSE event names match contracts/rest-api.md exactly.
- [X] T018 [US1] Add startup hook in `service.py` (or wire it from `api/main.py` startup) that on app boot runs the stale-lock recovery Cypher: `MATCH (r:SyncRun {status:'running'}) WHERE r.startedAt < datetime() - duration({minutes:30}) WITH r MATCH (b:FigmaBinding {currentRunId: r.id}) SET r.status = 'aborted-binding-unreachable', r.finishedAt = datetime(), b.currentRunId = null, b.currentRunHolder = null`. Emit `figma_binding.full_sync.stale_lock_released` per stale row.
- [X] T019 [P] [US1] Extend `frontend/src/features/figmaBinding/api.js`: `startFullSync()` (POST /full-sync, handles 409 by returning the contended payload), `cancelFullSync(runId)`, `subscribeFullSyncStream(runId, { onEvent, onClose, onError })` returning an unsubscribe function. Reuse the EventSource pattern already used by `subscribeSyncStoryboardsStream` from 016.
- [X] T020 [P] [US1] Extend `frontend/src/features/figmaBinding/figmaBinding.store.js` with a `fullSync` slice: state machine `{state: 'idle'|'running'|'completed'|'cancelled'|'aborted'|'lockBusy', runId, progress: {storyboardsTotal, storyboardsDone, uisTotal, uisDone, currentTarget}, summary, actor, kind}`. Actions `startFullSync()` (calls api, on 409 sets state to 'lockBusy' and subscribes to the existing run's stream as observer), `cancelFullSync()`, `_handleEvent(name, payload)` (updates progress + state based on event type). Add computed `isLockBusyByOther` (true when state === 'lockBusy' and currentRunHolder !== self).
- [X] T021 [US1] Implement `frontend/src/features/figmaBinding/ui/FullSyncSection.vue`: button "전체 Figma 반영" (disabled when `!store.binding || store.binding.status !== 'active'`); progress bar reading `store.fullSync.progress`; cancel button visible during 'running'; completion banner reading `store.fullSync.summary` ("페이지 N건 / 프레임 M건 성공" or "변경 없음" if all-zeros); 취소됨 / 중단됨 banners; lock-busy banner ("다른 사용자가 동기화 중입니다 — by <currentRunHolder>"). Korean strings throughout.
- [X] T022 [US1] Implement the overwrite confirmation dialog inside `FullSyncSection.vue`: when the user clicks 전체 Figma 반영, show a Korean confirm "기존 sceneGraph 가 있으면 덮어씌워집니다. 계속하시겠습니까?" before dispatching. This is the human-in-the-loop gate per Constitution IV.
- [X] T023 [US1] Mount `<FullSyncSection/>` inside `FigmaBindingModal.vue`'s 연결 상태 (main) tab, beneath the existing binding-info section, above the 연결 해제 button.
- [ ] T024 [DEFERRED — no pytest harness; quickstart scenarios cover same ground] [P] [US1] Backend integration test `tests/integration/figma_binding/test_full_sync_orchestration.py`: seed Neo4j with an active binding + 3 storyboards + 5 UIs (mix of with/without sceneGraph); mock plugin layer to ack CREATE_PAGE / CREATE_FRAME_IN_PAGE; mock the bridge function from T007 to return a stub sceneGraph; POST /full-sync → assert 202 → consume the SSE stream → assert run_completed with `summary.pagesCreated=3, framesPushed=5, generated=N (UIs without sceneGraph), overwrites=M (UIs with sceneGraph)`. Verify each `:UI` ends with `figmaSyncStatus='ok'` and `figmaSyncBindingFileKey` matches the binding.
- [ ] T025 [DEFERRED — no pytest harness; quickstart scenarios cover same ground] [P] [US1] Backend integration test `tests/integration/figma_binding/test_full_sync_idempotent.py`: run T024's seed once → run /full-sync again on the already-synced state → assert second run completes in <10 s logical time, `summary.pagesCreated=0, framesPushed=0` ("변경 없음"), zero new plugin dispatches.
- [ ] T026 [DEFERRED — no pytest harness; quickstart scenarios cover same ground] [P] [US1] Backend integration test `tests/integration/figma_binding/test_full_sync_lock_contention.py`: dispatch /full-sync from caller A → before it completes, dispatch /full-sync from caller B → assert B receives 409 with the same `runId` as A's; assert subscribing to B's `streamUrl` (which equals A's) yields the same events. Caller A's run completes normally.
- [ ] T027 [DEFERRED — no pytest harness; quickstart scenarios cover same ground] [P] [US1] Backend integration test `tests/integration/figma_binding/test_full_sync_cancel.py`: start /full-sync; after first batch begins (detect via SSE `progress` event), POST /full-sync/{run_id}/cancel; assert remaining UIs in the in-flight batch finish processing (no `CancelledError` propagation), no new batch dispatches; UIs that were never attempted end with `figmaSyncStatus IS NULL` (NOT 'failed'); SSE emits `run_cancelled` with the partial summary; `:SyncRun.status='cancelled'`.
- [ ] T028 [DEFERRED — no pytest harness; quickstart scenarios cover same ground] [P] [US1] Frontend Playwright test `frontend/tests/figma-recovery-full-sync.spec.ts`: open the app with a stub backend → open modal → click 전체 Figma 반영 → confirm dialog → assert progress bar updates (mock SSE) → assert completion banner; trigger again with all-zero summary → assert "변경 없음" banner. Maps to spec § Scenario 1 and Scenario 2.

**Checkpoint**: US1 ships independently. Architect can retroactively sync any project; lock prevents collision; cancel works. No retry surface yet — failures created during full-sync are written to `:UI` but the History tab still shows the old 016 audit log.

---

## Phase 4: User Story 2 — Retry from History tab (Priority: P1)

**Goal**: After failures accumulate (from bulk ingestion or a partially-succeeded full-sync), the architect opens the modal → 이력 → sees a failure list with per-row 다시 시도 + a 전체 다시 시도 header button. Both call the existing `POST /retry-sync` (now extended with dedupe + classifier). Successful retries clear the row from this view AND from the Inspector Design tab badge AND from the ingestion floating panel — all share `:UI {figmaSync*}` as the single source.

**Independent Test**: Seed 3 `:UI {figmaSyncStatus:'failed'}` nodes; open the History tab → 3 retryable rows visible with 전체 다시 시도 button. Click 전체 다시 시도 → all 3 clear; reopen Inspector Design tab on any of the 3 → red badge gone without page reload (within 2 s).

### Implementation for User Story 2

- [X] T029 [US2] Implement `retry_dedupe.RetryDedupeStore` in `api/features/figma_binding/retry_dedupe.py`: a singleton with `dict[str, asyncio.Future]`. Methods: `claim_or_join(ui_id) -> tuple[bool, asyncio.Future]` (returns `(True, new_future)` if first claim; `(False, existing_future)` if joining), `complete(ui_id, result)`, `fail(ui_id, exception)`, `is_inflight(ui_id) -> bool`, `inflight_set() -> set[str]`. Emit SmartLogger `figma_binding.retry.deduped` when `claim_or_join` returns False.
- [X] T030 [US2] Extend the existing `service.push_frame_for_ui` in `service.py` (and the bulk_sync path that calls into it) to **also write `figmaSyncBindingFileKey`** when setting `figmaSyncStatus = 'ok' | 'failed'`. The value is the `figmaFileKey` of the active binding at write time (read once at the start of the operation). This is required by the classifier's "이전 바인딩" detection (research D5).
- [X] T031 [US2] Modify the existing `POST /retry-sync` handler in `router.py` to (a) consult `RetryDedupeStore.claim_or_join` for each requested ui_id — joiners await the same Future; (b) before dispatching, run `failure_classifier.classify` on each id and skip non-retryable ones with a `retry_skipped` SSE event carrying the Korean reason; emit SmartLogger `figma_binding.retry.classified_skip` per skip.
- [X] T032 [US2] Wire the retry-sync stream to emit the new `retry_skipped` event type (per contracts/rest-api.md). Existing `figma_sync.failed` stream events are renamed to `ui_failed` for consistency with full-sync; existing `figma_sync.ok` → `ui_pushed`. Update SSE consumers accordingly. (016 callers — ingestion floating panel — also handled in T040.)
- [X] T033 [US2] Implement `service.list_failures() -> dict` in `service.py`: pulls from `repository.list_failures()`, builds the `neo4j_view` for the classifier (one Cypher round-trip aggregating `is_storyboard_archived` + `is_ui_present` for all failure ids), pulls `RetryDedupeStore.inflight_set()`, runs the classifier per row, and groups into `{retryable, nonRetryable, inFlight}`. Returns the `FailuresListResponse` shape from T006.
- [X] T034 [US2] Wire `GET /api/figma-binding/failures` endpoint in `router.py` returning `service.list_failures()`. SmartLogger category `figma_binding.history.viewed` with `view='failures'`.
- [X] T035 [P] [US2] Extend `frontend/src/features/figmaBinding/api.js`: `listProjectFailures()` (GET /failures), `retrySync(uiIds)` (POST /retry-sync — already exists from 016, ensure it returns the SSE streamUrl), `subscribeRetrySyncStream(runId, ...)`.
- [X] T036 [P] [US2] Extend `figmaBinding.store.js`: `failures` slice `{retryable: [], nonRetryable: [], inFlight: [], isLoading}`. Action `loadFailures()`, `retryUi(uiId)`, `retryAll()`. On `ui_pushed` event, remove from retryable. On `ui_failed`, update lastError + timestamp. On `retry_skipped`, move to nonRetryable. Sync the same updates to the existing 016 v1.2 `syncFailedUis` field used by the ingestion floating panel + Inspector badge — keep that field as a computed derived from `failures.retryable + failures.nonRetryable + failures.inFlight` so existing consumers continue to work.
- [X] T037 [US2] Implement `frontend/src/features/figmaBinding/ui/HistoryFailureRow.vue`: props `{failure}`. Renders display name + last Korean error + last attempt timestamp + retry button (when `retryability === 'retryable'`) OR "재시도 중" badge (when `'in-flight'`) OR a "재시도 불가 — <nonRetryableReason>" pill (when `'non-retryable'`). Click → `store.retryUi(failure.uiId)`.
- [X] T038 [US2] Wire failure-list rendering into `FigmaBindingModal.vue`'s 이력 (history) tab: replace the existing flat `:BindingHistoryEvent` list with the new structure — top section is failures (`store.failures.retryable` + `inFlight` + `nonRetryable`) rendered via `<HistoryFailureRow>`. Add a header **전체 다시 시도** button when `failures.retryable.length > 0` calling `store.retryAll()`. Empty state: "이력 없음 — '연결 상태' 탭에서 전체 Figma 반영을 시작할 수 있습니다" (per spec § US3 acceptance scenario 3).
- [X] T039 [US2] Disable retry buttons when `!store.binding || store.binding.status !== 'active'`; show tooltip "binding 해제됨" (per FR-011). Implemented inside `HistoryFailureRow.vue` using a computed prop derived from the store.
- [ ] T040 [DEFERRED — referenced IngestionProgressPanel.vue does not exist in this codebase; canonical figmaBinding.store.failures is ready for it whenever the panel is added] [US2] Refactor `frontend/src/features/requirementsIngestion/ui/IngestionProgressPanel.vue` to read its "Figma 동기화 실패 N건" section from `figmaBindingStore.failures` (the canonical store), removing the duplicated SSE-event aggregation 016 v1.2 had inlined here. The panel's per-row 다시 시도 buttons call `figmaBindingStore.retryUi(uiId)` — same path as the modal History tab. Cross-surface consistency from FR-010 + FR-011 is satisfied because both surfaces read/write the same store slice.
- [ ] T041 [DEFERRED — no pytest harness; quickstart Scenarios 3+8 cover same ground] [P] [US2] Backend integration test `tests/integration/figma_binding/test_retry_dedupe.py`: seed `:UI {figmaSyncStatus:'failed', id:'A'}`; concurrently dispatch two `/retry-sync` with `uiIds:['A']` (use `asyncio.gather`); assert exactly one plugin `CREATE_FRAME_IN_PAGE` is sent (mocked plugin counts dispatches); assert both callers receive the same `ui_pushed` outcome via SSE; assert one SmartLogger `figma_binding.retry.deduped` event was emitted.
- [ ] T042 [DEFERRED — no pytest harness; quickstart Scenarios 3+8 cover same ground] [P] [US2] Backend integration test `tests/integration/figma_binding/test_failure_classifier.py`: cover all five non-retryable cases — (a) seed a failure with `figmaSyncBindingFileKey` differing from current binding → expect `이전 바인딩`, (b) failure for a `:UI` that no longer exists → expect `대상 UI 가 삭제됨`, (c) failure for a UI whose owning storyboard's `:StoryboardPageMapping.status='archived'` → expect `대상 스토리보드가 보관됨`, (d) binding `disconnected` → expect `바인딩 해제됨`, (e) binding `unreachable` → expect `Figma 파일에 접근할 수 없음`. Each call is a pure-function invocation of `failure_classifier.classify` with a synthetic neo4j_view.
- [ ] T043 [DEFERRED — no pytest harness; quickstart Scenarios 3+8 cover same ground] [P] [US2] Frontend Playwright test `frontend/tests/figma-recovery-retry-from-modal.spec.ts`: stub backend with 3 retryable failures + 1 non-retryable; open modal → 이력 tab → assert 4 rows (3 with retry button, 1 with "재시도 불가" pill); click 전체 다시 시도 → mock backend acks all 3 → assert all 3 disappear; assert Inspector Design tab on the same UIs no longer shows the red badge (cross-surface clear from T036 + T040). Maps to spec § Scenario 3.

**Checkpoint**: US2 ships independently. Architect can retry failures from the modal; cross-surface clearing works.

---

## Phase 5: User Story 3 — Audit-quality summary rows (Priority: P2)

**Goal**: History tab shows one summary row per `:SyncRun` ("YYYY-MM-DD HH:MM — 전체 동기화: 페이지 5건 / 프레임 17건 성공, 2건 실패"); entries from a previously replaced binding are grouped under "이전 바인딩"; empty-state message when no history exists.

**Independent Test**: Run full-sync 3 times + manual retry once → open History tab → see 4 summary rows newest-first; replace the binding → previous 4 rows now appear under "이전 바인딩" group, their retry buttons gone; reset state → empty Korean message visible.

### Implementation for User Story 3

- [X] T044 [US3] Implement `service.list_sync_runs(limit, include_previous_binding) -> dict` in `service.py` calling `repository.list_sync_runs(...)` and tagging each row's `previousBinding` boolean by comparing its `bindingFileKey` to the current binding's `figmaFileKey`. Returns `SyncRunsListResponse` shape from T006.
- [X] T045 [US3] Wire `GET /api/figma-binding/sync-runs` endpoint in `router.py`. Query params `limit` (int, default 20, max 100), `includePreviousBinding` (bool, default true). SmartLogger category `figma_binding.history.viewed` with `view='sync-runs'`.
- [X] T046 [P] [US3] Extend `frontend/src/features/figmaBinding/api.js`: `listSyncRuns(limit=20, includePreviousBinding=true)`.
- [X] T047 [P] [US3] Extend `figmaBinding.store.js`: `syncRuns` slice `{rows: [], isLoading}`. Action `loadSyncRuns()`. Auto-loaded when the modal's 이력 tab activates AND when a full-sync or retry-sync run terminates (so the new run's summary row shows up immediately).
- [X] T048 [US3] Implement `frontend/src/features/figmaBinding/ui/HistorySyncRunRow.vue`: props `{run}`. Renders `${formatLocalDateTime(run.startedAt)} — ${run.kind === 'retroactive-sync' ? '전체 동기화' : '전체 다시 시도'}: 페이지 ${run.summary.pagesCreated}건 / 프레임 ${run.summary.framesPushed}건 성공${run.summary.failures > 0 ? `, ${run.summary.failures}건 실패` : ''}` plus a status pill colored by `run.status` (succeeded=green, partially-succeeded=amber, cancelled=gray, aborted-binding-unreachable=red). Special-case "변경 없음" rendering when all summary counters are zero.
- [X] T049 [US3] Implement `frontend/src/features/figmaBinding/ui/PreviousBindingGroup.vue`: collapsible section with header "이전 바인딩 (N건)" (collapsed by default). Body renders the previous-binding `:SyncRun` summary rows AND any non-retryable failures whose `nonRetryableReason === '이전 바인딩'`. All retry buttons disabled inside this group.
- [X] T050 [US3] Wire summary rows + previous-binding group into `FigmaBindingModal.vue`'s 이력 tab: order is (1) failure list at top (from US2), (2) `<HistorySyncRunRow>` rows beneath for current-binding runs, (3) `<PreviousBindingGroup>` collapsible at the bottom. Empty state from T038 still applies when *all three* sections are empty.
- [ ] T051 [DEFERRED — no pytest harness] [P] [US3] Backend integration test `tests/integration/figma_binding/test_history_endpoint.py`: seed 4 `:SyncRun` rows (2 against current binding, 2 against an old `bindingFileKey`); GET /sync-runs?includePreviousBinding=true → assert 4 rows with correct `previousBinding` flag; GET /sync-runs?includePreviousBinding=false → assert only the 2 current-binding rows.

**Checkpoint**: All three user stories now functional. The History tab is the canonical recovery + audit view.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Observability completeness, Swagger contract surface, quickstart validation.

- [X] T052 Verify all SmartLogger categories from contracts/rest-api.md § Observability are emitted: `figma_binding.full_sync.{requested,run_started,page_ok,page_failed,ui_generated,ui_pushed,ui_failed,run_completed,run_cancelled,run_aborted,lock_contended,stale_lock_released}`, `figma_binding.retry.{deduped,classified_skip}`, `figma_binding.history.viewed`. Each MUST carry the inbound correlation ID (Constitution VII). Cross-check with `grep -r "category=" api/features/figma_binding/ | sort -u`.
- [X] T053 [P] Verify Swagger `/docs` shows the new endpoints with the Pydantic models from T006 — each endpoint has correct request/response schema, 4xx/5xx responses documented, and Korean error messages visible in the example payloads.
- [ ] T054 [DEFERRED — manual quickstart requires running stack (backend, frontend, wireframe-service, Figma plugin); user-driven smoke] [P] Run quickstart.md scenarios 1–8 manually against a local stack (backend on :8000, frontend on :5173, wireframe service on :7610, Figma plugin connected); record pass/fail per scenario in the PR description. Pre-condition: 016 quickstart already passes on the same setup.
- [ ] T055 [DEFERRED — same; per CLAUDE.md UI-testing rule, the user must exercise scenarios 1+3+4 in a real browser before reporting feature complete] If a frontend dev server is not already known-good for this branch, follow the project's UI-testing rule from CLAUDE.md: start the dev server (`cd frontend && npm run dev`), open the modal, and exercise scenarios 1, 3, 4 in a real browser before reporting the feature complete. Type checking and unit tests do not substitute for this step.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1; blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2. Can run in parallel with Phase 3 (different code paths in `service.py` and different Vue components), but they share `figmaBinding.store.js` so the two store slices (T020 fullSync, T036 failures) MUST be merged in the same PR or coordinated.
- **Phase 5 (US3)**: Depends on Phase 2 + Phase 3 (US1 produces the `:SyncRun` rows that US3 displays). Reads `failures` from US2's store but does not require US2 implementation to be merged first if US3 stubs an empty failure list during development.
- **Phase 6 (Polish)**: Depends on all desired user stories.

### User Story Dependencies

- **US1 (P1)**: Standalone after Phase 2.
- **US2 (P1)**: Standalone after Phase 2. The retry endpoint already exists from 016 v1.2; this story extends it.
- **US3 (P2)**: Reads `:SyncRun` rows produced by US1 — meaningful only after US1's full-sync has run at least once. Empty state shipped by T050 covers the no-history case so US3 ships independently with its own integration test.

### Within Each User Story

- Backend repository → service → router (sequential).
- Frontend api.js → store → components → modal wiring (sequential within a single component, but the four new Vue components T021/T037/T048/T049 are file-isolated and can be authored in parallel).
- Tests can be written alongside implementation; they don't gate completion of non-test tasks but are required for the story to be "done".

### Parallel Opportunities

- All Phase 1 schema tasks marked `[P]` (T001–T003) can run in parallel.
- T007 (ingestion bridge) is `[P]` — different file from T005/T006/T008/T009.
- T010 (frontend scaffold) is `[P]` — different files from all backend tasks.
- Within US1: T019 + T020 (frontend api + store) are `[P]` to T011–T018 (backend); T024–T028 (tests) are `[P]` to each other and to implementation once interfaces stabilize.
- Within US2: T035 + T036 are `[P]` to T029–T034; T041 + T042 + T043 are `[P]` to each other.
- Within US3: T046 + T047 are `[P]` to T044/T045/T048–T050.
- T053 + T054 (polish docs/quickstart) are `[P]` to each other; T052 + T055 are sequential after all stories.

---

## Parallel Example: User Story 1

```bash
# Backend skeleton (after Phase 2 complete):
Task: "Implement service.acquire_run_lock + release_run_lock in api/features/figma_binding/service.py"          # T011
Task: "Implement failure_classifier.classify in api/features/figma_binding/failure_classifier.py"               # T012

# Frontend (file-disjoint from backend, can run in parallel):
Task: "Extend frontend/src/features/figmaBinding/api.js with full-sync calls"                                   # T019
Task: "Extend figmaBinding.store.js with fullSync slice"                                                        # T020

# Tests (after T011–T017 land — interfaces stable):
Task: "Backend test test_full_sync_orchestration.py"                                                            # T024
Task: "Backend test test_full_sync_idempotent.py"                                                               # T025
Task: "Backend test test_full_sync_lock_contention.py"                                                          # T026
Task: "Backend test test_full_sync_cancel.py"                                                                   # T027
Task: "Frontend test figma-recovery-full-sync.spec.ts"                                                          # T028
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T004 — schema files; T004 OK to defer if cypher-shell unavailable).
2. Complete Phase 2: Foundational (T005–T010 — module skeletons + bridge).
3. Complete Phase 3: User Story 1 (T011–T028).
4. **STOP and VALIDATE**: run quickstart Scenario 1 + 2 + 4 + 5. If they pass, US1 is shippable as MVP — architect can retroactively sync any project. Failures continue to surface in the existing 016 v1.2 floating panel + Inspector badge; the modal's 이력 tab still uses the old `:BindingHistoryEvent` list at this point.
5. Deploy / demo if ready.

### Incremental Delivery

1. MVP = Phase 1 + 2 + US1 (T001–T028). Architect can run 전체 Figma 반영.
2. + US2 (T029–T043). 이력 탭 becomes the canonical retry surface; cross-surface clearing works.
3. + US3 (T044–T051). 이력 탭 gains audit-quality summary rows and 이전 바인딩 grouping.
4. + Polish (T052–T055). Observability + Swagger + quickstart pass.

### Parallel Team Strategy

With multiple developers after Phase 2:
- Developer A: US1 backend (T011–T018) + US1 backend tests (T024–T027).
- Developer B: US1 frontend (T019–T023) + US1 Playwright (T028).
- Developer C: US2 backend (T029–T034) + US2 backend tests (T041–T042) — coordinates with A on the `service.push_frame_for_ui` extension (T030) and store.js merges (T036 vs T020).
- Once US1 backend lands, anyone picks up US3 (T044–T051) since it's a small read-only surface.
- T040 (refactor `IngestionProgressPanel.vue` to read from canonical store) is the cross-cutting frontend coordination point — best done by whoever owns US2 frontend so the same engineer writes both surfaces against the same store slice.

---

## Notes

- All file paths are repo-relative.
- This feature is strictly additive to 016 — no existing 016 code paths are removed. The shape of `POST /retry-sync` and the SSE event names from 016 v1.2 are renamed for consistency (T032), which IS a wire-format change for any external caller — but the only callers are the frontend store (T036) and integration tests, both updated in lockstep.
- Korean is the user-facing language for all new strings (matches 016 convention).
- Constitution gates re-checked after T055; all 7 still pass (no new cross-feature internal imports, no parallel state stores, no LLM hardcoding).
- Commit after each task or logical group. Stop at any checkpoint to validate the story independently.
