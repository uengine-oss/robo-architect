# Research: Ingestion Batch Persist (Phase 0)

## D1 — Chunking strategy

**Decision**: Transparent chunking inside the bulk helper. Default chunk size 500 rows, configurable via `INGESTION_BATCH_SIZE` env. Each chunk is one Neo4j transaction; chunks within a single helper call run sequentially (NOT in parallel — Neo4j-side concurrency control is more predictable when one chunk commits before the next begins).

**Rationale**:
- Neo4j 5.x handles `UNWIND $rows AS row` with up to a few thousand rows per transaction comfortably; 500 is the empirical sweet spot for typical entity sizes (a `:UserStory` with `description` strings of a few hundred chars). Larger chunks risk transaction-size limits or memory pressure on the driver/server.
- Sequential chunks keep error handling simple: if chunk 2 fails, chunks 3+ are not attempted, and the helper returns partial-success results for chunks 1 (committed) and reports chunk 2's rows as failed.
- Configurable env so a deployment with very small entities (e.g., relationship-only batches) can raise to 2000+, or one with very large entities (UI sceneGraphs of 100KB+) can drop to 50.

**Alternatives considered**:
- *No chunking, send everything in one transaction*: rejected. A 1000-row event extraction with 5 KB events each is a 5 MB transaction — well within Neo4j limits but unnecessarily aggressive on memory and produces less helpful error messages on partial failures.
- *Parallel chunks via asyncio.gather*: rejected. Concurrency under the same write transaction is what Neo4j locking serializes anyway; no benefit, and it complicates the per-row return ordering.

## D2 — Per-row error contract

**Decision**: `bulk_create_<entity>(rows: list[dict]) -> list[dict]` where the return list mirrors the input list 1:1 in order. Each return element is `{"ok": bool, "id": str | None, "error": str | None, **entity_fields_returned}`. Pre-flush validation (D3) catches per-row issues before any Cypher runs, populating `error` for invalid rows. The chunk's Cypher then only sees valid rows — chunks succeed or roll back atomically.

**Rationale**:
- 1:1 return ordering means callers can `zip(rows, results, strict=True)` and immediately see which input had which result.
- Splitting per-row validation (cheap, in Python) from chunk transactions (expensive, in Neo4j) means a single bad row rarely takes down its chunk.
- The `entity_fields_returned` (e.g. `{"key": "...", "name": "...", "id": "..."}`) preserves the existing single-row helper return shape — so call-sites that read `result["id"]` or `result["key"]` keep working.

**Alternatives considered**:
- *Throw on first error*: rejected. The whole point of LLM-extracted batches is that some rows may be borderline; we want partial success to be the default, not the exception path.
- *Return only counts*: rejected. Phase logic often needs the persisted entity's `id` to wire up downstream relationships (e.g., the `Event.id` that the next phase's GWT links).

## D3 — Pre-flush validation

**Decision**: Each `bulk_create_<entity>` validates rows in Python before the Cypher transaction:

1. Required-fields check (per entity type — `Event` needs `name + command_id`; `Command` needs `name + aggregate_id`; etc.)
2. Field-size check (any string field > 1 MB → flagged, optional truncate to a configured limit, mark `approximate=True`)
3. Natural-key derivation (compute `key` via `api/platform/keys.py` if not provided)
4. Duplicate-key warning within the batch (D2 in spec edge cases) — log and dedupe in the input list before flushing

Invalid rows get `{"ok": False, "error": "..."}` immediately and are excluded from the chunk. Valid rows enter the chunk.

