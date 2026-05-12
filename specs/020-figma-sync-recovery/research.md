# Phase 0 Research — Figma Sync Recovery & Retroactive Push

All decisions resolved at plan-time. The spec already collapsed three open scope questions into informed defaults during `/speckit-specify` (see spec § Clarifications); this document captures the architectural decisions that follow from those defaults plus a few that arise during implementation planning.

## D1 — Project-scoped sync lock mechanism

**Question**: How do we prevent two collaborators from dispatching concurrent full-sync runs against the same binding (FR-017), while still letting a second user *join* the in-flight progress view (read-only)?

**Decision**: Use two new advisory fields on the existing `:FigmaBinding` singleton — `currentRunId` (string|null) and `currentRunHolder` (string|null) — mutated atomically with a guarded Cypher write. A second dispatch sees `currentRunId IS NOT NULL` and gets back `409 Conflict` with the in-flight `runId` so the client can subscribe to its SSE stream as a passive observer.

**Rationale**:
- 016 already established that the binding is a singleton (one `:FigmaBinding` per deployment). Adding two fields to that node is the cheapest possible lock — no new label, no new index, no separate lock service.
- The Cypher `MATCH (b:FigmaBinding {id:'singleton'}) WHERE b.currentRunId IS NULL SET b.currentRunId = $runId, b.currentRunHolder = $actor RETURN b` returns 0 rows on contention, which is the natural test for "lock not acquired" — no separate query needed.
- The client subscribing as a passive observer is a feature, not a bug: when the architect opens the modal during a teammate's run, they see live progress immediately, which is exactly what FR-017 requires.

**Alternatives considered**:
- *Process-level `asyncio.Lock`*: works for single-process FastAPI, breaks the moment we run multiple workers. Backend already runs single-worker for development but production deployments may scale; tying correctness to that is brittle.
- *Distributed lock via Redis/etcd*: introduces a new infra dependency just for one feature. Constitution V's "through the platform layer or through Neo4j" — Neo4j is already there, use it.
- *Separate `:ProjectSyncLock` node*: same correctness as the field-on-binding approach with extra schema noise (need a relationship, need a constraint to prevent duplicates). The binding singleton constraint already gives us "one lock at a time" for free.

**Consequences**:
- Lock release MUST happen in `finally` blocks of every full-sync code path, including `CancelledError` and process termination. Stale locks on crash are recovered via a startup hook in `service.py` that releases any `currentRunId` whose corresponding `:SyncRun {status:'running'}` is older than 30 minutes (a `:SyncRun` startedAt watermark).
- The `currentRunHolder` field is informational (used to render "다른 사용자가 동기화 중입니다 — by <actor>" in the busy state). It is NOT a security boundary; any actor can join the progress view.

## D2 — `:SyncRun` granularity (per-run vs per-item)

**Question**: How granular should the History tab's summary rows be? Per dispatched run, per storyboard, per UI?

**Decision**: One `:SyncRun` per dispatched full-sync or 전체 다시 시도. Per-item activity (per-page, per-frame) is collapsed into a `summary` map on the run; per-item *failures* continue to live on `:UI {figmaSyncStatus:'failed'}` (the existing 016 v1.2 store) — they are NOT duplicated as separate `:SyncRun` rows or sub-rows.

`:SyncRun` shape:
```
{ id, kind: 'retroactive-sync' | 'manual-retry',
  startedAt, finishedAt, status: 'running'|'succeeded'|'partially-succeeded'|'cancelled'|'aborted-binding-unreachable',
  bindingFileKey,  // file key at run-time (so 이전 바인딩 entries can be filtered)
  actor,           // who clicked the button
  summary: { storyboardsTotal, pagesCreated, pagesAlreadyOk, uisTotal, framesPushed, generated, overwrites, failures } }
```

**Rationale** (matches spec Q3 "실패 + 요약만"):
- Failures are the thing the user acts on — they need their own first-class rows with retry controls. Putting them on `:UI` (where 016 already keeps them) means the modal History tab + ingestion floating panel + Inspector badge all read from the same store and clear together.
- Successes are the thing the user audits — "did we sync? when? how much?". One summary row per run is enough; a sub-row per page or frame would create thousands of rows for a busy project.
- `bindingFileKey` on the run is the discriminator that makes "이전 바인딩" grouping (FR-013) a simple filter in Cypher, not a join through history events.

**Alternatives considered**:
- *Per-item rows in `:BindingHistoryEvent`*: 016 already does this for binding lifecycle. Adding per-page and per-frame events here would explode the table. Rejected.
- *No `:SyncRun` at all, derive summaries from `:BindingHistoryEvent`*: would force the History query to aggregate hundreds of events per run, slowing every modal open. Rejected.

## D3 — In-flight retry deduplication

**Question**: Two collaborators (or the same collaborator across two surfaces — modal + Inspector badge) can click 다시 시도 on the same UI at nearly the same moment. How do we prevent two plugin dispatches?

**Decision**: A process-level `dict[str, asyncio.Future]` keyed by UI id in a new `figma_binding/retry_dedupe.py` module. The first caller creates the Future and runs the actual retry; concurrent callers `await` the same Future. Cleared after the Future completes. This is a single-process dedupe — sufficient because:
1. The Figma plugin transport (`figma_plugin_ws.py`) is process-local; cross-process duplicate dispatches happen only if multiple FastAPI workers all hold a plugin connection, which is not the current deployment shape.
2. The plugin layer itself is idempotent on `CREATE_FRAME_IN_PAGE` for an existing frame (it returns the same node id); even if a duplicate slipped through, no duplicate frame would be created.

