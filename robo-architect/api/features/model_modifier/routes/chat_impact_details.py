from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger


router = APIRouter()


class ImpactDetailsRequest(BaseModel):
    seedIds: List[str] = Field(default_factory=list)


def _dedupe_relationships(rels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for r in rels or []:
        src = r.get("source")
        tgt = r.get("target")
        typ = r.get("type")
        if not src or not tgt or not typ:
            continue
        key = f"{src}::{typ}::{tgt}"
        if key in seen:
            continue
        seen.add(key)
        out.append({"source": src, "target": tgt, "type": typ})
    return out


def _compute_hop_distances(seed_ids: List[str], rels: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Compute minimal hop distance from any seed, treating edges as undirected for debugging.
    """
    seeds = [s for s in seed_ids if s]
    dist: Dict[str, int] = {}
    if not seeds:
        return dist

    adj: Dict[str, Set[str]] = {}
    for r in rels or []:
        a = str(r.get("source") or "")
        b = str(r.get("target") or "")
        if not a or not b:
            continue
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    q: deque[str] = deque()
    for s in seeds:
        sid = str(s)
        dist[sid] = 0
        q.append(sid)

    while q:
        cur = q.popleft()
        base = dist.get(cur, 0)
        for nxt in adj.get(cur, set()):
            if nxt in dist:
                continue
            dist[nxt] = base + 1
            q.append(nxt)

    return dist


def _get_node_contexts(session, node_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Batch resolve BC context for nodes. Mirrors patterns used by canvas graph node-context.
    """
    if not node_ids:
        return {}
    query = """
    UNWIND $node_ids as node_id
    MATCH (n {id: node_id})
    OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE|HAS_POLICY*1..2]->(n)
    OPTIONAL MATCH (bc2:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(n)
    OPTIONAL MATCH (bc3:BoundedContext)-[:HAS_AGGREGATE]->(agg2:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(n)
    OPTIONAL MATCH (bc4:BoundedContext)-[:HAS_UI]->(n)
    OPTIONAL MATCH (bc5:BoundedContext)-[:HAS_READMODEL]->(n)
    WITH n, coalesce(bc, bc2, bc3, bc4, bc5) as context
    RETURN collect({
        nodeId: n.id,
        bcId: context.id,
        bcName: context.name
    }) as results
    """
    rec = session.run(query, node_ids=node_ids).single()
    if not rec:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for row in rec.get("results") or []:
        nid = row.get("nodeId")
        if nid:
            out[str(nid)] = dict(row)
    return out


def _fetch_properties_for_parents(session, parent_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not parent_ids:
        return {}
    query = """
    UNWIND $parent_ids as pid
    MATCH (parent {id: pid})
    OPTIONAL MATCH (parent)-[:HAS_PROPERTY]->(p:Property)
    OPTIONAL MATCH (p)-[:REFERENCES]->(tgt:Property)
    WITH pid, p, collect(DISTINCT {
      id: tgt.id,
      name: tgt.name,
      type: tgt.type,
      isKey: tgt.isKey,
      parentType: tgt.parentType,
      parentId: tgt.parentId
    }) as tgtProps
    WITH pid, collect(DISTINCT {
      id: p.id,
      name: p.name,
      type: p.type,
      description: p.description,
      isKey: p.isKey,
      isForeignKey: p.isForeignKey,
      isRequired: p.isRequired,
      parentType: p.parentType,
      parentId: p.parentId,
      references: [t in tgtProps WHERE t.id IS NOT NULL]
    }) as props
    RETURN pid as parentId, [x in props WHERE x.id IS NOT NULL] as props
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in session.run(query, parent_ids=parent_ids).data() or []:
        pid = r.get("parentId")
        if pid:
            out[str(pid)] = list(r.get("props") or [])
    return out


@router.post("/impact-details")
async def impact_details(payload: ImpactDetailsRequest, request: Request) -> Dict[str, Any]:
    seed_ids = [str(s).strip() for s in (payload.seedIds or []) if str(s).strip()]
    if not seed_ids:
        raise HTTPException(status_code=400, detail="seedIds is required")

    # Align hop K with propagation max rounds, and reuse the same relationship whitelist.
    try:
        from api.features.change_management.planning_agent.impact_propagation_settings import (
            propagation_limits,
            relationship_whitelist,
        )

        limits = propagation_limits()
        k = min(int(limits.get("max_rounds") or 0), 2)
        whitelist = relationship_whitelist()
    except Exception:
        k = 0
        whitelist = []

    if k <= 0:
        # Defensive: never execute unbounded traversal if env is misconfigured.
        raise HTTPException(status_code=500, detail="Invalid hop configuration (k <= 0)")
    if not whitelist:
        raise HTTPException(status_code=500, detail="Relationship whitelist is empty")

    rel_pattern = "|".join([t for t in whitelist if t])
    if not rel_pattern:
        raise HTTPException(status_code=500, detail="Relationship whitelist is empty")

    SmartLogger.log(
        "INFO",
        "Chat impact-details requested: computing K-hop debug subgraph for selected nodes.",
        category="api.chat.impact_details.request",
        params={**http_context(request), "inputs": {"seedIds": seed_ids, "k": k, "whitelist": whitelist}},
    )

    query = f"""
    MATCH (s)
    WHERE s.id IN $seed_ids
    WITH collect(DISTINCT s) as seeds
    UNWIND seeds as seed
    OPTIONAL MATCH p=(seed)-[r:{rel_pattern}*1..{k}]-(n)
    WITH seeds, collect(p) as ps
    WITH seeds,
         CASE
            WHEN size(ps) = 0 THEN seeds
            ELSE reduce(allNodes = [], p in ps | allNodes + nodes(p)) + seeds
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
        attachedToId: n.attachedToId,
        attachedToType: n.attachedToType,
        attachedToName: n.attachedToName,
        parentType: n.parentType,
        parentId: n.parentId,
        isKey: n.isKey,
        isForeignKey: n.isForeignKey,
        isRequired: n.isRequired
      }}] as nodes,
      [r in rels | {{
        source: startNode(r).id,
        target: endNode(r).id,
        type: type(r)
      }}] as relationships
    """

    with get_session() as session:
        rec = session.run(query, seed_ids=seed_ids).single()
        if not rec:
            # Should not happen unless Neo4j is empty or query failed.
            raise HTTPException(status_code=404, detail="No subgraph found for seedIds")

        nodes = list(rec.get("nodes") or [])
        rels = _dedupe_relationships(list(rec.get("relationships") or []))

        # Attach BC context (best-effort)
        node_ids = [str(n.get("id")) for n in nodes if n.get("id")]
        ctx = _get_node_contexts(session, node_ids)
        for n in nodes:
            nid = n.get("id")
            if nid and str(nid) in ctx:
                n["bcId"] = ctx[str(nid)].get("bcId")
                n["bcName"] = ctx[str(nid)].get("bcName")

        hop_distance_by_id = _compute_hop_distances(seed_ids, rels)
        for n in nodes:
            nid = str(n.get("id") or "")
            if nid and nid in hop_distance_by_id:
                n["hop"] = hop_distance_by_id[nid]

        # Properties by parent id (for parent nodes that can embed properties)
        parent_types = {"Aggregate", "Command", "Event", "ReadModel", "UI"}
        parent_ids = [str(n.get("id")) for n in nodes if n.get("id") and (n.get("type") in parent_types)]
        properties_by_parent_id = _fetch_properties_for_parents(session, parent_ids)

        # Property nodes (if present in hopGraph)
        property_nodes: List[Dict[str, Any]] = []
        for n in nodes:
            if n.get("type") != "Property":
                continue
            property_nodes.append(
                {
                    "id": n.get("id"),
                    "name": n.get("name"),
                    "description": n.get("description"),
                    "type": n.get("type"),
                    "parentType": n.get("parentType"),
                    "parentId": n.get("parentId"),
                    "isKey": n.get("isKey"),
                    "isForeignKey": n.get("isForeignKey"),
                    "isRequired": n.get("isRequired"),
                    "bcId": n.get("bcId"),
                    "bcName": n.get("bcName"),
                    "hop": n.get("hop"),
                }
            )

        SmartLogger.log(
            "INFO",
            "Chat impact-details computed.",
            category="api.chat.impact_details.done",
            params={
                **http_context(request),
                "seedCount": len(seed_ids),
                "nodeCount": len(nodes),
                "relCount": len(rels),
                "k": k,
            },
        )

        return {
            "k": k,
            "whitelist": whitelist,
            "hopGraph": {"nodes": nodes, "relationships": rels},
            "hopDistanceById": hop_distance_by_id,
            "propertiesByParentId": properties_by_parent_id,
            "propertyNodes": property_nodes,
        }


