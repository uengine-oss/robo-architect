from __future__ import annotations

from typing import Any

from api.platform.keys import event_key

from ._bulk_helper import (
    BulkResult,
    bulk_flush,
    chunked,
    emit_flush_log,
    reorder_to_input,
    run_chunk,
    validate_required,
    with_retry,
)


_EVENT_BULK_CYPHER = """
UNWIND $rows AS r
MATCH (cmd:Command {id: r.command_id})
MERGE (evt:Event {key: r.key})
  ON CREATE SET evt.id = randomUUID(),
                evt.createdAt = datetime()
SET evt.key = r.key,
    evt.name = r.name,
    evt.displayName = r.display_name,
    evt.version = r.version,
    evt.schema = r.schema,
    evt.payload = r.payload,
    evt.description = r.description,
    evt.isBreaking = false,
    evt.updatedAt = datetime()
MERGE (cmd)-[:EMITS {isGuaranteed: true}]->(evt)
RETURN evt {.id, .key, .name, .displayName, .version, .schema, .payload, .description} AS result
"""


_EMITS_BULK_CYPHER = """
UNWIND $rows AS r
MATCH (cmd:Command {id: r.cmd_id})
MATCH (evt:Event {id: r.evt_id})
MERGE (cmd)-[em:EMITS]->(evt)
  ON CREATE SET em.isGuaranteed = coalesce(r.is_guaranteed, true)
SET em.isGuaranteed = coalesce(em.isGuaranteed, coalesce(r.is_guaranteed, true))
RETURN {cmd_id: cmd.id, evt_id: evt.id} AS result
"""


_EVENT_SEQ_BULK_CYPHER = """
UNWIND $rows AS r
MATCH (evt:Event {id: r.evt_id})
SET evt.sequence = r.sequence,
    evt.updatedAt = datetime()
RETURN {evt_id: evt.id, sequence: evt.sequence} AS result
"""


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

    def bulk_create_events(
        self,
        rows: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> list[BulkResult]:
        """Persist events in batch — schema-equivalent to `create_event`.

        Required input fields per row: `name`, `command_id`. Optional:
        `key` (auto-derived from command's key + name + version when absent),
        `version` (default `"1.0.0"`), `display_name` (default `name`),
        `schema`, `payload`, `description`.

        Two passes inside this single helper call:
          1. Look up `cmd.key` for every distinct `command_id` (one MATCH).
          2. UNWIND the rows (with derived `key`s) into the MERGE template.
        """
        if not rows:
            return []

        # Step 1 — identify the rows that look complete enough to consider for
        # key-derivation (same baseline as the per-row helper).
        valid, errors = validate_required(rows, ["name", "command_id"])

        # Step 2 — fetch cmd.key for every distinct command_id present in valid.
        cmd_ids = sorted({r["command_id"] for r in valid})
        cmd_key_map: dict[str, str] = {}
        if cmd_ids:
            with self.session() as session:
                cur = session.run(
                    "MATCH (cmd:Command) WHERE cmd.id IN $ids RETURN cmd.id AS id, cmd.key AS key",
                    ids=cmd_ids,
                )
                for rec in cur:
                    if rec and rec.get("id") and rec.get("key"):
                        cmd_key_map[rec["id"]] = rec["key"]

        # Step 3 — derive each row's key (or reject if command not found).
        prepared: list[dict[str, Any]] = []
        cmd_missing_errors: list[BulkResult] = []
        for r in valid:
            cmd_key = cmd_key_map.get(r["command_id"])
            if not cmd_key:
                cmd_missing_errors.append(
                    {
                        "ok": False,
                        "error": f"command not found: {r['command_id']}",
                        "error_field": "command_id",
                        "id": r.get("id"),
                    }
                )
                continue
            version = r.get("version") or "1.0.0"
            key = r.get("key") or event_key(cmd_key, r["name"], version)
            display_name = r.get("display_name") or r["name"]
            prepared.append(
                {
                    "key": key,
                    "name": r["name"],
                    "command_id": r["command_id"],
                    "display_name": display_name,
                    "version": version,
                    "schema": r.get("schema"),
                    "payload": r.get("payload"),
                    "description": r.get("description"),
                }
            )

        # Step 4 — flush prepared rows through the shared orchestrator.
        # We bypass `bulk_flush`'s built-in validate/dedupe (already done) and
        # call run_chunk directly so we can correctly reassemble three error
        # sources (validation, command-missing, chunk-failure).
        from time import perf_counter

        started = perf_counter()
        success: list[BulkResult] = []
        chunk_count = 0
        for chunk in chunked(prepared):
            chunk_count += 1
            try:
                with self.session() as session:
                    rs = with_retry(
                        lambda s=session, c=chunk: run_chunk(
                            s, _EVENT_BULK_CYPHER, c, return_field="result"
                        )
                    )
                for r in rs:
                    success.append({"ok": True, **r} if r else {"ok": False, "error": "no result row"})
            except Exception as exc:  # noqa: BLE001
                for _ in chunk:
                    success.append({"ok": False, "error": str(exc)})

        # Step 5 — reassemble: prepared-order successes + cmd-missing errors +
        # validate_required errors → original input order.
        all_errors = list(cmd_missing_errors) + list(errors)
        out = reorder_to_input(rows, success, all_errors)
        duration_ms = (perf_counter() - started) * 1000.0
        emit_flush_log(
            "event",
            count=len(rows),
            duration_ms=duration_ms,
            chunks=chunk_count,
            errors=sum(1 for r in out if not r.get("ok")),
            session_id=session_id,
            phase=phase,
        )
        return out

    def bulk_link_emits(
        self,
        rows: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> list[BulkResult]:
        """Batch-create `(:Command)-[:EMITS]->(:Event)` rels.

        Required input fields per row: `cmd_id`, `evt_id`. Optional:
        `is_guaranteed` (default `True`).
        """
        if not rows:
            return []
        return bulk_flush(
            self.session,
            entity="emits_link",
            rows=rows,
            cypher=_EMITS_BULK_CYPHER,
            return_field="result",
            required_fields=["cmd_id", "evt_id"],
            dedupe_key=None,
            session_id=session_id,
            phase=phase,
        )

    def bulk_set_event_sequence(
        self,
        rows: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> list[BulkResult]:
        """Batch-set `Event.sequence` from user-story flow analysis.

        Required input fields: `evt_id`, `sequence`.
        """
        if not rows:
            return []
        return bulk_flush(
            self.session,
            entity="event_sequence",
            rows=rows,
            cypher=_EVENT_SEQ_BULK_CYPHER,
            return_field="result",
            required_fields=["evt_id", "sequence"],
            dedupe_key=None,
            session_id=session_id,
            phase=phase,
        )

    def get_events_emitted_by_command(self, command_id: str) -> list[dict[str, Any]]:
        """Return Event nodes linked from Command via EMITS (for workflow context)."""
        if not command_id:
            return []
        with self.session() as session:
            result = session.run(
                """
                MATCH (cmd:Command {id: $cmd_id})-[:EMITS]->(evt:Event)
                RETURN evt {
                    .id, .key, .name, .displayName, .version, .schema, .payload, .description, .sequence
                } AS event
                ORDER BY evt.name
                """,
                cmd_id=command_id,
            )
            return [dict(record["event"]) for record in result]


