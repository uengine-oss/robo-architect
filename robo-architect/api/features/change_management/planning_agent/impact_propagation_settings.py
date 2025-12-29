from __future__ import annotations

import os
from typing import Any, Dict, List


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def relationship_whitelist() -> List[str]:
    """
    Relationship whitelist used for 2-hop propagation context.
    Defaults align with p_local/poc/1_poc_propagation.md.
    """
    raw = os.getenv(
        "CHANGE_PROPAGATION_REL_WHITELIST",
        "IMPLEMENTS,HAS_AGGREGATE,HAS_COMMAND,EMITS,HAS_POLICY,TRIGGERS,INVOKES",
    )
    return [x.strip() for x in raw.split(",") if x.strip()]


def propagation_limits() -> Dict[str, Any]:
    """
    Stop rules / budget limits (sane defaults for PoC).
    """

    def _env_int(key: str, default: int) -> int:
        try:
            return int((os.getenv(key) or "").strip() or default)
        except Exception:
            return default

    def _env_float(key: str, default: float) -> float:
        try:
            return float((os.getenv(key) or "").strip() or default)
        except Exception:
            return default

    return {
        "max_rounds": _env_int("CHANGE_PROPAGATION_MAX_ROUNDS", 4),
        "max_confirmed_nodes": _env_int("CHANGE_PROPAGATION_MAX_CONFIRMED", 60),
        "max_new_per_round": _env_int("CHANGE_PROPAGATION_MAX_NEW_PER_ROUND", 20),
        "max_frontier_per_round": _env_int("CHANGE_PROPAGATION_MAX_FRONTIER_PER_ROUND", 8),
        "confidence_confirmed": _env_float("CHANGE_PROPAGATION_CONFIRMED_THRESHOLD", 0.70),
        "confidence_review": _env_float("CHANGE_PROPAGATION_REVIEW_THRESHOLD", 0.40),
    }


