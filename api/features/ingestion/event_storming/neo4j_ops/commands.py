from __future__ import annotations

from typing import Any

from api.platform.keys import command_key


class CommandOps:
    # =========================================================================
    # Command Operations
    # =========================================================================

    def create_command(
        self,
        *,
        name: str,
        aggregate_id: str,
        key: str | None = None,
        actor: str = "user",
        category: str | None = None,
        input_schema: str | None = None,
        display_name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a new command and link it to an aggregate."""
        display_name = display_name or name
        with self.session() as session:
            agg_rec = session.run("MATCH (agg:Aggregate {id: $id}) RETURN agg.key as key", id=aggregate_id).single()
            agg_key_value = (agg_rec or {}).get("key") or ""
            if not agg_key_value:
                raise ValueError(f"Aggregate not found or missing key: {aggregate_id}")
            key = key or command_key(agg_key_value, name)

            query = """
            MATCH (agg:Aggregate {id: $aggregate_id})
            MERGE (cmd:Command {key: $key})
            ON CREATE SET cmd.id = randomUUID(),
                          cmd.createdAt = datetime()
            SET cmd.key = $key,
                cmd.name = $name,
                cmd.displayName = $display_name,
                cmd.actor = $actor,
                cmd.category = $category,
                cmd.inputSchema = $input_schema,
                cmd.description = $description,
                cmd.updatedAt = datetime()
            MERGE (agg)-[:HAS_COMMAND]->(cmd)
            RETURN cmd {.id, .key, .name, .displayName, .actor, .category, .inputSchema, .description} as command
            """
            result = session.run(
                query,
                key=key,
                name=name,
                display_name=display_name,
                aggregate_id=aggregate_id,
                actor=actor,
                category=category,
                input_schema=input_schema,
                description=description,
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
            displayName: cmd.displayName,
            actor: cmd.actor,
            category: cmd.category,
            inputSchema: cmd.inputSchema,
            description: cmd.description,
            emits: emits
        } as command
        ORDER BY command.name
        """
        with self.session() as session:
            result = session.run(query, aggregate_id=aggregate_id)
            return [dict(record["command"]) for record in result]


