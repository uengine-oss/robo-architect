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


# --- 041: Constitution + Plan stage ----------------------------------------

class ArchitectureStyle(str, Enum):
    MONOLITH = "MONOLITH"
    MICROSERVICES = "MICROSERVICES"


class RepoStrategy(str, Enum):
    MONOREPO = "MONOREPO"
    REPO_PER_SERVICE = "REPO_PER_SERVICE"


class RepoMode(str, Enum):
    # repoStrategy == REPO_PER_SERVICE 일 때만 의미가 있다.
    SPLIT_GIT = "SPLIT_GIT"          # git 을 신규 레포로 쪼갬
    REUSE_EXISTING = "REUSE_EXISTING"  # 이미 있는 레포를 재사용


class ArchitectureAspect(str, Enum):
    DEPLOYMENT_ENV = "DEPLOYMENT_ENV"
    INGRESS = "INGRESS"
    SERVICE_MESH_FRAMEWORK = "SERVICE_MESH_FRAMEWORK"
    FRONTEND = "FRONTEND"
    REPO_MAPPING = "REPO_MAPPING"
    # 다수 BoundedContext(서비스)일 때 추가로 결정되는 항목들.
    INTER_CONTEXT_INTEGRATION = "INTER_CONTEXT_INTEGRATION"  # 연동 방식(req/res vs pub/sub)
    MESSAGING_CHANNEL = "MESSAGING_CHANNEL"                  # pub/sub 채널 구현(Kafka 등)
    DEV_ENVIRONMENT = "DEV_ENVIRONMENT"                      # 서비스별 개발 환경(Docker 등)


# Plan 완전성(SC-003) 판정에 쓰이는 필수 아키텍처 항목(항상 필수인 5개).
REQUIRED_ARCHITECTURE_ASPECTS = [
    ArchitectureAspect.DEPLOYMENT_ENV.value,
    ArchitectureAspect.INGRESS.value,
    ArchitectureAspect.SERVICE_MESH_FRAMEWORK.value,
    ArchitectureAspect.FRONTEND.value,
    ArchitectureAspect.REPO_MAPPING.value,
]

# 마이크로서비스 + 다수 컨텍스트일 때 추가로 요구되는 항목.
MICROSERVICE_REQUIRED_ASPECTS = [
    ArchitectureAspect.INTER_CONTEXT_INTEGRATION.value,
    ArchitectureAspect.MESSAGING_CHANNEL.value,
    ArchitectureAspect.DEV_ENVIRONMENT.value,
]


class IntegrationKind(str, Enum):
    # ddd-starter Step 5 (Connect) 메시지 분류와 일치.
    EVENT = "EVENT"      # pub/sub, 발신자가 수신자를 모름, 비동기
    COMMAND = "COMMAND"  # 특정 대상 지시
    QUERY = "QUERY"      # 동기 조회 응답


class StatusHistoryEntry(BaseModel):
    from_status: Optional[str] = None
    to_status: str
    actor: str
    at: str
    comment: Optional[str] = None


class StrategicDiffEntry(BaseModel):
    # extra="allow": 스킬이 emit 하는 계층 참조(tempId / epicId / featureId /
    # boundedContextId)와 UserStory 의 role/action/benefit 등 부가 필드를
    # 그대로 보존해 프런트의 BC→Feature→UserStory 중첩 렌더가 가능하게 한다.
    # (선언하지 않으면 직렬화 시 누락되어 계층 연결이 끊긴다.)
    model_config = ConfigDict(extra="allow")

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


class ConstitutionFields(BaseModel):
    """타깃 프로젝트 Constitution 파일에서 파싱한 핵심 결정값."""
    designPrinciples: Optional[str] = None
    techStack: Optional[str] = None
    architectureStyle: Optional[ArchitectureStyle] = None
    repoStrategy: Optional[RepoStrategy] = None
    repoMode: Optional[RepoMode] = None


