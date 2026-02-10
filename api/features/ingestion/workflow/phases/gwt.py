from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from api.features.ingestion.ingestion_contracts import IngestionPhase, ProgressEvent
from api.features.ingestion.event_storming.neo4j_ops.gwt import GWTOps
from api.features.ingestion.event_storming.prompts import SYSTEM_PROMPT
from api.features.ingestion.workflow.ingestion_workflow_context import IngestionWorkflowContext
from api.features.ingestion.workflow.utils.chunking import (
    should_chunk_list,
    split_list_with_overlap,
)
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
- **given:** Reference the Aggregate that handles this Command. Include `name` (e.g., "Aggregate: {aggregate_name}") and optional `description`. The `fieldValues` dictionary should map property names from the Aggregate to realistic test values based on the properties listed above.
- **when:** Reference the Command itself. Include `name` (e.g., "Command: {command_name}") and optional `description`. The `fieldValues` dictionary should map property names from the Command to realistic test values based on the properties listed above.
- **then:** Reference the Event emitted by this Command. Include `name` (e.g., "Event: {event_name}") and optional `description`. The `fieldValues` dictionary should map property names from the Event to realistic test values based on the properties listed above.

Return a JSON array with multiple test cases:
[
  {{
    "scenarioDescription": "Brief description of this test case's business flow",
    "given": {{
      "name": "Aggregate: {aggregate_name}",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue1", ...}}
    }},
    "when": {{
      "name": "Command: {command_name}",
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
      "name": "Aggregate: {aggregate_name}",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue2", ...}}
    }},
    "when": {{
      "name": "Command: {command_name}",
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

async def _generate_gwt_for_command(
    task: dict[str, Any],
    llm: Any,
    client: Any,
    ctx: IngestionWorkflowContext,
    cmd_count: int,
    total_commands: int,
) -> int:
    """
    Generate GWT for a single command.
    Returns the number of GWT test cases created.
    """
    from api.features.ingestion.event_storming.neo4j_ops.gwt import GWTOps
    
    bc = task["bc"]
    agg = task["agg"]
    cmd = task["cmd"]
    evt = task["evt"]
    
    # Check if this Command is invoked by a Policy
    policy_trigger_event_id = None
    policy_trigger_event_name = None
    try:
        def _check_policy():
            with client.session() as session:
                policy_query = """
                MATCH (pol:Policy)-[:INVOKES]->(cmd:Command {id: $cmd_id})
                MATCH (trigger_evt:Event)-[:TRIGGERS]->(pol)
                RETURN trigger_evt.id as trigger_event_id, trigger_evt.name as trigger_event_name
                LIMIT 1
                """
                policy_result = session.run(policy_query, cmd_id=cmd.id)
                return policy_result.single()
        
        policy_record = await asyncio.wait_for(
            asyncio.to_thread(_check_policy),
            timeout=5.0
        )
        if policy_record:
            policy_trigger_event_id = policy_record.get("trigger_event_id")
            policy_trigger_event_name = policy_record.get("trigger_event_name")
    except (asyncio.TimeoutError, Exception) as e:
        pass  # Policy check failed - continue without trigger event
    
    # Get properties from Neo4j
    try:
        def _fetch_properties():
            with client.session() as session:
                cmd_props_result = session.run(
                    "MATCH (cmd:Command {id: $cmd_id})-[:HAS_PROPERTY]->(p:Property) RETURN p.name as name, p.type as type ORDER BY p.name",
                    cmd_id=cmd.id
                )
                cmd_props_list = [{"name": r["name"], "type": r["type"]} for r in cmd_props_result if r.get("name")]
                
                agg_record = session.run(
                    "MATCH (agg:Aggregate {id: $agg_id}) RETURN agg.enumerations as enumerations, agg.valueObjects as valueObjects",
                    agg_id=agg.id
                ).single()
                
                agg_enumerations_list = []
                agg_value_objects_list = []
                if agg_record:
                    import json
                    try:
                        enum_json = agg_record.get("enumerations")
                        if isinstance(enum_json, str):
                            agg_enumerations_list = json.loads(enum_json) or []
                        elif isinstance(enum_json, list):
                            agg_enumerations_list = enum_json or []
                            
                        vo_json = agg_record.get("valueObjects")
                        if isinstance(vo_json, str):
                            agg_value_objects_list = json.loads(vo_json) or []
                        elif isinstance(vo_json, list):
                            agg_value_objects_list = vo_json or []
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                agg_props_result = session.run(
                    "MATCH (agg:Aggregate {id: $agg_id})-[:HAS_PROPERTY]->(p:Property) RETURN p.name as name, p.type as type ORDER BY p.name",
                    agg_id=agg.id
                )
                agg_props_list = [{"name": r["name"], "type": r["type"]} for r in agg_props_result if r.get("name")]
                
                evt_props_list = []
                if evt:
                    evt_props_result = session.run(
                        "MATCH (evt:Event {id: $evt_id})-[:HAS_PROPERTY]->(p:Property) RETURN p.name as name, p.type as type ORDER BY p.name",
                        evt_id=evt.id
                    )
                    evt_props_list = [{"name": r["name"], "type": r["type"]} for r in evt_props_result if r.get("name")]
                
                trigger_evt_props_list = []
                if policy_trigger_event_id:
                    trigger_evt_props_result = session.run(
                        "MATCH (evt:Event {id: $evt_id})-[:HAS_PROPERTY]->(p:Property) RETURN p.name as name, p.type as type ORDER BY p.name",
                        evt_id=policy_trigger_event_id
                    )
                    trigger_evt_props_list = [{"name": r["name"], "type": r["type"]} for r in trigger_evt_props_result if r.get("name")]
                
                return {
                    "cmd_props": cmd_props_list,
                    "agg_props": agg_props_list,
                    "agg_enumerations": agg_enumerations_list,
                    "agg_value_objects": agg_value_objects_list,
                    "evt_props": evt_props_list,
                    "trigger_evt_props": trigger_evt_props_list,
                }
        
        props_data = await asyncio.wait_for(
            asyncio.to_thread(_fetch_properties),
            timeout=10.0
        )
        cmd_props = props_data["cmd_props"]
        agg_props = props_data["agg_props"]
        agg_enumerations = props_data["agg_enumerations"]
        agg_value_objects = props_data["agg_value_objects"]
        evt_props = props_data["evt_props"]
        trigger_evt_props = props_data["trigger_evt_props"]
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"Failed to query properties for Command {cmd.name}: {e}",
            category="ingestion.workflow.gwt.properties_error",
            params={"session_id": ctx.session.id, "command_name": cmd.name, "error": str(e)}
        )
        cmd_props = []
        agg_props = []
        agg_enumerations = []
        agg_value_objects = []
        evt_props = []
        trigger_evt_props = []
    
    # Format properties (기존 로직과 동일)
    cmd_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in cmd_props]) if cmd_props else "No properties available yet"
    
    agg_props_lines = [f"- {p.get('name', '')}: {p.get('type', '')}" for p in agg_props] if agg_props else []
    if agg_enumerations:
        for enum in agg_enumerations:
            enum_name = enum.get("name", "")
            enum_items = enum.get("items", [])
            items_str = ", ".join(enum_items) if enum_items else "no items"
            agg_props_lines.append(f"- {enum_name}: Enum (items: {items_str})")
    if agg_value_objects:
        for vo in agg_value_objects:
            vo_name = vo.get("name", "")
            vo_fields = vo.get("fields", [])
            if vo_fields:
                fields_str = ", ".join([f.get("name", "") + ": " + f.get("type", "") for f in vo_fields])
                agg_props_lines.append(f"- {vo_name}: ValueObject (fields: {fields_str})")
            else:
                agg_props_lines.append(f"- {vo_name}: ValueObject")
    agg_props_text = "\n".join(agg_props_lines) if agg_props_lines else "No properties available yet"
    
    evt_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in evt_props]) if evt and evt_props else "No properties available yet"
    
    is_invoked_by_policy = policy_trigger_event_id is not None
    trigger_evt_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in trigger_evt_props]) if trigger_evt_props else "No properties available yet"
    
    # Build prompt (기존 로직과 동일하지만 간소화)
    if is_invoked_by_policy:
        when_section = f"""
<trigger_event>
Name: {policy_trigger_event_name}
Properties: {trigger_evt_props_text}
</trigger_event>
"""
        when_instruction = f'- **when:** Reference the trigger Event that Policy receives. Include `name` (e.g., "Event: {policy_trigger_event_name}") and optional `description`. The `fieldValues` dictionary MUST map ALL property names from the trigger Event (including Enum and ValueObject properties) to realistic test values. For each property, provide a realistic test value (e.g., for String type use "sample text", for Integer use 123, for Boolean use true/false, for Date use "2024-01-01", for Enum use one of the enum items, for ValueObject use a JSON object with nested fields). DO NOT leave fieldValues empty - always provide values for all available properties.'
        when_example = f'"when": {{\n      "name": "Event: {policy_trigger_event_name}",'
    else:
        when_section = ""
        when_instruction = f'- **when:** Reference the Command itself. Include `name` (e.g., "Command: {cmd.name}") and optional `description`. The `fieldValues` dictionary MUST map ALL property names from the Command (including Enum and ValueObject properties) to realistic test values. For each property, provide a realistic test value (e.g., for String type use "sample text", for Integer use 123, for Boolean use true/false, for Date use "2024-01-01", for Enum use one of the enum items, for ValueObject use a JSON object with nested fields). DO NOT leave fieldValues empty - always provide values for all available properties.'
        when_example = f'"when": {{\n      "name": "Command: {cmd.name}",'
    
    # Build prompt - use different when field based on whether Command is invoked by Policy
    prompt = f"""Generate Given/When/Then (GWT) test cases for a Command to support BDD-style test scenarios.

<command>
Name: {cmd.name}
Description: {getattr(cmd, "description", "") or ""}
Properties: {cmd_props_text}
</command>

<aggregate>
Name: {agg.name}
Properties: {agg_props_text}
</aggregate>
{when_section}
<event>
Name: {evt.name if evt else "UnknownEvent"}
Description: {getattr(evt, "description", "") if evt else "Event will be emitted"}
Properties: {evt_props_text}
</event>

For this Command, generate multiple GWT test cases (typically 2-5 test cases covering different scenarios):
- **scenarioDescription:** A brief description of the business flow/scenario this test case represents (e.g., "Happy path: User successfully creates an order with valid items")
- **given:** Reference the Aggregate that handles this Command. Include `name` (e.g., "Aggregate: {agg.name}") and optional `description`. The `fieldValues` dictionary MUST map ALL property names from the Aggregate (including Enum and ValueObject properties) to realistic test values representing the INITIAL STATE of the Aggregate before the Command is executed. For each property listed in the Aggregate properties above, provide a realistic test value (e.g., for String type use "sample text", for Integer use 123, for Boolean use true/false, for Date use "2024-01-01", for Enum use one of the enum items, for ValueObject use a JSON object with nested fields). DO NOT leave fieldValues empty - always provide values for all available properties.
{when_instruction}
- **then:** Reference the Event emitted by this Command. Include `name` (e.g., "Event: {evt.name if evt else "UnknownEvent"}") and optional `description`. The `fieldValues` dictionary MUST map ALL property names from the Event (including Enum and ValueObject properties) to realistic test values representing the RESULT STATE after the Command is executed. For each property listed in the Event properties above, provide a realistic test value (e.g., for String type use "sample text", for Integer use 123, for Boolean use true/false, for Date use "2024-01-01", for Enum use one of the enum items, for ValueObject use a JSON object with nested fields). DO NOT leave fieldValues empty - always provide values for all available properties.

Return a JSON array with multiple test cases:
[
  {{
    "scenarioDescription": "Brief description of this test case's business flow",
    "given": {{
      "name": "Aggregate: {agg.name}",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue1", ...}}
    }},
    {when_example}
      "description": "...",
      "fieldValues": {{"propertyName": "testValue1", ...}}
    }},
    "then": {{
      "name": "Event: {evt.name if evt else "UnknownEvent"}",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue1", ...}}
    }}
  }}
]

Each test case should represent a different scenario with different field values. 

CRITICAL REQUIREMENTS:
1. **ALWAYS populate fieldValues** - Never leave fieldValues empty ({{}}). If properties are listed above, you MUST provide test values for ALL of them.
2. **Given fieldValues** - Represent the initial state of the Aggregate before the Command executes. Use realistic domain values (e.g., orderId: "ORD-12345", customerName: "John Doe", amount: 100.50, status: "PENDING").
3. **When fieldValues** - Represent the Command input parameters. Use realistic values that would trigger the business logic.
4. **Then fieldValues** - Represent the resulting state after the Command executes. Use realistic values that reflect the outcome (e.g., orderId: "ORD-12345", status: "CONFIRMED", timestamp: "2024-01-15T10:30:00Z").
5. **Value types - STRICT TYPE MATCHING REQUIRED** - You MUST match the exact property type from the properties list above:
   - **String** → Use quoted strings: "sample text", "ORD-12345", "John Doe"
   - **Integer** or **int** or **Long** or **long** → Use numbers WITHOUT quotes: 123, 456, 1000
   - **Boolean** or **boolean** → Use true or false WITHOUT quotes: true, false
   - **Decimal** or **BigDecimal** or **Double** or **double** or **Float** or **float** → Use decimal numbers WITHOUT quotes: 100.50, 99.99, 0.01
   - **Date** or **LocalDate** → Use ISO date format string: "2024-01-15"
   - **DateTime** or **LocalDateTime** or **Timestamp** → Use ISO datetime format string: "2024-01-15T10:30:00Z" or "2024-01-15T10:30:00"
   - **UUID** → Use UUID format string: "550e8400-e29b-41d4-a716-446655440000"
   - **List<T>** or **Array** → Use JSON array format: ["item1", "item2"] or [1, 2, 3]
   - **Enum** → Use the enum value as a string from the enumeration items: "PENDING", "ACTIVE", "COMPLETED" (must match one of the enum items if available). For example, if an Enum property "status" has items ["PENDING", "ACTIVE", "COMPLETED"], use one of these exact values in fieldValues: {{"status": "PENDING"}}.
   - **ValueObject** → Use JSON object format with nested fields: {{"field1": "value1", "field2": 123}} (represent the ValueObject as a nested object with its fields). For example, if a ValueObject "Address" has fields [{{"name": "street", "type": "String"}}, {{"name": "city", "type": "String"}}], use: {{"address": {{"street": "123 Main St", "city": "Seoul"}}}}.
   
   **IMPORTANT**: 
   - Do NOT quote numbers or booleans. Do NOT use strings for numeric types. Always check the property type from the properties list and match it exactly.
   - For Enum types, use one of the enumeration item values (if enumeration items are provided in the properties list).
   - For ValueObject types, represent as a JSON object with the ValueObject's fields as nested properties.

If no properties are available, only then use empty fieldValues {{}}."""
    
    # LLM 호출
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                llm.invoke,
                [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
            ),
            timeout=300.0
        )
        
        # Parse JSON response
        content = response.content if hasattr(response, 'content') else str(response)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        gwt_test_cases = json.loads(content)
        if not isinstance(gwt_test_cases, list):
            gwt_test_cases = [gwt_test_cases]
        
        # Prepare test cases payload
        test_cases_payload: list[dict[str, Any]] = []
        for gwt_data in gwt_test_cases:
            given_data = gwt_data.get("given") or {}
            when_data = gwt_data.get("when") or {}
            then_data = gwt_data.get("then") or {}
            
            test_cases_payload.append({
                "scenarioDescription": gwt_data.get("scenarioDescription") or None,
                "givenFieldValues": (given_data.get("fieldValues") or {}) if isinstance(given_data, dict) else {},
                "whenFieldValues": (when_data.get("fieldValues") or {}) if isinstance(when_data, dict) else {},
                "thenFieldValues": (then_data.get("fieldValues") or {}) if isinstance(then_data, dict) else {},
            })
        
        # Determine when_ref
        if is_invoked_by_policy and policy_trigger_event_id:
            when_ref = {
                "referencedNodeId": policy_trigger_event_id,
                "referencedNodeType": "Event",
                "name": f"Event: {policy_trigger_event_name}",
            }
        else:
            when_ref = {
                "referencedNodeId": cmd.id,
                "referencedNodeType": "Command",
                "name": f"Command: {cmd.name}",
            }
        
        # Save to Neo4j using GWTOps
        gwt_ops = GWTOps(client)
        gwt_ops.upsert_gwt_bundle(
            parent_type="Command",
            parent_id=cmd.id,
            given_ref={
                "referencedNodeId": agg.id,
                "referencedNodeType": "Aggregate",
                "name": f"Aggregate: {agg.name}",
            },
            when_ref=when_ref,
            then_ref={
                "referencedNodeId": evt.id,
                "referencedNodeType": "Event",
                "name": f"Event: {evt.name}",
            } if evt else None,
            test_cases=test_cases_payload,
        )
        
        return max(len(test_cases_payload), 1)
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"Failed to generate GWT for Command {cmd.name}: {e}",
            category="ingestion.workflow.gwt.command_error",
            params={"session_id": ctx.session.id, "command_name": cmd.name, "error": str(e)}
        )
        # Fallback: create empty GWT bundle
        try:
            if is_invoked_by_policy and policy_trigger_event_id:
                fallback_when_ref = {
                    "referencedNodeId": policy_trigger_event_id,
                    "referencedNodeType": "Event",
                    "name": f"Event: {policy_trigger_event_name}",
                }
            else:
                fallback_when_ref = {
                    "referencedNodeId": cmd.id,
                    "referencedNodeType": "Command",
                    "name": f"Command: {cmd.name}",
                }
            
            gwt_ops = GWTOps(client)
            gwt_ops.upsert_gwt_bundle(
                parent_type="Command",
                parent_id=cmd.id,
                given_ref={
                    "referencedNodeId": agg.id,
                    "referencedNodeType": "Aggregate",
                    "name": f"Aggregate: {agg.name}",
                },
                when_ref=fallback_when_ref,
                then_ref={
                    "referencedNodeId": evt.id,
                    "referencedNodeType": "Event",
                    "name": f"Event: {evt.name}",
                } if evt else None,
                test_cases=[{
                    "scenarioDescription": None,
                    "givenFieldValues": {},
                    "whenFieldValues": {},
                    "thenFieldValues": {},
                }],
            )
            return 1
        except Exception:
            return 0


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
- **given:** Reference the Aggregate that handles the invoked Command. Include `name` (e.g., "Aggregate: <target_aggregate_name>") and optional `description`. The `fieldValues` dictionary should map property names from the Aggregate to realistic test values based on the properties listed above.
- **when:** Reference the trigger Event(s) that Policy receives. For each trigger event, include `name` (e.g., "Event: <event_name>") and optional `description`. The `fieldValues` dictionary should map property names from the trigger Event to realistic test values. If there are multiple trigger events, create a separate When for each trigger event.
- **then:** Reference the Event emitted by the invoked Command. Include `name` (e.g., "Event: <target_event_name>") and optional `description`. The `fieldValues` dictionary should map property names from the Event to realistic test values based on the properties listed above.

