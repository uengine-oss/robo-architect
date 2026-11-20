"""플러그인 '연결됨' 은 최근 poll 이 있을 때만 — 옛 파일 키로 메시지를 넣지 않는다(2026-11-20 현장)."""
import time

from api.features.ingestion import figma_plugin_ws as ws


def test_alive_only_after_recent_poll(monkeypatch):
    monkeypatch.setattr(ws, "_last_seen", {})
    monkeypatch.setattr(ws, "_connections", {})
    assert not ws.is_polling_active("old")
    ws._touch("old")
    assert ws.is_polling_active("old")
    t = ws._last_seen["old"]
    monkeypatch.setattr(time, "monotonic", lambda: t + ws._ALIVE_WITHIN_S + 1)
    assert not ws.is_polling_active("old")


def test_metadata_alone_is_not_alive(monkeypatch):
    """예전에는 _plugin_metadata 에 한 번 들어가면 영원히 '연결됨' 이었다."""
    monkeypatch.setattr(ws, "_last_seen", {})
    monkeypatch.setattr(ws, "_connections", {})
    monkeypatch.setattr(ws, "_plugin_metadata", {"stale": {"supportedMessages": []}})
    assert not ws.is_polling_active("stale")
