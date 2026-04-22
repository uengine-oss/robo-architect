"""Cross-process arbitration — the missing final step of agentic retrieval.

The per-process `agent_validator` runs in isolation: each process's LLM call
has no knowledge of other processes. A rule that looks like a plausible fit
in `자동납부 신청` ALSO looks plausible in `자동납부 해지` when viewed
independently, so both validators happily accept it.

This module adds a second-pass LLM that sees ALL competing process claims
for a single rule at once and picks the TRUE home — or rejects all claims
if the rule is a genuinely cross-cutting utility not tied to one process.

Shape (see 개선&재구조화.md §1 "원인 B"):
    for each rule accepted by >1 processes:
        ask LLM, given the rule + each (process, task, per-process rationale):
            {home_process_id, home_task_id, rationale}  OR
            {reject: true, rationale: "cross-cutting utility"}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.features.ingestion.hybrid.contracts import (
    BpmProcess,
    BpmTaskDTO,
    RuleContext,
    RuleDTO,
)
from api.features.ingestion.ingestion_llm_runtime import get_llm


_SYSTEM_PROMPT = """당신은 업무 프로세스와 Business Logic 의 최종 귀속을 판정하는 분석가입니다.

한 Business Logic(BL) 에 대해 하나 이상의 **프로세스** 가 "이 BL 은 우리 프로세스의 Task X 에 속한다" 고 주장하고 있습니다.
각 주장에는 프로세스 이름, 해당 프로세스의 Task 이름, 그 프로세스 수준의 판단 근거(rationale), 그리고 **module_confidence** (이 프로세스와 BL 이 속한 코드 모듈 사이의 임베딩 유사도) 가 있습니다.

당신의 일: 이 BL 의 **진짜 본거지(home)** 를 정하거나, 어느 주장도 맞지 않으면 reject.

원칙:
1. BL 은 대개 **단 하나의 프로세스** 의 **단 하나의 Task** 에 속합니다.
   코드 함수가 여러 프로세스에서 공유되어도 BL 자체는 원래 어느 프로세스의 어느
   단계를 수행하려고 작성됐는지 를 기준으로 귀속.

2. **판정 우선순위 (가장 중요)**:
   (1) Stage / 업무 단계 매치 = **primary**
   (2) BL semantics(GIVEN/WHEN/THEN, 함수명, function_summary) 와 task 의미의 부합도 = **primary**
   (3) module_confidence 수치 = **타이브레이커 전용 (secondary)**
   **module_confidence 차이가 0.05 미만이면 수치 차이는 무시하고, stage/semantic 부합만으로 결정하세요.**
   예: 조회 0.618 vs 신청 0.599 (차이 0.019) 인데 BL 이 "신청 단계 입력 검증" 이면 조회가 수치상 높아도 **신청** 을 선택.

3. **Stage 매치 판정 가이드 (정면 불일치면 reject)**:
   - **신청/등록/insert** stage: BL 이 create 성 로직 (필수값 검증, 초기값 설정, INSERT) 이면 신청/등록 쪽 task 에 귀속.
   - **조회/read-only** stage: BL 이 SELECT 만 하고 write 를 안 하는 경우만 조회 쪽 task 에 귀속. **"조회 요청의 입력값 검증" 같은 표현에 속지 마세요** — 조회 요청을 받는 task 는 단순히 요청을 수령하는 단계일 뿐, 신청 전용의 "업무구분 보정", "원장등록 플래그 초기화" 같은 create-path 보정 로직과는 다른 단계입니다.
   - **해지/delete** stage: BL 이 unbind / 이력 말소 / 외부 통보 이면 해지 쪽.
   - **판정/이력적재/메시지 조립**: BL 의 기능 동사로 판단 — "판정한다" / "저장한다(INSERT/UPDATE)" / "조립한다(메시지 생성)".

4. **module_confidence 3-밴드 (타이브레이커 기준)**:
   - 0.60 이상: 코드 구현 가능성 높음.
   - 0.55 ~ 0.60: 경계. stage/semantic 이 명백히 맞을 때만 의미 있음.
   - 0.55 미만: 사실상 "이 프로세스는 이 모듈에 구현되지 않음". default reject.

5. **reject 해야 하는 케이스**:
   (a) BL 이 순수 기술 유틸리티(로깅/직렬화/공통 헬퍼).
   (b) 모든 주장이 stage 불일치거나 semantic 부합이 약함.
   (c) 모든 주장의 module_confidence 가 낮고 (< 0.60) stage/semantic 도 약함.

