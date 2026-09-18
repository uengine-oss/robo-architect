"""앱이 스택을 내렸다 다시 띄웠을 때 데이터가 **내용까지** 남는가 (spec 058 T042 · US3).

## 왜 개수로 판정하지 않는가

`count(n)` 이 같다고 같은 데이터가 아니다. 이 저장소에서 개수만 보고 "보존됐다"고
읽었다가 틀린 적이 있다. 그래서 **이름 목록**으로 비교한다.

## 왜 "정말 멈췄는지" 를 먼저 보는가

멈추지 않았는데 다시 읽어서 같으면 **아무것도 증명하지 못한 것이다.** 이것이 이
검사에서 제일 쉽게 무너지는 자리다 — 실제로 `verify_graph_isolation.py` 에서 같은
구멍을 짝으로 확인했다.

## 무엇을 하지 않는가

`down` 도 `down -v` 도 부르지 않는다. `stop` 이다 — named volume 을 지우면 이 검사가
"보존 안 됨"을 정확히 보고하겠지만, **실제 데이터를 지운 뒤에 보고하는 것**이므로
그건 검사가 아니라 사고다.

## 안전

`zz_` graph 만 만들고 지운다. 컨테이너는 **라벨로 고른다** — 이름·포트로 고르면
사용자가 따로 띄운 남의 것을 내린다.

## 종료 코드

    0  내용까지 보존됐다      1  달라졌다      3  못 쟀다
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time

GRAPH = "zz_preserve"
LABEL = "org.uengine.robo.release"


class Measured(Exception):
    """쟀는데 틀렸다."""


class Unmeasured(Exception):
    """못 쟀다."""


def docker(args: list[str], timeout: int = 120) -> tuple[int, str]:
    proc = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    return proc.returncode, f"{proc.stdout}{proc.stderr}"


def psql(container: str, user: str, database: str, sql: str) -> str:
    code, out = docker(
        ["exec", "-i", container, "psql", "-U", user, "-d", database, "-v", "ON_ERROR_STOP=1",
         "-tAc", sql]
    )
    if code != 0:
        raise Unmeasured(f"psql 실패: {out.strip().splitlines()[-1][:120] if out.strip() else code}")
    return out.strip()


def names(container: str, user: str, database: str) -> list[str]:
    """**이름 목록**. 개수가 아니다."""
    out = psql(container, user, database,
               f"SELECT og_cypher('{GRAPH}', $$MATCH (n:ZzKeep) RETURN n.name AS name ORDER BY n.name$$)")
    return sorted(re.findall(r'"name": "([^"]*)"', out))


def owned_containers(project: str) -> list[str]:
    """**라벨이 아니라 프로젝트 이름으로 고르는 경우**도 받아 준다.

    설치본은 compose 라벨(`org.uengine.robo.release`)이 붙지만, 측정 스택은 그 라벨 없이
    돌 수 있다(손으로 띄운 경우). 그래서 compose 프로젝트 라벨을 쓴다 — 어느 쪽이든
    **이름 문자열 매칭은 하지 않는다.**
    """
    code, out = docker(["ps", "--all", "--filter", f"label=com.docker.compose.project={project}",
                        "--format", "{{.Names}}"])
    if code != 0:
        raise Unmeasured("컨테이너 목록을 확인하지 못했다")
    return sorted(line.strip() for line in out.strip().split("\n") if line.strip())


def running(names_: list[str]) -> list[str]:
    alive: list[str] = []
    for name in names_:
        code, out = docker(["inspect", name, "--format", "{{.State.Running}}"])
        if code == 0 and out.strip() == "true":
            alive.append(name)
    return alive


def volumes_of(project: str) -> list[str]:
    code, out = docker(["volume", "ls", "--filter", f"label=com.docker.compose.project={project}",
                        "--format", "{{.Name}}"])
    if code != 0:
        raise Unmeasured("볼륨 목록을 확인하지 못했다")
    return sorted(line.strip() for line in out.strip().split("\n") if line.strip())


def wait_for_graph(container: str, user: str, database: str, seconds: int) -> None:
    deadline = time.time() + seconds
    last = ""
    while time.time() < deadline:
        try:
            psql(container, user, database, "SELECT 1")
            return
        except Unmeasured as exc:
            last = str(exc)
            time.sleep(3)
    raise Unmeasured(f"다시 띄운 뒤 저장소가 응답하지 않는다: {last}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="robo-og-measure")
    parser.add_argument("--container", default="robo-og-measure-graph-db-1")
    parser.add_argument("--user", default="robo")
    parser.add_argument("--database", default="robo")
    parser.add_argument("--wait-seconds", type=int, default=120)
    args = parser.parse_args(argv)

    if not GRAPH.startswith("zz_"):
        print("검증 graph 이름이 zz_ 로 시작하지 않는다")
        return 3

    lines: list[str] = []
    verdict = 0
    planted = [f"keep_{i}" for i in range(5)]
    try:
        psql(args.container, args.user, args.database, f"SELECT og_create_graph('{GRAPH}')")
        for name in planted:
            psql(args.container, args.user, args.database,
                 f"SELECT og_cypher('{GRAPH}', $$CREATE (n:ZzKeep {{name:'{name}'}})$$)")
        before = names(args.container, args.user, args.database)
        if before != sorted(planted):
            raise Unmeasured(f"심은 것이 들어가지 않았다: {before}")
        lines.append(f"  ✓ 심음 — {before}")

        containers = owned_containers(args.project)
        if not containers:
            raise Unmeasured(f"'{args.project}' 소유 컨테이너를 못 찾았다")
        volumes_before = volumes_of(args.project)
        lines.append(f"  ✓ 대상 컨테이너 {len(containers)}개 · 볼륨 {len(volumes_before)}개")

        # `stop` 이다. `down` 도 `down -v` 도 아니다.
        code, out = docker(["stop", *containers], timeout=300)
        if code != 0:
            raise Unmeasured(f"멈추지 못했다: {out.strip()[:120]}")

        # **정말 멈췄는지 먼저 본다.** 안 멈췄으면 아래 비교는 아무것도 증명하지 않는다.
        still = running(containers)
        if still:
            raise Unmeasured(
                f"멈추라고 했는데 아직 돌고 있다: {still} — 이 상태로 '보존됐다'고 말하면 "
                "아무것도 증명하지 못한 것이다"
            )
        lines.append(f"  ✓ 전부 멈췄다 ({len(containers)}개)")

        # 볼륨이 살아 있어야 한다 — `stop` 의 요점이 이것이다.
        volumes_after_stop = volumes_of(args.project)
        if volumes_after_stop != volumes_before:
            raise Measured(f"볼륨이 사라졌다: {volumes_before} → {volumes_after_stop}")
        lines.append("  ✓ 볼륨이 그대로다")

        code, out = docker(["start", *containers], timeout=300)
        if code != 0:
            raise Unmeasured(f"다시 띄우지 못했다: {out.strip()[:120]}")
        wait_for_graph(args.container, args.user, args.database, args.wait_seconds)

        after = names(args.container, args.user, args.database)
        if after != before:
            raise Measured(f"내용이 달라졌다: {before} → {after}")
        lines.append(f"  ✓ 내용까지 그대로다 — {after}")
    except Measured as exc:
        lines.append(f"  ✗ {exc}")
        verdict = 1
    except Unmeasured as exc:
        lines.append(f"  ? 못 쟀다: {exc}")
        verdict = 3
    except subprocess.TimeoutExpired as exc:
        lines.append(f"  ? 못 쟀다: 시간 초과 ({exc.cmd[:2]})")
        verdict = 3

    leftovers: list[str] = []
    try:
        psql(args.container, args.user, args.database, f"SELECT og_drop_graph('{GRAPH}')")
        left = psql(args.container, args.user, args.database,
                    f"SELECT count(*) FROM og_catalog.graph WHERE name = '{GRAPH}'")
        if left != "0":
            leftovers.append(f"검증 graph 가 남았다 ({left})")
    except Unmeasured as exc:
        leftovers.append(f"치우기 실패: {exc}")

    print("\n".join(lines) or "  (아무것도 못 했다)")
    if leftovers:
        print("\n치우기 실패 — 검사 실패로 친다:")
        for problem in leftovers:
            print(f"  ✗ {problem}")
        verdict = 3 if verdict == 3 else 1

    print("=" * 60)
    print({0: "내용까지 보존됐다", 1: "실패", 3: "못 쟀다"}[verdict])
    return verdict


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
