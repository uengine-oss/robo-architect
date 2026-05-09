"""Phase 5 §3.2 — LLM-driven naming layer on top of deterministic candidates.

`decomposer.merge_session_decompositions(...)` produces a SessionDecomposition
that fully describes the *structure* of an Event Storming model (which rules
group into which Aggregate, which task spawns which Commands, etc.) but with
placeholder names. This module asks the LLM to fill in:

  - BC grouping: which UserStories live in which Bounded Context (Korean BC name)
  - Aggregate name: root_table + member fns → Korean domain noun
  - Command displayName: task name + statement → Korean imperative label
  - Event name: aggregate + write op + statement → English PastParticiple + Korean label
  - Policy name: trigger Event + invoke Command + coupled domains → name + Korean desc
  - ReadModel name: source rules + bc → Korean read-model label

Each LLM call is wrapped with a deterministic fallback so the pipeline always
produces *some* names even when the model is unavailable. Reuses the legacy
`IDENTIFY_BC_FROM_STORIES_PROMPT` + `BoundedContextList` for BC grouping
(the legacy prompt already understands "user stories → BC candidates"
without needing rule-internal context). The other namings use compact
Phase-5-specific prompts because the legacy `EXTRACT_AGGREGATES_PROMPT` etc.
are designed to *identify from scratch*, while we already know the structure
and only need names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.features.ingestion.event_storming.prompts import (
    IDENTIFY_BC_FROM_STORIES_PROMPT,
)
from api.features.ingestion.event_storming.structured_outputs import (
    BoundedContextList,
)
from api.features.ingestion.event_storming.state import BoundedContextCandidate
from api.features.ingestion.hybrid.event_storming_bridge.decomposer import (
    CommandCandidate,
    EventCandidate,
    PolicyCandidate,
    ReadModelCandidate,
    SessionAggregate,
    SessionDecomposition,
    UserStoryCandidate,
)
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.observability.smart_logger import SmartLogger


# =============================================================================
# Naming-layer DTOs
# =============================================================================


@dataclass
class BCAssignment:
    """LLM-named Bounded Context with the user_story_ids it owns."""

    key: str                                # slug
    name: str                               # English/canonical short name
    display_name: str                       # Korean UI label
    description: str
    rationale: str = ""
    domain_type: str = "Supporting Domain"  # "Core Domain" | "Supporting Domain" | "Generic Domain"
    user_story_ids: list[str] = field(default_factory=list)


@dataclass
class AggregateName:
    name: str                  # PascalCase domain noun
    display_name: str          # Korean UI label
    bc_key: str                # which BC owns this Aggregate


@dataclass
class CommandName:
    name: str                  # imperative PascalCase
    display_name: str          # Korean imperative label


@dataclass
class EventName:
    name: str                  # PastParticiple PascalCase, e.g. "AuthHistoryRecorded"
    display_name: str          # Korean past-tense label


@dataclass
class PolicyName:
    name: str                  # On{Event}Trigger{Command} or similar
    description: str           # Korean description


@dataclass
class ReadModelName:
    name: str                  # PascalCase
    display_name: str          # Korean UI label


@dataclass
class UserStoryShape:
    """LLM-shaped action + benefit for a UserStory candidate.

    `action` becomes us.action (the 'I want to' clause), `benefit` becomes
    us.benefit (the 'so that' clause). Together with us.role they form the
    canonical As-a / I-want-to / So-that triplet rendered on the canvas.
    """

    action: str
    benefit: str


@dataclass
class NamedSession:
    """Bundle of all LLM-named results, keyed by candidate id / root_table."""

    bcs: list[BCAssignment] = field(default_factory=list)
    aggregate_names: dict[str, AggregateName] = field(default_factory=dict)   # by root_table
    command_names: dict[str, CommandName] = field(default_factory=dict)        # by command id
    event_names: dict[str, EventName] = field(default_factory=dict)            # by event id
    policy_names: dict[str, PolicyName] = field(default_factory=dict)          # by policy id
    read_model_names: dict[str, ReadModelName] = field(default_factory=dict)   # by readmodel id
    user_story_shapes: dict[str, UserStoryShape] = field(default_factory=dict) # by us id


# =============================================================================
# Compact LLM I/O schemas (for non-BC namings — BC reuses legacy schema)
# =============================================================================


class _AggregateNamingOut(BaseModel):
    name: str = Field(description="PascalCase 영문 도메인 명사 (e.g., 'AuthHistory')")
    display_name: str = Field(description="한국어 UI 라벨 (e.g., '실시간인증이력')")


class _CommandNamingOut(BaseModel):
    name: str = Field(description="PascalCase 영문 명령형 (e.g., 'ProcessAuthResult')")
    display_name: str = Field(description="한국어 명령형 짧은 라벨 (e.g., '인증결과 처리')")


class _EventNamingOut(BaseModel):
    name: str = Field(description="PastParticiple PascalCase 영문 (e.g., 'AuthHistoryRecorded')")
    display_name: str = Field(description="한국어 과거형 짧은 라벨 (e.g., '실시간인증이력 기록됨')")


class _PolicyNamingOut(BaseModel):
    name: str = Field(description="On{Event}Trigger{Command} 형식")
    description: str = Field(default="", description="한국어 1줄 설명")


class _ReadModelNamingOut(BaseModel):
    name: str = Field(description="PascalCase 영문 조회 모델 이름")
    display_name: str = Field(description="한국어 UI 라벨")


class _UserStoryNamingOut(BaseModel):
    """LLM-shaped UserStory action + benefit (As-a / I want to / So that).

    Korean output: action is imperative ("...한다"), benefit explains motivation
    ("...하기 위해"). Both are short — one-liner each. Drop trailing punctuation.
    """

    action: str = Field(description="한국어 평서문 'I want to' 본문 (예: '자동납부 신청 결과를 확인한다')")
    benefit: str = Field(description="한국어 'so that' 의도 설명 (예: '안전한 자동납부 등록을 보장받기 위해')")


# =============================================================================
# System prompts (Phase 5 specific — compact, naming-only)
# =============================================================================


_SYSTEM_AGGREGATE = """당신은 DDD Aggregate 명명 전문가입니다.
주어진 root 테이블과 멤버 함수를 보고 한국어 도메인 명사 + 영문 PascalCase 이름을 부여합니다.
규칙:
- name 은 영문 PascalCase 단수형 (예: AuthHistory, OrderItem). 코드 식별자 그대로 노출 금지.
- display_name 은 한국어 도메인 용어 (예: 실시간인증이력, 주문항목). 영문이나 코드명 사용 금지.
"""

_SYSTEM_COMMAND = """당신은 DDD Command 명명 전문가입니다.
주어진 Task 의도와 결정론적으로 추출된 invariant rule statements 를 보고
이 Command 의 영문 PascalCase + 한국어 라벨을 부여합니다.
규칙:
- name 은 영문 PascalCase 동사형 (예: ProcessAuthResult, ValidateInput).
- display_name 은 한국어 명령형 짧은 라벨 (예: '인증결과 처리', '입력값 검증').
"""

_SYSTEM_EVENT = """당신은 DDD Event 명명 전문가입니다.
주어진 Aggregate 와 write 동작 (INSERT/UPDATE/DELETE), invariant rule 의도를 보고
사실(과거형) 이벤트 이름을 부여합니다.
규칙:
- name 은 영문 PascalCase **PastParticiple** (예: AuthHistoryRecorded, OrderShipped).
- display_name 은 한국어 과거형 짧은 라벨 (예: '실시간인증이력 기록됨', '주문 배송됨').
- INSERT → ...Recorded/Created, UPDATE → ...Updated/Adjusted, DELETE → ...Removed/Cancelled.
"""

_SYSTEM_POLICY = """당신은 DDD Policy 명명 전문가입니다.
주어진 trigger Event, invoke Command, coupled_domains 를 보고
"이벤트 발생 시 다른 도메인 Command 가 자동으로 호출되는" 정책 이름을 부여합니다.
규칙:
- name 은 영문 PascalCase: On{Event}Trigger{Command} 또는 On{Event}{ImperativeAction} 형태.
- description 은 한국어 1줄로 trigger → invoke 의미 설명.
"""

_SYSTEM_READMODEL = """당신은 DDD ReadModel 명명 전문가입니다.
주어진 source rule statement(읽기 동작 위주) 와 host 함수명을 보고
조회 모델의 한국어/영문 이름을 부여합니다.
규칙:
- name 은 영문 PascalCase (예: AuthHistoryQueryView, OrderListView).
- display_name 은 한국어 UI 라벨 (예: '실시간인증이력 조회', '주문 목록').
"""

_SYSTEM_USER_STORY = """당신은 사용자 스토리 작성 전문가입니다.
주어진 Task 정보 + 매핑된 코드 Rule 들 + role 를 보고
이 스토리의 'I want to' 본문(action)과 'so that' 의도(benefit)를 작성합니다.

