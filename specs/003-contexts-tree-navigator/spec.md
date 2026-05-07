# Feature Specification: Bounded-Context Tree Navigator

**Feature Branch**: `003-contexts-tree-navigator`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/contexts/router.py`, `frontend/src/features/navigator/navigator.store.js`, `frontend/src/features/navigator/ui/NavigatorPanel.vue`, `frontend/src/features/navigator/ui/TreeNode.vue`

## User Scenarios & Testing

### User Story 1 - Browse all bounded contexts in the system from a single side panel (Priority: P1)

An architect opens the workspace and immediately sees a left-side navigator listing every Bounded Context that exists in the graph. Each context shows its name, optional description, and a count of its aggregates and user stories so the architect can pick where to start without first opening the canvas.

**Why this priority**: The navigator is the primary entry point into the model. Without a discoverable list of bounded contexts, the architect has no way to choose what to render on the canvas.

**Independent Test**: After ingestion populates the graph, call `GET /api/contexts` and assert the response is an alphabetically sorted list (by `bc.name`) where each item contains `id`, `name`, `description`, `owner`, `domainType`, `userStoryIds`, `aggregateCount`, and `userStoryCount`.

**Acceptance Scenarios**:

1. **Given** the graph contains multiple bounded contexts, **When** the navigator loads, **Then** every BC is listed sorted by name and shows accurate aggregate and user-story counts.
2. **Given** an empty graph, **When** the endpoint is called, **Then** the response is an empty list (not an error).
3. **Given** a BC with no aggregates and no user stories, **When** the endpoint is called, **Then** both counts are returned as `0`.

### User Story 2 - Expand a context node to drill into its aggregates, commands, events, and policies (Priority: P1)

The architect clicks the chevron on a context. The navigator fetches the context's full subtree on demand and renders a hierarchical view: aggregates contain their commands; commands contain the events they emit; policies are listed alongside, with their trigger event id and the command they invoke surfaced for cross-linking. Read models, UIs, and user stories under the context are also shown so the architect has a single place to inspect what the context owns.

**Why this priority**: Without expandable detail, the navigator is just a flat list. Drilling into a context's structure is what makes it a real navigator.

**Independent Test**: Call `GET /api/contexts/{contextId}/full-tree` for a populated context and assert the response includes `userStories[]`, `aggregates[]` (each with embedded `commands[]`, `events[]`, sorted `properties[]`, parsed `enumerations[]`, `valueObjects[]`), `policies[]` (with `triggerEventId` and `invokeCommandId`), `readmodels[]` (with `properties[]` and `operations[]`), and `uis[]`.

**Acceptance Scenarios**:

1. **Given** a context id, **When** `full-tree` is requested, **Then** the response is a single normalized object with the BC at the root and child collections as siblings (`userStories`, `aggregates`, `policies`, `readmodels`, `uis`).
2. **Given** an aggregate inside that response, **When** the navigator reads it, **Then** its `commands[]` list each have their own `events[]` and `properties[]`, and the aggregate also exposes `enumerations[]` and `valueObjects[]` parsed from JSON-encoded storage.
3. **Given** a policy inside that response, **When** the navigator reads it, **Then** the policy carries the id of the `Event` that triggers it and the id of the `Command` it invokes, so cross-links can be drawn without an extra query.
4. **Given** a non-existent context id, **When** `full-tree` is requested, **Then** the API returns HTTP 404.

### User Story 3 - Drag a node from the navigator onto the canvas to focus on it (Priority: P2)

The architect spots an aggregate of interest deep in the tree, grabs it, and drops it onto the canvas. The canvas opens that node (and its surrounding BC context, via the canvas-graph expand-with-bc endpoint) so the architect can keep working visually while continuing to use the navigator as a structural index.

**Why this priority**: Drag-and-drop is the connective tissue between the structural navigator and the visual canvas; without it the architect has to copy ids by hand.

**Independent Test**: Trigger a `dragstart` on a TreeNode in the DOM, inspect `event.dataTransfer` and verify the payload is JSON containing the node id, type, and minimal display fields needed by the canvas drop handler.

**Acceptance Scenarios**:

1. **Given** any node in the tree, **When** the architect starts dragging it, **Then** the navigator places a JSON payload on the drag event describing the node and sets `effectAllowed = 'copy'`.
2. **Given** a drop on the canvas, **When** the canvas handles the dragged payload, **Then** the corresponding node is added to the canvas with its bounded-context grouping intact.

### User Story 4 - Switch between a lightweight tree summary and the full normalized tree (Priority: P3)

For very large bounded contexts, the architect can request the lighter `tree` view (BC + aggregates with command/event names + policies) when they only need the shape. For deeper edits and inspector content, they use the `full-tree` view that includes properties, enumerations, value objects, read models, UIs, and user stories.

**Why this priority**: Performance affordance for large models; not the default but valuable for the largest workspaces where loading every property would be wasteful.

**Independent Test**: For the same context id, call both `GET /api/contexts/{id}/tree` and `GET /api/contexts/{id}/full-tree`. Assert the lighter response omits `properties`, `enumerations`, `valueObjects`, `readmodels`, `uis`, and `userStories`, while the full response includes them.

**Acceptance Scenarios**:

1. **Given** a context, **When** the lightweight `tree` endpoint is called, **Then** the response contains only `aggregates[]` (with `commands[]` and `events[]` summaries) and `policies[]` (with `triggerEventId` and `invokeCommandId`).
2. **Given** the full-tree endpoint is called, **Then** the response also includes `userStories[]`, `readmodels[]` (with `properties[]` and CQRS `operations[]`), `uis[]`, and embedded `properties[]` on Aggregate/Command/Event/ReadModel.

### Edge Cases

- A bounded context with no aggregates still appears in the list with `aggregateCount: 0`, and its `tree` / `full-tree` responses return empty `aggregates[]`.
- Aggregate `enumerations` and `valueObjects` are stored as JSON strings; the navigator API parses them into arrays and defaults to `[]` when null or malformed.
- The light `tree` endpoint requires the BC to also have at least one Policy due to the `MATCH (bc)-[:HAS_POLICY]->(pol:Policy)` clause; BCs without policies will return an empty result from that endpoint. The `full-tree` endpoint does not have this restriction and uses `OPTIONAL MATCH` everywhere.
- Properties are returned sorted by `isKey desc → isForeignKey desc → name asc`, identical to the canvas API's contract, so the inspector and navigator agree on field order.
- The navigator front-end auto-expands a newly created BC during ingestion so the analyst can see new entities appear in real time as SSE events arrive.
- A network failure on `full-tree` is reported but the BC is shown in the tree as empty until a retry succeeds — the navigator does not become unusable.

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose `GET /api/contexts` returning every `BoundedContext` sorted alphabetically by `name`, with each entry including `id`, `name`, `description`, `owner`, `domainType`, `userStoryIds`, and counts of distinct attached aggregates and user stories.
- **FR-002**: System MUST expose `GET /api/contexts/{context_id}/tree` returning a lightweight nested tree containing the BC, its aggregates with summarized commands (`id`, `name`, `actor`) and events (`id`, `name`, `version`), and its policies with `triggerEventId` and `invokeCommandId` for cross-linking.
- **FR-003**: System MUST expose `GET /api/contexts/{context_id}/full-tree` returning a normalized object that includes the BC, its `userStories[]` (with `role`, `action`, `benefit`, `priority`, `status`), its `aggregates[]` (each with embedded `commands[]`, `events[]`, parsed `enumerations[]`, `valueObjects[]`), its `policies[]`, its `readmodels[]` (each with `properties[]` and CQRS `operations[]`), and its `uis[]`.
- **FR-004**: System MUST embed sorted `properties[]` on every `Aggregate`, `Command`, `Event`, and `ReadModel` returned by `full-tree`, sorted by `isKey desc → isForeignKey desc → name asc` with null treated as false.
- **FR-005**: System MUST parse Aggregate `enumerations` and `valueObjects` from their stored JSON-string form into arrays before returning, defaulting to `[]` when null or unparseable.
- **FR-006**: System MUST surface CQRS operations (`operationType` and `triggerEventId`) on each ReadModel together with the human-readable `triggerEventName`, so the navigator can show what each read-model operation reacts to.
- **FR-007**: System MUST return HTTP 404 when `tree` or `full-tree` is requested for a context id that does not exist.
- **FR-008**: System MUST also expose `GET /api/contexts/aggregates/viewer` returning every aggregate across every BC, grouped by BC, with each aggregate carrying its `enumerations[]`, `valueObjects[]`, and `properties[]` — used to power a system-wide aggregate viewer.
- **FR-009**: System MUST allow editing an aggregate's properties through `PUT /api/contexts/aggregates/{aggregate_id}/properties`, upserting Property nodes (keyed by `parentType + parentId + name`) and ensuring each is linked to its parent via `HAS_PROPERTY`.
- **FR-010**: System MUST allow editing an aggregate's enumerations and value objects through `PUT /api/contexts/aggregates/{aggregate_id}/enumerations-valueobjects`, returning the updated aggregate with both fields parsed back into arrays.
- **FR-011**: Navigator UI MUST allow expanding/collapsing every node by id, including utility actions to expand-all and collapse-all.
- **FR-012**: Navigator UI MUST support drag-and-drop of any tree node by populating `dataTransfer` with a JSON payload describing the node and setting `effectAllowed = 'copy'`, so the canvas can accept drops to focus on a node.
- **FR-013**: Navigator state MUST allow real-time additions during ingestion (new BCs, new user stories, assignment of a user story to a BC) without re-fetching the whole tree, and SHOULD auto-expand newly added BCs to surface progress.
- **FR-014**: Navigator MUST cache per-context full-tree responses keyed by context id; a `forceRefresh` request MUST bypass the cache and re-fetch.

### Key Entities

- **BoundedContext** (Neo4j label): the root of every tree branch. Carries `id`, `name`, `displayName`, `description`, `owner`, `domainType`, and `userStoryIds`.
- **UserStory** (Neo4j label): linked to a BC via `IMPLEMENTS`. Carries `role`, `action`, `benefit`, `priority`, `status`. Surfaced on the BC under `userStories[]`.
- **Aggregate / Command / Event / Policy / ReadModel / UI / Property** (Neo4j labels): the full Event Storming tree under a BC, navigated via `HAS_AGGREGATE`, `HAS_COMMAND`, `EMITS`, `HAS_POLICY`, `TRIGGERS`, `INVOKES`, `HAS_READMODEL`, `HAS_UI`, and `HAS_PROPERTY` relationships.
- **CQRSConfig / CQRSOperation** (Neo4j labels): attached to each ReadModel via `HAS_CQRS` → `HAS_OPERATION`. The navigator surfaces operation type and the triggering event id/name.
- **Tree node payload** (frontend): the in-memory representation of any tree row carrying at least `id`, `type`, `name`, plus type-specific fields. Used as the JSON payload during drag-and-drop to the canvas.
- **Navigator store state** (frontend, client-side): contexts list, per-context cached tree, expanded-node id set, newly-added node ids, and pending user-story-to-BC assignments. Mutated incrementally by SSE events from ingestion.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Architects can locate any bounded context in the model from the navigator side panel without first opening the canvas, in a single page-load round-trip.
- **SC-002**: Expanding a bounded context returns its full structural detail (aggregates, commands, events, policies, read models, UIs, user stories) in one request, so the navigator does not chain multiple round-trips per BC.
- **SC-003**: Property ordering is consistent across navigator and canvas: keys appear first, then foreign keys, then alphabetical — so the user's mental model of an entity does not shift between views.
- **SC-004**: Newly created BCs and user stories appear in the navigator within the same UI tick as the corresponding ingestion progress event, with no manual refresh required.
- **SC-005**: Drag-and-drop from the navigator to the canvas works for every node type with no manual id copying.
- **SC-006**: A non-existent context id returns HTTP 404 quickly, and the navigator surfaces the failure without leaving the panel in a broken state.

## Assumptions

- Neo4j is the source of truth; navigator endpoints do not consult any cache outside the database itself.
- The frontend caches `full-tree` results in-memory per context id and may serve stale data until `forceRefresh` is requested; freshness is the caller's responsibility after destructive operations.
- BCs are uniquely identified by their `id`; the human-readable `name` is the sort key but is not assumed to be unique.
- Aggregates store complex value-object and enumeration definitions as JSON strings in Neo4j; both write and read paths agree to (de)serialize them.
- CQRS configuration is one-per-ReadModel (`HAS_CQRS`) with multiple operations under it (`HAS_OPERATION`); each operation may be triggered by at most one event (`TRIGGERED_BY`).
- Drag-and-drop is the only supported way to push a navigator node onto the canvas; there is no "send to canvas" button in the contract.
- The lightweight `tree` endpoint exists primarily for compact summaries; the navigator UI primarily consumes `full-tree` for inspection and editing.
