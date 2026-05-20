# Feature Specification: ReadModel CQRS Projection Configuration

**Feature Branch**: `006-readmodel-cqrs-config`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/readmodel_cqrs/router.py`, `frontend/src/features/canvas/ui/ReadModelCQRSConfigModal.vue`, `frontend/src/features/canvas/ui/ReadModelCQRSEditor.vue`

## User Scenarios & Testing

### User Story 1 - Define a CQRS projection that materializes a ReadModel from domain events (Priority: P1)

When a ReadModel needs to be kept in sync with the write side, the architect opens "ReadModel CQRS 설정" on the ReadModel node, picks a triggering Event (e.g., `OrderPlaced`), declares the operation kind (INSERT/UPDATE/DELETE), and maps Event payload fields onto ReadModel properties. The configuration is persisted in Neo4j as a `CQRSConfig`/`CQRSOperation`/`CQRSMapping` subgraph attached to the ReadModel.

**Why this priority**: Without this, ReadModels are documented but have no executable semantics; the generated PRD/agent context cannot describe how the projection is computed and downstream code generators cannot scaffold the projector.

**Independent Test**: Open a ReadModel with no CQRS, click "Add Operation", select an Event, choose INSERT, save, and verify the operation appears in `GET /api/readmodel/{id}/cqrs`.

**Acceptance Scenarios**:

1. **Given** a ReadModel with provisioning type CQRS, **When** the user opens the CQRS editor, **Then** available Events (with their properties) and ReadModel properties load from `/api/readmodel/{id}/cqrs/events` and `/api/readmodel/{id}/properties`.
2. **Given** an open editor, **When** the user creates an operation `(INSERT, OrderPlaced)`, **Then** a `CQRSOperation` node is created and linked `(:CQRSConfig)-[:HAS_OPERATION]->(:CQRSOperation)-[:TRIGGERED_BY]->(:Event)`.
3. **Given** an existing operation, **When** the user adds a mapping from event field `customerId` to ReadModel property `ownerId`, **Then** a `CQRSMapping` node is created with `[:SOURCE]` and `[:TARGET]` edges to the two `Property` nodes.

### User Story 2 - Filter projections with WHERE conditions (Priority: P2)

For UPDATE/DELETE operations, the architect needs to express *which* ReadModel rows are affected (e.g., "where row.orderId = event.orderId"). The editor lets the user pick a ReadModel-side `Property`, an event-side `Property`, and an operator; persistence creates a `CQRSWhere` node.

**Why this priority**: INSERT works without filters, but UPDATE/DELETE projections are unsafe without a row selector — most non-trivial projections need this within the first iteration.

**Independent Test**: For an UPDATE operation, add a where condition `(targetProp=Order.id, sourceEventField=OrderShipped.orderId, operator='=')` and verify it round-trips on the next `GET /api/readmodel/{id}/cqrs`.

**Acceptance Scenarios**:

1. **Given** an UPDATE operation, **When** the user adds a where condition, **Then** `(:CQRSOperation)-[:HAS_WHERE]->(:CQRSWhere)-[:TARGET]->(:Property)` and `(:CQRSWhere)-[:SOURCE_EVENT_FIELD]->(:Property)` are created with the chosen `operator`.
2. **Given** multiple where conditions, **When** the editor reloads, **Then** they are returned grouped under their owning operation in the response.

### User Story 3 - Static-value mappings (Priority: P3)

For audit/discriminator columns, a mapping may use a constant rather than an event field. The editor lets the user choose `source_type='value'` and supply a `static_value` string.

**Why this priority**: Common but not on the critical path — most fields come from event payloads.

**Acceptance Scenarios**:

1. **Given** an operation, **When** the user creates a mapping with `source_type='value'` and `static_value='ACTIVE'`, **Then** the persisted `CQRSMapping` has no `[:SOURCE]` edge but exposes `staticValue='ACTIVE'`.

### User Story 4 - Surface CQRS references before deleting a Property (Priority: P2)

Before deleting a `Property`, the system must warn the user about any `CQRSMapping` or `CQRSWhere` that references it (as target, source, or source-event-field), across *all* ReadModels — otherwise projections silently break.

**Why this priority**: Data-integrity safeguard. Required before any model edit that removes a Property.

**Independent Test**: Create a CQRS mapping that targets `Property X`, then call `GET /api/cqrs/property/{X}/references` and verify the mapping is returned with `role='targetPropertyId'`.

**Acceptance Scenarios**:

1. **Given** a Property is referenced by a Mapping target, a Mapping source, a Where target, and a Where source-event-field, **When** the references endpoint is called, **Then** four entries are returned, each with `refType` (`mapping`/`where`) and `role` populated, sorted stably by ReadModel → Operation → Kind → Role.

### Edge Cases

- Calling `GET /api/readmodel/{id}/cqrs` for a ReadModel with no `CQRSConfig` returns `{id: null, operations: []}` instead of 404 (the ReadModel must exist; a missing ReadModel returns 404).
- `POST /api/readmodel/{id}/cqrs/operations` is idempotent on `(readmodel, operation_type, trigger_event)` because the operation id is deterministic: `CQRS-OP-{readmodel}-{type}-{event}`.
- Deleting a `CQRSConfig` cascades to all operations, mappings, and where conditions via `DETACH DELETE`.
- Deleting an operation cascades to its mappings and where conditions but not to the trigger Event.
- Mappings without a `[:TARGET]` are filtered from responses (server side post-processing).

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose a CQRS configuration tree per ReadModel via `GET /api/readmodel/{readmodel_id}/cqrs`, returning `{id, readmodelId, operations: [{id, operationType, triggerEventId, triggerEventName, mappings, whereConditions}]}`.
- **FR-002**: System MUST create a `CQRSConfig` (id `CQRS-{readmodel_id}`) on demand via `POST /api/readmodel/{id}/cqrs`, idempotently linking `(:ReadModel)-[:HAS_CQRS]->(:CQRSConfig)`.
- **FR-003**: System MUST allow creating a CQRS operation via `POST /api/readmodel/{id}/cqrs/operations` with `operation_type ∈ {INSERT, UPDATE, DELETE}` and `trigger_event_id`, deterministically deriving the operation id from those inputs.
- **FR-004**: System MUST list trigger-eligible Events (with their `Property` definitions) for the editor via `GET /api/readmodel/{id}/cqrs/events`, traversing `(BoundedContext)-[:HAS_AGGREGATE]->(Aggregate)-[:HAS_COMMAND]->(Command)-[:EMITS]->(Event)-[:HAS_PROPERTY]->(Property)`.
- **FR-005**: System MUST list ReadModel-side properties for mapping targets via `GET /api/readmodel/{id}/properties`.
- **FR-006**: System MUST allow creating a field-to-field mapping via `POST /api/cqrs/operation/{operation_id}/mappings` with `source_type='event'`, persisting `(:CQRSMapping)-[:SOURCE]->(:Property)` and `[:TARGET]->(:Property)`.
- **FR-007**: System MUST allow creating a static-value mapping via the same endpoint with `source_type='value'` and `static_value`, persisting `staticValue` on the `CQRSMapping` and omitting the `[:SOURCE]` edge.
- **FR-008**: System MUST allow creating a WHERE condition via `POST /api/cqrs/operation/{operation_id}/where` with `target_property_id`, `source_event_field_id`, and `operator` (default `=`), persisting `(:CQRSWhere)-[:TARGET]->(:Property)` and `[:SOURCE_EVENT_FIELD]->(:Property)`.
- **FR-009**: System MUST support deletion of CQRS sub-elements: `DELETE /api/readmodel/{id}/cqrs` (cascade), `DELETE /api/cqrs/operation/{id}` (cascade to mappings/where), `DELETE /api/cqrs/mapping/{id}`, `DELETE /api/cqrs/where/{id}`.
- **FR-010**: System MUST resolve all CQRS references for a given Property via `GET /api/cqrs/property/{property_id}/references`, returning entries with `refType ∈ {mapping, where}` and `role ∈ {targetPropertyId, sourcePropertyId, sourceEventFieldId}`, including the owning ReadModel and Operation context.
- **FR-011**: References MUST be returned in a stable order: ReadModel name → ReadModel id → Operation type → Operation id → ref type → role → ref id.
- **FR-012**: All CQRS API actions MUST emit structured `SmartLogger` events under `api.cqrs.*` and `api.readmodel.cqrs.*` categories with `http_context` for traceability.
- **FR-013**: The editor UI MUST show the four provisioning options (`CQRS`, `API` (UI Mashup), `GraphQL`, `SharedDB`) but persist CQRS-specific structure only when CQRS is active; non-CQRS provisioning hides operation/mapping panels.
- **FR-014**: The editor UI MUST load events, properties, and config concurrently and gracefully error if any of the three responses are not OK.

### Key Entities

- **ReadModel** (Neo4j label `ReadModel`): the projection target; has `[:HAS_CQRS]` to its config, `[:HAS_PROPERTY]` to its properties.
- **CQRSConfig** (Neo4j label `CQRSConfig`): per-ReadModel container; id `CQRS-{readmodel_id}`; carries `readmodelId`.
- **CQRSOperation** (Neo4j label `CQRSOperation`): one per (config, type, trigger event); carries `operationType`, `cqrsConfigId`, `triggerEventId`; relates `[:TRIGGERED_BY]->(Event)` and aggregates `[:HAS_MAPPING]` / `[:HAS_WHERE]`.
- **CQRSMapping** (Neo4j label `CQRSMapping`): single field assignment; carries `sourceType` (`event`|`value`) and optional `staticValue`; relates `[:SOURCE]->(Property)` (event-mode only) and `[:TARGET]->(Property)`.
- **CQRSWhere** (Neo4j label `CQRSWhere`): row-selection predicate; carries `operator`; relates `[:TARGET]->(Property)` (ReadModel side) and `[:SOURCE_EVENT_FIELD]->(Property)` (event side).
- **Event** (Neo4j label `Event`) / **Property** (Neo4j label `Property`): referenced from operations and mappings/where; sourced from the canvas event-storming model.

## Success Criteria

### Measurable Outcomes

- **SC-001**: An architect can fully configure a CQRS projection (operation + ≥1 mapping + ≥1 where) for a ReadModel in under 2 minutes through the editor UI without leaving the canvas.
- **SC-002**: 100% of created operations, mappings, and where conditions round-trip identically through `GET /api/readmodel/{id}/cqrs` (idempotent reload).
- **SC-003**: Property-deletion safety: when `GET /api/cqrs/property/{id}/references` reports ≥1 reference, the UI MUST present a warning before the user proceeds.
- **SC-004**: Cascade deletion of a `CQRSConfig` removes 100% of its descendant `CQRSOperation`/`CQRSMapping`/`CQRSWhere` nodes (no orphans).
- **SC-005**: The `GET .../cqrs/events` query returns every Event reachable via `(BC)-[:HAS_AGGREGATE]->(Agg)-[:HAS_COMMAND]->(Cmd)-[:EMITS]->(Event)`, ordered by BC name then Event name.

## Assumptions

- Operation id derivation `CQRS-OP-{readmodel}-{type}-{event}` is intentionally deterministic so that re-creation is idempotent; this implies you cannot have two operations of the same type triggered by the same event on the same ReadModel.
- The provisioning type (CQRS / UI Mashup / GraphQL / SharedDB) is selected in the editor but persisted by the Inspector's generic node-update flow, not by CQRS endpoints.
- `Event` and `Property` nodes already exist in the graph (created by upstream model-editing features); CQRS endpoints reference but never create them.
- All CQRS endpoints assume single-tenant Neo4j access through `api.platform.neo4j.get_session()`; no per-user isolation is enforced at this layer.
