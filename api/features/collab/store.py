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
    session      TEXT,
    acquired_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (graph, element_id)
);
CREATE INDEX IF NOT EXISTS idx_app_locks_holder
    ON public.app_element_locks (graph, uid);

ALTER TABLE IF EXISTS public.app_element_locks
    ADD COLUMN IF NOT EXISTS session TEXT;

CREATE TABLE IF NOT EXISTS public.app_collab_sessions (
    graph      TEXT NOT NULL,
    uid        TEXT NOT NULL,
    session    TEXT NOT NULL,
    last_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (graph, uid, session)
);
CREATE INDEX IF NOT EXISTS idx_app_sessions_holder
    ON public.app_collab_sessions (graph, uid, last_seen DESC);

CREATE TABLE IF NOT EXISTS public.app_project_changes (
    graph      TEXT NOT NULL,
    rev        BIGINT NOT NULL,
    actor_uid  TEXT,
    changes    JSONB NOT NULL,
    at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (graph, rev)
);
"""

# 판마다 변경 목록을 얼마나 남길 것인가. 뒤처진 창이 따라잡을 만큼만 남기고
# 버린다 — 이것은 이력이 아니라 **따라잡기용 꼬리**다. 더 뒤처진 창은 목록 대신
# "통째로 다시 읽어라"를 받는다.
CHANGE_TAIL = 200

# 잠금의 수명은 **시계가 아니라 접속**이다.
#
# 전에는 `LOCK_TTL_SECONDS = 60` 이었고, 그 60초를 갱신하는 것은 SSE 스트림뿐이었다.
# 두 방향으로 다 틀렸다.
#
#     스트림이 끊기면        `release_all` 이 **그 자리에서** 잠금을 놓았다.
#                            사람은 화면 앞에 앉아 글자를 치고 있는데. 60초를
#                            기다리지도 않는다 — 실측으로 10초 안에 사라졌다
#     스트림 종료를 못 보면   반열림 연결·백엔드 재시작. 잠금이 60초를 더 산다
#
# 재야 하는 것은 "몇 초가 지났나"가 아니라 **"그 사람이 아직 붙어 있나"** 다.
# 그 사실은 `app_collab_sessions` 가 들고 있다 — 창(탭)마다 한 행이고, 앱이
# **스트림과 별개로** 보통 HTTP 로 갱신한다. 그래서 SSE 만 끊기는 흔한 경우
# (프록시·절전·재연결 백오프)에 잠금이 안 풀린다.
#
# 이 값은 반드시 `PRESENCE_TTL_SECONDS` 보다 커야 한다. 같거나 작으면 접속자
# 목록이 깜빡이는 순간에 잠금이 걷힌다.
LOCK_ABSENT_GRACE_SECONDS = 25

# 창이 자기를 알리는 주기(화면 쪽 값)보다 넉넉해야 한다 — 5초마다 알리므로
# 다섯 번을 놓쳐도 버틴다.
assert LOCK_ABSENT_GRACE_SECONDS > PRESENCE_TTL_SECONDS

# 보유자가 아직 붙어 있는가. **한 곳에만 적는다** — `locks()` 와
# `blocking_holder()` 와 `acquire_lock()` 이 기준을 따로 들면, 한쪽에는 보이는데
# 다른 쪽에서는 못 집는 상태가 생긴다.
# 잠금은 **사람이 아니라 창**에 묶인다.
#
# 사람에만 묶었더니, 창을 둘 열어 둔 사람이 편집하던 창을 닫아도 다른 창이
# 살아 있다는 이유로 잠금이 남았다. 남은 창은 그 요소를 열고 있지도 않은데
# 아무도 못 고치게 된다.
#
# `l.session` 이 비어 있으면(옛 행·스크립트) 사람 기준으로 본다 — 그것까지
# 막으면 잠금을 안 거치는 쓰기가 영구 잠금이 된다.
_HOLDER_PRESENT = """
    EXISTS (SELECT 1 FROM public.app_collab_sessions s
             WHERE s.graph = l.graph AND s.uid = l.uid
               AND (l.session IS NULL OR l.session = '' OR s.session = l.session)
               AND s.last_seen > now() - make_interval(secs => {grace}))
