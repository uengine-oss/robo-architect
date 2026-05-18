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
    GROUPING_FEATURES = "grouping_features"  # spec 026 — group user stories into Features within each BC
    EXTRACTING_AGGREGATES = "extracting_aggregates"
    EXTRACTING_COMMANDS = "extracting_commands"
    EXTRACTING_EVENTS = "extracting_events"
    EXTRACTING_READMODELS = "extracting_readmodels"
    GENERATING_PROPERTIES = "generating_properties"
    GENERATING_REFERENCES = "generating_references"
    GENERATING_UI = "generating_ui"
    GENERATING_UI_FLOW = "generating_ui_flow"  # spec 025 — UI-to-UI flow edges + Gateway derivation
    IDENTIFYING_POLICIES = "identifying_policies"
    GENERATING_GWT = "generating_gwt"
    EXTRACTING_INVARIANTS = "extracting_invariants"  # spec 027 — aggregate invariants
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
    # Spec 017 — additive, optional fields. Frontend treats absence as
    # "no update; keep showing previous value." See contracts/sse-events.md
    # for the full schema.
    tokens: Optional[dict] = None  # {total, byPhase?, approximate?, lastCallTokens?}
    suspendState: Optional[str] = None  # "running" | "suspending" | "suspended"


# spec 025 — warning codes emitted by the UI-flow phase. String constants
# (not an enum) so they survive JSON serialization to the SSE channel as-is.
UI_FLOW_WARNING_CODES: tuple[str, ...] = (
    "ui_flow_unclear",              # No detectable screen flow in the source document
    "ui_flow_unresolved_target",    # LLM referenced a screen name that doesn't bind to any UI node
    "gateway_single_branch",        # Gateway has only one outgoing NEXT_UI edge (degenerate)
    "gateway_kind_downgrade",       # LLM emitted parallel/inclusive → downgraded to exclusive (research D6)
)


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
    source_bl: list[int] = Field(default_factory=list, description="BL sequence numbers this US originated from. Only used when source_type is analyzer_graph.")
    # Acceptance criteria — field-level / data-validation / business-rule details
    # that belong to *this* user story but should not be promoted to a separate
    # user story. Example: for "회원이 회원가입을 한다", the acceptance criteria
    # might list ["이름·휴대폰번호·이메일·생년월일·성별이 저장된다", "약관 동의 결과가
    # 함께 저장된다", ...]. Cross-chunk consolidation populates this from
    # rule-fragments that the chunk-level extraction created as separate stories.
    acceptance_criteria: list[str] = Field(default_factory=list, description="Field-level / business-rule details for this user story. Not separate stories.")


class UserStoryList(BaseModel):
    """List of generated user stories."""

    user_stories: list[GeneratedUserStory]


