from __future__ import annotations

from typing import Any

from api.platform.keys import policy_key


class PolicyOps:
    # =========================================================================
    # Policy Operations
    # =========================================================================

    def create_policy(
        self,
        *,
        name: str,
        bc_id: str,
        trigger_event_id: str,
        invoke_command_id: str,
        key: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a policy with TRIGGERS and INVOKES relationships."""
        with self.session() as session:
            bc_rec = session.run("MATCH (bc:BoundedContext {id: $id}) RETURN bc.key as key", id=bc_id).single()
            bc_key_value = (bc_rec or {}).get("key") or ""
            if not bc_key_value:
                raise ValueError(f"BoundedContext not found or missing key: {bc_id}")
            key = key or policy_key(bc_key_value, name)

            query = """
            MATCH (bc:BoundedContext {id: $bc_id})
            MATCH (evt:Event {id: $trigger_event_id})
            MATCH (cmd:Command {id: $invoke_command_id})
            MERGE (pol:Policy {key: $key})
            ON CREATE SET pol.id = randomUUID(),
                          pol.createdAt = datetime()
            SET pol.key = $key,
                pol.name = $name,
                pol.description = $description,
                pol.updatedAt = datetime()
            MERGE (bc)-[:HAS_POLICY]->(pol)
            MERGE (evt)-[:TRIGGERS {priority: 1, isEnabled: true}]->(pol)
            MERGE (pol)-[:INVOKES {isAsync: true}]->(cmd)
            RETURN pol {.id, .key, .name, .description} as policy
            """
            result = session.run(
                query,
                key=key,
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


