"""Phase 2.6: Per-Rule DDD role tagging (Event Storming promotion hint).

Goal: give each Rule an `es_role` label so Phase 5 can route it to the correct
Event Storming node type without re-deriving the classification via LLM.

Roles (5, unified 2026-04-20):
  - aggregate   🟨 — any Aggregate-internal rule (state mutation OR decision).
                      Phase 5 sub-routes by `writes_tables` presence:
                      WRITES → invariant section, no WRITES → domain rule section.
  - validation  🟦 — Command input guard (no writes, GIVEN input → accept/reject)
  - policy      🟪 — reactive rule (on Event/state → build msg / call next command)
  - query       🟩 — READS-only data retrieval (lookup / boolean predicate)
  - external    🟥 — external system adapter / top-level entry

Previously invariant + decision were separate roles; merged because both live
inside the same Aggregate and non-developer designers found the split confusing
at the UI layer.

Design:
  1. **Deterministic heuristics first** — using the same signals we already
     have in RuleContext (reads_tables, writes_tables, source_function,
     source_module) + rule.title / then keyword patterns.
  2. **Confidence score** per classification. Ambiguous (<0.5) falls back to
     `decision` as a sane default. No LLM call in this phase (keeps cost zero
     and makes re-runs deterministic). LLM refinement can be added later
     behind a flag if heuristic precision drops.

Output: `dict[rule_id, tuple[role, confidence]]`.
"""

from __future__ import annotations

import re
from typing import Iterable

from api.features.ingestion.hybrid.contracts import RuleContext, RuleDTO
from api.platform.observability.smart_logger import SmartLogger

# Role constants — must match the set exposed on `Rule.es_role` in Neo4j.
ROLE_AGGREGATE = "aggregate"     # merged from invariant + decision (2026-04-20)
ROLE_VALIDATION = "validation"
ROLE_POLICY = "policy"
ROLE_QUERY = "query"
ROLE_EXTERNAL = "external"

ALL_ROLES: tuple[str, ...] = (
    ROLE_AGGREGATE,
    ROLE_VALIDATION,
    ROLE_POLICY,
    ROLE_QUERY,
    ROLE_EXTERNAL,
)


# ---------------------------------------------------------------------------
# Keyword signal banks (Korean + ASCII). Kept as plain regex so the rationale
# is inspectable and tweakable per-project. Each entry: (role, score).
# Higher score wins; ties broken by stable iteration order.
# ---------------------------------------------------------------------------

# Title / `then` keyword signals — strongest semantic layer.
_TITLE_SIGNALS: list[tuple[re.Pattern[str], str, float]] = [
    # Validation — rejection verbs
    (re.compile(r"(거부|거절|반려)"), ROLE_VALIDATION, 0.9),
    (re.compile(r"(필수|누락|없으면|비어 ?있)"), ROLE_VALIDATION, 0.85),
    (re.compile(r"(유효성|valid)", re.I), ROLE_VALIDATION, 0.8),
    # Policy — reactive "on → produce message / trigger next"
    (re.compile(r"(메시지|문구).{0,6}(만들|만든|만드|조립|생성|반환|결정|고정|부여|대체)"), ROLE_POLICY, 0.92),
    # Reactive chain — requires an explicit action verb (message/call/send), NOT generic 처리 which is too broad
    (re.compile(r"(이면|일 ?때|시).{0,30}(호출|요청|전달|만든|만들|생성|발송|전송)"), ROLE_POLICY, 0.7),
    # Aggregate — decision forms (computed flag / Y-N / 반영여부)
    (re.compile(r"(반영여부|반영 ?여부)"), ROLE_AGGREGATE, 0.88),
    (re.compile(r"(판정|결정|보정|반영한다|선택한다|경로를 ?고른다|결정한다)"), ROLE_AGGREGATE, 0.85),
    # Negation & judgement forms that also express a decision outcome
    (re.compile(r"반영하지 ?않"), ROLE_AGGREGATE, 0.85),
    (re.compile(r"(으로|이면).{0,10}(본다|간주한다)"), ROLE_AGGREGATE, 0.8),
    # Bank/auth decision rules of the form "X는 Y일 때만 반영한다" — strong aggregate signal
    (re.compile(r"(일 ?때만|때만).{0,15}반영"), ROLE_AGGREGATE, 0.9),
    (re.compile(r"(계산|산출|집계)"), ROLE_AGGREGATE, 0.7),
    # Aggregate — state-mutating actions (formerly `invariant`)
    (re.compile(r"(이력|history|hst).{0,10}(저장|적재|누적|생성|갱신|반영|삭제)"), ROLE_AGGREGATE, 0.9),
    (re.compile(r"(저장|적재|누적|갱신|update|insert)", re.I), ROLE_AGGREGATE, 0.75),
    # Query — lookup / boolean check
    (re.compile(r"(조회|검색|확인을 ?요청|존재 ?여부)"), ROLE_QUERY, 0.85),
    (re.compile(r"(공통코드|코드군).{0,10}(조회|포함)"), ROLE_QUERY, 0.8),
    # External adapter — require a concrete external-integration verb.
    # "외부인증" (auth type name) alone must NOT match; only "외부 조회/호출/연동/…" does.
    (re.compile(r"외부\s*(조회|호출|API|연동|시스템|전문|통신|연계)", re.I), ROLE_EXTERNAL, 0.9),
    (re.compile(r"(externally ?call|gateway|rpc|api\s*호출)", re.I), ROLE_EXTERNAL, 0.85),
]

