from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.observability.smart_logger import SmartLogger


def _parse_fk_hint(hint: str) -> tuple[str, str, str] | None:
    """
    Parse `<TargetType>:<TargetKey>:<TargetPropertyName>`.
    """
    if not isinstance(hint, str):
        return None
    h = hint.strip()
    if not h:
        return None
    parts = [p.strip() for p in h.split(":")]
    if len(parts) != 3:
        return None
    tgt_type, tgt_key, tgt_prop = parts
    if tgt_type not in ("Aggregate", "Command", "Event", "ReadModel"):
        return None
    if not tgt_key or not tgt_prop:
        return None
    return tgt_type, tgt_key, tgt_prop


async def generate_property_references_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 2: Create (src:Property)-[:REFERENCES]->(tgt:Property) based on fkTargetHint.

    Policy:
    - Only consider src properties with isForeignKey=true and fkTargetHint present.
    - Only create REFERENCES when target property has isKey=true.
    - Ambiguity/failures are skipped and logged (no candidate persistence in Phase 2).
    """
    yield ProgressEvent(
        phase=IngestionPhase.GENERATING_REFERENCES,
        message="REFERENCES 생성 중...",
        progress=89,
    )

    sources = ctx.client.fetch_fk_hint_sources()
    scanned = len(sources)
    parsed_items: list[dict[str, Any]] = []
    skipped_parse = 0
    for s in sources:
        sid = str(s.get("id") or "").strip()
        hint = str(s.get("fkTargetHint") or "").strip()
        parsed = _parse_fk_hint(hint)
        if not sid or not parsed:
            skipped_parse += 1
            continue
        tgt_type, tgt_key, tgt_prop = parsed
        parsed_items.append({"srcId": sid, "tgtType": tgt_type, "tgtKey": tgt_key, "tgtProp": tgt_prop})

    SmartLogger.log(
        "INFO",
        "REFERENCES phase: parsed fkTargetHint sources",
        category="ingestion.workflow.references.parse",
        params={
            "session_id": ctx.session.id,
            "scanned": scanned,
            "parsed": len(parsed_items),
            "skipped_parse": skipped_parse,
        },
    )

    if not parsed_items:
        yield ProgressEvent(
            phase=IngestionPhase.GENERATING_REFERENCES,
            message="REFERENCES 생성할 대상이 없습니다.",
            progress=90,
            data={"scanned": scanned, "parsed": 0, "created": 0, "skipped_parse": skipped_parse},
        )
        return

    result = ctx.client.create_references_from_hints(parsed_items)

    SmartLogger.log(
        "INFO",
        "REFERENCES created from fkTargetHint",
        category="ingestion.neo4j.references.create",
        params={"session_id": ctx.session.id, "result": result, "skipped_parse": skipped_parse},
    )

    yield ProgressEvent(
        phase=IngestionPhase.GENERATING_REFERENCES,
        message="REFERENCES 생성 완료",
        progress=90,
        data={
            **(result or {}),
            "scanned_candidates": scanned,
            "parsed": len(parsed_items),
            "skipped_parse": skipped_parse,
        },
    )
    await asyncio.sleep(0.05)


