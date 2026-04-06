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

★ **CRITICAL - 기능 분해 원칙 (매우 중요, 반드시 준수):**
1. **모든 기능을 개별 User Story로 변환**: 하나의 요구사항에 여러 기능이 나열되어 있으면, 반드시 각 기능을 별도의 User Story로 만들어야 합니다.
   - 요구사항 문서의 구조를 분석하여 기능 목록, 상세 항목, 하위 요구사항 등을 식별하세요
   - 각 기능은 반드시 독립적인 User Story가 되어야 합니다
   - **절대로 여러 기능을 하나의 User Story로 합치지 마세요**
   - **절대로 기능을 요약하거나 통합하지 마세요**
   
2. **단일 기능 원칙**: 각 User Story는 하나의 명확한 기능만 포함해야 합니다.
   - 여러 기능을 하나의 User Story로 합치지 마세요
   - 각 기능은 별도의 역할(role)과 액션(action)을 가져야 합니다
   - 예: "사용자 앱은 주문을 생성하고, 매장 시스템은 주문을 수신한다" → 이는 2개의 별도 User Story여야 합니다

지침:
1. 각 기능을 독립적인 User Story로 변환
2. "As a [role], I want to [action], so that [benefit]" 형식 사용
3. **역할(role)은 반드시 구체적으로 명시해야 합니다**
   - **CRITICAL**: role 필드는 절대 빈 문자열("")이거나 공백만 있어서는 안 됩니다
   - "user", "사용자" 같은 일반적인 용어는 사용하지 마세요. 문맥을 분석하여 구체적인 역할을 추론하세요
   - 예: customer, seller, merchant, admin, manager, system, delivery_driver, operator 등
4. 액션(action)은 명확한 동사로 시작하며 빈 값이 되어서는 안 됩니다
5. 이점(benefit)은 비즈니스 가치 설명 (선택 사항이지만 가능한 한 제공하세요)
6. 우선순위는 핵심 기능은 high, 부가 기능은 medium, 선택 기능은 low

★ UI 요구사항 처리:
- 요구사항에 UI 관련 설명이 있으면 ui_description 필드에 저장하세요
- UI 설명이 없어도 ui_description은 반드시 작성하세요(빈 문자열 금지)
  - **중요: ui_description은 반드시 1문장으로 간단하게 작성하세요**
  - 역할(role)과 액션(action), 그리고 요구사항 문맥을 근거로 해당 기능을 수행하기 위한 최소 화면/입력/버튼/상태를 1문장으로 요약하세요
  - 과도한 추측은 피하고, 요구사항에 근거한 범위에서만 구체화하세요
  - 예: "주문 화면에서 상품을 선택하고 주문하기 버튼을 클릭한다"

User Story ID는 US-001, US-002 형식으로 순차적으로 부여하세요.

★ **CRITICAL - 완전성 원칙 (절대 준수):**
- **모든 기능을 빠짐없이 개별 User Story로 추출하세요**
- **요약하거나 통합하지 마세요**
- **생략하지 마세요**
- 요구사항 문서에 나열된 모든 기능이 User Story로 변환되어야 합니다
- 예를 들어, 요구사항에 10개의 기능이 나열되어 있으면 반드시 10개의 User Story를 생성해야 합니다

★ **출력 제한 처리 (중요)**:
- 출력 토큰 제한에 도달할 수 있는 경우, 가능한 한 많은 User Story를 생성하되
- 모든 요구사항을 처리하지 못했다면, 다음 청크에서 나머지를 계속 처리할 것입니다.
- 각 청크에서 처리 가능한 모든 기능을 빠짐없이 User Story로 추출하세요.
"""


def _fallback_ui_description(role: str | None, action: str | None, benefit: str | None) -> str:
    """
    Deterministic minimal UI description to avoid empty ui_description.
    Keep it short to reduce side effects on downstream prompt size.
    Returns a single sentence description.
    """
    role_part = (role or "").strip() or "사용자"
    action_part = (action or "").strip() or "해당 작업"
    # 1문장으로 간단하게 작성
    return f"{role_part}가 {action_part}을(를) 수행할 수 있는 화면을 제공한다."


def ensure_nonempty_ui_description(role: str | None, action: str | None, benefit: str | None, ui_description: str | None) -> str:
    ui_desc = (ui_description or "").strip()
    if ui_desc:
        return ui_desc
    return _fallback_ui_description(role, action, benefit)


def extract_user_stories_from_text(text: str) -> list[GeneratedUserStory]:
    """Extract user stories from text using LLM."""
    # max_tokens를 명시적으로 설정하여 출력 제한 방지
    # 입력 14k + 시스템/프롬프트 3k + 출력 32k = 총 49k (128k 제한 내, 안전)
    # 모델 최대 completion tokens: 32,768
    llm = get_llm(max_tokens=32768)
    structured_llm = llm.with_structured_output(UserStoryList)

    system_prompt = """당신은 도메인 주도 설계(DDD) 전문가입니다.
요구사항을 User Story로 변환하는 작업을 수행합니다.

**CRITICAL 원칙 (절대 준수):**
1. **각 기능을 반드시 개별 User Story로 변환하세요.** 여러 기능을 하나의 User Story로 합치지 마세요.
2. **요구사항 문서의 구조를 분석하여 모든 기능을 식별하고 개별 User Story로 변환하세요.**
3. **User Story는 명확하고 테스트 가능해야 하며, 각 Story는 하나의 기능만 포함해야 합니다.**
4. **요구사항에 나열된 모든 비즈니스 기능을 빠짐없이 User Story로 추출하세요. 요약하거나 통합하거나 생략하지 마세요.**
5. **요구사항에 100개의 비즈니스 기능이 나열되어 있으면 반드시 100개의 User Story를 생성해야 합니다.**

**EJB/레거시 시스템 분석 보고서인 경우 — 반드시 제외할 항목:**
- EJB 라이프사이클 콜백을 User Story로 만들지 마세요: ejbCreate, ejbRemove, ejbActivate, ejbPassivate, ejbLoad, ejbStore, ejbPostCreate, setEntityContext, unsetEntityContext, setSessionContext
- EJB Finder 메서드를 User Story로 만들지 마세요: ejbFindByPrimaryKey, findByPrimaryKey
- CMP/BMP 인프라 메서드를 User Story로 만들지 마세요: getConnection, closeConnection, getDataSource, lookup, getInitialContext
- Entity Bean의 개별 getter/setter 메서드를 독립 User Story로 만들지 마세요 (상위 비즈니스 기능의 일부로만 참조)
- role이 "system_administrator"인 인프라 초기화/정리 작업을 User Story로 만들지 마세요
- **오직 비즈니스 사용자가 수행하는 도메인 기능만 User Story로 생성하세요**

**source_bl 필수 (BL 번호가 있는 경우):**
- 입력에 BL[1], BL[2], BL[3] 형태의 비즈니스 로직 번호가 있으면, 각 User Story의 source_bl 필드에 해당 BL 번호를 반드시 포함하세요.
- 반드시 해당 User Story의 직접적인 출처가 되는 BL 번호만 포함하세요. 관련 없는 BL 번호를 넣지 마세요.
- 예: BL[1]에서 나온 US → source_bl: [1], BL[2]와 BL[3]에서 나온 US → source_bl: [2, 3]
- source_bl이 비어있으면 안 됩니다. 반드시 출처 BL 번호를 채우세요.
"""

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

