"""운영자가 적용하는 중앙 계정/템플릿 DB 권한 분리. 실제 역할을 명시해야 한다."""
from __future__ import annotations

from psycopg import sql

from api.platform import pg

TABLES = ("app_users", "app_auth_policy", "app_account_audit",
          "app_code_templates", "app_code_template_history")
SEQUENCES = ("app_account_audit_id_seq", "app_code_template_history_id_seq")


def configure(server_role: str, client_role: str) -> None:
    if not server_role or not client_role or server_role == client_role:
        raise ValueError("서로 다른 중앙 API/PC DB 역할이 필요합니다.")
    with pg.connection() as conn, conn.cursor() as cur:
        for name in (server_role, client_role):
            cur.execute("SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls "
                        "FROM pg_roles WHERE rolname = %s", (name,))
            role = cur.fetchone()
            if not role or any(role.values()):
                raise ValueError("DB 역할은 미리 만든 제한된 역할이어야 합니다.")
            cur.execute("SELECT EXISTS (SELECT 1 FROM pg_database d JOIN pg_roles r "
                        "ON r.oid=d.datdba WHERE d.datname=current_database() AND r.rolname=%s) "
                        "OR EXISTS (SELECT 1 FROM pg_namespace n JOIN pg_roles r ON r.oid=n.nspowner "
                        "WHERE n.nspname='public' AND r.rolname=%s) AS owned", (name, name))
            if cur.fetchone()["owned"]:
                raise ValueError("DB/public 스키마 소유자는 runtime으로 사용할 수 없습니다.")
            cur.execute("SELECT EXISTS (SELECT 1 FROM pg_roles r "
                        "WHERE r.rolname <> %s AND pg_has_role(%s, r.oid, 'MEMBER')) AS inherited",
                        (name, name))
            if cur.fetchone()["inherited"]:
                raise ValueError("상위 역할 멤버십을 먼저 제거해야 합니다.")
            cur.execute("SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n "
                        "ON n.oid=c.relnamespace WHERE n.nspname='public' "
                        "AND c.relname = ANY(%s) AND c.relowner = (SELECT oid FROM pg_roles "
                        "WHERE rolname=%s)) AS owned", (list(TABLES), name))
            if cur.fetchone()["owned"]:
                raise ValueError("보호 테이블 소유권은 서버 운영자에게 있어야 합니다.")
        cur.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC, {}, {}").format(
            sql.Identifier(server_role), sql.Identifier(client_role)))
        for table in TABLES:
            cur.execute(sql.SQL("REVOKE ALL ON TABLE public.{} FROM PUBLIC, {}, {}").format(
                sql.Identifier(table), sql.Identifier(server_role), sql.Identifier(client_role)))
            # 테이블 REVOKE는 이전의 열 단위 GRANT를 회수하지 않는다.
            cur.execute("SELECT attname FROM pg_attribute WHERE attrelid = %s::regclass "
                        "AND attnum > 0 AND NOT attisdropped", ("public." + table,))
            columns = sql.SQL(", ").join(sql.Identifier(row["attname"]) for row in cur.fetchall())
            cur.execute(sql.SQL("REVOKE ALL ({}) ON TABLE public.{} FROM PUBLIC, {}, {}").format(
                columns, sql.Identifier(table), sql.Identifier(server_role), sql.Identifier(client_role)))
        for sequence in SEQUENCES:
            cur.execute(sql.SQL("REVOKE ALL ON SEQUENCE public.{} FROM PUBLIC, {}, {}").format(
                sql.Identifier(sequence), sql.Identifier(server_role), sql.Identifier(client_role)))
            cur.execute(sql.SQL("GRANT USAGE, SELECT ON SEQUENCE public.{} TO {}").format(
                sql.Identifier(sequence), sql.Identifier(server_role)))
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}, {}").format(
            sql.Identifier(server_role), sql.Identifier(client_role)))
        cur.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE ON public.app_users, "
                            "public.app_auth_policy TO {}").format(sql.Identifier(server_role)))
        cur.execute(sql.SQL("GRANT INSERT ON public.app_account_audit TO {}").format(
            sql.Identifier(server_role)))
        cur.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON public.app_code_templates, "
                            "public.app_code_template_history TO {}").format(sql.Identifier(server_role)))
        # 계정 찾기/프로젝트 공유를 위해 PC는 사용자/정책만 읽을 수 있다.
        cur.execute(sql.SQL("GRANT SELECT ON public.app_users, public.app_auth_policy TO {}").format(
            sql.Identifier(client_role)))
        # 검토한 확장 뷰 빌더만 예외: og_data의 security_invoker 뷰를 만드는 C 함수.
        # 이름뿐 아니라 확장 소속/인자/라이브러리/심볼까지 대조한다.
        cur.execute("SELECT count(*) AS n FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "WHERE p.prosecdef AND n.nspname NOT IN ('pg_catalog', 'information_schema') "
                    "AND has_function_privilege(%s, p.oid, 'EXECUTE') AND NOT ("
                    "n.nspname='public' AND p.proname='og_build_view' AND p.proargtypes::text='23 16' "
                    "AND p.prosrc='og_build_view_wrapper' AND p.probin='$libdir/ontological' "
                    "AND EXISTS (SELECT 1 FROM pg_depend d JOIN pg_extension e ON e.oid=d.refobjid "
                    "WHERE d.objid=p.oid AND d.classid='pg_proc'::regclass AND d.deptype='e' "
                    "AND e.extname='ontological'))", (client_role,))
        if cur.fetchone()["n"]:
            raise ValueError("PC가 실행 가능한 SECURITY DEFINER 함수를 먼저 검토·차단해야 합니다.")
        cur.execute("SELECT count(*) AS n FROM pg_class v JOIN pg_rewrite rw ON rw.ev_class=v.oid "
                    "JOIN pg_depend d ON d.objid=rw.oid AND d.classid='pg_rewrite'::regclass "
                    "JOIN pg_class t ON t.oid=d.refobjid JOIN pg_namespace ns ON ns.oid=t.relnamespace "
                    "WHERE v.relkind='v' AND ns.nspname='public' AND t.relname=ANY(%s) "
                    "AND has_table_privilege(%s, v.oid, 'INSERT, UPDATE, DELETE')",
                    (list(TABLES), client_role))
        if cur.fetchone()["n"]:
            raise ValueError("PC가 보호 표를 변경할 수 있는 뷰 권한을 먼저 회수해야 합니다.")
