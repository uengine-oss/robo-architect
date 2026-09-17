#!/usr/bin/env python3
"""선점 수명 — 서버 쪽 근거.

화면 검사(`frontend/tests/collab-lock-lifetime.spec.ts`)가 못 보는 두 자리를 잰다.

    물리 행    `locks()` 가 안 보여 주는 것과 **행이 지워진 것**은 다르다.
               표를 들여다본 사람은 유령을 진짜로 착각한다
    기동 정리  붙은 창이 하나도 없을 때가 유령이 가장 잘 남는 자리다.
               그때는 스트림 한 바퀴도 안 돈다 — 백엔드 재시작이 정확히 그 상태다

spec: `specs/057-presence-bound-element-lock/`

    uv run python scripts/verify_collab_lock_lifetime.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("ROBO_API_URL", "http://localhost:8000")
CONTAINER = os.environ.get("OG_CONTAINER", "ontological-dev")

_fail: list[str] = []
_n = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _n
    _n += 1
    print(f"  {'✓' if ok else '✘'} {name}{('  — ' + detail) if detail and not ok else ''}")
    if not ok:
        _fail.append(f"{name}{(' — ' + detail) if detail else ''}")


def env_value(key: str) -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def sql(query: str) -> str:
    """물리 행을 직접 본다. **API 를 통하면 걸러진 것을 보게 된다.**"""
    pw = env_value("OG_PG_PASSWORD") or env_value("NEO4J_PASSWORD")
    out = subprocess.run(
        ["docker", "exec", "-e", f"PGPASSWORD={pw}", CONTAINER,
         "psql", "-h", "127.0.0.1", "-p", "28816", "-d", "og", "-U", "dev", "-Atc", query],
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0:
        raise RuntimeError(f"psql 실패: {out.stderr.strip()[:200]}")
    return out.stdout.strip()


def dev_password(login_id: str) -> str:
    if login_id == (os.environ.get("AUTH_DEV_LOGIN_ID") or "test"):
        return os.environ.get("AUTH_DEV_LOGIN_PASSWORD") or "test"
    for acc in env_value("AUTH_DEV_LOGIN_ACCOUNTS").split(","):
        f = acc.split(":")
        if f and f[0].strip() == login_id and len(f) > 1:
            return f[1]
    raise RuntimeError(f".env 의 AUTH_DEV_LOGIN_ACCOUNTS 에 '{login_id}' 가 없다")


def login(login_id: str) -> tuple[str, str]:
    r = httpx.post(f"{API}/api/auth/dev-login",
                   files={"loginId": (None, login_id), "password": (None, dev_password(login_id))},
                   timeout=30)
    body = r.json()
    if not body.get("accessToken"):
        raise RuntimeError(f"{login_id} 로그인 실패: {r.status_code}")
    return body["accessToken"], body.get("user", {}).get("uid", "")


def writable_graph(token: str) -> str:
    r = httpx.get(f"{API}/api/projects", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    for p in r.json().get("projects", []):
        if p.get("level") and p["level"] != "read":
            return p["graph"]
    raise RuntimeError("쓰기 권한이 있는 프로젝트가 없다")


def h(token: str, graph: str, session: str | None = None) -> dict:
    head = {"Authorization": f"Bearer {token}", "X-Project-Graph": graph}
    if session:
        head["X-Collab-Session"] = session
    return head


def lock(token: str, graph: str, element_id: str, session: str | None) -> dict:
    return httpx.post(f"{API}/api/collab/lock", headers=h(token, graph, session),
                      json={"elementId": element_id, "session": session}, timeout=30).json()


def state_locks(token: str, graph: str, session: str | None = None) -> list[dict]:
    r = httpx.get(f"{API}/api/collab/state", headers=h(token, graph, session), timeout=30)
    return r.json().get("locks", []) if r.status_code == 200 else []


def rows_for(element_id: str) -> int:
    return int(sql(f"select count(*) from public.app_element_locks "
                   f"where element_id = '{element_id}'") or 0)


def main() -> int:
    # **앱과 같은 설정으로 붙어야 한다.** 안 그러면 `pg` 가 비밀번호 없이 붙으려
    # 다 실패하고, `sweep_absent_locks` 의 `except` 가 그걸 먹어 **0 을 돌려준다** —
    # "정리가 아무것도 안 했다"와 구별이 안 된다. 실제로 한 번 그렇게 읽었다.
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from api.features.collab import store

    print("선점 수명 — 서버 쪽 근거\n")

    print("계약")
    # 이 부등식이 깨지면 접속자 목록이 깜빡이는 순간에 잠금이 걷힌다.
    check("유예가 접속 TTL 보다 길다 (FR-002)",
          store.LOCK_ABSENT_GRACE_SECONDS > store.PRESENCE_TTL_SECONDS,
          f"grace={store.LOCK_ABSENT_GRACE_SECONDS} presence={store.PRESENCE_TTL_SECONDS}")
    check("고정 TTL 이 남아 있지 않다 (FR-001)",
          not hasattr(store, "LOCK_TTL_SECONDS"),
          "LOCK_TTL_SECONDS 가 아직 있다 — 시계로 재는 길이 남았다")

    token, uid = login("alice")
    graph = writable_graph(token)
    stamp = int(time.time())
    print(f"\n대상  uid={uid} graph={graph}")

    # ── 1. 붙어 있으면 안 만료 ────────────────────────────────────────────
    print("\n붙어 있는 동안")
    el = f"zz-lifetime-{stamp}-live"
    s1 = f"sess-{stamp}-1"
    check("잠금을 잡는다", lock(token, graph, el, s1).get("ok") is True)
    # 유예를 넘겨 기다리되, 창이 하는 것처럼 계속 알린다.
    for _ in range(4):
        time.sleep(8)
        state_locks(token, graph, s1)
    holders = [l["uid"] for l in state_locks(token, graph, s1) if l["elementId"] == el]
    check("32초가 지나도 내 것이다", holders == [uid], f"holders={holders}")
    check("행도 남아 있다", rows_for(el) == 1)

    # ── 2. 사라지면 만료되고 **행이 지워진다** ────────────────────────────
    print("\n사라진 뒤")
    el2 = f"zz-lifetime-{stamp}-gone"
    s2 = f"sess-{stamp}-2"
    check("다른 창이 잠금을 잡는다", lock(token, graph, el2, s2).get("ok") is True)
    # 이 창은 다시는 안 알린다 — 브라우저를 강제 종료한 것과 같다.
    time.sleep(store.LOCK_ABSENT_GRACE_SECONDS + 4)
    visible = [l for l in state_locks(token, graph, s1) if l["elementId"] == el2]
    check("유예가 지나면 목록에서 사라진다", visible == [], f"아직 보인다: {visible}")
    swept = store.sweep_absent_locks(graph)
    check("정리가 행을 지운다 (FR-004)", rows_for(el2) == 0, f"sweep={swept} rows={rows_for(el2)}")
    check("살아 있는 창의 잠금은 안 지운다", rows_for(el) == 1,
          "정리가 붙어 있는 사람 것까지 걷어갔다 — 전부 지우면 이 검사만 통과한다")

    # ── 3. 잠금은 **창**에 묶인다 ─────────────────────────────────────────
    print("\n창 단위")
    el3 = f"zz-lifetime-{stamp}-window"
    s3 = f"sess-{stamp}-3"
    check("세 번째 창이 잡는다", lock(token, graph, el3, s3).get("ok") is True)
    httpx.post(f"{API}/api/collab/leave", headers=h(token, graph, s1),
               json={"graph": graph, "session": s1}, timeout=30)
    check("다른 창을 닫아도 안 풀린다", rows_for(el3) == 1,
          "같은 사람의 다른 창을 닫았는데 이 창의 잠금이 사라졌다")
    httpx.post(f"{API}/api/collab/leave", headers=h(token, graph, s3),
               json={"graph": graph, "session": s3}, timeout=30)
    check("잡은 창을 닫으면 즉시 풀린다", rows_for(el3) == 0)

    # ── 4. 기동 시 정리 ───────────────────────────────────────────────────
    print("\n기동 시 정리 (백엔드 재시작)")
    el4 = f"zz-lifetime-{stamp}-restart"
    s4 = f"sess-{stamp}-4"
    check("재시작 전에 잠금이 있다", lock(token, graph, el4, s4).get("ok") is True)
    # 세션을 낡게 만든다 — 재시작 뒤 아무도 이 창을 못 살려 준다.
    sql(f"update public.app_collab_sessions set last_seen = now() - interval '10 minutes' "
        f"where session = '{s4}'")
    check("낡았지만 행은 남아 있다", rows_for(el4) == 1,
          "정리를 안 돌렸는데 행이 사라졌다 — 이 검사가 재는 것이 없어진다")

    # uvicorn --reload 가 파일 변경으로 앱을 다시 띄운다. 프로세스를 죽이지 않는다.
    (ROOT / "api" / "main.py").touch()
    ok = False
    for _ in range(40):
        time.sleep(1)
        try:
            if httpx.get(f"{API}/api/collab/state", headers=h(token, graph, s1),
                         timeout=5).status_code in (200, 400, 403):
                if rows_for(el4) == 0:
                    ok = True
                    break
        except Exception:
            continue
    check("재시작하면 유령 선점이 사라진다 (FR-004)", ok,
          f"rows={rows_for(el4)} — 붙은 창이 없으면 한 바퀴도 안 도는데 아무도 안 치웠다")

    # ── 뒷정리 ────────────────────────────────────────────────────────────
    sql(f"delete from public.app_element_locks where element_id like 'zz-lifetime-{stamp}%'")
    sql(f"delete from public.app_collab_sessions where session like 'sess-{stamp}-%'")

    print(f"\n{_n - len(_fail)}/{_n} 통과")
    for f in _fail:
        print(f"  실패: {f}")
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
