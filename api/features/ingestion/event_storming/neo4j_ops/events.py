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
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new event and link it to a command via EMITS."""
        display_name = display_name or name
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
                evt.displayName = $display_name,
                evt.version = $version,
                evt.schema = $schema,
                evt.payload = $payload,
                evt.isBreaking = false,
                evt.updatedAt = datetime()
            MERGE (cmd)-[:EMITS {isGuaranteed: true}]->(evt)
            RETURN evt {.id, .key, .name, .displayName, .version, .schema, .payload} as event
            """
            result = session.run(
                query,
                key=key,
                name=name,
                display_name=display_name,
                command_id=command_id,
                version=version,
                schema=schema,
                payload=payload,
            )
            return dict(result.single()["event"])

    def link_command_to_event_by_name(self, *, command_id: str, event_name: str) -> bool:
        """Link an existing Event (matched by name or displayName) to a Command via EMITS."""
        name = (event_name or "").strip()
        if not name or not command_id:
            return False
        with self.session() as session:
            # 1차: name 정확 일치, 2차: displayName 일치, 3차: 대소문자 무시
            result = session.run(
                """
                MATCH (cmd:Command {id: $command_id})
                OPTIONAL MATCH (evt1:Event {name: $event_name})
                OPTIONAL MATCH (evt2:Event {displayName: $event_name})
                OPTIONAL MATCH (evt3:Event) WHERE toLower(evt3.name) = toLower($event_name)
                   OR toLower(evt3.displayName) = toLower($event_name)
                WITH cmd, coalesce(evt1, evt2, evt3) AS evt
                WHERE evt IS NOT NULL
                MERGE (cmd)-[r:EMITS]->(evt)
                ON CREATE SET r.isGuaranteed = true
                SET r.isGuaranteed = coalesce(r.isGuaranteed, true)
                RETURN evt.id AS id
                LIMIT 1
                """,
                command_id=command_id,
                event_name=name,
            )
            rec = result.single()
            return bool(rec and rec.get("id"))

    def get_events_emitted_by_command(self, command_id: str) -> list[dict[str, Any]]:
        """Return Event nodes linked from Command via EMITS (for workflow context)."""
        if not command_id:
            return []
        with self.session() as session:
            result = session.run(
                """
                MATCH (cmd:Command {id: $cmd_id})-[:EMITS]->(evt:Event)
                RETURN evt {
                    .id, .name, .displayName, .version, .schema, .payload, .description, .sequence
                } AS event
                ORDER BY evt.name
                """,
                cmd_id=command_id,
            )
            return [dict(record["event"]) for record in result]


