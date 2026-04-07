"""
User Story formatting utilities for LLM prompts.

Provides a unified formatter that all ingestion phases use to build US text.
When BL (BusinessLogic) data is available (analyzer_graph source),
it automatically appends business rules to each US text.
For rfp/figma sources, BL data is empty and output is identical to the legacy format.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def load_bl_for_user_stories(client: Any) -> dict[str, list[dict]]:
    """Query SOURCED_FROM relationships to build {us_id: [bl_dict, ...]} mapping.

    Returns a dict keyed by UserStory ID, each value is a list of BL dicts
    sorted by sequence: [{seq, title, parent_seq}, ...]

    Only returns data when SOURCED_FROM relationships exist (analyzer_graph source).
    For rfp/figma sources, this returns an empty dict.
    """
    query = """
    MATCH (us:UserStory)-[:SOURCED_FROM]->(bl:BusinessLogic)
    RETURN us.id AS us_id, bl.sequence AS seq, bl.title AS title,
           bl.parent_sequence AS parent_seq,
           bl.given AS given, bl.when AS wh, bl.then AS th
    ORDER BY us.id, bl.sequence
    """
    result: dict[str, list[dict]] = {}
    try:
        with client.session() as session:
            for record in session.run(query):
                us_id = record["us_id"]
                if us_id:
                    result.setdefault(us_id, []).append({
                        "seq": record["seq"],
                        "title": record["title"],
                        "parent_seq": record["parent_seq"],
                        "given": record["given"],
                        "when": record["wh"],
                        "then": record["th"],
                    })
    except Exception:
        # If Neo4j query fails (e.g., no SOURCED_FROM relationships), return empty
        pass
    return result


def format_us_text(
    us: Any,
    bl_map: Optional[Dict[str, List[dict]]] = None,
    *,
    include_benefit: bool = True,
    include_ui_description: bool = False,
    bullet_prefix: str = "",
) -> str:
    """Unified US text formatter used by all ingestion phases.

    When bl_map is provided and contains BL data for this US,
    business rules are appended below the US text.

    Args:
        us: UserStory object (Pydantic model or dict)
        bl_map: {us_id: [{seq, title, parent_seq}, ...]} or None
        include_benefit: Include "so that {benefit}" (default True)
        include_ui_description: Include "(ui: ...)" suffix (default False)
        bullet_prefix: Prefix for the line (e.g., "- " for bullet lists)

    Returns:
        Formatted US text string, optionally with BL rules appended.
    """
    # Extract fields from either Pydantic model or dict
    us_id = _get(us, "id", "")
    role = _get(us, "role", "")
    action = _get(us, "action", "")
    benefit = _get(us, "benefit", "")

    # Ensure role is valid
    if not role or role.lower() in ("user", "사용자", ""):
        role = role or "user"

    # Build base text
    text = f"{bullet_prefix}[{us_id}] As a {role}, I want to {action}"
    if include_benefit and benefit:
        text += f", so that {benefit}"
    if include_ui_description:
        ui = _get(us, "ui_description", "")
        if ui and ui.strip():
            text += f" (ui: {ui})"

    # Append BL rules if available
    if bl_map and us_id and us_id in bl_map:
        bls = bl_map[us_id]
        if bls:
            text += "\n    [비즈니스 규칙]"
            for bl in bls:
                parent = bl.get("parent_seq")
                indent = "      " if parent else ""
                seq = bl['seq']
                parent_info = f" (parent: BL[{parent}])" if parent else ""
                text += f"\n    {indent}- BL[{seq}]{parent_info}: {bl['title']}"
                if bl.get("given"):
                    text += f"\n    {indent}  Given: {bl['given']}"
                if bl.get("when"):
                    text += f"\n    {indent}  When: {bl['when']}"
                if bl.get("then"):
                    text += f"\n    {indent}  Then: {bl['then']}"

    return text


def _get(obj: Any, key: str, default: str = "") -> str:
    """Get a string attribute from either a Pydantic model or dict."""
    if isinstance(obj, dict):
        return str(obj.get(key, default) or default).strip()
    return str(getattr(obj, key, default) or default).strip()
