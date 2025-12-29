"""
Ingestion LLM Runtime

Business capability: configure and obtain the LLM used by ingestion workflows.
Kept feature-local to avoid creating a generic global LLM layer.
"""

from __future__ import annotations

from api.platform.env import get_llm_provider_model

from api.platform.observability.smart_logger import SmartLogger


def get_llm():
    """Get configured LLM instance."""
    provider, model = get_llm_provider_model()
    SmartLogger.log("INFO", "LLM configured", category="ingestion.llm", params={"provider": provider, "model": model})

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, temperature=0)
    else:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=0)


