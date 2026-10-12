"""중앙 DB의 계정·정책. 스키마/최초 지정은 서버 운영 명령에서만 한다."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from api.platform import pg

STATUS_APPROVED = "approved"
STATUS_PENDING = "pending"
STATUS_REJECTED = "rejected"
VALID_STATUSES = (STATUS_APPROVED, STATUS_PENDING, STATUS_REJECTED)
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS public.app_users (
    uid TEXT PRIMARY KEY, value JSONB NOT NULL DEFAULT '{}'::jsonb,
    email TEXT GENERATED ALWAYS AS (value->>'email') STORED,
    status TEXT GENERATED ALWAYS AS (coalesce(value->>'status', 'approved')) STORED,
    role TEXT GENERATED ALWAYS AS (coalesce(value->>'role', 'member')) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_app_users_email
    ON public.app_users (email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_app_users_status ON public.app_users (status);
CREATE TABLE IF NOT EXISTS public.app_auth_policy (
    id SMALLINT PRIMARY KEY CHECK (id = 1), initialized BOOLEAN NOT NULL DEFAULT false,
    approval_required BOOLEAN NOT NULL DEFAULT true, revision BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_by TEXT
);
INSERT INTO public.app_auth_policy (id) VALUES (1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS public.app_account_audit (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('user', 'operator')),
    actor_id TEXT NOT NULL, target_uid TEXT, action TEXT NOT NULL,
    before_value JSONB, after_value JSONB, reason TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(), request_id TEXT
);
"""


class AuthorityNotInitialized(RuntimeError):  # noqa: N818
    """운영자가 최초 관리자를 등록하지 않았다."""


class AccountChangeDenied(RuntimeError):  # noqa: N818
    """현재 권한 또는 마지막 관리자 보존 규칙으로 거절됐다."""


