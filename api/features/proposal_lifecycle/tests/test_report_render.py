"""013-report-mcda — 렌더러 완전성/결정론/스냅샷 테스트.

ac.md 자동화 범위:
- AC-1: 완전성(모든 top-level 키 + 리스트 원소 식별값 전수 + 개수 N 일치).
- AC-5: 결정론(2회 렌더 바이트 동일) + 대표 phase 최소 골든 스냅샷.
- 폴백/가드 동작(FR-5 참조 구현, 미표시 키 강제 append).
"""

from __future__ import annotations

from api.features.proposal_lifecycle.services import report_contract_data as rc
from api.features.proposal_lifecycle.services import report_render as R  # noqa: N812

# --- phase 별 대표 샘플 artifact --------------------------------------------

STRATEGIC = {
    "action": "done",
    "strategicDiff": {
        "version": 1,
        "epics": [{"op": "CREATE", "entityType": "Epic", "tempId": "E1", "entityTitle": "주문 관리"}],
        "features": [{"op": "CREATE", "entityTitle": "장바구니", "epicId": "E1", "tempId": "F1"}],
        "userStories": [
            {"op": "CREATE", "entityTitle": "장바구니 담기", "featureId": "F1",
             "boundedContextId": "BC-order", "role": "고객", "action": "담는다", "benefit": "모아 주문"},
            {"op": "CREATE", "entityTitle": "주문 상태 조회", "featureId": "F1",
             "boundedContextId": "BC-order", "role": "고객", "action": "조회한다", "benefit": "배송 확인"},
        ],
        "processes": [{"op": "CREATE", "entityTitle": "주문 처리", "tempId": "P1"}],
    },
    "journeys": [],
}

TACTICAL = {
    "tacticalDiff": [
        {"nodeId": "AGG-cart", "nodeLabel": "Aggregate", "nodeTitle": "장바구니",
         "changeType": "CREATE", "impactLevel": "HIGH"},
        {"nodeId": "CMD-add", "nodeLabel": "Command", "nodeTitle": "장바구니에 담기",
         "changeType": "CREATE", "impactLevel": "HIGH"},
        {"nodeId": "EVT-added", "nodeLabel": "Event", "nodeTitle": "상품 담김",
         "changeType": "CREATE", "impactLevel": "MEDIUM"},
    ],
    "implementationPlan": {
        "version": 1,
        "architectureDecisions": [{"aspect": "DEPLOYMENT_ENV", "decision": "Docker Compose", "rationale": "단순"}],
        "constitutionGaps": ["관측성 미정의"],
    },
}

STAGES = {
    "DISCOVER": {"DiscoverArtifact": {
        "events": [{"name": "OrderPlaced", "actor": "고객", "external": False},
                   {"name": "PaymentCompleted", "actor": "PG", "external": True}],
        "pivotalEvents": ["OrderPlaced"],
        "hotspots": [{"text": "결제 실패 처리", "disposition": "RESOLVE_NOW"}],
    }},
    "DECOMPOSE": {"DecomposeArtifact": {
        "subDomains": [{"name": "주문", "responsibility": "주문 생성", "eventRefs": ["OrderPlaced"]},
                       {"name": "결제", "responsibility": "결제 처리", "eventRefs": ["PaymentCompleted"]}],
        "adjacency": [{"from": "주문", "to": "결제"}],
        "couplingNotes": ["주문→결제 동기 호출 주의"],
    }},
    "STRATEGIZE": {"StrategizeArtifact": {
        "classifications": [{"subDomain": "주문", "kind": "CORE", "rationale": "차별성"},
                            {"subDomain": "결제", "kind": "GENERIC", "rationale": "외부 PG"}],
    }},
    "CONNECT": {"ConnectArtifact": {
        "interactions": [{"from": "주문", "to": "결제", "message": "결제요청", "kind": "COMMAND", "sync": True, "rationale": "즉시성"}],
        "couplingWarnings": ["동기 결합"],
        "messagingChannel": "Kafka",
    }},
    "DEFINE": {"DefineArtifact": {
        "contexts": [{"name": "주문 컨텍스트", "purpose": "주문 관리", "classification": "CORE"}],
    }},
    "TACTICAL": {"TacticalArtifact": {
        "aggregates": [{"name": "Cart", "description": "장바구니", "boundaryRationale": "일관성 경계",
                        "invariants": ["수량>0", "상품 존재"]}],
    }},
}

