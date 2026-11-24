from __future__ import annotations

from typing import Any, Dict, List


def get_node_contexts(session, node_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Resolve (bcId, bcName) for each node id in one query.
    """
    if not node_ids:
        return {}

    query = """
    UNWIND $node_ids as node_id
    MATCH (n {id: node_id})
    WITH n, labels(n)[0] as nodeType, node_id

    // Find parent BC based on known containment patterns
    OPTIONAL MATCH (bc1:BoundedContext {id: node_id})
    OPTIONAL MATCH (bc2:BoundedContext)-[:HAS_AGGREGATE]->(n)
    OPTIONAL MATCH (bc3:BoundedContext)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(n)
    OPTIONAL MATCH (bc4:BoundedContext)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(:Command)-[:EMITS]->(n)
    OPTIONAL MATCH (bc5:BoundedContext)-[:HAS_POLICY]->(n)

    WITH n, nodeType, coalesce(bc1, bc2, bc3, bc4, bc5) as bc
    RETURN collect({
        nodeId: n.id,
        nodeType: nodeType,
        bcId: bc.id,
        bcName: bc.name
    }) as results
    """
    rec = session.run(query, node_ids=node_ids).single()
    if not rec:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for row in rec["results"] or []:
        nid = row.get("nodeId")
        if nid:
            out[nid] = row
    return out


def fetch_2hop_subgraph(session, node_id: str, rel_types: List[str]) -> Dict[str, Any]:
    """
    Fetch a 2-hop context subgraph around a node using a whitelist of relationship types.

    Returns {nodes: [...], relationships: [...]} where relationships preserve direction.
    """
    if not node_id:
        return {"nodes": [], "relationships": []}

    rel_pattern = "|".join(rel_types) if rel_types else ""
    if not rel_pattern:
        return {"nodes": [], "relationships": []}

    # 두 단계로 읽는다 — 한 문장의 경로 집계 · startNode() 를 그래프 저장소(Ontological)가 못 해 늘 실패했다
    # (2026-11-24). api/platform/graph_subgraph.py
    from api.platform.graph_subgraph import k_hop_nodes, relationships_among

    raw_nodes = k_hop_nodes(session, [node_id], rel_types, 2)
    if not raw_nodes:
        return {"nodes": [], "relationships": []}
    nodes = []
    for n in raw_nodes:
        labels = n.pop("_labels", None) or []
        nodes.append({
            "id": n.get("id"),
            "type": labels[0] if labels else None,
            "name": n.get("name") or "",
            "description": n.get("description") or "",
            "properties": n,
        })
    relationships = relationships_among(
        session, [n["id"] for n in nodes if n.get("id")], rel_types, with_properties=True)

    node_ids = [n.get("id") for n in nodes if n.get("id")]
    ctx = get_node_contexts(session, node_ids)
    for n in nodes:
        nid = n.get("id")
        if nid and nid in ctx:
            n["bcId"] = ctx[nid].get("bcId")
            n["bcName"] = ctx[nid].get("bcName")

    return {"nodes": nodes, "relationships": relationships}


