# -*- coding: utf-8 -*-
"""중앙 DB 에서 **남의 role 비밀번호를 덮어쓰지 않는다** (2026-10-01).

## 무엇이 위험했나

사용자 한 명이 Postgres role 하나(`p_<사번>`)이고, 비밀번호는 저장하지 않고
`HMAC(AUTH_ROLE_SECRET, 사번)` 으로 매번 유도한다. 그래서 PC 마다 그 비밀이
같아야 한다.

`ensure_role()` 은 부를 때마다 `ALTER ROLE … PASSWORD` 를 다시 걸었다. 단일 PC
에서는 "비밀이 바뀌면 스스로 따라오게" 하는 장치지만, 중앙 DB 에서는 그대로
**피해 전파 장치**가 된다 — 비밀을 잘못 넣은 PC 한 대가 프로젝트를 만들거나
공유하는 순간 그 사용자는 **다른 모든 PC 에서** 못 붙는다.

role 이름은 비밀과 무관하다. 그래서 이름은 멀쩡하고 비밀번호만 어긋나며,
증상은 "왜 나만 프로젝트가 안 열리지" 로 나타난다.

## 여기서 재는 것

  ① 단일 PC 는 **그대로다** — 폴백도, 다시 거는 것도 살아 있다
  ② 중앙은 `AUTH_JWT_SECRET` 으로 대신할 수 없다
  ③ 중앙에서 이미 있는 role 은 비밀번호가 맞으면 **건드리지 않는다**
  ④ 안 맞으면 **덮지 않고 멈춘다**
  ⑤ 중앙이라도 **없는 role 은 만든다** — 첫 사용자가 막히면 안 된다
"""

from __future__ import annotations

import pytest

from api.features.projects import roles


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    for k in ("ROBO_GRAPH_MODE", "AUTH_ROLE_SECRET", "AUTH_JWT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    yield


class _Spy:
    """`ensure_role` 이 DB 에 무엇을 했는지 본다."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    def install(self, monkeypatch, *, exists: bool):
        import contextlib

        spy = self

        class _Cur:
            def execute(self, q, *a, **k):
                spy.statements.append(str(q))

            def fetchone(self):
                return {"x": 1} if exists else None

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class _Conn:
            def cursor(self):
                return _Cur()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        @contextlib.contextmanager
        def conn():
            yield _Conn()

        monkeypatch.setattr(roles.pg, "connection", conn)
        monkeypatch.setattr(roles, "role_exists", lambda n: exists)

    @property
    def altered(self) -> bool:
        return any("ALTER ROLE" in s for s in self.statements)

    @property
    def created(self) -> bool:
        return any("CREATE ROLE" in s for s in self.statements)


def test_단일_PC_는_그대로다(monkeypatch):
    """폴백도, 비밀이 바뀌면 다시 거는 것도 살아 있어야 한다."""
    monkeypatch.setenv("AUTH_JWT_SECRET", "only-session-secret")
    assert roles.central_mode() is False
    assert roles.role_password("A1")  # 폴백이 산다

    spy = _Spy()
    spy.install(monkeypatch, exists=True)
    assert roles.ensure_role("A1") == "p_a1"
    assert spy.altered, "단일 PC 에서는 다시 걸어야 한다"


def test_중앙은_세션_비밀로_대신할_수_없다(monkeypatch):
    monkeypatch.setenv("ROBO_GRAPH_MODE", "central")
    monkeypatch.setenv("AUTH_JWT_SECRET", "only-session-secret")
    assert roles.central_mode() is True
    with pytest.raises(RuntimeError) as e:
        roles.role_password("A1")
    assert "AUTH_ROLE_SECRET" in str(e.value)


def test_중앙에서_비밀번호가_맞으면_건드리지_않는다(monkeypatch):
    monkeypatch.setenv("ROBO_GRAPH_MODE", "central")
    monkeypatch.setenv("AUTH_ROLE_SECRET", "shared-across-pcs")
    spy = _Spy()
    spy.install(monkeypatch, exists=True)
    monkeypatch.setattr(roles, "_can_login", lambda n, p: True)

    assert roles.ensure_role("A1") == "p_a1"
    assert not spy.altered, "맞는데도 다시 걸었다 — 남의 비밀번호를 덮을 수 있다"
    assert not spy.created


def test_중앙에서_안_맞으면_덮지_않고_멈춘다(monkeypatch):
    monkeypatch.setenv("ROBO_GRAPH_MODE", "central")
    monkeypatch.setenv("AUTH_ROLE_SECRET", "this-pc-is-wrong")
    spy = _Spy()
    spy.install(monkeypatch, exists=True)
    monkeypatch.setattr(roles, "_can_login", lambda n, p: False)

    with pytest.raises(roles.RoleSecretMismatch) as e:
        roles.ensure_role("A1")
    assert not spy.altered, "**덮어썼다** — 이 사용자가 다른 PC 에서 못 붙게 된다"
    assert "다른 PC" in str(e.value), "사람이 읽고 고칠 수 있는 말이어야 한다"


def test_중앙이라도_없는_role_은_만든다(monkeypatch):
    """첫 사용자가 막히면 중앙 구성을 시작할 수가 없다."""
    monkeypatch.setenv("ROBO_GRAPH_MODE", "central")
    monkeypatch.setenv("AUTH_ROLE_SECRET", "shared-across-pcs")
    spy = _Spy()
    spy.install(monkeypatch, exists=False)

    assert roles.ensure_role("A2") == "p_a2"
    assert spy.created, "없는 role 을 안 만들었다"


def test_모드를_모르면_단일_PC_로_본다(monkeypatch):
    """모르는 상태에서 중앙으로 가정하면 1인 사용자가 기동을 못 한다."""
    monkeypatch.setenv("AUTH_JWT_SECRET", "s")
    for value in ("", "bundled", "BUNDLED", "weird"):
        monkeypatch.setenv("ROBO_GRAPH_MODE", value)
        assert roles.central_mode() is False, value
    monkeypatch.setenv("ROBO_GRAPH_MODE", "CENTRAL")
    assert roles.central_mode() is True, "대소문자를 가린다"


def test_같은_비밀이면_같은_비밀번호_다르면_다르다(monkeypatch):
    """이름은 비밀과 무관하다 — 그래서 어긋남이 조용하다."""
    monkeypatch.setenv("AUTH_ROLE_SECRET", "secret-A")
    a = roles.role_password("A1")
    monkeypatch.setenv("AUTH_ROLE_SECRET", "secret-A")
    assert roles.role_password("A1") == a
    monkeypatch.setenv("AUTH_ROLE_SECRET", "secret-B")
    assert roles.role_password("A1") != a
    assert roles.role_name("A1") == "p_a1", "이름은 그대로다"
