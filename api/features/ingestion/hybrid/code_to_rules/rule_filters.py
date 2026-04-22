"""Infrastructure/boilerplate filters for Phase 2 rule extraction.

Mirrors the exclusion policy of `analyzer_graph/graph_to_user_stories.py`:
only business-meaningful judgement logic (approval, eligibility, discount,
exception handling, etc.) should become a Rule. EJB lifecycle callbacks,
finder methods, CMP/BMP plumbing, getters/setters and logging are out.
"""

from __future__ import annotations

import re

# Substrings on function / BusinessLogic.title — case-insensitive match.
INFRA_KEYWORDS: tuple[str, ...] = (
    # EJB lifecycle
    "ejbcreate", "ejbremove", "ejbactivate", "ejbpassivate", "ejbstore", "ejbload",
    "ejbpostcreate",
    # Finders
    "ejbfind", "findbyprimarykey", "findall", "findby",
    # CMP/BMP/JDBC plumbing
    "getconnection", "closeconnection", "getdatasource", "initialcontext",
    "lookup", "preparestatement", "executequery", "executeupdate",
    # Bean accessors / bookkeeping
    "getentitycontext", "setentitycontext", "unsetentitycontext",
    "getsessioncontext", "setsessioncontext",
    # Logging / tracing
    "logger", "log.debug", "log.info", "log.warn", "log.error",
    "system.out", "printstacktrace",
)

# getter / setter heuristic: getXxx / setXxx / isXxx with nothing substantive afterwards.
_ACCESSOR_RE = re.compile(r"^(get|set|is)[A-Z]\w*$")


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def is_infra(title: str | None, function_name: str | None = None) -> bool:
    """True if the BusinessLogic entry is infrastructure / boilerplate, not a business rule."""
    hay = f"{_norm(title)} {_norm(function_name)}"
    if not hay.strip():
        return True  # nothing meaningful to keep
    for kw in INFRA_KEYWORDS:
        if kw in hay:
            return True
    fn = (function_name or "").strip()
    if _ACCESSOR_RE.match(fn):
        return True
    return False


def is_meaningful_gwt(given: str | None, when: str | None, then: str | None) -> bool:
    """Require at least two of the three GWT slots to be non-trivial."""
    filled = sum(1 for x in (given, when, then) if (x or "").strip())
    return filled >= 2