class ConstitutionResponse(BaseModel):
    exists: bool
    raw: Optional[str] = None
    fields: ConstitutionFields = ConstitutionFields()
    constitutionHash: Optional[str] = None
    # 인터뷰가 프롬프트에서 시드한 근거(FR-002a) / 적합성 추천(FR-002b).
    seededFrom: list[str] = []
    recommendations: list[dict] = []


class ArchitectureDecision(BaseModel):
    aspect: str  # ArchitectureAspect 값 또는 확장 항목
    decision: str
    rationale: Optional[str] = None
    constitutionRef: Optional[str] = None  # None ⇒ gap 으로 표시


class InterContextIntegration(BaseModel):
    """두 BoundedContext(서비스) 간 연동 1건. ddd-starter Step 5(Connect) 기반."""
    fromContext: str
    toContext: str
    message: str                      # 예: OrderConfirmed, ChargePayment, GetCustomerCredit
    kind: IntegrationKind             # EVENT(pub/sub) | COMMAND | QUERY
    sync: bool = False                # 동기 응답 필요 여부
    rationale: Optional[str] = None   # 왜 이 패턴인지(의도 분석 결과)


class ServiceDevEnvironment(BaseModel):
    """마이크로서비스 1개의 개발 환경 — 멀티레포 전환 시 각 개발자가 자기 것만 가져가도록 범위 제한."""
    service: str                       # 서비스/BoundedContext 이름
    runtime: Optional[str] = None      # 예: "JDK 21 / Spring Boot 3"
    dockerBaseImage: Optional[str] = None  # 예: "eclipse-temurin:21-jre"
    dependencies: list[str] = []       # 이 서비스에 한정된 인프라 의존(예: ["kafka", "postgres"])
    composeServices: list[str] = []    # docker-compose 로 띄울 로컬 의존(이 서비스 범위만)
    scopeNote: Optional[str] = None    # 멀티레포에서 이 개발자가 무엇만 반영하면 되는지


class ImplementationPlan(BaseModel):
    version: int = 1
    architectureDecisions: list[ArchitectureDecision] = []
    constitutionGaps: list[str] = []
    tacticalSummary: Optional[str] = None
    # 다수 BoundedContext 연동(요청/응답 vs pub/sub) — ddd-starter Connect 의도 분석.
    interContextIntegrations: list[InterContextIntegration] = []
    # pub/sub 채널 구현(예: "Kafka"). 이벤트 드리븐 마이크로서비스 기본값.
    messagingChannel: Optional[str] = None
    # 서비스별 개발 환경(Docker 기반, 범위 제한) — 멀티레포 대비.
    serviceDevEnvironments: list[ServiceDevEnvironment] = []
    # 어떤 Constitution / Strategic Diff 버전 위에서 만들었는지(staleness 판정).
    constitutionHash: Optional[str] = None
    strategicVersion: int = 1

    def is_complete(self, architecture_style: Optional[str] = None,
                    context_count: int = 1) -> bool:
        """필수 아키텍처 항목이 모두 결정되었거나 gap 으로 명시되었는가(SC-003).

        마이크로서비스 + 다수 컨텍스트이면 연동/채널/개발환경 항목도 요구한다.
        """
        covered = {d.aspect for d in self.architectureDecisions} | set(self.constitutionGaps)
        required = list(REQUIRED_ARCHITECTURE_ASPECTS)
        if architecture_style == ArchitectureStyle.MICROSERVICES.value and context_count > 1:
            required += MICROSERVICE_REQUIRED_ASPECTS
        return all(a in covered for a in required)


# --- 042: Staged DDD decomposition mode -------------------------------------

class DecompositionMode(str, Enum):
    SIMPLIFIED = "SIMPLIFIED"       # 현행 Intent→Plan
    DETAILED_DDD = "DETAILED_DDD"   # ddd-starter 6단계 walkthrough


class DddStage(str, Enum):
    DISCOVER = "DISCOVER"
    DECOMPOSE = "DECOMPOSE"
    STRATEGIZE = "STRATEGIZE"
    CONNECT = "CONNECT"
    DEFINE = "DEFINE"
    TACTICAL = "TACTICAL"


