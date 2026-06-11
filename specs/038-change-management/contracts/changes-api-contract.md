# API Contract: Requirement Change Management (038)

**Prefix:** `/api/requirement-changes`
**Feature module:** `api/features/requirement_changes/`

---

## 1. Change CRUD

### POST `/api/requirement-changes/`
Change 생성. `DRAFT` 상태로 시작.

**Request body:** `CreateChangeRequest`
```json
{
  "title": "주문 취소 정책 변경",
  "originalPrompt": "반품 기간을 7일에서 14일로 연장하는 요건이 추가됐습니다",
  "sourceType": "PROMPT",
  "directAffectedNodeIds": null
}
```

**Response:** `ChangeResponse` (HTTP 201)
```json
{
  "id": "CHG-003",
  "title": "주문 취소 정책 변경",
  "originalPrompt": "...",
  "author": "user@example.com",
  "createdAt": "2026-06-02T10:00:00Z",
  "status": "DRAFT",
  "statusHistory": [],
  "sourceType": "PROMPT",
  "changeSetId": null,
  "effects": []
}
```

**Side effects:**
- `sourceType=PROMPT` → 비동기로 `robo-change-specify` 스킬 호출 → EFFECT 관계 생성 (백그라운드)
- `sourceType=DIRECT_EDIT` + `directAffectedNodeIds` → 해당 노드에 EFFECT 즉시 생성 (impactLevel=HIGH)

---

### GET `/api/requirement-changes/`
Change 목록 반환. 생성일시 역순.

**Query params:**
- `status`: 필터 (선택, DRAFT|SUBMITTED|APPROVED 등)
- `limit`: 기본 50

**Response:** `List[ChangeResponse]`

---

### GET `/api/requirement-changes/{id}`
Change 상세 조회. EFFECT 목록 포함.

**Response:** `ChangeResponse` (effects 포함)

---

### DELETE `/api/requirement-changes/{id}`
Change 삭제. EFFECT 관계도 함께 삭제 (`DETACH DELETE`).

**조건:** `IMPLEMENTED` 상태이면 HTTP 409 반환.

**Response:** HTTP 204

---

## 2. Change 상태 전이

### POST `/api/requirement-changes/{id}/submit`
DRAFT → SUBMITTED. 작성자 본인만 가능.

**Request body:** 없음

**Response:** `ChangeResponse`

**Error:** HTTP 400 if status != DRAFT | HTTP 403 if not author

---

### POST `/api/requirement-changes/{id}/approve`
SUBMITTED → APPROVED. 작성자 본인은 불가(자기 승인 방지).

**Request body:**
```json
{ "comment": "확인 후 승인합니다" }
```

**Response:** `ChangeResponse`

**Error:** HTTP 400 if status != SUBMITTED | HTTP 403 if author == current user

---

### POST `/api/requirement-changes/{id}/reject`
SUBMITTED → REJECTED. 작성자 본인은 불가.

**Request body:**
```json
{ "comment": "추가 검토 필요" }
```

**Response:** `ChangeResponse`

---

## 3. 영향도 분석 (EFFECT)

### GET `/api/requirement-changes/{id}/impact`
EFFECT 관계 및 영향받는 노드 목록 반환.

**Response:**
```json
{
  "changeId": "CHG-003",
  "effects": [
    {
      "nodeId": "US-012",
      "nodeLabel": "UserStory",
      "nodeTitle": "주문 취소 처리",
      "reason": "반품 기간 변경으로 인수조건 수정 필요",
      "impactLevel": "HIGH"
    }
  ]
}
```

---

### POST `/api/requirement-changes/{id}/analyze-impact`
EFFECT 관계를 (재)분석 트리거. SSE 스트림으로 진행 상황 반환.

**Response:** `text/event-stream`
```
data: {"phase": "analyzing", "message": "그래프 분석 중..."}
data: {"phase": "done", "effectCount": 3}
```

---

## 4. 구현 워크플로우 (SSE)

### GET `/api/requirement-changes/{id}/preflight`
구현 시작 전 선행 Change 확인.

**Response:** `ImplementationPreflight`
```json
{
  "changeId": "CHG-003",
  "pendingPriorChanges": [
    {"id": "CHG-001", "title": "...", "status": "APPROVED", "createdAt": "..."}
  ],
  "canProceed": true
}
```

