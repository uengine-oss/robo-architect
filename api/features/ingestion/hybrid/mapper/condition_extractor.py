"""Phase 4.4: distill short business-condition statements per Task.

Combines two evidence sources per task:
  - document passages (top-k from passage_retriever)
  - matched Rule GWT (from Phase 3 auto_matches)

Returns a compact list of natural-language conditions that together explain
"what does this Task actually decide / enforce". Kept short (<= 6 items per
task) so the navigator tree stays legible.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.hybrid.contracts import (
    BpmSkeleton,
    DocumentPassage,
    RuleDTO,
    TaskPassageLink,
)
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.observability.smart_logger import SmartLogger


SYSTEM_PROMPT = """당신은 레거시 시스템 문서화 보조원입니다.
주어진 업무 활동(Task)에 대해, 문서 발췌와 코드 규칙(GWT)을 근거로
이 Task가 실제로 판단/제어하는 **조건(condition)** 을 짧은 문장 목록으로 뽑으세요.

규칙:
- 각 condition 은 한 줄(<= 60자)로, 명사구 또는 "~인 경우" 형태로.
- 문서 또는 코드에 근거가 없는 항목은 만들지 마세요.
- 코드 GWT 의 when/then 이 있으면 그것을 한국어로 자연스럽게 풀어 쓰세요.
- 중복 의미는 합치고, 최대 6개까지만.
- 단순 CRUD / 로깅 / 일반 UI 동작은 조건이 아닙니다. 제외하세요.
"""


class _ConditionList(BaseModel):
    conditions: list[str] = Field(default_factory=list)


def _build_user_prompt(
    task_name: str,
    task_description: str | None,
    passages: list[DocumentPassage],
    rules: list[RuleDTO],
) -> str:
    parts = [f"## Task\n- 이름: {task_name}"]
    if task_description:
        parts.append(f"- 설명: {task_description}")
    if passages:
        parts.append("\n## 문서 근거")
        for i, p in enumerate(passages, start=1):
            head = f" — {p.heading}" if p.heading else ""
            body = p.text[:600] + ("..." if len(p.text) > 600 else "")
            parts.append(f"[{i}]{head}\n{body}")
    if rules:
        parts.append("\n## 코드 근거 (Business Rules)")
        for i, r in enumerate(rules, start=1):
            parts.append(
                f"[{i}] fn={r.source_function or '-'}\n"
                f"   GIVEN: {r.given}\n   WHEN : {r.when}\n   THEN : {r.then}"
            )
    parts.append(
        "\n위 근거를 바탕으로 이 Task의 조건(condition) 목록을 짧은 한국어 문장으로 뽑으세요."
    )
    return "\n".join(parts)


async def extract_conditions_for_task(
    task_name: str,
    task_description: str | None,
    passages: list[DocumentPassage],
    rules: list[RuleDTO],
) -> list[str]:
    if not passages and not rules:
        return []
    try:
        llm = get_llm()
        structured = llm.with_structured_output(_ConditionList)
        result: _ConditionList = await structured.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=_build_user_prompt(task_name, task_description, passages, rules)),
        ])
    except Exception as e:
        SmartLogger.log(
            "WARN", "Condition LLM failed for task",
            category="ingestion.hybrid.bpm_enrich",
            params={"task": task_name, "error": str(e)},
        )
        return []

    seen: set[str] = set()
    out: list[str] = []
    for c in result.conditions or []:
        c = (c or "").strip()
        if not c or c in seen:
            continue
        seen.add(c)
        out.append(c)
        if len(out) >= 6:
            break
    return out


async def extract_conditions_for_all(
    skeleton: BpmSkeleton,
    passages_by_task: dict[str, list[DocumentPassage]],
    rules_by_task: dict[str, list[RuleDTO]],
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for task in skeleton.tasks:
        passages = passages_by_task.get(task.id, [])
        rules = rules_by_task.get(task.id, [])
        if not passages and not rules:
            continue
        conds = await extract_conditions_for_task(
            task.name, task.description, passages, rules,
        )
        if conds:
            out[task.id] = conds
    return out
