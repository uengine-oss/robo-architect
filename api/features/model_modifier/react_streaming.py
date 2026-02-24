from __future__ import annotations

import re
import json
import time
from typing import Any, AsyncGenerator, Dict, List, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.platform.llm import get_llm as get_platform_llm
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    MODEL_MODIFIER_CONTEXT_CHARS_LIMIT
)
from .react_prompt import REACT_SYSTEM_PROMPT
from .react_sections import extract_section
from .sse_events import format_sse_event


def _gen_change_id() -> str:
    # Short, stable-enough for a single stream. Not cryptographic.
    return f"chg-{int(time.time() * 1000)}-{int(time.perf_counter() * 1000000) % 1000000}"


def _sanitize_updates(change: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize legacy fields into `updates` for update/create actions.
    This keeps the system tolerant while we transition prompt formats.
    """
    updates = change.get("updates")
    if isinstance(updates, dict):
        return updates

    updates = {}
    for k in ["description", "template", "attachedToId", "attachedToType", "attachedToName"]:
        if k in change:
            updates[k] = change.get(k)
    return updates


def _selected_node_map(selected_nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for n in selected_nodes or []:
        node_id = n.get("id")
        if node_id:
            out[str(node_id)] = n
    return out


def _type_priority(type_name: str | None) -> int:
    # Smaller is higher priority
    t = (type_name or "").strip()
    order = {
        "Aggregate": 0,
        "Command": 1,
        "ReadModel": 2,
        "Event": 3,
        "UI": 4,
        "Property": 5,
    }
    return order.get(t, 999)


_NORMALIZE_RX = re.compile(r"[\s_\-./:|\\]+")


def _normalize_for_match(s: str | None) -> str:
    raw = (s or "").strip().lower()
    if not raw:
        return ""
    return _NORMALIZE_RX.sub("", raw)


def _fetch_node_snapshot(target_id: str) -> dict[str, Any] | None:
    """
    Fetch a minimal snapshot for confirm UI: current fields + labels.
    NOTE: sync neo4j call; acceptable at change-block granularity.
    """
    query = """
    MATCH (n {id: $id})
    RETURN labels(n) as labels,
           n.id as id,
           n.name as name,
           n.description as description,
           n.type as type,
           n.isKey as isKey,
           n.isForeignKey as isForeignKey,
           n.isRequired as isRequired,
           n.parentType as parentType,
           n.parentId as parentId,
           n.template as template,
           n.attachedToId as attachedToId,
           n.attachedToType as attachedToType,
           n.attachedToName as attachedToName
    """
    with get_session() as session:
        rec = session.run(query, id=target_id).single()
        if not rec:
            return None
        return {
            "labels": rec.get("labels") or [],
            "id": rec.get("id"),
            "name": rec.get("name"),
            "description": rec.get("description"),
            "type": rec.get("type"),
            "isKey": rec.get("isKey"),
            "isForeignKey": rec.get("isForeignKey"),
            "isRequired": rec.get("isRequired"),
            "parentType": rec.get("parentType"),
            "parentId": rec.get("parentId"),
            "template": rec.get("template"),
            "attachedToId": rec.get("attachedToId"),
            "attachedToType": rec.get("attachedToType"),
            "attachedToName": rec.get("attachedToName"),
        }


async def stream_react_response(
    prompt: str,
    selected_nodes: List[Dict[str, Any]],
    conversation_history: List[Dict[str, Any]],
) -> AsyncGenerator[str, None]:
    try:
        t0 = time.perf_counter()
        first_token_ms: int | None = None

        llm_non_streaming = get_platform_llm(
            streaming=False
        )

        llm = get_platform_llm(
            streaming=True
        )

        nodes_context = "\n".join(
            [
                f"- {node.get('type', 'Unknown')}: {node.get('name', node.get('id'))} "
                f"(ID: {node.get('id')}, BC: {node.get('bcId', 'N/A')})"
                for node in selected_nodes
            ]
        )

        # =============================================================================
        # Intent analysis (structured) + propagation reuse + injected context block
        # =============================================================================
        class IntentAnalysis(BaseModel):
            scope: Literal["local", "cross_bc", "new_capability"] = "local"
            required_types: List[str] = Field(default_factory=list)
            need_propagation: bool = True
            property_focus: bool = False

        def _analyze_intent() -> IntentAnalysis:
            system = (
                "You are an intent classifier for a chat-based Event Storming model editor.\n"
                "Given a natural language request and selected node context, decide:\n"
                "- scope: local|cross_bc|new_capability\n"
                "- required_types: list of node types needed to answer accurately\n"
                "- need_propagation: whether to expand context beyond selected nodes\n"
                "- property_focus: whether this request primarily targets Property changes\n"
                "Return ONLY the structured fields."
            )
            human = f"Selected nodes:\n{nodes_context}\n\nUser request:\n{prompt}\n"
            try:
                structured = llm_non_streaming.with_structured_output(IntentAnalysis)
                return structured.invoke([SystemMessage(content=system), HumanMessage(content=human)])
            except Exception as e:
                SmartLogger.log(
                    "WARNING",
                    "Model Modifier intent analysis failed; falling back to defaults.",
                    category="api.chat.intent.fallback",
                    params={"error": {"type": type(e).__name__, "message": str(e)}},
                )
                return IntentAnalysis(
                    scope="local",
                    required_types=["Aggregate", "Command", "ReadModel", "Event", "UI", "Property"],
                    need_propagation=True,
                    property_focus=True,
                )

        intent = _analyze_intent()
        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "Model Modifier intent analyzed.",
                category="api.chat.intent",
                params={"prompt": prompt, "intent": intent.model_dump(), "selectedNodes": selected_nodes},
            )

        propagation_confirmed: list[dict[str, Any]] = []
        propagation_review: list[dict[str, Any]] = []
        propagation_debug: dict[str, Any] = {}
        propagation_rounds: int = 0
        propagation_stop_reason: str = ""
        
        # 영향도 분석은 항상 선행되어야 함 (workflow에 필수)
        # Intent의 need_propagation 값과 무관하게 항상 실행
        SmartLogger.log(
            "INFO",
            "Model Modifier: Starting impact propagation (always executed before workflow).",
            category="api.chat.propagation.start",
            params={
                "intent_need_propagation": getattr(intent, 'need_propagation', None),
                "selectedNodes": selected_nodes,
                "prompt": prompt[:200],  # 첫 200자만 로깅
            },
        )
        
        try:
            from api.features.change_management.planning_agent.change_planning_contracts import (
                ChangePlanningState,
                ChangeScope,
            )
            from api.features.change_management.planning_agent.impact_propagation_engine import (
                propagate_impacts_node,
            )

            scope_map = {
                "local": ChangeScope.LOCAL,
                "cross_bc": ChangeScope.CROSS_BC,
                "new_capability": ChangeScope.NEW_CAPABILITY,
            }
            state = ChangePlanningState(
                user_story_id="chat.model_modifier",
                edited_user_story={"role": "user", "action": prompt, "benefit": ""},
                change_description=prompt,
                connected_objects=list(selected_nodes or []),
                change_scope=scope_map.get(intent.scope, ChangeScope.LOCAL),
            )
            
            SmartLogger.log(
                "INFO",
                "Model Modifier: Calling propagate_impacts_node.",
                category="api.chat.propagation.call",
                params={
                    "state_user_story_id": state.user_story_id,
                    "change_scope": str(state.change_scope),
                    "connected_objects_count": len(state.connected_objects or []),
                },
            )
            
            result = propagate_impacts_node(state)
            confirmed = result.get("propagation_confirmed") or []
            review = result.get("propagation_review") or []
            propagation_confirmed = [(c.model_dump() if hasattr(c, "model_dump") else dict(c)) for c in confirmed]
            propagation_review = [(c.model_dump() if hasattr(c, "model_dump") else dict(c)) for c in review]
            propagation_debug = result.get("propagation_debug") or {}
            try:
                propagation_rounds = int(result.get("propagation_rounds") or 0)
            except Exception:
                propagation_rounds = 0
            propagation_stop_reason = str(result.get("propagation_stop_reason") or "")
            
            SmartLogger.log(
                "INFO",
                "Model Modifier: Impact propagation completed.",
                category="api.chat.propagation.complete",
                params={
                    "confirmed_count": len(propagation_confirmed),
                    "review_count": len(propagation_review),
                    "rounds": propagation_rounds,
                    "stop_reason": propagation_stop_reason,
                    "has_debug": bool(propagation_debug),
                },
            )
        except Exception as e:
            SmartLogger.log(
                "ERROR",
                "Model Modifier propagation failed; continuing with selected nodes only.",
                category="api.chat.propagation.failed",
                params={
                    "error": {"type": type(e).__name__, "message": str(e)},
                    "traceback": str(e.__traceback__) if hasattr(e, "__traceback__") else None,
                },
            )

        # =============================================================================
        # Emit impact summary (once) for frontend debugging UI
        # - confirmed only (review is intentionally omitted for UX noise control)
        # - includes K (max rounds) and relationship whitelist for hop analysis alignment
        # =============================================================================
        def _minimize_candidate(c: dict[str, Any]) -> dict[str, Any]:
            return {
                "id": c.get("id"),
                "type": c.get("type"),
                "name": c.get("name"),
                "bcId": c.get("bcId"),
                "bcName": c.get("bcName"),
                "round": c.get("round", 0),
                "confidence": c.get("confidence", 0.0),
                "reason": c.get("reason", ""),
                "evidence_paths": list(c.get("evidence_paths") or []),
                "suggested_change_type": c.get("suggested_change_type", "unknown"),
            }

        try:
            from api.features.change_management.planning_agent.impact_propagation_settings import (
                propagation_limits,
                relationship_whitelist,
            )

            _limits = propagation_limits()
            _whitelist = relationship_whitelist()
            _k = int(_limits.get("max_rounds") or 0)
        except Exception:
            _k = 0
            _whitelist = []

        confirmed_min = [_minimize_candidate(dict(c)) for c in (propagation_confirmed or [])]
        # UserStory ids discovered by propagation (for drill-down impact analysis)
        user_story_ids: list[str] = []
        for c in confirmed_min:
            if (c.get("type") or "") == "UserStory" and c.get("id"):
                user_story_ids.append(str(c["id"]))

        yield format_sse_event(
            "impact_summary",
            {
                "seedIds": [str(n.get("id")) for n in (selected_nodes or []) if n.get("id")],
                "confirmedCount": len(confirmed_min),
                "propagationConfirmed": confirmed_min,
                "userStoryIds": user_story_ids,
                "k": _k,
                "whitelist": _whitelist,
                "propagationRounds": propagation_rounds,
                "propagationStopReason": propagation_stop_reason,
                # keep minimal debug metadata for UI labeling
                "propagationDebug": propagation_debug or {},
            },
        )

        def _fetch_nodes_context(node_ids: list[str]) -> list[dict[str, Any]]:
            if not node_ids:
                return []
            query = """
            UNWIND $ids as id
            MATCH (n {id: id})
            RETURN n.id as id,
                   labels(n) as labels,
                   labels(n)[0] as type,
                   n.name as name,
                   n.description as description,
                   n.attachedToId as attachedToId,
                   n.attachedToType as attachedToType,
                   n.attachedToName as attachedToName
            """
            with get_session() as session:
                rows = session.run(query, ids=node_ids).data() or []
                try:
                    from api.features.change_management.planning_agent.impact_propagation_neo4j_context import (
                        get_node_contexts,
                    )

                    bc_ctx = get_node_contexts(session, node_ids)
                except Exception:
                    bc_ctx = {}
            out: list[dict[str, Any]] = []
            for r in rows:
                nid = r.get("id")
                if not nid:
                    continue
                c = dict(r)
                if nid in bc_ctx:
                    c["bcId"] = bc_ctx[nid].get("bcId")
                    c["bcName"] = bc_ctx[nid].get("bcName")
                out.append(c)
            return out

        def _fetch_properties_for_parents(parent_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
            if not parent_ids:
                return {}
            query = """
            UNWIND $parent_ids as pid
            MATCH (parent {id: pid})
            OPTIONAL MATCH (parent)-[:HAS_PROPERTY]->(p:Property)
            OPTIONAL MATCH (p)-[:REFERENCES]->(tgt:Property)
            WITH pid, p, collect(DISTINCT {
              id: tgt.id,
              name: tgt.name,
              type: tgt.type,
              isKey: tgt.isKey,
              parentType: tgt.parentType,
              parentId: tgt.parentId
            }) as tgtProps
            WITH pid, collect(DISTINCT {
              id: p.id,
              name: p.name,
              type: p.type,
              description: p.description,
              isKey: p.isKey,
              isForeignKey: p.isForeignKey,
              isRequired: p.isRequired,
              parentType: p.parentType,
              parentId: p.parentId,
              references: [t in tgtProps WHERE t.id IS NOT NULL]
            }) as props
            RETURN pid as parentId, [x in props WHERE x.id IS NOT NULL] as props
            """
            out: dict[str, list[dict[str, Any]]] = {}
            with get_session() as session:
                for r in session.run(query, parent_ids=parent_ids).data() or []:
                    pid = r.get("parentId")
                    if pid:
                        out[str(pid)] = list(r.get("props") or [])
            return out

        def _build_injected_context_block() -> str:
            selected_ids = [str(n.get("id")) for n in (selected_nodes or []) if n.get("id")]
            confirmed_ids = [str(c.get("id")) for c in (propagation_confirmed or []) if c.get("id")]
            review_ids = [str(c.get("id")) for c in (propagation_review or []) if c.get("id")]

            all_ids: list[str] = []
            seen: set[str] = set()
            for nid in (selected_ids + confirmed_ids + review_ids):
                if nid and nid not in seen:
                    seen.add(nid)
                    all_ids.append(nid)

            nodes_meta = _fetch_nodes_context(all_ids)
            nodes_by_id = {str(n.get("id")): n for n in nodes_meta if n.get("id")}
            parent_ids = [
                nid
                for nid, meta in nodes_by_id.items()
                if meta.get("type") in {"Aggregate", "Command", "Event", "ReadModel", "UI"}
            ]
            props_by_parent = _fetch_properties_for_parents(parent_ids)

            segments: list[dict[str, Any]] = []
            for nid in all_ids:
                meta = nodes_by_id.get(nid)
                if not meta:
                    continue
                t = meta.get("type")
                name = meta.get("name") or nid
                bc_name = meta.get("bcName") or "Unknown"
                bc_id = meta.get("bcId") or "N/A"
                desc = meta.get("description") or ""

                props = props_by_parent.get(nid) or []
                prop_lines: list[str] = []
                for p in props:
                    refs = p.get("references") or []
                    ref_str = ""
                    if refs:
                        ref_bits = []
                        for tgt in refs[:5]:
                            ref_bits.append(
                                f"{tgt.get('name') or tgt.get('id')}({tgt.get('parentType')}/{tgt.get('parentId')})"
                            )
                        more = f" +{len(refs) - 5} more" if len(refs) > 5 else ""
                        ref_str = f" refs=[{'; '.join(ref_bits)}]{more}"
                    prop_lines.append(
                        f"- Property[{p.get('id')}]: {p.get('name')} :: {p.get('type')} "
                        f"(isKey={p.get('isKey')}, isFK={p.get('isForeignKey')}, isReq={p.get('isRequired')}, "
                        f"parent={p.get('parentType')}/{p.get('parentId')}){ref_str} "
                        f"desc={p.get('description')!r}"
                    )

                ann_bits: list[str] = []
                for c in (propagation_confirmed or []):
                    if str(c.get("id")) == nid:
                        ann_bits.append(
                            f"propagation: CONFIRMED (round={c.get('round')}, conf={c.get('confidence')}, suggest={c.get('suggested_change_type')})"
                        )
                        if c.get("reason"):
                            ann_bits.append(f"reason: {c.get('reason')}")
                        if c.get("evidence_paths"):
                            ann_bits.append(f"evidence_paths: {c.get('evidence_paths')[:3]}")
                for c in (propagation_review or []):
                    if str(c.get("id")) == nid:
                        ann_bits.append(
                            f"propagation: REVIEW (round={c.get('round')}, conf={c.get('confidence')}, suggest={c.get('suggested_change_type')})"
                        )
                        if c.get("reason"):
                            ann_bits.append(f"reason: {c.get('reason')}")
                        if c.get("evidence_paths"):
                            ann_bits.append(f"evidence_paths: {c.get('evidence_paths')[:2]}")

                header = f"- Node[{nid}] {t}: {name} (BC={bc_name}/{bc_id})"
                body_lines: list[str] = []
                if desc:
                    body_lines.append(f"  - description: {desc!r}")
                if t == "UI":
                    body_lines.append(
                        f"  - attachedTo: {meta.get('attachedToType')}/{meta.get('attachedToName')} (id={meta.get('attachedToId')})"
                    )
                for a in ann_bits:
                    body_lines.append(f"  - {a}")
                if props:
                    body_lines.append(f"  - properties ({len(props)}):")
                    body_lines.extend([f"    {ln}" for ln in prop_lines])

                text = "\n".join([header] + body_lines)
                segments.append(
                    {
                        "id": nid,
                        "type": t,
                        "name": name,
                        "text": text,
                        "rank_hint": f"{t} {name} {bc_name} {desc[:200]} props={len(props)}",
                    }
                )

            limit = int(MODEL_MODIFIER_CONTEXT_CHARS_LIMIT or 100_000)
            base = (
                "## Injected Context (Auto)\n"
                f"- context_chars_limit: {limit}\n"
                f"- intent: {intent.model_dump()}\n"
                f"- propagation: confirmed={len(propagation_confirmed)} review={len(propagation_review)} debug={propagation_debug}\n\n"
                "### Nodes + Embedded Properties\n"
            )
            total = len(base) + sum(len(s["text"]) + 2 for s in segments)
            if total <= limit:
                return base + "\n\n".join(s["text"] for s in segments)

            # Ranking-only LLM call
            rank_system = (
                "You are a ranking model. Score each item by relevance to the user request.\n"
                "Return JSON: {\"items\":[{\"id\":\"...\",\"relevance\":0.0,\"reason\":\"...\"}...]}\n"
                "Rules:\n"
                "- relevance must be in [0,1]\n"
                "- keep reason short\n"
                "- do not invent ids; use only provided ids\n"
            )
            rank_lines = [f"- id={s['id']} type={s['type']} name={s['name']} hint={s['rank_hint']}" for s in segments]
            rank_human = f"User request:\n{prompt}\n\nItems:\n" + "\n".join(rank_lines)

            rankings: dict[str, dict[str, Any]] = {}
            try:
                resp = llm_non_streaming.invoke([SystemMessage(content=rank_system), HumanMessage(content=rank_human)])
                raw = getattr(resp, "content", "") or ""
                if "```json" in raw:
                    raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
                elif "```" in raw:
                    raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
                parsed = json.loads(raw) if raw else {}
                for it in parsed.get("items") or []:
                    rid = str(it.get("id") or "")
                    if not rid:
                        continue
                    try:
                        rel = float(it.get("relevance", 0.0))
                    except Exception:
                        rel = 0.0
                    rel = max(0.0, min(1.0, rel))
                    rankings[rid] = {"relevance": rel, "reason": str(it.get("reason") or "")}
            except Exception as e:
                SmartLogger.log(
                    "WARNING",
                    "Context ranking failed; falling back to deterministic ordering.",
                    category="api.chat.context.rank.failed",
                    params={"error": {"type": type(e).__name__, "message": str(e)}},
                )

            for s in segments:
                r = rankings.get(s["id"]) or {}
                s["relevance"] = float(r.get("relevance", 0.0))
                s["relevance_reason"] = r.get("reason", "")

            segments.sort(
                key=lambda s: (
                    -float(s.get("relevance", 0.0)),
                    _type_priority(str(s.get("type"))),
                    str(s.get("name") or ""),
                )
            )

            kept: list[str] = []
            used = len(base)
            for s in segments:
                chunk = s["text"]
                extra = (2 if kept else 0) + len(chunk)
                if used + extra > limit:
                    continue
                kept.append(chunk)
                used += extra

            meta = (
                "\n\n### Context Truncation\n"
                f"- original_chars: {total}\n"
                f"- kept_items: {len(kept)} / {len(segments)}\n"
                "- sort: relevance desc → type priority → name asc\n"
            )
            return base + meta + "\n\n" + "\n\n".join(kept)

        injected_context = ""
        if bool(intent.property_focus) or ("Property" in (intent.required_types or [])):
            injected_context = _build_injected_context_block()

        messages = [SystemMessage(content=REACT_SYSTEM_PROMPT)]
        for msg in conversation_history[-5:]:
            if msg.get("type") == "user":
                messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("type") == "assistant":
                messages.append(AIMessage(content=msg.get("content", "")))

        current_message = f"""## Selected Nodes
{nodes_context}

## User Request
{prompt}

{injected_context}

## Instructions
1. First, analyze what changes are needed (THOUGHT)
2. Then describe the specific actions to take (ACTION)
3. After each action, describe the result (OBSERVATION)
4. If changes cascade to other nodes, continue the ReAct loop
5. Finally, summarize all changes made

Format your response like this:
💭 THOUGHT: ...
⚡ ACTION: ...
👁️ OBSERVATION: ...
✅ SUMMARY: ...

For each proposed change, also output a JSON block (DRAFT ONLY) in this format:
```json
{{
  "changeId": "chg-...",
  "action": "rename|update|create|delete|connect",
  "targetId": "...",
  "targetType": "Command|Event|Policy|Aggregate|ReadModel|UI|BoundedContext|Property",
  "targetName": "...",
  "bcId": "<uuid>",
  "rationale": "why this change is necessary",
  "updates": {{
    "description": "...",
    "template": "<div class=\\"wf-root wf-theme-ant\\" data-wf-root=\\"1\\">...</div>",
    "attachedToId": "...",
    "attachedToType": "Command|ReadModel",
    "attachedToName": "..."
  }}
}}
```

Rules:
- For "update": put ALL property changes inside `updates` (field patch). Do not invent extra fields.
- For UI wireframes: `updates.template` MUST be a body-only HTML fragment (no markdown fences).
  - MUST NOT include: <!doctype>, <html>, <head>, <body>
  - MUST NOT include: <script>, inline event handlers (on*), javascript: URLs
  - MUST start with: <div class="wf-root wf-theme-ant|wf-theme-material" data-wf-root="1"> ... </div>
  - <style> is allowed ONLY if every selector is scoped under `.wf-root`, and it MUST NOT use @import or url(...)
  - Make it modern UI (Ant/Material): app bar, cards, table toolbar + pagination, form grid, tabs/segments, chips/badges, empty/loading/error placeholders
- For "rename": set `targetName` to the NEW name (and you may omit `updates`).

For "connect" actions, include:
- "sourceId"
- "connectionType": "TRIGGERS" | "INVOKES" | "EMITS" | "REFERENCES"

For Property actions:
- targetType MUST be "Property"
- updates MUST include: parentType, parentId
- For create Property, updates MUST include: name, type, description, isKey, isForeignKey, isRequired, parentType, parentId
  - Note: Property id is server-assigned UUID; you may use a temporary targetId like "prop-temp-1" and the server will replace it in the applied response.
"""
        messages.append(HumanMessage(content=current_message))

        selected_map = _selected_node_map(selected_nodes)

        draft_changes: list[dict[str, Any]] = []
        buffer = ""
        raw_output = ""
        chunk_count = 0
        total_chars = 0
        json_blocks_seen = 0
        json_decode_errors = 0

        # De-dup streaming events: only emit when section content actually changes.
        # Without this, the backend may re-emit THOUGHT/ACTION/OBSERVATION on every token,
        # and the frontend will keep appending trace lines.
        last_sent_thought: str | None = None
        last_sent_action: str | None = None
        last_sent_observation: str | None = None

        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "Chat modify: LLM call starting (streaming).",
                category="api.chat.llm.start",
                params={
                    "prompt": prompt,
                    "system_prompt": REACT_SYSTEM_PROMPT,
                    "constructed_user_message": current_message,
                    # Reproducibility: keep raw payloads (SmartLogger can offload to detail files).
                    "selected_nodes": selected_nodes,
                    "conversation_history": conversation_history,
                }
            )

        async for chunk in llm.astream(messages):
            if not chunk.content:
                continue

            buffer += chunk.content
            raw_output += chunk.content
            chunk_count += 1
            total_chars += len(chunk.content)

            if first_token_ms is None:
                first_token_ms = int((time.perf_counter() - t0) * 1000)
                if AI_AUDIT_LOG_ENABLED:
                    SmartLogger.log(
                        "INFO",
                        "Chat modify: first token received from LLM.",
                        category="api.chat.llm.first_token",
                        params={"first_token_ms": first_token_ms}
                    )

            if "THOUGHT:" in buffer:
                thought = extract_section(buffer, "THOUGHT")
                if thought and thought != last_sent_thought:
                    last_sent_thought = thought
                    yield format_sse_event("thought", {"content": thought})

            if "ACTION:" in buffer:
                action_txt = extract_section(buffer, "ACTION")
                if action_txt and action_txt != last_sent_action:
                    last_sent_action = action_txt
                    yield format_sse_event("action", {"content": action_txt})

            if "OBSERVATION:" in buffer:
                obs = extract_section(buffer, "OBSERVATION")
                if obs and obs != last_sent_observation:
                    last_sent_observation = obs
                    yield format_sse_event("observation", {"content": obs})

            while "```json" in buffer and "```" in buffer[buffer.find("```json") + 7 :]:
                start = buffer.find("```json") + 7
                end = buffer.find("```", start)
                if end <= start:
                    break
                json_str = buffer[start:end].strip()
                try:
                    json_blocks_seen += 1
                    change = json.loads(json_str)

                    # Normalize / enrich draft payload
                    if not change.get("changeId"):
                        change["changeId"] = _gen_change_id()

                    action = change.get("action")
                    if action in ("update", "create"):
                        change["updates"] = _sanitize_updates(change)

                    # Best-effort before/after for confirm UI
                    before: dict[str, Any] = {}
                    after: dict[str, Any] = {}
                    target_id = change.get("targetId")
                    if target_id:
                        # Prefer selected-nodes context for speed/consistency
                        src = selected_map.get(str(target_id))
                        if src:
                            for k in [
                                "name",
                                "description",
                                "template",
                                "attachedToId",
                                "attachedToType",
                                "attachedToName",
                                # Property core fields (when selected node is a Property-like payload)
                                "type",
                                "isKey",
                                "isForeignKey",
                                "isRequired",
                                "parentType",
                                "parentId",
                            ]:
                                if k in src:
                                    before[k] = src.get(k)
                        else:
                            snap = _fetch_node_snapshot(str(target_id))
                            if snap:
                                for k in [
                                    "name",
                                    "description",
                                    "template",
                                    "attachedToId",
                                    "attachedToType",
                                    "attachedToName",
                                    "type",
                                    "isKey",
                                    "isForeignKey",
                                    "isRequired",
                                    "parentType",
                                    "parentId",
                                ]:
                                    before[k] = snap.get(k)

                    # If Property update draft does not point to a real UUID (or snapshot was empty),
                    # try to enrich `before` using (parentType,parentId,targetName/updates.name) selector.
                    if change.get("targetType") == "Property" and (not before):
                        updates = change.get("updates") if isinstance(change.get("updates"), dict) else {}
                        parent_type = str(updates.get("parentType") or "").strip()
                        parent_id = str(updates.get("parentId") or "").strip()
                        # For updates, prefer `targetName` as selector (existing property name), fall back to updates.name
                        selector_name = str(change.get("targetName") or updates.get("name") or "").strip()
                        if parent_type and parent_id and selector_name:
                            try:
                                q = """
                                MATCH (p:Property {parentType: $pt, parentId: $pid, name: $name})
                                RETURN p.id as id, p.name as name, p.description as description,
                                       p.type as type, p.isKey as isKey, p.isForeignKey as isForeignKey,
                                       p.isRequired as isRequired, p.parentType as parentType, p.parentId as parentId
                                """
                                with get_session() as session:
                                    rec = session.run(q, pt=parent_type, pid=parent_id, name=selector_name).single()
                                    if rec:
                                        for k in [
                                            "id",
                                            "name",
                                            "description",
                                            "type",
                                            "isKey",
                                            "isForeignKey",
                                            "isRequired",
                                            "parentType",
                                            "parentId",
                                        ]:
                                            before[k] = rec.get(k)
                            except Exception:
                                pass

                    # Compute after from updates / rename targetName
                    if change.get("action") == "rename" and change.get("targetName") is not None:
                        after["name"] = change.get("targetName")
                    updates = change.get("updates") if isinstance(change.get("updates"), dict) else {}
                    for k, v in updates.items():
                        after[k] = v
                    change["before"] = before
                    change["after"] = after

                    draft_changes.append(change)
                    yield format_sse_event("draft_change", {"draft": change})
                    if AI_AUDIT_LOG_ENABLED:
                        SmartLogger.log(
                            "INFO",
                            "Chat modify: draft change block captured (not applied).",
                            category="api.chat.draft.block",
                            params={
                                "change": change,
                            }
                        )
                except json.JSONDecodeError:
                    json_decode_errors += 1
                    pass
                buffer = buffer[: buffer.find("```json")] + buffer[end + 3 :]

        total_ms = int((time.perf_counter() - t0) * 1000)
        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "Chat modify: LLM streaming completed.",
                category="api.chat.llm.done",
                params={
                    "duration_ms": total_ms,
                    "first_token_ms": first_token_ms,
                    "stream": {"chunks": chunk_count, "chars": total_chars},
                    "json_blocks": {
                        "seen": json_blocks_seen,
                        "json_decode_errors": json_decode_errors,
                    },
                    # Reproducibility: keep raw data.
                    "draft_changes": draft_changes,
                    "raw_output": raw_output,
                }
            )

        summary_section = extract_section(raw_output, "SUMMARY")
        final_summary = (
            summary_section
            if summary_section
            else f"제안 완료: {len(draft_changes)}개의 변경사항을 준비했습니다. 승인 후 적용됩니다."
        )

        yield format_sse_event(
            "draft_complete",
            {"summary": final_summary, "draftChanges": draft_changes},
        )

    except Exception as e:
        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "ERROR",
                "Chat modify failed: exception during streaming.",
                category="api.chat.llm.error",
                params={"error": {"type": type(e).__name__, "message": str(e)}}
            )
        yield format_sse_event("error", {"message": str(e)})


