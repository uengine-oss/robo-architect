"""
Event Storming Nodes: GWT (Given/When/Then) generation

Post-processing step to generate GWT structures for Commands and Policies
after they have been created, using their actual properties.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
    get_llm_provider_model,
)
from api.platform.observability.request_logging import summarize_for_log
from api.platform.observability.smart_logger import SmartLogger

from .node_runtime import dump_model, get_llm
from .prompts import SYSTEM_PROMPT
from .state import EventStormingState, WorkflowPhase, GivenCandidate, WhenCandidate, ThenCandidate

GENERATE_GWT_PROMPT = """Generate Given/When/Then (GWT) structures for Commands and Policies to support BDD-style test scenarios.

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

For this Command, generate a GWT structure:
- **given:** Reference the Command itself. Include `name` (e.g., "Command: {command_name}") and optional `description`. The `fieldValues` dictionary should map property names from the Command to realistic test values based on the properties listed above.
- **when:** Reference the Aggregate that handles this Command. Include `name` (e.g., "Aggregate: {aggregate_name}") and optional `description`. The `fieldValues` dictionary should map property names from the Aggregate to realistic test values based on the properties listed above.
- **then:** Reference the Event emitted by this Command. Include `name` (e.g., "Event: {event_name}") and optional `description`. The `fieldValues` dictionary should map property names from the Event to realistic test values based on the properties listed above.

Return a JSON object with:
{{
  "given": {{
    "name": "Command: {command_name}",
    "description": "...",
    "fieldValues": {{"propertyName": "testValue", ...}}
  }},
  "when": {{
    "name": "Aggregate: {aggregate_name}",
    "description": "...",
    "fieldValues": {{"propertyName": "testValue", ...}}
  }},
  "then": {{
    "name": "Event: {event_name}",
    "description": "...",
    "fieldValues": {{"propertyName": "testValue", ...}}
  }}
}}

