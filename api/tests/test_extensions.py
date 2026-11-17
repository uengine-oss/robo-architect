# -*- coding: utf-8 -*-
"""고객 확장 등록부 — **기본은 빈 자리, 고른 고객 하나만, 없는 고객은 멈춘다**."""

from __future__ import annotations

import pytest

from api import extensions


@pytest.fixture(autouse=True)
def _fresh(monkeypatch: pytest.MonkeyPatch):
    extensions._reset_for_tests()
    monkeypatch.delenv("ROBO_CUSTOMER", raising=False)
    yield
    extensions._reset_for_tests()


class _App:
    def __init__(self):
        self.routers = []

    def include_router(self, r):
        self.routers.append(r)


def test_고객을_안_주면_default_이고_자리가_비어_있다():
    reg = extensions.load_extensions(_App())
    assert extensions.customer() == "default"
    assert reg == extensions.Registry()


def test_posco_를_고르면_posco_값이_들어온다(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROBO_CUSTOMER", "posco")
    reg = extensions.load_extensions(_App())
    assert reg.llm_overrides["default_model"] == "gpt-4.1"
    assert reg.deliverable_policies["allowed_formats"] == ["docx"]
    assert [t["name"] for t in reg.template_sets] == ["template-poscodx"]


def test_없는_고객은_기동을_멈춘다(monkeypatch: pytest.MonkeyPatch):
    """조용히 기본 판으로 뜨면 고객 기능이 빠진 판이 현장에 나간다."""
    monkeypatch.setenv("ROBO_CUSTOMER", "hanwha")
    with pytest.raises(extensions.ExtensionError):
        extensions.load_extensions(_App())


def test_모양이_틀린_고객_이름은_막는다(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROBO_CUSTOMER", "../posco")
    with pytest.raises(extensions.ExtensionError):
        extensions.load_extensions(_App())


def test_한_기동에_두_고객을_읽지_않는다(monkeypatch: pytest.MonkeyPatch):
    extensions.load_extensions(_App())
    monkeypatch.setenv("ROBO_CUSTOMER", "posco")
    with pytest.raises(extensions.ExtensionError):
        extensions.load_extensions(_App())


def test_확장_라우터는_app_에_붙는다(monkeypatch: pytest.MonkeyPatch):
    import types, sys

    fake = types.ModuleType("extensions.zz_test.backend")
    fake.register = lambda app, reg: reg.routers.append("R")
    monkeypatch.setitem(sys.modules, "extensions.zz_test.backend", fake)
    monkeypatch.setattr(extensions, "_module_for", lambda name: "extensions.zz_test.backend")
    monkeypatch.setenv("ROBO_CUSTOMER", "zz_test")
    app = _App()
    extensions.load_extensions(app)
    assert app.routers == ["R"]


def test_프로필_기본값은_빈_환경변수만_채운다(monkeypatch: pytest.MonkeyPatch):
    """사람이 .env 에 넣은 값이 늘 이긴다. 현장 compose 는 SWP 주소를 빈 문자열로 넘긴다."""
    monkeypatch.setenv("ROBO_CUSTOMER", "posco")
    monkeypatch.setenv("SWP_SSO_LOGIN_URL", "")                       # 비어 있음 → 채운다
    monkeypatch.setenv("SWP_SSO_VALID_CHECK_URL", "http://site/valid")  # 사람이 넣음 → 그대로
    monkeypatch.delenv("SWP_SSO_REDIRECT_URL", raising=False)           # 없음 → 채운다
    extensions.load_extensions(_App())
    import os
    assert os.environ["SWP_SSO_LOGIN_URL"] == "http://swp.posco.net"
    assert os.environ["SWP_SSO_VALID_CHECK_URL"] == "http://site/valid"
    assert os.environ["SWP_SSO_REDIRECT_URL"].startswith("http://swpsso.posco.net/")


def test_기본_고객은_SWP_주소를_채우지_않는다(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SWP_SSO_LOGIN_URL", raising=False)
    extensions.load_extensions(_App())
    import os
    assert "SWP_SSO_LOGIN_URL" not in os.environ
