from __future__ import annotations

from api.features.requirement_changes.requirement_changes_contracts import (
    EffectItem,
    ImpactLevel,
    RegressionAnalysis,
    RegressionTestItem,
)
from api.platform.neo4j import get_session


def analyze_regression(change_id: str) -> RegressionAnalysis:
    """Change의 EFFECT 대상을 그래프 트래버설로 분석하여 회귀 테스트 대상 반환."""

    # 1. EFFECT 대상 노드 조회
    effects_query = """
    MATCH (chg:RequirementChange {id: $id})-[e:EFFECT]->(n)
    RETURN n.id AS nodeId,
           labels(n)[0] AS nodeLabel,
           COALESCE(n.title, n.name, n.action, '') AS nodeTitle,
           e.reason AS reason,
           e.impactLevel AS impactLevel
    """
    with get_session() as session:
        result = session.run(effects_query, id=change_id)
        effect_rows = result.data()

    impacted = [
        EffectItem(
            nodeId=r["nodeId"] or "",
            nodeLabel=r["nodeLabel"] or "",
            nodeTitle=r["nodeTitle"] or "",
            reason=r["reason"] or "",
            impactLevel=ImpactLevel(r.get("impactLevel") or "LOW"),
        )
        for r in effect_rows
        if r["nodeId"]
    ]

    has_contract = any(r["nodeLabel"] == "BoundedContext" for r in effect_rows)
    has_e2e = False

    # 2. 테스트 노드 트래버설 (있을 경우)
    test_query = """
    MATCH (chg:RequirementChange {id: $id})-[:EFFECT]->(n)
    OPTIONAL MATCH (n)-[:IMPLEMENTS|HAS_AGGREGATE|HAS_COMMAND*1..3]->(design)
    OPTIONAL MATCH (test:Test)-[:TESTS_FOR]->(design)
    RETURN n.id AS nodeId, labels(n)[0] AS nodeLabel,
           design.id AS designId, labels(design)[0] AS designLabel,
           test.id AS testId, test.type AS testType, test.description AS testDesc
    """
    with get_session() as session:
        result = session.run(test_query, id=change_id)
        test_rows = result.data()

    regression_tests: list[RegressionTestItem] = []
    seen = set()

    for r in test_rows:
        if r.get("nodeLabel") == "UserStory":
            has_e2e = True  # US가 EFFECT 대상이면 E2E 가능성

        if r.get("testId") and r["testId"] not in seen:
            seen.add(r["testId"])
            regression_tests.append(
                RegressionTestItem(
                    testId=r["testId"],
                    testType=r.get("testType") or "unit",
                    description=r.get("testDesc") or f"테스트 연결: {r['testId']}",
                    affectedNodeId=r.get("designId") or r["nodeId"],
                    affectedNodeLabel=r.get("designLabel") or r["nodeLabel"],
                )
            )

    # 테스트 노드 없어도 BC 대상이면 계약 테스트 항목 추가
    if has_contract and not any(t.testType == "contract" for t in regression_tests):
        bc_nodes = [r for r in effect_rows if r["nodeLabel"] == "BoundedContext"]
        for bc in bc_nodes:
            regression_tests.append(
                RegressionTestItem(
                    testId=None,
                    testType="contract",
                    description=f"BoundedContext({bc['nodeId']}) 계약 테스트 확인 필요",
                    affectedNodeId=bc["nodeId"],
                    affectedNodeLabel="BoundedContext",
                )
            )

    if has_e2e:
        regression_tests.append(
            RegressionTestItem(
                testId=None,
                testType="e2e",
                description="UI 흐름 포함 UserStory가 변경됨 — E2E 테스트 검토 필요",
                affectedNodeId=change_id,
                affectedNodeLabel="RequirementChange",
            )
        )

    return RegressionAnalysis(
        changeId=change_id,
        impactedDesignNodes=impacted,
        regressionTests=regression_tests,
        hasContractTests=has_contract,
        hasE2ETests=has_e2e,
    )
