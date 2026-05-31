"""Scope-aware read/write for conversational editing (035).

One module that knows, for each requirement scope (Epic/Feature/UserStory),
which Neo4j label backs it and which fields are user-editable — so the chat
agent, the apply route, and the history log all share a single source of
truth. Property updates only (keys + relationships preserved), mirroring the
existing PATCH /bounded-context · /feature · /user-story behaviour.
"""

from __future__ import annotations

from typing import Optional

# scope (URL token) → Neo4j label
LABELS = {
    "epic": "BoundedContext",
    "feature": "Feature",
    "user-story": "UserStory",
}

# scope → editable fields. list-typed fields are stored as Neo4j string lists.
SCALAR_FIELDS = {
    "epic": ["name", "description"],
    "feature": ["name", "description"],
    "user-story": ["role", "action", "benefit", "priority", "status"],
}
LIST_FIELDS = {
    "epic": [],
    "feature": ["edgeCases", "assumptions"],
    "user-story": ["acceptanceCriteria"],
}

SCOPE_TITLE = {"epic": "Epic", "feature": "Feature", "user-story": "User Story"}


def all_fields(scope: str) -> list[str]:
    return SCALAR_FIELDS.get(scope, []) + LIST_FIELDS.get(scope, [])


def fetch_state(session, scope: str, node_id: str) -> Optional[dict]:
    """Return the editable fields (+ updatedAt) for a node, or None if absent."""
    label = LABELS.get(scope)
    if not label:
        return None
    fields = all_fields(scope)
    projections = ",\n        ".join(f"n.{f} AS {f}" for f in fields)
    row = session.run(
        f"""
        MATCH (n:{label} {{id: $id}})
        RETURN n.id AS id, n.updatedAt AS updatedAt{',' if projections else ''}
        {projections}
        """,
        id=node_id,
    ).single()
    if not row:
        return None
    state: dict = {"id": row["id"], "updatedAt": _ts(row["updatedAt"])}
    for f in SCALAR_FIELDS.get(scope, []):
        state[f] = row[f] or ""
    for f in LIST_FIELDS.get(scope, []):
        state[f] = list(row[f] or [])
    return state


def apply_edits(session, scope: str, node_id: str, fields: dict) -> tuple[dict, Optional[str]]:
    """SET the provided fields, return (changes_diff, updatedAt).

    changes_diff = {field: {before, after}} for fields that actually changed.
    Only known editable fields are written; unknown keys are ignored.
    """
    label = LABELS[scope]
    before = fetch_state(session, scope, node_id) or {}
    sets, params = [], {"id": node_id}
    diff: dict = {}
    for f in all_fields(scope):
        if f not in fields:
            continue
        new = fields[f]
        if f in LIST_FIELDS.get(scope, []):
            new = [str(x) for x in (new or [])]
        else:
            new = "" if new is None else str(new)
        if before.get(f) == new:
            continue
        sets.append(f"n.{f} = ${f}")
        params[f] = new
        diff[f] = {"before": before.get(f), "after": new}
    # Keep the Epic's displayName in step with its name (matches create path).
    if scope == "epic" and "name" in diff:
        sets.append("n.displayName = $name")
    if not sets:
        return {}, before.get("updatedAt")
    sets.append("n.updatedAt = datetime()")
    row = session.run(
        f"MATCH (n:{label} {{id: $id}}) SET {', '.join(sets)} RETURN n.updatedAt AS updatedAt",
        **params,
    ).single()
    return diff, _ts(row["updatedAt"]) if row else None


def _ts(value) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
