"""User-story edit service — single mutation path for clarification apply (030).

Wraps a `UserStory` partial-update with:
 - optimistic concurrency via `baseUpdatedAt` (rejects on drift)
 - no-op detection (skip the write when the proposed `after` equals the
   current snapshot)
 - a uniform `EditResult` for the caller

This consolidates the read-modify-write the clarification `/apply` and
`/revert` paths need, so the only thing the routes do is build the desired
`after` and let this service handle persistence + reporting.

Apply is intentionally scoped to the `UserStory` fields the clarification
flow can mutate: `role`, `action`, `benefit`, `priority`, `status`,
`acceptanceCriteria`. Other relationships (BC/feature assignment, command
linkage) are out of scope here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import json

from api.features.requirements.clarification_contracts import UserStorySnapshot
from api.platform.identity.models import Actor
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger


class EditConflictError(Exception):
    """Raised when the live `updatedAt` no longer matches `baseUpdatedAt`."""

    def __init__(self, requirement_id: str, latest_updated_at: Optional[str]):
        super().__init__(
            f"edit conflict on {requirement_id}: latest={latest_updated_at}"
        )
        self.requirement_id = requirement_id
        self.latest_updated_at = latest_updated_at


@dataclass
class UserStoryEdit:
    """Caller-supplied edit intent."""

    requirement_id: str
    after: UserStorySnapshot
    base_updated_at: Optional[str] = None
    actor: Optional[Actor] = None


@dataclass
class FetchedSnapshot:
    requirement_id: str
    snapshot: UserStorySnapshot
    updated_at: Optional[str]


@dataclass
class EditResult:
    requirement_id: str
    changed: bool
    after_snapshot: UserStorySnapshot
    updated_at: str


def _row_to_snapshot(row: dict) -> UserStorySnapshot:
    return UserStorySnapshot(
        role=row.get("role") or "",
        action=row.get("action") or "",
        benefit=row.get("benefit") or "",
        priority=row.get("priority") or "medium",
        status=row.get("status") or "draft",
        acceptanceCriteria=[
            s for s in (row.get("acceptanceCriteria") or []) if s
        ],
    )


def _updated_at_str(value) -> Optional[str]:
    """neo4j returns DateTime objects; coerce to ISO string for diffing."""
    if value is None:
        return None
    try:
        # neo4j.time.DateTime supports `.iso_format()` / `to_native()`.
        if hasattr(value, "iso_format"):
            return value.iso_format()
        if hasattr(value, "to_native"):
            return value.to_native().isoformat()
    except Exception:  # noqa: BLE001
        pass
    return str(value)


def fetch_user_story_snapshot(requirement_id: str) -> Optional[FetchedSnapshot]:
    """Read the live snapshot + `updatedAt` for a UserStory."""
    query = """
    MATCH (us:UserStory {id: $id})
    RETURN us.role AS role,
           us.action AS action,
           us.benefit AS benefit,
           us.priority AS priority,
           us.status AS status,
           coalesce(us.acceptanceCriteria, []) AS acceptanceCriteria,
           us.updatedAt AS updatedAt
    """
    with get_session() as session:
        row = session.run(query, id=requirement_id).single()
    if row is None:
        return None
    data = dict(row)
    return FetchedSnapshot(
        requirement_id=requirement_id,
        snapshot=_row_to_snapshot(data),
        updated_at=_updated_at_str(data.get("updatedAt")),
    )


def apply_user_story_edit(edit: UserStoryEdit) -> EditResult:
    """Apply the edit to the graph after the concurrency + no-op checks.

    Raises `EditConflictError` when `base_updated_at` was supplied and no
    longer matches the live `updatedAt` on the node.
    """
    current = fetch_user_story_snapshot(edit.requirement_id)
    if current is None:
        raise EditConflictError(edit.requirement_id, latest_updated_at=None)

    if edit.base_updated_at is not None and current.updated_at not in (
        None,
        edit.base_updated_at,
    ):
        raise EditConflictError(
            edit.requirement_id, latest_updated_at=current.updated_at
        )

    if current.snapshot == edit.after:
        # No-op: skip the write but still return the live updatedAt.
        return EditResult(
            requirement_id=edit.requirement_id,
            changed=False,
            after_snapshot=current.snapshot,
            updated_at=current.updated_at or _now_iso(),
        )

    after = edit.after
    changes = _compute_diff(current.snapshot, after)
    actor = edit.actor
    query = """
    MATCH (us:UserStory {id: $id})
    SET us.role = $role,
        us.action = $action,
        us.benefit = $benefit,
        us.priority = $priority,
        us.status = $status,
        us.acceptanceCriteria = $acceptanceCriteria,
        us.criteriaUserEdited = CASE
            WHEN size($acceptanceCriteria) > 0 OR coalesce(us.criteriaUserEdited, false)
            THEN true ELSE false END,
        us.criteriaEditedAt = CASE
            WHEN size($acceptanceCriteria) > 0 THEN datetime() ELSE us.criteriaEditedAt END,
        us.updatedAt = datetime()
    WITH us
    CREATE (h:EditHistory {
        id: randomUUID(),
        timestamp: datetime(),
        userName: $user_name,
        userEmail: $user_email,
        changes: $changes_json
    })
    CREATE (us)-[:HAS_HISTORY]->(h)
    RETURN us.updatedAt AS updatedAt
    """
    with get_session() as session:
        row = session.run(
            query,
            id=edit.requirement_id,
            role=after.role,
            action=after.action,
            benefit=after.benefit,
            priority=after.priority or "medium",
            status=after.status or "draft",
            acceptanceCriteria=list(after.acceptanceCriteria or []),
            user_name=actor.name if actor else "unknown",
            user_email=actor.email if actor else "unknown",
            changes_json=json.dumps(changes, ensure_ascii=False),
        ).single()

    updated_at = _updated_at_str(row["updatedAt"]) if row else _now_iso()

    SmartLogger.log(
        "INFO",
        "User story edit applied via clarification.",
        category="requirements.clarification.edit_applied",
        params={
            "requirement_id": edit.requirement_id,
            "criteria_count": len(after.acceptanceCriteria or []),
        },
    )
    return EditResult(
        requirement_id=edit.requirement_id,
        changed=True,
        after_snapshot=after,
        updated_at=updated_at or _now_iso(),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_diff(before: UserStorySnapshot, after: UserStorySnapshot) -> dict:
    """Return only the changed scalar fields as {field: {before, after}}."""
    diff: dict = {}
    for field in ("role", "action", "benefit", "priority", "status"):
        b = getattr(before, field, "")
        a = getattr(after, field, "")
        if b != a:
            diff[field] = {"before": b, "after": a}
    return diff
