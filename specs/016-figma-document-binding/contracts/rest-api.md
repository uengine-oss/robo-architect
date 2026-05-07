# REST Contract — `/api/figma-binding`

All routes appear in the auto-generated Swagger at `http://localhost:8000/docs` per the Development Workflow. Requests/responses use Pydantic models in `api/features/figma_binding/schemas.py`. Korean error messages match 009 conventions.

> **Vocabulary**: every reference to "storyboard" in this contract = one row in the `BUSINESS PROCESSES` panel = one entry `:Command`. The mapping unit is the storyboard, not the BoundedContext. See research D1 / D9.

## `GET /api/figma-binding`

Get the current binding (or `404` if none).

**Response 200**:

```json
{
  "id": "singleton",
  "figmaFileKey": "abcd1234",
  "figmaFileName": "Acme Wireframes",
  "connectedBy": "learning@uengine.org",
  "connectedAt": "2026-05-07T10:00:00Z",
  "lastSyncAt": "2026-05-07T10:01:32Z",
  "status": "active",
  "storyboardCounts": { "active": 5, "archived": 0 }
}
```

**Response 404**: `{ "detail": "바인딩된 Figma 다큐먼트가 없습니다." }`

## `POST /api/figma-binding/connect`

Validate a Figma file (read-only REST call) and persist the binding.

**Request**:

```json
{ "figmaFileKey": "abcd1234", "apiToken": "figd_..." }
```

**Response 200**: same shape as `GET /api/figma-binding`. Side effect: `:FigmaBinding {id:"singleton"}` upserted; `:BindingHistoryEvent {eventType:"connect"}` appended. `sync-storyboards` is **not** auto-run — the client calls it next (lets the UI show progress).

**Response 400**: `{ "detail": "Figma 파일에 접근할 수 없습니다: <reason>" }` (binding NOT saved; `:BindingHistoryEvent {eventType:"validate_failure"}` appended).

**Response 409**: `{ "detail": "이미 다른 Figma 다큐먼트가 바인딩되어 있습니다. 먼저 해제하거나 /replace를 사용하세요." }`

## `POST /api/figma-binding/replace`

Atomically disconnect the current binding and connect a new one. Existing storyboard mappings are detached (status → `archived`) and the new file gets fresh mappings on the next `sync-storyboards`.

**Request / Response**: same as `/connect`. History gets `replace` then `connect`.

## `DELETE /api/figma-binding`

Disconnect. Returns `204`. Side effect: status → `disconnected`; `:BindingHistoryEvent {eventType:"disconnect"}` appended. UI scene graphs and previously created Figma frames are left intact (FR-005).

## `POST /api/figma-binding/sync-storyboards`

Ensure each entry-command storyboard has an active `:StoryboardPageMapping`. For storyboards without a mapping, send `CREATE_PAGE` to the plugin and persist the response. Idempotent.

**Response 200**:

```json
{
  "created": [
    { "commandId": "cmd-uuid-1", "figmaPageId": "0:42", "figmaPageName": "상품 등록" }
  ],
  "reused": [
    { "commandId": "cmd-uuid-2", "figmaPageId": "0:13", "figmaPageName": "주문하기" }
  ],
  "renamed": [
    { "commandId": "cmd-uuid-3", "from": "주문 취소", "to": "주문 취소하기" }
  ],
  "archived": [
    { "commandId": "cmd-uuid-9", "reason": "entry_command_removed" }
  ],
  "unreachable": []
}
```

**Response 503**: `{ "detail": "Figma 플러그인이 연결되어 있지 않습니다." }` (no plugin connected for the bound file key; binding status set to `unreachable`).

**Streaming variant** — for projects with > 5 unmapped storyboards, the client may instead call `GET /api/figma-binding/sync-storyboards/stream` (SSE) to receive per-storyboard `created` events. Same outcome, incremental UX.

## `POST /api/figma-binding/generate-frame/{ui_node_id}`

Open a generation session for a UI node. Returns immediately; client subscribes to the SSE stream below. Backend resolves the UI's owning storyboard via `storyboard_resolver.resolve_storyboard_for_ui(ui_node_id)` (D9).

**Request**:

```json
{ "mode": "component" | "openpencil-ai" | "html-to-design",
  "prompt": "선택적 사용자 입력 (openpencil-ai 모드에서만 사용)",
  "onConflict": "ask" | "overwrite" | "import-existing" }
```

`onConflict` is mandatory when the target UI node already has a `sceneGraph`. The frontend modal (FR-012) collects this from the user before calling.

**Response 202**:

```json
{
  "sessionId": "gen-uuid",
  "streamUrl": "/api/figma-binding/generate-frame/gen-uuid/stream",
  "resolvedStoryboard": {
    "commandId": "cmd-uuid-1",
    "figmaPageId": "0:42",
    "figmaPageName": "상품 등록"
  }
}
```

**Response 409 (conflict — existing sceneGraph)**: `{ "detail": "기존 디자인이 있습니다. onConflict를 선택해 주세요.", "currentSource": "html" }`

