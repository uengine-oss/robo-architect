from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from api.platform.neo4j import get_session

router = APIRouter()


@router.get("/node/{node_id}")
async def get_node_details(node_id: str) -> Dict[str, Any]:
    # 1단계: 노드 기본 정보
    node_query = """
    MATCH (n {id: $node_id})
    RETURN n {.*, labels: labels(n)} as node
    """

    # 2단계: 부모 BC (별도 쿼리로 조합 폭발 방지)
    bc_query = """
    MATCH (n {id: $node_id})
    OPTIONAL MATCH (bc:BoundedContext)
    WHERE (bc)-[:HAS_AGGREGATE]->(n)
       OR (bc)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(n)
       OR (bc)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(:Command)-[:EMITS]->(n)
       OR (bc)-[:HAS_POLICY]->(n)
       OR (bc)-[:HAS_UI]->(n)
       OR (bc)-[:HAS_READMODEL]->(n)
       OR (bc)-[:HAS_EVENT]->(n)
    RETURN bc {.id, .name, .description} as boundedContext
    LIMIT 1
    """

    # 3단계: 관계 정보 — 방향마다 따로 묻는다.
    # 전에는 `CASE WHEN startNode(r) = n` 으로 한 번에 가렸는데, 그래프 저장소(Ontological)에
    # startNode() 가 없어 이 API 가 늘 500 이었다(2026-11-24 확인). 방향을 패턴으로 적으면
    # Neo4j · Ontological · AGE 어디서나 같은 답이다.
    rel_queries = (
        ("outgoing", """
    MATCH (n {id: $node_id})-[r]->(related)
    RETURN DISTINCT related.id as id, related.name as name,
           labels(related)[0] as type, type(r) as relationship
    """),
        ("incoming", """
    MATCH (n {id: $node_id})<-[r]-(related)
    RETURN DISTINCT related.id as id, related.name as name,
           labels(related)[0] as type, type(r) as relationship
    """),
    )

    with get_session() as session:
        # 노드
        record = session.run(node_query, node_id=node_id).single()
        if not record:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
        node = dict(record["node"])

        # BC
        bc_record = session.run(bc_query, node_id=node_id).single()
        bc = dict(bc_record["boundedContext"]) if bc_record and bc_record["boundedContext"] else None
        if bc:
            node["bcId"] = bc["id"]
            node["bcName"] = bc["name"]

        # 관계
        relationships = [
            {**dict(r), "direction": direction}
            for direction, q in rel_queries
            for r in session.run(q, node_id=node_id)
            if r.get("id")
        ]

        return {"node": node, "boundedContext": bc, "relationships": relationships}


