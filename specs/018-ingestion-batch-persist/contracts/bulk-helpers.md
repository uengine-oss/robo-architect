# Bulk Helper Contracts — 018 Ingestion Batch Persist (Phase 1)

This document specifies the exact function signatures and Cypher templates each `bulk_create_<entity>` helper exposes. Internal modules (the ingestion phases) call these helpers; no HTTP / SSE / external surface is added by this feature.

## Common contract

Every helper:

```python
def bulk_create_<entity>(self, rows: list[dict]) -> list[BulkResult]:
    """
    Persist `rows` in one or more chunked Neo4j transactions.

    - Validates each row in Python (required fields, field-size limits,
      duplicate-key detection within batch). Invalid rows return
      `{ok: False, error: "...", error_field: "..."}` and are excluded
      from the Cypher transaction.
    - Chunks valid rows by INGESTION_BATCH_SIZE (default 500) and runs
      one transaction per chunk, sequentially.
    - On chunk-level failure (Neo4j unreachable, deadlock, transaction
      timeout): retries the chunk once with a 1 s back-off; on second
      failure, every row in that chunk is marked `{ok: False, error: "..."}`.
    - Return list mirrors `rows` 1:1 in input order.
    - Empty `rows` → empty return, no Neo4j round-trip.
    """
```

The helpers are methods on the existing `Neo4jClient` class (mixed in from `event_storming/neo4j_ops/<entity>.py` per the existing pattern).

## Shared `_bulk_helper` API

```python
# api/features/ingestion/event_storming/neo4j_ops/_bulk_helper.py

def chunked(rows: list[dict], size: int) -> Iterator[list[dict]]:
    """Yield rows in chunks of `size`."""

def validate_required(rows: list[dict], required: list[str]) -> tuple[list[dict], list[BulkResult]]:
    """Split rows into (valid, error_results) by required-field presence."""

def run_chunk(
    session,
    cypher: str,
    rows: list[dict],
    *,
    return_field: str = "result",  # the field name in each row of the Cypher RETURN clause
) -> list[dict]:
    """
    Run one UNWIND chunk and return the per-row Cypher RETURN value, in input order.
    Raises on Neo4j-level error (caller decides retry policy).
    """

def with_retry(fn, *, retries: int = 1, backoff: float = 1.0):
    """Run fn; on Neo4j-level exception, sleep and retry up to `retries` times."""

def emit_flush_log(entity: str, count: int, duration_ms: float, chunks: int, errors: int):
    """SmartLogger event `ingestion.batch.<entity>.flush`."""

def maybe_snapshot(session_id: str, phase: str, entity: str, rows: list[dict]) -> None:
    """When INGESTION_SNAPSHOT_DEBUG=1, write rows to logs/ingestion-snapshots/."""
```

Each `bulk_create_<entity>` is then a thin wrapper:

```python
def bulk_create_events(self, rows: list[dict]) -> list[BulkResult]:
    valid, errors = validate_required(rows, required=["name", "command_id"])
    # Derive keys + dedupe
    valid = self._derive_event_keys(valid)
    valid = dedupe_by_key(valid)
    # Chunked flush
    started = perf_counter()
    out: list[BulkResult] = []
    chunk_count = 0
    for chunk in chunked(valid, get_batch_size()):
        chunk_count += 1
        try:
            with self.session() as session:
                rs = with_retry(lambda: run_chunk(session, _EVENT_CYPHER, chunk, return_field="event"))
            for row, r in zip(chunk, rs, strict=True):
                out.append({"ok": True, "id": r["id"], "key": r["key"], **r})
        except Exception as e:
            for row in chunk:
                out.append({"ok": False, "error": str(e)})
    # Reassemble in input order
    final = reorder_to_input(rows, out, errors)
    emit_flush_log("event", len(rows), (perf_counter()-started)*1000, chunk_count, sum(1 for r in final if not r.get("ok")))
    maybe_snapshot(...) 
    return final
```

## Per-entity Cypher templates

Below are illustrative templates; see `data-model.md` for required input fields per entity.

### `:UserStory`

```cypher
UNWIND $rows AS r
MERGE (us:UserStory {id: r.id})
  ON CREATE SET us.createdAt = datetime()
SET us.role = r.role,
    us.action = r.action,
    us.benefit = r.benefit,
    us.description = r.description,
    us.ui_description = r.ui_description,
    us.source_screen_name = r.source_screen_name,
    us.is_estimated = coalesce(r.is_estimated, false),
    us.updatedAt = datetime()
RETURN us {.id, .role, .action, .benefit, .description, .ui_description, .source_screen_name, .is_estimated} AS user_story
```

