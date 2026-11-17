"""속성 ↔ 표준항목 맞추기 규칙 — **지어내지 않는다.**

- 속성 한글 이름(displayName)으로 조회한 결과에서 표준항목명이 **정확히 같은 것**(빈칸만 무시)
  이 **하나**이고, 그 상태가 **사용 중**이면 붙인다(`matched`).
- 정확히 같은 것이 여럿 · 같은 것이 있으나 사용 중이 아님 · 비슷한 것만 있음 → **후보만** 남긴다
  (`candidates`). 표준 칸은 비운다.
- 결과가 없으면 `not_found`, 조회가 실패하면 `unverified`(표준 미확인).

"사용 중" 판정은 `is_active_status` **한 곳**에서만 한다. `standardItemStatus` 의 실제 값 목록은
아직 모른다(포스코망에서 probe 로 잰다). 그래서 목록은 상수로 두고, 이미지를 다시 굽지 않고 고칠
수 있게 `.env` 의 `ROBO_STANDARD_ACTIVE_STATUSES`(쉼표 구분)로 덮어쓸 수 있다.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from api.features.standard_items.contracts import StandardItem, StandardLookup

# 사용 중으로 보는 standardItemStatus 값 — **현장에서 재서 고친다.**
# 대소문자·빈칸은 무시하고 비교한다. 여기에 없는 값(빈 값 포함)은 "사용 중 아님" → 후보로만 남는다.
ACTIVE_STATUS_VALUES: frozenset[str] = frozenset(
    {"사용", "사용중", "Y", "USE", "USED", "ACTIVE"}
)

# 후보는 몇 건까지 남기나 — 화면/설계서에서 사람이 고를 만큼만.
MAX_CANDIDATES = 5

MATCHED = "matched"
CANDIDATES = "candidates"
NOT_FOUND = "not_found"
UNVERIFIED = "unverified"

_WS = re.compile(r"\s+")


def normalize_name(name: str | None) -> str:
    """비교용 — 빈칸만 없앤다(`주문 번호` == `주문번호`). 다른 것은 건드리지 않는다."""
    return _WS.sub("", str(name or ""))


def active_status_values() -> frozenset[str]:
    raw = (os.getenv("ROBO_STANDARD_ACTIVE_STATUSES") or "").strip()
    values = [v for v in raw.split(",") if v.strip()] if raw else list(ACTIVE_STATUS_VALUES)
    return frozenset(normalize_name(v).upper() for v in values)


def is_active_status(status: str | None) -> bool:
    """표준항목상태구분이 '사용 중'인가 — 판정은 여기 한 곳."""
    s = normalize_name(status).upper()
    return bool(s) and s in active_status_values()


@dataclass(frozen=True)
class MatchResult:
    state: str                               # matched | candidates | not_found | unverified
    item: StandardItem | None
    candidates: tuple[StandardItem, ...]
    note: str | None = None


def match_property(display_name: str, lookup: StandardLookup) -> MatchResult:
    if lookup.error:
        return MatchResult(UNVERIFIED, None, (), f"표준 미확인: {lookup.error}")
    if not lookup.items:
        return MatchResult(NOT_FOUND, None, (), None)

    target = normalize_name(display_name)
    exact = [it for it in lookup.items if normalize_name(it.standard_korean_name) == target]
    if len(exact) == 1:
        it = exact[0]
        if is_active_status(it.status):
            return MatchResult(MATCHED, it, (), None)
        return MatchResult(
            CANDIDATES, None, (it,), f"이름은 같으나 상태가 사용 중이 아님({it.status or '빈 값'})"
        )
    if len(exact) > 1:
        return MatchResult(
            CANDIDATES, None, tuple(exact[:MAX_CANDIDATES]), f"같은 이름이 {len(exact)}건"
        )
    return MatchResult(
        CANDIDATES, None, tuple(lookup.items[:MAX_CANDIDATES]), "같은 이름 없음 — 비슷한 것만"
    )


def property_standard_fields(result: MatchResult, lookup: StandardLookup) -> dict[str, Any]:
    """Property 노드에 쓸 칸. 붙이지 않을 때는 표준 칸을 **None 으로** 둔다(예전 값을 남기지 않는다).

    그래프 저장소에 지도 목록을 못 넣으므로 후보는 `이름|ID|상태` 문자열 목록으로 둔다.
    """
    it = result.item
    return {
        "standardMatch": result.state,
        "standardId": it.standard_english_id if it else None,
        "standardName": it.standard_korean_name if it else None,
        "standardValueType": it.value_type if it else None,
        "standardDataLength": it.data_length if it else None,
        "standardDecimalLength": it.decimal_length if it else None,
        "standardCodeItem": it.code_item if it else None,
        "standardCandidates": [
            f"{c.standard_korean_name}|{c.standard_english_id or ''}|{c.status or ''}"
            for c in result.candidates
        ],
        "standardNote": result.note,
        "standardSource": lookup.source,
        "standardCheckedAt": lookup.checked_at,
    }
