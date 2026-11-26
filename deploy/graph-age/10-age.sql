-- 새 볼륨의 첫 실행에서 postgres 이미지의 entrypoint 가 POSTGRES_USER(관리자)로 돌린다.
-- ontological-db age/main `age-supabase/sql/99999999999999_age.sql` 을 일반 PostgreSQL 로 옮긴 것
-- (Supabase 의 `extensions` 스키마 · supabase_admin · service_role 이 없다는 것만 다르다).
--
--   1. 이 DB(postgres): AGE 확장 · DROP EXTENSION 막이
--   2. graph DB: 문자열이 코드 포인트 순(LC_COLLATE C, Neo4j 와 같다) · search_path · CONNECT 는 PUBLIC 에서 거둠
--   3. 다른 모든 DB 와 template1 에도 확장 — AGE 1.8.0 의 TRUNCATE 훅이 확장 없는 DB 에서 실패한다
--      (shared_preload_libraries 로 올라와 있으므로)

\set ON_ERROR_STOP on
\set QUIET on
\pset tuples_only on
\pset format unaligned
\set age_graph_db `printf '%s' "${AGE_GRAPH_DB-graph}"`
SELECT current_user AS age_admin_role \gset

-- ------------------------------------------------------------ 1. postgres
CREATE EXTENSION IF NOT EXISTS age;
CREATE SCHEMA IF NOT EXISTS age_admin;
REVOKE ALL ON SCHEMA age_admin FROM PUBLIC;
-- DROP EXTENSION age 는 그래프를 모두 지운다 — 세션이 age_guard.allow_drop = on 을 하지 않으면 되돌린다
CREATE OR REPLACE FUNCTION age_admin.age_guard_drop()
RETURNS event_trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $fn$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_event_trigger_dropped_objects()
             WHERE object_type = 'extension' AND object_identity = 'age')
     AND coalesce(current_setting('age_guard.allow_drop', true), 'off') <> 'on' THEN
    RAISE EXCEPTION 'DROP EXTENSION age would drop every graph; refused'
      USING HINT = 'SET age_guard.allow_drop = on in this session if this is intended.';
  END IF;
END
$fn$;
REVOKE ALL ON FUNCTION age_admin.age_guard_drop() FROM PUBLIC;
DO $do$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_event_trigger WHERE evtname = 'age_guard_drop') THEN
    CREATE EVENT TRIGGER age_guard_drop ON sql_drop EXECUTE FUNCTION age_admin.age_guard_drop();
  END IF;
END
$do$;

-- ------------------------------------------------------------ 2a. graph DB 만들기(template1 에 확장을 넣기 전에)
SELECT (:'age_graph_db' <> '') AS age_want_graph_db \gset
\if :age_want_graph_db
SELECT NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'age_graph_db') AS age_make_graph_db,
       CASE WHEN EXISTS (SELECT 1 FROM pg_collation WHERE collprovider = 'c' AND collname IN ('C.utf8', 'C.UTF-8'))
            THEN 'C.UTF-8' ELSE 'C' END AS age_graph_ctype \gset
\if :age_make_graph_db
CREATE DATABASE :"age_graph_db" TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE :'age_graph_ctype';
\endif
ALTER DATABASE :"age_graph_db" SET search_path = ag_catalog, "$user", public;
REVOKE CONNECT, TEMPORARY ON DATABASE :"age_graph_db" FROM PUBLIC;
\endif

-- ------------------------------------------------------------ 3. 다른 DB 와 template1
\set age_tmp `mktemp "${TMPDIR:-/tmp}/age-dbs.XXXXXX"`
\o :age_tmp
SELECT format(E'\\connect %I\nCREATE EXTENSION IF NOT EXISTS age;', datname)
  FROM pg_database
 WHERE datallowconn AND datname <> current_database()
 ORDER BY datname;
\o
\i :age_tmp
\set age_rm `rm -f :'age_tmp'`

-- ------------------------------------------------------------ 2b. graph DB 안
\if :age_want_graph_db
\connect :"age_graph_db"
CREATE EXTENSION IF NOT EXISTS age;
CREATE SCHEMA IF NOT EXISTS age_admin;
REVOKE ALL ON SCHEMA age_admin FROM PUBLIC;
CREATE OR REPLACE FUNCTION age_admin.age_guard_drop()
RETURNS event_trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $fn$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_event_trigger_dropped_objects()
             WHERE object_type = 'extension' AND object_identity = 'age')
     AND coalesce(current_setting('age_guard.allow_drop', true), 'off') <> 'on' THEN
    RAISE EXCEPTION 'DROP EXTENSION age would drop every graph; refused'
      USING HINT = 'SET age_guard.allow_drop = on in this session if this is intended.';
  END IF;
END
$fn$;
REVOKE ALL ON FUNCTION age_admin.age_guard_drop() FROM PUBLIC;
DO $do$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_event_trigger WHERE evtname = 'age_guard_drop') THEN
    CREATE EVENT TRIGGER age_guard_drop ON sql_drop EXECUTE FUNCTION age_admin.age_guard_drop();
  END IF;
END
$do$;
\endif

\pset tuples_only off
\pset format aligned
\unset QUIET
