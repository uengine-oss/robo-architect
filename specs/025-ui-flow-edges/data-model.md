# Phase 1 Data Model: UI Sticker Flow Edges with Conditional Gateways

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md) | **Date**: 2026-05-15

Two surfaces: (1) Neo4j graph schema (canonical, per Constitution I), and (2) Pydantic models for API requests/responses and the LLM-derivation phase output.

---

## 1. Neo4j Graph Schema

### 1.1 Node: `Gateway` (new)

| Property | Type | Constraint | Notes |
|---|---|---|---|
| `id` | String (UUID v5) | unique, indexed | `uuid5(NAMESPACE_OID, gateway.key)` — deterministic from key |
| `key` | String | unique, indexed | `"<bc.key>.gateway.<slug(label)>"` — natural key for idempotent MERGE |
| `label` | String | required, non-empty | The decision question shown inside the diamond, e.g., "주문 승인?" |
| `kind` | String | required | `"exclusive"` only in v1. Reserved values: `"parallel"`, `"inclusive"` (future) |
| `boundedContextId` | String | required | id of the owning BC; used for HAS_GATEWAY linkage |
| `source` | String | required | `"llm"` or `"manual"` — controls re-ingest preservation per D4 |
| `createdAt` | DateTime | required | `datetime()` on MERGE create |
| `updatedAt` | DateTime | required | `datetime()` on every SET |

**Constraint to add to `docs/cypher/schema/01_constraints.cypher`**:
```cypher
CREATE CONSTRAINT gateway_id_unique IF NOT EXISTS FOR (g:Gateway) REQUIRE g.id IS UNIQUE;
CREATE CONSTRAINT gateway_key_unique IF NOT EXISTS FOR (g:Gateway) REQUIRE g.key IS UNIQUE;
```

**Index to add to `docs/cypher/schema/02_indexes.cypher`**:
```cypher
CREATE INDEX gateway_bc_idx IF NOT EXISTS FOR (g:Gateway) ON (g.boundedContextId);
```

**Doc entry in `docs/cypher/schema/03_node_types.cypher`** (append):
```cypher
// ############################################################
// Gateway (UI-layer decision diamond) — spec 025
// ############################################################
// 설명: UI 흐름에서 분기 조건이 있는 지점. NEXT_UI 관계 위에 놓인다.
// 관계:
//   - BoundedContext-[:HAS_GATEWAY]->Gateway
//   - (UI|Gateway)-[:NEXT_UI]->Gateway-[:NEXT_UI]->(UI|Gateway)
//
// 필수 속성:
//   - id: String (UUID v5, gateway.key 기반)
//   - key: String (`<bc.key>.gateway.<slug(label)>`)
//   - label: String (의사결정 질문)
//   - kind: String ("exclusive" only in v1)
//   - boundedContextId: String
//   - source: String ("llm" | "manual")
// ############################################################

CREATE (g:Gateway {
    id: "00000000-0000-5000-8000-000000000000",
    key: "order.gateway.approval",
    label: "주문 승인?",
    kind: "exclusive",
    boundedContextId: "<bc-uuid>",
    source: "llm",
    createdAt: datetime(),
    updatedAt: datetime()
});
```

---

### 1.2 Relationship: `NEXT_UI` (new)

**Pattern**: `(:UI|:Gateway)-[:NEXT_UI]->(:UI|:Gateway)`

| Property | Type | Constraint | Notes |
|---|---|---|---|
| `id` | String (UUID v5) | required | `uuid5(NAMESPACE_OID, f"{source.key}->{target.key}#{slug(condition)}")` — deterministic |
| `condition` | String | optional (default `""`) | Branch label, e.g., "승인됨" / "반려됨". Required when source is a Gateway; otherwise empty |
| `source` | String | required | `"llm"` or `"manual"` |
| `documentExcerpt` | String | optional (default `""`) | Snippet of source text that motivated this edge (≤ ~500 chars, truncated by the LLM phase) |
| `createdAt` | DateTime | required | |
| `updatedAt` | DateTime | required | |

