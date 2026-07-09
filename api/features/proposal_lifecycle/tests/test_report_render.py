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
         "changeType": "CREATE", "impactLevel": "HIGH", "boundedContextId": "BC-order",
         "properties": [{"name": "cartId", "type": "UUID"}, {"name": "items", "type": "List"}],
         "fields": {"rootEntity": "Cart"}},
        {"nodeId": "CMD-add", "nodeLabel": "Command", "nodeTitle": "장바구니에 담기",
         "changeType": "CREATE", "impactLevel": "HIGH", "aggregateId": "AGG-cart",
         "userStoryRefs": ["US-add-to-cart"],
         "properties": [{"name": "productId", "type": "UUID"}, {"name": "quantity", "type": "Integer"}],
         "fields": {"inputSchema": {"productId": "UUID", "quantity": "Integer"}},
         "gwt": [{"given": {"fieldValues": {"cartId": "cart-1"}},
                  "when": {"fieldValues": {"productId": "prod-1", "quantity": 2}},
                  "then": {"fieldValues": {"productId": "prod-1", "quantity": 2}}}]},
        {"nodeId": "EVT-added", "nodeLabel": "Event", "nodeTitle": "상품 담김",
         "changeType": "CREATE", "impactLevel": "MEDIUM", "commandId": "CMD-add",
         "properties": [{"name": "productId", "type": "UUID"}],
         "fields": {"payload": {"productId": "UUID"}}},
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
        "contexts": [{"name": "주문 컨텍스트", "purpose": "주문 관리", "classification": "CORE",
                      "businessModel": ["핵심 매출"], "evolution": "custom_built", "domainRoles": ["execution"],
                      "inbound": [{"collaborator": "장바구니", "message": "주문하기", "type": "Command"}],
                      "outbound": [{"collaborator": "결제", "message": "OrderPlaced", "type": "Event"}],
                      "ubiquitousLanguage": [{"term": "주문", "definition": "구매 요청 단위"},
                                             {"term": "상태", "definition": "DRAFT→PAID"}],
                      "businessDecisions": ["게스트 미지원"], "assumptions": ["외부 PG"],
                      "verificationMetrics": ["성공률99"], "openQuestions": ["롤백?"],
                      "languageClashes": ["취소 혼용"]}],
    }},
    "TACTICAL": {"TacticalArtifact": {
        "aggregates": [{"name": "Cart", "description": "장바구니", "boundaryRationale": "일관성 경계",
                        "handledCommands": ["AddToCart"], "createdEvents": ["ItemAdded"],
                        "invariants": ["수량>0", "상품 존재"], "correctivePolicies": ["재고부족 보류"],
                        "stateTransitions": [{"from": "EMPTY", "to": "ACTIVE", "trigger": "AddToCart"}],
                        "throughput": {"commandHandlingRate": {"avg": "50/s", "max": "500/s"},
                                       "totalClients": {"avg": "1k", "max": "20k"},
                                       "concurrencyConflictChance": {"avg": "낮음", "max": "중간"}},
                        "size": {"eventGrowthRate": {"avg": "3", "max": "8"},
                                 "lifetime": {"avg": "30일", "max": "1년"},
                                 "eventsPersisted": {"avg": "3", "max": "20"}}}],
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
    # target-02: properties(name:type) · fields · gwt fieldValues · ref 전부 표현(A2/B7).
    for token in ["cartId", "UUID", "items", "rootEntity", "Cart",
                  "inputSchema", "productId", "quantity", "payload",
                  "aggregateId", "AGG-cart", "userStoryRefs", "US-add-to-cart",
                  "given.fieldValues", "when.fieldValues", "then.fieldValues", "cart-1", "prod-1"]:
        assert token in out, f"전술 하위 필드 누락: {token}"
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
    # target-04: phase 그룹 + 병렬 배지 + 집계 헤더.
    assert "⚡ 병렬" in out_t and "순차" in out_t
    assert "실행 순서:" in out_t and "구현 태스크" in out_t
    out_test = R.render_report("TEST", TEST)
    _assert_all_elements("TEST", TEST, out_test)
    assert "SC-001" in out_test and "SC-002" in out_test
    # target-05: KPI 헤더(스칼라 값) + FAIL 우선 + reason 보존.
    assert "총 3" in out_test and "PASS 2" in out_test and "FAIL 1" in out_test
    assert "404" in out_test  # FAIL reason 절대 생략 금지
    # FAIL 이 PASS 보다 앞(주의-우선 정렬).
    assert out_test.index("SC-002") < out_test.index("SC-001")


def test_define_canvas_completeness():
    out = R.render_report("DEFINE", STAGES["DEFINE"])
    for token in ["핵심 매출", "custom_built", "execution", "장바구니", "OrderPlaced",
                  "주문하기", "게스트 미지원", "외부 PG", "성공률99", "롤백?", "취소 혼용",
                  "유비쿼터스 언어", "구매 요청 단위", "수신", "발신"]:
        assert token in out, f"BC 캔버스 필드 누락: {token}"
    assert "⚠️ 누락 보정" not in out


def test_tactical_stage_canvas_completeness():
    out = R.render_report("TACTICAL", STAGES["TACTICAL"])
    for token in ["AddToCart", "ItemAdded", "수량>0", "상품 존재", "재고부족 보류",
                  "상태 전이", "EMPTY", "ACTIVE", "특성", "50/s", "500/s", "1k", "30일"]:
        assert token in out, f"Aggregate 캔버스 필드 누락: {token}"
    assert "⚠️ 누락 보정" not in out


# --- 015-report-issue: 상위 phase 로 온 DDD 스테이지 초안도 리치 렌더 --------------

# 스테이지 → 상위 라이프사이클 phase(전략 3 / 전술 3).
_STAGE_UMBRELLA = {
    "DISCOVER": "STRATEGIC_DDD", "DECOMPOSE": "STRATEGIC_DDD", "STRATEGIZE": "STRATEGIC_DDD",
    "CONNECT": "TACTICAL_DDD", "DEFINE": "TACTICAL_DDD", "TACTICAL": "TACTICAL_DDD",
}
# 스테이지별 리치 렌더 시그니처(폴백엔 없는 헤더 토큰).
_STAGE_RICH_SIGNATURE = {
    "DISCOVER": "DDD Discover", "DECOMPOSE": "DDD Decompose", "STRATEGIZE": "DDD Strategize",
    "CONNECT": "DDD Connect", "DEFINE": "DDD Define", "TACTICAL": "DDD Tactical",
}


def test_umbrella_phase_stage_draft_renders_rich():
    """회귀 방지(015-report-issue): 스킬이 DDD 스테이지 초안을 상위 phase
    (STRATEGIC_DDD/TACTICAL_DDD)로 저장해도, 서버는 artifact 봉투 키에서 스테이지를
    복원해 **리치 렌더**를 내야 한다(키-값 폴백 테이블로 강등 금지).
    """
    for stage, envelope in STAGES.items():
        umbrella = _STAGE_UMBRELLA[stage]
        out = R.render_report(umbrella, envelope)
        # 리치 렌더 시그니처 존재 + 폴백 테이블 부재.
        assert _STAGE_RICH_SIGNATURE[stage] in out, (
            f"{umbrella}+{stage}: 리치 렌더 실패(폴백 강등) — {out[:120]}")
        assert "| 키 | 값 |" not in out, f"{umbrella}+{stage}: 폴백 키-값 테이블 강등"
        # stage 이름을 직접 넘긴 결과와 본문이 동일해야 함(경로 무관 동일 산출).
        assert out == R.render_report(stage, envelope)


# --- 015 scope-design: SCOPE 스테이지 플랜 스타일 B(전략/전술 2단 트리) ----------

SCOPE = {"stagePlan": {
    "version": 1,
    "classifiedReach": "신규 도메인 설계 — 온라인 쇼핑몰 주문 관리",
    "stages": [
        {"stage": "DISCOVER", "applies": True, "recommendSkip": False, "reason": "이벤트 스토밍 발굴"},
        {"stage": "DECOMPOSE", "applies": True, "recommendSkip": False, "reason": "서브도메인 분해"},
        {"stage": "STRATEGIZE", "applies": True, "recommendSkip": False, "reason": "Core/Supporting/Generic"},
        {"stage": "CONNECT", "applies": True, "recommendSkip": True, "reason": "단일 BC면 생략 가능"},
        {"stage": "DEFINE", "applies": True, "recommendSkip": False, "reason": "BC 캔버스"},
        {"stage": "TACTICAL", "applies": True, "recommendSkip": False, "reason": "Aggregate 설계", "skipped": True},
    ],
}}


def test_scope_stage_plan_style_b():
    out = R.render_report("SCOPE", SCOPE)
    # 제목 + 집계 헤더 + classifiedReach 인트로.
    assert out.startswith("## 📄 스코프(스테이지 플랜) 보고서")
    assert "🗺️ 스테이지 플랜 · 6 스테이지" in out
    assert "스코프 분류(classifiedReach):" in out and "온라인 쇼핑몰 주문 관리" in out
    # 전략/전술 2단 그룹 헤더 + D1 전각 공백 트리 들여쓰기.
    assert "**전략 DDD** (3)" in out and "**전술 DDD** (3)" in out
    assert "　└" in out
    # 6개 스테이지 라벨 전부 표현(누락 0).
    for label in ["Discover", "Decompose", "Strategize", "Connect", "Define", "Tactical"]:
        assert label in out, f"스테이지 누락: {label}"
    # 상태·생략권장·확정 구분(E1) + 사유 보존.
    assert "▶ 적용" in out
    assert "⏭️ 권장" in out                 # recommendSkip=True (CONNECT)
    assert "⛔ 생략확정" in out              # skipped=True (TACTICAL)
    assert "단일 BC면 생략 가능" in out       # reason 보존
    # 폴백 강등 금지 + 가드 오탐 없음.
    assert "| 키 | 값 |" not in out
    assert "⚠️ 누락 보정" not in out


def test_scope_envelope_and_bare_equivalent():
    """봉투({stagePlan:{...}})와 언랩({version,...}) 입력이 동일 렌더."""
    bare = SCOPE["stagePlan"]
    assert R.render_report("SCOPE", SCOPE) == R.render_report("SCOPE", bare)


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
    """대표 phase 최소 골든 스냅샷 — 구조 불변식(요약 헤더/트리 표/US 카드)."""
    out = R.render_report("STRATEGIC_DIFF", STRATEGIC)
    assert out.startswith("## 📄 전략 Diff 보고서")
    assert "**요약** — Epic 1 · Feature 1 · UserStory 2" in out
    assert "| 계층 · 항목 | tempId | 상위/BC | op |" in out
    assert "### UserStory 상세" in out
    # UserStory role/action/benefit 3요소 완전(target-01 핵심).
    assert "**역할(role)**: 고객" in out
    assert "**행동(action)**: 담는다" in out
    assert "**가치(benefit)**: 모아 주문" in out
    # 트리 계층 D1 전각 공백 들여쓰기.
    assert "　└" in out


def test_snapshot_discover():
    out = R.render_report("DISCOVER", STAGES["DISCOVER"])
    assert out.startswith("## 📄 Discover · 이벤트 발굴 보고서")
    assert "이벤트 스파인" in out
    assert "OrderPlaced" in out and "PaymentCompleted" in out
    # actor / 내부·외부 완전(target-06).
    assert "🌐 외부" in out and "🏠 내부" in out
    assert "⭐ 피벗" in out


def test_snapshot_tactical_tree_and_cards():
    out = R.render_report("TACTICAL_DIFF", TACTICAL)
    assert "| 계층 · 노드 | 변경 · 임팩트 | 참조(ref) |" in out
    assert "**상세 카드**" in out
    assert "| name | type |" in out
    assert "| 시나리오 | given.fieldValues | when.fieldValues | then.fieldValues |" in out


def test_constitution_sections_render():
    art = {"implementationPlan": {"version": 2,
           "architectureDecisions": [{"aspect": "배포 환경", "decision": "Kubernetes", "rationale": "확장"}],
           "constitutionGaps": ["서비스 메시 미결정"]}}
    out = R.render_report("CONSTITUTION", art)
    assert "구현계획 (Constitution) · v2" in out
    assert "결정 1건" in out and "미결 1건" in out
    assert "**결정**: Kubernetes" in out and "**근거**: 확장" in out
    assert "서비스 메시 미결정" in out


def test_constitution_no_gaps():
    art = {"implementationPlan": {"version": 1,
           "architectureDecisions": [{"aspect": "프론트엔드", "decision": "Vue 3", "rationale": "정합"}],
           "constitutionGaps": []}}
    out = R.render_report("CONSTITUTION", art)
    assert "미결 없음" in out


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
