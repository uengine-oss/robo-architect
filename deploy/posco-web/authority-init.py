"""authority-init — 권한 서버의 최초 초기화. **한 번 돌고 끝난다. 다시 돌려도 안전하다.**

`desktop/runtime/robo-central.sh` 의 `bring_up` + `init_accounts` 와 **같은 순서**다.
현장 서버에서 사람이 셸로 하던 일을 compose 가 하게 옮겼다 — 값은 전부
compose 의 `environment:` 로 들어오고, 컨테이너 안의 파일을 고치지 않는다.

    1. DB 역할 — robo_authority(상시 authority 의 제한 역할)
       있으면 비밀번호를 맞추고, 없으면 만든다
       ⓘ robo-central.sh 의 robo_operator 는 만들지 않는다 — 프로젝트 운영은 소유자 자격으로
         한다(README §④: 이 배치에선 별도 운영 역할이 격리를 늘리지 않는다)
    2. migrate                     표 구조
    2-b. 권한 서버 역할에 계정 표 권한   ← robo-central.sh 에 **없던** 단계
    3. grant  --employee-no <사번>  최초 관리자. **initialized 를 켠다**
    4. policy --approval-required   ⚠ grant 보다 먼저 부르면 거절된다 — 순서를 안 바꾼다

## 2-b — 없으면 authority 가 기동에서 죽는다 (2026-11-10, 이 compose 로 처음 띄워 쟀다)

    psycopg.errors.InsufficientPrivilege: permission denied for table app_auth_policy

제한 역할은 만들어지기만 하고, 표 권한을 주는 자리는 `accounts_admin configure-access`
하나뿐이다. 그런데 그 명령은 **이 DB 이미지에서 통과할 수 없다**:

    PC가 실행 가능한 SECURITY DEFINER 함수를 먼저 검토·차단해야 합니다.

막는 함수는 `public.og__ensure_view`(ontological 확장) 하나다. `access.py` 의 허용 목록은
`og_build_view` 만 알고, 납품 DB 이미지의 확장은 그 뒤에 이 함수를 더했다. 그 검사는
**PC 가 붙는 역할**을 지키는 것인데 서버 판에는 PC 가 없다(API 는 소유자로 붙는다).

그래서 `configure()` 가 **서버 역할에 주는 권한만** 여기서 그대로 준다. 표·시퀀스 이름은
`api.features.accounts.access` 의 상수에서 읽고, 그 목록이 바뀌면 **여기서 멈춘다** —
같은 목록을 두 곳에 두되, 어긋나면 조용히 지나가지 않게 한다.

이 컨테이너만 **소유자(superuser) 자격**을 받는다(`OG_PG_DSN`). 상시 authority 는
제한된 역할로만 붙는다.

출력에는 비밀 값을 찍지 않는다 — 이름과 결과만.
"""
from __future__ import annotations

import os
import subprocess
import sys

import psycopg
from psycopg import sql


