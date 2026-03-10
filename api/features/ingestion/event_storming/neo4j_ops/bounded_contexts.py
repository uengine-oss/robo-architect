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
            displayName: bc.displayName,
            description: bc.description,
            owner: bc.owner,
            domainType: bc.domainType,
            userStoryIds: bc.userStoryIds,
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
        user_story_ids: list[str] | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new bounded context."""
        key = key or bc_key(name)
        display_name = display_name or name
        query = """
        MERGE (bc:BoundedContext {key: $key})
        ON CREATE SET bc.id = randomUUID(),
                      bc.createdAt = datetime()
        SET bc.name = $name,
            bc.key = $key,
            bc.displayName = $display_name,
            bc.description = $description,
            bc.owner = $owner,
            bc.domainType = $domain_type,
            bc.userStoryIds = $user_story_ids,
            bc.updatedAt = datetime()
        RETURN bc {.id, .key, .name, .displayName, .description, .owner, .domainType, .userStoryIds} as bounded_context
        """
        with self.session() as session:
            result = session.run(query, key=key, name=name, display_name=display_name, description=description, owner=owner, domain_type=domain_type, user_story_ids=user_story_ids or [])
            return dict(result.single()["bounded_context"])

    def link_user_story_to_bc(self, user_story_id: str, bc_id: str, confidence: float = 0.9) -> tuple[bool, dict[str, Any] | None]:
        """
        Link a user story to a bounded context via IMPLEMENTS relationship.
        Also updates the BC node's userStoryIds array property.
        
        Returns:
            (success: bool, diagnostic: dict | None)
            - success: True if link was created, False otherwise
            - diagnostic: If False, contains diagnostic info about why it failed
        """
        # First, create the relationship
        create_query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (bc:BoundedContext {id: $bc_id})
        MERGE (us)-[r:IMPLEMENTS]->(bc)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id as us_id, bc.id as bc_id
        """
        
        # Then, update BC's userStoryIds array
        update_query = """
        MATCH (bc:BoundedContext {id: $bc_id})<-[:IMPLEMENTS]-(linked_us:UserStory)
        WITH bc, collect(DISTINCT linked_us.id) as all_us_ids
        SET bc.userStoryIds = all_us_ids,
            bc.updatedAt = datetime()
        RETURN bc.id, all_us_ids
        """
        
        with self.session() as session:
            # Create the relationship first
            create_result = session.run(create_query, user_story_id=user_story_id, bc_id=bc_id, confidence=confidence)
            create_record = create_result.single()
            if create_record is None:
                # 진단: 왜 실패했는지 확인
                us_exists = session.run("MATCH (us:UserStory {id: $user_story_id}) RETURN us.id", user_story_id=user_story_id).single()
                bc_exists = session.run("MATCH (bc:BoundedContext {id: $bc_id}) RETURN bc.id", bc_id=bc_id).single()
                return False, {
                    "user_story_exists": us_exists is not None,
                    "bc_exists": bc_exists is not None,
                    "user_story_id": user_story_id,
                    "bc_id": bc_id,
                }
            
            # Update BC's userStoryIds array
            update_result = session.run(update_query, bc_id=bc_id)
            update_record = update_result.single()
            
            return True, None


