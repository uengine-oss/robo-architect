"""
Ingestion phase: UI Flow Edges (spec 025).

Runs after `ui_wireframes`. Reads:
  - the source document text already in `ctx.content`
  - the UI catalog (id + displayName + bc_name + bc_key + bc_id) from Neo4j

Asks the LLM to extract user-journey transitions (NEXT_UI edges) and
branching decision points (Gateway nodes), then persists them to Neo4j
idempotently via `UIFlowOps`. Honors `source='manual'` rows by skipping
any LLM proposal that collides with a pinned manual row (research D4).
"""

from __future__ import annotations

import json
import time
from collections import Counter
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage
from api.platform.llm_messages import build_system_message

from api.features.ingestion.event_storming.prompts import UI_FLOW_SYSTEM_PROMPT
from api.features.ingestion.event_storming.structured_outputs import (
    UIFlowDerivation,
    UIFlowEdgeItem,
    UIFlowGatewayItem,
)
from api.features.ingestion.figma_to_user_stories import _fuzzy_match_screen_name
from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.workflow.ingestion_workflow_context import (
    IngestionWorkflowContext,
)
from api.platform.env import get_llm_provider_model
from api.platform.keys import (
    journey_key,
    journey_node_id,
    journey_slug,
    journey_step_id,
    journey_step_key,
    next_step_id,
)
from api.platform.observability.smart_logger import SmartLogger


def _build_ui_catalog(ctx: IngestionWorkflowContext) -> list[dict[str, Any]]:
    """Fetch the UI catalog the LLM needs to bind transitions against.

    Returns rows: {id, displayName, bc_id, bc_name, bc_key}.
    Reads Neo4j directly so we don't depend on ctx fields drifting across
    phase implementations.
    """
    with ctx.client.session() as session:
        cur = session.run(
            """
            MATCH (bc:BoundedContext)-[:HAS_UI]->(ui:UI)
            RETURN ui.id AS id,
                   coalesce(ui.displayName, ui.name) AS displayName,
                   bc.id AS bc_id,
                   bc.name AS bc_name,
                   bc.key AS bc_key
            ORDER BY bc.name, ui.displayName
            """
        )
        return [dict(rec) for rec in cur]


def _build_bc_catalog(ctx: IngestionWorkflowContext) -> dict[str, dict[str, str]]:
    """Map BC name → {id, key} for resolving gateway BC references."""
    with ctx.client.session() as session:
        cur = session.run(
            "MATCH (bc:BoundedContext) RETURN bc.id AS id, bc.key AS key, bc.name AS name"
        )
        out: dict[str, dict[str, str]] = {}
        for rec in cur:
            name = rec.get("name") or ""
            if name:
                out[name.strip().lower()] = {
                    "id": rec["id"],
                    "key": rec["key"],
                    "name": name,
                }
        return out


def _strip_json_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```json"):
        t = t[len("```json"):].strip()
        if t.endswith("```"):
            t = t[:-3].strip()
        return t
    if t.startswith("```"):
        t = t[3:].strip()
        if t.endswith("```"):
            t = t[:-3].strip()
        return t
    return t