**Rationale**:
- `asyncio.Future` is the lightest primitive that lets multiple awaiters share one outcome.
- Dedupe in the service layer (not the router) — the same protection applies to retry triggered from the bulk_sync path (016) and from the new full_sync path.

**Alternatives considered**:
- *Lock on `:UI` node via Cypher*: across-process correctness but every retry pays a Neo4j round-trip just for serialization. The plugin's idempotency makes that overhead unjustified.
- *Token-based fencing*: too elaborate for the failure mode actually observed.

## D4 — Bridging into ingestion's figma-mode generator

**Question**: Full-sync needs to generate sceneGraphs for UIs that lack one (Q1 "Generate + Push"). The existing generator `_generate_jsx_scene_graph_for_figma_mode` lives in `api/features/ingestion/workflow/phases/ui_wireframes.py`. Constitution V forbids cross-feature imports of internal modules. How do we bridge?

**Decision**: Extract a thin module-public wrapper `generate_jsx_for_existing_ui(ui_id, *, actor) -> dict | None` in `ui_wireframes.py` that:
1. Reads the `:UI` node from Neo4j (its display name, owning command, owning storyboard).
2. Builds the same `IngestionWorkflowContext`-shaped object the existing generator expects (or a minimal shim with the fields it actually reads — `session_id`, `correlation_id`, `actor`).
3. Calls the existing private `_generate_jsx_scene_graph_for_figma_mode(...)` and returns the resulting sceneGraph (or None if the agent gave up after all 3 attempts).

`figma_binding.full_sync` imports *only* this one module-public function — same shape and constraint as 016 v1.2's `figma_binding.bulk_sync.sync_batch` being imported from `ingestion`. The pattern is symmetric: each feature exposes one named bridge function for the other side to call.

**Rationale**:
- Avoids creating a third feature module just to host the generator. The generator's natural home is ingestion (it was built for the bulk path), and the wrapper is a deliberate, named affordance.
- The bridge is one function — easy to reason about and easy to test in isolation (mock the wrapper, assert full_sync called it the right number of times with the right ids).

**Alternatives considered**:
- *Move the generator to `api/platform/`*: it would no longer be a feature concern. But the generator depends on the LLM runtime and the agent loop, and `platform/` is reserved for low-level cross-cutting infrastructure (Neo4j driver, observability). Moving it would muddy the layer.
- *Reimplement a slimmer generator inside `figma_binding`*: duplicates 016 v1.1 reliability hardening (3 retry layers, semaphore caps) which would inevitably drift. Rejected.

## D5 — Non-retryable failure classification

**Question**: FR-012 lists four cases that should mark a failure non-retryable: (a) binding replaced (different file key), (b) underlying storyboard/UI deleted/archived, (c) binding `disconnected`, (d) Figma file confirmed unreachable. How is this decided, and when?

**Decision**: A pure-function classifier `failure_classifier.classify(failure, current_binding, neo4j_view) -> 'retryable' | 'non-retryable' | 'in-flight'` evaluated **at read time** (when the History tab query runs) — not stored on the failure record. Stale classifications are not possible because we always recompute from current state.

Inputs:
- `failure.bindingFileKey`: recorded on the `:UI` at write time (extension of 016 v1.2 — add `figmaSyncBindingFileKey` to the `:UI` node).
- `current_binding`: the active `:FigmaBinding` (or null if disconnected).
- `neo4j_view`: query results "does this `:UI` still exist?", "does the owning storyboard's entry command still exist?", "is the binding's file actually reachable?" (the last is bounded — the classifier uses the most recent reachability probe from `:FigmaBinding.status`, not a fresh probe per row).
- In-flight: cross-checked against `retry_dedupe`'s in-flight set.

Output: `'retryable' | 'non-retryable' | 'in-flight'` plus, when non-retryable, a Korean reason ('이전 바인딩', '대상 UI 가 삭제됨', '대상 스토리보드가 보관됨', '바인딩 해제됨', 'Figma 파일에 접근할 수 없음').

**Rationale**:
- Recomputing at read time means the user always sees the current truth, not a snapshot from when the failure happened.
- The classifier is pure and testable — six cases, each a few lines.
- Storing `figmaSyncBindingFileKey` on the `:UI` at write time is the only persistent change; it's necessary because once the binding is replaced, we can no longer figure out which previous binding a failure belonged to without it.

**Alternatives considered**:
- *Store retryability flag on `:UI`*: would have to be invalidated whenever the binding is replaced or a storyboard archived. Bug-prone. Rejected.
- *Separate `:FailureClassification` node*: extra storage with no benefit. Rejected.

## Summary table

| Concern | Decision | Where it lives |
|---|---|---|
| Sync lock | 2 fields on `:FigmaBinding` + atomic Cypher | `repository.py` |
| Run summaries | `:SyncRun` Neo4j node, one per dispatched run | `repository.py` |
| Retry dedupe | Process-local `dict[str, Future]` | `figma_binding/retry_dedupe.py` (new) |
| Generator bridge | Module-public wrapper in ingestion | `ingestion/workflow/phases/ui_wireframes.py` |
| Retryability | Pure classifier at read-time | `figma_binding/failure_classifier.py` (new) |
| Failure store | Existing `:UI {figmaSync*}` from 016 v1.2 + new `figmaSyncBindingFileKey` | unchanged + tiny extension |

All five decisions preserve the constitution: Neo4j stays the source of truth; vocabulary stays Event Storming-flavored; the long-running full-sync streams over SSE; explicit user click is the human-in-the-loop gate; no cross-feature internal imports; LLM provider is unchanged; SmartLogger covers all phase boundaries.
