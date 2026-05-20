# Plugin Protocol — Additions for Figma Document Binding

Two new request/response message pairs extend the existing Figma plugin WebSocket transport (`api/features/ingestion/figma_plugin_ws.py` ↔ `figma-plugin/src/plugin.ts`). The transport itself (REGISTER, polling fallback, queue) is unchanged.

> **Naming source**: `CREATE_PAGE.name` = the entry Command's `displayName || name` (one row in the `BUSINESS PROCESSES` panel = one entry Command = one storyboard = one Figma page). See data-model.md and research D1/D5.

## Versioning

The plugin's existing `REGISTER` message is extended to declare its supported message set. Backend rejects (with a clear "plugin update required" error) any operation whose required message is missing.

```jsonc
// Plugin → Backend (existing REGISTER, extended)
{
  "type": "REGISTER",
  "fileKey": "abcd1234",
  "supportedMessages": [
    "UPDATE_NODES", "UPDATE_TEXT", "SYNC_FRAME",     // 009-era
    "CREATE_PAGE", "CREATE_FRAME_IN_PAGE"            // 016 additions
  ]
}
```

## `CREATE_PAGE`

Create a new page in the bound Figma document.

**Backend → Plugin**

```json
{
  "type": "CREATE_PAGE",
  "requestId": "uuid",
  "name": "상품 등록"
}
```

**Plugin → Backend (success)**

```json
{
  "type": "CREATE_PAGE_ACK",
  "requestId": "uuid",
  "ok": true,
  "figmaPageId": "0:42",
  "figmaPageName": "상품 등록"
}
```

**Plugin → Backend (failure)**

```json
{
  "type": "CREATE_PAGE_ACK",
  "requestId": "uuid",
  "ok": false,
  "error": "페이지 이름이 비어 있습니다."
}
```

**Plugin behavior**:
1. Call `figma.createPage()`.
2. Set `page.name = msg.name`.
3. Reply with the newly created `page.id`.
4. Do not reorder existing pages; the new page is appended.

## `CREATE_FRAME_IN_PAGE`

Create a new frame inside a specific page from a sceneGraph payload.

**Backend → Plugin**

```json
{
  "type": "CREATE_FRAME_IN_PAGE",
  "requestId": "uuid",
  "figmaPageId": "0:42",
  "frameName": "상품 상세",
  "sceneGraph": { "nodes": { /* ... */ }, "rootId": "FRAME-1", "images": {} }
}
```

The `sceneGraph` shape is the same canonical SceneGraph used in 009 (DOCUMENT → CANVAS → FRAME → ...).

**Plugin → Backend (success)**

```json
{
  "type": "CREATE_FRAME_IN_PAGE_ACK",
  "requestId": "uuid",
  "ok": true,
  "figmaPageId": "0:42",
  "figmaNodeId": "12:7",
  "figmaFrameName": "상품 상세"
}
```

**Plugin → Backend (failure)**

```json
{
  "type": "CREATE_FRAME_IN_PAGE_ACK",
  "requestId": "uuid",
  "ok": false,
  "error": "페이지 0:42 를 찾을 수 없습니다."
}
```

**Plugin behavior**:
1. Locate the target page by `figmaPageId`. If not found → fail with the Korean message above.
2. Walk the `sceneGraph.nodes` tree starting at `rootId`, creating Figma nodes via `figma.createFrame()` / `figma.createText()` / etc., as the plugin's existing `SYNC_FRAME` handler already does for 009.
3. Append the rendered top-level frame as a child of the target page.
4. Reply with the new top-level frame's `id`.

## Routing rules (backend)

- `figma_plugin_ws.py` adds two handlers, registered in the existing handler dispatch dict (no new module needed).
- All correlation IDs follow the existing convention: backend generates the `requestId`, the plugin echoes it.
- Timeout: 15 s for `CREATE_PAGE`, 30 s for `CREATE_FRAME_IN_PAGE` (the latter is sceneGraph-bound). On timeout, the in-flight request resolves with `{ ok: false, error: "Figma 응답 시간이 초과되었습니다." }` and the binding's `lastSyncAt` is *not* updated.
- Polling fallback (`/api/figma-plugin/poll`) is preserved: when no plugin is connected, `CREATE_PAGE` and `CREATE_FRAME_IN_PAGE` are *not* queued — instead the originating REST endpoint returns `503` immediately. Rationale: these are interactive operations whose results the user is waiting on; queuing them silently would surprise the user.