---

### POST `/api/requirement-changes/{id}/implement`
APPROVED → IMPLEMENTED 시작. SSE 스트림.

**Request body:**
```json
{ "includePriorChangeIds": ["CHG-001"] }  // 빈 배열이면 현재 Change만
```

**Response:** `text/event-stream`
```
data: {"phase": "planning", "percentage": 0, "message": "스킬 실행 중..."}
data: {"phase": "executing", "percentage": 30, "tasks": [...]}
data: {"phase": "done", "percentage": 100, "changeId": "CHG-003"}
```

**Side effects:**
- `robo-change-tasks` 스킬 PTY 호출 (인수: `--change-id CHG-003`)
- 완료 시 Change 상태 → IMPLEMENTED
- 문서 자동 갱신 트리거 (robo-sync)

---

## 5. 회귀 테스트 분석

### GET `/api/requirement-changes/{id}/regression`
Change 적용 후 영향받는 테스트 목록.

**Response:** `RegressionAnalysis`
```json
{
  "changeId": "CHG-003",
  "impactedDesignNodes": [...],
  "regressionTests": [
    {
      "testId": null,
      "testType": "contract",
      "description": "OrderBC 계약 테스트 (EFFECT 대상 BC)",
      "affectedNodeId": "BC-order",
      "affectedNodeLabel": "BoundedContext"
    }
  ],
  "hasContractTests": true,
  "hasE2ETests": false
}
```

---

## 6. ChangeSet

### POST `/api/requirement-changes/changesets/`
ChangeSet 생성.

**Request body:** `CreateChangeSetRequest`
```json
{
  "title": "Q3 정책 변경 묶음",
  "changeIds": ["CHG-001", "CHG-002"]
}
```

**Response:** `ChangeSetResponse` (HTTP 201)

---

### GET `/api/requirement-changes/changesets/{id}`
ChangeSet 상세 (포함된 Change 목록 포함).

---

### POST `/api/requirement-changes/changesets/{id}/submit`
ChangeSet 전체 SUBMITTED 처리 (포함된 모든 Change 일괄).

### POST `/api/requirement-changes/changesets/{id}/approve`
ChangeSet 전체 APPROVED 처리 (자기 승인 방지 적용).

---

## Frontend 연동 (ChangesPanel.vue)

| UI 이벤트 | API 호출 |
|-----------|----------|
| Changes 탭 진입 | `GET /api/requirement-changes/` |
| Change 클릭 | `GET /api/requirement-changes/{id}` |
| 추가 Change 버튼 | `POST /api/requirement-changes/` |
| Change 삭제 | `DELETE /api/requirement-changes/{id}` |
| 제출 버튼 | `POST /api/requirement-changes/{id}/submit` |
| 승인 버튼 | `POST /api/requirement-changes/{id}/approve` |
| 구현 시작 | `GET preflight` → 확인 → `POST implement` (SSE) |
| 영향도 확인 | `GET /api/requirement-changes/{id}/impact` |
| 회귀 테스트 | `GET /api/requirement-changes/{id}/regression` |
| US/Design 탭 수정 저장 | `POST /api/requirement-changes/` (sourceType=DIRECT_EDIT) |

---

## Constitution 게이트

| 원칙 | 판단 |
|------|------|
| I (Graph SOT) | ✅ 모든 Change·ChangeSet·EFFECT가 Neo4j 저장 |
| II (DDD 어휘) | ✅ BoundedContext·Aggregate·UserStory 용어 사용 |
| III (Streaming) | ✅ impact-analyze·implement 모두 SSE |
| IV (Human-in-Loop) | ✅ DRAFT→SUBMITTED→APPROVED 전에 구현 불가 |
| V (Feature-Modular) | ✅ `api/features/requirement_changes/` 독립 모듈 |
| VI (Provider-Agnostic) | ✅ 직접 LLM 호출 없음, 스킬이 담당 |
| VII (Observable) | ✅ SmartLogger + correlation ID 각 상태 전이 |
| X (Skill-First) | ✅ robo-change-specify·tasks 스킬 PTY 호출 |
