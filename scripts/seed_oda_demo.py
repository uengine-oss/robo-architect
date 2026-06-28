"""매뉴얼 데모용 ODA_STANDARD Proposal 시드. (run: uv run python scripts/seed_oda_demo.py)

OdaStandardTrack 패널이 가득 차게 보이도록 alignment/conformance(FAIL+violations+items)/
artifacts 를 채운다. FAIL 게이트로 두어 '면제(waive)' 인터랙션을 시연할 수 있게 한다.
"""

import json
from datetime import datetime, timezone

from api.platform.neo4j import get_session

PID = "PRO-ODA-DEMO"

alignment = {
    "useCases": [{"id": "UC003", "intent": "주문 우선처리(expedite)와 수수료 부과",
                  "source": "repo/usecase-library/UC003"}],
    "sidEntities": [{"name": "Customer", "domain": "Customer", "source": "sid/markdown/Customer.md"},
                    {"name": "ProductOrder", "domain": "Product", "source": "sid/markdown/Product.md"}],
    "tmfApis": [{"id": "TMF622", "name": "Product Ordering", "version": "v4"}],
    "componentBlock": "coreFunction",
    "notes": "",
}

conformance = {
    "baseline": "SID v22 / TMF622 v4",
    "items": [
        {"element": "Customer", "kind": "entity", "classification": "REUSE",
         "source": "sid/markdown/Customer.md"},
        {"element": "ProductOrder", "kind": "entity", "classification": "REUSE",
         "source": "sid/markdown/Product.md"},
        {"element": "ProductOrder.expediteFee", "kind": "attribute", "classification": "EXTEND",
         "mechanism": "characteristic", "justification": "비표준 수수료 → Characteristic 패턴"},
        {"element": "ExpediteOrder", "kind": "operation", "classification": "NEW",
         "justification": "표준 미정의 신규 오퍼레이션"},
    ],
    # FAIL 유발 위반 — 시연에서 '면제'로 풀 수 있게 둔다.
    "violations": [
        {"rule": "non_additive_change", "element": "ProductOrder.orderDate",
         "detail": "표준 필드 타입을 string→date 로 재정의(재타이핑) — 추가형이 아님"},
    ],
    "gateResult": "FAIL",
}

artifacts = {
    "dataModel": {"entities": [
        {"name": "ProductOrder", "reuseOf": "SID:ProductOrder",
         "addedAttributes": [{"name": "expediteFee", "mechanism": "characteristic",
                              "justification": "우선처리 수수료"}]}]},
    "contracts": [{"api": "TMF622", "operations": [
        {"name": "POST /productOrder", "classification": "REUSE"},
        {"name": "POST /productOrder/{id}/expedite", "classification": "NEW"}]}],
    "architecture": {
        "coreFunction": ["ProductOrderingManagement"],
        "managementFunction": [], "securityFunction": [],
        "exposedAPIs": ["TMF622"], "dependentAPIs": ["TMF629"],
        "events": ["ProductOrderExpedited"], "canvasOperators": ["api-operator", "identity-config"]},
    "featureFiles": [{"filename": "UC003-F001-ExpediteOrder.feature",
                      "content": "@UC003\nFeature: UC003-F001 Expedite Order\n  Scenario Outline: ..."}],
}

strategic = {
    "version": 1,
    "userStories": [{"entityTitle": "주문 우선처리", "role": "고객",
                     "action": "주문을 우선처리하고 수수료를 지불한다"}],
}

with get_session() as s:
    s.run("MATCH (p:Proposal {id:$id}) DETACH DELETE p", id=PID)
    s.run(
        """
        CREATE (p:Proposal {
            id:$id, title:$title, originalPrompt:$prompt, author:'manual-demo',
            createdAt: datetime($createdAt), status:'DRAFT', statusHistory:'[]',
            clarificationLog:'[]', decompositionMode:'ODA_STANDARD',
            strategicDiff:$sd, odaAlignment:$align, odaConformance:$conf, odaArtifacts:$arts
        })
        """,
        id=PID, title="주문 우선처리 (ODA 표준 데모)",
        prompt="고객이 주문을 우선처리(expedite)하고 수수료를 부과한다",
        createdAt=datetime.now(timezone.utc).isoformat(),
        sd=json.dumps(strategic, ensure_ascii=False),
        align=json.dumps(alignment, ensure_ascii=False),
        conf=json.dumps(conformance, ensure_ascii=False),
        arts=json.dumps(artifacts, ensure_ascii=False),
    )
print(f"seeded {PID}")


# --- SUBMITTED(=Plan 단계) ODA Proposal — Plan 탭/Impact 탭 결정적 캡처용 ----
PID2 = "PRO-ODA-PLAN"

# 게이트는 면제(WAIVED)되어 plan/submit 통과한 상태.
conformance2 = dict(conformance)
conformance2["gateResult"] = "WAIVED"
conformance2["waiver"] = {"reason": "표준 위반은 차기 릴리스에서 해소 — 리스크 수용",
                          "at": datetime.now(timezone.utc).isoformat()}

