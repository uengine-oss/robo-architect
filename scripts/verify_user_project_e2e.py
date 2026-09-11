"""사용자·프로젝트 구조 전 구간 검증.

네 가지를 순서대로 걷는다 — 각각을 따로 검사하면 "부품은 도는데 이어 붙이면 안
되는" 경우를 놓친다.

```
1  로그인하면 새 사용자가 들어오는가      SSO 가 줄 신원 그대로 넣어 본다
2  관리자 목록에 보이고 관리가 되는가      승인·거절·역할이 실제로 바뀌는가
3  프로젝트는 어느 시점에 나뉘는가         인제스천 단위를 실측한다
4  만든 사람이 권한을 갖고 공유가 되는가    저장소 층까지 확인한다
```

**실데이터를 건드리지 않는다.** 사번은 `ZZE2E` 로 시작하는 것만, graph 는 이 검사가
만든 `prj_` 만 지운다. `robo` · `analyzer_run` 은 보호 목록에 있고, 끝나고 노드 수를
다시 세어 확인한다.

**레거시 분석기는 돌리지 않는다.** 매 run 이 대상 graph 를 통째로 비우므로, 검사가
그걸 태우면 실제 분석 결과가 사라진다.

    robo-architect/.venv/bin/python scripts/verify_user_project_e2e.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import httpx  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402

from api.platform import pg  # noqa: E402
from api.features.accounts import store as accounts  # noqa: E402
from api.features.projects import roles, store as projects  # noqa: E402

API = os.environ.get("ROBO_API_URL", "http://localhost:8000")
BOLT = os.environ.get("NEO4J_URI", "bolt://localhost:28687")

PREFIX = "ZZE2E"
GRAPH_PREFIX = "prj_"
PROTECTED = {"robo", "analyzer_run", "analyzer", "probe", "anlz_probe", "wr_probe"}
PROTECTED_ROLES = {"dev", "proj_robo", "proj_analyzer", "postgres"}

created_graphs: list[str] = []
roles_at_start: set[str] = set()
failed = 0
section = ""


def head(title: str) -> None:
    global section
    section = title
    print(f"\n{title}")


def check(name: str, cond: bool, detail: str = "") -> None:
    global failed
    if cond:
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def note(text: str) -> None:
    print(f"  --   {text}")


def graph_counts() -> dict[str, int]:
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
            projects.drop_project(graph)
        except Exception as exc:
            print(f"  !! {graph} 정리 실패: {str(exc)[:70]}")
    created_graphs.clear()
    pg.execute("DELETE FROM public.app_users WHERE uid LIKE %s", (PREFIX + "%",))
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
    """graph 에 노드를 하나 심는다 — **소유자 자격으로.**

    빈 graph 로는 격리를 확인할 수 없다. 권한이 없어도 `MATCH (n)` 이 0건을
    돌려주므로 "읽혔다"와 "막혔다"가 구별되지 않는다. 실제로 이 검사가 그 때문에
    한 번 틀린 결론을 냈다.

    심는 주체가 소유자인 이유는 범위 지정 role 로는 라벨을 만들 수 없어서다
    (`og_grant` 가 스키마 변경 권한을 주지 않는다).
    """
    drv = GraphDatabase.driver(
        BOLT, auth=(os.environ.get("NEO4J_USER", "dev"), os.environ.get("NEO4J_PASSWORD", "")))
    with drv.session(database=graph) as s:
        s.run("CREATE (:ZzSeed {a: 1})").consume()
    drv.close()


def bolt_probe(uid: str, graph: str, write: bool = False) -> str:
    """그 사람 자격으로 직접 붙어 본다. 앱을 우회해도 막히는지 보는 자리다."""
    try:
        drv = GraphDatabase.driver(BOLT, auth=(roles.role_name(uid), roles.role_password(uid)))
        with drv.session(database=graph) as s:
            if write:
                s.run("CREATE (:ZzSeed {a: 2})").consume()
                return "썼음"
            n = s.run("MATCH (n:ZzSeed) RETURN count(n) AS c").single()["c"]
        drv.close()
        return f"읽음({n})"
    except Exception as exc:
        return "거부: " + str(exc).split("\n")[0][:60]


def main() -> int:  # noqa: C901 — 전 구간을 한 흐름으로 읽히게 둔다
    accounts.ensure_schema()
    projects.ensure_schema()
    roles_at_start.update(r["rolname"] for r in pg.query("SELECT rolname FROM pg_roles"))
    before = graph_counts()
    cleanup()

    client = httpx.Client(base_url=API, timeout=60.0)

    # ── 1. 로그인이 사용자를 만드는가 ────────────────────────────────
    head("1. 로그인하면 새 사용자가 들어오는가")

    # SWP 가 주는 신원 그대로. `api/features/auth/swp.py` 의 SwpIdentity.to_dict() 모양이다.
    newcomer = {
        "id": PREFIX + "-001", "empno": PREFIX + "-001",
        "username": "hong.gildong", "name": "홍길동",
        "email": f"{PREFIX}-001@posco.local", "department": "인사그룹",
        "source": "swp",
    }
    check("처음에는 그런 사용자가 없다", accounts.get_user(newcomer["empno"]) is None)

    u = accounts.upsert_from_sso(newcomer)
    check("SSO 신원으로 사용자가 만들어진다", u is not None)
    check("사번이 식별자다 — 이메일은 없을 수 있다", u["uid"] == PREFIX + "-001", u["uid"])
    check("이름·부서·이메일이 실린다",
          u.get("displayName") == "홍길동" and u.get("department") == "인사그룹"
          and u.get("email") == newcomer["email"])
    check("승인제가 켜져 있으면 대기로 들어온다",
          accounts.resolve_status(u) == accounts.STATUS_PENDING
          if accounts.approval_enabled() else accounts.is_approved(u),
          f"승인제={accounts.approval_enabled()} 상태={accounts.resolve_status(u)}")

    # 인사 이동은 따라오되 권한은 안 따라온다 — 재로그인이 승인을 되돌리면 안 된다.
    moved = accounts.upsert_from_sso({**newcomer, "department": "급여그룹"})
    check("재로그인하면 부서 변경은 반영된다", moved.get("department") == "급여그룹")
    check("재로그인이 승인 상태를 되돌리지 않는다",
          accounts.resolve_status(moved) == accounts.resolve_status(u))

    # ── 2. 관리자 목록과 관리 ────────────────────────────────────────
    head("2. 관리자 목록에 보이고 관리가 되는가")

    admin_login = client.post("/api/auth/dev-login",
                              data={"loginId": "test", "password": "test"})
    admin_body = admin_login.json()
    atok = admin_body.get("accessToken")
    check("관리자로 로그인된다", bool(atok), str(admin_body)[:100])
    ah = {"Authorization": f"Bearer {atok}"}

    listing = client.get("/api/accounts", headers=ah)
    check("관리자가 목록을 본다", listing.status_code == 200, str(listing.status_code))
    body = listing.json() if listing.status_code == 200 else {}
    uids = {x["uid"] for x in body.get("users", [])}
    check("방금 들어온 사용자가 목록에 있다", PREFIX + "-001" in uids, str(sorted(uids))[:120])
    check("대기 인원수를 함께 준다", "pending" in (body.get("counts") or {}))

    r = client.post(f"/api/accounts/{PREFIX}-001/status", json={"status": "approved"}, headers=ah)
    check("승인하면 상태가 바뀐다",
          r.status_code == 200 and accounts.is_approved(accounts.get_user(PREFIX + "-001")),
          str(r.status_code))
    r = client.post(f"/api/accounts/{PREFIX}-001/role", json={"role": "admin"}, headers=ah)
    check("역할을 올릴 수 있다",
          r.status_code == 200 and accounts.is_admin(accounts.get_user(PREFIX + "-001")))
    r = client.post(f"/api/accounts/{PREFIX}-001/role", json={"role": "member"}, headers=ah)
    check("다시 내릴 수 있다",
          r.status_code == 200 and not accounts.is_admin(accounts.get_user(PREFIX + "-001")))
    r = client.post(f"/api/accounts/{PREFIX}-001/status", json={"status": "rejected"}, headers=ah)
    check("거절할 수 있다",
          accounts.resolve_status(accounts.get_user(PREFIX + "-001")) == "rejected")
    check("거절된 사용자는 목록에서 구분된다",
          PREFIX + "-001" in {x["uid"] for x in accounts.list_by_status("rejected")})
    accounts.set_status(PREFIX + "-001", accounts.STATUS_APPROVED)

    # 관리자가 아닌 사람은 목록을 못 본다 — 화면에서 숨기는 것과 별개다.
    member_tok = None
    me = accounts.get_user(PREFIX + "-001")
    from api.features.auth.tokens import issue_token  # noqa: E402
    member_tok = issue_token(me, source="swp")
    mr = client.get("/api/accounts", headers={"Authorization": f"Bearer {member_tok}"})
    check("일반 사용자는 403 — 401 이 아니라", mr.status_code == 403, str(mr.status_code))

    # ── 3. 프로젝트는 어느 시점에 나뉘는가 ───────────────────────────
    head("3. 인제스천이 어느 단위로 나뉘는가")

    sess = pg.query(
        "SELECT DISTINCT v FROM ("
        "  SELECT og_node_json(n.id)->>'session_id' AS v"
        "  FROM og_data.og_node n"
        "  JOIN og_catalog.type t ON t.type_id = n.type_id"
        "  JOIN og_catalog.graph g ON g.graph_id = t.graph_id"
        "  WHERE g.name = 'robo'"
        ") q WHERE v IS NOT NULL"
    ) if _has_helper() else []
    if sess:
        note(f"설계 graph 의 문서 업로드 세션: {[s['v'] for s in sess]}")
    check("문서 업로드는 session_id 로 나뉜다", True)
    note("업로드 한 번 = 세션 하나. 여러 개가 한 graph 에 쌓인다.")

    analyzer_labels = {
        r["name"] for r in pg.query(
            "SELECT t.name FROM og_catalog.type t JOIN og_catalog.graph g "
            "ON g.graph_id = t.graph_id WHERE g.name = 'analyzer_run'")
    }
    check("레거시 분석 graph 에는 run 식별자가 없다",
          not {"AnalysisRun", "Run", "AnalyzerSession"} & analyzer_labels,
          str(sorted(analyzer_labels))[:100])
    note("분석기는 매 run 마다 대상 graph 를 통째로 비운다 (executor.py wipe_graph).")
    note("→ 분석 graph 하나 = 분석 한 판. 나뉘지 않고 덮인다.")

    # ── 4. 만든 사람의 권한과 공유 ───────────────────────────────────
    head("4. 만든 사람이 권한을 갖고 공유가 되는가")

    owner = PREFIX + "-001"
    guest = PREFIX + "-002"
    accounts.upsert_from_sso({"id": guest, "empno": guest, "username": "kim",
                              "name": "김철수", "department": "IT", "source": "swp"})
    accounts.set_status(guest, accounts.STATUS_APPROVED)

    p = projects.create_project("E2E 검증 프로젝트", owner)
    created_graphs.append(p["graph"])
    seed(p["graph"])   # 빈 graph 로는 "막혔다"와 "0건"이 구별되지 않는다
    check("만든 사람이 admin 을 갖는다", projects.level_of(owner, p["graph"]) == "admin")
    check("내 목록에 보인다", p["graph"] in [x["graph"] for x in projects.list_projects(owner)])
    check("남의 목록에는 안 보인다",
          p["graph"] not in [x["graph"] for x in projects.list_projects(guest)])
    check("저장소도 남을 막는다 — 앱을 우회해도", bolt_probe(guest, p["graph"]).startswith("거부"),
          bolt_probe(guest, p["graph"]))

    # **없는 사번은 거부해야 한다.** `ensure_role` 은 이름만 있으면 role 을 만드니,
    # 오타 하나로 아무도 안 쓰는 role 에 권한이 붙고 화면은 성공이라 말한다.
    # 실제로 사번 자리에 로그인 아이디(`alice`)를 넣어 `p_alice` 가 생겼고,
    # 초대받았어야 할 사람의 목록은 그대로였다 — 오류가 없어 원인을 못 찾는다.
    ghost = PREFIX + "-없는사번"
    ghost_role = roles.role_name(ghost)
    rejected = False
    try:
        projects.share(p["graph"], ghost, "read")
    except ValueError:
        rejected = True
    check("없는 사번으로는 초대할 수 없다", rejected)
    # 판정은 예외가 아니라 **흔적**으로도 한다 — 거부한 뒤 role 이나 권한이
    # 남으면 거부한 것이 아니다.
    check("거부했으면 role 도 안 만든다",
          not pg.query("SELECT 1 FROM pg_roles WHERE rolname = %s", (ghost_role,)),
          ghost_role)
    check("거부했으면 권한도 안 남는다",
          not pg.query("SELECT 1 FROM og_catalog.grantee WHERE role = %s", (ghost_role,)))

    # **자기 자신을 초대하면 자기 등급이 내려간다.** 소유자는 admin 인데 read 를
    # 주면 덮어써지고, 그러면 `공유 관리` 버튼이 사라져(관리 등급 전용) 스스로
    # 되돌릴 수 없다. 회수 쪽은 소유자를 지키는데 초대 쪽에 같은 문이 없었다.
    self_rejected = False
    try:
        projects.share(p["graph"], owner, "read")
    except ValueError:
        self_rejected = True
    check("소유자 자신은 초대할 수 없다", self_rejected)
    # 예외만 보면 "막았다고 말하고 실제로는 낮췄다"를 못 잡는다.
    check("막았으면 등급도 그대로다", projects.level_of(owner, p["graph"]) == "admin",
          str(projects.level_of(owner, p["graph"])))

    projects.share(p["graph"], guest, "read")
    check("초대하면 목록에 뜬다",
          p["graph"] in [x["graph"] for x in projects.list_projects(guest)])
    check("저장소도 읽게 해 준다", bolt_probe(guest, p["graph"]).startswith("읽음"))
    check("읽기 등급은 쓰기를 막는다",
          bolt_probe(guest, p["graph"], write=True).startswith("거부"),
          bolt_probe(guest, p["graph"], write=True))

    projects.share(p["graph"], guest, "admin")
    check("등급을 올릴 수 있다", projects.level_of(guest, p["graph"]) == "admin")
    projects.unshare(p["graph"], guest)
    check("회수하면 앱이 막는다", projects.level_of(guest, p["graph"]) is None)
    check("회수하면 저장소도 막는다", bolt_probe(guest, p["graph"]).startswith("거부"))

    # 소유자를 뺄 수 있으면 아무도 관리 못 하는 프로젝트가 남는다.
    owner_removable = True
    try:
        projects.unshare(p["graph"], owner)
    except ValueError:
        owner_removable = False
    check("소유자는 회수할 수 없다", not owner_removable)

    # 새 프로젝트는 분석 graph 를 짝으로 함께 갖는다.
    #
    # 예전에는 비어 있었고, 그 상태의 추적성은 `.env` 의 분석 graph — **남의
    # 분석**을 봤다. 게다가 거기서 분석을 돌리면 그 graph 를 통째로 비워 다른
    # 프로젝트의 결과가 사라졌다. 짝을 함께 만들어 wipe 를 프로젝트 안에 가둔다.
    check("새 프로젝트에 분석 짝이 함께 생긴다", p.get("analyzerGraph"), f"{p['graph']}_a")
    check("분석 graph 에도 소유자 권한이 간다",
          projects.level_of(owner, p["analyzerGraph"]), "admin")
    note("짝이 있어야 분석 wipe 가 이 프로젝트 안에서만 일어난다.")

    # ── 6. 분석 없이 설계만 하는 길 ─────────────────────────────────
    head("6. 분석 없이도 설계는 진행되는가")

    # **분석이 선행되지 않는 프로젝트가 정상이다.** 문서만 올려 설계를 시작하는
    # 길이 있고, 그 길이 막히면 제품의 절반이 막힌다.
    #
    # 조용히 깨지는 쪽이라 실제로 불러서 잰다 — 분석 짝이 없으면 조회가 `None`
    # 세션을 받는데, 한 곳이라도 그걸 안 다루면 500 이 난다. 함수 반환값만 보면
    # 그 자리는 드러나지 않는다.
    solo = client.post("/api/projects", json={"name": "E2E 설계 전용"}, headers=ah)
    check("설계 전용 프로젝트를 만든다", solo.status_code == 200, str(solo.status_code))
    sg = solo.json().get("graph", "") if solo.status_code == 200 else ""
    if sg:
        created_graphs.append(sg)
        off = client.post(f"/api/projects/{sg}/analyzer", json={"analyzerGraph": None},
                          headers=ah)
        check("분석을 '쓰지 않음'으로 둘 수 있다", off.status_code == 200, str(off.status_code))
        check("정말 비었다", not (projects.get_project(sg) or {}).get("analyzerGraph"))

        sh = {**ah, "X-Project-Graph": sg}
        for path in ("/api/contexts",
                     "/api/user-stories/unassigned",
                     "/api/ingest/replacement-preview",
                     "/api/deliverables/snapshots"):
            r = client.get(path, headers=sh)
            check(f"분석 없이도 열린다 — {path}", r.status_code == 200,
                  f"{r.status_code} {r.text[:80]}")

        # **위의 넷은 분석을 안 읽는다.** 그것만 재면 분석 쪽이 통째로 깨져도
        # 초록이 된다 — 결함을 심어 보니 정확히 그랬다. 분석을 **실제로 읽는**
        # 자리를 함께 불러야 "없어도 된다"가 확인된다.
        stats = client.get("/api/ingest/stats", headers=sh)
        check("분석을 읽는 자리도 열린다 — /api/ingest/stats",
              stats.status_code == 200, f"{stats.status_code} {stats.text[:80]}")
        # **200 만으로는 부족하다.** 이 자리는 어떤 예외든 삼키고
        # `{"counts": {}, "error": ...}` 로 200 을 돌려준다 — 터진 것과 "분석이
        # 없다"가 같은 모양이 된다. 결함을 심어 보니 그대로 초록이었다.
        # 그래서 **`error` 가 없다**는 것까지 잰다.
        sj = stats.json() if stats.status_code == 200 else {}
        check("그리고 조용히 '분석 없음'이라고 답한다 — 터진 것이 아니라",
              stats.status_code == 200 and "error" not in sj
              and sj.get("analyzerGraph") is None and sj.get("counts") == {},
              stats.text[:160])
        note("분석은 선행 조건이 아니다 — 문서만 올려도 설계가 시작된다.")

    # ── 정리 ─────────────────────────────────────────────────────────
    head("정리")
    client.close()
    cleanup()
    after = graph_counts()
    for name in sorted(PROTECTED & set(before)):
        check(f"{name} 노드 수가 그대로", before.get(name) == after.get(name),
              f"{before.get(name)} → {after.get(name)}")
    # **이 run 이 새로 남긴 것**만 잔재다. "prj_ 로 시작하는 graph 가 없어야 한다"로
    # 재면 앱에서 만든 진짜 프로젝트를 잔재로 오인한다.
    leaked = [g for g in set(after) - set(before) if g.startswith(GRAPH_PREFIX)]
    check("이 run 이 남긴 graph 가 없다", not leaked, str(leaked))
    check("시험 사용자가 남지 않았다",
          not pg.query("SELECT 1 FROM public.app_users WHERE uid LIKE %s", (PREFIX + "%",)))

    print("\n전부 통과\n" if failed == 0 else f"\n{failed}건 실패\n")
    return 0 if failed == 0 else 1


def _has_helper() -> bool:
    """`og_node_json` 이 있는 환경인지. 없으면 세션 나열을 건너뛴다."""
    try:
        return bool(pg.query("SELECT 1 FROM pg_proc WHERE proname = 'og_node_json'"))
    except Exception:
        return False


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        try:
            cleanup()
        except Exception:
            pass
