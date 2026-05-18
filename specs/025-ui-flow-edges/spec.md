# Feature Specification: UI Sticker Flow Edges with Conditional Gateways

**Feature Branch**: `025-ui-flow-edges`
**Created**: 2026-05-15
**Status**: Draft
**Input**: User description: "이벤트 모델링을 할 때 ui 스티커와 ui 스티커 간 연결선이 없는데, 업로드된 원본 문서의 업무 흐름·UI 흐름을 분석해 UI 스티커 사이의 인터랙션 연결선을 그어주자. 조건 분기는 마름모(gateway)로 단순 표시. 기존 UI→Command→Event→ReadModel→UI 경로와는 별도로, 하이레벨 프로세스 관점의 UI↔UI 흐름을 가시화. 메타모델/Neo4j 데이터모델부터 잘 설계하자 — UI 프레임 간 `NEXT` 류 relation, 조건은 그 relation에 부착."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Auto-derive UI-to-UI flow from source documents during ingestion (Priority: P1)

When a user runs the requirements ingestion workflow (uploaded BRD/PRD/Confluence/Figma), the system reads the document's described business flow and screen flow, and emits a new layer of relationships **between UI stickers** representing "after the user completes this screen, they proceed to that screen." This is independent of the existing data-flow chain (`UI → Command → Event → ReadModel → UI`) and lives at the *user journey / process* layer.

**Why this priority**: Today the event-modeling canvas shows UI stickers as isolated nodes; the only connectivity comes from the implicit data-flow chain. Stakeholders reviewing the canvas cannot answer "what does the user do next?" without re-reading the source document. Producing UI↔UI flow edges is the single highest-leverage change because it turns the canvas into a navigable user journey map.

**Independent Test**: Upload a source document that describes a 3-screen flow (e.g., Login → Dashboard → Item Detail). After the ingestion run completes, open the event-modeling canvas; verify two `NEXT_UI` edges exist between the three corresponding UI stickers and that they are rendered as visible arrows between sticker frames.

**Acceptance Scenarios**:

1. **Given** an uploaded requirements document that contains a linear screen flow with 3 UI frames, **When** the ingestion run completes the `event_storming` phase, **Then** the resulting Neo4j graph contains `(:UI)-[:NEXT_UI]->(:UI)` relationships matching the document's described order.
2. **Given** the source document describes a flow that branches based on a user decision (e.g., "if user clicks Approve … else if user clicks Reject …"), **When** ingestion completes, **Then** the graph contains a `(:Gateway {kind:'exclusive'})` node with `NEXT_UI` edges incoming from the prior UI and outgoing to each branch UI, each outgoing edge carrying a `condition` property quoting the branch label.
3. **Given** the source document is ambiguous about screen ordering for a section, **When** the ingestion run reaches that section, **Then** no `NEXT_UI` edges are emitted for that section and a `GenerationWarning` of code `ui_flow_unclear` is attached to the workflow result with the affected UI ids.
4. **Given** the user re-runs ingestion on the same document, **When** the run completes, **Then** the existing `NEXT_UI` edges and `Gateway` nodes are upserted idempotently (no duplicates, conditions overwrite to current LLM output).

---

### User Story 2 - Visualize the UI flow layer on the event-modeling canvas (Priority: P1)

A modeler opens the event-modeling panel. In addition to the existing horizontal `UI → Command → Event → ReadModel → UI` row, they can see directed arrows running **across UI stickers** at the top, with diamond-shaped `Gateway` nodes inserted wherever the flow branches. Each gateway diamond visually contains a short label of the decision; each outgoing edge from the diamond is annotated with the condition text.

**Why this priority**: A graph in Neo4j with no canvas representation is invisible to the people who use this tool. The visualisation makes the UI flow layer reviewable by domain experts and PMs without opening a separate diagram tool.

**Independent Test**: With the graph state from Story 1, open the event-modeling canvas; verify (a) `NEXT_UI` edges render as arrows between UI sticker frames at the top swimlane, visually distinct from existing data-flow arrows (different colour/style); (b) each `Gateway` node renders as a diamond shape; (c) condition labels are visible on each outgoing edge from a Gateway.

**Acceptance Scenarios**:

