# Phase 0 Research — Figma Document Binding

All `NEEDS CLARIFICATION` items from the Technical Context were resolved during exploration of the existing codebase (no open items). This document records each decision so downstream design (Phase 1) and tasks are traceable.

## Decision Log

### D1 — What "page in Event Modeling" / "BUSINESS PROCESS row" actually is

- **Decision**: One row in the left-panel `BUSINESS PROCESSES` list = one **storyboard**, identified by its **entry `:Command`** (a Command that is *not* invoked by any Policy, i.e. is initiated directly from a user UI). One storyboard maps to one Figma page.
- **Rationale**: Code investigation traced the list to:
  - Frontend: `frontend/src/features/navigator/ui/NavigatorPanel.vue` iterates `emStore.processChains` (header text `"Business Processes"`).
  - Store: `frontend/src/features/eventModeling/eventModeling.store.js` builds `processChains` via `_buildProcessChains()` from the response of `GET /api/graph/event-modeling`.
  - The build extracts entry commands as `cmds.filter(c => !policyInvokedCmds.has(c.id))`, then BFS-walks Command → Events → ReadModels → UI to assemble each storyboard.
  - Each row's stable identity is the entry Command's `id`; the badge count (e.g. `12`, `40`) is the BFS step count.
  - Backend Cypher in `api/features/canvas_graph/routes/event_modeling.py:49–89` confirms the same: there is no `:BusinessProcess` or `:Storyboard` label — the storyboard is an emergent grouping.
  - User explicitly confirmed: "이벤트 모델링 한 건이 페이지 한 건에 맵핑". A storyboard (= one Event Modeling slice) is the right Figma-page granularity.
- **Alternatives considered**:
  - Map per `:BoundedContext` — rejected (the previous draft made this mistake). A BC contains many storyboards; granularity would be far too coarse, and renaming a BC would not match the user's mental model of "one Figma page per flow".
  - Map per UI node — rejected; spec 009 already covers per-node bindings, and the user explicitly wants page-level grouping.
  - Introduce a new `:Storyboard` Neo4j label — rejected; storyboards are derived from Commands+flows, not first-class entities. Introducing a new label would duplicate state and risk drift between the new label and the live processChains computation. We use the entry Command's `id` as the storyboard's stable ID instead.

### D2 — Where Figma write operations happen

- **Decision**: All Figma writes (create page, create frame) go through the existing Figma plugin's WebSocket channel (`api/features/ingestion/figma_plugin_ws.py`). Two new message types are added: `CREATE_PAGE` and `CREATE_FRAME_IN_PAGE`. Polling-fallback + queue (already implemented for 009) is reused unchanged.
- **Rationale**: Investigation found Figma REST usage in this repo is read-only (`figma_api.py` exposes only pages/nodes/thumbnails fetch). Spec 009's existing write pathway already runs through the plugin (`SYNC_FRAME` etc.). Adding Figma REST write would (a) fragment the integration, (b) duplicate auth/rate-limit handling, and (c) require service-account–level Figma OAuth that the project does not currently use.
- **Alternatives considered**:
  - Add Figma REST writes (Figma API supports POSTs for some operations) — rejected; outside the existing 009 transport.
  - Frontend calls Figma directly with the user's token — rejected (Constitution I — backend remains the integration boundary).

### D3 — Where the binding state is persisted

- **Decision**: A singleton Neo4j node `(:FigmaBinding {id:"singleton"})`, with one outgoing relationship per mapped storyboard `(:FigmaBinding)-[:MAPS_STORYBOARD]->(:StoryboardPageMapping)-[:MAPS]->(:Command)`.
- **Rationale**: Constitution I forbids parallel state stores. The product is currently single-tenant per deployment (one active Event Modeling project at a time); a singleton constraint matches that. Putting the binding on a Neo4j node means existing read/write tooling (`api/platform/neo4j.py`) applies for free, including future export/PRD generation.
- **Alternatives considered**:
  - Local storage on the frontend — rejected (Constitution I; would make the binding invisible to backend and other collaborators).
  - Properties on a hypothetical `:Project` root node — rejected; no such node exists.
  - Filesystem `.env` or settings file — rejected (not graph-source-of-truth; no concurrency story).

