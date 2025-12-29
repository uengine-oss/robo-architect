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

    query = f"""
    MATCH (center {{id: $node_id}})
    OPTIONAL MATCH p=(center)-[r:{rel_pattern}*1..2]-(n)
    WITH center, [p in collect(p) WHERE p IS NOT NULL] as ps
    WITH center,
         CASE
            WHEN size(ps) = 0 THEN [center]
            ELSE reduce(allNodes = [], p in ps | allNodes + nodes(p))
         END as node_list,
         CASE
            WHEN size(ps) = 0 THEN []
            ELSE reduce(allRels = [], p in ps | allRels + relationships(p))
         END as rel_list

    UNWIND node_list as nd
    WITH collect(DISTINCT nd) as nodes, rel_list

    UNWIND (CASE WHEN size(rel_list) = 0 THEN [null] ELSE rel_list END) as rl
    WITH nodes, collect(DISTINCT rl) as rels
    WITH nodes, [r IN rels WHERE r IS NOT NULL] as rels

    RETURN
      [n in nodes | {{
        id: n.id,
        type: labels(n)[0],
        name: coalesce(n.name, ''),
        description: coalesce(n.description, ''),
        properties: properties(n)
      }}] as nodes,
      [r in rels | {{
        source: startNode(r).id,
        target: endNode(r).id,
        type: type(r),
        properties: properties(r)
      }}] as relationships
    """

    record = session.run(query, node_id=node_id).single()
    if not record:
        return {"nodes": [], "relationships": []}
    nodes = record["nodes"] or []
    relationships = record["relationships"] or []

    node_ids = [n.get("id") for n in nodes if n.get("id")]
    ctx = get_node_contexts(session, node_ids)
    for n in nodes:
        nid = n.get("id")
        if nid and nid in ctx:
            n["bcId"] = ctx[nid].get("bcId")
            n["bcName"] = ctx[nid].get("bcName")

    return {"nodes": nodes, "relationships": relationships}


