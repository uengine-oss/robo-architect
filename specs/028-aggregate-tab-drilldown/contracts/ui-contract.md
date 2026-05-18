# UI Contract: Aggregate Tab Drill-Down & Canvas UX

This feature exposes **no new HTTP endpoints**. Its "contracts" are (a) the cross-tab interaction contract between the Design tab and the Aggregate tab, and (b) the reuse terms of two existing endpoints. Documented here so `/speckit-tasks` and implementation stay aligned.

## A. Cross-tab focus contract

### A.1 Producer — Design tab "View Detail" action (`InspectorPanel.vue`)

**Precondition**: A single Aggregate node is selected and its property panel is open.

**Action**: User activates the "View Detail" button.

**Contract**:
1. Resolve `{ aggregateId, bcId }` for the selected aggregate (bcId per research R3).
2. Call `aggregateViewerStore.focusAggregate(aggregateId, bcId)`.
3. Set the injected `activeTab.value = 'Aggregate'`.

The button MUST be rendered/enabled only when the selected node is an Aggregate (FR-006).

### A.2 Consumer — Aggregate tab (`AggregatePanel.vue`) on mount

The Aggregate-tab component remounts on every tab switch (`App.vue` `:key="activeTab"`). On mount it MUST run exactly this resolution order:

```
target ← aggregateViewerStore.consumeFocus()          # US1: explicit button intent
if target is null:
    sel ← canvasStore.selectedNodes                   # US2: Design-tab selection carry-over
    aggs ← sel.filter(n => n.data?.type === 'Aggregate')
    if aggs.length == 1:
        target ← { aggregateId: aggs[0].id|data.id,
                   bcId: aggs[0].parentNode | aggs[0].data.bcId }
    else:
        target ← null                                 # FR-008: ambiguous/empty → no-op
if target is not null:
    if target.aggregateId ∉ visibleAggregateIds:
        await fetchAggregate(target.aggregateId, target.bcId)
    fitView({ nodes: ['agg-container-' + target.aggregateId], padding: 0.3 })
```

**Guarantees**:
- No duplicate detail view — `fetchAggregate` adds to a `Set` (FR-005).
- Empty / multi / non-aggregate selection never forces a canvas change (FR-008).
- A missing aggregate sets `store.error` → existing error/retry block renders (FR-015).

### A.3 Producer — navigator Aggregate drop (`AggregatePanel.vue` `handleDrop`)

Current `handleDrop` only handles `nodeType === 'BoundedContext'`. Extended contract:

| Dropped `nodeType` | Behavior |
|--------------------|----------|
| `BoundedContext` | **Unchanged** — `fetchAggregatesForBC(nodeId)`; all aggregates of the BC become visible (FR-011). |
| `Aggregate` | Resolve `bcId` (drag payload `nodeData`, else `expand-with-bc` fallback); `fetchAggregate(nodeId, bcId)`; `fitView` to `agg-container-<nodeId>`. Additive, de-duplicated (FR-009, FR-010). |
| other | Ignored (unchanged). |

Drag payload shape (from `TreeNode.vue`, unchanged): `{ id, type, nodeId, nodeType, nodeData }`.

## B. Reused endpoint terms (no change to either endpoint)

### B.1 `GET /api/contexts/{bcId}/full-tree`

- **Used by**: `fetchAggregate` (and existing `fetchAggregatesForBC`).
- **Contract relied upon**: response includes `aggregates[]`, each with `id, name, displayName, rootEntity, properties[], valueObjects[], enumerations[], invariants[]`.
- **Reuse rule**: if the BC is already in `boundedContexts`, `fetchAggregate` MUST NOT re-request it.

### B.2 `GET /api/graph/expand-with-bc/{aggregateId}` — fallback only

- **Used by**: bcId resolution when the caller has no `bcId` in hand.
- **Contract relied upon**: response `nodes[]` contains the parent `BoundedContext` node; the `Aggregate` node carries `bcId`.
- **Reuse rule**: called at most once per drop/drill, and only when `bcId` is otherwise unavailable.

## C. Visual contract — Aggregate grouping box (`AggregateContainerNode.vue`)

| Aspect | Contract |
|--------|----------|
| Background | Subtle aggregate-yellow tint (low-opacity `--color-aggregate`); inner cards remain legible (FR-012). |
| Border | Aggregate-yellow, visibly distinct from a neutral container (FR-012). |
| Label region | Displays an `«Aggregate»` stereotype indicator alongside the existing name (FR-013). |
| Theming | Defined for both `theme-light` and `theme-dark`; tint + stereotype legible in each (FR-014). |

## D. Out of scope (explicit non-contract)

- No new endpoints; `/docs` (Swagger) is unchanged.
- No Neo4j schema changes.
- No mutation of model state — drill / drop / focus are read + display only.
- No new application tab — the feature connects the existing Design and Aggregate tabs.
