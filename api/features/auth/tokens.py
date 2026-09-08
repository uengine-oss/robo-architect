"""세션 토큰 발급과 검증.

SSO 는 "이 사람이 누구인가"만 답한다. 그 뒤 모든 요청이 스스로를 증명하려면
서버가 발급한 토큰이 필요하다 — 지금은 그게 없어서 `/api/auth/sso/valid` 가
신원을 확인해 주고도 아무 데도 쓰이지 않는다.

**승인 상태와 역할을 클레임에 싣는다.** 기준 구현(local-msaez `oauth/routes.js`)이
같은 판단을 했고 이유도 같다 — 요청마다 사용자 표를 읽지 않기 위해서다. 대신
승인이 바뀌면 토큰이 낡으므로, 상태를 바꾸는 쪽이 짧은 만료로 이를 흡수한다.
"""

from __future__ import annotations

import os
import secrets
import time
from typing import Any, Optional

import jwt

from api.platform.observability.smart_logger import SmartLogger

__all__ = [
    "issue_token", "verify_token", "token_ttl_seconds",
    "jwt_secret_configured", "TokenError",
]

ALGORITHM = "HS256"
_DEFAULT_TTL = 8 * 60 * 60  # 8시간 — 근무 하루

# 비밀이 설정되지 않았을 때 쓰는 임시 값. 프로세스마다 달라 재시작하면 토큰이
# 전부 무효해진다. 개발 편의를 위한 것이고, 강제 모드에서는 이 길로 오지 않는다.
_EPHEMERAL_SECRET = secrets.token_urlsafe(48)
_warned_ephemeral = False


class TokenError(RuntimeError):
    """토큰이 없거나, 만료됐거나, 서명이 맞지 않는다."""


def jwt_secret_configured() -> bool:
    return bool((os.environ.get("AUTH_JWT_SECRET") or "").strip())


def _secret() -> str:
    configured = (os.environ.get("AUTH_JWT_SECRET") or "").strip()
    if configured:
        return configured
    global _warned_ephemeral
    if not _warned_ephemeral:
        _warned_ephemeral = True
        SmartLogger.log(
            "WARN",
            "AUTH_JWT_SECRET 이 없어 임시 비밀로 토큰을 발급한다. "
            "재시작하면 모든 세션이 끊긴다 — 배포 전에 반드시 설정할 것.",
            category="auth.token.ephemeral_secret",
        )
    return _EPHEMERAL_SECRET


def token_ttl_seconds() -> int:
    raw = (os.environ.get("AUTH_SESSION_TTL_SECONDS") or "").strip()
    try:
        ttl = int(raw)
    except ValueError:
        return _DEFAULT_TTL
    return ttl if ttl > 0 else _DEFAULT_TTL


def issue_token(user: dict[str, Any], source: str = "swp") -> str:
    """사용자 한 명에게 세션 토큰을 준다.

    `source` 는 어떤 경로로 로그인했는지다 — `swp` 또는 `dev`. 감사에서 개발용
    우회 로그인을 구분할 수 있어야 하므로 토큰 안에 남긴다.
    """
    now = int(time.time())
    payload = {
        "sub": str(user.get("uid") or ""),
        "role": user.get("role") or "member",
        "approved": (user.get("status") or "approved") == "approved",
        "name": user.get("displayName") or user.get("loginId") or "",
        "dept": user.get("department") or "",
        "email": user.get("email") or "",
        "src": source,
        "iat": now,
        "exp": now + token_ttl_seconds(),
    }
    if not payload["sub"]:
        raise ValueError("uid 가 없는 사용자에게는 토큰을 발급하지 않는다")
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def verify_token(token: Optional[str]) -> dict[str, Any]:
    """토큰을 검증해 클레임을 돌려준다. 실패는 전부 `TokenError` 다.

    실패 사유를 구분해 던지지 않는다 — 만료인지 위조인지 알려 주면 공격자에게
    단서가 된다. 로그에는 남긴다.
    """
    if not token:
        raise TokenError("토큰이 없다")
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("세션이 만료됐다") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("토큰이 유효하지 않다") from exc
