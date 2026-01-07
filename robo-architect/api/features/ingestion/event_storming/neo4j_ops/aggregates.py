from __future__ import annotations

from typing import Any

from api.platform.keys import aggregate_key


class AggregateOps:
    # =========================================================================
    # Aggregate Operations
    # =========================================================================

    def get_aggregates_by_bc(self, bc_id: str) -> list[dict[str, Any]]:
        """Fetch aggregates belonging to a bounded context."""
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_AGGREGATE]->(agg:Aggregate)
        OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
        WITH agg, collect(DISTINCT cmd {.id, .name}) as commands
        RETURN {
            id: agg.id,
            name: agg.name,
            rootEntity: agg.rootEntity,
            invariants: agg.invariants,
            commands: commands
        } as aggregate
        ORDER BY aggregate.name
        """
        with self.session() as session:
            result = session.run(query, bc_id=bc_id)
            return [dict(record["aggregate"]) for record in result]

    def create_aggregate(
        self,
        *,
        name: str,
        bc_id: str,
        key: str | None = None,
        root_entity: str | None = None,
        invariants: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new aggregate and link it to a bounded context.

        IMPORTANT: One Aggregate belongs to exactly ONE Bounded Context.
        If an aggregate with the same key already exists and belongs to a different BC,
        this will raise an error.
        """
        with self.session() as session:
            bc_rec = session.run("MATCH (bc:BoundedContext {id: $id}) RETURN bc.key as key", id=bc_id).single()
            bc_key_value = (bc_rec or {}).get("key") or ""
            if not bc_key_value:
                raise ValueError(f"BoundedContext not found or missing key: {bc_id}")
            key = key or aggregate_key(bc_key_value, name)

            check_query = """
            OPTIONAL MATCH (existing:Aggregate {key: $key})<-[:HAS_AGGREGATE]-(otherBC:BoundedContext)
            WHERE otherBC.id <> $bc_id
            RETURN otherBC.id as existing_bc
            """
            record = session.run(check_query, key=key, bc_id=bc_id).single()
            if record and record["existing_bc"]:
                raise ValueError(
                    f"Aggregate {key} already belongs to BC {record['existing_bc']}. "
                    f"An Aggregate can only belong to ONE Bounded Context."
                )

        query = """
        MATCH (bc:BoundedContext {id: $bc_id})
        MERGE (agg:Aggregate {key: $key})
        ON CREATE SET agg.id = randomUUID(),
                      agg.createdAt = datetime()
        SET agg.key = $key,
            agg.name = $name,
            agg.rootEntity = $root_entity,
            agg.invariants = $invariants,
            agg.updatedAt = datetime()
        MERGE (bc)-[:HAS_AGGREGATE {isPrimary: false}]->(agg)
        RETURN agg {.id, .key, .name, .rootEntity, .invariants} as aggregate
        """
        with self.session() as session:
            result = session.run(
                query,
                key=key,
                name=name,
                bc_id=bc_id,
                root_entity=root_entity or name,
                invariants=invariants or [],
            )
            return dict(result.single()["aggregate"])

    def link_user_story_to_aggregate(self, user_story_id: str, aggregate_id: str, confidence: float = 0.9) -> bool:
        """Link a user story to an aggregate via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (agg:Aggregate {id: $aggregate_id})
        MERGE (us)-[r:IMPLEMENTS]->(agg)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, agg.id
        """
        with self.session() as session:
            result = session.run(query, user_story_id=user_story_id, aggregate_id=aggregate_id, confidence=confidence)
            return result.single() is not None

    def link_user_story_to_command(self, user_story_id: str, command_id: str, confidence: float = 0.9) -> bool:
        """Link a user story to a command via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (cmd:Command {id: $command_id})
        MERGE (us)-[r:IMPLEMENTS]->(cmd)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, cmd.id
        """
        with self.session() as session:
            result = session.run(query, user_story_id=user_story_id, command_id=command_id, confidence=confidence)
            return result.single() is not None

    def link_user_story_to_event(self, user_story_id: str, event_id: str, confidence: float = 0.9) -> bool:
        """Link a user story to an event via IMPLEMENTS relationship."""
        query = """
        MATCH (us:UserStory {id: $user_story_id})
        MATCH (evt:Event {id: $event_id})
        MERGE (us)-[r:IMPLEMENTS]->(evt)
        SET r.confidence = $confidence,
            r.createdAt = datetime()
        RETURN us.id, evt.id
        """
        with self.session() as session:
            result = session.run(query, user_story_id=user_story_id, event_id=event_id, confidence=confidence)
            return result.single() is not None


