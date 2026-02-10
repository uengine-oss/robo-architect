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
3. **역할(role)은 반드시 구체적으로 명시해야 합니다** (customer, seller, admin, system, manager, operator 등). 
   - **CRITICAL**: role 필드는 절대 빈 문자열("")이거나 공백만 있어서는 안 됩니다. 반드시 구체적인 역할을 제공하세요.
   - "user", "사용자", 빈 문자열("")은 사용할 수 없습니다. 항상 구체적인 역할을 사용하세요.
   - 요구사항에서 명확한 역할이 없으면, 문맥을 분석하여 가장 적절한 역할을 추론하세요:
     * 주문/구매/결제 관련 → "customer"
     * 판매/상품 관리 → "seller" 또는 "merchant"
     * 관리/승인/설정 → "admin" 또는 "manager"
     * 시스템 자동화/배치 → "system"
     * 배송/운송 → "delivery_driver"
     * 재고/창고 → "warehouse_manager"
   - 예시: "user" ❌ → "customer" ✅, "사용자" ❌ → "customer" 또는 "seller" ✅
4. 액션(action)은 명확한 동사로 시작하며 빈 값이 되어서는 안 됩니다.
5. 이점(benefit)은 비즈니스 가치 설명 (선택 사항이지만 가능한 한 제공하세요).
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

    # 청킹 단계에서 이미 토큰 제한을 고려한 적절한 크기로 나뉘었으므로,
    # 여기서는 전체 텍스트를 모두 사용해야 함
    # (청킹이 없는 경우를 대비해 과도하게 큰 텍스트는 여전히 제한)
    # 하지만 청킹이 적용된 경우 각 청크는 이미 적절한 크기이므로 제한 불필요
    prompt = EXTRACT_USER_STORIES_PROMPT.format(requirements=text)

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
    skipped_count = 0
    
    for s in stories:
        # Prefer attribute access (Pydantic model), but tolerate dict-like items just in case.
        if isinstance(s, dict):
            role = str(s.get("role") or "").strip()
            action = str(s.get("action") or "").strip()
            benefit = str(s.get("benefit") or "").strip()
            ui_desc = str(s.get("ui_description") or "")
            
            # Validate required fields: role and action must not be empty
            if not role or not action:
                skipped_count += 1
                SmartLogger.log(
                    "WARN",
                    f"Skipping user story with empty role or action: role='{role}', action='{action}'",
                    category="ingestion.user_stories.validation",
                    params={
                        "story_id": s.get("id", "unknown"),
                        "role": role,
                        "action": action,
                    }
                )
                continue
            
            # If role is too generic (just "user"), try to infer from action/benefit
            if role.lower() in ("user", "사용자", ""):
                # Try to infer role from action or benefit context
                inferred_role = _infer_role_from_context(action, benefit)
                if inferred_role:
                    role = inferred_role
                    SmartLogger.log(
                        "INFO",
                        f"Inferred role '{inferred_role}' for user story (was '{s.get('role')}')",
                        category="ingestion.user_stories.role_inference",
                        params={
                            "story_id": s.get("id", "unknown"),
                            "original_role": s.get("role"),
                            "inferred_role": inferred_role,
                            "action": action,
                        }
                    )
                else:
                    # Fallback to "customer" if cannot infer
                    role = "customer"
                    SmartLogger.log(
                        "WARN",
                        f"Using fallback role 'customer' for user story (original was empty/generic)",
                        category="ingestion.user_stories.role_fallback",
                        params={
                            "story_id": s.get("id", "unknown"),
                            "action": action,
                        }
                    )
            
            s["role"] = role
            s["action"] = action
            s["benefit"] = benefit
            s["ui_description"] = ensure_nonempty_ui_description(role, action, benefit, ui_desc)
            fixed.append(GeneratedUserStory(**s))
            continue

        role = (getattr(s, "role", "") or "").strip()
        action = (getattr(s, "action", "") or "").strip()
        benefit = (getattr(s, "benefit", "") or "").strip()
        ui_desc = getattr(s, "ui_description", "") or ""
        
        # Validate required fields: role and action must not be empty
        if not role or not action:
            skipped_count += 1
            story_id = getattr(s, "id", "unknown")
            SmartLogger.log(
                "WARN",
                f"Skipping user story with empty role or action: role='{role}', action='{action}'",
                category="ingestion.user_stories.validation",
                params={
                    "story_id": story_id,
                    "role": role,
                    "action": action,
                }
            )
            continue
        
        # If role is too generic (just "user"), try to infer from action/benefit
        if role.lower() in ("user", "사용자", ""):
            # Try to infer role from action or benefit context
            inferred_role = _infer_role_from_context(action, benefit)
            if inferred_role:
                role = inferred_role
                SmartLogger.log(
                    "INFO",
                    f"Inferred role '{inferred_role}' for user story (was '{getattr(s, 'role', '')}')",
                    category="ingestion.user_stories.role_inference",
                    params={
                        "story_id": getattr(s, "id", "unknown"),
                        "original_role": getattr(s, "role", ""),
                        "inferred_role": inferred_role,
                        "action": action,
                    }
                )
            else:
                # Fallback to "customer" if cannot infer
                role = "customer"
                SmartLogger.log(
                    "WARN",
                    f"Using fallback role 'customer' for user story (original was empty/generic)",
                    category="ingestion.user_stories.role_fallback",
                    params={
                        "story_id": getattr(s, "id", "unknown"),
                        "action": action,
                    }
                )
        
        ensured = ensure_nonempty_ui_description(role, action, benefit, ui_desc)

        # Try to update in-place; if unavailable, create a copied model.
        updated = False
        try:
            # Try direct attribute assignment first
            setattr(s, "role", role)
            setattr(s, "action", action)
            setattr(s, "benefit", benefit)
            setattr(s, "ui_description", ensured)
            updated = True
        except Exception:
            pass
        
        if not updated:
            try:
                # Try model_copy (Pydantic v2)
                if hasattr(s, "model_copy"):
                    s = s.model_copy(update={"role": role, "action": action, "benefit": benefit, "ui_description": ensured})
                    updated = True
                # Try copy (Pydantic v1 or dict)
                elif hasattr(s, "copy"):
                    s = s.copy(update={"role": role, "action": action, "benefit": benefit, "ui_description": ensured})
                    updated = True
            except Exception as e:
                SmartLogger.log(
                    "WARN",
                    f"Failed to update user story role: {e}",
                    category="ingestion.user_stories.update_failed",
                    params={"story_id": getattr(s, "id", "unknown"), "role": role}
                )
        
        # If still not updated, create new instance
        if not updated:
            try:
                story_dict = s.model_dump() if hasattr(s, "model_dump") else (s.dict() if hasattr(s, "dict") else dict(s))
                story_dict["role"] = role
                story_dict["action"] = action
                story_dict["benefit"] = benefit
                story_dict["ui_description"] = ensured
                s = GeneratedUserStory(**story_dict)
            except Exception as e:
                SmartLogger.log(
                    "ERROR",
                    f"Failed to create updated user story: {e}",
                    category="ingestion.user_stories.create_failed",
                    params={"story_id": getattr(s, "id", "unknown"), "role": role}
                )
                # Skip this story if we can't update it
                continue

        fixed.append(s)
    
    if skipped_count > 0:
        SmartLogger.log(
            "WARN",
            f"Skipped {skipped_count} user stories with empty role or action",
            category="ingestion.user_stories.validation.summary",
            params={"skipped_count": skipped_count, "total_stories": len(stories), "valid_stories": len(fixed)}
        )

    return fixed


def _infer_role_from_context(action: str, benefit: str) -> str | None:
    """
    Try to infer a specific role from action and benefit context.
    Returns None if cannot infer.
    """
    if not action:
        return None
    
    action_lower = action.lower()
    benefit_lower = (benefit or "").lower()
    combined = f"{action_lower} {benefit_lower}"
    
    # Common role patterns
    if any(word in combined for word in ["주문", "order", "구매", "purchase", "결제", "payment", "장바구니", "cart"]):
        return "customer"
    if any(word in combined for word in ["판매", "sell", "상품", "product", "재고", "inventory", "배송", "shipping"]):
        return "seller"
    if any(word in combined for word in ["관리", "manage", "admin", "승인", "approve", "설정", "setting", "시스템", "system"]):
        return "admin"
    if any(word in combined for word in ["자동", "auto", "스케줄", "schedule", "배치", "batch", "알림", "notification"]):
        return "system"
    if any(word in combined for word in ["배송", "delivery", "배달", "운송", "transport"]):
        return "delivery_driver"
    if any(word in combined for word in ["재고", "stock", "창고", "warehouse", "입고", "출고"]):
        return "warehouse_manager"
    
    return None

