"""Phase 5 §4 — Task → Event Storming decomposition (deterministic layer).

Two entry points:

  - `decompose_task(...)` runs §4.1 on a single Task: takes the BpmTask metadata
    + its mapped ClassifiedRules + its document passages, returns a
    `TaskDecomposition` carrying *candidate* DTOs (no LLM-supplied names yet).

  - `merge_session_decompositions(...)` runs §4.2 across all Tasks in a
    session: groups Aggregate candidates by `root_table`, aligns Commands /
    Events / Policies / ReadModels onto the merged Aggregates, and returns a
    `SessionDecomposition` that downstream LLM-naming + persistence consumes.

Everything here is pure: no Neo4j writes, no LLM. The candidate DTOs carry the
exact `rule_ids` / `user_story_id` / `derived_from_*` metadata needed by §5
traceability edges. LLM-naming (Aggregate name, Command displayName, Event
PastParticiple, BC grouping, Policy name, ReadModel name) happens in a later
orchestration pass on top of these candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from api.features.ingestion.hybrid.contracts import (
    BpmProcess,
    BpmTaskDTO,
    DocumentPassage,
    ExampleDTO,
    RuleDTO,
)
from api.features.ingestion.hybrid.event_storming_bridge.rule_classifier import (
    ClassifiedRule,
    RuleCategory,
    classify_rules,
    index_by_function_local_id,
)


# =============================================================================
# Candidate DTOs — pre-LLM intermediate shapes
# =============================================================================


UserStorySource = str  # "mapped" | "document_only"


@dataclass
class UserStoryCandidate:
    """Pre-LLM UserStory: structure + rule provenance, names placeholder.

    `name`/`action`/`benefit` get filled by an LLM step that consumes
    `rule_statements` + `passage_excerpts`. Until then they hold the source
    seed strings so the candidate is inspectable.
    """

    id: str                            # `us_<task_id>` — stable, idempotent
    task_id: str
    role: str                          # actor name resolved up the chain, or "system"
    sequence: int                      # display order on Event Storming canvas
    source: UserStorySource            # "mapped" | "document_only"
    rule_ids: list[str] = field(default_factory=list)
    rule_statements: list[str] = field(default_factory=list)   # LLM input
    passage_excerpts: list[str] = field(default_factory=list)  # LLM input (first ~3)
    task_name: str = ""                                         # LLM input fallback
    task_description: str = ""                                  # LLM input fallback
    name_seed: str = ""                                         # quick deterministic placeholder name
    source_functions: list[str] = field(default_factory=list)


@dataclass
class AggregateCandidate:
    """Pre-LLM Aggregate: a root_table + member rules + lifecycle event seeds.

    Multiple tasks can produce candidates pointing at the same root_table; §4.2
    merges them by `root_table` into a single SessionAggregate.
    """

    root_table: str
    member_rule_ids: list[str] = field(default_factory=list)
    invariant_rule_ids: list[str] = field(default_factory=list)   # UPDATE writes
    creation_rule_ids: list[str] = field(default_factory=list)    # INSERT writes
    removal_rule_ids: list[str] = field(default_factory=list)     # DELETE writes
    user_story_ids: list[str] = field(default_factory=list)       # IMPLEMENTS edges
    member_functions: list[str] = field(default_factory=list)     # for LLM aggregate naming


@dataclass
class CommandCandidate:
    """Pre-LLM Command: 1 per Task by default, additional ones for branch splits.

    - `precondition_rule_ids` = guard chain (statement-verb rules + guard targets
       that survived infra filter)
    - `emit_rule_ids` = rules whose writes drive an Event
    - `branch_local_id` non-None marks a branch-derived Command (split off a
       parent Task command)
    """

    id: str
    task_id: str
    user_story_id: str
    aggregate_root_table: Optional[str] = None
    actor: str = ""
    precondition_rule_ids: list[str] = field(default_factory=list)
    emit_rule_ids: list[str] = field(default_factory=list)
    branch_local_id: Optional[str] = None
    seed_label: str = ""               # task.name; LLM rewrites


@dataclass
class EventCandidate:
    """Pre-LLM Event: 1 per write-bearing rule.

    `op` ∈ {"INSERT","UPDATE","DELETE"} drives the Event flavor (created /
    state-mutated / removed). `derived_from_example_id` points at the canonical
    Example carrying the GWT for acceptance tests.
    """

    id: str
    task_id: str
    user_story_id: str
    rule_id: str                       # source rule
    op: str
    target_table: str
    aggregate_root_table: str
    derived_from_example_id: Optional[str] = None
    sequence_within_command: Optional[str] = None  # rule.local_id


@dataclass
class PolicyCandidate:
    """Pre-LLM Policy: a cross-BC coupling source.

    `coupled_domains` lists the foreign domains this rule touches. The actual
    target Command (in another BC) is resolved later in §4.2 once BC grouping
    is decided.
    """

    id: str
    task_id: str
    user_story_id: str
    source_rule_id: str
    coupled_domains: list[str] = field(default_factory=list)
    branch_kind: str = "per_fn"        # "per_fn" | "branch_split"


@dataclass
class ReadModelCandidate:
    """Pre-LLM ReadModel: read-only rules whose function pulls data."""

    id: str
    task_id: str
    user_story_id: str
    rule_ids: list[str] = field(default_factory=list)
    source_functions: list[str] = field(default_factory=list)


@dataclass
class QuestionRef:
    """Pass-through Question reference — attaches to a BC after grouping."""

    question_id: str
    text: str
    reason: str
    host_function: str


@dataclass
class TaskDecomposition:
    """Output of §4.1 for a single BpmTask."""

    task_id: str
    user_stories: list[UserStoryCandidate] = field(default_factory=list)
    aggregate_contributions: list[AggregateCandidate] = field(default_factory=list)
    commands: list[CommandCandidate] = field(default_factory=list)
    events: list[EventCandidate] = field(default_factory=list)
    policies: list[PolicyCandidate] = field(default_factory=list)
    read_models: list[ReadModelCandidate] = field(default_factory=list)
    questions: list[QuestionRef] = field(default_factory=list)


@dataclass
class SessionAggregate:
    """Output of §4.2: an Aggregate after merging contributions across tasks."""

    root_table: str
    member_rule_ids: list[str] = field(default_factory=list)
    invariant_rule_ids: list[str] = field(default_factory=list)
    creation_rule_ids: list[str] = field(default_factory=list)
    removal_rule_ids: list[str] = field(default_factory=list)
    user_story_ids: list[str] = field(default_factory=list)
    member_functions: list[str] = field(default_factory=list)
    contributing_task_ids: list[str] = field(default_factory=list)


@dataclass
class SessionDecomposition:
    """Output of §4.2 for a whole session."""

    session_id: str
    user_stories: list[UserStoryCandidate] = field(default_factory=list)
    aggregates: list[SessionAggregate] = field(default_factory=list)
    commands: list[CommandCandidate] = field(default_factory=list)
    events: list[EventCandidate] = field(default_factory=list)
    policies: list[PolicyCandidate] = field(default_factory=list)
    read_models: list[ReadModelCandidate] = field(default_factory=list)
    questions: list[QuestionRef] = field(default_factory=list)


# =============================================================================
# §4.1 — Single-Task decomposition
# =============================================================================


def _pick_canonical_example(rule: RuleDTO) -> Optional[ExampleDTO]:
    """Non-boundary first; stable by example_id."""
    if not rule.examples:
        return None
    sorted_ex = sorted(
        rule.examples,
        key=lambda e: (bool(e.is_boundary), e.example_id or ""),
    )
    return sorted_ex[0]


def _name_seed_from_rules(statements: list[str], task_name: str) -> str:
    """Best-effort placeholder UserStory label without LLM."""
    if statements:
        first = statements[0].strip()
        if first:
            return first[:50] + ("…" if len(first) > 50 else "")
    return task_name or "(unnamed task)"


def decompose_task(
    *,
    task: BpmTaskDTO,
    task_rules: list[ClassifiedRule],
    task_passages: list[DocumentPassage] | None = None,
    task_actor_name: Optional[str] = None,
    process: Optional[BpmProcess] = None,
) -> TaskDecomposition:
    """Run §4.1 on one BpmTask. No LLM, no Neo4j write."""
    task_passages = task_passages or []
    task_seq = task.sequence_index or 0
    process_offset = 0
    if process is not None:
        # Stable, deterministic process offset: hash of process id mod 1000 so
        # different processes get distinct sequence bands without needing the
        # process to carry its own sequence_index field. § 4.2 may override.
        process_offset = (sum(ord(c) for c in (process.id or "")) % 100) * 1000

    role = (task_actor_name or "system").strip() or "system"
    rule_idx = index_by_function_local_id(task_rules)
    rule_id_set = {c.rule.id for c in task_rules}

    # --- 1. UserStory ---------------------------------------------------------
    rule_statements = [
        (c.rule.title or c.rule.when or "").strip()
        for c in task_rules
        if (c.rule.title or c.rule.when)
    ]
    rule_statements = [s for s in rule_statements if s]
    passage_excerpts = [
        (p.heading or "")[:80] + " — " + (p.text or "").replace("\n", " ")[:160]
        for p in task_passages[:3]
    ]
    source: UserStorySource = "mapped" if task_rules else "document_only"
    us = UserStoryCandidate(
        id=f"us_{task.id}",
        task_id=task.id,
        role=role,
        sequence=process_offset + task_seq,
        source=source,
        rule_ids=[c.rule.id for c in task_rules],
        rule_statements=rule_statements,
        passage_excerpts=passage_excerpts,
        task_name=task.name or "",
        task_description=task.description or "",
        name_seed=_name_seed_from_rules(rule_statements, task.name or ""),
        source_functions=sorted({
            c.rule.source_function for c in task_rules if c.rule.source_function
        }),
    )

    decomp = TaskDecomposition(task_id=task.id, user_stories=[us])

    # No code mapping → only the document-only US, nothing else.
    if not task_rules:
        return decomp

    # --- 2. Bucket rules by category ----------------------------------------
    bucket_creation: list[ClassifiedRule] = []
    bucket_mutation: list[ClassifiedRule] = []
    bucket_removal: list[ClassifiedRule] = []
    bucket_read: list[ClassifiedRule] = []
    bucket_guard: list[ClassifiedRule] = []
    bucket_cross_bc: list[ClassifiedRule] = []
    for c in task_rules:
        cats = c.categories
        if RuleCategory.AGGREGATE_CREATION in cats:
            bucket_creation.append(c)
        if RuleCategory.AGGREGATE_MUTATION in cats:
            bucket_mutation.append(c)
        if RuleCategory.AGGREGATE_REMOVAL in cats:
            bucket_removal.append(c)
        if RuleCategory.READ_CANDIDATE in cats:
            bucket_read.append(c)
        if RuleCategory.COMMAND_GUARD in cats:
            bucket_guard.append(c)
        if c.has_cross_bc_coupling:
            bucket_cross_bc.append(c)

    # --- 3. Aggregate candidates --------------------------------------------
    # Group write-bearing rules by root_table; each group → 1 candidate.
    write_bearing = bucket_creation + bucket_mutation + bucket_removal
    by_root: dict[str, list[ClassifiedRule]] = {}
    for c in write_bearing:
        root = c.root_table
        if root is None:
            continue
        by_root.setdefault(root, []).append(c)
    for root, members in by_root.items():
        creation_ids = [c.rule.id for c in members if RuleCategory.AGGREGATE_CREATION in c.categories]
        mutation_ids = [c.rule.id for c in members if RuleCategory.AGGREGATE_MUTATION in c.categories]
        removal_ids = [c.rule.id for c in members if RuleCategory.AGGREGATE_REMOVAL in c.categories]
        member_fns = sorted({c.rule.source_function for c in members if c.rule.source_function})
        decomp.aggregate_contributions.append(AggregateCandidate(
            root_table=root,
            member_rule_ids=[c.rule.id for c in members],
            invariant_rule_ids=mutation_ids,
            creation_rule_ids=creation_ids,
            removal_rule_ids=removal_ids,
            user_story_ids=[us.id],
            member_functions=member_fns,
        ))

    # --- 4. Command candidates ----------------------------------------------
    # Resolve guard chains; orphan guard pointers (target dropped by infra
    # filter) gracefully degrade per PRD §4.1 fallback note.
    main_precond_ids: list[str] = []
    seen_precond: set[str] = set()
    for c in bucket_guard:
        if c.rule.id in seen_precond:
            continue
        main_precond_ids.append(c.rule.id)
        seen_precond.add(c.rule.id)
        if c.is_guarded:
            target = rule_idx.get((c.rule.source_function, c.rule.guard_rule_id or ""))
            if target and target.rule.id not in seen_precond:
                main_precond_ids.append(target.rule.id)
                seen_precond.add(target.rule.id)

    main_emit_ids = [c.rule.id for c in write_bearing]

    # If a task has no write-bearing rules and no guard rules, there is no
    # meaningful main Command — the task is purely a ReadModel projection or
    # a document-only US. Skip Command emission to avoid orphan nodes that
    # would fail to land on any Aggregate during persistence.
    has_main_command = bool(write_bearing or main_precond_ids)

    # Branch_from-driven secondary commands: rules whose `branch_from` points
    # at another in-task rule become a separate Command (the else-leg).
    branch_split_ids: dict[str, list[ClassifiedRule]] = {}
    for c in task_rules:
        if not c.is_branched:
            continue
        target = rule_idx.get((c.rule.source_function, c.rule.branch_from or ""))
        if target is None:
            continue  # orphan branch_from — fold into main command
        branch_split_ids.setdefault(c.rule.branch_from or "", []).append(c)

    # Subtract branch-split rules from main command's emit list — they become
    # the split commands' emits.
    split_emit_set: set[str] = {c.rule.id for grp in branch_split_ids.values() for c in grp}
    main_emit_ids = [rid for rid in main_emit_ids if rid not in split_emit_set]

    if has_main_command:
        decomp.commands.append(CommandCandidate(
            id=f"cmd_{task.id}_main",
            task_id=task.id,
            user_story_id=us.id,
            aggregate_root_table=_pick_main_root(decomp.aggregate_contributions, main_emit_ids, task_rules),
            actor=role,
            precondition_rule_ids=main_precond_ids,
            emit_rule_ids=main_emit_ids,
            seed_label=task.name or "",
        ))

    for parent_lid, branch_rules in branch_split_ids.items():
        emits = [c.rule.id for c in branch_rules]
        agg_root = _root_of_first_emit(branch_rules)
        decomp.commands.append(CommandCandidate(
            id=f"cmd_{task.id}_branch_{parent_lid}",
            task_id=task.id,
            user_story_id=us.id,
            aggregate_root_table=agg_root,
            actor=role,
            precondition_rule_ids=[],   # branch leg precondition is the parent rule itself
            emit_rule_ids=emits,
            branch_local_id=parent_lid,
            seed_label=f"{task.name or ''} — branch {parent_lid}",
        ))

    # --- 5. Event candidates ------------------------------------------------
    # 1 Event per (rule × op × table) write target.
    for c in write_bearing:
        canon = _pick_canonical_example(c.rule)
        for op, tables in c.write_tables_by_op.items():
            for tbl in sorted(tables):
                ev_id = f"evt_{c.rule.id}_{op}_{tbl}"
                decomp.events.append(EventCandidate(
                    id=ev_id,
                    task_id=task.id,
                    user_story_id=us.id,
                    rule_id=c.rule.id,
                    op=op,
                    target_table=tbl,
                    aggregate_root_table=c.root_table or tbl,
                    derived_from_example_id=canon.example_id if canon else None,
                    sequence_within_command=c.rule.local_id,
                ))

    # --- 6. Policy candidates -----------------------------------------------
    for c in bucket_cross_bc:
        decomp.policies.append(PolicyCandidate(
            id=f"pol_{c.rule.id}",
            task_id=task.id,
            user_story_id=us.id,
            source_rule_id=c.rule.id,
            coupled_domains=list(c.rule.coupled_domains),
            branch_kind="branch_split" if c.is_branched else "per_fn",
        ))

    # --- 7. ReadModel candidates --------------------------------------------
    if bucket_read:
        # 1 ReadModel per task collecting all read-only rules — refinement
        # (per source-table) happens in §4.2 once Aggregates are merged.
        decomp.read_models.append(ReadModelCandidate(
            id=f"rm_{task.id}",
            task_id=task.id,
            user_story_id=us.id,
            rule_ids=[c.rule.id for c in bucket_read],
            source_functions=sorted({c.rule.source_function for c in bucket_read if c.rule.source_function}),
        ))

    # --- 8. Question — populated by caller (analyzer DB query) --------------
    # decompose_task only consumes ClassifiedRule; Question fetch is a separate
    # cross-cut. SessionDecomposition merges them onto the right BC after
    # grouping (§4.2 step 8).
    _ = rule_id_set  # currently unused; reserved for future cross-task dedup
    return decomp


def _pick_main_root(
    aggregates: list[AggregateCandidate],
    emit_rule_ids: list[str],
    classified: list[ClassifiedRule],
) -> Optional[str]:
    """Find the Aggregate root_table that the main Command's emits land on."""
    emit_set = set(emit_rule_ids)
    if not emit_set:
        return None
    for agg in aggregates:
        if any(rid in emit_set for rid in agg.member_rule_ids):
            return agg.root_table
    # Fallback: first emit rule's root_table directly
    for c in classified:
        if c.rule.id in emit_set and c.root_table:
            return c.root_table
    return None


