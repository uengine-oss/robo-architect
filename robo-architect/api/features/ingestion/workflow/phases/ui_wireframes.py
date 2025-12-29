from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.observability.smart_logger import SmartLogger


async def generate_ui_wireframes_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Optional phase: generate UI wireframe stickers for commands, based on user story ui_description.

    Design goal: keep this lightweight and deterministic:
    - Create at most 1 UI per Command
    - Use the first related user story that has a ui_description
    - Attach UI to Command (ATTACHED_TO), and to BC (HAS_UI)
    """
    yield ProgressEvent(phase=IngestionPhase.GENERATING_UI, message="UI 와이어프레임 생성 중...", progress=70)

    user_story_ui: dict[str, str] = {}
    for us in ctx.user_stories or []:
        ui_desc = getattr(us, "ui_description", "") or ""
        if ui_desc.strip():
            user_story_ui[us.id] = ui_desc.strip()

    created = 0
    created_by_command: set[str] = set()

    for bc in ctx.bounded_contexts or []:
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

                # Deterministic enough, but avoids collisions across multiple commands.
                ui_id = f"UI-{cmd.id}"
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
                        progress=72,
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

    SmartLogger.log(
        "INFO",
        "UI wireframes generated",
        category="ingestion.workflow.ui",
        params={"session_id": ctx.session.id, "count": created},
    )


