# API Contracts: Proposal Lifecycle Management

**Base URL**: `/api/proposals`
**Feature**: `039-proposal-lifecycle`
**Date**: 2026-06-05

---

## 엔드포인트 목록

| Method | Path | 설명 | 응답 |
|--------|------|------|------|
| POST | `/api/proposals/` | Proposal 생성 (인텐트 분해 SSE 시작) | `ProposalResponse` |
| GET | `/api/proposals/` | Proposal 목록 조회 | `list[ProposalResponse]` |
| GET | `/api/proposals/{id}` | Proposal 상세 조회 | `ProposalResponse` |
| POST | `/api/proposals/{id}/clarify` | 명확화 질문 답변 제출 | `ProposalResponse` |
| PUT | `/api/proposals/{id}/diff` | Strategic/Tactical Diff 수정 | `ProposalResponse` |
| POST | `/api/proposals/{id}/submit` | DRAFT → SUBMITTED | `ProposalResponse` |
| POST | `/api/proposals/{id}/implement` | SUBMITTED → IMPLEMENTING (SSE) | SSE stream |
| GET | `/api/proposals/{id}/test-results` | 자동 테스트 결과 조회 | `TestRunResult` |
| POST | `/api/proposals/{id}/accept` | PENDING_ACCEPTANCE → ACCEPTED (Dual Merge) | `ProposalResponse` |
| POST | `/api/proposals/{id}/destroy` | → DESTROYED | `ProposalResponse` |
| POST | `/api/proposals/{id}/retry-merge` | MERGE_FAILED → 재시도 | SSE stream |
| GET | `/api/proposals/stream/{id}/intent` | 인텐트 분해 진행 SSE | SSE stream |

---

## POST /api/proposals/

Proposal을 생성하고 백그라운드에서 인텐트 분해를 시작한다.

**Request**
```json
{
  "originalPrompt": "결제 시스템에 부분 환불 버튼 하나만 추가해줘",
  "title": null
}
```

**Response** `201 Created`
```json
{
  "id": "PRO-001",
  "title": "부분 환불 기능 추가",
  "originalPrompt": "결제 시스템에 부분 환불 버튼 하나만 추가해줘",
  "author": "jyjang@uengine.org",
  "createdAt": "2026-06-05T10:00:00Z",
  "status": "DRAFT",
  "statusHistory": [],
  "strategicDiff": null,
  "tacticalDiff": null,
  "impactMap": null,
  "sandboxBranch": null,
  "sandboxStatus": null,
  "clarificationLog": []
}
```

---

## GET /api/proposals/stream/{id}/intent (SSE)

인텐트 분해 + Impact Map 생성 진행 상황을 SSE로 스트리밍한다.

**SSE Event Types**

```
event: phase
data: {"phase": "intent_decomposition", "message": "자연어 인텐트 분해 중..."}

event: clarification_needed
data: {"questions": [{"index": 0, "text": "부분 환불의 최소/최대 금액 제한이 있나요?", "options": ["있음", "없음", "직접 입력"]}]}

event: strategic_diff
data: {"strategicDiff": {...}}

event: tactical_diff
data: {"tacticalDiff": [...]}

event: impact_map
data: {"impactMap": [...]}

event: done
data: {"proposalId": "PRO-001", "status": "DRAFT"}

event: error
data: {"code": "INTENT_FAILED", "message": "인텐트 분해 실패"}
```

---

## POST /api/proposals/{id}/clarify

사용자가 명확화 질문에 답변한다. 스킬이 재호출되어 Diff가 확정된다.

**Request**
```json
{
  "answers": [
    {"questionIndex": 0, "answer": "있음"},
    {"questionIndex": 1, "answer": "원화 단위, 100원 이상"}
  ]
}
```

**Response** `200 OK` — 업데이트된 `ProposalResponse`

---

## PUT /api/proposals/{id}/diff

사용자가 AI 생성 Diff를 수동으로 수정한다.

**Request**
```json
{
  "strategicDiff": { ... },
  "tacticalDiff": [ ... ]
}
```

**Response** `200 OK` — 업데이트된 `ProposalResponse`

