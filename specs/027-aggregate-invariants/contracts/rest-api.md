# REST API Contract: Aggregate Invariants

**Feature**: 027-aggregate-invariants | **Date**: 2026-05-18

New router `api/features/invariants/router.py`, registered in `api/main.py`. All bodies are
Pydantic models (see data-model.md §2). Every endpoint appears in `/docs` (constitution
Development Workflow). Invariant CRUD are instant graph queries → plain request/response
(constitution III); the only streamed surface is the ingestion phase (§7).

## §1 List invariants of an Aggregate (triggers lazy migration)

```
GET /api/aggregates/{aggregate_id}/invariants
→ 200  { "aggregateId": str, "invariants": InvariantSummaryDTO[] }
→ 404  aggregate not found
```

First call for an Aggregate runs the lazy migration of legacy `Aggregate.invariants` text into
`Invariant` nodes (research R5) before responding. Idempotent via `invariantsMigratedAt`.

## §2 Invariant CRUD

```
POST   /api/aggregates/{aggregate_id}/invariants
  body  CreateInvariantRequest
  → 201 InvariantDetailDTO
  → 404 aggregate not found
  → 409 an Invariant with the same derived key already exists on the Aggregate

GET    /api/invariants/{invariant_id}
  → 200 InvariantDetailDTO
  → 404 not found

PATCH  /api/invariants/{invariant_id}
  body  UpdateInvariantRequest      (any subset of fields)
  → 200 InvariantDetailDTO
  → 404 not found

DELETE /api/invariants/{invariant_id}
  → 204  (deletes own GWT triple; preserves referenced Command GWT — data-model §1.6)
  → 404 not found
```

## §3 Detailed conditions — references (shared with Command acceptance criteria)

```
GET    /api/invariants/{invariant_id}/reference-candidates
  → 200 { "candidates": ReferenceCandidateDTO[] }   # Commands in the same Aggregate

POST   /api/invariants/{invariant_id}/references
  body  AddReferenceRequest { commandId }
  → 201 InvariantDetailDTO        # creates Invariant-[:VERIFIED_BY]->Command
  → 404 invariant or command not found
  → 409 command already referenced
  → 422 command does not belong to the invariant's Aggregate

DELETE /api/invariants/{invariant_id}/references/{command_id}
  → 204  detaches the VERIFIED_BY edge only; Command GWT untouched (FR-014)
  → 404 reference not found
```

## §4 Detailed conditions — editing GWT (reuses the existing endpoint)

There is **no new GWT endpoint**. Both the Invariant editor and the Command inspector edit GWT
through the existing endpoint; only `parentType` differs:

```
POST /api/graph/gwt/upsert
  body UpsertGWTRequest
    - referenced (shared) condition:   parentType="Command",   parentId=<commandId>
    - invariant-owned standalone:      parentType="Invariant", parentId=<invariantId>
  → 200 { "success": true, "gwt": {...} }
```

Because a referenced condition is physically the Command's own GWT triple, editing it from the
Invariant editor and from the Command inspector hit the same node — edits propagate with no
extra call and no confirmation prompt (clarification 3, FR-011, FR-012).

`GET /api/graph/gwt/{parentType}/{parentId}` (existing read path) likewise accepts
`parentType="Invariant"` for loading an invariant-owned triple into the editor.

## §5 Behavior summary table

| Action | Endpoint | Graph effect |
|--------|----------|--------------|
| Open Aggregate in design tree | §1 | lazy-migrate legacy text → `Invariant` nodes |
| Add invariant | §2 POST | `MERGE (Invariant)`, `Aggregate-[:HAS_INVARIANT]->` |
| Edit declaration | §2 PATCH | `SET inv.declaration/name/description, inv.updatedAt` |
| Delete invariant | §2 DELETE | detach all edges; delete own GWT; keep referenced Command GWT |
| Reference a Command's criteria | §3 POST | `MERGE (Invariant)-[:VERIFIED_BY]->(Command)` |
| Un-reference | §3 DELETE | delete one `VERIFIED_BY` edge only |
| Edit a shared condition | §4 | upsert Command GWT — visible to Command + every referencing Invariant |
| Declare invariant-only condition | §4 | upsert GWT with `parentType="Invariant"` |

## §6 Cross-feature reuse

`/api/contexts/{id}/full-tree` (navigator) is **extended** so each serialized `Aggregate` also
carries `invariants: InvariantSummaryDTO[]`, letting the design tree render the Invariants group
in the same payload it already fetches (no extra round-trip on tree expand).

## §7 Ingestion — new streamed phase

The existing ingestion SSE stream (`/api/ingest/upload` and related) gains one event:

```
event: EXTRACTING_INVARIANTS
data:  { phase, message, progress, data: { aggregateName, invariantCount } }
```

Emitted by `extract_invariants_phase` (data-model §3), after the `generate_gwt` phase. No new
HTTP endpoint — the phase is part of the existing ingestion workflow.
