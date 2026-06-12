# API Contract: Proposal Impact Artifact Preview

**Feature**: `040-proposal-impact-preview` | **Date**: 2026-06-11

모든 엔드포인트는 **읽기 전용**(Neo4j read 트랜잭션). 라이브 그래프에 절대 쓰지 않는다(Constitution I). prefix: `/api/proposals/{proposal_id}/preview`. 라우터: `api/features/proposal_lifecycle/routes/proposals_preview.py`.

설계 원칙: 각 preview 엔드포인트는 **대응하는 라이브 read 엔드포인트의 응답 형태를 미러**한다(노드 객체에 옵셔널 `source` 필드만 추가). 따라서 프런트 뷰어 스토어는 fetch base URL 분기 외 파싱 변경이 없다.

---

## 1. 열기 가능성 조회 (라우팅 보조)

```
GET /api/proposals/{proposal_id}/preview/resolve?nodeId={id}&nodeLabel={label}
```
임팩트/diff 항목 하나가 어떤 뷰어로 열리는지 + 열기 가능 여부 판정.

**200 OK**
```json
{
  "renderable": true,
  "viewer": "data",
  "targetNodeId": "PREVIEW:PRO-001:0",
  "bcId": "BC-payment",
  "reason": null
}
```
`renderable=false` 시 `viewer:null`, `reason:"대응 뷰어 없음"` 등. 프런트는 "열기"를 비활성 + 사유 표시(FR-010).

---

## 2. Data (Aggregate) 미리보기 — full-tree 미러

```
GET /api/proposals/{proposal_id}/preview/contexts/{bc_id}/full-tree
```
라이브 `GET /api/contexts/{bc_id}/full-tree` 와 **동일 구조**의 본문 + 노드별 `source`/badge. tacticalDiff 의 Aggregate/VO/Command/Event CREATE·MODIFY 가 오버레이된다.

**200 OK** (발췌 — 라이브 형태 + source)
```json
{
  "boundedContext": { "id": "BC-payment", "name": "결제 컨텍스트" },
  "aggregates": [
    {
      "id": "AGG-refund", "name": "환불 Aggregate", "source": "live+modified",
      "valueObjects": [
        { "name": "RefundReason", "type": "String", "source": "live" },
        { "name": "PartialRefundAmount", "type": "Long", "source": "temporary", "badge": "신규" }
      ],
      "invariants": [
        { "text": "부분 환불 금액은 원래 결제 금액을 초과할 수 없다", "source": "temporary", "badge": "신규" }
      ]
    },
    {
      "id": "PREVIEW:PRO-001:0", "name": "신규 Aggregate", "source": "temporary", "badge": "신규",
      "valueObjects": []
    }
  ],
  "_preview": { "proposalId": "PRO-001", "targetNodeId": "AGG-refund" }
}
```

```
GET /api/proposals/{proposal_id}/preview/graph/expand-with-bc/{node_id}
```
라이브 `GET /api/graph/expand-with-bc/{node_id}` 미러(Design/Data 노드 확장). 동일 `{nodes, relationships, bcContext}` + `source` 태그.

---

## 3. Process (BPMN) 미리보기

```
GET /api/proposals/{proposal_id}/preview/graph/bpmn/process-flows
GET /api/proposals/{proposal_id}/preview/graph/bpmn/process-flow/{start_command_id}
```
라이브 `GET /api/graph/bpmn/process-flow*` 미러. `strategicDiff.processes` 변경을 단계에 오버레이. 라이브 flow 부재 시 `{ renderable:false, reason }`.

---

## 4. Processes (Event Modeling) 미리보기

```
GET /api/proposals/{proposal_id}/preview/graph/event-modeling
```
라이브 `GET /api/graph/event-modeling` 미러. tacticalDiff 에 이벤트모델 항목 있으면 오버레이, 없으면 라이브 슬라이스 read-only(`source:live`).

---

## 5. 미리보기 편집 → 제안 diff 반영 (US4)

