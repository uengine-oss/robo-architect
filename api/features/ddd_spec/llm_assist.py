"""Narrow optional LLM helpers routed through ``ingestion_llm_runtime``.

Every helper degrades to a deterministic passthrough (or returns ``None``)
plus an ``llm_unavailable`` warning when the LLM runtime isn't configured.
No direct ``openai`` / ``anthropic`` / ``google.*`` imports here — that's
Constitution VI.
"""
from __future__ import annotations

import re
from typing import Optional

from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.observability.smart_logger import SmartLogger


def _try_get_llm():
    try:
        return get_llm()
    except Exception as e:  # noqa: BLE001 — LLM availability is best-effort
        SmartLogger.log(
            "WARN",
            f"DDD-spec llm_assist: LLM unavailable ({e})",
            category="ddd_spec.llm_assist.unavailable",
        )
        return None


# --- 1. EARS grammar smoothing -------------------------------------------

_PRESERVED = re.compile(r"\b(WHEN|IF|THEN|SHALL|AND|THE)\b")


def smooth_ears(lines: list[str]) -> tuple[list[str], bool]:
    """Optionally smooth grammar in EARS lines.

    Returns ``(possibly_smoothed_lines, smoothed)``. Load-bearing tokens
    (``WHEN`` / ``IF`` / ``THEN`` / ``SHALL`` / ``AND`` / ``THE``) and any
    aggregate-name token are preserved verbatim: if the smoother strips any
    of them the original line is kept instead. When the LLM is unavailable,
    the deterministic passthrough is returned.
    """
    if not lines:
        return list(lines), False
    llm = _try_get_llm()
    if llm is None:
        return list(lines), False

    prompt = (
        "Rewrite each EARS requirement on a separate line so the English reads "
        "naturally, but keep every UPPERCASE keyword (WHEN, IF, THEN, SHALL, AND, "
        "THE) and every quoted/CamelCase identifier exactly as written. Do not "
        "renumber or omit lines.\n\n"
        + "\n".join(lines)
    )
    try:
        # LangChain-style invoke; the runtime returns AIMessage-like with .content.
        resp = llm.invoke(prompt)
        text = getattr(resp, "content", None) or str(resp)
        rewritten = [ln.strip() for ln in text.splitlines() if ln.strip()]
    except Exception as e:  # noqa: BLE001
        SmartLogger.log(
            "WARN",
            f"DDD-spec llm_assist.smooth_ears failed: {e}",
            category="ddd_spec.llm_assist.smooth_ears_failed",
        )
        return list(lines), False

    if len(rewritten) != len(lines):
        # Fail closed: smoothing changed the structure.
        return list(lines), False

    safe: list[str] = []
    for original, smoothed in zip(lines, rewritten):
        original_keywords = set(_PRESERVED.findall(original))
        smoothed_keywords = set(_PRESERVED.findall(smoothed))
        if not original_keywords.issubset(smoothed_keywords):
            safe.append(original)  # drop the smoothed version
        else:
            safe.append(smoothed)
    return safe, True


# --- 2. Aliases-to-AVOID suggestions -------------------------------------


def suggest_aliases_to_avoid(term: str, context: str) -> tuple[list[str], bool]:
    """Suggest names that should NOT be used as synonyms for ``term``.

    Returns ``(suggestions, ok)``. On LLM unavailable returns ``([], False)``.
    """
    if not term.strip():
        return [], False
    llm = _try_get_llm()
    if llm is None:
        return [], False
    prompt = (
        f"In the bounded context described below, suggest up to four short "
        f"alternative names that developers should NOT use as synonyms for the "
        f"term '{term}', because they would create confusion with neighbouring "
        f"concepts. Output only a JSON array of strings — no prose.\n\n"
        f"Context:\n{context}\n"
    )
    try:
        resp = llm.invoke(prompt)
        text = getattr(resp, "content", None) or str(resp)
    except Exception as e:  # noqa: BLE001
        SmartLogger.log(
            "WARN",
            f"DDD-spec llm_assist.suggest_aliases_to_avoid failed: {e}",
            category="ddd_spec.llm_assist.aliases_failed",
        )
        return [], False

    import json
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text).strip()
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        return [], False
    if not isinstance(out, list):
        return [], False
    cleaned = [str(x).strip() for x in out if str(x).strip()]
    return cleaned[:4], True


# --- 3. Relationship-pattern inference -----------------------------------


def infer_relationship_pattern(
    *,
    upstream_bc: str,
    downstream_bc: str,
    upstream_description: Optional[str],
    downstream_description: Optional[str],
    heuristic_pattern: str,
) -> Optional[str]:
    """LLM-augmented pattern suggestion on top of the heuristic.

    Returns ``None`` when the LLM is unavailable or the response can't be
    parsed — callers keep the heuristic. The caller must always still emit
    the ``relationship_pattern_inferred`` warning.
    """
    llm = _try_get_llm()
    if llm is None:
        return None
    prompt = (
        f"Choose the most fitting DDD strategic relationship pattern for the "
        f"flow from '{upstream_bc}' to '{downstream_bc}'. Options: "
        f"Customer-Supplier, Conformist, Anti-Corruption Layer, "
        f"Open Host Service + Published Language, Shared Kernel, Separate Ways. "
        f"Reply with ONLY the pattern name — no prose. A heuristic already "
        f"chose '{heuristic_pattern}'; correct it only if confident.\n\n"
        f"Upstream BC: {upstream_bc}. {upstream_description or ''}\n"
        f"Downstream BC: {downstream_bc}. {downstream_description or ''}\n"
    )
    try:
        resp = llm.invoke(prompt)
        text = getattr(resp, "content", None) or str(resp)
    except Exception as e:  # noqa: BLE001
        SmartLogger.log(
            "WARN",
            f"DDD-spec llm_assist.infer_relationship_pattern failed: {e}",
            category="ddd_spec.llm_assist.pattern_failed",
        )
        return None
    pat = text.strip().strip("`").strip()
    return pat or None
