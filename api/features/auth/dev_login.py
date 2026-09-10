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

계정은 **여럿을 둘 수 있다.** 프로젝트 격리와 공유는 사람이 둘 이상이어야 확인되고,
한 계정만으로는 "남의 프로젝트가 안 보인다"를 잴 수 없다. 브라우저 시크릿 창으로
다른 계정에 들어가 양쪽에서 동시에 작업해 보는 것이 목적이다.

```
AUTH_DEV_LOGIN_ID/PASSWORD/EMPNO/NAME   첫 계정 (기존 그대로)
AUTH_DEV_LOGIN_ACCOUNTS                  추가 계정들
    id:비밀번호:사번:이름:부서  를 `,` 나 개행으로 나열. 뒤 셋은 생략 가능
```
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

__all__ = ["DevLoginSettings", "DevAccount", "dev_login_enabled", "is_loopback",
           "describe", "dev_accounts", "find_account"]

_TRUE = ("1", "true", "yes", "on")


def _flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in _TRUE


@dataclass(frozen=True)
class DevAccount:
    """우회 로그인 계정 하나."""

    login_id: str
    password: str
    employee_no: str
    display_name: str
    department: str = "개발"

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
            "department": self.department,
            "source": "dev",
        }


def _parse_accounts(raw: str) -> list[DevAccount]:
    """`id:비밀번호:사번:이름:부서` 목록을 읽는다.

    비어 있거나 자리가 모자란 항목은 **조용히 건너뛰지 않고 무시하되**, 아이디와
    비밀번호가 둘 다 있어야만 계정으로 친다 — 반쪽짜리 항목이 비밀번호 없는 계정을
    만들면 그게 이 기능의 최악이다.
    """
    out: list[DevAccount] = []
    for chunk in (raw or "").replace("\n", ",").split(","):
        part = chunk.strip()
        if not part:
            continue
        fields = [f.strip() for f in part.split(":")]
        login_id = fields[0] if fields else ""
        password = fields[1] if len(fields) > 1 else ""
        if not login_id or not password:
            continue
        empno = (fields[2] if len(fields) > 2 and fields[2] else f"DEV-{login_id}").upper()
        name = fields[3] if len(fields) > 3 and fields[3] else f"개발용 {login_id}"
        dept = fields[4] if len(fields) > 4 and fields[4] else "개발"
        out.append(DevAccount(login_id, password, empno, name, dept))
    return out


@dataclass(frozen=True)
class DevLoginSettings:
    enabled: bool
    login_id: str
    password: str
    allow_remote: bool
    employee_no: str
    display_name: str
    accounts: tuple[DevAccount, ...] = ()

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
            accounts=tuple(cls._accounts()),
        )

    @staticmethod
    def _accounts() -> list[DevAccount]:
        """첫 계정 + 추가 계정들. 같은 아이디는 **앞의 것이 이긴다.**

        뒤에서 덮어쓰게 두면 추가 목록에 오타 하나로 기본 계정의 비밀번호가 조용히
        바뀐다.
        """
        first = DevAccount(
            login_id=(os.environ.get("AUTH_DEV_LOGIN_ID") or "test").strip(),
            password=os.environ.get("AUTH_DEV_LOGIN_PASSWORD") or "test",
            employee_no=(os.environ.get("AUTH_DEV_LOGIN_EMPNO") or "DEV-TEST").strip(),
            display_name=(os.environ.get("AUTH_DEV_LOGIN_NAME") or "개발용 계정").strip(),
        )
        out = [first]
        seen = {first.login_id}
        for acc in _parse_accounts(os.environ.get("AUTH_DEV_LOGIN_ACCOUNTS", "")):
            if acc.login_id in seen:
                continue
            seen.add(acc.login_id)
            out.append(acc)
        return out

    def find(self, login_id: str, password: str) -> DevAccount | None:
        """맞는 계정 하나. 없으면 None.

        **맞는 것을 찾아도 끝까지 돈다** — 몇 번째에서 멈췄는지가 시간으로 새지
        않게 한다.
        """
        found: DevAccount | None = None
        for acc in self.accounts:
            if acc.matches(login_id, password):
                found = found or acc
        return found

    def matches(self, login_id: str, password: str) -> bool:
        """어느 계정이든 맞으면 참. 옛 호출부를 위해 남겨 둔다."""
        return self.find(login_id, password) is not None

    def identity(self) -> dict:
        """첫 계정의 신원. 옛 호출부를 위해 남겨 둔다."""
        return self.accounts[0].identity() if self.accounts else {}


def dev_login_enabled() -> bool:
    return DevLoginSettings.from_env().enabled


def dev_accounts() -> list[DevAccount]:
    """켜져 있을 때의 계정 목록. 꺼져 있으면 빈 목록이다."""
    s = DevLoginSettings.from_env()
    return list(s.accounts) if s.enabled else []


def find_account(login_id: str, password: str) -> DevAccount | None:
    s = DevLoginSettings.from_env()
    return s.find(login_id, password) if s.enabled else None


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
        # 로그인 화면이 "어떤 계정으로 들어갈 수 있는지"를 보여 준다. 비밀번호는
        # 담지 않는다 — 아이디만으로도 고를 수 있다.
        "accounts": [
            {"loginId": a.login_id, "employeeNo": a.employee_no, "name": a.display_name}
            for a in (s.accounts if s.enabled else ())
        ],
    }
