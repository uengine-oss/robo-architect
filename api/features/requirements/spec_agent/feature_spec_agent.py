"""Epic → Feature(spec.md) 생성 deep agent (034).

Epic(BoundedContext) 아래는 User Story를 바로 만들지 않고 **Feature부터** 만든다.
각 Feature = 하나의 speckit `spec.md` 와 같은 단위로, 그 안에 **User Story들 + edge
cases + 핵심 가정**을 함께 담는다. clarification(ambiguity_agent)과 동일하게
`deepagents.create_deep_agent` + `get_llm()` 로 speckit-specify 방법론을 실행한다.

Provider-agnostic: 모델은 `get_llm()`에서 받는다.
"""

from __future__ import annotations

from typing import Any, Iterator

from pydantic import BaseModel, Field

from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.observability.smart_logger import SmartLogger


# 에이전트가 한 번 호출하는 terminal tool의 인자 스키마 (speckit spec.md 구조).
class AgentStory(BaseModel):
    role: str = ""
    action: str = ""
    benefit: str = ""
    # speckit spec.md의 Acceptance Scenarios — Given/When/Then 형태의 문장 목록.
    acceptanceCriteria: list[str] = Field(default_factory=list)


class AgentFeature(BaseModel):
    name: str
    description: str = ""
    edgeCases: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)  # 기존 요구사항과의 충돌/중복 경고
    userStories: list[AgentStory] = Field(default_factory=list)


DEEP_AGENT_INSTRUCTIONS = (
    "You are a senior product architect running the SpecKit `/speckit-specify` "
    "methodology. You are given ONE Epic (a DDD Bounded Context). Decompose it "
    "into a set of **Features** — each Feature is exactly ONE spec.md-sized unit: "
    "a cohesive, independently-valuable slice of capability.\n\n"
    "For EACH Feature produce, as in a SpecKit spec.md:\n"
    "  • name — short, action-noun\n"
    "  • description — one or two sentences (what & why)\n"
    "  • userStories — 3–7 prioritized stories. Each story has role / action / "
    "benefit AND `acceptanceCriteria`: 1–3 testable Given/When/Then scenarios "
    "(e.g. 'Given 로그인 상태, When 주문을 취소하면, Then 환불이 시작된다'). "
    "ALWAYS fill acceptanceCriteria — a story without it is incomplete.\n"
    "  • edgeCases — boundary conditions, error/failure scenarios worth recording\n"
    "  • assumptions — reasonable defaults & scope boundaries you chose\n"
    "  • conflicts — if this Feature/story overlaps, duplicates, or contradicts an "
    "EXISTING requirement listed below, note the conflict here (else empty).\n\n"
    "Rules: keep Features DDD-appropriate in granularity (not too coarse); cover the "
    "Epic's scope without overlapping the existing Features/requirements listed; do "
    "NOT duplicate them — reconcile conflicts explicitly via the `conflicts` field. "
    "Write ALL natural-language text in the SAME language as the Epic's name/"
    "description (e.g. Korean if they are Korean).\n\n"
    "When your decomposition is final, call `submit_features` EXACTLY ONCE with the "
    "full list. That ends the session."
)


