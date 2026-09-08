"""사용자 저장소와 승인 상태 검사.

실제 Postgres 에 대고 돌린다 — 표가 generated column 과 부분 유니크 인덱스를 쓰므로
가짜 저장소로는 확인이 안 된다.

**실데이터를 건드리지 않는다.** 사번이 `ZZTEST` 로 시작하는 행만 만들고 끝나면
지운다. 지우는 조건을 접두사로 못박아, 조건이 비면 아무것도 지우지 않는다.

    robo-architect/.venv/bin/python scripts/verify_accounts.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from api.platform import pg  # noqa: E402
from api.features.accounts import store  # noqa: E402

PREFIX = "ZZTEST"
failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global failed
    if cond:
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def cleanup() -> int:
    """시험 행만 지운다. 접두사가 비면 아무것도 지우지 않는다."""
    if not PREFIX:
        raise RuntimeError("접두사가 비어 있다 — 전수 삭제를 막는다")
    return pg.execute(
        "DELETE FROM public.app_users WHERE uid LIKE %s", (PREFIX + "%",)
    )


def identity(empno: str, **over) -> dict:
    base = {
        "id": empno, "empno": empno,
        "username": f"user{empno}", "name": f"이름{empno}",
        "email": f"{empno}@posco.local", "department": "인사그룹",
        "source": "swp",
    }
    base.update(over)
    return base


def main() -> int:
    print("\n접속")
    try:
        store.ensure_schema()
        check("표를 만들거나 이미 있다", True)
        store.ensure_schema()
        check("여러 번 불러도 안전하다", True)
    except pg.PgUnavailable as e:
        print(f"  FAIL Postgres 에 붙지 못했다 — {e}")
        return 1

    cleanup()

    print("\n승인제가 꺼져 있을 때")
    os.environ.pop("ADMIN_EMPLOYEE_NOS", None)
    os.environ.pop("AUTH_APPROVAL_REQUIRED", None)
    check("관리자가 없으면 승인제가 꺼진다", store.approval_enabled() is False)
    u = store.upsert_from_sso(identity(PREFIX + "001"))
    check("신규 사용자가 바로 승인된다", store.resolve_status(u) == store.STATUS_APPROVED,
          store.resolve_status(u))
    check("기본 역할은 member", store.resolve_role(u) == store.ROLE_MEMBER)
    check("사번이 uid 다", u["uid"] == PREFIX + "001")
    check("이름·부서가 실린다", u.get("displayName") and u.get("department") == "인사그룹")

    print("\n승인제가 켜져 있을 때")
    os.environ["ADMIN_EMPLOYEE_NOS"] = PREFIX + "999"
    check("관리자가 있으면 승인제가 켜진다", store.approval_enabled() is True)
    p = store.upsert_from_sso(identity(PREFIX + "002"))
    check("신규 사용자는 대기 상태로 들어온다", store.resolve_status(p) == store.STATUS_PENDING,
          store.resolve_status(p))
    a = store.upsert_from_sso(identity(PREFIX + "999"))
    check("지정된 관리자는 대기하지 않는다", store.is_approved(a) and store.is_admin(a))

    print("\n승인·거절")
    ok = store.set_status(PREFIX + "002", store.STATUS_APPROVED)
    check("승인하면 상태가 바뀐다", store.is_approved(ok))
    check("바뀐 시각을 남긴다", bool(ok.get("statusUpdatedAt")))
    check("없는 사용자를 승인하면 None — 유령 계정을 만들지 않는다",
          store.set_status(PREFIX + "404", store.STATUS_APPROVED) is None)
    try:
        store.set_status(PREFIX + "002", "무효")
        check("알 수 없는 상태를 거부한다", False)
    except ValueError:
        check("알 수 없는 상태를 거부한다", True)

    print("\n재로그인이 권한을 되돌리지 않는다")
    store.set_status(PREFIX + "002", store.STATUS_REJECTED)
    again = store.upsert_from_sso(identity(PREFIX + "002"))
    check("거절된 사용자가 재로그인으로 풀리지 않는다",
          store.resolve_status(again) == store.STATUS_REJECTED, store.resolve_status(again))
    store.set_role(PREFIX + "001", store.ROLE_ADMIN)
    back = store.upsert_from_sso(identity(PREFIX + "001"))
    check("관리자 지정이 재로그인으로 덮이지 않는다", store.is_admin(back))
    check("인사 이동은 반영된다",
          store.upsert_from_sso(identity(PREFIX + "001", department="급여그룹"))
          .get("department") == "급여그룹")

    print("\n조회")
    pend = [u["uid"] for u in store.list_by_status(store.STATUS_PENDING)]
    check("대기 목록에 시험 계정이 안 남아 있다", PREFIX + "002" not in pend)
    check("이메일로 찾는다",
          (store.find_by_email(PREFIX + "001@posco.local") or {}).get("uid") == PREFIX + "001")
    check("없는 이메일은 None", store.find_by_email("") is None)
    uids = {u["uid"] for u in store.list_users()}
    check("전체 목록에 들어 있다", {PREFIX + "001", PREFIX + "002"} <= uids)

    print("\n관리자 부트스트랩")
    # 대상은 **아직 관리자가 아닌** 계정이라야 한다. 이미 관리자인 계정을 쓰면
    # 부트스트랩이 아무것도 안 해도 통과한다.
    check("검사 전제 — 002 는 아직 관리자가 아니다",
          not store.is_admin(store.get_user(PREFIX + "002")))
    os.environ["ADMIN_EMPLOYEE_NOS"] = f"{PREFIX}777,{PREFIX}002"
    made = store.bootstrap_admins()
    check("없던 관리자를 미리 만든다", PREFIX + "777" in made)
    check("만들어진 관리자는 바로 승인 상태",
          store.is_admin(store.get_user(PREFIX + "777"))
          and store.is_approved(store.get_user(PREFIX + "777")))
    check("이미 있는 사용자는 역할을 올려 준다", store.is_admin(store.get_user(PREFIX + "002")))

    print("\n정리")
    removed = cleanup()
    check("시험 행을 전부 지웠다", store.get_user(PREFIX + "001") is None, f"{removed}행 삭제")

    print("\n전부 통과\n" if failed == 0 else f"\n{failed}건 실패\n")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        try:
            cleanup()
        except Exception:
            pass
