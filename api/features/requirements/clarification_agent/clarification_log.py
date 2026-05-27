"""Clarification log persistence (030 — FR-009 / FR-014).

Stores `ClarificationLogEntry`s as a JSON-encoded list on the
`UserStory.clarifications` property — no new node label, same provenance
pattern as the existing `criteriaUserEdited`/`criteriaEditedAt` fields
(data-model.md §1.1, research R5).

Three operations:
 - `append_log_entry(user_story_id, entry)` — `/apply` writes here.
 - `mark_log_entries_reverted(user_story_id, *, session_id)` — `/revert`
   flags the affected entries so the audit trail records the rollback.
 - `read_scope_log(user_story_ids)` — `/log` aggregates across the scope
   in chronological order.
"""

from __future__ import annotations

import json
from typing import Iterable, Optional

from api.features.requirements.clarification_contracts import ClarificationLogEntry
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger


def _load_entries(raw) -> list[dict]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return list(raw)
    try:
        data = json.loads(raw)
        return list(data) if isinstance(data, list) else []
    except (TypeError, ValueError):
        return []


def append_log_entry(user_story_id: str, entry: ClarificationLogEntry) -> None:
    """Read the JSON array, append the entry, write it back atomically."""
    payload = entry.model_dump(mode="json")
    query = """
    MATCH (us:UserStory {id: $id})
    WITH us, coalesce(us.clarifications, '[]') AS raw
    WITH us, CASE WHEN raw = '' THEN '[]' ELSE raw END AS raw
    RETURN raw
    """
    with get_session() as session:
        rec = session.run(query, id=user_story_id).single()
        if rec is None:
            SmartLogger.log(
                "WARN",
                "Cannot append clarification log: user story not found.",
                category="requirements.clarification.log_append_missing",
                params={"user_story_id": user_story_id},
            )
            return
        entries = _load_entries(rec["raw"])
        entries.append(payload)
        session.run(
            """
            MATCH (us:UserStory {id: $id})
            SET us.clarifications = $payload
            """,
            id=user_story_id,
            payload=json.dumps(entries, ensure_ascii=False),
        )


def mark_log_entries_reverted(
    user_story_id: str, *, session_id: str
) -> None:
    """Flag every entry on a user story that came from this session as reverted."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    query = """
    MATCH (us:UserStory {id: $id})
    RETURN coalesce(us.clarifications, '[]') AS raw
    """
    with get_session() as session:
        rec = session.run(query, id=user_story_id).single()
        if rec is None:
            return
        entries = _load_entries(rec["raw"])
        for e in entries:
            if e.get("sessionId") == session_id and not e.get("reverted"):
                e["reverted"] = True
                e["revertedAt"] = now
        session.run(
            """
            MATCH (us:UserStory {id: $id})
            SET us.clarifications = $payload
            """,
            id=user_story_id,
            payload=json.dumps(entries, ensure_ascii=False),
        )


def read_scope_log(
    user_story_ids: Iterable[str],
) -> list[ClarificationLogEntry]:
    """Aggregate clarification entries across a scope, sorted by `at`."""
    ids = [i for i in user_story_ids if i]
    if not ids:
        return []
    query = """
    UNWIND $ids AS id
    MATCH (us:UserStory {id: id})
    RETURN us.id AS userStoryId, coalesce(us.clarifications, '[]') AS raw
    """
    flat: list[ClarificationLogEntry] = []
    with get_session() as session:
        for rec in session.run(query, ids=ids):
            for raw_entry in _load_entries(rec["raw"]):
                try:
                    flat.append(ClarificationLogEntry.model_validate(raw_entry))
                except Exception as exc:  # noqa: BLE001
                    SmartLogger.log(
                        "WARN",
                        f"Skipping malformed clarification log entry: {exc}",
                        category="requirements.clarification.log_read_malformed",
                        params={"user_story_id": rec["userStoryId"], "error": str(exc)},
                    )
                    continue
    flat.sort(key=lambda e: e.at or "")
    return flat


def _placeholder() -> Optional[str]:  # pragma: no cover — unused marker
    return None
