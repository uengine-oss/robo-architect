"""
Requirements -> User Stories

Business capability: transform a requirements document into a structured user story list.
"""

from __future__ import annotations

import time

from langchain_core.messages import HumanMessage, SystemMessage

from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
)
from api.features.ingestion.ingestion_contracts import GeneratedUserStory, UserStoryList
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


EXTRACT_USER_STORIES_PROMPT = """분석할 요구사항 문서:

{requirements}

---

위 요구사항을 분석하여 User Story 목록을 추출하세요.

지침:
1. 각 기능/요구사항을 독립적인 User Story로 변환
2. "As a [role], I want to [action], so that [benefit]" 형식 사용
3. 역할(role)은 구체적으로 (customer, seller, admin, system 등)
4. 액션(action)은 명확한 동사로 시작
5. 이점(benefit)은 비즈니스 가치 설명
6. 우선순위는 핵심 기능은 high, 부가 기능은 medium, 선택 기능은 low

★ UI 요구사항 처리 (중요):
- 요구사항에 "UI:", "화면", "페이지", "폼", "입력", "버튼", "인터페이스" 등 UI 관련 설명이 있으면
  해당 설명을 ui_description 필드에 저장하세요.
- 예시: ui_description="주문 화면에서 상품명, 수량, 배송지 주소를 입력하고 '주문하기' 버튼을 클릭한다"
- UI 설명이 명시되지 않아도 ui_description은 반드시 작성하세요(빈 문자열 금지).
  - 역할(role)과 액션(action), 그리고 요구사항 문맥을 근거로 해당 기능을 수행하기 위한 최소 화면/입력/버튼/상태를 1문장 이상으로 추론해 작성하세요.
  - 과도한 추측(없는 기능 추가)은 피하고, 요구사항에 근거한 범위에서만 구체화하세요.

User Story ID는 US-001, US-002 형식으로 순차적으로 부여하세요.
모든 주요 기능을 빠짐없이 User Story로 추출하세요.
"""


def _fallback_ui_description(role: str | None, action: str | None, benefit: str | None) -> str:
    """
    Deterministic minimal UI description to avoid empty ui_description.
    Keep it short to reduce side effects on downstream prompt size.
    """
    role_part = (role or "").strip() or "사용자"
    action_part = (action or "").strip() or "해당 작업"
    benefit_part = (benefit or "").strip()
    if benefit_part:
        return (
            f"{role_part}가 {action_part}을(를) 수행해 {benefit_part}을(를) 달성할 수 있도록, "
            "입력 폼/필수 필드, 주요 버튼(확인/저장), 성공·오류 상태를 포함한 화면을 제공한다."
        )
    return (
        f"{role_part}가 {action_part}을(를) 수행할 수 있도록, "
        "입력 폼/필수 필드, 주요 버튼(확인/저장), 성공·오류 상태를 포함한 화면을 제공한다."
    )


def ensure_nonempty_ui_description(role: str | None, action: str | None, benefit: str | None, ui_description: str | None) -> str:
    ui_desc = (ui_description or "").strip()
    if ui_desc:
        return ui_desc
    return _fallback_ui_description(role, action, benefit)


def extract_user_stories_from_text(text: str) -> list[GeneratedUserStory]:
    """Extract user stories from text using LLM."""
    llm = get_llm()
    structured_llm = llm.with_structured_output(UserStoryList)

    system_prompt = """당신은 도메인 주도 설계(DDD) 전문가입니다. 
요구사항을 User Story로 변환하는 작업을 수행합니다.
User Story는 명확하고 테스트 가능해야 합니다."""

    prompt = EXTRACT_USER_STORIES_PROMPT.format(requirements=text[:8000])  # Limit context

    provider, model = get_llm_provider_model()
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "Ingestion: extract user stories - LLM invoke starting.",
            category="ingestion.llm.user_stories.start",
            params={
                "llm": {"provider": provider, "model": model},
                "inputs": {
                    "requirements": text,
                    "requirements_used": text[:8000],
                },
                "system_prompt": system_prompt,
                "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
            }
        )

    t_llm0 = time.perf_counter()
    response = structured_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
    llm_ms = int((time.perf_counter() - t_llm0) * 1000)

    if AI_AUDIT_LOG_ENABLED:
        try:
            resp_dump = response.model_dump() if hasattr(response, "model_dump") else response.dict()
        except Exception:
            resp_dump = {"__type__": type(response).__name__, "__repr__": repr(response)[:1000]}
        stories = getattr(response, "user_stories", []) or []
        SmartLogger.log(
            "INFO",
            "Ingestion: extract user stories - LLM invoke completed.",
            category="ingestion.llm.user_stories.done",
            params={
                "llm": {"provider": provider, "model": model},
                "llm_ms": llm_ms,
                "result": {
                    "user_story_ids": summarize_for_log([getattr(s, "id", None) for s in stories]),
                    "user_stories": summarize_for_log(stories),
                    "response": resp_dump if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_dump),
                },
            }
        )

    stories = getattr(response, "user_stories", []) or []
    fixed: list[GeneratedUserStory] = []
    for s in stories:
        # Prefer attribute access (Pydantic model), but tolerate dict-like items just in case.
        if isinstance(s, dict):
            role = str(s.get("role") or "")
            action = str(s.get("action") or "")
            benefit = str(s.get("benefit") or "")
            ui_desc = str(s.get("ui_description") or "")
            s["ui_description"] = ensure_nonempty_ui_description(role, action, benefit, ui_desc)
            fixed.append(GeneratedUserStory(**s))
            continue

        role = getattr(s, "role", "") or ""
        action = getattr(s, "action", "") or ""
        benefit = getattr(s, "benefit", "") or ""
        ui_desc = getattr(s, "ui_description", "") or ""
        ensured = ensure_nonempty_ui_description(role, action, benefit, ui_desc)

        # Try to update in-place; if unavailable, create a copied model.
        try:
            setattr(s, "ui_description", ensured)
        except Exception:
            try:
                if hasattr(s, "model_copy"):
                    s = s.model_copy(update={"ui_description": ensured})
                elif hasattr(s, "copy"):
                    s = s.copy(update={"ui_description": ensured})
            except Exception:
                pass

        fixed.append(s)

    return fixed


