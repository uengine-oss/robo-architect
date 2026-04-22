"""Hierarchical Agentic Retrieval — Step 3: Agentic Validator.

Given a `BpmProcess`, a target `BpmTask`, and a pre-filtered list of BL
candidates (Step 2 output), ask the LLM — with Cypher-fetched parent
context injected into the prompt — to judge which candidates truly
realize this process's task. One LLM call per Task, all candidates
batched (§C in docs/legacy-ingestion/개선&재구조화.md).

This is NOT an autonomous tool-calling agent — the project uses the
`with_structured_output(PydanticSchema)` convention throughout; matching
that keeps one coherent LLM path. The "agent reasoning" UX (§2.C) is
driven by us emitting SSE events around these deterministic steps.
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
from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session


_SYSTEM_PROMPT = """당신은 레거시 코드의 Business Logic 과 업무 프로세스 Task 를 정확히 매핑하는 분석가입니다.

입력으로 하나의 업무 프로세스와 그 프로세스의 Task 하나, 그리고 Task 후보 Business Logic(BL) 목록을 받습니다.
각 BL 에는 그것이 속한 함수/모듈/호출 체인(부모 노드 정보) 이 함께 주어집니다.

당신의 일은 각 후보 BL 이 이 **특정 프로세스** 의 이 **특정 Task** 에 진짜로 해당하는지 판단하는 것입니다.

**판정 철학 (중요)**:
- 숫자 제한은 없습니다. 정당한 매핑은 **모두** accept 하세요.
- 한 Task 가 코드 상 10 개 분기 rule 로 구현되어 있으면 10 개 전부 accept 하는 것이 옳습니다
  (예: b000_main_proc 의 여러 인증 유형별 반영여부 결정 분기들이 모두 "실시간 인증결과 판정" task 에 속함).
- 반대로 의미가 어긋나면 1 개도 accept 하지 마세요.
- 기준은 "숫자" 가 아니라 "각 BL 의 의미가 이 Task 에 정말 속하는가" 입니다.

판정 기준:
1. Task 와 BL 의 의미 축이 **같은 방향** 이면 accept:
   - Task "입력값 검증" ↔ BL "입력 필수값 확인 / 형식 검증 / 기본값 세팅 / 거부 조건"
   - Task "결과 판정" ↔ BL "결과 코드 해석 / 반영/미반영 결정 / 분기별 판정"
   - Task "이력 생성/갱신" ↔ BL "DB 에 이력 INSERT/UPDATE"
   - Task "오류 메시지 조립" ↔ BL "오류 코드 → 메시지 변환 / 메시지 조합"
2. **동일 프로세스 내 여러 Task 에 걸치면 (매우 중요)**: 가장 본질적 Task 하나만 accept, 부차적 Task 에서는 **무조건 reject**. 둘 다 accept 하면 후단 파이프라인이 embedding score 로 자동 선택해버려 의도한 task 귀속이 깨집니다.
   - 본질 Task 판정 기준: **BL 의 동사가 가리키는 단계**.
     · "저장한다 / INSERT / UPDATE" 동사 → **이력 적재 / 등록** 류 task (결코 "실시간 인증" 같은 상위 task 아님).
     · "판정한다 / 결정한다 / 반영여부=X" 동사 → **결과 판정** 류.
     · "메시지를 만든다 / 오류코드 부여" 동사 → **메시지 조립** 류.
     · "검증한다 / 필수값 확인 / 거부한다" 동사 → **입력값 검증** 류.
   - 예 1: "SKB 외부인증 성공코드면 반영한다" 의 본질 동사는 "반영한다(판정)" → **판정** task 에 accept, "이력 적재" 에서는 reject.
   - 예 2: "외부인증 요청은 인증결과와 반영 플래그를 고정값으로 저장한다" 의 본질 동사는 "저장한다(INSERT)" → **이력 적재** task 에 accept, "신규 수단 실시간 인증" 같은 상위 task 에서는 reject (BL 이 상위 task 의 일부로 호출되더라도 BL 자체의 일은 이력 적재임).
   - Task 이름이 추상적 (예: "신규 수단 실시간 인증") 이고 BL 이 구체적 DB 조작(INSERT) 이면, 더 구체적인 task (예: "실시간 인증이력 적재") 가 있는지 살펴보고 그 쪽을 고르세요.
