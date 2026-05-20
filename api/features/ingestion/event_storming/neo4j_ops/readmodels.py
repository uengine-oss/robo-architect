from __future__ import annotations

from typing import Any

from api.platform.keys import readmodel_key

from ._bulk_helper import (
    BulkResult,
    bulk_flush,
    chunked,
    reorder_to_input,
    run_chunk,
    validate_required,
    with_retry,
)


_READMODEL_BULK_CYPHER = """
UNWIND $rows AS r
MATCH (bc:BoundedContext {id: r.bc_id})
MERGE (rm:ReadModel {key: r.key})
  ON CREATE SET rm.id = randomUUID(),
                rm.createdAt = datetime()
SET rm.key = r.key,
    rm.name = r.name,
    rm.displayName = r.display_name,
    rm.description = r.description,
    rm.provisioningType = r.provisioning_type,
    rm.actor = r.actor,
    rm.isMultipleResult = r.is_multiple_result,
    rm.updatedAt = datetime()
MERGE (bc)-[:HAS_READMODEL]->(rm)
RETURN rm {.id, .key, .name, .displayName, .description, .provisioningType, .actor, .isMultipleResult} AS result
"""


_READMODEL_USER_STORY_LINK_CYPHER = """
UNWIND $rows AS r
MATCH (us:UserStory {id: r.user_story_id})
MATCH (rm:ReadModel {id: r.readmodel_id})
MERGE (us)-[rel:IMPLEMENTS]->(rm)
  ON CREATE SET rel.confidence = coalesce(r.confidence, 0.9),
                rel.createdAt = datetime()
SET rel.confidence = coalesce(r.confidence, rel.confidence, 0.9)
RETURN {us_id: us.id, rm_id: rm.id} AS result
"""


