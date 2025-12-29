from __future__ import annotations

from api.platform.env import (
    AI_AUDIT_LOG_ENABLED,
    AI_AUDIT_LOG_FULL_OUTPUT,
    env_first,
    env_str,
)


OPENAI_API_KEY = env_str("OPENAI_API_KEY")
OPENAI_MODEL = env_first(["OPENAI_MODEL", "CHAT_MODEL", "LLM_MODEL"], default="gpt-4o")


