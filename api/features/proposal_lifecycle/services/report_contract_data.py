"""013-report-mcda — 렌더 데이터 계약 (Single Source of Truth).

`report_render.py`(렌더러)·완전성 가드·`test_report_render.py`(테스트)·
`proposal_state_service`(progressMeta 라벨)가 공용으로 참조하는 상수 맵.

정의 대상(spec §7 데이터 모델 / ac.md AC-1 "핵심 식별값"):
  1) phase 별 **필수 top-level 키**(렌더 완전성 기준).
  2) phase 별 리스트 top-level 키의 **원소 핵심 식별필드**(예: epic→entityTitle, aggregate→name).
  3) 한글 phaseLabel / stageLabel (progressMeta·헤더용).

신규 Neo4j 스키마 없음(spec N2). 순수 상수·순수 함수만.
"""

from __future__ import annotations

from typing import Any

# --- 이모지 라벨(FR-10) ------------------------------------------------------
EMOJI_PROGRESS = "📍"
EMOJI_APPROVE = "✅"
EMOJI_AMEND = "✏️"
EMOJI_ROLLBACK = "↩️"
EMOJI_SKIP = "⏭️"
EMOJI_WARN = "⚠️"


# --- phase / stage 한글 라벨 -------------------------------------------------
PHASE_LABELS: dict[str, str] = {
    "START_OR_RESUME": "시작/재개",
    "SCOPE": "스코프(스테이지 플랜)",
    "STRATEGIC_DDD": "전략 DDD",
    "STRATEGIC_DIFF": "전략 Diff",
    "TACTICAL_DDD": "전술 DDD",
    "TACTICAL_DIFF": "전술 Diff",
    "CONSTITUTION": "구현 계획(Constitution)",
    "CONTEXT": "임팩트 분석",
    "TASKS": "구현 태스크",
    "IMPLEMENT": "구현",
    "TEST": "테스트/리뷰",
    "SUBMIT": "제출(Plan 전이)",
    "ACCEPT": "수용/완료",
    # 다형 렌더 pseudo-phase
    "QUESTION": "질문(clarify)",
    "VIOLATIONS": "검증 오류",
}

STAGE_LABELS: dict[str, str] = {
    "DISCOVER": "Discover · 이벤트 발굴",
    "DECOMPOSE": "Decompose · 서브도메인 분해",
    "STRATEGIZE": "Strategize · Core/Supporting/Generic 분류",
    "CONNECT": "Connect · 컨텍스트 연동",
    "DEFINE": "Define · Bounded Context 정의",
    "TACTICAL": "Tactical · Aggregate 설계",
}


def phase_label(phase: str | None) -> str:
    if not phase:
        return "-"
    return PHASE_LABELS.get(phase.upper(), phase)


def stage_label(stage: str | None) -> str:
    if not stage:
        return "-"
    return STAGE_LABELS.get(stage.upper(), stage)


# --- 렌더 대상 phase → 필수 top-level 키 + 리스트 원소 식별필드 ----------------
# 구조: phase -> { "keys": [필수 top-level 키...],
#                  "identity": { list_key: id_field_or_None } }
# id_field 가 None 이면 스칼라 리스트(원소 문자열 그 자체가 식별값).
REPORT_CONTRACT: dict[str, dict[str, Any]] = {
    # 전략 Diff: 저장 형태 = strategicDiff dict({version, epics, features, userStories, processes})
    # 또는 draft 봉투({action, strategicDiff, journeys}). 렌더러가 평탄화 후 이 계약으로 검사.
    "STRATEGIC_DIFF": {
        "keys": ["epics", "features", "userStories", "processes"],
        "identity": {
            "epics": "entityTitle",
            "features": "entityTitle",
            "userStories": "entityTitle",
            "processes": "entityTitle",
            "journeys": "entityTitle",
        },
    },
    # 전술 Diff: {tacticalDiff:[...], implementationPlan:{...}}
    "TACTICAL_DIFF": {
        "keys": ["tacticalDiff", "implementationPlan"],
        "identity": {
            "tacticalDiff": "nodeTitle",
        },
    },
    "CONSTITUTION": {
        "keys": ["implementationPlan"],
        "identity": {
            "tacticalDiff": "nodeTitle",
        },
    },
    # DDD 스테이지 아티팩트(각 stage 의 top-level 키 = 필수 배열).
    "DISCOVER": {
        "keys": ["events"],
        "identity": {"events": "name", "pivotalEvents": None, "hotspots": "text"},
    },
    "DECOMPOSE": {
        "keys": ["subDomains"],
        "identity": {"subDomains": "name", "adjacency": "from", "couplingNotes": None},
    },
    "STRATEGIZE": {
        "keys": ["classifications"],
        "identity": {"classifications": "subDomain"},
    },
    "CONNECT": {
        "keys": ["interactions"],
        "identity": {"interactions": "message", "couplingWarnings": None},
    },
    "DEFINE": {
        "keys": ["contexts"],
        "identity": {"contexts": "name"},
    },
    "TACTICAL": {
        "keys": ["aggregates"],
        "identity": {"aggregates": "name"},
    },
    "TASKS": {
        "keys": ["tasks"],
        "identity": {"tasks": "id"},
    },
    "TEST": {
        "keys": ["totalScenarios", "passed", "failed", "skipped", "items"],
        "identity": {"items": "scenarioId"},
    },
}

# DDD 스테이지 top-level 키(아티팩트 봉투가 {StageArtifactName: {...}} 로 감싸질 때 언랩용).
STAGE_ARTIFACT_KEYS: dict[str, str] = {
    "DISCOVER": "DiscoverArtifact",
    "DECOMPOSE": "DecomposeArtifact",
    "STRATEGIZE": "StrategizeArtifact",
    "CONNECT": "ConnectArtifact",
    "DEFINE": "DefineArtifact",
    "TACTICAL": "TacticalArtifact",
}

# progressMeta 등에서 "artifact" 다형 kind 로 취급되는 실제 phase 집합.
ARTIFACT_PHASES = set(REPORT_CONTRACT.keys())


def identity_field(phase: str, list_key: str) -> str | None:
    """(phase, list_key) 리스트 원소의 핵심 식별필드. 미정의면 관례적 후보."""
    contract = REPORT_CONTRACT.get((phase or "").upper(), {})
    identity = contract.get("identity", {})
    if list_key in identity:
        return identity[list_key]
    return None


def identity_token(element: Any, id_field: str | None) -> str | None:
    """리스트 원소에서 식별 토큰 추출(가드·테스트 공용)."""
    if id_field is None:
        # 스칼라 리스트: 원소 자체가 식별값.
        if isinstance(element, (str, int, float)):
            return str(element)
        # dict 인데 id_field 미지정 → 관례 후보 순회.
        if isinstance(element, dict):
            for cand in ("nodeTitle", "name", "title", "entityTitle", "id"):
                if element.get(cand):
                    return str(element[cand])
        return None
    if isinstance(element, dict):
        val = element.get(id_field)
        return str(val) if val not in (None, "") else None
    return None
