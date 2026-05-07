---
description: "Tasks for Figma Document Binding for Event Modeling"
---

# Tasks: Figma Document Binding for Event Modeling

**Input**: Design documents from `/specs/016-figma-document-binding/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/rest-api.md, contracts/plugin-protocol.md, quickstart.md

**Tests**: Backend integration tests (pytest) and one Playwright smoke for the Design-tab routing are included because plan.md explicitly named both as the chosen testing approach. Tests are not full-TDD — they target each endpoint's contract and the user-visible routing decision.

**Organization**: Tasks are grouped by user story (US1–US4) so each story can be implemented and shipped independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- File paths are absolute repository-relative; assume repo root is `/Users/uengine/robo-architect/`

## Path Conventions

This is a web app with mirrored backend/frontend layout per Constitution V:

- Backend feature: `api/features/figma_binding/`
- Frontend feature: `frontend/src/features/figmaBinding/`
- Shared schema: `docs/cypher/schema/`
- Plugin: `figma-plugin/src/plugin.ts`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Schema additions and basic skeletons. No business logic yet.

- [X] T001 [P] Append `:FigmaBinding`, `:StoryboardPageMapping`, `:BindingHistoryEvent` node-type definitions to `docs/cypher/schema/03_node_types.cypher` (one section per label, with property comments mirroring `data-model.md`)
- [X] T002 [P] Append relationship-type definitions `:MAPS_STORYBOARD`, `:MAPS`, `:LOGGED` to `docs/cypher/schema/04_relationships.cypher`
- [X] T003 [P] Append the four UNIQUE constraints (figma_binding_singleton, storyboard_page_mapping_id_unique, storyboard_page_mapping_command_unique, binding_history_event_id_unique) to `docs/cypher/schema/01_constraints.cypher`
- [ ] T004 Apply the new constraints to the running Neo4j (one-shot: `cypher-shell -f docs/cypher/schema/01_constraints.cypher`); record success in PR description **[DEFERRED — cypher-shell not installed on dev machine; constraint MERGE-based code paths still work without UNIQUE]**

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend module skeleton, plugin protocol versioning hook, frontend feature folder. Required before any user story can begin.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Create backend feature scaffold: empty `api/features/figma_binding/__init__.py`, empty `service.py`, empty `repository.py`, empty `storyboard_resolver.py`, empty `plugin_messages.py`
- [X] T006 Create `api/features/figma_binding/schemas.py` with Pydantic models: `FigmaBindingResponse`, `ConnectRequest`, `SyncStoryboardsResponse`, `StoryboardListItem`, `GenerateFrameRequest`, `GenerateFrameAccepted`, `BindingHistoryEntry` (all field shapes per `contracts/rest-api.md`)
- [X] T007 Create `api/features/figma_binding/router.py` with empty FastAPI `APIRouter(prefix="/api/figma-binding")`; mount it in `api/main.py` (one import + one `app.include_router(...)` line)
- [X] T008 Implement `api/features/figma_binding/repository.py` Neo4j helpers: `get_binding()`, `upsert_binding(...)`, `mark_binding_status(status)`, `delete_binding()`, `list_storyboard_mappings()`, `upsert_storyboard_mapping(...)`, `archive_storyboard_mapping(commandId)`, `append_history_event(...)`, `list_history_events(limit)`. All Cypher goes through `api/platform/neo4j.py`.
- [X] T009 [P] Implement `api/features/figma_binding/storyboard_resolver.py`: `list_entry_commands()` (Cypher per data-model.md) + `resolve_storyboard_for_ui(uiNodeId)` (BFS Cypher per data-model.md, depth-bounded to 30 hops). Returns `None` for orphans.
- [X] T010 [P] Implement private Figma read-only client `api/features/figma_binding/_figma_validate.py` with `validate_file(file_key, api_token) -> {fileName, ok, errorOrNone}` calling Figma REST `GET /v1/files/{file_key}` (httpx). Self-contained; no cross-feature import from `api/features/ingestion/figma_api.py`.
- [X] T011 [P] Plugin REGISTER extension: in `figma-plugin/src/plugin.ts`, add `supportedMessages: ["UPDATE_NODES","UPDATE_TEXT","SYNC_FRAME","CREATE_PAGE","CREATE_FRAME_IN_PAGE"]` to the existing REGISTER payload
- [X] T012 [P] Backend reads `supportedMessages` on REGISTER: in `api/features/ingestion/figma_plugin_ws.py`, store it on the connection record; expose `is_message_supported(file_key, msg_type)` for figma_binding to query
- [X] T013 [P] Create frontend feature scaffold: empty files `frontend/src/features/figmaBinding/figmaBinding.store.js`, `frontend/src/features/figmaBinding/api.js`, `frontend/src/features/figmaBinding/ui/FigmaButton.vue`, `frontend/src/features/figmaBinding/ui/FigmaBindingModal.vue`, `frontend/src/features/figmaBinding/ui/DesignBindingBadge.vue`

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 — Connect to a Figma document (Priority: P1) 🎯 MVP

**Goal**: An architect can bind the current Event Modeling project to a Figma document via a top-bar control, see a "Connected to <file>" indicator, and have the binding survive page reload.

**Independent Test**: Click the new top-bar Figma button → paste file URL + token → confirm → indicator shows; reload page → indicator persists; `GET /api/figma-binding` returns the binding.

### Implementation for User Story 1

- [X] T014 [US1] Implement `service.connect_binding(file_key, api_token, actor)` in `api/features/figma_binding/service.py`: validate via `_figma_validate.validate_file(...)` → upsert binding → append `connect` history event. Reject with 409 if an active binding already exists. Reject with 400 with Korean error on validation failure (and append `validate_failure` event).
- [X] T015 [US1] Implement `service.disconnect_binding(actor)` in `api/features/figma_binding/service.py`: mark current binding `disconnected` + append `disconnect` event. Idempotent (no-op if no active binding).
- [X] T016 [US1] Implement `service.replace_binding(file_key, api_token, actor)` in `api/features/figma_binding/service.py`: atomic disconnect + connect, archive existing storyboard mappings, append `replace` then `connect` events.
- [X] T017 [US1] Implement `service.get_history(limit)` in `api/features/figma_binding/service.py`.
- [X] T018 [US1] Wire endpoints in `api/features/figma_binding/router.py`: `GET /api/figma-binding`, `POST /api/figma-binding/connect`, `DELETE /api/figma-binding`, `POST /api/figma-binding/replace`, `GET /api/figma-binding/history`. Each route emits a `SmartLogger` event with the inbound correlation ID at start and end.
- [X] T019 [P] [US1] Implement `frontend/src/features/figmaBinding/api.js` REST client: `getBinding()`, `connect(fileKey, apiToken)`, `disconnect()`, `replace(fileKey, apiToken)`, `getHistory(limit)`. Token is read from existing 009 storage (`figma_api_creds` in localStorage) — do not introduce a new token store.
- [X] T020 [P] [US1] Implement `frontend/src/features/figmaBinding/figmaBinding.store.js` (Pinia): state `{ binding, isLoading, error }`; actions `loadBinding()`, `connect(...)`, `disconnect()`, `replace(...)`. Computed `isActive`. Auto-loads on store init.
- [X] T021 [US1] Implement `frontend/src/features/figmaBinding/ui/FigmaButton.vue`: shows "Figma" with status dot (gray = none, green = active, red = unreachable). Click opens `FigmaBindingModal`.
- [X] T022 [US1] Implement `frontend/src/features/figmaBinding/ui/FigmaBindingModal.vue` Connect tab: file URL/key input + token input (auto-fill from existing storage if present) + Connect button → calls `store.connect(...)`. On success closes; on error shows the Korean error inline.
- [X] T023 [US1] Add Disconnect and Replace tabs to `FigmaBindingModal.vue` (Disconnect = confirmation + `store.disconnect()`; Replace = same as Connect but calls `store.replace(...)` and shows `archived` notice for previous mappings).
- [X] T024 [US1] Add History tab to `FigmaBindingModal.vue`: lists `getHistory(50)` newest-first with eventType, actor, at, payload tooltip.
- [X] T025 [US1] Insert `<FigmaButton/>` into `frontend/src/app/layout/TopBar.vue` between `PRD 생성` and `Claude Code` controls. Mount the modal at the same level as existing modals.
- [ ] T026 [DEFERRED — pytest harness not yet wired for figma_binding] [P] [US1] Backend integration test in `tests/integration/figma_binding/test_connect_lifecycle.py`: connect (mock Figma REST OK) → get → replace → disconnect, verifying `:FigmaBinding` and `:BindingHistoryEvent` rows in Neo4j (use existing test Neo4j harness pattern from `tests/integration/`).
- [ ] T027 [DEFERRED — pytest harness not yet wired] [P] [US1] Backend integration test in `tests/integration/figma_binding/test_connect_validation_failure.py`: connect with mocked 401 from Figma → assert 400 response, `validate_failure` history event appended, no `:FigmaBinding` row created.

**Checkpoint**: US1 ships independently. Architect can bind/replace/disconnect; nothing yet writes to Figma.

---

## Phase 4: User Story 2 — Storyboard pages mapped to Figma (Priority: P1)

**Goal**: After binding, every storyboard (left-panel `BUSINESS PROCESSES` row) has a 1:1 Figma page in the linked document. Sync is idempotent.

**Independent Test**: Bind to an empty Figma file with N storyboards locally → after sync, the file contains N pages with matching names; re-running sync produces `created: []`, `reused: [...]`.

### Implementation for User Story 2

- [X] T028 [US2] Plugin: handle `CREATE_PAGE` in `figma-plugin/src/plugin.ts` — `handleCreatePage()` calls `figma.createPage()`, sets `page.name = msg.name`, posts `CREATE_PAGE_RESULT` to ui.html. Wired through ui.html (`CREATE_PAGE` case forwards to sandbox; `CREATE_PAGE_RESULT` case POSTs `/api/figma-plugin/create-page-ack`).
- [X] T029 [US2] Backend `api/features/figma_binding/plugin_messages.py` already exposed `build_create_page(name)` + `/create-page-ack` endpoint + `send_and_wait` correlator from earlier scaffold. No changes needed for v1 — existing surface satisfies T029.
- [X] T030 [US2] Implement `service.sync_storyboards(actor)` in `api/features/figma_binding/service.py`:
  1. If no active binding → 404. If binding `unreachable` → attempt; recover on success.
  2. Call `storyboard_resolver.list_entry_commands()` to get current storyboards.
  3. For each entry command without an active mapping: call plugin via `figma_plugin_ws.send_and_wait(file_key, build_create_page(name), timeout=15s)`.
     - On `503` (plugin not connected) or timeout: append `validate_failure`/`unreachable` event, set binding `unreachable`, return `{unreachable: [...]}`.
     - On ack OK: persist `:StoryboardPageMapping` via `repository.upsert_storyboard_mapping(...)`, append to `created`.
  4. For mappings whose entry command is gone or now policy-invoked: archive via `repository.archive_storyboard_mapping(commandId)`, append to `archived`.
  5. For mappings whose cached `figmaPageName` ≠ current `Command.displayName`: update cached name, bump `lastRenameAt`, append `page_renamed` history event, append to `renamed`. (Actual Figma rename is a follow-up — see research D5.)
  6. Update `:FigmaBinding.lastSyncAt`, append `sync_storyboards` history event with summary.
- [X] T031 [US2] Wire `POST /api/figma-binding/sync-storyboards` in `router.py` returning the per-section breakdown per `contracts/rest-api.md` (uses `_normalize_sync_summary` to adapt service output to `SyncStoryboardsResponse` schema).
- [X] T032 [US2] Wire `GET /api/figma-binding/sync-storyboards/stream` in `router.py` — async generator yielding `created`/`reused`/`renamed`/`done`/`error` SSE events. Uses `service.sync_storyboards_stream` which wraps `sync_storyboards` with an `asyncio.Queue` so the same business logic powers both the request/response and SSE variants.
- [X] T033 [Done early to power US1 modal] [US2] Implement `service.list_storyboards()` in `api/features/figma_binding/service.py`: returns the union of `list_entry_commands()` + active mappings (mapping = null when no Figma page yet). Wire `GET /api/figma-binding/storyboards` endpoint in `router.py`.
- [ ] T034 [P] [US2] Extend `frontend/src/features/figmaBinding/api.js`: `syncStoryboards()`, `syncStoryboardsStream()` (SSE), `listStoryboards()`.
- [ ] T035 [P] [US2] Extend `figmaBinding.store.js`: state `{ storyboards: [], lastSyncSummary }`; actions `syncStoryboards()`, `loadStoryboards()`. Auto-runs `syncStoryboards()` after a successful `connect()`.
- [ ] T036 [US2] Add Storyboards section to `FigmaBindingModal.vue`: list each storyboard with its mapping status (gray dot = unmapped, green dot = active, dim = archived). "Sync now" button triggers `store.syncStoryboards()` and shows the diff (`created`/`reused`/`renamed`/`archived`).
- [ ] T037 [P] [US2] Backend integration test in `tests/integration/figma_binding/test_sync_storyboards.py`: bind → run sync against a fake plugin transport that returns `CREATE_PAGE_ACK` with synthesized page IDs → assert mappings exist; re-run sync → `created: []`, `reused: [...]`. Add a case where one entry command is removed → assert mapping archived.
- [ ] T038 [P] [US2] Backend integration test in `tests/integration/figma_binding/test_sync_no_plugin.py`: bind → run sync with no plugin connected for the file key → assert 503 + binding status `unreachable`.

**Checkpoint**: US2 ships. Architects see Figma pages auto-created for each storyboard. Generation routing (US3) still uses HTML.

---

## Phase 5: User Story 3 — UI generation targets Figma (Priority: P1)

**Goal**: With binding active, clicking generate on a UI node creates a Figma frame in the resolved storyboard's page (instead of producing HTML).

**Independent Test**: Bind to a fresh Figma doc, sync storyboards, open Inspector→Design on a UI node with no design → click `Component로 생성` → frame appears in the matching Figma page; UI node `designSource = figma-bound` in Neo4j.

### Implementation for User Story 3

- [X] T039 [US3] Plugin: handle `CREATE_FRAME_IN_PAGE` in `figma-plugin/src/plugin.ts` — `handleCreateFrameInPage()` locates page by `figmaPageId` (Korean error if missing), creates a 375×812 frame, populates from `sceneGraph` via existing `buildFrameFromSceneGraph`, posts `CREATE_FRAME_IN_PAGE_RESULT { ok, figmaPageId, figmaNodeId, figmaFrameName }` (or `{ok:false, error}`). ui.html new cases for `CREATE_FRAME_IN_PAGE` (forward to sandbox) and `CREATE_FRAME_IN_PAGE_RESULT` (POST `/api/figma-plugin/create-frame-in-page-ack`).
- [ ] T040 [US3] Backend extend `api/features/figma_binding/plugin_messages.py`: `build_create_frame_in_page(figmaPageId, frameName, sceneGraph)`, `parse_create_frame_in_page_ack(msg)`.
- [ ] T041 [US3] Backend `api/features/figma_binding/service.py`: implement `start_generate_session(uiNodeId, mode, prompt, onConflict, actor)` — validates binding active, runs `storyboard_resolver.resolve_storyboard_for_ui(uiNodeId)`:
  - `None` → 409 with Korean orphan message + append `orphan_ui_blocked` event.
  - existing sceneGraph + `onConflict == "ask"` → 409 with `currentSource`.
  - else → create in-memory `:GenerateSession` (uuid + state), return `{sessionId, streamUrl, resolvedStoryboard}`.
- [ ] T042 [US3] Backend `service.run_generate_session(sessionId)` async generator yielding SSE events. Phases:
  1. `wireframe.start` → call wireframe service (same external `WIREFRAME_SERVICE_URL/render` 009 uses) for `mode=component`; for `openpencil-ai`/`html-to-design`, call the corresponding existing pipeline. (These calls go directly to the external service — no cross-feature import.)
  2. `wireframe.done` with `nodeCount`.
  3. `figma.send` with `figmaPageId`.
  4. `figma_plugin_ws.send_and_wait(file_key, build_create_frame_in_page(...), timeout=30s)`; on ack, `figma.ack`.
  5. Update UI node via Cypher SET (`designSource`, `figmaFileKey`, `figmaPageId`, `figmaNodeId`, `figmaBindingId`, `figmaStoryboardCommandId`, `sceneGraph`, `updatedAt`).
  6. `persist.done`, then `done`.
  7. On any failure, `error` with phase + Korean message; UI node left in prior state.
  8. Append `generate_routed` history event with the session outcome.
- [ ] T043 [US3] Wire `POST /api/figma-binding/generate-frame/{ui_node_id}` (returns 202 with sessionId) and `GET /api/figma-binding/generate-frame/{session_id}/stream` (SSE) in `router.py`. Sessions are kept in-memory; reject duplicate session IDs.
- [ ] T044 [US3] Backend Cypher SET for the UI node: extend the allow-list in `api/features/canvas_graph/routes/canvas_expansion.py` `update_node()` to include `designSource`, `figmaPageId`, `figmaBindingId`, `figmaStoryboardCommandId` (the existing `sceneGraph`, `figmaFileKey`, `figmaNodeId` are already allowed). One-line allow-list edit only — no new endpoints in `canvas_graph`.
- [ ] T045 [P] [US3] Extend `frontend/src/features/figmaBinding/api.js`: `startGenerateFrame(uiNodeId, payload)` (POST returning `{sessionId, streamUrl, resolvedStoryboard}`); `streamGenerate(streamUrl, onEvent)` opens EventSource.
- [ ] T046 [P] [US3] Extend `figmaBinding.store.js`: action `generateFrameForUI(uiNodeId, mode, prompt)` — if existing sceneGraph, opens conflict modal first; orchestrates the SSE stream; on `done`, refreshes the affected UI node in the canvas store.
- [ ] T047 [P] [US3] Implement `frontend/src/features/figmaBinding/ui/DesignBindingBadge.vue`: when `node.data.designSource ∈ {"figma-bound","imported"}`, shows "Linked to <fileName>/<pageName>/<frameName>" with an "Open in Figma" link.
- [ ] T048 [P] [US3] Implement conflict-choice dialog inside `FigmaBindingModal.vue` (or its own small modal): 2 buttons "Overwrite from Figma" / "Import existing into Figma". Returns the user's choice to the caller via promise.
- [ ] T049 [US3] Add orphan-UI dialog: when API returns 409 with the orphan message, show "이 UI는 어떤 스토리보드에도 속하지 않습니다" with options "HTML로 생성" (per-node fallback to existing wireframe path) or "취소".
- [ ] T050 [US3] Branch in `frontend/src/features/canvas/ui/InspectorPanel.vue`: in each of `generateComponentWireframe()`, `generateWithAI()`/`onConvertComplete()`, `startConvertToDesign()`, when `figmaBindingStore.isActive`, call `figmaBindingStore.generateFrameForUI(node.id, mode, prompt)` instead of the existing path. Display `DesignBindingBadge` on the Design tab when binding is active and the node has a Figma source.
- [ ] T051 [P] [US3] Backend integration test in `tests/integration/figma_binding/test_generate_happy_path.py`: bind → sync → start session for a UI reachable from one storyboard → assert SSE events arrive in order, UI node properties set, `generate_routed` history event appended.
- [ ] T052 [P] [US3] Backend integration test in `tests/integration/figma_binding/test_generate_orphan_ui.py`: bind → sync → start session for a UI not reachable from any entry command → assert 409 + `orphan_ui_blocked` event.
- [ ] T053 [P] [US3] Backend integration test in `tests/integration/figma_binding/test_generate_conflict.py`: UI already has `sceneGraph` and `onConflict=ask` → assert 409; with `onConflict=overwrite` → flow proceeds and `designSource` becomes `figma-bound`; with `onConflict=import-existing` → flow proceeds without calling wireframe service and `designSource` becomes `imported`.
- [ ] T054 [US3] Playwright smoke test in `frontend/tests/figma-binding-design-route.spec.ts`: with binding stubbed active, open a UI node's Design tab, click `Component로 생성`, assert that the network call is to `/api/figma-binding/generate-frame/...` (NOT the existing wireframe endpoint). With binding stubbed inactive, assert the original wireframe endpoint is called.

**Checkpoint**: US3 ships. Architect can generate UI frames directly into Figma. MVP for the entire feature is complete with US1+US2+US3.

---

## Phase 6: User Story 4 — Disconnect / Replace UX polish (Priority: P2)

**Goal**: Disconnecting clears state without destroying artifacts; replacing flags previously bound nodes.

**Independent Test**: With nodes generated under binding A, replace with binding B → previously generated nodes show "from previous binding" badge; disconnect entirely → top-bar indicator clears, nodes still render their existing scene graphs.

### Implementation for User Story 4

- [ ] T055 [US4] Frontend: in `DesignBindingBadge.vue`, when `node.data.figmaBindingId` ≠ current binding ID, render the badge in a muted style with text "from previous binding (<fileName>)". Reads previous file name from `node.data.figmaFileKey` resolution via a small `getFileNameByKey(key)` helper that hits `getHistory()` to recover the old name (no extra endpoint needed).
- [ ] T056 [US4] Frontend: confirmation dialog for Disconnect explicitly mentions "기존에 생성된 Figma 프레임과 sceneGraph는 삭제되지 않습니다." (informational; no behavior change).
- [ ] T057 [US4] Backend integration test in `tests/integration/figma_binding/test_replace_atomicity.py`: connect A → sync (1 mapping created) → replace with B → assert old `:StoryboardPageMapping` rows status=`archived`, no race where both bindings are active simultaneously.
- [ ] T058 [US4] Backend integration test in `tests/integration/figma_binding/test_disconnect_preserves_artifacts.py`: connect → generate (mocked) → disconnect → assert UI node properties (`sceneGraph`, `figmaFileKey`, `figmaNodeId`) untouched; subsequent generate call (with no binding) routes to HTML path (not via figma_binding endpoints).

**Checkpoint**: US4 ships. Replace/disconnect lifecycle complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, observability sweep, and quickstart validation.

- [ ] T059 [P] Update `README.md` "API 개요" section to add `Figma Binding: /api/figma-binding/...` row in the prefix table
- [ ] T060 [P] Verify SmartLogger structured event names are consistent with 009: `figma_binding.connect`, `.validate`, `.sync_storyboards`, `.sync_storyboards.unreachable`, `.generate.start`, `.generate.done`, `.generate.error`, `.disconnect`, `.replace`, `.orphan_ui_blocked`, `.page_renamed`, `.page_archived`. Cross-check with the events listed in `data-model.md`.
- [ ] T061 [P] Korean error string consistency review: grep all new `HTTPException` `detail=` strings; ensure they end with `.` and follow 009's tone (e.g., "Figma 노드 {id}를 찾을 수 없습니다.")
- [ ] T062 [P] Comment in `api/features/canvas_graph/routes/canvas_expansion.py` `generate_component_wireframe()` noting that when a `:FigmaBinding` is active, the *frontend* routes around this endpoint (link to `specs/016-figma-document-binding/research.md#d6`)
- [ ] T063 Run `specs/016-figma-document-binding/quickstart.md` end-to-end manually; record outcome in PR description
- [ ] T064 [P] Spec 009 boost: open a follow-up PR (separate, NOT in this branch) to add a paragraph in `specs/009-figma-sync-bidirectional/spec.md` Assumptions noting precedence with 016's document-level binding. This task is just a tracking checkbox to make sure the follow-up actually gets opened — the work itself lives outside this feature's scope.

