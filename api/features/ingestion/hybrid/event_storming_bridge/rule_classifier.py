"""Phase 5 §3.1 — deterministic Rule classification.

Maps each RuleDTO onto Event Storming categories without any LLM call. The
categorization is the leaf of the Phase 5 decomposition pipeline; downstream
modules (decompose_task, merge_session_decompositions) consume `ClassifiedRule`
to assemble Aggregates / Commands / Events / Policies / ReadModels.

Signals consumed (set on RuleDTO/ExampleDTO by §2.1 input boost):
  - ExampleDTO.writes[].op  → INSERT / UPDATE / DELETE → creation / mutation / removal
  - empty writes            → ReadModel candidate (refined later with RuleContext.reads_tables)
  - RuleDTO.title           → statement verb match → Command guard
  - RuleDTO.guard_rule_id   → this rule has a precondition (R2.guard=R1)
  - RuleDTO.branch_from     → this rule is the else-leg of an if/else
  - RuleDTO.coupled_domains → cross-BC Policy candidate
  - RuleDTO.next_rule_local_ids / branch_rule_local_ids → flow shape

A single rule can land in multiple categories (e.g., a rule that does both
INSERT and UPDATE writes belongs to creation AND mutation). Categories are
non-exclusive on purpose — Aggregate root resolution and Event naming consume
each independently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from api.features.ingestion.hybrid.contracts import RuleDTO


class RuleCategory(str, Enum):
    """Mutually-non-exclusive Event Storming role tags for a single Rule."""

    AGGREGATE_CREATION = "aggregate_creation"   # writes contains op=INSERT
    AGGREGATE_MUTATION = "aggregate_mutation"   # writes contains op=UPDATE
    AGGREGATE_REMOVAL = "aggregate_removal"     # writes contains op=DELETE
    READ_CANDIDATE = "read_candidate"           # writes empty (raw signal — refine with RuleContext)
    COMMAND_GUARD = "command_guard"             # statement starts with a validation verb


# §3.1: statement signals that mark a Command precondition / validation rule.
# PRD originally specified `^(검증|거부|판정|확인|체크)` but zapamcom10060 statements
# are natural-language predicates, not imperatives — typical shapes:
#   "청구번호가 0이면 오류로 종료한다"      ← precondition: error termination
#   "납부방법 5는 고객번호가 필수다"        ← precondition: required field
#   "유효성 검증을 수행한다"                ← classic verb start
# We match either an early validation verb anywhere in the first ~15 chars OR
# any of the natural-language termination cues.
_GUARD_HEAD_PATTERN = re.compile(r"^.{0,15}?(검증|거부|판정|확인|체크|검사)")
_GUARD_TAIL_PATTERN = re.compile(r"(필수(?:다|이다)|오류(?:로 종료한다|이다|다)|예외(?:이다|다))\s*$")


def _matches_guard_pattern(statement: str) -> bool:
    s = (statement or "").strip()
    if not s:
        return False
    return bool(_GUARD_HEAD_PATTERN.search(s) or _GUARD_TAIL_PATTERN.search(s))


@dataclass
class ClassifiedRule:
    """A RuleDTO annotated with its §3.1 deterministic classification."""

    rule: RuleDTO
    categories: set[RuleCategory] = field(default_factory=set)
    # Per-op write footprint: {"INSERT": {"tbl_a", "tbl_b"}, "UPDATE": {"tbl_c"}, ...}
    write_tables_by_op: dict[str, set[str]] = field(default_factory=dict)
    # Convenience flags lifted from RuleDTO so callers don't re-test the source.
    is_branched: bool = False              # branch_from non-null → else-leg of an if/else
    is_guarded: bool = False                # guard_rule_id non-null → has a precondition rule
    has_cross_bc_coupling: bool = False    # coupled_domains non-empty → Policy candidate
    has_next_chain: bool = False           # outgoing NEXT to same-fn rule(s)
    has_branch_chain: bool = False         # outgoing BRANCH to same-fn rule(s)

    @property
    def all_write_tables(self) -> set[str]:
        out: set[str] = set()
        for tables in self.write_tables_by_op.values():
            out.update(tables)
        return out

    @property
    def root_table(self) -> str | None:
        """Pick the most-frequent (op, table) target as the Aggregate root candidate.

        §4.2 merges Aggregates by shared root_table; ties broken alphabetically
        for determinism. None when the rule has no writes (READ_CANDIDATE).
        """
        counts: dict[str, int] = {}
        for tables in self.write_tables_by_op.values():
            for t in tables:
                counts[t] = counts.get(t, 0) + 1
        if not counts:
            return None
        return max(counts.items(), key=lambda kv: (kv[1], -ord(kv[0][0]) if kv[0] else 0))[0]


def classify_rule(rule: RuleDTO) -> ClassifiedRule:
    """Apply §3.1 deterministic matrix to a single RuleDTO."""
    cls = ClassifiedRule(rule=rule)

    by_op: dict[str, set[str]] = {}
    for ex in rule.examples:
        for w in ex.writes or []:
            op = (w.get("op") or "").upper()
            tbl = w.get("table")
            if not op or not tbl:
                continue
            by_op.setdefault(op, set()).add(tbl)
    cls.write_tables_by_op = by_op

    if "INSERT" in by_op:
        cls.categories.add(RuleCategory.AGGREGATE_CREATION)
    if "UPDATE" in by_op:
        cls.categories.add(RuleCategory.AGGREGATE_MUTATION)
    if "DELETE" in by_op:
        cls.categories.add(RuleCategory.AGGREGATE_REMOVAL)
    if not by_op:
        cls.categories.add(RuleCategory.READ_CANDIDATE)

    if _matches_guard_pattern(rule.title or ""):
        cls.categories.add(RuleCategory.COMMAND_GUARD)

    cls.is_branched = bool(rule.branch_from)
    cls.is_guarded = bool(rule.guard_rule_id)
    cls.has_cross_bc_coupling = bool(rule.coupled_domains)
    cls.has_next_chain = bool(rule.next_rule_local_ids)
    cls.has_branch_chain = bool(rule.branch_rule_local_ids)
    return cls


def classify_rules(rules: list[RuleDTO]) -> list[ClassifiedRule]:
    """Classify each rule, then propagate COMMAND_GUARD across guard chains.

    PRD §4.1 bucket["command_guard"] = "statement-verb rules + guard_rule_id chain".
    A rule R2 that declares `guard_rule_id = R1` makes R1 a precondition rule —
    so even if R1's statement doesn't pattern-match a validation verb, it earns
    COMMAND_GUARD by virtue of being someone's guard. Same for the guarded rule
    itself: being downstream of a guard is a Command-precondition shape.
    """
    classified = [classify_rule(r) for r in rules]
    idx = index_by_function_local_id(classified)

    for c in classified:
        if not c.is_guarded:
            continue
        # The rule itself sits in a guard chain → mark as guard-related.
        c.categories.add(RuleCategory.COMMAND_GUARD)
        # The guard target (if it survived the infra/meaningful filter) inherits
        # the same category — being someone's guard is precondition-like.
        target = idx.get((c.rule.source_function, c.rule.guard_rule_id))
        if target is not None:
            target.categories.add(RuleCategory.COMMAND_GUARD)

    return classified


def group_by_root_table(
    classified: list[ClassifiedRule],
) -> dict[str, list[ClassifiedRule]]:
    """§4.2 Aggregate seed: group write-bearing rules by their root_table.

    Read-only rules (no writes) are excluded — they become ReadModel candidates
    after RuleContext join, not Aggregate members.
    """
    groups: dict[str, list[ClassifiedRule]] = {}
    for c in classified:
        root = c.root_table
        if root is None:
            continue
        groups.setdefault(root, []).append(c)
    return groups


def index_by_function_local_id(
    classified: list[ClassifiedRule],
) -> dict[tuple[str, str], ClassifiedRule]:
    """Build (source_function, local_id) → ClassifiedRule index for guard / NEXT / BRANCH lookup.

    NEXT/BRANCH and guard_rule_id reference a rule by its function-scoped local_id;
    this index lets §4.1 resolve "what statement is R2's guard pointing at"
    without an O(N²) scan.
    """
    out: dict[tuple[str, str], ClassifiedRule] = {}
    for c in classified:
        fn = c.rule.source_function
        lid = c.rule.local_id
        if fn and lid:
            out[(fn, lid)] = c
    return out
