from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from api.platform.env import get_llm_provider_model
from api.platform.observability.request_logging import sha256_text, summarize_for_log
from api.platform.observability.smart_logger import SmartLogger
from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
)

from .user_story_planning_contracts import PlanningScope, ProposedObject, UserStoryPlanningState
from .user_story_planning_runtime import generate_id, get_llm, get_neo4j_driver, get_neo4j_session


def analyze_story_node(state: UserStoryPlanningState) -> Dict[str, Any]:
    llm = get_llm()

    prompt = f"""Analyze this user story and extract domain modeling information.

User Story:
- As a: {state.role}
- I want to: {state.action}
- So that: {state.benefit}

Extract:
1. Primary intent
2. Domain keywords (nouns)
3. Action verbs (commands)
4. State changes (events, past tense)

Respond in JSON:
{{
  "intent": "...",
  "domain_keywords": ["..."],
  "action_verbs": ["..."],
  "state_changes": ["..."]
}}"""

    provider, model = get_llm_provider_model()
    system_msg = "You are a DDD expert analyzing user stories for domain modeling."

    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "User story planning (analyze): LLM invoke starting.",
            category="agent.user_story_graph.analyze.llm.start",
            params={
                "llm": {"provider": provider, "model": model},
                "inputs": {
                    "role": state.role,
                    "action": state.action,
                    "benefit": state.benefit,
                    "target_bc_id": state.target_bc_id,
                    "auto_generate": state.auto_generate,
                },
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

    import json

    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())
        if AI_AUDIT_LOG_ENABLED:
            resp_text = getattr(response, "content", "") or ""
            SmartLogger.log(
                "INFO",
                "User story planning (analyze): LLM invoke completed.",
                category="agent.user_story_graph.analyze.llm.done",
                params={
                    "llm": {"provider": provider, "model": model},
                    "llm_ms": llm_ms,
                    "response_len": len(resp_text),
                    "response_sha256": sha256_text(resp_text),
                    "response": resp_text if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_text),
                    "parsed": {
                        "intent_preview": (result.get("intent") or "")[:200],
                        "domain_keywords": (result.get("domain_keywords") or [])[:30],
                        "action_verbs": (result.get("action_verbs") or [])[:30],
                    },
                }
            )
        return {
            "story_intent": result.get("intent", ""),
            "domain_keywords": result.get("domain_keywords", []),
            "action_verbs": result.get("action_verbs", []),
        }
    except Exception as e:
        if AI_AUDIT_LOG_ENABLED:
            resp_text = getattr(response, "content", "") or ""
            SmartLogger.log(
                "WARNING",
                "User story planning (analyze): failed to parse LLM response; using fallback.",
                category="agent.user_story_graph.analyze.llm.parse_error",
                params={
                    "llm": {"provider": provider, "model": model},
                    "llm_ms": llm_ms,
                    "error": {"type": type(e).__name__, "message": str(e)},
                    "response_len": len(resp_text),
                    "response_sha256": sha256_text(resp_text),
                    "response_preview": resp_text[:1500],
                }
            )
        return {
            "story_intent": state.action,
            "domain_keywords": [state.action.split()[0]] if state.action else [],
            "action_verbs": [],
            "error": str(e),
        }


def find_matching_bc_node(state: UserStoryPlanningState) -> Dict[str, Any]:
    if state.target_bc_id:
        driver = get_neo4j_driver()
        try:
            with get_neo4j_session(driver) as session:
                result = session.run(
                    """
                    MATCH (bc:BoundedContext {id: $bc_id})
                    RETURN bc.id as id, bc.name as name
                    """,
                    bc_id=state.target_bc_id,
                )
                record = result.single()
                if record:
                    return {
                        "scope": PlanningScope.EXISTING_BC,
                        "scope_reasoning": f"Using specified BC: {record['name']}",
                        "matched_bc_id": record["id"],
                        "matched_bc_name": record["name"],
                    }
        finally:
            driver.close()

    driver = get_neo4j_driver()
    keywords = state.domain_keywords + state.action_verbs

    try:
        with get_neo4j_session(driver) as session:
            result = session.run(
                """
                UNWIND $keywords as keyword
                MATCH (bc:BoundedContext)
                OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
                WITH bc, agg, keyword,
                     CASE
                         WHEN toLower(bc.name) CONTAINS toLower(keyword) THEN 3
                         WHEN toLower(coalesce(bc.description, '')) CONTAINS toLower(keyword) THEN 2
                         WHEN agg IS NOT NULL AND toLower(agg.name) CONTAINS toLower(keyword) THEN 1
                         ELSE 0
                     END as score
                WHERE score > 0
                WITH bc, sum(score) as totalScore
                ORDER BY totalScore DESC
                LIMIT 1
                RETURN bc.id as id, bc.name as name, totalScore as score
                """,
                keywords=keywords,
            )
            record = result.single()

            if record and record["score"] >= 2:
                related_result = session.run(
                    """
                    MATCH (bc:BoundedContext {id: $bc_id})
                    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
                    OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
                    OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
                    RETURN
                        collect(DISTINCT {id: agg.id, name: agg.name, type: 'Aggregate'}) as aggregates,
                        collect(DISTINCT {id: cmd.id, name: cmd.name, type: 'Command'}) as commands,
                        collect(DISTINCT {id: evt.id, name: evt.name, type: 'Event'}) as events
                    """,
                    bc_id=record["id"],
                )
                related_record = related_result.single()

                related_objects: list[dict[str, Any]] = []
                if related_record:
                    for agg in related_record["aggregates"]:
                        if agg.get("id"):
                            related_objects.append(dict(agg))
                    for cmd in related_record["commands"]:
                        if cmd.get("id"):
                            related_objects.append(dict(cmd))
                    for evt in related_record["events"]:
                        if evt.get("id"):
                            related_objects.append(dict(evt))

                return {
                    "scope": PlanningScope.EXISTING_BC,
                    "scope_reasoning": f"Found matching BC '{record['name']}' based on keywords: {keywords}",
                    "matched_bc_id": record["id"],
                    "matched_bc_name": record["name"],
                    "related_objects": related_objects,
                }

            return {
                "scope": PlanningScope.NEW_BC,
                "scope_reasoning": f"No matching BC found for keywords: {keywords}. Proposing new BC.",
                "matched_bc_id": None,
                "matched_bc_name": None,
                "related_objects": [],
            }
    finally:
        driver.close()


