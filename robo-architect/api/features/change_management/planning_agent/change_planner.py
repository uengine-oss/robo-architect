"""
LLM-based Change Plan Generator for User Story Modifications

This module uses an LLM to analyze changes to User Stories and generate
a comprehensive change plan for connected domain objects.

The change planner:
1. Analyzes what changed in the User Story (role, action, benefit)
2. Identifies which connected objects (Aggregate, Command, Event) need updates
3. Generates specific changes for each object
4. Supports revision based on human feedback (human-in-the-loop)
"""

from __future__ import annotations

import json
import time
from typing import Optional, List

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    AI_AUDIT_LOG_FULL_PROMPT,
    get_llm_provider_model,
)
from api.platform.observability.smart_logger import SmartLogger
from api.platform.observability.request_logging import summarize_for_log, sha256_text


# =============================================================================
# LLM Audit Logging (prompt/output + performance)
# =============================================================================


# =============================================================================
# Pydantic Models for Structured Output
# =============================================================================


class ChangeItem(BaseModel):
    """A single change in the plan."""
    action: str = Field(..., description="Type of change: rename, update, create, or delete")
    targetType: str = Field(..., description="Type of target: Aggregate, Command, or Event")
    targetId: str = Field(..., description="ID of the target node")
    targetName: str = Field(..., description="Current name of the target")
    from_value: Optional[str] = Field(None, description="Original value (for rename)")
    to_value: Optional[str] = Field(None, description="New value (for rename)")
    description: str = Field(..., description="Description of the change")
    reason: str = Field(..., description="Why this change is needed")
    
    class Config:
        populate_by_name = True


class ChangePlan(BaseModel):
    """Complete change plan for a User Story modification."""
    changes: List[ChangeItem] = Field(default_factory=list, description="List of changes to apply")


# =============================================================================
# System Prompt
# =============================================================================

CHANGE_PLANNER_SYSTEM_PROMPT = """You are a Domain-Driven Design (DDD) expert helping to maintain consistency in an Event Storming model.

When a User Story is modified, you analyze the impact on connected domain objects and generate a change plan.

Your task is to:
1. Understand what changed in the User Story
2. Identify which connected objects (Aggregate, Command, Event) need to be updated
3. Generate specific, actionable changes for each object

Guidelines:
- Command names should be verbs in PascalCase (e.g., PlaceOrder, UpdateCart)
- Event names should be past tense in PascalCase (e.g., OrderPlaced, CartUpdated)
- Aggregate names should be nouns in PascalCase (e.g., Order, Cart)
- Keep changes minimal and focused - only change what's necessary
- Preserve domain semantics while updating names and descriptions

Available actions:
- rename: Change the name of an object
- update: Update properties like description
- create: Create a new object (rare, only when story adds new capability)
- delete: Mark object as no longer needed (rare)

Always explain the reason for each change."""


CHANGE_PLANNER_PROMPT = """A User Story has been modified. Please analyze the impact and generate a change plan.

## Original User Story
ID: {user_story_id}
Role: {original_role}
Action: {original_action}
Benefit: {original_benefit}

## Modified User Story
Role: {edited_role}
Action: {edited_action}
Benefit: {edited_benefit}

## What Changed
{change_summary}

## Connected Objects That May Need Updates
{impacted_nodes_text}

## Your Task
Analyze the changes and determine which connected objects need to be updated.
For each object that needs a change, provide:
- action: What type of change (rename, update, create, delete)
- targetType: The type of object (Aggregate, Command, Event)
- targetId: The ID of the object
- targetName: Current name
- from_value: Original value (for rename)
- to_value: New value (for rename)
- description: What the change does
- reason: Why this change is necessary

Return a JSON object with a "changes" array. Only include objects that actually need changes.
If no changes are needed for the connected objects, return an empty changes array.

Think carefully about whether each object needs to change based on the User Story modification."""


