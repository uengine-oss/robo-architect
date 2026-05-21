"""Hybrid Phase 5 post-workflow hook — augment-only.

Run after the standard workflow's hybrid branch finishes (legacy ES phases
already produced UserStory / BoundedContext / Aggregate / Command / Event /
ReadModel / Policy / GWT / UI nodes via their `ctx.source_type == "hybrid"`
sub-paths). This module **does not re-create or wipe** any of those — its
sole responsibilities are:

  1. Tag every ES node from this run with `session_id = hsid` so re-runs and
     `clear_promoted_nodes(hsid)` can selectively remove them.
  2. Attach `(BpmTask)-[:PROMOTED_TO]->(UserStory)` bridges so the BPM canvas
     and the ES canvas share a navigable lineage edge.
  3. Backfill `(UserStory)-[:IMPLEMENTS]->(BoundedContext)` for stories the
     LLM forgot to assign — the navigator's BC tree relies on this.
  4. Attach analyzer-side traceability edges that the legacy phases never
     produced — `(UserStory)-[:SOURCED_FROM]->(Rule)` and
     `(Question)-[:ATTACHED_TO]->(BoundedContext)`. These are the ones that
     let downstream PRD generation (Phase 6) pull Rule.statement / Example
     GWT / source_function into the markdown.
  5. Detect cross-BC Policy candidates from `BpmTask.NEXT` pairs that span
     different BCs and persist them with an LLM-assigned name.

Earlier revisions of this file *replaced* the legacy phase output with a
fresh deterministic pipeline; that approach silently destroyed the rich
properties / inputSchema / valueObjects / GWT / UI that the legacy hybrid
branch had already built, and introduced a critical wipe bug that erased
analyzer FUNCTION nodes carrying multi-labels (`[FUNCTION, Command]`). The
augment-only model below avoids both problems.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.features.ingestion.hybrid.bpm_context_builder import (
    fetch_task_metadata_for_bpm,
)
from api.features.ingestion.hybrid.contracts import HybridPhase
from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger


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


# Public — preserved for router.py + /reset endpoint backwards compatibility.
# Includes labels both Phase 5 (this file) and the legacy ES phases may persist.
ALL_PROMOTED_LABELS = (
    "UserStory", "BoundedContext", "Aggregate", "Command", "Event",
    "Policy", "ReadModel", "CQRSConfig", "CQRSOperation",
    # GWT comes from the legacy phase; UI from the same. Both belong to the
    # session's ES output and should be wiped together when a user explicitly
    # resets via /reset (see router.py).
    "UI", "GWT",
)

# Labels wiped on re-ingestion but NOT auto-tagged by
# `_tag_es_nodes_with_session_id`. Feature (spec 026) and Invariant (spec 027)
# set their own `session_id` at creation time only for the ingestion path —
# manually-created Features/Invariants have no `session_id` and must survive
# re-ingestion, so the blanket tag pass must never touch them.
_CLEAR_ONLY_LABELS = ("Feature", "Invariant")
ALL_CLEARED_LABELS = ALL_PROMOTED_LABELS + _CLEAR_ONLY_LABELS


def _ev(message: str, progress: int, data: dict | None = None) -> ProgressEvent:
    payload = dict(data or {})
    payload["hybrid_phase"] = HybridPhase.EVENT_STORMING.value
    return ProgressEvent(
        phase=IngestionPhase.PARSING,
        message=message, progress=progress, data=payload,
    )


# =============================================================================
# 1) session_id tagging — wraps ES nodes from this hybrid promotion run
# =============================================================================


def _tag_es_nodes_with_session_id(hybrid_session_id: str) -> dict[str, int]:
    """Tag any ES node that lacks a session_id with the current hybrid session id.

    CRITICAL — single-label only. The analyzer applies stereotype labels
    (Command / Query / Validation / Handler) directly on its FUNCTION nodes
    as multi-labels: a function classified as a Command carries
    `[FUNCTION, Command]`. Without the `size(labels(n)) = 1` guard, this tag
    pass would mark those analyzer FUNCTIONs with our session_id, and a later
    /reset wipe would delete them — destroying HAS_RULE / AFFECTS_TABLE chains.
    """
    counts: dict[str, int] = {}
    with get_session() as s:
        for label in ALL_PROMOTED_LABELS:
            r = s.run(
                f"MATCH (n:{label}) "
                "WHERE n.session_id IS NULL AND size(labels(n)) = 1 "
                "SET n.session_id = $sid RETURN count(n) AS c",
                sid=hybrid_session_id,
            ).single()
            if r and r["c"]:
                counts[label] = int(r["c"])
    return counts


def clear_promoted_nodes(hybrid_session_id: str) -> dict[str, int]:
    """Wipe ES nodes tagged with the given hybrid session_id. Untagged ES nodes
    (legacy ingestion, and manually-created Features/Invariants) are preserved.
    Used by /reset and the test harness."""
    counts: dict[str, int] = {}
    with get_session() as s:
        for label in ALL_CLEARED_LABELS:
            r = s.run(
                f"MATCH (n:{label} {{session_id: $sid}}) "
                "WHERE size(labels(n)) = 1 "
                "WITH n, count(n) AS c DETACH DELETE n RETURN c",
                sid=hybrid_session_id,
            ).single()
            if r and r["c"]:
                counts[label] = int(r["c"])
    return counts


# =============================================================================
# 2) BpmTask → UserStory PROMOTED_TO bridges (via sourceUnitId)
# =============================================================================


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


def _attach_orphan_us_to_first_bc(hybrid_session_id: str) -> int:
    """Safety net: if a UserStory has no IMPLEMENTS edge to any BoundedContext,
    attach it to the first BC (alphabetic by key)."""
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


# =============================================================================
# 3) Analyzer-side traceability edges — the new value this module adds on top
#    of the legacy phases. Without these, downstream PRD generation has no
#    way to surface Rule.statement / Example GWT / source_function as code
#    grounding for each ES node.
# =============================================================================


def _attach_analyzer_traceability(hybrid_session_id: str) -> dict[str, int]:
    """Attach analyzer→ES edges. Two main edges:

      (UserStory)-[:SOURCED_FROM]->(Rule)
        For each BpmTask realized by shadow Rules, fan out the same
        SOURCED_FROM relation to every UserStory that points back at the
        task via sourceUnitId. Lets PRD generation pull every rule
        statement that contributed to a story.

      (Question)-[:ATTACHED_TO]->(BoundedContext)
        Analyzer Questions live on FUNCTION nodes. We follow the function
        to its REALIZED_BY task → IMPLEMENTS BC chain so the question
        surfaces in the right BC's "Open Decisions" section. When a
        question's host fn maps to no task (rare), it attaches to the
        first BC by key as a fallback so it isn't lost.
    """
    counts = {"sourced_from": 0, "attached_to": 0}
    with get_session() as s:
        # (US)-[:SOURCED_FROM]->(Rule) via shadow Rule reached through BpmTask.
        # Shadow Rule has session_id (created during BPM phase); we follow that
        # so PRD generation can retrieve title/given/when/then directly.
        rec = s.run(
            "MATCH (t:BpmTask {session_id: $sid})-[:REALIZED_BY]->(r:Rule {session_id: $sid}) "
            "MATCH (us:UserStory {session_id: $sid}) "
            "WHERE us.sourceUnitId = t.id "
            "MERGE (us)-[rel:SOURCED_FROM]->(r) "
            "RETURN count(rel) AS c",
            sid=hybrid_session_id,
        ).single()
        counts["sourced_from"] = int(rec["c"]) if rec else 0

        # (Question)-[:ATTACHED_TO]->(BC) via FUNCTION → task → IMPLEMENTS BC.
        # We touch any analyzer Question (no session_id); this is a one-way
        # link from immutable analyzer data into the hybrid session.
        rec = s.run(
            "MATCH (q:Question) WHERE q.session_id IS NULL "
            "OPTIONAL MATCH (f:FUNCTION)-[:HAS_QUESTION]->(q) "
            "OPTIONAL MATCH (t:BpmTask {session_id: $sid})-[:REALIZED_BY]->"
            "          (sh:Rule {session_id: $sid}) "
            "          WHERE sh.source_function = coalesce(f.procedure_name, f.name) "
            "OPTIONAL MATCH (us:UserStory {session_id: $sid}) "
            "          WHERE us.sourceUnitId = t.id "
            "OPTIONAL MATCH (us)-[:IMPLEMENTS]->(bc:BoundedContext {session_id: $sid}) "
            "WITH q, collect(DISTINCT bc) AS bcs "
            "WHERE size(bcs) > 0 "
            "UNWIND bcs AS bc "
            "MERGE (q)-[rel:ATTACHED_TO]->(bc) "
            "RETURN count(rel) AS c",
            sid=hybrid_session_id,
        ).single()
        counts["attached_to"] = int(rec["c"]) if rec else 0

        # Fallback: any Question still unattached → first BC of the session.
        # IMPORTANT: `LIMIT 1` must apply to BC selection only, not to the
        # question stream. Otherwise only one orphan question gets attached.
        rec = s.run(
            "MATCH (q:Question) WHERE q.session_id IS NULL "
            "  AND NOT (q)-[:ATTACHED_TO]->(:BoundedContext {session_id: $sid}) "
            "MATCH (bc:BoundedContext {session_id: $sid}) "
            "WITH bc ORDER BY bc.key LIMIT 1 "
            "MATCH (q:Question) WHERE q.session_id IS NULL "
            "  AND NOT (q)-[:ATTACHED_TO]->(:BoundedContext {session_id: $sid}) "
            "MERGE (q)-[rel:ATTACHED_TO]->(bc) "
            "RETURN count(rel) AS c",
            sid=hybrid_session_id,
        ).single()
        counts["attached_to"] += int(rec["c"]) if rec else 0
    return counts


# =============================================================================
# 4) Cross-BC Policy detection (BpmTask.NEXT pairs spanning BCs)
# =============================================================================


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
            bca = bc_of_task[tid]
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


# =============================================================================
# Public hook called by ingestion_workflow_runner
# =============================================================================


async def hybrid_post_workflow_hook(
    hybrid_session_id: str,
) -> AsyncGenerator[ProgressEvent, None]:
    """Augment the legacy hybrid ES output with session tagging, BPM bridges,
    analyzer traceability, and cross-BC policies. Idempotent."""
    yield _ev("🏷  ES 노드에 hybrid session_id 태깅 중...", 95,
              {"type": "HybridTaggingStart"})
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

    yield _ev("🧬 분석기 traceability 엣지 부착 중 (US→Rule, Question→BC)...", 98,
              {"type": "HybridTraceabilityStart"})
    trace_counts = _attach_analyzer_traceability(hybrid_session_id)
    yield _ev(
        f"🧬 traceability 부착: SOURCED_FROM {trace_counts['sourced_from']} / "
        f"ATTACHED_TO {trace_counts['attached_to']}",
        98,
        {"type": "HybridTraceabilityAttached", "counts": trace_counts},
    )

    yield _ev("🔁 Cross-BC Policy 탐지 중 (BpmTask.NEXT 흐름 기반)...", 99)
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
            "orphan_us_backfilled": orphans,
            "traceability": trace_counts,
            "cross_bc_policies": len(cross_policies),
        },
    )
