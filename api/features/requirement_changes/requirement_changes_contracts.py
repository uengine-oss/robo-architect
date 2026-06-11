from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator


class ChangeStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PLAN_APPROVED = "PLAN_APPROVED"    # 1차 승인: 영향도 계획 승인
    DESIGN_APPLIED = "DESIGN_APPLIED"  # 설계 반영 완료: Stories/Process/Design 업데이트
    APPROVED = "APPROVED"              # 2차 승인: 구현 가능
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


class EffectChangeType(str, Enum):
    MODIFY = "MODIFY"
    CREATE = "CREATE"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateChangeRequest(BaseModel):
    title: Optional[str] = None   # 없으면 originalPrompt 첫 문장에서 자동 추출
    originalPrompt: str
    sourceType: ChangeSourceType = ChangeSourceType.MANUAL
    directAffectedNodeIds: Optional[list[str]] = None


class ApproveChangeRequest(BaseModel):
    comment: Optional[str] = None


class RejectChangeRequest(BaseModel):
    comment: str


class CreateChangeSetRequest(BaseModel):
    title: str
    changeIds: list[str]


class AddToChangeSetRequest(BaseModel):
    changeId: str


class ImplementChangeRequest(BaseModel):
    includePriorChangeIds: list[str] = []


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------

class StatusHistoryEntry(BaseModel):
    fromStatus: str
    toStatus: str
    at: datetime
    actor: str
    comment: Optional[str] = None


class EffectItem(BaseModel):
    nodeId: str
    nodeLabel: str
    nodeTitle: str
    reason: str
    impactLevel: ImpactLevel
    changeType: EffectChangeType = EffectChangeType.MODIFY
    templateData: Optional[dict] = None   # CREATE only: 생성할 노드 필드 명세
    appliedNodeId: Optional[str] = None   # CREATE only: apply 후 실제 생성된 노드 ID


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ChangeResponse(BaseModel):
    id: str
    title: str
    originalPrompt: str
    author: str
    createdAt: datetime
    status: ChangeStatus
    statusHistory: list[StatusHistoryEntry]
    sourceType: ChangeSourceType
    changeSetId: Optional[str] = None
    effects: Optional[list[EffectItem]] = None

    @classmethod
    def from_neo4j(cls, record: dict, effects: list[EffectItem] | None = None) -> "ChangeResponse":
        history_raw = record.get("statusHistory", "[]") or "[]"
        try:
            history_data = json.loads(history_raw)
        except (json.JSONDecodeError, TypeError):
            history_data = []
        history = [StatusHistoryEntry(**h) for h in history_data]

        # Neo4j DateTime → Python datetime 변환
        raw_dt = record.get("createdAt")
        if hasattr(raw_dt, "to_native"):
            created_at = raw_dt.to_native()
        elif isinstance(raw_dt, str):
            from datetime import datetime
            created_at = datetime.fromisoformat(raw_dt.replace("Z", "+00:00"))
        else:
            created_at = raw_dt

        return cls(
            id=record["id"],
            title=record["title"],
            originalPrompt=record.get("originalPrompt", ""),
            author=record.get("author", ""),
            createdAt=created_at,
            status=ChangeStatus(record["status"]),
            statusHistory=history,
            sourceType=ChangeSourceType(record.get("sourceType", "MANUAL")),
            changeSetId=record.get("changeSetId"),
            effects=effects,
        )


class ChangeSetResponse(BaseModel):
    id: str
    title: str
    author: str
    createdAt: datetime
    status: ChangeStatus
    changes: list[ChangeResponse]


# ---------------------------------------------------------------------------
# Implementation / SSE models
# ---------------------------------------------------------------------------

class TaskItem(BaseModel):
    taskId: str
    title: str
    status: TaskStatus
    progress: Optional[str] = None


class ImplementationProgress(BaseModel):
    changeId: str
    phase: str
    percentage: int
    tasks: list[TaskItem]
    message: Optional[str] = None


class PendingChange(BaseModel):
    id: str
    title: str
    createdAt: datetime
    status: ChangeStatus


class ImplementationPreflight(BaseModel):
    changeId: str
    pendingPriorChanges: list[PendingChange]
    canProceed: bool


# ---------------------------------------------------------------------------
# Design-apply models (Step 2: PLAN_APPROVED → DESIGN_APPLIED)
# ---------------------------------------------------------------------------

# ── Semantic Diff ──────────────────────────────────────────────────────────
# EFFECT 관계 속성에 저장되는 의미적 변경 연산 단위.
# 각 RequirementChange→Target 쌍마다 하나의 SemanticDiff가 저장된다.
# ---------------------------------------------------------------------------

