from __future__ import annotations

import asyncio
import re
import time
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.event_storming.prompts import (
    GENERATE_PROPERTIES_AGGREGATE_BATCH_PROMPT,
    GENERATE_PROPERTIES_READMODELS_BATCH_PROMPT,
    SYSTEM_PROMPT,
)
from api.features.ingestion.event_storming.structured_outputs import PropertyBatch
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.features.ingestion.workflow.utils.chunking import (
    estimate_tokens,
    split_list_with_overlap,
    ACCUMULATED_NAMES_MAX,
    DEFAULT_MAX_TOKENS,
)
from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
    get_llm_provider_model,
)
from api.platform.keys import bc_key as build_bc_key
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

# Chunking constants for intra-aggregate command/event splitting
_PROP_CHUNK_CMD_SIZE = 15
_PROP_CHUNK_CMD_OVERLAP = 2


_NON_ALNUM = re.compile(r"[^a-zA-Z0-9]+")


def _to_camel_case(raw: str) -> str:
    """
    Normalize property names to camelCase.
    Tries to reduce churn by keeping existing casing when it already looks like camelCase.
    """
    s = (raw or "").strip()
    if not s:
        return ""

    # If it already looks like camelCase or lowerCamelCase, keep it with minimal fixes.
    if " " not in s and "-" not in s and "_" not in s:
        # Normalize common ID spellings.
        if s.lower() == "id":
            return "id"
        if s.endswith("ID"):
            return s[:-2] + "Id"
        if s.endswith("id") and s != "id":
            return s[:-2] + "Id"
        return s[0].lower() + s[1:]

    s = _NON_ALNUM.sub(" ", s).strip()
    parts = [p for p in s.split(" ") if p]
    if not parts:
        return ""

    lower_parts = [p.lower() for p in parts]
    if len(lower_parts) == 1:
        return "id" if lower_parts[0] == "id" else lower_parts[0]

    head = lower_parts[0]
    tail = [p.capitalize() for p in lower_parts[1:]]
    out = head + "".join(tail)

    # Enforce identifier suffix formatting (xxxId)
    if out.lower() == "id":
        return "id"
    if out.lower().endswith("id") and not out.endswith("Id"):
        out = out[:-2] + "Id"
    return out


