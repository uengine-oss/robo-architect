"""User Story formatting utility used by ingestion phases for LLM prompts."""

from __future__ import annotations

from typing import Any


def format_us_text(
    us: Any,
    *,
    include_benefit: bool = True,
    include_ui_description: bool = False,
    bullet_prefix: str = "",
) -> str:
    """Render a User Story as a single line for inclusion in LLM prompts.

    Args:
        us: UserStory object (Pydantic model or dict)
        include_benefit: Append "so that {benefit}" tail (default True)
        include_ui_description: Append "(ui: ...)" suffix (default False)
        bullet_prefix: Optional line prefix (e.g., "- " for bullet lists)
    """
    us_id = _get(us, "id", "")
    role = _get(us, "role", "")
    action = _get(us, "action", "")
    benefit = _get(us, "benefit", "")

    if not role or role.lower() in ("user", "사용자", ""):
        role = role or "user"

    text = f"{bullet_prefix}[{us_id}] As a {role}, I want to {action}"
    if include_benefit and benefit:
        text += f", so that {benefit}"
    if include_ui_description:
        ui = _get(us, "ui_description", "")
        if ui and ui.strip():
            text += f" (ui: {ui})"
    return text


def _get(obj: Any, key: str, default: str = "") -> str:
    if isinstance(obj, dict):
        return str(obj.get(key, default) or default).strip()
    return str(getattr(obj, key, default) or default).strip()