1. **Given** the canvas is loading and the graph has `NEXT_UI` edges, **When** the panel finishes rendering, **Then** UI-to-UI arrows are drawn at the UI swimlane height, in a style (e.g., dashed or distinct color) clearly different from the existing solid data-flow arrows.
2. **Given** the graph has a `Gateway {kind:'exclusive'}` node between two UI stickers, **When** the canvas renders, **Then** the gateway is shown as a diamond with the decision label inside and each outgoing arrow shows the `condition` text.
3. **Given** the modeler hovers over a `NEXT_UI` edge, **When** the hover state activates, **Then** a tooltip surfaces the edge `condition` (if any) and the source-document excerpt that motivated this edge.
4. **Given** a UI sticker has no incoming or outgoing `NEXT_UI` edge, **When** the canvas renders, **Then** the sticker still renders normally (orphan UIs are not hidden).

---

### User Story 3 - Inspect and edit a Gateway and its conditions (Priority: P2)

When a modeler selects a `Gateway` node or a `NEXT_UI` edge on the canvas, the Inspector panel opens with editable fields for the gateway's decision label, the `condition` text on each outgoing edge, and the source/target UI references. Edits persist via the existing graph-write API.

**Why this priority**: LLM-derived flows will not always be correct on first generation. Without an editor, the auto-generation is a one-shot artifact that becomes stale once anyone notices a mistake. Editing closes the loop.

**Independent Test**: Open a Gateway on the canvas; change its decision label and one of its outgoing edge conditions; save; reload the canvas — both edits persist.

**Acceptance Scenarios**:

1. **Given** a `Gateway` node is selected, **When** the Inspector renders, **Then** fields for `label`, `kind` (exclusive only in v1), and a per-outgoing-edge condition list are shown and editable.
2. **Given** the user edits a condition and saves, **When** the save request completes, **Then** the `condition` property on the corresponding `NEXT_UI` relationship is updated in Neo4j and the canvas reflects it without page reload.
3. **Given** the user deletes a Gateway from the Inspector, **When** the delete request completes, **Then** the Gateway node is removed and its incoming/outgoing `NEXT_UI` edges are stitched into a single direct `(:UI)-[:NEXT_UI]->(:UI)` edge per remaining branch, or simply removed if the deletion was destructive (user confirms which).
4. **Given** the user manually draws a `NEXT_UI` edge between two UI stickers from the canvas, **When** the change persists, **Then** the new edge appears with an empty `condition` and a `source:'manual'` marker so it survives subsequent ingestion re-runs without being overwritten by the LLM.

---

### Edge Cases

- **No screen-flow signal in source**: A document that only describes data shape (e.g., a glossary or schema) yields zero `NEXT_UI` edges. The system emits a `GenerationWarning` with code `ui_flow_unclear` listing the affected BCs/UIs and does not fabricate edges.
- **Cycle in the user flow**: A document may legitimately describe loops (e.g., "after submitting feedback, return to Dashboard"). Cycles are allowed; the system stores them as ordinary edges. The renderer must not infinite-loop when laying out the flow.
- **Cross-BC flow**: A `NEXT_UI` edge may legitimately link UIs in different BoundedContexts (e.g., Auth → Catalog). The relationship is stored regardless of BC membership; the renderer draws it across swimlanes.
- **Branch with >2 paths**: An exclusive gateway with 3+ outgoing edges is allowed. Each outgoing edge carries its own `condition`.
- **Self-edge**: A UI looping back to itself (e.g., form validation error stays on the same screen) is allowed but must be visually rendered as a self-loop rather than overlapping the sticker.
- **Manual edit collides with re-ingest**: When the user has flagged an edge as `source:'manual'`, the LLM must not delete or overwrite it on re-ingest. The LLM may add new edges around it.
- **Gateway with one outgoing edge**: Treated as a degenerate gateway — the system warns (`gateway_single_branch`) and offers to collapse it, but does not auto-delete.
- **Edge to a UI in a different language/locale variant**: Out of scope for v1; treat locale variants as the same UI node.
- **Deleted UI referenced by an edge**: When a UI is deleted, its incident `NEXT_UI` edges and any Gateway that loses all branches must be cleaned up atomically.

## Requirements *(mandatory)*

### Functional Requirements

**Metamodel & graph schema**

