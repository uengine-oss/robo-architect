from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ProposalStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    IMPLEMENTING = "IMPLEMENTING"
    TESTING = "TESTING"
    PENDING_ACCEPTANCE = "PENDING_ACCEPTANCE"
    ACCEPTED = "ACCEPTED"
    DESTROYED = "DESTROYED"
    MERGE_FAILED = "MERGE_FAILED"


class ImpactLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class StrategicDiffOp(str, Enum):
    CREATE = "CREATE"
    MODIFY = "MODIFY"
    DELETE = "DELETE"


class StatusHistoryEntry(BaseModel):
    from_status: Optional[str] = None
    to_status: str
    actor: str
    at: str
    comment: Optional[str] = None


class StrategicDiffEntry(BaseModel):
    op: StrategicDiffOp
    entityType: str
    entityId: Optional[str] = None
    entityTitle: str
    fields: Optional[dict] = None
    acceptanceCriteria: Optional[list[str]] = None


class StrategicDiff(BaseModel):
    # extra="allow": 프로젝트별로 스킬을 맞춤화하면 아래 1급 카테고리 외의
    # 전략 항목(예: 정책/규칙 등)을 camelCase 복수형 키로 추가할 수 있다.
    # 미지의 키도 그대로 보존되어 UI가 제네릭하게 렌더링한다.
    model_config = ConfigDict(extra="allow")

    version: int = 1
    epics: list[StrategicDiffEntry] = []
    features: list[StrategicDiffEntry] = []
    userStories: list[StrategicDiffEntry] = []
    # 프로세스(Process)는 Epic/Feature/UserStory와 함께 거의 모든 변경에서
    # 쓰이므로 1급 고착 카테고리로 명시.
    processes: list[StrategicDiffEntry] = []


class ImpactMapEntry(BaseModel):
    nodeId: str
    nodeLabel: str
    nodeTitle: str
    conflictLevel: ImpactLevel
    reason: str


class EffectItem(BaseModel):
    nodeId: str
    nodeLabel: str
    nodeTitle: str
    reason: str
    impactLevel: ImpactLevel
    changeType: Optional[str] = "MODIFY"
    diff: Optional[str] = None


