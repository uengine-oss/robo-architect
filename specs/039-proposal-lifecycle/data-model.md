# Data Model: Proposal Lifecycle Management

**Feature**: `039-proposal-lifecycle`
**Date**: 2026-06-05

---

## Neo4j Node: Proposal

038의 `RequirementChange` 노드를 대체하는 새로운 노드 레이블.

### Properties

| 속성 | 타입 | 설명 |
|------|------|------|
| `id` | `String` (PK) | `PRO-NNN` 형식 전역 고유 ID |
| `title` | `String` | Proposal 제목 (originalPrompt 첫 문장에서 자동 추출) |
| `originalPrompt` | `String` | 사용자가 입력한 원본 자연어 |
| `author` | `String` | 생성자 사용자 ID/이메일 |
| `createdAt` | `DateTime` | 생성 시각 (ISO-8601 UTC) |
| `status` | `String` | ProposalStatus 열거값 (아래 참조) |
| `statusHistory` | `String` (JSON) | `StatusHistoryEntry[]` 직렬화 |
| `clarificationLog` | `String` (JSON) | 명확화 질문/답변 이력 `[{question, answer, at}]` |
| `strategicDiff` | `String` (JSON) | `StrategicDiff` 객체 직렬화 (Epic/Feature/UserStory 변경안) |
| `tacticalDiff` | `String` (JSON) | `TacticalDiff` 객체 직렬화 (Aggregate/Command/Event/VO SemanticDiff) |
| `impactMap` | `String` (JSON) | `ImpactMapEntry[]` 직렬화 (nodeId, nodeLabel, conflictLevel, reason) |
| `projectRoot` | `String?` | 대상 프로젝트 Git repo 절대 경로 (= Claude Code 탭 경로, `localStorage['claude_code_workspace_root']`). Worktree 원천이며 robo-architect 자신이 아님. 구현 시작 시 저장, 머지·정리에 재사용 |
| `sandboxBranch` | `String?` | Git 브랜치명 `proposal/PRO-NNN` (샌드박스 생성 후 설정) |
| `sandboxWorktreePath` | `String?` | 절대 경로 `<projectRoot>/.sandbox/proposal/PRO-NNN` |
| `sandboxStatus` | `String?` | `CREATING \| READY \| IMPLEMENTING \| DONE \| DESTROYED` |
| `acceptedAt` | `DateTime?` | Dual Merge 완료 시각 |
| `destroyedAt` | `DateTime?` | Destroy 처리 시각 |

### ProposalStatus 열거형

```
DRAFT              ← 인텐트 분해 중 or 완료, 사용자 검토 대기
SUBMITTED          ← 사용자가 검토 후 제출, 샌드박스 구현 대기
IMPLEMENTING       ← Git Worktree 생성 완료, Claude Code 구현 중
TESTING            ← 구현 완료, 자동 테스트 실행 중
PENDING_ACCEPTANCE ← 테스트 완료, PO 승인 대기
ACCEPTED           ← Dual Merge 완료, 라이브 반영
DESTROYED          ← PO가 폐기, Worktree 정리 완료
MERGE_FAILED       ← Dual Merge 실패, 재시도 가능
```

### 상태 전이 다이어그램

```
                ┌─────────┐
                │  DRAFT  │ ← 생성, AI 인텐트 분해, 명확화
                └────┬────┘
                     │ submit()
                     ▼
               ┌───────────┐
               │ SUBMITTED │ ← 사용자 검토 완료
               └─────┬─────┘
                     │ implement()
                     ▼
             ┌──────────────┐
             │ IMPLEMENTING │ ← Git Worktree + Claude Code
             └──────┬───────┘
                    │ (tasks done)
                    ▼
              ┌─────────┐
              │ TESTING │ ← GWT 자동 검증
              └────┬────┘
                   │ (tests done)
                   ▼
        ┌────────────────────┐
        │ PENDING_ACCEPTANCE │ ← PO 최종 검토
        └──────┬─────────────┘
        accept()│           │destroy()
               ▼            ▼
         ┌──────────┐  ┌───────────┐
         │ ACCEPTED │  │ DESTROYED │
         └──────────┘  └───────────┘
              ↑
     MERGE_FAILED ──retry()──┘
```

