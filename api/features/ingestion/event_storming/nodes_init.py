"""
Event Storming Nodes: initialization + loading user stories
"""

from __future__ import annotations

from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from .neo4j_client import get_neo4j_client
from .prompts import SYSTEM_PROMPT
from .state import EventStormingState, WorkflowPhase, format_user_story


def init_node(state: EventStormingState) -> Dict[str, Any]:
    """Initialize the workflow."""
    return {
        "phase": WorkflowPhase.LOAD_USER_STORIES,
        "messages": [SystemMessage(content=SYSTEM_PROMPT)],
    }


def load_user_stories_node(state: EventStormingState) -> Dict[str, Any]:
    """Load unprocessed user stories from Neo4j."""
    client = get_neo4j_client()

    # First try to get unprocessed stories
    user_stories = client.get_unprocessed_user_stories()

    # If none, get all stories for demo purposes
    if not user_stories:
        user_stories = client.get_all_user_stories()

    if not user_stories:
        return {
            "phase": WorkflowPhase.COMPLETE,
            "error": "No user stories found in Neo4j. Please load sample data first.",
        }

    # Format stories for display
    stories_text = "\n".join([f"- [{us['id']}] {format_user_story(us)}" for us in user_stories])

    return {
        "user_stories": user_stories,
        "total_user_stories": len(user_stories),
        "phase": WorkflowPhase.IDENTIFY_BC,
        "messages": [HumanMessage(content=f"Loaded {len(user_stories)} user stories:\n{stories_text}")],
    }


