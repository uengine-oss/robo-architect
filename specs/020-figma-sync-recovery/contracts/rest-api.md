# REST + SSE Contracts — Figma Sync Recovery

All endpoints live under the existing 016 prefix `/api/figma-binding/`. Auth model and correlation-ID handling are inherited unchanged from 016 — every request gets a correlation ID via `api/platform/observability/`.

Status codes follow project convention: 200 for completed reads, 202 for accepted long-running jobs, 204 for no-content writes, 400 for malformed input, 404 when the binding does not exist or is `disconnected`, 409 for lock contention, 410 when the target object (UI/storyboard) was deleted between request and processing.

## POST `/api/figma-binding/full-sync` — start a retroactive full-sync

Triggers the project-wide retroactive sync described in spec US1. Acquires the project-scoped advisory lock (research D1) and returns immediately with the new run's `id`. Per-item progress streams from the SSE endpoint below.

**Request body**: empty (or `{}`).

**Responses**:

`202 Accepted`:
```json
{
  "runId": "uuid-v4",
  "kind": "retroactive-sync",
  "startedAt": "2026-05-08T11:43:37Z",
  "streamUrl": "/api/figma-binding/full-sync/uuid-v4/stream"
}
```

`409 Conflict` — another full-sync is already running:
```json
{
  "error": "lock_contended",
  "messageKr": "다른 사용자가 동기화 중입니다",
  "currentRunId": "uuid-v4-of-active-run",
  "currentRunHolder": "<actor>",
  "streamUrl": "/api/figma-binding/full-sync/uuid-v4-of-active-run/stream"
}
```

`404 Not Found` — no active binding:
```json
{ "error": "no_active_binding", "messageKr": "활성화된 Figma 바인딩이 없습니다" }
```

`502 Bad Gateway` — binding is `unreachable`:
```json
{ "error": "binding_unreachable", "messageKr": "Figma 파일에 접근할 수 없습니다" }
```

## GET `/api/figma-binding/full-sync/{run_id}/stream` — SSE progress stream

`Content-Type: text/event-stream`. Streams progress for the run identified by `run_id`. Multiple subscribers MAY connect simultaneously (passive observers). The stream closes when the run reaches a terminal status (`succeeded` | `partially-succeeded` | `cancelled` | `aborted-binding-unreachable`).

**Event types**:

```text
event: run_started
data: { "runId": "...", "storyboardsTotal": 5, "uisTotal": 19, "actor": "<...>", "startedAt": "...", "kind": "retroactive-sync" }

event: page_ok
data: { "runId": "...", "storyboardId": "<entry-command-id>", "displayName": "주문하기", "figmaPageId": "..." }

event: page_failed
data: { "runId": "...", "storyboardId": "<entry-command-id>", "displayName": "주문하기", "lastErrorKr": "Figma plugin이 응답하지 않음" }

event: ui_generated
data: { "runId": "...", "uiId": "...", "displayName": "탈퇴 최종 동의 제출", "sceneGraphNodes": 42, "overwroteExisting": true }

event: ui_pushed
data: { "runId": "...", "uiId": "...", "displayName": "탈퇴 최종 동의 제출", "figmaPageId": "...", "figmaNodeId": "..." }

event: ui_failed
data: { "runId": "...", "uiId": "...", "displayName": "탈퇴 최종 동의 제출", "lastErrorKr": "Figma 가 4초 내 응답하지 않음" }

event: progress
data: { "runId": "...", "storyboardsDone": 3, "storyboardsTotal": 5, "uisDone": 11, "uisTotal": 19, "currentTarget": { "kind": "ui", "displayName": "..." } }

event: run_completed
data: { "runId": "...", "status": "succeeded" | "partially-succeeded", "summary": { ... } }

event: run_cancelled
data: { "runId": "...", "summary": { ... } }

event: run_aborted
data: { "runId": "...", "reason": "binding_unreachable", "messageKr": "동기화 중 Figma 파일이 분리되었습니다", "summary": { ... } }
```

The frontend's existing SSE event-handler for `figma_sync.failed` (added by 016 v1.2) is replaced by `ui_failed` on this stream — they carry the same payload semantics; using a clearer name avoids cross-feature naming overlap.

A late subscriber (joining after `run_started`) MUST receive a synthetic `run_started` and the most recent `progress` event on connect, so the UI can render the current state immediately.

## POST `/api/figma-binding/full-sync/{run_id}/cancel` — cancel a running full-sync

Sets a cancellation flag on the in-memory orchestrator for `run_id`. In-flight UI generations and frame pushes complete naturally; no new dispatches are made.

**Responses**:

`202 Accepted`:
```json
{ "runId": "...", "cancelledAt": "..." }
```

`404 Not Found` — `run_id` is unknown or the run already terminated:
```json
{ "error": "no_such_run_or_terminated" }
```

## GET `/api/figma-binding/sync-runs` — list past run summaries

Drives the History tab's summary rows. Returns at most `limit` (default 20) most-recent runs for the active binding. Includes runs from previous bindings only when `includePreviousBinding=true`.

**Query**:
- `limit` (int, default 20, max 100)
- `includePreviousBinding` (bool, default true) — when true, returns runs whose `bindingFileKey` differs from the current active binding's, marked with `previousBinding=true`.

