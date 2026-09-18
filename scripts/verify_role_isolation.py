"""권한 격리를 **설치본 구성에서** 데이터로 판정한다 (spec 058 T046~T048).

## 여기 있는 이유

원래 `Desktop/robo/og-verify/authz/installer_isolation.py` 에 있었다. 그 폴더는 **어느
저장소에도 안 들어 있다** — 이 장비에만 있었다. Windows 설치 검증 가이드를 쓰다가
"clone 한 장비에서는 이 파일을 받을 수 없다" 는 것을 알았다. 저장소로 옮겼다.

## 왜 따로 있나

`probe_authz.py` 는 개발 환경(`ontological-dev` · 포트 28687 · role `proj_*`)에 붙어
있고, 결과를 **사람이 표로 읽는다**. 이 스크립트는 그 판정을 설치본 구성에 대고
자동으로 내린다 — 개발 환경 통과를 설치본 통과로 치지 않는다(SC-011).

## 무엇으로 판정하나 — 빈 graph 로는 아무것도 증명 못 한다

권한이 없어도 `MATCH (n)` 은 **0 건**을 낸다. 그래서 여기서는

    1. 양쪽 graph 에 **서로 다른 개수**를 심고
    2. 심은 것이 실제로 들어갔는지 먼저 되읽고 (안 들어갔으면 ERROR — 못 쟀다)
    3. 자기 graph 에서는 **심은 수만큼** 나오는지
    4. 남의 graph 에서는 **거부되는지** (0 건이 아니라 거부여야 한다)

를 본다. 라벨 없는 스캔을 반드시 포함한다 — 상류 결함 5 가 새던 자리가 거기다.

## 안전

`zz_` 로 시작하는 graph·role 만 만들고 지운다. 다른 이름이 들어오면 시작도 안 한다.
치우기에 실패하면 **검사 실패**로 친다 — 남겨 두면 다음 회차가 오염된 환경을 만난다.

## 종료 코드

    0  통과      1  실패(격리가 안 선다 / 치우기 실패)      3  못 쟀다
"""

from __future__ import annotations

import os
import subprocess
import sys

from neo4j import GraphDatabase

BOLT_URI = os.environ.get("OG_BOLT_URI", "bolt://127.0.0.1:38687")
PSQL_CONTAINER = os.environ.get("OG_PSQL_CONTAINER", "robo-og-measure-graph-db-1")
PSQL_USER = os.environ.get("OG_PSQL_USER", "robo")
PSQL_DB = os.environ.get("OG_PSQL_DB", "robo")

PREFIX = "zz_"
GRAPH_A, GRAPH_B = "zz_isolation_a", "zz_isolation_b"
ROLE_A, ROLE_B = "zz_iso_a", "zz_iso_b"
PW_A, PW_B = "zz_iso_pw_a", "zz_iso_pw_b"
# 개수를 다르게 둔다. 같으면 한쪽을 다른 쪽으로 착각해도 안 드러난다.
COUNT_A, COUNT_B, COUNT_GAMMA = 3, 5, 2


class Measured(Exception):
    """쟀는데 틀렸다 — 실패."""


class Unmeasured(Exception):
    """못 쟀다 — 실패와 구분한다."""


