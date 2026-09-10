"""분석 대상 graph 배선 검사.

레거시 분석은 **매 run 이 대상 graph 를 통째로 비운다.** 그 대상이 프로세스 환경
하나로 고정돼 있으면, 한 프로젝트를 분석했을 뿐인데 다른 프로젝트의 분석 결과가
사라진다 — 오류는 나지 않는다. 실제로 이 저장소는 그 사고로 422건을 날린 적이 있다.

그래서 대상이 **요청을 따라오는지**를 다섯 칸 전부에서 잰다.

```
1 Architect   프로젝트를 만들면 분석 graph 도 짝으로 생기고 권한이 함께 간다
2 Architect   공유·회수·삭제가 짝을 함께 따라간다
3 분석기      Neo4jClient / execute_run 이 대상 graph 를 인자로 받는다
4 분석기 API  X-Neo4j-Database 를 읽고, system 은 거부한다
5 catalog     같은 헤더를 요청 컨텍스트로 잡는다
6 프런트      mount 인자 → 세션 스토어 → getHeaders() 한 곳
```

**실데이터를 태우지 않는다.** 임시 프로젝트를 만들어 그 안에서만 돌고 지운다.
보호 목록에 든 graph 를 만나면 그 자리에서 멈춘다.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "robo-analyzer" / "robo-data-analyzer"
CATALOG = ROOT / "robo-analyzer" / "robo-data-catalog"
AFRONT = ROOT / "robo-analyzer" / "robo-data-frontend"
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from api.features.projects import roles, store  # noqa: E402
from api.platform import pg  # noqa: E402

PROTECTED = {"robo", "analyzer_run", "analyzer", "neo4j"}
OWNER = "ZZ-WIRE-OWNER"
GUEST = "ZZ-WIRE-GUEST"

_fails: list[str] = []
_passes = 0


def check(label: str, got, want) -> None:
    global _passes
    if got == want:
        _passes += 1
        print(f"  ok   {label}")
    else:
        _fails.append(f"{label}: 기대 {want!r} · 실제 {got!r}")
        print(f"  FAIL {label}: 기대 {want!r} · 실제 {got!r}")


def check_true(label: str, got) -> None:
    check(label, bool(got), True)


def grants(role: str, graph: str) -> str | None:
    rows = pg.query(
        "SELECT level FROM og_catalog.grantee WHERE role = %s AND graph = %s",
        (role, graph),
    )
    return rows[0]["level"] if rows else None


def graph_exists(name: str) -> bool:
    return bool(pg.query("SELECT 1 FROM og_catalog.graph WHERE name = %s", (name,)))


# ---------------------------------------------------------------------------
# 1~2. Architect — 짝을 만들고, 권한이 함께 간다
# ---------------------------------------------------------------------------

def test_pairing() -> None:
    print("\n[1] 프로젝트를 만들면 분석 graph 도 함께 생긴다")
    project = store.create_project("배선 검사용", OWNER)
    graph = project["graph"]
    assert graph not in PROTECTED, "보호된 graph 를 대상으로 삼았다"
    analyzer = project.get("analyzerGraph")

    check("짝이 함께 만들어진다", analyzer, f"{graph}_a")
    check_true("설계 graph 가 실재한다", graph_exists(graph))
    check_true("분석 graph 도 실재한다", graph_exists(analyzer))

    owner_role = roles.role_name(OWNER)
    check("소유자가 설계에 admin", grants(owner_role, graph), "admin")
    # 추적성이 두 graph 를 오가며 읽는다. 한쪽만 열면 출처만 조용히 빈다.
    check("소유자가 분석에도 admin", grants(owner_role, analyzer), "admin")

    print("\n[2] 공유·회수·삭제가 짝을 따라간다")
    store.share(graph, GUEST, "read")
    guest_role = roles.role_name(GUEST)
    check("공유가 설계에 걸린다", grants(guest_role, graph), "read")
    check("공유가 분석에도 걸린다", grants(guest_role, analyzer), "read")

    store.unshare(graph, GUEST)
    check("회수가 설계에서 빠진다", grants(guest_role, graph), None)
    check("회수가 분석에서도 빠진다", grants(guest_role, analyzer), None)

    store.drop_project(graph)
    check_true("설계 graph 가 사라진다", not graph_exists(graph))
    check_true("분석 graph 도 사라진다", not graph_exists(analyzer))
    check("설계 권한이 안 남는다", grants(owner_role, graph), None)
    check("분석 권한도 안 남는다", grants(owner_role, analyzer), None)


def test_pair_not_stolen() -> None:
    """남과 나눠 쓰는 분석 graph 는 프로젝트를 지워도 함께 지우지 않는다."""
    print("\n[3] 남의 분석 graph 는 건드리지 않는다")
    p = store.create_project("배선 검사용2", OWNER, with_analyzer=False)
    graph = p["graph"]
    assert graph not in PROTECTED
    shared = "zz_wire_shared"
    if not graph_exists(shared):
        pg.execute("SELECT og_create_graph(%s)", (shared,))
    store.set_analyzer_graph(graph, shared)

    store.drop_project(graph)
    check_true("나눠 쓰던 graph 는 남는다", graph_exists(shared))
    pg.execute("SELECT og_drop_graph(%s)", (shared,))


# ---------------------------------------------------------------------------
# 4~6. 분석기·catalog·프런트 — 소스로 잰다 (다른 저장소라 기동 없이)
# ---------------------------------------------------------------------------

def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_analyzer_backend() -> None:
    print("\n[4] 분석기가 대상 graph 를 인자로 받는다")
    client = _src(ANALYZER / "shared/neo4j/neo4j_client.py")
    check_true("Neo4jClient 가 database 를 받는다",
               "def __init__(self, database: str | None = None)" in client)
    check_true("인자가 ENV 보다 앞선다",
               "database or ENV.neo4j.database" in client)

    ex = _src(ANALYZER / "shared/workflow/executor.py")
    check_true("execute_run 이 database 를 받는다", "database: Optional[str] = None" in ex)
    check_true("그 값으로 클라이언트를 만든다", "Neo4jClient(target_db)" in ex)
    # 순서가 뒤집히면 엉뚱한 graph 를 비운다.
    check_true("대상을 정한 뒤에 wipe 한다",
               0 < ex.find("target_db = database or") < ex.find("await wipe_graph("))

    router = _src(ANALYZER / "api/analyze_router.py")
    check_true("헤더를 읽는다", '"x-neo4j-database"' in router)
    check_true("system 을 막는다", 'system database is forbidden' in router)
    check_true("run 으로 넘긴다", "database=target_db" in router)


def test_analyzer_router_precedence() -> None:
    """헤더가 본문을 이긴다 — 실제로 함수를 불러 확인한다."""
    print("\n[5] 헤더 우선순위와 거부")
    sys.path.insert(0, str(ANALYZER))
    src = _src(ANALYZER / "api/analyze_router.py")
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "_target_database")

    class _Req:
        def __init__(self, h): self.headers = h

    class _Body:
        def __init__(self, d): self.database = d

    class _Refused(Exception):
        """라우터의 HTTPException 자리. 키워드 인자를 받아야 한다."""
        def __init__(self, **kwargs):
            super().__init__(kwargs.get("detail", ""))
            self.status_code = kwargs.get("status_code")

    ns: dict = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<probe>", "exec"),
         {"Optional": object, "HTTPException": _Refused}, ns)
    target = ns["_target_database"]

    check("헤더가 본문을 이긴다", target(_Req({"x-neo4j-database": "h"}), _Body("b")), "h")
    check("헤더가 없으면 본문", target(_Req({}), _Body("b")), "b")
    check("둘 다 없으면 None (env 폴백)", target(_Req({}), _Body(None)), None)
    check("공백만이면 None", target(_Req({"x-neo4j-database": "  "}), _Body(None)), None)
    try:
        target(_Req({"x-neo4j-database": "system"}), _Body(None))
        check("system 을 거부한다", "통과함", "거부됨")
    except _Refused as exc:
        # 예외 종류와 상태 코드를 함께 본다 — 아무 예외나 통과로 세면 검사가 둔해진다.
        check("system 을 거부한다", "거부됨" if exc.status_code == 400 else "엉뚱한 코드", "거부됨")


def test_catalog() -> None:
    print("\n[6] catalog 가 같은 헤더를 본다")
    ctx = CATALOG / "client/neo4j_context.py"
    check_true("요청 컨텍스트 모듈이 있다", ctx.exists())
    if ctx.exists():
        body = _src(ctx)
        check_true("헤더 이름이 같다", "x-neo4j-database" in body)
        check_true("system 을 막는다", "system" in body)

    client = _src(CATALOG / "client/neo4j_client.py")
    check_true("클라이언트가 컨텍스트를 본다",
               "database or get_database() or self._config.database" in client)
    main = _src(CATALOG / "main.py")
    check_true("미들웨어가 붙어 있다", "DatabaseScopeMiddleware" in main)


def test_frontend_chain() -> None:
    print("\n[7] 프런트가 값을 끝까지 나른다")
    panel = _src(ROOT / "frontend/src/features/analysis/ui/AnalysisPanel.vue")
    check_true("Analysis 탭이 프로젝트의 분석 graph 를 읽는다",
               "currentAnalyzerGraph" in panel)
    check_true("mount 인자로 넘긴다", "neo4jDatabase," in panel)
    check_true("짝이 바뀌면 다시 마운트한다",
               "watch(() => projectsStore.currentAnalyzerGraph" in panel)

    store_js = _src(ROOT / "frontend/src/features/projects/projects.store.js")
    check_true("스토어가 그 값을 노출한다", "currentAnalyzerGraph" in store_js)

    boot = _src(AFRONT / "src/bootstrap.ts")
    check_true("분석기 mount 가 인자를 받는다", "neo4jDatabase?: string" in boot)
    check_true("세션 스토어에 넣는다", "setNeo4jDatabase(opts.neo4jDatabase)" in boot)

    sess = _src(AFRONT / "src/stores/session.ts")
    check_true("헤더를 한 곳에서 붙인다", "'X-Neo4j-Database'" in sess)
    check_true("값이 없으면 안 붙인다", "if (neo4jDatabase.value)" in sess)


# ---------------------------------------------------------------------------

def cleanup() -> None:
    for uid in (OWNER, GUEST):
        role = roles.role_name(uid)
        for row in pg.query("SELECT graph FROM og_catalog.grantee WHERE role = %s", (role,)):
            if row["graph"] in PROTECTED:
                continue
            try:
                pg.execute("SELECT og_revoke(%s, %s)", (role, row["graph"]))
            except Exception:
                pass
        for stmt in (f'DROP OWNED BY "{role}"', f'DROP ROLE IF EXISTS "{role}"'):
            try:
                pg.execute(stmt)
            except Exception:
                pass
    for row in pg.query("SELECT name FROM og_catalog.graph WHERE name LIKE 'zz_wire%%'"):
        try:
            pg.execute("SELECT og_drop_graph(%s)", (row["name"],))
        except Exception:
            pass


def main() -> int:
    try:
        test_pairing()
        test_pair_not_stolen()
        test_analyzer_backend()
        test_analyzer_router_precedence()
        test_catalog()
        test_frontend_chain()
    finally:
        cleanup()

    print()
    if _fails:
        print(f"실패 {len(_fails)}건 / 통과 {_passes}건")
        for f in _fails:
            print(f"  - {f}")
        return 1
    print(f"전부 통과 — {_passes}종")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
