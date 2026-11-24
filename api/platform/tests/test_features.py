"""Figma 끄기 스위치 (2026-11-24) — 꺼지면 Figma 경로가 막히고 화면은 features 로 안다."""

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api.platform import features


def _app():
    app = FastAPI()
    app.add_middleware(features.FeatureGateMiddleware)
    app.include_router(features.router)

    @app.get("/api/figma-binding/")
    def binding():
        return {"ok": True}

    @app.post("/api/auth/figma-pair")
    def pair():
        return {"ok": True}

    @app.get("/api/contexts")
    def other():
        return {"ok": True}

    @app.websocket("/ws/figma-plugin")
    async def ws(sock: WebSocket):
        await sock.accept()
        await sock.send_text("hi")
        await sock.close()

    return TestClient(app)


@pytest.mark.parametrize("value,on", [(None, True), ("", True), ("true", True), ("1", True),
                                      ("false", False), ("0", False), ("OFF", False), ("no", False)])
def test_flag_values(monkeypatch, value, on):
    if value is None:
        monkeypatch.delenv("ROBO_FIGMA_ENABLED", raising=False)
    else:
        monkeypatch.setenv("ROBO_FIGMA_ENABLED", value)
    assert features.figma_enabled() is on
    assert _app().get("/api/features").json() == {"figma": on}


def test_off_blocks_figma_paths_only(monkeypatch):
    monkeypatch.setenv("ROBO_FIGMA_ENABLED", "false")
    c = _app()
    assert c.get("/api/figma-binding/").status_code == 404
    assert c.post("/api/auth/figma-pair").status_code == 404
    assert c.get("/api/contexts").status_code == 200
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws/figma-plugin") as s:
            s.receive_text()


def test_on_is_unchanged(monkeypatch):
    monkeypatch.setenv("ROBO_FIGMA_ENABLED", "true")
    c = _app()
    assert c.get("/api/figma-binding/").json() == {"ok": True}
    with c.websocket_connect("/ws/figma-plugin") as s:
        assert s.receive_text() == "hi"


def test_posco_extension_defaults_off():
    from api.extensions import Registry
    from extensions.posco.backend import register
    reg = Registry()
    register(None, reg)
    assert reg.env_defaults.get("ROBO_FIGMA_ENABLED") == "false"