# Function-name pattern signals — structural layer (reliable when present).
# We weight fn signals lower than title signals in `_classify_single` because
# function names tell us *where* the code lives, not *what role* the BL plays.
# A zapam* entry function can contain a validation BL; a check_* function can
# contain a policy BL. So fn hints are supplementary.
_FN_SIGNALS: list[tuple[re.Pattern[str], str, float]] = [
    # dbio with _i / _u / _d suffix = insert / update / delete → Aggregate
    (re.compile(r"dbio_.*_i\d+", re.I), ROLE_AGGREGATE, 0.95),
    (re.compile(r"dbio_.*_u\d+", re.I), ROLE_AGGREGATE, 0.95),
    (re.compile(r"dbio_.*_d\d+", re.I), ROLE_AGGREGATE, 0.9),
    # dbio with *canyn / *_s / *_q suffix = select / query
    (re.compile(r"dbio_.*_(canyn|check|exist|s\d+|q\d+)", re.I), ROLE_QUERY, 0.9),
    # check_ / valid* / verify* / assert* — allow anywhere in fn name, not just start
    (re.compile(r"(?:^|_)(check|valid|verify|assert)(?:_|$)", re.I), ROLE_VALIDATION, 0.9),
    # msg_make / err_msg = message building (policy)
    (re.compile(r"(err_msg|msg_make|make_msg|build_msg|notify)", re.I), ROLE_POLICY, 0.92),
    # input_validation name
    (re.compile(r"input_valid", re.I), ROLE_VALIDATION, 0.95),
    # Top-level entry functions — weak external hint only (title should override).
    (re.compile(r"^z[a-z]+\d+", re.I), ROLE_EXTERNAL, 0.7),
    (re.compile(r"^(entry|main_entry|handler)_", re.I), ROLE_EXTERNAL, 0.7),
]


def _score_role_from_signals(
    text: str,
    signals: list[tuple[re.Pattern[str], str, float]],
) -> dict[str, float]:
    """Accumulate role scores from a signal bank. Max wins per role so a single
    strong hit can dominate multiple weak ones."""
    scores: dict[str, float] = {}
    if not text:
        return scores
    for pattern, role, score in signals:
        if pattern.search(text):
            if score > scores.get(role, 0.0):
                scores[role] = score
    return scores


# Signal weights — title semantics dominate over structural hints.
# A zapam* entry function with a "거절한다" title IS validation, regardless of
# where it lives. These weights are applied as multipliers on the raw bank scores.
_W_TITLE = 1.0
_W_FN = 0.80
_W_TABLES = 0.55


def _classify_single(rule: RuleDTO, ctx: RuleContext | None) -> tuple[str, float, str]:
    """Classify one rule. Returns (role, confidence, rationale).

    Rationale is a short debug string naming which signal bank fired — useful
    for spot-checking distributions and tuning the regex banks.
    """
    has_writes = bool(ctx and ctx.writes_tables)
    has_reads = bool(ctx and ctx.reads_tables)

    # 1. Function-name signal (structural hint)
    fn_scores_raw = _score_role_from_signals(rule.source_function or "", _FN_SIGNALS)

    # 2. Title / then keyword signal (semantic — highest weight)
    text = rule.title or " ".join([rule.when or "", rule.then or ""])
    title_scores_raw = _score_role_from_signals(text, _TITLE_SIGNALS)

    # 3. Table-presence signal (weak but broad)
    table_scores_raw: dict[str, float] = {}
    if has_writes:
        # WRITES → Aggregate (state-mutating side of the Aggregate family)
        table_scores_raw[ROLE_AGGREGATE] = 0.6
    elif has_reads:
        table_scores_raw[ROLE_QUERY] = 0.6

    # Weight each bank and merge — take max per role across all banks.
    combined: dict[str, float] = {}
    provenance: dict[str, str] = {}
    for bank, weight, tag in (
        (title_scores_raw, _W_TITLE, "title"),
        (fn_scores_raw, _W_FN, "fn"),
        (table_scores_raw, _W_TABLES, "tables"),
    ):
        for role, raw in bank.items():
            weighted = raw * weight
            if weighted > combined.get(role, 0.0):
                combined[role] = weighted
                provenance[role] = tag

    if not combined:
        # Pure fallback — unclassifiable rule, bias toward aggregate (the
        # broadest bucket) so it still gets considered in Phase 5 rather
        # than silently dropped.
        return ROLE_AGGREGATE, 0.3, "fallback_no_signal"

    # Pick best role
    best_role = max(combined.items(), key=lambda kv: kv[1])[0]
    best_score = combined[best_role]
    rationale = provenance.get(best_role, "weighted")

    return best_role, float(best_score), rationale


def tag_rule_es_roles(
    rules: Iterable[RuleDTO],
    contexts: Iterable[RuleContext],
) -> dict[str, tuple[str, float]]:
    """Phase 2.6 main entry — returns `rule_id → (role, confidence)`.

    Deterministic: same input always produces same output. No LLM calls.
    """
    rules = list(rules)
    contexts = list(contexts)
    if not rules:
        return {}

    ctx_by_rule = {c.rule_id: c for c in contexts}
    result: dict[str, tuple[str, float]] = {}
    role_counts: dict[str, int] = {r: 0 for r in ALL_ROLES}

    for r in rules:
        ctx = ctx_by_rule.get(r.id)
        role, conf, _ = _classify_single(r, ctx)
        result[r.id] = (role, conf)
        role_counts[role] = role_counts.get(role, 0) + 1

    SmartLogger.log(
        "INFO", "Phase 2.6 ES role tagging complete",
        category="ingestion.hybrid.es_role",
        params={
            "rules_in": len(rules),
            "rules_tagged": len(result),
            "role_counts": role_counts,
        },
    )
    return result
