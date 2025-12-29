from __future__ import annotations

from typing import Any


class BoundedContextOps:
    # =========================================================================
    # Bounded Context Operations
    # =========================================================================

    def get_all_bounded_contexts(self) -> list[dict[str, Any]]:
        """Fetch all bounded contexts with their aggregates."""
        query = """
        MATCH (bc:BoundedContext)
        OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
        WITH bc, collect(DISTINCT agg {.id, .name}) as aggregates
        RETURN {
            id: bc.id,
            name: bc.name,
            description: bc.description,
            owner: bc.owner,
            aggregates: aggregates
        } as bounded_context
        ORDER BY bounded_context.name
        """
        with self.session() as session:
            result = session.run(query)
            return [dict(record["bounded_context"]) for record in result]

    def create_bounded_context(
        self,
        id: str,
        name: str,
        description: str | None = None,
        owner: str | None = None,
    ) -> dict[str, Any]:
        """Create a new bounded context."""
        query = """
        MERGE (bc:BoundedContext {id: $id})
        SET bc.name = $name,
            bc.description = $description,
            bc.owner = $owner
        RETURN bc {.id, .name, .description, .owner} as bounded_context
        """
        with self.session() as session:
            result = session.run(query, id=id, name=name, description=description, owner=owner)
            return dict(result.single()["bounded_context"])

    def link_user_story_to_bc(self, user_story_id: str, bc_id: str, confidence: float = 0.9) -> bool:
        """Link a user story to a bounded context via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (bc:BoundedContext {id: $bc_id})
        MERGE (us)-[r:IMPLEMENTS]->(bc)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, bc.id
        """
        with self.session() as session:
            result = session.run(query, user_story_id=user_story_id, bc_id=bc_id, confidence=confidence)
            return result.single() is not None