class ReadModelOps:
    # =========================================================================
    # ReadModel Operations
    # =========================================================================

    def create_readmodel(
        self,
        *,
        name: str,
        bc_id: str,
        key: str | None = None,
        description: str | None = None,
        provisioning_type: str = "CQRS",
        actor: str | None = None,
        is_multiple_result: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a ReadModel node and link it to a BoundedContext via HAS_READMODEL.

        NOTE:
        - provisioningType is used by the UI to decide CQRS config behavior.
        - We keep this idempotent (MERGE on key).
        """
        display_name = display_name or name
        with self.session() as session:
            bc_rec = session.run("MATCH (bc:BoundedContext {id: $id}) RETURN bc.key as key", id=bc_id).single()
            bc_key_value = (bc_rec or {}).get("key") or ""
            if not bc_key_value:
                raise ValueError(f"BoundedContext not found or missing key: {bc_id}")
            key = key or readmodel_key(bc_key_value, name)

            query = """
            MATCH (bc:BoundedContext {id: $bc_id})
            MERGE (rm:ReadModel {key: $key})
            ON CREATE SET rm.id = randomUUID(),
                          rm.createdAt = datetime()
            SET rm.key = $key,
                rm.name = $name,
                rm.displayName = $display_name,
                rm.description = $description,
                rm.provisioningType = $provisioning_type,
                rm.actor = $actor,
                rm.isMultipleResult = $is_multiple_result,
                rm.updatedAt = datetime()
            MERGE (bc)-[:HAS_READMODEL]->(rm)
            RETURN rm {.id, .key, .name, .displayName, .description, .provisioningType, .actor, .isMultipleResult} as readmodel
            """
            result = session.run(
                query,
                key=key,
                name=name,
                display_name=display_name,
                bc_id=bc_id,
                description=description,
                provisioning_type=provisioning_type,
                actor=actor,
                is_multiple_result=is_multiple_result,
            )
            return dict(result.single()["readmodel"])

    def bulk_create_readmodels(
        self,
        rows: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> list[BulkResult]:
        """Persist read models in batch — schema-equivalent to `create_readmodel`.

        Required: `name`, `bc_id`. Optional: `key`, `description`,
        `provisioning_type` (default `"CQRS"`), `actor`, `is_multiple_result`,
        `display_name`, `user_story_ids`.
        """
        if not rows:
            return []

        valid, errors = validate_required(rows, ["name", "bc_id"])

        bc_ids = sorted({r["bc_id"] for r in valid})
        bc_key_map: dict[str, str] = {}
        if bc_ids:
            with self.session() as session:
                cur = session.run(
                    "MATCH (bc:BoundedContext) WHERE bc.id IN $ids RETURN bc.id AS id, bc.key AS key",
                    ids=bc_ids,
                )
                for rec in cur:
                    if rec and rec.get("id") and rec.get("key"):
                        bc_key_map[rec["id"]] = rec["key"]

        prepared: list[dict[str, Any]] = []
        bc_missing: list[BulkResult] = []
        for r in valid:
            bc_key_value = bc_key_map.get(r["bc_id"])
            if not bc_key_value:
                bc_missing.append(
                    {
                        "ok": False,
                        "error": f"BoundedContext not found: {r['bc_id']}",
                        "error_field": "bc_id",
                        "id": r.get("id"),
                    }
                )
                continue
            key = r.get("key") or readmodel_key(bc_key_value, r["name"])
            prepared.append(
                {
                    "key": key,
                    "name": r["name"],
                    "bc_id": r["bc_id"],
                    "display_name": r.get("display_name") or r["name"],
                    "description": r.get("description"),
                    "provisioning_type": r.get("provisioning_type") or "CQRS",
                    "actor": r.get("actor"),
                    "is_multiple_result": r.get("is_multiple_result"),
                    "_user_story_ids": r.get("user_story_ids") or [],
                }
            )

        # Pass 1: nodes via bulk_flush (no dedupe within batch — `key` is the
        # natural unique field already and we want every input row to map 1:1).
        # We can't use bulk_flush here because we need rm_id for pass-2 links;
        # but bulk_flush already does this correctly when we read `id` from
        # success results.
        from time import perf_counter

        from ._bulk_helper import emit_flush_log

        started = perf_counter()
        success: list[BulkResult] = []
        chunk_count = 0
        cur_idx = 0
        rm_id_by_index: dict[int, str | None] = {}
        node_chunk_payloads = [
            {k: v for k, v in row.items() if not k.startswith("_")} for row in prepared
        ]
        for chunk in chunked(node_chunk_payloads):
            chunk_count += 1
            try:
                with self.session() as session:
                    rs = with_retry(
                        lambda s=session, c=chunk: run_chunk(
                            s, _READMODEL_BULK_CYPHER, c, return_field="result"
                        )
                    )
                for r in rs:
                    rm_id_by_index[cur_idx] = r.get("id") if r else None
                    success.append({"ok": True, **r} if r else {"ok": False, "error": "no result row"})
                    cur_idx += 1
            except Exception as exc:  # noqa: BLE001
                for _ in chunk:
                    rm_id_by_index[cur_idx] = None
                    success.append({"ok": False, "error": str(exc)})
                    cur_idx += 1

        # Pass 2: UserStory IMPLEMENTS rels.
        link_rows: list[dict[str, Any]] = []
        for idx, prepared_row in enumerate(prepared):
            rm_id = rm_id_by_index.get(idx)
            if not rm_id:
                continue
            for us_id in prepared_row["_user_story_ids"]:
                if us_id:
                    link_rows.append({"user_story_id": us_id, "readmodel_id": rm_id})
        for chunk in chunked(link_rows):
            try:
                with self.session() as session:
                    with_retry(
                        lambda s=session, c=chunk: run_chunk(
                            s, _READMODEL_USER_STORY_LINK_CYPHER, c, return_field="result"
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                from api.platform.observability.smart_logger import SmartLogger

                SmartLogger.log(
                    "WARN",
                    f"ingestion.batch.readmodel.user_story_link_failed err={exc}",
                    category="ingestion.batch.readmodel.user_story_link_failed",
                    params={"error": str(exc), "linkChunk": len(chunk)},
                )

        all_errors = list(bc_missing) + list(errors)
        out = reorder_to_input(rows, success, all_errors)
        duration_ms = (perf_counter() - started) * 1000.0
        emit_flush_log(
            "readmodel",
            count=len(rows),
            duration_ms=duration_ms,
            chunks=chunk_count,
            errors=sum(1 for r in out if not r.get("ok")),
            session_id=session_id,
            phase=phase,
        )
        return out

    def link_readmodel_to_event(
        self,
        *,
        readmodel_id: str,
        event_name: str,
    ) -> bool:
        """
        Create CQRS projection chain compatible with ReadModelCQRSEditor:
          ReadModel -[:HAS_CQRS]-> CQRSConfig -[:HAS_OPERATION]-> CQRSOperation -[:TRIGGERED_BY]-> Event

        ID conventions (must match readmodel_cqrs router):
          CQRSConfig.id  = "CQRS-{readmodelId}"
          CQRSOperation.id = "CQRS-OP-{readmodelId}-INSERT-{eventId}"

        Finds Event by name (cross-BC safe). Idempotent via MERGE.
        Returns True if link was created, False if Event not found.
        """
        with self.session() as session:
            # name → displayName → 대소문자 무시 순으로 fuzzy matching
            query = """
            MATCH (rm:ReadModel {id: $rm_id})
            OPTIONAL MATCH (evt1:Event {name: $event_name})
            OPTIONAL MATCH (evt2:Event {displayName: $event_name})
            OPTIONAL MATCH (evt3:Event) WHERE toLower(evt3.name) = toLower($event_name)
               OR toLower(evt3.displayName) = toLower($event_name)
            WITH rm, coalesce(evt1, evt2, evt3) AS evt
            WHERE evt IS NOT NULL
            WITH rm, evt, 'CQRS-' + rm.id AS cqrsId,
                 'CQRS-OP-' + rm.id + '-INSERT-' + evt.id AS opId

            MERGE (cqrs:CQRSConfig {id: cqrsId})
            SET cqrs.readmodelId = rm.id
            MERGE (rm)-[:HAS_CQRS]->(cqrs)

            MERGE (op:CQRSOperation {id: opId})
            SET op.operationType = 'INSERT',
                op.cqrsConfigId = cqrsId,
                op.triggerEventId = evt.id
            MERGE (cqrs)-[:HAS_OPERATION]->(op)
            MERGE (op)-[:TRIGGERED_BY]->(evt)
            RETURN evt.id AS eventId
            LIMIT 1
            """
            result = session.run(query, rm_id=readmodel_id, event_name=event_name)
            record = result.single()
            return record is not None

    def link_user_story_to_readmodel(
        self,
        user_story_id: str,
        readmodel_id: str,
        confidence: float = 0.9,
    ) -> bool:
        """Persist (UserStory)-[:IMPLEMENTS]->(ReadModel) bidirectionally.

        Mirrors `link_user_story_to_aggregate` / `_command` / `_event` — every
        other ES node type already has this helper. Without it the Inspector
        traceability "출처" tab cannot show distinct source US's per ReadModel
        and falls back to BC-wide fan-out which makes all ReadModels in a BC
        share identical sources (the original bug).
        """
        with self.session() as session:
            result = session.run(
                """
                MATCH (us:UserStory {id: $usid})
                MATCH (rm:ReadModel {id: $rmid})
                MERGE (us)-[r1:IMPLEMENTS]->(rm)
                  ON CREATE SET r1.confidence = $conf
                MERGE (rm)-[r2:IMPLEMENTS]->(us)
                  ON CREATE SET r2.confidence = $conf
                RETURN id(us) AS uid
                """,
                usid=user_story_id,
                rmid=readmodel_id,
                conf=confidence,
            )
            return result.single() is not None


