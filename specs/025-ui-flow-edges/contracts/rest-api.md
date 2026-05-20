# Phase 1 Contracts: REST API (UI Flow Edges)

**Spec**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md) | **Data Model**: [../data-model.md](../data-model.md) | **Date**: 2026-05-15

All new endpoints live under the existing `/api/graph` router prefix (`api/features/canvas_graph/router.py`) and are mounted from a new module `api/features/canvas_graph/routes/ui_flow.py`. The ingestion contribution surfaces through the existing SSE channel — no new ingestion endpoint is added.

---

## 1. New endpoints

### 1.1 `POST /api/graph/ui-flow/gateway/upsert`

Create or update a `Gateway` from the Inspector. Only `source='manual'` writes are accepted on this path; LLM writes go through the ingestion phase.

**Request body** (`GatewayUpsertRequest`):
```json
{
  "id": null,
  "bounded_context_id": "<bc-uuid>",
  "label": "주문 승인?",
  "kind": "exclusive",
  "source": "manual"
}
```

**Behavior**:
- If `id` is null: compute `key = f"{bc.key}.gateway.{slugify(label)}"`, compute `id = uuid5(NAMESPACE_OID, key)`, MERGE on `key`, set `source='manual'`.
- If `id` is provided: MATCH on `id`; update mutable fields (`label`, `kind`); refresh `updatedAt`. **Renaming a manual gateway does NOT change its `key` or `id`** — the key is frozen at create time to keep references stable. (LLM-created gateways with `source='llm'` follow the same rule.)
- Always set `source='manual'` (the endpoint is for manual edits; FR-021).
- MERGE `(bc)-[:HAS_GATEWAY]->(g)` if missing.

**Response** (200): `GatewayDTO`

**Errors**:
- `400` — `bounded_context_id` not found, or `label` empty, or `kind != 'exclusive'` in v1
- `404` — `id` provided but no matching Gateway

---

### 1.2 `POST /api/graph/ui-flow/gateway/delete`

Delete a `Gateway` with explicit fallback strategy (FR-013).

**Request body** (`GatewayDeleteRequest`):
```json
{
  "id": "<gw-id>",
  "strategy": "stitch"
}
```

**Behavior**:
- `strategy='stitch'`: For each `(a)-[:NEXT_UI]->(g)` and each `(g)-[:NEXT_UI]->(b)`, create a direct `(a)-[:NEXT_UI {condition: out.condition, source:'manual', documentExcerpt:''}]->(b)`. Then DELETE the gateway and its incident edges. The stitched edges are tagged `source='manual'` because the user's intent was to keep the flow but lose the decision.
- `strategy='drop'`: DELETE the gateway and all incident `NEXT_UI` edges. No stitching.
- Both strategies also delete the `HAS_GATEWAY` edge.

**Response** (200):
```json
{
  "deleted_gateway_id": "<gw-id>",
  "deleted_edge_ids": ["<edge-id-1>", "<edge-id-2>"],
  "created_edge_ids": ["<stitched-edge-id-1>"]
}
```

**Errors**:
- `400` — `strategy` not in `{stitch, drop}` (no default)
- `404` — Gateway id not found

---

### 1.3 `POST /api/graph/ui-flow/edge/upsert`

Manually create or update a `NEXT_UI` edge from the canvas (drag-from-handle) or Inspector.

**Request body** (`UIFlowEdgeUpsertRequest`):
```json
{
  "id": null,
  "source_id": "<ui-or-gateway-id>",
  "source_kind": "ui",
  "target_id": "<ui-or-gateway-id>",
  "target_kind": "gateway",
  "condition": "승인됨",
  "source": "manual",
  "document_excerpt": ""
}
```

**Behavior**:
- Validate both endpoints exist and have the declared kind (FR-012).
- If `id` is null: compute deterministic `id = uuid5(NAMESPACE_OID, f"{src.key}->{tgt.key}#{slugify(condition)}")`. MERGE on `id`. Set `source='manual'`.
- If `id` provided: MATCH and update mutable fields (`condition`, `document_excerpt`). `source_id` / `target_id` are **immutable** after create — to move an edge, delete and recreate.
- Always force `source='manual'` (FR-021).

**Response** (200): `UIFlowEdgeDTO`

