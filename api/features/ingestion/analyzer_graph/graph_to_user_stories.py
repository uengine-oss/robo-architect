"""
Analyzer Graph (Legacy Code BL) -> User Stories

Business capability: transform BusinessLogic scenarios extracted from legacy code
into structured user stories for DDD Event Storming.
Follows the same module pattern as figma_to_user_stories.py.
"""

from __future__ import annotations

import time

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.ingestion_contracts import GeneratedUserStory, UserStoryList
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
    get_llm_provider_model,
)
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


# ---------------------------------------------------------------------------
# Prompts (analyzer_graph 전용)
# ---------------------------------------------------------------------------

ANALYZER_GRAPH_SYSTEM_PROMPT = """당신은 도메인 주도 설계(DDD) 전문가입니다.
레거시 코드에서 추출된 비즈니스 로직(BL) 시나리오를 분석하여 User Story로 변환합니다.

★★★ 입력 데이터 형식 ★★★

입력은 레거시 코드의 함수/프로시저 단위로 구성됩니다:
- 함수명과 Actor(역할자) 정보
- 비즈니스 규칙 목록: BL[1], BL[2], BL[3]... 형태로 번호가 부여됨
- 각 BL은 코드의 실행 순서(비즈니스 프로세스 흐름)를 반영함
- BL에 parent_sequence가 있으면 상위 규칙 안에 중첩된 하위 규칙임

★★★ User Story 변환 원칙 ★★★

1. **비즈니스 기능 단위로 변환**: 각 BL을 독립적인 User Story로 만들지 마세요.
   관련된 BL들을 묶어서 하나의 의미 있는 비즈니스 기능 단위로 User Story를 만드세요.
   예: BL[1]:입력검증 + BL[2]:중복확인 + BL[3]:등록 → 하나의 "가입 처리" US

2. **Actor 활용**: 입력에 Actor 정보가 있으면 User Story의 role로 사용하세요.
   Actor가 없으면 코드의 맥락에서 적절한 역할을 추론하세요.

3. **source_bl 필수**: 각 User Story가 어떤 BL에서 유래했는지 반드시 source_bl에 기록하세요.
   - 예: BL[1]에서 나온 US → source_bl: [1]
   - BL[2]와 BL[3]에서 나온 US → source_bl: [2, 3]
   - 하나의 US가 여러 BL을 포함할 수 있음
   - source_bl이 비어있으면 안 됩니다

4. **인프라 코드 제외**: 다음은 User Story로 만들지 마세요:
   - EJB 라이프사이클 콜백 (ejbCreate, ejbRemove, ejbActivate, ejbPassivate 등)
   - EJB Finder 메서드 (ejbFindByPrimaryKey, findByPrimaryKey)
   - CMP/BMP 인프라 (getConnection, closeConnection, getDataSource, lookup 등)
   - getter/setter, 초기화, 로깅 등 기술적 구현
   - 오직 비즈니스 사용자가 수행하는 도메인 기능만 User Story로 생성하세요

5. **비즈니스 규칙의 구체성 유지**: BL의 구체적인 조건, 값, 분기를 US의 action에 반영하세요.
   나쁜 예: "요금을 계산한다" (너무 추상적)
   좋은 예: "음성 사용량의 무료 분수 초과분에 대해 분당 추가 요금을 계산한다"

6. **중첩 BL 처리**: parent_sequence가 있는 BL은 상위 규칙의 세부 조건입니다.
   상위 규칙과 함께 하나의 US로 묶거나, 충분히 독립적이면 별도 US로 분리하세요.
"""

ANALYZER_GRAPH_EXTRACT_PROMPT = """분석할 레거시 코드 비즈니스 로직:

{context}

---

위 비즈니스 로직을 분석하여 User Story 목록을 추출하세요.

지침:
1. 관련된 BL들을 묶어 의미 있는 비즈니스 기능 단위의 User Story로 변환
2. "As a [role], I want to [action], so that [benefit]" 형식 사용
3. 역할(role)은 입력의 Actor 정보를 우선 사용. 없으면 맥락에서 추론
4. 역할(role)은 구체적으로 명시: "user", "사용자" 같은 일반적 용어 대신 도메인에 맞는 역할명 사용
5. 액션(action)은 명확한 동사로 시작하며, BL의 구체적 조건/값을 반영
6. source_bl에 해당 US의 출처 BL 번호를 반드시 기입
7. ui_description은 해당 기능을 수행하기 위한 최소 화면을 1문장으로 요약

User Story ID는 US-001, US-002 형식으로 순차적으로 부여하세요.

★ 완전성 원칙: 모든 비즈니스 기능을 빠짐없이 User Story로 추출하세요.
★ 기술적 구현(DB 초기화, 로깅, getter/setter 등)은 제외하세요.
"""


# ---------------------------------------------------------------------------
# Public API (sync – called via asyncio.to_thread from workflow phase)
# ---------------------------------------------------------------------------

def extract_user_stories_from_analyzer_graph(context: str) -> list[GeneratedUserStory]:
    """Extract user stories from analyzer graph BL context using LLM.

    Follows the same pattern as figma_to_user_stories.extract_user_stories_from_figma().
    Called from workflow/phases/user_stories.py via asyncio.to_thread().
    """
    llm = get_llm(max_tokens=32768)
    structured_llm = llm.with_structured_output(UserStoryList)

    prompt = ANALYZER_GRAPH_EXTRACT_PROMPT.format(context=context)

    provider, model = get_llm_provider_model()
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "Ingestion: extract user stories from analyzer graph - LLM invoke starting.",
            category="ingestion.llm.user_stories.analyzer_graph.start",
            params={
                "llm": {"provider": provider, "model": model},
                "context_length": len(context),
                "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
            },
        )

    t_llm0 = time.perf_counter()
    response = structured_llm.invoke([
        SystemMessage(content=ANALYZER_GRAPH_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    llm_ms = int((time.perf_counter() - t_llm0) * 1000)

    stories = getattr(response, "user_stories", []) or []
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "Ingestion: extract user stories from analyzer graph - LLM invoke completed.",
            category="ingestion.llm.user_stories.analyzer_graph.done",
            params={
                "llm": {"provider": provider, "model": model},
                "llm_ms": llm_ms,
                "user_story_count": len(stories),
            },
        )

    fixed: list[GeneratedUserStory] = []
    for s in stories:
        role = (getattr(s, "role", "") or "").strip()
        action = (getattr(s, "action", "") or "").strip()
        if not action:
            continue
        if not role:
            role = "system"
        fixed.append(
            GeneratedUserStory(
                id=getattr(s, "id", "") or "",
                role=role,
                action=action,
                benefit=getattr(s, "benefit", "") or "",
                priority=getattr(s, "priority", "medium") or "medium",
                ui_description=getattr(s, "ui_description", "") or "",
                displayName=getattr(s, "displayName", None),
                source_bl=getattr(s, "source_bl", []) or [],
            )
        )
    return fixed