def _resolve_ui(name: str, catalog: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Case-insensitive trimmed match, fuzzy fallback."""
    if not name:
        return None
    key = name.strip().lower()
    for ui in catalog:
        if (ui.get("displayName") or "").strip().lower() == key:
            return ui
    # Fuzzy fallback
    name_set = {(ui.get("displayName") or "") for ui in catalog if ui.get("displayName")}
    matched = _fuzzy_match_screen_name(name, name_set)
    if matched:
        for ui in catalog:
            if (ui.get("displayName") or "") == matched:
                return ui
    return None


async def generate_ui_flow_edges_phase(
    ctx: IngestionWorkflowContext,
) -> AsyncGenerator[ProgressEvent, None]:
    """Spec 025 — derive UI-to-UI flow edges + Gateways from the source document."""

    session_id = ctx.session.id
    warnings: list[dict[str, Any]] = []
    next_ui_edges_created = 0
    gateways_created = 0
    next_ui_edges_skipped_manual = 0
    next_ui_edges_deleted = 0

    yield ProgressEvent(
        phase=IngestionPhase.GENERATING_UI_FLOW,
        message="🧭 UI 흐름 추론 중...",
        progress=93,
        data={"status": "starting"},
    )

    ui_catalog = _build_ui_catalog(ctx)
    bc_catalog = _build_bc_catalog(ctx)

    SmartLogger.log(
        "INFO",
        "UI flow phase: catalog built",
        category="agent.nodes.ui_flow.catalog",
        params={"session_id": session_id, "ui_count": len(ui_catalog), "bc_count": len(bc_catalog)},
    )

    # ── Empty-catalog short circuit ─────────────────────────────────────
    if not ui_catalog:
        warnings.append({"code": "ui_flow_unclear", "message": "No UI nodes available — skipping UI-flow derivation"})
        _finalize_summary(
            ctx,
            next_ui_edges_created=0,
            gateways_created=0,
            next_ui_edges_skipped_manual=0,
            next_ui_edges_deleted=0,
            warnings=warnings,
        )
        yield ProgressEvent(
            phase=IngestionPhase.GENERATING_UI_FLOW,
            message="UI 흐름 추론 생략 (UI 노드 없음)",
            progress=96,
            data={
                "next_ui_edges_created": 0,
                "gateways_created": 0,
                "next_ui_edges_skipped_manual": 0,
                "warnings": warnings,
            },
        )
        return

    # ── Build the prompt with the UI catalog ────────────────────────────
    catalog_lines = [
        f"- id={ui['id']} | displayName={ui['displayName']} | bc={ui['bc_name']}"
        for ui in ui_catalog
    ]
    bc_lines = [f"- {bc['name']}" for bc in bc_catalog.values()]
    prompt = f"""Source document (verbatim):
---
{ctx.content or ''}
---

UI catalog (use these as the ONLY valid source/target values for ui-kind edges):
{chr(10).join(catalog_lines)}

Bounded Contexts (use these names for gateway `bounded_context_name`):
{chr(10).join(bc_lines)}

Return the JSON object now."""

    provider, model = get_llm_provider_model()
    t0 = time.perf_counter()
    try:
        # MUST be async (ainvoke): this runs inside an async-generator SSE phase,
        # so a *sync* .invoke() does a blocking httpx read to OpenAI on the event
        # loop — a stalled stream then freezes the entire server (every request,
        # incl. the Figma plugin, times out). ainvoke uses AsyncOpenAI so a slow
        # call only suspends this coroutine, not the loop.
        response = await ctx.llm.ainvoke(
            [build_system_message(UI_FLOW_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        llm_ms = int((time.perf_counter() - t0) * 1000)
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "UI flow phase: LLM call failed",
            category="agent.nodes.ui_flow.llm.error",
            params={"session_id": session_id, "error": str(e)},
        )
        warnings.append({"code": "ui_flow_unclear", "message": f"LLM call failed: {e}"})
        _finalize_summary(
            ctx,
            next_ui_edges_created=0,
            gateways_created=0,
            next_ui_edges_skipped_manual=0,
            next_ui_edges_deleted=0,
            warnings=warnings,
        )
        yield ProgressEvent(
            phase=IngestionPhase.GENERATING_UI_FLOW,
            message="UI 흐름 추론 실패 — 0건 생성 (다른 단계는 계속 진행)",
            progress=96,
            data={
                "next_ui_edges_created": 0,
                "gateways_created": 0,
                "next_ui_edges_skipped_manual": 0,
                "warnings": warnings,
            },
        )
        return

    raw = response.content if hasattr(response, "content") else str(response)
    cleaned = _strip_json_fences(raw)

    try:
        payload = json.loads(cleaned) if cleaned else {}
        derivation = UIFlowDerivation(**payload)
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            "UI flow phase: parse failed",
            category="agent.nodes.ui_flow.parse.error",
            params={"session_id": session_id, "error": str(e), "raw_head": raw[:300]},
        )
        warnings.append({"code": "ui_flow_unclear", "message": f"LLM output unparsable: {e}"})
        derivation = UIFlowDerivation()

    SmartLogger.log(
        "INFO",
        "UI flow phase: LLM parsed",
        category="agent.nodes.ui_flow.llm.ok",
        params={
            "session_id": session_id,
            "provider": provider,
            "model": model,
            "llm_ms": llm_ms,
            "journeys_proposed": len(derivation.journeys),
            "unresolved": len(derivation.unresolved),
        },
    )

    # ── Empty derivation ────────────────────────────────────────────────
    if not derivation.journeys:
        warnings.append(
            {"code": "ui_flow_unclear", "message": "No user journeys detected in the source document"}
        )
        _finalize_summary(
            ctx,
            next_ui_edges_created=0,
            gateways_created=0,
            next_ui_edges_skipped_manual=0,
            next_ui_edges_deleted=0,
            warnings=warnings,
        )
        yield ProgressEvent(
            phase=IngestionPhase.GENERATING_UI_FLOW,
            message="UI 흐름 감지 안됨",
            progress=96,
            data={
                "next_ui_edges_created": 0,
                "gateways_created": 0,
                "next_ui_edges_skipped_manual": 0,
                "journeys_created": 0,
                "warnings": warnings,
            },
        )
        return

    # ── Build & persist each journey as a Journey / JourneyStep graph ───
    bc_by_id = {bc["id"]: bc for bc in bc_catalog.values()}
    journey_keep_ids: set[str] = set()
    journeys_created = 0
    gateways_created = 0
    next_ui_edges_created = 0

    for journey in derivation.journeys:
        jname = (journey.name or "").strip()
        if not jname:
            continue

        # Gateway kind downgrade warnings (v1 supports exclusive only).
        for gw in journey.gateways:
            k = (gw.kind or "exclusive").strip().lower()
            if k != "exclusive":
                warnings.append(
                    {
                        "code": "gateway_kind_downgrade",
                        "message": f"Gateway '{gw.label}' kind={k} → downgraded to exclusive",
                        "original_kind": k, "gateway_label": gw.label, "journey": jname,
                    }
                )

        # Resolve every edge endpoint; collect screen UIs + gateway labels.
        resolved: list[tuple[dict, dict, str, str]] = []
        screen_uis: dict[str, dict] = {}        # ui_id → ui catalog dict
        gateway_labels: dict[str, str] = {}     # label_lower → original label
        bc_count: Counter = Counter()
        for edge in journey.edges:
            src = _resolve_journey_endpoint(edge.source_name, edge.source_kind, ui_catalog)
            tgt = _resolve_journey_endpoint(edge.target_name, edge.target_kind, ui_catalog)
            if not src:
                warnings.append({
                    "code": "ui_flow_unresolved_target",
                    "message": f"Source not resolved: {edge.source_name}",
                    "name": edge.source_name, "journey": jname,
                })
                continue
            if not tgt:
                warnings.append({
                    "code": "ui_flow_unresolved_target",
                    "message": f"Target not resolved: {edge.target_name}",
                    "name": edge.target_name, "journey": jname,
                })
                continue
            resolved.append((src, tgt, (edge.condition or "").strip(),
                             (edge.document_excerpt or "")[:500]))
            for ep in (src, tgt):
                if ep["kind"] == "screen":
                    screen_uis[ep["ui"]["id"]] = ep["ui"]
                    if ep["ui"].get("bc_id"):
                        bc_count[ep["ui"]["bc_id"]] += 1
                else:
                    gateway_labels[ep["label"].strip().lower()] = ep["label"]

        if not resolved or not bc_count:
            warnings.append({
                "code": "ui_flow_unclear",
                "message": f"Journey '{jname}' has no resolvable screen flow",
                "journey": jname,
            })
            continue

        # Owner BC = the BC owning the most screens in the journey.
        owner_bc = bc_by_id.get(bc_count.most_common(1)[0][0])
        jkey = journey_key(owner_bc["key"], jname)
        jnode_id = journey_node_id(jkey)
        jslug = journey_slug(jname)

        # Steps: one per distinct screen UI + one per distinct gateway label.
        steps: list[dict] = []
        step_by_ref: dict[tuple[str, str], dict] = {}
        for ui_id, ui in screen_uis.items():
            skey = journey_step_key(jkey, "screen", ui_id)
            st = {
                "id": journey_step_id(skey), "key": skey, "kind": "screen",
                "label": ui.get("displayName") or "", "ui_id": ui_id, "sequence": 0,
            }
            steps.append(st)
            step_by_ref[("screen", ui_id)] = st
        for label_lc, label in gateway_labels.items():
            skey = journey_step_key(jkey, "gateway", label)
            st = {
                "id": journey_step_id(skey), "key": skey, "kind": "gateway",
                "label": label, "ui_id": None, "sequence": 0,
            }
            steps.append(st)
            step_by_ref[("gateway", label_lc)] = st

        def _step_of(ep: dict) -> dict:
            if ep["kind"] == "screen":
                return step_by_ref[("screen", ep["ui"]["id"])]
            return step_by_ref[("gateway", ep["label"].strip().lower())]

        # NEXT edges between steps.
        next_edges: list[dict] = []
        seen_next: set[str] = set()
        for src, tgt, cond, excerpt in resolved:
            s_st, t_st = _step_of(src), _step_of(tgt)
            nid = next_step_id(s_st["key"], t_st["key"], cond)
            if nid in seen_next:
                continue
            seen_next.add(nid)
            next_edges.append({
                "id": nid,
                "source_step_id": s_st["id"], "target_step_id": t_st["id"],
                "condition": cond, "document_excerpt": excerpt, "source": "llm",
            })

        _assign_step_sequence(steps, next_edges)

        # Degenerate gateway check — a gateway step with < 2 outgoing edges.
        out_count: Counter = Counter()
        for e in next_edges:
            out_count[e["source_step_id"]] += 1
        for st in steps:
            if st["kind"] == "gateway" and out_count[st["id"]] < 2:
                warnings.append({
                    "code": "gateway_single_branch",
                    "message": f"Gateway '{st['label']}' has {out_count[st['id']]} outgoing edges",
                    "gateway_id": st["id"], "journey": jname,
                })

        ctx.client.upsert_journey_graph({
            "journey_node_id": jnode_id,
            "journey_key": jkey,
            "journey_slug": jslug,
            "name": jname,
            "description": (journey.description or "").strip(),
            "bounded_context_id": owner_bc["id"],
            "source": "llm",
            "steps": steps,
            "next": next_edges,
        })
        journey_keep_ids.add(jnode_id)
        journeys_created += 1
        gateways_created += len(gateway_labels)
        next_ui_edges_created += len(next_edges)

    # ── Reconcile: delete llm journeys not in the current keep set ──────
    bc_id_list = [bc["id"] for bc in bc_catalog.values()]
    journeys_deleted = ctx.client.delete_llm_journeys_not_in(journey_keep_ids, bc_id_list)
    next_ui_edges_deleted = 0  # journey-level reconcile supersedes edge-level

    _finalize_summary(
        ctx,
        next_ui_edges_created=next_ui_edges_created,
        gateways_created=gateways_created,
        next_ui_edges_skipped_manual=next_ui_edges_skipped_manual,
        next_ui_edges_deleted=next_ui_edges_deleted,
        journeys_created=journeys_created,
        warnings=warnings,
    )

    SmartLogger.log(
        "INFO",
        "UI flow phase: complete",
        category="agent.nodes.ui_flow.complete",
        params={
            "session_id": session_id,
            "journeys_created": journeys_created,
            "next_ui_edges_created": next_ui_edges_created,
            "gateways_created": gateways_created,
            "next_ui_edges_skipped_manual": next_ui_edges_skipped_manual,
            "next_ui_edges_deleted": next_ui_edges_deleted,
            "journeys_deleted": journeys_deleted,
            "warnings": len(warnings),
        },
    )

    yield ProgressEvent(
        phase=IngestionPhase.GENERATING_UI_FLOW,
        message=(
            f"🧭 UI 흐름: {journeys_created}개 여정 / {next_ui_edges_created}개 엣지 / {gateways_created}개 게이트웨이"
            + (f" (수동 보존 {next_ui_edges_skipped_manual}개)" if next_ui_edges_skipped_manual else "")
        ),
        progress=96,
        data={
            "journeys_created": journeys_created,
            "next_ui_edges_created": next_ui_edges_created,
            "gateways_created": gateways_created,
            "next_ui_edges_skipped_manual": next_ui_edges_skipped_manual,
            "warnings": warnings,
        },
    )


def _resolve_journey_endpoint(
    name: str,
    kind: str,
    ui_catalog: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Resolve a journey edge endpoint.

    Returns `{"kind": "screen", "ui": <ui catalog dict>}` for a UI endpoint
    (bound to the catalog), or `{"kind": "gateway", "label": <label>}` for a
    gateway endpoint (gateways are journey-local, created from the label).
    """
    if not name:
        return None
    if (kind or "ui").strip().lower() == "gateway":
        return {"kind": "gateway", "label": name.strip()}
    ui = _resolve_ui(name, ui_catalog)
    if not ui:
        return None
    return {"kind": "screen", "ui": ui}


def _assign_step_sequence(steps: list[dict], next_edges: list[dict]) -> None:
    """Assign a `sequence` layout hint to each step via chain-following
    topological sort over the NEXT graph. Cycles fall back to insertion order.
    Mutates `steps` in place."""
    by_id = {s["id"]: s for s in steps}
    adj: dict[str, list[str]] = {s["id"]: [] for s in steps}
    indeg: dict[str, int] = {s["id"]: 0 for s in steps}
    for e in next_edges:
        a, b = e["source_step_id"], e["target_step_id"]
        if a in adj and b in indeg:
            adj[a].append(b)
            indeg[b] += 1
    available = [sid for sid in by_id if indeg[sid] == 0]
    placed: set[str] = set()
    rank = 0
    last = None
    while available:
        pick = None
        if last is not None:
            cand = [c for c in adj.get(last, []) if c in available]
            if cand:
                pick = cand[0]
        if pick is None:
            pick = available[0]
        available.remove(pick)
        if pick in placed:
            continue
        placed.add(pick)
        by_id[pick]["sequence"] = rank
        rank += 1
        last = pick
        for nxt in adj.get(pick, []):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                available.append(nxt)
    # cycle leftovers
    for s in steps:
        if s["id"] not in placed:
            s["sequence"] = rank
            rank += 1


def _finalize_summary(
    ctx: IngestionWorkflowContext,
    *,
    next_ui_edges_created: int,
    gateways_created: int,
    next_ui_edges_skipped_manual: int,
    next_ui_edges_deleted: int,
    warnings: list[dict[str, Any]],
    journeys_created: int = 0,
) -> None:
    """Stash counters on ctx so the run-summary block in the workflow runner
    can include them in the final COMPLETE event."""
    by_code = Counter(w.get("code", "unknown") for w in warnings)
    setattr(
        ctx,
        "ui_flow_summary",
        {
            "journeys_created": journeys_created,
            "next_ui_edges_created": next_ui_edges_created,
            "gateways_created": gateways_created,
            "next_ui_edges_skipped_manual": next_ui_edges_skipped_manual,
            "next_ui_edges_deleted": next_ui_edges_deleted,
            "warnings": warnings,
            "warnings_by_code": dict(by_code),
        },
    )
