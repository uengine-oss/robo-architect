"""
Event Storming Nodes: persist generated artifacts into Neo4j
"""

from __future__ import annotations

from typing import Any, Dict

from langchain_core.messages import AIMessage

from .neo4j_client import get_neo4j_client
from .state import EventStormingState, WorkflowPhase


def save_to_graph_node(state: EventStormingState) -> Dict[str, Any]:
    """Save all generated artifacts to Neo4j."""
    client = get_neo4j_client()
    saved_items = []

    try:
        bc_id_map: dict[str, str] = {}
        agg_id_map: dict[str, str] = {}

        # 1. Create Bounded Contexts
        for bc in state.approved_bcs:
            old_id = str(bc.id)
            domain_type = getattr(bc, "domain_type", None)
            created_bc = client.create_bounded_context(
                name=bc.name,
                description=bc.description,
                domain_type=domain_type
            )
            bc_id_map[old_id] = str(created_bc.get("id"))
            try:
                bc.id = created_bc.get("id")
            except Exception:
                pass
            saved_items.append(f"BC: {bc.name}")

            # Link user stories to BC
            for us_id in bc.user_story_ids:
                link_result = client.link_user_story_to_bc(us_id, bc_id_map[old_id])
                # link_user_story_to_bc는 (success, diagnostic) 튜플을 반환
                if isinstance(link_result, tuple):
                    success, _ = link_result
                    if not success:
                        # 연결 실패는 무시 (이미 로그에 기록됨)
                        pass

        # 2. Create Aggregates and link to User Stories
        for bc_id, aggregates in state.approved_aggregates.items():
            bc_uuid = bc_id_map.get(str(bc_id)) or str(bc_id)
            for agg in aggregates:
                old_agg_id = str(agg.id)
                # Convert enumerations and value_objects to dict format
                enum_list = [
                    {
                        "name": e.name,
                        "alias": e.alias,
                        "items": getattr(e, "items", []) or []
                    }
                    for e in (agg.enumerations or [])
                ]
                vo_list = [
                    {
                        "name": vo.name,
                        "alias": vo.alias,
                        "referenced_aggregate_name": vo.referenced_aggregate_name,
                        "referenced_aggregate_field": getattr(vo, "referenced_aggregate_field", None),
                        "fields": getattr(vo, "fields", []) or []
                    }
                    for vo in (agg.value_objects or [])
                ]
                created_agg = client.create_aggregate(
                    name=agg.name,
                    bc_id=bc_uuid,
                    root_entity=agg.root_entity,
                    invariants=agg.invariants,
                    enumerations=enum_list if enum_list else None,
                    value_objects=vo_list if vo_list else None,
                )
                agg_id_map[old_agg_id] = str(created_agg.get("id"))
                try:
                    agg.id = created_agg.get("id")
                except Exception:
                    pass
                saved_items.append(f"  Aggregate: {agg.name}")

                # Link user stories to aggregate (IMPLEMENTS)
                for us_id in agg.user_story_ids:
                    try:
                        client.link_user_story_to_aggregate(us_id, agg_id_map[old_agg_id])
                    except Exception:
                        pass  # User story might not exist

        # 3. Create Commands and link to User Stories
        for agg_id, commands in state.command_candidates.items():
            agg_uuid = agg_id_map.get(str(agg_id)) or str(agg_id)
            for cmd in commands:
                category = getattr(cmd, "category", None)
                input_schema = getattr(cmd, "inputSchema", None)
                created_cmd = client.create_command(
                    name=cmd.name,
                    aggregate_id=agg_uuid,
                    actor=cmd.actor,
                    category=category,
                    input_schema=input_schema,
                )
                try:
                    cmd.id = created_cmd.get("id")
                except Exception:
                    pass
                saved_items.append(f"    Command: {cmd.name}")

                # Link user stories to command (IMPLEMENTS)
                for us_id in cmd.user_story_ids:
                    try:
                        client.link_user_story_to_command(us_id, str(cmd.id))
                    except Exception:
                        pass  # User story might not exist

                # Create GWT for Command (using getattr for dynamically added fields)
                cmd_id = created_cmd.get("id")
                cmd_given = getattr(cmd, "given", None)
                if cmd_given:
                    try:
                        client.create_given(
                            parent_type="Command",
                            parent_id=cmd_id,
                            name=cmd_given.name,
                            description=cmd_given.description,
                            referenced_node_id=cmd_given.referencedNodeId,
                            referenced_node_type=cmd_given.referencedNodeType,
                            field_values=cmd_given.fieldValues if hasattr(cmd_given, 'fieldValues') else None,
                        )
                    except Exception:
                        pass
                cmd_when = getattr(cmd, "when", None)
                if cmd_when:
                    try:
                        client.create_when(
                            parent_type="Command",
                            parent_id=cmd_id,
                            name=cmd_when.name,
                            description=cmd_when.description,
                            referenced_node_id=cmd_when.referencedNodeId,
                            referenced_node_type=cmd_when.referencedNodeType,
                            field_values=cmd_when.fieldValues if hasattr(cmd_when, 'fieldValues') else None,
                        )
                    except Exception:
                        pass
                # Then will be created after events are created (below)

        # 4. Create Events and link to User Stories
        # Track command-to-event mapping for GWT Then updates
        cmd_to_event_map = {}  # {cmd_id: [event_id, ...]}
        
        for agg_id, events in state.event_candidates.items():
            commands = state.command_candidates.get(agg_id, [])
            for i, evt in enumerate(events):
                # Link to corresponding command if available
                cmd_id = commands[i].id if i < len(commands) else commands[0].id if commands else None
                if cmd_id:
                    version = getattr(evt, "version", "1.0.0")
                    payload = getattr(evt, "payload", None)
                    created_evt = client.create_event(
                        name=evt.name,
                        command_id=str(cmd_id),
                        version=version,
                        payload=payload,
                    )
                    try:
                        evt.id = created_evt.get("id")
                        # Track command-to-event mapping for GWT Then
                        cmd_id_str = str(cmd_id)
                        if cmd_id_str not in cmd_to_event_map:
                            cmd_to_event_map[cmd_id_str] = []
                        cmd_to_event_map[cmd_id_str].append({
                            "id": created_evt.get("id"),
                            "name": evt.name
                        })
                    except Exception:
                        pass
                    saved_items.append(f"      Event: {evt.name}")

                    # Link user stories to event (IMPLEMENTS)
                    for us_id in evt.user_story_ids:
                        try:
                            client.link_user_story_to_event(us_id, str(evt.id))
                        except Exception:
                            pass  # User story might not exist
        
        # Update Command's Then component with the created events
        for agg_id, commands in state.command_candidates.items():
            for cmd in commands:
                if not cmd.id:
                    continue
                cmd_id_str = str(cmd.id)
                event_list = cmd_to_event_map.get(cmd_id_str, [])
                cmd_then = getattr(cmd, "then", None)
                if event_list and cmd_then:
                    # Use the first event for the Then component
                    first_event = event_list[0]
                    try:
                        client.create_then(
                            parent_type="Command",
                            parent_id=cmd_id_str,
                            name=cmd_then.name or f"Event: {first_event['name']}",
                            description=cmd_then.description or f"{first_event['name']} 이벤트가 발생함",
                            referenced_node_id=first_event["id"],
                            referenced_node_type="Event",
                            field_values=cmd_then.fieldValues if hasattr(cmd_then, 'fieldValues') else None,
                        )
                    except Exception:
                        pass

        # 5. Create Policies
        for pol in state.approved_policies:
            # Find the event and command IDs
            trigger_event_id = None
            invoke_command_id = None
            target_bc_id = None

            # Find event ID
            for events in state.event_candidates.values():
                for evt in events:
                    if evt.name == pol.trigger_event:
                        trigger_event_id = evt.id
                        break

            # Find command ID and BC ID
            for bc in state.approved_bcs:
                if bc.name == pol.target_bc or bc.id == pol.target_bc:
                    target_bc_id = bc.id
                    for agg in state.approved_aggregates.get(bc.id, []):
                        for cmd in state.command_candidates.get(agg.id, []):
                            if cmd.name == pol.invoke_command:
                                invoke_command_id = cmd.id
                                break

            if trigger_event_id and invoke_command_id and target_bc_id:
                created_pol = client.create_policy(
                    name=pol.name,
                    bc_id=str(target_bc_id),
                    trigger_event_id=trigger_event_id,
                    invoke_command_id=invoke_command_id,
                    description=pol.description,
                )
                try:
                    pol.id = created_pol.get("id")
                except Exception:
                    pass
                saved_items.append(f"  Policy: {pol.name}")
                
                # Create GWT for Policy (using getattr for dynamically added fields)
                pol_id = created_pol.get("id")
                pol_given = getattr(pol, "given", None)
                if pol_given:
                    try:
                        client.create_given(
                            parent_type="Policy",
                            parent_id=pol_id,
                            name=pol_given.name,
                            description=pol_given.description,
                            referenced_node_id=pol_given.referencedNodeId,
                            referenced_node_type=pol_given.referencedNodeType,
                            field_values=pol_given.fieldValues if hasattr(pol_given, 'fieldValues') else None,
                        )
                    except Exception:
                        pass
                pol_when = getattr(pol, "when", None)
                if pol_when:
                    try:
                        client.create_when(
                            parent_type="Policy",
                            parent_id=pol_id,
                            name=pol_when.name,
                            description=pol_when.description,
                            referenced_node_id=pol_when.referencedNodeId,
                            referenced_node_type=pol_when.referencedNodeType,
                            field_values=pol_when.fieldValues if hasattr(pol_when, 'fieldValues') else None,
                        )
                    except Exception:
                        pass
                pol_then = getattr(pol, "then", None)
                if pol_then:
                    try:
                        client.create_then(
                            parent_type="Policy",
                            parent_id=pol_id,
                            name=pol_then.name,
                            description=pol_then.description,
                            referenced_node_id=pol_then.referencedNodeId,
                            referenced_node_type=pol_then.referencedNodeType,
                            field_values=pol_then.fieldValues if hasattr(pol_then, 'fieldValues') else None,
                        )
                    except Exception:
                        pass

        return {
            "phase": WorkflowPhase.COMPLETE,
            "messages": [
                AIMessage(
                    content=f"✅ Successfully saved to Neo4j!\n\n"
                    f"Created items:\n"
                    + "\n".join(saved_items)
                    + f"\n\nYou can now view the graph in Neo4j Browser at http://localhost:7474"
                )
            ],
        }

    except Exception as e:
        return {
            "phase": WorkflowPhase.COMPLETE,
            "error": str(e),
            "messages": [AIMessage(content=f"❌ Error saving to Neo4j: {str(e)}")],
        }


