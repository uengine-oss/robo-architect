"""041 — Constitution + Plan stage 단위 테스트 (Neo4j 불필요, 순수 로직)."""

import json

from api.features.proposal_lifecycle.proposal_contracts import (
    ImplementationPlan, ArchitectureDecision, ProposalResponse,
    REQUIRED_ARCHITECTURE_ASPECTS, MICROSERVICE_REQUIRED_ASPECTS,
    constitution_hash, InterContextIntegration, ServiceDevEnvironment,
)


def _plan_with(aspects, **kw):
    return ImplementationPlan(
        architectureDecisions=[ArchitectureDecision(aspect=a, decision="x") for a in aspects],
        **kw,
    )


def test_constitution_hash_stable_and_differs():
    assert constitution_hash(None) is None
    assert constitution_hash("a") == constitution_hash("a")
    assert constitution_hash("a") != constitution_hash("b")


def test_monolith_plan_complete_with_five_aspects():
    plan = _plan_with(REQUIRED_ARCHITECTURE_ASPECTS)
    assert plan.is_complete("MONOLITH", 1) is True


def test_microservices_requires_extra_aspects():
    plan = _plan_with(REQUIRED_ARCHITECTURE_ASPECTS)
    # 5개만으로는 마이크로서비스+다수컨텍스트 완전성 미충족 (SC-003)
    assert plan.is_complete("MICROSERVICES", 3) is False
    full = _plan_with(
        REQUIRED_ARCHITECTURE_ASPECTS + MICROSERVICE_REQUIRED_ASPECTS,
        messagingChannel="Kafka",
        interContextIntegrations=[
            InterContextIntegration(fromContext="Ordering", toContext="Payment",
                                    message="ChargePayment", kind="COMMAND", sync=True)
        ],
        serviceDevEnvironments=[
            ServiceDevEnvironment(service="Ordering", dependencies=["kafka"])
        ],
    )
    assert full.is_complete("MICROSERVICES", 3) is True


def test_gap_counts_as_covered():
    plan = _plan_with([a for a in REQUIRED_ARCHITECTURE_ASPECTS if a != "INGRESS"],
                      constitutionGaps=["INGRESS"])
    assert plan.is_complete("MONOLITH", 1) is True


def _node(**over):
    base = {
        "id": "PRO-001", "title": "t", "originalPrompt": "p", "author": "a",
        "status": "DRAFT",
    }
    base.update(over)
    return base


def test_plan_stale_on_constitution_hash_mismatch():
    plan = _plan_with(REQUIRED_ARCHITECTURE_ASPECTS)
    plan_dict = json.loads(plan.model_dump_json())
    plan_dict["constitutionHash"] = "OLD"
    node = _node(
        implementationPlan=json.dumps(plan_dict),
        constitutionHash="NEW",
        strategicDiff=json.dumps({"version": 1}),
    )
    resp = ProposalResponse.from_neo4j(node, [])
    assert resp.planStale is True


def test_plan_not_stale_when_hash_and_version_match():
    plan = _plan_with(REQUIRED_ARCHITECTURE_ASPECTS, strategicVersion=2)
    plan_dict = json.loads(plan.model_dump_json())
    plan_dict["constitutionHash"] = "H"
    node = _node(
        implementationPlan=json.dumps(plan_dict),
        constitutionHash="H",
        strategicDiff=json.dumps({"version": 2}),
    )
    resp = ProposalResponse.from_neo4j(node, [])
    assert resp.planStale is False


def test_plan_stale_when_strategic_version_advances():
    plan = _plan_with(REQUIRED_ARCHITECTURE_ASPECTS, strategicVersion=1)
    plan_dict = json.loads(plan.model_dump_json())
    plan_dict["constitutionHash"] = "H"
    node = _node(
        implementationPlan=json.dumps(plan_dict),
        constitutionHash="H",
        strategicDiff=json.dumps({"version": 3}),  # intent 재실행으로 버전 상승
    )
    resp = ProposalResponse.from_neo4j(node, [])
    assert resp.planStale is True
