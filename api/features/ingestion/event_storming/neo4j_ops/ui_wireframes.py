from __future__ import annotations

from typing import Any

from api.platform.keys import slugify, ui_key

from ._bulk_helper import (
    BulkResult,
    chunked,
    emit_flush_log,
    reorder_to_input,
    run_chunk,
    validate_required,
    with_retry,
)


_UI_BULK_CYPHER = """
UNWIND $rows AS r
MATCH (bc:BoundedContext {id: r.bc_id})
MERGE (ui:UI {key: r.key})
  ON CREATE SET ui.id = randomUUID(),
                ui.createdAt = datetime()
SET ui.key = r.key,
    ui.name = r.name,
    ui.displayName = r.display_name,
    ui.description = r.description,
    ui.template = r.template,
    ui.sceneGraph = r.scene_graph,
    ui.attachedToId = r.attached_to_id,
    ui.attachedToType = r.attached_to_type,
    ui.attachedToName = r.attached_to_name,
    ui.userStoryId = r.user_story_id,
    ui.actor = r.actor,
    ui.figmaFileKey = r.figma_file_key,
    ui.figmaNodeId = r.figma_node_id,
    ui.updatedAt = datetime()
MERGE (bc)-[:HAS_UI]->(ui)
RETURN ui {.id, .key, .name, .displayName, .description, .template, .sceneGraph,
           .attachedToId, .attachedToType, .attachedToName, .userStoryId, .actor,
           .figmaFileKey, .figmaNodeId} AS result
"""


_UI_ATTACHED_COMMAND_CYPHER = """
UNWIND $rows AS r
MATCH (ui:UI {id: r.ui_id})
MATCH (target:Command {id: r.target_id})
MERGE (ui)-[:ATTACHED_TO]->(target)
RETURN ui.id AS ui_id
"""

_UI_ATTACHED_READMODEL_CYPHER = """
UNWIND $rows AS r
MATCH (ui:UI {id: r.ui_id})
MATCH (target:ReadModel {id: r.target_id})
MERGE (ui)-[:ATTACHED_TO]->(target)
RETURN ui.id AS ui_id
"""


