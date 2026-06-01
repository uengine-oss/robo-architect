"""마법사 단계 메타 + 프로파일링 기반 단계 추천 + 단계별 질문 (035 — US1/US4).

ddd-starter references(00-orientation ~ 08-code)의 흐름을 robo-architect에 맞춰
정리한 데이터. LLM 프롬프트의 컨텍스트로도 쓰인다.
"""

from __future__ import annotations

from api.features.requirements.requirements_contracts import ProfileAnswer, WizardStepRef

# 8단계 메타 (key, 제목, 기본 필수 여부)
STEP_META: list[tuple[str, str, bool]] = [
    ("understand", "Understand — 비즈니스 컨텍스트 정렬", False),
    ("discover", "Discover — Big Picture EventStorming", True),  # 절대 생략 불가
    ("decompose", "Decompose — 서브도메인 식별", True),
    ("strategize", "Strategize — Core/Supporting/Generic 분류", False),
    ("connect", "Connect — Domain Message Flow", False),
    ("organise", "Organise — 팀 토폴로지", False),
    ("define", "Define — Bounded Context Canvas", True),
    ("code", "Code — Aggregate Design Canvas", False),
]

# 단계별 핵심 질문(초심자 기준). 마법사가 3~5개씩 제시.
STEP_QUESTIONS: dict[str, list[str]] = {
    "understand": [
        "이 시스템이 한 문장으로 만드는 가치는? ('누가 무엇을 할 수 있다')",
        "주요 수익/가치 전달 모델은? (구독·수수료·광고·비용절감 등)",
        "핵심 사용자 그룹 2~3개와 그들이 매일/매주 하려는 일 한 가지는?",
        "이번 분기 가장 중요한 비즈니스 목표와 아직 검증되지 않은 가장 큰 가정은?",
    ],
    "discover": [
        "도메인에서 일어나는 사건을 과거형으로 시간순 나열해 주세요(예: '주문이 확정되었다').",
        "각 사건의 트리거는 누구/무엇인가요? (사용자/시간/외부 시스템)",
        "상태가 크게 바뀌는 분기점(피보탈 이벤트) 2~3개는 무엇인가요?",
        "의견이 갈리거나 규칙이 모호한 핫스팟이 있나요?",
    ],
    "decompose": [
        "피보탈 이벤트를 경계로 사건들을 묶으면 어떤 서브도메인이 보이나요?",
        "각 서브도메인의 한 줄 책임은?",
        "서브도메인 간 정보/이벤트 흐름은 어떻게 되나요?",
    ],
    "strategize": [
        "각 서브도메인을 외부에 아웃소싱하면 고객이 차이를 느낄까요? (Core 판별)",
        "충분히 좋은 외부 솔루션(SaaS/라이브러리)이 있나요? (Generic 판별)",
    ],
    "connect": [
        "가장 중요한 비즈니스 흐름 1~3개를 고르면?",
        "각 흐름에서 컨텍스트 간 메시지는 Event/Command/Query 중 무엇인가요?",
    ],
    "organise": [
        "현재/계획 중인 팀 구성(팀 수·인원·전문성)은?",
        "각 컨텍스트를 어느 팀이 소유하나요?",
    ],
    "define": [
        "이 컨텍스트의 한 줄 책임은?",
        "들어오고 나가는 메시지(인/아웃바운드)는?",
        "이 컨텍스트에서 한 가지 뜻으로 써야 하는 핵심 용어 5~10개는?",
        "이 컨텍스트가 다른 컨텍스트에 묻지 않고 스스로 내리는 결정은?",
    ],
    "code": [
        "이 애그리거트의 가능한 상태와 전이는?",
        "항상 참이어야 하는 불변 조건은?",
        "처리하는 커맨드와 발행하는 이벤트는?",
        "예상 동시 쓰기 부하는? (낮음/중간/높음)",
    ],
}


def recommend_plan(profile: ProfileAnswer, *, scope: str) -> list[WizardStepRef]:
    """프로파일/스코프에 맞는 추천 단계 조합. Discover/Decompose/Define은 항상 권장."""
    recommended: set[str] = {"discover", "decompose", "define"}

    if profile.projectType in ("greenfield", "brownfield"):
        recommended.add("understand")
    if profile.dddExperience in ("first_time", "heard") or profile.projectType != "single_feature":
        recommended.add("strategize")
    if profile.teamSize in ("multi_team", "large"):
        recommended.update({"connect", "organise"})
    if profile.projectType != "learning":
        recommended.add("code")
    # 에픽 추가 스코프: 이미 컨텍스트가 있으므로 전략·조직 단계는 선택으로 좁힘.
    if scope == "epic":
        recommended.discard("organise")
        recommended.discard("connect")

    plan: list[WizardStepRef] = []
    for key, title, required in STEP_META:
        is_recommended = required or key in recommended
        plan.append(
            WizardStepRef(key=key, title=title, optional=not required, recommended=is_recommended)
        )
    return plan


def profile_summary(profile: ProfileAnswer, *, scope: str) -> str:
    pt = {
        "greenfield": "신규(그린필드)",
        "brownfield": "기존 시스템 재설계",
        "single_feature": "단일 기능",
        "learning": "학습용",
    }.get(profile.projectType, profile.projectType)
    exp = {
        "first_time": "DDD 처음",
        "heard": "들어봄",
        "practiced": "적용 경험",
        "expert": "숙련",
    }.get(profile.dddExperience, profile.dddExperience)
    team = {
        "solo": "1~3명",
        "small": "4~10명 단일팀",
        "multi_team": "2~5팀",
        "large": "6팀+",
    }.get(profile.teamSize, profile.teamSize)
    where = "에픽 추가" if scope == "epic" else "맨땅에서 시작"
    return f"{pt} · {exp} · {team} · {where}"
