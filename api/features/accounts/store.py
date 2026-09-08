"""사용자 저장소와 승인 상태.

기준 구현(local-msaez `data-gateway/src/oauth/users.js`)과 **같은 모양**을 쓴다 —
행 하나에 `value JSONB`, 조회에 쓰는 것만 generated column. 화면과 흐름을 옮겨올
때 필드 이름이 어긋나지 않게 하려는 것이다.

**다른 것은 식별자다.** 기준은 Gitea 계정이라 이메일이 사실상의 키이고 uid 는
push-id 다. 우리는 사내망이고 SWP 가 사번을 준다. 이메일은 없을 수도 있어
기준조차 `SWP_EMAIL_FALLBACK_DOMAIN` 으로 합성한다 — 없을 수 있는 값을 키로 쓰면
안 된다. 그래서 **uid = 사번**이고, 이것이 그대로 Postgres role 이름
(`p_<사번>`)의 근거가 된다.

표는 그래프와 **같은 데이터베이스**(`og`)의 `public` 스키마에 둔다. 사용자·권한·
감사가 한 트랜잭션 경계 안에 있으면 "누가 무엇을 했는가"가 조인 한 번이 된다.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from api.platform import pg

__all__ = [
    "ensure_schema", "get_user", "find_by_email", "list_users",
    "list_by_status", "set_status", "upsert_from_sso",
    "resolve_status", "is_approved", "resolve_role", "is_admin",
    "approval_enabled", "bootstrap_admins",
    "STATUS_APPROVED", "STATUS_PENDING", "STATUS_REJECTED",
    "ROLE_ADMIN", "ROLE_MEMBER",
]

STATUS_APPROVED = "approved"
STATUS_PENDING = "pending"
STATUS_REJECTED = "rejected"
VALID_STATUSES = (STATUS_APPROVED, STATUS_PENDING, STATUS_REJECTED)

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"

# status 는 generated column 이라 값이 없어도 'approved' 로 읽힌다. 이 기능을
# 켜기 전에 쓰던 사용자가 잠기지 않게 하려는 것이고, 기준도 같은 판단을 한다.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS public.app_users (
    uid         TEXT PRIMARY KEY,
    value       JSONB NOT NULL DEFAULT '{}'::jsonb,
    email       TEXT GENERATED ALWAYS AS (value->>'email') STORED,
    status      TEXT GENERATED ALWAYS AS (coalesce(value->>'status', 'approved')) STORED,
    role        TEXT GENERATED ALWAYS AS (coalesce(value->>'role', 'member')) STORED,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_app_users_email
    ON public.app_users (email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_app_users_status ON public.app_users (status);
"""


def ensure_schema() -> None:
    """표가 없으면 만든다. 여러 번 불러도 안전하다."""
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_user(row: dict[str, Any]) -> dict[str, Any]:
    """행을 사용자 dict 로. `value` 를 펼치고 uid 를 덮어쓰지 못하게 한다."""
    value = dict(row.get("value") or {})
    value.pop("uid", None)
    return {"uid": row["uid"], **value}


# ── 상태·역할 판정 ────────────────────────────────────────────────────
# 저장된 값이 없을 때의 기본을 한 곳에서 정한다. 호출부마다 다르게 기본값을
# 정하면 어떤 경로는 잠기고 어떤 경로는 열린다.

def resolve_status(user: Optional[dict[str, Any]]) -> str:
    return (user or {}).get("status") or STATUS_APPROVED


def is_approved(user: Optional[dict[str, Any]]) -> bool:
    return resolve_status(user) == STATUS_APPROVED


def resolve_role(user: Optional[dict[str, Any]]) -> str:
    return (user or {}).get("role") or ROLE_MEMBER


def is_admin(user: Optional[dict[str, Any]]) -> bool:
    return resolve_role(user) == ROLE_ADMIN


# 저장 이름 ← SWP 신원 이름. 한 곳에만 둔다.
_IDENTITY_FIELDS = (
    ("loginId", "username"),
    ("email", "email"),
    ("displayName", "name"),
    ("department", "department"),
)