3. BL 의 부모 모듈/함수 이름이 프로세스 도메인과 **정반대**(예: 해지 프로세스에 신청 전용 함수) 일 때 reject. 같은 모듈/프로세스 내면서 Task 축이 겹치면 accept.
4. 명백한 기술 유틸리티(getConnection, 로깅 등)는 reject. 업무 로직이면 기본적으로 accept 검토.
5. **Process-domain 충돌 필터 (가장 중요)**: Process 의 domain_keywords / process.name 과 BL 의 source_function / function_summary 가 **서로 다른 업무 단계** 를 가리키면 무조건 reject. 단어만 비슷하다고 연결하지 마세요.
   - 예: Process = "자동납부 **해지**", BL = a000_input_validation 의 "간편결제 **신청** 시 고객번호 필수" → **reject**. "입력 검증" 이라는 단어만으로 끌어오면 안 됨. 해지 요청의 입력은 해지 사유/청구번호이지, 신규 수단의 고객번호가 아님.
   - 예: Process = "자동납부 **조회**", BL = "실시간 인증 결과 **INSERT**" → **reject**. 조회는 읽기 단계, BL 은 쓰기 단계.
6. **트리거 맥락 불일치 필터**: BL 의 function_summary 가 설명하는 "언제 호출되는가" (예: "자동납부 신청 요청 수신 시", "실시간 인증 응답 도착 시") 가 현재 Task 의 시점과 다르면 reject.
   - function_summary 에 "신청/등록/insert/요청 접수" 등 create 성 단어가 있는 BL 을 update/delete 성 Task 에 붙이지 마세요 (역도 동일).
7. **애매하면 reject** — process 단계 맥락이 확실히 맞을 때만 accept. (이전 버전의 "애매하면 accept" 는 cross-process 오염을 유발해 폐기.)