**Response 409 (orphan UI — no storyboard reaches it)**: `{ "detail": "이 UI는 어떤 스토리보드에도 속하지 않아 Figma 페이지를 결정할 수 없습니다.", "uiNodeId": "ui-42" }` (FR-016 audit event `orphan_ui_blocked` is appended).

**Response 503**: `{ "detail": "Figma 플러그인이 연결되어 있지 않습니다. 일시 해제하면 HTML 모드로 생성할 수 있습니다." }`

## `GET /api/figma-binding/generate-frame/{session_id}/stream`

SSE endpoint. Each event is one phase. Last event is `done` or `error`.

| `event:` | `data:` payload (JSON) |
|----------|------------------------|
| `wireframe.start` | `{ "mode": "component" }` |
| `wireframe.done` | `{ "nodeCount": 23 }` |
| `figma.send` | `{ "figmaPageId": "0:42" }` |
| `figma.ack` | `{ "figmaPageId": "0:42", "figmaNodeId": "12:7" }` |
| `persist.done` | `{ "uiNodeId": "ui-42", "designSource": "figma-bound" }` |
| `done` | `{ "uiNodeId": "ui-42", "figmaFileKey": "...", "figmaPageId": "0:42", "figmaNodeId": "12:7", "figmaStoryboardCommandId": "cmd-uuid-1" }` |
| `error` | `{ "phase": "figma.ack", "message": "..." }` |

## `GET /api/figma-binding/storyboards`

Convenience endpoint for the modal/badge UI: returns the current set of storyboards (entry commands) with their mapping status. Read-only.

```json
[
  { "commandId": "cmd-uuid-1", "displayName": "상품 등록", "stepCount": 12,
    "mapping": { "figmaPageId": "0:42", "figmaPageName": "상품 등록", "status": "active" } },
  { "commandId": "cmd-uuid-2", "displayName": "주문하기", "stepCount": 40,
    "mapping": null }
]
```

## `GET /api/figma-binding/history?limit=N`

Returns the most recent `N` `:BindingHistoryEvent` rows (default 50, max 500), newest first.

## Cross-cutting

- Every endpoint emits at least one `SmartLogger` event with the inbound correlation ID.
- All endpoints require the same auth context as the rest of `/api/*` (no separate auth model for this feature).
- All response bodies are UTF-8 JSON; SSE event lines follow the existing `/api/ingest/stream/...` formatting (`event: <name>\ndata: <json>\n\n`).

---

## v1.2 Additions (Clarification-driven, FR-019 / FR-020)

### `POST /api/figma-binding/retry-sync`

Re-runs the Figma push for `:UI` nodes whose `figmaSyncStatus` is `'failed'`.

**Request body**:

```json
{ "uiIds": ["<id1>", "<id2>"] }      // explicit set
// or
{ "uiIds": null }                      // null/missing → retry every :UI {figmaSyncStatus:'failed'}
```

**Response**: `202 Accepted`

```json
{ "session_id": "<uuid>", "queuedCount": 7 }
```

**SSE stream**: `GET /api/figma-binding/retry-sync/{session_id}/stream` emits the same event types as the bulk-with-binding flow:

```
event: figma_sync.start
data: {"uiId": "<id>", "uiName": "주문하기"}

event: figma_sync.ok
data: {"uiId": "<id>", "figmaPageId": "0:42", "figmaNodeId": "12:7"}

event: figma_sync.failed
data: {"uiId": "<id>", "errorKo": "Figma 플러그인 응답 시간 초과"}

event: done
data: {"ok": <count>, "failed": <count>}
```

### Ingestion stream new events (FR-019b)

The existing `/api/ingest/stream/{session_id}` SSE stream gains three event types when the ingestion runs in `Figma UI` mode AND a `:FigmaBinding` is active. The frontend treats them as additive — they do not replace existing `progress` events.

```
event: figma_sync.start    | data: {"uiId": "<id>", "uiName": "주문 목록"}
event: figma_sync.ok       | data: {"uiId": "<id>", "figmaPageId": "0:42", "figmaNodeId": "12:7"}
event: figma_sync.failed   | data: {"uiId": "<id>", "errorKo": "<message>"}
```

### `:UI` node properties exposed in graph reads

`GET /api/graph/event-modeling` and per-node read endpoints MUST return three additional properties on every `:UI` node when set:

| Property | Type | Meaning |
|---|---|---|
| `figmaSyncStatus` | `"ok" \| "failed" \| null` | null = never attempted; "ok" = Figma frame exists; "failed" = last attempt errored. |
| `figmaSyncLastError` | `string \| null` | Korean error message when `status='failed'`; null when `status='ok'`. |
| `figmaSyncLastAttemptAt` | `datetime \| null` | ISO 8601 timestamp of the last sync attempt (success or failure). |

Existing endpoints add these in the `node.data` payload alongside `figmaFileKey`, `figmaPageId`, `figmaNodeId`. No new endpoint is required.