### `:Event` (with `[:EMITS]` from existing `:Command`)

```cypher
UNWIND $rows AS r
MATCH (cmd:Command {id: r.command_id})
MERGE (evt:Event {key: r.key})
  ON CREATE SET evt.id = randomUUID(), evt.createdAt = datetime()
SET evt.name = r.name,
    evt.displayName = coalesce(r.display_name, r.name),
    evt.version = coalesce(r.version, "1.0.0"),
    evt.schema = r.schema,
    evt.payload = r.payload,
    evt.description = r.description,
    evt.isBreaking = false,
    evt.updatedAt = datetime()
MERGE (cmd)-[:EMITS {isGuaranteed: true}]->(evt)
RETURN evt {.id, .key, .name, .displayName, .version, .schema, .payload, .description} AS event
```

If `r.command_id` doesn't match, the `MATCH` produces no row and the `MERGE` is skipped — the helper marks that input row as `{ok: False, error: "command not found"}`.

### `:Command` (two-pass — nodes, then `[:REFERENCES]` rels)

Pass 1 (nodes + `:HAS_COMMAND` rel from existing `:Aggregate`):

```cypher
UNWIND $rows AS r
MATCH (agg:Aggregate {id: r.aggregate_id})
MERGE (cmd:Command {key: r.key})
  ON CREATE SET cmd.id = randomUUID(), cmd.createdAt = datetime()
SET cmd.name = r.name,
    cmd.displayName = coalesce(r.display_name, r.name),
    cmd.description = r.description,
    cmd.actor = r.actor,
    cmd.updatedAt = datetime()
MERGE (agg)-[:HAS_COMMAND]->(cmd)
RETURN cmd {.id, .key, .name, .displayName} AS command
```

Pass 2 (per-row UserStory references — only rows whose `user_story_ids` is non-empty):

```cypher
UNWIND $links AS l
MATCH (cmd:Command {id: l.cmd_id})
MATCH (us:UserStory {id: l.us_id})
MERGE (cmd)-[:REFERENCES]->(us)
```

### `:Aggregate` (with `[:HAS_AGGREGATE]` from `:BoundedContext`)

```cypher
UNWIND $rows AS r
MATCH (bc:BoundedContext {id: r.bc_id})
MERGE (agg:Aggregate {key: r.key})
  ON CREATE SET agg.id = randomUUID(), agg.createdAt = datetime()
SET agg.name = r.name,
    agg.displayName = coalesce(r.display_name, r.name),
    agg.description = r.description,
    agg.rootEntity = r.rootEntity,
    agg.updatedAt = datetime()
MERGE (bc)-[:HAS_AGGREGATE]->(agg)
RETURN agg {.id, .key, .name, .rootEntity} AS aggregate
```

### `:Policy`

```cypher
UNWIND $rows AS r
MATCH (trigger:Event {id: r.trigger_event_id})
MERGE (pol:Policy {name: r.name, trigger_event_id: r.trigger_event_id})
  ON CREATE SET pol.id = randomUUID(), pol.createdAt = datetime()
SET pol.description = r.description,
    pol.invoke_command = r.invoke_command,
    pol.invoke_command_id = r.invoke_command_id,
    pol.updatedAt = datetime()
MERGE (trigger)-[:TRIGGERS]->(pol)
WITH pol, r
OPTIONAL MATCH (target:Command {id: r.invoke_command_id})
FOREACH (_ IN CASE WHEN target IS NOT NULL THEN [1] ELSE [] END |
  MERGE (pol)-[:INVOKES]->(target)
)
RETURN pol {.id, .name, .description} AS policy
```

### `:ReadModel`

```cypher
UNWIND $rows AS r
MATCH (bc:BoundedContext {id: r.bc_id})
MERGE (rm:ReadModel {id: r.id})
  ON CREATE SET rm.createdAt = datetime()
SET rm.name = r.name,
    rm.displayName = coalesce(r.display_name, r.name),
    rm.description = r.description,
    rm.actor = r.actor,
    rm.updatedAt = datetime()
MERGE (bc)-[:HAS_READMODEL]->(rm)
RETURN rm {.id, .name, .displayName} AS readmodel
```

