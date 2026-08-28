from __future__ import annotations

import pytest

from api.features.auth.config import (
    AuthProvider,
    SwpSettings,
    auth_provider,
    is_allowed_callback,
)
from api.features.auth.swp import build_redirect_url, parse_user_info


@pytest.fixture
def settings(monkeypatch):
    for key in (
        "SWP_SSO_REDIRECT_URL", "SWP_SSO_VALID_CHECK_URL", "SWP_SSO_LOGIN_URL",
        "SWP_IDX_ID", "SWP_IDX_EMPNO", "SWP_IDX_DISPLAYNAME", "SWP_IDX_MAIL",
        "SWP_IDX_DEPT", "SWP_EMAIL_FALLBACK_DOMAIN", "SWP_SSO_TIMEOUT_S",
    ):
        monkeypatch.delenv(key, raising=False)
    return SwpSettings.from_env()


def _csv(*fields):
    return ",".join(fields)


# 스펙 표 순서: 0=iv-user, 1=sp_empno, 4=seealso, 8=displayname, 9=mail
def _spec_response(**over):
    parts = [""] * 10
    parts[0] = over.get("id", "hong.gildong")
    parts[1] = over.get("empno", "A123456")
    parts[4] = over.get("dept", "%EC%84%A4%EA%B3%84%ED%8C%80")  # 설계팀
    parts[8] = over.get("display", "HONG%20GILDONG")
    parts[9] = over.get("mail", "hong@posco.com")
    return _csv(*parts)


# ---------------------------------------------------------------------------
# 정상 파싱
# ---------------------------------------------------------------------------


def test_parses_spec_ordered_response(settings):
    user = parse_user_info(_spec_response(), settings)

    assert user is not None
    assert user.id == "A123456"          # 안정 고유키 = 사번
    assert user.empno == "A123456"
    assert user.username == "hong.gildong"
    assert user.name == "HONG GILDONG"   # URL 디코드
    assert user.email == "hong@posco.com"
    assert user.department == "설계팀"    # URL 디코드
    assert user.source == "swp"


def test_field_drift_email_and_name_follow_the_at_sign(settings):
    """현장 피드가 한 칸 밀려 와도 이메일·영문성명을 놓치지 않는다.

    스펙상 8=displayname, 9=mail 인데 idx 8 이 비고 9/10 으로 밀린 사례.
    이메일은 '@' 토큰을 직접 찾고, 영문성명은 그 앞 토큰을 쓴다.
    """
    parts = [""] * 11
    parts[0] = "hong.gildong"
    parts[1] = "A123456"
    parts[9] = "HONG%20GILDONG"
    parts[10] = "hong@posco.com"
    user = parse_user_info(_csv(*parts), settings)

    assert user.email == "hong@posco.com"
    assert user.name == "HONG GILDONG"


def test_email_falls_back_to_synthesized_address(settings):
    """메일이 비면 사번으로 합성한다 — 식별 키가 비는 것을 막는다."""
    user = parse_user_info(_spec_response(mail="", display="HONG"), settings)

    assert user.email == "A123456@posco.local"


def test_display_name_falls_back_to_login_id(settings):
    parts = [""] * 10
    parts[0] = "hong.gildong"
    parts[1] = "A123456"
    user = parse_user_info(_csv(*parts), settings)

    assert user.name == "hong.gildong"


def test_login_id_used_when_empno_missing(settings):
    parts = [""] * 10
    parts[0] = "hong.gildong"
    parts[9] = "hong@posco.com"
    user = parse_user_info(_csv(*parts), settings)

    assert user.id == "hong.gildong"
    assert user.empno == ""


# ---------------------------------------------------------------------------
# 거부 경로
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["Unauthenticated", "Unauthenticated,,,", "", "   "])
def test_unauthenticated_responses_return_none(settings, raw):
    assert parse_user_info(raw, settings) is None


def test_none_response_returns_none(settings):
    assert parse_user_info(None, settings) is None