출력 규칙:
- 각 BL 에 verdict ∈ {accept, reject} + rationale(1~2 문장, 한국어).
- rationale 에는 반드시 증거 (모듈명/함수명/summary 키워드) 포함.
- reject 시 **어떤 단계/시점 불일치인지** 를 rationale 에 명시 (예: "BL 은 신청 단계 입력 검증인데 Task 는 해지 단계 요청 접수").
- **accept 개수 제한 없음**. 정당한 모든 매핑을 살리는 것이 목표.
"""


class ValidationVerdict(BaseModel):
    rule_id: str
    verdict: str = Field(description="accept 또는 reject")
    rationale: str = Field(description="판단 근거 1~2 문장 (한국어)")
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="rationale 에서 언급한 모듈/함수/호출자 식별자들",
    )


class _ValidationResult(BaseModel):
    verdicts: list[ValidationVerdict] = Field(default_factory=list)


@dataclass
class CandidateBL:
    """Step 2 output entry — a rule + its analyzer-graph context."""

    rule: RuleDTO
    context: RuleContext


# ---------------------------------------------------------------------------
# Parent-chain fetch — runs ONCE per Task before the LLM call. Feeds rationale.
# ---------------------------------------------------------------------------


def _fetch_parent_chains(fn_names: list[str]) -> dict[str, dict]:
    """Cypher pre-fetch: for each source function, look up one-hop callers,
    owning module, and owning package — enough for the LLM to gauge whether
    a rule belongs to the Process in question.

    Same query shape as `rule_context.build_rule_contexts` but scoped tight
    to the parent-chain fields the validator needs.
    """
    if not fn_names:
        return {}
    out: dict[str, dict] = {}
    try:
        with get_session(database=ANALYZER_NEO4J_DATABASE) as s:
            for rec in s.run(
                """
                UNWIND $fn_names AS fn
                MATCH (f)
                WHERE coalesce(f.procedure_name, f.name) = fn
                OPTIONAL MATCH (caller)-[:CALLS]->(f)
                OPTIONAL MATCH (mod)-[:HAS_FUNCTION]->(f)
                OPTIONAL MATCH (mod)-[:BELONGS_TO_PACKAGE]->(pkg:PACKAGE)
                WITH fn, f,
                     collect(DISTINCT coalesce(caller.procedure_name, caller.name)) AS callers,
                     collect(DISTINCT coalesce(mod.name, mod.procedure_name)) AS mods,
                     collect(DISTINCT pkg.name) AS pkgs
                RETURN fn,
                       f.summary AS summary,
                       [c IN callers WHERE c IS NOT NULL] AS callers,
                       head([m IN mods WHERE m IS NOT NULL]) AS module,
                       head([p IN pkgs WHERE p IS NOT NULL]) AS package
                """,
                fn_names=fn_names,
            ):
                out[rec["fn"]] = {
                    "summary": rec.get("summary"),
                    "callers": rec.get("callers") or [],
                    "module": rec.get("module"),
                    "package": rec.get("package"),
                }
    except Exception:
        return out
    return out


def _format_candidate_for_prompt(
    idx: int, candidate: CandidateBL, chain: Optional[dict],
) -> str:
    r = candidate.rule
    ctx = candidate.context
    lines = [
        f"[{idx}] rule_id: {r.id}",
        f"    title: {r.title or '(없음)'}",
        f"    given: {r.given}",
        f"    when:  {r.when}",
        f"    then:  {r.then}",
        f"    source_function: {r.source_function or '(없음)'}",
        f"    source_module:   {r.source_module or '(없음)'}",
    ]
    summary = (chain or {}).get("summary") or ctx.function_summary
    if summary:
        lines.append(f"    function_summary: {summary}")
    callers = (chain or {}).get("callers") or ctx.callers
    if callers:
        lines.append(f"    callers: {', '.join(callers[:8])}")
    callees = ctx.callees
    if callees:
        lines.append(f"    callees: {', '.join(callees[:8])}")
    module = (chain or {}).get("module") or ctx.parent_module
    package = (chain or {}).get("package") or ctx.parent_package
    if module:
        lines.append(f"    parent_module: {module}")
    if package:
        lines.append(f"    parent_package: {package}")
    if ctx.context_cluster:
        lines.append(f"    context_cluster: {ctx.context_cluster}")
    return "\n".join(lines)


async def validate_candidates(
    process: BpmProcess,
    task: BpmTaskDTO,
    candidates: list[CandidateBL],
    *,
    sibling_tasks: Optional[list[BpmTaskDTO]] = None,
) -> list[ValidationVerdict]:
    """One LLM call → verdict per candidate. Empty candidates → empty list.

    `sibling_tasks` gives the LLM visibility into *other* tasks in the same
    process so it can apply rule 2 ("pick the most essential task, reject
    the rest") meaningfully. Without this context the validator has no
    menu of alternatives and over-accepts on adjacent tasks, which the
    downstream cross-task dedup then resolves by raw embedding score —
    often picking the wrong task (e.g., "신규 수단 실시간 인증" beats
    "실시간 인증이력 적재" for INSERT rules).
    """
    if not candidates:
        return []

    # Pre-fetch parent chains for all distinct functions referenced.
    fn_names = sorted({
        c.rule.source_function for c in candidates if c.rule.source_function
    })
    chains = _fetch_parent_chains(fn_names)

    candidate_blocks = [
        _format_candidate_for_prompt(i + 1, c, chains.get(c.rule.source_function or ""))
        for i, c in enumerate(candidates)
    ]

    siblings_block = ""
    if sibling_tasks:
        sibling_lines = []
        for st in sibling_tasks:
            if st.id == task.id:
                continue
            line = f"  - {st.name}"
            if st.description:
                desc = st.description.strip().splitlines()[0][:80]
                line += f" — {desc}"
            sibling_lines.append(line)
        if sibling_lines:
            siblings_block = (
                "\n\n**같은 프로세스의 다른 Task 들** (참고 — BL 이 아래 중 어느 하나에 더 맞으면 현재 Task 에선 reject):\n"
                + "\n".join(sibling_lines)
                + "\n"
            )

    user_prompt = (
        f"프로세스: {process.name}\n"
        f"도메인 키워드: {', '.join(process.domain_keywords or []) or '(없음)'}\n\n"
        f"현재 판정 중인 Task: {task.name}\n"
        f"Task 설명: {task.description or '(없음)'}"
        f"{siblings_block}\n\n"
        f"후보 BL ({len(candidates)} 개):\n\n"
        + "\n\n".join(candidate_blocks)
        + "\n\n각 rule_id 에 대해 verdict 를 결정하고 근거를 작성하세요.\n"
        + "주의: BL 이 현재 Task 와 위의 sibling Task 모두에 부합해 보여도, "
        + "BL 의 핵심 동사 (INSERT/판정/조립/검증) 에 더 가까운 쪽이 sibling 이면 **현재 Task 에선 reject** 하세요."
    )

    structured = get_llm().with_structured_output(_ValidationResult)
    result: _ValidationResult = await structured.ainvoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ])

    # Defensive dedup by rule_id (keep first verdict).
    seen: set[str] = set()
    out: list[ValidationVerdict] = []
    for v in result.verdicts:
        if not v.rule_id or v.rule_id in seen:
            continue
        seen.add(v.rule_id)
        verdict = v.verdict.strip().lower()
        if verdict not in ("accept", "reject"):
            verdict = "reject"
        out.append(ValidationVerdict(
            rule_id=v.rule_id,
            verdict=verdict,
            rationale=v.rationale.strip(),
            evidence_refs=v.evidence_refs or [],
        ))
    return out