REVISION_PROMPT = """The user has provided feedback on your change plan. Please revise the plan accordingly.

## Original Change Plan
{previous_plan}

## User Feedback
{feedback}

## Context
- User Story ID: {user_story_id}
- Original Story: As a {original_role}, I want to {original_action}, so that {original_benefit}
- Edited Story: As a {edited_role}, I want to {edited_action}, so that {edited_benefit}

## Connected Objects
{impacted_nodes_text}

## Your Task
Revise the change plan based on the user's feedback. The user may want to:
- Skip certain changes
- Modify the proposed changes
- Add additional changes
- Adjust the scope of changes

Return a JSON object with the revised "changes" array."""


# =============================================================================
# Helper Functions
# =============================================================================


def get_llm():
    """Get the configured LLM instance."""
    provider, model = get_llm_provider_model()

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0)
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0)


def format_impacted_nodes(nodes: List[dict]) -> str:
    """Format impacted nodes for the prompt."""
    if not nodes:
        return "No connected objects found."
    
    lines = []
    for node in nodes:
        node_type = node.get("type", "Unknown")
        node_id = node.get("id", "?")
        node_name = node.get("name", "?")
        
        if node_type == "Aggregate":
            lines.append(f"- 📦 Aggregate [{node_id}]: {node_name}")
            if node.get("rootEntity"):
                lines.append(f"  Root Entity: {node.get('rootEntity')}")
        elif node_type == "Command":
            lines.append(f"- ⚡ Command [{node_id}]: {node_name}")
            if node.get("actor"):
                lines.append(f"  Actor: {node.get('actor')}")
        elif node_type == "Event":
            lines.append(f"- 📣 Event [{node_id}]: {node_name}")
    
    return "\n".join(lines)


def format_change_summary(original: dict, edited: dict) -> str:
    """Format a summary of what changed."""
    changes = []
    
    orig_role = original.get("role", "")
    edit_role = edited.get("role", "")
    if orig_role != edit_role:
        changes.append(f"- Role changed from '{orig_role}' to '{edit_role}'")
    
    orig_action = original.get("action", "")
    edit_action = edited.get("action", "")
    if orig_action != edit_action:
        changes.append(f"- Action changed from '{orig_action}' to '{edit_action}'")
    
    orig_benefit = original.get("benefit", "")
    edit_benefit = edited.get("benefit", "")
    if orig_benefit != edit_benefit:
        changes.append(f"- Benefit changed from '{orig_benefit}' to '{edit_benefit}'")
    
    return "\n".join(changes) if changes else "No textual changes detected."


# =============================================================================
# Main Function
# =============================================================================