def _root_of_first_emit(rules: list[ClassifiedRule]) -> Optional[str]:
    for c in rules:
        if c.root_table:
            return c.root_table
    return None


# =============================================================================
# §4.2 — Session-wide merge
# =============================================================================


def merge_session_decompositions(
    session_id: str,
    decompositions: list[TaskDecomposition],
    *,
    questions: list[QuestionRef] | None = None,
) -> SessionDecomposition:
    """Merge per-Task TaskDecomposition into a SessionDecomposition.

    Aggregate merging by `root_table`; Commands / Events / Policies / ReadModels
    pass through (they're already task-scoped). BC grouping + LLM-naming happen
    downstream in the orchestration layer.
    """
    out = SessionDecomposition(session_id=session_id)

    by_root: dict[str, SessionAggregate] = {}
    for d in decompositions:
        out.user_stories.extend(d.user_stories)
        out.commands.extend(d.commands)
        out.events.extend(d.events)
        out.policies.extend(d.policies)
        out.read_models.extend(d.read_models)
        for agg in d.aggregate_contributions:
            target = by_root.setdefault(agg.root_table, SessionAggregate(root_table=agg.root_table))
            _merge_into(target, agg, contributing_task_id=d.task_id)

    out.aggregates = list(by_root.values())
    out.questions = list(questions or [])
    return out


def _merge_into(target: SessionAggregate, src: AggregateCandidate, contributing_task_id: str) -> None:
    """Union-merge an AggregateCandidate into the SessionAggregate, dedup-stable."""
    target.member_rule_ids = _dedup_extend(target.member_rule_ids, src.member_rule_ids)
    target.invariant_rule_ids = _dedup_extend(target.invariant_rule_ids, src.invariant_rule_ids)
    target.creation_rule_ids = _dedup_extend(target.creation_rule_ids, src.creation_rule_ids)
    target.removal_rule_ids = _dedup_extend(target.removal_rule_ids, src.removal_rule_ids)
    target.user_story_ids = _dedup_extend(target.user_story_ids, src.user_story_ids)
    target.member_functions = _dedup_extend(target.member_functions, src.member_functions)
    if contributing_task_id and contributing_task_id not in target.contributing_task_ids:
        target.contributing_task_ids.append(contributing_task_id)


def _dedup_extend(base: list[str], more: list[str]) -> list[str]:
    """Append items from `more` to `base`, preserving order and dropping dups."""
    seen = set(base)
    for x in more:
        if x in seen or not x:
            continue
        seen.add(x)
        base.append(x)
    return base
