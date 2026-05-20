# Feature Specification: Ingestion Batch Persist (UNWIND-based Bulk Insert)

**Feature Branch**: `018-ingestion-batch-persist`
**Created**: 2026-05-08
**Status**: Draft
**Input**: User description: "기존에 네 어 어 아 네오4j에 적재할 때 인제스션 과정에서 네오4j에 적재할 때 지금 보면 머지 사이퍼 쿼리를 한 번에 한 번씩 호출하는 것 같아 그렇게 하지 말고 각 단계 예를 들면 유저 스토리라든지 이벤트라든지 이런 것들을 제이슨 파일이나 메모리에 한번에 쭉 다 담아낸 다음에 배치로 네오포제이에 인서트 시켜야 돼 안그러면 속도가 너무 느려"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Faster ingestion through batch persist of LLM-extracted entities (Priority: P1)

When the architect uploads a requirements document, each ingestion phase (`extracting_user_stories`, `extracting_events`, `extracting_commands`, `extracting_readmodels`, `identifying_bc`, `extracting_aggregates`, `identifying_policies`, `generating_gwt`, `link_command_to_events`, `generating_ui`, etc.) currently calls Neo4j once per extracted entity — one MERGE round-trip per user story, per event, per command, etc. With dozens to hundreds of entities per run, the cumulative round-trip latency dominates wall-clock time. The new behavior collects all of a phase's entities in memory (or a temporary JSON buffer) first, then writes them to Neo4j in one or a small number of `UNWIND $rows AS row MERGE …` batched queries. The architect sees ingestion finish meaningfully faster — phases that previously took 30–60 s of pure Neo4j I/O now take 1–3 s.

**Why this priority**: Slow ingestion is a perpetual frustration: a 5-minute LLM-bound run becomes 8–10 minutes when half the time is Neo4j round-trips. Speed is one of the top quality signals for the whole product, and this change unlocks it without any LLM-prompt changes or retry-stack changes.

**Independent Test**: Run the built-in food-delivery sample on a fresh Neo4j. Time the wall-clock duration of each phase before and after the change (both runs use the same LLM provider, same model, same network). Verify (a) each phase's Neo4j-only time drops by ≥ 70%, (b) total entity counts in Neo4j after the run are identical between the two runs (same number of `:UserStory`, `:Event`, `:Command`, `:Aggregate`, `:Policy`, `:UI`, `:GWT`, `:Property`, `:CQRSConfig`, `:CQRSOperation` nodes), (c) all relationships (HAS_AGGREGATE, EMITS, ATTACHED_TO, …) are present.

**Acceptance Scenarios**:

1. **Given** a phase has extracted N entities (N ≥ 5) from the LLM, **When** the phase persists them, **Then** the number of Cypher write transactions issued by that phase MUST be O(1) per entity *type* (not O(N)) — typically 1 transaction per type using `UNWIND $rows AS row …`.
2. **Given** the same input document, **When** the architect runs ingestion before vs. after this change, **Then** the resulting Neo4j graph (counts per label + counts per relationship type) MUST be byte-equivalent (no missing or duplicated nodes/relationships).
3. **Given** ingestion is partway through a phase, **When** the architect suspends (spec 017 FR-005), **Then** the phase MUST still cleanly halt without leaving Neo4j in a half-written state — either the entire batch flushed, or none of it (transactional flush per batch).
4. **Given** an entity in the batch has invalid data (e.g., missing required field), **When** the batch is flushed, **Then** the per-row error MUST be captured and reported (which entity, which field) without dropping the entire batch unless the failure is at the transaction level.

---

### User Story 2 - Phase-level "decide → buffer → flush" pattern is uniform across all phases (Priority: P2)

Today some phases use `UNWIND` (e.g., `references.py`, `properties.py`) and others issue per-item MERGE calls. The new architecture standardizes the pattern so every phase follows the same shape: (1) the LLM step decides what entities to create, (2) those entities are buffered in an in-memory list (and optionally a JSON snapshot for debug), (3) at the end of the phase a single `bulk_create_<entity>(rows)` helper writes them all in one transaction.

**Why this priority**: Beyond raw speed, uniformity makes future maintenance trivial — anyone adding a new entity type (e.g., a future `:Story`, `:Capability`) follows the same template. It also means the suspend gate from spec 017 only needs one check point per entity type per phase (before the flush), not one per row.