def generate_features_for_epic(
    *,
    bc_name: str,
    bc_description: str,
    existing_feature_names: list[str],
    existing_requirements: list[str] | None = None,
) -> list[dict]:
    """deepagents로 Epic을 Feature(spec.md)들로 분해. 각 Feature에 US+edge cases 포함."""
    captured: dict[str, Any] = {}

    from langchain_core.tools import tool

    @tool("submit_features")
    def submit_features(features: list[AgentFeature]) -> str:
        """Submit the final Feature decomposition (terminal tool). Call once."""
        captured["features"] = [f.model_dump() for f in (features or [])]
        return "features accepted"

    reqs = existing_requirements or []
    user_message = (
        f"# Epic (Bounded Context)\n이름: {bc_name}\n"
        + (f"설명: {bc_description}\n" if bc_description else "")
        + "\n# 이미 존재하는 Feature (중복 금지)\n"
        + ("\n".join(f"- {n}" for n in existing_feature_names) or "(없음)")
        + "\n\n# 이미 존재하는 요구사항 (충돌·중복 검사 대상)\n"
        + ("\n".join(f"- {r}" for r in reqs[:80]) or "(없음)")
        + (f"\n... 외 {len(reqs) - 80}건" if len(reqs) > 80 else "")
        + "\n\n이 Epic을 Feature(각 = 하나의 spec.md)들로 분해하고, 각 Feature에 "
        "User Story(각 acceptanceCriteria 포함)·edge cases·가정·conflicts를 담아 "
        "`submit_features`로 제출하세요."
    )

    try:
        from deepagents import create_deep_agent
    except ImportError as exc:  # noqa: BLE001
        SmartLogger.log(
            "ERROR",
            "deepagents 패키지가 설치되어 있지 않습니다.",
            category="requirements.feature_spec.deepagents_missing",
            params={"error": str(exc)},
        )
        raise RuntimeError("deepagents 패키지가 설치되어 있지 않습니다. `uv sync` 후 다시 시도하세요.") from exc

    agent = create_deep_agent(
        model=get_llm(),
        tools=[submit_features],
        system_prompt=DEEP_AGENT_INSTRUCTIONS,
    )
    agent.invoke({"messages": [{"role": "user", "content": user_message}]})

    features = captured.get("features", [])
    SmartLogger.log(
        "INFO",
        f"Feature spec agent produced {len(features)} feature(s) for '{bc_name}'.",
        category="requirements.feature_spec.generated",
        params={"bc": bc_name, "count": len(features)},
    )
    return features


def stream_features_for_epic(
    *,
    bc_name: str,
    bc_description: str,
    existing_feature_names: list[str],
    existing_requirements: list[str] | None = None,
) -> Iterator[dict]:
    """generate_features_for_epic의 스트리밍 버전 — deep agent의 리즈닝 단계를 yield.

    yield 형태: {"phase": "reasoning"|"start"|"complete", "message": str, "features"?: [...]}
    """
    captured: dict[str, Any] = {}
    from langchain_core.tools import tool

    @tool("submit_features")
    def submit_features(features: list[AgentFeature]) -> str:
        """Submit the final Feature decomposition (terminal tool). Call once."""
        captured["features"] = [f.model_dump() for f in (features or [])]
        return "features accepted"

    reqs = existing_requirements or []
    user_message = (
        f"# Epic (Bounded Context)\n이름: {bc_name}\n"
        + (f"설명: {bc_description}\n" if bc_description else "")
        + "\n# 이미 존재하는 Feature (중복 금지)\n"
        + ("\n".join(f"- {n}" for n in existing_feature_names) or "(없음)")
        + "\n\n# 이미 존재하는 요구사항 (충돌·중복 검사 대상)\n"
        + ("\n".join(f"- {r}" for r in reqs[:80]) or "(없음)")
        + "\n\n이 Epic을 Feature(각=spec.md)들로 분해하고, 각 Feature에 "
        "User Story(acceptanceCriteria 포함)·edge cases·가정·conflicts를 담아 `submit_features`로 제출하세요."
    )

    try:
        from deepagents import create_deep_agent
    except ImportError as exc:  # noqa: BLE001
        yield {"phase": "complete", "message": f"deepagents 미설치: {exc}", "features": []}
        return

    agent = create_deep_agent(model=get_llm(), tools=[submit_features], system_prompt=DEEP_AGENT_INSTRUCTIONS)
    yield {"phase": "start", "message": f"딥 에이전트 시작 — '{bc_name}'를 Feature(spec.md)로 분해합니다…"}

    try:
        for chunk in agent.stream({"messages": [{"role": "user", "content": user_message}]}, stream_mode="updates"):
            for node, upd in (chunk or {}).items():
                msgs = (upd or {}).get("messages") if isinstance(upd, dict) else None
                if not msgs:
                    continue
                last = msgs[-1]
                tc = getattr(last, "tool_calls", None) or []
                content = getattr(last, "content", "")
                if tc:
                    yield {"phase": "reasoning", "message": f"🔧 {node}: {', '.join(t.get('name','') for t in tc)} 호출"}
                elif content:
                    yield {"phase": "reasoning", "message": f"💭 {node}: {str(content)[:240]}"}
                elif node == "tools":
                    yield {"phase": "reasoning", "message": "✓ 도구 결과 수신"}
    except Exception as exc:  # noqa: BLE001
        yield {"phase": "reasoning", "message": f"스트림 경고: {exc}"}

    feats = captured.get("features", [])
    yield {"phase": "complete", "message": f"✅ {len(feats)}개 Feature 생성 완료", "features": feats}
