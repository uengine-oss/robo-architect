#!/usr/bin/env python3
"""프로브 판정과 컨테이너 물리 상태가 서로 모순되지 않는가 (spec 058 T032).

## 이 스크립트가 `decideState` 를 다시 짜지 않는 이유

상태 판정 규칙은 `desktop/src/main/supervisor.ts` 에 있고 그쪽 단위 검사가 지킨다.
여기서 그 규칙을 파이썬으로 다시 쓰면 **재구현이 원본보다 옳아져서 결함을 가린다** —
이 저장소가 실제로 밟은 함정이다.

그래서 여기서는 규칙을 검사하지 않고 **서로 독립인 두 측정이 모순되는지**만 본다.

    물리   docker inspect 의 State.Running · State.Health
    기능   **앱의 프로브** (`desktop/src/main/probes/`) — `desktop/scripts/probe-runtime.mjs`
           껍데기를 통해 부른다. `scripts/probe_runtime.py` 를 쓰지 않는다: 그건 앱에
           프로브가 없던 동안의 측정 도구이고, 판정을 둘로 두면 드리프트한다

## 모순의 정의

    죽은 컨테이너인데 프로브가 pass      → 둘 중 하나가 거짓말이다. **모순**
    없는 컨테이너인데 프로브가 pass      → 같다. **모순**
    healthy 인데 우리 health 가 fail     → 모순이 아니라 **소견**. healthcheck 가
                                          "떴다"만 보기 때문이고, 그 간격이 이 스펙의
                                          이유다. 보고하되 실패로 치지 않는다
    healthy 인데 capability 가 fail      → `degraded`. **정상적인 판정**이다
    전부 error                           → 아무것도 못 쟀다. exit 3

## 비밀정보

이 스크립트는 환경 변수를 **읽지 않고 출력하지 않는다.** 프로브 상세 문자열만 그대로
옮기며, 그쪽이 비밀정보를 안 싣는 것은 프로브의 계약이다.

## 종료 코드

    0  모순 없음      1  모순 있음      3  못 쟀다
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 프로브 서비스 id → compose 서비스 이름 후보.
# **같지 않다.** 설치본의 저장소는 컨테이너가 둘(`graph-db` + `graph-bolt`)이고
# 되돌아간 Neo4j 구성에서는 `neo4j` 다. 한 이름으로 못 박으면 다른 구성에서 조용히
# "컨테이너 없음"이 되어 대조가 통째로 무의미해진다.
COMPOSE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "graph": ("graph-bolt", "neo4j"),
}

# 호스트 프로세스라 컨테이너가 없다 — 물리 대조 대상이 아니다.
HOST_PROCESS_IDS = {"architect"}


def inspect(name: str) -> dict | None:
    proc = subprocess.run(
        ["docker", "inspect", name, "--format",
         "{{.State.Running}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.State.ExitCode}}"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    running, health, exit_code = proc.stdout.strip().split("|")
    return {"running": running == "true", "health": health, "exitCode": int(exit_code)}


def physical(project: str, service_id: str) -> tuple[str, dict | None]:
    """(찾은 컨테이너 이름, 상태). 못 찾으면 (마지막 후보, None)."""
    last = ""
    for candidate in COMPOSE_CANDIDATES.get(service_id, (service_id,)):
        name = f"{project}-{candidate}-1"
        last = name
        state = inspect(name)
        if state is not None:
            return name, state
    return last, None


def run_probes(argv: list[str]) -> list[dict] | None:
    shell = HERE.parent / "desktop" / "scripts" / "probe-runtime.mjs"
    proc = subprocess.run(
        ["node", str(shell), *argv, "--json"],
        capture_output=True, text=True,
    )
    # **exit 0 만 성공으로 보지 않는다.** 프로브는 fail 이면 1, 못 쟀으면 3 을 낸다 —
    # 그 경우에도 판정 목록은 유효하다. 우리가 볼 수 없는 것은 JSON 이 안 나온 경우뿐이다.
    text = proc.stdout.strip()
    if not text:
        print(f"프로브 출력이 없다 (exit={proc.returncode})")
        if proc.stderr.strip():
            print(proc.stderr.strip().splitlines()[-1])
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"프로브 출력을 못 읽었다 (exit={proc.returncode})")
        return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="compose 프로젝트 이름")
    parser.add_argument("--probe-arg", action="append", default=[],
                        help="probe_runtime.py 에 그대로 넘길 인자 (여러 번)")
    args = parser.parse_args(argv)

    results = run_probes(args.probe_arg)
    if results is None:
        return 3

    measured = [r for r in results if r["outcome"] != "error"]
    if not measured:
        print("판정을 하나도 못 얻었다 — 전부 error 다. 환경을 먼저 확인한다.")
        return 3

    contradictions: list[str] = []
    findings: list[str] = []
    lines: list[str] = []

    for result in results:
        service_id = result["service_id"]
        if service_id in HOST_PROCESS_IDS:
            lines.append(f"  - {service_id:9} {result['kind']:11} {result['outcome']:8} (호스트 프로세스 — 물리 대조 없음)")
            continue
        name, state = physical(args.project, service_id)
        if state is None:
            where = "컨테이너 없음"
            if result["outcome"] == "pass":
                contradictions.append(
                    f"{service_id}: 컨테이너({name})가 없는데 {result['kind']} 가 pass 다"
                )
        else:
            where = f"running={state['running']} health={state['health']}"
            if not state["running"] and result["outcome"] == "pass":
                contradictions.append(
                    f"{service_id}: 컨테이너가 실행 중이 아닌데({name}, exit={state['exitCode']}) "
                    f"{result['kind']} 가 pass 다"
                )
            if (
                state["running"]
                and state["health"] == "healthy"
                and result["kind"] == "health"
                and result["outcome"] == "fail"
            ):
                findings.append(
                    f"{service_id}: compose 는 healthy 인데 우리 health 는 fail — "
                    "판정 기준이 다른 것이다(모순 아님)"
                )
            # **반대 방향도 본다.** compose 가 unhealthy 인데 우리는 pass 라면 둘 중
            # 하나의 기준이 실제 사용과 어긋나 있다. 한쪽만 보면 "healthcheck 를 믿지
            # 말라"는 이 스펙의 교훈을 반대로 적용하게 된다.
            if (
                state["running"]
                and state["health"] == "unhealthy"
                and result["outcome"] == "pass"
            ):
                findings.append(
                    f"{service_id}: compose 는 unhealthy 인데 우리 {result['kind']} 는 pass — "
                    "어느 기준이 실제 사용에 맞는지 확인해야 한다(모순 아님)"
                )
            if (
                state["running"]
                and state["health"] == "healthy"
                and result["kind"] == "capability"
                and result["outcome"] == "fail"
            ):
                findings.append(
                    f"{service_id}: healthy 인데 기능은 못 한다 → degraded. "
                    f"이 스펙이 있는 이유다 ({result['detail'][:60]})"
                )
        mark = {"pass": "✓", "fail": "✗", "error": "!", "skipped": "-"}[result["outcome"]]
        lines.append(f"  {mark} {service_id:9} {result['kind']:11} {result['outcome']:8} {where}")

    print("\n".join(lines))

    if findings:
        print("\n소견 — 실패가 아니다:")
        for finding in findings:
            print(f"  · {finding}")

    print("=" * 60)
    if contradictions:
        print("모순:")
        for contradiction in contradictions:
            print(f"  ✗ {contradiction}")
        return 1
    print(f"모순 없음 — 판정 {len(measured)}건 대조")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