def psql(sql: str) -> str:
    proc = subprocess.run(
        ["docker", "exec", "-i", PSQL_CONTAINER,
         "psql", "-U", PSQL_USER, "-d", PSQL_DB, "-v", "ON_ERROR_STOP=1", "-tAc", sql],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise Unmeasured(f"psql 실패: {proc.stderr.strip().splitlines()[-1:] or proc.stderr!r}")
    return proc.stdout.strip()


def cypher_as_owner(graph: str, query: str) -> str:
    return psql(f"SELECT og_cypher('{graph}', $${query}$$)")


def guard_names() -> None:
    for name in (GRAPH_A, GRAPH_B, ROLE_A, ROLE_B):
        if not name.startswith(PREFIX):
            raise Unmeasured(f"'{PREFIX}' 로 시작하지 않는 이름: {name}")


# ---------------------------------------------------------------------------

def setup() -> None:
    for g in (GRAPH_A, GRAPH_B):
        psql(f"SELECT og_create_graph('{g}')")
    for role, pw in ((ROLE_A, PW_A), (ROLE_B, PW_B)):
        psql(f"DROP ROLE IF EXISTS {role}")
        psql(f"CREATE ROLE {role} LOGIN PASSWORD '{pw}'")


def plant() -> None:
    # **빈 graph 로는 아무것도 증명 못 한다.** 권한이 없어도 `MATCH (n)` 은 0 건이다.
    # 여기서 안 막으면, 심는 쪽이 망가졌을 때 증상이 "격리가 샌다" 로 잘못 보인다
    # (실제로 그렇게 보였다 — 2026-09-17).
    if COUNT_A < 1 or COUNT_B < 1 or COUNT_GAMMA < 1:
        raise Unmeasured(
            f"양쪽에 데이터를 심어야 잰다 (A={COUNT_A} · B={COUNT_B} · Gamma={COUNT_GAMMA})"
        )
    for i in range(COUNT_A):
        cypher_as_owner(GRAPH_A, f"CREATE (n:ZzAlpha {{name:'a{i}'}})")
    for i in range(COUNT_B):
        cypher_as_owner(GRAPH_B, f"CREATE (n:ZzBeta {{name:'b{i}'}})")
    # **심은 것이 들어갔는지 먼저 확인한다.** 안 들어갔으면 아래 판정은 전부 무의미하다.
    for graph, expected in ((GRAPH_A, COUNT_A), (GRAPH_B, COUNT_B)):
        got = cypher_as_owner(graph, "MATCH (n) RETURN count(n)")
        if f'"count(n)": {expected}' not in got:
            raise Unmeasured(f"{graph} 에 {expected} 건을 못 심었다: {got}")


def grant() -> None:
    psql(f"SELECT og_grant('{ROLE_A}','write','{GRAPH_A}')")
    psql(f"SELECT og_grant('{ROLE_B}','write','{GRAPH_B}')")


def ask(role: str, pw: str, graph: str, query: str):
    """(건수, None) 또는 (None, 거부 사유). 예외를 삼키지 않는다."""
    try:
        driver = GraphDatabase.driver(BOLT_URI, auth=(role, pw))
    except Exception as exc:  # 접속 자체가 안 되면 못 잰 것이다
        raise Unmeasured(f"{role} Bolt 접속 실패: {exc}") from exc
    try:
        with driver.session(database=graph) as session:
            return session.run(query).single()["c"], None
    except Exception as exc:
        return None, str(exc).split("\n")[0][:90]
    finally:
        driver.close()


LABELLESS = "MATCH (n) RETURN count(n) AS c"


def check(results: list[str]) -> None:
    def ok(msg): results.append(f"  ✓ {msg}")

    for role, pw, own, expected, own_label, own_label_count in (
        (ROLE_A, PW_A, GRAPH_A, COUNT_A, "ZzAlpha", COUNT_A),
        (ROLE_B, PW_B, GRAPH_B, COUNT_B, "ZzBeta", COUNT_B),
    ):
        other = GRAPH_B if own == GRAPH_A else GRAPH_A

        # 자기 graph — **심은 수만큼** 나와야 한다. 0 이면 격리가 아니라 고장이다.
        count, denied = ask(role, pw, own, LABELLESS)
        if denied is not None:
            raise Measured(f"{role} 이 자기 graph {own} 에서 거부됐다: {denied}")
        if count != expected:
            raise Measured(f"{role} 이 자기 graph 에서 {expected} 가 아니라 {count} 를 봤다")
        ok(f"{role} → {own}(자기) 라벨 없는 스캔 = {count}")

        count, denied = ask(role, pw, own, f"MATCH (n:{own_label}) RETURN count(n) AS c")
        if denied is not None or count != own_label_count:
            raise Measured(f"{role} 이 자기 라벨 {own_label} 을 못 읽는다: {denied or count}")
        ok(f"{role} → {own}(자기) :{own_label} = {count}")

        # 남의 graph — **거기 실제로 있는 것을 물으면 거부**여야 한다.
        # 0 건은 통과가 아니다. 다만 거기 **없는 라벨**을 물어 나온 0 은 다른 이야기다
        # (아래 `absent_label` 참고) — 셋을 가른다: 정상 부재 / 거부 / 샘.
        other_label = "ZzBeta" if other == GRAPH_B else "ZzAlpha"
        for query, what in (
            (LABELLESS, "라벨 없는 스캔"),
            (f"MATCH (n:{other_label}) RETURN count(n) AS c", f":{other_label}"),
        ):
            count, denied = ask(role, pw, other, query)
            if denied is None:
                raise Measured(
                    f"{role} 이 남의 graph {other} 에서 {what} 를 실행했다 (결과 {count}). "
                    "0 건이어도 격리가 아니다 — 거부되어야 한다"
                )
            ok(f"{role} → {other}(남의) {what} 거부됨")

        # **정상 부재를 거부로 착각하지 않는다.** 남의 graph 에 아예 없는 라벨은
        # 저장 테이블이 없어 권한 검사에 닿지도 않고 0 건이 나온다. 그건 샌 것이
        # 아니다 — 다만 "정말 없는지" 를 주인 자격으로 되읽어 확인한다. 안 그러면
        # 조회 실패를 부재로 읽는다.
        absent_label = "ZzAlpha" if other == GRAPH_B else "ZzBeta"
        count, denied = ask(role, pw, other, f"MATCH (n:{absent_label}) RETURN count(n) AS c")
        owner_view = cypher_as_owner(other, f"MATCH (n:{absent_label}) RETURN count(n)")
        if '"count(n)": 0' not in owner_view:
            raise Measured(f"{other} 에 :{absent_label} 이 실제로 있다: {owner_view}")
        if denied is None and count == 0:
            ok(f"{role} → {other}(남의) :{absent_label} = 0 (정상 부재 — 주인도 0)")
        elif denied is not None:
            ok(f"{role} → {other}(남의) :{absent_label} 거부됨")
        else:
            raise Measured(f"{role} 이 남의 graph 에서 :{absent_label} {count} 건을 봤다")


def check_new_label(results: list[str]) -> None:
    """graph 가 생긴 **뒤에** 새 라벨이 나타나도 격리가 유지되는가.

    상류를 그대로 쓰면 여기서 무너졌다(AUTHZ.md 결함 15). 새 저장 테이블이
    기본 권한으로 생겨 남이 읽게 된다.
    """
    for i in range(COUNT_GAMMA):
        cypher_as_owner(GRAPH_B, f"CREATE (n:ZzGamma {{name:'g{i}'}})")

    count, denied = ask(ROLE_B, PW_B, GRAPH_B, "MATCH (n:ZzGamma) RETURN count(n) AS c")
    if denied is not None or count != COUNT_GAMMA:
        raise Measured(f"주인이 새 라벨을 못 읽는다: {denied or count}")
    results.append(f"  ✓ {ROLE_B} 가 나중에 생긴 :ZzGamma {count} 건을 읽는다")

    count, denied = ask(ROLE_A, PW_A, GRAPH_B, "MATCH (n:ZzGamma) RETURN count(n) AS c")
    if denied is None:
        raise Measured(f"나중에 생긴 라벨이 남에게 샌다: {ROLE_A} 가 {count} 건을 봤다")
    results.append(f"  ✓ {ROLE_A} 는 나중에 생긴 :ZzGamma 도 거부됨")


def teardown() -> list[str]:
    """실패해도 예외를 던지지 않고 남은 것을 돌려준다. 남으면 검사 실패다."""
    problems = []
    # **자기 graph 만 되뺏으면 안 된다.** `DROP ROLE` 은 `og_catalog.grantee` 행을
    # 지우지 않는다(2026-09-17 실측). 같은 이름의 role 이 나중에 다시 생기면 그 행이
    # 살아나 예전 권한을 물려받는다. 그래서 **그 role 의 모든 행**을 되뺀다.
    try:
        rows = psql(
            "SELECT role || '|' || graph FROM og_catalog.grantee "
            f"WHERE role IN ('{ROLE_A}','{ROLE_B}')"
        )
        for line in filter(None, rows.splitlines()):
            role, graph = line.split("|", 1)
            try:
                psql(f"SELECT og_revoke('{role}','{graph}')")
            except Unmeasured as exc:
                problems.append(f"og_revoke({role},{graph}): {exc}")
    except Unmeasured as exc:
        problems.append(f"grantee 조회 실패: {exc}")
    for graph in (GRAPH_A, GRAPH_B):
        try:
            psql(f"SELECT og_drop_graph('{graph}')")
        except Unmeasured as exc:
            problems.append(f"og_drop_graph({graph}): {exc}")
    for role in (ROLE_A, ROLE_B):
        try:
            psql(f"DROP OWNED BY {role}")
            psql(f"DROP ROLE {role}")
        except Unmeasured as exc:
            problems.append(f"DROP ROLE {role}: {exc}")
    # **믿지 않고 되읽는다.**
    try:
        left = psql(
            "SELECT count(*) FROM og_catalog.graph WHERE name IN "
            f"('{GRAPH_A}','{GRAPH_B}')"
        )
        if left != "0":
            problems.append(f"graph 가 {left} 개 남았다")
        left = psql(f"SELECT count(*) FROM pg_roles WHERE rolname IN ('{ROLE_A}','{ROLE_B}')")
        if left != "0":
            problems.append(f"role 이 {left} 개 남았다")
        left = psql(
            "SELECT count(*) FROM og_catalog.grantee WHERE role IN "
            f"('{ROLE_A}','{ROLE_B}')"
        )
        if left != "0":
            problems.append(f"og_catalog.grantee 에 {left} 행 남았다 — 같은 이름 role 이 물려받는다")
    except Unmeasured as exc:
        problems.append(f"치운 뒤 확인 실패: {exc}")
    return problems


def main() -> int:
    print(f"대상 Bolt   {BOLT_URI}")
    print(f"대상 psql   docker exec {PSQL_CONTAINER} psql -U {PSQL_USER} -d {PSQL_DB}")
    results: list[str] = []
    verdict = 0
    try:
        guard_names()
        setup()
        plant()
        grant()
        check(results)
        check_new_label(results)
    except Measured as exc:
        results.append(f"  ✗ {exc}")
        verdict = 1
    except Unmeasured as exc:
        results.append(f"  ? 못 쟀다: {exc}")
        verdict = 3
    finally:
        leftovers = teardown()

    print("\n".join(results) or "  (아무것도 못 했다)")
    if leftovers:
        print("\n치우기 실패 — 검사 실패로 친다:")
        for problem in leftovers:
            print(f"  ✗ {problem}")
        verdict = max(verdict, 1) if verdict != 3 else 3

    print("=" * 60)
    print({0: "통과", 1: "실패", 3: "못 쟀다"}[verdict])
    return verdict


if __name__ == "__main__":
    sys.exit(main())
