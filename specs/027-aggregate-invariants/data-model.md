# Data Model: Aggregate Invariants

**Feature**: 027-aggregate-invariants | **Date**: 2026-05-18

## §1 Neo4j Graph Schema

### 1.1 New node label: `Invariant`

| Property | Type | Notes |
|----------|------|-------|
| `id` | String (UUID) | `randomUUID()` on create |
| `key` | String | Natural key `"<aggregate.key>.invariant.<slug>"` — unique, not null |
| `name` | String | Short title (defaults to a truncation of `declaration`) |
| `declaration` | String | The rule statement — the invariant in plain language; not null |
| `description` | String? | Optional elaboration |
| `source` | String | `manual` \| `ingested` \| `migrated` |
| `seq` | Integer | Ordering within the Aggregate |
| `createdAt` | DateTime | |
| `updatedAt` | DateTime | |

### 1.2 New relationships

| Relationship | From → To | Cardinality | Meaning |
|--------------|-----------|-------------|---------|
| `HAS_INVARIANT` | `Aggregate` → `Invariant` | 1 → many | Aggregate owns the Invariant |
| `VERIFIED_BY` | `Invariant` → `Command` | many → many | The Command's GWT acceptance criteria serve as a detailed (shared) condition that verifies the invariant |
| `HAS_GIVEN` / `HAS_WHEN` / `HAS_THEN` | `Invariant` → `Given`/`When`/`Then` | 1 → 0..1 each | The Invariant's own standalone GWT triple |

### 1.3 Extended: `Given` / `When` / `Then`

No structural change. The existing `parentType` property — today `"Command"` \| `"Policy"` —
additionally accepts `"Invariant"`. A standalone invariant triple is stored as
`(parentType="Invariant", parentId=<invariant.id>)`, preserving the existing
`(parentType, parentId)` composite-unique constraint. `When` for an invariant-owned triple
keeps the default `referencedNodeType="Aggregate"`.

### 1.4 Extended: `Aggregate`

| Property | Change |
|----------|--------|
| `invariants` | Legacy `list[String]`. After lazy migration it is cleared to `[]` and is no longer the source of truth (R5). |
| `invariantsMigratedAt` | **New.** DateTime stamp; presence marks migration done — guards against re-migration / resurrection of deleted Invariants. |

### 1.5 Schema file updates (`docs/cypher/schema/`)

- `01_constraints.cypher` — `Invariant`: unique+not-null `id`, unique+not-null `key`, not-null
  `declaration`. (No new constraint needed for `Given/When/Then` — `parentType` widening is
  value-only.)
- `02_indexes.cypher` — `Invariant`: RANGE index on `id`, TEXT index on `name` / `declaration`.
- `03_node_types.cypher` — add an `Invariant` example block; note `parentType` now accepts
  `"Invariant"` on the `Given/When/Then` blocks.
- `04_relationships.cypher` — add `HAS_INVARIANT` and `VERIFIED_BY`; note `HAS_GIVEN/WHEN/THEN`
  may now originate from an `Invariant`.

### 1.6 Lifecycle / deletion rules

- **Delete Invariant**: detach `HAS_INVARIANT` and all `VERIFIED_BY` edges; **delete** the
  invariant-owned `Given/When/Then` triple (parentType="Invariant"); **preserve** every Command
  GWT triple reached via `VERIFIED_BY` (FR-015).
- **Remove a reference**: deleting one `VERIFIED_BY` edge detaches that Command from the
  Invariant only; the Command's GWT is never touched (FR-014).
- **Delete Aggregate** (existing op, extended): cascade-delete its Invariants using the rules
  above.

## §2 Pydantic DTOs (`api/features/invariants/invariants_contracts.py`)

### 2.1 `InvariantSummaryDTO` — tree / list rows

```
id: str
key: str
name: str
declaration: str
source: Literal["manual", "ingested", "migrated"]
seq: int
isSpecified: bool        # True if >=1 VERIFIED_BY edge OR an own GWT triple exists
referencedCommandCount: int
type: Literal["Invariant"] = "Invariant"
```

### 2.2 `ReferencedConditionDTO` — one shared (command-backed) condition

```
commandId: str
commandName: str
hasGwt: bool             # whether that Command currently has a GWT triple
```

### 2.3 `InvariantDetailDTO` — property editor payload

```
id: str
key: str
name: str
declaration: str
description: str | None
source: Literal["manual", "ingested", "migrated"]
seq: int
aggregateId: str
aggregateName: str
referencedConditions: list[ReferencedConditionDTO]
ownGwtParentId: str | None     # = invariant id when an own triple exists, else None
isSpecified: bool
```

### 2.4 CRUD request bodies

```
CreateInvariantRequest:   name: str | None; declaration: str; description: str | None
UpdateInvariantRequest:   name: str | None; declaration: str | None; description: str | None
AddReferenceRequest:      commandId: str
```

### 2.5 `ReferenceCandidateDTO` — command pick-list for the editor

```
commandId: str
commandName: str
hasGwt: bool
alreadyReferenced: bool
```

### 2.6 GWT contract extension (`api/features/canvas_graph/routes/gwt.py`)

`UpsertGWTRequest.parentType`: `Literal["Command", "Policy"]` → `Literal["Command", "Policy",
"Invariant"]`. No other field changes — the invariant-owned triple reuses the existing
upsert/test-case shape verbatim.

### 2.7 Ingestion structured output (`…/event_storming/structured_outputs.py`)

```
ExtractedInvariant:        declaration: str; aggregateName: str; verifyingCommandNames: list[str]
ExtractedInvariantSet:     invariants: list[ExtractedInvariant]
```

## §3 Ingestion phase: `extract_invariants_phase`

- **File**: `api/features/ingestion/workflow/phases/extract_invariants.py`
- **Order**: after `generate_gwt_phase` (Command GWT must exist to be referenced).
- **Behavior**: per Aggregate, prompt `ctx.llm.with_structured_output(ExtractedInvariantSet)` on
  the requirements text; for each result, `MERGE` an `Invariant` on its natural key (R2) with
  `source="ingested"`, and `MERGE` a `VERIFIED_BY` edge for each resolvable
  `verifyingCommandName` within that Aggregate.
- **Streaming**: yields `ProgressEvent(phase="EXTRACTING_INVARIANTS", …)`; the SSE event name
  `EXTRACTING_INVARIANTS` is added to the ingestion event vocabulary.
- **Idempotency**: `MERGE` on `key` means re-ingestion updates rather than duplicates (FR-022).

## §4 State

An `Invariant` has one derived state, `isSpecified`:

- `declaration-only` — `isSpecified=false`: has a declaration but no `VERIFIED_BY` edge and no
  own GWT triple. Valid but flagged in the UI as incompletely specified.
- `specified` — `isSpecified=true`: has at least one detailed condition (referenced or owned).

State is computed at read time, never stored.
