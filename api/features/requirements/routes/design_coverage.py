"""설계 커버리지 검증·복구 엔드포인트 (034 — 인제스천 사후 검증).

핵심 로직은 `api/features/ingestion/workflow/post_coverage.py`(인제스천 사후 단계와
공유)에 있고, 여기서는 HTTP 표면 + Pydantic 매핑만 담당한다.
"""

from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from api.features.ingestion.workflow import post_coverage
from api.features.requirements.requirements_contracts import (
    CoverageBC,
    CoverageReport,
    ReconcileRequest,
    ReconcileResponse,
    ReconcileResult,
)
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


@router.get("/design-coverage", response_model=CoverageReport)
async def coverage_report(request: Request) -> CoverageReport:
    """BC별 고아 US(설계 누락) 집계 — 인제스천 사후 검증 체크리스트."""
    rows = post_coverage.coverage_report()
    bcs = [
        CoverageBC(
            boundedContextId=r["id"], name=r["name"] or "",
            totalUS=r["totalUS"] or 0, orphanUS=r["orphanUS"] or 0,
            orphanSample=[s for s in (r["sample"] or []) if s],
        )
        for r in rows
    ]
    total_orphan = sum(b.orphanUS for b in bcs)
    SmartLogger.log(
        "INFO", f"Design coverage: {total_orphan} orphan user stories.",
        category="requirements.design.coverage",
        params={**http_context(request), "totalOrphan": total_orphan},
    )
    return CoverageReport(bcs=bcs, totalOrphan=total_orphan)


@router.post("/design-coverage/reconcile", response_model=ReconcileResponse)
async def reconcile(req: ReconcileRequest, request: Request) -> ReconcileResponse:
    """고아 US를 기존 Command/ReadModel에 매핑·링크(복구). dryRun이면 집계만."""
    bc_ids = [req.boundedContextId] if req.boundedContextId else None
    summary = post_coverage.reconcile(bc_ids, dry_run=req.dryRun)
    results = [
        ReconcileResult(
            boundedContextId=r["boundedContextId"], name=r["name"],
            orphanBefore=r["orphanBefore"], linkedToCommand=r["linkedToCommand"],
            linkedToReadModel=r["linkedToReadModel"], unmapped=r["unmapped"], notes=r["notes"],
        )
        for r in summary["results"]
    ]
    SmartLogger.log(
        "INFO",
        f"Reconcile linked {summary['totalLinked']}, unmapped {summary['totalUnmapped']} (dryRun={req.dryRun}).",
        category="requirements.design.reconcile",
        params={**http_context(request), "linked": summary["totalLinked"], "unmapped": summary["totalUnmapped"]},
    )
    return ReconcileResponse(
        results=results, totalLinked=summary["totalLinked"], totalUnmapped=summary["totalUnmapped"]
    )