def test_no_identifier_returns_none(settings):
    """사번도 로그인 ID 도 없으면 이메일로 대체하지 않는다.

    불안정한 키로 계정을 만들면 나중에 병합 사고가 난다.
    """
    parts = [""] * 10
    parts[0] = ""
    parts[9] = "hong@posco.com"
    # 첫 필드가 비면 애초에 미인증으로 본다.
    assert parse_user_info(_csv(*parts), settings) is None

    parts[0] = "-"
    parts[1] = ""
    user = parse_user_info(_csv(*parts), settings)
    assert user is not None and user.id == "-"


# ---------------------------------------------------------------------------
# 인덱스 재조정 (재빌드 없이 .env 로만)
# ---------------------------------------------------------------------------


def test_field_indexes_are_env_adjustable(monkeypatch):
    monkeypatch.setenv("SWP_IDX_ID", "1")
    monkeypatch.setenv("SWP_IDX_EMPNO", "0")
    monkeypatch.setenv("SWP_EMAIL_FALLBACK_DOMAIN", "example.test")
    settings = SwpSettings.from_env()

    user = parse_user_info(_csv("A999", "login.id", "", ""), settings)

    assert user.empno == "A999"
    assert user.username == "login.id"
    assert user.email == "A999@example.test"


# ---------------------------------------------------------------------------
# redirect URL
# ---------------------------------------------------------------------------


def test_redirect_url_encodes_callback(settings):
    url = build_redirect_url(settings, "https://robo.posco.net/auth/callback?x=1")

    assert url.startswith(settings.redirect_url)
    assert "https%3A%2F%2Frobo.posco.net%2Fauth%2Fcallback%3Fx%3D1" in url


# ---------------------------------------------------------------------------
# provider 전환 / 콜백 허용목록
# ---------------------------------------------------------------------------


def test_default_provider_is_none(monkeypatch):
    monkeypatch.delenv("AUTH_PROVIDER", raising=False)
    assert auth_provider() is AuthProvider.NONE


@pytest.mark.parametrize("value", ["swp", "SWP", "posco", "posco-swp", "swp_sso"])
def test_provider_aliases(monkeypatch, value):
    monkeypatch.setenv("AUTH_PROVIDER", value)
    assert auth_provider() is AuthProvider.SWP


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("AUTH_PROVIDER", "keycloak")
    with pytest.raises(RuntimeError, match="AUTH_PROVIDER"):
        auth_provider()


def test_callback_allowlist_defaults_to_loopback_only(monkeypatch):
    monkeypatch.delenv("AUTH_CALLBACK_ALLOWLIST", raising=False)

    assert is_allowed_callback("http://localhost:5173/cb") is True
    assert is_allowed_callback("http://127.0.0.1:8000/cb") is True
    assert is_allowed_callback("https://evil.example.com/cb") is False


def test_callback_allowlist_matches_origin(monkeypatch):
    monkeypatch.setenv("AUTH_CALLBACK_ALLOWLIST", "https://robo.posco.net, https://robo2.posco.net/")

    assert is_allowed_callback("https://robo.posco.net/auth/callback") is True
    assert is_allowed_callback("https://robo2.posco.net/auth/callback") is True
    # 호스트가 부분 일치하는 공격 도메인을 걸러낸다.
    assert is_allowed_callback("https://robo.posco.net.evil.com/cb") is False
    assert is_allowed_callback("http://robo.posco.net/cb") is False  # scheme 다름
    assert is_allowed_callback("http://localhost:5173/cb") is False  # 목록이 있으면 loopback 자동허용 없음


@pytest.mark.parametrize("url", ["", "javascript:alert(1)", "ftp://x/y", "not a url"])
def test_malformed_callbacks_rejected(monkeypatch, url):
    monkeypatch.delenv("AUTH_CALLBACK_ALLOWLIST", raising=False)
    assert is_allowed_callback(url) is False