---

## JSON Payload: StrategicDiff

```json
{
  "version": 1,
  "epics": [
    {
      "op": "MODIFY",
      "epicId": "EP-001",
      "epicTitle": "결제 관리",
      "fields": { "description": { "before": "...", "after": "..." } }
    },
    {
      "op": "CREATE",
      "epicId": null,
      "epicTitle": "부분 환불 관리"
    }
  ],
  "features": [
    {
      "op": "CREATE",
      "featureId": null,
      "featureTitle": "부분 환불 요청",
      "epicId": "EP-001"
    }
  ],
  "userStories": [
    {
      "op": "CREATE",
      "storyId": null,
      "storyTitle": "고객이 주문의 일부 금액만 환불을 요청할 수 있다",
      "featureId": null,
      "description": "...",
      "acceptanceCriteria": [
        "Given 주문 상태가 완료일 때, When 부분 환불 금액을 입력하면, Then 환불 요청이 생성된다",
        "Given 부분 환불 금액이 결제 금액을 초과할 때, Then 오류 메시지가 표시된다"
      ]
    },
    {
      "op": "MODIFY",
      "storyId": "US-042",
      "storyTitle": "전액 환불 처리",
      "fields": {
        "description": { "before": "...", "after": "..." }
      }
    }
  ],
  "processes": [
    {
      "op": "MODIFY",
      "entityType": "process",
      "entityId": "PROC-refund",
      "entityTitle": "환불 처리 프로세스",
      "fields": { "steps": { "before": "환불요청→승인→정산", "after": "환불요청→부분금액검증→승인→정산" } }
    }
  ]
}
```

> **1급 카테고리 vs 제네릭 확장**: `epics` / `features` / `userStories` / `processes` 네 개는 거의 모든
> 변경에서 쓰이므로 백엔드 모델·UI에 고착(first-class)되어 있다. 프로젝트별로 스킬을 맞춤화할 때
> 이 외의 전략 항목이 필요하면 `camelCase` 복수형 키(예: `policies`, `businessRules`)를 추가할 수 있다.
> `StrategicDiff`는 `extra="allow"`로 미지 키를 보존하고, `IntentDecompositionView`는 1급 외 배열 키를
> 키 이름 기준으로 제네릭하게 렌더링하므로 **백엔드·프론트엔드 코드 수정 없이** 새 전략 카테고리가 표시된다.

---

## JSON Payload: TacticalDiff

038의 `SemanticDiff` 구조 재사용. Proposal → Aggregate EFFECT 관계에 저장됨.

```json
[
  {
    "nodeId": "AGG-refund",
    "nodeLabel": "Aggregate",
    "nodeTitle": "환불 Aggregate",
    "impactLevel": "HIGH",
    "changeType": "MODIFY",
    "semanticDiff": {
      "v": 1,
      "nodeLabel": "Aggregate",
      "nodeTitle": "환불 Aggregate",
      "appliedAt": null,
      "ops": [
        {
          "field": "valueObjects",
          "op": "obj_append",
          "obj_name": "PartialRefundAmount",
          "obj_data": {
            "name": "PartialRefundAmount",
            "type": "Long",
            "description": "부분 환불 금액 (원화 단위)"
          }
        },
        {
          "field": "invariants",
          "op": "list_append",
          "items": ["부분 환불 금액은 원래 결제 금액을 초과할 수 없다"]
        }
      ],
      "changeType": "MODIFY"
    }
  },
  {
    "nodeId": null,
    "nodeLabel": "Command",
    "nodeTitle": "RequestPartialRefund",
    "impactLevel": "HIGH",
    "changeType": "CREATE",
    "semanticDiff": {
      "v": 1,
      "nodeLabel": "Command",
      "nodeTitle": "RequestPartialRefund",
      "appliedAt": null,
      "ops": [],
      "changeType": "CREATE"
    }
  }
]
```

