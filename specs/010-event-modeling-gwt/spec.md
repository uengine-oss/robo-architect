# Feature Specification: Given-When-Then (GWT) Test Scenario Editor

**Feature Branch**: `010-event-modeling-gwt`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/canvas_graph/routes/gwt.py`, `api/features/ingestion/event_storming/nodes_gwt.py`, `frontend/src/features/canvas/ui/InspectorPanel.vue`, `frontend/src/features/eventModeling/ui/EventModelingPanel.vue`

## User Scenarios & Testing

### User Story 1 - Auto-generated GWT scaffolding from ingestion (Priority: P1)

When the Event Storming ingestion workflow finishes building Aggregates / Commands / Events for a bounded context, each Command is automatically annotated with a Given-When-Then bundle. The Given references the Command itself (precondition / input), the When references the Aggregate that handles it, and the Then references the resulting Event. Each part carries a `fieldValues` map of property names to realistic test values produced by the LLM.

**Why this priority**: GWT is the contract between domain experts and engineers. Without it, the modeling output is just a graph of names; with it, every Command becomes BDD-testable on day one.

**Independent Test**: Run an ingestion session; afterwards open any Command in the canvas inspector and verify a populated GWT bundle is present without any human edit.

**Acceptance Scenarios**:
1. **Given** an ingestion run that produced at least one Command and matching Event, **When** the `generate_gwt_node` step finishes, **Then** the Command exposes `given`, `when`, and `then` candidates with referenced node ids and types (`Command`, `Aggregate`, `Event`).
2. **Given** the LLM call fails for a Command, **When** the fallback path runs, **Then** a basic GWT structure with empty `fieldValues` is still attached so downstream UI never sees a blank Command.
3. **Given** there are no Commands in the workflow state, **When** the GWT node executes, **Then** it transitions directly to `SAVE_TO_GRAPH` without raising.

### User Story 2 - Editing GWT test cases in the Inspector (Priority: P1)

A modeler opens a Command on the canvas, switches to the GWT tab, and edits the scenario as a decision table: multiple test-case rows, each with a description and field-value maps for Given/When/Then. On save the bundle is upserted to Neo4j as a single `GWT` node attached via `HAS_GWT` to the Command, with all test cases serialized as JSON.

**Why this priority**: The auto-generated GWT is a starting point; teams must refine values, add edge cases, and remove invalid ones. Without an editor the auto-generation has no follow-through.

**Independent Test**: Open a Command, add a second test case, save, reload — the second row persists.

**Acceptance Scenarios**:
1. **Given** a Command without any `GWT` node, **When** the user saves a GWT bundle, **Then** `POST /api/graph/gwt/upsert` creates a `GWT {parentType:"Command", parentId:<cmd.id>}` node and a `(Command)-[:HAS_GWT]->(GWT)` edge.
2. **Given** an existing `GWT` node, **When** the user saves edits, **Then** the same node is updated (MERGE on parentType + parentId), `updatedAt` is refreshed, and `testCases` JSON is overwritten.
3. **Given** the user adds rows referencing additional nodes via `givenRef`/`whenRef`/`thenRef`, **When** the upsert succeeds, **Then** any prior `(GWT)-[:REFERENCES]->()` edges are deleted and recreated to match the new refs.

### User Story 3 - GWT shown only for Commands (Priority: P2)

The inspector exposes the GWT editor only for nodes labelled `Command`. Aggregates, Events, and ReadModels show property editors instead. Policies are intentionally excluded from GWT generation in the current scope.

**Why this priority**: Limits cognitive load and avoids producing GWT for nodes where the semantics are unclear.

**Independent Test**: Open an Event in the inspector — no GWT tab visible. Open a Command — tab visible.

**Acceptance Scenarios**:
1. **Given** the selected node label is `Event`, **When** the inspector renders, **Then** `showGWTEditor` evaluates to false.
2. **Given** the selected node label is `Command`, **When** the inspector renders, **Then** the GWT editor section is shown.

### Edge Cases
- Upsert called with an empty `parentId` returns HTTP 400.
- A `GWT` node with `parentType` not matching any label on the parent fails the `WHERE $parent_type IN labels(parent)` guard and the MERGE returns no row → HTTP 500 with detail "Failed to upsert GWT".
- Reference targets (`referencedNodeId` + `referencedNodeType`) that don't exist in the graph silently produce zero `REFERENCES` edges; the bundle still saves.
- Backward compatibility: legacy single-row payloads with `data.given` / `data.when` / `data.then` are wrapped into a one-element `gwtSets` array on the frontend.
- LLM returns content wrapped in ```json fences — the parser strips fences before `json.loads`.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST attempt LLM-based GWT generation for every Command produced during an Event Storming ingestion run.
- **FR-002**: Each generated GWT MUST include `referencedNodeId` and `referencedNodeType` for Given (Command), When (Aggregate), and Then (Event), bound to the actual ids in the same workflow state.
- **FR-003**: When LLM generation fails, the system MUST attach a fallback GWT with empty `fieldValues` so no Command is left without scaffolding.
- **FR-004**: The system MUST expose `POST /api/graph/gwt/upsert` accepting `parentType` (`Command` or `Policy`), `parentId`, optional `givenRef`/`whenRef`/`thenRef`, and a list of `testCases`.
- **FR-005**: The upsert MUST be idempotent per (`parentType`, `parentId`): repeated calls update the same `GWT` node, refresh `updatedAt`, and overwrite serialized fields.
- **FR-006**: The upsert MUST attach the GWT to its parent via `(parent)-[:HAS_GWT]->(gwt:GWT)`.
- **FR-007**: Each test case MUST persist `scenarioDescription`, `givenFieldValues`, `whenFieldValues`, and `thenFieldValues` together as a single JSON-serialized array on the GWT node.
- **FR-008**: The upsert MUST replace existing `(GWT)-[:REFERENCES]->()` edges with the current Given/When/Then references on every save.
- **FR-009**: The inspector UI MUST render the GWT editor only when the selected node is labelled `Command`.
- **FR-010**: When the user saves edits, the inspector MUST send the GWT bundle to `/api/graph/gwt/upsert` independently of the general node-save path (`/api/chat/confirm`).
- **FR-011**: The system MUST validate that `parentId` is non-empty (HTTP 400 otherwise).
- **FR-012**: All GWT operations MUST be logged via SmartLogger under `api.graph.gwt.upsert` and `agent.nodes.generate_gwt.*` categories with workflow context.