class ProposalResponse(BaseModel):
    id: str
    title: str
    originalPrompt: str
    author: str
    createdAt: str
    status: ProposalStatus
    statusHistory: list[StatusHistoryEntry] = []
    strategicDiff: Optional[StrategicDiff] = None
    tacticalDiff: Optional[list[dict]] = None
    journeys: Optional[list[dict]] = None
    impactMap: Optional[list[ImpactMapEntry]] = None
    projectRoot: Optional[str] = None
    sandboxBranch: Optional[str] = None
    sandboxWorktreePath: Optional[str] = None
    sandboxStatus: Optional[str] = None
    clarificationLog: Optional[list[dict]] = None
    intentFeedbackLog: Optional[list[dict]] = None
    acceptedAt: Optional[str] = None
    destroyedAt: Optional[str] = None
    testResults: Optional[dict] = None

    @staticmethod
    def from_neo4j(node: dict, effects: list[EffectItem]) -> "ProposalResponse":
        def _dt(v) -> str:
            if v is None:
                return datetime.now(timezone.utc).isoformat()
            try:
                return v.isoformat()
            except Exception:
                return str(v)

        def _parse_json(v, default):
            if not v:
                return default
            if isinstance(v, (dict, list)):
                return v
            try:
                return json.loads(v)
            except Exception:
                return default

        raw_history = _parse_json(node.get("statusHistory"), [])
        history = []
        for h in raw_history:
            try:
                history.append(StatusHistoryEntry(**h) if isinstance(h, dict) else h)
            except Exception:
                continue

        raw_strategic = _parse_json(node.get("strategicDiff"), None)
        try:
            strategic = StrategicDiff(**raw_strategic) if raw_strategic else None
        except Exception:
            strategic = None

        raw_tactical = _parse_json(node.get("tacticalDiff"), None)
        raw_journeys = _parse_json(node.get("journeys"), None)

        raw_impact = _parse_json(node.get("impactMap"), None)
        impact = None
        if raw_impact:
            impact = []
            for e in raw_impact:
                if not isinstance(e, dict):
                    continue
                # 과거 데이터 호환: 누락/널 필드를 안전한 기본값으로 보정해
                # 항목 하나의 스키마 위반이 목록 전체를 500으로 만들지 않게 한다.
                try:
                    impact.append(ImpactMapEntry(
                        nodeId=str(e.get("nodeId") or ""),
                        nodeLabel=str(e.get("nodeLabel") or "Unknown"),
                        nodeTitle=str(e.get("nodeTitle") or e.get("nodeId") or ""),
                        conflictLevel=e.get("conflictLevel") or "LOW",
                        reason=str(e.get("reason") or ""),
                    ))
                except Exception:
                    continue

        raw_clarify = _parse_json(node.get("clarificationLog"), [])
        raw_feedback = _parse_json(node.get("intentFeedbackLog"), [])

        raw_test_results = _parse_json(node.get("testResults"), None)

        accepted_at = node.get("acceptedAt")
        destroyed_at = node.get("destroyedAt")

        return ProposalResponse(
            id=node["id"],
            title=node.get("title", ""),
            originalPrompt=node.get("originalPrompt", ""),
            author=node.get("author", "anonymous"),
            createdAt=_dt(node.get("createdAt")),
            status=ProposalStatus(node.get("status", "DRAFT")),
            statusHistory=history,
            strategicDiff=strategic,
            tacticalDiff=raw_tactical,
            journeys=raw_journeys,
            impactMap=impact,
            projectRoot=node.get("projectRoot"),
            sandboxBranch=node.get("sandboxBranch"),
            sandboxWorktreePath=node.get("sandboxWorktreePath"),
            sandboxStatus=node.get("sandboxStatus"),
            clarificationLog=raw_clarify,
            intentFeedbackLog=raw_feedback,
            acceptedAt=_dt(accepted_at) if accepted_at else None,
            destroyedAt=_dt(destroyed_at) if destroyed_at else None,
            testResults=raw_test_results,
        )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateProposalRequest(BaseModel):
    originalPrompt: str
    title: Optional[str] = None


class SubmitProposalRequest(BaseModel):
    pass


class AcceptProposalRequest(BaseModel):
    comment: Optional[str] = None
    forceAcceptWithFailures: bool = False


class DestroyProposalRequest(BaseModel):
    reason: Optional[str] = None


class RevokeProposalRequest(BaseModel):
    # revertCode=True면 Accept 머지 커밋까지 git revert(코드 되돌림). False면 그래프만 복원.
    revertCode: bool = False
    comment: Optional[str] = None


class ClarificationAnswer(BaseModel):
    questionIndex: int
    answer: str


class AnswerClarificationRequest(BaseModel):
    answers: list[ClarificationAnswer]


class UpdateDiffRequest(BaseModel):
    strategicDiff: Optional[dict] = None
    tacticalDiff: Optional[list[dict]] = None


class IntentFeedbackRequest(BaseModel):
    # 인텐트 분해 결과가 의도를 잘못 반영했을 때, 보정할 자연어 피드백.
    feedback: str


class TestResultItem(BaseModel):
    scenarioId: str
    storyId: str
    storyTitle: str
    scenario: str
    result: str
    reason: Optional[str] = None
    # "acceptance"(GWT 인수 조건) | "structural"(Tactical Diff ↔ 구현체 구조 검증)
    category: Optional[str] = None


class TestRunResult(BaseModel):
    proposalId: str
    totalScenarios: int
    passed: int
    failed: int
    skipped: int
    items: list[TestResultItem] = []


def extract_title_from_prompt(prompt: str) -> str:
    first = re.split(r'[.!?\n]', prompt.strip())[0].strip()
    if len(first) > 50:
        first = first[:50] + "..."
    return first or prompt[:50]


def append_status_history(existing_json: str, from_status: str, to_status: str, actor: str, comment: Optional[str] = None) -> str:
    try:
        history = json.loads(existing_json) if existing_json else []
    except Exception:
        history = []
    history.append({
        "from_status": from_status,
        "to_status": to_status,
        "actor": actor,
        "at": datetime.now(timezone.utc).isoformat(),
        "comment": comment,
    })
    return json.dumps(history, ensure_ascii=False)
