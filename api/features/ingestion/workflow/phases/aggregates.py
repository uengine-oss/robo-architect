from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
)
from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.event_storming.nodes import AggregateList
from api.features.ingestion.event_storming.prompts import EXTRACT_AGGREGATES_PROMPT, SYSTEM_PROMPT
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger


async def extract_aggregates_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase 4: extract aggregates per BC and persist them.
    """
    yield ProgressEvent(phase=IngestionPhase.EXTRACTING_AGGREGATES, message="Aggregate 추출 중...", progress=45)

    all_aggregates: dict[str, Any] = {}
    progress_per_bc = 10 // max(len(ctx.bounded_contexts), 1)

    for bc_idx, bc in enumerate(ctx.bounded_contexts):
        # Legacy field used only for prompt text; keep stable without prefix-based ids.
        bc_id_short = (getattr(bc, "name", "") or "").strip()
        breakdowns_text = f"User Stories: {', '.join(bc.user_story_ids)}"

        # Collect existing aggregates from previously processed BCs for reference validation
        existing_aggregates_text = ""
        all_existing_aggregate_names = set()
        for prev_bc_idx in range(bc_idx):
            prev_bc = ctx.bounded_contexts[prev_bc_idx]
            prev_aggregates = all_aggregates.get(prev_bc.id, [])
            if prev_aggregates:
                agg_names = [getattr(agg, "name", "") for agg in prev_aggregates if getattr(agg, "name", None)]
                if agg_names:
                    existing_aggregates_text += f"  - {prev_bc.name}: {', '.join(agg_names)}\n"
                    all_existing_aggregate_names.update(agg_names)
        
        if not existing_aggregates_text:
            existing_aggregates_text = "  (No aggregates have been extracted from other Bounded Contexts yet.)"
        else:
            existing_aggregates_text = "The following Aggregates already exist in other Bounded Contexts and can be referenced:\n" + existing_aggregates_text

        prompt = EXTRACT_AGGREGATES_PROMPT.format(
            bc_name=bc.name,
            bc_id=bc.id,
            bc_id_short=bc_id_short,
            bc_description=bc.description,
            breakdowns=breakdowns_text,
            existing_aggregates=existing_aggregates_text,
        )

        structured_llm = ctx.llm.with_structured_output(AggregateList)

        provider, model = get_llm_provider_model()
        if AI_AUDIT_LOG_ENABLED:
            SmartLogger.log(
                "INFO",
                "Ingestion: extract aggregates - LLM invoke starting.",
                category="ingestion.llm.extract_aggregates.start",
                params={
                    "session_id": ctx.session.id,
                    "llm": {"provider": provider, "model": model},
                    "bc": {"id": bc.id, "name": bc.name},
                    "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                    "system_prompt": SYSTEM_PROMPT,
                }
            )

        t_llm0 = time.perf_counter()
        agg_response = structured_llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
        llm_ms = int((time.perf_counter() - t_llm0) * 1000)

        if AI_AUDIT_LOG_ENABLED:
            try:
                resp_dump = agg_response.model_dump() if hasattr(agg_response, "model_dump") else agg_response.dict()
            except Exception:
                resp_dump = {"__type__": type(agg_response).__name__, "__repr__": repr(agg_response)[:1000]}
            aggs = getattr(agg_response, "aggregates", []) or []
            SmartLogger.log(
                "INFO",
                "Ingestion: extract aggregates - LLM invoke completed.",
                category="ingestion.llm.extract_aggregates.done",
                params={
                    "session_id": ctx.session.id,
                    "llm": {"provider": provider, "model": model},
                    "bc": {"id": bc.id, "name": bc.name},
                    "llm_ms": llm_ms,
                    "result": {
                        "aggregate_ids": summarize_for_log([getattr(a, "id", None) for a in aggs]),
                        "response": resp_dump if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_dump, max_list=5000, max_dict_items=5000),
                    },
                }
            )

        aggregates = agg_response.aggregates
        
        # Validate and fix Value Object references
        # Collect all existing aggregate names (from previously processed BCs and current BC)
        all_existing_aggregate_names_for_validation = set(all_existing_aggregate_names)
        for agg in aggregates or []:
            agg_name = getattr(agg, "name", None)
            if agg_name:
                all_existing_aggregate_names_for_validation.add(agg_name)
        
        # Validate and remove invalid references
        validation_warnings = []
        for agg in aggregates or []:
            if hasattr(agg, "value_objects") and agg.value_objects:
                for vo in agg.value_objects:
                    ref_name = getattr(vo, "referenced_aggregate_name", None)
                    if ref_name and ref_name not in all_existing_aggregate_names_for_validation:
                        # Remove invalid reference
                        validation_warnings.append(
                            f"Removed invalid reference: {agg.name}.{getattr(vo, 'name', 'unknown')} → {ref_name} (Aggregate does not exist)"
                        )
                        try:
                            vo.referenced_aggregate_name = None
                        except Exception:
                            pass
                        SmartLogger.log(
                            "WARNING",
                            f"Removed invalid Aggregate reference in {bc.name}.{agg.name}",
                            category="ingestion.workflow.aggregates.reference_validation.auto_fix",
                            params={
                                "session_id": ctx.session.id,
                                "bc_id": bc.id,
                                "bc_name": bc.name,
                                "aggregate_name": getattr(agg, "name", None),
                                "vo_name": getattr(vo, "name", None),
                                "referenced_aggregate_name": ref_name,
                            },
                        )
        
        if validation_warnings:
            SmartLogger.log(
                "INFO",
                f"Auto-fixed {len(validation_warnings)} invalid Aggregate references",
                category="ingestion.workflow.aggregates.reference_validation.auto_fix_summary",
                params={
                    "session_id": ctx.session.id,
                    "bc_id": bc.id,
                    "bc_name": bc.name,
                    "warnings": validation_warnings,
                },
            )
        
        all_aggregates[bc.id] = aggregates

        SmartLogger.log(
            "INFO",
            "Aggregates extracted",
            category="ingestion.workflow.aggregates",
            params={
                "session_id": ctx.session.id,
                "bc_id": bc.id,
                "bc_name": bc.name,
                "aggregates": summarize_for_log(aggregates, max_list=5000, max_dict_items=5000),
            },
        )

        for agg in aggregates:
            # Validate aggregate has required fields
            agg_name = getattr(agg, "name", None)
            if not agg_name:
                SmartLogger.log(
                    "WARNING",
                    "Skipping aggregate without name",
                    category="ingestion.workflow.aggregates.validation",
                    params={"session_id": ctx.session.id, "bc_id": bc.id, "aggregate": str(agg)[:200]},
                )
                continue
            
            # Convert enumerations and value_objects to dict format for Neo4j
            enum_list = []
            try:
                if hasattr(agg, "enumerations") and agg.enumerations:
                    for e in agg.enumerations:
                        if isinstance(e, dict):
                            enum_name = e.get("name")
                            if enum_name:  # Only add if name exists
                                enum_list.append({
                                    "name": str(enum_name),
                                    "alias": e.get("alias"),
                                    "items": e.get("items", [])
                                })
                        else:
                            # Handle Pydantic model
                            enum_name = getattr(e, "name", None)
                            if enum_name:  # Only add if name exists
                                enum_list.append({
                                    "name": str(enum_name),
                                    "alias": getattr(e, "alias", None),
                                    "items": getattr(e, "items", []) or []
                                })
            except Exception as e:
                SmartLogger.log(
                    "WARNING",
                    "Failed to process enumerations for aggregate",
                    category="ingestion.workflow.aggregates.enumerations",
                    params={"session_id": ctx.session.id, "aggregate_name": agg_name, "error": str(e)},
                )
            
            vo_list = []
            try:
                if hasattr(agg, "value_objects") and agg.value_objects:
                    for vo in agg.value_objects:
                        if isinstance(vo, dict):
                            vo_name = vo.get("name")
                            if vo_name:  # Only add if name exists
                                # Convert fields to dict format
                                fields_list = vo.get("fields", [])
                                fields_dicts = []
                                for field in fields_list:
                                    if isinstance(field, dict):
                                        fields_dicts.append(field)
                                    else:
                                        # Handle Pydantic ValueObjectField model
                                        fields_dicts.append({
                                            "name": getattr(field, "name", ""),
                                            "type": getattr(field, "type", "")
                                        })
                                vo_list.append({
                                    "name": str(vo_name),
                                    "alias": vo.get("alias"),
                                    "referenced_aggregate_name": vo.get("referenced_aggregate_name"),
                                    "referenced_aggregate_field": vo.get("referenced_aggregate_field"),
                                    "fields": fields_dicts
                                })
                        else:
                            # Handle Pydantic model
                            vo_name = getattr(vo, "name", None)
                            if vo_name:  # Only add if name exists
                                # Convert fields to dict format
                                fields_list = getattr(vo, "fields", []) or []
                                fields_dicts = []
                                for field in fields_list:
                                    if isinstance(field, dict):
                                        fields_dicts.append(field)
                                    else:
                                        # Handle Pydantic ValueObjectField model
                                        fields_dicts.append({
                                            "name": getattr(field, "name", ""),
                                            "type": getattr(field, "type", "")
                                        })
                                vo_list.append({
                                    "name": str(vo_name),
                                    "alias": getattr(vo, "alias", None),
                                    "referenced_aggregate_name": getattr(vo, "referenced_aggregate_name", None),
                                    "referenced_aggregate_field": getattr(vo, "referenced_aggregate_field", None),
                                    "fields": fields_dicts
                                })
            except Exception as e:
                SmartLogger.log(
                    "WARNING",
                    "Failed to process value_objects for aggregate",
                    category="ingestion.workflow.aggregates.value_objects",
                    params={"session_id": ctx.session.id, "aggregate_name": agg_name, "error": str(e)},
                )
            
            try:
                root_entity = getattr(agg, "root_entity", None) or agg_name
                invariants = getattr(agg, "invariants", None) or []
                
                created_agg = ctx.client.create_aggregate(
                    name=agg_name,
                    bc_id=bc.id,
                    root_entity=root_entity,
                    invariants=invariants,
                    enumerations=enum_list if enum_list else None,
                    value_objects=vo_list if vo_list else None,
                )
            except Exception as e:
                SmartLogger.log(
                    "ERROR",
                    "Failed to create aggregate in Neo4j",
                    category="ingestion.workflow.aggregates.create",
                    params={
                        "session_id": ctx.session.id,
                        "aggregate_name": agg_name,
                        "bc_id": bc.id,
                        "error": str(e),
                        "enum_count": len(enum_list),
                        "vo_count": len(vo_list),
                    },
                )
                raise
            # Overwrite LLM-proposed id with UUID from DB (canonical)
            try:
                agg.id = created_agg.get("id")
            except Exception:
                pass
            # Preserve natural key (needed by downstream property generation prompts)
            try:
                agg.key = created_agg.get("key")
            except Exception:
                pass

            # Traceability: UserStory -> Aggregate
            for us_id in getattr(agg, "user_story_ids", []) or []:
                try:
                    ctx.client.link_user_story_to_aggregate(us_id, created_agg.get("id"))
                except Exception:
                    pass

            yield ProgressEvent(
                phase=IngestionPhase.EXTRACTING_AGGREGATES,
                message=f"Aggregate 생성: {agg.name}",
                progress=45 + progress_per_bc * bc_idx,
                data={
                    "type": "Aggregate",
                    "object": {"id": created_agg.get("id"), "name": agg.name, "type": "Aggregate", "parentId": bc.id},
                },
            )
            await asyncio.sleep(0.15)

    ctx.aggregates_by_bc = all_aggregates


