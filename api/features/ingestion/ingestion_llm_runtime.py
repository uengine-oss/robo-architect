"""
Ingestion LLM Runtime

Business capability: configure and obtain the LLM used by ingestion workflows.
Kept feature-local to avoid creating a generic global LLM layer.
"""

from __future__ import annotations

from api.platform.env import get_llm_provider_model
from api.platform.llm import get_llm as _platform_get_llm
from api.platform.observability.smart_logger import SmartLogger


def get_llm(**kwargs):
    """Get configured LLM instance."""
    provider, model = get_llm_provider_model()
    log_params = {"provider": provider, "model": model}
    if kwargs:
        log_params.update(kwargs)
    SmartLogger.log("INFO", "LLM configured", category="ingestion.llm", params=log_params)

    return _platform_get_llm(**kwargs)


