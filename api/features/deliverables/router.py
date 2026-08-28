"""Session 단위 설계 산출물 조회 API.

`GET /api/deliverables/architecture-document?sessionId={id}`

기존 내보내기는 `/api/contexts` 전역을 읽어 같은 Neo4j 에 남은 다른 세션의
결과까지 한 문서에 섞었다. 납품 문서의 재현성과 감사 가능성을 위해, 산출물은
반드시 하나의 Ingestion 세션 범위로 고정한다.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from starlette.requests import Request

from api.features.deliverables.aggregate_export import build_aggregate_payloads
from api.features.deliverables.docx_normalize import (
    DOCX_MIME,
    DocxNormalizeFailed,
    DocxNormalizeUnavailable,
    compare_documents,
    inspect_docx_package,
    normalize_docx,
    soffice_binary,
)
from api.features.deliverables.architecture_document import (
    build_architecture_document,
    fetch_session_trees,
    list_sessions,
)
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/deliverables", tags=["deliverables"])


@router.get("/sessions")
async def get_sessions(request: Request) -> dict:
    """산출물을 뽑을 수 있는 Ingestion 세션 목록.

    내보내기 화면이 세션을 고를 수 있게 한다. 이 목록이 없으면 브라우저
    localStorage 에 남은 세션 하나에만 접근할 수 있어, 지난 세션의 산출물을 다시
    뽑을 수 없다(Electron 은 origin 이 달라 그 값조차 공유되지 않는다).
    """
    sessions = list_sessions()
    SmartLogger.log(
        "INFO",
        "Deliverable sessions listed.",
        category="deliverables.sessions.listed",
        params={**http_context(request), "count": len(sessions)},
    )
    return {"sessions": sessions}


@router.get("/architecture-document")
async def get_architecture_document(request: Request, sessionId: str = Query(..., min_length=1)) -> dict:
    doc = build_architecture_document(sessionId)
    if doc is None:
        SmartLogger.log(
            "WARN",
            "Architecture document requested for a session with no BoundedContext.",
            category="deliverables.architecture_document.not_found",
            params={**http_context(request), "session_id": sessionId},
        )
        raise HTTPException(
            status_code=404,
            detail=f"세션 '{sessionId}' 에 Bounded Context 가 없습니다. 이벤트 스토밍 승격이 끝났는지 확인하세요.",
        )

    trace = doc["traceabilityMatrix"]["summary"]
    SmartLogger.log(
        "INFO",
        "Architecture document snapshot built.",
        category="deliverables.architecture_document.built",
        params={
            **http_context(request),
            "session_id": sessionId,
            "bounded_contexts": len(doc["boundedContexts"]),
            "processes": doc["projectInfo"]["processCount"],
            "user_stories": doc["userScenario"]["summary"]["total"],
            "trace_direct": trace["directElements"],
            "trace_inferred": trace["inferredElements"],
            "trace_unmapped": trace["unmappedElements"],
        },
    )
    return doc


@router.get("/aggregates")
async def get_aggregate_export(request: Request, sessionId: str = Query(..., min_length=1)) -> dict:
    """Aggregate 구조를 코드 생성기 호환 JSON 으로 반환한다.

    기준 기능: `local-msaez` CodeGenerator 의 "Export Aggregates". 산출물 문서
    전체가 필요 없는 소비자(코드 생성기·외부 도구)를 위해 별도 경로로 둔다.
    """
    trees = fetch_session_trees(sessionId)
    if not trees:
        raise HTTPException(
            status_code=404,
            detail=f"세션 '{sessionId}' 에 Bounded Context 가 없습니다. 이벤트 스토밍 승격이 끝났는지 확인하세요.",
        )

    payload = build_aggregate_payloads(trees)
    SmartLogger.log(
        "INFO",
        "Aggregate export built.",
        category="deliverables.aggregate_export.built",
        params={**http_context(request), "session_id": sessionId, **payload["summary"]},
    )
    return payload


# ---------------------------------------------------------------------------
# DOCX 정본화 / ECM 호환 검증
# ---------------------------------------------------------------------------


@router.get("/docx-normalization/status")
async def get_docx_normalization_status() -> dict:
    """정본화 가능 여부를 보고한다.

    프런트엔드가 "정본화 없이 원본을 내려받을지"를 사전에 안내할 수 있도록,
    실제 변환을 시도하기 전에 확인할 수 있는 경로를 둔다.
    """
    binary = soffice_binary()
    return {
        "available": binary is not None,
        "binary": binary,
        "hint": None if binary else "libreoffice-writer 를 설치하거나 LIBREOFFICE_BIN 을 지정하세요.",
    }


@router.post("/docx-normalization/inspect")
async def inspect_docx(file: UploadFile = File(...)) -> dict:
    """ECM 콘텐츠 검출기가 Word 로 인식할 패키지인지 판정한다.

    LibreOffice 없이도 동작한다. 정본화가 필요한 이유를 근거와 함께 제시하는 것이
    목적이다.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    return inspect_docx_package(data)