- **FR-001**: The graph schema MUST introduce a `NEXT_UI` relationship type with allowed pattern `(:UI|:Gateway)-[:NEXT_UI]->(:UI|:Gateway)` to express user-journey continuity at the UI layer. This relationship is semantically distinct from the existing `ATTACHED_TO` and any data-flow edges.
- **FR-002**: The graph schema MUST introduce a `Gateway` node label representing a branching point. In v1 the only supported `kind` value is `exclusive` (XOR diamond). Future `parallel`/`inclusive` kinds are out of scope but the property name MUST be reserved.
- **FR-003**: Each `NEXT_UI` relationship MUST carry the following properties: `id` (UUID, idempotent across re-ingest), `condition` (string, may be empty), `source` (enum `llm|manual`, default `llm`), `documentExcerpt` (string, the snippet that justified the edge, may be empty), `createdAt`, `updatedAt`.
- **FR-004**: Each `Gateway` node MUST carry: `id`, `key` (deterministic, BC-scoped slug for idempotent upsert), `label` (decision question, e.g., "주문 승인?"), `kind` (`exclusive` in v1), `boundedContextId` (the BC that owns the gateway; cross-BC flow MAY still pass through it), `createdAt`, `updatedAt`.
- **FR-005**: A `Gateway` MUST be connected to its containing BoundedContext via `(:BoundedContext)-[:HAS_GATEWAY]->(:Gateway)` for retrieval and lifecycle management.

**Ingestion: derivation from source documents**

- **FR-006**: During the event-storming ingestion workflow, after UI wireframes are emitted, a new dedicated phase MUST analyze the source document(s) to derive UI-layer flow and persist `NEXT_UI` edges and `Gateway` nodes. This phase MUST run after UI wireframes exist so it can reference them by id.
- **FR-007**: The LLM prompt for this phase MUST instruct the model to extract user-journey transitions ("after screen A the user goes to screen B") and decision points ("if … then … else …") from the source text and bind them to the existing UI node ids by name match (case-insensitive, trimmed, displayName preferred).
- **FR-008**: The phase MUST be idempotent: re-running ingestion on the same document re-derives the LLM output and MERGEs `NEXT_UI` and `Gateway` nodes by their deterministic keys, updating properties in place. `source:'manual'` edges MUST NOT be deleted or overwritten by this phase.
- **FR-009**: When the LLM cannot bind a transition to a known UI id (e.g., the document mentions "Settings screen" but no UI node by that name exists), the system MUST emit a `GenerationWarning` with code `ui_flow_unresolved_target` carrying the unresolved name and the inferred source UI, and MUST NOT create dangling edges.
- **FR-010**: When the document contains no detectable screen flow, the phase MUST complete successfully with zero edges and emit a single `GenerationWarning` with code `ui_flow_unclear`. The phase MUST NOT block the overall ingestion run.

**API surface**

- **FR-011**: The system MUST expose a graph-write endpoint to upsert/delete `NEXT_UI` edges and `Gateway` nodes from the canvas Inspector. Existing graph-write conventions in the codebase (idempotent MERGE, UUID-based ids, atomic per-call) MUST be followed.
- **FR-012**: The endpoint MUST validate that endpoint nodes referenced by `sourceId`/`targetId` exist and are of label `UI` or `Gateway`; otherwise return HTTP 400.
- **FR-013**: Deleting a Gateway via the endpoint MUST require the client to specify a strategy (`stitch` to merge incoming/outgoing edges into direct UI→UI edges, or `drop` to remove the gateway and all its incident edges). No default — the client picks.

**Canvas visualization**

- **FR-014**: The event-modeling canvas MUST render `NEXT_UI` edges visually distinct from existing data-flow arrows (different stroke style and/or color), running across UI stickers in the UI swimlane.
- **FR-015**: The canvas MUST render `Gateway` nodes as diamond shapes (rhombus), with the gateway `label` shown inside or directly above the diamond.
- **FR-016**: Each outgoing edge from a `Gateway` MUST display its `condition` text as an edge label.
- **FR-017**: Hovering over a `NEXT_UI` edge MUST surface a tooltip containing the `condition` (if any) and the `documentExcerpt` (truncated to ~200 chars with an ellipsis if longer).
- **FR-018**: Selecting a `Gateway` node or a `NEXT_UI` edge MUST open the Inspector with the editable fields specified in FR-019.

**Inspector editing**

- **FR-019**: The Inspector MUST support editing for: (a) Gateway `label` and `kind`; (b) per-outgoing `NEXT_UI` edge `condition`; (c) manual creation of a `NEXT_UI` edge between two UIs via a drag-from-handle interaction on the canvas; (d) deletion of a `Gateway` with the required strategy choice.
- **FR-020**: Edits MUST persist via the API in FR-011 and the canvas state MUST refresh without a full page reload.
- **FR-021**: Manually created or edited edges MUST have `source` set to `manual` so subsequent ingestion runs preserve them.