# Detailed 모드 walkthrough 의 정규 스테이지 순서(Understand/Organise 는 범위 외).
DDD_STAGE_ORDER = [
    DddStage.DISCOVER.value, DddStage.DECOMPOSE.value, DddStage.STRATEGIZE.value,
    DddStage.CONNECT.value, DddStage.DEFINE.value, DddStage.TACTICAL.value,
]

# 행위 변경 Proposal 에서 절대 완전 생략 불가한 스테이지(ddd-starter 규칙, FR-014).
NON_OMITTABLE_STAGES = {DddStage.DISCOVER.value}


class StagePlanItem(BaseModel):
    stage: DddStage
    applies: bool = True
    recommendSkip: bool = False
    skipped: bool = False           # 아키텍트 최종 결정
    reason: str = ""                # 권고 한 줄 사유(FR-010/FR-015)


class StagePlan(BaseModel):
    version: int = 1
    stages: list[StagePlanItem] = []
    classifiedReach: Optional[str] = None   # "single-BC tactical change" 등 사람용 요약


class MemoryConflict(BaseModel):
    bcId: Optional[str] = None
    field: str                       # 예: "classification", "couplingPosture"
    memoryValue: str
    proposalValue: str
    resolution: str = "UNRESOLVED"   # AMEND_MEMORY | JUSTIFY_LOCAL | UNRESOLVED (FR-019)
    justification: Optional[str] = None


class StageArtifact(BaseModel):
    """스테이지별 리뷰 산출물의 느슨한 컨테이너.

    스테이지마다 형태가 다르므로(data-model.md §1) extra='allow' 로 두고 `stage` 로
    판별한다. 구조 검증(필수 필드/최소 개수)은 각 스테이지 러너/스킬이 책임진다.
    """
    model_config = ConfigDict(extra="allow")
    stage: DddStage


class ContextStrategy(BaseModel):
    model_config = ConfigDict(extra="allow")
    classification: Optional[str] = None      # CORE | SUPPORTING | GENERIC
    rationale: Optional[str] = None
    buildVsBuy: Optional[str] = None
    ubiquitousLanguage: list[dict] = []       # [{term, definition}]
    businessDecisions: list[str] = []
    purpose: Optional[str] = None
    domainRoles: list[str] = []


