"""Background impact analysis for requirement mutations (026 — requirements-tab).

When a User Story / Feature is added, moved, or deleted, the requirements
routes register an impact report and kick this analysis off as a background
task. It never blocks the mutation response (research R7 / FR-019).

The analysis reuses the change-management impact traversal (spec 004) for
design impact, plus a lightweight token-overlap heuristic for duplicate
detection against existing User Stories.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from api.features.requirements.requirements_contracts import ImpactFinding, ImpactReportDTO
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

# In-memory report store. Reports are short-lived advisory artifacts; the
# graph remains the source of truth, so a process-local store is sufficient.
_REPORTS: dict[str, ImpactReportDTO] = {}

_WORD_RE = re.compile(r"[0-9a-z가-힣]+")


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall((text or "").lower()) if len(t) > 1}


def create_report(trigger: str) -> str:
    """Register a fresh 'running' report and return its id."""
    report_id = str(uuid.uuid4())
    _REPORTS[report_id] = ImpactReportDTO(
        id=report_id,
        status="running",
        trigger=trigger,  # type: ignore[arg-type]
        findings=[],
        createdAt=datetime.now(timezone.utc).isoformat(),
    )
    return report_id


def get_report(report_id: str) -> Optional[ImpactReportDTO]:
    return _REPORTS.get(report_id)


def _design_impact(user_story_id: str) -> list[str]:
    """Impacted design node ids reachable from a User Story (spec 004 traversal)."""
    query = """
    MATCH (us:UserStory {id: $id})
    OPTIONAL MATCH (us)-[:IMPLEMENTS]->(cmd:Command)
    OPTIONAL MATCH (agg:Aggregate)-[:HAS_COMMAND]->(cmd)
    OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
    OPTIONAL MATCH (evt)-[:TRIGGERS]->(pol:Policy)
    WITH collect(DISTINCT cmd.id) + collect(DISTINCT agg.id)
       + collect(DISTINCT evt.id) + collect(DISTINCT pol.id) AS ids
    RETURN [x IN ids WHERE x IS NOT NULL] AS impacted
    """
    with get_session() as session:
        rec = session.run(query, id=user_story_id).single()
        return list(rec["impacted"]) if rec and rec["impacted"] else []


def _duplicate_findings(user_story_id: str) -> list[ImpactFinding]:
    """Flag existing User Stories with strongly overlapping action text."""
    with get_session() as session:
        target = session.run(
            "MATCH (us:UserStory {id: $id}) RETURN us.role AS role, us.action AS action",
            id=user_story_id,
        ).single()
        if not target:
            return []
        others = list(
            session.run(
                """
                MATCH (us:UserStory) WHERE us.id <> $id
                RETURN us.id AS id, us.role AS role, us.action AS action
                """,
                id=user_story_id,
            )
        )

    target_tokens = _tokens(target["action"])
    if not target_tokens:
        return []

    findings: list[ImpactFinding] = []
    for other in others:
        other_tokens = _tokens(other["action"])
        if not other_tokens:
            continue
        overlap = len(target_tokens & other_tokens)
        union = len(target_tokens | other_tokens)
        if union and (overlap / union) >= 0.6:
            findings.append(
                ImpactFinding(
                    kind="duplicate",
                    severity="warning",
                    message=(
                        f"기존 User Story와 중복 가능성: "
                        f"\"{other['role']}: {other['action']}\""
                    ),
                    relatedNodeIds=[other["id"]],
                )
            )
    return findings


def run_impact_analysis(
    report_id: str,
    *,
    trigger: str,
    user_story_id: Optional[str] = None,
) -> None:
    """Compute findings for a registered report. Safe to run as a background task."""
    report = _REPORTS.get(report_id)
    if report is None:
        return
    try:
        findings: list[ImpactFinding] = []
        if user_story_id:
            if trigger == "add":
                findings.extend(_duplicate_findings(user_story_id))
            impacted = _design_impact(user_story_id) if trigger != "add" else []
            if impacted:
                findings.append(
                    ImpactFinding(
                        kind="design_impact",
                        severity="warning",
                        message=(
                            f"이 변경은 {len(impacted)}개의 설계 요소에 영향을 줍니다."
                        ),
                        relatedNodeIds=impacted,
                    )
                )
        report.findings = findings
        report.status = "done"
        SmartLogger.log(
            "INFO",
            f"Impact analysis done: {len(findings)} findings",
            category="requirements.impact.done",
            params={"report_id": report_id, "trigger": trigger, "findings": len(findings)},
        )
    except Exception as exc:  # noqa: BLE001 — advisory analysis must not crash
        report.status = "failed"
        SmartLogger.log(
            "ERROR",
            f"Impact analysis failed: {exc}",
            category="requirements.impact.error",
            params={"report_id": report_id, "error": str(exc)},
        )
