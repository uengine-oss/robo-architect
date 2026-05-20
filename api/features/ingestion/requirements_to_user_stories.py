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

위 요구사항에서 **사용자 가치 단위(unit of user value)** 의 User Story 들을 추출하세요.

★ **User Story의 정의 — 절대 준수**

User Story 는 "어떤 역할(role)이 어떤 행위(action)를 수행함으로써 어떤 가치(benefit)를 얻는다" 의 **하나의 완결된 사용자 행위 단위**입니다.

- ✅ **하나의 User Story = 하나의 사용자 목표/행위**
  - 예: "회원이 회원가입을 한다", "회원이 도서를 검색한다", "사서가 도서를 등록한다"
- ❌ **개별 데이터 필드 / 검증 규칙 / 저장 동작은 User Story 가 아닙니다**
  - 예: "이름을 저장한다", "휴대폰번호를 저장한다", "이메일 형식을 검증한다" — 이런 것은 User Story 가 아니라 **인수조건(acceptance criteria)** 입니다

★ **인수조건(acceptance_criteria) 활용 — 핵심**

요구사항 문서에 다음과 같은 **상세 규칙**이 나열되어 있을 때:

> "회원 프로필 생성 시:
>  - 이름이 저장되어야 한다
>  - 휴대폰번호가 저장되어야 한다
>  - 이메일이 저장되어야 한다
>  - 생년월일이 저장되어야 한다
>  - 약관 동의 결과가 함께 저장되어야 한다"

이것은 **하나의 User Story** 인 "회원이 회원가입을 한다(또는 회원 프로필을 생성한다)" 의 **인수조건들** 입니다. 각 항목을 별도의 User Story 로 만들지 말고, 다음과 같이 처리하세요:

```
{{
  "id": "US-001",
  "role": "회원",
  "action": "회원가입을 한다",
  "benefit": "서비스를 이용하기 위해",
  "priority": "high",
  "acceptance_criteria": [
    "이름이 저장된다",
    "휴대폰번호가 저장된다",
    "이메일이 저장된다",
    "생년월일이 저장된다",
    "약관 동의 결과가 함께 저장된다"
  ],
  "ui_description": "회원가입 화면에서 이름·휴대폰·이메일 등을 입력하고 약관에 동의한 뒤 가입 버튼을 누른다"
}}
```

★ **무엇이 인수조건인가 — 판별 기준**

다음에 해당하면 별도 User Story 가 아니라 인수조건입니다:
- 데이터 필드 단위의 저장/조회/검증 ("X가 저장된다", "Y가 표시된다", "Z 형식이어야 한다")
- 비즈니스 규칙·제약 ("최대 5권까지", "14일 이내", "1일당 100원")
- 초기값·기본값 설정 ("기본 권한은 일반 회원으로 설정")
- 단일 사용자 행위의 부수적 동작 (저장, 알림 발송, 이력 기록 등 — 액션 자체와 분리할 수 없는 후속 처리)

다음에 해당하면 별도 User Story 입니다:
- 사용자가 명시적으로 호출하는 다른 행위 ("회원이 로그인한다", "회원이 비밀번호를 변경한다" 는 회원가입과 별개)
- 다른 역할이 수행하는 행위 ("관리자가 회원을 비활성화한다" 는 회원의 행위와 별개)
- 본질적으로 다른 비즈니스 가치를 제공하는 흐름

★ **추출 지침**

1. **요구사항 문서를 사용자 행위 단위로 묶어서 분석**: 산발적으로 나열된 규칙들을 그것들이 어떤 사용자 행위에 속하는지 파악하여 묶으세요.
2. "As a [role], I want to [action], so that [benefit]" 형식 — role/action/benefit 모두 구체적으로 작성
3. **역할(role)** 은 절대 빈 문자열이거나 공백이 되어서는 안 되며, "user/사용자" 같은 모호한 용어 대신 구체적인 도메인 역할로 명시 (customer, member, librarian, admin, system, delivery_driver, ...)
4. **액션(action)** 은 사용자가 의도하는 하나의 명확한 목표를 동사로 시작
5. **benefit** 은 비즈니스 가치
6. **acceptance_criteria** 는 위 정의대로 하위 규칙·필드·검증을 한국어 문장으로 나열 (없으면 빈 배열 [])
7. **priority**: 핵심 high / 부가 medium / 선택 low

