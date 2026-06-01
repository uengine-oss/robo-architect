"""Conversational-edit deep agent (035).

Given a single requirement item (Epic / Feature / User Story), its current
state, the user's natural-language feedback, and the recent chat turns, the
agent proposes a ONE-SHOT edit: the full updated field set + a one-line summary
+ a rationale + any conflicts it spots against existing requirements. The user
confirms before anything is written (propose→confirm / HITL, constitution IV).

Mirrors the clarification / feature-spec agents: `deepagents.create_deep_agent`
+ provider-agnostic `get_llm()`, a single terminal `submit_edit` tool, and a
streaming variant that yields the agent's reasoning steps for the UI.
"""

from __future__ import annotations

from typing import Any, Iterator

from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.features.requirements.chat_edit.scope_io import SCOPE_TITLE, all_fields

_FIELD_GUIDE = {
    "name": "짧은 명칭",
    "description": "한두 문단 설명",
    "role": "User Story의 행위 주체 (As a ...)",
    "action": "원하는 행동 (I want ...)",
    "benefit": "기대 효용 (so that ...)",
    "priority": "low|medium|high 중 하나",
    "status": "draft|ready|done 등 상태",
    "acceptanceCriteria": "Given/When/Then 형태의 인수조건 문장 리스트(list[str])",
    "edgeCases": "엣지 케이스 문장 리스트(list[str])",
    "assumptions": "가정 문장 리스트(list[str])",
}


def _system_prompt(scope: str) -> str:
    fields = all_fields(scope)
    guide = "\n".join(f"- {f}: {_FIELD_GUIDE.get(f, '')}" for f in fields)
    return (
        f"당신은 DDD 기반 요구사항 편집 어시스턴트입니다. 지금 편집 대상은 하나의 "
        f"**{SCOPE_TITLE.get(scope, scope)}** 입니다.\n\n"
        "사용자의 자연어 피드백을 반영하여 이 항목을 한 번에 수정하세요. 규칙:\n"
        "1. 피드백이 명시적으로 바꾸라고 한 부분만 수정하고, 나머지 필드는 현재 값을 그대로 유지합니다.\n"
        "2. 반환하는 `fields`에는 이 항목의 **전체 필드 최종값**을 담습니다(바뀌지 않은 값 포함).\n"
        "3. `summary`는 무엇을 바꿨는지 한 줄로, `rationale`은 왜 그렇게 바꿨는지 간단히 설명합니다.\n"
        "4. 제공된 '기존 요구사항'과 충돌·중복이 보이면 `conflicts`에 경고로 담습니다(없으면 빈 배열).\n"
        "5. 사용자의 언어(요청에 사용된 언어)로 작성합니다.\n\n"
        f"편집 가능한 필드:\n{guide}\n\n"
        "결정이 끝나면 `submit_edit`를 정확히 한 번 호출해 제출하세요."
    )


def _user_message(state: dict, feedback: str, history: list[dict], existing: list[str]) -> str:
    import json as _json

    convo = ""
    for t in (history or [])[-6:]:
        who = t.get("role", "user")
        convo += f"- {who}: {t.get('content', '')}\n"
    return (
        "# 현재 항목 상태\n```json\n"
        + _json.dumps({k: v for k, v in state.items() if k not in ("updatedAt",)}, ensure_ascii=False, indent=2)
        + "\n```\n\n"
        + ("# 최근 대화\n" + convo + "\n" if convo else "")
        + "# 기존 요구사항 (충돌·중복 검사 대상)\n"
        + ("\n".join(f"- {r}" for r in (existing or [])[:60]) or "(없음)")
        + "\n\n# 사용자 피드백\n"
        + feedback
        + "\n\n위 피드백을 반영해 `submit_edit`로 제출하세요."
    )


def _build(scope: str):
    """Return (agent, captured) — captured['proposal'] filled by the tool."""
    from langchain_core.tools import tool

    captured: dict[str, Any] = {}

    @tool("submit_edit")
    def submit_edit(
        fields: dict,
        summary: str = "",
        rationale: str = "",
        conflicts: list[str] | None = None,
    ) -> str:
        """Submit the final one-shot edit (terminal tool). Call exactly once.

        fields: the FULL updated field set for the item.
        summary: one-line description of the change.
        rationale: why this change.
        conflicts: warnings about clashes with existing requirements.
        """
        captured["proposal"] = {
            "fields": fields or {},
            "summary": summary or "",
            "rationale": rationale or "",
            "conflicts": list(conflicts or []),
        }
        return "edit accepted"

    from deepagents import create_deep_agent

    agent = create_deep_agent(
        model=get_llm(), tools=[submit_edit], system_prompt=_system_prompt(scope)
    )
    return agent, captured


def stream_chat_edit(
    *,
    scope: str,
    state: dict,
    feedback: str,
    history: list[dict] | None = None,
    existing_requirements: list[str] | None = None,
) -> Iterator[dict]:
    """Yield reasoning steps then the final proposal.

    yield: {"phase": "start"|"reasoning"|"complete", "message": str,
            "proposal"?: {...}}
    """
    try:
        agent, captured = _build(scope)
    except ImportError as exc:  # noqa: BLE001 — deepagents missing
        yield {"phase": "complete", "message": f"deepagents 미설치: {exc}", "proposal": None}
        return

    msg = _user_message(state, feedback, history or [], existing_requirements or [])
    yield {"phase": "start", "message": "AI가 피드백을 분석하는 중…"}
    try:
        for chunk in agent.stream({"messages": [{"role": "user", "content": msg}]}, stream_mode="updates"):
            for node, upd in (chunk or {}).items():
                msgs = (upd or {}).get("messages") if isinstance(upd, dict) else None
                if not msgs:
                    continue
                last = msgs[-1]
                tc = getattr(last, "tool_calls", None) or []
                content = getattr(last, "content", "")
                if tc:
                    yield {"phase": "reasoning", "message": f"🔧 {', '.join(t.get('name', '') for t in tc)} 호출"}
                elif content:
                    yield {"phase": "reasoning", "message": f"💭 {str(content)[:240]}"}
    except Exception as exc:  # noqa: BLE001
        yield {"phase": "reasoning", "message": f"스트림 경고: {exc}"}

    proposal = captured.get("proposal")
    if proposal:
        yield {"phase": "complete", "message": "✅ 제안 준비 완료", "proposal": proposal}
    else:
        yield {"phase": "complete", "message": "제안을 생성하지 못했습니다.", "proposal": None}
