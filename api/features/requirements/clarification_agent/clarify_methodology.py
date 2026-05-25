"""SpecKit `clarify` methodology — deep-agent instructions + taxonomy (030).

The ambiguity-scan portion of `.claude/skills/speckit-clarify/SKILL.md`
encoded as constants + a deep-agent system prompt. The interactive Q&A
loop from SKILL.md is NOT in scope here — that part runs in the REST
layer (research R3); the deep agent only produces the prioritized
question queue, then exits via `submit_clarification_questions`.
"""

from __future__ import annotations

from api.features.requirements.clarification_contracts import AmbiguityCategory

# ── 8-category taxonomy (data-model §2.1, research R2) ───────────────────

CATEGORY_DEFINITIONS: dict[AmbiguityCategory, str] = {
    AmbiguityCategory.functional_scope: (
        "Functional Scope & Behavior — what user actions are in/out of scope, "
        "what business rules apply, what outputs the system produces. Flag "
        "vague verbs ('manage', 'handle'), missing actor, undefined success."
    ),
    AmbiguityCategory.domain_data_model: (
        "Domain & Data Model — entities involved, field names/types, "
        "identifiers, relationships, persistence rules. Flag undefined "
        "entities, missing fields, ambiguous identity."
    ),
    AmbiguityCategory.interaction_flow: (
        "Interaction & UX Flow — sequence of user steps, navigation, input "
        "validation timing, confirmation/cancel paths. Flag missing 'what "
        "happens next' or unclear entry/exit."
    ),
    AmbiguityCategory.non_functional: (
        "Non-Functional Quality — performance targets, latency budgets, "
        "concurrency, availability, security, accessibility. Flag "
        "measurable-but-unspecified targets ('fast', 'secure')."
    ),
    AmbiguityCategory.integration_dependencies: (
        "Integration & External Dependencies — external services consumed, "
        "events emitted/consumed, sync vs async, retry/timeout semantics. "
        "Flag undefined integration partner or contract."
    ),
    AmbiguityCategory.edge_cases: (
        "Edge Cases & Failure Handling — empty inputs, partial failures, "
        "concurrent access, error messaging, recovery. Flag 'happy path "
        "only' descriptions with no failure mode."
    ),
    AmbiguityCategory.terminology: (
        "Terminology Consistency — same concept named differently across "
        "requirements, or different concepts named the same. Flag synonyms, "
        "undefined jargon, inconsistent labels."
    ),
    AmbiguityCategory.completion_signals: (
        "Completion / Acceptance Criteria — how the user/system knows the "
        "story is done, what the testable outcome is. Flag missing or "
        "non-testable acceptance criteria."
    ),
}

# ── Caps + scan rubric (research R2) ─────────────────────────────────────

MAX_QUESTIONS_PER_SESSION: int = 5
MAX_OPTIONS_PER_CLOSED_QUESTION: int = 5
MIN_OPTIONS_PER_CLOSED_QUESTION: int = 2

SCAN_STATUSES: tuple[str, ...] = ("Clear", "Partial", "Missing")

PRIORITIZATION_RUBRIC: str = (
    "Score each candidate question by Impact × Uncertainty:\n"
    " - Impact (1-5): how badly the gap would distort planning or implementation "
    "if left unanswered.\n"
    " - Uncertainty (1-5): how vague the current text is — a fully missing "
    "rule scores higher than a partially specified one.\n"
    "Keep only the top "
    f"{MAX_QUESTIONS_PER_SESSION} questions across all categories. If more "
    "candidate questions exist, set `deferredNote` to a one-line summary of "
    "the categories that were left unaddressed (FR-004)."
)

# ── Deep-agent system instructions ───────────────────────────────────────

_CATEGORY_LINES = "\n".join(
    f"  - {cat.value}: {desc}" for cat, desc in CATEGORY_DEFINITIONS.items()
)

DEEP_AGENT_INSTRUCTIONS: str = f"""You are the Requirements Clarification Agent.

Your job is to scan a set of extracted requirements (user stories) for
ambiguity and underspecification, then produce a small, prioritized queue
of clarification questions that a human architect will answer one at a
time.

# Method

For each requirement in scope, label every taxonomy category below as one
of: {", ".join(SCAN_STATUSES)}.

Taxonomy:
{_CATEGORY_LINES}

# Question generation

For each Partial/Missing finding, draft a candidate question that:
 - References the specific requirement id(s) it addresses
 - States which category it resolves
 - Carries a recommended answer that, if accepted, makes the requirement
   clear without invalidating its intent
 - When the answer is one of a small set of mutually exclusive choices,
   provides between {MIN_OPTIONS_PER_CLOSED_QUESTION} and
   {MAX_OPTIONS_PER_CLOSED_QUESTION} closed options; otherwise marks the
   question as a short-answer (≤5 word) free-form question.

# Prioritization & cap

{PRIORITIZATION_RUBRIC}

# Termination

After you have your final ranked queue, call the tool
`submit_clarification_questions(questions, noAmbiguities, deferredNote,
coverage)`:
 - `questions`: at most {MAX_QUESTIONS_PER_SESSION}; order them by
   descending Impact × Uncertainty.
 - `noAmbiguities`: true with an empty `questions` list when every
   requirement is already Clear across every category (FR-011).
 - `deferredNote`: a short Korean note naming any categories you had to
   defer because of the cap; null otherwise.
 - `coverage`: one row per taxonomy category with status
   `resolved`/`deferred`/`clear`/`outstanding`.

Do not call this tool until you have a final, deduped queue. Do not ask
the user any questions yourself — your only output is the structured queue.
"""
