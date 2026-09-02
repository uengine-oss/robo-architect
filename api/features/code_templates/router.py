"""템플릿 기반 코드 생성 — 읽기 API.

렌더링 자체는 프런트엔드가 한다. **템플릿이 자기 Handlebars 헬퍼를
JavaScript 로 들고 다니기 때문**이다(`<function>` 블록). 파이썬으로 옮기려면
그 JS 를 실행해야 하므로, 렌더러는 브라우저에 두고 서버는 재료만 준다 —
템플릿 원문과 ES 모델 컨텍스트.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from starlette.requests import Request

from api.features.code_templates import context as ctx_builder
from api.features.code_templates import repository
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/code-templates", tags=["code-templates"])


@router.get("/sets")
async def list_sets() -> dict:
    """`templates/` 아래에 받아 둔 템플릿 묶음 목록."""
    sets = repository.list_template_sets()
    return {
        "sets": sets,
        # 비어 있으면 화면이 원인을 말할 수 있어야 한다.
        "templatesRoot": str(repository.TEMPLATES_ROOT),
        "hint": None if sets else "scripts/fetch-templates.sh 를 실행해 템플릿을 받으세요.",
    }


@router.get("/sets/{set_name}/files")
async def list_files(request: Request, set_name: str) -> dict:
    """묶음 하나의 템플릿 전체 — front matter 를 떼고 본문과 헬퍼를 나눠서."""
    try:
        templates = repository.load_templates(set_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    files = [t.to_dict() for t in templates]
    renderable = [f for f in files if f["forEach"]]
    SmartLogger.log(
        "INFO",
        f"Template set loaded: {set_name}",
        category="code_templates.files",
        params={**http_context(request), "set": set_name,
                "files": len(files), "renderable": len(renderable)},
    )
    return {
        "set": set_name,
        "files": files,
        "summary": {
            "files": len(files),
            "renderable": len(renderable),
            "withHelpers": sum(1 for f in files if f["functions"]),
        },
    }


@router.get("/context")
async def get_context(
    request: Request,
    sessionId: str = Query(..., min_length=1),
    serviceId: str = Query(..., min_length=1),
) -> dict:
    """세션의 ES 모델을 렌더 컨텍스트로 편다.

    `serviceId` 는 자바 패키지의 한 마디가 되므로(`com.poscodx.<serviceId>.…`)
    호출자가 정한다. 화면은 세션 이름을 기본값으로 보여 주고 사용자가 고치게
    한다 — 여기서 추측하지 않는다.
    """
    payload = ctx_builder.build_context(sessionId, service_id=serviceId)
    if not payload["boundedContexts"]:
        raise HTTPException(
            status_code=404,
            detail=f"세션 '{sessionId}' 에 Bounded Context 가 없습니다. 이벤트 스토밍 승격이 끝났는지 확인하세요.",
        )
    SmartLogger.log(
        "INFO",
        "Template render context built.",
        category="code_templates.context",
        params={**http_context(request), "session_id": sessionId, "service_id": serviceId,
                "bounded_contexts": len(payload["boundedContexts"]),
                "aggregates": sum(len(b["aggregates"]) for b in payload["boundedContexts"])},
    )
    return payload
