from __future__ import annotations

import json
import time
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.event_storming.neo4j_ops.gwt import GWTOps
from api.features.ingestion.event_storming.prompts import SYSTEM_PROMPT
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
    get_llm_provider_model,
)
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

GENERATE_GWT_PROMPT_COMMAND = """Generate Given/When/Then (GWT) test cases for a Command to support BDD-style test scenarios.

<command>
Name: {command_name}
Description: {command_description}
Properties: {command_properties}
</command>

<aggregate>
Name: {aggregate_name}
Properties: {aggregate_properties}
</aggregate>

<event>
Name: {event_name}
Description: {event_description}
Properties: {event_properties}
</event>

For this Command, generate multiple GWT test cases (typically 2-5 test cases covering different scenarios):
- **scenarioDescription:** A brief description of the business flow/scenario this test case represents (e.g., "Happy path: User successfully creates an order with valid items")
- **given:** Reference the Command itself. Include `name` (e.g., "Command: {command_name}") and optional `description`. The `fieldValues` dictionary should map property names from the Command to realistic test values based on the properties listed above.
- **when:** Reference the Aggregate that handles this Command. Include `name` (e.g., "Aggregate: {aggregate_name}") and optional `description`. The `fieldValues` dictionary should map property names from the Aggregate to realistic test values based on the properties listed above.
- **then:** Reference the Event emitted by this Command. Include `name` (e.g., "Event: {event_name}") and optional `description`. The `fieldValues` dictionary should map property names from the Event to realistic test values based on the properties listed above.

Return a JSON array with multiple test cases:
[
  {{
    "scenarioDescription": "Brief description of this test case's business flow",
    "given": {{
      "name": "Command: {command_name}",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue1", ...}}
    }},
    "when": {{
      "name": "Aggregate: {aggregate_name}",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue1", ...}}
    }},
    "then": {{
      "name": "Event: {event_name}",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue1", ...}}
    }}
  }},
  {{
    "scenarioDescription": "Brief description of this test case's business flow",
    "given": {{
      "name": "Command: {command_name}",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue2", ...}}
    }},
    "when": {{
      "name": "Aggregate: {aggregate_name}",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue2", ...}}
    }},
    "then": {{
      "name": "Event: {event_name}",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue2", ...}}
    }}
  }}
]

Each test case should represent a different scenario with different field values. If properties are not available or empty, use empty fieldValues {{}}.
"""

GENERATE_GWT_PROMPT_POLICY = """Generate Given/When/Then (GWT) test cases for a Policy to support BDD-style test scenarios.

<policy>
Name: {policy_name}
Description: {policy_description}
</policy>

<trigger_events>
{trigger_events_info}
</trigger_events>

<invoke_command>
Name: {invoke_command_name}
Description: {invoke_command_description}
Properties: {invoke_command_properties}
</invoke_command>

<target_aggregate>
Name: {target_aggregate_name}
Properties: {target_aggregate_properties}
</target_aggregate>

<target_event>
Name: {target_event_name}
Description: {target_event_description}
Properties: {target_event_properties}
</target_event>

For this Policy, generate multiple GWT test cases (typically 2-5 test cases covering different scenarios):
- **scenarioDescription:** A brief description of the business flow/scenario this test case represents (e.g., "Happy path: Policy triggers when order is placed and successfully invokes payment command")
- **given:** Reference the trigger Event(s). For each trigger event, include `name` (e.g., "Event: <event_name>") and optional `description`. The `fieldValues` dictionary should map property names from the trigger Event to realistic test values. If there are multiple trigger events, create a separate Given for each trigger event.
- **when:** Reference the Aggregate that handles the invoked Command. Include `name` (e.g., "Aggregate: <target_aggregate_name>") and optional `description`. The `fieldValues` dictionary should map property names from the Aggregate to realistic test values based on the properties listed above.
- **then:** Reference the Event emitted by the invoked Command. Include `name` (e.g., "Event: <target_event_name>") and optional `description`. The `fieldValues` dictionary should map property names from the Event to realistic test values based on the properties listed above.

Return a JSON array with multiple test cases:
[
  {{
    "scenarioDescription": "Brief description of this test case's business flow",
    "given": [
      {{
        "name": "Event: <trigger_event_name>",
        "description": "...",
        "fieldValues": {{"propertyName": "testValue1", ...}}
      }}
    ],
    "when": {{
      "name": "Aggregate: <target_aggregate_name>",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue1", ...}}
    }},
    "then": {{
      "name": "Event: <target_event_name>",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue1", ...}}
    }}
  }},
  {{
    "scenarioDescription": "Brief description of this test case's business flow",
    "given": [
      {{
        "name": "Event: <trigger_event_name>",
        "description": "...",
        "fieldValues": {{"propertyName": "testValue2", ...}}
      }}
    ],
    "when": {{
      "name": "Aggregate: <target_aggregate_name>",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue2", ...}}
    }},
    "then": {{
      "name": "Event: <target_event_name>",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue2", ...}}
    }}
  }}
]

Each test case should represent a different scenario with different field values. If there are multiple trigger events, include all of them in the "given" array. If properties are not available or empty, use empty fieldValues {{}}.
"""


