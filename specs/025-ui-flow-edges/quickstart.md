# Phase 1 Quickstart: UI Sticker Flow Edges with Conditional Gateways

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-05-15

Six manual smoke scenarios that exercise the feature end-to-end. Each scenario lists prerequisites, exact steps, and the expected observable outcome. These map 1:1 to the success criteria (SC-001..SC-007).

---

## Prerequisites (one-time)

1. `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000` running.
2. Frontend dev server up (`bun run dev` or `vite`).
3. Neo4j running and reachable from `.env`.
4. The new Cypher schema entries from `data-model.md §1` have been applied (`docs/cypher/schema/01_constraints.cypher`, `02_indexes.cypher`).
5. `LLM_PROVIDER` + `LLM_MODEL` + the appropriate `*_API_KEY` set in `.env`.

---

## S1 — Linear flow auto-derivation (covers SC-001 + AS-1 of US-1)

**Goal**: Verify the LLM phase emits `NEXT_UI` edges for a linear 3-screen flow.

**Setup**: Prepare a source document with text like:
> "사용자는 먼저 로그인 화면에서 인증한다. 인증이 성공하면 대시보드 화면으로 이동한다. 대시보드에서 상품 카드를 클릭하면 상세 화면을 본다."

**Steps**:
1. POST the document to `/api/ingest/run` (multipart, with `mode=requirements-only` or whichever existing mode is appropriate).
2. Watch the SSE stream — expect a `GENERATING_UI_FLOW` phase event with `next_ui_edges_created: 2`.
3. Open the event-modeling canvas in the browser for the ingested session.

**Expected**:
- 3 UI stickers (Login, Dashboard, Detail).
- 2 dashed purple arrows: `Login → Dashboard`, `Dashboard → Detail`.
- Neo4j query `MATCH (a:UI)-[r:NEXT_UI]->(b:UI) RETURN a.displayName, b.displayName, r.source` returns 2 rows, all with `r.source = 'llm'`.

---

## S2 — Branching flow with exclusive gateway (covers AS-2 of US-1 + Story 2)

**Goal**: Verify the LLM emits a `Gateway` diamond and labelled outgoing edges.

**Setup**: Source document text:
> "주문 검토 화면에서 관리자는 주문을 승인하거나 반려할 수 있다. 승인하면 주문 완료 화면으로, 반려하면 반려 사유 입력 화면으로 이동한다."

**Steps**:
1. POST to `/api/ingest/run`.
2. Open the canvas.

**Expected**:
- One yellow diamond between `주문 검토` and `주문 완료` / `반려 사유 입력`.
- The diamond shows the label "주문 승인?" (or similar — LLM-phrased).
- Two outgoing edges from the diamond with condition labels "승인됨" and "반려됨".
- Neo4j: `MATCH (g:Gateway) RETURN g.label, g.kind` returns one row, kind `exclusive`.
- `MATCH (g:Gateway)-[r:NEXT_UI]->() RETURN r.condition` returns two rows, both non-empty.

---

## S3 — Re-ingest idempotency (covers SC-003 + AS-4 of US-1)

**Goal**: Re-running ingestion on the same document does NOT duplicate edges/gateways.

**Steps**:
1. Note the `r.id` values from S1 and S2's `NEXT_UI` edges and Gateway nodes.
2. Re-run `/api/ingest/run` with the exact same documents.
3. Re-query Neo4j for the same edges.

**Expected**:
- Same edge `id` values; same Gateway `id` and `key`. No new nodes/edges.
- `updatedAt` MAY refresh; `createdAt` MUST be unchanged.
- The SSE summary shows `next_ui_edges_created: 0` (or the delta count, not the total).

---

## S4 — Manual edit survives re-ingest (covers SC-004 + Story 3 AS-2/AS-4)

**Goal**: Verify `source='manual'` edges and gateways are preserved across re-ingest.

**Steps**:
1. From the S1 state, in the Inspector for the edge `Dashboard → Detail`, change the condition to `"카드 클릭"` and save.
2. Verify Neo4j: `MATCH ()-[r:NEXT_UI]->() WHERE r.condition = '카드 클릭' RETURN r.source` returns `"manual"`.
3. Manually draw a new edge from `Login → Detail` (drag-from-handle on canvas), with condition `"바로가기"`.
4. Re-run `/api/ingest/run` with the same documents.
5. Re-query the graph.

**Expected**:
- The edited `Dashboard → Detail` edge retains `condition = '카드 클릭'` and `source = 'manual'`.
- The new manual edge `Login → Detail` still exists with `source = 'manual'`.
- No LLM-generated edges were added that conflict with the manual ones.
- The LLM phase emits zero new edges or only adds edges that aren't already covered by manual edges.

---

## S5 — Ambiguous source emits warning (covers AS-3 of US-1 + Edge Case "no signal")

**Goal**: A document with no detectable flow yields zero edges and one warning.

**Setup**: Document = a glossary or schema-only spec with no narrative about screens, e.g.,
> "본 시스템은 Order, Customer, Product 세 가지 엔터티를 관리한다. 각 엔터티는 id, name, createdAt 속성을 갖는다."

**Steps**:
1. POST to `/api/ingest/run`.
2. Inspect the SSE stream.

**Expected**:
- `GENERATING_UI_FLOW` phase event yields `next_ui_edges_created: 0` and `warnings: [{code: 'ui_flow_unclear', ...}]`.
- Ingestion does NOT fail; the run completes.
- Canvas opens with no `NEXT_UI` arrows.

---

## S6 — Gateway delete with stitch strategy (covers FR-013 + Story 3 AS-3)

**Goal**: Deleting a gateway with `strategy=stitch` preserves the flow as direct UI→UI edges.

**Steps**:
1. From the S2 state, in the Inspector select the `주문 승인?` gateway.
2. Click Delete → choose "Keep flow (stitch)".
3. Confirm and verify the canvas updates.

**Expected**:
- The diamond is gone.
- Two new direct edges exist: `주문 검토 → 주문 완료` (condition `"승인됨"`) and `주문 검토 → 반려 사유 입력` (condition `"반려됨"`). Both `source='manual'`.
- Neo4j: `MATCH (g:Gateway {label: '주문 승인?'}) RETURN g` returns no rows.
- API response body lists the deleted gateway id, the deleted edge ids, and the two newly created stitched edge ids.

**Alternate variant (drop)**:
- Repeat with `strategy='drop'` instead: the gateway and all 3 incident edges disappear; no replacement edges are created.

---

## Tear-down

```cypher
// Clean test data between scenarios
MATCH (g:Gateway) DETACH DELETE g;
MATCH ()-[r:NEXT_UI]->() DELETE r;
```

(Use only against a dev Neo4j; not for any shared environment.)
