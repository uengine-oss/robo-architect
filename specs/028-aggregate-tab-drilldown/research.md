# Phase 0 Research: Aggregate Tab Drill-Down & Canvas UX

All unknowns from Technical Context are resolved below. No `NEEDS CLARIFICATION` markers remain.

## R1 — Cross-tab "current aggregate" intent: where to hold it

**Decision**: Add a small `pendingFocus` object (`{ aggregateId, bcId }`) and a `focusAggregate(aggregateId, bcId)` action to the existing `aggregateViewer` Pinia store (`frontend/src/features/canvas/aggregateViewer.store.js`). Tab switching itself reuses the existing `provide('activeTab')` ref in `App.vue`.

**Rationale**:
- `App.vue:25` already does `provide('activeTab', activeTab)`; `TreeNode.vue` and `NavigatorPanel.vue` already `inject('activeTab', ...)`. `InspectorPanel.vue` can inject the same ref to switch tabs — no new plumbing.
- `App.vue:175` keys the tab component by `:key="activeTab"`, so the Aggregate tab component **remounts** every time it becomes active. A piece of intent state must therefore live in a store that *survives* the remount, not in component state. The `aggregateViewer` store is the natural owner — it already holds the Aggregate tab's canvas data.
- `pendingFocus` is consumed once (on mount) and cleared, so it does not become a competing source of truth (Principle I).

**Alternatives considered**:
- *New dedicated Pinia store for cross-tab selection* — rejected: over-engineering for one `{aggregateId, bcId}` value; the `aggregateViewer` store is already the consumer.
- *Reuse `modelModifier.store.js` `selectedNodes`* — rejected: that store mediates chat selection semantics; overloading it couples unrelated features (Principle V).
- *Route/query param* — rejected: the app is tab-state-driven, not router-driven; introducing routing for one feature is disproportionate.

## R2 — Single-aggregate display vs. whole-Bounded-Context display