# ODA 산출물이 수렴한 표준 tacticalDiff(Impact 탭 시각화).
tactical = [
    {"nodeId": "agg-ProductOrder", "entityTitle": "ProductOrder", "label": "Aggregate",
     "impactLevel": "HIGH", "changeType": "MODIFY"},
    {"nodeId": "cmd-ExpediteOrder", "entityTitle": "ExpediteOrder", "label": "Command",
     "impactLevel": "MEDIUM", "changeType": "CREATE"},
    {"nodeId": "evt-ProductOrderExpedited", "entityTitle": "ProductOrderExpedited",
     "label": "Event", "impactLevel": "LOW", "changeType": "CREATE"},
]
impact_map = [
    {"nodeId": "agg-ProductOrder", "nodeLabel": "Aggregate", "nodeTitle": "ProductOrder",
     "conflictLevel": "LOW", "reason": "expediteFee 특성 추가(추가형)"},
]

# 041 Constitution 기반 구현계획(ODA 모드도 무분기로 동일 PlanView 사용).
impl_plan = {
    "version": 1,
    "tacticalSummary": "ProductOrder 애그리거트에 우선처리(expedite) 명령/이벤트와 수수료 특성을 추가.",
    "architectureDecisions": [
        {"aspect": "DEPLOYMENT_ENV", "decision": "Kubernetes + ODA Canvas",
         "rationale": "ODA Component CRD(oda.tmforum.org/v1) 배포", "constitutionRef": "PROJECT"},
        {"aspect": "INGRESS", "decision": "Istio API Gateway",
         "rationale": "Canvas 표준 게이트웨이", "constitutionRef": "PROJECT"},
        {"aspect": "SERVICE_MESH_FRAMEWORK", "decision": "Istio",
         "rationale": "Canvas 서비스 메시", "constitutionRef": "PROJECT"},
        {"aspect": "FRONTEND", "decision": "변경 없음", "rationale": "백엔드 API 확장만",
         "constitutionRef": "PROJECT"},
        {"aspect": "REPO_MAPPING", "decision": "product-ordering 서비스 레포",
         "rationale": "단일 BC", "constitutionRef": "PROJECT"},
    ],
    "constitutionGaps": [],
    "interContextIntegrations": [
        {"fromContext": "ProductOrdering", "toContext": "Customer", "message": "GetCustomerCredit",
         "kind": "QUERY", "sync": True, "rationale": "수수료 부과 전 신용 확인(동기)"},
        {"fromContext": "ProductOrdering", "toContext": "Billing", "message": "ProductOrderExpedited",
         "kind": "EVENT", "sync": False, "rationale": "수수료 청구는 이벤트 pub/sub"},
    ],
    "messagingChannel": "Kafka",
    "serviceDevEnvironments": [
        {"service": "product-ordering", "runtime": "JDK 21 / Spring Boot 3",
         "dockerBaseImage": "eclipse-temurin:21-jre", "dependencies": ["kafka", "postgres"],
         "composeServices": ["kafka", "postgres"],
         "scopeNote": "product-ordering 레포만 클론해 docker compose up 으로 로컬 구동"},
    ],
    "constitutionHash": "demo-hash", "strategicVersion": 1,
}
history2 = json.dumps([{"from": "DRAFT", "to": "SUBMITTED", "by": "manual-demo",
                        "at": datetime.now(timezone.utc).isoformat()}], ensure_ascii=False)

with get_session() as s:
    s.run("MATCH (p:Proposal {id:$id}) DETACH DELETE p", id=PID2)
    s.run(
        """
        CREATE (p:Proposal {
            id:$id, title:$title, originalPrompt:$prompt, author:'manual-demo',
            createdAt: datetime($createdAt), status:'SUBMITTED', statusHistory:$hist,
            clarificationLog:'[]', decompositionMode:'ODA_STANDARD',
            strategicDiff:$sd, tacticalDiff:$td, impactMap:$im,
            implementationPlan:$plan, constitutionHash:'demo-hash',
            odaAlignment:$align, odaConformance:$conf, odaArtifacts:$arts
        })
        """,
        id=PID2, title="주문 우선처리 — Plan 단계 (ODA 표준 데모)",
        prompt="고객이 주문을 우선처리(expedite)하고 수수료를 부과한다",
        createdAt=datetime.now(timezone.utc).isoformat(), hist=history2,
        sd=json.dumps(strategic, ensure_ascii=False),
        td=json.dumps(tactical, ensure_ascii=False),
        im=json.dumps(impact_map, ensure_ascii=False),
        plan=json.dumps(impl_plan, ensure_ascii=False),
        align=json.dumps(alignment, ensure_ascii=False),
        conf=json.dumps(conformance2, ensure_ascii=False),
        arts=json.dumps(artifacts, ensure_ascii=False),
    )
print(f"seeded {PID2}")
