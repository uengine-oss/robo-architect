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
