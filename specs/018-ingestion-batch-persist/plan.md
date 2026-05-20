# Implementation Plan: Ingestion Batch Persist (UNWIND-based Bulk Insert)

**Branch**: `018-ingestion-batch-persist` (current working branch: `figma-integration`) | **Date**: 2026-05-08 | **Spec**: [./spec.md](./spec.md)
**Input**: Feature specification from `/specs/018-ingestion-batch-persist/spec.md`

## Summary

Replace the per-row `MERGE` round-trips that currently dominate every ingestion phase with `UNWIND $rows AS row …` bulk writes. The phase loops change from "extract one entity → write one row → repeat" to "extract all entities into a list → flush list once via a `bulk_create_<entity>(rows)` helper." The bulk helpers live next to the existing single-row helpers in `api/features/ingestion/event_storming/neo4j_ops/<entity>.py`, follow the same return-shape contract per row, and chunk into ≤ 500-row transactions transparently. The pattern is already proven in this codebase (`references.py`, `properties.py` already use UNWIND); this feature extends it to every entity.

End-to-end: phase wall-clock time for the Neo4j-write step drops by ≥ 70% on the food-delivery sample, total ingestion drops by ≥ 30%, the resulting Neo4j graph is byte-equivalent to the pre-change run, and the spec 017 suspend gate gets a single check point per phase (before each flush) instead of N check points (one per row) — actually simpler than the per-row variant.

## Technical Context

**Language/Version**: Python 3.11+ (FastAPI, Neo4j Python driver). No new runtime dependencies.
**Primary Dependencies**: existing `neo4j` Python driver (already used). The driver natively accepts `list[dict]` as a `$rows` parameter for `UNWIND` — no extra serialization layer.
**Storage**: Neo4j only. No new labels or constraints. Uses existing keys (the canonical `key` derivation in `api/platform/keys.py`).
**Testing**: pytest for the bulk helpers (input list, expected return list, idempotency on re-run); existing Playwright `figma-ui-bulk-diag.spec.ts` doubles as the end-to-end regression because it already verifies graph equivalence. New micro-bench script counts Neo4j write transactions per phase before vs after.
**Target Platform**: backend on `localhost:8000`, Neo4j on `bolt://localhost:7687`.
**Project Type**: Web-application backend; this feature is server-side only (no frontend changes).
**Performance Goals**:
- Per-phase Neo4j-only wall-clock time reduced by ≥ 70% on the food-delivery sample (SC-001).
- Total ingestion time reduced by ≥ 30% (SC-004).
- No regression in graph correctness (SC-002).
- Suspend latency unchanged at ≤ 30 s worst case (SC-005).
**Constraints**:
- Single-row helpers stay (Constitution V — other features call them). Bulk helpers are *additions*, not replacements.
- Each bulk helper issues at most one Cypher transaction per chunk; chunk default 500 rows (configurable via `INGESTION_BATCH_SIZE` env).
- Per-row error capture: helpers return `[{ok, id, error}, …]` mirroring inputs 1:1.
- Bulk helpers MUST be transactional: a chunk either fully commits or fully rolls back. A single bad row that violates a Cypher-level constraint kills its chunk; pre-validation (FR-005) keeps that rare.
**Scale/Scope**: ingestion phases produce 5–500 rows per entity per run. The chunk size of 500 means typical phases finish in 1 chunk; outlier large documents may split into 2–4 chunks.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Graph-as-Source-of-Truth | ✅ | Persistence target is unchanged: same Neo4j, same labels, same keys. Only the *write strategy* changes. SC-002 enforces graph byte-equivalence. |
| II. Event Storming as Domain Vocabulary | ✅ | No vocabulary change. Bulk helper names mirror domain entity names (`bulk_create_event`, `bulk_create_command`, …). |
| III. Streaming-First UX | ✅ | Phase-level SSE progress events still fire (one at flush start, one at flush end). The reduction is in *per-row* events during the flush itself, which were noisy and not load-bearing. The architect still sees "X user stories created" at flush completion. |
| IV. Human-in-the-Loop on Mutations | ✅ | This change is internal to the workflow's persistence layer; user-driven mutations (chat-modify, change-plan apply) are unaffected. |
| V. Feature-Modular Architecture | ✅ | All edits stay inside `api/features/ingestion/event_storming/neo4j_ops/` (helper additions) and `api/features/ingestion/workflow/phases/` (call-site swaps). No cross-feature touches; no new feature module. |
| VI. Provider-Agnostic LLM Runtime | ✅ | LLM layer untouched. |
| VII. Observable by Default | ✅ | Each flush emits one `ingestion.batch.<entity>.flush` SmartLogger event with `{count, durationMs, chunked, errorRows}`. Per-phase totals roll up as today. |