**Response** `200 OK`:
```json
{
  "currentBindingFileKey": "b7085rfvcgkBeIkljMNc8y",
  "runs": [
    {
      "runId": "...",
      "kind": "retroactive-sync",
      "startedAt": "...",
      "finishedAt": "...",
      "status": "partially-succeeded",
      "summary": {
        "storyboardsTotal": 5,
        "pagesCreated": 2,
        "pagesAlreadyOk": 3,
        "uisTotal": 19,
        "framesPushed": 17,
        "generated": 14,
        "overwrites": 4,
        "failures": 2
      },
      "actor": "<...>",
      "previousBinding": false
    },
    ...
  ]
}
```

## GET `/api/figma-binding/failures` — canonical failure list

Drives the History tab's failure rows AND replaces the ad-hoc failure aggregation the ingestion floating panel currently does on the frontend. Same store as 016 v1.2 (`:UI {figmaSyncStatus:'failed'}`); this endpoint just exposes it with the failure classifier (research D5) applied.

**Query**: none.

**Response** `200 OK`:
```json
{
  "currentBindingFileKey": "b7085rfvcgkBeIkljMNc8y",
  "retryable": [
    {
      "uiId": "...",
      "displayName": "탈퇴 최종 동의 제출",
      "lastErrorKr": "Figma 가 4초 내 응답하지 않음",
      "lastAttemptAt": "...",
      "retryability": "retryable",
      "nonRetryableReason": null,
      "bindingFileKey": "b7085rfvcgkBeIkljMNc8y"
    },
    ...
  ],
  "nonRetryable": [
    {
      "uiId": "...",
      "displayName": "이전 결제 화면",
      "lastErrorKr": "Figma 가 4초 내 응답하지 않음",
      "lastAttemptAt": "...",
      "retryability": "non-retryable",
      "nonRetryableReason": "이전 바인딩",
      "bindingFileKey": "old-file-key"
    },
    ...
  ],
  "inFlight": [
    { "uiId": "...", "displayName": "...", "retryability": "in-flight" }
  ]
}
```

## POST `/api/figma-binding/retry-sync` — retry one or more failures (existing endpoint, semantics extended)

Already shipped by 016 v1.2 (`router.py:166`). This feature **extends its semantics** without changing the wire format:

1. Before dispatching, the in-flight retry deduplication store (research D3) is consulted. If a UI id is already in flight, the second caller awaits the same outcome instead of re-dispatching.
2. UI ids that are non-retryable per the classifier (research D5) are skipped with a per-id `skipped` event in the stream and a Korean reason.

**Request body** (unchanged):
```json
{ "uiIds": ["<id1>", "<id2>"] }   // empty/missing → retry every retryable :UI {figmaSyncStatus:'failed'}
```

**Response** (unchanged 016 v1.2 shape):
```json
{ "runId": "...", "streamUrl": "/api/figma-binding/retry-sync/<run-id>/stream" }
```

The retry stream's events match the full-sync stream's `ui_*` and `run_*` events, with `kind: 'manual-retry'` in `run_started`. Plus one new event:

```text
event: retry_skipped
data: { "uiId": "...", "reason": "non-retryable", "reasonKr": "대상 UI 가 삭제됨" }
```

## SSE event reference summary

| Event | When | Streams it appears in |
|---|---|---|
| `run_started` | Run begins or late-subscriber joins | full-sync, retry-sync |
| `progress` | Periodically (every batch boundary) | full-sync, retry-sync |
| `page_ok` / `page_failed` | After a `CREATE_PAGE` plugin ack | full-sync only (retry doesn't touch pages) |
| `ui_generated` | A sceneGraph was generated for a UI without one | full-sync only |
| `ui_pushed` | After a `CREATE_FRAME_IN_PAGE` plugin ack succeeds | full-sync, retry-sync |
| `ui_failed` | A per-UI step (generate or push) failed | full-sync, retry-sync |
| `retry_skipped` | A UI in the retry batch was non-retryable | retry-sync only |
| `run_completed` / `run_cancelled` / `run_aborted` | Terminal | full-sync, retry-sync |

## Backward compatibility with 016

- 016's `POST /sync-storyboards` and its SSE stream continue to work unchanged. Internally, `service.full_sync` calls the existing `service.sync_storyboards` for the page-creation phase — they share Cypher and side effects.
- 016's `POST /retry-sync` keeps its 016 wire format; the dedupe + classifier additions are server-side behavior that improves the semantics without breaking existing callers.
- 016's binding lifecycle endpoints (`POST /connect`, `DELETE`, `POST /replace`, `GET /history`) are untouched. The History tab in the modal stops rendering `GET /history` directly and instead renders failures + sync-runs; lifecycle events from `GET /history` remain available for any future audit-only view but are not the primary data source for this tab.

## Observability

Every endpoint emits SmartLogger events at phase boundaries (Constitution VII). New categories:

| Category | When |
|---|---|
| `figma_binding.full_sync.requested` | POST /full-sync received |
| `figma_binding.full_sync.run_started` | Lock acquired, orchestrator dispatched |
| `figma_binding.full_sync.lock_contended` | 409 returned |
| `figma_binding.full_sync.page_ok` / `.page_failed` | Per-storyboard outcome |
| `figma_binding.full_sync.ui_generated` / `.ui_pushed` / `.ui_failed` | Per-UI outcome |
| `figma_binding.full_sync.run_completed` / `.run_cancelled` / `.run_aborted` | Terminal |
| `figma_binding.retry.deduped` | Retry no-op'd because already in flight |
| `figma_binding.retry.classified_skip` | Retry skipped because classifier returned non-retryable |
| `figma_binding.history.viewed` | GET /sync-runs or /failures |