def _admin_ids() -> list[str]:
    """관리자로 부트스트랩할 사번 목록."""
    raw = os.environ.get("ADMIN_EMPLOYEE_NOS", "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def approval_enabled() -> bool:
    """승인제 스위치.

    관리자를 한 명도 지정하지 않고 승인제를 켜면 **아무도 승인할 수 없어 전원이
    잠긴다.** 그래서 관리자가 지정된 경우에만 켜지게 한다 — 기준도 같은 이유로
    `adminEmails` 유무로 판정한다.
    """
    explicit = os.environ.get("AUTH_APPROVAL_REQUIRED", "").strip().lower()
    if explicit in ("1", "true", "yes"):
        return bool(_admin_ids())
    if explicit in ("0", "false", "no"):
        return False
    return bool(_admin_ids())


# ── 조회 ─────────────────────────────────────────────────────────────

def get_user(uid: str) -> Optional[dict[str, Any]]:
    rows = pg.query("SELECT uid, value FROM public.app_users WHERE uid = %s", (uid,))
    return _row_to_user(rows[0]) if rows else None


def find_by_email(email: str) -> Optional[dict[str, Any]]:
    if not email:
        return None
    rows = pg.query("SELECT uid, value FROM public.app_users WHERE email = %s", (email,))
    return _row_to_user(rows[0]) if rows else None


def list_users() -> list[dict[str, Any]]:
    rows = pg.query(
        "SELECT uid, value FROM public.app_users ORDER BY created_at DESC, uid"
    )
    return [_row_to_user(r) for r in rows]


def list_by_status(status: str) -> list[dict[str, Any]]:
    rows = pg.query(
        "SELECT uid, value FROM public.app_users WHERE status = %s "
        "ORDER BY created_at DESC, uid",
        (status,),
    )
    return [_row_to_user(r) for r in rows]


# ── 변경 ─────────────────────────────────────────────────────────────

def _write(uid: str, value: dict[str, Any]) -> dict[str, Any]:
    value = {k: v for k, v in value.items() if k != "uid"}
    pg.execute(
        "INSERT INTO public.app_users (uid, value) VALUES (%s, %s::jsonb) "
        "ON CONFLICT (uid) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
        (uid, json.dumps(value, ensure_ascii=False)),
    )
    return {"uid": uid, **value}


def set_status(uid: str, status: str) -> Optional[dict[str, Any]]:
    """승인·거절. 없는 사용자는 만들지 않는다 — 오타로 유령 계정이 생긴다."""
    if status not in VALID_STATUSES:
        raise ValueError(f"알 수 없는 상태: {status}")
    existing = get_user(uid)
    if existing is None:
        return None
    value = {k: v for k, v in existing.items() if k != "uid"}
    value["status"] = status
    value["statusUpdatedAt"] = _now()
    return _write(uid, value)


def set_role(uid: str, role: str) -> Optional[dict[str, Any]]:
    if role not in (ROLE_ADMIN, ROLE_MEMBER):
        raise ValueError(f"알 수 없는 역할: {role}")
    existing = get_user(uid)
    if existing is None:
        return None
    value = {k: v for k, v in existing.items() if k != "uid"}
    value["role"] = role
    value["roleUpdatedAt"] = _now()
    return _write(uid, value)


def upsert_from_sso(identity: dict[str, Any]) -> dict[str, Any]:
    """SSO 가 확인해 준 신원으로 사용자를 만들거나 갱신한다.

    `identity` 는 `api.features.auth.swp` 의 `SwpIdentity.to_dict()` 결과다 —
    `{id, username, name, email, department, empno}`. 그쪽 이름을 그대로 받아
    번역 계층을 하나 더 만들지 않는다.

    **기존 사용자의 상태와 역할은 로그인으로 바뀌지 않는다.** 재로그인이 승인을
    되돌리거나 관리자 지정을 덮으면 권한 관리가 성립하지 않는다. 다만 환경변수로
    지정한 관리자는 매번 다시 보장한다 — 관리자를 잃으면 아무도 승인할 수 없다.
    """
    uid = str(identity.get("empno") or identity.get("id") or "").strip()
    if not uid:
        raise ValueError("사번도 로그인 ID 도 없다 — 사용자 식별자를 만들 수 없다")

    admin = uid in _admin_ids()
    existing = get_user(uid)
    now = _now()

    if existing is not None:
        value = {k: v for k, v in existing.items() if k != "uid"}
        # 이름·부서·이메일은 인사 이동으로 바뀌므로 최신 값을 따른다.
        for stored, incoming in _IDENTITY_FIELDS:
            if identity.get(incoming):
                value[stored] = identity[incoming]
        value["lastSignIn"] = now
        if admin:
            value["role"] = ROLE_ADMIN
            value["status"] = STATUS_APPROVED
        else:
            value.setdefault("role", ROLE_MEMBER)
            value.setdefault("status", STATUS_APPROVED)  # 도입 전 사용자는 잠그지 않는다
        return _write(uid, value)

    status = STATUS_APPROVED if admin or not approval_enabled() else STATUS_PENDING
    value = {
        "employeeNo": uid,
        **{stored: identity.get(incoming) for stored, incoming in _IDENTITY_FIELDS},
        "role": ROLE_ADMIN if admin else ROLE_MEMBER,
        "status": status,
        "created": now,
        "lastSignIn": now,
    }
    return _write(uid, value)


def bootstrap_admins() -> list[str]:
    """환경변수로 지정된 관리자를 미리 만들어 둔다.

    첫 관리자가 로그인하기 전에도 승인 대기자가 쌓일 수 있고, 그때 관리자 계정이
    없으면 목록을 볼 사람이 없다. 사번만 아는 상태이므로 나머지는 비워 둔다.
    """
    made = []
    for uid in _admin_ids():
        if get_user(uid) is None:
            _write(uid, {
                "employeeNo": uid,
                "role": ROLE_ADMIN,
                "status": STATUS_APPROVED,
                "created": _now(),
                "bootstrapped": True,
            })
            made.append(uid)
        else:
            set_role(uid, ROLE_ADMIN)
    return made