★ **UI 설명 (ui_description)**
- 1문장으로 해당 행위 수행을 위한 화면/입력/버튼을 요약
- 예: "회원가입 화면에서 개인정보를 입력하고 약관 동의 후 가입 버튼을 누른다"

User Story ID 는 US-001, US-002 형식으로 순차 부여하세요.

★ **세분화 회피 (CRITICAL)**

요구사항이 "다음을 저장한다: A, B, C, D, E" 형태일 때 → A·B·C·D·E 각각을 별도 User Story 로 만들지 마세요. 이것은 **하나의 User Story 의 인수조건들** 입니다.

규칙은 인수조건이고, User Story 는 그 규칙들이 적용되는 사용자 가치 단위라는 점을 항상 기억하세요. 보통 한 페이지의 요구사항 문서는 5–15 개의 User Story 를 산출하는 것이 적절합니다 (수십~수백 개가 나오면 잘게 쪼개진 것입니다).

★ **출력 토큰 제한 처리**
- 청크 입력이라 출력이 잘릴 수 있으니, 발견한 User Story 들을 **온전히 완결된 형태로** 차례대로 작성하세요.
- 미완성 User Story 를 부분 출력하지 말고, 완성한 것까지만 반환하세요.
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

    system_prompt = """당신은 도메인 주도 설계(DDD)와 애자일 요구사항 분석 전문가입니다.
요구사항을 **사용자 가치 단위(unit of user value)** 의 User Story 로 변환합니다.

**핵심 원칙 (절대 준수):**

1. **User Story = 하나의 완결된 사용자 행위/목표**
   - "회원이 회원가입을 한다", "회원이 도서를 검색한다" 처럼 사용자가 명시적으로 수행하는 의도된 행위 단위.
   - 데이터 필드 단위 저장/검증, 비즈니스 규칙, 초기값 설정 등 **세부 규칙은 User Story 가 아니라 그 사용자 행위의 acceptance_criteria** 입니다.

2. **세분화 금지**
   - "이름을 저장한다", "휴대폰번호를 저장한다", "이메일을 저장한다" 같은 필드 단위 항목들은 별도 User Story 가 아닙니다 — 모두 "회원가입을 한다" 라는 하나의 User Story 의 acceptance_criteria 로 묶으세요.
   - 한 사용자 행위를 수행할 때 자연스럽게 따라오는 부수 처리 (저장·알림·이력 기록) 는 별개 Story 가 아닙니다.

3. **무엇이 별도 User Story 인가**
   - 사용자가 명시적으로 별개로 호출하는 행위 (로그인, 비밀번호 변경 등은 회원가입과 별개)
   - 다른 역할이 수행하는 행위
   - 본질적으로 다른 비즈니스 가치를 제공하는 흐름

4. **role 은 구체적인 도메인 역할**: customer, member, librarian, admin, system 등. "user/사용자" 같은 모호한 표현 금지. 빈 문자열·공백 금지.

5. **acceptance_criteria** 는 그 User Story 의 세부 규칙·필드·검증·초기값을 한국어 문장 배열로 나열. 없으면 빈 배열 `[]`.

좋은 신호: 한 페이지 분량의 요구사항이 5–15 개의 User Story 가 됩니다. 수십~수백 개가 나오면 분명히 세분화된 것입니다.
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


# =============================================================================
# Cross-chunk consolidation (LLM-based semantic merge)
# =============================================================================
#
# Problem this solves: per-chunk extraction can over-fragment requirements into
# rule-level "stories" (e.g. "이름을 저장한다", "이메일을 저장한다") that should
# really be acceptance criteria of one parent story (e.g. "회원가입을 한다").
# Even after a stricter prompt, fragmentation may slip through, *and* the same
# parent story can be split across chunks. This consolidation pass runs ONE
# LLM call over all chunk-extracted stories to merge fragments and surface
# field-level rules into `acceptance_criteria`.

from pydantic import BaseModel, Field as _Field


class ConsolidatedStory(BaseModel):
    """One canonical user story emitted by the consolidation pass."""
    canonical_id: str = _Field(description="Pick one of the input ids to keep as the canonical id (preserves frontend tree-node identity).")
    role: str
    action: str
    benefit: str = ""
    priority: str = "medium"
    ui_description: str = ""
    acceptance_criteria: list[str] = _Field(default_factory=list)
    merged_from_ids: list[str] = _Field(default_factory=list, description="The full set of input story ids this canonical story absorbed (including canonical_id).")


class ConsolidationResult(BaseModel):
    consolidated_stories: list[ConsolidatedStory]


CONSOLIDATE_USER_STORIES_PROMPT = """다음은 여러 청크에서 추출된 User Story 목록입니다. 각 항목은 (id, role, action, benefit, priority, ui_description, acceptance_criteria) 를 가집니다.

