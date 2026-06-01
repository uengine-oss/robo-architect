"""Extract Invariants Phase (spec 027 — aggregate-invariants).

Runs right after GWT generation. For each Aggregate, asks the LLM to state the
business invariants the aggregate must always uphold, then persists each as a
first-class `Invariant` node (`source='ingested'`) and links it to the
Commands whose acceptance criteria verify it via `VERIFIED_BY`.

Idempotent: `Invariant` is `MERGE`d on its natural key, so re-ingesting the
same requirement updates rather than duplicates (spec FR-022).
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage
from api.platform.llm_messages import build_system_message
from pydantic import BaseModel, Field

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.observability.smart_logger import SmartLogger

PHASE_START = 88
PHASE_END = 91

_SYSTEM_PROMPT = (
    "You are a domain-driven design expert. For a given DDD Aggregate you "
    "identify its invariants — the business consistency rules the aggregate "
    "must ALWAYS uphold, regardless of which command runs. Each invariant is a "
    "single declarative sentence. When a listed command's behavior is what "
    "keeps an invariant true, name that command as a verifier. Produce 0-6 "
    "invariants; prefer fewer, genuine consistency rules over trivial ones."
)


class _ExtractedInvariant(BaseModel):
    declaration: str = Field(description="One declarative sentence stating the rule")
    verifying_command_names: list[str] = Field(
        default_factory=list,
        description="Names of listed commands whose behavior verifies this invariant",
    )


class _ExtractedInvariantSet(BaseModel):
    invariants: list[_ExtractedInvariant] = Field(default_factory=list)


def _build_prompt(agg: dict) -> str:
    lines = [
        f'Aggregate: "{agg.get("aggName") or ""}"',
        f'Root entity: {agg.get("rootEntity") or "(unspecified)"}',
        "",
        "Commands handled by this aggregate:",
    ]
    commands = agg.get("commands") or []
    if commands:
        for c in commands:
            lines.append(f'  - {c.get("name") or ""}')
    else:
        lines.append("  (none)")
    events = [e for e in (agg.get("events") or []) if e]
    if events:
        lines += ["", "Events it emits:"]
        lines += [f"  - {e}" for e in events]
    lines += [
        "",
        "List the invariants this aggregate must always uphold. For each, set "
        "verifying_command_names to the subset of the commands above that keep "
        "it true (use the exact command names; leave empty if none apply).",
    ]
    return "\n".join(lines)


async def extract_invariants_phase(
    ctx: IngestionWorkflowContext,
) -> AsyncGenerator[ProgressEvent, None]:
    """Extract candidate Invariants for every Aggregate and persist them."""
    client = ctx.client
    session_id = getattr(ctx.session, "id", None)

    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_INVARIANTS,
        message="📐 어그리거트 인베리언트를 추출하는 중...",
        progress=PHASE_START,
    )

    # Housekeeping — re-ingestion wipes session-scoped Aggregates but Invariant
    # nodes are not session-tagged. If a prior run's aggregate was renamed, its
    # invariants are left orphaned. Drop them before re-extracting so the model
    # only carries invariants attached to current aggregates.
    try:
        pruned = client.prune_orphan_invariants()
        if pruned:
            SmartLogger.log(
                "INFO",
                f"Pruned {pruned} orphan invariant(s) before extraction",
                category="agent.invariants.extract.prune",
                params={"session_id": session_id, "pruned": pruned},
            )
    except Exception as exc:  # noqa: BLE001 — housekeeping is best-effort
        SmartLogger.log(
            "WARN",
            f"Orphan-invariant prune failed (non-fatal): {exc}",
            category="agent.invariants.extract.prune.error",
            params={"session_id": session_id, "error": str(exc)},
        )

    with client.session() as session:
        agg_rows = list(
            session.run(
                """
                MATCH (agg:Aggregate)
                OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
                OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
                WITH agg, collect(DISTINCT cmd {.id, .name}) AS commands,
                     collect(DISTINCT evt.name) AS events
                RETURN agg.id AS aggId, agg.key AS aggKey, agg.name AS aggName,
                       agg.rootEntity AS rootEntity, commands, events
                ORDER BY agg.name
                """
            )
        )

    total = len(agg_rows)
    invariants_created = 0
    links_created = 0

    SmartLogger.log(
        "INFO",
        f"Invariant extraction started: {total} aggregates",
        category="agent.invariants.extract.start",
        params={"session_id": session_id, "aggregate_count": total},
    )

    for idx, row in enumerate(agg_rows):
        agg = {
            "aggId": row["aggId"],
            "aggKey": row["aggKey"],
            "aggName": row["aggName"] or "",
            "rootEntity": row["rootEntity"],
            "commands": [dict(c) for c in (row["commands"] or []) if c and c.get("id")],
            "events": list(row["events"] or []),
        }

        progress = PHASE_START + int((PHASE_END - PHASE_START) * (idx / max(total, 1)))
        yield ProgressEvent(
            phase=IngestionPhase.EXTRACTING_INVARIANTS,
            message=f"📐 '{agg['aggName']}' 인베리언트 추출 중... ({idx + 1}/{total})",
            progress=progress,
        )

        try:
            structured_llm = ctx.llm.with_structured_output(_ExtractedInvariantSet)
            result: _ExtractedInvariantSet = await asyncio.wait_for(
                asyncio.to_thread(
                    structured_llm.invoke,
                    [
                        build_system_message(_SYSTEM_PROMPT),
                        HumanMessage(content=_build_prompt(agg)),
                    ],
                ),
                timeout=180.0,
            )
            extracted = result.invariants or []
        except Exception as exc:  # noqa: BLE001 — skip this aggregate, keep going
            SmartLogger.log(
                "WARN",
                f"Invariant extraction LLM failed for aggregate '{agg['aggName']}': {exc}",
                category="agent.invariants.extract.error",
                params={"session_id": session_id, "aggregate_id": agg["aggId"], "error": str(exc)},
            )
            continue

        cmd_by_name = {(c.get("name") or "").strip().lower(): c["id"] for c in agg["commands"]}

        for seq, item in enumerate(extracted, start=1):
            declaration = (item.declaration or "").strip()
            if not declaration:
                continue
            invariant = client.upsert_invariant(
                aggregate_id=agg["aggId"],
                aggregate_key=agg["aggKey"],
                declaration=declaration,
                source="ingested",
                seq=seq,
                session_id=session_id,
            )
            if not invariant:
                continue
            invariants_created += 1
            for cmd_name in item.verifying_command_names or []:
                cmd_id = cmd_by_name.get((cmd_name or "").strip().lower())
                if cmd_id and client.link_invariant_verified_by(invariant["id"], cmd_id):
                    links_created += 1

    ctx.invariant_extraction_summary = {
        "invariants_created": invariants_created,
        "verified_by_links": links_created,
    }
    SmartLogger.log(
        "INFO",
        f"Invariant extraction done: {invariants_created} invariants, {links_created} links",
        category="agent.invariants.extract.done",
        params={
            "session_id": session_id,
            "invariants_created": invariants_created,
            "verified_by_links": links_created,
        },
    )

    yield ProgressEvent(
        phase=IngestionPhase.EXTRACTING_INVARIANTS,
        message=f"✅ 인베리언트 추출 완료 ({invariants_created}개)",
        progress=PHASE_END,
        data={"invariants_created": invariants_created, "verified_by_links": links_created},
    )
