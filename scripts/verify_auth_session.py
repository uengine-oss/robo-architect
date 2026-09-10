"""세션 발급 · 개발용 로그인 · 인증 강제 검사.

토큰 함수만 부르지 않고 **실제 HTTP 로** 건다. 이 기능의 위험은 로직이 아니라
배선에 있다 — 우회로가 열린 채로 남거나, 강제 스위치가 열어 둔 경로를 잘못
잡거나, 미들웨어 등록 순서가 어긋나는 쪽이다.

앱을 이 프로세스 안에서 띄우므로 돌고 있는 백엔드를 건드리지 않고, 사용자 표에는
`ZZAUTH` 로 시작하는 행만 만들고 지운다.

    robo-architect/.venv/bin/python scripts/verify_auth_session.py
"""

from __future__ import annotations

import importlib
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

# 실행 중인 설정이 새어 들어오지 않게 먼저 비운다.
for key in ("AUTH_ENFORCE", "AUTH_DEV_LOGIN_ENABLED", "AUTH_DEV_LOGIN_ALLOW_REMOTE",
            "AUTH_DEV_LOGIN_ID", "AUTH_DEV_LOGIN_PASSWORD", "ADMIN_EMPLOYEE_NOS",
            "AUTH_APPROVAL_REQUIRED"):
    os.environ.pop(key, None)
os.environ["AUTH_JWT_SECRET"] = "verify-only-secret"
os.environ["AUTH_DEV_LOGIN_EMPNO"] = "ZZAUTH-DEV"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.platform import pg  # noqa: E402
from api.features.accounts import store as accounts  # noqa: E402
from api.features.auth import tokens  # noqa: E402
from api.features.accounts.router import router as accounts_router  # noqa: E402
from api.features.auth.router import router as auth_router  # noqa: E402
from api.platform.identity.auth_guard import AuthGuardMiddleware  # noqa: E402

PREFIX = "ZZAUTH"
failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global failed
    if cond:
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))


def cleanup() -> int:
    if not PREFIX:
        raise RuntimeError("접두사가 비어 있다 — 전수 삭제를 막는다")
    return pg.execute("DELETE FROM public.app_users WHERE uid LIKE %s", (PREFIX + "%",))


def build_app() -> FastAPI:
    """검사용 앱. 보호 대상 경로를 하나 달아 강제 동작을 확인한다."""
    app = FastAPI()
    app.add_middleware(AuthGuardMiddleware)
    app.include_router(auth_router)
    app.include_router(accounts_router)

    @app.get("/api/contexts")
    async def _protected():           # noqa: ANN202
        return {"ok": True}

    return app