### Key Entities

- **GWT** (Neo4j label `GWT`): A bundle of BDD test cases attached to a single parent Command (or Policy). Properties: `id` (UUID), `parentType`, `parentId`, `givenRef` (JSON), `whenRef` (JSON), `thenRef` (JSON), `testCases` (JSON array), `createdAt`, `updatedAt`.
- **Command** (Neo4j label `Command`): The behavioural element a GWT bundle describes. Holds `id`, `name`, `displayName`, `actor`, `description`.
- **Aggregate** (Neo4j label `Aggregate`): Referenced by the When clause as the handler of the Command.
- **Event** (Neo4j label `Event`): Referenced by the Then clause as the outcome.
- **HAS_GWT** (relationship): `(Command|Policy)-[:HAS_GWT]->(GWT)`.
- **REFERENCES** (relationship): `(GWT)-[:REFERENCES]->(Command|Aggregate|Event)`, recreated on every save.

## Success Criteria

### Measurable Outcomes

- **SC-001**: After a successful ingestion run, 100% of newly created Commands have a non-null Given/When/Then triple (LLM or fallback).
- **SC-002**: A round-trip "open Command → edit GWT → save → reload" preserves all rows, descriptions, and field values exactly.
- **SC-003**: Repeated upserts for the same Command produce exactly one `GWT` node and one `HAS_GWT` edge (no duplicates).
- **SC-004**: GWT save latency stays below 500 ms for bundles with up to 20 test cases under nominal Neo4j load.
- **SC-005**: Inspector hides the GWT editor for every non-Command node label without throwing UI errors.

## Assumptions

- Policies are intentionally out of scope for GWT generation in the current implementation, although the upsert API accepts `parentType="Policy"` for future use.
- The frontend treats `gwtSets` as the source of truth and falls back to top-level `given`/`when`/`then` only for backward compatibility with older payloads.
- Field-value generation quality depends on the LLM provider configured by `get_llm_provider_model()`; downstream code does not validate the realism of values.
- Reference integrity is best-effort: if a referenced node disappears later, dangling `REFERENCES` edges are not auto-pruned.
- The `GWT` node lives under the `/api/graph` prefix together with the rest of the canvas-graph routes.