**Doc entry in `docs/cypher/schema/04_relationships.cypher`** (append):
```cypher
// ############################################################
// NEXT_UI — UI-layer user-journey edge (spec 025)
// ############################################################
// 방향: (UI|Gateway) → (UI|Gateway)
// 의미: 사용자 여정 관점에서 "이 화면(또는 분기) 다음에 저 화면(또는 분기)으로 진행"
//
// 속성:
//   - id: String (UUID v5, 결정적)
//   - condition: String (Gateway 출구일 때 분기 라벨; 그 외 "")
//   - source: String ("llm" | "manual")
//   - documentExcerpt: String (원본 문서 인용; ≤500자)
// ############################################################

MATCH (a:UI {id: "<ui-a-id>"})
MATCH (b:UI {id: "<ui-b-id>"})
MERGE (a)-[r:NEXT_UI {id: "<deterministic-uuid5>"}]->(b)
ON CREATE SET r.createdAt = datetime()
SET r.condition = "",
    r.source = "llm",
    r.documentExcerpt = "원본 문서 인용",
    r.updatedAt = datetime();
```

**Note**: `MERGE` is keyed on `r.id` (deterministic per D2) so re-ingest with the same (source, target, condition) is idempotent.

---

### 1.3 Relationship: `HAS_GATEWAY` (new)

**Pattern**: `(:BoundedContext)-[:HAS_GATEWAY]->(:Gateway)`

| Property | Type | Notes |
|---|---|---|
| `createdAt` | DateTime | |

**Doc entry in `04_relationships.cypher`** (append):
```cypher
// ############################################################
// HAS_GATEWAY — BC 소유권 (spec 025)
// ############################################################
// 방향: BoundedContext → Gateway
// 의미: 해당 Gateway는 이 BC의 UI 흐름에 속함 (cross-BC NEXT_UI 통과는 허용)
// ############################################################

MATCH (bc:BoundedContext {id: "<bc-id>"})
MATCH (g:Gateway {id: "<gw-id>"})
MERGE (bc)-[:HAS_GATEWAY]->(g);
```

---

### 1.4 Schema invariants

These MUST hold after every ingestion run and after every API mutation:

1. **No dangling endpoints**: every `NEXT_UI` edge has both endpoints existing as `UI` or `Gateway` nodes. Enforced by `MATCH` (not `MERGE`) on endpoints in `_NEXT_UI_BULK_CYPHER`.
2. **Gateway containment**: every `Gateway` has exactly one `HAS_GATEWAY` incoming edge from a `BoundedContext`. Enforced by writing both in the same transaction.
3. **Gateway non-orphan**: every `Gateway` has ≥1 incoming and ≥1 outgoing `NEXT_UI`. Singletons emit `gateway_single_branch` warning per edge case spec.
4. **Source tag domain**: `source ∈ {"llm", "manual"}` on both nodes and edges. Validated in Pydantic and at the Cypher boundary.

A periodic graph-integrity check (`api/features/canvas_graph/routes/graph_maintenance.py`) MUST be extended to verify invariants 1 and 2 and report violations.

---

## 2. Pydantic Models

### 2.1 LLM structured output (`api/features/ingestion/event_storming/structured_outputs.py`)

```python
from pydantic import BaseModel, Field
from typing import Literal


class UIFlowGatewayItem(BaseModel):
    """LLM-emitted gateway specification before id resolution."""
    label: str = Field(..., min_length=1, description="Decision question, e.g., '주문 승인?'")
    kind: Literal["exclusive", "parallel", "inclusive"] = "exclusive"
    bounded_context_name: str = Field(..., description="BC name to resolve to id")


class UIFlowEdgeItem(BaseModel):
    """LLM-emitted NEXT_UI edge before id resolution."""
    source_name: str = Field(..., description="UI displayName or Gateway label")
    source_kind: Literal["ui", "gateway"] = "ui"
    target_name: str
    target_kind: Literal["ui", "gateway"] = "ui"
    condition: str = ""
    document_excerpt: str = ""


class UIFlowDerivation(BaseModel):
    """Top-level LLM output for the new ingestion phase."""
    gateways: list[UIFlowGatewayItem] = Field(default_factory=list)
    edges: list[UIFlowEdgeItem] = Field(default_factory=list)
    unresolved: list[str] = Field(
        default_factory=list,
        description="Screen names referenced in source text that couldn't be bound to a UI node",
    )
```

