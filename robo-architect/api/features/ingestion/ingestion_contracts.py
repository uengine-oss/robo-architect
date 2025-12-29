"""
Ingestion Contracts (DTOs)

Business capability: document ingestion progress streaming and extracted artifacts.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class IngestionPhase(str, Enum):
    UPLOAD = "upload"
    PARSING = "parsing"
    EXTRACTING_USER_STORIES = "extracting_user_stories"
    IDENTIFYING_BC = "identifying_bc"
    EXTRACTING_AGGREGATES = "extracting_aggregates"
    EXTRACTING_COMMANDS = "extracting_commands"
    GENERATING_UI = "generating_ui"
    EXTRACTING_EVENTS = "extracting_events"
    IDENTIFYING_POLICIES = "identifying_policies"
    SAVING = "saving"
    PAUSED = "paused"
    COMPLETE = "complete"
    ERROR = "error"


class ProgressEvent(BaseModel):
    """Progress event sent via SSE."""

    phase: IngestionPhase
    message: str
    progress: int  # 0-100
    data: Optional[dict] = None  # Created objects / step payloads


class CreatedObject(BaseModel):
    """Information about a created DDD object."""

    id: str
    name: str
    type: str  # BoundedContext, Aggregate, Command, Event, Policy, UserStory
    parent_id: Optional[str] = None
    description: Optional[str] = None


class GeneratedUserStory(BaseModel):
    """Generated User Story from requirements."""

    id: str
    role: str
    action: str
    benefit: str
    priority: str = "medium"
    # Optional UI description extracted from requirements (used to generate UI wireframe stickers)
    ui_description: str = ""


class UserStoryList(BaseModel):
    """List of generated user stories."""

    user_stories: list[GeneratedUserStory]


