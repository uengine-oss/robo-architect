"""Session and Sticker models."""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class SessionPhase(str, Enum):
    """Event storming session phases."""
    ORIENTATION = "orientation"
    EVENT_ELICITATION = "event_elicitation"
    EVENT_REFINEMENT = "event_refinement"
    COMMAND_POLICY = "command_policy"
    TIMELINE_ORDERING = "timeline_ordering"
    SUMMARY = "summary"


class StickerType(str, Enum):
    """Types of stickers in event storming."""
    EVENT = "event"              # Orange - Domain Event (past tense)
    COMMAND = "command"          # Blue - Command
    POLICY = "policy"            # Purple - Policy
    READ_MODEL = "read_model"    # Green - Read Model
    EXTERNAL_SYSTEM = "external_system"  # Pink - External System
    AGGREGATE = "aggregate"      # Yellow - Aggregate (v2)
    ACTOR = "actor"              # Yellow sticky - Actor


class Position(BaseModel):
    """2D position on canvas."""
    x: float
    y: float


class StickerCreate(BaseModel):
    """Request model for creating a sticker."""
    type: StickerType
    text: str
    position: Position
    author: str


class Sticker(BaseModel):
    """Sticker entity."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: StickerType
    text: str
    position: Position
    author: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StickerUpdate(BaseModel):
    """Request model for updating a sticker."""
    text: Optional[str] = None
    position: Optional[Position] = None


class Connection(BaseModel):
    """Connection between stickers."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    target_id: str
    label: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ConnectionCreate(BaseModel):
    """Request model for creating a connection."""
    source_id: str
    target_id: str
    label: Optional[str] = None


class SessionCreate(BaseModel):
    """Request model for creating a session."""
    title: str
    description: Optional[str] = None
    duration_minutes: int = 60


class Session(BaseModel):
    """Event storming session."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: Optional[str] = None
    phase: SessionPhase = SessionPhase.ORIENTATION
    duration_minutes: int = 60
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    participants: list[str] = Field(default_factory=list)


class Participant(BaseModel):
    """Session participant."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    session_id: str
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True


