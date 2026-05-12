# Data Model — 018 Ingestion Batch Persist (Phase 1)

This feature changes only the **write strategy** to Neo4j. There are no new labels, no new properties, no new constraints. The Neo4j schema is unchanged.

What this document specifies:

- Input row shapes for each `bulk_create_<entity>` helper.
- Common return shape across all helpers.
- Snapshot file format for the FR-010 debug feature.

## Common shapes

### Per-row return

Every `bulk_create_<entity>` returns `list[BulkResult]` with one entry per input row, in input order:

```python
class BulkResult(TypedDict, total=False):
    ok: bool                # True if persisted; False if rejected pre-flush or chunk-level failure
    id: str | None          # the entity's UUID (Neo4j-generated) when ok=True; None otherwise
    key: str | None         # canonical natural key (from api/platform/keys.py); always set on ok=True
    error: str | None       # human-readable error string when ok=False
    error_field: str | None # specific field that failed validation, when applicable
    # Plus selected entity fields the caller needs (matches existing single-row return)
```

### Per-row input

Every helper accepts `rows: list[dict]` where each dict carries the same fields the existing single-row helper expects. The helper supplies the same defaults the single-row helper does (e.g., `display_name = display_name or name`). Bulk helpers do NOT accept extra parameters — all per-row variation goes inside the row dict.

## Per-entity row shapes

### `bulk_create_user_stories(rows)` → `:UserStory`

Input row:
```python
{
    "id": str,                    # required; LLM-supplied stable id
    "role": str,
    "action": str,
    "benefit": str,
    "description": str | None,    # optional
    "ui_description": str | None, # optional
    "source_screen_name": str | None, # optional
    "is_estimated": bool,         # optional, default False
}
```

Cypher: `UNWIND $rows AS r MERGE (us:UserStory {id: r.id}) ON CREATE SET us.createdAt = datetime() SET us.role = r.role, …, us.updatedAt = datetime() RETURN us {.id, .role, .action, .benefit} AS user_story`

### `bulk_create_events(rows)` → `:Event` + `[:EMITS]` from Command

Input row:
```python
{
    "name": str,                  # required
    "command_id": str,            # required; cross-phase relationship target
    "key": str | None,            # optional; derived if absent
    "version": str,               # default "1.0.0"
    "schema": str | None,
    "payload": str | None,
    "display_name": str | None,
    "description": str | None,
}
```

Strategy: single-pass (D4) — `MATCH (cmd:Command {id: r.command_id}) MERGE (evt:Event {key: r.key}) … MERGE (cmd)-[:EMITS]->(evt)`. Rows whose `command_id` doesn't match an existing Command return `{ok: False, error: "command not found"}` for that row.

### `bulk_create_commands(rows)` → `:Command` + `[:HAS_COMMAND]` from Aggregate

Input row:
```python
{
    "name": str,
    "aggregate_id": str,          # required; cross-phase
    "key": str | None,
    "display_name": str | None,
    "description": str | None,
    "actor": str | None,
    "user_story_ids": list[str],  # used to attach :REFERENCES :UserStory rels in the same flush (two-pass: nodes then rels)
}
```

Strategy: two-pass — flush Command nodes, then flush `(cmd)-[:REFERENCES]->(us)` relationship rows.

### `bulk_create_aggregates(rows)` → `:Aggregate` + `[:HAS_AGGREGATE]` from BC

Input row:
```python
{
    "name": str,
    "bc_id": str,                 # required; cross-phase
    "key": str | None,
    "display_name": str | None,
    "description": str | None,
    "rootEntity": str | None,
    "user_story_ids": list[str],
}
```

### `bulk_create_policies(rows)` → `:Policy`

```python
{
    "name": str,
    "trigger_event_id": str,
    "invoke_command_id": str | None,
    "invoke_command": str | None, # name fallback when id absent
    "description": str | None,
    "user_story_ids": list[str],
}
```

### `bulk_create_readmodels(rows)` → `:ReadModel`

```python
{
    "id": str,                    # LLM-supplied
    "name": str,
    "bc_id": str,
    "display_name": str | None,
    "description": str | None,
    "actor": str | None,
    "user_story_ids": list[str],
}
```

### `bulk_create_uis(rows)` → `:UI` + `[:HAS_UI]` from BC + `[:ATTACHED_TO]`

```python
{
    "key": str,                   # required; UI keys are deterministic
    "name": str,
    "bc_id": str,
    "description": str | None,
    "template": str,              # may be empty in figma mode
    "scene_graph": str | None,    # JSON string
    "attached_to_id": str,
    "attached_to_type": str,      # "Command" | "ReadModel"
    "attached_to_name": str,
    "user_story_id": str | None,
    "display_name": str | None,
    # Figma-binding (016) fields, optional:
    "figma_file_key": str | None,
    "figma_node_id": str | None,
    "figma_page_id": str | None,
    "figma_binding_id": str | None,
    "figma_storyboard_command_id": str | None,
    "design_source": str | None,
}
```

### `bulk_create_gwts(rows)` → `:GWT`

```python
{
    "id": str,
    "command_id": str | None,     # one of command_id or policy_id required
    "policy_id": str | None,
    "given": list[str],
    "when": str,
    "then": list[str],
}
```

### `bulk_create_bcs(rows)` → `:BoundedContext`

```python
{
    "id": str,
    "name": str,
    "type": str,                  # "core" | "supporting" | "generic"
    "description": str | None,
}
```

### Relationship-only batches

For phases that only create relationships (e.g., `link_command_to_events`, `user_story_sequencing`), the helper signature is:

```python
def bulk_link_<rel>(rows: list[dict]) -> list[BulkResult]
```

Each row carries `from_id`, `to_id`, plus rel-specific properties. Cypher: `UNWIND $rows AS r MATCH (a:LabelA {id: r.from_id}), (b:LabelB {id: r.to_id}) MERGE (a)-[r:REL_TYPE]->(b) SET r.prop = r.prop_value`.

## Snapshot file format (FR-010)

When `INGESTION_SNAPSHOT_DEBUG=1`:

```text
logs/
└── ingestion-snapshots/
    └── <session_id>/
        ├── extracting_user_stories.user_story.json
        ├── extracting_events.event.json
        ├── extracting_commands.command.json
        └── … (one file per (phase, entity_type) pair)
```

File contents:
```json
{
  "session_id": "...",
  "phase": "extracting_events",
  "entity_type": "event",
  "captured_at": "2026-05-08T14:30:12Z",
  "rows": [
    { /* input row 1 */ },
    { /* input row 2 */ }
  ]
}
```

These files are NOT replayed automatically; they exist for offline forensics. A separate future tool can replay them through the bulk helpers to reproduce a graph state.

## What does NOT change

- Neo4j labels, properties, constraints, indexes — unchanged.
- The single-row create helpers (`create_event`, `create_command`, etc.) keep working; other features call them directly.
- LLM prompts, agent loops, retry stacks — unchanged.
- SSE event types — unchanged.
