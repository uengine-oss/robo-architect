"""생성 모델 목록 — 환경설정 모달이 부른다. 고르는 것은 브라우저(사용자마다)가 한다.

GET /api/llm/models          {"default": "gpt-4.1", "models": [...], "error": null}
GET /api/llm/models?refresh=1  캐시(5분)를 건너뛴다
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from api.platform.llm_model_choice import default_model, list_models, selected_model

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/models")
async def get_models(refresh: bool = Query(default=False)) -> dict:
    models, error = await list_models(force=refresh)
    return {
        "default": default_model(),
        "models": models or [],
        "selected": selected_model(),   # 이 요청에 실린 헤더가 받아들여졌나
        "error": error,
    }
