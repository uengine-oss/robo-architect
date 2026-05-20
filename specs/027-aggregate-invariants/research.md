# Research: Aggregate Invariants

**Feature**: 027-aggregate-invariants | **Date**: 2026-05-18

All three open questions from the spec were resolved during `/speckit-specify` via interactive
clarification. This document records the technical decisions that follow from them and from the
existing codebase conventions.

## R1 — `Invariant` node as a first-class label

**Decision**: Introduce a new Neo4j node label `Invariant`, attached to its owning `Aggregate`
via a new `HAS_INVARIANT` relationship. Properties: `id`, `key`, `name`, `declaration`,
`description` (optional), `source` (`manual` / `ingested` / `migrated`), `seq` (ordering),
`createdAt`, `updatedAt`.

**Rationale**: Constitution Principle I (Graph-as-Source-of-Truth) requires every modeling
object to live in Neo4j. The `Aggregate.invariants` string list is unstructured and carries no
traceability — a dedicated label lets Invariants own relationships (to GWT, to Commands) and be
queried by impact analysis. `seq` mirrors the ordering pattern used by other child objects.

**Alternatives considered**: Keep `invariants` as a richer JSON blob on the Aggregate — rejected:
JSON blobs cannot participate in graph traversal, breaking impact propagation (the explicit
"second source of truth" failure mode the constitution warns against).

## R2 — Idempotent natural key

**Decision**: `key = "<aggregate.key>.invariant.<slug>"`, where `<slug>` is a kebab-case slug of
the declaration (or name). The `(parentType, parentId)`-style uniqueness is enforced by a unique
constraint on `Invariant.key`.

**Rationale**: Matches the spec 026 `Feature` key convention (`<bc.key>.feature.<slug>`).
Satisfies FR-022 — re-ingesting the same requirement `MERGE`s on `key` instead of creating a
duplicate.

**Alternatives considered**: Random-UUID-only identity — rejected: gives ingestion no idempotent
merge target, so re-ingestion would duplicate Invariants.

## R3 — Detailed GWT conditions: reuse the existing `Given`/`When`/`Then` model

**Decision**: An Invariant's detailed conditions are expressed in exactly two ways, both reusing
the existing `Given`/`When`/`Then` nodes (no new condition label):

1. **Referenced (shared)** — `Invariant -[:VERIFIED_BY]-> Command`. The detailed conditions for
   that link *are* the Command's existing GWT triple `(parentType="Command", parentId=cmd.id)`.
   Editing them — from either the Invariant editor or the Command inspector — calls the same
   `POST /api/graph/gwt/upsert` against the Command, so there is physically one copy and edits
   propagate with no synchronization logic.
2. **Invariant-owned (standalone)** — a GWT triple stored with `parentType="Invariant"`,
   `parentId=<invariant.id>`, linked `Invariant -[:HAS_GIVEN|HAS_WHEN|HAS_THEN]-> …`.

**Rationale**: The existing GWT model already enforces one `Given`/`When`/`Then` triple per
`(parentType, parentId)` with multiple scenarios stored as `fieldValues` test cases. "Sharing by
explicit reference" (spec assumption) maps cleanly onto a `VERIFIED_BY` edge — there is never a
duplicated condition to keep in sync, which is exactly why "silently propagate" (clarification 3)
needs *zero* extra code: the edit hits one node. Extending `parentType` to also accept
`"Invariant"` is schema-compatible (the constraint is NOT-NULL + composite-unique, not an enum).

**Alternatives considered**:
- A new `Condition` label copied between Command and Invariant — rejected: creates duplicates
  that must be diffed/merged on every edit; reintroduces the second-source-of-truth problem.
- Pointing `VERIFIED_BY` at the `Given`/`When`/`Then` nodes directly — rejected: the triple is
  always reachable through the Command and per-node links triple the edge count for no gain.

## R4 — One GWT editor component for Commands and Invariants

**Decision**: Extract the GWT editing form currently embedded in
`frontend/src/features/canvas/ui/InspectorPanel.vue` (the `gwtSets` form + `/api/graph/gwt/upsert`
save path) into a standalone `GwtEditor.vue` component. The Command inspector and the new
Invariant editor both mount it.

**Rationale**: FR-008 / SC-005 require the Invariant detailed-condition editor to be the *same*
window as the Command GWT editor. A shared component is the only way to guarantee they cannot
drift. The component takes `parentType` + `parentId` as props, so it is parent-agnostic.

**Alternatives considered**: Duplicate the form in the Invariant editor — rejected: guarantees
drift, violates SC-005.

## R5 — Lazy migration of legacy `Aggregate.invariants`

**Decision**: Migration runs lazily on the first `GET …/invariants` for an Aggregate. If the
Aggregate has no `Invariant` nodes and `invariantsMigratedAt` is unset: for each non-empty,
de-duplicated string in `agg.invariants`, `MERGE` an `Invariant` with `declaration=<string>`,
`source="migrated"`; then set `agg.invariantsMigratedAt` and clear `agg.invariants = []`.

**Rationale**: Spec FR-018 mandates migration "when Invariants are first accessed". The
`invariantsMigratedAt` stamp makes it idempotent and prevents deleted Invariants from being
resurrected on the next read. Clearing the legacy list enforces FR-019 (single source of truth).

**Alternatives considered**: Eager migration via a one-off Cypher script — rejected: would have
to run against every existing deployment's database out-of-band; lazy migration is self-healing.

## R6 — Ingestion phase placement

**Decision**: Add an `extract_invariants_phase` to the ingestion workflow, running **after**
`generate_gwt_phase` (so Command GWT exists and can be referenced) and after
`extract_aggregates_phase`. It emits a new SSE progress event `EXTRACTING_INVARIANTS`. The LLM
call uses `ctx.llm.with_structured_output(...)`; results are persisted via the new
`InvariantOps` Neo4j helper and `MERGE`d on the natural key (R2).

**Rationale**: Mirrors the `feature_grouping_phase` (spec 026) pattern — a late phase that
enriches already-extracted aggregates. Placing it after GWT generation lets the LLM optionally
link an extracted invariant to an existing Command via `VERIFIED_BY`. Constitution III requires
the streamed phase event; Principle VI is satisfied by going through `ctx.llm`.

**Alternatives considered**: Run before GWT — rejected: there would be no Command GWT to
reference, forcing every ingested invariant to be standalone.

## R7 — Constitution Principle IV (Human-in-the-Loop) applicability

**Decision**: Invariant CRUD endpoints apply graph mutations directly (no propose→confirm),
because they are direct user actions, not LLM-generated changes. Ingestion-extracted Invariants
are persisted by the ingestion pipeline (whose entire output is a user-reviewable draft model)
and are then editable/deletable like any Invariant (FR-021).

**Rationale**: Principle IV governs *LLM-generated* changes to an *existing* graph (change plans,
chat edits). Direct user CRUD and the initial ingestion build are explicitly outside that scope —
consistent with how Command/Aggregate CRUD already behaves. No violation.

## R8 — No canvas representation

**Decision**: Invariants are surfaced only in the navigator design tree and the inspector; no
Vue Flow node type is added. The tree adds an "Invariants" group under each Aggregate, drilling
down to individual `Invariant` nodes.

**Rationale**: Spec FR-004 explicitly forbids a canvas sticker. The navigator already renders
non-canvas child groups (e.g. ReadModel → operations/properties), so this is an established
pattern.