def need(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        print(f"authority-init: {name} 가 비어 있다 — .env 를 채운다", file=sys.stderr)
        raise SystemExit(2)
    return value


def ensure_roles(dsn: str) -> None:
    wanted = {
        "robo_authority": need("ROBO_AUTHORITY_DB_PASSWORD"),
    }
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        for role, password in wanted.items():
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            verb = "ALTER" if cur.fetchone() else "CREATE"
            cur.execute(sql.SQL(verb + " ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)))
            print(f"  role {role}: {'맞춤' if verb == 'ALTER' else '만듦'}")


# `api.features.accounts.access.configure()` 가 server_role 에 주는 것과 같다.
_EXPECTED_TABLES = ("app_users", "app_auth_policy", "app_account_audit",
                    "app_code_templates", "app_code_template_history")
_EXPECTED_SEQUENCES = ("app_account_audit_id_seq", "app_code_template_history_id_seq")


def grant_authority_role(dsn: str, role: str = "robo_authority") -> None:
    sys.path.insert(0, "/app")
    from api.features.accounts import access  # 이미지 안의 원본과 대조한다

    if tuple(access.TABLES) != _EXPECTED_TABLES or tuple(access.SEQUENCES) != _EXPECTED_SEQUENCES:
        print("authority-init: access.py 의 보호 표 목록이 바뀌었다 — 이 파일의 2-b 를 다시 맞춘다",
              file=sys.stderr)
        raise SystemExit(3)
    r = sql.Identifier(role)
    t = lambda name: sql.SQL("public.") + sql.Identifier(name)  # noqa: E731
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(r))
        for seq in _EXPECTED_SEQUENCES:
            cur.execute(sql.SQL("GRANT USAGE, SELECT ON SEQUENCE {} TO {}").format(t(seq), r))
        cur.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE ON {}, {} TO {}").format(
            t("app_users"), t("app_auth_policy"), r))
        cur.execute(sql.SQL("GRANT INSERT ON {} TO {}").format(t("app_account_audit"), r))
        cur.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON {}, {} TO {}").format(
            t("app_code_templates"), t("app_code_template_history"), r))
        # 2-c. 프로젝트 목록 **읽기** — Figma 연결 코드 발급(`/api/auth/figma-pair`)이
        #      "이 사람이 이 프로젝트에 쓰기 권한이 있나" 를 이 역할로 본다
        #      (`projects.list_projects` · app_projects ⋈ og_catalog.grantee).
        #      /api/projects 는 소유자 자격(ROBO_PROJECT_OPERATOR_DSN)으로 돌지만 이 경로는 아니다.
        #      없으면 `permission denied for schema og_catalog` → 503 "중앙 권한 저장소를
        #      초기화하거나 연결을 확인하세요"(2026-11-13 현장 · 로컬 재현). 읽기만 준다.
        cur.execute("SELECT to_regclass('public.app_projects'), to_regclass('og_catalog.grantee')")
        projects_table, grantee_table = cur.fetchone()
        if projects_table and grantee_table:
            cur.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(t("app_projects"), r))
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA og_catalog TO {}").format(r))
            cur.execute(sql.SQL("GRANT SELECT ON og_catalog.grantee TO {}").format(r))
            print(f"  grants {role}: 프로젝트 목록 읽기 (app_projects · og_catalog.grantee)")
        else:
            print(f"  grants {role}: 프로젝트 표가 아직 없다 — Figma 연결 코드는 다음 init 에서", file=sys.stderr)
    print(f"  grants {role}: 계정 표 {len(_EXPECTED_TABLES)} · 시퀀스 {len(_EXPECTED_SEQUENCES)}")


def admin(*args: str) -> None:
    print(f"  accounts_admin {args[0]}")
    done = subprocess.run([sys.executable, "-m", "scripts.accounts_admin", *args],
                          cwd="/app", capture_output=True, text=True)
    if done.stdout.strip():
        print("    " + done.stdout.strip())
    if done.returncode != 0:
        print("    " + (done.stderr.strip() or f"exit {done.returncode}"), file=sys.stderr)
        raise SystemExit(done.returncode)


def main() -> None:
    dsn = need("OG_PG_DSN")
    empno = need("ROBO_ADMIN_EMPNO")
    approval = (os.environ.get("ROBO_APPROVAL_REQUIRED") or "true").strip().lower()
    if approval not in ("true", "false"):
        print("authority-init: ROBO_APPROVAL_REQUIRED 는 true|false", file=sys.stderr)
        raise SystemExit(2)
    print("authority-init: 시작")
    ensure_roles(dsn)
    admin("migrate")
    grant_authority_role(dsn)
    admin("grant", "--employee-no", empno, "--reason", "initial administrator (compose)")
    admin("policy", "--approval-required", approval, "--reason", "posco-web approval policy")
    print("authority-init: 끝")


if __name__ == "__main__":
    main()