**Rationale**:
- Cheap pre-flush checks turn most "bad row" cases into structured errors instead of cryptic Neo4j constraint violations.
- Keeping the Cypher chunks "clean" (validated rows only) means a chunk failure is a real Neo4j-level failure (timeout, deadlock, server unreachable) — those cases are rarer and warrant retry (FR-005's "transaction-level error → retry once").

**Alternatives considered**:
- *Push all validation into Cypher*: Cypher's error messages on constraint violation are unhelpful for debugging; structured Python validation gives `{"error": "missing field 'command_id'"}` directly.

## D4 — Relationship handling (two-pass vs single-pass)

**Decision**: Per-entity choice based on whether the relationship target was created in *this* phase or in a *previous* phase.

- **Same-phase relationships** (e.g., a phase that creates both `Aggregate` and its `Command` children, then `HAS_AGGREGATE` and `HAS_COMMAND` rels): two-pass. Flush all `Aggregate` nodes; flush all `Command` nodes; flush relationship rows referencing both via natural keys.
- **Cross-phase relationships** (e.g., `Event.command_id` already exists from the prior phase): single-pass `UNWIND $rows AS row MATCH (cmd:Command {id: row.command_id}) MERGE (evt:Event {key: row.key}) … MERGE (cmd)-[:EMITS]->(evt)`. The MATCH on the prior-phase entity is cheap because it's already indexed by `id`.

The shared `_bulk_helper.py` exposes both patterns; per-entity bulk helpers pick. The helper Cypher template documents which strategy each entity uses.

**Rationale**:
- Two-pass is mandatory when both endpoints of a relationship are created in the same batch; otherwise the MATCH inside `UNWIND` won't see the row created earlier in the same loop iteration.
- Single-pass is simpler and avoids an extra round-trip when the relationship target is already persisted.

**Alternatives considered**:
- *Always two-pass*: rejected. Doubles round-trips for entities with cross-phase relationships (most of them) for no benefit.
- *Always single-pass with `OPTIONAL MATCH ... CREATE` fallback*: complicates Cypher and can produce silent missing-relationship rows. The two strategies are clearer.

## D5 — Idempotency

**Decision**: Every bulk Cypher uses `MERGE` on the entity's canonical `key` (derived in `api/platform/keys.py`). Re-running ingestion on the same input MUST produce the same node count and not duplicate anything.

**Rationale**:
- The single-row helpers already use this pattern; bulk helpers inherit. The risk is in switching from "MERGE per row" to "UNWIND + MERGE per row in one transaction" — but Neo4j's MERGE semantics are unchanged; just batched.
- Constraints in `docs/cypher/schema/01_constraints.cypher` already enforce uniqueness on `key` for most entities, providing a safety net.

**Alternatives considered**:
- *MERGE on `id`*: rejected. `id` is generated server-side via `randomUUID()`; using it as the merge key would create duplicates on re-run.

## D6 — Snapshot debug (FR-010)

**Decision**: When `INGESTION_SNAPSHOT_DEBUG=1`, each phase's bulk helper call also writes the input `rows` to `logs/ingestion-snapshots/<session_id>/<phase>.<entity>.json` (pretty-printed, UTF-8). Best-effort: a write failure logs a warning but does not affect the phase. Default off.

**Rationale**:
- Replay capability for debugging: "what did the LLM extract for this phase?" — currently requires re-running the LLM. Snapshots make it offline-replayable.
- Disk cost is bounded: typical phase has < 1 MB of JSON; cleanup is the user's responsibility (the directory is gitignored).

**Alternatives considered**:
- *Always-on snapshots*: rejected. Disk IO + privacy implications (some inputs are sensitive). Opt-in is right.
- *DB-stored snapshots on `:IngestionRun`*: out of scope (no Neo4j schema changes per the constitution gate).

## Cross-cutting: interaction with spec 017 (suspend gate)

The bulk flush is a single Cypher transaction. Once it starts, it cannot be cancelled mid-stream — that's a Neo4j-server property. The spec 017 suspend gate sits BEFORE each `bulk_create_<entity>(rows)` call, not inside the helper. Concretely:

```python
# In each phase:
async with session_call_slot(ctx.session):  # 017 gate — raises CancelledError if suspended
    results = await asyncio.to_thread(ctx.client.bulk_create_events, rows)
```

If suspend happens *during* the flush (rare; flushes are 50–500 ms typical), the transaction commits and the gate triggers cancellation on the next phase's first call. This is consistent with FR-005 of spec 017: "in-flight call may complete; results MUST NOT trigger further calls."

The reduction from N gate checks (one per row) to 1 gate check per phase per entity type is a *simplification* — not a regression — because the per-row checks were never load-bearing (suspend latency was bounded by the slowest LLM call, not by the per-row Neo4j round-trip).

## Cross-cutting: interaction with spec 016 (bulk_sync)

`figma_binding.bulk_sync.sync_batch` already does the right thing: it accepts a list of UI ids per batch and processes them. This feature does NOT change `bulk_sync` — that path operates on UI rows already in Neo4j and pushes them to Figma; no Neo4j writes inside `bulk_sync.sync_batch` itself (it only updates per-UI status flags via `mark_ui_sync_ok` / `mark_ui_sync_failed`, and those are already single-row updates against ID — fast and not in this scope).

The Neo4j writes that *create* the UI nodes in the first place (in `ui_wireframes.py`) are what this feature batches.
