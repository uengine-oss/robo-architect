"""
Change Planning: Impact Propagation (engine)

Business capability: iteratively expand impacted node candidates (2nd~N-th order) using 2-hop graph contexts.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from api.platform.observability.request_logging import sha256_text, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger
from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
    env_flag,
    get_llm_provider_model,
)

from .change_planning_contracts import (
    ChangePlanningPhase,
    ChangePlanningState,
    ChangeScope,
    PropagationCandidate,
)
from .change_planning_runtime import get_llm, get_neo4j_driver, neo4j_session
from .impact_propagation_neo4j_context import fetch_2hop_subgraph
from .impact_propagation_prompting import extract_json_from_llm_text, format_subgraph_for_prompt, propagation_prompt
from .impact_propagation_settings import propagation_limits, relationship_whitelist, safe_float


def propagate_impacts_node(state: ChangePlanningState) -> Dict[str, Any]:
    """
    Iteratively expand impacted node candidates (2nd~N-th order) using 2-hop graph contexts.

    Option 1 from PoC: inserted inside /plan (LangGraph workflow), not as a separate endpoint.
    """
    enabled = env_flag("CHANGE_PROPAGATION_ENABLED", True)
    if not enabled:
        SmartLogger.log(
            "INFO",
            "Impact propagation skipped: CHANGE_PROPAGATION_ENABLED is disabled, so the plan will be generated without iterative expansion.",
            category="agent.change_graph.propagation.skipped",
            params={
                "user_story_id": state.user_story_id,
                "scope": state.change_scope.value if state.change_scope else None,
                "reason": "disabled_by_env",
            },
        )
        return {
            "phase": ChangePlanningPhase.SEARCH_RELATED
            if state.change_scope in [ChangeScope.CROSS_BC, ChangeScope.NEW_CAPABILITY]
            else ChangePlanningPhase.GENERATE_PLAN,
            "propagation_enabled": False,
            "propagation_confirmed": [],
            "propagation_review": [],
            "propagation_rounds": 0,
            "propagation_stop_reason": "disabled",
            "propagation_debug": {"enabled": False},
        }

    limits = propagation_limits()
    rel_types = relationship_whitelist()
    llm = get_llm()

    seed_nodes = state.connected_objects or []
    seed_ids = [n.get("id") for n in seed_nodes if n.get("id")]
    seen_ids = set(seed_ids)

    SmartLogger.log(
        "INFO",
        "Impact propagation started: iteratively expanding impacted nodes using 2-hop contexts and evidence-backed LLM suggestions.",
        category="agent.change_graph.propagation.start",
        params={
            "user_story_id": state.user_story_id,
            "scope": state.change_scope.value if state.change_scope else None,
            "change_description": state.change_description,
            "seed_count": len(seed_ids),
            "seed_ids": summarize_for_log(seed_ids),
            "limits": limits,
            "relationship_whitelist": rel_types,
        }
    )

    if not seed_ids:
        SmartLogger.log(
            "INFO",
            "Impact propagation stopped early: no seed nodes were provided (nothing to expand).",
            category="agent.change_graph.propagation.stop",
            params={
                "user_story_id": state.user_story_id,
                "stop_reason": "no_seeds",
                "limits": limits,
            },
        )
        return {
            "phase": ChangePlanningPhase.SEARCH_RELATED
            if state.change_scope in [ChangeScope.CROSS_BC, ChangeScope.NEW_CAPABILITY]
            else ChangePlanningPhase.GENERATE_PLAN,
            "propagation_enabled": True,
            "propagation_confirmed": [],
            "propagation_review": [],
            "propagation_rounds": 0,
            "propagation_stop_reason": "no_seeds",
            "propagation_debug": {"limits": limits, "whitelist": rel_types, "seed_count": 0},
        }

    confirmed: List[PropagationCandidate] = []
    review: List[PropagationCandidate] = []
    review_by_id: Dict[str, PropagationCandidate] = {}
    confirmed_ids: set[str] = set()

    node_meta_by_id: Dict[str, Dict[str, Any]] = {n.get("id"): n for n in seed_nodes if n.get("id")}

    driver = get_neo4j_driver()
    stop_reason = "max_rounds_reached"
    rounds_done = 0

    try:
        with neo4j_session(driver) as session:
            frontier: List[str] = list(seed_ids)

            for round_idx in range(1, max(1, limits["max_rounds"]) + 1):
                rounds_done = round_idx

                if len(confirmed) >= limits["max_confirmed_nodes"]:
                    stop_reason = "max_confirmed_reached"
                    break

                if not frontier:
                    stop_reason = "fixpoint_no_frontier"
                    break

                frontier_original_size = len(frontier)
                frontier = frontier[: limits["max_frontier_per_round"]]

                SmartLogger.log(
                    "INFO",
                    "Impact propagation round started: building 2-hop contexts around frontier nodes.",
                    category="agent.change_graph.propagation.round.start",
                    params={
                        "user_story_id": state.user_story_id,
                        "round": round_idx,
                        "frontier_original_size": frontier_original_size,
                        "frontier_capped_size": len(frontier),
                        "frontier": frontier,
                        "confirmed_so_far": len(confirmed),
                        "review_so_far": len(review),
                        "seen_so_far": len(seen_ids),
                    }
                )

                contexts: list[str] = []
                union_node_ids: set[str] = set()
                per_center_subgraph_sizes: Dict[str, Dict[str, int]] = {}

                for center_id in frontier:
                    subgraph = fetch_2hop_subgraph(session, center_id, rel_types)
                    per_center_subgraph_sizes[center_id] = {
                        "nodes": len(subgraph.get("nodes") or []),
                        "relationships": len(subgraph.get("relationships") or []),
                    }
                    for n in subgraph.get("nodes") or []:
                        nid = n.get("id")
                        if nid:
                            union_node_ids.add(nid)
                            node_meta_by_id.setdefault(
                                nid,
                                {
                                    "id": nid,
                                    "name": n.get("name") or "",
                                    "type": n.get("type") or "",
                                    "bcId": n.get("bcId"),
                                    "bcName": n.get("bcName"),
                                    "description": n.get("description") or "",
                                },
                            )
                    contexts.append(format_subgraph_for_prompt(center_id, subgraph))

                remaining_confirmed_budget = max(0, limits["max_confirmed_nodes"] - len(confirmed))
                round_budget = min(limits["max_new_per_round"], remaining_confirmed_budget)

                if round_budget <= 0:
                    stop_reason = "budget_exhausted"
                    break

                SmartLogger.log(
                    "INFO",
                    "Impact propagation round context prepared: union subgraph assembled; invoking LLM with stop rules and budget limits.",
                    category="agent.change_graph.propagation.round.context_ready",
                    params={
                        "user_story_id": state.user_story_id,
                        "round": round_idx,
                        "relationship_whitelist": rel_types,
                        "union_node_count": len(union_node_ids),
                        "per_center_subgraph_sizes": per_center_subgraph_sizes,
                        "remaining_confirmed_budget": remaining_confirmed_budget,
                        "round_budget": round_budget,
                    }
                )

                prompt = propagation_prompt(
                    edited_user_story=state.edited_user_story,
                    change_description=state.change_description,
                    centers_context_text="\n\n".join(contexts),
                    max_new=round_budget,
                )

                SmartLogger.log(
                    "INFO",
                    "Propagation round: invoking LLM to identify additional impacted candidates.",
                    category="agent.change_graph.propagation.round",
                    params={
                        "round": round_idx,
                        "frontier": frontier,
                        "seen_ids": len(seen_ids),
                        "confirmed": len(confirmed),
                        "review": len(review),
                        "round_budget": round_budget,
                    }
                )

                provider, model = get_llm_provider_model()
                system_msg = "You are a DDD expert performing iterative impact propagation with evidence."

                if AI_AUDIT_LOG_ENABLED:
                    SmartLogger.log(
                        "INFO",
                        "Impact propagation: LLM invoke starting.",
                        category="agent.change_graph.propagation.llm.start",
                        params={
                            "user_story_id": state.user_story_id,
                            "round": round_idx,
                            "llm": {"provider": provider, "model": model},
                            "round_budget": round_budget,
                            "union_node_count": len(union_node_ids),
                            "prompt_len": len(prompt),
                            "prompt_sha256": sha256_text(prompt),
                            "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                            "system_len": len(system_msg),
                            "system_sha256": sha256_text(system_msg),
                        }
                    )

                t_llm0 = time.perf_counter()
                response = llm.invoke([SystemMessage(content=system_msg), HumanMessage(content=prompt)])
                llm_ms = int((time.perf_counter() - t_llm0) * 1000)

                resp_text = getattr(response, "content", "") or ""
                if AI_AUDIT_LOG_ENABLED:
                    SmartLogger.log(
                        "INFO",
                        "Impact propagation: LLM invoke completed.",
                        category="agent.change_graph.propagation.llm.done",
                        params={
                            "user_story_id": state.user_story_id,
                            "round": round_idx,
                            "llm": {"provider": provider, "model": model},
                            "llm_ms": llm_ms,
                            "response_len": len(resp_text),
                            "response_sha256": sha256_text(resp_text),
                            "response": resp_text if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_text),
                        }
                    )

                parsed: Dict[str, Any] = {}
                try:
                    parsed = json.loads(extract_json_from_llm_text(resp_text))
                except Exception as e:
                    SmartLogger.log(
                        "WARNING",
                        "Propagation round: failed to parse LLM JSON, stopping propagation early.",
                        category="agent.change_graph.propagation.parse_error",
                        params={"round": round_idx, "error": str(e), "raw": resp_text[:1500]}
                    )
                    stop_reason = "llm_parse_error"
                    break

                candidates = parsed.get("candidates") or []
                if not isinstance(candidates, list):
                    candidates = []

                new_confirmed_ids: List[str] = []
                added_this_round = 0
                stats = Counter()
                stats["llm_candidates_total"] = len(candidates)

                for c in candidates:
                    if not isinstance(c, dict):
                        stats["skip_non_dict"] += 1
                        continue

                    cid = (c.get("id") or "").strip()
                    if not cid:
                        stats["skip_missing_id"] += 1
                        continue

                    if cid not in union_node_ids:
                        stats["skip_not_in_context"] += 1
                        continue

                    if cid in confirmed_ids:
                        stats["skip_already_confirmed"] += 1
                        continue
                    if cid in seen_ids and cid not in review_by_id:
                        stats["skip_already_seen"] += 1
                        continue

                    ctype = (c.get("type") or node_meta_by_id.get(cid, {}).get("type") or "").strip()
                    cname = (c.get("name") or node_meta_by_id.get(cid, {}).get("name") or "").strip()
                    conf = safe_float(c.get("confidence"), 0.0)
                    reason = (c.get("reason") or "").strip()
                    evidence_paths = c.get("evidence_paths") or []
                    if not isinstance(evidence_paths, list):
                        evidence_paths = []
                    evidence_paths = [str(p) for p in evidence_paths if str(p).strip()][:5]
                    suggested = (c.get("suggested_change_type") or "unknown").strip().lower()

                    meta = node_meta_by_id.get(cid) or {}
                    cand = PropagationCandidate(
                        id=cid,
                        type=ctype or meta.get("type") or "Unknown",
                        name=cname or meta.get("name") or "",
                        bcId=meta.get("bcId"),
                        bcName=meta.get("bcName"),
                        confidence=conf,
                        reason=reason,
                        evidence_paths=evidence_paths,
                        suggested_change_type=suggested if suggested else "unknown",
                        round=round_idx,
                    )

                    if conf >= limits["confidence_confirmed"] and added_this_round < limits["max_new_per_round"]:
                        if cid in review_by_id:
                            try:
                                review.remove(review_by_id[cid])
                            except ValueError:
                                pass
                            review_by_id.pop(cid, None)
                            stats["promoted_review_to_confirmed"] += 1
                        confirmed.append(cand)
                        confirmed_ids.add(cid)
                        new_confirmed_ids.append(cid)
                        seen_ids.add(cid)
                        added_this_round += 1
                        stats["added_confirmed"] += 1
                    elif conf >= limits["confidence_review"]:
                        prev = review_by_id.get(cid)
                        if prev is None:
                            review.append(cand)
                            review_by_id[cid] = cand
                            seen_ids.add(cid)
                            stats["added_review"] += 1
                        else:
                            if cand.confidence > prev.confidence:
                                try:
                                    idx = review.index(prev)
                                    review[idx] = cand
                                except ValueError:
                                    review.append(cand)
                                review_by_id[cid] = cand
                                stats["updated_review_higher_confidence"] += 1
                    else:
                        stats["discard_low_confidence"] += 1
                        continue

                SmartLogger.log(
                    "INFO",
                    "Impact propagation round classified candidates: accepted/ignored counts explain why the frontier will expand or converge.",
                    category="agent.change_graph.propagation.round.classified",
                    params={
                        "user_story_id": state.user_story_id,
                        "round": round_idx,
                        "thresholds": {
                            "confirmed": limits["confidence_confirmed"],
                            "review": limits["confidence_review"],
                        },
                        "stats": dict(stats),
                        "new_confirmed_ids": new_confirmed_ids,
                        "confirmed_total": len(confirmed),
                        "review_total": len(review),
                        "seen_total": len(seen_ids),
                    }
                )

                if not new_confirmed_ids:
                    stop_reason = "fixpoint_no_new_confirmed"
                    break

                frontier = new_confirmed_ids

    finally:
        try:
            driver.close()
        except Exception:
            pass

    expanded_connected = list(state.connected_objects or [])
    connected_before = len(expanded_connected)
    existing_ids = {n.get("id") for n in expanded_connected if n.get("id")}

    for cand in confirmed:
        if cand.id in existing_ids:
            continue
        meta = node_meta_by_id.get(cand.id) or {}
        expanded_connected.append(
            {
                "id": cand.id,
                "type": cand.type or meta.get("type") or "Unknown",
                "name": cand.name or meta.get("name") or "",
                "bcId": cand.bcId or meta.get("bcId"),
                "bcName": cand.bcName or meta.get("bcName"),
                "description": meta.get("description") or "",
                "propagation": {
                    "confidence": cand.confidence,
                    "reason": cand.reason,
                    "evidence_paths": cand.evidence_paths,
                    "suggested_change_type": cand.suggested_change_type,
                },
            }
        )
        existing_ids.add(cand.id)

    SmartLogger.log(
        "INFO",
        "Impact propagation completed: stop reason and counts summarize whether the algorithm converged safely.",
        category="agent.change_graph.propagation.done",
        params={
            "user_story_id": state.user_story_id,
            "rounds_done": rounds_done,
            "stop_reason": stop_reason,
            "seed_count": len(seed_ids),
            "confirmed_count": len(confirmed),
            "review_count": len(review),
            "connected_objects_before": connected_before,
            "connected_objects_after": len(expanded_connected),
        },
    )

    return {
        "phase": ChangePlanningPhase.SEARCH_RELATED
        if state.change_scope in [ChangeScope.CROSS_BC, ChangeScope.NEW_CAPABILITY]
        else ChangePlanningPhase.GENERATE_PLAN,
        "propagation_enabled": True,
        "propagation_confirmed": confirmed,
        "propagation_review": review,
        "propagation_rounds": rounds_done,
        "propagation_stop_reason": stop_reason,
        "propagation_debug": {
            "limits": limits,
            "whitelist": rel_types,
            "seed_count": len(seed_ids),
            "confirmed_count": len(confirmed),
            "review_count": len(review),
        },
        "connected_objects": expanded_connected,
    }


