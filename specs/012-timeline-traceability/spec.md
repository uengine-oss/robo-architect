# Feature Specification: Big Picture Timeline and Element Traceability

**Feature Branch**: `012-timeline-traceability`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/canvas_graph/routes/bigpicture_timeline.py`, `api/features/canvas_graph/routes/traceability.py`, `frontend/src/features/canvas/bigpicture.store.js`, `frontend/src/features/canvas/ui/BigPicturePanel.vue`, `frontend/src/features/canvas/ui/InspectorPanel.vue`

## User Scenarios & Testing

### User Story 1 - Cross-BC big-picture timeline (Priority: P1)

A modeler opens the Big Picture view and sees every Event in the system arranged on a 2-D grid: rows are bounded contexts (swimlanes), columns are sequence steps assigned by topological sort across the Event → Policy → Command → Event dependency graph. Cross-BC and same-BC Policy connections are rendered as arrows so the user can read the system-wide narrative left-to-right.

**Why this priority**: Without a single-screen view of how Events flow between bounded contexts, teams cannot reason about end-to-end choreography or detect orphan Events.

**Independent Test**: Hit `GET /api/graph/bigpicture-timeline` against a graph with at least two BCs connected via Policy and confirm the response contains both swimlanes plus a `connection` whose `type` is `cross-bc`.

**Acceptance Scenarios**:
1. **Given** an Event in BC `A` that triggers a Policy attached to BC `B` invoking a Command emitting Event `B1`, **When** the timeline is fetched, **Then** the response includes a `connection` of type `cross-bc` with `sourceBcId = A`, `targetBcId = B`, `sourceEventId`, `policyId`, and `targetEventId` populated.
2. **Given** a chain `Evt1 → Pol → Cmd → Evt2` within the same BC, **When** the timeline is fetched, **Then** a `same-bc` connection is added and `Evt2.sequence > Evt1.sequence`.
3. **Given** Events with no Policy-based dependencies in the same BC, **When** sequences are assigned, **Then** they share the same sequence number (rendered stacked vertically in the same column).
4. **Given** an Event that triggers a Policy with no `INVOKES` target yet, **When** the timeline is fetched, **Then** the source Event still carries a `triggeredPolicies` entry with `targetEventId: null`.

### User Story 2 - Focused timeline starting from a single BC (Priority: P2)

A modeler picks one BC and the system returns only that BC plus everything reachable downstream via the outbound Event-Policy-Command-Event chain. Sequence numbering is recomputed inside the filtered subset so the user gets a clean, locally-scoped narrative.

**Why this priority**: Full big-picture views become noisy in large systems; per-BC focus mode lets engineers reason about a feature slice without distraction.

**Independent Test**: Call `GET /api/graph/bigpicture-timeline/{bc_id}` for an outbound-only BC and verify the response contains the start BC plus only its downstream BCs.

**Acceptance Scenarios**:
1. **Given** a BC with no outbound Policy connections, **When** the focused timeline is fetched, **Then** the response contains exactly that one BC.
2. **Given** start BC `A` with outbound chains into `B` and `C`, **When** the focused timeline is fetched for `A`, **Then** swimlanes for `A`, `B`, and `C` are present and unrelated BCs are excluded.

### User Story 3 - End-to-end traceability for any DDD node (Priority: P1)

The user clicks any Aggregate / Command / Event / ReadModel / Policy / BoundedContext on the canvas, opens the inspector's "Traceability" tab, and sees the full chain that justifies that node's existence: the DDD node itself → its Bounded Context → the User Story that drove it (with role / action) → the originating Business Logic flow (Given-When-Then steps and coupled domains) → the actual source Function (file path, line range, source code, READS / WRITES tables with columns).

**Why this priority**: Every model element has to be defensible against the legacy code it came from; without traceability the canvas is just an opinion.

**Independent Test**: Pick a Command id that you know was generated from analysis; call `GET /api/graph/traceability/{command_id}` and confirm at least one chain returns with steps `DDD Node → Bounded Context → User Story → Business Logic → Function` and that the Function's `file_path` and `code_text` match a real file.

**Acceptance Scenarios**:
1. **Given** a `Command` node with at least one `(UserStory)-[:IMPLEMENTS]->(Command)` edge whose User Story has a `sourceUnitId`, **When** traceability is fetched, **Then** the response contains a chain ending in a Function step with `id == sourceUnitId`.
2. **Given** the Function reads / writes tables, **When** traceability is fetched, **Then** each table appears once in the Function step with merged `access` (e.g. `["READS","WRITES"]`) and a deduplicated columns list.
3. **Given** multiple User Stories point at the same Function, **When** chains are returned, **Then** duplicate chains for the same `function_id` are collapsed to one entry.
4. **Given** a node id that does not exist, **When** traceability is requested, **Then** the API returns HTTP 404 "Node not found".
5. **Given** a node type the API does not recognise, **When** traceability runs, **Then** a generic outbound-edge query is used as a fallback to discover related User Stories.

### Edge Cases
- Standalone Events (in no Policy chain) get a sequence number assigned per BC at the tail of the topological order so they still appear on the grid.
- Events appearing only in the dependency graph but not in any swimlane are skipped during sequence assignment.
- Cross-BC and same-BC connections are emitted into the same `connections[]` array with a `type` discriminator.
- The traceability `_US_QUERIES` map intentionally uses different relationship paths per node type (e.g. `IMPLEMENTS` for Command/Aggregate/BC, `HAS_EVENT` for Event, BC-mediated lookup for ReadModel and Policy).
- Business Logic steps without a `coupled_domain` are still added to `flow` but skipped from `domain_couplings`.
- `topological_sort` uses BFS by levels: nodes with the same in-degree-0 wave receive the same sequence number, enabling vertical stacking.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST expose `GET /api/graph/bigpicture-timeline` returning `swimlanes[]`, `connections[]`, and `allBCs[]`.
- **FR-002**: Each swimlane MUST aggregate its Events with `commandId`, `commandName`, `aggregateId`, `aggregateName`, `actor`, and a `sequence` integer.
- **FR-003**: Swimlane `actors` MUST union the `actor` fields of contained Commands and the `role` fields of `(UserStory)-[:IMPLEMENTS]->(BoundedContext)` edges, defaulting to `["System"]` when empty.
- **FR-004**: The system MUST emit two connection categories: `cross-bc` (source BC ≠ target BC) and `same-bc` (source BC == target BC), both keyed by Policy.
- **FR-005**: Sequence assignment MUST use a level-by-level topological sort over the Event dependency graph; events at the same level MUST share the same sequence number.
- **FR-006**: Events without dependencies MUST be appended after the topological tail, grouped by BC so events in the same BC share a sequence.
- **FR-007**: The system MUST expose `GET /api/graph/bigpicture-timeline/{bc_id}` returning only the start BC plus BCs reachable through outbound Policy chains, with sequence numbers recomputed inside that subset.
- **FR-008**: The system MUST expose `GET /api/graph/traceability/{node_id}` returning `node` and `chains[]`.
- **FR-009**: Each traceability chain MUST be ordered as: `DDD Node` → `Bounded Context` (when resolvable) → `User Story` → `Business Logic` (when present) → `Function` (when `sourceUnitId` resolves).
- **FR-010**: The User Story discovery query MUST use a per-label path mapping (`Command`/`Event`/`Aggregate`/`BoundedContext`/`ReadModel`/`Policy`) and fall back to a generic outbound query for unknown labels.
- **FR-011**: The Function step MUST include `id`, `name`, `summary`, file `location` (file_name + ":" + start_line + "-" + end_line), raw `code_text`, and grouped `tables` listing column metadata and READS / WRITES access modes.
- **FR-012**: Duplicate chains sharing the same `function_id` MUST be collapsed; chains with no resolvable Function MUST still be returned.
- **FR-013**: A non-existent `node_id` MUST return HTTP 404.
- **FR-014**: All endpoints MUST log under `api.graph.bigpicture.*` and `graph.traceability.*` with HTTP context and result counts.

### Key Entities

- **BoundedContext** (Neo4j label `BoundedContext`): A swimlane row in the timeline; root of the per-BC focused view.
- **Event** (Neo4j label `Event`): The atomic unit positioned on the timeline grid by `sequence`.
- **Policy** (Neo4j label `Policy`): The connector that creates dependency edges between Events (`TRIGGERS` / `INVOKES`).
- **Command** / **Aggregate** (Neo4j labels): Provide actor and grouping metadata for events.
- **UserStory** (Neo4j label `UserStory`): The "why" anchor in traceability chains; carries `role`, `action`, and `sourceUnitId` linking to a Function.
- **BusinessLogic** (Neo4j label `BusinessLogic`): The intermediate step describing Given-When-Then flow and `coupled_domain`.
- **FUNCTION** (Neo4j label `FUNCTION`): The legacy-code anchor with `function_id`, `file_path`, `start_line`, `end_line`, `code_text`.
- **Table** / **Column** (Neo4j labels): Data dependencies surfaced via `READS` / `WRITES` from a Function.
- **HAS_AGGREGATE / HAS_COMMAND / EMITS / TRIGGERS / INVOKES / HAS_POLICY / IMPLEMENTS / HAS_EVENT / HAS_READMODEL / HAS_BUSINESS_LOGIC / READS / WRITES** (relationships): The traversal alphabet for both endpoints.

## Success Criteria

### Measurable Outcomes

- **SC-001**: For graphs with up to 200 Events and 50 BCs, the global timeline endpoint responds within 2 seconds under nominal Neo4j load.
- **SC-002**: For any Event in a fully chained scenario, its sequence is strictly greater than the sequence of every Event it transitively depends on.
- **SC-003**: For any DDD node generated from analysed source code, traceability returns at least one chain whose Function `code_text` matches the on-disk file content at `file_path`.
- **SC-004**: Duplicate Function chains never appear in a single traceability response (verified by `seen_funcs` deduplication).
- **SC-005**: The focused per-BC endpoint returns a swimlane subset that is a strict subgraph of (or equal to) the global response for the same graph.
- **SC-006**: 100% of swimlanes carry a non-empty `actors` array, even when no Command actor or User Story role exists.

## Assumptions

- A "phase" in the timeline equals one BFS level in the Event dependency graph, not wall-clock time.
- The same-Aggregate command order is intentionally NOT used as an implicit dependency; only Policy-mediated chains create order.
- "Outbound" reachability in the focused view follows a single hop `(BC)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(:Command)-[:EMITS]->(:Event)-[:TRIGGERS]->(:Policy)<-[:HAS_POLICY]-(targetBC)`; multi-hop transitive closures are not computed by the API.
- A User Story without a `sourceUnitId` cannot reach the Function step and the chain stops at the User Story; this is acceptable.
- The Function step assumes `f.function_id == sourceUnitId`; if upstream ingestion changes that contract, the chain breaks silently.
- Columns lacking a `name` are filtered out of the table summary.
- Frontend rendering (BigPicturePanel.vue) is responsible for X-positioning by `sequence` and Y-stacking when several events share a sequence inside a BC; the API exposes only the data, not pixel coordinates.
