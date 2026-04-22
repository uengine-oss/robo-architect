"""Phase 3.1: lexical matcher (glossary-aware).

High-precision pass. For each Task, compute its token set (expanded via glossary
into English code-identifier candidates), then check containment against each
Rule's function / module / tables / actors. Matches here are locked and removed
from the pool handed to Phase 3.2.

Overmatch protection (2026-04-15):
- Tokens appearing in > `max_token_df` (default 40%) of all Rules are dropped
  as corpus-wide stopwords. This kills shared module-family prefixes (e.g.
  `zapamcom`) that would otherwise match every Rule via a single token.
- An additional hard-coded stopword list covers generic entry/utility names
  (`main`, `proc`, `init`, `common`, `call`, `make`, `check`, ...).
- `min_hits` defaults to 2: a single shared informative token is rarely enough
  evidence for a high-confidence lock.
"""

from __future__ import annotations

import os

from api.features.ingestion.hybrid.contracts import (
    ActivityRuleMapping,
    BpmSkeleton,
    GlossaryTerm,
    RuleContext,
)
from api.features.ingestion.hybrid.mapper.glossary_extractor import (
    _split_identifier,
    expand_task_tokens,
)


# Generic identifiers that carry no business meaning even before DF filtering.
def _is_hangul(s: str) -> bool:
    return any("\uAC00" <= ch <= "\uD7A3" for ch in s)


def _is_informative(tok: str) -> bool:
    """Hangul tokens count from 2 syllables, ASCII tokens from 3 chars."""
    if not tok:
        return False
    if _is_hangul(tok):
        return len(tok) >= 2
    return len(tok) >= 3


_HARD_STOPWORDS: frozenset[str] = frozenset({
    "main", "proc", "process", "init", "common", "util", "utils", "helper",
    "module", "call", "make", "check", "get", "set", "is", "do",
    "impl", "factory", "manager", "service", "handler",
    "input", "output", "result", "value", "data",
})


def _rule_tokens(ctx: RuleContext) -> set[str]:
    tokens: set[str] = set()
    for s in (
        ctx.source_function,
        ctx.source_module,
        ctx.function_summary,
        ctx.given,
        ctx.when,
        ctx.then,
        ctx.context_cluster,  # Phase 2.5 BC tag (e.g. "이력관리")
    ):
        for tok in _split_identifier(s or ""):
            tokens.add(tok)
    for name in ctx.actors:
        for tok in _split_identifier(name or ""):
            tokens.add(tok)
    for name in ctx.reads_tables + ctx.writes_tables:
        for tok in _split_identifier(name or ""):
            tokens.add(tok)
    return tokens


def _score(hits: set[str]) -> float:
    """Confidence goes up with distinct hits, capped at 0.97 to leave room for 1.0 = manual."""
    n = len(hits)
    if n == 0:
        return 0.0
    if n == 1:
        return 0.85
    if n == 2:
        return 0.92
    return 0.97


def _build_stopword_set(rule_token_sets: dict[str, set[str]], max_df_ratio: float) -> set[str]:
    """Tokens that occur in more than `max_df_ratio` of rule docs are corpus stopwords."""
    n_rules = len(rule_token_sets)
    if n_rules == 0:
        return set(_HARD_STOPWORDS)
    df: dict[str, int] = {}
    for tokens in rule_token_sets.values():
        for tok in tokens:
            df[tok] = df.get(tok, 0) + 1
    threshold = max(2, int(round(n_rules * max_df_ratio)))
    auto = {tok for tok, c in df.items() if c >= threshold}
    return set(_HARD_STOPWORDS) | auto


def match_lexical(
    skeleton: BpmSkeleton,
    contexts: list[RuleContext],
    glossary: list[GlossaryTerm],
    min_hits: int | None = None,
    max_token_df: float | None = None,
) -> list[ActivityRuleMapping]:
    """Return high-confidence Task↔Rule matches based on token containment."""
    if not skeleton.tasks or not contexts:
        return []

    if min_hits is None:
        min_hits = int(os.getenv("HYBRID_LEXICAL_MIN_HITS", "2"))
    if max_token_df is None:
        # With Hangul tokens flowing through, common Korean nouns like 처리/결과/입력
        # also need to be filtered. 0.35 keeps domain-distinctive words while
        # cutting cross-rule generic ones.
        max_token_df = float(os.getenv("HYBRID_LEXICAL_MAX_TOKEN_DF", "0.35"))

    rule_token_sets = {c.rule_id: _rule_tokens(c) for c in contexts}
    stopwords = _build_stopword_set(rule_token_sets, max_token_df)
    rule_token_sets = {rid: (toks - stopwords) for rid, toks in rule_token_sets.items()}

    results: list[ActivityRuleMapping] = []
    actor_name_by_id = {a.id: a.name for a in skeleton.actors}

    for task in skeleton.tasks:
        task_text = " ".join(filter(None, [
            task.name,
            task.description or "",
            *(actor_name_by_id.get(aid, "") for aid in task.actor_ids),
        ]))
        tokens = expand_task_tokens(task_text, glossary) - stopwords
        if not tokens:
            continue
        for ctx in contexts:
            hits = tokens & rule_token_sets[ctx.rule_id]
            # Strong = informative tokens. Hangul carries more semantic weight
            # per character than ASCII, so 2 syllables qualify; ASCII needs 3+.
            strong = {h for h in hits if _is_informative(h)}
            if len(strong) < min_hits:
                continue
            results.append(ActivityRuleMapping(
                task_id=task.id,
                rule_id=ctx.rule_id,
                score=_score(strong),
                method="lexical",
            ))
    return results