""".format(grace=LOCK_ABSENT_GRACE_SECONDS)


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

def heartbeat(graph: str, uid: str, display_name: str | None = None,
              session: str | None = None) -> None:
    """내가 아직 이 프로젝트를 보고 있다.

    **접속자 표시와 잠금 수명을 같은 자리에서 올린다.** 둘을 다른 곳에서 올리면
    수명이 갈리고, 갈린 순간 "접속자에는 있는데 잠금은 만료된" 상태가 생긴다 —
    그게 정확히 전에 있던 고장이다(접속 15초 · 잠금 60초).

    `session` 은 **창(탭) 하나**를 가리킨다. 사람이 아니라 창을 세는 이유는,
    한 사람이 창을 둘 열었을 때 하나를 닫는다고 다른 창의 잠금이 죽으면 안
    되기 때문이다.
    """
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
        if session:
            pg.execute(
                """
                INSERT INTO public.app_collab_sessions (graph, uid, session, last_seen)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (graph, uid, session) DO UPDATE SET last_seen = now()
                """,
                (graph, uid, session),
            )
    except Exception:
        return


def live_sessions(graph: str, uid: str, exclude: str | None = None) -> int:
    """이 사람의 창이 아직 몇 개 붙어 있나. `exclude` 는 지금 닫는 창."""
    if not valid_graph(graph) or not uid:
        return 0
    rows = pg.query(
        """
        SELECT count(*) AS n FROM public.app_collab_sessions
         WHERE graph = %s AND uid = %s
           AND (%s IS NULL OR session <> %s)
           AND last_seen > now() - make_interval(secs => %s)
        """,
        (graph, uid, exclude, exclude, LOCK_ABSENT_GRACE_SECONDS),
    )
    return int(rows[0]["n"]) if rows else 0


def leave(graph: str, uid: str, session: str | None = None) -> None:
    """창을 닫았다. 안 불려도 유예가 걷어가지만, 불리면 즉시 사라진다.

    **창이 여럿이면 마지막 창을 닫을 때만 접속자에서 뺀다.** 한 창을 닫았다고
    그 사람이 떠난 것은 아니다.
    """
    if not valid_graph(graph) or not uid:
        return
    try:
        if session:
            pg.execute(
                "DELETE FROM public.app_collab_sessions "
                "WHERE graph = %s AND uid = %s AND session = %s",
                (graph, uid, session),
            )
            if live_sessions(graph, uid):
                return
        else:
            pg.execute(
                "DELETE FROM public.app_collab_sessions WHERE graph = %s AND uid = %s",
                (graph, uid),
            )
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
                 label: str | None = None,
                 session: str | None = None) -> dict[str, Any]:
    """이 요소를 내가 잡는다. 이미 남이 잡고 있으면 그 사람을 돌려준다.

    한 문장으로 끝내는 것이 핵심이다. "만료된 것을 지우고 → 넣는다"로 나누면
    그 사이에 둘이 들어온다.
    """
    if not valid_graph(graph) or not element_id or not uid:
        return {"ok": False, "reason": "invalid"}
    rows = pg.query(
        """
        INSERT INTO public.app_element_locks
               (graph, element_id, uid, display_name, label, session)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (graph, element_id) DO UPDATE
           SET uid = EXCLUDED.uid,
               display_name = EXCLUDED.display_name,
               label = EXCLUDED.label,
               session = EXCLUDED.session,
               refreshed_at = now(),
               -- 내가 이미 갖고 있었으면 잡은 시각은 그대로 둔다.
               acquired_at = CASE
                   WHEN public.app_element_locks.uid = EXCLUDED.uid
                   THEN public.app_element_locks.acquired_at ELSE now() END
         WHERE public.app_element_locks.uid = EXCLUDED.uid
            OR NOT EXISTS (
                   SELECT 1 FROM public.app_collab_sessions s
                    WHERE s.graph = public.app_element_locks.graph
                      AND s.uid = public.app_element_locks.uid
                      AND (public.app_element_locks.session IS NULL
                           OR public.app_element_locks.session = ''
                           OR s.session = public.app_element_locks.session)
                      AND s.last_seen > now() - make_interval(secs => %s))
        RETURNING uid, display_name, acquired_at
        """,
        (graph, element_id, uid, display_name, label, session, LOCK_ABSENT_GRACE_SECONDS),
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
    """마지막으로 이 사람이 잠금을 만진 시각을 적어 둔다.

    **이제 잠금의 생사를 정하는 값이 아니다.** 생사는 `app_collab_sessions` 가
    정한다(`_HOLDER_PRESENT`). 이 열은 "언제부터 이 상태였나"를 사람이 볼 때만
    쓴다 — 지우면 진단할 때 눈이 하나 없어진다.
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


