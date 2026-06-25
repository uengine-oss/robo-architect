"""그래프 → .ddd 내보내기 (035 — US7, 보조 산출물).

진실의 원천=그래프. 현행 그래프 상태를 ddd-starter의 `.ddd/` 디렉터리 구조
(00-plan ~ 08-aggregates/)로 내보낸다. 사람이 편집 가능한 마크다운.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter
from starlette.requests import Request

from api.features.requirements.requirements_contracts import (
    DddExportRequest,
    DddExportResponse,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", (name or "untitled").strip().lower())
    return s.strip("-") or "untitled"


def _write(base: Path, rel: str, text: str, written: list[str]) -> None:
    target = base / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    written.append(rel)


@router.post("/ddd-export", response_model=DddExportResponse)
async def ddd_export(req: DddExportRequest, request: Request) -> DddExportResponse:
    base = Path(req.outputDir or ".ddd")
    steps = set(req.steps) if req.steps else None

    def want(step: str) -> bool:
        return steps is None or step in steps

    written: list[str] = []
    skipped: list[str] = []

    with get_session() as session:
        bcs = [
            dict(r)
            for r in session.run(
                """
                MATCH (bc:BoundedContext)
                RETURN bc.id AS id, coalesce(bc.displayName, bc.name) AS name,
                       bc.purpose AS purpose, bc.classification AS classification,
                       bc.ubiquitousLanguage AS ul, bc.businessDecisions AS bd
                ORDER BY name
                """
            )
        ]
        events = [
            dict(r)
            for r in session.run(
                """
                MATCH (e:Event)
                RETURN coalesce(e.displayName, e.name) AS name,
                       coalesce(e.sequence, 0) AS seq,
                       coalesce(e.pivotal, false) AS pivotal,
                       coalesce(e.hotspot, false) AS hotspot
                ORDER BY seq, name
                """
            )
        ]
        aggregates = [
            dict(r)
            for r in session.run(
                """
                MATCH (a:Aggregate)
                OPTIONAL MATCH (a)-[:HAS_COMMAND]->(c:Command)
                OPTIONAL MATCH (c)-[:EMITS]->(ev:Event)
                RETURN a.id AS id, coalesce(a.displayName, a.name) AS name,
                       a.description AS description, a.stateTransitions AS st,
                       a.invariants AS inv,
                       collect(DISTINCT coalesce(c.displayName, c.name)) AS commands,
                       collect(DISTINCT coalesce(ev.displayName, ev.name)) AS events
                """
            )
        ]

    if want("plan"):
        plan = ["# DDD 모델 (그래프 내보내기)", "",
                f"- Bounded Context: {len(bcs)}개",
                f"- Aggregate: {len(aggregates)}개",
                f"- Domain Event: {len(events)}개", ""]
        _write(base, "00-plan.md", "\n".join(plan), written)

    if want("discover"):
        es = ["# Big Picture EventStorm", ""]
        for e in events:
            mark = ""
            if e["pivotal"]:
                mark += " ⭐(pivotal)"
            if e["hotspot"]:
                mark += " 🔥(hotspot)"
            es.append(f"{e['seq']}. {e['name']}{mark}")
        if not events:
            es.append("_(이벤트 없음)_")
        _write(base, "02-event-storm.md", "\n".join(es), written)

    if want("strategize"):
        cd = ["# Core Domain Chart", "", "| Bounded Context | 분류 |", "|---|---|"]
        for bc in bcs:
            cd.append(f"| {bc['name']} | {bc['classification'] or '(미분류)'} |")
        _write(base, "04-core-domain-chart.md", "\n".join(cd), written)

    if want("define"):
        for bc in bcs:
            lines = [f"# Bounded Context Canvas — {bc['name']}", ""]
            lines.append(f"## Purpose\n{bc['purpose'] or '_(미정)_'}\n")
            lines.append(f"## Strategic Classification\n{bc['classification'] or '_(미분류)_'}\n")
            ul = bc.get("ul") or []
            lines.append("## Ubiquitous Language")
            lines += [f"- {t}" for t in ul] or ["_(없음)_"]
            bd = bc.get("bd") or []
            lines.append("\n## Business Decisions")
            lines += [f"- {d}" for d in bd] or ["_(없음)_"]
            _write(base, f"07-bounded-contexts/{_slug(bc['name'])}.md", "\n".join(lines), written)

    if want("code"):
        for a in aggregates:
            lines = [f"# Aggregate Design Canvas — {a['name']}", ""]
            lines.append(f"## Description\n{a['description'] or '_(미정)_'}\n")
            if a.get("st"):
                lines.append(f"## State Transitions\n```mermaid\n{a['st']}\n```\n")
            lines.append("## Handled Commands")
            lines += [f"- {c}" for c in (a.get("commands") or []) if c] or ["_(없음)_"]
            lines.append("\n## Created Events")
            lines += [f"- {e}" for e in (a.get("events") or []) if e] or ["_(없음)_"]
            inv = a.get("inv") or []
            lines.append("\n## Enforced Invariants")
            lines += [f"- {i}" for i in inv] or ["_(없음)_"]
            _write(base, f"08-aggregates/{_slug(a['name'])}.md", "\n".join(lines), written)

    SmartLogger.log(
        "INFO", f"Exported {len(written)} .ddd files.",
        category="requirements.ddd_export",
        params={**http_context(request), "count": len(written), "output_dir": str(base)},
    )
    return DddExportResponse(writtenFiles=written, skipped=skipped)
