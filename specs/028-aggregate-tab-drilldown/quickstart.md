# Quickstart — Manual Smoke Test: Aggregate Tab Drill-Down & Canvas UX

Frontend-only feature. No backend or DB changes — a running backend with an existing model (at least one Bounded Context with ≥ 2 aggregates) is enough.

## Setup

1. Backend running: `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`
2. Frontend running: `npm run dev` in `frontend/` (Vite).
3. Open the app; ensure the graph has a Bounded Context with at least 2 aggregates.

## Scenario S1 — Drill into an aggregate from the Design tab (US1)

1. Open the **Design** tab. Select an aggregate node so its property panel opens.
2. Confirm a **"View Detail"** action is visible in the aggregate property panel.
3. Click it.
4. **Expect**: the app switches to the **Aggregate** tab, the selected aggregate's detailed view is loaded, and it is centered/focused in the viewport.

## Scenario S2 — "View Detail" only for aggregates (FR-006)

1. In the **Design** tab, select a non-aggregate node (e.g. a Command or Event).
2. **Expect**: the "View Detail" action is **not** shown (or is inert) — it appears only for Aggregate nodes.

## Scenario S3 — Selection carries over on manual tab switch (US2)

1. In the **Design** tab, select exactly one aggregate.
2. Switch to the **Aggregate** tab using the **tab bar** (not the View Detail button).
3. **Expect**: that aggregate is loaded and focused automatically — no drag, no extra click.

## Scenario S4 — Ambiguous / empty selection does not force a change (FR-008)

1. In the **Design** tab, select nothing (or select two nodes, or a non-aggregate node).
2. Switch to the **Aggregate** tab via the tab bar.
3. **Expect**: the Aggregate tab opens in its normal state (previously loaded content, or the empty state) — no forced load or canvas change.

## Scenario S5 — Drop an aggregate onto the Aggregate canvas (US3)

1. Open the **Aggregate** tab.
2. From the navigator tree, drag an **aggregate** item onto the canvas and drop it.
3. **Expect**: that aggregate's detailed view appears and is focused.
4. Drag a **second** aggregate onto the canvas.
5. **Expect**: the second aggregate is added **alongside** the first — the first is not removed.
6. Drag the **first** aggregate onto the canvas again.
7. **Expect**: no duplicate appears; the existing one is focused (FR-005, FR-010).

## Scenario S6 — Bounded Context drop still works (FR-011, no regression)

1. On the **Aggregate** tab, drag a **Bounded Context** from the navigator onto the canvas.
2. **Expect**: all of that BC's aggregates appear — unchanged from previous behavior.

## Scenario S7 — Aggregate boundary is visually identifiable (US4)

1. With any aggregate shown on the Aggregate canvas, inspect its grouping box.
2. **Expect**: the box has a **subtle yellow tint** background/border (not the old neutral/dark fill), and inner cards (root, value objects, enumerations) remain clearly readable.
3. **Expect**: the box label region shows an **`«Aggregate»`** stereotype indicator alongside the name.
4. Toggle the app between **light** and **dark** theme.
5. **Expect**: the yellow tint and the `«Aggregate»` label stay legible and consistent in both themes.

## Scenario S8 — Missing aggregate shows a clear state (FR-015)

1. Trigger a drill-down or drop for an aggregate that no longer exists in the model (e.g. delete it in another session first, or simulate a failed fetch).
2. **Expect**: the Aggregate tab shows a clear error / not-found state with a retry affordance — **not** a blank canvas or an unhandled error.

## Pass criteria

All eight scenarios behave as described. In particular: S1/S3 reach a focused detail with one action, S4 never forces a change, S5–S6 are additive with zero duplicates and no BC-drop regression, S7 makes the aggregate boundary obvious in both themes.