def generate_change_plan(
    user_story_id: str,
    original_user_story: Optional[dict],
    edited_user_story: dict,
    impacted_nodes: List[dict],
    feedback: Optional[str] = None,
    previous_plan: Optional[List[dict]] = None
) -> List[dict]:
    """
    Generate a change plan for User Story modifications.
    
    Args:
        user_story_id: ID of the user story being edited
        original_user_story: Original user story data
        edited_user_story: Edited user story data
        impacted_nodes: List of connected objects that may need changes
        feedback: Optional human feedback for plan revision
        previous_plan: Previous plan to revise (used with feedback)
    
    Returns:
        List of changes to apply
    """
    llm = get_llm()
    
    # Default original values if not provided
    if original_user_story is None:
        original_user_story = {}
    
    original_role = original_user_story.get("role", "user")
    original_action = original_user_story.get("action", "")
    original_benefit = original_user_story.get("benefit", "")
    
    edited_role = edited_user_story.get("role", "user")
    edited_action = edited_user_story.get("action", "")
    edited_benefit = edited_user_story.get("benefit", "")
    
    impacted_nodes_text = format_impacted_nodes(impacted_nodes)
    change_summary = format_change_summary(original_user_story, edited_user_story)
    
    if feedback and previous_plan:
        # Revision mode - incorporate feedback
        prompt = REVISION_PROMPT.format(
            previous_plan=json.dumps(previous_plan, indent=2),
            feedback=feedback,
            user_story_id=user_story_id,
            original_role=original_role,
            original_action=original_action,
            original_benefit=original_benefit,
            edited_role=edited_role,
            edited_action=edited_action,
            edited_benefit=edited_benefit,
            impacted_nodes_text=impacted_nodes_text
        )
    else:
        # Initial plan generation
        prompt = CHANGE_PLANNER_PROMPT.format(
            user_story_id=user_story_id,
            original_role=original_role,
            original_action=original_action,
            original_benefit=original_benefit,
            edited_role=edited_role,
            edited_action=edited_action,
            edited_benefit=edited_benefit,
            change_summary=change_summary,
            impacted_nodes_text=impacted_nodes_text
        )
    
    # Use structured output
    structured_llm = llm.with_structured_output(ChangePlan)
    
    provider, model = get_llm_provider_model()
    if AI_AUDIT_LOG_ENABLED:
        SmartLogger.log(
            "INFO",
            "Change planner: LLM invoke starting.",
            category="agent.change_planner.llm.start",
            params={
                "llm": {"provider": provider, "model": model},
                "user_story_id": user_story_id,
                "revision_mode": bool(feedback and previous_plan),
                "impacted_nodes_count": len(impacted_nodes or []),
                "prompt_len": len(prompt),
                "prompt_sha256": sha256_text(prompt),
                "prompt": prompt if AI_AUDIT_LOG_FULL_PROMPT else summarize_for_log(prompt),
                "system_len": len(CHANGE_PLANNER_SYSTEM_PROMPT),
                "system_sha256": sha256_text(CHANGE_PLANNER_SYSTEM_PROMPT),
            }
        )

    t_llm0 = time.perf_counter()
    response = structured_llm.invoke(
        [SystemMessage(content=CHANGE_PLANNER_SYSTEM_PROMPT), HumanMessage(content=prompt)]
    )
    llm_ms = int((time.perf_counter() - t_llm0) * 1000)

    if AI_AUDIT_LOG_ENABLED:
        try:
            resp_dump = response.model_dump() if hasattr(response, "model_dump") else response.dict()
        except Exception:
            resp_dump = {"__type__": type(response).__name__, "__repr__": repr(response)[:1000]}
        SmartLogger.log(
            "INFO",
            "Change planner: LLM invoke completed.",
            category="agent.change_planner.llm.done",
            params={
                "llm": {"provider": provider, "model": model},
                "user_story_id": user_story_id,
                "llm_ms": llm_ms,
                "changes_count": len(getattr(response, "changes", []) or []),
                "response": resp_dump if AI_AUDIT_LOG_FULL_OUTPUT else summarize_for_log(resp_dump),
            }
        )
    
    # Convert to dict format for API response
    changes = []
    for change in response.changes:
        change_dict = {
            "action": change.action,
            "targetType": change.targetType,
            "targetId": change.targetId,
            "targetName": change.targetName,
            "description": change.description,
            "reason": change.reason
        }
        
        if change.from_value:
            change_dict["from"] = change.from_value
        if change.to_value:
            change_dict["to"] = change.to_value
        
        changes.append(change_dict)
    
    return changes


# =============================================================================
# Testing
# =============================================================================


if __name__ == "__main__":
    # Test the change planner
    test_changes = generate_change_plan(
        user_story_id="US-001",
        original_user_story={
            "role": "customer",
            "action": "add items to my shopping cart",
            "benefit": "I can purchase multiple items at once"
        },
        edited_user_story={
            "role": "premium customer",
            "action": "add items to my wishlist and shopping cart",
            "benefit": "I can save items for later and purchase multiple items at once"
        },
        impacted_nodes=[
            {"id": "AGG-CART", "name": "Cart", "type": "Aggregate", "rootEntity": "Cart"},
            {"id": "CMD-ADD-TO-CART", "name": "AddToCart", "type": "Command", "actor": "customer"},
            {"id": "EVT-ITEM-ADDED", "name": "ItemAddedToCart", "type": "Event"}
        ]
    )

    SmartLogger.log(
        "INFO",
        "Generated Change Plan (test)",
        category="agent.change_planner",
        params={"changes": test_changes}
    )

