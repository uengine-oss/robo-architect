"""서버 운영 명령: python -m scripts.accounts_admin grant --employee-no ... --reason ...

운영 DB 자격은 stdin/인자에 싣지 않고 서버의 OG_PG_DSN 등으로 공급한다.
현재 DB 사용자가 superuser인지 확인해 PC의 제한된 서비스 자격 실행을 거절한다.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys

from api.features.accounts import store
from api.platform import pg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="서버 운영자용 계정 초기화·복구")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    access_cmd = sub.add_parser("configure-access")
    access_cmd.add_argument("--server-role", required=True)
    access_cmd.add_argument("--client-role", required=True)
    for name in ("grant", "revoke", "policy"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--reason", required=True)
        if name == "policy":
            cmd.add_argument("--approval-required", choices=("true", "false"), required=True)
        else:
            cmd.add_argument("--employee-no", required=True)
    args = parser.parse_args(argv)
    try:
        rows = pg.query("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        if not rows or not rows[0]["rolsuper"]:
            raise store.AccountChangeDenied("서버 운영자 DB 자격이 필요합니다.")
        if args.command == "migrate":
            store.ensure_schema()
            from api.features.code_templates import store as templates
            # 운영 명령은 DDL을 수행하며 중앙 runtime은 존재만 확인한다.
            with pg.connection() as conn, conn.cursor() as cur:
                cur.execute(templates._SCHEMA)
                from api.features.projects import store as projects
                cur.execute(projects._SCHEMA)
            result = {"migrated": True}
        elif args.command == "configure-access":
            from api.features.accounts.access import configure
            configure(args.server_role, args.client_role)
            result = {"configured": True, "serverRole": args.server_role, "clientRole": args.client_role}
        elif args.command == "grant":
            result = store.operator_grant(args.employee_no.strip(), operator_id=getpass.getuser(),
                                          reason=args.reason)
        elif args.command == "revoke":
            result = store.operator_revoke(args.employee_no.strip(), operator_id=getpass.getuser(),
                                           reason=args.reason)
            if result is None:
                raise ValueError("그런 사용자가 없습니다.")
        else:
            result = store.set_policy(args.approval_required == "true",
                                      operator_id=getpass.getuser(), reason=args.reason)
        print(json.dumps(result, ensure_ascii=True, default=str))
        return 0
    except (store.AccountChangeDenied, store.AuthorityNotInitialized, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        # DSN/드라이버 예외에서 비밀이 나올 수 있으므로 원문은 출력하지 않는다.
        print("계정 운영 명령 실패: DB 연결·스키마·운영 권한을 확인하세요.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
