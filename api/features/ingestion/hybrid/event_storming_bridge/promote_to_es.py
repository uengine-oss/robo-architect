"""Hybrid Phase 5 post-workflow hook.

The bulk of Phase 5 (UserStory→Event→BC→Aggregate→Command→ReadModel→Policy)
is now executed by the existing ingestion workflow once `source_type=='hybrid'`.

This module owns the small set of BPM-specific finishing touches that the
generic workflow does NOT cover:

  1. Tag every ES node produced during this run with `session_id = hsid`
     (so re-runs are idempotent and `clear_promoted_nodes(hsid)` can wipe them).
  2. Attach `(BpmTask)-[:PROMOTED_TO]->(UserStory)` bridges via UserStory.source_unit_id.
  3. Detect Cross-BC Policy candidates from BpmTask.NEXT pairs that span different
     BoundedContexts → name via LLM → persist using the existing event_storming
     `create_policy` ops.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.hybrid.bpm_context_builder import (
    fetch_task_metadata_for_bpm,
)
from api.features.ingestion.hybrid.contracts import HybridPhase
from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from pydantic import BaseModel, Field


_CROSS_BC_POLICY_SYSTEM = """당신은 BoundedContext 간 자동화(Cross-BC Policy) 명명 전문가입니다.

BPM 흐름에서 인접한 두 Task 가 서로 다른 BC 에 속하면,
"BC1 의 Event → Policy → BC2 의 Command" 자동 트리거 패턴이 됩니다.