**Observability**

- **FR-022**: All operations (LLM derivation, upserts, deletes) MUST emit structured logs under categories `agent.nodes.ui_flow.*` and `api.graph.ui_flow.*` including workflow id, BC id, counts of edges/gateways created/updated/skipped, and warning codes when applicable.
- **FR-023**: The ingestion run summary MUST include counts: `next_ui_edges_created`, `gateways_created`, `ui_flow_warnings` (broken down by code).

### Key Entities

- **UI** (existing label, unchanged): the screen sticker. New UI flow edges originate and terminate at UI nodes.
- **Gateway** (new label): a branching decision point. Properties: `id`, `key`, `label`, `kind` (`exclusive` v1), `boundedContextId`, `createdAt`, `updatedAt`. Rendered as a diamond.
- **NEXT_UI** (new relationship): directed edge representing "after this comes that" at the user-journey layer. Properties: `id`, `condition`, `source` (`llm|manual`), `documentExcerpt`, `createdAt`, `updatedAt`.
- **HAS_GATEWAY** (new relationship): `(:BoundedContext)-[:HAS_GATEWAY]->(:Gateway)` for BC ownership and lifecycle.
- **GenerationWarning** (existing concept, new codes): `ui_flow_unclear`, `ui_flow_unresolved_target`, `gateway_single_branch`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a benchmark corpus of 5 representative source documents (each describing a flow with ≥3 screens and ≥1 branch), the ingestion run produces UI-flow graphs whose edge set has ≥80% precision and ≥80% recall vs. a human-curated gold standard, measured per document and averaged.
- **SC-002**: A modeler can review the auto-generated UI flow on the canvas and correct one wrong edge in ≤30 seconds end-to-end (open Inspector → change condition or redraw edge → save).
- **SC-003**: Re-running ingestion on the same document with no source changes results in zero net changes to `NEXT_UI` edges and `Gateway` nodes (idempotent: same ids, same property values, same `updatedAt` if no LLM drift, or only `updatedAt` refresh if drift).
- **SC-004**: Manual edits (edges or gateways with `source='manual'`) survive 100% of subsequent re-ingest runs on the same document.
- **SC-005**: For a graph with up to 50 UI nodes and 80 `NEXT_UI` edges, the event-modeling canvas renders the UI-flow layer in under 2 seconds on a developer laptop.
- **SC-006**: Across the v1 launch period, ≥90% of `Gateway` nodes the LLM produces have a non-empty `label` and ≥2 outgoing edges each with a non-empty `condition`. (Quality floor — anything below should be flagged as a regression.)
- **SC-007**: Zero dangling `NEXT_UI` edges (edges pointing to a non-existent UI or Gateway) ever appear in production after this feature ships — measured by a periodic graph-integrity check.

## Assumptions

- The existing UI wireframe ingestion phase already emits UI nodes with stable `id` and `displayName` values that the new UI-flow phase can reference. (Verified: `api/features/ingestion/event_storming/neo4j_ops/ui_wireframes.py` writes `ui.id` and `ui.displayName`.)
- "Source document" in v1 means the text/markdown body that the requirements ingestion pipeline already consumes (uploaded PRD/BRD, Confluence import, Figma textual descriptions). No new ingestion sources are introduced.
- The existing event-modeling canvas component is extensible enough to render additional edge types and node shapes at the UI swimlane; if it is not, a small refactor is in scope.
- Only `exclusive` gateways are needed for v1. Parallel/inclusive gateways may exist in the source document but will be modeled as exclusive gateways (each path treated as a separate exclusive branch) with a `gateway_kind_downgrade` warning. This is a known limitation, not a bug.
- The LLM has access to enough context (the source document text plus the list of UI nodes for this run) to bind transitions to UI ids by name match. No retrieval-augmented step over historical sessions is needed.
- The Inspector and the canvas-edit workflow already exist and the new entity types plug into them; the spec does not require building a separate edit UI from scratch.
- Cross-BC `NEXT_UI` edges are allowed and rendered, but no extra cross-BC governance (approval, ownership transfer) is in scope for v1.
- Performance target in SC-005 assumes a developer laptop with the existing canvas renderer; production SLOs for very large graphs (>200 UIs) are out of scope for v1.
