# Feature Specification: Requirements Ingestion with SSE Progress Streaming

**Feature Branch**: `001-requirements-ingestion-sse`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/ingestion/router.py`, `api/features/ingestion/ingestion_sessions.py`, `api/features/ingestion/ingestion_workflow_runner.py`, `api/features/ingestion/event_storming/`

## User Scenarios & Testing

### User Story 1 - Upload a requirements document and watch it become an Event Storming model (Priority: P1)

A business analyst opens the ingestion modal, pastes the text of an RFP (or uploads a PDF), and submits. The backend immediately returns a session identifier; the analyst sees a live progress panel that streams each stage of an LLM-driven Event Storming pipeline — parsing, user-story extraction, bounded-context identification, aggregates, commands, events, read models, properties, references, policies, GWT and UI wireframe generation — until the resulting graph appears in Neo4j and the canvas/navigator views populate themselves with the discovered domain model.

**Why this priority**: This is the entry point of the entire product. Without ingestion there is no graph to explore, no model to modify, and no PRD to generate. Every other feature consumes the artifacts produced here.

**Independent Test**: Submit a non-trivial requirements document via `POST /api/ingest/upload`, open the SSE stream returned by `GET /api/ingest/stream/{session_id}`, and assert that progress events with phases `parsing → extracting_user_stories → identifying_bc → ... → complete` arrive in order and that `GET /api/ingest/stats` reports a non-zero node count for `BoundedContext`, `Aggregate`, `Command`, and `Event` afterwards.

**Acceptance Scenarios**:

1. **Given** a plain-text requirements document, **When** the user POSTs it to `/api/ingest/upload`, **Then** the response includes `session_id`, `content_length`, `display_language`, `source_type`, and a `preview` truncated to 500 characters.
2. **Given** a PDF file is supplied instead of text, **When** the upload request is processed, **Then** the system extracts text from the PDF and continues identically to the text path.
3. **Given** a valid session_id, **When** the client connects to `/api/ingest/stream/{session_id}`, **Then** the workflow runner is started exactly once for the session and progress events are delivered as `event: progress` messages until a `complete` or `error` event closes the stream.
4. **Given** an upload was made with `display_language=ko` (default), **When** the workflow generates entities, **Then** the persisted nodes carry Korean `displayName` values; **And** when `display_language=en` is supplied the names are produced in English.

### User Story 2 - Pause a long-running ingestion to fix something, then resume (Priority: P2)

While the LLM is mid-run on a large document, the analyst notices that an extracted bounded context is incorrect. They press Pause; the workflow stops at the next checkpoint and emits a `paused` event. The analyst edits the affected node through other features (chat-based modification, manual fix-up), then presses Resume; the workflow re-syncs its in-memory context from Neo4j and continues from where it was waiting.

**Why this priority**: Long ingestion runs (10+ minutes on rich requirements) make it expensive to re-start from scratch when the analyst wants to correct something mid-flight. Pause/resume is a strong differentiator vs. one-shot generators.

**Independent Test**: Start an ingestion, call `POST /api/ingest/{session_id}/pause`, observe a `paused` event arriving on the SSE stream and `is_paused: true` in `GET /api/ingest/session/{session_id}/status`. Then call `POST /api/ingest/{session_id}/resume` and observe the next non-paused phase event.

**Acceptance Scenarios**:

1. **Given** an active session, **When** `POST /api/ingest/{session_id}/pause` is called, **Then** a `paused` SSE event is emitted with the message `⏸️ 일시 정지됨 (채팅으로 일부를 수정한 후 재개하세요)` and the response returns `is_paused: true`.
2. **Given** a paused session, **When** `POST /api/ingest/{session_id}/resume` is called, **Then** the workflow re-reads its context from Neo4j and emits the next phase event; the response returns `is_paused: false`.
3. **Given** a session that is not paused, **When** resume is called, **Then** the request fails with HTTP 400.

### User Story 3 - Cancel an unwanted run and start over with a clean graph (Priority: P2)

The analyst realises the wrong document was uploaded. They press Cancel, then choose "Clear all data" before starting a new ingestion. The current workflow task is cancelled, an `error` event with `cancelled: true` is broadcast, and Neo4j is wiped of all nodes and relationships so the next run starts from an empty graph.

**Why this priority**: Without a clean-slate operation, repeated experimentation pollutes the graph and corrupts downstream artifacts (PRD, navigator tree, canvas).

**Independent Test**: Start a session, call `POST /api/ingest/{session_id}/cancel`, then `DELETE /api/ingest/clear-all`. Assert `GET /api/ingest/stats` returns `total: 0` and `hasData: false`.

**Acceptance Scenarios**:

1. **Given** a running session, **When** cancel is called, **Then** `is_cancelled` is set, the asyncio task is cancelled, and an `error` event with payload `{cancelled: true}` is broadcast.
2. **Given** a cancel request for an already-expired session id, **When** the call is made, **Then** the API returns success with a message indicating the session was already removed (idempotent cancel).
3. **Given** the user invokes `DELETE /api/ingest/clear-all`, **When** the call succeeds, **Then** the response includes a `deleted` map of node-label counts that were removed before the wipe.

### User Story 4 - Recover the in-progress session after a page refresh (Priority: P3)

The analyst accidentally refreshes the browser. The frontend calls `GET /api/ingest/session/{session_id}/status`, sees the session is still active, and reconnects to the SSE stream with `?reconnect=true`; previously emitted events are replayed so the progress UI shows the full history before continuing live.

**Why this priority**: Quality-of-life recovery; ingestion runs are long enough that browser refreshes happen, but the workflow is not restarted by reconnect — only the event stream is re-played.

**Independent Test**: After a session has emitted a few events, open a new SSE connection with `?reconnect=true` and verify that all stored events arrive before any new ones.

**Acceptance Scenarios**:

1. **Given** a still-active session, **When** the status endpoint is queried, **Then** the response returns `active: true` plus the latest `phase`, `message`, `progress`, and `isPaused` flag.
2. **Given** the session has completed or errored, **When** status is queried, **Then** `active: false` is returned with a reason.
3. **Given** the SSE endpoint is hit with `reconnect=true`, **When** the stream opens, **Then** all stored events are replayed first, then live events resume.

### User Story 5 - Inspect a streamed object mid-generation without waiting (Priority: P3)

While the progress panel is still streaming entities, the analyst spots a name in the live created-items list (e.g. a `Trigger…` policy) and wants to read its properties immediately — not after the run finishes. They click the row in the panel; the corresponding sticker is highlighted on the canvas and the unified InspectorPanel opens with that object's properties pre-populated, even if the node has not yet been laid out on the canvas.

**Why this priority**: Long ingestion runs surface dozens or hundreds of items before completion (the panel shows `+436 items` in flight). Today the analyst has to wait for `complete` before they can click anything; allowing inspection mid-run shortens the feedback loop for catching wrongly named or mis-extracted entities (the same problem User Story 2's pause/resume targets, but without having to halt the workflow).

**Independent Test**: With an active session, push a `progress` event whose `data.object` carries a typed entity payload, then click the corresponding `.mini-item` row in the floating panel. Assert that (a) the row receives the `mini-item--selected` style, (b) `canvasStore.selectedNodeIds` contains that id, and (c) the InspectorPanel renders for that node — even when the node is not yet present on the canvas (the inspector falls back to the inlined node payload).

**Acceptance Scenarios**:

1. **Given** the floating progress panel is showing live items, **When** the analyst clicks a row, **Then** the row's `aria role` is `button`, the canvas store records the id as selected, and the InspectorPanel opens with that object's properties.
2. **Given** the clicked entity exists on the canvas, **When** the click handler runs, **Then** the corresponding sticker is visually marked selected (`es-node--selected` style) in addition to the panel row.
3. **Given** the clicked entity has only been streamed (not yet rendered on the canvas), **When** the click handler runs, **Then** the InspectorPanel still opens by reading the inlined `nodeData` payload pushed through `inspectorRequestStore.request` — without requiring a successful `GET /api/graph/...` fetch.
4. **Given** the user is on a non-Design tab (e.g. Event Modeling) when they click a row, **When** the click fires, **Then** `activeTab` switches to `Design` before the InspectorPanel opens.

### Edge Cases

- An upload without either `file` or `text` is rejected with HTTP 400 (`Either 'file' or 'text' must be provided`), unless `source_type=analyzer_graph` (which feeds from another data source).
- A document whose extracted content is empty (e.g. an unreadable PDF) is rejected with HTTP 400 (`Document content is empty`).
- Text uploaded via the form field is bounded by Starlette's 1024 KB FormData limit; the API documents that callers should switch to file upload for larger content.
- `display_language` values other than `ko` or `en` are silently coerced to `ko`; `source_type` values outside `rfp | analyzer_graph | figma` are coerced to `rfp`.
- When a stream client disconnects, its subscriber queue is unregistered and a completed/errored session with no remaining subscribers is deleted from memory.
- Multiple SSE clients for the same session each receive a fan-out copy of the events from a per-subscriber queue; the workflow itself is run only once per session (`is_workflow_running` guard).
- Calling pause after the workflow has already entered a phase only takes effect at the next cooperative checkpoint, not instantly.

## Requirements

### Functional Requirements

- **FR-001**: System MUST accept a requirements document as either a multipart file upload (`.pdf` extracted as text; other files decoded as UTF-8 with Latin-1 fallback) or as a `text` form field.
- **FR-002**: System MUST return a unique `session_id` for every accepted upload and MUST allow callers to subsequently subscribe to per-session progress.
- **FR-003**: System MUST support a `display_language` parameter (`ko` or `en`, default `ko`) that influences the language of generated display names on extracted nodes.
- **FR-004**: System MUST support a `source_type` parameter (`rfp`, `analyzer_graph`, or `figma`) that selects the appropriate ingestion adapter; values outside this set MUST be coerced to `rfp`.
- **FR-005**: System MUST stream ingestion progress over Server-Sent Events at `GET /api/ingest/stream/{session_id}`, emitting events whose phase is one of `upload`, `parsing`, `extracting_user_stories`, `identifying_bc`, `extracting_aggregates`, `extracting_commands`, `extracting_events`, `extracting_readmodels`, `generating_properties`, `generating_references`, `generating_ui`, `identifying_policies`, `generating_gwt`, `saving`, `paused`, `complete`, or `error`.
- **FR-006**: System MUST guarantee that the workflow for a given session runs at most once even if multiple SSE clients connect; subsequent subscribers MUST receive the same broadcast events.
- **FR-007**: System MUST support replay of all previously emitted events when the SSE endpoint is re-opened with `reconnect=true`.
- **FR-008**: System MUST allow pausing a running session via `POST /api/ingest/{session_id}/pause`; the workflow MUST stop at the next checkpoint, emit a `paused` event, and wait until resumed.
- **FR-009**: System MUST allow resuming a paused session via `POST /api/ingest/{session_id}/resume`; on resume, the workflow context MUST be re-synchronized from Neo4j up to the current phase before continuing.
- **FR-010**: System MUST allow cancellation via `POST /api/ingest/{session_id}/cancel`; cancellation MUST tear down the asyncio task and emit a final `error` event with `cancelled: true`. Cancellation of a non-existent session MUST be treated as success (idempotent).
- **FR-011**: System MUST expose a destructive `DELETE /api/ingest/clear-all` operation that removes every node and relationship from the underlying graph and returns the per-label deletion counts.
- **FR-012**: System MUST provide `GET /api/ingest/stats` returning total node count, per-label counts, and a `hasData` boolean.
- **FR-013**: System MUST provide `GET /api/ingest/sessions` listing all currently active sessions with their status, progress, paused flag, and workflow-running flag.
- **FR-014**: System MUST expose runtime LLM-cache controls (`GET /api/ingest/cache/status`, `POST /api/ingest/cache/enable`, `POST /api/ingest/cache/disable`) so operators can toggle response caching during experimentation.
- **FR-015**: System MUST persist all extracted entities to a graph store with node labels including `BoundedContext`, `Aggregate`, `Command`, `Event`, `Policy`, `Property`, `ReadModel`, `UI`, and `UserStory`, and relationships including `HAS_AGGREGATE`, `HAS_COMMAND`, `EMITS`, `TRIGGERS`, `INVOKES`, `HAS_POLICY`, `HAS_PROPERTY`, `HAS_UI`, `HAS_READMODEL`, and `IMPLEMENTS`.
- **FR-016**: The floating ingestion progress panel MUST render the live created-items list (`createdItems.slice(-5)` plus an overflow counter) as interactive rows. Each row MUST expose `role="button"`, be keyboard-activatable (Enter / Space), and visually indicate hover and selected states. Activating a row MUST (a) call `canvasStore.selectNode(item.id)` so the matching canvas sticker is highlighted and the row receives the `mini-item--selected` style, (b) push the row's payload through `inspectorRequestStore.request(item)` so `CanvasWorkspace` opens the unified `InspectorPanel` with that node's properties — using the inlined payload as a fallback when the node has not yet been laid out on the canvas, and (c) switch the active workspace tab to `Design` if it is not already there. This MUST work while the workflow is mid-run (no pause required) and MUST NOT affect SSE streaming, pause/resume, or cancel semantics.

### Key Entities

- **IngestionSession** (in-memory record): a single ingestion run identified by a short UUID. Holds the uploaded content, the current phase/progress/message, the list of past `ProgressEvent`s, the per-subscriber event queues, paused/cancelled/running flags, and metadata such as `display_language` and `source_type`.
- **ProgressEvent** (DTO): a single update emitted to subscribers, carrying `phase`, human-readable `message`, integer `progress` (0–100), and an optional `data` payload describing what was just produced.
- **CreatedObject** (DTO): a compact reference to a newly persisted entity (id, name, type, optional parent_id and description) included inside `ProgressEvent.data` so the UI can incrementally render the model.
- **GeneratedUserStory** (DTO): role/action/benefit triple with priority, sequence, optional UI description, optional Figma source screen name, and optional Analyzer source unit id.
- **BoundedContext / Aggregate / Command / Event / Policy / ReadModel / UI / Property / UserStory** (Neo4j labels): the persisted Event Storming graph the workflow produces; consumed by every other feature in the system.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A 5–10 page RFP can be ingested end-to-end without operator intervention, and the resulting graph contains at least one `BoundedContext` and one `Aggregate`/`Command`/`Event` chain per major capability described in the document.
- **SC-002**: Progress events arrive on the SSE stream within 2 seconds of each phase transition, so the user always sees forward motion rather than a frozen UI.
- **SC-003**: Pause and resume preserve all work performed so far — no extracted entity is lost or duplicated across the pause boundary.
- **SC-004**: Cancellation reliably stops further LLM calls within one phase boundary and frees the session from active memory once the stream closes.
- **SC-005**: A page refresh during an active ingestion can be recovered: the user sees the prior history of the run (via reconnect replay) and continues to receive new events without manual intervention.
- **SC-006**: After `clear-all`, the next ingestion starts from a verifiably empty graph (`stats.total == 0`).
- **SC-007**: While the workflow is still streaming (`phase` ∈ extracting_* / generating_*), clicking any row in the live created-items list opens the InspectorPanel with that object's properties within one render frame, with no dependency on the workflow having reached `complete`. Regression coverage: `frontend/tests/ingestion-mini-item-select.spec.ts`.

## Assumptions

- Neo4j is the configured graph store and is reachable from the API process; clear-all and stats use direct Cypher.
- Sessions are kept in-process memory only; restarting the API process loses any in-flight session state. There is no horizontal scaling story for ingestion in the current implementation.
- One LLM provider is configured at runtime via `get_llm()`; provider failures surface as an `error` phase with the exception message bubbled into `data.error`.
- Cooperative pause is acceptable: callers accept a delay between pressing Pause and the workflow actually halting.
- The graph is treated as a single-tenant working space: `clear-all` is destructive across the entire database, not scoped per session or user.
- Figma and analyzer-graph source types reuse the same SSE / pause / cancel machinery and only differ in how `content` is shaped before the workflow runs.
