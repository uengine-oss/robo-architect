"""Deterministically load the TM Forum ODA standard (golden) component designs
into the Neo4j event-storming graph so they render in the **Design tab**
(big-picture timeline / canvas) exactly as authored — 그대로.

Source of truth: the two ODA EventStorming canvases under /Users/uengine/oda-canvas
  - EventStorming-LayerB-OrderToActivate.md  (business golden components: Catalog,
    Party/Customer, Product Order, Service Order, Resource Order, Billing, Notification)
  - EventStorming-LayerA-Canvas.md           (management-plane components / Canvas operators)

Why not the LLM `/api/ingest/upload` pipeline? That path RE-DERIVES a model from
natural-language requirements (it extracted 0 user stories from these finished
design tables, and currently crashes on a latent `is_analyzer` bug). To load a
*finished* event-storming design faithfully we write the nodes directly, reusing
the proven `apply_tactical_diff` applier (same schema the Design tab reads:
BoundedContext-HAS_AGGREGATE->Aggregate-HAS_COMMAND->Command-EMITS->Event, plus
Event-TRIGGERS->Policy-INVOKES->Command for the cross-BC spine).

Run:  set -a; . ./.env; set +a; \
      PYTHONPATH=. uv run python scripts/load_oda_components.py
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from api.platform.neo4j import get_session
from api.features.proposal_lifecycle.services.proposal_apply import apply_tactical_diff

PROPOSAL_ID = "ODA-STANDARD"  # provenance tag (no Proposal node → no EFFECT edges)

_ES_LABELS = [
    "UserStory", "BoundedContext", "Aggregate", "Command", "Event",
    "ReadModel", "Policy", "Property", "CQRSConfig", "CQRSOperation",
    "UI", "GWT", "Feature", "Invariant",
]


# ─────────────────────────────────────────────────────────────────────────────
# ODA model definition (faithfully transcribed from the EventStorming canvases)
#
# Each BC: name / display(ko) / desc(SID·TMF mapping) / aggregates / commands /
# readmodels / invariants. Commands carry actor + which aggregate + emitted events.
# Cross/intra-BC reactions are declared in POLICIES (trigger event → invoke command).
# ─────────────────────────────────────────────────────────────────────────────

LAYER_B = [
    {
        "name": "ProductCatalog", "display": "상품 카탈로그",
        "desc": "TMF620 · SID:Product — 판매 가능 상품/요금제 카탈로그·자격확인",
        "aggregates": ["ProductOffering", "ProductSpecification", "PricePlan"],
        "commands": [
            {"name": "BrowseCatalog", "actor": "고객", "agg": "ProductOffering",
             "emits": [("ProductOfferingViewed", "상품 조회됨")]},
            {"name": "QualifyOffering", "actor": "CSR", "agg": "ProductOffering",
             "emits": [("ServiceQualificationCompleted", "서비스 자격확인 완료")]},
        ],
        "readmodels": ["판매가능상품목록", "가격프로모션뷰"],
    },
    {
        "name": "PartyCustomer", "display": "고객·계정",
        "desc": "TMF632/TMF666 · SID:EngagedParty,Customer — 고객/계정/청구계정",
        "aggregates": ["Party", "Customer", "BillingAccount"],
        "commands": [
            {"name": "RegisterCustomer", "actor": "CSR", "agg": "Customer",
             "emits": [("CustomerIdentified", "고객 식별됨")]},
            {"name": "OpenBillingAccount", "actor": "CSR", "agg": "BillingAccount",
             "emits": [("BillingAccountOpened", "청구계정 개설됨")]},
        ],
        "readmodels": ["Customer360뷰", "계정잔액"],
    },
    {
        "name": "ProductOrder", "display": "상품 주문 (Core Domain)",
        "desc": "TMF622 · SID:Product — 주문 접수·검증·수락·완료 (사가 시작점)",
        "aggregates": ["ProductOrder"],
        "commands": [
            {"name": "SubmitProductOrder", "actor": "고객", "agg": "ProductOrder",
             "emits": [("ProductOrderSubmitted", "상품주문 제출됨")]},
            {"name": "ValidateOrder", "actor": "system", "agg": "ProductOrder",
             "emits": [("ProductOrderValidated", "상품주문 검증됨"),
                       ("CreditCheckPassed", "신용평가 통과됨")]},
            {"name": "AcceptOrder", "actor": "system", "agg": "ProductOrder",
             "emits": [("ProductOrderAccepted", "상품주문 수락됨")]},
            {"name": "HoldOrder", "actor": "system", "agg": "ProductOrder",
             "emits": [("ProductOrderHeld", "상품주문 보류됨")]},
            {"name": "CompleteOrder", "actor": "system", "agg": "ProductOrder",
             "emits": [("ProductOrderCompleted", "상품주문 완료됨")]},
            {"name": "ActivateProduct", "actor": "system", "agg": "ProductOrder",
             "emits": [("ProductActivated", "상품 개통됨")]},
            {"name": "CancelOrder", "actor": "고객", "agg": "ProductOrder",
             "emits": [("ProductOrderCancelled", "상품주문 취소됨")]},
        ],
        "readmodels": ["주문상태추적", "진행률"],
        "invariants": {"ProductOrder": [
            "orderItem 은 최소 1개 이상 (len(orderItem) >= 1)",
            "모든 orderItem.productOffering 은 판매가능(qualified) 상태여야 제출 가능",
            "orderTotalPrice = Σ(orderItem.price) — 변경 시 재계산 일치",
            "acknowledged 이전엔 항목 추가/삭제 가능, 이후엔 취소만 가능",
            "상태는 정의된 전이만 허용",
            "completed/cancelled 는 종료 상태 — 이후 명령 거부",
            "relatedParty 에 Customer 1, BillingAccount 1 필수",
        ]},
    },
    {
        "name": "ServiceOrder", "display": "서비스 오케스트레이션",
        "desc": "TMF641 · SID:Service — 상품→서비스 분해·서비스 개통",
        "aggregates": ["ServiceOrder", "ServiceSpecification"],
        "commands": [
            {"name": "CreateServiceOrder", "actor": "system", "agg": "ServiceOrder",
             "emits": [("ServiceOrderCreated", "서비스주문 생성됨"),
                       ("ServiceOrderValidated", "서비스주문 검증됨")]},
            {"name": "ActivateService", "actor": "system", "agg": "ServiceOrder",
             "emits": [("ServiceActivated", "서비스 개통됨")]},
        ],
        "readmodels": ["서비스개통진행상태"],
    },
    {
        "name": "ResourceOrder", "display": "리소스 프로비저닝",
        "desc": "TMF652/TMF639 · SID:Resource — 번호/eSIM/네트워크 슬라이스 할당",
        "aggregates": ["ResourceOrder", "LogicalResource", "NetworkSlice"],
        "commands": [
            {"name": "CreateResourceOrder", "actor": "system", "agg": "ResourceOrder",
             "emits": [("ResourceOrderCreated", "리소스주문 생성됨")]},
            {"name": "ReserveNumber", "actor": "system", "agg": "LogicalResource",
             "emits": [("MSISDNAssigned", "MSISDN 할당됨")]},
            {"name": "ProvisionSIM", "actor": "system", "agg": "LogicalResource",
             "emits": [("eSIMProvisioned", "eSIM 프로비저닝됨")]},
            {"name": "ActivateSlice", "actor": "system", "agg": "NetworkSlice",
             "emits": [("NetworkSliceActivated", "네트워크 슬라이스 활성화됨")]},
        ],
        "readmodels": ["번호재고(MSISDN pool)", "리소스인벤토리"],
    },
    {
        "name": "InventoryBilling", "display": "인벤토리·과금",
        "desc": "TMF637/638/639, TMF678/676 · SID:Product,Customer — 인벤토리·구독·청구·결제",
        "aggregates": ["ProductInventory", "BillingSubscription", "Invoice", "Payment"],
        "commands": [
            {"name": "CreateSubscription", "actor": "system", "agg": "BillingSubscription",
             "emits": [("BillingSubscriptionCreated", "과금구독 생성됨"),
                       ("ProductInventoryUpdated", "상품인벤토리 갱신됨")]},
            {"name": "IssueInvoice", "actor": "system", "agg": "Invoice",
             "emits": [("FirstChargeApplied", "최초청구 적용됨")]},
            {"name": "CapturePayment", "actor": "system", "agg": "Payment",
             "emits": [("PaymentReceived", "결제 수신됨")]},
        ],
        "readmodels": ["활성가입상품목록", "청구서", "결제내역"],
    },
    {
        "name": "Notification", "display": "통지",
        "desc": "SID:Common / event hub — 개통완료 통지",
        "aggregates": ["CustomerNotification"],
        "commands": [
            {"name": "NotifyCustomer", "actor": "system", "agg": "CustomerNotification",
             "emits": [("CustomerNotified", "고객 통지됨")]},
        ],
        "readmodels": [],
    },
]

# Layer B cross/intra-BC reaction spine (the process backbone).
POLICIES_B = [
    {"name": "신용평가 요청", "bc": "ProductOrder", "trigger": "ProductOrderSubmitted", "invoke": "ValidateOrder"},
    {"name": "검증·신용 통과 시 수락", "bc": "ProductOrder", "trigger": "CreditCheckPassed", "invoke": "AcceptOrder"},
    {"name": "주문수락 시 서비스주문 생성", "bc": "ServiceOrder", "trigger": "ProductOrderAccepted", "invoke": "CreateServiceOrder"},
    {"name": "서비스검증 시 리소스주문 생성", "bc": "ResourceOrder", "trigger": "ServiceOrderValidated", "invoke": "CreateResourceOrder"},
    {"name": "슬라이스 활성화 시 서비스 개통", "bc": "ServiceOrder", "trigger": "NetworkSliceActivated", "invoke": "ActivateService"},
    {"name": "서비스 개통 시 상품 개통", "bc": "ProductOrder", "trigger": "ServiceActivated", "invoke": "ActivateProduct"},
    {"name": "상품 개통 시 과금구독 생성", "bc": "InventoryBilling", "trigger": "ProductActivated", "invoke": "CreateSubscription"},
    {"name": "주문 완료 시 고객 통지", "bc": "Notification", "trigger": "ProductOrderCompleted", "invoke": "NotifyCustomer"},
]

LAYER_A = [
    {
        "name": "ComponentLifecycle", "display": "컴포넌트 라이프사이클",
        "desc": "TMFOP001 · ODA Canvas — 컴포넌트 온보딩 사가 오케스트레이터",
        "aggregates": ["Component"],
        "commands": [
            {"name": "OnboardComponent", "actor": "Component Vendor", "agg": "Component",
             "emits": [("ComponentSubmitted", "컴포넌트 제출됨"),
                       ("ExposedAPICreated", "ExposedAPI 생성됨"),
                       ("DependentAPICreated", "DependentAPI 생성됨")]},
            {"name": "UpdateComponent", "actor": "Component Vendor", "agg": "Component",
             "emits": [("ComponentDeploymentCompleted", "컴포넌트 배포 완료됨")]},
            {"name": "DeleteComponent", "actor": "Platform Operator", "agg": "Component",
             "emits": [("ComponentSubResourcesCleaned", "하위 리소스 정리됨")]},
        ],
        "readmodels": ["배포진행률(status.summary)"],
    },
    {
        "name": "ApiExposure", "display": "API 노출·관측성",
        "desc": "TMFOP002 / Istio — VirtualService·관측성 구성",
        "aggregates": ["ExposedAPI"],
        "commands": [
            {"name": "ConfigureExposedAPI", "actor": "system", "agg": "ExposedAPI",
             "emits": [("VirtualServiceConfigured", "VirtualService 구성됨"),
                       ("APIImplementationReady", "API 구현 준비됨")]},
        ],
        "readmodels": ["ExposedAPI status(외부 URL)"],
    },
    {
        "name": "DependencyResolution", "display": "의존성 해소",
        "desc": "TMFOP005 — Service Inventory 기반 의존성 해소",
        "aggregates": ["DependentAPI"],
        "commands": [
            {"name": "DeclareDependentAPI", "actor": "system", "agg": "DependentAPI",
             "emits": [("DependencyResolved", "의존성 해소됨"),
                       ("DependentAPIReady", "DependentAPI 준비됨")]},
        ],
        "readmodels": ["Service Inventory(TMF638)"],
    },
    {
        "name": "IdentityConfig", "display": "아이덴티티 구성",
        "desc": "TMFOP003 / Keycloak — client/role 등록·listener",
        "aggregates": ["IdentityConfig"],
        "commands": [
            {"name": "ConfigureIdentity", "actor": "system", "agg": "IdentityConfig",
             "emits": [("IdentityRolesConfigured", "아이덴티티 역할 구성됨"),
                       ("RoleListenerRegistered", "역할 리스너 등록됨")]},
        ],
        "readmodels": ["등록된 listener 레지스트리"],
    },
    {
        "name": "SecretsManagement", "display": "시크릿 관리",
        "desc": "TMFOP007 / Vault — Vault 설정·사이드카 주입",
        "aggregates": ["SecretsManagement"],
        "commands": [
            {"name": "ConfigureSecrets", "actor": "system", "agg": "SecretsManagement",
             "emits": [("SecretsProvisioned", "시크릿 프로비저닝됨"),
                       ("SecretsManagementReady", "시크릿 관리 준비됨")]},
        ],
        "readmodels": [],
    },
    {
        "name": "EventManagement", "display": "이벤트 관리",
        "desc": "TMFOP006 (Planned) — Published/Subscribed Notification 배선",
        "aggregates": ["NotificationCR"],
        "commands": [
            {"name": "WireEventTopic", "actor": "system", "agg": "NotificationCR",
             "emits": [("EventTopicCreated", "이벤트 토픽 생성됨"),
                       ("SubscriptionRegistered", "구독 등록됨")]},
        ],
        "readmodels": [],
    },
    {
        "name": "Availability", "display": "가용성",
        "desc": "TMFOP010 — PodDisruptionBudget 적용",
        "aggregates": ["AvailabilityPolicy"],
        "commands": [
            {"name": "ApplyAvailabilityPolicy", "actor": "system", "agg": "AvailabilityPolicy",
             "emits": [("PodDisruptionBudgetApplied", "PDB 적용됨")]},
        ],
        "readmodels": [],
    },
    {
        "name": "CarbonFootprint", "display": "탄소 발자국",
        "desc": "TMFOP011 — 탄소 메트릭 기록",
        "aggregates": ["CarbonFootprint"],
        "commands": [
            {"name": "RecordCarbonFootprint", "actor": "system", "agg": "CarbonFootprint",
             "emits": [("CarbonFootprintRecorded", "탄소 발자국 기록됨")]},
        ],
        "readmodels": ["탄소 메트릭"],
    },
]

POLICIES_A = [
    {"name": "컴포넌트 제출 시 서브리소스 생성", "bc": "ApiExposure", "trigger": "ComponentSubmitted", "invoke": "ConfigureExposedAPI"},
    {"name": "ExposedAPI 생성 시 의존성 선언", "bc": "DependencyResolution", "trigger": "ExposedAPICreated", "invoke": "DeclareDependentAPI"},
    {"name": "API 준비 시 아이덴티티 구성", "bc": "IdentityConfig", "trigger": "APIImplementationReady", "invoke": "ConfigureIdentity"},
    {"name": "아이덴티티 구성 시 시크릿 구성", "bc": "SecretsManagement", "trigger": "IdentityRolesConfigured", "invoke": "ConfigureSecrets"},
    {"name": "시크릿 준비 시 배포 완료", "bc": "ComponentLifecycle", "trigger": "SecretsManagementReady", "invoke": "UpdateComponent"},
]


def build_tactical_diff(bcs: list[dict], policies: list[dict]) -> list[dict]:
    items: list[dict] = []
    for bc in bcs:
        bc_temp = f"bc:{bc['name']}"
        items.append({
            "nodeLabel": "BoundedContext", "changeType": "CREATE",
            "nodeTitle": bc["name"], "tempId": bc_temp,
            "fields": {"displayName": bc["display"], "description": bc["desc"]},
        })
        for agg in bc["aggregates"]:
            items.append({
                "nodeLabel": "Aggregate", "changeType": "CREATE",
                "nodeTitle": agg, "tempId": f"agg:{agg}",
                "boundedContextId": bc_temp,
                "invariants": [{"declaration": d} for d in bc.get("invariants", {}).get(agg, [])],
            })
        for cmd in bc["commands"]:
            cmd_temp = f"cmd:{cmd['name']}"
            items.append({
                "nodeLabel": "Command", "changeType": "CREATE",
                "nodeTitle": cmd["name"], "tempId": cmd_temp,
                "aggregateId": f"agg:{cmd['agg']}",
                "fields": {"actor": cmd.get("actor", "system")},
            })
            for evt_name, evt_disp in cmd["emits"]:
                items.append({
                    "nodeLabel": "Event", "changeType": "CREATE",
                    "nodeTitle": evt_name, "tempId": f"evt:{evt_name}",
                    "commandId": cmd_temp,
                    "fields": {"displayName": evt_disp},
                })
        for rm in bc.get("readmodels", []):
            items.append({
                "nodeLabel": "ReadModel", "changeType": "CREATE",
                "nodeTitle": rm, "tempId": f"rm:{bc['name']}:{rm}",
                "boundedContextId": bc_temp,
            })
    for pol in policies:
        items.append({
            "nodeLabel": "Policy", "changeType": "CREATE",
            "nodeTitle": pol["name"], "tempId": f"pol:{pol['name']}",
            "boundedContextId": f"bc:{pol['bc']}",
            "triggerEventId": f"evt:{pol['trigger']}",
            "invokeCommandId": f"cmd:{pol['invoke']}",
        })
    return items


def clear_es(session) -> dict:
    counts = {}
    for label in _ES_LABELS:
        r = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
        if r and r["c"]:
            counts[label] = r["c"]
    for label in reversed(_ES_LABELS):
        session.run(f"MATCH (n:{label}) DETACH DELETE n")
    return counts


def main() -> None:
    tactical = build_tactical_diff(LAYER_B, POLICIES_B) + build_tactical_diff(LAYER_A, POLICIES_A)
    print(f"[oda] tactical items: {len(tactical)}")

    with get_session() as session:
        deleted = clear_es(session)
        print(f"[oda] cleared existing ES nodes: {deleted or '(none)'}")

        ref_map: dict = {}
        applied = apply_tactical_diff(session, PROPOSAL_ID, tactical, ref_map)
        print(f"[oda] applied tactical items: {applied}")

        # Verify the Design-tab contract.
        summary = session.run(
            """
            MATCH (bc:BoundedContext)
            OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(a:Aggregate)
            OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(c:Command)
            OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(:Command)-[:EMITS]->(e:Event)
            OPTIONAL MATCH (bc)-[:HAS_POLICY]->(p:Policy)
            RETURN bc.name AS bc, count(DISTINCT a) AS agg, count(DISTINCT c) AS cmd,
                   count(DISTINCT e) AS evt, count(DISTINCT p) AS pol
            ORDER BY bc
            """
        ).data()
        print("\n[oda] per-BC (agg/cmd/evt/pol):")
        tot = {"agg": 0, "cmd": 0, "evt": 0, "pol": 0}
        for r in summary:
            print(f"   {r['bc']:<22} agg={r['agg']} cmd={r['cmd']} evt={r['evt']} pol={r['pol']}")
            for k in tot:
                tot[k] += r[k]
        spine = session.run(
            "MATCH (e:Event)-[:TRIGGERS]->(p:Policy)-[:INVOKES]->(c:Command) RETURN count(*) AS n"
        ).single()["n"]
        print(f"\n[oda] BCs={len(summary)}  aggregates={tot['agg']}  commands={tot['cmd']}  "
              f"events={tot['evt']}  policies={tot['pol']}  spine(TRIGGERS-INVOKES)={spine}")


if __name__ == "__main__":
    main()
