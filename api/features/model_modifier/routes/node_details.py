from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from api.platform.neo4j import get_session

router = APIRouter()


@router.get("/node/{node_id}")
async def get_node_details(node_id: str) -> Dict[str, Any]:
    query = """
    MATCH (n {id: $node_id})

    // Find parent BC
    OPTIONAL MATCH (bc1:BoundedContext)-[:HAS_AGGREGATE]->(n)
    OPTIONAL MATCH (bc2:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(n)
    OPTIONAL MATCH (bc3:BoundedContext)-[:HAS_AGGREGATE]->(agg2:Aggregate)-[:HAS_COMMAND]->(cmd:Command)-[:EMITS]->(n)
    OPTIONAL MATCH (bc4:BoundedContext)-[:HAS_POLICY]->(n)
    OPTIONAL MATCH (bc5:BoundedContext)-[:HAS_UI]->(n)
    OPTIONAL MATCH (bc6:BoundedContext)-[:HAS_READMODEL]->(n)

    WITH n, coalesce(bc1, bc2, bc3, bc4, bc5, bc6) as bc

    OPTIONAL MATCH (n)-[r]-(related)

    RETURN n {.*, labels: labels(n)} as node,
           bc {.id, .name, .description} as boundedContext,
           collect({
               id: related.id,
               name: related.name,
               type: labels(related)[0],
               relationship: type(r),
               direction: CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END
           }) as relationships
    """

    with get_session() as session:
        result = session.run(query, node_id=node_id)
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

        node = dict(record["node"])
        relationships = [r for r in record["relationships"] if r.get("id")]
        bc = dict(record["boundedContext"]) if record["boundedContext"] else None

        if bc:
            node["bcId"] = bc["id"]
            node["bcName"] = bc["name"]

        return {"node": node, "boundedContext": bc, "relationships": relationships}


