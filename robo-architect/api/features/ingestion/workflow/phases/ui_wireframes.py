from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.observability.smart_logger import SmartLogger


async def generate_ui_wireframes_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Optional phase: generate UI wireframe stickers for commands and readmodels, based on user story ui_description.

    Design goal: keep this lightweight and deterministic:
    - Create at most 1 UI per Command
    - Create at most 1 UI per ReadModel
    - Use the first related user story that has a ui_description
    - Attach UI to Command/ReadModel (ATTACHED_TO), and to BC (HAS_UI)
    """
    yield ProgressEvent(phase=IngestionPhase.GENERATING_UI, message="UI 와이어프레임 생성 중...", progress=87)

    user_story_ui: dict[str, str] = {}
    for us in ctx.user_stories or []:
        ui_desc = getattr(us, "ui_description", "") or ""
        if ui_desc.strip():
            user_story_ui[us.id] = ui_desc.strip()

    created = 0
    created_by_command: set[str] = set()
    created_by_readmodel: set[str] = set()

    for bc in ctx.bounded_contexts or []:
        # -------------------------------------------------------------
        # Command UI
        # -------------------------------------------------------------
        for agg in ctx.aggregates_by_bc.get(bc.id, []) or []:
            for cmd in ctx.commands_by_agg.get(agg.id, []) or []:
                if cmd.id in created_by_command:
                    continue

                story_ids = getattr(cmd, "user_story_ids", []) or []
                chosen_us_id = None
                chosen_ui_desc = ""
                for us_id in story_ids:
                    if us_id in user_story_ui:
                        chosen_us_id = us_id
                        chosen_ui_desc = user_story_ui[us_id]
                        break

                if not chosen_ui_desc:
                    continue

                # Deterministic + collision-free (explicit target type)
                ui_id = f"UI-CMD-{cmd.id}"
                ui_name = f"{cmd.name} UI"

                try:
                    ui = ctx.client.create_ui(
                        id=ui_id,
                        name=ui_name,
                        bc_id=bc.id,
                        description=chosen_ui_desc,
                        template="",
                        attached_to_id=cmd.id,
                        attached_to_type="Command",
                        attached_to_name=cmd.name,
                        user_story_id=chosen_us_id,
                    )
                    ctx.uis.append(ui)
                    created += 1
                    created_by_command.add(cmd.id)

                    yield ProgressEvent(
                        phase=IngestionPhase.GENERATING_UI,
                        message=f"UI 생성: {ui_name}",
                        progress=88,
                        data={
                            "type": "UI",
                            "object": {
                                "id": ui_id,
                                "name": ui_name,
                                "type": "UI",
                                "parentId": bc.id,
                                "template": "",
                                "attachedToId": cmd.id,
                                "attachedToType": "Command",
                                "attachedToName": cmd.name,
                                "userStoryId": chosen_us_id,
                                "description": chosen_ui_desc,
                            },
                        },
                    )
                    await asyncio.sleep(0.08)
                except Exception as e:
                    SmartLogger.log(
                        "WARNING",
                        "UI creation skipped",
                        category="ingestion.neo4j.ui",
                        params={"session_id": ctx.session.id, "ui_id": ui_id, "command_id": cmd.id, "error": str(e)},
                    )

        # -------------------------------------------------------------
        # ReadModel UI
        # -------------------------------------------------------------
        for rm in ctx.readmodels_by_bc.get(bc.id, []) or []:
            rm_id = rm.get("id")
            if not rm_id or rm_id in created_by_readmodel:
                continue

            story_ids = rm.get("user_story_ids", []) or []
            chosen_us_id = None
            chosen_ui_desc = ""
            for us_id in story_ids:
                if us_id in user_story_ui:
                    chosen_us_id = us_id
                    chosen_ui_desc = user_story_ui[us_id]
                    break

            if not chosen_ui_desc:
                continue

            ui_id = f"UI-RM-{rm_id}"
            ui_name = f"{rm.get('name', rm_id)} UI"

            try:
                ui = ctx.client.create_ui(
                    id=ui_id,
                    name=ui_name,
                    bc_id=bc.id,
                    description=chosen_ui_desc,
                    template="",
                    attached_to_id=rm_id,
                    attached_to_type="ReadModel",
                    attached_to_name=rm.get("name"),
                    user_story_id=chosen_us_id,
                )
                ctx.uis.append(ui)
                created += 1
                created_by_readmodel.add(rm_id)

                yield ProgressEvent(
                    phase=IngestionPhase.GENERATING_UI,
                    message=f"UI 생성: {ui_name}",
                    progress=88,
                    data={
                        "type": "UI",
                        "object": {
                            "id": ui_id,
                            "name": ui_name,
                            "type": "UI",
                            "parentId": bc.id,
                            "template": "",
                            "attachedToId": rm_id,
                            "attachedToType": "ReadModel",
                            "attachedToName": rm.get("name"),
                            "userStoryId": chosen_us_id,
                            "description": chosen_ui_desc,
                        },
                    },
                )
                await asyncio.sleep(0.08)
            except Exception as e:
                SmartLogger.log(
                    "WARNING",
                    "UI creation skipped",
                    category="ingestion.neo4j.ui",
                    params={"session_id": ctx.session.id, "ui_id": ui_id, "readmodel_id": rm_id, "error": str(e)},
                )

    SmartLogger.log(
        "INFO",
        "UI wireframes generated",
        category="ingestion.workflow.ui",
        params={"session_id": ctx.session.id, "count": created},
    )


