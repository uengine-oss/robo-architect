"""SWP(POSCO) SSO 클라이언트.

기준 구현: `local-msaez` `platform/data-gateway/src/oauth/swp.js`.

OIDC 가 아니라 **SWP HTTP 인증 토큰 방식**이다. authorization-code flow 가
아니므로 표준 OAuth 라이브러리를 쓸 수 없다.

    1) 사용자를 SWP `redirect.jsp` 로 보내 로그인시킨다.
    2) SWP 가 우리 콜백으로 `ssoToken` 을 전달한다(보통 form POST, 환경에 따라 GET).
    3) `isValidSSO.jsp` 에 `Cookie: SWP-H-SESSION-ID` 로 재검증해 사용자정보(CSV)를 받는다.

응답 파싱은 순수 함수(`parse_user_info`)로 분리했다. 현장 필드 드리프트 대응이
이 로직의 핵심이라 네트워크 없이 검증할 수 있어야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote

from api.features.auth.config import SwpSettings

# 미인증 응답의 첫 필드 (POSCO 샘플 코드 기준).
UNAUTHENTICATED = "Unauthenticated"


@dataclass(frozen=True)
class SwpUser:
    """정규화된 SWP 사용자.

    `id` 는 사번을 우선 쓴다 — 이메일이나 로그인 ID 와 달리 바뀔 가능성이 낮아
    사내 고유키로 안전하다.
    """

    id: str
    username: str
    name: str
    email: str | None
    department: str
    empno: str
    source: str = "swp"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "email": self.email,
            "department": self.department,
            "empno": self.empno,
            "source": self.source,
        }


def build_redirect_url(settings: SwpSettings, callback_url: str) -> str:
    """SWP 로그인 페이지로 보낼 URL. 콜백 주소를 인코딩해 붙인다."""
    return settings.redirect_url + quote(callback_url, safe="")


def _decode(value: str) -> str:
    try:
        return unquote(value)
    except Exception:
        return value


def parse_user_info(raw: str, settings: SwpSettings) -> SwpUser | None:
    """`isValidSSO` 응답(콤마 구분)을 정규화한다. 미인증이면 None.

    ## 필드 드리프트 대응 (기준 구현의 현장 대응을 그대로 가져옴)

    스펙 표상 인덱스는 `0=iv-user, 1=sp_empno, 4=seealso, 8=displayname, 9=mail`
    이지만, 현장 피드가 필드 하나 더 밀려 오는 사례가 있다(idx 8 이 빈 값으로
    들어와 displayname/mail 이 +1 어긋남). 그래서 이 둘만 인덱스에 의존하지
    않는다.

    - **이메일**: `@` 를 포함한 토큰을 직접 찾는다. 없으면 설정 인덱스 → 사번 합성.
    - **영문성명**: 스펙상 mail 바로 앞 필드이므로 이메일 토큰의 앞 토큰을 쓴다.
      SWP 가 URL 인코딩해 보내므로 디코드한다.

    사번(1)과 로그인 ID(0)는 드리프트 지점 앞이라 인덱스 고정이 안전하다.
    """
    if raw is None:
        return None

    parts = [p.strip() for p in raw.split(",")]
    if not parts or not parts[0] or parts[0] == UNAUTHENTICATED:
        return None

    def at(index: int) -> str:
        return parts[index] if 0 <= index < len(parts) else ""

    empno = at(settings.idx_empno)
    login_id = at(settings.idx_id)

    email_idx = next((i for i, p in enumerate(parts) if "@" in p), -1)
    email = parts[email_idx] if email_idx >= 0 else at(settings.idx_mail)
    if not email and empno:
        email = f"{empno}@{settings.email_fallback_domain}"

    if email_idx > 0:
        display_name = _decode(parts[email_idx - 1])
    else:
        display_name = _decode(at(settings.idx_display_name))
    display_name = display_name or login_id or empno

    identifier = empno or login_id
    if not identifier:
        # 사번도 로그인 ID 도 없으면 사용자를 특정할 수 없다. 이메일로 대체하지
        # 않는다 — 불안정한 키로 계정을 만들면 나중에 병합 사고가 난다.
        return None

    return SwpUser(
        id=identifier,
        username=login_id or empno,
        name=display_name,
        email=email or None,
        department=_decode(at(settings.idx_dept)),
        empno=empno,
    )


async def validate_sso_token(settings: SwpSettings, sso_token: str) -> tuple[SwpUser | None, str]:
    """`ssoToken` 을 SWP 에 재검증하고 사용자 정보를 돌려준다.

    Returns:
        (사용자 또는 None, 원문 응답)

    원문을 함께 반환하는 이유: 현장 첫 연동 때 필드 순서를 눈으로 확인해야
    `SWP_IDX_*` 를 맞출 수 있다. 로깅은 호출부가 정책에 따라 결정한다.
    """
    import httpx

    async with httpx.AsyncClient(timeout=settings.timeout_s) as client:
        response = await client.get(
            settings.valid_check_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": f"SWP-H-SESSION-ID={sso_token}",
            },
        )
        raw = response.text

    return parse_user_info(raw, settings), raw