If properties are not available or empty, use empty fieldValues {{}}.
"""


def generate_gwt_node(state: EventStormingState) -> Dict[str, Any]:
    """Generate GWT structures for Commands and Policies using their actual properties."""
    llm = get_llm()
    
    command_count = sum(len(cmds) for cmds in state.command_candidates.values())
    policy_count = len(state.approved_policies)
    
    SmartLogger.log(
        "INFO",
        "EventStorming: generate_gwt_node started.",
        category="agent.nodes.generate_gwt.start",
        params={
            "command_count": command_count,
            "policy_count": policy_count,
            "command_candidates_keys": list(state.command_candidates.keys()),
        }
    )
    
    # Early return if no commands to process
    if command_count == 0:
        SmartLogger.log(
            "WARN",
            "EventStorming: generate_gwt_node - No commands found, skipping GWT generation.",
            category="agent.nodes.generate_gwt.skip",
            params={"command_candidates": state.command_candidates}
        )
        return {
            "phase": WorkflowPhase.SAVE_TO_GRAPH,
            "messages": [AIMessage(content="No commands found. Skipping GWT generation. Ready to save to graph...")],
        }
    
    # Generate GWT for Commands
    for agg_id, commands in state.command_candidates.items():
        # Find aggregate
        agg = None
        for bc_id, aggregates in state.approved_aggregates.items():
            for a in aggregates:
                if a.id == agg_id:
                    agg = a
                    break
            if agg:
                break
        
        if not agg:
            continue
        
        # Find events for this aggregate's commands
        # event_candidates is organized by aggregate_id: [events]
        aggregate_events = state.event_candidates.get(agg_id, [])
        events_by_command = {}
        
        # Map events to commands by index (simple heuristic: first event to first command, etc.)
        # This is a fallback - ideally events should be explicitly linked to commands
        for i, cmd in enumerate(commands):
            if i < len(aggregate_events):
                events_by_command[cmd.id] = aggregate_events[i]
            elif aggregate_events:
                # If more commands than events, use first event for remaining commands
                events_by_command[cmd.id] = aggregate_events[0]
            else:
                events_by_command[cmd.id] = None
        
        for cmd in commands:
            # Get command properties (if available)
            cmd_props = []
            # Properties would be available after property generation phase
            # For now, we'll work with what we have
            
            # Get aggregate properties
            agg_props = []
            
            # Get event properties
            evt = events_by_command.get(cmd.id)
            evt_props = []
            
            # Format properties as text
            cmd_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in cmd_props]) if cmd_props else "No properties available yet"
            agg_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in agg_props]) if agg_props else "No properties available yet"
            evt_props_text = "\n".join([f"- {p.get('name', '')}: {p.get('type', '')}" for p in evt_props]) if evt and evt_props else "No properties available yet"
            
            prompt = GENERATE_GWT_PROMPT.format(
                command_name=cmd.name,
                command_description=cmd.description,
                command_properties=cmd_props_text,
                aggregate_name=agg.name,
                aggregate_properties=agg_props_text,
                event_name=evt.name if evt else "UnknownEvent",
                event_description=evt.description if evt else "Event will be emitted",
                event_properties=evt_props_text,
            )
            
            provider, model = get_llm_provider_model()
            if AI_AUDIT_LOG_ENABLED:
                SmartLogger.log(
                    "INFO",
                    "EventStorming: generate GWT - LLM invoke starting.",
                    category="agent.nodes.generate_gwt.llm.start",
                    params={
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
                import json
                content = response.content if hasattr(response, 'content') else str(response)
                # Extract JSON from markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                gwt_data = json.loads(content)
                
                # Update command's GWT (dynamically add fields using setattr)
                if gwt_data.get("given"):
                    given_data = gwt_data["given"]
                    setattr(cmd, "given", GivenCandidate(
                        name=given_data.get("name", f"Command: {cmd.name}"),
                        description=given_data.get("description"),
                        referencedNodeId=cmd.id,
                        referencedNodeType="Command",
                        fieldValues=given_data.get("fieldValues", {})
                    ))
                
                if gwt_data.get("when"):
                    when_data = gwt_data["when"]
                    setattr(cmd, "when", WhenCandidate(
                        name=when_data.get("name", f"Aggregate: {agg.name}"),
                        description=when_data.get("description"),
                        referencedNodeId=agg.id,
                        referencedNodeType="Aggregate",
                        fieldValues=when_data.get("fieldValues", {})
                    ))
                
                if gwt_data.get("then") and evt:
                    then_data = gwt_data["then"]
                    setattr(cmd, "then", ThenCandidate(
                        name=then_data.get("name", f"Event: {evt.name}"),
                        description=then_data.get("description"),
                        referencedNodeId=evt.id,
                        referencedNodeType="Event",
                        fieldValues=then_data.get("fieldValues", {})
                    ))
                
                if AI_AUDIT_LOG_ENABLED:
                    cmd_given = getattr(cmd, "given", None)
                    cmd_when = getattr(cmd, "when", None)
                    cmd_then = getattr(cmd, "then", None)
                    SmartLogger.log(
                        "INFO",
                        "EventStorming: generate GWT - LLM invoke completed.",
                        category="agent.nodes.generate_gwt.llm.done",
                        params={
                            "llm": {"provider": provider, "model": model},
                            "command": {"id": cmd.id, "name": cmd.name},
                            "llm_ms": llm_ms,
                            "gwt_generated": bool(cmd_given or cmd_when or cmd_then),
                        }
                    )
            except Exception as e:
                SmartLogger.log(
                    "WARN",
                    f"EventStorming: generate GWT - LLM invoke failed for command {cmd.name}: {e}. Creating fallback GWT.",
                    category="agent.nodes.generate_gwt.llm.error",
                    params={
                        "llm": {"provider": provider, "model": model},
                        "command": {"id": cmd.id, "name": cmd.name},
                        "error": str(e),
                    }
                )
                # Fallback: Create basic GWT structure without fieldValues
                setattr(cmd, "given", GivenCandidate(
                    name=f"Command: {cmd.name}",
                    description=cmd.description or f"Command {cmd.name} is available",
                    referencedNodeId=cmd.id,
                    referencedNodeType="Command",
                    fieldValues={}
                ))
                setattr(cmd, "when", WhenCandidate(
                    name=f"Aggregate: {agg.name}",
                    description=f"Aggregate {agg.name} handles this command",
                    referencedNodeId=agg.id,
                    referencedNodeType="Aggregate",
                    fieldValues={}
                ))
                if evt:
                    setattr(cmd, "then", ThenCandidate(
                        name=f"Event: {evt.name}",
                        description=f"Event {evt.name} is emitted",
                        referencedNodeId=evt.id,
                        referencedNodeType="Event",
                        fieldValues={}
                    ))
    
    # Generate GWT for Policies (similar logic)
    for pol in state.approved_policies:
        # Find trigger event
        trigger_event = None
        for events in state.event_candidates.values():
            for evt in events:
                if evt.name == pol.trigger_event:
                    trigger_event = evt
                    break
            if trigger_event:
                break
        
        # Find target aggregate and command
        target_agg = None
        target_cmd = None
        for bc in state.approved_bcs:
            if bc.name == pol.target_bc or bc.id == pol.target_bc:
                for agg in state.approved_aggregates.get(bc.id, []):
                    for cmd in state.command_candidates.get(agg.id, []):
                        if cmd.name == pol.invoke_command:
                            target_agg = agg
                            target_cmd = cmd
                            break
                    if target_agg:
                        break
                if target_agg:
                    break
        
        # Find event emitted by target command
        target_event = None
        if target_cmd:
            for events in state.event_candidates.values():
                for evt in events:
                    # Simple heuristic: first event in same BC
                    if target_agg and evt.id in [e.id for e in events if True]:  # Simplified
                        target_event = evt
                        break
                if target_event:
                    break
        
        if trigger_event and target_agg and target_event:
            # Generate GWT for policy (similar to command)
            # For now, use auto-generated GWT from identify_policies_node
            # Can be enhanced later with LLM call if needed
            pass
    
    # Return updated state with GWT fields
    # Note: command_candidates and approved_policies are updated in-place via setattr,
    # so we don't need to explicitly return them, but we should log the results
    gwt_count = 0
    for agg_id, commands in state.command_candidates.items():
        for cmd in commands:
            if hasattr(cmd, "given") or hasattr(cmd, "when") or hasattr(cmd, "then"):
                gwt_count += 1
    
    for pol in state.approved_policies:
        if hasattr(pol, "given") or hasattr(pol, "when") or hasattr(pol, "then"):
            gwt_count += 1
    
    SmartLogger.log(
        "INFO",
        f"EventStorming: generate GWT completed. Generated GWT for {gwt_count} items.",
        category="agent.nodes.generate_gwt.complete",
        params={"gwt_count": gwt_count}
    )
    
    return {
        "phase": WorkflowPhase.SAVE_TO_GRAPH,
        "messages": [AIMessage(content=f"Generated GWT structures for {gwt_count} Commands and Policies. Ready to save to graph...")],
    }
