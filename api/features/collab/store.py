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

CREATE TABLE IF NOT EXISTS public.app_element_locks (
    graph        TEXT NOT NULL,
    element_id   TEXT NOT NULL,
    uid          TEXT NOT NULL,
    display_name TEXT,
    label        TEXT,
    acquired_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (graph, element_id)
);
CREATE INDEX IF NOT EXISTS idx_app_locks_holder
    ON public.app_element_locks (graph, uid);
"""

# 잠금이 저절로 풀리는 시간. 창을 닫으면 스트림이 끊기고 갱신이 멎는다.
# **이게 없으면 브라우저를 강제 종료한 사람이 요소를 영영 잠가 놓는다.**
LOCK_TTL_SECONDS = 60


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


# ── 요소 선점 잠금 ───────────────────────────────────────────────────────
#
# **그래프가 아니라 여기에 둔다.** §17-1 은 Cypher 관용구가 성립한다고 적었는데,
# 다시 재니 아니었다 — 안 잠긴 요소를 16명이 동시에 집으면 **아홉이 다 잡았다고
# 믿는다**(최종 주인은 마지막에 쓴 사람). 실측:
#
#     A 속성이 아직 없다      잡음 1 · 거절 10 · 오류 5   (카탈로그 동시 생성 경합)
#     B 안 잠긴 것을 16명     잡음 9   ← 취득이 안 막힌다
#     C 이미 잠긴 것을 16명   거절 16  (한번 잡히면 지켜진다)
#
# `MATCH ... WHERE ... SET` 이 한 UPDATE 로 내려가지 않는 것으로 보인다. 조건을
# 읽은 스냅샷과 쓰는 시점이 갈리면 **행 잠금이 조건을 다시 평가할 기회가 없다.**
#
# Postgres 기본키 위의 `INSERT ... ON CONFLICT` 는 진짜로 원자적이다. 덤으로
# 세 가지가 따라온다 — 설계 graph 를 안 더럽히고(분석기가 통째로 비우는 자리다),
# 스냅샷·산출물에 잠금 흔적이 안 섞이고, `og_add_property` 경합을 아예 안 만난다.

def acquire_lock(graph: str, element_id: str, uid: str,
                 display_name: str | None = None,
                 label: str | None = None) -> dict[str, Any]:
    """이 요소를 내가 잡는다. 이미 남이 잡고 있으면 그 사람을 돌려준다.

    한 문장으로 끝내는 것이 핵심이다. "만료된 것을 지우고 → 넣는다"로 나누면
    그 사이에 둘이 들어온다.
    """
    if not valid_graph(graph) or not element_id or not uid:
        return {"ok": False, "reason": "invalid"}
    rows = pg.query(
        """
        INSERT INTO public.app_element_locks
               (graph, element_id, uid, display_name, label)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (graph, element_id) DO UPDATE
           SET uid = EXCLUDED.uid,
               display_name = EXCLUDED.display_name,
               label = EXCLUDED.label,
               refreshed_at = now(),
               -- 내가 이미 갖고 있었으면 잡은 시각은 그대로 둔다.
               acquired_at = CASE
                   WHEN public.app_element_locks.uid = EXCLUDED.uid
                   THEN public.app_element_locks.acquired_at ELSE now() END
         WHERE public.app_element_locks.uid = EXCLUDED.uid
            OR public.app_element_locks.refreshed_at
               < now() - make_interval(secs => %s)
        RETURNING uid, display_name, acquired_at
        """,
        (graph, element_id, uid, display_name, label, LOCK_TTL_SECONDS),
    )
    if rows:
        return {"ok": True, "elementId": element_id, "uid": uid}
    # 못 잡았다 — 누가 갖고 있는지 알려 준다. "실패"만 말하면 화면이 아무것도
    # 설명하지 못한다.
    holder = pg.query(
        "SELECT uid, display_name, acquired_at FROM public.app_element_locks "
        "WHERE graph = %s AND element_id = %s",
        (graph, element_id),
    )
    h = holder[0] if holder else {}
    return {
        "ok": False,
        "reason": "held",
        "elementId": element_id,
        "uid": h.get("uid"),
        "displayName": h.get("display_name") or h.get("uid"),
    }


def release_lock(graph: str, element_id: str, uid: str) -> bool:
    """내 잠금만 푼다. **남의 것을 풀 수 있으면 잠금이 아니다.**"""
    if not valid_graph(graph) or not element_id or not uid:
        return False
    return pg.execute(
        "DELETE FROM public.app_element_locks "
        "WHERE graph = %s AND element_id = %s AND uid = %s",
        (graph, element_id, uid),
    ) > 0


def refresh_locks(graph: str, uid: str) -> None:
    """내가 아직 붙어 있다 — 스트림이 한 바퀴마다 부른다.

    갱신이 멎으면 TTL 이 걷어간다. 그게 창을 강제로 닫은 사람의 잠금을 푸는
    유일한 길이다.
    """
    if not valid_graph(graph) or not uid:
        return
    try:
        pg.execute(
            "UPDATE public.app_element_locks SET refreshed_at = now() "
            "WHERE graph = %s AND uid = %s",
            (graph, uid),
        )
    except Exception:
        return


def release_all(graph: str, uid: str) -> None:
    """창을 닫았다. TTL 을 기다리지 않고 바로 푼다."""
    if not valid_graph(graph) or not uid:
        return
    try:
        pg.execute(
            "DELETE FROM public.app_element_locks WHERE graph = %s AND uid = %s",
            (graph, uid),
        )
    except Exception:
        return


def locks(graph: str) -> list[dict[str, Any]]:
    """지금 잡혀 있는 것들. **만료된 것은 빼고 준다** — 유령 잠금을 보여 주면
    아무도 못 고치는 요소가 생긴다."""
    if not valid_graph(graph):
        return []
    rows = pg.query(
        """
        SELECT l.element_id, l.uid, l.label, l.acquired_at,
               COALESCE(u.value->>'displayName', l.display_name, l.uid) AS who
          FROM public.app_element_locks l
          LEFT JOIN public.app_users u ON u.uid = l.uid
         WHERE l.graph = %s
           AND l.refreshed_at > now() - make_interval(secs => %s)
         ORDER BY l.acquired_at
        """,
        (graph, LOCK_TTL_SECONDS),
    )
    return [
        {
            "elementId": r["element_id"],
            "uid": r["uid"],
            "displayName": r["who"],
            "label": r["label"],
            "since": r["acquired_at"].isoformat() if r["acquired_at"] else None,
        }
        for r in rows
    ]
