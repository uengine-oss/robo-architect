# Data Model — Figma Document Binding

Authoritative storage is Neo4j (Constitution I). Schema additions go in `docs/cypher/schema/03_node_types.cypher` (labels) and `docs/cypher/schema/04_relationships.cypher` (relationship types) before any code that reads/writes them ships.

## Domain Vocabulary Note

A **storyboard** in this feature = one row of the left-panel `BUSINESS PROCESSES` list = the vertical slice rooted at one user-initiated entry `:Command` (a Command not invoked by any Policy). The storyboard's **stable identifier is the entry Command's `id`**. There is intentionally no `:Storyboard` Neo4j label — see research D1 / D9.

## Nodes

### `:FigmaBinding` (singleton)

Represents the active link between the Event Modeling project and one Figma document.

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `id` | string | yes | Always `"singleton"` (with UNIQUE constraint). Future multi-project support reuses this slot per-project ID. |
| `figmaFileKey` | string | yes | The Figma file key. Validated at connect time via Figma REST `GET /v1/files/{file_key}`. |
| `figmaFileName` | string | yes | Display name fetched at connect time. Read-only after that; refreshable on user demand. |
| `connectedBy` | string | yes | Identifier of the user who connected (email or session ID — match what 009 already records on UI nodes for `updatedAt` provenance). |
| `connectedAt` | ISO-8601 string | yes | UTC timestamp. |
| `lastSyncAt` | ISO-8601 string | no | Updated whenever sync-storyboards or generate-frame completes. |
| `status` | enum string | yes | `active` \| `unreachable` \| `disconnected`. `disconnected` rows are kept for history but excluded from `GET /api/figma-binding`. |

Constraint:

```cypher
CREATE CONSTRAINT figma_binding_singleton IF NOT EXISTS
FOR (b:FigmaBinding) REQUIRE b.id IS UNIQUE;
```

### `:StoryboardPageMapping`

Per-storyboard mapping to a Figma page. One row per entry-command × active binding.

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `id` | string (UUID) | yes | UNIQUE constraint. The stable mapping ID referenced by FR-007. Survives Command and Figma-page renames. |
| `commandId` | string | yes | The entry Command's `id`. UNIQUE per active binding. |
| `figmaPageId` | string | yes | The Figma page ID returned by the plugin's `CREATE_PAGE` ack. |
| `figmaPageName` | string | yes | Cached for display; not authoritative. |
| `status` | enum string | yes | `active` \| `archived`. `archived` is set when the entry Command no longer exists locally (e.g. removed, or now policy-invoked); the Figma page itself is not deleted. |
| `lastRenameAt` | ISO-8601 string | no | Bumped when either side renames. |

Constraints:

```cypher
CREATE CONSTRAINT storyboard_page_mapping_id_unique IF NOT EXISTS
FOR (m:StoryboardPageMapping) REQUIRE m.id IS UNIQUE;

CREATE CONSTRAINT storyboard_page_mapping_command_unique IF NOT EXISTS
FOR (m:StoryboardPageMapping) REQUIRE m.commandId IS UNIQUE;
```

### `:BindingHistoryEvent`

Append-only audit row. Created by `service.py` for every connect, validate-failure, sync, page-rename, page-archive, disconnect, and replace.

| Property | Type | Required | Notes |
|----------|------|----------|-------|
| `id` | string (UUID) | yes | |
| `eventType` | string | yes | One of: `connect`, `validate_failure`, `sync_storyboards`, `page_renamed`, `page_archived`, `disconnect`, `replace`, `generate_routed`, `orphan_ui_blocked`. |
| `figmaFileKey` | string | no | The file key in scope at event time (helps for `replace` audit). |
| `actor` | string | yes | User identifier. |
| `at` | ISO-8601 string | yes | |
| `payload` | JSON string | no | Free-form: error messages, before/after names, generation IDs, the resolver's chosen entry command for a generation, etc. |

History is unconstrained beyond ID uniqueness; it is read by `GET /api/figma-binding/history?limit=N`.