**Result**: All gates pass; no Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/018-ingestion-batch-persist/
├── plan.md              # This file
├── research.md          # Phase 0 — bulk helper signatures, chunking, error handling, idempotency
├── data-model.md        # Phase 1 — bulk helper input/output row shapes, no Neo4j schema changes
├── quickstart.md        # Phase 1 — manual perf comparison + graph equivalence check
├── contracts/
│   └── bulk-helpers.md  # Phase 1 — function signatures + return contract per entity type
├── checklists/
│   └── requirements.md  # already created by /speckit-specify
└── tasks.md             # Phase 2 output — created later by /speckit-tasks
```

### Source Code (repository root)

Pure additive backend changes. No frontend changes.

```text
api/
└── features/
    └── ingestion/
        ├── event_storming/
        │   ├── neo4j_ops/
        │   │   ├── _bulk_helper.py                  # NEW: shared chunking + per-row error
        │   │   │                                    # capture pattern. Used by every
        │   │   │                                    # bulk_create_<entity> below.
        │   │   ├── user_stories.py                  # ADD: bulk_create_user_stories(rows)
        │   │   ├── events.py                        # ADD: bulk_create_events(rows)
        │   │   ├── commands.py                      # ADD: bulk_create_commands(rows)
        │   │   ├── aggregates.py                    # ADD: bulk_create_aggregates(rows)
        │   │   ├── policies.py                      # ADD: bulk_create_policies(rows)
        │   │   ├── readmodels.py                    # ADD: bulk_create_readmodels(rows)
        │   │   ├── ui_wireframes.py                 # ADD: bulk_create_uis(rows)
        │   │   ├── gwt.py                           # ADD: bulk_create_gwts(rows)
        │   │   ├── bounded_contexts.py              # ADD: bulk_create_bcs(rows)
        │   │   └── properties.py                    # ALREADY UNWIND — minimal cleanup
        │   │                                        # to match new helper contract.
        │   └── nodes_persist.py                     # MINIMAL EDIT: where this module
        │                                            # currently calls per-row create_*
        │                                            # in a loop, swap to bulk_create_*.
        │                                            # No new logic; just batching.
        └── workflow/
            └── phases/
                ├── user_stories.py                  # SWAP: collect → bulk_create_user_stories
                ├── events.py                        # SWAP: collect → bulk_create_events
                ├── events_from_user_stories.py      # SWAP
                ├── commands.py                      # SWAP
                ├── aggregates.py                    # SWAP
                ├── policies.py                      # SWAP
                ├── readmodels.py                    # SWAP
                ├── ui_wireframes.py                 # SWAP — note: figma-mode bulk_sync
                │                                    # path is independent of this and
                │                                    # already async. UI Neo4j writes
                │                                    # are the part being batched here.
                ├── gwt.py                           # SWAP
                ├── bounded_contexts.py              # SWAP
                ├── link_command_to_events.py        # SWAP (relationship-only batch)
                ├── user_story_sequencing.py        # SWAP (relationship + property update)
                ├── parsing.py                       # No DB writes here (LLM-only); skip.
                ├── properties.py                    # ALREADY batched; verify call-site.
                └── references.py                    # ALREADY batched; verify call-site.

api/platform/env.py                                  # MINIMAL EDIT: add INGESTION_BATCH_SIZE
                                                     # (default 500) helper getter.

logs/ingestion-snapshots/                            # NEW (runtime, gitignored): JSON
                                                     # snapshots when INGESTION_SNAPSHOT_DEBUG=1.
                                                     # FR-010 only.
```

**Structure Decision**: A single shared `_bulk_helper.py` provides the chunking + per-row error capture template. Every entity-specific `bulk_create_*` is a thin wrapper that just supplies the per-entity Cypher and field validation. This means the chunking / retry / per-row-error-isolation behavior is identical across entities — no copy-paste drift. Phase call-sites become trivial:

```python
# Before (per-row):
for evt in events:
    ctx.client.create_event(name=evt.name, command_id=evt.cmd_id, ...)

# After (bulk):
rows = [{"name": evt.name, "command_id": evt.cmd_id, ...} for evt in events]
results = ctx.client.bulk_create_events(rows)  # one transaction
for evt, result in zip(events, results, strict=True):
    if not result["ok"]:
        log_error(evt, result["error"])
```

## Complexity Tracking

> No constitution violations; no entries required.

---

## Phase 0 Output

See [./research.md](./research.md). Decisions resolved:

- D1: Chunking strategy (transparent, default 500, configurable via env).
- D2: Per-row error contract (helpers return `list[dict]` 1:1 with inputs; transactional rollback only on chunk-level failures).
- D3: Pre-flush validation (cheap field presence + size checks; the helper rejects bad rows before issuing Cypher to keep chunks clean).
- D4: Relationship handling (two-pass: nodes first, relationships second; or single-pass MERGE-with-MATCH where the related entity already exists in graph).
- D5: Idempotency (MERGE on canonical `key` from `api/platform/keys.py` keeps re-runs safe).
- D6: Snapshot debug (FR-010) — write JSON to `logs/ingestion-snapshots/<session_id>/<phase>.json` when env flag set; non-blocking on failure.

## Phase 1 Outputs

- [./data-model.md](./data-model.md) — input row shapes per entity type, return shape, snapshot file format.
- [./contracts/bulk-helpers.md](./contracts/bulk-helpers.md) — exact function signatures + Cypher templates per entity.
- [./quickstart.md](./quickstart.md) — manual perf comparison (food-delivery sample, before/after timings + graph diff).
