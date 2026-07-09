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

# --- 014-report-design: 보조 아이콘 사전(C1 — 라벨 정본, 아이콘은 보조) --------
# 빈 셀 표식(B6).
DASH = "—"

# 변경 op(전략/전술 공통).
OP_ICON: dict[str, str] = {"CREATE": "🆕", "MODIFY": "✏️", "DELETE": "🗑️"}
# 임팩트 레벨.
IMPACT_ICON: dict[str, str] = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "NONE": "⚪"}
# 전략 엔티티 유형.
STRATEGIC_TYPE_ICON: dict[str, str] = {
    "Epic": "🎯", "Feature": "🧩", "UserStory": "👤", "Process": "🔀", "Journey": "🗺️",
}
# 전술 노드 라벨.
TACTICAL_LABEL_ICON: dict[str, str] = {
    "Aggregate": "🧩", "Command": "⚡", "Event": "📣", "ReadModel": "🔎",
    "Policy": "🛡️", "UI": "🖥️", "Invariant": "📏",
}
# 전략 분류(Core/Supporting/Generic).
CLASSIFICATION_ICON: dict[str, str] = {"CORE": "⭐", "SUPPORTING": "🧩", "GENERIC": "⚙️"}
CLASSIFICATION_LABEL: dict[str, str] = {"CORE": "Core", "SUPPORTING": "Supporting", "GENERIC": "Generic"}
# 테스트 결과.
TEST_RESULT_ICON: dict[str, str] = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}
# 상호작용/의존 종류.
KIND_ICON: dict[str, str] = {"COMMAND": "⚡", "EVENT": "📣"}


def _classification_key(value: str | None) -> str:
    """분류 문자열을 정규 키(CORE/SUPPORTING/GENERIC)로."""
    return (value or "").strip().upper()


def classification_display(value: str | None) -> str:
    """분류 라벨 정본 + 아이콘 보조(예: '⭐ CORE'). 원본 손실 없음."""
    key = _classification_key(value)
    icon = CLASSIFICATION_ICON.get(key, "")
    return f"{icon} {value}".strip() if value else DASH


def aspect_icon(aspect: str | None) -> str:
    """구현계획 관점(aspect) 보조 아이콘. 미지 관점은 아이콘 생략(C1)."""
    a = (aspect or "").lower()
    if any(k in a for k in ("deploy", "배포", "ingress", "k8s", "kubernetes", "환경")):
        return "🚀"
    if any(k in a for k in ("front", "프론트", "ui", "화면")):
        return "🖥️"
    if any(k in a for k in ("repo", "레포", "monorepo", "모노", "저장소")):
        return "📦"
    if any(k in a for k in ("통신", "comm", "messag", "mesh", "kafka", "integration", "연동", "이벤트")):
        return "🔗"
    return ""


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


# --- 014-report-design: 완전성 가드 심화 — 리스트 원소의 하위 필드 계약 ---------
# 구조: phase -> { list_key: [원소가 반드시 렌더에 표현해야 할 하위 필드명...] }
# 완전성 가드가 top-level 식별자뿐 아니라 이 하위 필드의 값 토큰까지 검출한다
# (캔버스 필드·GWT·properties 등 하위 유실 방지, 00-spec-overview 구현순서 3).
DEEP_FIELDS: dict[str, dict[str, list[str]]] = {
    "STRATEGIC_DIFF": {"userStories": ["role", "action", "benefit"]},
    "TACTICAL_DIFF": {"tacticalDiff": ["properties", "fields", "gwt"]},
    "CONSTITUTION": {"tacticalDiff": ["properties", "fields", "gwt"]},
    "DISCOVER": {"events": ["actor"], "hotspots": ["disposition"]},
    "DECOMPOSE": {"subDomains": ["responsibility"], "adjacency": ["to"]},
    # kind/classification 은 라벨+아이콘으로 매핑 렌더(원본 enum 문자열 미노출) →
    # 가드는 라벨화되지 않는 자유텍스트 필드(rationale·message 등)만 검사.
    "STRATEGIZE": {"classifications": ["rationale"]},
    "CONNECT": {"interactions": ["message", "from", "to"]},
    "DEFINE": {"contexts": [
        "purpose", "classification", "businessModel", "evolution", "domainRoles",
        "inbound", "outbound", "ubiquitousLanguage", "languageClashes",
        "businessDecisions", "assumptions", "verificationMetrics", "openQuestions",
    ]},
    "TACTICAL": {"aggregates": [
        "description", "boundaryRationale", "handledCommands", "createdEvents",
        "stateTransitions", "invariants", "correctivePolicies", "throughput", "size",
    ]},
}


def flatten_tokens(value: Any) -> list[str]:
    """중첩 값(dict/list 포함)에서 렌더 검증용 스칼라 문자열 토큰을 평탄 추출.

    - bool 은 아이콘으로 렌더되므로 토큰에서 제외(내부/외부 등).
    - 빈 문자열/None 은 '의도적 없음'이므로 제외(누락 아님).
    """
    out: list[str] = []
    if value is None or isinstance(value, bool):
        return out
    if isinstance(value, (str, int, float)):
        s = str(value).strip()
        if s:
            out.append(s)
        return out
    if isinstance(value, dict):
        for v in value.values():
            out.extend(flatten_tokens(v))
        return out
    if isinstance(value, (list, tuple)):
        for v in value:
            out.extend(flatten_tokens(v))
        return out
    return out


def deep_fields(phase: str, list_key: str) -> list[str]:
    """(phase, list_key) 원소가 렌더에 반드시 표현해야 하는 하위 필드명."""
    return DEEP_FIELDS.get((phase or "").upper(), {}).get(list_key, [])


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