---

## Phase 8: v1.1 Reliability Hardening (post-MVP, completed 2026-05-07)

**Purpose**: Two operability problems surfaced once the JSX agent was wired into the bulk ingestion path and into the in-browser FrameEditor. Both are now spec'd (FR-017, FR-018) and addressed by the tasks below. See `plan.md` "Reliability & Operability Addendum" for the full architectural justification.

### A. Wireframe-service fan-out reliability (FR-017)

- [X] T065 Add `asyncio.Semaphore(2)` (`_RENDER_SEM`, lazy-init) around the wireframe-service call in `api/features/ai_design/wireframe_agent.py::_render_jsx`. 2 is the empirical sweet spot — 3 still produced sporadic `Unexpected end of JSON input` 500s from Bun under bulk fan-out, 1 serializes too aggressively.
- [X] T066 Wrap the wireframe-service call in `_render_jsx` with a 3-attempt retry loop (0.5/1/2 s exponential backoff). Each retry re-uses the same JSX with **no extra LLM round-trip**; transient `httpx.ReadTimeout`, `httpx.RemoteProtocolError`, and 5xx all become recoverable.
- [X] T067 Raise `httpx.post(/render)` timeout from 60 s to 120 s in `api/platform/open_pencil_client.py::render_wireframe`. Each render is CPU-heavy (JSX parse + Yoga layout); 60 s was the dominant cause of `ReadTimeout` under load.
- [X] T068 In `api/features/ai_design/wireframe_agent.py::run_render_agent`, cache the JSX from every `render` tool call into a module-local `last_jsx` variable. After the agent loop ends without a successful render, attempt one direct `_render_jsx(last_jsx)` outside the agent — the LLM's tendency to summarize after a tool error instead of retrying meant we were giving up while still holding valid JSX.
- [X] T069 Add a 3-attempt retry loop with jittered backoff (`asyncio.sleep(0.5 * attempt)`) around `run_render_agent` inside `api/features/ingestion/workflow/phases/ui_wireframes.py::_generate_jsx_scene_graph_for_figma_mode`. Distinct SmartLogger categories per outcome: `.success` (with attempt number), `.retry` (between attempts), `.empty` (after all attempts), `.error` (exception path).
- [X] T070 Diagnostic Playwright test `frontend/tests/figma-ui-bulk-diag.spec.ts`: drives the full ingestion flow with the built-in food-delivery sample under `Figma UI` mode, instruments `window.EventSource` to relay every `progress` event, classifies each emitted UI by `sceneGraph` length, and reports populated/empty counts. Includes a fallback exit on `phase=complete` + `progress=100` because the ingestion SSE never sends an explicit `done` event. Used as the SC-007 measurement harness.