@router.post("/docx-normalization/normalize")
async def normalize_docx_endpoint(
    request: Request,
    file: UploadFile = File(...),
    filename: str = Form(default="document.docx"),
) -> Response:
    """docx 를 정본 OOXML 로 재직렬화해 돌려준다.

    변환 전후 지표는 응답 헤더(`X-Docx-*`)로 함께 전달한다. 본문이 파일이라
    JSON 을 실을 수 없고, 클라이언트가 유실 경고를 띄우려면 그 값이 필요하다.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    before = inspect_docx_package(data)
    if not before["valid"]:
        raise HTTPException(status_code=400, detail="docx(ZIP) 패키지로 열리지 않습니다.")

    try:
        normalized = normalize_docx(data)
    except DocxNormalizeUnavailable as exc:
        # 정본화 불가와 변환 실패를 구분한다 — 전자는 환경 설정, 후자는 문서 문제다.
        SmartLogger.log(
            "WARN",
            "DOCX normalization unavailable (LibreOffice not found).",
            category="deliverables.docx_normalize.unavailable",
            params={**http_context(request), "filename": filename},
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DocxNormalizeFailed as exc:
        SmartLogger.log(
            "ERROR",
            "DOCX normalization failed.",
            category="deliverables.docx_normalize.failed",
            params={**http_context(request), "filename": filename, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    after = inspect_docx_package(normalized)
    diff = compare_documents(data, normalized)

    SmartLogger.log(
        "INFO",
        "DOCX normalized.",
        category="deliverables.docx_normalize.done",
        params={
            **http_context(request),
            "filename": filename,
            "ecm_compatible_before": before["ecmCompatible"],
            "ecm_compatible_after": after["ecmCompatible"],
            "lossless": diff["lossless"],
            "losses": diff["losses"],
            "size_before": len(data),
            "size_after": len(normalized),
        },
    )

    safe_name = filename if filename.lower().endswith(".docx") else f"{filename}.docx"
    return Response(
        content=normalized,
        media_type=DOCX_MIME,
        headers={
            # 한글 파일명은 RFC 5987 형식으로만 싣는다.
            "Content-Disposition": f"attachment; filename*=UTF-8\'\'{quote(safe_name)}",
            "X-Docx-Ecm-Compatible-Before": str(before["ecmCompatible"]).lower(),
            "X-Docx-Ecm-Compatible-After": str(after["ecmCompatible"]).lower(),
            "X-Docx-Lossless": str(diff["lossless"]).lower(),
            "X-Docx-Losses": "; ".join(diff["losses"]),
            "Access-Control-Expose-Headers": (
                "X-Docx-Ecm-Compatible-Before, X-Docx-Ecm-Compatible-After, "
                "X-Docx-Lossless, X-Docx-Losses"
            ),
        },
    )
