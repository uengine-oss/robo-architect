"""
Link Commands to existing Events (Event Modeling path)

User-story events are created earlier without a Command. After commands exist,
this phase maps each Command → event name(s) and creates only EMITS edges —
no second LLM event extraction, no duplicate Event nodes.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.observability.smart_logger import SmartLogger


class CommandEmittedEvents(BaseModel):
    command_name: str = Field(..., description="Exact Command name from the list")
    emitted_event_names: list[str] = Field(
        default_factory=list,
        description="Event names this command emits; must be from the available events list only",
    )


class AggregateCommandEventLinks(BaseModel):
    links: list[CommandEmittedEvents] = Field(default_factory=list)


SYSTEM = (
    "You connect Domain Commands to business Events that already exist. "
    "Use only event names from the provided list. Output exact string matches."
)

USER_TEMPLATE = """## Aggregate
Name: {aggregate_name}
Bounded context: {bc_name}

## Commands (name — description)
{commands_block}

## Available Events (names only — from user stories in this BC)
{events_block}

For each Command, list which of the **Available Events** it emits when it succeeds (and optional failure events if clearly implied).
- Every Command should emit at least one event when possible.
- **emitted_event_names** must be copied exactly from the Available Events list (no new names).
If a command does not match any listed event, use an empty list for emitted_event_names.
"""


def _bc_user_story_ids(bc: Any) -> list[str]:
    try:
        if hasattr(bc, "model_dump"):
            bc_dict = bc.model_dump()
            ids = bc_dict.get("user_story_ids", [])
        elif hasattr(bc, "dict"):
            ids = bc.dict().get("user_story_ids", [])
        elif isinstance(bc, dict):
            ids = bc.get("user_story_ids", [])
        else:
            ids = getattr(bc, "user_story_ids", None) or []
    except Exception:
        ids = getattr(bc, "user_story_ids", None) or []
    if not isinstance(ids, list):
        return []
    return [x for x in ids if x]


def _candidate_event_names_for_bc(ctx: IngestionWorkflowContext, bc: Any) -> list[str]:
    us_ids = set(_bc_user_story_ids(bc))
    names: list[str] = []
    for e in ctx.events_from_us or []:
        if not isinstance(e, dict):
            continue
        us_id = e.get("userStoryId") or e.get("user_story_id") or ""
        if us_id not in us_ids:
            continue
        n = (e.get("name") or "").strip()
        if n and n not in names:
            names.append(n)
    if not names and ctx.events_from_us:
        for e in ctx.events_from_us:
            if isinstance(e, dict):
                n = (e.get("name") or "").strip()
                if n and n not in names:
                    names.append(n)
    return names


def _refresh_events_by_agg(ctx: IngestionWorkflowContext) -> None:
    all_events: dict[str, list[dict[str, Any]]] = {}
    for _bc_id, aggregates in (ctx.aggregates_by_bc or {}).items():
        for agg in aggregates or []:
            agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
            if not agg_id:
                continue
            cmds = ctx.commands_by_agg.get(agg_id, []) or []
            merged: list[dict[str, Any]] = []
            seen: set[str] = set()
            for cmd in cmds:
                cmd_id = cmd.get("id") if isinstance(cmd, dict) else getattr(cmd, "id", None)
                if not cmd_id:
                    continue
                evts = ctx.client.get_events_emitted_by_command(cmd_id)
                for evt in evts:
                    eid = evt.get("id")
                    if eid and eid not in seen:
                        seen.add(eid)
                        merged.append(evt)
            if merged:
                all_events[agg_id] = merged
    ctx.events_by_agg = all_events


async def link_commands_to_existing_events_phase(
    ctx: IngestionWorkflowContext,
) -> AsyncGenerator[ProgressEvent, None]:
    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_EVENTS,
        message="Command → Event 연결 중 (기존 이벤트)...",
        progress=72,
    )

    if not ctx.commands_by_agg:
        ctx.events_by_agg = {}
        return

    structured = ctx.llm.with_structured_output(AggregateCommandEventLinks)
    linked_total = 0

    for bc in ctx.bounded_contexts or []:
        bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
        bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", "") or ""
        if not bc_id:
            continue

        event_names = _candidate_event_names_for_bc(ctx, bc)
        events_block = "\n".join(f"- {n}" for n in event_names) if event_names else "(none — leave emitted_event_names empty)"

        for agg in ctx.aggregates_by_bc.get(bc_id, []) or []:
            agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
            agg_name = agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", "") or ""
            cmds = ctx.commands_by_agg.get(agg_id, []) or []
            if not cmds:
                continue
            if not event_names:
                continue

            if getattr(ctx.session, "is_cancelled", False):
                yield ProgressEvent(
                    phase=IngestionPhase.ERROR,
                    message="❌ 생성이 중단되었습니다",
                    progress=getattr(ctx.session, "progress", 0) or 0,
                    data={"error": "Cancelled by user", "cancelled": True},
                )
                return

            commands_block = "\n".join(
                f"- {c.get('name') if isinstance(c, dict) else getattr(c, 'name', '')}: "
                f"{c.get('description') if isinstance(c, dict) else getattr(c, 'description', '')}"
                for c in cmds
            )

            prompt = USER_TEMPLATE.format(
                aggregate_name=agg_name,
                bc_name=bc_name,
                commands_block=commands_block,
                events_block=events_block,
            )

            try:
                out = await asyncio.wait_for(
                    asyncio.to_thread(
                        structured.invoke,
                        [SystemMessage(content=SYSTEM), HumanMessage(content=prompt)],
                    ),
                    timeout=120.0,
                )
                links = (out.links if out else []) or []
            except Exception as e:
                SmartLogger.log(
                    "ERROR",
                    f"Command–Event link LLM failed: {e}",
                    category="ingestion.workflow.link_cmd_evt",
                    params={"session_id": ctx.session.id, "agg_id": agg_id, "error": str(e)},
                )
                links = []

            allowed_set = set(event_names)
            cmd_name_to_id: dict[str, str] = {}
            for c in cmds:
                cn = (c.get("name") if isinstance(c, dict) else getattr(c, "name", "") or "").strip()
                cid = c.get("id") if isinstance(c, dict) else getattr(c, "id", None)
                if cn and cid:
                    cmd_name_to_id[cn] = cid

            for row in links:
                cname = (row.command_name or "").strip()
                cmd_id = cmd_name_to_id.get(cname)
                if not cmd_id:
                    continue
                for ename in row.emitted_event_names or []:
                    ename = (ename or "").strip()
                    if not ename or ename not in allowed_set:
                        continue
                    ok = await asyncio.wait_for(
                        asyncio.to_thread(
                            ctx.client.link_command_to_event_by_name,
                            command_id=cmd_id,
                            event_name=ename,
                        ),
                        timeout=10.0,
                    )
                    if ok:
                        linked_total += 1

    _refresh_events_by_agg(ctx)

    SmartLogger.log(
        "INFO",
        f"Command→Event EMITS links created: {linked_total}",
        category="ingestion.workflow.link_cmd_evt.done",
        params={
            "session_id": ctx.session.id,
            "aggregates_with_events": len(ctx.events_by_agg),
        },
    )

