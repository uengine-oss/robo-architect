"""Epic → Feature(spec.md) 생성 deep agent (034).

Epic(BoundedContext) 아래는 User Story를 바로 만들지 않고 **Feature부터** 만든다.
각 Feature = 하나의 speckit `spec.md` 와 같은 단위로, 그 안에 **User Story들 + edge
cases + 핵심 가정**을 함께 담는다. clarification(ambiguity_agent)과 동일하게
`deepagents.create_deep_agent` + `get_llm()` 로 speckit-specify 방법론을 실행한다.

Provider-agnostic: 모델은 `get_llm()`에서 받는다.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.observability.smart_logger import SmartLogger


# 에이전트가 한 번 호출하는 terminal tool의 인자 스키마 (speckit spec.md 구조).
class AgentStory(BaseModel):
    role: str = ""
    action: str = ""
    benefit: str = ""


class AgentFeature(BaseModel):
    name: str
    description: str = ""
    edgeCases: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    userStories: list[AgentStory] = Field(default_factory=list)


DEEP_AGENT_INSTRUCTIONS = (
    "You are a senior product architect running the SpecKit `/speckit-specify` "
    "methodology. You are given ONE Epic (a DDD Bounded Context). Decompose it "
    "into a set of **Features** — each Feature is exactly ONE spec.md-sized unit: "
    "a cohesive, independently-valuable slice of capability.\n\n"
    "For EACH Feature produce, as in a SpecKit spec.md:\n"
    "  • name — short, action-noun\n"
    "  • description — one or two sentences (what & why)\n"
    "  • userStories — 3–7 prioritized stories as role / action / benefit\n"
    "  • edgeCases — boundary conditions, error/conflict scenarios worth recording\n"
    "  • assumptions — reasonable defaults & scope boundaries you chose\n\n"
    "Rules: keep Features DDD-appropriate in granularity (not too coarse); cover the "
    "Epic's scope without overlapping the existing Features listed; do NOT duplicate "
    "them. Write ALL natural-language text in the SAME language as the Epic's name/"
    "description (e.g. Korean if they are Korean).\n\n"
    "When your decomposition is final, call `submit_features` EXACTLY ONCE with the "
    "full list. That ends the session."
)


def generate_features_for_epic(
    *, bc_name: str, bc_description: str, existing_feature_names: list[str]
) -> list[dict]:
    """deepagents로 Epic을 Feature(spec.md)들로 분해. 각 Feature에 US+edge cases 포함."""
    captured: dict[str, Any] = {}

    from langchain_core.tools import tool

    @tool("submit_features")
    def submit_features(features: list[AgentFeature]) -> str:
        """Submit the final Feature decomposition (terminal tool). Call once."""
        captured["features"] = [f.model_dump() for f in (features or [])]
        return "features accepted"

    user_message = (
        f"# Epic (Bounded Context)\n이름: {bc_name}\n"
        + (f"설명: {bc_description}\n" if bc_description else "")
        + "\n# 이미 존재하는 Feature (중복 금지)\n"
        + ("\n".join(f"- {n}" for n in existing_feature_names) or "(없음)")
        + "\n\n이 Epic을 Feature(각 = 하나의 spec.md)들로 분해하고, 각 Feature에 "
        "User Story·edge cases·가정을 담아 `submit_features`로 제출하세요."
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
