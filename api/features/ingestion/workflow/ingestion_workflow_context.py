from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import json

import re

from api.features.ingestion.ingestion_contracts import GeneratedUserStory
from api.features.ingestion.ingestion_sessions import IngestionSession
from api.platform.observability.smart_logger import SmartLogger

# Control characters that break JSON serialisation (C0 range minus \t \n \r)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


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

    def __post_init__(self) -> None:
        # Sanitize content at initialization to prevent JSON serialisation
        # errors when content is embedded in LLM prompts across all phases.
        if self.content:
            self.content = _CONTROL_CHAR_RE.sub("", self.content)
    # Display language for node/property displayName: "ko" (한글) or "en" (English)
    display_language: str = "ko"
    source_type: str = "rfp"

    user_stories: list[Any] = field(default_factory=list)
    bounded_contexts: list[Any] = field(default_factory=list)

    aggregates_by_bc: Dict[str, Any] = field(default_factory=dict)
    commands_by_agg: Dict[str, Any] = field(default_factory=dict)
    events_by_agg: Dict[str, Any] = field(default_factory=dict)
    policies: List[Any] = field(default_factory=list)

    # Event Modeling: events extracted per UserStory (before Command exists)
    events_from_us: List[Any] = field(default_factory=list)

    # Optional artifacts
    uis: List[Any] = field(default_factory=list)
    readmodels_by_bc: Dict[str, Any] = field(default_factory=dict)

    # Figma screen data: screen_name → node structure summary text (set when source_type == "figma")
    figma_screens: Dict[str, str] = field(default_factory=dict)

    # Figma API sync: preserved when source is Figma REST API (not clipboard paste)
    figma_file_key: str | None = None
    figma_node_id_map: Dict[str, str] = field(default_factory=dict)  # screen_name → figma_node_id

    # BL (BusinessLogic) cache per UserStory ID: {us_id: [{seq, title, coupled_domain, given, when, then}, ...]}
    # Populated after Phase 1 for source_type == "analyzer_graph". Empty for rfp/figma.
    bl_by_user_story: Dict[str, List[Any]] = field(default_factory=dict)

    def sync_from_neo4j(self, up_to_phase: str | None = None) -> None:
        """
        Synchronize context from Neo4j to reflect any modifications made during pause.
        
        Args:
            up_to_phase: Optional phase name to limit sync scope (e.g., 'user_stories', 'bounded_contexts')
                        If None, syncs all available data based on current context state.
        """
        try:
            SmartLogger.log(
                "INFO",
                "Syncing ingestion workflow context from Neo4j after resume",
                category="ingestion.workflow.context.sync",
                params={
                    "session_id": self.session.id,
                    "up_to_phase": up_to_phase,
                },
            )

            # Always sync user stories (base data)
            if up_to_phase is None or up_to_phase in ("user_stories", "bounded_contexts", "aggregates", "commands", "events", "readmodels", "policies"):
                user_stories_dict = self.client.get_all_user_stories()
                # Convert dict to GeneratedUserStory objects for consistency with extract_user_stories_phase
                self.user_stories = [
                    GeneratedUserStory(
                        id=us.get("id", ""),
                        role=us.get("role", ""),
                        action=us.get("action", ""),
                        benefit=us.get("benefit", ""),
                        priority=us.get("priority", "medium"),
                        ui_description=us.get("uiDescription", "") or us.get("ui_description", ""),
                        displayName=us.get("displayName"),
                        source_screen_name=us.get("sourceScreenName") or us.get("source_screen_name"),
                    )
                    for us in user_stories_dict
                    if us.get("id") and us.get("action")  # Only include valid user stories
                ]
                SmartLogger.log(
                    "INFO",
                    "Synced user stories from Neo4j",
                    category="ingestion.workflow.context.sync",
                    params={
                        "session_id": self.session.id,
                        "user_story_count": len(self.user_stories),
                    },
                )

            # Sync bounded contexts if we have user stories
            if self.user_stories and (up_to_phase is None or up_to_phase in ("bounded_contexts", "aggregates", "commands", "events", "readmodels", "policies")):
                self.bounded_contexts = self.client.get_all_bounded_contexts()
                SmartLogger.log(
                    "INFO",
                    "Synced bounded contexts from Neo4j",
                    category="ingestion.workflow.context.sync",
                    params={
                        "session_id": self.session.id,
                        "bc_count": len(self.bounded_contexts),
                    },
                )

            # Sync aggregates if we have bounded contexts
            if self.bounded_contexts and (up_to_phase is None or up_to_phase in ("aggregates", "commands", "events", "readmodels", "policies")):
                self.aggregates_by_bc = {}
                for bc in self.bounded_contexts:
                    bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
                    if bc_id:
                        aggregates = self.client.get_aggregates_by_bc(bc_id)
                        self.aggregates_by_bc[bc_id] = aggregates
                SmartLogger.log(
                    "INFO",
                    "Synced aggregates from Neo4j",
                    category="ingestion.workflow.context.sync",
                    params={
                        "session_id": self.session.id,
                        "aggregate_count": sum(len(aggs) for aggs in self.aggregates_by_bc.values()),
                    },
                )

            # Sync commands if we have aggregates
            if self.aggregates_by_bc and (up_to_phase is None or up_to_phase in ("commands", "events", "readmodels", "policies")):
                self.commands_by_agg = {}
                for bc_id, aggregates in self.aggregates_by_bc.items():
                    for agg in aggregates:
                        agg_id = agg.get("id") if isinstance(agg, dict) else getattr(agg, "id", None)
                        if agg_id:
                            commands = self.client.get_commands_by_aggregate(agg_id)
                            self.commands_by_agg[agg_id] = commands
                SmartLogger.log(
                    "INFO",
                    "Synced commands from Neo4j",
                    category="ingestion.workflow.context.sync",
                    params={
                        "session_id": self.session.id,
                        "command_count": sum(len(cmds) for cmds in self.commands_by_agg.values()),
                    },
                )

            # Sync events if we have commands
            if self.commands_by_agg and (up_to_phase is None or up_to_phase in ("events", "readmodels", "policies")):
                self.events_by_agg = {}
                # Load events by querying Neo4j for each command
                for agg_id, commands in self.commands_by_agg.items():
                    events_for_agg = []
                    for cmd in commands:
                        cmd_id = cmd.get("id") if isinstance(cmd, dict) else getattr(cmd, "id", None)
                        if cmd_id:
                            # Query events emitted by this command
                            query = """
                            MATCH (cmd:Command {id: $cmd_id})-[:EMITS]->(evt:Event)
                            RETURN evt {.id, .name, .displayName, .version, .schema, .payload} as event
                            ORDER BY evt.name
                            """
                            with self.client.session() as session:
                                result = session.run(query, cmd_id=cmd_id)
                                for record in result:
                                    evt_dict = dict(record["event"])
                                    events_for_agg.append(evt_dict)
                    if events_for_agg:
                        self.events_by_agg[agg_id] = events_for_agg
                SmartLogger.log(
                    "INFO",
                    "Synced events from Neo4j",
                    category="ingestion.workflow.context.sync",
                    params={
                        "session_id": self.session.id,
                        "event_count": sum(len(evts) for evts in self.events_by_agg.values()),
                    },
                )

            # Sync readmodels if we have bounded contexts
            if self.bounded_contexts and (up_to_phase is None or up_to_phase in ("readmodels", "policies")):
                self.readmodels_by_bc = {}
                for bc in self.bounded_contexts:
                    bc_id = bc.get("id") if isinstance(bc, dict) else getattr(bc, "id", None)
                    if bc_id:
                        # Query readmodels for this BC
                        query = """
                        MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_READMODEL]->(rm:ReadModel)
                        RETURN rm {.id, .name, .displayName, .description, .provisioningType, .actor, .isMultipleResult} as readmodel
                        ORDER BY rm.name
                        """
                        with self.client.session() as session:
                            result = session.run(query, bc_id=bc_id)
                            readmodels = [dict(record["readmodel"]) for record in result]
                            if readmodels:
                                self.readmodels_by_bc[bc_id] = readmodels
                SmartLogger.log(
                    "INFO",
                    "Synced readmodels from Neo4j",
                    category="ingestion.workflow.context.sync",
                    params={
                        "session_id": self.session.id,
                        "readmodel_count": sum(len(rms) for rms in self.readmodels_by_bc.values()),
                    },
                )

            # Sync policies if we have bounded contexts
            if self.bounded_contexts and (up_to_phase is None or up_to_phase == "policies"):
                # Query all policies with their relationships
                query = """
                MATCH (bc:BoundedContext)-[:HAS_POLICY]->(pol:Policy)
                OPTIONAL MATCH (evt:Event)-[:TRIGGERS]->(pol)
                OPTIONAL MATCH (pol)-[:INVOKES]->(cmd:Command)
                RETURN {
                    id: pol.id,
                    name: pol.name,
                    description: pol.description,
                    bcId: bc.id,
                    triggerEventId: evt.id,
                    invokeCommandId: cmd.id
                } as policy
                ORDER BY pol.name
                """
                with self.client.session() as session:
                    result = session.run(query)
                    self.policies = [dict(record["policy"]) for record in result]
                SmartLogger.log(
                    "INFO",
                    "Synced policies from Neo4j",
                    category="ingestion.workflow.context.sync",
                    params={
                        "session_id": self.session.id,
                        "policy_count": len(self.policies),
                    },
                )

            # Rebuild figma_screens map from content if source_type is figma
            if self.source_type == "figma" and self.content and not self.figma_screens:
                try:
                    from api.features.ingestion.figma_to_user_stories import (
                        _build_node_maps,
                        _describe_node,
                    )
                    nodes = json.loads(self.content)
                    children_map, top_frames = _build_node_maps(nodes)
                    for frame in top_frames:
                        screen_name = frame.get("name", "")
                        if screen_name:
                            screen_lines = _describe_node(frame, children_map, 0)
                            self.figma_screens[screen_name] = "\n".join(screen_lines)
                    SmartLogger.log(
                        "INFO",
                        f"Rebuilt figma_screens map from content: {len(self.figma_screens)} screens",
                        category="ingestion.workflow.context.sync.figma_screens",
                        params={"session_id": self.session.id, "screen_count": len(self.figma_screens)},
                    )
                except Exception as figma_err:
                    SmartLogger.log(
                        "WARN",
                        f"Failed to rebuild figma_screens map: {figma_err}",
                        category="ingestion.workflow.context.sync.figma_screens.error",
                        params={"session_id": self.session.id, "error": str(figma_err)},
                    )

            SmartLogger.log(
                "INFO",
                "Completed syncing ingestion workflow context from Neo4j",
                category="ingestion.workflow.context.sync.complete",
                params={
                    "session_id": self.session.id,
                    "user_stories": len(self.user_stories),
                    "bounded_contexts": len(self.bounded_contexts),
                    "aggregates": sum(len(aggs) for aggs in self.aggregates_by_bc.values()),
                    "commands": sum(len(cmds) for cmds in self.commands_by_agg.values()),
                    "events": sum(len(evts) for evts in self.events_by_agg.values()),
                    "readmodels": sum(len(rms) for rms in self.readmodels_by_bc.values()),
                    "policies": len(self.policies),
                    "figma_screens": len(self.figma_screens),
                },
            )

        except Exception as e:
            SmartLogger.log(
                "ERROR",
                "Failed to sync ingestion workflow context from Neo4j",
                category="ingestion.workflow.context.sync.error",
                params={
                    "session_id": self.session.id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            # Don't raise - allow workflow to continue with existing context
            # The modifications in Neo4j will still be there, just not reflected in context


