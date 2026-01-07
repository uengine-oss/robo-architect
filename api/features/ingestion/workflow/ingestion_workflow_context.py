from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from api.features.ingestion.ingestion_sessions import IngestionSession


@dataclass
class IngestionWorkflowContext:
    """
    Shared state for a single ingestion run.

    Kept feature-local and organized around the ingestion business process.
    """

    session: IngestionSession
    content: str
    client: Any
    llm: Any

    user_stories: list[Any] = field(default_factory=list)
    bounded_contexts: list[Any] = field(default_factory=list)

    aggregates_by_bc: Dict[str, Any] = field(default_factory=dict)
    commands_by_agg: Dict[str, Any] = field(default_factory=dict)
    events_by_agg: Dict[str, Any] = field(default_factory=dict)
    policies: List[Any] = field(default_factory=list)

    # Optional artifacts
    uis: List[Any] = field(default_factory=list)
    readmodels_by_bc: Dict[str, Any] = field(default_factory=dict)