---

## JSON Payload: ImpactMap

```json
[
  {
    "nodeId": "US-042",
    "nodeLabel": "UserStory",
    "nodeTitle": "전액 환불 처리",
    "conflictLevel": "MEDIUM",
    "reason": "부분 환불 추가 시 전액 환불 플로우와 분기 처리 필요"
  },
  {
    "nodeId": "AGG-refund",
    "nodeLabel": "Aggregate",
    "nodeTitle": "환불 Aggregate",
    "conflictLevel": "HIGH",
    "reason": "PartialRefundAmount VO 추가 및 불변 조건 추가 필요"
  },
  {
    "nodeId": "BC-payment",
    "nodeLabel": "BoundedContext",
    "nodeTitle": "결제 컨텍스트",
    "conflictLevel": "LOW",
    "reason": "환불 흐름이 이미 결제 컨텍스트 내 Aggregate와 연결됨"
  }
]
```

---

## Neo4j Relationship: EFFECT (재사용)

038에서 `RequirementChange` → 대상 노드였던 관계를 `Proposal` → 대상 노드로 재사용.

```
(p:Proposal)-[:EFFECT {
  reason: String,
  impactLevel: "HIGH|MEDIUM|LOW",
  changeType: "MODIFY|CREATE",
  diff: String (SemanticDiff JSON, TacticalDiff의 항목별 저장)
}]->(target)
```

target은 `UserStory | Feature | BoundedContext | Aggregate | Command | Event` 노드.

---

## Neo4j Cypher Schema 추가 (docs/cypher/schema/)

### 03_node_types.cypher 추가

```cypher
CREATE CONSTRAINT proposal_id_unique IF NOT EXISTS
FOR (p:Proposal) REQUIRE p.id IS UNIQUE;

CREATE INDEX proposal_status IF NOT EXISTS
FOR (p:Proposal) ON (p.status);

CREATE INDEX proposal_author IF NOT EXISTS
FOR (p:Proposal) ON (p.author);
```

### 04_relationships.cypher 추가

```cypher
-- Proposal → 영향받는 도메인 노드
-- (p:Proposal)-[:EFFECT]->(n)
-- 038의 RequirementChange→n EFFECT 관계와 동일 구조, 레이블만 변경
```

---

## Python Pydantic Models (proposal_contracts.py)

