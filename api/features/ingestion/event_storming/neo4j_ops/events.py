from __future__ import annotations

from typing import Any

from api.platform.keys import event_key


class EventOps:
    # =========================================================================
    # Event Operations
    # =========================================================================

    def create_event(
        self,
        *,
        name: str,
        command_id: str,
        key: str | None = None,
        version: str = "1.0.0",
        schema: str | None = None,
        payload: str | None = None,
    ) -> dict[str, Any]:
        """Create a new event and link it to a command via EMITS."""
        with self.session() as session:
            cmd_rec = session.run("MATCH (cmd:Command {id: $id}) RETURN cmd.key as key", id=command_id).single()
            cmd_key_value = (cmd_rec or {}).get("key") or ""
            if not cmd_key_value:
                raise ValueError(f"Command not found or missing key: {command_id}")
            key = key or event_key(cmd_key_value, name, version)

            query = """
            MATCH (cmd:Command {id: $command_id})
            MERGE (evt:Event {key: $key})
            ON CREATE SET evt.id = randomUUID(),
                          evt.createdAt = datetime()
            SET evt.key = $key,
                evt.name = $name,
                evt.version = $version,
                evt.schema = $schema,
                evt.payload = $payload,
                evt.isBreaking = false,
                evt.updatedAt = datetime()
            MERGE (cmd)-[:EMITS {isGuaranteed: true}]->(evt)
            RETURN evt {.id, .key, .name, .version, .schema, .payload} as event
            """
            result = session.run(
                query,
                key=key,
                name=name,
                command_id=command_id,
                version=version,
                schema=schema,
                payload=payload,
            )
            return dict(result.single()["event"])