---

## POST /api/proposals/{id}/submit

DRAFT → SUBMITTED 전환. Impact Map 확인 후 구현 승인.

**Response** `200 OK`
```json
{
  "id": "PRO-001",
  "status": "SUBMITTED",
  ...
}
```

**Error Cases**
- `400`: strategicDiff 또는 tacticalDiff가 null인 경우
- `409`: 동일 노드를 수정하는 IMPLEMENTING 중인 Proposal이 존재할 때

---

## POST /api/proposals/{id}/implement (SSE)

Git Worktree를 생성하고 Claude Code로 구현 태스크를 실행한다.

**SSE Event Types**

```
event: sandbox_creating
data: {"branch": "proposal/PRO-001", "worktreePath": ".sandbox/proposal/PRO-001"}

event: sandbox_ready
data: {"branch": "proposal/PRO-001", "message": "Worktree 생성 완료"}

event: task_start
data: {"taskId": "T-001", "title": "API Skeleton 생성"}

event: task_progress
data: {"taskId": "T-001", "output": "...claude code output...", "percentage": 30}

event: task_done
data: {"taskId": "T-001", "status": "DONE"}

event: task_failed
data: {"taskId": "T-002", "status": "FAILED", "error": "..."}

event: all_done
data: {"proposalId": "PRO-001", "status": "TESTING", "totalTasks": 5, "doneTasks": 5}

event: error
data: {"code": "WORKTREE_FAILED", "message": "Git Worktree 생성 실패: 디스크 공간 부족"}
```

---

## GET /api/proposals/{id}/test-results

자동 테스트 결과를 반환한다. TESTING → PENDING_ACCEPTANCE 전환 후 호출 가능.

**Response** `200 OK`
```json
{
  "proposalId": "PRO-001",
  "totalScenarios": 5,
  "passed": 4,
  "failed": 1,
  "skipped": 0,
  "items": [
    {
      "scenarioId": "SC-001",
      "storyId": "US-new-1",
      "storyTitle": "고객이 부분 환불을 요청할 수 있다",
      "scenario": "Given 주문 완료 상태, When 부분 금액 입력, Then 환불 요청 생성",
      "result": "PASS",
      "reason": null
    },
    {
      "scenarioId": "SC-002",
      "storyId": "US-new-1",
      "storyTitle": "고객이 부분 환불을 요청할 수 있다",
      "scenario": "Given 부분 금액이 결제 금액 초과, Then 오류 표시",
      "result": "FAIL",
      "reason": "구현된 API가 초과 금액을 허용함"
    }
  ]
}
```

---

## POST /api/proposals/{id}/accept

PO가 Accept를 확정하면 Dual Merge를 실행한다.

**Request**
```json
{
  "comment": "검토 완료, 반영 승인",
  "forceAcceptWithFailures": false
}
```

**Response** `200 OK`
```json
{
  "id": "PRO-001",
  "status": "ACCEPTED",
  "acceptedAt": "2026-06-05T15:30:00Z",
  ...
}
```

**Error Cases**
- `400`: 테스트 실패 항목이 있고 `forceAcceptWithFailures=false`
- `400`: 자기 승인 시도 (생성자 == 요청자)
- `409`: status가 `PENDING_ACCEPTANCE`가 아님
- `500`: Dual Merge 실패 → status가 `MERGE_FAILED`로 전환됨

---

## POST /api/proposals/{id}/destroy

**Request**
```json
{
  "reason": "설계 재검토 필요"
}
```

**Response** `200 OK`
```json
{
  "id": "PRO-001",
  "status": "DESTROYED",
  "destroyedAt": "2026-06-05T15:35:00Z",
  ...
}
```

---

## GET /api/proposals/

**Query Parameters**
- `status`: 상태 필터 (optional, 복수 허용: `?status=DRAFT&status=SUBMITTED`)
- `author`: 작성자 필터 (optional)
- `limit`: 최대 반환 수 (default: 50)
- `offset`: 페이징 오프셋 (default: 0)

**Response** `200 OK` — `list[ProposalResponse]`