class UIWireframeOps:
    # =========================================================================
    # UI Wireframe Operations
    # =========================================================================

    def create_ui(
        self,
        *,
        name: str,
        bc_id: str,
        key: str | None = None,
        description: str | None = None,
        template: str | None = None,
        scene_graph: str | None = None,
        attached_to_id: str | None = None,
        attached_to_type: str = "Command",
        attached_to_name: str | None = None,
        user_story_id: str | None = None,
        display_name: str | None = None,
        figma_file_key: str | None = None,
        figma_node_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a UI wireframe node and link it to:
        - BoundedContext via HAS_UI
        - (optional) attached target via ATTACHED_TO
        """
        with self.session() as session:
            if not key:
                if attached_to_id:
                    key = ui_key(attached_to_type, attached_to_id)
                else:
                    # Fallback for unattached UI: stable within the BC by name.
                    bc_rec = session.run("MATCH (bc:BoundedContext {id: $id}) RETURN bc.key as key", id=bc_id).single()
                    bc_key_value = (bc_rec or {}).get("key") or ""
                    if not bc_key_value:
                        raise ValueError(f"BoundedContext not found or missing key: {bc_id}")
                    key = f"{bc_key_value}.ui.{slugify(name)}"

            display_name_val = display_name if display_name is not None else name

            # Resolve actor from the attached Command/ReadModel
            resolved_actor = None
            if attached_to_id and attached_to_type == "Command":
                actor_rec = session.run(
                    "MATCH (cmd:Command {id: $id}) RETURN cmd.actor as actor",
                    id=attached_to_id,
                ).single()
                resolved_actor = (actor_rec or {}).get("actor")
            elif attached_to_id and attached_to_type == "ReadModel":
                actor_rec = session.run(
                    "MATCH (rm:ReadModel {id: $id}) RETURN rm.actor as actor",
                    id=attached_to_id,
                ).single()
                resolved_actor = (actor_rec or {}).get("actor")

            query = """
            MATCH (bc:BoundedContext {id: $bc_id})
            MERGE (ui:UI {key: $key})
            ON CREATE SET ui.id = randomUUID(),
                          ui.createdAt = datetime()
            SET ui.key = $key,
                ui.name = $name,
                ui.displayName = $display_name,
                ui.description = $description,
                ui.template = $template,
                ui.sceneGraph = $scene_graph,
                ui.attachedToId = $attached_to_id,
                ui.attachedToType = $attached_to_type,
                ui.attachedToName = $attached_to_name,
                ui.userStoryId = $user_story_id,
                ui.actor = $actor,
                ui.figmaFileKey = $figma_file_key,
                ui.figmaNodeId = $figma_node_id,
                ui.updatedAt = datetime()
            MERGE (bc)-[:HAS_UI]->(ui)
            RETURN ui {.id, .key, .name, .displayName, .description, .template, .sceneGraph, .attachedToId, .attachedToType, .attachedToName, .userStoryId, .actor, .figmaFileKey, .figmaNodeId} as ui
            """
            result = session.run(
                query,
                key=key,
                name=name,
                display_name=display_name_val,
                bc_id=bc_id,
                description=description,
                template=template,
                scene_graph=scene_graph,
                attached_to_id=attached_to_id,
                attached_to_type=attached_to_type,
                attached_to_name=attached_to_name,
                user_story_id=user_story_id,
                actor=resolved_actor,
                figma_file_key=figma_file_key,
                figma_node_id=figma_node_id,
            )
            ui = dict(result.single()["ui"])

            # Attach relationship (best-effort; keep schema flexible)
            if attached_to_id:
                attach_query = f"""
                MATCH (ui:UI {{id: $ui_id}})
                MATCH (target:{attached_to_type} {{id: $target_id}})
                MERGE (ui)-[:ATTACHED_TO]->(target)
                """
                session.run(attach_query, ui_id=ui["id"], target_id=attached_to_id)

            return ui

    def bulk_create_uis(
        self,
        rows: list[dict[str, Any]],
        *,
        session_id: str | None = None,
        phase: str | None = None,
    ) -> list[BulkResult]:
        """Persist UI wireframes in batch — schema-equivalent to `create_ui`.

        Required: `name`, `bc_id`. Optional: everything `create_ui` accepts.

        Three passes:
          1. Resolve every distinct `bc_id` → `bc.key` (for fallback key gen).
          2. Resolve `actor` for every distinct `(attached_to_type, attached_to_id)`.
          3. UNWIND nodes + HAS_UI rels.
          4. UNWIND ATTACHED_TO rels for the two attachment types.
        """
        if not rows:
            return []

        from time import perf_counter

        started = perf_counter()
        valid, errors = validate_required(rows, ["name", "bc_id"])

        # Step 1 — bc.key map (for fallback key generation when no attached_to_id).
        bc_ids_needing_fallback = sorted(
            {r["bc_id"] for r in valid if not r.get("key") and not r.get("attached_to_id")}
        )
        bc_key_map: dict[str, str] = {}
        if bc_ids_needing_fallback:
            with self.session() as session:
                cur = session.run(
                    "MATCH (bc:BoundedContext) WHERE bc.id IN $ids RETURN bc.id AS id, bc.key AS key",
                    ids=bc_ids_needing_fallback,
                )
                for rec in cur:
                    if rec and rec.get("id") and rec.get("key"):
                        bc_key_map[rec["id"]] = rec["key"]

        # Step 2 — actor resolution per (type, id).
        cmd_ids = sorted({
            r["attached_to_id"] for r in valid
            if r.get("attached_to_id") and (r.get("attached_to_type") or "Command") == "Command"
        })
        rm_ids = sorted({
            r["attached_to_id"] for r in valid
            if r.get("attached_to_id") and r.get("attached_to_type") == "ReadModel"
        })
        actor_map: dict[tuple[str, str], str | None] = {}
        with self.session() as session:
            if cmd_ids:
                cur = session.run(
                    "MATCH (cmd:Command) WHERE cmd.id IN $ids RETURN cmd.id AS id, cmd.actor AS actor",
                    ids=cmd_ids,
                )
                for rec in cur:
                    if rec:
                        actor_map[("Command", rec["id"])] = rec.get("actor")
            if rm_ids:
                cur = session.run(
                    "MATCH (rm:ReadModel) WHERE rm.id IN $ids RETURN rm.id AS id, rm.actor AS actor",
                    ids=rm_ids,
                )
                for rec in cur:
                    if rec:
                        actor_map[("ReadModel", rec["id"])] = rec.get("actor")

        # Step 3 — derive every row's payload.
        prepared: list[dict[str, Any]] = []
        prep_errors: list[BulkResult] = []
        for r in valid:
            attached_to_id = r.get("attached_to_id")
            attached_to_type = r.get("attached_to_type") or "Command"
            key = r.get("key")
            if not key:
                if attached_to_id:
                    key = ui_key(attached_to_type, attached_to_id)
                else:
                    bc_key_value = bc_key_map.get(r["bc_id"])
                    if not bc_key_value:
                        prep_errors.append(
                            {
                                "ok": False,
                                "error": f"BoundedContext not found: {r['bc_id']}",
                                "error_field": "bc_id",
                                "id": r.get("id"),
                            }
                        )
                        continue
                    key = f"{bc_key_value}.ui.{slugify(r['name'])}"
            display_name = (
                r.get("display_name") if r.get("display_name") is not None else r["name"]
            )
            resolved_actor = (
                actor_map.get((attached_to_type, attached_to_id))
                if attached_to_id
                else r.get("actor")
            )
            prepared.append(
                {
                    "key": key,
                    "name": r["name"],
                    "bc_id": r["bc_id"],
                    "display_name": display_name,
                    "description": r.get("description"),
                    "template": r.get("template"),
                    "scene_graph": r.get("scene_graph"),
                    "attached_to_id": attached_to_id,
                    "attached_to_type": attached_to_type,
                    "attached_to_name": r.get("attached_to_name"),
                    "user_story_id": r.get("user_story_id"),
                    "actor": resolved_actor,
                    "figma_file_key": r.get("figma_file_key"),
                    "figma_node_id": r.get("figma_node_id"),
                }
            )

        # Step 4 — UNWIND nodes.
        success: list[BulkResult] = []
        chunk_count = 0
        cur_idx = 0
        ui_id_by_index: dict[int, str | None] = {}
        for chunk in chunked(prepared):
            chunk_count += 1
            try:
                with self.session() as session:
                    rs = with_retry(
                        lambda s=session, c=chunk: run_chunk(
                            s, _UI_BULK_CYPHER, c, return_field="result"
                        )
                    )
                for r in rs:
                    ui_id_by_index[cur_idx] = r.get("id") if r else None
                    success.append({"ok": True, **r} if r else {"ok": False, "error": "no result row"})
                    cur_idx += 1
            except Exception as exc:  # noqa: BLE001
                for _ in chunk:
                    ui_id_by_index[cur_idx] = None
                    success.append({"ok": False, "error": str(exc)})
                    cur_idx += 1

        # Step 5 — ATTACHED_TO rels (split by type because Cypher labels can't
        # be parameterized).
        cmd_attach_rows: list[dict[str, Any]] = []
        rm_attach_rows: list[dict[str, Any]] = []
        for idx, prepared_row in enumerate(prepared):
            ui_id = ui_id_by_index.get(idx)
            target_id = prepared_row["attached_to_id"]
            if not ui_id or not target_id:
                continue
            tt = prepared_row["attached_to_type"]
            payload = {"ui_id": ui_id, "target_id": target_id}
            if tt == "ReadModel":
                rm_attach_rows.append(payload)
            else:
                cmd_attach_rows.append(payload)

        for chunk in chunked(cmd_attach_rows):
            try:
                with self.session() as session:
                    with_retry(
                        lambda s=session, c=chunk: run_chunk(
                            s, _UI_ATTACHED_COMMAND_CYPHER, c, return_field="ui_id"
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                from api.platform.observability.smart_logger import SmartLogger

                SmartLogger.log(
                    "WARN",
                    f"ingestion.batch.ui.attach_command_failed err={exc}",
                    category="ingestion.batch.ui.attach_command_failed",
                    params={"error": str(exc), "linkChunk": len(chunk)},
                )
        for chunk in chunked(rm_attach_rows):
            try:
                with self.session() as session:
                    with_retry(
                        lambda s=session, c=chunk: run_chunk(
                            s, _UI_ATTACHED_READMODEL_CYPHER, c, return_field="ui_id"
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                from api.platform.observability.smart_logger import SmartLogger

                SmartLogger.log(
                    "WARN",
                    f"ingestion.batch.ui.attach_readmodel_failed err={exc}",
                    category="ingestion.batch.ui.attach_readmodel_failed",
                    params={"error": str(exc), "linkChunk": len(chunk)},
                )

        all_errors = list(prep_errors) + list(errors)
        out = reorder_to_input(rows, success, all_errors)
        duration_ms = (perf_counter() - started) * 1000.0
        emit_flush_log(
            "ui",
            count=len(rows),
            duration_ms=duration_ms,
            chunks=chunk_count,
            errors=sum(1 for r in out if not r.get("ok")),
            session_id=session_id,
            phase=phase,
        )
        return out