def ensure_schema() -> None:
    """서버 운영 명령 전용. 로그인/관리자 요청에서 호출하지 않는다."""
    with pg.connection() as conn, conn.cursor() as cur:
        cur.execute(_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_user(row: dict[str, Any]) -> dict:
    value = dict(row.get("value") or {})
    value.pop("uid", None)
    return {"uid": row["uid"], **value}


def resolve_status(user: dict | None) -> str:
    return (user or {}).get("status") or STATUS_PENDING


def is_approved(user: dict | None) -> bool:
    return resolve_status(user) == STATUS_APPROVED


def resolve_role(user: dict | None) -> str:
    return (user or {}).get("role") or ROLE_MEMBER


def is_admin(user: dict | None) -> bool:
    return resolve_role(user) == ROLE_ADMIN


def get_policy() -> dict:
    rows = pg.query("SELECT * FROM public.app_auth_policy WHERE id = 1")
    if not rows:
        raise AuthorityNotInitialized("서버에서 계정 정책을 초기화해야 합니다.")
    return rows[0]


def approval_enabled() -> bool:
    return bool(get_policy()["approval_required"])


def require_initialized() -> None:
    if not get_policy()["initialized"]:
        raise AuthorityNotInitialized("서버 운영자가 최초 관리자를 지정해야 합니다.")


def get_user(uid: str) -> dict | None:
    rows = pg.query("SELECT uid, value FROM public.app_users WHERE uid = %s", (uid,))
    return _row_to_user(rows[0]) if rows else None


def find_by_email(email: str) -> dict | None:
    if not email:
        return None
    rows = pg.query("SELECT uid, value FROM public.app_users WHERE email = %s", (email,))
    return _row_to_user(rows[0]) if rows else None


def list_users() -> list[dict]:
    return [_row_to_user(row) for row in pg.query(
        "SELECT uid, value FROM public.app_users ORDER BY created_at DESC, uid")]


def list_by_status(status: str) -> list[dict]:
    return [_row_to_user(row) for row in pg.query(
        "SELECT uid, value FROM public.app_users WHERE status = %s "
        "ORDER BY created_at DESC, uid", (status,))]


def _locked_policy(cur) -> dict:
    cur.execute("SELECT * FROM public.app_auth_policy WHERE id = 1 FOR UPDATE")
    policy = cur.fetchone()
    if not policy:
        raise AuthorityNotInitialized("서버에서 계정 정책을 초기화해야 합니다.")
    return policy


def _audit(cur, actor_type, actor_id, uid, action, before, after, reason, request_id):
    cur.execute(
        "INSERT INTO public.app_account_audit "
        "(actor_type, actor_id, target_uid, action, before_value, after_value, reason, request_id) "
        "VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)",
        (actor_type, actor_id, uid, action, json.dumps(before, ensure_ascii=False),
         json.dumps(after, ensure_ascii=False), reason, request_id))


def _check_actor(cur, actor_uid: str) -> None:
    cur.execute("SELECT uid, value FROM public.app_users WHERE uid = %s", (actor_uid,))
    row = cur.fetchone()
    user = _row_to_user(row) if row else None
    if not is_admin(user) or not is_approved(user):
        raise AccountChangeDenied("승인된 관리자만 변경할 수 있습니다.")


def _preserve_admin(cur) -> None:
    cur.execute("SELECT count(*) AS n FROM public.app_users "
                "WHERE value->>'role' = 'admin' AND value->>'status' = 'approved'")
    if not cur.fetchone()["n"]:
        raise AccountChangeDenied("마지막 승인된 관리자는 해제하거나 거절할 수 없습니다.")


def _change(uid: str, fields: dict, *, actor_uid: str, reason: str,
            operator: bool = False, request_id: str | None = None, create: bool = False):
    if not uid.strip() or not actor_uid.strip() or not reason.strip():
        raise ValueError("사번·변경자·변경 사유가 필요합니다.")
    with pg.connection() as conn, conn.cursor() as cur:
        policy = _locked_policy(cur)
        if not operator:
            if not policy["initialized"]:
                raise AuthorityNotInitialized("서버 운영자가 최초 관리자를 지정해야 합니다.")
            _check_actor(cur, actor_uid)
            if uid == actor_uid:
                raise AccountChangeDenied("자기 계정의 역할·상태는 바꿀 수 없습니다.")
        cur.execute("SELECT uid, value FROM public.app_users WHERE uid = %s FOR UPDATE", (uid,))
        row = cur.fetchone()
        if not row and not create:
            return None
        before = dict(row["value"]) if row else None
        if policy["initialized"] and before is not None and all(before.get(k) == v for k, v in fields.items()):
            return {"uid": uid, **before}
        after = dict(before or {"employeeNo": uid, "created": _now()})
        after.update(fields)
        for key in fields:
            after[key + "UpdatedAt"] = _now()
        cur.execute(
            "INSERT INTO public.app_users (uid, value) VALUES (%s, %s::jsonb) "
            "ON CONFLICT (uid) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
            (uid, json.dumps(after, ensure_ascii=False)))
        _preserve_admin(cur)
        if operator and not policy["initialized"]:
            # 환경변수에서 만들어진 기존 관리자를 자동 신뢰하지 않는다.
            cur.execute("UPDATE public.app_users SET value = jsonb_set(value, '{role}', "
                        "'\"member\"'::jsonb), updated_at = now() "
                        "WHERE uid <> %s AND value->>'role' = 'admin' RETURNING uid", (uid,))
            for old in cur.fetchall():
                _audit(cur, "operator", actor_uid, old["uid"], "legacy_admin_revoked",
                       {"role": ROLE_ADMIN}, {"role": ROLE_MEMBER}, reason, request_id)
            cur.execute("UPDATE public.app_auth_policy SET initialized = true, "
                        "revision = revision + 1, updated_at = now(), updated_by = %s WHERE id = 1",
                        (actor_uid,))
        _audit(cur, "operator" if operator else "user", actor_uid, uid, "account_changed",
               before, after, reason, request_id)
        return {"uid": uid, **after}


def set_status(uid: str, status: str, *, actor_uid: str, reason: str = "사용자 승인 상태 변경",
               request_id: str | None = None) -> dict | None:
    if status not in VALID_STATUSES:
        raise ValueError(f"알 수 없는 상태: {status}")
    return _change(uid, {"status": status}, actor_uid=actor_uid, reason=reason,
                   request_id=request_id)


def set_role(uid: str, role: str, *, actor_uid: str, reason: str = "사용자 역할 변경",
             request_id: str | None = None) -> dict | None:
    if role not in (ROLE_ADMIN, ROLE_MEMBER):
        raise ValueError(f"알 수 없는 역할: {role}")
    return _change(uid, {"role": role}, actor_uid=actor_uid, reason=reason,
                   request_id=request_id)


def operator_grant(uid: str, *, operator_id: str, reason: str) -> dict:
    return _change(uid, {"role": ROLE_ADMIN, "status": STATUS_APPROVED},
                   actor_uid=operator_id, reason=reason, operator=True, create=True)


def operator_revoke(uid: str, *, operator_id: str, reason: str) -> dict | None:
    return _change(uid, {"role": ROLE_MEMBER}, actor_uid=operator_id,
                   reason=reason, operator=True)


def set_policy(approval_required: bool, *, operator_id: str, reason: str) -> dict:
    if not operator_id.strip() or not reason.strip():
        raise ValueError("변경자·변경 사유가 필요합니다.")
    with pg.connection() as conn, conn.cursor() as cur:
        before = _locked_policy(cur)
        if not before["initialized"]:
            raise AuthorityNotInitialized("먼저 최초 관리자를 지정해야 합니다.")
        _preserve_admin(cur)
        cur.execute("UPDATE public.app_auth_policy SET approval_required = %s, "
                    "revision = revision + 1, updated_at = now(), updated_by = %s "
                    "WHERE id = 1 RETURNING approval_required, revision",
                    (approval_required, operator_id))
        after = cur.fetchone()
        _audit(cur, "operator", operator_id, None, "policy_changed",
               {"approval_required": before["approval_required"], "revision": before["revision"]},
               after, reason, None)
        return after


_IDENTITY_FIELDS = (("loginId", "username"), ("email", "email"),
                    ("displayName", "name"), ("department", "department"))


def upsert_from_sso(identity: dict[str, Any]) -> dict:
    """신원 필드만 원자적으로 갱신. 기존 권한을 되살리지 않는다."""
    uid = str(identity.get("empno") or identity.get("id") or "").strip()
    if not uid:
        raise ValueError("사용자 식별자가 없습니다.")
    profile = {stored: identity[incoming] for stored, incoming in _IDENTITY_FIELDS
               if identity.get(incoming)}
    profile["lastSignIn"] = _now()
    with pg.connection() as conn, conn.cursor() as cur:
        policy = _locked_policy(cur)
        if not policy["initialized"]:
            raise AuthorityNotInitialized("서버 운영자가 최초 관리자를 지정해야 합니다.")
        initial = {"employeeNo": uid, "role": ROLE_MEMBER, "created": _now(),
                   "status": STATUS_PENDING if policy["approval_required"] else STATUS_APPROVED,
                   **profile}
        cur.execute(
            "INSERT INTO public.app_users (uid, value) VALUES (%s, %s::jsonb) "
            "ON CONFLICT (uid) DO UPDATE SET value = app_users.value || %s::jsonb, "
            "updated_at = now() RETURNING uid, value",
            (uid, json.dumps(initial, ensure_ascii=False), json.dumps(profile, ensure_ascii=False)))
        return _row_to_user(cur.fetchone())
