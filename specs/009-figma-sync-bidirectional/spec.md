# Feature Specification: Bidirectional Figma Sync

**Feature Branch**: `009-figma-sync-bidirectional`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/ingestion/figma_sync.py`, `api/features/ingestion/figma_to_user_stories.py`, `api/features/ingestion/figma_plugin_ws.py`, `figma-plugin/src/plugin.ts`, `figma-plugin/manifest.json`

## User Scenarios & Testing

### User Story 1 - Pull a Figma frame into the Event Storming canvas (Priority: P1)

A product designer has created wireframe screens in a Figma file. The architect wants to bring those screens into the Event Storming canvas as `UI` nodes so they can be linked to user stories, commands, and read models. The architect connects with a personal access token and a file key, picks a frame node ID, points to a target `UI` node, and pulls. The backend fetches the frame from Figma's REST API, extracts top-level component instances and text overrides, asks the wireframe service to render them as a canonical scene graph (open-pencil components), and stores `sceneGraph`, `figmaFileKey`, `figmaNodeId`, and `updatedAt` on the `UI` node.

**Why this priority**: This is the primary path that gets external design content into the architectural model. Without it, every other Figma capability is auxiliary.

**Independent Test**: Issue `POST /api/ingest/figma-sync/pull` with a known token, file key, frame node ID, and target UI node ID. Verify the response returns `ok: true`, the node count is positive, and a follow-up Cypher query shows the `UI` node has `sceneGraph`, `figmaFileKey`, and `figmaNodeId` populated.

**Acceptance Scenarios**:

1. **Given** a UI node `ui-42` exists and a Figma file/frame is reachable with the token, **When** `POST /api/ingest/figma-sync/pull` is called, **Then** the response includes the rendered `sceneGraph` JSON and a `nodeCount` matching the rendered scene.
2. **Given** the Figma frame has component instances named `header-main`, `button-primary`, etc., **When** the pull runs, **Then** those component names plus their nested TEXT overrides are forwarded to the wireframe service `/render` endpoint.
3. **Given** the wireframe `/render` call fails, **When** the pull continues, **Then** it falls back to building a minimal `DOCUMENT → CANVAS → FRAME` scene graph directly from Figma node data so the user is not blocked.
4. **Given** the Figma node ID is missing from the file, **When** the pull runs, **Then** the response is `404` with a Korean message `Figma 노드 {id}를 찾을 수 없습니다.`

### User Story 2 - Push local wireframe back as a `.fig` file (Priority: P2)

After modifying a wireframe in the canvas (re-arranging components, editing labels), the architect wants to hand the result back to design. They invoke push, which serializes the stored `sceneGraph` and posts it to the wireframe service's `/export-fig` endpoint, which returns a binary `.fig` archive. The browser downloads it as `<displayName>.fig` and the designer drag-drops it into Figma.

**Why this priority**: Round-trip is what makes the integration "bidirectional"; without it, design changes flow only one way.

**Independent Test**: Create a `UI` node with a non-empty `sceneGraph`, call `POST /api/ingest/figma-sync/push`, and verify the response is a binary stream with `Content-Disposition: attachment; filename="<name>.fig"`.

**Acceptance Scenarios**:

1. **Given** a UI node has `sceneGraph` populated, **When** push is called, **Then** the response media type is `application/octet-stream` and the filename is sanitized (no quotes, ≤50 chars).
2. **Given** the UI node has no `sceneGraph`, **When** push is called, **Then** the response is `400` `sceneGraph 데이터가 없습니다.`
3. **Given** the wireframe service is unreachable, **When** push is called, **Then** the response is `502` `Wireframe service 오류: ...`.

### User Story 3 - Live edit via Figma plugin over WebSocket (Priority: P2)

A power user installs the `RoboArchitect Sync` Figma plugin (manifest id `robo-architect-sync`). The plugin connects to `/ws/figma-plugin?file_key=<fileKey>` and listens for `UPDATE_NODES`, `UPDATE_TEXT`, and `SYNC_FRAME` commands. When the architect edits a wireframe in the canvas, the backend tries to deliver the change over the WebSocket; if no plugin is connected for that file key it queues the message for the polling endpoint instead. The plugin can also push edits the other way: it serializes a frame and posts it to `/api/figma-plugin/export-result`, which converts to a SceneGraph (via wireframe `/render` or direct fallback) and persists it on the matching `UI` node.

**Why this priority**: Live mode replaces export/import friction with an interactive loop, but only matters once base pull/push works.

**Independent Test**: Connect a WebSocket client to `/ws/figma-plugin?file_key=K`, then `POST /api/figma-plugin/update-text` with `file_key=K`. Confirm the WebSocket receives `{type: "UPDATE_TEXT", ...}` and the REST response reports `delivery: "websocket"`.

**Acceptance Scenarios**:

1. **Given** a plugin is connected for `file_key=K`, **When** `POST /api/figma-plugin/update-nodes` is called with `file_key=K`, **Then** delivery is `websocket` and the message is forwarded.
2. **Given** no plugin is connected for `file_key=K`, **When** the same call is made, **Then** delivery is `queued` and `GET /api/figma-plugin/poll?file_key=K` returns the queued message and clears the queue.
3. **Given** the plugin creates a brand-new frame for an unknown name, **When** it calls `POST /api/figma-plugin/register-frame`, **Then** the matching `UI` node (matched by `displayName` or `name`) is updated with `figmaFileKey` and `figmaNodeId`.
4. **Given** the plugin reports a sync result via `POST /api/figma-plugin/report-result`, **When** the frontend polls `GET /api/figma-plugin/get-result`, **Then** it receives the queued result exactly once.

### User Story 4 - Generate user stories from a Figma storyboard (Priority: P3)

During the requirements ingestion flow, the architect chooses Figma as the source. The backend extracts top-level FRAME nodes (treated as screens), summarizes their hierarchy in Korean text, chunks at 5 screens per LLM call (max 3 concurrent calls), and asks the LLM (DDD/UX expert prompt) to emit a `UserStoryList` in `As a [role], I want to [action], so that [benefit]` form. Each story carries a `source_screen_name` validated by fuzzy-matching back to actual frame names.

**Why this priority**: This populates the rest of the architectural model from design — high value but conceptually depends on having Figma content available.

**Independent Test**: Call `extract_user_stories_from_figma(figma_nodes_json)` with a JSON describing two top-level frames containing buttons/text; assert returned `GeneratedUserStory` objects each have non-empty `action` and `source_screen_name` matching one of the input frames.

### Edge Cases

- Figma frame whose `children` are all groups/sections (not `INSTANCE`) — system still treats them as components and emits component overrides; if the wireframe service render returns fewer than 3 nodes, the fallback direct conversion runs.
- Storyboard with more than 5 top-level screens — chunked into batches of 5 and processed concurrently (cap of 3) by `extract_user_stories_from_figma_chunk`.
- LLM returns a `source_screen_name` that does not match any input frame — the fuzzy matcher (Jaccard bigram similarity, 0.5 threshold) corrects it; if nothing scores high enough, the original is kept and a `WARN` is logged.
- A Figma plugin reconnects with the same `file_key` while one is already registered — the prior WebSocket is closed before the new one is registered.
- Polling queue grows unbounded — pending updates per file are capped at the most recent 100 messages.
- Figma node IDs contain `:` which conflict with internal scene-graph IDs — they are remapped to `_` during conversion.

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose `POST /api/ingest/figma-sync/pull` accepting `{api_token, file_key, figma_node_id, ui_node_id}` and returning the rendered scene graph plus the updated `UI` node summary.
- **FR-002**: System MUST fetch the frame via `GET {FIGMA_API_BASE}/files/{file_key}/nodes?ids={figma_node_id}` using the `_figma_headers` and `_semaphore` defined in `figma_api.py`.
- **FR-003**: System MUST extract component placements (any `INSTANCE`, `FRAME`, `GROUP`, or `COMPONENT` child) plus recursive TEXT overrides from the frame, then call the wireframe service `POST {WIREFRAME_SERVICE_URL}/render` (default `http://localhost:7610`).
- **FR-004**: System MUST persist `sceneGraph` (JSON string), `figmaFileKey`, `figmaNodeId`, and `updatedAt` on the `(:UI {id})` node via Neo4j `MATCH ... SET`.
- **FR-005**: System MUST expose `POST /api/ingest/figma-sync/push` that streams a `.fig` file produced by `POST {WIREFRAME_SERVICE_URL}/export-fig` with `application/octet-stream` and a sanitized `Content-Disposition` filename.
- **FR-006**: System MUST expose `GET /api/ingest/figma-sync/status/{ui_node_id}` returning `{linked, figmaFileKey, figmaNodeId, lastUpdated}`.
- **FR-007**: System MUST expose `WS /ws/figma-plugin` accepting an optional `?file_key=` query parameter or a `REGISTER` message; only one connection per `file_key` is retained at a time.
- **FR-008**: System MUST expose `POST /api/figma-plugin/update-nodes` and `POST /api/figma-plugin/update-text` that prefer WebSocket delivery and fall back to a polling queue (`GET /api/figma-plugin/poll`) when no plugin is connected.
- **FR-009**: System MUST expose `POST /api/figma-plugin/register-frame` to attach a Figma node ID to a `UI` node located by `displayName` or `name`.
- **FR-010**: System MUST expose `POST /api/figma-plugin/report-result` and `GET /api/figma-plugin/get-result` to relay plugin sync outcomes back to the frontend through a one-shot keyed queue (`{file_key}:{frame_name}`).
- **FR-011**: System MUST expose `POST /api/figma-plugin/export-result`, which converts the plugin's serialized frame to a SceneGraph (preferring wireframe `/render`, falling back to direct conversion when the result has fewer than 3 nodes) and persists it to the matching `UI` node.
- **FR-012**: System MUST expose `GET /api/figma-plugin/status` returning the list of connected file keys, files with pending polling messages, and the connection count.
- **FR-013**: User story extraction from Figma MUST use the Korean DDD/UX system prompt, chunk top-level frames at 5 per LLM call, run at most 3 chunks concurrently, and validate `source_screen_name` via a fuzzy matcher (Jaccard bigram similarity, threshold 0.5).
- **FR-014**: System MUST log structured events to `SmartLogger` for every cross-system action (`figma_sync.pull`, `figma_plugin.register`, `figma_plugin.export.components`, `ingestion.llm.user_stories.figma.start`/`.done`, etc.).
- **FR-015**: The Figma plugin manifest MUST declare `id: robo-architect-sync`, `editorType: ["figma"]`, `permissions: ["currentuser"]`, and unrestricted `networkAccess.allowedDomains` so it can reach the local backend over WebSocket.

