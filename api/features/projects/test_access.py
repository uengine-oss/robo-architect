# -*- coding: utf-8 -*-
"""읽기 등급은 **일을 시작하기 전에** 막는다 (2026-10-02).

## 무엇이 있었나

읽기 등급 사용자가 `POST /api/ingest/hybrid/upload` 를 불렀더니 **200 과 세션
아이디**가 나왔다. 그 세션으로 워크플로가 돌면서 **임베딩을 실제로 호출하고**
(비용) 첫 쓰기에서 Postgres 가 막았다 —

    Neo.ClientError.Security.Forbidden: permission denied for table og_role_player

데이터는 안전했다. 막은 것은 **DB** 다. 그런데 사람에게는 **아무 말도 안 갔다**
(SSE 0바이트). 이 저장소가 반복해서 내는 "조용히 아무 일도 안 일어난다" 에
**돈**까지 붙은 꼴이다.

## 여기서 재는 것

  ① 읽기 등급이면 **403 으로 지금 끝낸다**
  ② 쓰기·관리 등급은 지나간다
  ③ 프로젝트를 안 골랐거나 사람을 모르면 **막지 않는다**
     — 단일 PC 구성은 등급 표가 비어 있다. 여기서 막으면 멀쩡하던 길이 닫힌다
  ④ 등급을 못 읽어도 막지 않는다 — 거절의 근거가 아니다
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.features.projects import access


class _Req:
    def __init__(self, headers: dict[str, str]):
        self.headers = {k.lower(): v for k, v in headers.items()}


def _req(graph: str | None = "prj_x", uid: str | None = "E1") -> _Req:
    h: dict[str, str] = {}
    if graph:
        h["x-project-graph"] = graph
    if uid:
        h["authorization"] = "Bearer token-for-" + uid
    return _Req(h)


@pytest.fixture(autouse=True)
def _stub(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(access, "request_uid",
                        lambda r: (r.headers.get("authorization") or "").replace("Bearer token-for-", ""))


def test_읽기_등급은_시작도_못_한다(monkeypatch):
    monkeypatch.setattr(access.projects, "level_of", lambda uid, g: "read")
    with pytest.raises(HTTPException) as e:
        access.require_write(_req())
    assert e.value.status_code == 403
    assert "읽기 권한" in e.value.detail


@pytest.mark.parametrize("level", ["write", "admin"])
def test_쓰기_관리_등급은_지나간다(monkeypatch, level):
    monkeypatch.setattr(access.projects, "level_of", lambda uid, g: level)
    access.require_write(_req())          # 던지지 않으면 통과다


def test_프로젝트를_안_골랐으면_막지_않는다(monkeypatch):
    called = []
    monkeypatch.setattr(access.projects, "level_of", lambda uid, g: called.append(1) or "read")
    access.require_write(_req(graph=None))
    access.require_write(_req(uid=None))
    assert not called, "등급을 볼 필요도 없다 — 그 판정은 다른 자리가 한다"


def test_등급을_못_읽어도_막지_않는다(monkeypatch):
    def boom(uid, g):
        raise RuntimeError("DB 없음")
    monkeypatch.setattr(access.projects, "level_of", boom)
    access.require_write(_req())          # 거절의 근거가 아니다


def test_업로드가_그_검사를_실제로_부른다():
    """검사를 만들어 두고 **안 부르면** 아무 일도 안 한다."""
    import pathlib
    src = pathlib.Path("api/features/ingestion/hybrid/router.py")
    text = src.read_text(encoding="utf-8")
    body = text.split("async def upload_hybrid")[1][:1200]
    assert "require_write(request)" in body, "업로드가 쓰기 권한을 안 본다"