규칙:
- action 은 role 입장에서 의도적 행위를 한국어 평서문 으로 (예: '자동납부 신청 결과를 확인한다').
  코드 식별자(camelCase, snake_case) 또는 컬럼명을 본문에 그대로 노출하지 마세요.
  rule statement 가 길거나 기술적이면 도메인 의도로 압축해서 표현.
- benefit 은 그 행위의 사용자/시스템적 가치를 한국어로 (예: '안전한 자동납부 등록을 보장받기 위해').
  benefit 추론이 어려우면 "업무 정확성을 보장하기 위해" 같은 일반화도 허용.
- 둘 다 한 문장씩, 마침표 없이.
"""


# =============================================================================
# Helpers
# =============================================================================


def _slug(text: str) -> str:
    """Stable lowercase slug for use as `key` (BC, Aggregate, etc.)."""
    s = re.sub(r"[^A-Za-z0-9가-힣_]+", "_", text or "").strip("_")
    return (s or "x").lower()[:80]


def _stories_text_for_bc_prompt(user_stories: list[UserStoryCandidate]) -> str:
    """Build the {user_stories} placeholder body legacy IDENTIFY_BC_FROM_STORIES_PROMPT expects.

    Format mirrors `bounded_contexts.py:_build_stories_text_with_ids` shape:
    one block per story, with id, role, action seed, and a few rule statements.
    """
    blocks: list[str] = []
    for us in user_stories:
        action = us.name_seed or us.task_name or "(unnamed)"
        rule_excerpts = ""
        if us.rule_statements:
            sample = us.rule_statements[:5]
            joined = "\n    - ".join(s for s in sample)
            rule_excerpts = f"\n  - rules:\n    - {joined}"
        blocks.append(
            f"- id: {us.id}\n"
            f"  role: {us.role}\n"
            f"  action: {action}\n"
            f"  source: {us.source}"
            f"{rule_excerpts}"
        )
    return "\n".join(blocks)


def _pascal(s: str) -> str:
    """Cheap PascalCase coercion for fallback names."""
    parts = re.split(r"[^A-Za-z0-9]+", s or "")
    return "".join(p[:1].upper() + p[1:] for p in parts if p) or "Unnamed"


# =============================================================================
# Public entry point
# =============================================================================


async def name_session(
    sd: SessionDecomposition,
    *,
    use_llm: bool = True,
) -> NamedSession:
    """Name every BC / Aggregate / Command / Event / Policy / ReadModel.

    `use_llm=False` skips all LLM calls and returns deterministic fallback
    names — useful for tests, debugging, and when the LLM is unavailable.
    """
    out = NamedSession()

    # --- 1. BC grouping (LLM, biggest call) ---------------------------------
    out.bcs = await _name_bcs(sd.user_stories, use_llm=use_llm)
    bc_of_us = _bc_of_user_story(out.bcs, sd.user_stories)

    # --- 1b. UserStory action/benefit shaping (LLM per US — N×LLM, but small) ----
    # Without this step the navigator shows raw rule statements in `action` and
    # an empty `benefit`, breaking the As-a / I-want-to / So-that contract.
    for us in sd.user_stories:
        out.user_story_shapes[us.id] = await _name_user_story(us, use_llm=use_llm)

    # --- 2. Aggregate names + BC assignment ---------------------------------
    for agg in sd.aggregates:
        bc_key = _bc_for_aggregate(agg, bc_of_us, out.bcs)
        out.aggregate_names[agg.root_table] = await _name_aggregate(
            agg, bc_key=bc_key, use_llm=use_llm,
        )

    # --- 3. Command displayNames -------------------------------------------
    rule_lookup = _rule_statement_lookup(sd)
    for cmd in sd.commands:
        out.command_names[cmd.id] = await _name_command(
            cmd,
            rule_lookup=rule_lookup,
            aggregate=out.aggregate_names.get(cmd.aggregate_root_table or ""),
            use_llm=use_llm,
        )

    # --- 4. Event names ----------------------------------------------------
    for ev in sd.events:
        out.event_names[ev.id] = await _name_event(
            ev,
            rule_lookup=rule_lookup,
            aggregate=out.aggregate_names.get(ev.aggregate_root_table),
            use_llm=use_llm,
        )

    # --- 5. Policy names ---------------------------------------------------
    bc_name_of_us: dict[str, str] = {
        us_id: bc.display_name or bc.name
        for bc in out.bcs for us_id in bc.user_story_ids
    }
    for pol in sd.policies:
        bc_label = bc_name_of_us.get(pol.user_story_id, "")
        trigger_seed = (rule_lookup.get(pol.source_rule_id) or "")[:40]
        out.policy_names[pol.id] = await _name_policy(
            pol,
            bc_label=bc_label,
            trigger_statement=trigger_seed,
            use_llm=use_llm,
        )

    # --- 6. ReadModel names ------------------------------------------------
    for rm in sd.read_models:
        statements = [rule_lookup.get(rid, "") for rid in rm.rule_ids[:3]]
        statements = [s for s in statements if s]
        out.read_model_names[rm.id] = await _name_read_model(
            rm,
            statements=statements,
            use_llm=use_llm,
        )

    return out


# =============================================================================
# Per-kind LLM functions (each with deterministic fallback)
# =============================================================================


async def _name_bcs(
    user_stories: list[UserStoryCandidate],
    *,
    use_llm: bool,
) -> list[BCAssignment]:
    """BC grouping — calls legacy IDENTIFY_BC_FROM_STORIES_PROMPT once."""
    if not user_stories:
        return []

    if use_llm:
        try:
            llm = get_llm()
            structured = llm.with_structured_output(BoundedContextList)
            prompt = IDENTIFY_BC_FROM_STORIES_PROMPT.format(
                user_stories=_stories_text_for_bc_prompt(user_stories),
            )
            result: BoundedContextList = await structured.ainvoke([
                SystemMessage(content="You are a Domain-Driven Design Bounded Context analyst. Output Korean displayName."),
                HumanMessage(content=prompt),
            ])
            if result and result.bounded_contexts:
                return [_bc_to_assignment(bc) for bc in result.bounded_contexts]
        except Exception as e:
            SmartLogger.log(
                "WARN", "BC grouping LLM failed; falling back to single-BC default",
                category="ingestion.hybrid.es.naming.bc",
                params={"error": str(e), "story_count": len(user_stories)},
            )

    # Fallback: dump everything into one Supporting Domain BC.
    return [BCAssignment(
        key="bc_default",
        name="Default",
        display_name="기본 도메인",
        description="LLM grouping unavailable — 모든 UserStory 를 단일 BC 로 묶음",
        rationale="LLM unavailable; deterministic fallback",
        domain_type="Supporting Domain",
        user_story_ids=[us.id for us in user_stories],
    )]


def _bc_to_assignment(bc: BoundedContextCandidate) -> BCAssignment:
    name = bc.name or "Unnamed"
    return BCAssignment(
        key=bc.key or _slug(name),
        name=name,
        display_name=bc.displayName or name,
        description=bc.description or "",
        rationale=bc.rationale or "",
        domain_type=bc.domain_type or "Supporting Domain",
        user_story_ids=list(bc.user_story_ids or []),
    )


def _bc_of_user_story(
    bcs: list[BCAssignment], user_stories: list[UserStoryCandidate],
) -> dict[str, str]:
    """Map us.id → bc.key, with a graceful fallback for stories the LLM forgot.

    LLM occasionally drops a user story from its assignments; we re-attach
    them to the first (or single) BC so no story orphans dangle on the canvas.
    """
    out: dict[str, str] = {}
    for bc in bcs:
        for us_id in bc.user_story_ids:
            out[us_id] = bc.key
    if bcs:
        primary = bcs[0].key
        for us in user_stories:
            out.setdefault(us.id, primary)
    return out


def _bc_for_aggregate(
    agg: SessionAggregate,
    bc_of_us: dict[str, str],
    bcs: list[BCAssignment],
) -> str:
    """An Aggregate inherits its BC from the most-frequent BC among its US contributors."""
    counts: dict[str, int] = {}
    for us_id in agg.user_story_ids:
        bc_key = bc_of_us.get(us_id)
        if bc_key:
            counts[bc_key] = counts.get(bc_key, 0) + 1
    if counts:
        return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return bcs[0].key if bcs else "bc_default"


async def _name_aggregate(
    agg: SessionAggregate, *, bc_key: str, use_llm: bool,
) -> AggregateName:
    if use_llm:
        try:
            llm = get_llm()
            structured = llm.with_structured_output(_AggregateNamingOut)
            user_msg = (
                f"### Aggregate root table\n- {agg.root_table}\n\n"
                f"### Member functions ({len(agg.member_functions)})\n"
                + "\n".join(f"- {fn}" for fn in agg.member_functions[:10])
                + f"\n\n### 통계\n- creation rules: {len(agg.creation_rule_ids)}\n"
                f"- mutation rules: {len(agg.invariant_rule_ids)}\n"
                f"- removal rules: {len(agg.removal_rule_ids)}\n"
            )
            result: _AggregateNamingOut = await structured.ainvoke([
                SystemMessage(content=_SYSTEM_AGGREGATE),
                HumanMessage(content=user_msg),
            ])
            if result and result.name:
                return AggregateName(
                    name=_pascal(result.name),
                    display_name=result.display_name or result.name,
                    bc_key=bc_key,
                )
        except Exception as e:
            SmartLogger.log(
                "WARN", f"Aggregate naming LLM failed for {agg.root_table}",
                category="ingestion.hybrid.es.naming.aggregate",
                params={"error": str(e)},
            )
    # Fallback: PascalCase the root_table.
    return AggregateName(
        name=_pascal(agg.root_table),
        display_name=agg.root_table,
        bc_key=bc_key,
    )


def _rule_statement_lookup(sd: SessionDecomposition) -> dict[str, str]:
    """rule_id → its statement, harvested from UserStoryCandidate.rule_statements.

    rule_statements list is parallel to rule_ids on the same UserStoryCandidate
    only by index when both come from the same RuleDTO list — for cross-task
    lookup we'd need the original RuleDTOs, but in practice each rule statement
    appears in exactly one user story so a flat join is enough.
    """
    out: dict[str, str] = {}
    for us in sd.user_stories:
        for rid, statement in zip(us.rule_ids, us.rule_statements):
            if statement:
                out[rid] = statement
    return out


async def _name_command(
    cmd: CommandCandidate, *,
    rule_lookup: dict[str, str],
    aggregate: Optional[AggregateName],
    use_llm: bool,
) -> CommandName:
    agg_label = aggregate.display_name if aggregate else (cmd.aggregate_root_table or "")
    seed = cmd.seed_label or "Command"

    if use_llm:
        try:
            llm = get_llm()
            structured = llm.with_structured_output(_CommandNamingOut)
            sample_statements = [
                rule_lookup.get(rid, "") for rid in cmd.emit_rule_ids[:5]
            ]
            sample_statements = [s for s in sample_statements if s]
            user_msg = (
                f"### Command 시드\n- task name: {cmd.seed_label}\n"
                f"- aggregate: {agg_label}\n"
                f"- branch leg: {cmd.branch_local_id or '(main)'}\n\n"
                "### 핵심 invariant rule 들 (대표 5건)\n"
                + ("\n".join(f"- {s}" for s in sample_statements) or "(없음)")
            )
            result: _CommandNamingOut = await structured.ainvoke([
                SystemMessage(content=_SYSTEM_COMMAND),
                HumanMessage(content=user_msg),
            ])
            if result and result.name:
                return CommandName(
                    name=_pascal(result.name),
                    display_name=result.display_name or result.name,
                )
        except Exception as e:
            SmartLogger.log(
                "WARN", f"Command naming LLM failed for {cmd.id}",
                category="ingestion.hybrid.es.naming.command",
                params={"error": str(e)},
            )

    pascal_name = _pascal(seed)
    if pascal_name == "Unnamed":
        # Korean-only task name → derive from command id as a stable fallback.
        pascal_name = f"Command{cmd.id.split('_')[-1].title() or 'X'}"
    return CommandName(name=pascal_name, display_name=seed)


_OP_TO_PAST = {"INSERT": "Recorded", "UPDATE": "Updated", "DELETE": "Removed"}
_OP_TO_KO = {"INSERT": "기록됨", "UPDATE": "갱신됨", "DELETE": "삭제됨"}


async def _name_event(
    ev: EventCandidate, *,
    rule_lookup: dict[str, str],
    aggregate: Optional[AggregateName],
    use_llm: bool,
) -> EventName:
    agg_pascal = aggregate.name if aggregate else _pascal(ev.aggregate_root_table)
    agg_ko = aggregate.display_name if aggregate else ev.aggregate_root_table

    if use_llm:
        try:
            llm = get_llm()
            structured = llm.with_structured_output(_EventNamingOut)
            statement = rule_lookup.get(ev.rule_id, "")
            user_msg = (
                f"### Event 시드\n- aggregate: {agg_ko} ({agg_pascal})\n"
                f"- write op: {ev.op}\n"
                f"- target table: {ev.target_table}\n"
                f"- source rule statement: {statement or '(none)'}\n"
            )
            result: _EventNamingOut = await structured.ainvoke([
                SystemMessage(content=_SYSTEM_EVENT),
                HumanMessage(content=user_msg),
            ])
            if result and result.name:
                return EventName(
                    name=_pascal(result.name),
                    display_name=result.display_name or result.name,
                )
        except Exception as e:
            SmartLogger.log(
                "WARN", f"Event naming LLM failed for {ev.id}",
                category="ingestion.hybrid.es.naming.event",
                params={"error": str(e)},
            )

    suffix = _OP_TO_PAST.get(ev.op, "Changed")
    suffix_ko = _OP_TO_KO.get(ev.op, "변경됨")
    return EventName(
        name=f"{agg_pascal}{suffix}",
        display_name=f"{agg_ko} {suffix_ko}",
    )


async def _name_policy(
    pol: PolicyCandidate, *,
    bc_label: str,
    trigger_statement: str,
    use_llm: bool,
) -> PolicyName:
    if use_llm:
        try:
            llm = get_llm()
            structured = llm.with_structured_output(_PolicyNamingOut)
            user_msg = (
                f"### Policy 후보\n"
                f"- source BC: {bc_label}\n"
                f"- coupled_domains (target): {pol.coupled_domains}\n"
                f"- trigger rule statement: {trigger_statement or '(unknown)'}\n"
                f"- branch_kind: {pol.branch_kind}\n\n"
                "위 정보로 정책 이름과 한국어 설명을 만드세요."
            )
            result: _PolicyNamingOut = await structured.ainvoke([
                SystemMessage(content=_SYSTEM_POLICY),
                HumanMessage(content=user_msg),
            ])
            if result and result.name:
                return PolicyName(
                    name=_pascal(result.name),
                    description=result.description or "",
                )
        except Exception as e:
            SmartLogger.log(
                "WARN", f"Policy naming LLM failed for {pol.id}",
                category="ingestion.hybrid.es.naming.policy",
                params={"error": str(e)},
            )

    domains = "_".join(_pascal(d) for d in pol.coupled_domains) or "ExternalDomain"
    return PolicyName(
        name=f"OnRuleTrigger{domains}",
        description=f"{bc_label} 의 규칙 발생 시 {', '.join(pol.coupled_domains) or '외부 도메인'} 호출",
    )


async def _name_user_story(
    us: UserStoryCandidate, *, use_llm: bool,
) -> UserStoryShape:
    """LLM-shape (us.role, task, rules) → (action, benefit). Falls back to
    a deterministic best-effort when LLM is unavailable."""
    if use_llm:
        try:
            llm = get_llm()
            structured = llm.with_structured_output(_UserStoryNamingOut)
            rules_block = ""
            if us.rule_statements:
                joined = "\n".join(f"  - {r}" for r in us.rule_statements[:5])
                rules_block = f"\n### 매핑된 코드 Rule statements ({len(us.rule_statements)})\n{joined}"
            passages_block = ""
            if us.passage_excerpts:
                pj = "\n".join(f"  - {p}" for p in us.passage_excerpts[:2])
                passages_block = f"\n### 문서 근거 발췌\n{pj}"
            user_msg = (
                f"### Task\n- name: {us.task_name}\n"
                f"- description: {us.task_description}\n"
                f"### Role\n- {us.role}"
                f"{rules_block}{passages_block}\n\n"
                "위 내용을 바탕으로 user story 의 'I want to' 본문 (action) 과 "
                "'so that' 의도 (benefit) 를 한국어로 작성하세요."
            )
            result: _UserStoryNamingOut = await structured.ainvoke([
                SystemMessage(content=_SYSTEM_USER_STORY),
                HumanMessage(content=user_msg),
            ])
            if result and (result.action or result.benefit):
                return UserStoryShape(
                    action=(result.action or us.name_seed).strip().rstrip("."),
                    benefit=(result.benefit or "").strip().rstrip("."),
                )
        except Exception as e:
            SmartLogger.log(
                "WARN", f"UserStory naming LLM failed for {us.id}",
                category="ingestion.hybrid.es.naming.user_story",
                params={"error": str(e)},
            )

    # Fallback — legible action from task name (preferred over rule statement
    # which is too low-level), empty benefit.
    fallback_action = (us.task_name or us.name_seed or "(미명시 행위)").strip()
    return UserStoryShape(action=fallback_action.rstrip("."), benefit="")


async def _name_read_model(
    rm: ReadModelCandidate, *,
    statements: list[str],
    use_llm: bool,
) -> ReadModelName:
    if use_llm:
        try:
            llm = get_llm()
            structured = llm.with_structured_output(_ReadModelNamingOut)
            fns = ", ".join(rm.source_functions[:5]) or "(unknown)"
            user_msg = (
                f"### ReadModel 후보\n"
                f"- source functions: {fns}\n"
                f"- representative rule statements:\n"
                + ("\n".join(f"  - {s}" for s in statements[:5]) or "  (없음)")
            )
            result: _ReadModelNamingOut = await structured.ainvoke([
                SystemMessage(content=_SYSTEM_READMODEL),
                HumanMessage(content=user_msg),
            ])
            if result and result.name:
                return ReadModelName(
                    name=_pascal(result.name),
                    display_name=result.display_name or result.name,
                )
        except Exception as e:
            SmartLogger.log(
                "WARN", f"ReadModel naming LLM failed for {rm.id}",
                category="ingestion.hybrid.es.naming.read_model",
                params={"error": str(e)},
            )

    seed = rm.source_functions[0] if rm.source_functions else rm.id
    return ReadModelName(name=f"{_pascal(seed)}View", display_name=f"{seed} 조회")
