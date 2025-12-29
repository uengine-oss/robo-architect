"""
Event Storming Structured Outputs

Business capability: wrapper DTOs for LLM structured outputs used by Event Storming nodes.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .state import AggregateCandidate, BoundedContextCandidate, CommandCandidate, EventCandidate, PolicyCandidate


class BoundedContextList(BaseModel):
    """List of Bounded Context candidates."""

    bounded_contexts: List[BoundedContextCandidate] = Field(description="List of identified bounded contexts")


class AggregateList(BaseModel):
    """List of Aggregate candidates."""

    aggregates: List[AggregateCandidate] = Field(description="List of identified aggregates")


class CommandList(BaseModel):
    """List of Command candidates."""

    commands: List[CommandCandidate] = Field(description="List of identified commands")


class EventList(BaseModel):
    """List of Event candidates."""

    events: List[EventCandidate] = Field(description="List of identified events")


class PolicyList(BaseModel):
    """List of Policy candidates."""

    policies: List[PolicyCandidate] = Field(description="List of identified policies")