TASKS = {"tasks": [
    {"id": "T001", "phase": "Phase 1: Setup", "text": "스캐폴딩", "files": [], "parallel": False},
    {"id": "T002", "phase": "Phase 2: Core", "text": "Aggregate 구현", "files": ["cart.py"], "parallel": True},
]}

TEST = {"proposalId": "PRO-1", "totalScenarios": 3, "passed": 2, "failed": 1, "skipped": 0,
        "items": [
            {"scenarioId": "SC-001", "category": "acceptance", "storyId": "US-1",
             "storyTitle": "장바구니 담기", "scenario": "Given...", "result": "PASS", "reason": None},
            {"scenarioId": "SC-002", "category": "acceptance", "storyId": "US-2",
             "storyTitle": "주문 상태 조회", "scenario": "Given...", "result": "FAIL", "reason": "404"},
        ]}


# --- 완전성 헬퍼 -------------------------------------------------------------

def _assert_all_elements(phase: str, work: dict, out: str) -> None:
    """각 리스트 top-level 키의 모든 원소 식별값이 출력에 존재 + 개수 N 일치."""
    identity = rc.REPORT_CONTRACT.get(phase, {}).get("identity", {})
    for key, value in work.items():
        if isinstance(value, list) and value:
            id_field = identity.get(key, rc.identity_field(phase, key))
            tokens = [rc.identity_token(e, id_field) for e in value]
            tokens = [t for t in tokens if t]
            present = [t for t in tokens if t in out]
            assert len(present) == len(tokens), (
                f"{phase}.{key}: 원소 누락 {set(tokens) - set(present)}")


# --- AC-1: 완전성 -----------------------------------------------------------

def test_strategic_completeness():
    out = R.render_report("STRATEGIC_DIFF", STRATEGIC)
    work = R._normalize_artifact("STRATEGIC_DIFF", STRATEGIC)
    _assert_all_elements("STRATEGIC_DIFF", work, out)
    for title in ["주문 관리", "장바구니", "장바구니 담기", "주문 상태 조회", "주문 처리"]:
        assert title in out
    assert "⚠️ 누락 보정" not in out  # 렌더러 자체가 완전(가드 미발동)


def test_tactical_completeness():
    out = R.render_report("TACTICAL_DIFF", TACTICAL)
    _assert_all_elements("TACTICAL_DIFF", TACTICAL, out)
    for nm in ["장바구니", "장바구니에 담기", "상품 담김", "DEPLOYMENT_ENV", "관측성 미정의"]:
        assert nm in out
    assert "⚠️ 누락 보정" not in out


def test_all_stage_completeness():
    for phase, art in STAGES.items():
        out = R.render_report(phase, art)
        work = R._normalize_artifact(phase, art)
        _assert_all_elements(phase, work, out)
        assert "⚠️ 누락 보정" not in out, f"{phase} 가드 미발동 기대"


def test_tasks_and_test_completeness():
    out_t = R.render_report("TASKS", TASKS)
    _assert_all_elements("TASKS", TASKS, out_t)
    assert "T001" in out_t and "T002" in out_t
    out_test = R.render_report("TEST", TEST)
    _assert_all_elements("TEST", TEST, out_test)
    assert "SC-001" in out_test and "SC-002" in out_test
    # 스칼라 top-level 키(개수)도 반영.
    for k in ["totalScenarios", "passed", "failed", "skipped"]:
        assert k in out_test


