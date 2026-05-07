# Feature Specification: Interactive Canvas Graph Explorer

**Feature Branch**: `002-canvas-graph-explorer`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/canvas_graph/router.py`, `api/features/canvas_graph/routes/canvas_subgraph.py`, `api/features/canvas_graph/routes/canvas_expansion.py`, `api/features/canvas_graph/routes/canvas_event_triggers.py`, `api/features/canvas_graph/routes/graph_maintenance.py`, `frontend/src/features/canvas/`

## User Scenarios & Testing

### User Story 1 - Open a single bounded context on the canvas and see its full Event Storming layout (Priority: P1)

An architect opens the canvas with one or more node ids selected (typically a `BoundedContext`). The canvas renders the BC as a container, with its child Aggregates inside, each Aggregate's Commands grouped to it, and the Events those Commands emit shown to the right. Policies inside the BC are placed near the events that trigger them and the commands they invoke. UI wireframes and ReadModels attached to the BC are also surfaced. The architect can immediately read the Event Storming "story" of that bounded context at a glance.

**Why this priority**: This is the primary view of the system — every other canvas interaction (expand, drill-down, modify) starts from being able to render a coherent BC subgraph in the first place.

**Independent Test**: Given a Neo4j database populated by ingestion, call `GET /api/graph/expand-with-bc/{boundedContextId}` and assert that the response's `nodes` array contains the BC plus its Aggregates, Commands, Events, Policies, UIs, and ReadModels, and that the `relationships` array contains the corresponding `HAS_AGGREGATE`, `HAS_COMMAND`, `EMITS`, `TRIGGERS`, `INVOKES`, `HAS_UI`, and `HAS_READMODEL` edges with no duplicates.

**Acceptance Scenarios**:

1. **Given** a list of node ids, **When** `GET /api/graph/subgraph?node_ids=...` is called, **Then** the response returns each node's id/name/type/properties and every relationship that exists strictly between the requested nodes.
2. **Given** a `BoundedContext` id, **When** the expand-with-bc endpoint is called, **Then** the BC node is included as a container plus all its descendants, every descendant carries `bcId` for grouping, and Commands carry `parentId` referring to their Aggregate.
3. **Given** an `Aggregate`, `Command`, `Event`, or `Policy` id, **When** expand-with-bc is called, **Then** the response includes the parent BC if one can be resolved and the appropriate one-hop neighbours for that node type.
4. **Given** the response payload, **When** the canvas renders, **Then** Aggregate, Command, Event, and ReadModel nodes carry an embedded `properties[]` list (sorted: `isKey desc → isForeignKey desc → name asc`) so individual Property nodes are not displayed on the canvas.

### User Story 2 - Lazily expand a single node to see only its immediate neighbours (Priority: P1)

The architect double-clicks an `Aggregate` chip on the canvas. The canvas calls the lightweight expand endpoint and adds only that aggregate's commands and the events those commands emit. Double-clicking a `Command` adds its emitted events; double-clicking an `Event` adds the policies it triggers and any commands those policies invoke; double-clicking a `Policy` reveals the event/command/aggregate chain around it.

**Why this priority**: Loading the entire graph would overwhelm the canvas at scale. Lazy expansion is the standard interaction pattern that makes the canvas usable on real-world models.

**Independent Test**: For a node of each type (`BoundedContext`, `Aggregate`, `Command`, `Event`, `Policy`), call `GET /api/graph/expand/{node_id}` and verify the returned nodes/relationships match the type-specific rules described in the implementation (e.g. Command → its emitted Events; Event → its triggered Policies and the Commands those Policies invoke).

**Acceptance Scenarios**:

1. **Given** a `BoundedContext` id, **When** `/expand/{id}` is called, **Then** the response includes all child Aggregates, their Commands, the Events those Commands emit, and all Policies (with their trigger event id and invoke command id surfaced for layout).
2. **Given** a `Command` id, **When** the endpoint is called, **Then** only the events that command emits are returned, with `EMITS` relationships.
3. **Given** an `Event` id, **When** the endpoint is called, **Then** the triggered Policies and the Commands they invoke are returned, with `TRIGGERS` and `INVOKES` relationships.
4. **Given** the response, **When** the canvas reads it, **Then** GWT bundles attached to Commands and Policies are returned as `gwtId` plus a `gwtSets[]` array of test cases (with `given/when/then` references and `fieldValues`), so the inspector can show test-case fixtures without a second round-trip.

### User Story 3 - Follow an event-trigger chain across bounded contexts (Priority: P2)

The architect double-clicks an `Event` to investigate which downstream contexts react to it. The canvas calls the event-triggers endpoint, which returns every BC that contains a Policy listening to that event, plus the full contents of each such BC (aggregates, commands, events, policies, UIs, read models). The canvas merges these into the existing layout so the user can visually trace cross-context choreography.

**Why this priority**: Cross-context flows are the highest-value insight an Event Storming model offers. Without this, the architect can only see one BC at a time.

**Independent Test**: Given an `Event` whose downstream policies live in a different BC, call `GET /api/graph/event-triggers/{event_id}` and assert the response includes both the source event id (echoed as `sourceEventId`), the new BC nodes, and a `TRIGGERS` relationship from the source event to each downstream policy.

**Acceptance Scenarios**:

1. **Given** an event with no downstream policies, **When** the endpoint is called, **Then** the response returns empty `nodes` and `relationships` arrays plus the original `sourceEventId`.
2. **Given** an event triggering policies in two different BCs, **When** the endpoint is called, **Then** both BCs are fully populated in the response and the source event has a `TRIGGERS` edge to each consumer policy.
3. **Given** the merged result, **When** rendered, **Then** no relationship is duplicated even if multiple policies in the same BC overlap in their dependencies.

### User Story 4 - Inspect graph health and start fresh (Priority: P3)

The architect opens a stats panel to see how many nodes of each label exist in the graph (e.g. "12 Aggregates, 47 Commands, 51 Events, 8 Policies"). When experimenting with prompts or new ingestion runs, they can wipe the entire canvas/graph with a single destructive action and start over.

**Why this priority**: Operational visibility and "reset" are important for a tool used in iterative modelling sessions, but not part of the core exploration flow.

**Independent Test**: Call `GET /api/graph/stats` and verify it returns `{ total, by_type }`. Call `DELETE /api/graph/clear` and verify it returns `nodes_deleted` and `relationships_deleted` counters that match the prior `total`.

**Acceptance Scenarios**:

1. **Given** a populated graph, **When** stats is requested, **Then** the API returns the total count and a `by_type` map keyed by node label.
2. **Given** an empty graph, **When** stats is requested, **Then** `total: 0` and `by_type: {}` is returned.
3. **Given** the user invokes clear, **When** the operation completes, **Then** every node and relationship in the graph store is removed and the response reports the counts that were deleted.

### Edge Cases

- The subgraph endpoint silently returns empty `nodes`/`relationships` when none of the requested ids exist; it does not 404.
- The expand endpoints return HTTP 404 if the requested node id does not exist.
- Aggregate nodes store `enumerations` and `valueObjects` as JSON-encoded strings in Neo4j; both endpoints parse these into arrays before returning the payload, defaulting to `[]` when the JSON is malformed or null.
- Neo4j temporal types (e.g. `neo4j.time.DateTime`) are coerced to ISO-formatted strings in expand-with-bc responses so the JSON payload is always serializable.
- Relationships are de-duplicated by `(source, target, type)` before being returned to keep the canvas free of overlapping arrows.
- An `Event` whose triggered policies live entirely in the same BC still returns the full BC contents; the architect sees the whole BC rather than a partial expansion.
- The single-node update endpoint (`PUT /api/graph/update-node/{id}`) only accepts a small allow-list of fields (`sceneGraph`, `template`, `description`, `name`, `displayName`, `figmaNodeId`, `figmaFileKey`); attempts to set other fields are silently filtered, and a request with no allowed fields returns HTTP 400.

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose `GET /api/graph/subgraph` that takes a list of node ids and returns the matching nodes plus every relationship that exists between them, with each node carrying `id`, `name`, `type` (its primary Neo4j label), and full `properties`.
- **FR-002**: System MUST expose `GET /api/graph/expand/{node_id}` that returns one-hop neighbours according to the node's type: BC → all Aggregates/Commands/Events plus Policies; Aggregate → its Commands and their Events; Command → emitted Events; Event → triggered Policies and the Commands those Policies invoke; Policy → its triggering Event, invoked Command, the Aggregate that owns the command, and the events that command emits.
- **FR-003**: System MUST expose `GET /api/graph/expand-with-bc/{node_id}` that includes the parent `BoundedContext` (when one can be resolved by walking `HAS_AGGREGATE`, `HAS_COMMAND`, `EMITS`, `HAS_POLICY`, `HAS_UI`, or `HAS_READMODEL` chains) so the canvas can group nodes inside their BC container.
- **FR-004**: System MUST embed each node's `Property` list directly into Aggregate/Command/Event/ReadModel payloads, sorted by `isKey desc → isForeignKey desc → name asc`, instead of returning Property nodes on the canvas.
- **FR-005**: System MUST attach GWT bundles (with parsed `givenRef`, `whenRef`, `thenRef`, and per-test-case `fieldValues`) to Command and Policy nodes so the inspector has the data it needs without an extra round-trip.
- **FR-006**: System MUST expose `GET /api/graph/event-triggers/{event_id}` that returns every BC containing a Policy triggered by the event, fully populated with that BC's Aggregates/Commands/Events/Policies/UIs/ReadModels and the appropriate `TRIGGERS`/`INVOKES`/`HAS_*` relationships.
- **FR-007**: System MUST expose `GET /api/graph/node-context/{node_id}` returning the resolved parent BC id/name/description for any node, or `bcId: null` when no context can be resolved.
- **FR-008**: System MUST de-duplicate relationships in every response by `(source, target, type)`.
- **FR-009**: System MUST coerce Aggregate `enumerations` and `valueObjects` from stored JSON strings into JSON arrays in every response, defaulting to `[]` when missing or malformed.
- **FR-010**: System MUST coerce Neo4j temporal types into ISO-format strings in JSON payloads.
- **FR-011**: System MUST expose `GET /api/graph/stats` returning `total` and `by_type` (per-label counts).
- **FR-012**: System MUST expose a destructive `DELETE /api/graph/clear` that detaches and deletes every node and relationship in the graph and returns counts of what was deleted.
- **FR-013**: System MUST expose `PUT /api/graph/update-node/{node_id}` accepting a small allow-list of editable fields (`sceneGraph`, `template`, `description`, `name`, `displayName`, `figmaNodeId`, `figmaFileKey`) and silently ignoring other fields; the call MUST return HTTP 400 when nothing in the body matches the allow-list.

### Key Entities

- **BoundedContext** (Neo4j label `BoundedContext`): top-level grouping container on the canvas. Holds `id`, `name`, `displayName`, `description`, optional `owner` and `domainType`. Aggregates, Policies, UIs, and ReadModels are scoped under it.
- **Aggregate** (Neo4j label `Aggregate`): a transactional consistency boundary. Owns Commands. Carries `rootEntity`, `invariants`, `enumerations`, and `valueObjects` (the latter two stored as JSON strings, exposed as arrays).
- **Command** (Neo4j label `Command`): a state-changing intent inside an Aggregate. May carry an attached GWT bundle and an `actor` field.
- **Event** (Neo4j label `Event`): a fact emitted by a Command (`EMITS`). May trigger Policies (`TRIGGERS`) — possibly across BCs.
- **Policy** (Neo4j label `Policy`): a reaction to an Event that invokes a Command (`INVOKES`). Lives inside a BC (`HAS_POLICY`).
- **UI** (Neo4j label `UI`): a wireframe attached to a Command/ReadModel/User Story. Holds an optional Figma binding (`figmaNodeId`, `figmaFileKey`) and an editable `sceneGraph` JSON.
- **ReadModel** (Neo4j label `ReadModel`): a query-side model attached to a BC, used by the canvas to render CQRS configuration.
- **Property** (Neo4j label `Property`): a typed field belonging to an Aggregate/Command/Event/ReadModel. Embedded into the parent's payload by the canvas API; not rendered as a standalone node.
- **GWT** (Neo4j label `GWT`): a bundle node attached to a Command or Policy via `HAS_GWT`, holding `givenRef`/`whenRef`/`thenRef` and an array of `testCases` with per-case field values.

## Success Criteria

### Measurable Outcomes

- **SC-001**: The architect can render any single bounded context with its full first-level structure (aggregates, commands, events, policies, UIs, read models) in a single round-trip and without any visible "stitching" of partial responses.
- **SC-002**: Lazy expansion of any node returns only the relevant one-hop neighbourhood, keeping the canvas readable for graphs with hundreds of aggregates.
- **SC-003**: Cross-BC event-trigger chains can be discovered in a single click on the source event, with no relationship duplicated when multiple paths converge.
- **SC-004**: The graph stats panel always reports node counts that match the actual database within one request round-trip.
- **SC-005**: Clearing the graph leaves zero nodes and zero relationships and reports the deleted counts so the user can confirm the wipe completed.
- **SC-006**: Every payload produced by the canvas API is JSON-serializable without further coercion, regardless of which Neo4j temporal or JSON-encoded string fields are involved.

## Assumptions

- Neo4j is the source of truth; the canvas backend never reads from caches and always issues fresh Cypher per request.
- The canvas frontend treats Property nodes as embedded data rather than first-class graph nodes, and trusts the API's sorting (key first, then foreign key, then alphabetical name).
- A node's "primary type" for canvas purposes is its first Neo4j label; nodes are expected to have exactly one Event Storming label.
- The graph store is single-tenant within an instance; clear and stats operate over the entire database.
- Wireframe-related fields (`sceneGraph`, `template`, `figmaNodeId`, `figmaFileKey`) on UI nodes are user-editable through the canvas; structural fields (relationships, ids) are not.
- Cross-BC discovery via the event-triggers endpoint is intentionally heavy: it loads each consuming BC in full so the architect always sees enough surrounding context, accepting the larger payload as a tradeoff for usability.
