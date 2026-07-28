"""정상적인 Figma 미연결 상태는 브라우저 오류를 만들지 않는다."""
from __future__ import annotations

import asyncio

from fastapi import Response

from api.features.figma_binding import router


def test_get_binding_returns_no_content_when_optional_binding_is_absent(monkeypatch):
    monkeypatch.setattr(router.service, "get_active_binding_response", lambda: None)
    response = asyncio.run(router.get_binding())
    assert isinstance(response, Response)
    assert response.status_code == 204
    assert response.body == b""


def test_get_binding_preserves_active_binding(monkeypatch):
    binding = {"id": "binding-1", "status": "active"}
    monkeypatch.setattr(router.service, "get_active_binding_response", lambda: binding)
    assert asyncio.run(router.get_binding()) is binding
