from __future__ import annotations

from typing import Any

from api.platform.keys import bc_key


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
            domainType: bc.domainType,
            aggregates: aggregates
        } as bounded_context
        ORDER BY bounded_context.name
        """
        with self.session() as session:
            result = session.run(query)
            return [dict(record["bounded_context"]) for record in result]

    def create_bounded_context(
        self,
        *,
        name: str,
        key: str | None = None,
        description: str | None = None,
        owner: str | None = None,
        domain_type: str | None = None,
    ) -> dict[str, Any]:
        """Create a new bounded context."""
        key = key or bc_key(name)
        query = """
        MERGE (bc:BoundedContext {key: $key})
        ON CREATE SET bc.id = randomUUID(),
                      bc.createdAt = datetime()
        SET bc.name = $name,
            bc.key = $key,
            bc.description = $description,
            bc.owner = $owner,
            bc.domainType = $domain_type,
            bc.updatedAt = datetime()
        RETURN bc {.id, .key, .name, .description, .owner, .domainType} as bounded_context
        """
        with self.session() as session:
            result = session.run(query, key=key, name=name, description=description, owner=owner, domain_type=domain_type)
            return dict(result.single()["bounded_context"])

    def link_user_story_to_bc(self, user_story_id: str, bc_id: str, confidence: float = 0.9) -> tuple[bool, dict[str, Any] | None]:
        """
        Link a user story to a bounded context via IMPLEMENTS relationship.
        
        Returns:
            (success: bool, diagnostic: dict | None)
            - success: True if link was created, False otherwise
            - diagnostic: If False, contains diagnostic info about why it failed
        """
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
            record = result.single()
            if record is None:
                # 진단: 왜 실패했는지 확인
                us_exists = session.run("MATCH (us:UserStory {id: $user_story_id}) RETURN us.id", user_story_id=user_story_id).single()
                bc_exists = session.run("MATCH (bc:BoundedContext {id: $bc_id}) RETURN bc.id", bc_id=bc_id).single()
                return False, {
                    "user_story_exists": us_exists is not None,
                    "bc_exists": bc_exists is not None,
                    "user_story_id": user_story_id,
                    "bc_id": bc_id,
                }
            return True, None


