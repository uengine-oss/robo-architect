"""Per-UserStory clarification flags (030 — review-loop UX; D-4 ① 영속화).

When a deep-agent scan flags a UserStory as ambiguous, we record that fact
here so the Requirements tree can render a badge ("이 요구사항은 명확화가
필요합니다"). When the user applies the encoded edit (or reverts), the
flag clears for that UserStory.

**영속(D-4 ①).** 예전에는 메모리뿐이라 lite(앱을 켤 때마다 백엔드가 새로 뜬다)에서
스캔 결과가 매번 사라졌고, 레이더가 100% 로 돌아갔다. 이제 플래그를
`UserStory.clarificationFlag`(FlagInfo 의 JSON 문자열) 속성에 쓴다 —
`UserStory.clarifications`(clarification_log) 와 같은 "UserStory 속성 JSON" 패턴이다.

- **그래프가 진실이다.** 읽기는 매번 그래프에서 한다 — 그래프 DB 는 프로젝트마다
  갈리므로(X-Project-Graph) 프로세스 전역 캐시를 믿으면 다른 프로젝트의 플래그가 섞인다.
- 그래프에 못 닿으면(DB 미기동 · 단위 시험) 메모리(`_FLAGS`)로 동작한다 — 예전 동작.
- Cypher 는 `MATCH … {id}` / `SET prop = $json` / `SET prop = null` 만 쓴다
  (Neo4j · Ontological DB 양쪽에서 같은 뜻).

Operations:
 - `record_flags(session_id, scope, user_story_ids)` — called when a scan
   surfaces ambiguity for a set of user-story ids.
 - `clear_flag(user_story_id)` — called after `/apply` or `/revert`.
 - `snapshot()` — returns `{user_story_id: FlagInfo}` for the frontend.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from api.platform.observability.smart_logger import SmartLogger

FLAG_PROPERTY = "clarificationFlag"


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
        if question_id and question_id not in self.questionIds:
            self.questionIds.append(question_id)
        if category and category not in self.categories:
            self.categories.append(category)

    def to_json(self) -> str:
        payload = {k: v for k, v in asdict(self).items() if k != "userStoryId"}
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, us_id: str, raw) -> Optional["FlagInfo"]:
        if raw is None or raw == "":
            return None
        try:
            data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        return cls(
            userStoryId=us_id,
            sessionId=str(data.get("sessionId") or ""),
            questionIds=list(data.get("questionIds") or []),
            categories=list(data.get("categories") or []),
            scopeType=str(data.get("scopeType") or "user_story"),
            scopeId=data.get("scopeId"),
            flaggedAt=str(data.get("flaggedAt") or _utcnow()),
        )


_FLAGS: dict[str, FlagInfo] = {}
_LOCK = threading.Lock()


# ── 그래프 저장소 ────────────────────────────────────────────────────────
# 시험이 갈아 끼울 수 있게 객체로 둔다. `_GRAPH = None` 이면 메모리만 쓴다.


class GraphFlagStore:
    def load_all(self) -> dict[str, FlagInfo]:
        from api.platform.neo4j import get_session

        out: dict[str, FlagInfo] = {}
        with get_session() as session:
            for rec in session.run(
                f"MATCH (us:UserStory) WHERE us.{FLAG_PROPERTY} IS NOT NULL "
                f"RETURN us.id AS id, us.{FLAG_PROPERTY} AS raw"
            ):
                info = FlagInfo.from_json(rec["id"], rec["raw"])
                if info is not None:
                    out[rec["id"]] = info
        return out

    def write(self, infos: list[FlagInfo]) -> None:
        from api.platform.neo4j import get_session

        with get_session() as session:
            for info in infos:
                session.run(
                    f"MATCH (us:UserStory {{id: $id}}) SET us.{FLAG_PROPERTY} = $raw",
                    id=info.userStoryId,
                    raw=info.to_json(),
                )

    def clear(self, user_story_ids: list[str]) -> None:
        from api.platform.neo4j import get_session

        with get_session() as session:
            for us_id in user_story_ids:
                session.run(
                    f"MATCH (us:UserStory {{id: $id}}) SET us.{FLAG_PROPERTY} = null",
                    id=us_id,
                )


_GRAPH: Optional[GraphFlagStore] = GraphFlagStore()


def _try_graph(op: str, fn: Callable[[], object]):
    """그래프 호출 — 실패하면 None(메모리로 간다). 실패는 WARN 으로 남긴다."""
    if _GRAPH is None:
        return None
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — DB 없음 · 일시 장애는 메모리로 버틴다
        SmartLogger.log(
            "WARN",
            f"Clarification flag {op} on graph failed; using in-memory flags.",
            category="requirements.clarification.flags_persist",
            params={"op": op, "error": str(exc)[:200]},
        )
        return None


def _current() -> dict[str, FlagInfo]:
    """지금 플래그 — 그래프가 되면 그래프, 아니면 메모리."""
    loaded = _try_graph("load", lambda: _GRAPH.load_all())  # type: ignore[union-attr]
    if loaded is not None:
        return loaded  # type: ignore[return-value]
    return dict(_FLAGS)


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
        current = _current()
        touched: dict[str, FlagInfo] = {}
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
                existing = touched.get(us_id) or current.get(us_id)
                if existing and existing.sessionId == session_id:
                    existing.merge_question(qid, category or "")
                    touched[us_id] = existing
                    continue
                touched[us_id] = FlagInfo(
                    userStoryId=us_id,
                    sessionId=session_id,
                    questionIds=[qid] if qid else [],
                    categories=[category] if category else [],
                    scopeType=scope_type,
                    scopeId=scope_id,
                )
        if not touched:
            return
        _FLAGS.update(touched)
        infos = list(touched.values())
        _try_graph("write", lambda: _GRAPH.write(infos))  # type: ignore[union-attr]


def clear_flag(user_story_id: str) -> None:
    """Drop the pending-clarification marker for one UserStory."""
    with _LOCK:
        _FLAGS.pop(user_story_id, None)
        _try_graph("clear", lambda: _GRAPH.clear([user_story_id]))  # type: ignore[union-attr]


def clear_session_flags(session_id: str) -> None:
    """Drop all flags belonging to a given session (e.g. on /discard)."""
    with _LOCK:
        current = _current()
        ids = {u for u, f in current.items() if f.sessionId == session_id}
        ids |= {u for u, f in _FLAGS.items() if f.sessionId == session_id}
        for us_id in ids:
            _FLAGS.pop(us_id, None)
        if ids:
            _try_graph("clear", lambda: _GRAPH.clear(sorted(ids)))  # type: ignore[union-attr]


def snapshot() -> dict[str, FlagInfo]:
    """Return the current pending-clarification flag map (graph first)."""
    with _LOCK:
        return _current()
