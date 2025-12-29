from __future__ import annotations

from typing import Any


class UIWireframeOps:
    # =========================================================================
    # UI Wireframe Operations
    # =========================================================================

    def create_ui(
        self,
        *,
        id: str,
        name: str,
        bc_id: str,
        description: str | None = None,
        template: str | None = None,
        attached_to_id: str | None = None,
        attached_to_type: str = "Command",
        attached_to_name: str | None = None,
        user_story_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a UI wireframe node and link it to:
        - BoundedContext via HAS_UI
        - (optional) attached target via ATTACHED_TO
        """
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})
        MERGE (ui:UI {id: $id})
        SET ui.name = $name,
            ui.description = $description,
            ui.template = $template,
            ui.attachedToId = $attached_to_id,
            ui.attachedToType = $attached_to_type,
            ui.attachedToName = $attached_to_name,
            ui.userStoryId = $user_story_id,
            ui.createdAt = coalesce(ui.createdAt, datetime()),
            ui.updatedAt = datetime()
        MERGE (bc)-[:HAS_UI]->(ui)
        RETURN ui {.id, .name, .description, .template, .attachedToId, .attachedToType, .attachedToName, .userStoryId} as ui
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
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
                session.run(attach_query, ui_id=id, target_id=attached_to_id)

            return ui