async def generate_gwt_phase(ctx: IngestionWorkflowContext) -> AsyncGenerator[ProgressEvent, None]:
    """
    Phase: Generate Given/When/Then (GWT) structures for Commands and Policies.
    This phase runs after policies are created and before UI generation.
    """
    yield ProgressEvent(
        phase=IngestionPhase.IDENTIFYING_POLICIES,  # Keep same phase for UI continuity
        message="GWT (Given/When/Then) 생성 중...",
        progress=91,
    )

    llm = ctx.llm
    client = ctx.client

    def _upsert_gwt_bundle(
        *,
        parent_type: str,
        parent_id: str,
        given_ref: dict[str, Any] | None,
        when_ref: dict[str, Any] | None,
        then_ref: dict[str, Any] | None,
        test_cases: list[dict[str, Any]],
    ) -> None:
        """
        Persist a single (GWT) node per parent and store test cases inside it.
        Also updates (gwt)-[:REFERENCES]->(ref) edges for mapped objects.
        """
        query = """
        MATCH (parent {id: $parent_id})
        WHERE $parent_type IN labels(parent)
        MERGE (gwt:GWT {parentType: $parent_type, parentId: $parent_id})
        ON CREATE SET gwt.id = randomUUID(),
                      gwt.createdAt = datetime()
        SET gwt.updatedAt = datetime(),
            gwt.givenRef = $given_ref_json,
            gwt.whenRef = $when_ref_json,
            gwt.thenRef = $then_ref_json,
            gwt.testCases = $test_cases_json
        MERGE (parent)-[:HAS_GWT]->(gwt)
        WITH gwt
        OPTIONAL MATCH (gwt)-[r:REFERENCES]->()
        DELETE r
        WITH gwt, $refs as refs
        UNWIND refs as ref
        WITH gwt, ref
        WHERE ref.id IS NOT NULL AND ref.type IS NOT NULL
        MATCH (n {id: ref.id})
        WHERE ref.type IN labels(n)
        MERGE (gwt)-[:REFERENCES]->(n)
        RETURN gwt.id as id
        """
        given_ref_json = json.dumps(given_ref) if given_ref else None
        when_ref_json = json.dumps(when_ref) if when_ref else None
        then_ref_json = json.dumps(then_ref) if then_ref else None
        test_cases_json = json.dumps(test_cases or [])

        refs: list[dict[str, Any]] = []
        for ref in (given_ref, when_ref, then_ref):
            if isinstance(ref, dict) and ref.get("referencedNodeId") and ref.get("referencedNodeType"):
                refs.append({"id": ref["referencedNodeId"], "type": ref["referencedNodeType"]})

        with client.session() as session:
            session.run(
                query,
                parent_type=parent_type,
                parent_id=parent_id,
                given_ref_json=given_ref_json,
                when_ref_json=when_ref_json,
                then_ref_json=then_ref_json,
                test_cases_json=test_cases_json,
                refs=refs,
            )
    
    total_gwt_created = 0

    # Generate GWT for Commands
    for bc in ctx.bounded_contexts:
        for agg in ctx.aggregates_by_bc.get(bc.id, []):
            commands = ctx.commands_by_agg.get(agg.id, [])
            events = ctx.events_by_agg.get(agg.id, [])
            
            for i, cmd in enumerate(commands):
                # Find corresponding event (simple heuristic: by index)
                evt = events[i] if i < len(events) else (events[0] if events else None)
                
                # Get properties from Neo4j
                cmd_props = []
                agg_props = []
                evt_props = []
                
                # Query properties from Neo4j
                try:
                    with client.session() as session:
                        # Get Command properties
                        cmd_props_result = session.run(
                            "MATCH (cmd:Command {id: $cmd_id})-[:HAS_PROPERTY]->(p:Property) RETURN p.name as name, p.type as type ORDER BY p.name",
                            cmd_id=cmd.id
                        )
                        cmd_props = [{"name": r["name"], "type": r["type"]} for r in cmd_props_result if r.get("name")]
                        
                        # Get Aggregate properties
                        agg_props_result = session.run(
                            "MATCH (agg:Aggregate {id: $agg_id})-[:HAS_PROPERTY]->(p:Property) RETURN p.name as name, p.type as type ORDER BY p.name",
                            agg_id=agg.id
                        )
                        agg_props = [{"name": r["name"], "type": r["type"]} for r in agg_props_result if r.get("name")]
                        
                        # Get Event properties
                        if evt:
                            evt_props_result = session.run(
                                "MATCH (evt:Event {id: $evt_id})-[:HAS_PROPERTY]->(p:Property) RETURN p.name as name, p.type as type ORDER BY p.name",
                                evt_id=evt.id
                            )
                            evt_props = [{"name": r["name"], "type": r["type"]} for r in evt_props_result if r.get("name")]
                except Exception as e:
                    SmartLogger.log(
                        "WARN",
                        f"Failed to query properties for GWT generation: {e}",
                        category="ingestion.workflow.gwt",
                        params={"session_id": ctx.session.id, "command_id": cmd.id, "error": str(e)}
                    )
                    # Continue with empty properties
                
                # Format properties as text
                cmd_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in cmd_props]) if cmd_props else "No properties available yet"
                agg_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in agg_props]) if agg_props else "No properties available yet"
                evt_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in evt_props]) if evt and evt_props else "No properties available yet"
                
                prompt = GENERATE_GWT_PROMPT_COMMAND.format(
                    command_name=cmd.name,
                    command_description=getattr(cmd, "description", "") or "",
                    command_properties=cmd_props_text,
                    aggregate_name=agg.name,
                    aggregate_properties=agg_props_text,
                    event_name=evt.name if evt else "UnknownEvent",
                    event_description=getattr(evt, "description", "") if evt else "Event will be emitted",
                    event_properties=evt_props_text,
                )
                
                provider, model = get_llm_provider_model()
                if AI_AUDIT_LOG_ENABLED:
                    SmartLogger.log(
                        "INFO",
                        "Ingestion: generate GWT - LLM invoke starting.",
                        category="ingestion.llm.generate_gwt.start",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "command": {"id": cmd.id, "name": cmd.name},
                            "aggregate": {"id": agg.id, "name": agg.name},
                            "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                        }
                    )
                
                t_llm0 = time.perf_counter()
                try:
                    # Use JSON mode for structured output
                    response = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
                    llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                    
                    # Parse JSON response
                    content = response.content if hasattr(response, 'content') else str(response)
                    # Extract JSON from markdown code blocks if present
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()
                    
                    gwt_test_cases = json.loads(content)
                    
                    # Handle both array and single object responses
                    if not isinstance(gwt_test_cases, list):
                        gwt_test_cases = [gwt_test_cases]
                    
                    # Persist as a single bundle node: mapped refs fixed, rows are testCases
                    test_cases_payload: list[dict[str, Any]] = []
                    for set_index, gwt_data in enumerate(gwt_test_cases):
                        scenario_description = gwt_data.get("scenarioDescription", "")
                        given_data = gwt_data.get("given") or {}
                        when_data = gwt_data.get("when") or {}
                        then_data = gwt_data.get("then") or {}

                        # Store scenario description inside the test case (preferred)
                        test_cases_payload.append(
                            {
                                "scenarioDescription": scenario_description or None,
                                "givenFieldValues": (given_data.get("fieldValues") or {}) if isinstance(given_data, dict) else {},
                                "whenFieldValues": (when_data.get("fieldValues") or {}) if isinstance(when_data, dict) else {},
                                "thenFieldValues": (then_data.get("fieldValues") or {}) if isinstance(then_data, dict) else {},
                            }
                        )

                    _upsert_gwt_bundle(
                        parent_type="Command",
                        parent_id=cmd.id,
                        given_ref={
                            "referencedNodeId": cmd.id,
                            "referencedNodeType": "Command",
                            "name": f"Command: {cmd.name}",
                        },
                        when_ref={
                            "referencedNodeId": agg.id,
                            "referencedNodeType": "Aggregate",
                            "name": f"Aggregate: {agg.name}",
                        },
                        then_ref={
                            "referencedNodeId": evt.id,
                            "referencedNodeType": "Event",
                            "name": f"Event: {evt.name}",
                        }
                        if evt
                        else None,
                        test_cases=test_cases_payload,
                    )
                    total_gwt_created += max(len(test_cases_payload), 1)
                    
                    if AI_AUDIT_LOG_ENABLED:
                        SmartLogger.log(
                            "INFO",
                            "Ingestion: generate GWT - LLM invoke completed.",
                            category="ingestion.llm.generate_gwt.done",
                            params={
                                "session_id": ctx.session.id,
                                "llm": {"provider": provider, "model": model},
                                "command": {"id": cmd.id, "name": cmd.name},
                                "llm_ms": llm_ms,
                                "test_cases_created": len(gwt_test_cases),
                            }
                        )
                except Exception as e:
                    SmartLogger.log(
                        "WARN",
                        f"Ingestion: generate GWT - LLM invoke failed for command {cmd.name}: {e}. Creating fallback GWT.",
                        category="ingestion.llm.generate_gwt.error",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "command": {"id": cmd.id, "name": cmd.name},
                            "error": str(e),
                        }
                    )
                    # Fallback: bundle with a single empty test case
                    try:
                        _upsert_gwt_bundle(
                            parent_type="Command",
                            parent_id=cmd.id,
                            given_ref={
                                "referencedNodeId": cmd.id,
                                "referencedNodeType": "Command",
                                "name": f"Command: {cmd.name}",
                            },
                            when_ref={
                                "referencedNodeId": agg.id,
                                "referencedNodeType": "Aggregate",
                                "name": f"Aggregate: {agg.name}",
                            },
                            then_ref={
                                "referencedNodeId": evt.id,
                                "referencedNodeType": "Event",
                                "name": f"Event: {evt.name}",
                            }
                            if evt
                            else None,
                            test_cases=[
                                {
                                    "scenarioDescription": None,
                                    "givenFieldValues": {},
                                    "whenFieldValues": {},
                                    "thenFieldValues": {},
                                }
                            ],
                        )
                        total_gwt_created += 1
                    except Exception as create_error:
                        SmartLogger.log(
                            "ERROR",
                            f"Failed to create fallback GWT bundle for Command {cmd.name}: {create_error}",
                            category="ingestion.neo4j.gwt",
                            params={"session_id": ctx.session.id, "command_id": cmd.id, "error": str(create_error)}
                        )
    
    # Generate GWT for Policies
    # Query all policies from Neo4j via BoundedContexts (ctx.policies may be empty)
    policies_list = []
    for bc in ctx.bounded_contexts:
        with client.session() as session:
            policies_query = """
            MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_POLICY]->(pol:Policy)
            RETURN pol.id as id, pol.name as name
            ORDER BY pol.name
            """
            policies_result = session.run(policies_query, bc_id=bc.id)
            for r in policies_result:
                if r.get("id"):
                    policies_list.append({"id": r["id"], "name": r["name"]})
    
    if not policies_list:
        SmartLogger.log(
            "INFO",
            "No policies found for GWT generation",
            category="ingestion.workflow.gwt.policy",
            params={"session_id": ctx.session.id}
        )
    else:
        SmartLogger.log(
            "INFO",
            f"Found {len(policies_list)} policies for GWT generation",
            category="ingestion.workflow.gwt.policy",
            params={"session_id": ctx.session.id, "policy_count": len(policies_list)}
        )
    
    for policy in policies_list:
        policy_id = policy.get("id")
        policy_name = policy.get("name")
        
        if not policy_id or not policy_name:
            continue
        
        # Query relationships from Neo4j (trigger events, invoke command, target event/aggregate)
        with client.session() as session:
            policy_query = """
            MATCH (pol:Policy {id: $policy_id})
            OPTIONAL MATCH (evt:Event)-[:TRIGGERS]->(pol)
            OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
            OPTIONAL MATCH (cmd)-[:EMITS]->(target_evt:Event)
            OPTIONAL MATCH (agg:Aggregate)-[:HAS_COMMAND]->(cmd)
            WITH pol,
                 collect(DISTINCT evt.id) as trigger_event_ids_all,
                 collect(DISTINCT evt.name) as trigger_event_names_all,
                 collect(DISTINCT cmd.id) as cmd_ids_all,
                 collect(DISTINCT cmd.name) as cmd_names_all,
                 collect(DISTINCT target_evt.id) as target_evt_ids_all,
                 collect(DISTINCT target_evt.name) as target_evt_names_all,
                 collect(DISTINCT agg.id) as agg_ids_all,
                 collect(DISTINCT agg.name) as agg_names_all
            RETURN trigger_event_ids_all,
                   trigger_event_names_all,
                   cmd_ids_all,
                   cmd_names_all,
                   target_evt_ids_all,
                   target_evt_names_all,
                   agg_ids_all,
                   agg_names_all
            """
            result = session.run(policy_query, policy_id=policy_id)
            record = result.single()
            
            if not record:
                SmartLogger.log(
                    "WARN",
                    f"Policy {policy_name} not found or has no relationships",
                    category="ingestion.workflow.gwt.policy.skip",
                    params={"session_id": ctx.session.id, "policy_id": policy_id, "policy_name": policy_name}
                )
                continue
            
            # Filter out NULL values from collections
            trigger_event_ids_all = record.get("trigger_event_ids_all") or []
            trigger_event_names_all = record.get("trigger_event_names_all") or []
            cmd_ids_all = record.get("cmd_ids_all") or []
            cmd_names_all = record.get("cmd_names_all") or []
            target_evt_ids_all = record.get("target_evt_ids_all") or []
            target_evt_names_all = record.get("target_evt_names_all") or []
            agg_ids_all = record.get("agg_ids_all") or []
            agg_names_all = record.get("agg_names_all") or []
            
            trigger_event_ids = [id for id in trigger_event_ids_all if id is not None]
            trigger_event_names = [name for name in trigger_event_names_all if name is not None]
            invoke_command_id = next((id for id in cmd_ids_all if id is not None), None)
            invoke_command_name = next((name for name in cmd_names_all if name is not None), None)
            target_event_id = next((id for id in target_evt_ids_all if id is not None), None)
            target_event_name = next((name for name in target_evt_names_all if name is not None), None)
            target_agg_id = next((id for id in agg_ids_all if id is not None), None)
            target_agg_name = next((name for name in agg_names_all if name is not None), None)
            
            # Log what we found
            SmartLogger.log(
                "INFO",
                f"Policy GWT processing: {policy_name}",
                category="ingestion.workflow.gwt.policy.check",
                params={
                    "session_id": ctx.session.id,
                    "policy_id": policy_id,
                    "policy_name": policy_name,
                    "trigger_event_ids_count": len(trigger_event_ids),
                    "invoke_command_id": invoke_command_id,
                    "target_event_id": target_event_id,
                    "target_agg_id": target_agg_id,
                }
            )
            
            # Only skip if absolutely essential data is missing (like Command does - minimal checks)
            if not trigger_event_ids:
                SmartLogger.log(
                    "WARN",
                    f"Skipping Policy {policy_name}: no trigger events found",
                    category="ingestion.workflow.gwt.policy.skip",
                    params={"session_id": ctx.session.id, "policy_id": policy_id, "policy_name": policy_name}
                )
                continue
            
            # Use defaults if missing (like Command does with evt)
            if not invoke_command_id:
                SmartLogger.log(
                    "WARN",
                    f"Policy {policy_name}: no invoke command found, will use defaults",
                    category="ingestion.workflow.gwt.policy.warn",
                    params={"session_id": ctx.session.id, "policy_id": policy_id, "policy_name": policy_name}
                )
            if not target_event_id:
                SmartLogger.log(
                    "WARN",
                    f"Policy {policy_name}: no target event found, will use defaults",
                    category="ingestion.workflow.gwt.policy.warn",
                    params={"session_id": ctx.session.id, "policy_id": policy_id, "policy_name": policy_name}
                )
            if not target_agg_id:
                SmartLogger.log(
                    "WARN",
                    f"Policy {policy_name}: no target aggregate found, will use defaults",
                    category="ingestion.workflow.gwt.policy.warn",
                    params={"session_id": ctx.session.id, "policy_id": policy_id, "policy_name": policy_name}
                )
            
            # Get properties from Neo4j for Policy GWT generation
            trigger_event_props_list = []
            invoke_cmd_props = []
            target_agg_props = []
            target_evt_props = []
            
            try:
                with client.session() as session:
                    # Get properties for each trigger event
                    for event_id in trigger_event_ids:
                        evt_props_result = session.run(
                            "MATCH (evt:Event {id: $evt_id})-[:HAS_PROPERTY]->(p:Property) RETURN p.name as name, p.type as type ORDER BY p.name",
                            evt_id=event_id
                        )
                        evt_props = [{"name": r["name"], "type": r["type"]} for r in evt_props_result if r.get("name")]
                        trigger_event_props_list.append(evt_props)
                    
                    # Get invoke command properties
                    if invoke_command_id:
                        cmd_props_result = session.run(
                            "MATCH (cmd:Command {id: $cmd_id})-[:HAS_PROPERTY]->(p:Property) RETURN p.name as name, p.type as type ORDER BY p.name",
                            cmd_id=invoke_command_id
                        )
                        invoke_cmd_props = [{"name": r["name"], "type": r["type"]} for r in cmd_props_result if r.get("name")]
                    
                    # Get target aggregate properties
                    agg_props_result = session.run(
                        "MATCH (agg:Aggregate {id: $agg_id})-[:HAS_PROPERTY]->(p:Property) RETURN p.name as name, p.type as type ORDER BY p.name",
                        agg_id=target_agg_id
                    )
                    target_agg_props = [{"name": r["name"], "type": r["type"]} for r in agg_props_result if r.get("name")]
                    
                    # Get target event properties
                    evt_props_result = session.run(
                        "MATCH (evt:Event {id: $evt_id})-[:HAS_PROPERTY]->(p:Property) RETURN p.name as name, p.type as type ORDER BY p.name",
                        evt_id=target_event_id
                    )
                    target_evt_props = [{"name": r["name"], "type": r["type"]} for r in evt_props_result if r.get("name")]
                    
                    # Get policy description
                    policy_desc_result = session.run(
                        "MATCH (pol:Policy {id: $policy_id}) RETURN pol.description as description",
                        policy_id=policy_id
                    )
                    policy_desc_record = policy_desc_result.single()
                    policy_description = policy_desc_record.get("description") if policy_desc_record else ""
                    
                    # Get invoke command description
                    invoke_cmd_desc = ""
                    if invoke_command_id:
                        cmd_desc_result = session.run(
                            "MATCH (cmd:Command {id: $cmd_id}) RETURN cmd.description as description",
                            cmd_id=invoke_command_id
                        )
                        cmd_desc_record = cmd_desc_result.single()
                        invoke_cmd_desc = cmd_desc_record.get("description") if cmd_desc_record else ""
                    
                    # Get target event description
                    target_evt_desc_result = session.run(
                        "MATCH (evt:Event {id: $evt_id}) RETURN evt.description as description",
                        evt_id=target_event_id
                    )
                    target_evt_desc_record = target_evt_desc_result.single()
                    target_evt_desc = target_evt_desc_record.get("description") if target_evt_desc_record else ""
            except Exception as e:
                SmartLogger.log(
                    "WARN",
                    f"Failed to query properties for Policy GWT generation: {e}",
                    category="ingestion.workflow.gwt",
                    params={"session_id": ctx.session.id, "policy_id": policy_id, "error": str(e)}
                )
                # Continue with empty properties
            
            # Format trigger events info
            trigger_events_info = ""
            for i, (event_name, event_props) in enumerate(zip(trigger_event_names, trigger_event_props_list)):
                event_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in event_props]) if event_props else "No properties available yet"
                trigger_events_info += f"\n<event_{i+1}>\nName: {event_name}\nProperties:\n{event_props_text}\n</event_{i+1}>\n"
            
            # Format properties as text
            invoke_cmd_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in invoke_cmd_props]) if invoke_cmd_props else "No properties available yet"
            target_agg_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in target_agg_props]) if target_agg_props else "No properties available yet"
            target_evt_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in target_evt_props]) if target_evt_props else "No properties available yet"
            
            prompt = GENERATE_GWT_PROMPT_POLICY.format(
                policy_name=policy_name,
                policy_description=policy_description or "",
                trigger_events_info=trigger_events_info.strip(),
                invoke_command_name=invoke_command_name or "UnknownCommand",
                invoke_command_description=invoke_cmd_desc or "",
                invoke_command_properties=invoke_cmd_props_text,
                target_aggregate_name=target_agg_name or "UnknownAggregate",
                target_aggregate_properties=target_agg_props_text,
                target_event_name=target_event_name or "UnknownEvent",
                target_event_description=target_evt_desc or "",
                target_event_properties=target_evt_props_text,
            )
            
            provider, model = get_llm_provider_model()
            if AI_AUDIT_LOG_ENABLED:
                SmartLogger.log(
                    "INFO",
                    "Ingestion: generate GWT for Policy - LLM invoke starting.",
                    category="ingestion.llm.generate_gwt.policy.start",
                    params={
                        "session_id": ctx.session.id,
                        "llm": {"provider": provider, "model": model},
                        "policy": {"id": policy_id, "name": policy_name},
                        "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                    }
                )
            
            t_llm0 = time.perf_counter()
            try:
                # Use JSON mode for structured output
                response = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
                llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                
                # Parse JSON response
                content = response.content if hasattr(response, 'content') else str(response)
                # Extract JSON from markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                try:
                    gwt_test_cases = json.loads(content)
                except json.JSONDecodeError as json_err:
                    SmartLogger.log(
                        "WARN",
                        f"Policy GWT JSON parse error for {policy_name}: {json_err}. Content preview: {content[:200]}",
                        category="ingestion.workflow.gwt.policy.json_parse_error",
                        params={
                            "session_id": ctx.session.id,
                            "policy_id": policy_id,
                            "policy_name": policy_name,
                            "error": str(json_err),
                            "content_preview": content[:200],
                        }
                    )
                    raise
                
                # Handle both array and single object responses
                if not isinstance(gwt_test_cases, list):
                    gwt_test_cases = [gwt_test_cases]
                
                if not gwt_test_cases:
                    SmartLogger.log(
                        "WARN",
                        f"Policy GWT LLM returned empty test cases for {policy_name}",
                        category="ingestion.workflow.gwt.policy.empty_response",
                        params={
                            "session_id": ctx.session.id,
                            "policy_id": policy_id,
                            "policy_name": policy_name,
                        }
                    )
                    # Create a single empty test case as fallback
                    gwt_test_cases = [{}]
                
                # Persist as a single bundle node
                test_cases_payload: list[dict[str, Any]] = []
                for set_index, gwt_data in enumerate(gwt_test_cases):
                    scenario_description = gwt_data.get("scenarioDescription", "")

                    # given can be array (multiple trigger events) or single object
                    # If multiple trigger events, merge all their fieldValues
                    given_raw = gwt_data.get("given")
                    given_field_values = {}
                    if isinstance(given_raw, list):
                        # Merge fieldValues from all trigger events
                        for given_item in given_raw:
                            if isinstance(given_item, dict) and given_item.get("fieldValues"):
                                given_field_values.update(given_item["fieldValues"])
                    elif isinstance(given_raw, dict) and given_raw.get("fieldValues"):
                        given_field_values = given_raw["fieldValues"]

                    when_data = gwt_data.get("when") or {}
                    then_data = gwt_data.get("then") or {}

                    test_cases_payload.append(
                        {
                            "scenarioDescription": scenario_description or None,
                            "givenFieldValues": given_field_values,
                            "whenFieldValues": (when_data.get("fieldValues") or {}) if isinstance(when_data, dict) else {},
                            "thenFieldValues": (then_data.get("fieldValues") or {}) if isinstance(then_data, dict) else {},
                        }
                    )

                SmartLogger.log(
                    "INFO",
                    f"Policy GWT test cases parsed: {len(test_cases_payload)} test cases for {policy_name}",
                    category="ingestion.workflow.gwt.policy.parsed",
                    params={
                        "session_id": ctx.session.id,
                        "policy_id": policy_id,
                        "policy_name": policy_name,
                        "test_cases_count": len(test_cases_payload),
                        "test_cases_payload": test_cases_payload[:2] if test_cases_payload else [],  # Log first 2 for debugging
                    }
                )

                # Mapped objects are fixed; pick first trigger event as the referenced event for the table columns.
                given_event_id = trigger_event_ids[0] if trigger_event_ids else None
                given_event_name = trigger_event_names[0] if trigger_event_names else None
                
                # Always upsert (like Command does) - use defaults if missing
                try:
                    _upsert_gwt_bundle(
                        parent_type="Policy",
                        parent_id=policy_id,
                        given_ref={
                            "referencedNodeId": given_event_id,
                            "referencedNodeType": "Event",
                            "name": f"Event: {given_event_name}" if given_event_name else "Event",
                        } if given_event_id else None,
                        when_ref={
                            "referencedNodeId": target_agg_id,
                            "referencedNodeType": "Aggregate",
                            "name": f"Aggregate: {target_agg_name}" if target_agg_name else "Aggregate",
                        } if target_agg_id else None,
                        then_ref={
                            "referencedNodeId": target_event_id,
                            "referencedNodeType": "Event",
                            "name": f"Event: {target_event_name}" if target_event_name else "Event",
                        } if target_event_id else None,
                        test_cases=test_cases_payload if test_cases_payload else [
                            {
                                "scenarioDescription": None,
                                "givenFieldValues": {},
                                "whenFieldValues": {},
                                "thenFieldValues": {},
                            }
                        ],
                    )
                    total_gwt_created += max(len(test_cases_payload), 1)
                    SmartLogger.log(
                        "INFO",
                        f"Policy GWT bundle upserted successfully: {policy_name}",
                        category="ingestion.workflow.gwt.policy.upserted",
                        params={
                            "session_id": ctx.session.id,
                            "policy_id": policy_id,
                            "policy_name": policy_name,
                            "test_cases_count": len(test_cases_payload),
                        }
                    )
                except Exception as upsert_error:
                    SmartLogger.log(
                        "ERROR",
                        f"Failed to upsert GWT bundle for Policy {policy_name}: {upsert_error}",
                        category="ingestion.workflow.gwt.policy.upsert_error",
                        params={
                            "session_id": ctx.session.id,
                            "policy_id": policy_id,
                            "policy_name": policy_name,
                            "error": str(upsert_error),
                        }
                    )
                    raise
                
                if AI_AUDIT_LOG_ENABLED:
                    SmartLogger.log(
                        "INFO",
                        "Ingestion: generate GWT for Policy - LLM invoke completed.",
                        category="ingestion.llm.generate_gwt.policy.done",
                        params={
                            "session_id": ctx.session.id,
                            "llm": {"provider": provider, "model": model},
                            "policy": {"id": policy_id, "name": policy_name},
                            "llm_ms": llm_ms,
                            "test_cases_created": len(gwt_test_cases),
                        }
                    )
            except Exception as e:
                SmartLogger.log(
                    "WARN",
                    f"Ingestion: generate GWT for Policy - LLM invoke failed for policy {policy_name}: {e}. Creating fallback GWT.",
                    category="ingestion.llm.generate_gwt.policy.error",
                    params={
                        "session_id": ctx.session.id,
                        "llm": {"provider": provider, "model": model},
                        "policy": {"id": policy_id, "name": policy_name},
                        "error": str(e),
                    }
                )
                # Fallback: bundle with a single empty test case
                try:
                    given_event_id = trigger_event_ids[0] if trigger_event_ids else None
                    given_event_name = trigger_event_names[0] if trigger_event_names else None
                    if given_event_id:
                        _upsert_gwt_bundle(
                            parent_type="Policy",
                            parent_id=policy_id,
                            given_ref={
                                "referencedNodeId": given_event_id,
                                "referencedNodeType": "Event",
                                "name": f"Event: {given_event_name}" if given_event_name else "Event",
                            },
                            when_ref={
                                "referencedNodeId": target_agg_id,
                                "referencedNodeType": "Aggregate",
                                "name": f"Aggregate: {target_agg_name}" if target_agg_name else "Aggregate",
                            },
                            then_ref={
                                "referencedNodeId": target_event_id,
                                "referencedNodeType": "Event",
                                "name": f"Event: {target_event_name}" if target_event_name else "Event",
                            },
                            test_cases=[
                                {
                                    "scenarioDescription": None,
                                    "givenFieldValues": {},
                                    "whenFieldValues": {},
                                    "thenFieldValues": {},
                                }
                            ],
                        )
                        total_gwt_created += 1
                except Exception as create_error:
                    SmartLogger.log(
                        "ERROR",
                        f"Failed to create fallback GWT bundle for Policy {policy_name}: {create_error}",
                        category="ingestion.neo4j.gwt",
                        params={"session_id": ctx.session.id, "policy_id": policy_id, "error": str(create_error)}
                    )
    
    SmartLogger.log(
        "INFO",
        f"Ingestion: generate GWT completed. Generated GWT for {total_gwt_created} components.",
        category="ingestion.workflow.gwt",
        params={"session_id": ctx.session.id, "gwt_count": total_gwt_created}
    )
    
    yield ProgressEvent(
        phase=IngestionPhase.IDENTIFYING_POLICIES,
        message=f"GWT 생성 완료 ({total_gwt_created}개 구성요소)",
        progress=92,
    )
