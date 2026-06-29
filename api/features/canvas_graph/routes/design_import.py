"""044 완성 설계 Import 라우트 (Design 탭 진입점).

POST /api/graph/design-import/preview  — 파싱만, 개수·경고 미리보기(그래프 무변경)
POST /api/graph/design-import/apply    — 파싱 + 적재(mode=replace|merge)
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.requests import Request

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger
from api.features.canvas_graph.design_import.parser import parse_design_markdown
from api.features.canvas_graph.design_import.importer import count_model, import_model

router = APIRouter()


async def _read_content(file: Optional[UploadFile], text: Optional[str]) -> str:
    if file is not None:
        raw = await file.read()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1")
    if text:
        return text
    raise HTTPException(status_code=400, detail="Either 'file' or 'text' must be provided")


@router.post("/design-import/preview")
async def design_import_preview(
    request: Request,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    mode: str = Form("replace"),
) -> dict[str, Any]:
    """완성 설계 문서를 파싱해 적재 미리보기(개수·경고·교체 영향)를 반환. 그래프 무변경."""
    content = await _read_content(file, text)
    model = parse_design_markdown(content)
    counts = count_model(model)
    existing: dict = {}
    if (mode or "replace") == "replace":
        with get_session() as session:
            r = session.run("MATCH (n:BoundedContext) RETURN count(n) AS c").single()
            if r and r["c"]:
                existing["boundedContextsRemoved"] = r["c"]
    SmartLogger.log(
        "INFO", "Design import preview",
        category="design_import.preview",
        params={**http_context(request), "counts": counts, "mode": mode,
                "warnings": len(model.get("warnings", []))},
    )
    return {
        "mode": mode,
        "counts": counts,
        "warnings": model.get("warnings", []),
        "replaceImpact": existing,
        "boundedContexts": [
            {"name": bc["name"], "display": bc.get("display"),
             "aggregates": len(bc.get("aggregates", [])),
             "commands": len(bc.get("commands", [])),
             "events": sum(len(c.get("emits", [])) for c in bc.get("commands", [])),
             "policies": len(bc.get("policies", [])),
             "readModels": len(bc.get("readModels", []))}
            for bc in model.get("boundedContexts", [])
        ],
    }


@router.post("/design-import/apply")
async def design_import_apply(
    request: Request,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    mode: str = Form("replace"),
) -> dict[str, Any]:
    """완성 설계 문서를 파싱해 그래프에 결정론적으로 적재한다."""
    resolved_mode = (mode or "replace").strip().lower()
    if resolved_mode not in ("replace", "merge"):
        resolved_mode = "replace"
    content = await _read_content(file, text)
    model = parse_design_markdown(content)
    if not model.get("boundedContexts"):
        raise HTTPException(status_code=422,
                            detail="인식 가능한 설계 요소가 없습니다(Bounded Context 표 미발견).")
    with get_session() as session:
        result = import_model(session, model, mode=resolved_mode)
    SmartLogger.log(
        "INFO", "Design import applied",
        category="design_import.apply",
        params={**http_context(request), "mode": resolved_mode,
                "counts": result.get("counts"), "applied": result.get("applied")},
    )
    return result