이 목록을 분석하여 **사용자 가치 단위(unit of user value)** 로 다시 정리하세요.

다음 두 가지 작업을 수행합니다:

1. **세분화된 규칙들을 인수조건으로 흡수**:
   - "X를 저장한다", "Y를 검증한다", "Z 형식이어야 한다" 같은 필드/규칙 단위 항목들은 그것이 속하는 **상위 사용자 행위 user story** 의 acceptance_criteria 에 한국어 문장으로 추가하세요.
   - 흡수된 입력들의 id 들을 merged_from_ids 에 함께 기록하세요.

2. **청크 경계로 쪼개진 동일 user story 통합**:
   - 같은 사용자 행위가 두 청크에서 비슷한 표현으로 반복 추출됐으면 하나로 합치세요.
   - 합쳐진 입력 id 들을 모두 merged_from_ids 에 포함시키세요.

**canonical_id 선택 규칙**: merged_from_ids 중 첫 번째 (입력 순서상 가장 먼저 등장한) id 를 canonical_id 로 선택하세요. 이는 frontend 트리에서 노드 정체성을 보존하기 위함입니다.

**출력 규칙**:
- 합쳐진 결과는 의미상 중복 없이, 도메인 사용자 행위 단위로만 남겨야 합니다.
- 합칠 게 없는 입력은 그대로 1:1 로 유지하되 `merged_from_ids: [그_id]`, `canonical_id: 그_id` 로 출력하세요.
- 흡수되어 사라진 id 는 출력에 (canonical_id 로) 등장하지 않습니다 — 누락된 id 들은 frontend 가 트리에서 제거합니다.
- role 은 구체적인 도메인 역할로 유지·정리. "user/사용자" 같은 모호한 표현 금지.

입력 user story 목록 (JSON):
{stories_json}