### Key Entities

- **UI** (Neo4j label): the architectural node representing a screen; carries `sceneGraph` (JSON string), `figmaFileKey`, `figmaNodeId`, `updatedAt`, plus name/displayName.
- **SceneGraph** (JSON document): canonical wireframe representation with `{nodes: {[id]: SceneNode}, rootId, images}`; `SceneNode` includes `type` (`DOCUMENT|CANVAS|FRAME|TEXT|...`), geometry, fills/strokes, parent/child IDs.
- **FigmaPullRequest / FigmaPushRequest** (Pydantic): request bodies for the REST sync endpoints.
- **PluginNodeUpdate / PluginTextUpdate / RegisterFrameRequest / PluginSyncResult / ExportResultRequest** (Pydantic): request bodies for plugin <-> backend traffic.
- **Plugin connection registry** (in-memory dict, keyed by `file_key`): the live WebSocket router; companion `_pending_updates` dict and `_sync_results` dict implement polling/handshake.
- **GeneratedUserStory** (Pydantic in `ingestion_contracts`): output of Figma-driven extraction, carrying `id`, `role`, `action`, `benefit`, `priority`, `ui_description`, `source_screen_name`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user with a valid Figma token can pull a 5-screen wireframe into a `UI` node and see the rendered scene graph within 10 seconds (one Figma fetch + one wireframe render call).
- **SC-002**: After a successful pull, exactly the four properties `sceneGraph`, `figmaFileKey`, `figmaNodeId`, `updatedAt` are set on the target `UI` node and visible via the `/status/{ui_node_id}` endpoint.
- **SC-003**: When a Figma plugin is connected for a given file key, REST update calls report `delivery: "websocket"` for at least 95% of attempts; otherwise messages enter the polling queue and are retrievable exactly once.
- **SC-004**: User story extraction from a Figma storyboard with up to 25 screens completes in at most 5 sequential chunk batches (capped at 3 concurrent LLM calls), and at least 90% of returned stories have a `source_screen_name` that matches an actual top-level frame name (after fuzzy correction).
- **SC-005**: Pushing a `UI` scene graph yields a downloadable `.fig` file whose filename matches the UI's `displayName`/`name`, contains no quote characters, and is at most 50 characters long.

## Assumptions

- The wireframe service (default `http://localhost:7610`) is reachable from the API process and exposes `/render` and `/export-fig` endpoints.
- Figma personal access tokens carry sufficient scope to read the requested file's nodes; auth/rate-limit handling is delegated to `figma_api._check_figma_response` and `_semaphore`.
- The Figma plugin runs in Figma's sandbox; the `manifest.json` `networkAccess` is intentionally permissive because users self-host the backend on `localhost`.
- Only one editing surface per Figma file is active at a time; the WebSocket registry's "close prior connection on re-register" policy is acceptable.
- LLM provider/model used for storyboard extraction is configured globally via `get_llm_provider_model`; no per-request override is exposed by this feature.
- `UI` node lookup by `name`/`displayName` is unique enough for the `register-frame` and `export-result` flows; collisions silently update the first match (`LIMIT 1`).
