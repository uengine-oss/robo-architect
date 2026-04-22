"""Hybrid ingestion DTOs and phase enum."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class HybridPhase(str, Enum):
    UPLOAD = "hybrid.upload"
    DOCUMENT_BPM = "hybrid.document_bpm"
    CODE_RULES = "hybrid.code_rules"
    MAPPING = "hybrid.mapping"
    ONTOLOGY = "hybrid.ontology"
    EVENT_STORMING = "hybrid.event_storming"
    COMPLETE = "hybrid.complete"
    ERROR = "hybrid.error"


class BpmProcess(BaseModel):
    """Phase 1 process identity — the top-level business process a document describes.

    One uploaded document may describe multiple processes (e.g., PDFs that bundle
    several business flows); the external extractor emits one `<bpmn:process>` per
    process, and this DTO captures each one's identity for Task disambiguation
    (see docs/legacy-ingestion/개선&재구조화.md §A).
    """

    id: str                                                # proc_{sha1(pdf + session + name)[:12]}
    name: str                                              # LLM-extracted human-readable process name
    description: Optional[str] = None                      # one-line process summary (for keyword backfill + UI)
    domain_keywords: list[str] = Field(default_factory=list)  # 3~8 domain terms for Step 1 retrieval query
    source_pdf_name: Optional[str] = None
    session_id: str
    actor_ids: list[str] = Field(default_factory=list)     # actors belonging to this process
    task_ids: list[str] = Field(default_factory=list)      # tasks belonging to this process


class BpmActor(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    process_id: Optional[str] = None  # None until Process identity is assigned


class BpmTaskDTO(BaseModel):
    """A document-derived Task: one business activity, may realize multiple code rules."""

    id: str
    name: str
    description: Optional[str] = None
    sequence_index: int = 0
    actor_ids: list[str] = Field(default_factory=list)
    source_page: Optional[int] = None
    source_section: Optional[str] = None
    process_id: Optional[str] = None  # the BpmProcess this task belongs to


class BpmSequenceDTO(BaseModel):
    id: str
    name: str
    task_ids: list[str] = Field(default_factory=list)
    process_id: Optional[str] = None


class BpmSkeleton(BaseModel):
    """Phase 1 output for ONE process: Actor/Task/Sequence graph.

    Multi-process documents produce a `ProcessBundle` wrapping several BpmSkeletons,
    one per process. Single-process documents still work unchanged (bundle with one
    element).
    """

    actors: list[BpmActor] = Field(default_factory=list)
    tasks: list[BpmTaskDTO] = Field(default_factory=list)
    sequences: list[BpmSequenceDTO] = Field(default_factory=list)
    # Optional raw BPMN 2.0 XML if we emit one in Phase 1 (per-process XML)
    bpmn_xml: Optional[str] = None
    # The process this skeleton describes. Populated by the adapter/native
    # extractor. Legacy callers that don't know about processes leave it None
    # and get lazy-backfill treatment downstream.
    process: Optional[BpmProcess] = None


class ProcessBundle(BaseModel):
    """Phase 1 output wrapping N processes extracted from a single document.

    `bpmn_xml` is the combined XML across all processes (for canvas rendering
    backward-compatibility). Each inner BpmSkeleton carries its own per-process
    XML in `BpmSkeleton.bpmn_xml`.
    """

    processes: list[BpmSkeleton] = Field(default_factory=list)
    bpmn_xml: Optional[str] = None  # merged XML for the whole document

    def flatten(self) -> BpmSkeleton:
        """Collapse into a single BpmSkeleton (for legacy code paths that
        still expect one). Drops per-process boundaries — use only for
        read-only rendering, never for retrieval."""
        actors: list[BpmActor] = []
        tasks: list[BpmTaskDTO] = []
        sequences: list[BpmSequenceDTO] = []
        for s in self.processes:
            actors.extend(s.actors)
            tasks.extend(s.tasks)
            sequences.extend(s.sequences)
        return BpmSkeleton(
            actors=actors, tasks=tasks, sequences=sequences, bpmn_xml=self.bpmn_xml,
        )


class RuleDTO(BaseModel):
    """Phase 2 output: GWT business rule extracted from legacy code."""

    id: str
    given: str
    when: str
    then: str
    source_function: Optional[str] = None
    source_module: Optional[str] = None
    confidence: float = 1.0
    # BL.title — the human-readable one-line summary of this rule's business intent.
    # Preferred over given/when/then for BC classification since those fields often
    # hold concrete test-case values or side-effect details, while title is pure semantics.
    title: Optional[str] = None
    # Phase 2.5 (BC pre-tagging) — domain term labelling this rule's business context
    # e.g. "입력검증", "실시간인증", "이력관리", "오류처리". None until Phase 2.5 runs.
    context_cluster: Optional[str] = None
    # Phase 2.6 (DDD role tagging) — which Event Storming element this rule
    # should be promoted into. One of: invariant/validation/decision/policy/query/external.
    es_role: Optional[str] = None
    es_role_confidence: float = 0.0


class ActivityRuleMapping(BaseModel):
    """Phase 3 output: Task ↔ Rule link."""

    task_id: str
    rule_id: str
    score: float
    method: str = "embedding"  # "lexical" | "embedding" | "structural" | "manual" | "agentic"
    reviewed: bool = False  # false ⇒ auto-accepted; review_queue stays false until user acts
    # Agentic retrieval fields (§2.B) — populated only for method='agentic'.
    rationale: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)
    evidence_path: list[str] = Field(default_factory=list)
    agent_verdict: Optional[str] = None  # "accept" | "reject"


class GlossaryTerm(BaseModel):
    """Phase 3.0 output: one domain term with aliases (Korean) + candidate code identifiers (English)."""

    term: str                              # canonical Korean (or original) term
    aliases: list[str] = Field(default_factory=list)
    code_candidates: list[str] = Field(default_factory=list)
    source: str = "llm"                    # "llm" | "analyzer" | "manual"


class DocumentPassage(BaseModel):
    """Phase 4 artifact: a chunk of the source document attached to one or more Tasks."""

    id: str
    heading: Optional[str] = None
    text: str
    page: Optional[int] = None
    char_start: int = 0
    char_end: int = 0
    chunk_method: str = "heading"  # "heading" | "window"


class TaskPassageLink(BaseModel):
    task_id: str
    passage_id: str
    score: float
    rank: int = 0
    low_confidence: bool = False


class RuleContext(BaseModel):
    """Enriched view of a Rule for matching — joins analyzer DB fn/actor/table info.

    Not persisted directly; built on demand from RuleDTO + analyzer graph queries.
    """

    rule_id: str
    given: str
    when: str
    then: str
    source_function: Optional[str] = None
    source_module: Optional[str] = None
    function_summary: Optional[str] = None
    actors: list[str] = Field(default_factory=list)
    reads_tables: list[str] = Field(default_factory=list)
    writes_tables: list[str] = Field(default_factory=list)
    context_cluster: Optional[str] = None  # Phase 2.5 BC tag
    # Parent-node context from analyzer graph (multi-module codebases)
    callers: list[str] = Field(default_factory=list)   # direct callers of source_function
    callees: list[str] = Field(default_factory=list)   # direct callees — orchestrator detection signal
    parent_module: Optional[str] = None                 # MODULE/FILE containing source_function
    parent_package: Optional[str] = None                # PACKAGE the module belongs to


# =============================================================================
# Phase 5 — Event Storming promotion DTOs
# =============================================================================


class UserStoryDTO(BaseModel):
    """Phase 5.A output: one Story = one (Task × source_function cluster) — or 1 Story for 0-rule Tasks."""

    id: str                                    # us_<task_seq>_<fn_order>  (0-rule: us_<task_seq>_doc)
    name: str                                  # human-readable, e.g. "입력값 검증 — 입력 파라미터 유효성"
    role: str                                  # actor name
    action: str                                # imperative goal
    benefit: str = ""
    sequence: int = 0                          # timeline X-axis (task.seq * 100 + fn_order)
    task_id: str
    source_function: Optional[str] = None
    rule_ids: list[str] = Field(default_factory=list)


class EventDTO(BaseModel):
    """Phase 5.B output."""

    key: str                                   # evt_<slug>
    name: str                                  # PastParticiple, e.g. "InputValidated"
    display_name: str = ""
    description: str = ""
    sequence: int = 0
    story_id: str
    task_id: str


class BoundedContextDTO(BaseModel):
    """Phase 5.C output."""

    key: str                                   # bc_<slug>
    name: str                                  # domain term, e.g. "실시간인증"
    description: str = ""
    story_ids: list[str] = Field(default_factory=list)
    actor_names: list[str] = Field(default_factory=list)


class AggregateDTO(BaseModel):
    """Phase 5.D output."""

    key: str                                   # agg_<slug>
    name: str                                  # domain term, e.g. "AuthHistory"
    bc_key: str
    root_table: Optional[str] = None
    member_functions: list[str] = Field(default_factory=list)
    event_keys: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)


class CommandDTO(BaseModel):
    """Phase 5.E output."""

    key: str                                   # cmd_<slug>
    name: str                                  # imperative, e.g. "ValidateInput"
    display_name: str = ""
    actor: str = ""
    aggregate_key: str
    task_id: str
    emits_event_keys: list[str] = Field(default_factory=list)


class PolicyDTO(BaseModel):
    """Phase 5.G output. kind: 'per_fn' | 'cross_bc' | 'same_bc_reactive'."""

    key: str                                   # pol_<slug>
    name: str                                  # natural sentence, e.g. "OnInputValidatedRequestLedgerLookup"
    kind: str = "per_fn"
    description: str = ""
    bc_key: Optional[str] = None
    trigger_event_key: Optional[str] = None
    invoke_command_key: Optional[str] = None
    rule_ids: list[str] = Field(default_factory=list)


class ReadModelDTO(BaseModel):
    """Phase 5.F output."""

    key: str                                   # rm_<slug>
    name: str
    bc_key: str
    trigger_event_keys: list[str] = Field(default_factory=list)
    query_keys: list[str] = Field(default_factory=list)


class PromotionResult(BaseModel):
    """Phase 5.H final aggregate — what gets persisted + summarized."""

    user_stories: list[UserStoryDTO] = Field(default_factory=list)
    events: list[EventDTO] = Field(default_factory=list)
    bounded_contexts: list[BoundedContextDTO] = Field(default_factory=list)
    aggregates: list[AggregateDTO] = Field(default_factory=list)
    commands: list[CommandDTO] = Field(default_factory=list)
    readmodels: list[ReadModelDTO] = Field(default_factory=list)
    policies: list[PolicyDTO] = Field(default_factory=list)