class StrategicMemory(BaseModel):
    """지속 DDD 전략 메모리. Constitution 노드의 strategicMemory 속성에 적재.

    프로젝트 루트 노드: differentiation/couplingPosture(+contexts) — BC 노드: contexts 만.
    """
    model_config = ConfigDict(extra="allow")
    version: int = 1
    differentiation: Optional[dict] = None    # {valueProposition, personas[], differentiator}  (루트)
    couplingPosture: Optional[dict] = None     # {default: PUBSUB|SYNC, rationale, pairs[]}       (루트)
    contexts: dict[str, ContextStrategy] = {}  # bcKey → ContextStrategy                          (BC)


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
    implementationPlan: Optional[ImplementationPlan] = None
    constitutionHash: Optional[str] = None
    planStale: bool = False
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
    # 042 — Staged DDD decomposition mode.
    decompositionMode: DecompositionMode = DecompositionMode.SIMPLIFIED
    stagePlan: Optional[StagePlan] = None
    stageArtifacts: Optional[dict] = None       # {stage → artifact}
    currentStage: Optional[str] = None
    memoryConflicts: Optional[list[MemoryConflict]] = None

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

        raw_plan = _parse_json(node.get("implementationPlan"), None)
        impl_plan = None
        if raw_plan:
            try:
                impl_plan = ImplementationPlan(**raw_plan)
            except Exception:
                impl_plan = None

        constitution_hash = node.get("constitutionHash")
        # planStale 은 파생값: plan 이 만들어진 뒤 Constitution 또는 Strategic Diff 가
        # 바뀌면 True. 저장된 plan 의 스냅샷 해시/버전과 현재 노드 상태를 비교한다.
        plan_stale = False
        if impl_plan is not None:
            strat_version = strategic.version if strategic else 1
            if impl_plan.constitutionHash and constitution_hash and \
                    impl_plan.constitutionHash != constitution_hash:
                plan_stale = True
            if strat_version > (impl_plan.strategicVersion or 1):
                plan_stale = True

        accepted_at = node.get("acceptedAt")
        destroyed_at = node.get("destroyedAt")

        # 042 — staged DDD 상태.
        raw_stage_plan = _parse_json(node.get("stagePlan"), None)
        stage_plan = None
        if raw_stage_plan:
            try:
                stage_plan = StagePlan(**raw_stage_plan)
            except Exception:
                stage_plan = None
        stage_artifacts = _parse_json(node.get("stageArtifacts"), None)
        raw_conflicts = _parse_json(node.get("memoryConflicts"), None)
        mem_conflicts = None
        if raw_conflicts:
            mem_conflicts = []
            for c in raw_conflicts:
                try:
                    mem_conflicts.append(MemoryConflict(**c) if isinstance(c, dict) else c)
                except Exception:
                    continue
        try:
            mode = DecompositionMode(node.get("decompositionMode") or "SIMPLIFIED")
        except Exception:
            mode = DecompositionMode.SIMPLIFIED

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
            implementationPlan=impl_plan,
            constitutionHash=constitution_hash,
            planStale=plan_stale,
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
            decompositionMode=mode,
            stagePlan=stage_plan,
            stageArtifacts=stage_artifacts,
            currentStage=node.get("currentStage"),
            memoryConflicts=mem_conflicts,
        )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateProposalRequest(BaseModel):
    originalPrompt: str
    title: Optional[str] = None
    # 042 — 분해 모드(다이얼로그 스위치). 기본은 현행 빠른 경로.
    decompositionMode: DecompositionMode = DecompositionMode.SIMPLIFIED


class SubmitProposalRequest(BaseModel):
    pass


class AcceptProposalRequest(BaseModel):
    comment: Optional[str] = None
    forceAcceptWithFailures: bool = False


class DestroyProposalRequest(BaseModel):
    reason: Optional[str] = None


class DeleteProposalRequest(BaseModel):
    # 영구 삭제 확인용 — 호출자가 삭제하려는 Proposal id 를 그대로 다시 입력해야 한다.
    # path 의 id 와 일치하지 않으면 거절한다(오삭제 방지).
    confirmId: str


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


# --- 042: staged DDD request bodies -----------------------------------------

class ModeUpgradeRequest(BaseModel):
    decompositionMode: DecompositionMode = DecompositionMode.DETAILED_DDD


class StagePlanItemDecision(BaseModel):
    stage: str
    skipped: bool = False


class ConfirmStagePlanRequest(BaseModel):
    stages: list[StagePlanItemDecision]


class ConflictResolution(BaseModel):
    bcId: Optional[str] = None
    field: str
    resolution: str               # AMEND_MEMORY | JUSTIFY_LOCAL
    justification: Optional[str] = None


class StageConfirmRequest(BaseModel):
    artifact: dict                                  # 아키텍트가 편집한 StageArtifact
    conflictResolutions: list[ConflictResolution] = []


class StageSkipRequest(BaseModel):
    reason: Optional[str] = None


class IntentFeedbackRequest(BaseModel):
    # 인텐트 분해 결과가 의도를 잘못 반영했을 때, 보정할 자연어 피드백.
    feedback: str


class UpdateConstitutionRequest(BaseModel):
    raw: str


class ConstitutionAnswerRequest(BaseModel):
    questionIndex: int
    answer: str


class ConfirmPlanRequest(BaseModel):
    implementationPlan: dict
    tacticalDiff: Optional[list[dict]] = None
    impactMap: Optional[list[dict]] = None


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


def constitution_hash(raw: Optional[str]) -> Optional[str]:
    """Constitution 본문의 SHA-256. staleness 판정에만 쓴다(본문은 타깃 레포 파일이 원천)."""
    if not raw:
        return None
    import hashlib
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