Return a JSON array with multiple test cases:
[
  {{
    "scenarioDescription": "Brief description of this test case's business flow",
    "given": {{
      "name": "Aggregate: <target_aggregate_name>",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue1", ...}}
    }},
    "when": [
      {{
        "name": "Event: <trigger_event_name>",
        "description": "...",
        "fieldValues": {{"propertyName": "testValue1", ...}}
      }}
    ],
    "then": {{
      "name": "Event: <target_event_name>",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue1", ...}}
    }}
  }},
  {{
    "scenarioDescription": "Brief description of this test case's business flow",
    "given": {{
      "name": "Aggregate: <target_aggregate_name>",
      "description": "...",
      "fieldValues": {{"propertyName": "testValue2", ...}}
    }},
    "when": [
      {{
        "name": "Event: <trigger_event_name>",
        "description": "...",
        "fieldValues": {{"propertyName": "testValue2", ...}}
      }}
    ],
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
    # Collect all commands with their context (BC, Aggregate, Event)
    all_command_tasks: list[dict[str, Any]] = []
    for bc in ctx.bounded_contexts:
        for agg in ctx.aggregates_by_bc.get(bc.id, []):
            commands = ctx.commands_by_agg.get(agg.id, [])
            events = ctx.events_by_agg.get(agg.id, [])
            
            for i, cmd in enumerate(commands):
                evt = events[i] if i < len(events) else (events[0] if events else None)
                all_command_tasks.append({
                    "bc": bc,
                    "agg": agg,
                    "cmd": cmd,
                    "evt": evt,
                    "cmd_index": i,
                })
    
    total_commands = len(all_command_tasks)
    
    # Estimate tokens for each command task
    # Each command prompt includes: command info, aggregate info, event info, instructions
    # Typical size: ~3000-6000 tokens per command (including properties, enumerations, valueObjects)
    def _estimate_command_tokens(task: dict[str, Any]) -> str:
        """Convert command task to text for token estimation"""
        cmd = task["cmd"]
        agg = task["agg"]
        evt = task["evt"]
        bc = task["bc"]
        
        # Estimate based on command, aggregate, event names and descriptions
        # This is a rough estimate - actual prompt will be longer with properties
        cmd_text = f"Command: {cmd.name} {getattr(cmd, 'description', '') or ''}"
        agg_text = f"Aggregate: {agg.name} {getattr(agg, 'description', '') or ''}"
        evt_text = f"Event: {evt.name if evt else 'Unknown'} {getattr(evt, 'description', '') if evt else ''}"
        bc_text = f"BC: {bc.name}"
        
        # Add estimated properties (rough: ~10 properties per entity, ~50 chars each)
        estimated_props = "Properties: " + " ".join([f"prop{i}" for i in range(10)])
        
        return f"{cmd_text} {agg_text} {evt_text} {bc_text} {estimated_props}"
    
    # Check if chunking is needed based on token estimation
    # Each command needs ~3000-6000 tokens, so max 15 commands per chunk (90k tokens max)
    # Use more conservative chunk size: 8 commands per chunk (48k tokens max)
    # This leaves room for system prompt, instructions, and output
    from api.features.ingestion.workflow.utils.chunking import estimate_tokens
    
    # Use should_chunk_list with proper token estimation
    # max_items=8: conservative chunk size to avoid token overflow
    # max_tokens=60000: leave room for system prompt, instructions, and output (100k total limit)
    if should_chunk_list(all_command_tasks, item_to_text=_estimate_command_tokens, max_items=8, max_tokens=60000):
        # Split into chunks with conservative size
        # chunk_size=8: max 8 commands per chunk (~48k tokens)
        # overlap_count=1: minimal overlap for GWT (less critical than extraction)
        command_chunks = split_list_with_overlap(all_command_tasks, chunk_size=8, overlap_count=1)
        total_chunks = len(command_chunks)
        
        chunk_results = []
        
        for chunk_idx, chunk_commands in enumerate(command_chunks):
            # Check cancellation before processing chunk
            if getattr(ctx.session, "is_cancelled", False):
                yield ProgressEvent(
                    phase=IngestionPhase.ERROR,
                    message="❌ 생성이 중단되었습니다",
                    progress=getattr(ctx.session, "progress", 0) or 0,
                    data={"error": "Cancelled by user", "cancelled": True},
                )
                return
            
            # Process all commands in this chunk in parallel using asyncio.gather
            chunk_start_idx = sum(len(chunk) for chunk in command_chunks[:chunk_idx])
            tasks = []
            for i, task in enumerate(chunk_commands):
                cmd_idx = chunk_start_idx + i + 1
                # Create async task for each command
                tasks.append(_generate_gwt_for_command(task, llm, client, ctx, cmd_idx, total_commands))
            
            # Execute all tasks in parallel
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                chunk_gwt_count = sum(r if isinstance(r, int) else 0 for r in results)
                total_gwt_created += chunk_gwt_count
                
                # Progress update
                progress = 91 + int((95 - 91) * (chunk_idx + 1) / max(total_chunks, 1))
                yield ProgressEvent(
                    phase=IngestionPhase.IDENTIFYING_POLICIES,
                    message=f"GWT 생성 중: 청크 {chunk_idx+1}/{total_chunks} 완료",
                    progress=min(progress, 95),
                )
            except Exception as e:
                SmartLogger.log(
                    "ERROR",
                    f"GWT chunk processing failed: {e}",
                    category="ingestion.workflow.gwt.chunk_error",
                    params={"session_id": ctx.session.id, "chunk_index": chunk_idx + 1, "error": str(e)}
                )
    else:
        # No chunking needed, process all commands in parallel
        command_chunks = [all_command_tasks]
        total_chunks = 1
        
        # Process all commands in parallel
        tasks = []
        for i, task in enumerate(all_command_tasks):
            tasks.append(_generate_gwt_for_command(task, llm, client, ctx, i + 1, total_commands))
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total_gwt_created = sum(r if isinstance(r, int) else 0 for r in results)
        except Exception as e:
            SmartLogger.log(
                "ERROR",
                f"GWT processing failed: {e}",
                category="ingestion.workflow.gwt.processing_error",
                params={"session_id": ctx.session.id, "error": str(e)}
            )
    
    # All commands have been processed in chunks above
    # Now proceed to Policy GWT generation (if needed)
    
    # Generate GWT for Policies
    # NOTE: Policy GWT generation is DISABLED.
    # Instead, Commands invoked by Policies will have their GWT's "when" field
    # set to the Policy's trigger Event (the Event that Policy receives).
    # This is because Policy always receives an Event and invokes a Command,
    # so the Command's GWT should reflect the trigger Event as the "when" condition.
    
    # Policy GWT generation code is commented out below
    # Uncomment if Policy-specific GWT is needed in the future
    if False:  # Policy GWT generation disabled
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
                        "ERROR",
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
                # LLM 호출을 비동기로 실행하고 타임아웃 추가
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        llm.invoke,
                        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
                    ),
                    timeout=300.0  # 5분 타임아웃
                )
                llm_ms = int((time.perf_counter() - t_llm0) * 1000)
            except asyncio.TimeoutError:
                llm_ms = int((time.perf_counter() - t_llm0) * 1000)
                SmartLogger.log(
                    "ERROR",
                    f"GWT LLM invoke timeout for Policy {policy_name}",
                    category="ingestion.llm.generate_gwt.policy.timeout",
                    params={
                        "session_id": ctx.session.id,
                        "policy_id": policy_id,
                        "policy_name": policy_name,
                        "elapsed_ms": llm_ms,
                    }
                )
                raise  # Re-raise to trigger fallback
                
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

                    # given is Aggregate (single object)
                    given_data = gwt_data.get("given") or {}
                    given_field_values = (given_data.get("fieldValues") or {}) if isinstance(given_data, dict) else {}

                    # when can be array (multiple trigger events) or single object
                    # If multiple trigger events, merge all their fieldValues
                    when_raw = gwt_data.get("when")
                    when_field_values = {}
                    if isinstance(when_raw, list):
                        # Merge fieldValues from all trigger events
                        for when_item in when_raw:
                            if isinstance(when_item, dict) and when_item.get("fieldValues"):
                                when_field_values.update(when_item["fieldValues"])
                    elif isinstance(when_raw, dict) and when_raw.get("fieldValues"):
                        when_field_values = when_raw["fieldValues"]

                    then_data = gwt_data.get("then") or {}

                    test_cases_payload.append(
                        {
                            "scenarioDescription": scenario_description or None,
                            "givenFieldValues": given_field_values,
                            "whenFieldValues": when_field_values,
                            "thenFieldValues": (then_data.get("fieldValues") or {}) if isinstance(then_data, dict) else {},
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
                            "referencedNodeId": target_agg_id,
                            "referencedNodeType": "Aggregate",
                            "name": f"Aggregate: {target_agg_name}" if target_agg_name else "Aggregate",
                        } if target_agg_id else None,
                        when_ref={
                            "referencedNodeId": given_event_id,
                            "referencedNodeType": "Event",
                            "name": f"Event: {given_event_name}" if given_event_name else "Event",
                        } if given_event_id else None,
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
                    if given_event_id or target_agg_id:
                        _upsert_gwt_bundle(
                            parent_type="Policy",
                            parent_id=policy_id,
                            given_ref={
                                "referencedNodeId": target_agg_id,
                                "referencedNodeType": "Aggregate",
                                "name": f"Aggregate: {target_agg_name}" if target_agg_name else "Aggregate",
                            } if target_agg_id else None,
                            when_ref={
                                "referencedNodeId": given_event_id,
                                "referencedNodeType": "Event",
                                "name": f"Event: {given_event_name}" if given_event_name else "Event",
                            } if given_event_id else None,
                            then_ref={
                                "referencedNodeId": target_event_id,
                                "referencedNodeType": "Event",
                                "name": f"Event: {target_event_name}" if target_event_name else "Event",
                            } if target_event_id else None,
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
    
    # 생성 결과 요약
    SmartLogger.log(
        "INFO",
        f"GWT generation completed: {total_gwt_created} GWT test cases created",
        category="ingestion.workflow.gwt.summary",
        params={"session_id": ctx.session.id, "gwt_count": total_gwt_created}
    )
    
    yield ProgressEvent(
        phase=IngestionPhase.IDENTIFYING_POLICIES,
        message=f"GWT 생성 완료 ({total_gwt_created}개 구성요소)",
        progress=92,
    )
