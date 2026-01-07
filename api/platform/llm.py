"""
Platform LLM factory.

Centralizes LLM instantiation so feature modules don't duplicate provider/model wiring.

Environment variables:
- LLM_PROVIDER: openai | anthropic | google (also supports aliases: gemini, google-genai, google_genai)
- LLM_MODEL: model name (required for anthropic/google; optional for openai)
- GOOGLE_API_KEY: required when using Google (Gemini) provider
- MODEL_KWARGS: JSON dict (or Python dict literal) merged into model constructor kwargs
  (e.g. {"temperature": 0.3})
"""

from __future__ import annotations

from typing import Any

from api.platform.env import env_dict, env_str, get_llm_provider

OPENAI_DEFAULT_MODEL = "gpt-4.1-2025-04-14"


def _normalize_provider(provider: str) -> str:
    p = (provider or "").strip().lower()
    p = p.replace("-", "_")
    return p


def _resolve_provider(provider: str | None) -> str:
    raw = provider if provider is not None else get_llm_provider("openai")
    p = _normalize_provider(raw)

    # Supported aliases
    if p in {"openai"}:
        return "openai"
    if p in {"anthropic"}:
        return "anthropic"
    if p in {"google", "gemini", "google_genai"}:
        return "google"

    raise ValueError(
        f"Unsupported LLM_PROVIDER='{raw}'. Supported: openai | anthropic | google "
        f"(aliases: gemini, google-genai, google_genai)."
    )


def _resolve_model(provider: str, model: str | None) -> str:
    if model is not None:
        m = model.strip()
        if not m:
            raise ValueError("LLM model was provided but empty.")
        return m

    # Important: `api.platform.env.get_llm_model()` always returns an OpenAI default.
    # For anthropic/google we require explicit configuration.
    m = env_str("LLM_MODEL", default=None)
    if provider == "openai":
        return m or OPENAI_DEFAULT_MODEL

    if not m:
        example = "claude-3-5-sonnet-latest" if provider == "anthropic" else "gemini-2.0-flash"
        raise ValueError(
            f"LLM_MODEL is required for provider '{provider}'. "
            f"Set environment variable LLM_MODEL (e.g. '{example}')."
        )
    return m


def get_llm(
    *,
    provider: str | None = None,
    model: str | None = None,
    **kwargs: Any
):
    """
    Get a configured LangChain chat model instance.

    Args:
        provider: Override LLM provider. If omitted, uses env `LLM_PROVIDER`.
        model: Override model name. If omitted, uses env `LLM_MODEL` with provider-specific policy.
        temperature: Sampling temperature. If omitted, uses `MODEL_KWARGS.temperature` if present, else defaults to 0.
        **kwargs: Passed through to the underlying chat model constructor.
    """
    resolved_provider = _resolve_provider(provider)
    resolved_model = _resolve_model(resolved_provider, model)

    # Merge extra kwargs from environment.
    # Precedence: call-time kwargs > MODEL_KWARGS
    model_kwargs_from_env = env_dict("MODEL_KWARGS", default={"temperature": 0.3})
    effective_kwargs: dict[str, Any] = dict(model_kwargs_from_env)
    effective_kwargs.update(kwargs)

    # Avoid passing reserved constructor arguments twice.
    if "model" in effective_kwargs:
        raise ValueError(
            "Do not pass 'model' via MODEL_KWARGS/kwargs; use LLM_MODEL env var or get_llm(model=...)."
        )

    if resolved_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=resolved_model, **effective_kwargs)

    if resolved_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=resolved_model, **effective_kwargs)

    # resolved_provider == "google"
    google_api_key = env_str("GOOGLE_API_KEY", default=None)
    if google_api_key and "google_api_key" not in effective_kwargs:
        effective_kwargs["google_api_key"] = google_api_key

    if "google_api_key" not in effective_kwargs:
        raise ValueError(
            "GOOGLE_API_KEY is required for provider 'google' (Gemini). "
            "Set environment variable GOOGLE_API_KEY."
        )

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=resolved_model, **effective_kwargs)


