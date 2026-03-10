from __future__ import annotations

from typing import Any

from api.platform.keys import slugify, ui_key


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
        attached_to_id: str | None = None,
        attached_to_type: str = "Command",
        attached_to_name: str | None = None,
        user_story_id: str | None = None,
        display_name: str | None = None,
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
                ui.attachedToId = $attached_to_id,
                ui.attachedToType = $attached_to_type,
                ui.attachedToName = $attached_to_name,
                ui.userStoryId = $user_story_id,
                ui.updatedAt = datetime()
            MERGE (bc)-[:HAS_UI]->(ui)
            RETURN ui {.id, .key, .name, .displayName, .description, .template, .attachedToId, .attachedToType, .attachedToName, .userStoryId} as ui
            """
            result = session.run(
                query,
                key=key,
                name=name,
                display_name=display_name_val,
                bc_id=bc_id,
                description=description,
                template=template,
                attached_to_id=attached_to_id,
                attached_to_type=attached_to_type,
                attached_to_name=attached_to_name,
                user_story_id=user_story_id,
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


