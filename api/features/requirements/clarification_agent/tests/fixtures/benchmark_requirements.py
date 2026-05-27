"""SC-001 / SC-004 benchmark fixture (030).

A small, hand-curated set of `UserStory` snapshots seeded with the 8
ambiguity-taxonomy gaps the clarification agent is expected to surface.
Each entry advertises the categories it *should* trigger so tests can
compute a detection rate against the agent's output without an external
ground-truth file.

Used by:
 - `test_ambiguity_agent.py` (SC-001 ≥80% detection)
 - SC-004 manual smoke (re-scan after a full session reports ≥70% fewer
   ambiguous requirements — measured in `tasks.md T035`).
"""

from __future__ import annotations

from dataclasses import dataclass

from api.features.requirements.clarification_agent.ambiguity_agent import (
    RequirementForScan,
)
from api.features.requirements.clarification_contracts import AmbiguityCategory


@dataclass(frozen=True)
class BenchmarkItem:
    requirement: RequirementForScan
    expected_categories: tuple[AmbiguityCategory, ...]
    note: str = ""


def _r(rid: str, role: str, action: str, **kwargs: object) -> RequirementForScan:
    return RequirementForScan(id=rid, role=role, action=action, **kwargs)  # type: ignore[arg-type]


# Each item carries ≥1 deliberately seeded ambiguity drawn from the taxonomy.
SEEDED_BENCHMARK: tuple[BenchmarkItem, ...] = (
    BenchmarkItem(
        _r(
            "BMK-001", "고객", "주문을 빠르게 검색하고 싶다",
            benefit="결제 전 빠른 확인을 위해",
        ),
        expected_categories=(
            AmbiguityCategory.non_functional,
            AmbiguityCategory.functional_scope,
        ),
        note="'빠르게'에 측정 가능한 NFR 누락 + 검색 키/필드 미정",
    ),
    BenchmarkItem(
        _r(
            "BMK-002", "관리자", "주문을 관리한다",
            benefit="운영 효율을 위해",
        ),
        expected_categories=(
            AmbiguityCategory.functional_scope,
            AmbiguityCategory.completion_signals,
        ),
        note="'관리한다'가 너무 광범위 + 수용 기준 부재",
    ),
    BenchmarkItem(
        _r(
            "BMK-003", "고객", "결제 정보를 입력한다",
            benefit="주문을 완료하기 위해",
        ),
        expected_categories=(AmbiguityCategory.domain_data_model,),
        note="결제 정보 데이터 모델(필드/검증) 미정",
    ),
    BenchmarkItem(
        _r(
            "BMK-004", "사용자", "외부 결제 게이트웨이를 사용한다",
            benefit="다양한 결제 수단 지원",
        ),
        expected_categories=(AmbiguityCategory.integration_dependencies,),
        note="게이트웨이 파트너/계약 미명세",
    ),
    BenchmarkItem(
        _r(
            "BMK-005", "고객", "장바구니가 비어 있을 때 결제를 시도한다",
            benefit="실수 방지",
        ),
        expected_categories=(AmbiguityCategory.edge_cases,),
        note="빈 장바구니 처리(에러/메시지/리다이렉트) 미정",
    ),
    BenchmarkItem(
        _r(
            "BMK-006", "사용자", "주문 화면에서 다음 단계로 이동한다",
            benefit="결제 흐름 완료",
        ),
        expected_categories=(AmbiguityCategory.interaction_flow,),
        note="'다음 단계'가 어디인지 미정 — 흐름 다이어그램 누락",
    ),
    BenchmarkItem(
        _r(
            "BMK-007", "고객", "쿠폰/coupon/할인권을 적용한다",
            benefit="할인을 받기 위해",
        ),
        expected_categories=(AmbiguityCategory.terminology,),
        note="쿠폰·coupon·할인권이 같은 개념인지 다른지 용어 통일 필요",
    ),
    BenchmarkItem(
        _r(
            "BMK-008", "고객", "원하는 색상으로 제품을 주문한다",
            benefit="개인 취향 반영",
            acceptanceCriteria=["주문할 수 있다"],
        ),
        expected_categories=(AmbiguityCategory.completion_signals,),
        note="수용 기준이 테스트 불가능하게 비어 있음",
    ),
    BenchmarkItem(
        _r(
            "BMK-009", "결제 시스템", "주문 취소 이벤트를 처리한다",
            benefit="환불 트리거",
        ),
        expected_categories=(
            AmbiguityCategory.integration_dependencies,
            AmbiguityCategory.edge_cases,
        ),
        note="동기/비동기, 재시도/타임아웃, 실패 경로 미명세",
    ),
    BenchmarkItem(
        _r(
            "BMK-010", "고객", "주문을 빠르고 안전하게 처리받는다",
            benefit="신뢰성 있는 쇼핑",
        ),
        expected_categories=(
            AmbiguityCategory.non_functional,
            AmbiguityCategory.completion_signals,
        ),
        note="'빠르고 안전하게' 모두 측정 불가 + 완료 신호 부재",
    ),
)

# Convenience accessors.
BENCHMARK_REQUIREMENTS: list[RequirementForScan] = [
    item.requirement for item in SEEDED_BENCHMARK
]
EXPECTED_AMBIGUOUS_IDS: set[str] = {
    item.requirement.id for item in SEEDED_BENCHMARK
}


def expected_categories_for(requirement_id: str) -> tuple[AmbiguityCategory, ...]:
    """Return the categories a seeded requirement should trigger."""
    for item in SEEDED_BENCHMARK:
        if item.requirement.id == requirement_id:
            return item.expected_categories
    return ()
