"""LangChain callback that tallies LLM token usage onto an IngestionSession.

Spec 017 / research.md D1.

How it works:
- One callback instance per `IngestionSession`.
- `get_llm()` (in `ingestion_llm_runtime.py`) auto-attaches the callback when
  a session is currently active (set via the `current_session` context-local
  hook). Existing call sites don't change.
- On each successful LLM response, `on_llm_end` reads
  `response.llm_output.token_usage` (LangChain's standardized token-usage
  surface that fans out across OpenAI / Anthropic / Google).
- If usage_metadata is missing (older provider, custom backend), falls back
  per the `LLM_TOKENIZER_FALLBACK` env: `tiktoken` → `heuristic` → `none`.
  Sets `session.tokens_approximate = True` (sticky) on any non-exact path.

Failure handling: ANY exception inside the callback is caught and logged at
WARN level. A token-tally failure MUST NOT propagate (would abort the LLM
call itself, which is a much worse user experience than a missing chip).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from api.platform.env import get_llm_tokenizer_fallback
from api.platform.observability.smart_logger import SmartLogger


class IngestionTokenCallback(BaseCallbackHandler):
    """Per-session token tally.

    Bound to one IngestionSession; not safe to share across sessions (the
    callback mutates session-level totals).
    """

    raise_error: bool = False  # never abort the LLM call on a tally error

    def __init__(self, session: Any) -> None:
        self._session = session
        self._tiktoken_enc: Any | None = None
        self._tiktoken_failed: bool = False

    # ─── LangChain hooks ─────────────────────────────────────────────────

    def on_llm_start(self, serialized: Any, prompts: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Spec 017 FR-005: gate the LLM dispatch.

        If `session.is_cancelled` was set after the LLM call was scheduled but
        before it dispatches, raise CancelledError to abort. This makes every
        LangChain `llm.invoke(...)` / `llm.ainvoke(...)` call automatically
        suspendable without per-call-site changes.

        Note: an in-flight call (response already streaming) cannot be aborted
        from here — that's a provider limitation. This hook only stops the
        *dispatch*, which combined with the explicit `session_call_slot` wraps
        around bulk-flush and wireframe-service calls covers all the major
        boundaries.
        """
        try:
            if getattr(self._session, "is_cancelled", False):
                phase = getattr(self._session, "current_phase", "") or "unknown"
                SmartLogger.log(
                    "INFO",
                    f"ingestion.suspend.gate fired (on_llm_start) phase={phase}",
                    category="ingestion.suspend.gate",
                    params={
                        "session_id": getattr(self._session, "id", None),
                        "phase": phase,
                        "trigger": "on_llm_start",
                    },
                )
                raise asyncio.CancelledError("ingestion suspended (LLM dispatch gate)")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — gate never aborts the call on a check error
            pass

    def on_chat_model_start(self, serialized: Any, messages: Any, **kwargs: Any) -> None:  # type: ignore[override]
        # Some LangChain versions route chat models through this hook instead.
        self.on_llm_start(serialized, None, **kwargs)

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:  # type: ignore[override]
        try:
            usage = self._extract_usage(response)
            tokens = usage["total"]
            approximate = usage["approximate"]
            self._record(tokens, approximate)
        except Exception as exc:  # noqa: BLE001
            SmartLogger.log(
                "WARN",
                f"ingestion.tokens.callback_error: {exc}",
                category="ingestion.tokens.callback_error",
                params={
                    "session_id": getattr(self._session, "id", None),
                    "phase": getattr(self._session, "current_phase", ""),
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )

    def on_chat_model_end(self, response: Any, **kwargs: Any) -> None:  # type: ignore[override]
        # Some LangChain versions route chat models through this hook instead.
        self.on_llm_end(response, **kwargs)

    # ─── usage_metadata extraction ───────────────────────────────────────

    def _extract_usage(self, response: Any) -> dict[str, Any]:
        """Return {"total": int, "approximate": bool}."""
        # Path 1: LLMResult.llm_output["token_usage"] (OpenAI legacy + others).
        try:
            llm_output = getattr(response, "llm_output", None) or {}
            token_usage = llm_output.get("token_usage") if isinstance(llm_output, dict) else None
            if isinstance(token_usage, dict):
                total = (
                    token_usage.get("total_tokens")
                    or (token_usage.get("prompt_tokens", 0) or 0) + (token_usage.get("completion_tokens", 0) or 0)
                )
                if total and int(total) > 0:
                    return {"total": int(total), "approximate": False}
        except Exception:  # noqa: BLE001
            pass

        # Path 2: AIMessage.usage_metadata (LangChain v0.2+ standardized).
        try:
            generations = getattr(response, "generations", None) or []
            if generations:
                inner = generations[0]
                if inner:
                    first = inner[0] if isinstance(inner, list) else inner
                    msg = getattr(first, "message", None)
                    usage_meta = getattr(msg, "usage_metadata", None) if msg is not None else None
                    if isinstance(usage_meta, dict):
                        total = (
                            usage_meta.get("total_tokens")
                            or (usage_meta.get("input_tokens", 0) or 0) + (usage_meta.get("output_tokens", 0) or 0)
                        )
                        if total and int(total) > 0:
                            return {"total": int(total), "approximate": False}
                    # Some adapters expose it on response_metadata instead.
                    rmeta = getattr(msg, "response_metadata", {}) if msg is not None else {}
                    if isinstance(rmeta, dict):
                        usage = rmeta.get("token_usage") or rmeta.get("usage")
                        if isinstance(usage, dict):
                            total = (
                                usage.get("total_tokens")
                                or (usage.get("prompt_tokens", 0) or 0) + (usage.get("completion_tokens", 0) or 0)
                            )
                            if total and int(total) > 0:
                                return {"total": int(total), "approximate": False}
        except Exception:  # noqa: BLE001
            pass

        # Path 3: fallback. We don't have prompt text here (LangChain hides it
        # in `on_llm_start`), so we approximate from the response text alone
        # and double it to roughly account for prompt tokens. Crude but better
        # than zero. Users can switch to "heuristic" or "none" via env.
        text = self._extract_response_text(response)
        if not text:
            return {"total": 0, "approximate": True}
        strategy = get_llm_tokenizer_fallback()
        if strategy == "none":
            return {"total": 0, "approximate": True}
        if strategy == "tiktoken" and not self._tiktoken_failed:
            count = self._tiktoken_count(text)
            if count is not None:
                # x2 to account for prompt tokens we can't see here.
                return {"total": int(count * 2), "approximate": True}
        # heuristic
        return {"total": (len(text) // 4) * 2, "approximate": True}

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        try:
            generations = getattr(response, "generations", None) or []
            if not generations:
                return ""
            inner = generations[0]
            first = inner[0] if isinstance(inner, list) else inner
            text = getattr(first, "text", None)
            if text:
                return str(text)
            msg = getattr(first, "message", None)
            content = getattr(msg, "content", None) if msg is not None else None
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                # Some adapters return list[dict] for multi-modal; flatten.
                return " ".join(
                    str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in content
                )
        except Exception:  # noqa: BLE001
            pass
        return ""

    def _tiktoken_count(self, text: str) -> int | None:
        if self._tiktoken_failed:
            return None
        if self._tiktoken_enc is None:
            try:
                import tiktoken
                self._tiktoken_enc = tiktoken.get_encoding("cl100k_base")
            except Exception:  # noqa: BLE001
                self._tiktoken_failed = True
                return None
        try:
            return len(self._tiktoken_enc.encode(text))
        except Exception:  # noqa: BLE001
            self._tiktoken_failed = True
            return None

    # ─── session mutation + observability ────────────────────────────────

    def _record(self, tokens: int, approximate: bool) -> None:
        if tokens <= 0 and not approximate:
            return  # nothing to record
        sess = self._session
        phase = getattr(sess, "current_phase", "") or "unknown"
        # Total + per-phase aggregation.
        sess.tokens_total = (getattr(sess, "tokens_total", 0) or 0) + max(int(tokens), 0)
        by_phase = getattr(sess, "tokens_by_phase", None)
        if by_phase is None:
            by_phase = {}
            sess.tokens_by_phase = by_phase
        by_phase[phase] = (by_phase.get(phase, 0) or 0) + max(int(tokens), 0)
        sess.tokens_last_call = max(int(tokens), 0)
        if approximate and not getattr(sess, "tokens_approximate", False):
            sess.tokens_approximate = True
        SmartLogger.log(
            "DEBUG",
            f"ingestion.tokens.call phase={phase} tokens={tokens} total={sess.tokens_total} approx={approximate}",
            category="ingestion.tokens.call",
            params={
                "session_id": getattr(sess, "id", None),
                "phase": phase,
                "tokens": int(tokens),
                "session_total": sess.tokens_total,
                "approximate": bool(approximate),
                "at": time.time(),
            },
        )
