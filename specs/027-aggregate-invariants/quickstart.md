# Quickstart: Aggregate Invariants — Manual Smoke Test

**Feature**: 027-aggregate-invariants | **Date**: 2026-05-18

Prerequisites: backend running (`uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`),
frontend running, Neo4j populated with at least one ingested model that has an Aggregate with
Commands. Schema files in `docs/cypher/schema/` applied.

## S1 — Invariants appear under the Aggregate in the design tree

1. Open the app, select a BoundedContext, switch to the **Design** tab.
2. Expand an Aggregate in the left navigator tree.
3. **Expect**: an **Invariants** group node appears among the Aggregate's children; it can be
   drilled into. Each Invariant shows as a child node with an `INV` icon.
4. Check the canvas — **expect**: no Invariant sticker is drawn anywhere on the canvas.

## S2 — Create, edit, and delete an Invariant

1. On the Invariants group, add a new Invariant; type a declaration ("주문 총액은 0보다 커야 한다").
2. **Expect**: it appears in the tree within ~30s of effort (SC-002) and persists after reload.
3. Double-click the Invariant — **expect**: a property editor opens showing the declaration.
4. Edit the declaration, save, reload — **expect**: the new text shows in the tree and editor.
5. Delete the Invariant — **expect**: it disappears from the tree.

## S3 — Legacy invariant text is migrated

1. Pick an Aggregate whose `invariants` string list was populated by an older ingestion.
2. Expand its Invariants group for the first time.
3. **Expect**: every legacy text entry now appears as an Invariant object, original wording
   intact (SC-004). Empty/duplicate strings produced no extra nodes.
4. In Neo4j, confirm `aggregate.invariantsMigratedAt` is set and `aggregate.invariants = []`.

## S4 — Reference a Command's acceptance criteria (shared condition)

1. Open an Invariant's editor; in the detailed-conditions area, add a condition by
   **referencing an existing Command** of the same Aggregate.
2. **Expect**: the pick-list shows only Commands of this Aggregate; already-referenced ones are
   marked.
3. The referenced condition shows the Command's GWT in the **same editor window** used on the
   Command inspector (SC-005).
4. Edit the GWT text from the Invariant editor, save.
5. Open that Command in the inspector — **expect**: the GWT shows the edited text.
6. Now edit the same GWT from the Command inspector, save; reopen the Invariant editor —
   **expect**: the change is reflected. No confirmation prompt appeared in either direction.

## S5 — Declare an invariant-only condition

1. In an Invariant's editor, add a condition as a **new declaration** (not a reference).
2. Fill in its Given/When/Then, save.
3. **Expect**: the condition is stored as invariant-owned (`parentType="Invariant"`); it does
   not appear on any Command.
4. Delete the Invariant — **expect**: the invariant-owned condition is removed, while any
   referenced Command GWT from S4 still exists on its Command.

## S6 — Ingestion extracts candidate Invariants

1. Run a requirements-document ingestion that describes aggregate-level rules.
2. Watch the SSE stream — **expect**: an `EXTRACTING_INVARIANTS` phase event with progress.
3. After completion, expand the relevant Aggregates — **expect**: candidate Invariants appear,
   editable and deletable like manual ones (S2).
4. Re-run the same ingestion — **expect**: zero duplicate Invariants on the same Aggregate
   (SC-007).

## S7 — `declaration-only` vs `specified` indication

1. Create an Invariant with only a declaration (no conditions).
2. **Expect**: the tree/editor flags it as incompletely specified (`isSpecified=false`).
3. Add a reference or an own condition — **expect**: the flag clears.