분석하고 정리한 결과를 출력하세요.
"""


def consolidate_user_stories(stories: list[GeneratedUserStory], session_id: str | None = None) -> tuple[list[GeneratedUserStory], list[str]]:
    """Cross-chunk semantic merge.

    Returns:
        (consolidated_stories, dropped_ids)
        - consolidated_stories: post-merge canonical list (each story carries
          its absorbed fragment ids in `acceptance_criteria_source_ids` … no,
          we keep the GeneratedUserStory schema clean; absorbed ids are
          returned via dropped_ids only).
        - dropped_ids: ids from the input that were absorbed into other
          canonical stories (frontend removes these from the tree).

    On any LLM failure, returns the input unchanged with empty dropped_ids
    (fail-open: better to ship per-chunk output than lose everything).
    """
    if not stories:
        return [], []
    if len(stories) <= 1:
        return list(stories), []

    import json

    # Compact JSON to keep token usage reasonable. Truncate ui_description and
    # acceptance_criteria entries so the LLM has room to think + write output.
    def _compact(s: GeneratedUserStory) -> dict:
        return {
            "id": s.id,
            "role": s.role or "",
            "action": s.action or "",
            "benefit": (s.benefit or "")[:120],
            "priority": s.priority or "medium",
            "ui_description": (s.ui_description or "")[:160],
            "acceptance_criteria": [c[:120] for c in (s.acceptance_criteria or [])][:20],
        }

    stories_json = json.dumps([_compact(s) for s in stories], ensure_ascii=False)

    system_prompt = (
        "당신은 도메인 주도 설계와 애자일 요구사항 분석 전문가입니다. "
        "여러 청크에서 추출된 User Story 단편을 사용자 가치 단위로 통합하는 일을 수행합니다. "
        "필드 단위 규칙·검증·저장 동작은 별도 user story 가 아니라 상위 user story 의 acceptance_criteria 입니다."
    )
    prompt = CONSOLIDATE_USER_STORIES_PROMPT.format(stories_json=stories_json)

    provider, model = get_llm_provider_model()
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "Ingestion: consolidate user stories - LLM invoke starting.",
            category="ingestion.llm.user_stories.consolidate.start",
            params={
                "llm": {"provider": provider, "model": model},
                "input_story_count": len(stories),
                "system_prompt": system_prompt,
                "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                "session_id": session_id,
            },
        )

    try:
        # Cap output tokens so it always fits even in 32k-context models.
        llm = get_llm(max_tokens=8192)
        structured_llm = llm.with_structured_output(ConsolidationResult)
        t0 = time.perf_counter()
        response = structured_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
    except Exception as exc:  # noqa: BLE001
        SmartLogger.log(
            "WARN",
            f"User story consolidation LLM call failed; using per-chunk output unchanged. err={exc}",
            category="ingestion.llm.user_stories.consolidate.failed",
            params={"session_id": session_id, "error": str(exc), "input_count": len(stories)},
        )
        return list(stories), []

    consolidated = getattr(response, "consolidated_stories", []) or []
    if not consolidated:
        SmartLogger.log(
            "WARN",
            "Consolidation returned 0 stories; using per-chunk output unchanged.",
            category="ingestion.llm.user_stories.consolidate.empty",
            params={"session_id": session_id, "input_count": len(stories)},
        )
        return list(stories), []

    # Build a lookup of input stories by id so we can preserve fields the LLM
    # didn't surface (sequence, source_unit_id, source_bl, etc.) and keep
    # types consistent.
    by_id: dict[str, GeneratedUserStory] = {s.id: s for s in stories if s.id}

    out: list[GeneratedUserStory] = []
    referenced_ids: set[str] = set()
    seen_canonical: set[str] = set()
    for c in consolidated:
        canonical_id = (c.canonical_id or "").strip()
        if not canonical_id or canonical_id in seen_canonical:
            continue
        seen_canonical.add(canonical_id)
        merged_ids = [mid for mid in (c.merged_from_ids or []) if mid]
        if canonical_id not in merged_ids:
            merged_ids = [canonical_id, *merged_ids]
        referenced_ids.update(merged_ids)

        # Anchor on the original story (preserves source_* fields). Fall back
        # to a synthetic record if the LLM invented a canonical_id we don't
        # recognize (rare; happens when models hallucinate).
        anchor = by_id.get(canonical_id)
        if anchor is None:
            try:
                anchor = GeneratedUserStory(
                    id=canonical_id,
                    role=c.role or "customer",
                    action=c.action or "",
                    benefit=c.benefit or "",
                )
            except Exception:
                continue

        try:
            updated = anchor.model_copy(update={
                "role": c.role or anchor.role,
                "action": c.action or anchor.action,
                "benefit": c.benefit or anchor.benefit,
                "priority": c.priority or anchor.priority,
                "ui_description": c.ui_description or anchor.ui_description,
                "acceptance_criteria": c.acceptance_criteria or anchor.acceptance_criteria,
            })
        except Exception:
            updated = anchor
        out.append(updated)

    # Any input id that the LLM never referenced (neither as canonical nor
    # absorbed) is suspicious — keep the input as-is to avoid silent loss.
    orphaned = [s for s in stories if s.id and s.id not in referenced_ids]
    if orphaned:
        SmartLogger.log(
            "INFO",
            f"Consolidation: {len(orphaned)} input stories were not referenced by LLM output; keeping them unchanged.",
            category="ingestion.llm.user_stories.consolidate.orphans",
            params={"session_id": session_id, "orphan_ids": [s.id for s in orphaned]},
        )
        out.extend(orphaned)
        referenced_ids.update(s.id for s in orphaned if s.id)

    # Dropped = input ids that were absorbed (in referenced_ids) but are NOT a
    # canonical id of any output story.
    canonical_ids = {s.id for s in out if s.id}
    dropped_ids = [s.id for s in stories if s.id and s.id in referenced_ids and s.id not in canonical_ids]

    SmartLogger.log(
        "INFO",
        f"User story consolidation: {len(stories)} → {len(out)} (dropped {len(dropped_ids)}) in {elapsed_ms}ms",
        category="ingestion.llm.user_stories.consolidate.done",
        params={
            "session_id": session_id,
            "input_count": len(stories),
            "output_count": len(out),
            "dropped_count": len(dropped_ids),
            "elapsed_ms": elapsed_ms,
        },
    )
    return out, dropped_ids

