# Data Model: Requirement Change Management (038)

## 신규 Neo4j 노드

### RequirementChange

> 기존 037의 `RequirementChange` 노드 스키마를 **전체 교체**. 기존 노드 데이터는 `DETACH DELETE`.

```cypher
// docs/cypher/schema/03_node_types.cypher 에 추가
CREATE (chg:RequirementChange {
    id: "CHG-001",                    // String, 필수, 전역 고유
    title: "주문 취소 정책 변경",       // String, 필수
    originalPrompt: "...",            // String, 원본 자연어 프롬프트 or 수정 요약
    author: "user@example.com",       // String, 생성자 ID
    createdAt: datetime(),            // DateTime, 필수
    status: "DRAFT",                  // String: DRAFT|SUBMITTED|APPROVED|REJECTED|IMPLEMENTED
    statusHistory: "[]",             // String (JSON), List<{fromStatus,toStatus,at,actor,comment}>
    sourceType: "PROMPT",             // String: PROMPT|DIRECT_EDIT|MANUAL
    changeSetId: null                 // String|null, 소속 ChangeSet ID (없으면 null)
});

CREATE CONSTRAINT req_change_id IF NOT EXISTS FOR (n:RequirementChange) REQUIRE n.id IS UNIQUE;
```

### ChangeSet

```cypher
CREATE (cs:ChangeSet {
    id: "CS-001",
    title: "Q3 정책 변경 묶음",
    author: "user@example.com",
    createdAt: datetime(),
    status: "DRAFT"                   // DRAFT|SUBMITTED|APPROVED|REJECTED|IMPLEMENTED
});

CREATE CONSTRAINT changeset_id IF NOT EXISTS FOR (n:ChangeSet) REQUIRE n.id IS UNIQUE;
```

---

## 신규 Neo4j 관계

### EFFECT

```cypher
// docs/cypher/schema/04_relationships.cypher 에 추가
// 방향: RequirementChange → UserStory | BoundedContext | Aggregate
MATCH (chg:RequirementChange {id: "CHG-001"})
MATCH (us:UserStory {id: "US-001"})
CREATE (chg)-[:EFFECT {
    reason: "취소 정책 변경으로 US-001 인수조건 수정 필요",
    impactLevel: "HIGH"     // HIGH|MEDIUM|LOW
}]->(us);
```

### CONTAINS

```cypher
// 방향: ChangeSet → RequirementChange
MATCH (cs:ChangeSet {id: "CS-001"})
MATCH (chg:RequirementChange {id: "CHG-001"})
CREATE (cs)-[:CONTAINS]->(chg);
```

---

## 신규 Pydantic 스키마 (`requirement_changes_contracts.py`)

```python
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

class ChangeStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    IMPLEMENTED = "IMPLEMENTED"

class ChangeSourceType(str, Enum):
    PROMPT = "PROMPT"
    DIRECT_EDIT = "DIRECT_EDIT"
    MANUAL = "MANUAL"

class ImpactLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

# --- Request models ---

class CreateChangeRequest(BaseModel):
    title: str
    originalPrompt: str
    sourceType: ChangeSourceType = ChangeSourceType.MANUAL
    # 직접 수정 모드: 영향받는 노드 ID 명시
    directAffectedNodeIds: Optional[List[str]] = None  

class SubmitChangeRequest(BaseModel):
    pass  # no body

class ApproveChangeRequest(BaseModel):
    comment: Optional[str] = None

class RejectChangeRequest(BaseModel):
    comment: str

class CreateChangeSetRequest(BaseModel):
    title: str
    changeIds: List[str]  # CHG-NNN 목록

class AddToChangeSetRequest(BaseModel):
    changeId: str

# --- Effect models ---

class EffectItem(BaseModel):
    nodeId: str
    nodeLabel: str      # UserStory | BoundedContext | Aggregate
    nodeTitle: str
    reason: str
    impactLevel: ImpactLevel

# --- Response models ---

class StatusHistoryEntry(BaseModel):
    fromStatus: str
    toStatus: str
    at: datetime
    actor: str
    comment: Optional[str] = None

class ChangeResponse(BaseModel):
    id: str             # CHG-NNN
    title: str
    originalPrompt: str
    author: str
    createdAt: datetime
    status: ChangeStatus
    statusHistory: List[StatusHistoryEntry]
    sourceType: ChangeSourceType
    changeSetId: Optional[str]
    effects: Optional[List[EffectItem]] = None

class ChangeSetResponse(BaseModel):
    id: str             # CS-NNN
    title: str
    author: str
    createdAt: datetime
    status: ChangeStatus
    changes: List[ChangeResponse]

# --- Implementation task models ---

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    FAILED = "FAILED"

class TaskItem(BaseModel):
    taskId: str
    title: str
    status: TaskStatus
    progress: Optional[str] = None  # partial output line

class ImplementationProgress(BaseModel):
    changeId: str
    phase: str          # "planning" | "executing" | "done"
    percentage: int
    tasks: List[TaskItem]
    message: Optional[str] = None

# --- Regression analysis models ---

class RegressionTestItem(BaseModel):
    testId: Optional[str]       # Test 노드 ID (없으면 null)
    testType: str               # unit | contract | e2e
    description: str
    affectedNodeId: str         # 영향받는 설계 노드 ID
    affectedNodeLabel: str

class RegressionAnalysis(BaseModel):
    changeId: str
    impactedDesignNodes: List[EffectItem]
    regressionTests: List[RegressionTestItem]
    hasContractTests: bool      # BC가 EFFECT 대상이면 true
    hasE2ETests: bool           # UserStory.ui = true이면 true

# --- Pending changes before implementation ---

class PendingChange(BaseModel):
    id: str
    title: str
    createdAt: datetime
    status: ChangeStatus

class ImplementationPreflight(BaseModel):
    changeId: str
    pendingPriorChanges: List[PendingChange]  # 미반영 선행 Change 목록
    canProceed: bool
```

---

## 스키마 변경 요약

| 항목 | 타입 | 비고 |
|------|------|------|
| `RequirementChange` 노드 | 교체 | 037 스키마 전체 초기화 후 재생성 |
| `ChangeSet` 노드 | 신규 | CS-NNN 패턴 |
| `EFFECT` 관계 | 신규 | Change→UserStory/BC/Aggregate |
| `CONTAINS` 관계 | 신규 | ChangeSet→Change |
| `CHANGED_TO` 관계 | 변경 없음 | 기존 change_management에서 사용, 그대로 유지 |

> **Constitution I 체크:** 모든 Change 상태·이력·관계가 Neo4j에 저장됨. ✅