### D4 — Streaming protocol for the generate-to-Figma flow

- **Decision**: `POST /api/figma-binding/generate-frame/{ui_node_id}` accepts the request, returns a `session_id` immediately, and the client subscribes to `GET /api/figma-binding/generate-frame/{session_id}/stream` (SSE) for phase events: `wireframe.start`, `wireframe.done`, `figma.send`, `figma.ack`, `persist.done`, `done`, `error`.
- **Rationale**: The end-to-end flow involves (a) LLM-driven wireframe generation, (b) plugin round-trip for frame creation, and (c) Neo4j persist. Total expected duration is multiple seconds. Constitution III requires streaming for any operation > a couple of seconds. The existing `ingestion/stream/{session_id}` SSE pattern is the established precedent — match it. The two-call shape (POST then SSE) is also the existing precedent and lets the client recover from disconnect.
- **Alternatives considered**:
  - Single synchronous POST that blocks until done — rejected (Constitution III).
  - WebSocket for the generate flow — rejected; SSE matches the precedent.

### D5 — Storyboard-page sync mechanism

- **Decision**: On successful connect (and on demand via `POST /api/figma-binding/sync-storyboards`), the backend:
  1. Queries Neo4j to enumerate entry commands. The Cypher is local to `api/features/figma_binding/storyboard_resolver.py` (intentionally **not** imported from `canvas_graph`, per Constitution V's "through Neo4j" rule).
  2. For each entry command without an existing `:StoryboardPageMapping`, sends `CREATE_PAGE` to the plugin with the command's display name (`Command.displayName || Command.name`) as the page name.
  3. On plugin ack, persists the new `:StoryboardPageMapping` with `commandId` and `figmaPageId`.
  4. Detects local renames (Command.displayName changed since last sync) and issues `RENAME_PAGE` (or `CREATE_PAGE` followed by mapping update — see D9 for protocol detail) — for v1, just rename the cached `figmaPageName` and emit a `page_renamed` event; actual Figma rename is a follow-up if/when the plugin grows a `RENAME_PAGE` op.
  5. Detects entry commands removed locally (no longer present in the entry-command set) and marks those mappings `archived` (Figma page itself untouched, per FR-009).
- **Rationale**: Plugin is the only write surface (D2). Mapping in Neo4j (D3) gives idempotency for free via UNIQUE constraint on `commandId`. Naming pages after the entry command's display name makes the integration immediately discoverable in Figma (matches what the user sees in the BUSINESS PROCESSES panel).
- **Alternatives considered**:
  - Lazy creation — only create a Figma page when the first UI node in that storyboard is generated. Rejected; the spec calls for all storyboard pages to exist after binding (US2 SC-002).
  - Bulk single plugin message — rejected; the plugin's protocol is one-message-one-action, and bulk would complicate ack semantics for partial failure.

### D6 — Routing in the Design tab when binding is active

- **Decision**: Branching happens in the frontend `InspectorPanel.vue` at the three call sites (`generateComponentWireframe`, `generateWithAI`, `startConvertToDesign`). When `figmaBindingStore.isActive`, each call site invokes `figmaBinding.api.generateFrame(uiNodeId, mode)` (which opens the SSE stream) instead of the existing wireframe API. The HTML wireframe code paths are not deleted — they remain the unbound-mode behavior.
- **Rationale**: Front-end branch keeps the routing decision visible in the component a developer reads. The three call sites all eventually call `onDesignSave()` for persistence; the new binding-aware path persists `figmaPageId` and `figmaNodeId` along with the sceneGraph so spec 009's per-node sync continues to work afterwards.
- **Alternatives considered**:
  - Branch in backend `generate_component_wireframe` — rejected; would conflate two endpoints' responsibilities and obscure the routing decision in code review.

### D7 — Authentication and token storage

- **Decision**: Reuse spec 009's existing token storage pattern unchanged. Personal access token handling stays as-is (009 stores it as `figma_api_creds` in browser local storage and forwards per-request to backend). The new feature only stores the file key + display name + sync metadata in Neo4j; it never persists the token server-side.
- **Rationale**: Diverging from 009 would create two token-handling surfaces. The token is needed for read-only validation (during connect) and for any background sync; both can pull from the same place.
- **Alternatives considered**:
  - Server-side token vault — out of scope for this feature.
  - OAuth flow — rejected; same scope concern, and Figma's OAuth requires app registration the project doesn't currently maintain.

### D8 — How "overwrite vs import existing scene graph" choice (FR-012) is collected

- **Decision**: Modal dialog in the frontend at the moment the user clicks generate on a node that already has a sceneGraph and binding is active. Two buttons: "Overwrite from Figma" (re-generate, push new frame) and "Import existing into Figma" (create a Figma frame from the current sceneGraph and link it). The chosen path emits a labeled SmartLogger event.
- **Rationale**: Synchronous UX for a binary, infrequent decision is appropriate. Constitution IV requires propose-then-confirm for LLM-driven mutations.
- **Alternatives considered**:
  - Always overwrite — rejected; destroys local design work without warning.
  - Always import — rejected; user may want a fresh design.

### D9 — UI → Storyboard membership resolution

- **Decision**: At generate time, the backend resolves which storyboard a given UI node belongs to by running a Cypher query that mirrors the frontend's `_buildProcessChains` BFS:
  1. Find all entry commands (`:Command` not invoked by any `:Policy`).
  2. For each entry command, BFS along `EMITS` (Command→Event), `INVOKES` (Policy→Command), `HAS_UI` / `ATTACHED_TO` / `INVOKES` paths, gathering reachable UI nodes.
  3. For each UI node, the *first* entry command (in canonical ordering: by `Command.displayName` ascending, then by `Command.id`) whose BFS reaches it = that UI's owning storyboard.
- **Rationale**: Mirrors what the user sees in the panel (so the choice is intuitive). Deterministic — same UI always resolves to the same storyboard. Computed not stored — keeps the model simple and avoids drift from the frontend.
- **Alternatives considered**:
  - Add a stored `(:Command)-[:OWNS_UI_FOR_STORYBOARD]->(:UI)` relationship — rejected; introduces denormalization and drift risk.
  - Pick the *closest* entry command (shortest BFS path) — rejected; "closest" is sometimes ambiguous and not how the existing UI panel decides ordering.
  - Allow a UI in multiple storyboards (= duplicate frames in multiple Figma pages) — rejected for v1; would multiply user surprise. Will be revisited if a real shared-UI use case emerges.

### D10 — Edge case: UI node not reachable from any entry command

- **Decision**: Resolver returns `None`. The generate endpoint responds `409` with a Korean message ("이 UI는 어떤 스토리보드에도 속하지 않아 Figma 페이지를 결정할 수 없습니다."). The frontend modal offers two recovery options: (a) generate without Figma binding (HTML mode for this node only), (b) cancel.
- **Rationale**: Silent fallback would hide a real model issue (an orphaned UI). Surfacing the choice respects Constitution IV (human-in-the-loop) and gives the architect a chance to fix the model.
- **Alternatives considered**:
  - Auto-create a "Misc" Figma page — rejected; clutters the linked Figma file with implementation-detail pages.

### D11 — Constraints discovered (cross-reference)

These are not decisions per se, but constraints the implementation must respect:

1. **Figma plugin must be running for any write** (D2). The connect step does not require the plugin (it does only a read-only Figma REST validation), but `sync-storyboards` and `generate-frame` cannot proceed if no plugin is connected for the bound file key. The system surfaces a clear Korean error and offers to either start the plugin or temporarily disconnect (FR-015).
2. **Plugin protocol versioning**: the new messages bump an implicit "supported messages" set. Add a `supportedMessages` field to plugin's existing `REGISTER` message so the backend can detect old plugins and surface "plugin update required" instead of timing out.
3. **Single active project** assumption: today's product runs one Event Modeling project per deployment. The singleton `:FigmaBinding {id:"singleton"}` mirrors that. If the product later supports multiple projects, the singleton ID becomes the project's stable ID — that migration is one Cypher rewrite and is out of scope here.
4. **Storyboard membership is ephemeral**: any model change that adds/removes a Policy `INVOKES` edge can change which UIs belong to which storyboard. Running `sync-storyboards` after such changes refreshes mappings; the UI's `figmaPageId` is *not* automatically rewritten on existing nodes (which would be destructive). A future "remap" UX may revisit this.
