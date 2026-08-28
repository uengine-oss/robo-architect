"""인증 provider 설정 — 전부 환경 변수로 해석한다.

기준 구현(`local-msaez`)은 data-gateway 컨테이너의 docker-compose 환경 블록에
값을 박았다. Robo Architect 는 게이트웨이 컨테이너가 없고 FastAPI 가 직접
요청을 받으므로, 같은 계약을 `.env` 로 옮긴다. 키 이름은 현장 운영자가 두
시스템을 오갈 수 있도록 기준 구현과 동일하게 유지한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from api.platform.env import env_int, env_list, env_str


class AuthProvider(str, Enum):
    #                                   기존 동작 — X-User-* 헤더 기반 Actor 전파
    NONE = "none"
    #                                   POSCO SWP SSO (HTTP 인증 토큰 방식)
    SWP = "swp"


# 운영자가 쓸 법한 표기를 모두 받는다.
_PROVIDER_ALIASES = {
    "": AuthProvider.NONE,
    "none": AuthProvider.NONE,
    "off": AuthProvider.NONE,
    "disabled": AuthProvider.NONE,
    "swp": AuthProvider.SWP,
    "posco": AuthProvider.SWP,
    "posco_swp": AuthProvider.SWP,
    "swp_sso": AuthProvider.SWP,
}


def auth_provider() -> AuthProvider:
    raw = (env_str("AUTH_PROVIDER", default="none") or "none").strip().lower().replace("-", "_")
    provider = _PROVIDER_ALIASES.get(raw)
    if provider is None:
        raise RuntimeError(
            f"지원하지 않는 AUTH_PROVIDER='{raw}'. 사용 가능: none | swp (별칭: posco)"
        )
    return provider


def is_enterprise_auth() -> bool:
    return auth_provider() is not AuthProvider.NONE


@dataclass(frozen=True)
class SwpSettings:
    """SWP(POSCO) SSO 설정.

    `idx_*` 는 `isValidSSO` 응답(콤마 구분)의 0-based 필드 위치다. 현장 응답이
    스펙 표와 어긋나는 사례가 있어, 재빌드 없이 `.env` 로만 조정할 수 있게 둔다.
    """

    redirect_url: str
    valid_check_url: str
    login_url: str
    idx_id: int
    idx_empno: int
    idx_display_name: int
    idx_mail: int
    idx_dept: int
    email_fallback_domain: str
    timeout_s: int

    @classmethod
    def from_env(cls) -> "SwpSettings":
        return cls(
            # 'redir_url=' 로 끝나야 하며 뒤에 우리 콜백 URL 을 append 한다.
            redirect_url=env_str(
                "SWP_SSO_REDIRECT_URL",
                default="http://swpsso.posco.net/idms/U61/jsp/redirect.jsp?redir_url=",
            ),
            # ssoToken 유효성 검증 (Cookie: SWP-H-SESSION-ID). 성공 시 사용자정보 CSV.
            valid_check_url=env_str(
                "SWP_SSO_VALID_CHECK_URL",
                default="http://swpsso.posco.net/idms/U61/jsp/isValidSSO.jsp",
            ),
            # 미인증 시 되돌려보낼 SWP 로그인 홈.
            login_url=env_str("SWP_SSO_LOGIN_URL", default="http://swp.posco.net"),
            idx_id=env_int("SWP_IDX_ID", 0),                    # iv-user (로그인 ID)
            idx_empno=env_int("SWP_IDX_EMPNO", 1),              # sp_empno (사번)
            idx_display_name=env_int("SWP_IDX_DISPLAYNAME", 8),  # displayname (영문성명)
            idx_mail=env_int("SWP_IDX_MAIL", 9),                # mail
            idx_dept=env_int("SWP_IDX_DEPT", 4),                # seealso (부서명)
            email_fallback_domain=env_str("SWP_EMAIL_FALLBACK_DOMAIN", default="posco.local"),
            timeout_s=env_int("SWP_SSO_TIMEOUT_S", 15),
        )


def callback_allowlist() -> list[str]:
    """콜백으로 되돌아갈 수 있는 Origin 목록.

    비어 있으면 loopback(개발 환경)만 허용한다. Open Redirect 방지를 위해
    허용 목록 밖의 URL 은 거부한다 (ENT-AUTHZ-002).
    """
    return env_list("AUTH_CALLBACK_ALLOWLIST", default=[])


def is_allowed_callback(url: str) -> bool:
    """콜백 URL 이 허용 Origin 에 속하는지 검사한다."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False

    allow = callback_allowlist()
    if not allow:
        # 설정이 없으면 로컬 개발만 허용한다 — 기본값이 열려 있으면 안 된다.
        return parsed.hostname in ("localhost", "127.0.0.1", "::1")

    origin = f"{parsed.scheme}://{parsed.netloc}"
    return any(origin == entry.rstrip("/") for entry in allow)