## Relationships

| Relationship | From | To | Cardinality | Created When |
|--------------|------|----|-------------|--------------|
| `:MAPS_STORYBOARD` | `:FigmaBinding` | `:StoryboardPageMapping` | 1 → many | After `CREATE_PAGE` plugin ack. Removed only by `replace` (mappings re-created against the new file). |
| `:MAPS` | `:StoryboardPageMapping` | `:Command` | 1 → 1 | Together with `:MAPS_STORYBOARD`. The target Command is the entry command. |
| `:LOGGED` | `:BindingHistoryEvent` | `:FigmaBinding` | many → 1 | Every audit event. |

No `(Command)-[:OWNS_UI_FOR_STORYBOARD]->(UI)` relationship is introduced — UI ownership is computed via the resolver in `storyboard_resolver.py` (D9).

## Updates to Existing Nodes

### `:UI` node — design-source provenance

Three new properties (the existing `figmaFileKey` / `figmaNodeId` from 009 are reused, not renamed):

| Property | Type | Notes |
|----------|------|-------|
| `designSource` | enum string | `html` \| `figma-bound` \| `imported`. Defaults to absent (treated as `html`) for back-compat with 009-era UI nodes. |
| `figmaPageId` | string | Set when `designSource = figma-bound` or `imported`. The Figma page the bound frame lives on. |
| `figmaBindingId` | string | The `:FigmaBinding.id` in effect when this design was generated. Lets the UI flag references "from previous binding" if it changes. |
| `figmaStoryboardCommandId` | string | The entry Command ID the resolver selected at generate time. Audit-only; not used for routing on subsequent generations (those re-run the resolver). |

