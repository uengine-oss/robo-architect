"""사용자 한 명 = Postgres role 하나.

`og_grant(role, level, graph)` 는 role 에 권한을 준다. 그래서 사용자를 role 로
만들어 두어야 공유가 성립한다.

**비밀번호는 저장하지 않고 유도한다.** Bolt 게이트웨이는 드라이버가 준 자격을
그대로 Postgres 인증에 쓰므로, 서버가 사용자 role 로 붙으려면 비밀번호를 알아야
한다. 저장하면 그것대로 지켜야 할 비밀이 하나 늘고 유출 경로가 생긴다. 서버
비밀 하나에서 사번마다 결정적으로 만들어 내면 보관할 것이 없다.

```
role      p_<사번>                       사번의 안전한 문자만 남긴다
비밀번호   HMAC-SHA256(AUTH_ROLE_SECRET, 사번)
```

> **비밀을 바꾸면 모든 role 의 비밀번호를 다시 걸어야 한다.** 바꾸는 일이
> 드물고, 다시 거는 것은 `ensure_role` 을 전원에 대해 한 번 도는 일이다.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re

from psycopg import sql

from api.platform import pg

__all__ = ["role_name", "role_password", "ensure_role", "role_exists",
           "role_secret_configured", "central_mode", "RoleSecretMismatch"]


class RoleSecretMismatch(RuntimeError):
    """이 PC 의 `AUTH_ROLE_SECRET` 이 DB 에 걸린 것과 다르다.

    **덮어쓰지 않고 멈춘다.** 덮으면 그 사용자가 다른 PC 에서 못 붙는다.
    """

_SAFE = re.compile(r"[^a-z0-9_]+")


def role_name(uid: str) -> str:
    """사번에서 role 이름을 만든다.

    Postgres 식별자로 안전한 문자만 남기고 소문자로 접는다. 사번이 통째로
    걸러지는 경우(전부 특수문자)는 식별자가 겹칠 수 있으므로 해시를 덧붙인다.
    """
    raw = (uid or "").strip().lower()
    if not raw:
        raise ValueError("uid 가 비었다 — role 이름을 만들 수 없다")
    slug = _SAFE.sub("_", raw).strip("_")
    if not slug or slug == "_":
        slug = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"p_{slug[:56]}"


def role_secret_configured() -> bool:
    return bool(_secret_raw())


def central_mode() -> bool:
    """그래프 저장소가 **사내 서버 한 대**에 있고 여러 PC 가 함께 쓰는 구성인가.

    `docker-stack.ts` 가 계산해 백엔드 환경에 실어 준다. 모르면 단일 PC 로 본다 —
    모르는 상태에서 중앙으로 가정하면 1인 사용자가 기동을 못 한다.
    """
    return (os.environ.get("ROBO_GRAPH_MODE") or "").strip().lower() == "central"


def _secret_raw() -> str:
    """role 비밀번호의 씨앗.

    **중앙 모드에서는 전용값만 받는다.** 단일 PC 에서는 세션 비밀로 대체한다 —
    하나만 두고 쓰다가 role 비밀번호가 임시값으로 만들어지는 쪽이 더 나쁘기
    때문이다. 중앙에서는 반대다: `AUTH_JWT_SECRET` 은 "바꿔도 재로그인하면 그만"
    이라 가볍게 바뀌는데, 그걸 씨앗으로 쓰면 **전원의 DB 비밀번호가 같이 바뀐다.**
    """
    dedicated = (os.environ.get("AUTH_ROLE_SECRET") or "").strip()
    if dedicated or central_mode():
        return dedicated
    return (os.environ.get("AUTH_JWT_SECRET") or "").strip()


def role_password(uid: str) -> str:
    secret = _secret_raw()
    if not secret:
        if central_mode():
            raise RuntimeError(
                "중앙 DB 구성인데 AUTH_ROLE_SECRET 이 없다. "
                "이 값은 **모든 PC 가 같아야** 하고, AUTH_JWT_SECRET 으로 대신할 수 없다 "
                "— 그걸 쓰면 세션 비밀을 바꿀 때 전원의 DB 비밀번호가 같이 바뀐다."
            )
        raise RuntimeError(
            "AUTH_ROLE_SECRET(또는 AUTH_JWT_SECRET)이 없어 role 비밀번호를 만들 수 없다"
        )
    digest = hmac.new(secret.encode(), (uid or "").encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def role_exists(name: str) -> bool:
    return bool(pg.query("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,)))


def _can_login(name: str, password: str) -> bool:
    """그 role 로 실제로 붙어 본다 — 유도한 비밀번호가 DB 와 맞는가.

    맞는지 확인할 길이 이것뿐이다. Postgres 는 비밀번호를 해시로만 들고 있고,
    우리가 쓰는 것도 해시 유도값이라 비교해 볼 평문이 양쪽에 없다.
    """
    import psycopg

    from api.platform.pg import pg_dsn

    dsn = pg_dsn()
    # 사용자와 비밀번호만 갈아 끼운다. 나머지(host/port/dbname)는 그대로 쓴다.
    parts = [p for p in dsn.split(" ")
             if p and not p.startswith(("user=", "password="))]
    parts += [f"user={name}", f"password={password}"]
    try:
        with psycopg.connect(" ".join(parts), connect_timeout=5):
            return True
    except psycopg.OperationalError:
        # 비밀번호 불일치뿐 아니라 "붙을 권한이 없다" 도 여기로 온다. 둘 다
        # **덮어쓰면 안 되는** 경우이므로 구별하지 않는다.
        return False


def ensure_role(uid: str) -> str:
    """사용자 role 이 있게 만든다. 이미 있으면 비밀번호만 다시 건다.

    비밀번호를 매번 다시 거는 이유는 **비밀이 바뀌었을 때 스스로 따라오게**
    하기 위해서다. 안 그러면 붙지 못하는 사용자가 조용히 생긴다.
    """
    name = role_name(uid)
    password = role_password(uid)
    ident = sql.Identifier(name)

    # **중앙 DB 에서는 이미 있는 role 을 건드리지 않는다.** 아래 ALTER 는 단일 PC
    # 에서 "비밀이 바뀌면 따라오게" 하는 장치인데, 여럿이 쓰는 저장소에서는 비밀을
    # 잘못 넣은 PC 한 대가 그 사용자를 **다른 모든 PC 에서** 끊어 버리는 경로가 된다.
    if central_mode() and role_exists(name):
        if _can_login(name, password):
            return name
        raise RoleSecretMismatch(
            f"이 PC 의 AUTH_ROLE_SECRET 이 '{name}' 에 걸린 것과 다르다. "
            "비밀번호를 덮어쓰지 않고 멈춘다 — 덮으면 이 사용자가 다른 PC 에서 "
            "못 붙는다. 이 PC 의 값을 다른 PC 와 맞춰라."
        )

    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
            if cur.fetchone():
                cur.execute(
                    sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                        ident, sql.Literal(password)))
            else:
                cur.execute(
                    sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                        ident, sql.Literal(password)))
    return name