def generate_objects_node(state: UserStoryPlanningState) -> Dict[str, Any]:
    if not state.auto_generate:
        return {
            "proposed_objects": [],
            "plan_summary": "Auto-generation disabled. User story will be created without related objects.",
        }

    llm = get_llm()

    related_text = (
        "\n".join([f"- {obj.get('type', 'Unknown')}: {obj.get('name', '?')}" for obj in state.related_objects])
        if state.related_objects
        else "None"
    )

    bc_context = (
        f"Target BC: {state.matched_bc_name} (ID: {state.matched_bc_id})"
        if state.scope == PlanningScope.EXISTING_BC
        else "Need to create a new Bounded Context"
    )

    prompt = f"""Generate domain objects for this new User Story.

## User Story
- As a: {state.role}
- I want to: {state.action}
- So that: {state.benefit}

## Analysis
- Intent: {state.story_intent}
- Domain Keywords: {state.domain_keywords}
- Action Verbs: {state.action_verbs}

## Context
{bc_context}

## Existing Related Objects in this BC
{related_text}

## Task
Generate objects:
1) If new BC is required, propose BC first
2) Aggregate
3) Command
4) Event (past tense)

Respond in JSON:
{{
  "summary": "...",
  "objects": [
    {{
      "action": "create",
      "targetType": "BoundedContext|Aggregate|Command|Event",
      "targetId": "ID",
      "targetName": "Name",
      "targetBcId": "BC-ID",
      "targetBcName": "BC Name",
      "description": "...",
      "reason": "...",
      "actor": "...",
      "aggregateId": "...",
      "commandId": "..."
    }}
  ]
}}"""

    provider, model = get_llm_provider_model()
    system_msg = (
        "You are a DDD expert generating domain objects.\n"
        "- Aggregate names: nouns (Order)\n"
        "- Command names: verbs (PlaceOrder)\n"
        "- Event names: past tense (OrderPlaced)\n"
        "- Reuse existing objects when appropriate"
    )

    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "User story planning (generate objects): LLM invoke starting.",
            category="agent.user_story_graph.generate_objects.llm.start",
            params={
                "llm": {"provider": provider, "model": model},
                "scope": state.scope.value if hasattr(state.scope, "value") else str(state.scope),
                "matched_bc": {"id": state.matched_bc_id, "name": state.matched_bc_name},
                "related_objects_count": len(state.related_objects or []),
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

    import json

    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())
        proposed_objects: list[ProposedObject] = []
        for obj in result.get("objects", []):
            proposed_objects.append(
                ProposedObject(
                    action=obj.get("action", "create"),
                    targetType=obj.get("targetType", "Unknown"),
                    targetId=obj.get("targetId", generate_id("OBJ")),
                    targetName=obj.get("targetName", ""),
                    targetBcId=obj.get("targetBcId") or state.matched_bc_id,
                    targetBcName=obj.get("targetBcName") or state.matched_bc_name,
                    description=obj.get("description", ""),
                    reason=obj.get("reason", ""),
                    connectionType=obj.get("connectionType"),
                    sourceId=obj.get("sourceId"),
                    actor=obj.get("actor"),
                    aggregateId=obj.get("aggregateId"),
                    commandId=obj.get("commandId"),
                )
            )

        if AI_AUDIT_LOG_ENABLED:
            resp_text = getattr(response, "content", "") or ""
            SmartLogger.log(
                "INFO",
                "User story planning (generate objects): LLM invoke completed.",
                category="agent.user_story_graph.generate_objects.llm.done",
                params={
                    "llm": {"provider": provider, "model": model},
                    "llm_ms": llm_ms,
                    "response_len": len(resp_text),
                    "response_sha256": sha256_text(resp_text),
                    "response": resp_text if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_text),
                    "summary_preview": (result.get("summary") or "")[:300],
                    "objects_count": len(proposed_objects),
                    "objects": summarize_for_log([o.dict() for o in proposed_objects]),
                }
            )

        return {"proposed_objects": proposed_objects, "plan_summary": result.get("summary", "")}
    except Exception as e:
        if AI_AUDIT_LOG_ENABLED:
            resp_text = getattr(response, "content", "") or ""
            SmartLogger.log(
                "WARNING",
                "User story planning (generate objects): failed to parse LLM response; returning empty plan.",
                category="agent.user_story_graph.generate_objects.llm.parse_error",
                params={
                    "llm": {"provider": provider, "model": model},
                    "llm_ms": llm_ms,
                    "error": {"type": type(e).__name__, "message": str(e)},
                    "response_len": len(resp_text),
                    "response_sha256": sha256_text(resp_text),
                    "response_preview": resp_text[:1500],
                }
            )
        return {"proposed_objects": [], "plan_summary": f"Error generating objects: {str(e)}", "error": str(e)}


