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

__all__ = ["role_name", "role_password", "ensure_role", "role_exists", "role_secret_configured"]

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


def _secret_raw() -> str:
    # 전용 비밀이 없으면 세션 비밀을 쓴다. 둘을 나누는 편이 낫지만, 하나만 두고
    # 쓰다가 role 비밀번호가 임시값으로 만들어지는 쪽이 더 나쁘다.
    return (os.environ.get("AUTH_ROLE_SECRET") or os.environ.get("AUTH_JWT_SECRET") or "").strip()


def role_password(uid: str) -> str:
    secret = _secret_raw()
    if not secret:
        raise RuntimeError(
            "AUTH_ROLE_SECRET(또는 AUTH_JWT_SECRET)이 없어 role 비밀번호를 만들 수 없다"
        )
    digest = hmac.new(secret.encode(), (uid or "").encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def role_exists(name: str) -> bool:
    return bool(pg.query("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,)))


def ensure_role(uid: str) -> str:
    """사용자 role 이 있게 만든다. 이미 있으면 비밀번호만 다시 건다.

    비밀번호를 매번 다시 거는 이유는 **비밀이 바뀌었을 때 스스로 따라오게**
    하기 위해서다. 안 그러면 붙지 못하는 사용자가 조용히 생긴다.
    """
    name = role_name(uid)
    password = role_password(uid)
    ident = sql.Identifier(name)
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
