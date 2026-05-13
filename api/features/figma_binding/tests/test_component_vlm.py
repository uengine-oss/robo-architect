"""Unit tests for component_vlm.describe_components (spec 024).

The VLM call must:
- skip components whose image_url is empty
- degrade to empty string when image download or LLM invocation fails
- return one entry per requested id
"""
from __future__ import annotations

import asyncio

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.features.figma_binding import component_vlm


class _FakeResp:
    def __init__(self, content: bytes, mime: str = "image/png", status: int = 200):
        self.content = content
        self.headers = {"content-type": mime}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


def test_describe_components_skips_empty_urls():
    async def _run():
        return await component_vlm.describe_components([
            ("1:1", "name1", ""),
            ("1:2", "name2", None),
        ])
    out = asyncio.run(_run())
    assert out == {}


def test_describe_components_returns_text_per_id():
    """LLM returns a text message; we keep it (one-line, trimmed)."""

    async def _aclient_get(self, url, timeout=None):
        return _FakeResp(b"PNGBYTES", "image/png")

    fake_llm_resp = MagicMock()
    fake_llm_resp.content = "A primary call-to-action button.\n"

    with patch.object(httpx.AsyncClient, "get", new=_aclient_get), \
         patch.object(component_vlm, "get_llm") as get_llm:
        llm = MagicMock()
        llm.invoke.return_value = fake_llm_resp
        get_llm.return_value = llm

        out = asyncio.run(component_vlm.describe_components([
            ("1:1", "btn-primary", "https://x/1.png"),
        ]))

    assert out == {"1:1": "A primary call-to-action button."}


def test_describe_components_swallows_llm_failure():
    async def _aclient_get(self, url, timeout=None):
        return _FakeResp(b"PNGBYTES", "image/png")

    with patch.object(httpx.AsyncClient, "get", new=_aclient_get), \
         patch.object(component_vlm, "get_llm") as get_llm:
        llm = MagicMock()
        llm.invoke.side_effect = RuntimeError("boom")
        get_llm.return_value = llm

        out = asyncio.run(component_vlm.describe_components([
            ("1:1", "btn", "https://x/1.png"),
        ]))

    assert out == {"1:1": ""}


def test_describe_components_swallows_image_download_failure():
    async def _aclient_get(self, url, timeout=None):
        raise httpx.ConnectError("down")

    with patch.object(httpx.AsyncClient, "get", new=_aclient_get):
        out = asyncio.run(component_vlm.describe_components([
            ("1:1", "btn", "https://x/1.png"),
        ]))

    assert out == {"1:1": ""}