def release_all(graph: str, uid: str, session: str | None = None) -> None:
    """창을 닫았다. 유예를 기다리지 않고 바로 푼다.

    `session` 을 주면 **그 창이 잡은 것만** 푼다. 같은 사람의 다른 창이 고치고
    있는 것까지 놓아 버리면 안 된다.
    """
    if not valid_graph(graph) or not uid:
        return
    try:
        if session:
            pg.execute(
                "DELETE FROM public.app_element_locks "
                "WHERE graph = %s AND uid = %s "
                "AND (session = %s OR session IS NULL OR session = '')",
                (graph, uid, session),
            )
        else:
            pg.execute(
                "DELETE FROM public.app_element_locks WHERE graph = %s AND uid = %s",
                (graph, uid),
            )
    except Exception:
        return


def sweep_absent_locks(graph: str | None = None) -> int:
    """보유자가 사라진 잠금을 **지운다.** 지운 개수를 돌려준다.

    **못 했으면 -1 이다.** 0 과 같은 값으로 돌려주면 "치울 게 없었다"와
    "치우려다 실패했다"가 구별이 안 된다 — 이 저장소가 반복해서 낸 고장이 그
    모양이고, 이 함수도 처음 판에서 정확히 그렇게 틀렸다(파라미터 타입 오류를
    `except` 가 먹고 0 을 냈다).

    숨기는 것만으로는 부족하다 — `locks()` 가 안 보여 줘도 행이 남아 있으면
    `ON CONFLICT` 가 그 행을 계속 만나고, 무엇보다 **표를 들여다본 사람이
    유령을 진짜로 착각한다.**

    두 자리에서 돈다. 스트림 한 바퀴마다(붙어 있는 창이 있을 때), 그리고
    **기동 시 한 번** — 붙은 창이 하나도 없을 때가 유령이 가장 잘 남는 자리이고,
    그때는 한 바퀴도 안 돈다. 백엔드를 재시작하면 정확히 그 상태가 된다.
    """
    if graph is not None and not valid_graph(graph):
        return -1
    try:
        # `%s::text` 의 캐스트가 필요하다. 없으면 Postgres 가 `%s IS NULL` 의
        # 타입을 못 정해 `IndeterminateDatatype` 을 던진다.
        return pg.execute(
            """
            DELETE FROM public.app_element_locks l
             WHERE (%s::text IS NULL OR l.graph = %s::text)
               AND NOT """ + _HOLDER_PRESENT + """
            """,
            (graph, graph),
        )
    except Exception as exc:  # noqa: BLE001 — 정리가 실패해도 앱은 돌아야 한다
        _log_sweep_failure(exc)
        return -1