**Errors**:
- `400` — endpoint not found, kind mismatch, self-edge from `(ui)->(ui)` with empty condition (allowed only on `(ui)->(gateway)->(ui)` self-loops per Edge Cases / form-validation example)
- `404` — `id` provided but no matching edge

---

### 1.4 `POST /api/graph/ui-flow/edge/delete`

Delete a `NEXT_UI` edge. No fallback strategy required (deleting an edge is a local op).

**Request body** (`UIFlowEdgeDeleteRequest`):
```json
{
  "id": "<edge-id>"
}
```

**Response** (200):
```json
{
  "deleted_edge_id": "<edge-id>"
}
```

**Errors**:
- `404` — edge id not found

---

### 1.5 `GET /api/graph/event-modeling` (extension, no breaking change)

The existing endpoint adds two response fields:

```json
{
  // ... existing fields (events, commands, aggregates, uis, ...) ...
  "gateways": [<GatewayDTO>, ...],
  "ui_flow_edges": [<UIFlowEdgeDTO>, ...]
}
```

These default to empty arrays for ingestion runs that pre-date this feature.

---

## 2. Ingestion phase contribution (SSE)

The existing ingestion endpoint `POST /api/ingest/run` (SSE) yields a new phase event after `11_ui_wireframes`:

```json
{
  "phase": "GENERATING_UI_FLOW",
  "message": "UI 흐름 도출 중…",
  "progress": 95,
  "data": {
    "next_ui_edges_created": 14,
    "gateways_created": 3,
    "next_ui_edges_skipped_manual": 2,
    "warnings": [
      {"code": "ui_flow_unresolved_target", "ui_name": "Settings", "near_ui_id": "<ui-id>"},
      {"code": "gateway_kind_downgrade", "gateway_key": "order.gateway.parallel-fanout", "original_kind": "parallel"}
    ]
  }
}
```

The final ingestion summary event (existing structure) gains these counters in its `data.counts`:
- `next_ui_edges_created` (int)
- `gateways_created` (int)
- `ui_flow_warnings` (map: code → count)

No new top-level ingestion endpoint is required (Constitution III: streaming-first via existing SSE).

---

## 3. Validation rules (consolidated)

Applied uniformly at the FastAPI request boundary via Pydantic, and re-checked at the Cypher boundary:

| Field | Rule |
|---|---|
| `label` | non-empty, ≤200 chars, trimmed |
| `kind` | exactly `"exclusive"` in v1; any other value → 400 |
| `condition` | ≤200 chars; empty allowed (but required-non-empty when the edge originates from a Gateway with ≥2 outgoing edges — enforced post-write by `gateway_single_branch` / `gateway_branch_missing_condition` warnings, not by 400) |
| `document_excerpt` | ≤500 chars, truncated server-side if longer |
| `source_id` / `target_id` | must MATCH an existing node of the declared kind; otherwise 400 |
| `source_kind` / `target_kind` | exactly `"ui"` or `"gateway"` |
| `source` | always coerced to `"manual"` on these endpoints; `"llm"` writes go through ingestion only |
| `strategy` (gateway delete) | exactly `"stitch"` or `"drop"`; no default — 400 if missing |

---

## 4. Idempotency & retry semantics

- All upserts are idempotent on the deterministic id (or on `(bc.key, slug(label))` for first-time gateway create). Retry on the same payload produces the same final state and the same response shape.
- Deletes are idempotent in the "happy path" sense: deleting an already-deleted id returns `404` (per existing conventions in `gwt.py`). Clients SHOULD treat `404` on delete as a soft success.
- The ingestion phase is idempotent across re-runs (D2 + D4): re-running on unchanged source text and unchanged graph state produces zero net writes.

---

## 5. Authorization

These endpoints follow the existing `/api/graph` auth posture (currently open within the dev environment). No new auth scopes are introduced. When the global auth model lands, these endpoints inherit it without re-spec.

---

## 6. Observability (Constitution VII)

Every endpoint MUST log under `api.graph.ui_flow.<endpoint>` with at least:
- correlation id (from middleware)
- `bounded_context_id` (when applicable)
- inputs (label / source_id / target_id / strategy)
- outcome (created / updated / deleted / stitched_edges_count)
- duration_ms

The ingestion phase logs under `agent.nodes.ui_flow.*` (per FR-022).
