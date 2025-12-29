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
        # 1. Create Bounded Contexts
        for bc in state.approved_bcs:
            client.create_bounded_context(
                id=bc.id,
                name=bc.name,
                description=bc.description,
            )
            saved_items.append(f"BC: {bc.name}")

            # Link user stories to BC
            for us_id in bc.user_story_ids:
                client.link_user_story_to_bc(us_id, bc.id)

        # 2. Create Aggregates and link to User Stories
        for bc_id, aggregates in state.approved_aggregates.items():
            for agg in aggregates:
                client.create_aggregate(
                    id=agg.id,
                    name=agg.name,
                    bc_id=bc_id,
                    root_entity=agg.root_entity,
                    invariants=agg.invariants,
                )
                saved_items.append(f"  Aggregate: {agg.name}")

                # Link user stories to aggregate (IMPLEMENTS)
                for us_id in agg.user_story_ids:
                    try:
                        client.link_user_story_to_aggregate(us_id, agg.id)
                    except Exception:
                        pass  # User story might not exist

        # 3. Create Commands and link to User Stories
        for agg_id, commands in state.command_candidates.items():
            for cmd in commands:
                client.create_command(
                    id=cmd.id,
                    name=cmd.name,
                    aggregate_id=agg_id,
                    actor=cmd.actor,
                )
                saved_items.append(f"    Command: {cmd.name}")

                # Link user stories to command (IMPLEMENTS)
                for us_id in cmd.user_story_ids:
                    try:
                        client.link_user_story_to_command(us_id, cmd.id)
                    except Exception:
                        pass  # User story might not exist

        # 4. Create Events and link to User Stories
        for agg_id, events in state.event_candidates.items():
            commands = state.command_candidates.get(agg_id, [])
            for i, evt in enumerate(events):
                # Link to corresponding command if available
                cmd_id = commands[i].id if i < len(commands) else commands[0].id if commands else None
                if cmd_id:
                    client.create_event(
                        id=evt.id,
                        name=evt.name,
                        command_id=cmd_id,
                    )
                    saved_items.append(f"      Event: {evt.name}")

                    # Link user stories to event (IMPLEMENTS)
                    for us_id in evt.user_story_ids:
                        try:
                            client.link_user_story_to_event(us_id, evt.id)
                        except Exception:
                            pass  # User story might not exist

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
                client.create_policy(
                    id=pol.id,
                    name=pol.name,
                    bc_id=target_bc_id,
                    trigger_event_id=trigger_event_id,
                    invoke_command_id=invoke_command_id,
                    description=pol.description,
                )
                saved_items.append(f"  Policy: {pol.name}")

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


