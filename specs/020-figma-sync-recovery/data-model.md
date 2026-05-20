# Data Model — Figma Sync Recovery & Retroactive Push

Authoritative storage is Neo4j (Constitution I). Schema additions go into `docs/cypher/schema/03_node_types.cypher` (labels) and `docs/cypher/schema/04_relationships.cypher` (relationship types) before any code that reads/writes them ships.

This feature is **strictly additive** to spec 016's data model. The only new entity is `:SyncRun`. Two advisory fields are added to the existing `:FigmaBinding` singleton. One new property is added to existing `:UI` nodes (`figmaSyncBindingFileKey`) so that previous-binding failures can be filtered after a binding replace.

## New: `:SyncRun`

One row per dispatched full-sync or 전체 다시 시도 run. Per-item activity is summarized via the `summary` map; per-item failures continue to live on `:UI {figmaSync*}` (extended below).

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `id` | string (UUID) | yes | UNIQUE constraint. Surfaced as `runId` in API responses. |
| `kind` | enum string | yes | `retroactive-sync` \| `manual-retry`. Distinguishes 전체 Figma 반영 from 다시 시도 dispatches in History summaries. |
| `bindingFileKey` | string | yes | The Figma file key in scope at run time. Discriminates "이전 바인딩" entries when the binding is replaced (FR-013). |
| `actor` | string | yes | User identifier of who clicked the trigger. Same identity convention as 016. |
| `startedAt` | ISO-8601 string | yes | UTC. |
| `finishedAt` | ISO-8601 string | no | UTC. Null while `status='running'`. |
| `status` | enum string | yes | `running` \| `succeeded` \| `partially-succeeded` \| `cancelled` \| `aborted-binding-unreachable`. |
| `summary` | JSON string | no | Map of counters, see below. Null until `finishedAt` is set. |

`summary` map shape (filled in at run-end):
```json
{
  "storyboardsTotal": 5,
  "pagesCreated": 2,
  "pagesAlreadyOk": 3,
  "uisTotal": 19,
  "framesPushed": 17,
  "generated": 14,
  "overwrites": 4,
  "failures": 2
}
```

Constraints:
```cypher
CREATE CONSTRAINT sync_run_id_unique IF NOT EXISTS
FOR (r:SyncRun) REQUIRE r.id IS UNIQUE;

CREATE INDEX sync_run_status_idx IF NOT EXISTS
FOR (r:SyncRun) ON (r.status);

CREATE INDEX sync_run_binding_file_key_idx IF NOT EXISTS
FOR (r:SyncRun) ON (r.bindingFileKey);
```

The status index supports the lock-recovery startup hook (`MATCH (r:SyncRun {status:'running'}) WHERE r.startedAt < $cutoff` — see research D1). The bindingFileKey index supports the History query's "이전 바인딩" filter without scanning all runs.

## Updated: `:FigmaBinding`

The existing 016 singleton (`id:'singleton'`) gains two **advisory lock fields**. Both are set to non-null only while a `:SyncRun {status:'running'}` exists for this binding; both are cleared when the run finalizes.

| Property (added) | Type | Required | Notes |
|------------------|------|----------|-------|
| `currentRunId` | string (UUID) \| null | no | The `id` of the active `:SyncRun`, or null when no run is in flight. |
| `currentRunHolder` | string \| null | no | The actor field of the active `:SyncRun`. Surface-only (rendered as "<actor>가 동기화 중입니다"). |

Atomic acquire (Cypher):
```cypher
MATCH (b:FigmaBinding {id:'singleton'})
WHERE b.currentRunId IS NULL AND b.status = 'active'
SET b.currentRunId = $runId, b.currentRunHolder = $actor
RETURN b
```
- 0 rows returned ⇒ lock contended OR binding not active. Caller checks the binding's actual state to distinguish; on contention, returns 409 with the in-flight `runId` so the client can subscribe.
- 1 row returned ⇒ lock acquired. Caller MUST release in `finally`.

Atomic release:
```cypher
MATCH (b:FigmaBinding {id:'singleton', currentRunId:$runId})
SET b.currentRunId = null, b.currentRunHolder = null
```
- The `currentRunId:$runId` predicate ensures we only release our own lock — no risk of clobbering a successor's lock if release runs late.

## Updated: `:UI`

The existing `:UI` `figmaSync*` fields from 016 v1.2 (`figmaSyncStatus`, `figmaSyncLastError`, `figmaSyncLastAttemptAt`) are unchanged. **One new property** is added so the failure classifier can decide retryability after a binding replace:

| Property (added) | Type | Required | Notes |
|------------------|------|----------|-------|
| `figmaSyncBindingFileKey` | string | no | The `figmaFileKey` of the binding at the time the most recent sync attempt was made. Set whenever `figmaSyncStatus` is set to `'failed'` or cleared to `'ok'`. Used by the failure classifier (research D5) to detect "이전 바인딩" failures. |

No constraint or index needed — this property is read alongside `figmaSyncStatus` which is already indirectly limited by the small UI population.

## New: `:SyncRun`-related relationships

| Relationship | From | To | Cardinality | Created When |
|--------------|------|----|-------------|--------------|
| `:RUN_OF` | `:SyncRun` | `:FigmaBinding` | many → 1 | At run start, `MERGE (r)-[:RUN_OF]->(b)`. Used by History query to scope sync-runs to a binding. |

No `:CONTAINS_FAILURE` relationship is introduced — failures are not duplicated as nodes. The History query joins by computation: failure rows come from `MATCH (u:UI {figmaSyncStatus:'failed'})`; summary rows come from `MATCH (r:SyncRun)-[:RUN_OF]->(b:FigmaBinding {id:'singleton'})`.

## Failure classification (computed at read time)

The classifier (`figma_binding/failure_classifier.py`) is a pure function over:
- the `:UI` node (id, displayName, figmaSyncStatus, figmaSyncLastError, figmaSyncLastAttemptAt, figmaSyncBindingFileKey)
- the active `:FigmaBinding` (or null if disconnected)
- a small Neo4j read: does the `:UI` still exist? does the owning entry `:Command` still exist? does the storyboard's `:StoryboardPageMapping` still exist with `status='active'`?
- the `retry_dedupe` in-flight set (process-local)

Output schema for a failure row delivered to the client:
```json
{
  "uiId": "<id>",
  "displayName": "탈퇴 최종 동의 제출",
  "lastError": "<korean>",
  "lastAttemptAt": "<iso8601>",
  "retryability": "retryable" | "non-retryable" | "in-flight",
  "nonRetryableReason": "이전 바인딩" | "대상 UI 가 삭제됨" | "대상 스토리보드가 보관됨" | "바인딩 해제됨" | "Figma 파일에 접근할 수 없음" | null,
  "bindingFileKey": "<file key at write time>"
}
```

## State Transitions

### `:SyncRun.status`

```
            ┌──────────────────────────────────────────┐
            ↓                                          │
       running  ──→  succeeded                         │
                ──→  partially-succeeded               │
                ──→  cancelled                         │
                ──→  aborted-binding-unreachable       │
                                                       │
(only running can transition; terminals are frozen)────┘
```

- `running → succeeded`: every storyboard page exists and every UI ended `figmaSyncStatus='ok'`.
- `running → partially-succeeded`: one or more UIs ended `figmaSyncStatus='failed'`, but the run reached natural completion.
- `running → cancelled`: user clicked 취소; in-flight items completed, no new dispatches; remaining UIs are NOT marked failed (they remain whatever they were before — typically `null` for never-attempted, `ok` for previously-synced).
- `running → aborted-binding-unreachable`: the binding flipped to `unreachable` mid-run; remaining items are not dispatched and the run is closed with this status.

The lock fields on `:FigmaBinding` clear in lockstep with this transition (in the `finally` block of the orchestrator).

### `:UI.figmaSyncStatus` (unchanged from 016 v1.2, restated for completeness)

```
       null  ──→  ok       (push success)
             ──→  failed   (push failure)
        ok  ──→  ok        (idempotent re-push)
             ──→  failed   (re-push failure)
     failed  ──→  ok       (retry success)
             ──→  failed   (retry failure — error/timestamp updated, status unchanged)
```

## Updates to the Schema Files

`docs/cypher/schema/03_node_types.cypher` gets:
- A new section `// :SyncRun` with the constraint and indexes from above.
- Two new properties documented on the existing `:FigmaBinding` block: `currentRunId` (string|null), `currentRunHolder` (string|null). No constraint added.
- One new property documented on the existing `:UI` block: `figmaSyncBindingFileKey` (string).

`docs/cypher/schema/04_relationships.cypher` gets:
- A new line `(:SyncRun)-[:RUN_OF]->(:FigmaBinding)` with the cardinality note.

Both files are updated in the implementation PR before any code that emits these reads/writes ships, per Constitution Development Workflow.
