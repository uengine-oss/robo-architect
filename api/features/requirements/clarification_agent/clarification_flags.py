"""In-memory per-UserStory clarification flags (030 — review-loop UX).

When a deep-agent scan flags a UserStory as ambiguous, we record that fact
here so the Requirements tree can render a badge ("이 요구사항은 명확화가
필요합니다"). When the user applies the encoded edit (or reverts), the
flag clears for that UserStory.

This is a *signal* layer, not a source of truth — same lifecycle as the
in-memory session store (`clarification_session._SESSIONS`). The persistent
audit trail lives on `UserStory.clarifications` (the JSON-encoded log).

Three operations:
 - `record_flags(session_id, scope, user_story_ids)` — called when a scan
   surfaces ambiguity for a set of user-story ids.
 - `clear_flag(user_story_id)` — called after `/apply` or `/revert`.
 - `snapshot()` — returns `{user_story_id: FlagInfo}` for the frontend.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FlagInfo:
    """A pending-clarification marker for one UserStory."""

    userStoryId: str
    sessionId: str
    questionIds: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    scopeType: str = "user_story"
    scopeId: Optional[str] = None
    flaggedAt: str = field(default_factory=_utcnow)

    def merge_question(self, question_id: str, category: str) -> None:
        if question_id not in self.questionIds:
            self.questionIds.append(question_id)
        if category and category not in self.categories:
            self.categories.append(category)


_FLAGS: dict[str, FlagInfo] = {}
_LOCK = threading.Lock()


def record_flags(
    *,
    session_id: str,
    scope_type: str,
    scope_id: str,
    questions: list,  # list[ClarificationQuestionDTO]
) -> None:
    """Mark every UserStory referenced by a freshly-produced question
    queue as needing clarification."""
    if not questions:
        return
    with _LOCK:
        for q in questions:
            is_dict = isinstance(q, dict)
            qid = (q.get("questionId") if is_dict else getattr(q, "questionId", None))
            raw_category = q.get("category") if is_dict else getattr(q, "category", None)
            category = (
                getattr(raw_category, "value", None) or str(raw_category)
                if raw_category is not None
                else None
            )
            ref_ids = (
                q.get("referencedRequirementIds")
                if is_dict
                else getattr(q, "referencedRequirementIds", None)
            ) or []
            for us_id in ref_ids or []:
                existing = _FLAGS.get(us_id)
                if existing and existing.sessionId == session_id:
                    existing.merge_question(qid, category or "")
                    continue
                _FLAGS[us_id] = FlagInfo(
                    userStoryId=us_id,
                    sessionId=session_id,
                    questionIds=[qid] if qid else [],
                    categories=[category] if category else [],
                    scopeType=scope_type,
                    scopeId=scope_id,
                )


def clear_flag(user_story_id: str) -> None:
    """Drop the pending-clarification marker for one UserStory."""
    with _LOCK:
        _FLAGS.pop(user_story_id, None)


def clear_session_flags(session_id: str) -> None:
    """Drop all flags belonging to a given session (e.g. on /discard)."""
    with _LOCK:
        for us_id in [u for u, f in _FLAGS.items() if f.sessionId == session_id]:
            _FLAGS.pop(us_id, None)


def snapshot() -> dict[str, FlagInfo]:
    """Return the current pending-clarification flag map."""
    with _LOCK:
        return dict(_FLAGS)
