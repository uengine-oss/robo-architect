"""사용자가 고른 생성 모델 — 요청마다 `X-LLM-Model` 헤더로 온다(환경설정 모달).

posco-web 은 사내 P-GPT(OpenAI 호환) 하나로 나간다. 그 게이트웨이의 `/models` 목록 가운데
**사람마다 자기 모델을 고른다**(2026-11-16 결정 — 서버 전체 하나가 아니다).

    브라우저 ─ X-LLM-Model: gpt-4o ─► LlmModelChoiceMiddleware
                                       └ 목록에 있으면 ContextVar 에 놓는다
    get_llm_model() · get_chat_model() · llm._resolve_model() 이 그 값을 먼저 본다
    ingestion 은 요청 안에서 asyncio.create_task 로 시작하므로 그 컨텍스트를 물려받는다

지키는 것
- **목록에 있는 이름만** 받는다. 없거나 목록을 못 받으면 헤더를 버리고 기본값(LLM_MODEL)으로 간다 —
  아무 문자열이나 게이트웨이에 흘려보내지 않는다.
- **임베딩은 바꾸지 않는다.** EMBEDDING_MODEL 은 따로 읽고, 목록에서도 임베딩·음성·이미지 모델은 뺀다
  (저장된 벡터와 차원이 달라지면 검색이 깨진다).
- 공급자가 openai 일 때만 쓴다(anthropic·google 판은 그대로).
"""

from __future__ import annotations

import asyncio
import os
import time
from contextvars import ContextVar
from typing import Any

HEADER = "x-llm-model"
_SELECTED: ContextVar[str | None] = ContextVar("robo_llm_model_choice", default=None)

_CACHE_TTL_S = 300.0
_cache: dict[str, Any] = {"at": 0.0, "models": None, "error": None}
_lock = asyncio.Lock()

# 생성(채팅)에 쓰지 않는 모델 — 이름에 이것이 들어 있으면 목록에서 뺀다.
_NON_CHAT = ("embedding", "embed", "whisper", "tts", "dall-e", "dalle", "moderation",
             "transcribe", "audio", "realtime", "image", "search", "davinci", "babbage")


def selected_model() -> str | None:
    """이 요청(또는 그 요청이 시작한 작업)에서 사용자가 고른 모델. 없으면 None."""
    return _SELECTED.get()


def set_selected_model(model: str | None):
    """시험·작업 시작점에서 직접 놓을 때. 돌려받은 토큰으로 `_SELECTED.reset()` 한다."""
    return _SELECTED.set(model)


def default_model() -> str:
    return (os.getenv("LLM_MODEL") or "").strip() or "gpt-4.1"


def _base_url() -> str:
    for key in ("LLM_API_BASE", "OPENAI_BASE_URL"):
        v = (os.getenv(key) or "").strip()
        if v:
            return v.rstrip("/")
    return "https://api.openai.com/v1"


def _api_key() -> str:
    for key in ("LLM_API_KEY", "OPENAI_API_KEY"):
        v = (os.getenv(key) or "").strip()
        if v:
            return v
    return ""


def is_chat_model(model_id: str) -> bool:
    low = model_id.lower()
    return bool(model_id) and not any(word in low for word in _NON_CHAT)


def _parse_models(payload: Any) -> list[str]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    ids: list[str] = []
    for row in rows or []:
        mid = row.get("id") if isinstance(row, dict) else row
        if isinstance(mid, str) and is_chat_model(mid.strip()):
            ids.append(mid.strip())
    return sorted(dict.fromkeys(ids))


async def list_models(*, force: bool = False) -> tuple[list[str] | None, str | None]:
    """(생성 모델 목록, 오류 문구). 5분 캐시. 실패하면 (None, 문구) — 키는 문구에 넣지 않는다."""
    now = time.monotonic()
    if not force and _cache["models"] is not None and now - _cache["at"] < _CACHE_TTL_S:
        return _cache["models"], None
    async with _lock:
        if not force and _cache["models"] is not None and time.monotonic() - _cache["at"] < _CACHE_TTL_S:
            return _cache["models"], None
        import httpx

        headers = {"Authorization": f"Bearer {_api_key()}"} if _api_key() else {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(_base_url() + "/models", headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"/models 가 HTTP {resp.status_code} 로 답했다")
            models = _parse_models(resp.json())
        except Exception as exc:  # noqa: BLE001 — 목록을 못 받으면 기본값으로 돈다
            _cache.update(error=str(exc)[:200])
            return _cache["models"], _cache["error"]
        _cache.update(at=time.monotonic(), models=models, error=None)
        return models, None


async def accept(requested: str | None) -> str | None:
    """헤더 값을 받을지 판정한다. 받으면 그 이름, 아니면 None(→ 기본값)."""
    name = (requested or "").strip()
    if not name or len(name) > 128 or name == default_model():
        return None
    models, _ = await list_models()
    return name if models and name in models else None


class LlmModelChoiceMiddleware:
    """순수 ASGI — ContextVar 가 엔드포인트와 그 안에서 만든 작업까지 그대로 내려가게."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)
        raw = None
        for key, value in scope.get("headers") or ():
            if key == HEADER.encode():
                raw = value.decode("utf-8", "replace")
                break
        chosen = await accept(raw) if raw else None
        token = _SELECTED.set(chosen)
        try:
            await self.app(scope, receive, send)
        finally:
            _SELECTED.reset(token)
