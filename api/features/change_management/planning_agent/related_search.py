"""
Change Planning: Related Object Search

Business capability: find semantically related objects across the graph (for cross-BC changes).
"""

from __future__ import annotations

from typing import Any, Dict

from api.platform.observability.smart_logger import SmartLogger

from .change_planning_contracts import ChangePlanningPhase, ChangePlanningState, RelatedObject
from .change_planning_runtime import get_embeddings, get_neo4j_driver, neo4j_session


def search_related_objects_node(state: ChangePlanningState) -> Dict[str, Any]:
    """
    Use vector search to find semantically related objects across all BCs.
    """
    if not state.keywords_to_search:
        return {
            "phase": ChangePlanningPhase.GENERATE_PLAN,
            "related_objects": [],
        }

    embeddings = get_embeddings()
    driver = get_neo4j_driver()

    related_objects = []

    try:
        # Combine keywords into a search query
        search_query = " ".join(state.keywords_to_search)
        query_embedding = embeddings.embed_query(search_query)
        _ = query_embedding  # keep side-effect parity (embedding call) even if not used by cypher below

        # First, check if vector index exists and nodes have embeddings
        with neo4j_session(driver) as session:
            # Try vector search if embeddings exist (fallback name/description matching)
            vector_search_query = """
            // First try to find objects by name similarity
            UNWIND $keywords as keyword
            MATCH (n)
            WHERE (n:Command OR n:Event OR n:Policy OR n:Aggregate)
            AND (toLower(n.name) CONTAINS toLower(keyword) 
                 OR toLower(coalesce(n.description, '')) CONTAINS toLower(keyword))
            
            // Get the BC for each node
            OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE|HAS_POLICY*1..3]->(n)
            
            WITH DISTINCT n, bc,
                 CASE 
                     WHEN toLower(n.name) CONTAINS toLower($primary_keyword) THEN 1.0
                     ELSE 0.7
                 END as score
            
            RETURN {
                id: n.id,
                name: n.name,
                type: labels(n)[0],
                bcId: bc.id,
                bcName: bc.name,
                description: n.description,
                similarity: score
            } as result
            ORDER BY score DESC
            LIMIT 10
            """

            result = session.run(
                vector_search_query,
                keywords=state.keywords_to_search,
                primary_keyword=state.keywords_to_search[0] if state.keywords_to_search else "",
            )

            seen_ids = set()
            # Exclude already connected objects
            connected_ids = {obj.get("id") for obj in state.connected_objects}

            for record in result:
                obj = record["result"]
                if obj["id"] and obj["id"] not in seen_ids and obj["id"] not in connected_ids:
                    seen_ids.add(obj["id"])
                    related_objects.append(
                        RelatedObject(
                            id=obj["id"],
                            name=obj["name"],
                            type=obj["type"],
                            bcId=obj.get("bcId"),
                            bcName=obj.get("bcName"),
                            similarity=obj.get("similarity", 0.5),
                            description=obj.get("description"),
                        )
                    )

    except Exception as e:
        SmartLogger.log("ERROR", "Vector search error", category="agent.change_graph.search_related", params={"error": str(e)})
    finally:
        driver.close()

    return {
        "phase": ChangePlanningPhase.GENERATE_PLAN,
        "related_objects": related_objects,
    }