6. 여러 주장 중 **하나만** home. 판정 근거는 구체 증거(함수명/부모모듈/stage/rationale 키워드) 포함.
7. **단일 주장 재판정** 시: module_confidence 낮으면 stage/semantic 이 완벽할 때만 accept, 아니면 reject.
"""


class ArbitrationVerdict(BaseModel):
    reject: bool = Field(default=False, description="true 면 어느 프로세스에도 귀속 안 함")
    home_process_id: Optional[str] = Field(default=None, description="선택한 프로세스 id (reject 아닐 때)")
    home_task_id: Optional[str] = Field(default=None, description="선택한 task id (reject 아닐 때)")
    rationale: str = Field(description="판정 근거 1~2 문장 (한국어)")


@dataclass
class ClaimEntry:
    """One (process, task, rationale) claim for a rule from the per-process validator."""

    process: BpmProcess
    task: BpmTaskDTO
    rationale: str
    score: float
    # Top-1 module cosine for this process (§2.B P3). Low values
    # (<0.55) flag "this process probably doesn't implement this module" —
    # the arbitrator down-weights such claims and may reject single-claim
    # matches outright.
    module_confidence: float = 1.0


# Below this module confidence, a single-claim rule is still routed through
# the arbitrator (instead of auto-accepted) to second-guess whether the
# validator over-reached. Same calibration as MIN_MODULE_CONFIDENCE but
# slightly stricter — leaves a safety margin for marginal Step-1 hits.
SINGLE_CLAIM_ARBITRATION_THRESHOLD = 0.60


def _format_rule(rule: RuleDTO, ctx: Optional[RuleContext]) -> str:
    lines = [
        f"rule_id: {rule.id}",
        f"title: {rule.title or '(없음)'}",
        f"given: {rule.given}",
        f"when:  {rule.when}",
        f"then:  {rule.then}",
        f"source_function: {rule.source_function or '(없음)'}",
        f"source_module:   {rule.source_module or '(없음)'}",
    ]
    if ctx:
        if ctx.function_summary:
            lines.append(f"function_summary: {ctx.function_summary}")
        if ctx.parent_module:
            lines.append(f"parent_module: {ctx.parent_module}")
        if ctx.callers:
            lines.append(f"callers: {', '.join(ctx.callers[:5])}")
    return "\n".join(lines)


def _format_claim(i: int, c: ClaimEntry) -> str:
    lines = [
        f"[후보 {i}]",
        f"  process_id: {c.process.id}",
        f"  process_name: {c.process.name}",
        f"  process_keywords: {', '.join(c.process.domain_keywords or []) or '(없음)'}",
        f"  task_id: {c.task.id}",
        f"  task_name: {c.task.name}",
        f"  task_description: {c.task.description or '(없음)'}",
        f"  module_confidence: {c.module_confidence:.3f}",
        f"  per_process_rationale: {c.rationale}",
    ]
    return "\n".join(lines)


async def arbitrate_rule_home(
    rule: RuleDTO,
    ctx: Optional[RuleContext],
    claims: list[ClaimEntry],
) -> ArbitrationVerdict:
    """Ask the LLM which competing process+task is the rule's true home.

    Returns reject=True if the rule is a cross-cutting utility that doesn't
    belong to any single process.
    """
    if not claims:
        return ArbitrationVerdict(reject=True, rationale="No claims to arbitrate")
    if len(claims) == 1:
        c = claims[0]
        # §2.B P3 — If the only claimant has high module confidence we
        # trust the per-process validator and skip an extra LLM call.
        # If module_confidence is low (< SINGLE_CLAIM_ARBITRATION_THRESHOLD),
        # we still route through the arbitrator so the LLM can catch
        # "this process doesn't implement this module — validator was
        # too permissive" cases.
        if c.module_confidence >= SINGLE_CLAIM_ARBITRATION_THRESHOLD:
            return ArbitrationVerdict(
                reject=False,
                home_process_id=c.process.id,
                home_task_id=c.task.id,
                rationale=c.rationale,
            )
        # Fall through to LLM call below with a single-claim prompt shape.

    rule_block = _format_rule(rule, ctx)
    claim_blocks = "\n\n".join(_format_claim(i + 1, c) for i, c in enumerate(claims))
    if len(claims) == 1:
        header = (
            f"--- 단일 주장 재판정 (module_confidence={claims[0].module_confidence:.3f} 낮음) ---\n"
            "이 프로세스의 코드가 이 모듈에 구현되어 있지 않을 가능성이 있습니다. "
            "그럼에도 BL 의 의미가 이 Task 에 정말 부합하는지, 아니면 validator 가 오남용한 것인지 판정하세요.\n"
        )
    else:
        header = f"--- {len(claims)} 개 프로세스가 이 BL 을 자기 Task 로 주장하는 중 ---\n"
    user = (
        f"--- Business Logic ---\n{rule_block}\n\n"
        f"{header}\n"
        f"{claim_blocks}\n\n"
        f"이 BL 의 진짜 home 을 하나만 고르거나, 어느 프로세스에도 귀속하기 부적절하면 reject=true."
    )
    structured = get_llm().with_structured_output(ArbitrationVerdict)
    verdict: ArbitrationVerdict = await structured.ainvoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user),
    ])

    # Defensive: validate the returned ids belong to the claim set.
    if not verdict.reject:
        valid_pairs = {(c.process.id, c.task.id) for c in claims}
        if (verdict.home_process_id, verdict.home_task_id) not in valid_pairs:
            # LLM hallucinated an id — fall back to first claim.
            c = claims[0]
            return ArbitrationVerdict(
                reject=False,
                home_process_id=c.process.id,
                home_task_id=c.task.id,
                rationale=verdict.rationale or c.rationale,
            )
    return verdict
