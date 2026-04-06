"""
Ingestion Contracts (DTOs)

Business capability: document ingestion progress streaming and extracted artifacts.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class IngestionPhase(str, Enum):
    UPLOAD = "upload"
    PARSING = "parsing"
    EXTRACTING_USER_STORIES = "extracting_user_stories"
    IDENTIFYING_BC = "identifying_bc"
    EXTRACTING_AGGREGATES = "extracting_aggregates"
    EXTRACTING_COMMANDS = "extracting_commands"
    EXTRACTING_EVENTS = "extracting_events"
    EXTRACTING_READMODELS = "extracting_readmodels"
    GENERATING_PROPERTIES = "generating_properties"
    GENERATING_REFERENCES = "generating_references"
    GENERATING_UI = "generating_ui"
    IDENTIFYING_POLICIES = "identifying_policies"
    GENERATING_GWT = "generating_gwt"
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
    # Business flow sequence (1-based, assigned after extraction)
    sequence: Optional[int] = None
    # Optional UI description extracted from requirements (used to generate UI wireframe stickers)
    ui_description: str = ""
    # Optional display label in chosen language for UI (e.g. '주문 생성' or 'Create Order')
    displayName: Optional[str] = None
    # Figma source screen name (set when source_type == "figma")
    source_screen_name: Optional[str] = None
    # Analyzer source unit ID (procedure fqn, class fqn 등 — 역추적용)
    source_unit_id: Optional[str] = None
    # BL sequence 번호 리스트 — 이 US가 어떤 BL에서 유래했는지 (필수: 입력의 BL[N] 번호)
    source_bl: list[int] = Field(default_factory=list, description="List of BL sequence numbers this User Story originated from. MUST be filled with BL[N] numbers from the input.")


class UserStoryList(BaseModel):
    """List of generated user stories."""

    user_stories: list[GeneratedUserStory]