> read-only 투영 엔드포인트와 **분리**된 라우트(`proposals_preview_edit.py`). 쓰기 대상은
> **오직 `:Proposal` 노드의 `tacticalDiff` 속성**(제안 자기 데이터)이며, 라이브 디자인 그래프
> (Aggregate/Command/Event 노드)는 절대 변경하지 않는다.

### Inspector 직접 편집

```
PUT /api/proposals/{proposal_id}/preview/aggregate/{node_id}
```
**Body** (변경된 필드만; 부분 갱신)
```json
{ "bcId": "EP-delivery",
  "properties": [ { "name": "trackingNo", "type": "String", "isRequired": false } ],
  "enumerations": [ ... ], "valueObjects": [ ... ], "invariants": [ ... ],
  "name": "배송", "rootEntity": "Delivery" }
```
- node_id 의 tacticalDiff 항목을 deep 표현으로 정규화 덮어쓰기(없으면 라이브 Aggregate → MODIFY 항목 신규).
- **200 OK**: 갱신된 미리보기 full-tree(§2 형태 + source/badge) → 뷰어가 즉시 재렌더.

### Chat 자연어 수정 적용

```
POST /api/proposals/{proposal_id}/preview/chat-confirm
```
**Body**
```json
{ "bcId": "EP-delivery",
  "drafts": [ { "changeId": "c1", "action": "update", "targetType": "Aggregate",
               "targetId": "AGG-delivery", "after": { "properties": [ ... ] } } ],
  "approvedChangeIds": ["c1"] }
```
- 승인된 DraftChange 의 `after`/`updates` 를 대상 Aggregate 항목에 병합 → tacticalDiff 반영.
- **200 OK**: 갱신된 미리보기 full-tree. 프런트는 `robo:preview-updated` 로 뷰어에 적용.
- Chat 의 *제안 생성*(LLM, `/api/chat/modify`)은 기존 인프라 재사용(선택 노드=투영 노드 컨텍스트). 적용(confirm)만 제안 diff 로 라우팅.

---

## 공통 규약

- **읽기 전용 강제**: 모든 핸들러는 read 세션. preview 모듈 내 `CREATE|MERGE|SET|DELETE` Cypher 금지(CI 검사 + pytest).
- **격리**: `proposal_id` 별로 독립 합성 — 동시 다중 제안 미리보기 상호 무간섭(US2-3).
- **오류**:
  - `404` — proposal_id 없음.
  - `200 {renderable:false, reason}` — 대상이 미리보기 표현 불가(끊긴 링크 대신, FR-010).
  - `409`(또는 본문 `source:conflict`) — MODIFY 대상이 라이브에서 삭제됨(엣지 케이스). 깨지지 않고 충돌 표기.
- **관측성**: correlation ID + `preview_projection_start` / `preview_projection_built`(노드 수, source 분포) 로그(Constitution VII).
- **성능**: 단일 BC 슬라이스 + JSON 오버레이, p95 < 2s(SC-004). request/response(SSE 불필요).
- **ACCEPTED/DESTROYED 제안**: 당시 직렬화 스냅샷으로 합성하되 `_preview.contextNote`("이미 반영됨"/"폐기됨") 첨부.

---

## Frontend 이벤트 계약 (앱 레벨, Principle V)

뷰어 스토어를 직접 호출하지 않고 이벤트로 오케스트레이션.

```
window.dispatchEvent(new CustomEvent('robo:open-preview', {
  detail: { proposalId: 'PRO-001', viewer: 'data', targetNodeId: 'AGG-refund', bcId: 'BC-payment' }
}))
```
`App.vue` 수신 → 탭 전환 → 대상 store.`setPreviewSource({ baseUrl:'/api/proposals/PRO-001/preview', proposalId, label:'PRO-001', readOnly:true })` → store.focus(targetNodeId) → `PreviewBanner` 표시.

`clearPreviewSource()` → 라이브 재적재 + 배너 제거.
