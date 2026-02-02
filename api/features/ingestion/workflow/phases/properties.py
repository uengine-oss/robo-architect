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
        bc_key_value = (getattr(bc, "key", None) or "").strip() or build_bc_key(getattr(bc, "name", "") or "")
        for agg in ctx.aggregates_by_bc.get(bc.id, []) or []:
            agg_key = (getattr(agg, "key", None) or "").strip()
            agg_id = (getattr(agg, "id", None) or "").strip()
            if not agg_key or not agg_id:
                continue

            commands = ctx.commands_by_agg.get(agg.id, []) or []
            events = ctx.events_by_agg.get(agg.id, []) or []

            command_lines: list[str] = []
            for cmd in commands:
                cmd_key = (getattr(cmd, "key", None) or "").strip()
                cmd_id = (getattr(cmd, "id", None) or "").strip()
                if not cmd_key or not cmd_id:
                    continue
                cmd_category = getattr(cmd, "category", None) or ""
                cmd_input_schema = getattr(cmd, "inputSchema", None) or ""
                command_lines.append(
                    f"- key: {cmd_key}\n"
                    f"  id: {cmd_id}\n"
                    f"  name: {getattr(cmd, 'name', '')}\n"
                    f"  actor: {getattr(cmd, 'actor', '')}\n"
                    f"  category: {cmd_category}\n"
                    f"  inputSchema: {cmd_input_schema}\n"
                    f"  description: {getattr(cmd, 'description', '')}"
                )
            commands_text = "\n".join(command_lines) if command_lines else "None"

            event_lines: list[str] = []
            for evt in events:
                evt_key = (getattr(evt, "key", None) or "").strip()
                evt_id = (getattr(evt, "id", None) or "").strip()
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
                bc_id=bc.id,
                bc_key=bc_key_value,
                bc_name=getattr(bc, "name", "") or "",
                bc_description=getattr(bc, "description", "") or "",
                aggregate_id=agg_id,
                aggregate_key=agg_key,
                aggregate_name=getattr(agg, "name", "") or "",
                aggregate_root_entity=getattr(agg, "root_entity", "") or "",
                aggregate_invariants=summarize_for_log(getattr(agg, "invariants", []) or [], max_list=200),
                aggregate_description=getattr(agg, "description", "") or "",
                commands=commands_text,
                events=events_text,
                known_aggregate_keys=known_aggregate_keys_text,
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
                        "bc": {"id": bc.id, "name": getattr(bc, "name", None), "key": bc_key_value},
                        "aggregate": {"id": agg_id, "name": getattr(agg, "name", None), "key": agg_key},
                        "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                        "system_prompt": SYSTEM_PROMPT,
                    },
                )

            t_llm0 = time.perf_counter()
            try:
                resp = structured_llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
            except Exception as e:
                SmartLogger.log(
                    "WARNING",
                    "Property generation failed (LLM) - aggregate batch",
                    category="ingestion.workflow.properties",
                    params={
                        "session_id": ctx.session.id,
                        "scope": "aggregate_batch",
                        "bc_id": bc.id,
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
                        "bc": {"id": bc.id, "name": getattr(bc, "name", None), "key": bc_key_value},
                        "aggregate": {"id": agg_id, "name": getattr(agg, "name", None), "key": agg_key},
                        "llm_ms": llm_ms,
                        "response": resp_dump if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_dump, max_list=5000, max_dict_items=5000),
                    },
                )

            # Build parentKey -> parentId map for this scope
            parent_id_by_key: dict[tuple[str, str], str] = {("Aggregate", agg_key): agg_id}
            for cmd in commands:
                ck = (getattr(cmd, "key", None) or "").strip()
                cid = (getattr(cmd, "id", None) or "").strip()
                if ck and cid:
                    parent_id_by_key[("Command", ck)] = cid
            for evt in events:
                ek = (getattr(evt, "key", None) or "").strip()
                eid = (getattr(evt, "id", None) or "").strip()
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
                    rows.append(
                        {
                            "parentType": ptype,
                            "parentId": pid,
                            "name": name,
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
                        "bc": {"id": bc.id, "name": getattr(bc, "name", None), "key": bc_key_value},
                        "aggregate": {"id": agg_id, "name": getattr(agg, "name", None), "key": agg_key},
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
        bc_key_value = (getattr(bc, "key", None) or "").strip() or build_bc_key(getattr(bc, "name", "") or "")
        rms = ctx.readmodels_by_bc.get(bc.id, []) or []
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
            bc_id=bc.id,
            bc_key=bc_key_value,
            bc_name=getattr(bc, "name", "") or "",
            bc_description=getattr(bc, "description", "") or "",
            readmodels=readmodels_text,
            known_aggregate_keys=known_aggregate_keys_text,
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
                    "bc": {"id": bc.id, "name": getattr(bc, "name", None), "key": bc_key_value},
                    "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                    "system_prompt": SYSTEM_PROMPT,
                },
            )

        t_llm0 = time.perf_counter()
        try:
            resp = structured_llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
        except Exception as e:
            SmartLogger.log(
                "WARNING",
                "Property generation failed (LLM) - readmodels batch",
                category="ingestion.workflow.properties",
                params={"session_id": ctx.session.id, "scope": "readmodels_batch", "bc_id": bc.id, "error": str(e)},
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
                    "bc": {"id": bc.id, "name": getattr(bc, "name", None), "key": bc_key_value},
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
                rows.append(
                    {
                        "parentType": ptype,
                        "parentId": pid,
                        "name": name,
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
                    "bc": {"id": bc.id, "name": getattr(bc, "name", None), "key": bc_key_value},
                    "readmodels": len(parent_id_by_key_rm),
                    "rows": len(rows),
                    "upserted": upserted,
                },
            )

            yield ProgressEvent(
                phase=IngestionPhase.GENERATING_PROPERTIES,
                message=f"ReadModel Property 생성/업데이트: {getattr(bc, 'name', '')}",
                progress=88,
                data={"scope": "readmodels_batch", "bcId": bc.id, "upserted": upserted, "rows": len(rows)},
            )
            await asyncio.sleep(0.05)

    SmartLogger.log(
        "INFO",
        "Property generation phase completed",
        category="ingestion.workflow.properties.done",
        params={"session_id": ctx.session.id, "targets": total_targets, "upserted": total_upserted},
    )


