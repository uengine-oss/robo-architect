# Phase 1 Data Model: Unified UserStory Editing in Properties Panel

**Feature**: `019-userstory-properties-panel`
**Date**: 2026-05-08

This feature does not introduce a new node label or relationship. It (a) makes an existing property visible/editable end-to-end, and (b) adds two small bookkeeping fields to the existing `UserStory` node to support the regeneration-vs-edit policy decided in research D2.

---

## UserStory node — property delta

Existing label: `UserStory` (see `docs/cypher/schema/03_node_types.cypher:39–58`).

| Property | Type | Status | Notes |
|---|---|---|---|
| `id` | String | unchanged | Stable identifier. |
| `role` | String | unchanged | "As a …" actor. |
| `action` | String | unchanged | "I want to …" action. |
| `benefit` | String | unchanged | "so that …" benefit. |
| `priority` | String | unchanged | `low` / `medium` / `high`. |
| `status` | String | unchanged | `new` / `in-progress` / `done` / etc. (existing values preserved). |
| `acceptanceCriteria` | List<String> | **now read+writeable from the API** | Already persisted by bulk ingestion (`neo4j_ops/user_stories.py:26,39,44`); now also exposed via GET responses and writeable via PATCH. Validation: each element is a non-empty trimmed string after the user submits; empty entries are stripped before write. Order is preserved as authored. |
| `criteriaUserEdited` | Boolean | **NEW** | Default `false`. Set to `true` whenever the PATCH endpoint receives an `acceptance_criteria` value (even an empty list). Used by the ingestion bulk-write phase to skip overwriting `acceptanceCriteria`. |
| `criteriaEditedAt` | DateTime | **NEW** | Default `null`. Set to `datetime()` whenever `criteriaUserEdited` flips to `true` or is re-set by another PATCH that touches criteria. Useful for telemetry and any future "regenerate from scratch" affordance. |

Other fields (`name`, `uiDescription`, `displayName`, `sourceScreenName`, `sourceUnitId`, `sequence`) remain unchanged and are not the subject of this feature.

### Validation rules (applied at the PATCH boundary)

- `acceptance_criteria`, when present, must be a list of strings (length 0 ≤ N ≤ 100). Hard cap of 100 prevents accidental UI runaway; user-visible error if exceeded.
- Each criterion string is trimmed; empty-after-trim entries are dropped silently (mirrors the user's "remove this criterion" gesture from the panel).
- `priority`, when present, must be one of the existing accepted values (validated against the same enum the rest of the codebase uses; no new enum introduced).
- `status`, when present, must be one of the existing accepted values.
- Other fields, when present, must be non-empty strings (matching the contract today on `apply`).
- Body with no recognised mutable fields → 400 (`{"detail": "no fields to update"}`); avoids no-op writes.

### State transitions for `criteriaUserEdited`

```
       [created via apply or ingestion]
                  │
                  ▼
      criteriaUserEdited = false
                  │
   ┌──────────────┼─────────────────┐
   │ PATCH with   │ regeneration    │
   │ acceptance_  │ via ingestion   │
   │ criteria     │ bulk write      │
   ▼              ▼                 │
edited=true    no-op on criteria    │
edited_at=now  (other fields still  │
   │           updated)             │
   │                                │
   └────── stays true forever ──────┘
       (until a future explicit
        "reset" action — out of
        scope for this feature)
```

There is intentionally no automatic path back to `false`. Once a user has curated the criteria, the system treats them as authoritative until the user (or a future explicit reset) says otherwise.

---

## Relationships — unchanged

This feature reads, but does not modify, the existing `UserStory` relationships:

- `(:UserStory)-[:LINKS_TO]->(:Command)` and `(:UserStory)-[:LINKS_TO]->(:Policy)` (or whatever the existing forward edges are — research used the conceptual term "linked to"; the GWT generator already follows them today). The GWT prompt-builder enriches its context by reading `acceptanceCriteria` from any `UserStory` reachable via these existing edges from the Command/Policy under generation. **No new relationship type is introduced.**

---

## Schema documentation update

`docs/cypher/schema/03_node_types.cypher` already lists `acceptanceCriteria: List<String>` for the `UserStory` node. Add the two new properties to the same block in the same PR:

```cypher
// UserStory (excerpt — additions only)
//   criteriaUserEdited: Boolean   // true once PATCH has overwritten criteria; blocks ingestion regen
//   criteriaEditedAt:   DateTime  // timestamp of the last criteria edit
```

Per Constitution / Development Workflow ("any new node label or relationship type MUST be reflected in `docs/cypher/schema/`"): no new label or relationship is added, but the property comment block is updated as a courtesy so the schema docs stay accurate.

---

## What is *not* in this data model

- No new node label.
- No new relationship.
- No history table / criteria revision log. The spec asks for "edit + persist", not "edit history". Out of scope; can be layered later if needed.
- No per-criterion identity. Criteria are a list of strings, not nodes. Reordering and editing operate on list position; there is no stable "criterion id" exposed to the API. (This is fine because GWT generation consumes the list semantically, and the panel renders by index.)