```python
class ProposalStatus(str, Enum):
    DRAFT              = "DRAFT"
    SUBMITTED          = "SUBMITTED"
    IMPLEMENTING       = "IMPLEMENTING"
    TESTING            = "TESTING"
    PENDING_ACCEPTANCE = "PENDING_ACCEPTANCE"
    ACCEPTED           = "ACCEPTED"
    DESTROYED          = "DESTROYED"
    MERGE_FAILED       = "MERGE_FAILED"

class StrategicDiffOp(str, Enum):
    CREATE = "CREATE"
    MODIFY = "MODIFY"
    DELETE = "DELETE"

class StrategicDiffEntry(BaseModel):
    op: StrategicDiffOp
    entityType: str        # "epic" | "feature" | "userStory"
    entityId: Optional[str]
    entityTitle: str
    fields: Optional[dict]              # MODIFY only
    acceptanceCriteria: Optional[list[str]]  # CREATE userStory only

class StrategicDiff(BaseModel):
    version: int = 1
    epics: list[StrategicDiffEntry] = []
    features: list[StrategicDiffEntry] = []
    userStories: list[StrategicDiffEntry] = []

class ImpactMapEntry(BaseModel):
    nodeId: str
    nodeLabel: str
    nodeTitle: str
    conflictLevel: ImpactLevel   # 038 ImpactLevel 재사용
    reason: str

class ProposalResponse(BaseModel):
    id: str                        # PRO-NNN
    title: str
    originalPrompt: str
    author: str
    createdAt: datetime
    status: ProposalStatus
    statusHistory: list[StatusHistoryEntry]   # 038 StatusHistoryEntry 재사용
    strategicDiff: Optional[StrategicDiff]
    tacticalDiff: Optional[list[EffectItem]]  # 038 EffectItem 재사용
    impactMap: Optional[list[ImpactMapEntry]]
    projectRoot: Optional[str]                # 대상 프로젝트 Git repo (Claude Code 탭 경로)
    sandboxBranch: Optional[str]
    sandboxWorktreePath: Optional[str]        # <projectRoot>/.sandbox/proposal/PRO-NNN
    sandboxStatus: Optional[str]
    clarificationLog: Optional[list[dict]]

class CreateProposalRequest(BaseModel):
    originalPrompt: str
    title: Optional[str] = None

class SubmitProposalRequest(BaseModel):
    pass  # 추가 파라미터 없음

class AcceptProposalRequest(BaseModel):
    comment: Optional[str] = None
    forceAcceptWithFailures: bool = False  # 테스트 실패 무시 시 True

class DestroyProposalRequest(BaseModel):
    reason: Optional[str] = None

class ClarificationAnswer(BaseModel):
    questionIndex: int
    answer: str

class AnswerClarificationRequest(BaseModel):
    answers: list[ClarificationAnswer]

class TestResultItem(BaseModel):
    scenarioId: str
    storyId: str
    storyTitle: str
    scenario: str
    result: str   # "PASS" | "FAIL" | "SKIPPED"
    reason: Optional[str]

class TestRunResult(BaseModel):
    proposalId: str
    totalScenarios: int
    passed: int
    failed: int
    skipped: int
    items: list[TestResultItem]

# ── 샌드박스 구현 (인터랙티브 셀) 엔드포인트 계약 ──
class ImplementRequest(BaseModel):
    projectRoot: str          # Claude Code 탭 대상 프로젝트 경로 (Worktree 원천)

class ImplementResponse(BaseModel):
    proposalId: str
    status: str               # "IMPLEMENTING"
    worktreePath: str         # <projectRoot>/.sandbox/proposal/PRO-NNN
    branch: str               # proposal/PRO-NNN
    command: str              # Code 탭 셀에 주입할 구현 지시
```

---

## Runtime State: Claude Code 셀(PTY) 세션

Neo4j가 아니라 런타임/클라이언트 상태. 여러 Proposal worktree를 동시에 독립
claude 세션으로 구현하고, 새로고침에도 세션이 살아남게 한다.

### 백엔드 세션 레지스트리 (api/features/claude_code/router.py — 메모리)

| 필드 | 설명 |
|------|------|
| `session_id` | 세션 키 = `<프런트 세션 id>#<epoch>` (예: `<worktreePath>#0`). 같은 키 재연결 시 재어태치 |
| `pid`, `master_fd` | fork된 `claude` PTY 프로세스/마스터 FD |
| `buffer` | 출력 스크롤백 링버퍼(기본 256KB) — 재연결 시 replay |
| `ws` | 현재 attach된 WebSocket(또는 None=detached) |
| `detached_at` | 분리 시각 — TTL(기본 30분) 회수 기준 |

- ws 끊김 = **detach**(PTY 유지). `{type:'close'}` 메시지 또는 `DELETE /api/claude-code/terminal/session?session_id=...` 만 PTY 종료(SIGTERM).
- 동시 세션 상한 기본 16. WebSocket 쿼리 파라미터에 `session_id` 추가.

### 프런트 세션 모델 (ClaudeCodeWorkspace — localStorage)

```ts
type TerminalSession = {
  id: string            // worktree 경로 | 'main' | 'shell-<ts>'
  label: string         // 탭 라벨 (PRO-NNN / 폴더명 / '프로젝트')
  workdir: string
  kind: 'main' | 'proposal' | 'shell'
  epoch: number         // "다시 구현하기" 시 +1 → 새 backend session_id
}
// localStorage: claude_code_workspace_sessions / _active_session
// backend session_id = `${id}#${epoch}`
```

