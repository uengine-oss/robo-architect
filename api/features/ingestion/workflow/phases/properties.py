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
from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
    get_llm_provider_model,
)
from api.platform.keys import bc_key as build_bc_key
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


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

            prompt = GENERATE_PROPERTIES_AGGREGATE_BATCH_PROMPT.format(
                bc_id=bc_id,
                bc_key=bc_key_value,
                bc_name=bc_name or "",
                bc_description=(bc.get("description") if isinstance(bc, dict) else getattr(bc, "description", None)) or "",
                aggregate_id=agg_id,
                aggregate_key=agg_key,
                aggregate_name=(agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", None)) or "",
                aggregate_root_entity=(agg.get("root_entity") if isinstance(agg, dict) else getattr(agg, "root_entity", None)) or "",
                aggregate_invariants=summarize_for_log((agg.get("invariants") if isinstance(agg, dict) else getattr(agg, "invariants", None)) or [], max_list=200),
                aggregate_description=(agg.get("description") if isinstance(agg, dict) else getattr(agg, "description", None)) or "",
                commands=commands_text,
                events=events_text,
                known_aggregate_keys=known_aggregate_keys_text,
            )
            display_lang = getattr(ctx, "display_language", "ko") or "ko"
            prompt += (
                "\n\n10) For each Property output displayName: a short UI label in Korean (e.g. '주문 번호', '고객명')."
                if display_lang == "ko"
                else "\n\n10) For each Property output displayName: a short UI label in English (e.g. 'Order ID', 'Customer Name')."
            )

            structured_llm = ctx.llm.with_structured_output(PropertyBatch)
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
                        "aggregate": {"id": agg_id, "name": (agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", None)), "key": agg_key},
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
                        "aggregate": {"id": agg_id, "name": (agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", None)), "key": agg_key},
                        "llm_ms": llm_ms,
                        "response": resp_dump if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_dump, max_list=5000, max_dict_items=5000),
                    },
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

            rows = _dedupe_rows(rows)
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
                        "aggregate": {"id": agg_id, "name": (agg.get("name") if isinstance(agg, dict) else getattr(agg, "name", None)), "key": agg_key},
                        "rows": len(rows),
                        "upserted": upserted,
                    },
                )

                yield ProgressEvent(
                    phase=IngestionPhase.GENERATING_PROPERTIES,
                    message=f"Property 생성/업데이트: {getattr(agg, 'name', '')}",
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

        rows: list[dict[str, Any]] = []
        for parent in getattr(resp, "parents", []) or []:
            ptype = str(getattr(parent, "parentType", "") or "").strip()
            pkey = str(getattr(parent, "parentKey", "") or "").strip()
            pid = parent_id_by_key_rm.get((ptype, pkey))
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

        rows = _dedupe_rows(rows)
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