def main() -> int:
    accounts.ensure_schema()
    cleanup()
    app = build_app()
    # TestClient 의 기본 클라이언트 주소는 `testclient` 라 루프백 판정에 걸린다.
    # 실제 주소를 줘서 제품의 판정 경로를 그대로 통과시킨다.
    client = TestClient(app, client=("127.0.0.1", 12345))
    remote = TestClient(app, client=("10.20.30.40", 54321))

    print("\n우회로는 기본이 꺼짐")
    check("설정이 없으면 켜지지 않는다", not importlib.import_module(
        "api.features.auth.dev_login").dev_login_enabled())
    r = client.post("/api/auth/dev-login", data={"loginId": "test", "password": "test"})
    check("꺼져 있으면 404 — 존재 자체를 알리지 않는다", r.status_code == 404, str(r.status_code))

    print("\n켜면 로그인된다")
    os.environ["AUTH_DEV_LOGIN_ENABLED"] = "true"
    r = client.post("/api/auth/dev-login", data={"loginId": "test", "password": "test"})
    check("기본 자격 test/test 로 들어간다", r.status_code == 200, r.text[:120])
    body = r.json() if r.status_code == 200 else {}
    token = body.get("accessToken")
    check("세션 토큰을 준다", bool(token))
    check("승인된 상태로 들어온다", body.get("authenticated") is True)
    check("사용자에 개발 꼬리표가 남는다", (body.get("user") or {}).get("source") == "dev")
    if token:
        claims = tokens.verify_token(token)
        check("토큰에도 꼬리표가 남는다 — 감사에서 구분된다", claims.get("src") == "dev")
        check("만료가 들어 있다", claims.get("exp", 0) > time.time())

    print("\n계정이 여럿일 때")
    # 프로젝트 격리와 공유는 사람이 둘 이상이어야 확인된다. 계정이 늘면 조용히
    # 틀리는 자리가 셋 생긴다 — 아무 계정이나 통과, 아이디와 사번이 어긋남,
    # 추가 목록이 기본 계정을 덮어씀.
    os.environ["AUTH_DEV_LOGIN_ACCOUNTS"] = (
        f"zzalice:pw-alice:{PREFIX}-ALICE:앨리스:설계1팀,"
        f"zzbob:pw-bob:{PREFIX}-BOB:밥:설계2팀,"
        # 아이디만 있고 비밀번호가 없는 반쪽 항목 — 계정이 되면 안 된다.
        "zzghost::"
        f",test:빼앗기:{PREFIX}-STEAL"      # 기본 계정 아이디를 노린 항목
    )
    r = client.post("/api/auth/dev-login", data={"loginId": "zzalice", "password": "pw-alice"})
    check("추가 계정으로 들어간다", r.status_code == 200, r.text[:120])
    who = (r.json().get("user") or {}) if r.status_code == 200 else {}
    check("그 계정의 사번이 실린다", who.get("uid") == f"{PREFIX}-ALICE", str(who.get("uid")))
    check("이름·부서가 따라온다",
          who.get("displayName") == "앨리스" and who.get("department") == "설계1팀",
          f"{who.get('displayName')}·{who.get('department')}")

    r2 = client.post("/api/auth/dev-login", data={"loginId": "zzbob", "password": "pw-bob"})
    check("두 번째 추가 계정도 들어간다", r2.status_code == 200, r2.text[:120])
    check("서로 다른 사번이다",
          ((r2.json().get("user") or {}).get("uid") if r2.status_code == 200 else None)
          == f"{PREFIX}-BOB")

    # 아이디는 맞고 비밀번호만 남의 것 — 계정끼리 섞이면 안 된다.
    check("남의 비밀번호로는 못 들어간다",
          client.post("/api/auth/dev-login",
                      data={"loginId": "zzalice", "password": "pw-bob"}).status_code == 401)
    # 반쪽 항목(`zzghost::`)이 계정이 됐는지는 **로그인으로 못 잰다** — 비밀번호가
    # 비어 있어 어차피 401 이고, 빈 문자열은 FastAPI 가 422 로 먼저 막는다. 결함을
    # 심어 보니 그 단언은 한 번도 실패하지 않았다. 아래 목록 대조가 그 일을 한다.
    # 뒤에서 덮어쓰게 두면 추가 목록의 오타 하나로 기본 계정 비밀번호가 바뀐다.
    check("추가 목록이 기본 계정을 못 덮는다",
          client.post("/api/auth/dev-login",
                      data={"loginId": "test", "password": "빼앗기"}).status_code == 401)
    check("기본 계정은 그대로 test/test",
          client.post("/api/auth/dev-login",
                      data={"loginId": "test", "password": "test"}).status_code == 200)

    # 화면이 계정을 고를 수 있으려면 목록이 나와야 한다. 비밀번호는 나오면 안 된다.
    prov = client.get("/api/auth/provider").json().get("devLogin") or {}
    listed = prov.get("accounts") or []
    # 셋이다 — `zzghost::` 는 비밀번호가 없어 계정이 아니고, `test:빼앗기:…` 는
    # 아이디가 겹쳐 안 들어간다(앞의 것이 이긴다). 이 한 줄이 둘 다 잰다.
    check("provider 가 계정 목록을 알려준다",
          [a.get("loginId") for a in listed] == ["test", "zzalice", "zzbob"],
          str([a.get("loginId") for a in listed]))
    check("비밀번호는 안 알려준다",
          all("password" not in a for a in listed))

    os.environ.pop("AUTH_DEV_LOGIN_ACCOUNTS", None)

    print("\n자격이 틀리면 막는다")
    check("비밀번호가 다르면 401",
          client.post("/api/auth/dev-login",
                      data={"loginId": "test", "password": "wrong"}).status_code == 401)
    check("아이디가 다르면 401",
          client.post("/api/auth/dev-login",
                      data={"loginId": "root", "password": "test"}).status_code == 401)
    os.environ["AUTH_DEV_LOGIN_PASSWORD"] = "another"
    check("환경변수로 바꾼 비밀번호가 적용된다",
          client.post("/api/auth/dev-login",
                      data={"loginId": "test", "password": "another"}).status_code == 200)
    os.environ.pop("AUTH_DEV_LOGIN_PASSWORD")

    print("\n같은 기계에서만")
    check("바깥에서 오면 403 — 자격이 맞아도 막는다",
          remote.post("/api/auth/dev-login",
                      data={"loginId": "test", "password": "test"}).status_code == 403)
    os.environ["AUTH_DEV_LOGIN_ALLOW_REMOTE"] = "true"
    check("명시로 열면 바깥도 된다",
          remote.post("/api/auth/dev-login",
                      data={"loginId": "test", "password": "test"}).status_code == 200)
    os.environ.pop("AUTH_DEV_LOGIN_ALLOW_REMOTE")
    check("되돌리면 다시 막힌다",
          remote.post("/api/auth/dev-login",
                      data={"loginId": "test", "password": "test"}).status_code == 403)

    print("\n인증 강제")
    check("꺼져 있으면 토큰 없이 통과한다 — 지금까지의 동작",
          client.get("/api/contexts").status_code == 200)
    os.environ["AUTH_ENFORCE"] = "true"
    check("켜면 토큰 없는 요청을 401 로 막는다",
          client.get("/api/contexts").status_code == 401)
    r = client.get("/api/contexts", headers={"Authorization": "Bearer not-a-real-token"})
    check("위조 토큰도 401", r.status_code == 401)
    r = client.get("/api/contexts", headers={"Authorization": f"Bearer {token}"})
    check("정상 토큰은 통과한다", r.status_code == 200, r.text[:120])
    check("로그인 경로는 잠기지 않는다 — 아니면 아무도 못 들어온다",
          client.get("/api/auth/provider").status_code == 200)
    check("내 상태 조회도 열려 있다", client.get("/api/auth/me").status_code == 200)

    print("\n승인 대기는 토큰을 못 받는다")
    os.environ["ADMIN_EMPLOYEE_NOS"] = PREFIX + "-ADMIN"
    os.environ["AUTH_DEV_LOGIN_EMPNO"] = PREFIX + "-PEND"
    accounts.set_status(PREFIX + "-PEND", accounts.STATUS_PENDING) or accounts.upsert_from_sso(
        {"empno": PREFIX + "-PEND", "id": PREFIX + "-PEND", "username": "p", "name": "대기"})
    accounts.set_status(PREFIX + "-PEND", accounts.STATUS_PENDING)
    r = client.post("/api/auth/dev-login", data={"loginId": "test", "password": "test"})
    b = r.json()
    check("대기 상태면 인증되지 않았다고 답한다", b.get("authenticated") is False, str(b)[:120])
    check("대기 상태면 토큰을 주지 않는다", "accessToken" not in b)
    check("상태를 알려 준다 — 화면이 안내를 띄울 수 있다", b.get("status") == "pending")

    print("\n만료된 토큰")
    os.environ["AUTH_SESSION_TTL_SECONDS"] = "1"
    accounts.set_status(PREFIX + "-PEND", accounts.STATUS_APPROVED)
    short = client.post("/api/auth/dev-login",
                        data={"loginId": "test", "password": "test"}).json().get("accessToken")
    time.sleep(1.2)
    check("만료되면 401",
          client.get("/api/contexts",
                     headers={"Authorization": f"Bearer {short}"}).status_code == 401)
    os.environ.pop("AUTH_SESSION_TTL_SECONDS")

    print("\n관리자만 사용자 관리를 할 수 있다")

    def login_as(empno: str) -> dict:
        os.environ["AUTH_DEV_LOGIN_EMPNO"] = empno
        return client.post("/api/auth/dev-login",
                           data={"loginId": "test", "password": "test"}).json()

    ah = {"Authorization": f"Bearer {login_as(PREFIX + '-ADMIN')['accessToken']}"}
    # 승인제가 켜져 있어 일반 사용자는 대기로 들어온다. 승인해야 토큰이 생기고,
    # 토큰이 있어야 "권한이 없어 막힌다"를 확인할 수 있다 — 대기 상태로 재면
    # 401(토큰 없음)이라 403(권한 없음)과 구별되지 않는다.
    login_as(PREFIX + "-MEMBER")
    client.post(f"/api/accounts/{PREFIX}-MEMBER/status", json={"status": "approved"}, headers=ah)
    mtok = login_as(PREFIX + "-MEMBER").get("accessToken")
    check("승인된 일반 사용자는 토큰을 받는다", bool(mtok))
    check("그래도 목록은 못 본다 — 401 이 아니라 403 이다",
          client.get("/api/accounts",
                     headers={"Authorization": f"Bearer {mtok}"}).status_code == 403)
    check("토큰이 없으면 401", client.get("/api/accounts").status_code == 401)
    os.environ["AUTH_DEV_LOGIN_EMPNO"] = PREFIX + "-ADMIN"
    check("관리자는 목록을 본다", client.get("/api/accounts", headers=ah).status_code == 200)
    listing = client.get("/api/accounts", headers=ah).json()
    check("대기 인원수를 함께 준다", "counts" in listing and "pending" in listing["counts"])

    r = client.post(f"/api/accounts/{PREFIX}-MEMBER/status",
                    json={"status": "rejected"}, headers=ah)
    check("관리자는 거절할 수 있다", r.status_code == 200, r.text[:100])
    os.environ["AUTH_DEV_LOGIN_EMPNO"] = PREFIX + "-MEMBER"
    after_reject = client.post("/api/auth/dev-login",
                               data={"loginId": "test", "password": "test"}).json()
    check("거절되면 다시 로그인해도 토큰이 없다", "accessToken" not in after_reject)
    check("거절 상태를 알려 준다", after_reject.get("status") == "rejected",
          str(after_reject)[:100])
    os.environ["AUTH_DEV_LOGIN_EMPNO"] = PREFIX + "-ADMIN"

    check("자기 상태는 못 바꾼다 — 마지막 관리자가 스스로를 잠글 수 있다",
          client.post(f"/api/accounts/{PREFIX}-ADMIN/status",
                      json={"status": "rejected"}, headers=ah).status_code == 403)
    check("자기 역할도 못 바꾼다 — 자기 승격과 자기 강등을 함께 막는다",
          client.post(f"/api/accounts/{PREFIX}-ADMIN/role",
                      json={"role": "member"}, headers=ah).status_code == 403)
    check("없는 사용자는 404",
          client.post(f"/api/accounts/{PREFIX}-NOPE/status",
                      json={"status": "approved"}, headers=ah).status_code == 404)
    check("알 수 없는 상태는 400",
          client.post(f"/api/accounts/{PREFIX}-MEMBER/status",
                      json={"status": "superuser"}, headers=ah).status_code == 400)
    check("관리자로 올릴 수 있다",
          client.post(f"/api/accounts/{PREFIX}-MEMBER/role",
                      json={"role": "admin"}, headers=ah).status_code == 200)

    print("\n강등되면 들고 있던 토큰이 통하지 않는다")
    # 역할은 토큰 클레임에도 실린다. 클레임만 보면 강등된 사람이 만료 전까지
    # 관리자로 남는다 — 저장된 값을 다시 읽어야 한다.
    client.post(f"/api/accounts/{PREFIX}-MEMBER/status", json={"status": "approved"}, headers=ah)
    promoted = login_as(PREFIX + "-MEMBER").get("accessToken")
    ph = {"Authorization": f"Bearer {promoted}"}
    check("올려 준 사람은 목록을 본다", client.get("/api/accounts", headers=ph).status_code == 200)
    check("그 토큰의 클레임은 admin 이다",
          tokens.verify_token(promoted).get("role") == "admin")
    client.post(f"/api/accounts/{PREFIX}-MEMBER/role", json={"role": "member"}, headers=ah)
    check("강등 뒤에는 같은 토큰으로 막힌다 — 클레임을 믿지 않는다",
          client.get("/api/accounts", headers=ph).status_code == 403)
    os.environ["AUTH_DEV_LOGIN_EMPNO"] = PREFIX + "-ADMIN"

    removed = cleanup()
    check("시험 행을 전부 지웠다",
          accounts.get_user(PREFIX + "-DEV") is None
          and accounts.get_user(PREFIX + "-PEND") is None, f"{removed}행 삭제")

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
