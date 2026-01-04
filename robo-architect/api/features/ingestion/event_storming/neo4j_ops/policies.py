from __future__ import annotations

from typing import Any


class PolicyOps:
    # =========================================================================
    # Policy Operations
    # =========================================================================

    def create_policy(
        self,
        id: str,
        name: str,
        bc_id: str,
        trigger_event_id: str,
        invoke_command_id: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a policy with TRIGGERS and INVOKES relationships."""
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})
        MATCH (evt:Event {id: $trigger_event_id})
        MATCH (cmd:Command {id: $invoke_command_id})
        MERGE (pol:Policy {id: $id})
        SET pol.name = $name,
            pol.description = $description
        MERGE (bc)-[:HAS_POLICY]->(pol)
        MERGE (evt)-[:TRIGGERS {priority: 1, isEnabled: true}]->(pol)
        MERGE (pol)-[:INVOKES {isAsync: true}]->(cmd)
        RETURN pol {.id, .name, .description} as policy
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
                bc_id=bc_id,
                trigger_event_id=trigger_event_id,
                invoke_command_id=invoke_command_id,
                description=description,
            )
            return dict(result.single()["policy"])

    def link_user_story_to_policy(
        self, user_story_id: str, policy_id: str, confidence: float = 0.9
    ) -> bool:
        """Link a user story to a policy via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (pol:Policy {id: $policy_id})
        MERGE (us)-[r:IMPLEMENTS]->(pol)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, pol.id
        """
        with self.session() as session:
            result = session.run(
                query,
                user_story_id=user_story_id,
                policy_id=policy_id,
                confidence=confidence,
            )
            return result.single() is not None


