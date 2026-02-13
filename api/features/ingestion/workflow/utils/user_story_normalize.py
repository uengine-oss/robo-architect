"""
User Story 정규화 및 중복 제거 유틸리티

도메인 독립적인 정규화를 통해 User Story의 중복을 안전하게 제거합니다.
- 대소문자, 공백, 하이픈, REQ-ID, 구두점 등을 정규화
- 최소한의 role alias만 사용하여 오탐(다른 기능을 합치는 사고) 방지
- action은 head+tail 방식으로 충돌 위험 최소화

사용 예:
    from api.features.ingestion.workflow.utils.user_story_normalize import dedup_key, canonicalize_role
    
    key = dedup_key(role="operator", action="create order", benefit="place orders")
    normalized_role = canonicalize_role("service operator")  # "operator"
"""

from __future__ import annotations

import re
from typing import Optional

_WS_RE = re.compile(r"\s+")
# keep words, spaces, colon, dash
_PUNCT_RE = re.compile(r"[^\w\s:-]")

def _norm_space(s: str) -> str:
    return _WS_RE.sub(" ", s).strip()

def _norm_text(s: str) -> str:
    s = (s or "").strip().lower()
    # 도메인 무관: 표현 통일
    s = s.replace("real-time", "real time").replace("realtime", "real time")
    s = _PUNCT_RE.sub(" ", s)
    return _norm_space(s)

# ✅ 도메인 자유를 위해 '범용'만 최소 alias 적용 (오탐 합침 방지)
ROLE_ALIASES_MIN = {
    "system": "system",
    "admin": "admin",
    "administrator": "admin",
    "ops": "operator",
    "operator": "operator",
    "service operator": "operator",
    "qa": "qa",
    "tester": "qa",
}

GENERIC_ROLE_WORDS = {"user", "사용자", "end user"}

def canonicalize_role(role: Optional[str], *, generic_to_customer: bool = True) -> str:
    r = _norm_text(role or "")
    if not r:
        return "unknown"
    if r in GENERIC_ROLE_WORDS:
        # 기존 정책 유지: 너무 일반 role은 customer로 (원하면 unknown으로 더 보수 가능)
        return "customer" if generic_to_customer else "unknown"
    return ROLE_ALIASES_MIN.get(r, r.replace(" ", "_"))

def canonicalize_action(action: Optional[str]) -> str:
    a = _norm_text(action or "")
    # REQ-00190 같은 잡음 제거(도메인 무관)
    a = re.sub(r"\breq[-_ ]?\d+\b", "", a)
    return _norm_space(a)

def canonicalize_benefit(benefit: Optional[str]) -> str:
    return _norm_text(benefit or "")

def action_key(action: str, *, head: int = 120, tail: int = 60) -> str:
    """
    dedup key 전용.
    너무 긴 action은 head+tail로 만들어 충돌(서로 다른 기능이 합쳐짐) 위험을 줄인다.
    """
    a = canonicalize_action(action)
    if len(a) <= head + tail + 3:
        return a
    return f"{a[:head].rstrip()} ... {a[-tail:].lstrip()}"

def dedup_key(role: str, action: str, benefit: str = "") -> str:
    """
    User Story 중복 제거를 위한 키 생성.
    benefit은 제외하여 같은 role/action의 변형을 하나로 합칩니다.
    """
    r = canonicalize_role(role)
    a = action_key(action)
    return f"{r}::{a}"
