from __future__ import annotations

from typing import Any

from api.platform.keys import command_key

from ._bulk_helper import (
    BulkResult,
    chunked,
    emit_flush_log,
    reorder_to_input,
    run_chunk,
    validate_required,
    with_retry,
)


_COMMAND_NODE_BULK_CYPHER = """
UNWIND $rows AS r
MATCH (agg:Aggregate {id: r.aggregate_id})
MERGE (cmd:Command {key: r.key})
  ON CREATE SET cmd.id = randomUUID(),
                cmd.createdAt = datetime()
SET cmd.key = r.key,
    cmd.name = r.name,
    cmd.displayName = r.display_name,
    cmd.actor = r.actor,
    cmd.category = r.category,
    cmd.inputSchema = r.input_schema,
    cmd.description = r.description,
    cmd.updatedAt = datetime()
MERGE (agg)-[:HAS_COMMAND]->(cmd)
RETURN cmd {.id, .key, .name, .displayName, .actor, .category, .inputSchema, .description} AS result
"""


_COMMAND_USER_STORY_LINK_CYPHER = """
UNWIND $rows AS r
MATCH (us:UserStory {id: r.user_story_id})
MATCH (cmd:Command {id: r.command_id})
MERGE (us)-[rel:IMPLEMENTS]->(cmd)
  ON CREATE SET rel.confidence = coalesce(r.confidence, 0.9),
                rel.createdAt = datetime()
SET rel.confidence = coalesce(r.confidence, rel.confidence, 0.9)
RETURN {us_id: us.id, cmd_id: cmd.id} AS result
"""


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

    def bulk_create_commands(
        self,
        rows: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> list[BulkResult]:
        """Persist commands in batch — schema-equivalent to `create_command`.

        Required: `name`, `aggregate_id`. Optional: `key` (auto-derived from
        aggregate's key + name when absent), `actor` (default `"user"`),
        `category`, `input_schema`, `display_name`, `description`,
        `user_story_ids` (list of strings — IMPLEMENTS rels created in a
        second pass within this same call).

        Two passes:
          1. Look up `agg.key` for every distinct `aggregate_id`.
          2. UNWIND nodes + HAS_COMMAND rels.
          3. Optionally UNWIND user-story IMPLEMENTS rels for rows that
             carry a non-empty `user_story_ids` list.
        """
        if not rows:
            return []

        from time import perf_counter

        started = perf_counter()
        valid, errors = validate_required(rows, ["name", "aggregate_id"])

        # Step 1 — fetch agg.key for every distinct aggregate_id.
        agg_ids = sorted({r["aggregate_id"] for r in valid})
        agg_key_map: dict[str, str] = {}
        if agg_ids:
            with self.session() as session:
                cur = session.run(
                    "MATCH (agg:Aggregate) WHERE agg.id IN $ids RETURN agg.id AS id, agg.key AS key",
                    ids=agg_ids,
                )
                for rec in cur:
                    if rec and rec.get("id") and rec.get("key"):
                        agg_key_map[rec["id"]] = rec["key"]

        # Step 2 — derive each row's key (or reject if aggregate not found).
        prepared: list[dict[str, Any]] = []
        agg_missing_errors: list[BulkResult] = []
        for r in valid:
            agg_key_value = agg_key_map.get(r["aggregate_id"])
            if not agg_key_value:
                agg_missing_errors.append(
                    {
                        "ok": False,
                        "error": f"aggregate not found: {r['aggregate_id']}",
                        "error_field": "aggregate_id",
                        "id": r.get("id"),
                    }
                )
                continue
            key = r.get("key") or command_key(agg_key_value, r["name"])
            display_name = r.get("display_name") or r["name"]
            prepared.append(
                {
                    "key": key,
                    "name": r["name"],
                    "aggregate_id": r["aggregate_id"],
                    "display_name": display_name,
                    "actor": r.get("actor") or "user",
                    "category": r.get("category"),
                    "input_schema": r.get("input_schema"),
                    "description": r.get("description"),
                    "_user_story_ids": r.get("user_story_ids") or [],
                }
            )

        # Step 3 — UNWIND nodes + HAS_COMMAND.
        success: list[BulkResult] = []
        chunk_count = 0
        node_chunk_payloads = [
            {k: v for k, v in row.items() if not k.startswith("_")} for row in prepared
        ]
        cmd_id_by_index: dict[int, str | None] = {}
        cur_idx = 0
        for chunk in chunked(node_chunk_payloads):
            chunk_count += 1
            try:
                with self.session() as session:
                    rs = with_retry(
                        lambda s=session, c=chunk: run_chunk(
                            s, _COMMAND_NODE_BULK_CYPHER, c, return_field="result"
                        )
                    )
                for r in rs:
                    cmd_id_by_index[cur_idx] = r.get("id") if r else None
                    success.append({"ok": True, **r} if r else {"ok": False, "error": "no result row"})
                    cur_idx += 1
            except Exception as exc:  # noqa: BLE001
                for _ in chunk:
                    cmd_id_by_index[cur_idx] = None
                    success.append({"ok": False, "error": str(exc)})
                    cur_idx += 1

        # Step 4 — IMPLEMENTS link rows for rows whose nodes succeeded AND
        # carry a non-empty user_story_ids list.
        link_rows: list[dict[str, Any]] = []
        for idx, prepared_row in enumerate(prepared):
            cmd_id = cmd_id_by_index.get(idx)
            if not cmd_id:
                continue
            for us_id in prepared_row["_user_story_ids"]:
                if us_id:
                    link_rows.append({"user_story_id": us_id, "command_id": cmd_id})
        for chunk in chunked(link_rows):
            try:
                with self.session() as session:
                    with_retry(
                        lambda s=session, c=chunk: run_chunk(
                            s, _COMMAND_USER_STORY_LINK_CYPHER, c, return_field="result"
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                from api.platform.observability.smart_logger import SmartLogger

                SmartLogger.log(
                    "WARN",
                    f"ingestion.batch.command.user_story_link_failed err={exc}",
                    category="ingestion.batch.command.user_story_link_failed",
                    params={"error": str(exc), "linkChunk": len(chunk)},
                )

        # Step 5 — reassemble in input order.
        all_errors = list(agg_missing_errors) + list(errors)
        out = reorder_to_input(rows, success, all_errors)
        duration_ms = (perf_counter() - started) * 1000.0
        emit_flush_log(
            "command",
            count=len(rows),
            duration_ms=duration_ms,
            chunks=chunk_count,
            errors=sum(1 for r in out if not r.get("ok")),
            session_id=session_id,
            phase=phase,
        )
        return out

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


