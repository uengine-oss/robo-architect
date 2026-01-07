"""
Event Storming LangGraph Agent

A LangGraph-based workflow for generating Event Storming models from User Stories.

Workflow:
1. Load User Stories from Neo4j
2. Identify Bounded Context candidates (one by one)
3. Break down User Stories within each Bounded Context
4. Extract Aggregates from breakdown
5. Extract Commands from Aggregates
6. Extract Events from Commands
7. Identify Policies for cross-BC communication

Human-in-the-loop checkpoints are provided for review and approval.
"""

from .graph import create_event_storming_graph
from .state import EventStormingState

__all__ = ["create_event_storming_graph", "EventStormingState"]