### `:UI`

```cypher
UNWIND $rows AS r
MATCH (bc:BoundedContext {id: r.bc_id})
MERGE (ui:UI {key: r.key})
  ON CREATE SET ui.id = randomUUID(), ui.createdAt = datetime()
SET ui.name = r.name,
    ui.displayName = coalesce(r.display_name, r.name),
    ui.description = r.description,
    ui.template = r.template,
    ui.sceneGraph = r.scene_graph,
    ui.attachedToId = r.attached_to_id,
    ui.attachedToType = r.attached_to_type,
    ui.attachedToName = r.attached_to_name,
    ui.userStoryId = r.user_story_id,
    ui.figmaFileKey = r.figma_file_key,
    ui.figmaNodeId = r.figma_node_id,
    ui.figmaPageId = r.figma_page_id,
    ui.figmaBindingId = r.figma_binding_id,
    ui.figmaStoryboardCommandId = r.figma_storyboard_command_id,
    ui.designSource = r.design_source,
    ui.updatedAt = datetime()
MERGE (bc)-[:HAS_UI]->(ui)
WITH ui, r
CALL {
  WITH ui, r
  MATCH (target {id: r.attached_to_id}) WHERE target:Command OR target:ReadModel
  MERGE (ui)-[:ATTACHED_TO]->(target)
  RETURN count(*) AS _
}
RETURN ui {.id, .key, .name, .displayName, .attachedToType, .attachedToName} AS ui_node
```

### `:GWT`

```cypher
UNWIND $rows AS r
MERGE (gwt:GWT {id: r.id})
  ON CREATE SET gwt.createdAt = datetime()
SET gwt.given = r.given,
    gwt.`when` = r.when,
    gwt.then = r.then,
    gwt.updatedAt = datetime()
WITH gwt, r
OPTIONAL MATCH (cmd:Command {id: r.command_id})
FOREACH (_ IN CASE WHEN cmd IS NOT NULL THEN [1] ELSE [] END |
  MERGE (cmd)-[:HAS_GWT]->(gwt)
)
WITH gwt, r
OPTIONAL MATCH (pol:Policy {id: r.policy_id})
FOREACH (_ IN CASE WHEN pol IS NOT NULL THEN [1] ELSE [] END |
  MERGE (pol)-[:HAS_GWT]->(gwt)
)
RETURN gwt {.id, .given, .`when`, .then} AS gwt
```

### `:BoundedContext`

```cypher
UNWIND $rows AS r
MERGE (bc:BoundedContext {id: r.id})
  ON CREATE SET bc.createdAt = datetime()
SET bc.name = r.name,
    bc.type = r.type,
    bc.description = r.description,
    bc.updatedAt = datetime()
RETURN bc {.id, .name, .type} AS bc
```

## Relationship-only batches

### `bulk_link_emits(rows)` — `(:Command)-[:EMITS]->(:Event)` (post-hoc fixup)

```cypher
UNWIND $rows AS r
MATCH (cmd:Command {id: r.cmd_id})
MATCH (evt:Event {id: r.evt_id})
MERGE (cmd)-[em:EMITS]->(evt)
SET em.isGuaranteed = coalesce(r.is_guaranteed, true)
RETURN cmd.id AS cmd_id, evt.id AS evt_id
```

(Used by `link_command_to_events.py` phase.)

### `bulk_set_event_sequence(rows)` — set `:Event.sequence` from user-story flow

```cypher
UNWIND $rows AS r
MATCH (evt:Event {id: r.evt_id})
SET evt.sequence = r.sequence
RETURN evt.id AS evt_id, evt.sequence AS sequence
```

(Used by `user_story_sequencing.py`.)

## Logging contract

Each helper emits exactly one SmartLogger event per call:

```python
SmartLogger.log("INFO",
    f"ingestion.batch.{entity}.flush count={count} duration_ms={d} chunks={c} errors={e}",
    category=f"ingestion.batch.{entity}.flush",
    params={
        "session_id": ...,
        "phase": ...,
        "count": count,
        "durationMs": d,
        "chunks": c,
        "errorRows": e,
    },
)
```

Plus, for every error row, one debug-level log line `ingestion.batch.{entity}.row_error` with the row's primary key and the error message. (Suppressed at INFO level in production.)
