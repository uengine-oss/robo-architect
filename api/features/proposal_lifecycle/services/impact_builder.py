"""
robo-proposal CONTEXT phase 호출 서비스.
그래프 탐색으로 Impact Map(영향 노드 목록 + conflictLevel) 생성.
"""

from __future__ import annotations

import json

from api.platform.neo4j import get_session
from api.platform.neo4j_helpers import load_domain_nodes
from api.platform.observability.smart_logger import SmartLogger
from api.platform.skill_runner import run_skill_once, extract_json

_SKILL_ROOT = "robo-proposals"
_SKILL_NAME = "robo-proposal"


async def build_impact_map(proposal_id: str, tactical_diff: list[dict]) -> list[dict]:
    """
    robo-proposal CONTEXT phase를 호출하여 ImpactMap을 생성하고 Neo4j에 저장한다.
    Returns: ImpactMapEntry 목록 (dict 형태)
    """
    SmartLogger.log("INFO", f"impact_map_start: {proposal_id}",
                    category="proposal_lifecycle.impact.start",
                    params={"proposalId": proposal_id})

    domain_nodes = load_domain_nodes()
    node_list = "\n".join(
        f"- id: {n['id']}, type: {n.get('label', '')}, name: {n.get('name', '')}"
        for n in domain_nodes
    )

    tactical_str = json.dumps(tactical_diff, ensure_ascii=False, indent=2)

    human_prompt = (
        "phase: CONTEXT\n"
        f"Proposal ID: {proposal_id}\n\n"
        f"Tactical Diff (변경 예정 도메인 요소):\n{tactical_str}\n\n"
        f"현재 시스템 구성 요소:\n{node_list or '(구성 요소 없음)'}\n\n"
        "위 변경이 영향을 미치는 노드 목록과 충돌 가능성(HIGH/MEDIUM/LOW)을 ImpactMap JSON으로 출력하세요."
    )

    raw = await run_skill_once(_SKILL_ROOT, _SKILL_NAME, human_prompt, timeout=60)

    if not raw:
        # 스킬 미구현 시 fallback: TacticalDiff 기반 단순 매핑
        return _fallback_impact_map(proposal_id, tactical_diff, domain_nodes)

    result = extract_json(raw)
    if not result:
        return _fallback_impact_map(proposal_id, tactical_diff, domain_nodes)

    impact_entries = result if isinstance(result, list) else result.get("impactMap", [])

    # 고아 노드 처리: nodeId가 없으면 "관련 노드 없음"
    processed = []
    for entry in impact_entries:
        if not entry.get("nodeId"):
            entry["conflictLevel"] = "NONE"
            entry["reason"] = entry.get("reason", "관련 노드 없음")
        processed.append(entry)

    _save_impact_map(proposal_id, processed)
    SmartLogger.log("INFO", f"Impact map saved: {proposal_id}, {len(processed)} entries",
                    category="proposal_lifecycle.impact.done",
                    params={"proposalId": proposal_id, "count": len(processed)})
    return processed


def _fallback_impact_map(proposal_id: str, tactical_diff: list[dict], domain_nodes: list[dict]) -> list[dict]:
    """스킬 미사용 시 TacticalDiff 기반 단순 Impact Map."""
    node_map = {n["id"]: n for n in domain_nodes}
    entries = []
    for item in (tactical_diff or []):
        node_id = item.get("nodeId")
        if node_id and node_id in node_map:
            n = node_map[node_id]
            entries.append({
                "nodeId": node_id,
                "nodeLabel": n.get("label", item.get("nodeLabel", "")),
                "nodeTitle": n.get("name", item.get("nodeTitle", "")),
                "conflictLevel": item.get("impactLevel", "MEDIUM"),
                "reason": f"TacticalDiff {item.get('changeType', 'MODIFY')} 작업",
            })
        elif node_id:
            entries.append({
                "nodeId": node_id,
                "nodeLabel": item.get("nodeLabel", ""),
                "nodeTitle": item.get("nodeTitle", ""),
                "conflictLevel": "NONE",
                "reason": "관련 노드 없음",
            })

    if entries:
        _save_impact_map(proposal_id, entries)
    return entries


def _save_impact_map(proposal_id: str, entries: list[dict]) -> None:
    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id: $id}) SET p.impactMap = $impactMap",
            id=proposal_id,
            impactMap=json.dumps(entries, ensure_ascii=False),
        )
