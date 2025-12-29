from __future__ import annotations

from typing import Any


class CommandOps:
    # =========================================================================
    # Command Operations
    # =========================================================================

    def create_command(
        self,
        id: str,
        name: str,
        aggregate_id: str,
        actor: str = "user",
        input_schema: str | None = None,
    ) -> dict[str, Any]:
        """Create a new command and link it to an aggregate."""
        query = """
        MATCH (agg:Aggregate {id: $aggregate_id})
        MERGE (cmd:Command {id: $id})
        SET cmd.name = $name,
            cmd.actor = $actor,
            cmd.inputSchema = $input_schema
        MERGE (agg)-[:HAS_COMMAND]->(cmd)
        RETURN cmd {.id, .name, .actor, .inputSchema} as command
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
                aggregate_id=aggregate_id,
                actor=actor,
                input_schema=input_schema,
            )
            return dict(result.single()["command"])

    def get_commands_by_aggregate(self, aggregate_id: str) -> list[dict[str, Any]]:
        """Fetch commands belonging to an aggregate."""
        query = """
        MATCH (agg:Aggregate {id: $aggregate_id})-[:HAS_COMMAND]->(cmd:Command)
        OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
        WITH cmd, collect(DISTINCT evt {.id, .name}) as emits
        RETURN {
            id: cmd.id,
            name: cmd.name,
            actor: cmd.actor,
            inputSchema: cmd.inputSchema,
            emits: emits
        } as command
        ORDER BY command.name
        """
        with self.session() as session:
            result = session.run(query, aggregate_id=aggregate_id)
            return [dict(record["command"]) for record in result]


