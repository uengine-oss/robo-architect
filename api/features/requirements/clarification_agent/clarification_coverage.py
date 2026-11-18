"""Per-scope coverage (030 — clarity radar fidelity; D-4 ① 영속화).

The deep agent's `submit_clarification_questions` tool returns a `coverage`
list with `CoverageStatus` (Clear / Resolved / Deferred / Outstanding) per
category — the SpecKit `/speckit-clarify` skill's step-8 reporting model.

We keep the most-recent coverage per scope so the clarity radar can score
categories with the skill's intended 4-state weighting (Clear/Resolved=1.0,
Deferred=0.5, Outstanding=0.0) instead of the cruder "any flagged?" binary.

**영속(D-4 ①).** 예전에는 메모리 캐시뿐이라 백엔드가 새로 뜨면(lite 는 앱을 켤 때마다)
coverage 가 사라졌다. 이제 **스코프 노드 속성** `clarificationCoverage` 에 JSON 으로 쓴다:

  bounded_context → (:BoundedContext {id}).clarificationCoverage
  feature         → (:Feature {id}).clarificationCoverage
  user_story      → (:UserStory {id}).clarificationCoverage
  project · 미분류 Feature(`__unassigned__…`) — 붙일 노드가 없다 →
                    (:ClarificationCoverage {id: "<scopeType>:<scopeId>"}).coverage

JSON 모양: `{"sessionId", "capturedAt", "rows": {"<category>": "<status>"}}`.

- 그래프가 진실이다 — 읽기는 매번 그래프에서(프로젝트마다 그래프 DB 가 갈린다).
- 그래프에 못 닿으면 메모리(`_COVERAGE`)로 동작한다(DB 미기동 · 단위 시험).
- Cypher 는 `MATCH {id}` · `MERGE {id}` · `SET prop = $json` 만 쓴다(Ontological 호환).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from api.features.requirements.clarification_contracts import (
    AmbiguityCategory,
    CoverageRow,
    CoverageStatus,
)
from api.platform.observability.smart_logger import SmartLogger

COVERAGE_PROPERTY = "clarificationCoverage"
COVERAGE_META_LABEL = "ClarificationCoverage"

# 스코프 → 붙일 노드 라벨. 여기 없는 스코프(project)는 메타 노드에 둔다.
_SCOPE_LABEL = {
    "bounded_context": "BoundedContext",
    "feature": "Feature",
    "user_story": "UserStory",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ScopeCoverage:
    """The most-recent coverage map the agent produced for one scope."""

    scopeType: str
    scopeId: str
    sessionId: str
    rows: dict[AmbiguityCategory, CoverageStatus] = field(default_factory=dict)
    capturedAt: str = field(default_factory=_utcnow)

    def merge_row(self, row: CoverageRow) -> None:
        """Upgrade-only merge: never *downgrade* a category to Outstanding
        once it has been Resolved. The skill's model treats Resolved as
        sticky for the current scope until a re-scan finds new gaps."""
        prev = self.rows.get(row.category)
        if prev == CoverageStatus.resolved and row.status in (
            CoverageStatus.outstanding,
            CoverageStatus.deferred,
        ):
            return
        self.rows[row.category] = row.status

    def to_json(self) -> str:
        return json.dumps(
            {
                "sessionId": self.sessionId,
                "capturedAt": self.capturedAt,
                "rows": {c.value: s.value for c, s in self.rows.items()},
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, scope_type: str, scope_id: str, raw) -> Optional["ScopeCoverage"]:
        if raw is None or raw == "":
            return None
        try:
            data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        rows: dict[AmbiguityCategory, CoverageStatus] = {}
        for c, s in (data.get("rows") or {}).items():
            try:
                rows[AmbiguityCategory(c)] = CoverageStatus(s)
            except (ValueError, TypeError):
                continue  # 모르는 카테고리/상태는 버린다(스키마가 바뀌어도 읽기는 산다)
        return cls(
            scopeType=scope_type,
            scopeId=scope_id,
            sessionId=str(data.get("sessionId") or ""),
            rows=rows,
            capturedAt=str(data.get("capturedAt") or _utcnow()),
        )


# Cache keyed by `{scopeType}:{scopeId}` — 그래프에 못 닿을 때의 저장소.
_COVERAGE: dict[str, ScopeCoverage] = {}
_LOCK = threading.Lock()


def _key(scope_type: str, scope_id: str) -> str:
    return f"{scope_type}:{scope_id}"


def _node_label(scope_type: str, scope_id: str) -> Optional[str]:
    if str(scope_id or "").startswith("__unassigned__"):
        return None  # 미분류 Feature 는 합성 id — 노드가 없다
    return _SCOPE_LABEL.get(scope_type)


class GraphCoverageStore:
    def load(self, scope_type: str, scope_id: str) -> Optional[ScopeCoverage]:
        from api.platform.neo4j import get_session

        label = _node_label(scope_type, scope_id)
        with get_session() as session:
            if label:
                rec = session.run(
                    f"MATCH (n:{label} {{id: $id}}) RETURN n.{COVERAGE_PROPERTY} AS raw",
                    id=scope_id,
                ).single()
            else:
                rec = session.run(
                    f"MATCH (n:{COVERAGE_META_LABEL} {{id: $id}}) RETURN n.coverage AS raw",
                    id=_key(scope_type, scope_id),
                ).single()
        return ScopeCoverage.from_json(scope_type, scope_id, rec["raw"] if rec else None)

    def save(self, cov: ScopeCoverage) -> None:
        from api.platform.neo4j import get_session

        label = _node_label(cov.scopeType, cov.scopeId)
        with get_session() as session:
            if label:
                session.run(
                    f"MATCH (n:{label} {{id: $id}}) SET n.{COVERAGE_PROPERTY} = $raw",
                    id=cov.scopeId,
                    raw=cov.to_json(),
                )
            else:
                session.run(
                    f"MERGE (n:{COVERAGE_META_LABEL} {{id: $id}}) SET n.coverage = $raw",
                    id=_key(cov.scopeType, cov.scopeId),
                    raw=cov.to_json(),
                )

    def clear(self, scope_type: str, scope_id: str) -> None:
        from api.platform.neo4j import get_session

        label = _node_label(scope_type, scope_id)
        with get_session() as session:
            if label:
                session.run(
                    f"MATCH (n:{label} {{id: $id}}) SET n.{COVERAGE_PROPERTY} = null",
                    id=scope_id,
                )
            else:
                session.run(
                    f"MATCH (n:{COVERAGE_META_LABEL} {{id: $id}}) SET n.coverage = null",
                    id=_key(scope_type, scope_id),
                )


_GRAPH: Optional[GraphCoverageStore] = GraphCoverageStore()

_MISSING = object()


def _try_graph(op: str, fn: Callable[[], object]):
    """그래프 호출 — 실패하면 `_MISSING`(메모리로 간다). 실패는 WARN 으로 남긴다."""
    if _GRAPH is None:
        return _MISSING
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — DB 없음 · 일시 장애는 메모리로 버틴다
        SmartLogger.log(
            "WARN",
            f"Clarification coverage {op} on graph failed; using in-memory cache.",
            category="requirements.clarification.coverage_persist",
            params={"op": op, "error": str(exc)[:200]},
        )
        return _MISSING


def _load(scope_type: str, scope_id: str) -> Optional[ScopeCoverage]:
    got = _try_graph("load", lambda: _GRAPH.load(scope_type, scope_id))  # type: ignore[union-attr]
    if got is _MISSING:
        return _COVERAGE.get(_key(scope_type, scope_id))
    return got  # type: ignore[return-value]


def _save(cov: ScopeCoverage) -> None:
    _COVERAGE[_key(cov.scopeType, cov.scopeId)] = cov
    _try_graph("save", lambda: _GRAPH.save(cov))  # type: ignore[union-attr]


def record_coverage(
    *,
    session_id: str,
    scope_type: str,
    scope_id: str,
    rows: list[CoverageRow],
) -> None:
    """Store the agent's coverage result for a scope.

    "Resolved" is sticky across sessions for the same scope (SKILL.md
    step 8 — `Resolved = was Partial/Missing and addressed`; a follow-up
    scan that re-detects Outstanding doesn't unmake the past resolution).
    Other statuses are overwritten by the most recent scan.
    """
    if not rows:
        return
    with _LOCK:
        prev = _load(scope_type, scope_id)
        # Preserve sticky Resolved entries when starting a fresh session
        # entry for this scope.
        carryover: dict[AmbiguityCategory, CoverageStatus] = {}
        if prev is not None:
            carryover = {
                c: s for c, s in prev.rows.items() if s == CoverageStatus.resolved
            }
        if prev is None or prev.sessionId != session_id:
            prev = ScopeCoverage(
                scopeType=scope_type, scopeId=scope_id, sessionId=session_id
            )
            # Re-seed with the sticky resolves from previous sessions.
            prev.rows.update(carryover)
        for row in rows:
            prev.merge_row(row)
        prev.capturedAt = _utcnow()
        _save(prev)


def get_coverage(scope_type: str, scope_id: str) -> Optional[ScopeCoverage]:
    with _LOCK:
        return _load(scope_type, scope_id)


def mark_resolved(scope_type: str, scope_id: str, category: AmbiguityCategory) -> None:
    """Upgrade a category to Resolved after a successful `/apply` — sticky."""
    with _LOCK:
        cov = _load(scope_type, scope_id)
        if cov is None:
            return
        cov.rows[category] = CoverageStatus.resolved
        cov.capturedAt = _utcnow()
        _save(cov)


def clear_scope(scope_type: str, scope_id: str) -> None:
    with _LOCK:
        _COVERAGE.pop(_key(scope_type, scope_id), None)
        _try_graph("clear", lambda: _GRAPH.clear(scope_type, scope_id))  # type: ignore[union-attr]
