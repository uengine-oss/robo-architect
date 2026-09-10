"""프로젝트 = graph · 공유 · 권한 검사.

실제 Postgres 와 Ontological 에 대고 돌린다. `og_create_graph`/`og_grant` 는
저장소 함수라 흉내로는 확인이 안 된다.

**안전장치**

```
만든 graph 만 지운다          이름을 목록에 담아 두고 그것만 og_drop_graph 한다
접두사를 두 번 확인한다        prj_ 로 시작하지 않으면 지우지 않는다
보호 목록을 둔다              robo · analyzer_run · analyzer 는 어떤 경우에도 제외
끝나고 실 graph 를 다시 센다   노드 수가 그대로인지 확인한다
```

한 번 설계 graph 를 통째로 날린 적이 있어(`STATUS.md` §4.2) 이중으로 막는다.

    robo-architect/.venv/bin/python scripts/verify_projects.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ.setdefault("AUTH_JWT_SECRET", "verify-only-secret")
os.environ["AUTH_ROLE_SECRET"] = "verify-only-role-secret"

from api.platform import pg  # noqa: E402
from api.features.accounts import store as accounts  # noqa: E402
from api.features.projects import roles, store  # noqa: E402

USER_PREFIX = "ZZPROJ"
GRAPH_PREFIX = "prj_"
# 어떤 경우에도 손대지 않는다.
PROTECTED = {"robo", "analyzer_run", "analyzer", "probe", "anlz_probe", "wr_probe"}

created_graphs: list[str] = []
# 시작 시점의 role 목록. 끝나고 늘어난 것만 지운다 — 이름 규칙을 예상해 지우면
# 규칙이 바뀐 코드를 검사할 때(결함을 심었을 때) 잔재가 남는다.
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
        "SELECT g.name AS name, count(n.*) AS c "
        "FROM og_catalog.graph g "
        "LEFT JOIN og_catalog.type t ON t.graph_id = g.graph_id "
        "LEFT JOIN og_data.og_node n ON n.type_id = t.type_id "
        "GROUP BY g.name"
    )
    return {r["name"]: int(r["c"]) for r in rows}


def cleanup() -> None:
    """만든 것만 지운다. 보호 목록과 접두사를 둘 다 확인한다."""
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

    # 늘어난 role 만 지운다. 권한을 들고 있으면 DROP ROLE 이 거부되므로 먼저
    # 소유·권한을 떼어 낸다.
    if not roles_at_start:
        return
    now = {r["rolname"] for r in pg.query("SELECT rolname FROM pg_roles")}
    for role in sorted(now - roles_at_start):
        if role in PROTECTED_ROLES or not role.startswith("p_"):
            continue
        try:
            pg.execute(f'DROP OWNED BY "{role}"')
        except Exception:
            pass
        try:
            pg.execute(f'DROP ROLE IF EXISTS "{role}"')
        except Exception as exc:
            print(f"  !! role {role} 정리 실패: {str(exc)[:80]}")


def main() -> int:
    accounts.ensure_schema()
    store.ensure_schema()
    roles_at_start.update(r["rolname"] for r in pg.query("SELECT rolname FROM pg_roles"))
    before = graph_node_counts()
    print(f"\n시작 — graph {len(before)}개")

    owner = USER_PREFIX + "-OWNER"
    guest = USER_PREFIX + "-GUEST"
    for uid in (owner, guest):
        accounts.upsert_from_sso({"empno": uid, "id": uid, "username": uid, "name": uid})

    print("\nrole")
    check("비밀이 있으면 role 비밀번호를 만든다", roles.role_secret_configured())
    r = roles.ensure_role(owner)
    check("role 을 만든다", roles.role_exists(r), r)
    check("이름이 사번에서 나온다", r == "p_zzproj_owner", r)
    check("여러 번 불러도 안전하다", roles.ensure_role(owner) == r)
    check("같은 사번이면 같은 비밀번호",
          roles.role_password(owner) == roles.role_password(owner))
    check("다른 사번이면 다른 비밀번호",
          roles.role_password(owner) != roles.role_password(guest))

    print("\n프로젝트 만들기")
    p = store.create_project("인사관리 설계", owner)
    created_graphs.append(p["graph"])
    check("graph 가 생겼다", store.graph_exists(p["graph"]), p["graph"])
    check("graph 이름이 사람 이름과 분리돼 있다", p["graph"].startswith(GRAPH_PREFIX))
    check("한글 이름이 그대로 남는다", p["displayName"] == "인사관리 설계")
    check("소유자에게 admin 이 갔다", store.level_of(owner, p["graph"]) == "admin")
    check("이름이 비면 거부한다", _raises(store.create_project, "  ", owner))

    print("\n목록은 내 것만")
    mine = [x["graph"] for x in store.list_projects(owner)]
    check("소유자에게 보인다", p["graph"] in mine)
    check("남에게는 안 보인다", p["graph"] not in [x["graph"] for x in store.list_projects(guest)])

    print("\n공유는 호출 한 줄")
    store.share(p["graph"], guest, "read")
    check("초대하면 등급이 생긴다", store.level_of(guest, p["graph"]) == "read")
    check("초대받은 사람 목록에 뜬다",
          p["graph"] in [x["graph"] for x in store.list_projects(guest)])
    check("등급도 함께 온다",
          next(x for x in store.list_projects(guest) if x["graph"] == p["graph"])["level"] == "read")
    store.share(p["graph"], guest, "write")
    check("등급을 올릴 수 있다", store.level_of(guest, p["graph"]) == "write")
    check("알 수 없는 등급은 거부한다", _raises(store.share, p["graph"], guest, "superuser"))
    check("없는 프로젝트에는 공유하지 않는다", _raises(store.share, "prj_nope", guest, "read"))

    print("\n참여자")
    ms = {m["uid"]: m for m in store.members(p["graph"])}
    check("소유자와 초대받은 사람이 보인다", owner in ms and guest in ms, str(list(ms)))
    check("등급이 실린다", ms[owner]["level"] == "admin" and ms[guest]["level"] == "write")
    check("이름을 사용자 표에서 찾아 붙인다", ms[guest]["displayName"] == guest)

    print("\n회수")
    store.unshare(p["graph"], guest)
    check("회수하면 등급이 사라진다", store.level_of(guest, p["graph"]) is None)
    check("목록에서도 빠진다",
          p["graph"] not in [x["graph"] for x in store.list_projects(guest)])
    check("소유자는 회수할 수 없다 — 관리자가 없는 프로젝트가 남는다",
          _raises(store.unshare, p["graph"], owner))

    print("\n기존 graph 등록")
    check("없는 graph 는 우리 쪽에서 먼저 거부한다 — 저장소 오류에 기대지 않는다",
          _raises(store.adopt_graph, "prj_nope", "없음", owner,
                  expect=ValueError, message="그런 graph 가 없다"))
    check("형식에 안 맞는 이름도 거부한다",
          _raises(store.adopt_graph, "Robo Graph!", "x", owner,
                  expect=ValueError, message="형식"))
    check("있는 graph 는 등록된다", _adopt_roundtrip(owner))
    p2 = store.create_project("두 번째", owner)
    created_graphs.append(p2["graph"])
    store.drop_project(p2["graph"])  # 표에서 지우고 graph 만 남기지 않는다
    created_graphs.remove(p2["graph"])
    check("지운 프로젝트는 목록에서 사라진다",
          p2["graph"] not in [x["graph"] for x in store.list_projects(owner)])

    print("\n실 데이터 확인")
    cleanup()
    after = graph_node_counts()
    for name in sorted(PROTECTED & set(before)):
        check(f"{name} 노드 수가 그대로", before.get(name) == after.get(name),
              f"{before.get(name)} → {after.get(name)}")
    # **이 run 이 새로 남긴 것**만 잔재다. "prj_ 로 시작하는 graph 가 없어야 한다"로
    # 재면 앱에서 만든 진짜 프로젝트를 잔재로 오인한다.
    leaked = [g for g in set(after) - set(before) if g.startswith(GRAPH_PREFIX)]
    check("이 run 이 남긴 graph 가 없다", not leaked, str(leaked))

    print("\n전부 통과\n" if failed == 0 else f"\n{failed}건 실패\n")
    return 0 if failed == 0 else 1


def _raises(fn, *args, expect: type = Exception, message: str = "") -> bool:
    """예상한 종류의 오류가, 예상한 말과 함께 나는가.

    아무 오류나 통과시키면 **저장소가 대신 죽어 준 것**을 우리 검증으로 착각한다.
    """
    try:
        fn(*args)
        return False
    except expect as exc:
        return message in str(exc) if message else True
    except Exception:
        return False


def _adopt_roundtrip(owner: str) -> bool:
    """실제로 있는 graph 를 등록해 목록에 뜨는지 본다."""
    p = store.create_project("등록 대상", owner)
    created_graphs.append(p["graph"])
    pg.execute("DELETE FROM public.app_projects WHERE graph = %s", (p["graph"],))
    store.adopt_graph(p["graph"], "다시 등록", owner)
    return any(x["graph"] == p["graph"] and x["displayName"] == "다시 등록"
               for x in store.list_projects(owner))


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        try:
            cleanup()
        except Exception:
            pass