def _log_sweep_failure(exc: Exception) -> None:
    """조용히 넘기지 않는다 — 다음 사람이 "0건"을 답으로 읽지 않게."""
    try:
        from api.platform.observability.smart_logger import SmartLogger
        SmartLogger.log(
            "WARN",
            f"보유자 없는 선점 정리에 실패했다: {exc}",
            category="collab.locks.sweep_failed",
            params={"error": str(exc)[:300]},
        )
    except Exception:  # noqa: BLE001 — 로깅 실패가 앱을 막으면 안 된다
        print(f"[collab] 선점 정리 실패: {exc}", flush=True)


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
           AND """ + _HOLDER_PRESENT + """
         ORDER BY l.acquired_at
        """,
        (graph,),
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


def blocking_holder(graph: Optional[str], element_id: str, uid: str) -> dict[str, Any] | None:
    """이 요소를 **남이** 잡고 있으면 그 사람. 아니면 None.

    내 잠금은 막지 않는다. 아무도 안 잡고 있어도 막지 않는다 — 잠금을 안 거치는
    쓰기(일괄 작업·인제스천)가 있고, 그것까지 막으면 잠금이 기능을 세우는 게
    아니라 무너뜨린다.

    **만료된 잠금은 없는 것으로 친다.** 브라우저를 강제 종료한 사람의 잠금이
    남아 아무도 못 고치는 요소가 생기면 안 된다 — `locks()` 와 같은 기준이다.
    """
    if not valid_graph(graph) or not element_id or not uid:
        return None
    rows = pg.query(
        """
        SELECT l.uid,
               COALESCE(u.value->>'displayName', l.display_name, l.uid) AS who
          FROM public.app_element_locks l
          LEFT JOIN public.app_users u ON u.uid = l.uid
         WHERE l.graph = %s
           AND l.element_id = %s
           AND l.uid <> %s
           AND """ + _HOLDER_PRESENT + """
        """,
        (graph, element_id, uid),
    )
    if not rows:
        return None
    return {"uid": rows[0]["uid"], "displayName": rows[0]["who"]}


# ── 무엇이 바뀌었는가 ────────────────────────────────────────────────────
#
# "뭔가 바뀌었다"만 보내면 받는 쪽이 통째로 다시 읽는다. 그러면 편집 중이던
# 화면이 초기화되고, Inspector 의 federated 편집기가 깨진다(done §49).
#
# **그런데 서버는 이미 무엇이 바뀌었는지 알고 있다.** `/api/chat/confirm` 이
# `appliedChanges` 를 만들어 돌려주고, 화면은 그것을 `syncAfterChanges` 로
# 제자리에 적용한다 — 자기 창에서는 이미 그렇게 돌고 있었다. 남의 창에도 같은
# 목록을 주면 같은 길로 반영된다.
#
#     자기 창    응답의 appliedChanges  →  syncAfterChanges
#     남의 창    스트림의 changes       →  syncAfterChanges   ← 여기를 잇는다
#
# 목록을 못 주는 쓰기(그 밖의 42곳)는 지금처럼 "판이 올랐다"만 보낸다. 그쪽은
# 받는 쪽이 통째로 다시 읽는다 — **정밀한 길과 거친 길을 섞어 두는 것이지,
# 거친 길을 없애는 것이 아니다.**

def publish(graph: Optional[str], changes: list[dict[str, Any]], *,
            actor_uid: str | None = None) -> Optional[int]:
    """판을 올리면서 **무엇이 바뀌었는지**를 같이 남긴다.

    `bump` 과 마찬가지로 **절대 던지지 않는다.** 목록을 못 남겨도 판은 올라야
    하고(그래야 남의 창이 거친 길로라도 갱신된다), 무엇보다 쓰기가 깨지면 안 된다.
    """
    if not valid_graph(graph) or not changes:
        return None
    rev = bump(graph, actor_uid=actor_uid, reason="changes")
    if rev is None:
        return None
    try:
        import json as _json

        pg.execute(
            "INSERT INTO public.app_project_changes (graph, rev, actor_uid, changes) "
            "VALUES (%s, %s, %s, %s::jsonb) ON CONFLICT (graph, rev) DO NOTHING",
            (graph, rev, actor_uid, _json.dumps(changes, ensure_ascii=False)),
        )
        # 꼬리만 남긴다. 안 지우면 프로젝트마다 무한히 쌓인다.
        pg.execute(
            "DELETE FROM public.app_project_changes "
            " WHERE graph = %s AND rev <= %s - %s",
            (graph, rev, CHANGE_TAIL),
        )
    except Exception:
        # 판은 이미 올랐다. 받는 쪽은 목록 없이 거친 길로 간다.
        return rev
    return rev


def changes_since(graph: str, since_rev: int, upto_rev: int) -> Optional[list[dict[str, Any]]]:
    """`since_rev` 다음부터 `upto_rev` 까지의 변경 목록.

    **`None` 은 "모른다"이지 "없다"가 아니다.** 중간에 목록 없는 판이 하나라도
    끼면 정밀하게 못 따라잡으므로 `None` 을 준다 — 받는 쪽이 통째로 다시 읽게.
    이 구분을 빈 리스트와 합치면 **빠진 변경이 조용히 사라진다.**
    """
    if not valid_graph(graph) or upto_rev <= since_rev:
        return []
    rows = pg.query(
        "SELECT rev, changes FROM public.app_project_changes "
        " WHERE graph = %s AND rev > %s AND rev <= %s ORDER BY rev",
        (graph, since_rev, upto_rev),
    )
    # 판 하나마다 목록이 하나씩 있어야 빠짐없이 따라잡은 것이다.
    if len(rows) != upto_rev - since_rev:
        return None
    out: list[dict[str, Any]] = []
    for r in rows:
        payload = r["changes"]
        if isinstance(payload, list):
            out.extend(payload)
    return out
