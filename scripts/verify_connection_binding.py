"""세션 신원으로 그래프 연결 자격이 정해지는지 검사.

두 층을 따로 본다.

```
앱 층        권한 없는 graph 를 고르면 403 · 클라이언트가 보낸 자격은 무시된다
저장소 층    그 role 로 Bolt 에 직접 붙어도 남의 graph 가 안 읽힌다
```

**두 번째가 본체다.** 앱 검사만 통과하고 저장소가 안 막으면, 앱을 우회하는 경로가
그대로 열려 있다 — 기준 구현(local-msaez)의 인가가 딱 그 상태다.

만든 graph 와 role 만 정리하고, 실 데이터 graph 는 시작·끝 노드 수로 확인한다.

    robo-architect/.venv/bin/python scripts/verify_connection_binding.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ["AUTH_JWT_SECRET"] = "verify-only-secret"
os.environ["AUTH_ROLE_SECRET"] = "verify-only-role-secret"
os.environ["AUTH_BIND_CONNECTION"] = "true"
os.environ["AUTH_BIND_CACHE_SECONDS"] = "0"   # 캐시가 결과를 가리지 않게

from neo4j import GraphDatabase  # noqa: E402

from api.platform import pg  # noqa: E402
from api.features.accounts import store as accounts  # noqa: E402
from api.features.auth.tokens import issue_token  # noqa: E402
from api.features.projects import roles, store  # noqa: E402
from api.platform.identity import connection_binding as binding  # noqa: E402
from api.platform import neo4j as neo4j_platform  # noqa: E402
from api.platform.neo4j_context import set_override  # noqa: E402

USER_PREFIX = "ZZBIND"
GRAPH_PREFIX = "prj_"
PROTECTED = {"robo", "analyzer_run", "analyzer", "probe", "anlz_probe", "wr_probe"}
URI = os.environ.get("NEO4J_URI", "bolt://localhost:28687")

created_graphs: list[str] = []
roles_at_start: set[str] = set()
PROTECTED_ROLES = {"dev", "proj_robo", "proj_analyzer", "postgres"}
failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global failed
    if cond:
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def graph_node_counts() -> dict[str, int]:
    rows = pg.query(
        "SELECT g.name AS name, count(n.*) AS c FROM og_catalog.graph g "
        "LEFT JOIN og_catalog.type t ON t.graph_id = g.graph_id "
        "LEFT JOIN og_data.og_node n ON n.type_id = t.type_id GROUP BY g.name"
    )
    return {r["name"]: int(r["c"]) for r in rows}


def cleanup() -> None:
    for graph in list(created_graphs):
        if graph in PROTECTED or not graph.startswith(GRAPH_PREFIX):
            print(f"  !! {graph} 는 지우지 않는다 (보호 대상)")
            continue
        try:
            store.drop_project(graph)
        except Exception as exc:
            print(f"  !! {graph} 정리 실패: {str(exc)[:80]}")
    created_graphs.clear()
    pg.execute("DELETE FROM public.app_users WHERE uid LIKE %s", (USER_PREFIX + "%",))
    if not roles_at_start:
        return
    now = {r["rolname"] for r in pg.query("SELECT rolname FROM pg_roles")}
    for role in sorted(now - roles_at_start):
        if role in PROTECTED_ROLES or not role.startswith("p_"):
            continue
        for stmt in (f'DROP OWNED BY "{role}"', f'DROP ROLE IF EXISTS "{role}"'):
            try:
                pg.execute(stmt)
            except Exception:
                pass


def seed(graph: str) -> None:
    """graph 에 노드를 하나 심는다.

    **소유자 자격으로 심는다.** 사용자 role 로는 못 심기 때문이다 — 라벨을 새로
    만드는 것은 스키마 변경이라 범위 지정 role 에게 허용되지 않는다(아래
    `schema_write_possible` 참고). 여기서 확인하려는 것은 읽기 격리이므로 심는
    주체는 중요하지 않다.
    """
    drv = GraphDatabase.driver(
        URI, auth=(os.environ.get("NEO4J_USER", "dev"), os.environ.get("NEO4J_PASSWORD", "")))
    with drv.session(database=graph) as s:
        s.run("CREATE (:ZzSeed {name: $n})", n=graph).consume()
    drv.close()


def bolt_write(user: str, password: str, graph: str) -> str:
    """그 자격으로 써 본다. 읽기 등급이면 거부돼야 한다."""
    try:
        drv = GraphDatabase.driver(URI, auth=(user, password))
        with drv.session(database=graph) as s:
            s.run("CREATE (:ZzSeed {name: 'w'})").consume()
        drv.close()
        return "썼음"
    except Exception as exc:
        return "거부: " + str(exc).split("\n")[0][:70]


def scoped_write_possible(uid: str, graph: str) -> str:
    """범위 지정 role 이 자기 graph 에 라벨을 만들 수 있는가.

    지금은 못 만든다. 라벨 생성이 `og_catalog.type` 삽입 + `og_data` 스키마
    CREATE 를 요구하는데, `og_grant` 는 범위를 지정하면 그 둘을 주지 않는다.
    프로젝트 소유자가 자기 프로젝트에 인제스천을 못 한다는 뜻이라 그냥 둘 수 없다.
    """
    try:
        drv = GraphDatabase.driver(URI, auth=(roles.role_name(uid), roles.role_password(uid)))
        with drv.session(database=graph) as s:
            s.run("CREATE (:ZzWriteProbe {a: 1})").consume()
        drv.close()
        return "가능"
    except Exception as exc:
        return "막힘: " + str(exc).split("\n")[0][:70]


def password_auth_required() -> bool:
    """host 연결에 비밀번호를 요구하는가.

    `trust` 면 **비밀번호를 아예 확인하지 않는다.** 그러면 role 이름만 대면 누구든
    그 role 이 되므로, 아래의 격리는 인가일 뿐 인증이 없다.
    """
    rows = pg.query(
        "SELECT auth_method FROM pg_hba_file_rules "
        "WHERE type = 'host' AND 'all' = ANY(database)"
    )
    return bool(rows) and all(r["auth_method"] != "trust" for r in rows)


def _raises(fn, *args, expect: type = Exception, message: str = "") -> bool:
    """예상한 종류의 오류가, 예상한 말과 함께 나는가.

    아무 오류나 통과시키면 저장소가 대신 죽어 준 것을 우리 검증으로 착각한다.
    """
    try:
        fn(*args)
        return False
    except expect as exc:
        return message in str(exc) if message else True
    except Exception:
        return False


def bolt_read(user: str, password: str, graph: str) -> str:
    """그 자격으로 직접 붙어 읽어 본다. 거부되면 사유를 돌려준다."""
    try:
        drv = GraphDatabase.driver(URI, auth=(user, password))
        with drv.session(database=graph) as s:
            n = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        drv.close()
        return f"읽음({n})"
    except Exception as exc:
        return "거부: " + str(exc).split("\n")[0][:80]


def main() -> int:
    accounts.ensure_schema()
    store.ensure_schema()
    roles_at_start.update(r["rolname"] for r in pg.query("SELECT rolname FROM pg_roles"))
    before = graph_node_counts()

    alice = USER_PREFIX + "-A"
    bob = USER_PREFIX + "-B"
    for uid in (alice, bob):
        accounts.upsert_from_sso({"empno": uid, "id": uid, "username": uid, "name": uid})

    pa = store.create_project("A 의 프로젝트", alice)
    created_graphs.append(pa["graph"])
    pb = store.create_project("B 의 프로젝트", bob)
    created_graphs.append(pb["graph"])

    # 빈 graph 로는 격리를 확인할 수 없다 — 권한이 없어도 "0건"이 돌아온다.
    # 각 graph 에 노드를 하나씩 심어, 못 읽는 것이 권한 때문임을 분명히 한다.
    for proj in (pa, pb):
        seed(proj["graph"])

    tok_a = issue_token(accounts.get_user(alice), source="dev")
    hdr_a = {"authorization": f"Bearer {tok_a}"}

    print("\n앱 층 — 등급으로 자격을 고른다")
    ov = binding.resolve_for_request({**hdr_a, "x-project-graph": pa["graph"]}, None)
    check("소유자(admin)는 소유자 자격으로 붙는다 — 범위 지정 role 로는 라벨을 못 만든다",
          ov is not None and ov.user == os.environ.get("NEO4J_USER", "dev"), ov.user if ov else "None")
    check("그래도 graph 는 그 프로젝트로 고정된다", ov.database == pa["graph"])

    # 읽기 등급은 그 사람 role 로 묶인다 — 여기가 DB 가 보장하는 자리다.
    store.share(pa["graph"], bob, "read")
    tok_b = issue_token(accounts.get_user(bob), source="dev")
    hdr_b = {"authorization": f"Bearer {tok_b}"}
    ovb = binding.resolve_for_request({**hdr_b, "x-project-graph": pa["graph"]}, None)
    check("읽기 등급은 그 사람 role 로 붙는다", ovb.user == roles.role_name(bob), ovb.user)
    check("비밀번호는 유도한 값", ovb.password == roles.role_password(bob))
    check("읽기 등급은 저장소가 쓰기를 막는다",
          bolt_write(roles.role_name(bob), roles.role_password(bob), pa["graph"]).startswith("거부"))
    store.unshare(pa["graph"], bob)

    denied = False
    try:
        binding.resolve_for_request({**hdr_a, "x-project-graph": pb["graph"]}, None)
    except binding.BindingDenied:
        denied = True
    check("남의 프로젝트를 고르면 막는다", denied)

    print("\n클라이언트가 보낸 자격은 무시한다")
    # 소유자 자격을 헤더로 지어내도 세션이 있으면 그쪽을 쓰지 않아야 한다.
    forged = {
        **hdr_a, "x-project-graph": pa["graph"],
        "x-neo4j-uri": URI, "x-neo4j-user": "dev",
        "x-neo4j-password": os.environ.get("NEO4J_PASSWORD", ""),
        "x-neo4j-database": "robo",
    }
    ov2 = binding.resolve_for_request(forged, None)
    check("지어낸 graph 를 따르지 않는다 — 남의 프로젝트를 가리켜도 소용없다",
          ov2.database == pa["graph"], ov2.database)
    forged_other = {**hdr_a, "x-project-graph": pb["graph"],
                    "x-neo4j-uri": URI, "x-neo4j-user": "dev",
                    "x-neo4j-password": os.environ.get("NEO4J_PASSWORD", "")}
    blocked = False
    try:
        binding.resolve_for_request(forged_other, None)
    except binding.BindingDenied:
        blocked = True
    check("자격을 지어내도 권한 없는 프로젝트는 막힌다", blocked)

    print("\n세션이 없으면 지금까지의 동작")
    check("토큰이 없으면 관여하지 않는다",
          binding.resolve_for_request({}, "robo") is None)
    os.environ["AUTH_BIND_CONNECTION"] = "false"
    check("스위치가 꺼져 있으면 관여하지 않는다",
          binding.resolve_for_request({**hdr_a, "x-project-graph": pa["graph"]}, None) is None)
    os.environ["AUTH_BIND_CONNECTION"] = "true"

    print("\n프로젝트가 없는 사람도 시작할 수 있다")
    # 프로젝트가 하나도 없으면 `X-Project-Graph` 를 보낼 수 없고, 그러면 바인딩이
    # `.env` 의 graph 로 떨어져 **403 이 난다** — 첫 프로젝트를 만들러 가는 길
    # 자체가 막힌다. 두 번째 계정을 만들자마자 실제로 이 막다른 길에 걸렸다.
    #
    # 그래서 graph 를 안 쓰는 경로(전부 Postgres 직결)는 바인딩을 건너뛴다.
    for path in ("/api/projects", "/api/projects/prj_x/members",
                 "/api/accounts", "/api/auth/dev-login"):
        check(f"{path} 는 graph 를 요구하지 않는다", not binding.needs_graph(path))
    for path in ("/api/contexts", "/api/graph/stats", "/api/ingest/upload"):
        check(f"{path} 는 graph 가 필요하다", binding.needs_graph(path))
    # 접두사만 보면 `/api/projectsomething` 같은 남의 경로까지 열린다.
    check("접두사가 비슷한 남의 경로는 열지 않는다",
          binding.needs_graph("/api/graph/projects"))

    # **판정 함수가 맞아도 미들웨어가 안 쓰면 소용없다.** 결함을 심어 보니 위의
    # 여덟 줄이 전부 통과하면서 실제 요청은 그대로 막혔다 — 이 저장소가 반복해
    # 밟은 죽은 배선이 정확히 그 모양이다.
    main_src = (ROOT / "api/main.py").read_text(encoding="utf-8")
    check("미들웨어가 그 판정을 실제로 쓴다",
          "binding_enabled() and needs_graph(request.url.path)" in main_src)

    print("\n고르지 않았다와 권한이 없다를 가른다")
    # 둘을 같은 오류로 내보내면 화면이 구별할 수 없다. 실제로 프로젝트를 안 고른
    # 사용자에게 "서버 연결 실패"라고 보여 줬다 — 백엔드가 멀쩡한데 죽은 것처럼
    # 보인다. 시크릿 창으로 두 번째 계정에 들어가자마자 이 자리에 걸렸다.
    try:
        binding.resolve_for_request(hdr_a, "robo")   # 헤더 없이 = 안 고른 상태
        check("안 고르면 거부한다", False, "통과해 버렸다")
    except binding.BindingDenied as exc:
        check("안 고르면 거부한다", True)
        check("코드가 '안 골랐다'다", exc.code == "PROJECT_NOT_SELECTED", exc.code)
        check("문구가 권한 얘기를 하지 않는다", "권한" not in str(exc), str(exc))
    try:
        binding.resolve_for_request({**hdr_a, "x-project-graph": pb["graph"]}, None)
        check("남의 graph 를 지정하면 거부한다", False, "통과해 버렸다")
    except binding.BindingDenied as exc:
        check("남의 graph 를 지정하면 거부한다", True)
        check("코드가 '권한 없음'이다", exc.code == "PROJECT_FORBIDDEN", exc.code)
    # 자기 것을 고르면 통과해야 한다 — 위 둘만 보면 "전부 거부"도 초록이 된다.
    check("자기 것을 고르면 통과한다",
          binding.resolve_for_request({**hdr_a, "x-project-graph": pa["graph"]}, None) is not None)

    # 여기부터는 **판정이 실제로 쓰이는지**를 본다. 판정 함수만 맞고 호출부가
    # 옛날 그대로면 위의 여섯 줄이 전부 통과하면서 사용자는 그대로 막힌다 —
    # 결함을 심어 보니 정확히 그렇게 됐다.
    main_src = (ROOT / "api/main.py").read_text(encoding="utf-8")
    check("미들웨어가 오류 코드를 그대로 내보낸다",
          '"code": exc.code' in main_src)

    store_src = (ROOT / "frontend/src/features/projects/projects.store.js").read_text(encoding="utf-8")
    check("화면이 안 고른 상태를 첫 프로젝트로 채운다",
          "auth.setProject(projects.value[0].graph)" in store_src)

    nav_src = (ROOT / "frontend/src/features/navigator/navigator.store.js").read_text(encoding="utf-8")
    check("화면이 403 을 서버 장애로 옮기지 않는다",
          "err.projectError" in nav_src and "if (e?.projectError)" in nav_src)

    print("\n저장소 층 — 여기가 본체다")
    role_a, pw_a = roles.role_name(alice), roles.role_password(alice)
    own = bolt_read(role_a, pw_a, pa["graph"])
    check("자기 graph 는 읽힌다", own.startswith("읽음"), own)
    other = bolt_read(role_a, pw_a, pb["graph"])
    check("남의 graph 는 Postgres 가 거부한다 — 앱을 우회해도 막힌다",
          other.startswith("거부"), other)
    real = bolt_read(role_a, pw_a, "robo")
    check("설계 graph 도 안 보인다", real.startswith("거부"), real)

    print("\n설계와 분석은 한 세트다")
    # 설계는 분석에서 뽑은 룰을 승격시킨 것이라 둘을 따로 고르면 추적성이 다른
    # 분석을 가리킨다. 화면에는 결과가 나오므로 오류로 드러나지 않는다.
    store.set_analyzer_graph(pa["graph"], pb["graph"])
    ovp = binding.resolve_for_request({**hdr_a, "x-project-graph": pa["graph"]}, None)
    check("프로젝트가 정한 분석 graph 가 연결에 실린다",
          ovp.analyzer_database == pb["graph"], str(ovp.analyzer_database))

    set_override(ovp)
    try:
        check("분석 graph 조회가 그 값을 따른다 — 모듈 상수를 쓰면 프로세스마다 하나다",
              neo4j_platform.analyzer_database() == pb["graph"],
              str(neo4j_platform.analyzer_database()))
    finally:
        set_override(None)
    check("요청 밖에서는 .env 값으로 돌아온다",
          neo4j_platform.analyzer_database() == neo4j_platform.ANALYZER_NEO4J_DATABASE)

    store.set_analyzer_graph(pa["graph"], None)
    ovn = binding.resolve_for_request({**hdr_a, "x-project-graph": pa["graph"]}, None)
    check("짝을 지우면 연결에서도 빠진다", ovn.analyzer_database is None)
    check("없는 graph 를 짝으로 걸 수 없다",
          _raises(store.set_analyzer_graph, pa["graph"], "prj_nope",
                  expect=ValueError, message="그런 graph 가 없다"))

    print("\n남은 전제조건 — 저장소 층에서 아직 안 되는 것")
    # 통과/실패로 세지 않는다. 앱 코드로 고칠 수 있는 것이 아니고, 무엇이 막혀
    # 있는지를 기록으로 남기는 자리다.
    print(f"  --   범위 지정 role 의 쓰기: {scoped_write_possible(alice, pa['graph'])}")
    print("       → 프로젝트 소유자가 자기 프로젝트에 인제스천을 못 한다.")
    print("          og_grant 가 범위를 지정하면 og_catalog.type 삽입과")
    print("          og_data 스키마 CREATE 를 주지 않는다 (엔진 변경 필요).")

    print("\n배포 전제조건 — 인증")
    # 인가(grant)와 인증(비밀번호)은 다른 층이다. 아래가 깨져 있으면 위의 격리는
    # role 이름만 대면 통과하는 상태가 된다.
    if password_auth_required():
        check("틀린 비밀번호로는 붙지 못한다",
              bolt_read(role_a, "wrong-password", pa["graph"]).startswith("거부"))
    else:
        print("  --   pg_hba 가 host 연결을 trust 로 둔다 — 비밀번호를 확인하지 않는다.")
        print("       → role 이름만 대면 그 role 이 된다. 위의 격리는 인가일 뿐")
        print("          인증이 없다. 배포 구성에서 scram-sha-256 으로 바꿔야 한다.")

    print("\n공유하면 열리고 회수하면 닫힌다")
    store.share(pb["graph"], alice, "read")
    ov3 = binding.resolve_for_request({**hdr_a, "x-project-graph": pb["graph"]}, None)
    check("초대받으면 앱이 통과시킨다", ov3 is not None and ov3.database == pb["graph"])
    check("초대받으면 저장소도 읽게 해 준다",
          bolt_read(role_a, pw_a, pb["graph"]).startswith("읽음"))
    store.unshare(pb["graph"], alice)
    denied2 = False
    try:
        binding.resolve_for_request({**hdr_a, "x-project-graph": pb["graph"]}, None)
    except binding.BindingDenied:
        denied2 = True
    check("회수하면 앱이 다시 막는다", denied2)
    check("회수하면 저장소도 다시 막는다",
          bolt_read(role_a, pw_a, pb["graph"]).startswith("거부"))

    print("\n실 데이터 확인")
    cleanup()
    after = graph_node_counts()
    for name in sorted(PROTECTED & set(before)):
        check(f"{name} 노드 수가 그대로", before.get(name) == after.get(name),
              f"{before.get(name)} → {after.get(name)}")
    # **이 run 이 새로 남긴 것**만 잔재다. "prj_ 로 시작하는 graph 가 없어야
    # 한다"로 재면 앱에서 만든 **진짜 프로젝트**를 잔재로 오인한다 — 실제로
    # alice 계정으로 프로젝트를 하나 만들자마자 이 검사가 틀린 실패를 냈다.
    leaked = [g for g in set(after) - set(before) if g.startswith(GRAPH_PREFIX)]
    check("이 run 이 남긴 graph 가 없다", not leaked, str(leaked))

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
