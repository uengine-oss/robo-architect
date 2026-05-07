# Feature Specification: BPMN Process Diagram Generation per Bounded Context

**Feature Branch**: `011-bpmn-process-export`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/canvas_graph/routes/bpmn_process.py`, `frontend/src/features/canvas/bpmn.store.js`, `frontend/src/features/canvas/ui/BpmnPanel.vue`, `frontend/src/features/canvas/ui/BpmnInspectorPanel.vue`

## User Scenarios & Testing

### User Story 1 - Browse process flows derived from the event storming graph (Priority: P1)

A modeler opens the BPMN view and sees a list of process flows automatically extracted from the canvas. Each flow corresponds to an entry-point Command (one that no Policy invokes), and is summarised with a name like "Place Order → OrderShipped", the involved actors, the originating bounded context, and a node count.

**Why this priority**: The list is the entry point — without it the user has no way to discover which processes the model implies.

**Independent Test**: Hit `GET /api/graph/bpmn/process-flows` against a non-empty graph and confirm it returns one flow per "root" Command with a stable name and `nodeCount > 0`.

**Acceptance Scenarios**:
1. **Given** Commands `A` and `B` where only `A` is not invoked by any Policy, **When** the user lists flows, **Then** only `A` appears as a starting Command.
2. **Given** a flow chain `Cmd1 → Evt1 → Pol1 → Cmd2 → Evt2`, **When** the list is built, **Then** the flow name combines the start Command's display name with the last Event's display name.
3. **Given** Commands without an explicit `actor`, **When** flows are computed, **Then** the actor list defaults to `["System"]`.

### User Story 2 - Render a single flow as BPMN XML with swimlanes (Priority: P1)

The user picks a flow and the system returns a complete BPMN 2.0 XML document plus a structured representation. Actors become lanes, Commands become tasks, Events become intermediate throw events, divergent Commands (multiple emitted Events) get a parallel gateway, the chain begins with a StartEvent and terminates at EndEvents tied to terminal Events. The XML is laid out via a Sugiyama-style algorithm (BFS layering, barycenter crossing minimisation, dynamic lane heights) so it renders cleanly in any BPMN viewer.

**Why this priority**: Hand-laying out BPMN is the slowest part of process work; auto-layout that is "good enough" turns hours into seconds.

**Independent Test**: Call `GET /api/graph/bpmn/process-flow/{startCommandId}` with a known root, paste the returned `bpmnXml` into bpmn.io, and verify it renders with non-overlapping lanes and orthogonal edges.

**Acceptance Scenarios**:
1. **Given** a Command emitting two Events, **When** the BPMN XML is generated, **Then** a `<bpmn:parallelGateway>` is inserted between the task and both intermediate events.
2. **Given** an Event with no downstream Policy, **When** the XML is generated, **Then** that Event is wired to `EndEvent_1` via a sequence flow.
3. **Given** the flow spans three actors, **When** lanes are laid out, **Then** each lane's height adapts to the maximum number of stacked nodes in any single layer (`actor_lane_height`).
4. **Given** a chain that loops or revisits a Command, **When** traversal runs, **Then** the BFS terminates after at most 30 visited commands (safety cap) without infinite recursion.

### User Story 3 - Inspect a single BPMN node for domain context (Priority: P2)

When the user double-clicks a Command or Event shape, a side inspector shows the node's display name, technical name, description, actor, owning Aggregate, owning bounded context, and — for Commands — the linked UI wireframe (if any) found via `(UI)-[:ATTACHED_TO]->(Command)`.

**Why this priority**: BPMN diagrams alone strip the domain semantics; the inspector restores them on demand.

**Independent Test**: Double-click a Command shape and confirm the panel displays Aggregate / Bounded Context / Actor; switch to a Command with an attached UI and confirm the wireframe template renders.

**Acceptance Scenarios**:
1. **Given** a selected Command, **When** the inspector opens, **Then** "Task (Command)" appears as the type badge.
2. **Given** a selected Event, **When** the inspector opens, **Then** "Output Message (Event)" appears as the type badge.
3. **Given** a Command linked to a UI node via `ATTACHED_TO`, **When** the flow API responds, **Then** the `uiMap` entry for that Command id contains the UI's `template`.

### Edge Cases
- A flow whose root Command emits no Events still appears in the list, but with `endEventName = null` and only the start name in the flow label.
- Cycles in the Policy → Command chain are bounded by `visited_cmds < 20` (list step) and `visited_cmds > 30` (XML step); excess steps are dropped silently.
- Sequence flows from Event back to Task (Policy chain) reuse the Policy's display name as the edge label.
- Same source-target-type relation tuples are deduplicated via `seen_rels` before XML emission.
- Node ids containing `-`, `.`, `@`, or spaces are sanitised by `_safe_id()` to remain valid XML ids.
- XML special characters in display names are escaped by `_xml_escape()`.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST expose `GET /api/graph/bpmn/process-flows` returning a list of flows, each rooted at a Command not targeted by any `(:Policy)-[:INVOKES]->(:Command)` edge.
- **FR-002**: Each flow summary MUST include `id`, `name`, `startCommandId`, `startCommandName`, `endEventName`, `actors[]`, `bcId`, `bcName`, and `nodeCount`.
- **FR-003**: The system MUST expose `GET /api/graph/bpmn/process-flow/{start_command_id}` returning `bpmnXml`, `structured`, `startCommand`, `nodes[]`, `relations[]`, and `uiMap`.
- **FR-004**: BPMN traversal MUST follow the chain `(Command)-[:EMITS]->(Event)-[:TRIGGERS]->(Policy)-[:INVOKES]->(Command)` and stop when an Event has no triggered Policy.
- **FR-005**: The generated BPMN XML MUST conform to the BPMN 2.0 namespace and include `bpmn:collaboration`, `bpmn:participant`, `bpmn:process`, `bpmn:laneSet` with one lane per actor, and a `bpmndi:BPMNDiagram` plane with shape and edge geometry.
- **FR-006**: Commands emitting more than one Event MUST be modelled with a `bpmn:parallelGateway` between the task and the events.
- **FR-007**: The system MUST assign each task / event / gateway to the lane corresponding to its Command's `actor` (or the parent Command's actor for events), defaulting to `"System"` when missing.
- **FR-008**: Layout MUST use longest-path BFS layer assignment, barycenter crossing minimisation across at least four sweeps, and per-actor lane heights derived from the maximum stack of same-actor nodes per layer.
- **FR-009**: Sequence flow edges MUST emit orthogonal waypoints (single horizontal segment when source and target are aligned, three-segment H-V-H otherwise).
- **FR-010**: The flow response MUST include a `uiMap` keyed by Command id with `id`, `name`, `displayName`, `description`, and `template` from any attached `UI` node.
- **FR-011**: The system MUST cap traversal at 30 commands per chain to prevent infinite loops on cyclic models.
- **FR-012**: All BPMN endpoints MUST emit SmartLogger events under `api.graph.bpmn.flows.*` and `api.graph.bpmn.flow.*` with HTTP context.

### Key Entities

- **Command** (Neo4j label `Command`): A task in the BPMN process. Provides `name`, `displayName`, `actor`, `description`, plus aggregate / BC context.
- **Event** (Neo4j label `Event`): A BPMN intermediate throw event (or end event when terminal).
- **Policy** (Neo4j label `Policy`): A reactive rule modelled as a sequence-flow label between Event and the next Command.
- **Aggregate** / **BoundedContext** (Neo4j labels `Aggregate`, `BoundedContext`): Provide grouping and lane labelling context.
- **UI** (Neo4j label `UI`): Wireframe attached via `(UI)-[:ATTACHED_TO]->(Command)` and surfaced in the inspector.
- **EMITS / TRIGGERS / INVOKES / HAS_AGGREGATE / HAS_COMMAND / ATTACHED_TO** (relationships): Drive the chain traversal and inspector lookups.

## Success Criteria

### Measurable Outcomes

- **SC-001**: For any graph with at least one root Command, `GET /api/graph/bpmn/process-flows` returns ≥ 1 flow within 1 second under nominal load.
- **SC-002**: Generated BPMN XML opens without validation errors in standard BPMN viewers (bpmn.io, Camunda Modeler) for chains up to 30 nodes.
- **SC-003**: For chains of ≤ 15 nodes, lane and node placement produce zero overlapping shapes after the four barycenter sweeps.
- **SC-004**: The inspector resolves Aggregate, BC, actor, and (when present) UI template for the selected node in a single API round trip.
- **SC-005**: Repeated calls to the flow endpoint with the same `startCommandId` return identical XML when the underlying graph has not changed.

## Assumptions

- "Process flow" is defined exclusively by the EMITS / TRIGGERS / INVOKES skeleton; ad-hoc relationships are not considered.
- Actors come from the Command's `actor` property; Events inherit the actor of their emitting Command.
- A Command without an `actor` is allowed and lands in a `"System"` lane.
- The current implementation always renders Commands as untyped `bpmn:task`; user types (User Task, Service Task) are not differentiated yet.
- Gateway selection is `parallelGateway` for any Command emitting multiple Events; exclusive / inclusive gateways are out of scope.
- Layout constants (`TASK_WIDTH=120`, `LAYER_GAP=180`, `LANE_MIN_HEIGHT=150`, etc.) are tuned for typical 5–15 node flows; very wide diagrams may need user pan / zoom.
- The endpoint trusts that frontend BPMN viewers handle the inline `bioc:` and `color:` namespaces for shape colouring.
