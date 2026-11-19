"""lite 0.1.5 — 인증을 안 쓰는 판에는 계정 스키마가 없다. /api/auth/provider 가 그 테이블을 읽으면 500."""

from __future__ import annotations

import asyncio

import pytest

from api.features.auth import router as auth_router


def _boom():
    raise RuntimeError('relation "public.app_auth_policy" does not exist')


def test_provider_none_does_not_read_account_policy(monkeypatch):
    monkeypatch.delenv("AUTH_PROVIDER", raising=False)
    monkeypatch.delenv("AUTH_ENFORCE", raising=False)
    monkeypatch.setattr(auth_router, "auth_enforced", lambda: False)
    monkeypatch.setattr(auth_router.accounts, "approval_enabled", _boom)
    body = asyncio.run(auth_router.get_provider())
    assert body["provider"] == "none" and body["approvalRequired"] is False and body["enforce"] is False


def test_enforced_still_reads_account_policy(monkeypatch):
    monkeypatch.setattr(auth_router, "auth_enforced", lambda: True)
    monkeypatch.setattr(auth_router.accounts, "approval_enabled", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(auth_router.get_provider())
