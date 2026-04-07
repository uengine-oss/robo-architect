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
        description: str | None = None,
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
                evt.description = $description,
                evt.isBreaking = false,
                evt.updatedAt = datetime()
            MERGE (cmd)-[:EMITS {isGuaranteed: true}]->(evt)
            RETURN evt {.id, .key, .name, .displayName, .version, .schema, .payload, .description} as event
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
                description=description,
            )
            return dict(result.single()["event"])

    def link_command_to_event_by_name(
        self, *, command_id: str, event_name: str,
    ) -> bool:
        """Link an existing Event (matched by name or displayName) to a Command via EMITS.

        Cross-BC EMITS are **warned** but still created — the diagnostic log
        helps identify cases that should use Policy instead.
        """
        from api.platform.observability.smart_logger import SmartLogger

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

                // Resolve BC ownership for both sides
                OPTIONAL MATCH (cmd_bc:BoundedContext)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(cmd)
                OPTIONAL MATCH (evt_bc:BoundedContext)-[:HAS_EVENT]->(evt)

                RETURN evt.id AS id, evt.name AS evt_name,
                       cmd_bc.id AS cmd_bc_id, cmd_bc.name AS cmd_bc_name,
                       evt_bc.id AS evt_bc_id, evt_bc.name AS evt_bc_name
                LIMIT 1
                """,
                command_id=command_id,
                event_name=name,
            )
            rec = result.single()
            if not rec or not rec.get("id"):
                return False

            # ── Cross-BC EMITS warning (warn-only, not blocking) ─────
            cmd_bc_id = rec.get("cmd_bc_id")
            evt_bc_id = rec.get("evt_bc_id")
            if cmd_bc_id and evt_bc_id and cmd_bc_id != evt_bc_id:
                SmartLogger.log(
                    "WARN",
                    f"Cross-BC EMITS detected: Command(bc={rec.get('cmd_bc_name')}) "
                    f"→ Event '{rec.get('evt_name')}'(bc={rec.get('evt_bc_name')}). "
                    f"Consider using a Policy for cross-BC causality.",
                    category="ingestion.neo4j.emits.cross_bc_warning",
                    params={
                        "command_id": command_id,
                        "event_name": name,
                        "cmd_bc": rec.get("cmd_bc_name"),
                        "evt_bc": rec.get("evt_bc_name"),
                    },
                )

            # Create the link (same-BC or cross-BC)
            evt_id = rec["id"]
            session.run(
                """
                MATCH (cmd:Command {id: $command_id}), (evt:Event {id: $evt_id})
                MERGE (cmd)-[r:EMITS]->(evt)
                ON CREATE SET r.isGuaranteed = true
                SET r.isGuaranteed = coalesce(r.isGuaranteed, true)
                """,
                command_id=command_id,
                evt_id=evt_id,
            )
            return True

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


