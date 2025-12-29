"""
Event Storming Nodes (facade)

Business capability: LangGraph node functions for Event Storming workflow.

This file intentionally stays small and re-exports node functions grouped by workflow phase.
"""

from __future__ import annotations

# Structured outputs (used by other ingestion flows too)
from .structured_outputs import (
    AggregateList,
    BoundedContextList,
    CommandList,
    EventList,
    PolicyList,
)

# Node functions grouped by workflow phase
from .nodes_init import init_node, load_user_stories_node
from .nodes_bounded_contexts import approve_bc_node, identify_bc_node
from .nodes_breakdown import breakdown_user_story_node
from .nodes_aggregates import approve_aggregates_node, extract_aggregates_node
from .nodes_commands import extract_commands_node
from .nodes_events import extract_events_node
from .nodes_policies import approve_policies_node, identify_policies_node
from .nodes_persist import save_to_graph_node
from .nodes_routing import route_after_approval, route_by_phase

__all__ = [
    # Structured outputs
    "BoundedContextList",
    "AggregateList",
    "CommandList",
    "EventList",
    "PolicyList",
    # Nodes
    "init_node",
    "load_user_stories_node",
    "identify_bc_node",
    "approve_bc_node",
    "breakdown_user_story_node",
    "extract_aggregates_node",
    "approve_aggregates_node",
    "extract_commands_node",
    "extract_events_node",
    "identify_policies_node",
    "approve_policies_node",
    "save_to_graph_node",
    # Routing
    "route_after_approval",
    "route_by_phase",
]