규칙:
- name 은 영문 PascalCase: On{Event}Trigger{Command} 형태.
- description 은 한국어 1줄로 두 BC 간 자동화 의미 설명.
"""


class _CrossBcPolicyOut(BaseModel):
    name: str = Field(description="On{Event}Trigger{Command} 형식")
    description: str = Field(default="")


def _ev(message: str, progress: int, data: dict | None = None) -> ProgressEvent:
    payload = dict(data or {})
    payload["hybrid_phase"] = HybridPhase.EVENT_STORMING.value
    return ProgressEvent(
        phase=IngestionPhase.PARSING,
        message=message, progress=progress, data=payload,
    )


# ---------------------------------------------------------------------------
# 1) Session_id tagging — wraps ES nodes from this hybrid promotion run
# ---------------------------------------------------------------------------

_TAGGABLE_LABELS = [
    "UserStory", "BoundedContext", "Aggregate", "Command", "Event",
    "Policy", "ReadModel", "CQRSConfig", "CQRSOperation",
]

# Public alias used by the hybrid router for /reset and /promote-to-es DELETE.
ALL_PROMOTED_LABELS = _TAGGABLE_LABELS


def clear_promoted_nodes(hybrid_session_id: str) -> dict[str, int]:
    """Wipe ES nodes tagged with the given hybrid session_id.
    Untagged ES nodes (legacy ingestion) are preserved."""
    counts: dict[str, int] = {}
    with get_session() as s:
        for label in ALL_PROMOTED_LABELS:
            r = s.run(
                f"MATCH (n:{label} {{session_id: $sid}}) "
                "WITH n, count(n) AS c DETACH DELETE n RETURN c",
                sid=hybrid_session_id,
            ).single()
            if r and r["c"]:
                counts[label] = int(r["c"])
    return counts


def _tag_es_nodes_with_session_id(hybrid_session_id: str) -> dict[str, int]:
    """Tag any ES node that lacks a session_id with the current hybrid session id.
    Assumes serial single-user hybrid promotion (no concurrent runs)."""
    counts: dict[str, int] = {}
    with get_session() as s:
        for label in _TAGGABLE_LABELS:
            r = s.run(
                f"MATCH (n:{label}) WHERE n.session_id IS NULL "
                "SET n.session_id = $sid RETURN count(n) AS c",
                sid=hybrid_session_id,
            ).single()
            if r and r["c"]:
                counts[label] = int(r["c"])
    return counts


# ---------------------------------------------------------------------------
# 2) BpmTask → UserStory PROMOTED_TO bridges (via source_unit_id)
# ---------------------------------------------------------------------------


def _attach_orphan_us_to_first_bc(hybrid_session_id: str) -> int:
    """Safety net: if a UserStory has no IMPLEMENTS edge to any BoundedContext,
    attach it to the first BC (alphabetic by key). Edge direction is
    (UserStory)-[:IMPLEMENTS]->(BoundedContext) per existing event_storming
    convention (see neo4j_ops/bounded_contexts.py)."""
    with get_session() as s:
        first_bc = s.run(
            "MATCH (b:BoundedContext {session_id: $sid}) RETURN b.id AS id, b.key AS key "
            "ORDER BY b.key LIMIT 1",
            sid=hybrid_session_id,
        ).single()
        if not first_bc or not first_bc.get("id"):
            return 0
        r = s.run(
            "MATCH (us:UserStory {session_id: $sid}) "
            "WHERE NOT (us)-[:IMPLEMENTS]->(:BoundedContext) "
            "WITH us "
            "MATCH (b:BoundedContext {session_id: $sid, id: $bid}) "
            "MERGE (us)-[rel:IMPLEMENTS]->(b) RETURN count(rel) AS c",
            sid=hybrid_session_id, bid=first_bc["id"],
        ).single()
        return int(r["c"]) if r else 0


def _attach_promoted_to_bridges(hybrid_session_id: str) -> int:
    """For each UserStory whose sourceUnitId is a BpmTask.id of this session,
    attach (BpmTask)-[:PROMOTED_TO]->(UserStory). Property name is camelCase
    (`sourceUnitId`) on Neo4j — see event_storming/neo4j_ops/user_stories.py."""
    with get_session() as s:
        r = s.run(
            "MATCH (us:UserStory {session_id: $sid}) "
            "WHERE us.sourceUnitId IS NOT NULL AND us.sourceUnitId <> '' "
            "MATCH (t:BpmTask {id: us.sourceUnitId, session_id: $sid}) "
            "MERGE (t)-[rel:PROMOTED_TO]->(us) SET rel.method = 'auto' "
            "RETURN count(rel) AS c",
            sid=hybrid_session_id,
        ).single()
        return int(r["c"]) if r else 0


# ---------------------------------------------------------------------------
# 3) Cross-BC Policy detection
# ---------------------------------------------------------------------------


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", (s or "")).strip("_").lower() or "pol"


def _fetch_bc_for_each_task(hybrid_session_id: str) -> dict[str, tuple[str, str]]:
    """task_id → (bc_key, bc_name) via BpmTask.id == UserStory.sourceUnitId →IMPLEMENTS→ BC."""
    out: dict[str, tuple[str, str]] = {}
    with get_session() as s:
        for r in s.run(
            "MATCH (t:BpmTask {session_id: $sid}) "
            "MATCH (us:UserStory {session_id: $sid}) WHERE us.sourceUnitId = t.id "
            "MATCH (us)-[:IMPLEMENTS]->(bc:BoundedContext {session_id: $sid}) "
            "RETURN t.id AS tid, bc.key AS bck, bc.name AS bcn",
            sid=hybrid_session_id,
        ):
            # Last write wins — a task may map to multiple BCs if its US span; we
            # take the last seen, which is fine for cross-BC pair detection.
            out[r["tid"]] = (r["bck"], r["bcn"])
    return out


def _fetch_last_event_for_task(hybrid_session_id: str) -> dict[str, dict]:
    """task_id → {event_key, event_name} of the highest-sequence Event tied to this task's
    UserStories. Picks the last in time-order."""
    out: dict[str, dict] = {}
    with get_session() as s:
        for r in s.run(
            "MATCH (us:UserStory {session_id: $sid})-[:HAS_EVENT]->(e:Event {session_id: $sid}) "
            "WHERE us.sourceUnitId IS NOT NULL "
            "RETURN us.sourceUnitId AS tid, e.key AS ek, e.name AS en, e.sequence AS sq "
            "ORDER BY e.sequence",
            sid=hybrid_session_id,
        ):
            tid = r["tid"]
            if tid:
                # Last write wins → highest sequence
                out[tid] = {"key": r["ek"], "name": r["en"]}
    return out


def _fetch_first_command_for_task(hybrid_session_id: str) -> dict[str, dict]:
    """task_id → {command_key, command_name, aggregate_key} via task→US→Event←EMITS←Command."""
    out: dict[str, dict] = {}
    with get_session() as s:
        for r in s.run(
            "MATCH (us:UserStory {session_id: $sid})-[:HAS_EVENT]->(e:Event {session_id: $sid}) "
            "MATCH (c:Command {session_id: $sid})-[:EMITS]->(e) "
            "WHERE us.sourceUnitId IS NOT NULL "
            "RETURN us.sourceUnitId AS tid, c.key AS ck, c.name AS cn, c.aggregate_id AS aid",
            sid=hybrid_session_id,
        ):
            tid = r["tid"]
            if tid and tid not in out:
                # First write wins — first command this task issues.
                out[tid] = {"key": r["ck"], "name": r["cn"], "aggregate_key": r["aid"]}
    return out


async def _name_cross_bc_policy(
    bc_a_name: str, bc_b_name: str, event_name: str, command_name: str,
) -> tuple[str, str]:
    """Ask the LLM for a meaningful policy name. Falls back deterministically."""
    user_msg = (
        f"### Cross-BC pair\n"
        f"- BC1 (source): {bc_a_name}\n"
        f"- BC2 (target): {bc_b_name}\n"
        f"- trigger_event: {event_name}\n"
        f"- invoke_command: {command_name}\n\n"
        "위 두 BC 간 자동화를 의미하는 Policy 이름과 한국어 설명을 만드세요."
    )
    try:
        llm = get_llm()
        structured = llm.with_structured_output(_CrossBcPolicyOut)
        result: _CrossBcPolicyOut = await structured.ainvoke([
            SystemMessage(content=_CROSS_BC_POLICY_SYSTEM),
            HumanMessage(content=user_msg),
        ])
        if result and result.name:
            return result.name, result.description or ""
    except Exception as e:
        SmartLogger.log(
            "WARN", f"Cross-BC policy LLM failed for {bc_a_name}->{bc_b_name}",
            category="ingestion.hybrid.es.cross_bc",
            params={"error": str(e)},
        )
    fallback_name = f"On{event_name}Trigger{command_name}"
    fallback_desc = f"{bc_a_name} 의 {event_name} 발생 시 {bc_b_name} 의 {command_name} 자동 호출"
    return fallback_name, fallback_desc


async def _create_cross_bc_policies(hybrid_session_id: str) -> list[dict]:
    """Walk BpmTask NEXT pairs, find cross-BC ones, build policies."""
    task_meta = fetch_task_metadata_for_bpm(hybrid_session_id)
    bc_of_task = _fetch_bc_for_each_task(hybrid_session_id)
    last_event = _fetch_last_event_for_task(hybrid_session_id)
    first_cmd = _fetch_first_command_for_task(hybrid_session_id)

    pairs: list[tuple[str, str]] = []
    for tid, meta in task_meta.items():
        for nxt in meta["next_ids"]:
            bca = bc_of_task.get(tid)
            bcb = bc_of_task.get(nxt)
            if bca and bcb and bca[0] != bcb[0]:
                pairs.append((tid, nxt))

    created: list[dict] = []
    if not pairs:
        return created

    seen_keys: set[str] = set()
    with get_session() as s:
        for tid, ntid in pairs:
            ev = last_event.get(tid)
            cm = first_cmd.get(ntid)
            if not ev or not cm:
                continue
            bca = bc_of_task[tid]   # (key, name)
            bcb = bc_of_task[ntid]
            name, desc = await _name_cross_bc_policy(bca[1], bcb[1], ev["name"], cm["name"])
            base_key = f"pol_{_slug(name)}"
            key = base_key
            n = 2
            while key in seen_keys:
                key = f"{base_key}_{n}"
                n += 1
            seen_keys.add(key)

            s.run(
                "MERGE (p:Policy {key: $key, session_id: $sid}) "
                "SET p.name = $name, p.displayName = $name, p.description = $desc, "
                "    p.kind = 'cross_bc', p.bc_id = $bcid",
                key=key, sid=hybrid_session_id, name=name, desc=desc, bcid=bca[0],
            )
            s.run(
                "MATCH (e:Event {key: $ek, session_id: $sid}), (p:Policy {key: $pk, session_id: $sid}) "
                "MERGE (e)-[:TRIGGERS]->(p)",
                ek=ev["key"], pk=key, sid=hybrid_session_id,
            )
            s.run(
                "MATCH (p:Policy {key: $pk, session_id: $sid}), (c:Command {key: $ck, session_id: $sid}) "
                "MERGE (p)-[:INVOKES]->(c)",
                pk=key, ck=cm["key"], sid=hybrid_session_id,
            )
            created.append({
                "key": key, "name": name, "kind": "cross_bc",
                "trigger_event": ev["name"], "invoke_command": cm["name"],
                "from_bc": bca[1], "to_bc": bcb[1],
            })
    return created


# ---------------------------------------------------------------------------
# Public hook called by the ingestion workflow runner at the end
# ---------------------------------------------------------------------------


async def hybrid_post_workflow_hook(
    hybrid_session_id: str,
) -> AsyncGenerator[ProgressEvent, None]:
    """Run after the standard workflow finishes for source_type=='hybrid'.
    Idempotent: re-running tags & merges, no duplicates."""
    yield _ev("🏷  ES 노드에 hybrid session_id 태깅 중...", 95, {"type": "HybridTaggingStart"})
    tag_counts = _tag_es_nodes_with_session_id(hybrid_session_id)
    yield _ev(
        f"🏷  태깅 완료: {sum(tag_counts.values())} nodes ({len(tag_counts)} 라벨)", 96,
        {"type": "HybridTagged", "tagged": tag_counts},
    )

    bridges = _attach_promoted_to_bridges(hybrid_session_id)
    yield _ev(
        f"🔗 BpmTask → UserStory PROMOTED_TO 부착: {bridges} edges", 97,
        {"type": "HybridPromotedBridges", "edge_count": bridges},
    )

    orphans = _attach_orphan_us_to_first_bc(hybrid_session_id)
    if orphans:
        yield _ev(
            f"🩹 Orphan UserStory {orphans}개 → 첫 BC 강제 부착 (BC LLM 매핑 누락 보정)",
            97,
            {"type": "HybridOrphanUsBackfilled", "edge_count": orphans},
        )

    yield _ev("🔁 Cross-BC Policy 탐지 중 (BpmTask.NEXT 흐름 기반)...", 98)
    cross_policies = await _create_cross_bc_policies(hybrid_session_id)
    yield _ev(
        f"🔁 Cross-BC Policy {len(cross_policies)}개 생성", 99,
        {"type": "HybridCrossBcPolicies", "policies": cross_policies},
    )

    SmartLogger.log(
        "INFO", "Hybrid post-workflow hook complete",
        category="ingestion.hybrid.es.post_hook",
        params={
            "hybrid_session_id": hybrid_session_id,
            "tagged": tag_counts,
            "promoted_bridges": bridges,
            "cross_bc_policies": len(cross_policies),
        },
    )
