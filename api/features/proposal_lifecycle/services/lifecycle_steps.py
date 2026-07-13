"""044-followup — 선언적 라이프사이클 스텝 테이블 (Single Source of Truth).

`/robo-proposal` 라이프사이클의 **순서·게이트·검증 참조·전이 가드**를 한 곳에서 선언한다.
`proposal_state_service.next_step()` 과 확정 후 전이(`refresh_current_phase`), 그리고 모든
`save_*`/`confirm_*` 도구의 하드 전이 가드가 모두 이 모듈을 파생 원천으로 사용한다.

설계 원칙(spec Option B):
- 순수 함수 — Neo4j 접근 없음. 입력은 `Proposal` 노드 dict(속성 그대로).
- LLM 이 순서를 추론하지 않는다. 서버가 이 테이블에서 "다음 액션"을 지시한다.
- 신규 Neo4j 라벨/관계 없음(N4). 기존 `Proposal` 속성만 참조.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from api.features.proposal_lifecycle.proposal_contracts import DDD_STAGE_ORDER

# --- 액션 집합(FR-4) --------------------------------------------------------
GENERATE_DRAFT = "generate_draft"
AWAIT_APPROVAL = "await_approval"
CONFIRM = "confirm"
ASK_QUESTION = "ask_question"
RUN_IMPLEMENT = "run_implement"
RUN_TEST = "run_test"
FINALIZE = "finalize"

ALL_ACTIONS = {
    GENERATE_DRAFT, AWAIT_APPROVAL, CONFIRM, ASK_QUESTION,
    RUN_IMPLEMENT, RUN_TEST, FINALIZE,
}

# 재생성 루프 재시도 상한(FR-1b, 조정 가능 상수).
MAX_DRAFT_RETRIES = 3

# DRAFT 상태(status)에서 SUBMIT 스텝이 미완료로 간주되는 유일 값.
STATUS_DRAFT = "DRAFT"
# IMPLEMENT/TEST 완료로 간주되는 진행 상태들.
_IMPLEMENT_DONE_STATUSES = {"TESTING", "PENDING_ACCEPTANCE", "ACCEPTED", "DONE"}
_TEST_DONE_STATUSES = {"PENDING_ACCEPTANCE", "ACCEPTED"}

_STRATEGIC_STAGES = set(DDD_STAGE_ORDER[:3])   # DISCOVER, DECOMPOSE, STRATEGIZE
_TACTICAL_STAGES = set(DDD_STAGE_ORDER[3:])    # CONNECT, DEFINE, TACTICAL


@dataclass(frozen=True)
class StepDef:
    phase: str
    stage: Optional[str]
    action: str
    requires_user_approval: bool
    validation_ref: Optional[str]
    # 사용자 명시 되돌리기(rollback) 대상이 될 수 있는 스텝인지(FR-7b).
    rollback_target: bool = False
    # 되돌릴 때 무효화할 canonical 필드(없으면 None).
    canonical_field: Optional[str] = None

    def key(self) -> tuple[str, Optional[str]]:
        return (self.phase, self.stage)


# --- SIMPLIFIED 정규 순서(FR-6: 전술 게이트가 CONSTITUTION 앞) ----------------
SIMPLIFIED_STEPS: list[StepDef] = [
    StepDef("STRATEGIC_DIFF", None, GENERATE_DRAFT, True, "strategic",
            rollback_target=True, canonical_field="strategicDiff"),
    StepDef("SUBMIT", None, CONFIRM, False, None),
    StepDef("TACTICAL_DIFF", None, GENERATE_DRAFT, True, "tactical",
            rollback_target=True, canonical_field="tacticalDiff"),
    # 015-issue3: 구현계획(implementationPlan) 앞에 **프로젝트 헌장 노드** 게이트.
    # 헌장이 없으면 인터뷰 → :Constitution 노드 생성 → 승인까지 마쳐야 다음으로 간다.
    StepDef("PROJECT_CONSTITUTION", None, GENERATE_DRAFT, True, "project_constitution"),
    StepDef("CONSTITUTION", None, GENERATE_DRAFT, True, "implementation_plan",
            rollback_target=True, canonical_field="implementationPlan"),
    StepDef("TASKS", None, GENERATE_DRAFT, True, "tasks",
            rollback_target=True, canonical_field="tasksJson"),
    StepDef("IMPLEMENT", None, RUN_IMPLEMENT, True, None),
    StepDef("TEST", None, RUN_TEST, True, None),
    StepDef("ACCEPT", None, FINALIZE, True, None),
]

# --- DETAILED_DDD 정규 순서 -------------------------------------------------
DETAILED_STEPS: list[StepDef] = [
    StepDef("SCOPE", None, GENERATE_DRAFT, True, "stage_plan",
            rollback_target=True, canonical_field="stagePlan"),
    StepDef("STRATEGIC_DDD", "DISCOVER", GENERATE_DRAFT, True, "stage_artifact",
            rollback_target=True, canonical_field="stageArtifacts"),
    StepDef("STRATEGIC_DDD", "DECOMPOSE", GENERATE_DRAFT, True, "stage_artifact",
            rollback_target=True, canonical_field="stageArtifacts"),
    StepDef("STRATEGIC_DDD", "STRATEGIZE", GENERATE_DRAFT, True, "stage_artifact",
            rollback_target=True, canonical_field="stageArtifacts"),
    StepDef("STRATEGIC_DIFF", None, GENERATE_DRAFT, True, "strategic",
            rollback_target=True, canonical_field="strategicDiff"),
    StepDef("SUBMIT", None, CONFIRM, False, None),
    StepDef("TACTICAL_DDD", "CONNECT", GENERATE_DRAFT, True, "stage_artifact",
            rollback_target=True, canonical_field="stageArtifacts"),
    StepDef("TACTICAL_DDD", "DEFINE", GENERATE_DRAFT, True, "stage_artifact",
            rollback_target=True, canonical_field="stageArtifacts"),
    StepDef("TACTICAL_DDD", "TACTICAL", GENERATE_DRAFT, True, "stage_artifact",
            rollback_target=True, canonical_field="stageArtifacts"),
    StepDef("TACTICAL_DIFF", None, GENERATE_DRAFT, True, "tactical",
            rollback_target=True, canonical_field="tacticalDiff"),
    StepDef("PROJECT_CONSTITUTION", None, GENERATE_DRAFT, True, "project_constitution"),
    StepDef("CONSTITUTION", None, GENERATE_DRAFT, True, "implementation_plan",
            rollback_target=True, canonical_field="implementationPlan"),
    StepDef("TASKS", None, GENERATE_DRAFT, True, "tasks",
            rollback_target=True, canonical_field="tasksJson"),
    StepDef("IMPLEMENT", None, RUN_IMPLEMENT, True, None),
    StepDef("TEST", None, RUN_TEST, True, None),
    StepDef("ACCEPT", None, FINALIZE, True, None),
]


# --- 파싱 헬퍼 --------------------------------------------------------------

def _parse(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


def _truthy(raw: Any) -> bool:
    # 불리언/숫자는 JSON 파싱 대상이 아니다(json.loads(True) 는 TypeError → 오탐 False).
    if isinstance(raw, bool):
        return raw
    value = _parse(raw, None)
    if isinstance(value, (dict, list)):
        return len(value) > 0
    return bool(value)


def normalize_mode(mode: str | None) -> str:
    normalized = (mode or "SIMPLIFIED").strip().upper()
    if normalized == "DETAILED":
        normalized = "DETAILED_DDD"
    return normalized


def steps_for(mode: str | None) -> list[StepDef]:
    if normalize_mode(mode) == "DETAILED_DDD":
        return DETAILED_STEPS
    return SIMPLIFIED_STEPS


def _mode_of(node: dict) -> str:
    return normalize_mode(node.get("decompositionMode"))


# --- stagePlan 활성 스테이지 -------------------------------------------------

def active_stages(stage_plan: Any) -> list[str]:
    """플랜에서 (적용되고 생략되지 않은) 스테이지를 정규 순서대로."""
    plan = _parse(stage_plan, None)
    if not plan:
        return list(DDD_STAGE_ORDER)
    by_stage = {i.get("stage"): i for i in plan.get("stages", [])}
    out: list[str] = []
    for s in DDD_STAGE_ORDER:
        item = by_stage.get(s)
        if item is None:
            continue
        if item.get("applies", True) and not item.get("skipped", False):
            out.append(s)
    return out


def active_steps(node: dict) -> list[StepDef]:
    """이 노드에 대해 실제로 밟게 되는 스텝(스킵된 DDD 스테이지는 제외)."""
    mode = _mode_of(node)
    stage_active = set(active_stages(node.get("stagePlan")))
    out: list[StepDef] = []
    for step in steps_for(mode):
        if step.stage is not None and step.stage not in stage_active:
            continue
        out.append(step)
    return out


# --- 완료 판정 --------------------------------------------------------------

def is_complete(node: dict, step: StepDef) -> bool:
    phase, stage = step.phase, step.stage
    if stage is not None:
        arts = _parse(node.get("stageArtifacts"), {}) or {}
        return stage in arts
    if phase == "SCOPE":
        return _truthy(node.get("stagePlan"))
    if phase == "STRATEGIC_DIFF":
        return _truthy(node.get("strategicDiff"))
    if phase == "SUBMIT":
        return (node.get("status") or STATUS_DRAFT) != STATUS_DRAFT
    if phase == "TACTICAL_DIFF":
        return _truthy(node.get("tacticalDiff"))
    if phase == "PROJECT_CONSTITUTION":
        # 프로젝트 루트 :Constitution 노드 존재 여부의 투영(proposal_state_service 가 동기화).
        return _truthy(node.get("constitutionConfirmed"))
    if phase == "CONSTITUTION":
        return _truthy(node.get("implementationPlan"))
    if phase == "TASKS":
        return _truthy(node.get("tasksJson"))
    if phase == "IMPLEMENT":
        status = node.get("status") or ""
        return status in _IMPLEMENT_DONE_STATUSES or (node.get("implementationStatus") or "").upper() == "DONE"
    if phase == "TEST":
        return _truthy(node.get("testResults")) or (node.get("status") or "") in _TEST_DONE_STATUSES
    if phase == "ACCEPT":
        return (node.get("status") or "") == "ACCEPTED"
    return False


def next_incomplete_step(node: dict) -> Optional[StepDef]:
    """정규 순서상 아직 완료되지 않은 첫 스텝(없으면 None = 모두 완료)."""
    for step in active_steps(node):
        if not is_complete(node, step):
            return step
    return None


def step_for(mode: str | None, phase: str, stage: str | None = None) -> Optional[StepDef]:
    target = (phase or "").strip().upper()
    target_stage = (stage or None)
    if target_stage:
        target_stage = target_stage.strip().upper()
    for step in steps_for(mode):
        if step.phase == target and step.stage == target_stage:
            return step
    # stage 미지정 phase 매칭(예: STRATEGIC_DDD 는 stage 로 구분되므로 첫 활성 반환 안 함)
    for step in steps_for(mode):
        if step.phase == target and target_stage is None and step.stage is None:
            return step
    return None


# --- 전이 가드(FR-7) --------------------------------------------------------

def prior_requirement_unmet(node: dict, phase: str, stage: str | None = None) -> bool:
    """(phase, stage) 스텝의 **직전 필수 스텝**이 미완료이면 True(하드 차단).

    앞으로 건너뛰기를 막는다. 대상 스텝 자체의 미완료는 정상이므로 검사하지 않는다.
    대상 스텝을 찾지 못하면(범위 밖) 차단하지 않는다.
    """
    steps = active_steps(node)
    target = (phase or "").strip().upper()
    target_stage = stage.strip().upper() if stage else None
    idx = None
    for i, step in enumerate(steps):
        if step.phase == target and (step.stage == target_stage or (target_stage is None and step.stage is None)):
            idx = i
            break
    if idx is None:
        return False
    for step in steps[:idx]:
        if not is_complete(node, step):
            return True
    return False


# --- 되돌리기 대상(FR-7b) ---------------------------------------------------

def rollback_targets(node: dict) -> list[dict]:
    """현재 진행 지점 이전의, 이미 완료된 rollback 가능 스텝 목록."""
    steps = active_steps(node)
    current = next_incomplete_step(node)
    out: list[dict] = []
    for step in steps:
        if current is not None and step.key() == current.key():
            break
        if not is_complete(node, step):
            break
        if step.rollback_target:
            out.append({"phase": step.phase, "stage": step.stage})
    return out


def downstream_of(node: dict, phase: str, stage: str | None = None) -> list[StepDef]:
    """(phase, stage) 이후의 모든 스텝(되돌리기 시 무효화 대상 산출)."""
    steps = active_steps(node)
    target = (phase or "").strip().upper()
    target_stage = stage.strip().upper() if stage else None
    idx = None
    for i, step in enumerate(steps):
        if step.phase == target and (step.stage == target_stage or (target_stage is None and step.stage is None)):
            idx = i
            break
    if idx is None:
        return []
    return steps[idx + 1:]
