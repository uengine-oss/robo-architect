"""사내망 밖에서 쓰는 개발용 로그인.

SWP SSO 는 사내망에서만 응답한다. 그래서 SSO 를 강제해 두면 **밖에서는 아무것도
테스트할 수 없다.** 이 우회로는 그 문제 하나만 푼다.

지켜야 할 성질이 넷이다.

```
기본은 꺼짐          AUTH_DEV_LOGIN_ENABLED 를 명시로 켜야만 열린다
루프백만            같은 기계에서만. 열려면 또 하나를 명시로 켜야 한다
눈에 띈다            켜져 있으면 기동 때 경고하고, 쓸 때마다 남긴다
꼬리표가 남는다      토큰과 사용자에 `dev` 표시가 붙어 감사에서 구분된다
```

**절대 하지 않는 것** — 설정이 없을 때 알아서 켜지는 것. 우회로가 조용히 열려
있는 것이 이 기능의 유일한 실패 방식이다.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

__all__ = ["DevLoginSettings", "dev_login_enabled", "is_loopback", "describe"]

_TRUE = ("1", "true", "yes", "on")


def _flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in _TRUE


@dataclass(frozen=True)
class DevLoginSettings:
    enabled: bool
    login_id: str
    password: str
    allow_remote: bool
    employee_no: str
    display_name: str

    @classmethod
    def from_env(cls) -> "DevLoginSettings":
        return cls(
            enabled=_flag("AUTH_DEV_LOGIN_ENABLED"),
            login_id=(os.environ.get("AUTH_DEV_LOGIN_ID") or "test").strip(),
            password=os.environ.get("AUTH_DEV_LOGIN_PASSWORD") or "test",
            allow_remote=_flag("AUTH_DEV_LOGIN_ALLOW_REMOTE"),
            # 사번 자리를 비워 두면 사용자 표에 uid 가 안 생긴다. 실제 사번과
            # 겹치지 않도록 접두사를 붙인다.
            employee_no=(os.environ.get("AUTH_DEV_LOGIN_EMPNO") or "DEV-TEST").strip(),
            display_name=(os.environ.get("AUTH_DEV_LOGIN_NAME") or "개발용 계정").strip(),
        )

    def matches(self, login_id: str, password: str) -> bool:
        """자격 대조. 길이로도 단서를 주지 않도록 상수 시간 비교를 쓴다."""
        ok_id = hmac.compare_digest((login_id or "").encode(), self.login_id.encode())
        ok_pw = hmac.compare_digest((password or "").encode(), self.password.encode())
        return ok_id and ok_pw

    def identity(self) -> dict:
        """`SwpIdentity.to_dict()` 와 같은 모양. 사용자 저장소가 한 길로 받는다."""
        return {
            "id": self.employee_no,
            "empno": self.employee_no,
            "username": self.login_id,
            "name": self.display_name,
            "email": None,
            "department": "개발",
            "source": "dev",
        }


def dev_login_enabled() -> bool:
    return DevLoginSettings.from_env().enabled


def is_loopback(host: str | None) -> bool:
    """요청이 같은 기계에서 왔는가."""
    if not host:
        return False
    return host in ("127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1")


def describe() -> dict:
    """진단용. 비밀번호는 담지 않는다."""
    s = DevLoginSettings.from_env()
    return {
        "enabled": s.enabled,
        "loginId": s.login_id if s.enabled else None,
        "employeeNo": s.employee_no if s.enabled else None,
        "allowRemote": s.allow_remote,
    }
