"""동시편집 — 변경 알림·접속자·선점 잠금 검사.

실제 Postgres 에 대고 돌린다. **이 기능의 핵심이 동시성이라 흉내로는 확인이
안 된다** — 16개 스레드가 동시에 같은 요소를 집는 것을 실제로 시켜 봐야 한다.

실측으로 드러난 것이 이 파일의 이유다. §17-1 은 Cypher 관용구

    MATCH (n) WHERE n.lockedBy IS NULL SET n.lockedBy = $me

가 Ontological 에서 성립한다고 적었는데, 다시 재니 **아니었다.**

    A 속성이 아직 없다      잡음 1 · 거절 10 · 오류 5
    B 안 잠긴 것을 16명     잡음 9   ← 아홉이 다 잡았다고 믿는다
    C 이미 잠긴 것을 16명   거절 16  (한번 잡히면 지켜진다)

그래서 잠금을 Postgres 기본키로 옮겼고, 여기서 **같은 조건으로** 다시 잰다.

**안전장치**

```
zz_ 로 시작하는 이름만 쓴다        실 프로젝트 graph 를 건드리지 않는다
표만 만지고 graph 는 안 만진다     설계 데이터에 손이 닿을 일이 없다
끝나고 만든 행만 지운다            graph 열로 걸러서 지운다
```

    robo-architect/.venv/bin/python scripts/verify_collab.py
"""

from __future__ import annotations

import concurrent.futures as cf
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ.setdefault("AUTH_JWT_SECRET", "verify-only-secret")
os.environ.setdefault("AUTH_ROLE_SECRET", "verify-only-role-secret")

from api.features.collab import notify, store  # noqa: E402
from api.platform import pg  # noqa: E402

# 실 프로젝트와 절대 안 겹치는 이름. 프로젝트 graph 는 `prj_` 로 시작한다.
G = "zz_verify_collab"
assert G.startswith("zz_"), "검사 graph 이름이 안전하지 않다"

_fail: list[str] = []
_n = 0


def check(label: str, got, want) -> None:
    global _n
    _n += 1
    ok = got == want
    print(f"{'ok ' if ok else 'FAIL'} {label}" + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        _fail.append(label)


def cleanup() -> None:
    for table in ("app_element_locks", "app_project_presence", "app_project_revisions"):
        try:
            pg.execute(f"DELETE FROM public.{table} WHERE graph = %s", (G,))
        except Exception:
            pass


def main() -> int:
    store.ensure_schema()
    cleanup()

    print("\n── 변경 알림 ───────────────────────────────────────────")
    check("한 번도 안 바뀐 프로젝트는 0 이다", store.revision(G)["rev"], 0)
    store.bump(G, actor_uid="U1", reason="probe")
    check("쓰면 판이 오른다", store.revision(G)["rev"], 1)
    check("누가 바꿨는지 실린다", store.revision(G)["actorUid"], "U1")
    store.bump(G, actor_uid="U2")
    check("다시 쓰면 또 오른다", store.revision(G)["rev"], 2)
    check("이름이 아닌 값은 판을 안 만든다", store.bump("../etc"), None)

    print("\n── 무엇에 울리는가 ─────────────────────────────────────")
    check("성공한 쓰기", notify.should_notify("POST", "/api/graph/x", 200), True)
    check("읽기에는 안 울린다", notify.should_notify("GET", "/api/graph/x", 200), False)
    check("실패한 쓰기에는 안 울린다", notify.should_notify("POST", "/api/graph/x", 403), False)
    check("스트림 자신에는 안 울린다",
          notify.should_notify("POST", "/api/collab/lock", 200), False)

    print("\n── 접속자 ──────────────────────────────────────────────")
    store.heartbeat(G, "U1", "일번")
    store.heartbeat(G, "U2", "이번")
    check("둘이 보고 있다", len(store.viewers(G)), 2)
    store.leave(G, "U2")
    check("나가면 바로 빠진다", [v["uid"] for v in store.viewers(G)], ["U1"])
    # 유령이 남으면 잠금의 근거가 무너진다 — 시간을 되돌려 확인한다.
    pg.execute(
        "UPDATE public.app_project_presence SET last_seen = now() - interval '1 hour' "
        "WHERE graph = %s",
        (G,),
    )
    check("끊긴 사람은 안 보인다", store.viewers(G), [])

    print("\n── 선점 잠금 ───────────────────────────────────────────")
    # **이 검사가 이 파일의 이유다.** 같은 조건에서 Cypher 는 9명이 잡았다.
    def grab(who: str) -> str:
        return "got" if store.acquire_lock(G, "e1", who, display_name=who)["ok"] else "refused"

    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        result = Counter(ex.map(grab, [f"u{i}" for i in range(16)]))
    check("16명이 동시에 집으면 한 명만 잡는다", result["got"], 1)
    check("나머지는 조용히 거절된다", result["refused"], 15)

    holder = store.locks(G)[0]["uid"]
    check("잡은 사람이 목록에 하나만 있다", len(store.locks(G)), 1)
    check("같은 사람이 다시 부르면 갱신이다",
          store.acquire_lock(G, "e1", holder)["ok"], True)
    other = "zz-other"
    denied = store.acquire_lock(G, "e1", other)
    check("남은 못 잡는다", denied["ok"], False)
    check("누가 갖고 있는지 알려 준다", denied["uid"], holder)

    check("남은 못 푼다", store.release_lock(G, "e1", other), False)
    check("주인은 푼다", store.release_lock(G, "e1", holder), True)
    check("풀면 목록에서 사라진다", store.locks(G), [])

    print("\n── 잠금이 남지 않는가 ──────────────────────────────────")
    store.acquire_lock(G, "e2", "ghost")
    pg.execute(
        "UPDATE public.app_element_locks SET refreshed_at = now() - interval '1 hour' "
        "WHERE graph = %s AND element_id = 'e2'",
        (G,),
    )
    check("갱신이 멎은 잠금은 안 보인다", store.locks(G), [])
    check("만료된 것은 뺏을 수 있다", store.acquire_lock(G, "e2", "newbie")["ok"], True)
    # 창을 닫으면 스트림이 부르는 자리.
    store.acquire_lock(G, "e3", "newbie")
    store.release_all(G, "newbie")
    check("창을 닫으면 내 잠금이 다 풀린다", store.locks(G), [])

    print("\n── 갱신이 만료를 이긴다 ────────────────────────────────")
    store.acquire_lock(G, "e4", "worker")
    pg.execute(
        "UPDATE public.app_element_locks SET refreshed_at = now() - interval '1 hour' "
        "WHERE graph = %s AND element_id = 'e4'",
        (G,),
    )
    store.refresh_locks(G, "worker")
    check("보고 있는 동안에는 안 만료된다",
          [l["elementId"] for l in store.locks(G)], ["e4"])

    cleanup()
    print(f"\n검사 {_n}종 — " + ("전부 통과" if not _fail else f"{len(_fail)}종 실패"))
    for f in _fail:
        print("  실패:", f)
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main())