### 2.2 API request/response models (`api/features/canvas_graph/routes/ui_flow.py`)

```python
from pydantic import BaseModel, Field
from typing import Literal


class GatewayUpsertRequest(BaseModel):
    id: str | None = None          # null on create; required on update
    bounded_context_id: str
    label: str = Field(..., min_length=1)
    kind: Literal["exclusive"] = "exclusive"   # v1 only
    source: Literal["manual"] = "manual"        # only manual upserts come through this endpoint


class GatewayDeleteRequest(BaseModel):
    id: str
    strategy: Literal["stitch", "drop"]
    # stitch: merge incoming-edges × outgoing-edges into direct (UI)->(UI) edges
    # drop: remove gateway + all incident edges


class UIFlowEdgeUpsertRequest(BaseModel):
    id: str | None = None
    source_id: str                  # UI.id or Gateway.id
    source_kind: Literal["ui", "gateway"]
    target_id: str
    target_kind: Literal["ui", "gateway"]
    condition: str = ""
    source: Literal["manual"] = "manual"
    document_excerpt: str = ""


class UIFlowEdgeDeleteRequest(BaseModel):
    id: str


class GatewayDTO(BaseModel):
    id: str
    key: str
    label: str
    kind: str
    bounded_context_id: str
    source: str
    created_at: str
    updated_at: str


class UIFlowEdgeDTO(BaseModel):
    id: str
    source_id: str
    source_kind: Literal["ui", "gateway"]
    target_id: str
    target_kind: Literal["ui", "gateway"]
    condition: str
    source: str
    document_excerpt: str
    created_at: str
    updated_at: str
```

### 2.3 Generation warnings (`api/features/ingestion/ingestion_contracts.py` — extend)

The existing `GenerationWarning` shape is reused. New codes:

| Code | Trigger |
|---|---|
| `ui_flow_unclear` | Source document contains no detectable screen flow |
| `ui_flow_unresolved_target` | LLM referenced a screen name that doesn't bind to any UI node |
| `gateway_single_branch` | Gateway has only one outgoing NEXT_UI edge (degenerate) |
| `gateway_kind_downgrade` | LLM emitted `parallel`/`inclusive`; downgraded to `exclusive` per D6 |

### 2.4 Event-modeling read model (`/api/graph/event-modeling` extension)

The existing `event_modeling` response gets two new top-level lists:

```python
class EventModelingResponse(BaseModel):
    # ... existing fields (events, commands, aggregates, uis, etc.) ...
    gateways: list[GatewayDTO] = Field(default_factory=list)
    ui_flow_edges: list[UIFlowEdgeDTO] = Field(default_factory=list)
```

Backward compatibility: clients that ignore unknown fields (the existing frontend store) continue to work; the frontend store is updated in the same PR to consume the new fields.

---

## 3. State transitions

A `Gateway` and a `NEXT_UI` edge each go through these lifecycle states:

```
        ┌──────────────┐ LLM phase emits
        │  (does not   │ ──────────────▶  source='llm'
        │   exist yet) │
        └──────────────┘                       │
                                               │ user edits via Inspector
                                               ▼
                                       source='manual'   (sticky)
                                               │
                                               │ re-ingest LLM phase
                                               ▼
                                       (unchanged — phase honors manual flag)
```

Once an edge or gateway is marked `manual`, the only way back to `llm` is an explicit user action (delete then let LLM re-create on next ingest). Re-ingestion never demotes `manual` → `llm`.
