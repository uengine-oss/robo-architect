"""
Ingestion LLM Runtime

Business capability: configure and obtain the LLM used by ingestion workflows.
Kept feature-local to avoid creating a generic global LLM layer.

Spec 017: when an ingestion workflow is running, the workflow runner sets
`current_session` to its `IngestionSession`. Every `get_llm()` call in that
workflow then auto-attaches an `IngestionTokenCallback` so token usage is
tallied without any per-call-site change. This keeps Constitution VI
(provider-agnostic) intact — capture happens at the LangChain callback layer,
not in feature code.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Optional

from api.platform.env import get_llm_provider_model
from api.platform.llm import get_llm as _platform_get_llm
from api.platform.observability.smart_logger import SmartLogger


# Context-local "current session" hook. Set by the workflow runner around
# its `_run()` body so every `get_llm()` inside that scope auto-attaches a
# session-bound IngestionTokenCallback. Outside an ingestion workflow this
# is None and `get_llm()` behaves exactly like the platform default.
_current_session: ContextVar[Optional[Any]] = ContextVar(
    "ingestion_current_session", default=None
)


def set_current_session(session: Optional[Any]) -> Any:
    """Set the active ingestion session for the current async context.

    Returns a token; pass to `reset_current_session(token)` in a `finally`
    block to restore the previous value (typically None).
    """
    return _current_session.set(session)


def reset_current_session(token: Any) -> None:
    """Restore the previous active session (typically None)."""
    try:
        _current_session.reset(token)
    except Exception:  # noqa: BLE001 — context-var reset can fail across loops
        pass


def _diag_context() -> dict:
    """구조화 출력 진단 로그(`platform/llm_structured_diag.py`)에 단계 이름을 붙인다.

    스키마 이름만으로는 같은 스키마를 쓰는 단계(commands·readmodels 등)가
    갈리지 않는다. 세션이 아는 현재 단계를 함께 남긴다.
    """
    session = _current_session.get()
    if session is None:
        return {}
    return {
        "phase": getattr(session, "current_phase", None),
        "session_id": getattr(session, "id", None),
    }


try:
    from api.platform.llm_structured_diag import register_context_provider

    register_context_provider(_diag_context)
except Exception:  # noqa: BLE001 — 진단 등록 실패가 인제스천을 막지 않는다
    pass


def get_llm(**kwargs):
    """Get configured LLM instance.

    If an ingestion workflow has set the current-session hook (see
    `set_current_session`), the returned LLM has an `IngestionTokenCallback`
    bound so token usage is tallied onto that session automatically.
    """
    provider, model = get_llm_provider_model()
    log_params = {"provider": provider, "model": model}
    if kwargs:
        log_params.update(kwargs)
    SmartLogger.log("INFO", "LLM configured", category="ingestion.llm", params=log_params)

    # Auto-attach the token callback when running inside an ingestion workflow.
    session = _current_session.get()
    if session is not None:
        # Lazy import to avoid a circular dependency at module load
        # (`token_callback` -> `smart_logger` -> typical OK; but the callback
        # type only needs to exist when actually used).
        from api.features.ingestion.token_callback import IngestionTokenCallback

        existing = list(kwargs.get("callbacks") or [])
        existing.append(IngestionTokenCallback(session))
        kwargs["callbacks"] = existing

    return _platform_get_llm(**kwargs)