class DiffOpType(str, Enum):
    """단일 필드 변경 연산 유형."""
    REPLACE          = "replace"           # 텍스트 필드 전체 교체 (description 등)
    LIST_APPEND      = "list_append"       # 리스트에 항목 추가 (acceptanceCriteria, invariants)
    LIST_REMOVE      = "list_remove"       # 리스트에서 항목 제거
    OBJ_APPEND       = "obj_append"        # JSON 배열에 객체 추가 (valueObjects, enumerations)
    OBJ_REMOVE       = "obj_remove"        # JSON 배열에서 이름으로 객체 제거
    ENUM_ADD_ITEMS   = "enum_add_items"    # 열거형 항목 추가
    ENUM_REMOVE_ITEMS= "enum_remove_items" # 열거형 항목 제거


class DiffOp(BaseModel):
    """EFFECT 관계에 기록되는 단일 변경 연산."""
    field: str                        # 대상 필드명 (description, valueObjects, ...)
    op: DiffOpType
    # replace
    from_val: Optional[str] = None    # 변경 전 값
    to_val:   Optional[str] = None    # 변경 후 값
    # list_append / list_remove (acceptanceCriteria, invariants)
    items: Optional[list] = None
    # obj_append / obj_remove (valueObjects, enumerations)
    obj_name: Optional[str] = None    # 객체 식별 이름
    obj_data: Optional[dict] = None   # obj_append 시 전체 데이터
    # enum_add_items / enum_remove_items
    enum_name: Optional[str] = None


class SemanticDiff(BaseModel):
    """
    EFFECT 관계 속성 e.diff 에 JSON 직렬화되어 저장되는 의미적 diff.
    RequirementChange 1건 × Target 노드 1건 = SemanticDiff 1건.
    ops 를 역방향 적용하면 완전한 undo가 가능하다.
    changeType=='CREATE' 인 경우 ops는 빈 리스트이며 createdNodeId로 undo(삭제)한다.
    """
    v: int = 1
    nodeLabel: str
    nodeTitle: str
    appliedAt: str                    # ISO-8601 UTC
    ops: list[DiffOp]
    changeType: str = "MODIFY"        # "MODIFY" | "CREATE"
    createdNodeId: Optional[str] = None  # CREATE only: 생성된 실제 노드 ID


# ── Display model (API 응답용) ─────────────────────────────────────────────
# SemanticDiff를 프론트엔드가 렌더링하기 좋은 형태로 평탄화한 뷰 모델.
# EFFECT.diff → DesignChangeItem 변환은 changes_design.py 에서 수행.
# ---------------------------------------------------------------------------

class DesignChangeItem(BaseModel):
    nodeId: str
    nodeLabel: str
    nodeTitle: str
    impactLevel: ImpactLevel
    appliedAt: Optional[str] = None
    # 변경 유형 (MODIFY: 기존 노드 수정, CREATE: 신규 노드 생성)
    changeType: str = "MODIFY"
    createdNodeId: Optional[str] = None  # CREATE only: 생성된 노드 ID
    templateData: Optional[dict] = None  # CREATE only: 생성 시 사용된 템플릿
    # 텍스트 diff (replace op에서 추출, MODIFY only)
    field: Optional[str] = None
    before: Optional[str] = None
    after:  Optional[str] = None
    # 구조화 diff (Aggregate/Command/Event — obj/enum/list ops에서 추출)
    fieldChanges:       Optional[list[dict]] = None  # AI가 생성한 field-level 변경 목록
    valueObjectChanges: Optional[list[dict]] = None
    enumChanges:        Optional[list[dict]] = None
    invariantChanges:   Optional[list[str]]  = None
    # 원본 semantic diff (undo 처리 및 상세 표시용)
    semanticDiff: Optional[dict] = None


class DesignApplyResult(BaseModel):
    changeId: str
    appliedCount: int
    skippedCount: int
    items: list[DesignChangeItem]


# ---------------------------------------------------------------------------
# Regression analysis models
# ---------------------------------------------------------------------------

class RegressionTestItem(BaseModel):
    testId: Optional[str] = None
    testType: str
    description: str
    affectedNodeId: str
    affectedNodeLabel: str


class RegressionAnalysis(BaseModel):
    changeId: str
    impactedDesignNodes: list[EffectItem]
    regressionTests: list[RegressionTestItem]
    hasContractTests: bool
    hasE2ETests: bool
