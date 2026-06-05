from __future__ import annotations

import json
import re
import uuid

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger


def create_direct_effects(change_id: str, node_ids: list[str]) -> None:
    """DIRECT_EDIT 타입 Change의 EFFECT 관계를 즉시 생성한다."""
    query = """
    MATCH (chg:RequirementChange {id: $change_id})
    MATCH (n) WHERE n.id = $node_id
    MERGE (chg)-[e:EFFECT]->(n)
    ON CREATE SET e.reason = '직접 수정', e.impactLevel = 'HIGH'
    ON MATCH SET e.reason = '직접 수정', e.impactLevel = 'HIGH'
    """
    with get_session() as session:
        for node_id in node_ids:
            session.run(query, change_id=change_id, node_id=node_id)


def create_effects_from_analysis(change_id: str, effects: list[dict]) -> None:
    """분석 결과로 EFFECT(MODIFY) 관계를 생성한다 (MERGE로 중복 방지)."""
    query = """
    MATCH (chg:RequirementChange {id: $change_id})
    MATCH (n) WHERE n.id = $node_id
    MERGE (chg)-[e:EFFECT]->(n)
    ON CREATE SET e.reason = $reason, e.impactLevel = $impact_level, e.changeType = 'MODIFY'
    ON MATCH SET e.reason = $reason, e.impactLevel = $impact_level, e.changeType = 'MODIFY'
    """
    with get_session() as session:
        for effect in effects:
            session.run(
                query,
                change_id=change_id,
                node_id=effect["nodeId"],
                reason=effect.get("reason", ""),
                impact_level=effect.get("impactLevel", "LOW"),
            )


def create_creation_intents(change_id: str, new_nodes: list[dict]) -> None:
    """newNodes 목록에서 CreationIntent 플레이스홀더 노드 + EFFECT(CREATE) 관계를 생성한다."""
    query = """
    MATCH (chg:RequirementChange {id: $change_id})
    CREATE (ci:CreationIntent {
        id: $placeholder_id,
        nodeLabel: $node_label,
        templateData: $template_json,
        reason: $reason,
        createdAt: datetime()
    })
    CREATE (chg)-[e:EFFECT]->(ci)
    SET e.reason = $reason,
        e.impactLevel = $impact_level,
        e.changeType = 'CREATE',
        e.templateData = $template_json
    """
    with get_session() as session:
        for node in new_nodes:
            placeholder_id = f"ci-{uuid.uuid4()}"
            template_json = json.dumps(node.get("templateData", {}), ensure_ascii=False)
            session.run(
                query,
                change_id=change_id,
                placeholder_id=placeholder_id,
                node_label=node.get("nodeLabel", ""),
                template_json=template_json,
                reason=node.get("reason", ""),
                impact_level=node.get("impactLevel", "MEDIUM"),
            )


def load_domain_nodes() -> list[dict]:
    """UserStory·BoundedContext·Aggregate·Feature 노드 목록을 Neo4j에서 조회한다."""
    query = """
    MATCH (n)
    WHERE n:UserStory OR n:BoundedContext OR n:Aggregate OR n:Feature
    RETURN n.id AS id,
           labels(n)[0] AS label,
           COALESCE(n.title, n.name, n.action, n.key, '') AS name
    LIMIT 200
    """
    with get_session() as session:
        result = session.run(query)
        return result.data()


def extract_title_from_prompt(prompt: str) -> str:
    """프롬프트 첫 문장 또는 첫 30자를 제목으로 추출한다."""
    first = re.split(r'[.!?\n]', prompt.strip())[0].strip()
    if len(first) > 40:
        first = first[:40] + '...'
    return first or prompt[:40]


async def run_effect_analysis(change_id: str, original_prompt: str) -> dict | None:
    """
    robo-change-specify 스킬을 통해 영향도를 분석하고 EFFECT 관계를 생성한다.
    성공 시 {"title": ..., "effects": [...]} 반환.
    """
    from api.features.requirement_changes.services.skill_runner import run_specify_skill

    nodes = load_domain_nodes()
    result = await run_specify_skill(change_id, original_prompt, nodes)

    if result and result.get("effects"):
        create_effects_from_analysis(change_id, result["effects"])
        SmartLogger.log("INFO",
                        f"EFFECT relations created: {len(result['effects'])} for {change_id}",
                        category="requirement_changes.effect.created",
                        params={"changeId": change_id, "count": len(result["effects"])})

    if result and result.get("newNodes"):
        create_creation_intents(change_id, result["newNodes"])
        SmartLogger.log("INFO",
                        f"CreationIntent nodes created: {len(result['newNodes'])} for {change_id}",
                        category="requirement_changes.effect.creation_intents",
                        params={"changeId": change_id, "count": len(result["newNodes"])})

    return result