**Independent Test**: Code-review pass — every phase under `api/features/ingestion/workflow/phases/` either calls `bulk_create_<entity>(rows)` (or equivalent UNWIND batch) at most once per entity type, or documents an explicit reason for falling back to per-item writes (e.g., a relationship that depends on the current row's auto-generated id). The number of distinct call sites that issue per-row MERGE outside the bulk helpers is monitored as a code-health metric.

**Acceptance Scenarios**:

1. **Given** the codebase, **When** I grep for `client.create_event(...)` / `client.create_command(...)` / `client.create_user_story(...)` etc. inside `workflow/phases/*.py`, **Then** each phase calls each helper at most once (the helper itself takes a list and does an UNWIND), or — if it must call per-item — has a code comment justifying why.
2. **Given** a new entity type is added in the future, **When** the developer adds a new phase, **Then** they have a clear `bulk_create_<entity>` helper to copy from and a single integration test pattern.

---

### Edge Cases

- A batch contains thousands of rows (e.g., a very large document yields 500+ events). The flush MUST stay within Neo4j's transaction-size practical limits — split into chunks of ~500 rows each, but the chunking is transparent to the caller.
- Two rows in the same batch have the same natural key (e.g., two events with the same `name` in the same BC). MERGE on the natural key naturally deduplicates within the batch, but the batch helper MUST log a warning (`ingestion.batch.duplicate_key`) so the architect can spot LLM-output anomalies.
- A batch fails mid-flush due to a Neo4j-level error (timeout, deadlock). The transaction rolls back; the phase MUST retry the batch once (with a 1 s back-off) before surfacing the error to the SSE stream as a phase failure.
- Some entities have *outgoing relationships to entities created in a different phase* (e.g., `Command -[:EMITS]-> Event` where the Event was created in a separate phase). Two strategies are valid:
  1. Flush nodes first, then flush relationships in a second batch, or
  2. Use `MERGE` with `MATCH` semantics on the related entity (relies on the related entity already existing).
  The chosen strategy MUST be documented per phase.
- The phase's LLM extraction returns an empty list (no entities to persist). The flush MUST be a no-op (no Neo4j round-trip) — not even an `UNWIND $empty_list`.
- A row's properties contain values too large for Neo4j (e.g., a 10 MB string). The batch helper MUST validate row size before flushing and either truncate with a warning or fail-fast on that row only — not poison the whole batch.
- The phase emits SSE progress events (e.g., "유저 스토리 5 생성됨" / "5 of 12 user stories"). After the change, there is no per-row event during the flush itself — events fire once at "starting flush" and once at "flush complete" with the final count. Phase-level progress percentage is unchanged; only the granularity of the per-row event stream is reduced.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each ingestion phase MUST collect all of its LLM-extracted entities in memory before issuing any Neo4j write for those entities. Per-row Neo4j round-trips inside the phase's main extraction loop MUST be eliminated.
- **FR-002**: For each entity type (`:UserStory`, `:Event`, `:Command`, `:Aggregate`, `:Policy`, `:ReadModel`, `:UI`, `:GWT`, `:Property`, `:BoundedContext`, `:CQRSConfig`, `:CQRSOperation`, plus relationships), there MUST be a `bulk_create_<entity>(rows: list[dict]) -> list[dict]` helper in `api/features/ingestion/event_storming/neo4j_ops/` that issues a single `UNWIND $rows AS row …` Cypher query per call.
- **FR-003**: Bulk helpers MUST be drop-in replacements at the call-site level (same return shape per row as the existing single-row helpers), so the call-site change is purely "loop+create_one → list+bulk_create." No phase-internal logic changes are required beyond batching.
- **FR-004**: Bulk helpers MUST chunk rows into Neo4j-friendly batches (default 500 rows per transaction; configurable via `INGESTION_BATCH_SIZE` env). Chunking is transparent to callers.
- **FR-005**: When a row in a batch is invalid (e.g., missing required field, validation error), the helper MUST capture the per-row error in its return value (returning a list of `{ok, id, error}` objects) and persist the valid rows. The helper MUST NOT abort the whole batch on a single row error unless the error is at the transaction level (Neo4j unreachable, deadlock).
- **FR-006**: Bulk helpers MUST log a single SmartLogger event per call (`ingestion.batch.<entity>.flush`) with payload `{count, durationMs, chunked, errorRows}` so flush performance is visible.
- **FR-007**: Phase-level wall-clock time for Neo4j writes (excluding LLM time) MUST be reduced by ≥ 70% on the food-delivery sample compared to the pre-batch baseline.
- **FR-008**: The change MUST be backward-compatible at the data level — the resulting Neo4j graph after a run with the same input MUST be identical (same node counts per label, same relationship counts per type) to a pre-change run.
- **FR-009**: Bulk helpers MUST cooperate with the spec 017 suspend gate — the gate sits before the flush call, not inside the flush loop. Once a flush starts, it runs to completion (or transactional rollback). After the flush returns, the next gate check determines whether the phase continues.
- **FR-010**: The ingestion workflow MUST optionally write a JSON snapshot of each phase's collected entities to `logs/ingestion-snapshots/<session_id>/<phase>.json` when `INGESTION_SNAPSHOT_DEBUG=1` is set, for offline replay and debugging. The snapshot is best-effort; failures to write don't affect the phase.

### Key Entities

- **Bulk Helper API** (per entity type, in `event_storming/neo4j_ops/<entity>.py`): `bulk_create_<entity>(rows: list[dict]) -> list[dict]`. Each input row carries the same fields the single-row helper expects; the return list mirrors the input list 1:1 with `{ok, id, error}` per row.
- **Phase Buffer**: a per-phase in-memory `list[dict]` (typed via simple dataclasses where helpful) that accumulates entities during the LLM extraction loop and is passed wholesale to the bulk helper at the end of the phase.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the built-in food-delivery sample, the cumulative Neo4j-only wall-clock time across the whole ingestion drops by ≥ 70% relative to the pre-change baseline. Measured by summing per-phase Neo4j-only timing logs (`ingestion.batch.<entity>.flush.durationMs` after; per-call `MERGE` timing before).
- **SC-002**: For the same input document, the post-change run produces a graph with identical counts per label and per relationship type compared to the pre-change run, across 5 representative documents (small / medium / large / Korean / English-mixed). 0 differences allowed.
- **SC-003**: No phase issues more than 5 distinct write transactions in the steady state (one per entity type plus relationship batches). Measured by counting transactions in Neo4j's `system` query log per phase.
- **SC-004**: The total wall-clock time of ingestion on the food-delivery sample drops by ≥ 30% (LLM time still dominates; this is the realistic ceiling on user-perceived speedup). Measured by panel-visible elapsed time across 3 runs.
- **SC-005**: Suspend latency (spec 017 SC-004) remains ≤ 30 s in the worst case after this change — batching does not make suspend slower.
- **SC-006**: All ingestion phases under `workflow/phases/` either use a `bulk_create_*` helper or have a documented exception with a code comment explaining why per-row writes are required for that phase.

## Assumptions

- Neo4j is the only persistence target affected. Wireframe-service (Bun :7610) and LLM-provider HTTP calls are unrelated and stay one-call-per-item by their nature.
- The single-row create helpers (`create_event`, `create_command`, etc.) are kept and remain functional; this feature *adds* bulk helpers and changes phase call-sites, but does not remove the single-row API. Other features that legitimately create one entity at a time (e.g., per-node Inspector actions) keep using the single-row API.
- The `INGESTION_BATCH_SIZE` default of 500 rows is an industry-standard sweet spot for Neo4j MERGE batches; can be tuned via env if specific deployments hit limits.
- Phases that do "LLM streams a partial result, persist it, then keep streaming" (uncommon but exists in some streaming agents) are out of scope — they remain per-row by design. The expected pattern is "LLM returns a complete list per phase, then we persist." Most existing phases match this.
- The change does not require any LLM-prompt changes. Prompts already produce complete-list outputs per phase; only the persistence step at the bottom of each phase is rewritten.
- Phase-level timing logs already exist (`ingestion.workflow.phase.*`); we only add per-flush timing on top.
- The JSON snapshot debug feature (FR-010) is opt-in; not enabled by default in production, but useful for support / replay.
- Spec 017's suspend gate (`session_call_slot`) is assumed to be already implemented or implemented in parallel. This feature inserts the gate check before each bulk flush; if 017 is not yet merged, this feature defines the same gate contract for its purposes and 017 absorbs it.