def test_guard_forces_missing_keys():
    """렌더러가 놓친 키/원소를 가드가 강제 append(누락 0 보장)."""
    # 미등록 phase → 폴백 경로. 여기에 임의 키를 넣어 가드 동작을 직접 확인.
    art = {"weirdList": [{"name": "잃어버린원소X"}], "scalarKey": "값Y"}
    # 일부러 등록 안 된 phase 로 렌더 → _fallback_body 는 키/값을 나열하므로 존재.
    out = R.render_report("UNKNOWN_PHASE", art)
    assert "잃어버린원소X" in out or "weirdList" in out
    assert "값Y" in out


def test_guard_backstop_fires_on_incomplete_render():
    """백스톱 직접 검증: 렌더러가 원소/스칼라를 누락했을 때 가드가 강제 append 한다.

    _completeness_guard 에 '고의로 불완전한' rendered 문자열을 주입해, 미표시
    리스트 원소 식별값과 스칼라 키가 ⚠️ 누락 보정 표에 강제 노출됨을 단정.
    """
    work = {
        "epics": [{"op": "CREATE", "entityTitle": "누락된에픽Z"}],
        "version": 7,
    }
    incomplete = "## 아무것도 렌더하지 않은 본문"  # 렌더러가 전부 놓친 상황 시뮬레이션
    patched = R._completeness_guard("STRATEGIC_DIFF", work, incomplete)
    assert "⚠️ 누락 보정" in patched          # 백스톱 발동
    assert "누락된에픽Z" in patched            # 리스트 원소 식별값 강제 노출
    assert "7" in patched                      # 스칼라 값 강제 노출
    # 원본이 완전하면 백스톱은 발동하지 않음(거짓 양성 없음).
    complete = incomplete + "\n누락된에픽Z\nversion 7"
    assert "⚠️ 누락 보정" not in R._completeness_guard("STRATEGIC_DIFF", work, complete)


# --- AC-5: 결정론 + 스냅샷 ---------------------------------------------------

def test_determinism_all_phases():
    samples = [("STRATEGIC_DIFF", STRATEGIC), ("TACTICAL_DIFF", TACTICAL),
               ("TASKS", TASKS), ("TEST", TEST)] + list(STAGES.items())
    for phase, art in samples:
        a = R.render_report(phase, art)
        b = R.render_report(phase, art)
        assert a == b, f"{phase} 비결정론"


def test_snapshot_strategic():
    """대표 phase 최소 골든 스냅샷 — 구조 불변식(헤더/표 헤더 행)."""
    out = R.render_report("STRATEGIC_DIFF", STRATEGIC)
    assert out.startswith("## 📄 전략 Diff 보고서")
    assert "### Epic (1건)" in out
    assert "| 작업 | 제목 | ID |" in out
    assert "### User Story (2건)" in out


def test_snapshot_discover():
    out = R.render_report("DISCOVER", STAGES["DISCOVER"])
    assert out.startswith("## 📄 Discover · 이벤트 발굴 보고서")
    assert "events (2건)" in out
    assert "OrderPlaced" in out and "PaymentCompleted" in out


# --- 다형 렌더(clarify/violations) ------------------------------------------

def test_question_render():
    out = R.render_report("QUESTION", {"question": "어떤 모드를 쓸까요?", "options": ["Simplified", "Detailed"]})
    assert "어떤 모드를 쓸까요?" in out
    assert "Simplified" in out and "Detailed" in out


def test_violations_render():
    out = R.render_report("VIOLATIONS", {"violationSummary": "role required",
                                         "violations": [{"path": "userStories[0].role", "message": "required"}]})
    assert "role required" in out
    assert "userStories[0].role" in out


# --- 폴백 참조 구현(FR-5/AC-6) ----------------------------------------------

def test_fallback_lists_all_keys():
    art = {"tacticalDiff": [{"nodeTitle": "장바구니"}], "implementationPlan": {"version": 1}}
    out = R.render_fallback("TACTICAL_DIFF", art)
    assert "tacticalDiff" in out and "implementationPlan" in out
    assert "폴백" in out