def _clean_fk_hint(is_fk: bool, hint: Any) -> str | None:
    if not is_fk:
        return None
    if not isinstance(hint, str):
        return None
    h = hint.strip()
    if not h:
        return None
    # Soft validation: <TargetType>:<TargetKey>:<TargetPropertyName>
    parts = h.split(":")
    if len(parts) != 3:
        return None
    tgt_type, tgt_key, tgt_prop = (p.strip() for p in parts)
    if tgt_type not in ("Aggregate", "Command", "Event", "ReadModel"):
        return None
    if not tgt_key or not tgt_prop:
        return None
    return f"{tgt_type}:{tgt_key}:{tgt_prop}"


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Deduplicate by (parentType,parentId,name). Last write wins (latest LLM value).
    """
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in rows or []:
        try:
            k = (str(r.get("parentType") or ""), str(r.get("parentId") or ""), str(r.get("name") or ""))
        except Exception:
            continue
        if not all(k):
            continue
        out[k] = r
    return list(out.values())


_PROP_ACCUMULATED_BUDGET_TOKENS = 4000  # Max token budget for accumulated properties context


def _format_accumulated_properties(accumulated: list[dict[str, Any]]) -> str:
    """Format already-generated properties for prompt injection across chunks.

    Applies progressive compression:
    1. Full detail (parent + props list) if within budget
    2. Compact (parent + prop count) if over budget
    """
    if not accumulated:
        return ""

    header = (
        "\n\n## ALREADY GENERATED PROPERTIES (previous chunks)\n"
        "The following properties have already been generated. "
        "Maintain consistency with existing property names and types. "
        "Do NOT regenerate properties for these parents.\n\n"
    )

    # Group by parentType+parentName
    groups: dict[str, list[str]] = {}
    for row in accumulated:
        ptype = row.get("parentType", "")
        pname = row.get("parentName", "")
        prop_name = row.get("name", "")
        prop_type = row.get("type", "")
        key = f"{ptype} {pname}"
        if key not in groups:
            groups[key] = []
        groups[key].append(f"{prop_name}: {prop_type}")

    # Try full detail first
    lines = []
    shown = 0
    for parent, props in groups.items():
        if shown >= ACCUMULATED_NAMES_MAX:
            lines.append(f"... and {len(groups) - shown} more parents")
            break
        props_str = ", ".join(props[:8])
        if len(props) > 8:
            props_str += f" ... +{len(props) - 8} more"
        lines.append(f"- {parent}: ({props_str})")
        shown += 1

    body = "\n".join(lines)

    # Check budget and compress if needed
    if estimate_tokens(header + body) > _PROP_ACCUMULATED_BUDGET_TOKENS:
        compact_lines = []
        shown = 0
        for parent, props in groups.items():
            if shown >= ACCUMULATED_NAMES_MAX:
                compact_lines.append(f"... and {len(groups) - shown} more")
                break
            compact_lines.append(f"- {parent}: {len(props)} properties")
            shown += 1
        body = "\n".join(compact_lines)

    return header + body + "\n"


def _extract_rows_from_response(
    resp: Any,
    parent_id_by_key: dict[tuple[str, str], str],
) -> list[dict[str, Any]]:
    """Extract property rows from a PropertyBatch LLM response."""
    rows: list[dict[str, Any]] = []
    for parent in getattr(resp, "parents", []) or []:
        ptype = str(getattr(parent, "parentType", "") or "").strip()
        pkey = str(getattr(parent, "parentKey", "") or "").strip()
        pid = parent_id_by_key.get((ptype, pkey))
        if not pid:
            continue
        for prop in getattr(parent, "properties", []) or []:
            raw_name = str(getattr(prop, "name", "") or "")
            name = _to_camel_case(raw_name)
            if not name:
                continue
            ptype_str = str(getattr(prop, "type", "") or "").strip()
            if not ptype_str:
                continue
            desc = str(getattr(prop, "description", "") or "")
            is_key = bool(getattr(prop, "isKey", False))
            is_fk = bool(getattr(prop, "isForeignKey", False))
            is_req = bool(getattr(prop, "isRequired", False))
            fk_hint = _clean_fk_hint(is_fk, getattr(prop, "fkTargetHint", None))
            prop_display_name = getattr(prop, "displayName", None) or name
            rows.append(
                {
                    "parentType": ptype,
                    "parentId": pid,
                    "name": name,
                    "displayName": prop_display_name,
                    "type": ptype_str,
                    "description": desc,
                    "isKey": is_key,
                    "isForeignKey": is_fk,
                    "isRequired": is_req,
                    "fkTargetHint": fk_hint,
                }
            )
    return rows


async def generate_properties_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase: Generate and persist Property nodes for:
    - Aggregate, Command, Event (batched per Aggregate)
    - ReadModel (batched per BC)

    Policy:
    - upsert-only + always overwrite (latest LLM result wins)
    - no deletes
    - FK hints stored in Property.fkTargetHint (optional)
    """
    yield ProgressEvent(
        phase=IngestionPhase.GENERATING_PROPERTIES,
        message="Property 생성 중...",
        progress=86,
    )

    # Known aggregate keys (FK hint help)
    known_aggregate_keys: list[str] = []
    for aggs in (ctx.aggregates_by_bc or {}).values():
        for agg in aggs or []:
            k = getattr(agg, "key", None)
            if isinstance(k, str) and k.strip():
                known_aggregate_keys.append(k.strip())
    known_aggregate_keys = sorted(set(known_aggregate_keys))
    known_aggregate_keys_text = "\n".join([f"- {k}" for k in known_aggregate_keys]) or "None"

    total_upserted = 0
    total_targets = 0

    provider, model = get_llm_provider_model()

    # ---------------------------------------------------------------------
    # A) Aggregate-scoped batch: Aggregate + Commands + Events
    # ---------------------------------------------------------------------
    for bc in ctx.bounded_contexts or []:
        # Handle both dict and object formats
        bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
        bc_key = bc.get("key") if isinstance(bc, dict) else getattr(bc, "key", None)
        bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", None)
        bc_key_value = (str(bc_key).strip() if bc_key else "") or build_bc_key(str(bc_name) if bc_name else "")
        for agg in ctx.aggregates_by_bc.get(bc_id, []) or []:
            agg_key_raw = agg.get("key") if isinstance(agg, dict) else getattr(agg, "key", None)
            agg_id_raw = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
            agg_key = str(agg_key_raw).strip() if agg_key_raw else ""
            agg_id = str(agg_id_raw).strip() if agg_id_raw else ""
            if not agg_key or not agg_id:
                continue

            commands = ctx.commands_by_agg.get(agg_id, []) or []
            events = ctx.events_by_agg.get(agg_id, []) or []

            command_lines: list[str] = []
            for cmd in commands:
                cmd_key_raw = cmd.get("key") if isinstance(cmd, dict) else getattr(cmd, "key", None)
                cmd_id_raw = cmd.get("id") if isinstance(cmd, dict) else getattr(cmd, "id", None)
                cmd_key = str(cmd_key_raw).strip() if cmd_key_raw else ""
                cmd_id = str(cmd_id_raw).strip() if cmd_id_raw else ""
                if not cmd_key or not cmd_id:
                    continue
                cmd_name = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
                cmd_actor = cmd.get("actor") if isinstance(cmd, dict) else getattr(cmd, "actor", "")
                cmd_category = cmd.get("category") if isinstance(cmd, dict) else getattr(cmd, "category", None)
                cmd_input_schema = cmd.get("inputSchema") if isinstance(cmd, dict) else getattr(cmd, "inputSchema", None)
                cmd_description = cmd.get("description") if isinstance(cmd, dict) else getattr(cmd, "description", "")
                command_lines.append(
                    f"- key: {cmd_key}\n"
                    f"  id: {cmd_id}\n"
                    f"  name: {cmd_name}\n"
                    f"  actor: {cmd_actor}\n"
                    f"  category: {cmd_category or ''}\n"
                    f"  inputSchema: {cmd_input_schema or ''}\n"
                    f"  description: {cmd_description}"
                )
            commands_text = "\n".join(command_lines) if command_lines else "None"

            event_lines: list[str] = []
            for evt in events:
                evt_key_raw = evt.get("key") if isinstance(evt, dict) else getattr(evt, "key", None)
                evt_id_raw = evt.get("id") if isinstance(evt, dict) else getattr(evt, "id", None)
                evt_key = str(evt_key_raw).strip() if evt_key_raw else ""
                evt_id = str(evt_id_raw).strip() if evt_id_raw else ""
                if not evt_key or not evt_id:
                    continue
                evt_version = getattr(evt, "version", "1.0.0") or "1.0.0"
                evt_payload = getattr(evt, "payload", None) or ""
                event_lines.append(
                    f"- key: {evt_key}\n"
                    f"  id: {evt_id}\n"
                    f"  name: {getattr(evt, 'name', '')}\n"
                    f"  version: {evt_version}\n"
                    f"  payload: {evt_payload}\n"
                    f"  description: {getattr(evt, 'description', '')}"
                )
            events_text = "\n".join(event_lines) if event_lines else "None"

            # Aggregate에 연결된 US의 source_unit_id → 테이블 스키마 역추적
            schema_context = ""
            if getattr(ctx, "source_type", "") == "analyzer_graph":
                agg_us_ids = (agg.get("user_story_ids") if isinstance(agg, dict) else getattr(agg, "user_story_ids", None)) or []
                unit_ids = []
                for us in (ctx.user_stories or []):
                    if (getattr(us, "id", "") or "") in set(agg_us_ids):
                        src = getattr(us, "source_unit_id", None)
                        if src:
                            unit_ids.append(src)
                if unit_ids:
                    try:
                        from api.features.ingestion.analyzer_graph.graph_context_builder import fetch_table_schemas_for_units
                        schema_context = fetch_table_schemas_for_units(unit_ids)
                    except Exception:
                        pass

            # Common prompt fragments
            agg_name_val = (agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", None)) or ""
            bc_desc_val = (bc.get("description") if isinstance(bc, dict) else getattr(bc, "description", None)) or ""
            agg_root_val = (agg.get("root_entity") if isinstance(agg, dict) else getattr(agg, "root_entity", None)) or ""
            agg_inv_val = summarize_for_log((agg.get("invariants") if isinstance(agg, dict) else getattr(agg, "invariants", None)) or [], max_list=200)
            agg_desc_val = (agg.get("description") if isinstance(agg, dict) else getattr(agg, "description", None)) or ""

            display_lang = getattr(ctx, "display_language", "ko") or "ko"
            display_tail = (
                "\n\n10) For each Property output displayName: a short UI label in Korean (e.g. '주문 번호', '고객명')."
                if display_lang == "ko"
                else "\n\n10) For each Property output displayName: a short UI label in English (e.g. 'Order ID', 'Customer Name')."
            )
            schema_tail = ""
            if schema_context:
                schema_tail = (
                    f"\n\n{schema_context}\n"
                    "위 테이블 스키마의 컬럼 타입을 참고하여 Property 타입을 맞추세요.\n"
                    "FK 관계가 있으면 isForeignKey로 표시하세요."
                )

            # Build parentKey -> parentId map for this scope
            parent_id_by_key: dict[tuple[str, str], str] = {("Aggregate", agg_key): agg_id}
            for cmd in commands:
                ck_raw = cmd.get("key") if isinstance(cmd, dict) else getattr(cmd, "key", None)
                cid_raw = cmd.get("id") if isinstance(cmd, dict) else getattr(cmd, "id", None)
                ck = str(ck_raw).strip() if ck_raw else ""
                cid = str(cid_raw).strip() if cid_raw else ""
                if ck and cid:
                    parent_id_by_key[("Command", ck)] = cid
            for evt in events:
                ek_raw = evt.get("key") if isinstance(evt, dict) else getattr(evt, "key", None)
                eid_raw = evt.get("id") if isinstance(evt, dict) else getattr(evt, "id", None)
                ek = str(ek_raw).strip() if ek_raw else ""
                eid = str(eid_raw).strip() if eid_raw else ""
                if ek and eid:
                    parent_id_by_key[("Event", ek)] = eid

            # ── Chunking decision ──
            test_prompt_tokens = estimate_tokens(
                commands_text + events_text + schema_tail + known_aggregate_keys_text
            )
            needs_chunking = (
                len(commands) > _PROP_CHUNK_CMD_SIZE
                or test_prompt_tokens > DEFAULT_MAX_TOKENS
            )

            structured_llm = ctx.llm.with_structured_output(PropertyBatch)

            if needs_chunking and commands:
                # ── Chunked property generation ──
                cmd_chunks = split_list_with_overlap(
                    commands, chunk_size=_PROP_CHUNK_CMD_SIZE, overlap_count=_PROP_CHUNK_CMD_OVERLAP
                )
                # Also chunk events proportionally based on commands
                evt_chunks = split_list_with_overlap(
                    events, chunk_size=max(len(events) // len(cmd_chunks), 5), overlap_count=1
                ) if events else [[] for _ in cmd_chunks]
                # Pad evt_chunks to match cmd_chunks length
                while len(evt_chunks) < len(cmd_chunks):
                    evt_chunks.append([])

                total_chunks = len(cmd_chunks)
                SmartLogger.log(
                    "INFO",
                    f"Property generation for agg '{agg_name_val}': chunking {len(commands)} cmds + "
                    f"{len(events)} evts into {total_chunks} chunks",
                    category="ingestion.workflow.properties.chunking",
                    params={
                        "session_id": ctx.session.id,
                        "agg_id": agg_id,
                        "total_commands": len(commands),
                        "total_events": len(events),
                        "total_chunks": total_chunks,
                    },
                )

                accumulated_props: list[dict[str, Any]] = []
                all_rows: list[dict[str, Any]] = []

                for chunk_idx in range(total_chunks):
                    chunk_cmds = cmd_chunks[chunk_idx]
                    chunk_evts = evt_chunks[chunk_idx] if chunk_idx < len(evt_chunks) else []

                    # Build chunk-specific command/event text
                    chunk_cmd_lines = []
                    for cmd in chunk_cmds:
                        cmd_key = str((cmd.get("key") if isinstance(cmd, dict) else getattr(cmd, "key", None)) or "").strip()
                        cmd_id = str((cmd.get("id") if isinstance(cmd, dict) else getattr(cmd, "id", None)) or "").strip()
                        if not cmd_key or not cmd_id:
                            continue
                        cmd_name = cmd.get("name") if isinstance(cmd, dict) else getattr(cmd, "name", "")
                        cmd_actor = cmd.get("actor") if isinstance(cmd, dict) else getattr(cmd, "actor", "")
                        cmd_category = cmd.get("category") if isinstance(cmd, dict) else getattr(cmd, "category", None)
                        cmd_input_schema = cmd.get("inputSchema") if isinstance(cmd, dict) else getattr(cmd, "inputSchema", None)
                        cmd_description = cmd.get("description") if isinstance(cmd, dict) else getattr(cmd, "description", "")
                        chunk_cmd_lines.append(
                            f"- key: {cmd_key}\n  id: {cmd_id}\n  name: {cmd_name}\n"
                            f"  actor: {cmd_actor}\n  category: {cmd_category or ''}\n"
                            f"  inputSchema: {cmd_input_schema or ''}\n  description: {cmd_description}"
                        )
                    chunk_cmds_text = "\n".join(chunk_cmd_lines) if chunk_cmd_lines else "None"

                    chunk_evt_lines = []
                    for evt in chunk_evts:
                        evt_key = str((evt.get("key") if isinstance(evt, dict) else getattr(evt, "key", None)) or "").strip()
                        evt_id = str((evt.get("id") if isinstance(evt, dict) else getattr(evt, "id", None)) or "").strip()
                        if not evt_key or not evt_id:
                            continue
                        chunk_evt_lines.append(
                            f"- key: {evt_key}\n  id: {evt_id}\n"
                            f"  name: {getattr(evt, 'name', '')}\n"
                            f"  version: {getattr(evt, 'version', '1.0.0') or '1.0.0'}\n"
                            f"  payload: {getattr(evt, 'payload', None) or ''}\n"
                            f"  description: {getattr(evt, 'description', '')}"
                        )
                    chunk_evts_text = "\n".join(chunk_evt_lines) if chunk_evt_lines else "None"

                    chunk_prompt = GENERATE_PROPERTIES_AGGREGATE_BATCH_PROMPT.format(
                        bc_id=bc_id, bc_key=bc_key_value, bc_name=bc_name or "",
                        bc_description=bc_desc_val, aggregate_id=agg_id,
                        aggregate_key=agg_key, aggregate_name=agg_name_val,
                        aggregate_root_entity=agg_root_val,
                        aggregate_invariants=agg_inv_val,
                        aggregate_description=agg_desc_val,
                        commands=chunk_cmds_text, events=chunk_evts_text,
                        known_aggregate_keys=known_aggregate_keys_text,
                    ) + schema_tail + display_tail

                    # Inject accumulated properties from previous chunks
                    if accumulated_props:
                        chunk_prompt += _format_accumulated_properties(accumulated_props)

                    t_llm0 = time.perf_counter()
                    try:
                        resp = await asyncio.wait_for(
                            asyncio.to_thread(
                                structured_llm.invoke,
                                [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=chunk_prompt)]
                            ),
                            timeout=300.0,
                        )
                    except asyncio.TimeoutError:
                        SmartLogger.log(
                            "ERROR",
                            f"Property generation chunk {chunk_idx + 1}/{total_chunks} timed out",
                            category="ingestion.workflow.properties.chunk_timeout",
                            params={"session_id": ctx.session.id, "agg_id": agg_id, "chunk_index": chunk_idx},
                        )
                        continue
                    except Exception as e:
                        SmartLogger.log(
                            "WARNING",
                            f"Property generation chunk {chunk_idx + 1}/{total_chunks} failed: {e}",
                            category="ingestion.workflow.properties.chunk_error",
                            params={"session_id": ctx.session.id, "agg_id": agg_id, "chunk_index": chunk_idx, "error": str(e)},
                        )
                        continue

                    chunk_rows = _extract_rows_from_response(resp, parent_id_by_key)
                    all_rows.extend(chunk_rows)

                    # Accumulate for next chunk
                    for row in chunk_rows:
                        accumulated_props.append({
                            "parentType": row.get("parentType", ""),
                            "parentName": row.get("name", ""),
                            "name": row.get("name", ""),
                            "type": row.get("type", ""),
                        })

                    SmartLogger.log(
                        "INFO",
                        f"Property chunk {chunk_idx + 1}/{total_chunks} for agg '{agg_name_val}': "
                        f"{len(chunk_rows)} properties",
                        category="ingestion.workflow.properties.chunk_done",
                        params={
                            "session_id": ctx.session.id,
                            "agg_id": agg_id,
                            "chunk_index": chunk_idx,
                            "chunk_rows": len(chunk_rows),
                        },
                    )

                rows = _dedupe_rows(all_rows)
            else:
                # ── Single LLM call (existing path) ──
                prompt = GENERATE_PROPERTIES_AGGREGATE_BATCH_PROMPT.format(
                    bc_id=bc_id, bc_key=bc_key_value, bc_name=bc_name or "",
                    bc_description=bc_desc_val, aggregate_id=agg_id,
                    aggregate_key=agg_key, aggregate_name=agg_name_val,
                    aggregate_root_entity=agg_root_val,
                    aggregate_invariants=agg_inv_val,
                    aggregate_description=agg_desc_val,
                    commands=commands_text, events=events_text,
                    known_aggregate_keys=known_aggregate_keys_text,
                ) + schema_tail + display_tail

                if AI_AUDIT_LOG_ENABLED:
                    SmartLogger.log(
                        "INFO",
                        "Ingestion: generate properties (aggregate batch) - LLM invoke starting.",
                        category="ingestion.llm.generate_properties.start",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "scope": "aggregate_batch",
                            "bc": {"id": bc_id, "name": bc_name, "key": bc_key_value},
                            "aggregate": {"id": agg_id, "name": agg_name_val, "key": agg_key},
                            "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                            "system_prompt": SYSTEM_PROMPT,
                        },
                    )

                t_llm0 = time.perf_counter()
                try:
                    resp = await asyncio.wait_for(
                        asyncio.to_thread(
                            structured_llm.invoke,
                            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
                        ),
                        timeout=300.0,
                    )
                except asyncio.TimeoutError:
                    SmartLogger.log(
                        "ERROR",
                        "Property generation timed out (300s) - aggregate batch",
                        category="ingestion.workflow.properties.timeout",
                        params={"session_id": ctx.session.id, "scope": "aggregate_batch", "bc_id": bc_id, "agg_id": agg_id},
                    )
                    continue
                except Exception as e:
                    SmartLogger.log(
                        "WARNING",
                        "Property generation failed (LLM) - aggregate batch",
                        category="ingestion.workflow.properties",
                        params={
                            "session_id": ctx.session.id,
                            "scope": "aggregate_batch",
                            "bc_id": bc_id,
                            "agg_id": agg_id,
                            "error": str(e),
                        },
                    )
                    continue
                llm_ms = int((time.perf_counter() - t_llm0) * 1000)

                if AI_AUDIT_LOG_ENABLED:
                    try:
                        resp_dump = resp.model_dump() if hasattr(resp, "model_dump") else resp.dict()
                    except Exception:
                        resp_dump = {"__type__": type(resp).__name__, "__repr__": repr(resp)[:1000]}
                    SmartLogger.log(
                        "INFO",
                        "Ingestion: generate properties (aggregate batch) - LLM invoke completed.",
                        category="ingestion.llm.generate_properties.done",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "scope": "aggregate_batch",
                            "bc": {"id": bc_id, "name": bc_name, "key": bc_key_value},
                            "aggregate": {"id": agg_id, "name": agg_name_val, "key": agg_key},
                            "llm_ms": llm_ms,
                            "response": resp_dump if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_dump, max_list=5000, max_dict_items=5000),
                        },
                    )

                rows = _dedupe_rows(_extract_rows_from_response(resp, parent_id_by_key))

            if rows:
                res = ctx.client.upsert_properties_bulk(rows)
                upserted = int((res or {}).get("upserted") or 0)
                total_upserted += upserted
                total_targets += 1

                SmartLogger.log(
                    "INFO",
                    "Properties upserted (aggregate batch)",
                    category="ingestion.neo4j.properties.upsert",
                    params={
                        "session_id": ctx.session.id,
                        "scope": "aggregate_batch",
                        "bc": {"id": bc_id, "name": bc_name, "key": bc_key_value},
                        "aggregate": {"id": agg_id, "name": agg_name_val, "key": agg_key},
                        "rows": len(rows),
                        "upserted": upserted,
                    },
                )

                yield ProgressEvent(
                    phase=IngestionPhase.GENERATING_PROPERTIES,
                    message=f"Property 생성/업데이트: {agg_name_val}",
                    progress=87,
                    data={"scope": "aggregate_batch", "aggregateId": agg_id, "upserted": upserted, "rows": len(rows)},
                )
                await asyncio.sleep(0.05)

    # ---------------------------------------------------------------------
    # B) BC-scoped batch: ReadModels
    # ---------------------------------------------------------------------
    for bc in ctx.bounded_contexts or []:
        # Handle both dict and object formats
        bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
        bc_key = bc.get("key") if isinstance(bc, dict) else getattr(bc, "key", None)
        bc_name = bc.get("name") if isinstance(bc, dict) else getattr(bc, "name", None)
        bc_key_value = (str(bc_key).strip() if bc_key else "") or build_bc_key(str(bc_name) if bc_name else "")
        rms = ctx.readmodels_by_bc.get(bc_id, []) or []
        if not rms:
            continue

        rm_lines: list[str] = []
        parent_id_by_key_rm: dict[tuple[str, str], str] = {}
        for rm in rms:
            rm_key = str((rm or {}).get("key") or "").strip()
            rm_id = str((rm or {}).get("id") or "").strip()
            if not rm_key or not rm_id:
                continue
            parent_id_by_key_rm[("ReadModel", rm_key)] = rm_id
            rm_lines.append(
                f"- key: {rm_key}\n"
                f"  id: {rm_id}\n"
                f"  name: {str((rm or {}).get('name') or '')}\n"
                f"  description: {str((rm or {}).get('description') or '')}"
            )
        readmodels_text = "\n".join(rm_lines) if rm_lines else "None"
        if readmodels_text == "None":
            continue

        prompt = GENERATE_PROPERTIES_READMODELS_BATCH_PROMPT.format(
            bc_id=bc_id,
            bc_key=bc_key_value,
            bc_name=bc_name or "",
            bc_description=(bc.get("description") if isinstance(bc, dict) else getattr(bc, "description", None)) or "",
            readmodels=readmodels_text,
            known_aggregate_keys=known_aggregate_keys_text,
        )
        display_lang = getattr(ctx, "display_language", "ko") or "ko"
        prompt += (
            "\n\nFor each Property output displayName: a short UI label in Korean (e.g. '주문 번호', '상태')."
            if display_lang == "ko"
            else "\n\nFor each Property output displayName: a short UI label in English (e.g. 'Order ID', 'Status')."
        )
        structured_llm = ctx.llm.with_structured_output(PropertyBatch)
        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "Ingestion: generate properties (readmodels batch) - LLM invoke starting.",
                category="ingestion.llm.generate_properties.start",
                params={
                    "session_id": ctx.session.id,
                    "llm": {"provider": provider, "model": model},
                    "scope": "readmodels_batch",
                    "bc": {"id": bc_id, "name": bc_name, "key": bc_key_value},
                    "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                    "system_prompt": SYSTEM_PROMPT,
                },
            )

        t_llm0 = time.perf_counter()
        try:
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    structured_llm.invoke,
                    [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
                ),
                timeout=300.0,
            )
        except asyncio.TimeoutError:
            SmartLogger.log(
                "ERROR",
                "Property generation timed out (300s) - readmodels batch",
                category="ingestion.workflow.properties.timeout",
                params={"session_id": ctx.session.id, "scope": "readmodels_batch", "bc_id": bc_id},
            )
            continue
        except Exception as e:
            SmartLogger.log(
                "WARNING",
                "Property generation failed (LLM) - readmodels batch",
                category="ingestion.workflow.properties",
                params={"session_id": ctx.session.id, "scope": "readmodels_batch", "bc_id": bc_id, "error": str(e)},
            )
            continue
        llm_ms = int((time.perf_counter() - t_llm0) * 1000)

        if AI_AUDIT_LOG_ENABLED:
            try:
                resp_dump = resp.model_dump() if hasattr(resp, "model_dump") else resp.dict()
            except Exception:
                resp_dump = {"__type__": type(resp).__name__, "__repr__": repr(resp)[:1000]}
            SmartLogger.log(
                "INFO",
                "Ingestion: generate properties (readmodels batch) - LLM invoke completed.",
                category="ingestion.llm.generate_properties.done",
                params={
                    "session_id": ctx.session.id,
                    "llm": {"provider": provider, "model": model},
                    "scope": "readmodels_batch",
                    "bc": {"id": bc_id, "name": bc_name, "key": bc_key_value},
                    "llm_ms": llm_ms,
                    "response": resp_dump if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_dump, max_list=5000, max_dict_items=5000),
                },
            )

        rows = _dedupe_rows(_extract_rows_from_response(resp, parent_id_by_key_rm))
        if rows:
            res = ctx.client.upsert_properties_bulk(rows)
            upserted = int((res or {}).get("upserted") or 0)
            total_upserted += upserted
            total_targets += 1

            SmartLogger.log(
                "INFO",
                "Properties upserted (readmodels batch)",
                category="ingestion.neo4j.properties.upsert",
                params={
                    "session_id": ctx.session.id,
                    "scope": "readmodels_batch",
                    "bc": {"id": bc_id, "name": bc_name, "key": bc_key_value},
                    "readmodels": len(parent_id_by_key_rm),
                    "rows": len(rows),
                    "upserted": upserted,
                },
            )

            yield ProgressEvent(
                phase=IngestionPhase.GENERATING_PROPERTIES,
                message=f"ReadModel Property 생성/업데이트: {getattr(bc, 'name', '')}",
                progress=88,
                data={"scope": "readmodels_batch", "bcId": bc_id, "upserted": upserted, "rows": len(rows)},
            )
            await asyncio.sleep(0.05)

    SmartLogger.log(
        "INFO",
        "Property generation phase completed",
        category="ingestion.workflow.properties.done",
        params={"session_id": ctx.session.id, "targets": total_targets, "upserted": total_upserted},
    )