`figmaFileKey` and `figmaNodeId` are populated as today (per 009's `figma_sync.py` SET clauses) so existing pull/push continues to work without modification.

## Storyboard Resolver (Cypher sketch)

Implemented in `api/features/figma_binding/storyboard_resolver.py`. Two operations:

### `list_entry_commands()`

```cypher
MATCH (c:Command)
WHERE NOT EXISTS { (:Policy)-[:INVOKES]->(c) }
RETURN c.id AS id, c.displayName AS displayName, c.name AS name
ORDER BY coalesce(c.displayName, c.name), c.id
```

### `resolve_storyboard_for_ui(uiNodeId)`

Conceptually: BFS from each entry command (Command→EMITS→Event→TRIGGERS→Policy→INVOKES→Command...→ATTACHED_TO/HAS_UI→UI), collecting reachable UI ids; pick the first entry command (canonical ordering above) whose reachable set contains `uiNodeId`. Implementation uses Cypher variable-length paths bounded by a sane depth limit (e.g. 30 hops) to avoid runaway traversal on pathological models.

```cypher
// pseudo (full impl in storyboard_resolver.py):
MATCH (c:Command)
WHERE NOT EXISTS { (:Policy)-[:INVOKES]->(c) }
WITH c
ORDER BY coalesce(c.displayName, c.name), c.id
MATCH p = (c)-[:EMITS|TRIGGERS|INVOKES|ATTACHED_TO|HAS_UI*1..30]-(u:UI {id: $uiNodeId})
RETURN c.id AS commandId LIMIT 1
```

Returns `None` if no entry command reaches the UI (D10 → 409 with Korean message).

## State Transitions

### `FigmaBinding.status`

```
        connect (validation OK)
   ──────────────────────────► active ─────► disconnected
                                  │              ▲
            unreachable Figma     │              │
                  ◄───────────────┘              │
   unreachable                                    │
        │                                         │
        └─────► (recovers on next successful op) ─┘
```

- `active`: normal state.
- `unreachable`: set when a sync or generate operation hits a transport failure to the plugin or to Figma REST validation. Read-only continues; new generations are blocked. Recovery is automatic on the next successful operation.
- `disconnected`: set explicitly by the user via `DELETE /api/figma-binding`. Generations on new nodes fall back to HTML mode (FR-005, SC-005).

### `StoryboardPageMapping.status`

```
   create page (CREATE_PAGE ack)
   ──────────────────────────► active ─────► archived
                                  │             ▲
                                  │             │ (entry command removed
                                  │             │  or became policy-invoked)
                                  └─────────────┘
```

`archived` is terminal for the mapping but not for the Figma page (page is left untouched in Figma).

## Plugin Message Schemas (data shape only — wire format in contracts)

### `CREATE_PAGE`

Backend → plugin:

```json
{ "type": "CREATE_PAGE", "requestId": "uuid", "name": "상품 등록" }
```

Plugin → backend:

```json
{ "type": "CREATE_PAGE_ACK", "requestId": "uuid", "ok": true,
  "figmaPageId": "0:42", "figmaPageName": "상품 등록" }
```

### `CREATE_FRAME_IN_PAGE`

Backend → plugin:

```json
{ "type": "CREATE_FRAME_IN_PAGE", "requestId": "uuid",
  "figmaPageId": "0:42", "frameName": "상품 상세",
  "sceneGraph": { /* same shape as 009's SceneGraph */ } }
```

Plugin → backend:

```json
{ "type": "CREATE_FRAME_IN_PAGE_ACK", "requestId": "uuid", "ok": true,
  "figmaPageId": "0:42", "figmaNodeId": "12:7", "figmaFrameName": "상품 상세" }
```

Errors: `{ "ok": false, "error": "<korean message>" }`.

---

## v1.2 Additions (Clarification-driven, FR-019b / FR-020)

### `:UI` node — new properties for Figma sync status

These three properties are written by the bulk-with-binding flow (`figma_binding.bulk_sync`) and read by both the Inspector Design tab badge (FR-020) and the ingestion floating panel summary (FR-020). They are independent from the existing `figmaFileKey` / `figmaPageId` / `figmaNodeId` triple, which remains the *what is the linked Figma frame* identity (set once on success).

| Property | Type | Cardinality | Meaning |
|---|---|---|---|
| `figmaSyncStatus` | string | 0..1 | Either `'ok'` (last sync succeeded), `'failed'` (last sync failed), or absent (never attempted). |
| `figmaSyncLastError` | string | 0..1 | Korean-language error message from the last failed attempt. Cleared when `figmaSyncStatus` becomes `'ok'`. |
| `figmaSyncLastAttemptAt` | datetime | 0..1 | ISO 8601 timestamp of the last sync attempt (success or failure). Used by retry UX to sort by recency. |

**No new constraints.** The properties are queryable but not unique; no index needed at v1.2 scale (≤ 50 failed UIs in a typical project).

**Lifecycle**:

```
(no Figma sync ever)        → all three null
post bulk_sync success      → figmaSyncStatus='ok',     figmaSyncLastError=null, figmaSyncLastAttemptAt=<ts>
post bulk_sync failure      → figmaSyncStatus='failed', figmaSyncLastError=<ko>, figmaSyncLastAttemptAt=<ts>
post retry-sync success     → figmaSyncStatus='ok',     figmaSyncLastError=null, figmaSyncLastAttemptAt=<ts>
post retry-sync failure     → figmaSyncStatus='failed', figmaSyncLastError=<ko>, figmaSyncLastAttemptAt=<ts>
post replace_binding        → all three nulled (mappings against a stale file are meaningless)
```

### Observability event names (additive)

Append to the FR-014 event enumeration:

- `figma_binding.bulk_sync.start { sessionId, batchSize }`
- `figma_binding.bulk_sync.ok { sessionId, uiId, figmaPageId, figmaNodeId }`
- `figma_binding.bulk_sync.failed { sessionId, uiId, errorKo }`
- `figma_binding.retry.requested { sessionId, uiIds, count }`
- `figma_binding.retry.ok { sessionId, uiId }`
- `figma_binding.retry.failed { sessionId, uiId, errorKo }`
- `frontend.fonts.preload_failed { url, error }` (frontend-emitted, structured)
