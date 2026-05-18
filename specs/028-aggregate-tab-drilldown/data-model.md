# Phase 1 Data Model: Aggregate Tab Drill-Down & Canvas UX

This feature introduces **no Neo4j nodes, relationships, or schema changes**. The data model below describes the **client-side UI state** added to the `aggregateViewer` Pinia store, and the shape of data already exchanged with existing endpoints.

## 1. New / changed UI state — `aggregateViewer` store

File: `frontend/src/features/canvas/aggregateViewer.store.js`

### 1.1 New state

| State | Type | Purpose |
|-------|------|---------|
| `visibleAggregateIds` | `Set<string>` | Ids of aggregates currently shown on the Aggregate-tab canvas. Gates display independently of which BCs are loaded. |
| `pendingFocus` | `{ aggregateId: string, bcId: string } \| null` | One-shot focus intent set by the Design-tab "View Detail" button (US1). Consumed and cleared on Aggregate-tab mount. |

### 1.2 Existing state (unchanged, referenced for context)

| State | Type | Note |
|-------|------|------|
| `boundedContexts` | `BC[]` | Loaded BC trees (each with `aggregates[]`). |
| `selectedBcIds` | `Set<string>` | BCs whose data is loaded. |
| `loading` / `error` | `boolean` / `string\|null` | Reused for the new fetch path (R7). |

### 1.3 New / changed actions

| Action | Signature | Behavior |
|--------|-----------|----------|
| `fetchAggregate` *(new)* | `(aggregateId, bcId) → Promise<void>` | Loads the owning BC tree via `GET /api/contexts/{bcId}/full-tree` (skips the request if the BC is already loaded), then adds **only** `aggregateId` to `visibleAggregateIds`. Sets `error` if the aggregate is not found in the tree (FR-015). |
| `focusAggregate` *(new)* | `(aggregateId, bcId) → void` | Sets `pendingFocus = { aggregateId, bcId }`. Called by the inspector "View Detail" button before switching tabs. |
| `consumeFocus` *(new)* | `() → { aggregateId, bcId } \| null` | Returns and clears `pendingFocus`. Called once on Aggregate-tab mount. |
| `fetchAggregatesForBC` *(changed)* | `(bcId) → Promise<void>` | Existing behavior **plus**: after load, add **all** of that BC's aggregate ids to `visibleAggregateIds` (preserves current "show whole BC" behavior). |
| `clearAllBCs` *(changed)* | `() → void` | Existing behavior **plus**: clear `visibleAggregateIds` and `pendingFocus`. |

### 1.4 Changed computed

| Computed | Change |
|----------|--------|
| `filteredBoundedContexts` | Still returns BCs in `selectedBcIds`, but each returned BC's `aggregates` array is filtered to entries whose `id ∈ visibleAggregateIds`. BCs left with zero visible aggregates are omitted. |

### State-transition notes

- **De-duplication**: `visibleAggregateIds` is a `Set` — re-dropping or re-drilling an already-visible aggregate is a no-op for display (FR-005, FR-010).
- **Additive**: neither `fetchAggregate` nor `fetchAggregatesForBC` removes ids from `visibleAggregateIds`; new aggregates appear alongside existing ones (FR-010).
- **`pendingFocus` lifecycle**: `null` → set by `focusAggregate` → read+nulled by `consumeFocus`. Never persisted.

## 2. Cross-tab focus target (transient, not stored)

A logical value passed between tabs, materialized either as `pendingFocus` (US1) or derived from the Design canvas selection (US2):

| Field | Type | Source |
|-------|------|--------|
| `aggregateId` | `string` | Selected aggregate node id (Design canvas node `id` / `data.id`, or navigator drag `nodeId`). |
| `bcId` | `string` | Owning Bounded Context — resolved per research R3 (Design-canvas `parentNode`, drag payload, or `expand-with-bc` fallback). |

## 3. Reused API payloads (no change)

### 3.1 `GET /api/contexts/{bcId}/full-tree`

Returns the BC with nested aggregates. Fields consumed by this feature (already used by `AggregatePanel.buildNodes`):

```
BC {
  id, name, displayName, description,
  aggregates: [
    Aggregate {
      id, name, displayName, rootEntity,
      properties[], valueObjects[], enumerations[], invariants[]
    }
  ]
}
```

### 3.2 `GET /api/graph/expand-with-bc/{aggregateId}` — fallback only

Used solely to resolve a missing `bcId`. Response `nodes[]` contains the parent `BoundedContext` node and an `Aggregate` node carrying `bcId`. No fields beyond `bcId` are consumed.

## 4. Canvas node identity (existing convention, referenced)

| Node | Vue Flow id |
|------|-------------|
| Aggregate grouping box (focus target for `fitView`) | `agg-container-${aggregateId}` |
| Aggregate root card | `agg-${aggregateId}` |

The `agg-container-*` id is the `fitView` target (research R5).

## 5. Validation rules

- `focusAggregate` / `fetchAggregate` require a non-empty `aggregateId`; `bcId` may be empty only if the caller relies on the `expand-with-bc` fallback to resolve it before `fetchAggregate` runs.
- Tab-switch auto-load (US2) triggers **only** when the Design canvas selection contains **exactly one** node with `data.type === 'Aggregate'` — zero, multiple, or non-aggregate selections are ignored (FR-008).
- A focus target whose `aggregateId` is absent from the fetched BC tree results in `error` being set, not a silent blank canvas (FR-015).
