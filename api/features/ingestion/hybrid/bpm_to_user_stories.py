"""Hybrid BPM grouped context → User Stories (LLM call).

Mirrors `analyzer_graph.graph_to_user_stories.extract_user_stories_from_analyzer_graph`
so the existing `workflow/phases/user_stories.py` flow can call it identically.

Called per BpmTask group from the user_stories phase via asyncio.to_thread().
"""

from __future__ import annotations

import time

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.ingestion_contracts import GeneratedUserStory, UserStoryList
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_PROMPT,
    get_llm_provider_model,
)
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


HYBRID_BPM_SYSTEM_PROMPT = """당신은 도메인 주도 설계(DDD) 전문가입니다.
문서에서 추출된 비즈니스 프로세스(BPM) 의 한 Task 와 그 Task 가 실현하는 코드 비즈니스 로직(BL) 을
하나의 LLM 호출로 받아 User Story 로 변환합니다.

★ 입력 데이터 ★
- Task: 문서가 정의한 한 업무 활동 (이름 + 설명 + Actor + 통합 조건)
- 각 fn 묶음: 같은 source_function 의 BL 들 (코드 응집 단위)
- WRITES Tables: fn 이 쓰는 테이블 (Aggregate root 후보)

★ User Story 변환 원칙 ★
1. **fn 묶음 단위 = 1 UserStory** (기본). 한 fn 의 여러 BL 은 같은 의도의 분기/세부 규칙으로 보고 묶으세요.
2. **0-rule Task** (매핑된 코드 없음): description 만으로 1개 US.
3. **role**: Task Actor 그대로. 없으면 'system'.
4. **action**: BL 의 구체적 조건/값 반영. "~한다" 형 한국어 동사구.
5. **displayName**: 한국어 (예: '입력값 검증 — 입력 파라미터 유효성').
6. **ui_description**: 해당 기능의 최소 화면을 1문장으로 요약.
7. **source_bl 은 비워두세요** (hybrid 는 후처리로 채웁니다).
8. **인프라 코드 제외**: getter/setter/init/log 등은 US 로 만들지 마세요.
9. **id** 는 US-001/US-002 ... 순차로 (workflow 가 나중에 재부여하므로 임의값 가능).
"""


HYBRID_BPM_USER_PROMPT_TMPL = """분석할 BPM Task 와 코드 비즈니스 로직:

{context}

---

위 Task 의 fn 묶음 마다 1개씩 User Story 를 만드세요 ("As a [role], I want to [action], so that [benefit]" 형식).
fn 이 없으면 description 만으로 1개. Task 1개 입력 → 보통 1~5개 US 가 나옵니다.
"""


def extract_user_stories_from_bpm_group(context: str) -> list[GeneratedUserStory]:
    """Synchronous LLM call — invoked from `user_stories.py` via asyncio.to_thread()."""
    llm = get_llm(max_tokens=16384)
    structured_llm = llm.with_structured_output(UserStoryList)
    prompt = HYBRID_BPM_USER_PROMPT_TMPL.format(context=context)

    provider, model = get_llm_provider_model()
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO", "Ingestion: extract user stories from BPM (hybrid) - LLM invoke starting.",
            category="ingestion.llm.user_stories.hybrid.start",
            params={
                "llm": {"provider": provider, "model": model},
                "context_length": len(context),
                "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
            },
        )

    t0 = time.perf_counter()
    response = structured_llm.invoke([
        SystemMessage(content=HYBRID_BPM_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    llm_ms = int((time.perf_counter() - t0) * 1000)

    raw = getattr(response, "user_stories", []) or []
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO", "Ingestion: extract user stories from BPM (hybrid) - LLM invoke completed.",
            category="ingestion.llm.user_stories.hybrid.done",
            params={
                "llm": {"provider": provider, "model": model},
                "llm_ms": llm_ms, "user_story_count": len(raw),
            },
        )

    out: list[GeneratedUserStory] = []
    for s in raw:
        action = (getattr(s, "action", "") or "").strip()
        if not action:
            continue
        role = (getattr(s, "role", "") or "").strip() or "system"
        out.append(GeneratedUserStory(
            id=getattr(s, "id", "") or "",
            role=role,
            action=action,
            benefit=getattr(s, "benefit", "") or "",
            priority=getattr(s, "priority", "medium") or "medium",
            ui_description=getattr(s, "ui_description", "") or "",
            displayName=getattr(s, "displayName", None),
            source_bl=getattr(s, "source_bl", []) or [],
        ))
    return out
