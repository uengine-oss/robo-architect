# Quickstart — 018 Ingestion Batch Persist (manual smoke + perf)

End-to-end manual verification of US1 and US2.

## Prerequisites

- Backend running with the 018 implementation merged.
- Neo4j up; clean DB recommended for the timing comparison (`MATCH (n) DETACH DELETE n` first).
- Frontend running.
- A pre-018 baseline run exists (or you can roll back, time, then re-run with 018).

## Step 1 — Graph equivalence (US1, FR-008, SC-002)

This is the safety check: confirm the new write strategy produces the same graph as the old one.

1. On a fresh Neo4j, run `git stash` to revert 018, restart the backend, ingest the food-delivery sample. Snapshot graph counts:
   ```cypher
   MATCH (n) WITH labels(n)[0] AS label, count(*) AS n RETURN label, n ORDER BY label
   ```
   Save the result as `baseline.txt`.
2. `git stash pop` to restore 018, clear Neo4j, restart, re-ingest the same sample. Snapshot again as `with_018.txt`.
3. `diff baseline.txt with_018.txt` MUST show **no differences**. SC-002 satisfied.

Also compare relationship counts:
```cypher
MATCH ()-[r]->() WITH type(r) AS rel, count(*) AS n RETURN rel, n ORDER BY rel
```
Same diff check.

## Step 2 — Per-phase Neo4j wall-clock time (US1, FR-007, SC-001)

1. Inspect the baseline run's logs (`api/main.py` stdout) and grep for per-phase timings (`ingestion.workflow.phase.*`). Note the `durationMs` for each.
2. Run with 018 enabled. Each phase now emits one extra event per entity type: `ingestion.batch.<entity>.flush durationMs=… count=… chunks=…`.
3. The baseline's "phase total - LLM time" is roughly the per-row Neo4j round-trip cost. Compare to 018's `ingestion.batch.*.flush durationMs` summed across the phase. The latter SHOULD be ≥ 70% smaller. SC-001 satisfied.

Example expected log lines (after):
```
ingestion.batch.event.flush count=25 duration_ms=180 chunks=1 errors=0
ingestion.batch.command.flush count=12 duration_ms=95 chunks=1 errors=0
ingestion.batch.aggregate.flush count=7 duration_ms=70 chunks=1 errors=0
```

vs. baseline (per-row, 25 events at ~50 ms round-trip each):
```
ingestion.neo4j.event count=1 duration_ms=48
ingestion.neo4j.event count=1 duration_ms=51
... (×25)
```

## Step 3 — Total ingestion time (SC-004)

Use the floating status panel's elapsed-time display (or the SSE `done` event's timestamp).

- Baseline: typically 5–8 minutes for the food-delivery sample (LLM-bound + per-row Neo4j).
- 018: typically 3.5–5.5 minutes (LLM-bound only).
- The 018 run MUST be ≥ 30% faster. SC-004 satisfied.

## Step 4 — Suspend latency unchanged (SC-005)

1. Start an ingestion in 018.
2. Click suspend during `extracting_events`.
3. The panel MUST flip to `suspended` within 30 s (worst case = waiting for the in-flight LLM call to finish; the bulk flush itself is < 1 s).
4. Verify no extra Neo4j writes happen post-suspend (Step 5 of spec 017's quickstart applies unchanged).

## Step 5 — Per-row error capture (FR-005)

To test the error-isolation contract:

1. Hand-craft a malformed entity in the LLM extraction (or temporarily inject a row with missing required field via a debug breakpoint).
2. Run the phase. The bulk helper MUST log:
   - One `ingestion.batch.<entity>.flush` with `errors=1`.
   - One `ingestion.batch.<entity>.row_error` (debug level) with the bad row's id.
3. The phase MUST continue with the other rows persisted; downstream phases continue.

## Step 6 — Snapshot debug (FR-010)

1. Set `INGESTION_SNAPSHOT_DEBUG=1` in `.env`, restart backend.
2. Run an ingestion.
3. After the run, `ls logs/ingestion-snapshots/<session_id>/` MUST contain one JSON file per (phase, entity) pair.
4. Inspect a file:
   ```sh
   jq . logs/ingestion-snapshots/<session_id>/extracting_events.event.json
   ```
   The file structure matches `data-model.md` § "Snapshot file format."
5. Unset the env, restart, re-run — the directory MUST not appear (or remain unchanged).

## Step 7 — Re-run idempotency

1. Run ingestion to completion.
2. Without clearing Neo4j, run the SAME ingestion again on the same input.
3. Graph counts MUST be identical (MERGE on canonical `key` deduplicates). No duplicate `:Event`, no duplicate `:Command`, etc. SC-002 (idempotency aspect) satisfied.

## Out of scope (NOT to verify here)

- Cross-session aggregated perf reporting — future feature.
- Bulk delete / bulk update — this feature is bulk *create* only. Updates and deletes still go per-row through existing helpers (rare in the ingestion flow).
- Frontend changes — this feature is server-only.
