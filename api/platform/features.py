"""망마다 켜고 끄는 기능 — 화면이 무엇을 보여 줄지 서버가 알려 준다 (2026-11-24).

첫 항목은 Figma. 포스코는 Figma 를 끈다(2026-11-23 사용자): 사내 서버에 https 가 없으면
Figma 앱이 플러그인 연결을 막아, PC 마다 우회 없이는 쓸 수 없다.

    ROBO_FIGMA_ENABLED   비우면 켜짐(지금과 같음) · false/0/off/no 면 꺼짐
                         포스코 확장(extensions/posco/backend)은 기본값을 false 로 둔다.

꺼지면
- 화면: `GET /api/features` 의 `figma: false` 를 보고 Figma 진입점을 모두 숨긴다(안 정한 기능은 숨김 원칙).
- 서버: Figma 경로를 404 로 막는다(웹소켓은 닫는다). 라우터는 그대로 붙여 두고 **요청마다** 본다 —
  확장의 기본값이 라우터를 붙인 뒤에 적용되기 때문이다(main.py `load_extensions` 가 맨 끝).
"""

from __future__ import annotations

import os

from fastapi import APIRouter
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

_OFF = {"0", "false", "off", "no", "n"}

# Figma 기능이 쓰는 경로 — figma_api · figma_sync · figma_plugin_ws · figma_binding(+plugin_messages) · 플러그인 짝짓기
FIGMA_PATH_PREFIXES = (
    "/api/ingest/figma-api",
    "/api/ingest/figma-sync",
    "/api/figma-plugin",
    "/api/figma-binding",
    "/ws/figma-plugin",
    "/api/auth/figma-",
)


def figma_enabled() -> bool:
    return (os.getenv("ROBO_FIGMA_ENABLED") or "").strip().lower() not in _OFF


def describe() -> dict:
    return {"figma": figma_enabled()}


router = APIRouter(tags=["features"])


@router.get("/api/features")
def get_features() -> dict:
    """화면이 부팅 때 한 번 읽는다. 인증 없이 — 로그인 화면에서도 무엇을 숨길지 알아야 한다."""
    return describe()


def is_figma_path(path: str) -> bool:
    return any(path.startswith(p) for p in FIGMA_PATH_PREFIXES)


class FeatureGateMiddleware:
    """꺼진 기능의 경로를 막는다. 순수 ASGI — 웹소켓도 같은 자리에서 막을 수 있게."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket") and is_figma_path(scope.get("path", "")) and not figma_enabled():
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            await JSONResponse({"detail": "이 서버에서는 Figma 기능을 쓰지 않습니다."}, status_code=404)(scope, receive, send)
            return
        await self.app(scope, receive, send)
