"""SpecKit `clarify` methodology — load the real skill file (030).

Instead of paraphrasing `.claude/skills/speckit-clarify/SKILL.md` in code,
we read the skill markdown at import time and feed it to the deep agent
as the system prompt. This keeps a *single source of truth* — when the
SpecKit skill evolves, the agent's behavior follows automatically with no
code edits.

If the skill file is missing (e.g. in a deployment environment where the
`.claude/` directory was not copied), we fall back to a compact embedded
summary so the feature still works.
"""

from __future__ import annotations

from pathlib import Path

from api.features.requirements.clarification_contracts import AmbiguityCategory

# ── Caps (FR-004) ────────────────────────────────────────────────────────

MAX_QUESTIONS_PER_SESSION: int = 5
MAX_OPTIONS_PER_CLOSED_QUESTION: int = 5
MIN_OPTIONS_PER_CLOSED_QUESTION: int = 2


# ── SKILL.md loader ──────────────────────────────────────────────────────


def _candidate_skill_paths() -> list[Path]:
    """Possible locations of the SpecKit clarify skill file."""
    here = Path(__file__).resolve()
    # Walk up the tree looking for `.claude/skills/speckit-clarify/SKILL.md`.
    candidates: list[Path] = []
    for parent in [here, *here.parents]:
        c = parent / ".claude" / "skills" / "speckit-clarify" / "SKILL.md"
        candidates.append(c)
    # Also check a few well-known absolute paths used during dev.
    candidates.append(Path.home() / ".claude" / "skills" / "speckit-clarify" / "SKILL.md")
    return candidates


def _load_skill_markdown() -> tuple[str, str | None]:
    """Return (markdown_text, source_path | None).

    Falls back to a compact embedded summary when the skill file isn't found.
    """
    for p in _candidate_skill_paths():
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8"), str(p)
        except Exception:  # noqa: BLE001
            continue
    return _FALLBACK_SKILL_MARKDOWN, None


# Compact fallback: covers the taxonomy + the cap + the question-format
# rules, in case the SKILL.md file isn't reachable at runtime.
_FALLBACK_SKILL_MARKDOWN = """\
SpecKit clarify methodology (compact fallback).

Scan each requirement across this taxonomy and label every category as
Clear / Partial / Missing:

- Functional Scope & Behavior — goals, success, out-of-scope, roles
- Domain & Data Model — entities, fields, identity, lifecycle, scale
- Interaction & UX Flow — journeys, error/empty/loading states, a11y
- Non-Functional Quality — performance, scalability, reliability,
  observability, security, compliance
- Integration & External Dependencies — services, formats, protocols
- Edge Cases & Failure Handling — negative scenarios, throttling, conflicts
- Constraints & Tradeoffs — tech constraints, rejected alternatives
- Terminology & Consistency — canonical terms, deprecated synonyms
- Completion Signals — testable acceptance, DoD-style indicators
- Misc / Placeholders — TODOs, ambiguous adjectives ('robust', 'intuitive')

Produce a prioritized queue of ≤5 questions, each answerable as:
- a 2–5 option closed question, OR
- a short-answer (≤5 words) free-form question.

Each question must include a referenced requirement id and a recommended
answer that, if accepted, resolves the gap. Use Impact × Uncertainty to
rank; if more than 5 unresolved categories remain, keep the top 5.
"""


_SKILL_MARKDOWN, _SKILL_SOURCE = _load_skill_markdown()


# ── Mapping from skill section headings → AmbiguityCategory enum ────────

# The deep agent emits these strings (matching the taxonomy enum values).
TAXONOMY_HINT: str = ", ".join(c.value for c in AmbiguityCategory)


# ── System prompt assembled from the real skill ─────────────────────────


DEEP_AGENT_INSTRUCTIONS: str = f"""\
You are the Requirements Clarification Agent.

Your job is to scan a set of extracted requirements (user stories) for
ambiguity and underspecification using the **SpecKit `clarify` skill
methodology** verbatim (reproduced below), then produce a small,
prioritized queue of clarification questions a human architect will
answer one at a time.

# IMPORTANT DEVIATIONS from the interactive SKILL workflow

This agent runs in BATCH mode, not interactively:
- DO NOT print the question table to the user — we collect them
  programmatically through the `submit_clarification_questions` tool.
- DO NOT modify any spec file. Encoding answers back into requirements is
  handled by a separate downstream step.
- DO NOT use `## Clarifications` section logic — your output is the
  structured tool call only.
- DO emit at most {MAX_QUESTIONS_PER_SESSION} questions, with categories
  drawn from this exact enum: {TAXONOMY_HINT}.
- DO call `submit_clarification_questions` EXACTLY ONCE at the end with
  the final queue. If you find no material ambiguities, call it with an
  empty `questions` list and `noAmbiguities=true`.
- For each question, the `category` field MUST be one of the enum values
  above (snake_case, not the human-readable heading).
- Closed questions need 2–{MAX_OPTIONS_PER_CLOSED_QUESTION} options;
  short_answer questions have no options. Always include a
  `recommendedAnswer`.
- `referencedRequirementIds` MUST contain only ids that appeared in the
  input list — never invent new ids.

# ── BEGIN SpecKit clarify SKILL.md (verbatim) ────────────────────────

{_SKILL_MARKDOWN}

# ── END SpecKit clarify SKILL.md ─────────────────────────────────────

Remember: your only output is the structured `submit_clarification_questions`
tool call. Do not ask the user anything yourself. Apply the SKILL's
taxonomy and prioritization rules to the input requirements.
"""


# ── Diagnostics ──────────────────────────────────────────────────────────


def get_skill_source() -> str | None:
    """Return the path to the SKILL.md file we loaded, or None if fallback."""
    return _SKILL_SOURCE
