"""Test that /api/ingest/upload* accepts the spec 024 mode value.

We avoid the heavy ingestion workflow by mocking it; the test only asserts
the validation layer keeps the mode value.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient


def _make_client():
    from api.main import app
    return TestClient(app)


def _post_upload_text(client: TestClient, mode: str):
    return client.post(
        "/api/ingest/upload",
        data={"text": "hello", "ui_generation_mode": mode},
    )


@pytest.mark.parametrize("mode,expected", [
    ("html", "html"),
    ("figma", "figma"),
    ("figma-with-components", "figma-with-components"),
    # Unknown values are coerced to "html" by the router.
    ("nonsense", "html"),
    ("FIGMA", "figma"),  # case-insensitive coercion
])
def test_upload_accepts_three_modes(mode: str, expected: str):
    client = _make_client()
    with patch("api.features.ingestion.router.run_ingestion_workflow"):
        r = _post_upload_text(client, mode)
    assert r.status_code == 200, r.text
    assert r.json()["ui_generation_mode"] == expected


def test_upload_figma_accepts_three_modes():
    client = _make_client()
    payload = {
        "figma_nodes": [{"id": "1:1", "type": "FRAME", "name": "x"}],
        "source_type": "figma",
        "display_language": "ko",
        "ui_generation_mode": "figma-with-components",
    }
    with patch("api.features.ingestion.router.run_ingestion_workflow"):
        r = client.post("/api/ingest/upload/figma", json=payload)
    assert r.status_code == 200, r.text