**Decision**: Add an aggregate-level visibility set `visibleAggregateIds: Set<string>` to the `aggregateViewer` store. `filteredBoundedContexts` (consumed by `AggregatePanel.buildNodes`) is changed to also filter each BC's `aggregates` down to those in `visibleAggregateIds`. Behavior of the two entry points:
- **Bounded-Context drop** (`fetchAggregatesForBC`) — after loading, add **all** of that BC's aggregate ids to `visibleAggregateIds` (preserves today's "show every aggregate" behavior).
- **Aggregate drop / drill-down** (new `fetchAggregate(aggregateId, bcId)`) — load the BC tree (needed to obtain the aggregate's contents), then add **only** that aggregate's id to `visibleAggregateIds`.
- `clearAllBCs()` also clears `visibleAggregateIds`.

**Rationale**:
- Today the store filters only at BC granularity (`selectedBcIds` + `filteredBoundedContexts`); there is no way to show one aggregate. A flat `Set` of visible aggregate ids is the minimal addition that supports both "all of a BC" and "just one aggregate" uniformly.
- A `Set` gives free de-duplication — satisfies FR-005 / FR-010 (no duplicate detail view) with no extra logic.
- Aggregate contents are only reachable through `GET /api/contexts/{bcId}/full-tree` (the per-aggregate fields — `properties`, `valueObjects`, `enumerations`, `rootEntity` — come from that BC tree). So fetching still happens at BC granularity; only **display** is gated per-aggregate.

**Alternatives considered**:
- *Per-BC "full vs partial" mode flag* — rejected: more states, mixed-mode bookkeeping; the flat visible-id set subsumes it.
- *New backend endpoint returning a single aggregate* — rejected: violates "no backend changes" constraint and duplicates `full-tree` query logic; the existing endpoint already returns everything needed.

## R3 — Resolving the owning Bounded Context id for an aggregate

**Decision**: The bcId is resolved at the call site, with a fallback:
1. **Drill-down from Design-tab inspector**: the selected aggregate is a Design-canvas Vue Flow node whose `parentNode` is the BC node id (Design canvas nests aggregates under BCs — confirmed in `canvas.store.js`, e.g. `node.parentNode === bcId`). Use `node.parentNode`; if absent, use `node.data.bcId`.
2. **Aggregate drop from navigator**: the drag payload (`TreeNode.vue` dragstart) is `{ nodeId, nodeType, nodeData, ... }`. Prefer a bcId/parentId carried on `nodeData`.
3. **Fallback for both**: if no bcId is available, call `GET /api/graph/expand-with-bc/{aggregateId}` — its response `nodes[]` includes the parent `BoundedContext` node and sets `bcId` on the Aggregate node.

**Rationale**:
- Two of the three call sites already have the bcId locally (Design-canvas `parentNode`, and the navigator tree nests aggregates under BC), so the common path needs no extra request.
- `expand-with-bc` already exists and already returns exactly the parent-BC mapping; using it as a fallback avoids a new endpoint and avoids coupling to navigator-tree internal shape.

**Alternatives considered**:
- *Always call `expand-with-bc`* — rejected: an avoidable round-trip when bcId is already in hand.
- *New `/api/contexts/aggregates/{id}/context` endpoint* — rejected: unnecessary; `expand-with-bc` covers it and "no backend changes" is a stated constraint.

## R4 — Unifying drill-down (US1) and tab-switch carry-over (US2)

**Decision**: One mechanism serves both. On the Aggregate tab component's mount:
1. If `aggregateViewer.pendingFocus` is set (US1 — the inspector's "View Detail" button set it explicitly), consume it.
2. Else, inspect the Design canvas selection (`canvasStore.selectedNodes`, a computed of selected Vue Flow nodes). If **exactly one** is an aggregate (`node.data?.type === 'Aggregate'`), derive `{aggregateId, bcId}` from it and treat it as the focus target (US2). If zero, multiple, or non-aggregate → do nothing (FR-008).
3. With a focus target: ensure the aggregate is loaded (`fetchAggregate` if its id is not already in `visibleAggregateIds`), then `fitView({ nodes: ['agg-container-<aggregateId>'], padding: 0.3 })` to center it. Clear `pendingFocus`.

**Rationale**:
- The spec models US1 and US2 as separate stories, but the *effect* — "the target aggregate is loaded and focused on the Aggregate tab" — is identical. Implementing them as one consume-on-mount routine avoids divergent code paths and guarantees consistent focus/no-duplicate behavior (FR-005).
- `App.vue` remounts the tab component on switch, so `onMounted` is the correct, reliable hook for both the explicit (button) and implicit (manual tab switch) paths.
- The "exactly one aggregate" guard directly encodes FR-007/FR-008 (single unambiguous selection only).

**Alternatives considered**:
- *Separate `onActivated` keep-alive path* — rejected: the tab container is not `<keep-alive>`-wrapped (`:key="activeTab"` forces remount); `onMounted` is the real lifecycle hook.
- *Watcher on `activeTab` inside a persistent component* — rejected: no persistent parent owns both tabs cleanly; mount-time consumption is simpler and matches existing architecture.

## R5 — Focusing a specific node on the Vue Flow canvas

**Decision**: Use Vue Flow's `fitView({ nodes: ['agg-container-<aggregateId>'], padding: 0.3 })`. The aggregate's grouping box node id is `agg-container-${agg.id}` (see `AggregatePanel.buildNodes`).

**Rationale**:
- `useVueFlow().fitView` already accepts a `nodes` filter; `AggregatePanel` already imports and uses `fitView`. No new dependency.
- The grouping box (`aggregateContainer` node) is the outermost node for an aggregate, so fitting to it brings the whole aggregate (root, properties, VOs, enums) into view.
- Must run after the canvas has built nodes for the newly loaded aggregate — sequence the `fitView` after the existing node-build/`nodes-initialized` settle, mirroring the existing post-drop `setTimeout(fitView, …)` pattern in `handleDrop`.

**Alternatives considered**:
- *`setCenter` on raw coordinates* — rejected: positions are computed asynchronously by `buildNodes`; `fitView({nodes})` lets Vue Flow resolve geometry itself.

## R6 — Aggregate grouping box styling (yellow tint + «Aggregate» stereotype)

**Decision**: In `AggregateContainerNode.vue`:
- Replace the neutral fill (`background: var(--color-bc-bg)`, dark `#373a40` header) with a subtle aggregate-yellow tint. Use a low-opacity tint of the existing aggregate accent color (`--color-aggregate`, `#fcc419`) — e.g. body `rgba(252,196,25,0.07)`, header a slightly stronger tint, border `rgba(252,196,25,~0.45)`. Provide explicit values for both `:root.theme-light` and `:root.theme-dark` so contrast holds in each theme.
- Add an `«Aggregate»` stereotype line in the header (`container-header`), small/uppercase, above or beside the existing name. Keep the existing name text.
- Optionally align the minimap color (`getNodeColor` → `aggregateContainer`) toward the yellow family for consistency.

**Rationale**:
- `--color-aggregate` is already the product's aggregate accent (used in `AggregatePanel` spinner/retry styles) — reusing it keeps the color language consistent (Principle II).
- A *low-opacity* tint (not a saturated fill) keeps the contained nodes (root/VO/enum cards) readable, per the spec assumption.
- Guillemet stereotype (`«Aggregate»`) is the standard modeling-notation convention and is unambiguous to DDD users.

**Alternatives considered**:
- *Saturated yellow fill* — rejected: would reduce contrast of inner cards; spec explicitly says "subtle"/"약간".
- *Single CSS value without per-theme overrides* — rejected: the file already theme-branches the header (`:root.theme-dark .container-header`); a one-value approach would look wrong in light theme.

## R7 — Error / not-found handling (FR-015)

**Decision**: Reuse the `aggregateViewer` store's existing `error` ref and `AggregatePanel`'s existing error state block. If `fetchAggregate` fails or the aggregate is absent from the fetched BC tree, set `error` to a clear message; the Aggregate tab already renders an error state with a Retry affordance. A drill/drop that targets a missing aggregate surfaces this state instead of a blank canvas.

**Rationale**: The error UI already exists in `AggregatePanel.vue` (`store.error` block with retry). No new component needed — only ensure the new code paths set `error` rather than failing silently.

**Alternatives considered**:
- *Toast / transient notification* — rejected: inconsistent with the tab's existing inline error pattern.

## Summary of decisions

| # | Topic | Decision |
|---|-------|----------|
| R1 | Cross-tab intent state | `pendingFocus` + `focusAggregate()` on `aggregateViewer` store; tabs via existing `activeTab` inject |
| R2 | Single-aggregate display | `visibleAggregateIds` set; `filteredBoundedContexts` filters aggregates by it |
| R3 | bcId resolution | Local (`parentNode` / drag payload), fallback `GET /api/graph/expand-with-bc/{id}` |
| R4 | US1+US2 unification | Single consume-on-mount routine; "exactly one aggregate selected" guard |
| R5 | Node focus | `fitView({ nodes: ['agg-container-<id>'] })` |
| R6 | Styling | Low-opacity `--color-aggregate` tint + `«Aggregate»` stereotype, per-theme values |
| R7 | Errors | Reuse store `error` ref + existing AggregatePanel error/retry block |
