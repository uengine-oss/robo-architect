"""표준항목 공급원 · 맞추기 규칙 — 가짜 MCP 서버(로컬)로 잰다.

정확 일치 · 여럿 · 없음 · 상태 비사용 · 시간 초과 · 닿지 않음 · 꺼짐 · 저장 쿼리 · probe 스크립트.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

from api.features.standard_items import annotate as annotate_mod
from api.features.standard_items.annotate import annotate_property_rows, get_standard_provider
from api.features.standard_items.matching import is_active_status
from api.features.standard_items.mcp_provider import McpDataDictionaryProvider
from api.features.standard_items.tests.fake_mcp_server import free_port, start_in_thread

REPO = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def fake_url():
    server, url = start_in_thread()
    yield url
    server.should_exit = True


def _row(display: str, name: str = "x") -> dict:
    return {"parentType": "Aggregate", "parentId": "A1", "name": name, "displayName": display, "type": "String"}


def _run(coro):
    return asyncio.run(coro)


def test_exact_single_match_attaches(fake_url):
    p = McpDataDictionaryProvider(fake_url, timeout_s=5)
    [r] = _run(annotate_property_rows([_row("주문 번호", "orderNo")], p))
    assert r["standardMatch"] == "matched"
    assert r["standardId"] == "ORD_NO"
    assert r["standardName"] == "주문번호"
    assert r["standardValueType"] == "VARCHAR"
    assert r["standardDataLength"] == 12
    assert r["standardDecimalLength"] is None
    assert r["standardCodeItem"] == "N"
    assert r["standardSource"] == f"posco-mcp:{fake_url}"
    assert r["standardCheckedAt"]
    assert r["name"] == "orderNo"  # 원래 칸은 그대로


def test_multiple_exact_leaves_candidates_only(fake_url):
    p = McpDataDictionaryProvider(fake_url, timeout_s=5)
    [r] = _run(annotate_property_rows([_row("고객명")], p))
    assert r["standardMatch"] == "candidates"
    assert r["standardId"] is None and r["standardName"] is None
    assert r["standardCandidates"] == ["고객명|CUST_NM|사용", "고객명|CUST_NAME|사용"]


def test_not_found(fake_url):
    p = McpDataDictionaryProvider(fake_url, timeout_s=5)
    [r] = _run(annotate_property_rows([_row("없는항목")], p))
    assert r["standardMatch"] == "not_found"
    assert r["standardId"] is None and r["standardCandidates"] == []


def test_similar_only_is_candidate_not_match(fake_url):
    # '주문번호' 로 물었을 때 함께 오는 '주문번호구분' 은 붙지 않는다 — 여기서는 '주문' 이라는 이름이 없다.
    p = McpDataDictionaryProvider(fake_url, timeout_s=5)
    lk = _run(p.search("주문번호"))
    assert [i.standard_korean_name for i in lk.items] == ["주문번호", "주문번호구분"]


def test_inactive_status_is_not_attached(fake_url):
    p = McpDataDictionaryProvider(fake_url, timeout_s=5)
    [r] = _run(annotate_property_rows([_row("폐기항목")], p))
    assert r["standardMatch"] == "candidates"
    assert r["standardId"] is None
    assert "사용 중이 아님" in r["standardNote"]


def test_timeout_is_unverified_and_fast(fake_url):
    p = McpDataDictionaryProvider(fake_url, timeout_s=0.5)
    import time

    t0 = time.monotonic()
    [r] = _run(annotate_property_rows([_row("느림")], p))
    assert time.monotonic() - t0 < 2.5
    assert r["standardMatch"] == "unverified"
    assert r["standardNote"].startswith("표준 미확인")


def test_unreachable_is_unverified_then_backs_off():
    import time

    p = McpDataDictionaryProvider(f"http://127.0.0.1:{free_port()}/mcp", timeout_s=1)
    [r] = _run(annotate_property_rows([_row("주문번호")], p))
    assert r["standardMatch"] == "unverified"
    t0 = time.monotonic()
    [r2] = _run(annotate_property_rows([_row("고객명")], p))
    assert time.monotonic() - t0 < 0.2  # 직전 실패 — 다시 붙지 않는다
    assert "직전 연결 실패" in r2["standardNote"]


def test_disabled_when_env_empty(monkeypatch):
    monkeypatch.delenv("ROBO_STANDARD_MCP_URL", raising=False)
    assert get_standard_provider() is None
    rows = [_row("주문번호")]
    out = _run(annotate_property_rows(rows))
    assert out == rows and "standardMatch" not in out[0]


def test_enabled_from_env(monkeypatch, fake_url):
    monkeypatch.setenv("ROBO_STANDARD_MCP_URL", fake_url)
    monkeypatch.setattr(annotate_mod, "_provider", None)
    [r] = _run(annotate_property_rows([_row("주문번호")]))
    assert r["standardMatch"] == "matched"


def test_active_status_list_overridable(monkeypatch):
    assert is_active_status("사용")
    assert is_active_status(" 사용 중 ")
    assert not is_active_status(None)
    assert not is_active_status("폐기")
    monkeypatch.setenv("ROBO_STANDARD_ACTIVE_STATUSES", "10, 확정")
    assert is_active_status("10") and is_active_status("확정")
    assert not is_active_status("사용")


def test_persistence_writes_standard_only_for_annotated_rows():
    from api.features.ingestion.event_storming.neo4j_ops.properties import PropertyOps

    calls: list[tuple[str, list]] = []

    class _Res:
        def single(self):
            return {"upserted": 2}

    class _Session:
        def run(self, q, rows=None):
            calls.append((q, rows))
            return _Res()

    class _Ops(PropertyOps):
        from contextlib import contextmanager

        @contextmanager
        def session(self):
            yield _Session()

    plain = _row("고객명", "customerName")
    annotated = {**_row("주문번호", "orderNo"), "standardMatch": "matched", "standardId": "ORD_NO"}
    _Ops().upsert_properties_bulk([plain, annotated])
    std = [rows for q, rows in calls if "p.standardMatch" in q]
    assert len(std) == 1 and [r["name"] for r in std[0]] == ["orderNo"]
    assert "p.standardMatch" not in calls[0][0]  # 기본 upsert 는 표준 칸을 건드리지 않는다


@pytest.mark.parametrize("json_mode", [False, True])
def test_probe_script_against_fake(json_mode):
    server, url = start_in_thread(json_response=json_mode)
    try:
        proc = subprocess.run(
            [sys.executable, str(REPO / "deploy/posco-web/probe-standard-mcp.py"), "주문번호", url],
            capture_output=True, timeout=30,
        )
    finally:
        server.should_exit = True
    out = proc.stdout.decode("utf-8", "replace")
    assert proc.returncode == 0, out + proc.stderr.decode("utf-8", "replace")
    assert "searchDataDictionary" in out
    assert "2 건" in out
    assert "정확히 같은 것: 1 건" in out
    assert "standardItemStatus 값: 사용" in out
    assert "✗ 없음" not in out
