from __future__ import annotations

from typing import Any


class EventOps:
    # =========================================================================
    # Event Operations
    # =========================================================================

    def create_event(
        self,
        id: str,
        name: str,
        command_id: str,
        version: str = "1.0.0",
        schema: str | None = None,
    ) -> dict[str, Any]:
        """Create a new event and link it to a command via EMITS."""
        query = """
        MATCH (cmd:Command {id: $command_id})
        MERGE (evt:Event {id: $id})
        SET evt.name = $name,
            evt.version = $version,
            evt.schema = $schema,
            evt.isBreaking = false
        MERGE (cmd)-[:EMITS {isGuaranteed: true}]->(evt)
        RETURN evt {.id, .name, .version, .schema} as event
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
                command_id=command_id,
                version=version,
                schema=schema,
            )
            return dict(result.single()["event"])