### B. Korean text rendering in the Design-tab canvas (FR-018)

- [X] T071 Add `Inter-Regular.ttf` and `NotoNaskhArabic-Regular.ttf` to `frontend/public/`, copied from `open-pencil/public/`. open-pencil's `BUNDLED_FONTS` map points at these root-relative URLs as the last fallback in `loadFont()`; without them, Vite was 200ing the SPA `index.html` instead, which CanvasKit fed to OTS as font data (`OTS parsing error: invalid sfntVersion: 1008813135` — `0x3C21444F` = `<!DO`).
- [X] T072 Add a `copy-open-pencil-fonts` Vite plugin to `frontend/vite.config.js`, modeled on the existing `copy-canvaskit-wasm` plugin, so a clean checkout / `rm -rf public/*.ttf` followed by `npm run dev` re-creates the bundled fonts automatically.
- [X] T073 Bundle a Korean-capable static OTF at `frontend/public/Pretendard-Regular.otf` (1.5 MB, fetched from jsdelivr's stable Pretendard mirror). Pretendard chosen over Noto Sans KR because it carries both Latin and Hangul in one file and already appears in open-pencil's `FIGMA_FONT_MAP` for export round-tripping.
- [X] T074 Create `frontend/src/features/aiDesign/fonts.js` with `preloadKoreanFont()`: fetches `/Pretendard-Regular.otf`, calls open-pencil's `markFontLoaded('Pretendard', 'Regular', buf)` to register into the module-level `loadedFamilies` cache, then `setCJKFallbackFamily('Pretendard')` so glyphs missing from Inter route to Pretendard. Idempotent (caches the in-flight Promise so concurrent callers share one fetch).
- [X] T075 Call `preloadKoreanFont()` from `frontend/src/main.js`, immediately after `bootstrapAIDesign()`. Fire-and-forget; the FrameEditor's lazy mount happens long after the fetch resolves, and even if it doesn't, open-pencil's `initFontService()` replays the cache into every fresh `TypefaceFontProvider` so registration order is forgiving.
- [X] T076 Diagnostic Playwright test `frontend/tests/font-loading-diag.spec.ts`: probes `/Inter-Regular.ttf`, `/NotoNaskhArabic-Regular.ttf`, `/canvaskit.wasm`, and Google Fonts metadata (to document the 429 baseline) from the live page; captures CanvasKit / OTS console messages; opens the Design tab and screenshots the canvas. Used as the SC-008 measurement harness.

### Verification artefacts

- Diagnostic test outputs (kept under `frontend/test-results/`):
  - `font-diag.png` — Design tab canvas after preload, showing rendered Korean labels.
  - `figma-ui-bulk-final.png` — full-flow screenshot at the end of the bulk ingestion run.
- Direct Neo4j post-run check (one-liner):
  ```
  MATCH (u:UI)
  RETURN count(u) AS total,
         count(CASE WHEN u.sceneGraph IS NOT NULL AND u.sceneGraph <> '' THEN 1 END) AS populated
  ```
  Pre-hardening baseline on the food-delivery sample: 19 / 11 populated. Post-hardening: 19 / 19.

**Checkpoint**: v1.1 reliability ships. The Figma-mode ingestion path no longer leaves UI nodes empty under nominal load, and the Design tab renders Korean labels on a fresh page load with no granted local-font permissions.

---

## Phase 9: v1.2 Clarification-Driven Additions (FR-018 banner / FR-019 / FR-020 / FR-021)

**Purpose**: Implement the four new requirements that came out of the 2026-05-07 clarification session (Q1–Q5 in `spec.md` § Clarifications). See `plan.md` § "Clarification-Driven Additions (v1.2)" for the architectural rationale; sections C / D / E in that addendum map 1:1 to the three task groups below.

**Prerequisites**: Phases 1–5 complete (US1, US2, US3 must have shipped — bulk-with-binding reuses their service-layer pieces). Phase 8 (v1.1 reliability) does NOT need to be re-applied; the retry stack at FR-017 already protects sceneGraph generation, and Phase 9's new failures (Figma push) are handled by FR-020 instead of FR-017's retry chain.

### C. Bulk-with-binding: storyboard sync + frame push during ingestion (FR-019b, FR-021)

- [X] T077 [P] Append three new properties to `:UI` node-type docs in `docs/cypher/schema/03_node_types.cypher`: `figmaSyncStatus` (string, nullable, values `'ok' | 'failed'`), `figmaSyncLastError` (string, nullable, Korean error message), `figmaSyncLastAttemptAt` (datetime, nullable). No constraint additions needed (these are queryable but not unique).
- [X] T078 [P] Add an SSE event-type list to `contracts/rest-api.md` § Ingestion stream: `figma_sync.start { uiId, uiName }`, `figma_sync.ok { uiId, figmaPageId, figmaNodeId }`, `figma_sync.failed { uiId, errorKo }`. (Already landed inline as part of the v1.2 plan-update — see "v1.2 Additions" section in `contracts/rest-api.md`.)
- [X] T079 Create `api/features/figma_binding/bulk_sync.py` with public `async def sync_batch(session_id, ui_ids, on_event)`. (1) loads active binding via `repository.get_active_binding()`, returns `{skipped: True}` if none; (2) calls `service.sync_storyboards_for_ids(ui_ids)` to ensure pages only for the storyboards touched by this batch; (3) for each UI calls `service.push_frame_for_ui(ui_id, figma_page_id, on_event)`; (4) records per-UI status via `repository.mark_ui_sync_ok` / `mark_ui_sync_failed`; (5) emits `figma_sync.start/ok/failed` via `on_event`. Pre-marks orphan UIs and page-failed UIs as failed. Never raises.
- [X] T080 Add `repository.mark_ui_sync_ok(ui_id, page_id, node_id)` and `repository.mark_ui_sync_failed(ui_id, error_ko)` helpers to `api/features/figma_binding/repository.py`. Both write `figmaSyncLastAttemptAt = datetime()`. The `_ok` helper clears `figmaSyncLastError`. (Implementation also added two free helpers consumed by FR-020 wiring later: `list_failed_sync_uis()` for the retry endpoint's null-uiIds case, and `clear_ui_sync_status_for_binding_replace()` consumed by T083.)
- [X] T081 Add `service.sync_storyboards_for_ids(ui_ids)` to `api/features/figma_binding/service.py` — slimmer FR-006 variant that resolves each UI's owning storyboard via `storyboard_resolver.resolve_storyboard_for_ui`, dedupes the storyboard set, and ensures pages exist only for that subset via the shared `_ensure_page_for_command` helper. Returns `{pagesCreated, pagesReused, pagesRenamed, orphanUis, unreachable, uiToPageId}`. Never raises — orphan / unreachable surface as arrays for the caller (`bulk_sync`) to route into FR-020's failed list.
- [X] T082 Wire the bridge in `api/features/ingestion/workflow/phases/ui_wireframes.py`: after each `asyncio.gather(...)` batch returns and the corresponding `:UI` nodes are written to Neo4j, if `figma_binding.repository.get_active_binding()` is non-null, calls `figma_binding.bulk_sync.sync_batch(session_id, batch_ui_ids, _capture)` with a callback that buffers per-UI events. Buffered events are then yielded as `ProgressEvent` payloads with `data.figmaSync.{event, ...}` into the ingestion SSE stream. Cancel-flag check ordering preserved per FR-021.
- [X] T083 [US1 follow-up] Update `service.replace_binding` to also write `figmaSyncStatus` cleanup on the affected UIs when `replace` archives mappings (existing failed-sync state from the previous binding becomes meaningless against the new file). (Implemented via the new `repository.clear_ui_sync_status_for_binding_replace()` helper. `connect_binding` does not need the cleanup because the no-prior-binding case has no stale state to clear.)
- [ ] T084 **[BLOCKED — depends on T079, T082]** [P] Backend integration test `tests/integration/figma_binding/test_bulk_sync_with_binding.py`: full ingestion under `Figma UI` mode with active `:FigmaBinding` and a mocked plugin layer that always succeeds. Assert every emitted UI ends with `figmaSyncStatus='ok'` AND has `figmaPageId/figmaNodeId` populated.
- [ ] T085 **[BLOCKED — depends on T079, T082]** [P] Backend integration test `tests/integration/figma_binding/test_bulk_sync_failures_dont_halt.py`: plugin mock fails for half the UIs. Assert ingestion still reaches `phase=complete`, the failed half has `figmaSyncStatus='failed'` + a Korean error string, and the SSE emitted exactly one `figma_sync.failed` per affected UI.
- [ ] T086 **[BLOCKED — depends on T079, T082]** [P] Backend integration test `tests/integration/figma_binding/test_cancel_during_bulk.py`: kick off ingestion, fire cancel after the first batch begins. Assert (a) the *current* batch's UIs all complete sceneGraph + sync attempt, (b) the next batch never starts, (c) no `CancelledError` propagates into running coroutines (= FR-021 contract).

### D. Failure list & retry UX (FR-020)

- [ ] T087 [P] Implement `POST /api/figma-binding/retry-sync` in `api/features/figma_binding/router.py`. Body: `{ uiIds: string[] | null }` (null/missing → retry every `:UI {figmaSyncStatus:'failed'}`). Returns 202 with `{ session_id }`. Backed by a new `retry.py` module that queues a background task running `bulk_sync.sync_batch(...)` for the requested ids.
- [ ] T088 [P] Implement SSE stream `GET /api/figma-binding/retry-sync/{session_id}/stream` that emits the same `figma_sync.start/ok/failed` event types as bulk-with-binding so the frontend has one event handler.
- [ ] T089 [P] Add `figma_binding.store::syncFailedUis` (reactive array) and `figma_binding.store::retrySync(uiIds)` action in `frontend/src/features/figmaBinding/figmaBinding.store.js`. The store also subscribes to the ingestion SSE stream (`figma_sync.failed` → push to array; `figma_sync.ok` → remove). Reads existing failed UIs from `:UI {figmaSyncStatus:'failed'}` on store init via a thin REST helper.
- [ ] T090 [P] Implement `frontend/src/features/figmaBinding/retry.js` REST + SSE client: `retrySync(uiIds)` returns the SSE EventSource; helper to drain into the store's array.
- [ ] T091 Implement `frontend/src/features/figmaBinding/ui/DesignSyncFailedBadge.vue`: red badge "Figma 동기화 실패" + tooltip (last error) + "다시 시도" button calling `store.retrySync([this.node.id])`. Mounts only when `node.data.figmaSyncStatus === 'failed'`.
- [ ] T092 Mount `<DesignSyncFailedBadge/>` from `frontend/src/features/canvas/ui/InspectorPanel.vue` Design tab when applicable. One-line addition above the existing FrameEditor mount.
- [ ] T093 Add the "Figma 동기화 실패 N건" section to `frontend/src/features/requirementsIngestion/ui/IngestionProgressPanel.vue`: visible when `store.syncFailedUis.length > 0`. Lists each failed UI's display name + error, with a "전체 다시 시도" button (`store.retrySync(null)`) and per-row "다시 시도" (`store.retrySync([uiId])`).
- [ ] T094 [P] SmartLogger event names: `figma_binding.retry.requested`, `.ok`, `.failed`. Add to the FR-014 enumeration in `data-model.md` § Observability events list.
- [ ] T095 [P] Backend integration test `tests/integration/figma_binding/test_retry_endpoint.py`: seed Neo4j with 3 `:UI {figmaSyncStatus:'failed'}` nodes; POST `/retry-sync` with all 3 ids; mock plugin success; assert all three flip to `'ok'` and clear `figmaSyncLastError`. Also test the null-uiIds case (= retry all failed).
- [ ] T096 [P] Playwright E2E test `frontend/tests/figma-ui-bulk-with-binding.spec.ts`: variant of `figma-ui-bulk-diag.spec.ts` with binding stubbed active and a `page.route(...)` interceptor forcing failures for ~30% of plugin requests. Assert summary panel renders the "Figma 동기화 실패 N건" section, "전체 다시 시도" re-runs and (with the route stub disabled) clears the section.

### E. Font-preload failure banner (FR-018 latter half)

- [ ] T097 Extend `frontend/src/features/aiDesign/fonts.js`: keep the existing `preloadKoreanFont()` shape but track `state: 'pending' | 'ok' | 'failed'` plus optional `error`. Expose a `subscribeToFontStatus(cb)` that fires once on settle, plus a synchronous `getFontStatus()` getter.
- [ ] T098 [P] Create `frontend/src/features/aiDesign/fontStatus.store.js` (Pinia): one-state store `{ koreanFont: 'pending'|'ok'|'failed', bannerShown: boolean }` with action `markBannerShown()`. On store init, calls `subscribeToFontStatus(...)` and writes the result.
- [ ] T099 Add a banner element above the FrameEditor mount inside `frontend/src/features/canvas/ui/InspectorPanel.vue` Design tab branch: when `fontStatusStore.koreanFont === 'failed' && !fontStatusStore.bannerShown`, render a small Korean-language banner reading "한글 폰트 로드 실패 — 새로고침을 시도해 주세요" with a dismiss button (or auto-dismiss after first display via `markBannerShown()`). Banner MUST NOT block interaction with the canvas.
- [ ] T100 [P] On font preload failure, POST a structured event to backend: `frontend.fonts.preload_failed { url, error }`. Use the existing observability log endpoint if there is one; if not, inline a single `fetch('/api/observability/log', ...)` call (a placeholder endpoint to add only if missing — confirm during implementation).
- [ ] T101 [P] Playwright test `frontend/tests/font-preload-failure-banner.spec.ts`: `page.route('**/Pretendard-Regular.otf', route => route.abort())` → open Design tab on a UI → assert the canvas-overlay banner appears exactly once and the FrameEditor itself still mounts (so the failure does not block other features).

**Checkpoint**: v1.2 ships. Bulk ingestion with active binding produces both populated sceneGraphs AND Figma-side artifacts; failures are visible in two places and trivially retryable; cancel respects in-flight work; Korean font failures are loud enough for users to act on but never block other features.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No deps — can start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1. Blocks all user stories.
- **Phase 3 (US1)**, **Phase 4 (US2)**, **Phase 5 (US3)**: All depend on Phase 2. US1 and US2 can be developed fully in parallel. US3 depends on US2's `storyboard_resolver` (T009) for the page lookup at generation time, but T009 is in Foundational so this is satisfied at the start of US3.
- **Phase 6 (US4)**: Depends on Phase 3 (needs Disconnect/Replace endpoints from US1) and references nodes generated by Phase 5; the badge logic (T055) only matters once real generations exist, so US4 should land after US3 in the canonical order.
- **Phase 7 (Polish)**: After all user stories are complete.
- **Phase 8 (v1.1 Reliability)**: Cross-cutting hardening on top of the JSX agent that US3 introduced; T065–T070 touch the agent / wireframe-service path, T071–T076 touch the in-browser FrameEditor font setup. None depend on US4 or Phase 7.
- **Phase 9 (v1.2 Clarification-Driven Additions)**: Depends on US1 (binding lifecycle, T014–T024), US2 (storyboard sync primitives, T028–T036), and US3 (per-node generation pipeline that bulk-with-binding reuses, T039–T050). Group C (T077–T086) ships before Group D (T087–T096) because the retry endpoint needs the same `bulk_sync` module the ingestion bridge invokes. Group E (T097–T101) is fully independent of C/D and can ship in parallel.

### Within Each User Story

- Backend service before backend router (router thin-wraps service).
- Backend before frontend client (frontend needs the contract to integrate against; in practice the contract is fixed in `contracts/rest-api.md` so the two can run in parallel — see [P] markers).
- Plugin handler must land before the corresponding backend integration test that exercises end-to-end flow.

### Parallel Opportunities

- All Phase 1 tasks `[P]` are independent file edits — run together.
- Phase 2: T009, T010, T011 (in plugin.ts), T013 are independent files — run together. T011 and T012 both touch the plugin/backend transport but in different files, so [P] is correct.
- Phase 3 (US1): T019, T020 (frontend) are independent of T014–T018 (backend) and of each other in different files — run together. T026/T027 (tests) parallel with each other.
- Phase 4 (US2): T034, T035, T037, T038 are independent files — run together.
- Phase 5 (US3): T045, T046, T047, T048 are independent files — run together. T051/T052/T053 are independent test files.
- Different user stories can be worked by different developers in parallel after Phase 2.

---

## Parallel Example: User Story 3

```bash
# After foundational + US2 complete, four developers can pick up:
Dev A: T039 (plugin handler) → T040 (backend message builder) → T041–T043 (service + router)
Dev B: T044 (one-line canvas_expansion edit), then T051+T052+T053 (backend tests in parallel)
Dev C: T045 → T046 → T050 (frontend orchestration)
Dev D: T047, T048, T049 (frontend dialogs/badges, all in parallel)
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 + Phase 2 (foundational).
2. Phase 3 (US1): connect/disconnect/replace + top-bar control.
3. **STOP & VALIDATE**: User can connect to Figma, see status, manage binding. No Figma writes yet — but the user story is meaningful (trust + control surface).
4. Demo / merge.

### Recommended Real MVP (US1 + US2 + US3)

The product value of 016 only lands when generation routes to Figma. Recommended scope for first user-visible release:

1. Phases 1–5.
2. **STOP & VALIDATE** with `quickstart.md` Steps 1–3.
3. Demo / merge.
4. US4 + Polish in a follow-up.

### Incremental Delivery After MVP

5. US4 (disconnect/replace UX polish).
6. Phase 7 (docs, observability sweep, quickstart re-run).

### Parallel Team Strategy

After Phase 2:

- **Backend lane**: T014–T018 (US1), T030–T033 (US2), T041–T044 (US3), T057–T058 (US4 tests)
- **Frontend lane**: T019–T025 (US1), T034–T036 (US2), T045–T050 (US3), T055–T056 (US4)
- **Plugin lane**: T028 (US2), T039 (US3) — sequential because both touch `plugin.ts`
- **Test lane**: T026–T027, T037–T038, T051–T054 — can shadow each story as it lands

---

## Notes

- Feature stays self-contained: no direct Python imports from `api/features/ingestion/` (009) into `api/features/figma_binding/` (016). Cross-cutting goes via Neo4j (storyboard resolver) or via the plugin transport layer's public functions exposed under its module's `__init__.py`.
- Token storage continues to live where 009 placed it (`localStorage.figma_api_creds`) — do not introduce a second token store.
- Every endpoint emits SmartLogger events at start AND end with the inbound correlation ID; this is checked by T060.
- Plugin protocol versioning (T011/T012) is a small but load-bearing change: without it, an old plugin connected against a new backend would silently time out instead of returning a clear "update required" error.
- The Figma page rename direction "local → Figma" is intentionally **not** wired in v1 (see research D5). The Cypher mapping is updated; the actual Figma rename awaits a future `RENAME_PAGE` plugin op. Quickstart Step 2.5 documents this limitation.
- After US3 lands, the existing per-node 009 sync (`/api/ingest/figma-sync/pull` and `/push`) continues to work unchanged. The two paths coexist: 016 governs new generations under an active document binding; 009 governs per-node manual pull/push for any node whose `figmaFileKey` and `figmaNodeId` are set, regardless of binding state.
- Avoid: mixing US3 generation logic into `canvas_expansion.py` (would couple two features); editing 009's `figma_sync.py` (out of scope, separate PR).
