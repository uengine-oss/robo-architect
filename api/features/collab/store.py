"""같은 프로젝트를 여럿이 볼 때 — 변경 알림과 접속자.

## 왜 필요한가

**새로고침해야 상대 변경이 보인다.** 실측이다 — bob 이 0 을 세고, alice 가
쓰고, bob 이 다시 세면 1 이다. 응답은 늘 최신인데 **다시 물을 계기가 없다.**

프런트에는 이미 `robo:data-changed` 버스가 있고 탭 네비게이터·캔버스가 전부
거기 붙어 있다. 모자란 것은 그 버스를 **다른 사람의 쓰기**로도 울리게 할
신호원이다. 여기가 그 신호원이다.

## 무엇을 신호로 쓰나

`og_data.og_audit`(질의 로그)에 트리거를 걸 수도 있다 — 실측으로 되는 것도
확인했다. 그런데 그것은 **저장소가 무엇을 실행했나**이지 "이 프로젝트가
바뀌었다"가 아니고, 앱이 모르는 경로까지 울린다.

우리는 **모든 쓰기가 API 를 지난다.** 그래서 신호원은 앱 계층에 둔다 —
요청이 성공적으로 끝나면 그 프로젝트의 판 번호를 하나 올린다.

## 왜 프로세스 메모리가 아니라 Postgres 인가

uvicorn 이 **여러 워커**로 뜬다(실측: 8000 에 두 프로세스). 판 번호를 프로세스
메모리에 두면 A 워커가 처리한 쓰기를 B 워커에 붙은 사람이 영영 못 본다.
조용히 반쪽만 도는 부류다 — [[singleton-client-ignores-request]] 와 같은 뿌리.

접속자도 같은 이유로 표에 둔다.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from api.platform import pg

# graph 이름이 SQL 로 들어간다. 값 바인딩이라 주입은 안 되지만, 표를 엉뚱한
# 이름으로 채우면 알림이 영영 안 맞는다 — 형태를 여기서 한 번 막는다.
_GRAPH = re.compile(r"^[A-Za-z0-9_]{1,63}$")

# 접속자로 셈하는 시간. 스트림이 이 주기보다 자주 자기를 갱신한다.
PRESENCE_TTL_SECONDS = 15

_SCHEMA = """
CREATE TABLE IF NOT EXISTS public.app_project_revisions (
    graph       TEXT PRIMARY KEY,
    rev         BIGINT NOT NULL DEFAULT 0,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_uid   TEXT,
    reason      TEXT
);

CREATE TABLE IF NOT EXISTS public.app_project_presence (
    graph        TEXT NOT NULL,
    uid          TEXT NOT NULL,
    display_name TEXT,
    last_seen    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (graph, uid)
);
CREATE INDEX IF NOT EXISTS idx_app_presence_seen
    ON public.app_project_presence (graph, last_seen DESC);
"""


def ensure_schema() -> None:
    with pg.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)


def valid_graph(graph: Optional[str]) -> bool:
    return bool(graph and _GRAPH.match(graph))


# ── 변경 알림 ────────────────────────────────────────────────────────────

def bump(graph: Optional[str], *, actor_uid: str | None = None,
         reason: str | None = None) -> Optional[int]:
    """이 프로젝트가 바뀌었다고 표시한다. 새 판 번호를 돌려준다.

    **절대 던지지 않는다.** 알림이 안 되는 것보다 쓰기가 실패하는 쪽이 훨씬
    나쁘다 — 이 함수는 응답을 내보낸 뒤에도 불린다.
    """
    if not valid_graph(graph):
        return None
    try:
        rows = pg.query(
            """
            INSERT INTO public.app_project_revisions (graph, rev, actor_uid, reason)
            VALUES (%s, 1, %s, %s)
            ON CONFLICT (graph) DO UPDATE
               SET rev = public.app_project_revisions.rev + 1,
                   changed_at = now(),
                   actor_uid = EXCLUDED.actor_uid,
                   reason = EXCLUDED.reason
            RETURNING rev
            """,
            (graph, actor_uid, (reason or "")[:64] or None),
        )
        return int(rows[0]["rev"]) if rows else None
    except Exception:
        # 알림은 편의다. 여기서 요청을 깨뜨리지 않는다.
        return None


def revision(graph: str) -> dict[str, Any]:
    """현재 판. 한 번도 안 바뀐 프로젝트는 0 이다 — 없는 것이 아니다."""
    rows = pg.query(
        "SELECT rev, actor_uid, reason, changed_at "
        "FROM public.app_project_revisions WHERE graph = %s",
        (graph,),
    )
    if not rows:
        return {"rev": 0, "actorUid": None, "reason": None}
    r = rows[0]
    return {
        "rev": int(r["rev"]),
        "actorUid": r["actor_uid"],
        "reason": r["reason"],
        "changedAt": r["changed_at"].isoformat() if r["changed_at"] else None,
    }


# ── 접속자 ───────────────────────────────────────────────────────────────

def heartbeat(graph: str, uid: str, display_name: str | None = None) -> None:
    """내가 아직 이 프로젝트를 보고 있다. 스트림이 한 바퀴마다 부른다."""
    if not valid_graph(graph) or not uid:
        return
    try:
        pg.execute(
            """
            INSERT INTO public.app_project_presence (graph, uid, display_name, last_seen)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (graph, uid) DO UPDATE
               SET last_seen = now(), display_name = EXCLUDED.display_name
            """,
            (graph, uid, display_name),
        )
    except Exception:
        return


def leave(graph: str, uid: str) -> None:
    """창을 닫았다. 안 불려도 TTL 이 걷어가지만, 불리면 즉시 사라진다."""
    if not valid_graph(graph) or not uid:
        return
    try:
        pg.execute(
            "DELETE FROM public.app_project_presence WHERE graph = %s AND uid = %s",
            (graph, uid),
        )
    except Exception:
        return


def viewers(graph: str) -> list[dict[str, Any]]:
    """지금 이 프로젝트를 보고 있는 사람들.

    **끊긴 사람을 계속 보여주면 안 된다** — 잠금을 붙일 때 "저 사람이 잡고
    있다"의 근거가 이 목록이라, 유령이 남으면 아무도 못 고치게 된다.
    """
    if not valid_graph(graph):
        return []
    rows = pg.query(
        """
        SELECT p.uid, p.display_name, p.last_seen,
               u.value->>'displayName' AS user_name
          FROM public.app_project_presence p
          LEFT JOIN public.app_users u ON u.uid = p.uid
         WHERE p.graph = %s
           AND p.last_seen > now() - make_interval(secs => %s)
         ORDER BY p.last_seen DESC
        """,
        (graph, PRESENCE_TTL_SECONDS),
    )
    return [
        {
            "uid": r["uid"],
            "displayName": r["user_name"] or r["display_name"] or r["uid"],
            "lastSeen": r["last_seen"].isoformat() if r["last_seen"] else None,
        }
        for r in rows
    ]
