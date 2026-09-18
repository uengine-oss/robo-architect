#!/usr/bin/env python3
"""앱 소유 스택의 준비 상태를 잰다 — healthcheck 가 아니라 **기능**으로.

spec 058 T003. 계약은 `specs/058-app-owned-runtime-supervision/contracts/
service-capability-probes.md`.

## 왜 healthcheck 로는 안 되나

2026-09-17 실측. `compose up --wait` 가 8/8 healthy 를 보고한 상태에서:

    자격증명 틀림   GET /healthz 200   POST /api/consulting-bpmn 502 (401)
    자격증명 맞음   GET /healthz 200   POST /api/consulting-bpmn 200 (task 4)

healthcheck 는 **떴는지**만 본다. 이 스크립트는 **일할 수 있는지**를 따로 잰다.

## 결과가 네 값인 이유

    pass     프로브가 돌았고 조건을 맞췄다
    fail     프로브가 돌았는데 조건을 못 맞췄다
    error    **프로브 자체가 못 돌았다** (도구 없음·연결 불가 등)
    skipped  앞 단계가 안 돼서 재지 않았다

셋을 뭉쳐 `False` 로 만들면 이 프로젝트에서 제일 흔한 고장 모양이 된다 — "0건"이
데이터 없음인지 실패인지 안 갈린다. 실제로 09-17 에 프로브 안에서 `try/except` 가
import 실패를 삼켜 조용히 빈 값을 낸 사고가 있었다.

## 하지 않는 것

- **LLM 을 부르지 않는다.** 12.6초 걸리고 돈이 나간다.
- **없는 경로를 지어내지 않는다.** 09-17 에 `/robo/health` 를 만들어 불렀다가
  500 을 보고 앱 결함으로 오독했다.
- **쓰기를 하지 않는다.**

사용:
    python3 scripts/probe_runtime.py --project robo-mac-measure \
        --gateway 39000 --analyzer 35502 --pdf2bpmn 38610 --bolt 38687 \
        --graph-user robo --graph-name robo
    python3 scripts/probe_runtime.py ... --json

graph 비밀번호는 **인자로 받지 않는다** — `ps` 와 셸 기록에 남는다.
`ROBO_NEO4J_PASSWORD` 환경 변수로 준다. 상세 문자열에도 절대 안 싣는다.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable

DEFAULT_TIMEOUT_S = 3.0

PASS, FAIL, ERROR, SKIPPED = "pass", "fail", "error", "skipped"


@dataclass
class ProbeResult:
    service_id: str
    kind: str          # "health" | "capability"
    outcome: str       # pass | fail | error | skipped
    detail: str        # **비밀정보 금지**
    duration_ms: int


# ---------------------------------------------------------------------------
# 낮은 수준 도구 — 전부 예외를 삼키지 않고 갈라서 돌려준다
# ---------------------------------------------------------------------------

def http_code(url: str, timeout: float = DEFAULT_TIMEOUT_S) -> tuple[str, str]:
    """(결과, 상세). 연결 자체가 안 되면 ERROR, 응답이 오면 PASS + 코드."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return PASS, str(response.status)
    except urllib.error.HTTPError as exc:
        # HTTP 응답이 왔다 — 서비스는 답한 것이다. 코드 판정은 호출자 몫.
        return PASS, str(exc.code)
    except Exception as exc:                      # 연결 실패·타임아웃 등
        return ERROR, type(exc).__name__


def port_open(host: str, port: int, timeout: float = DEFAULT_TIMEOUT_S) -> bool:
    """포트 응답으로 잰다. `nc -z` 와 `/dev/tcp` 는 IPv6 바인딩에서 거짓 음성을 낸다."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# 프로브의 서비스 id 와 compose 서비스 이름은 **같지 않다.** 설치본의 저장소는 컨테이너가
# 둘(`graph-db` + `graph-bolt`)인데 앱이 보는 것은 Bolt 하나다. 그리고 되돌아간 Neo4j
# 구성에서는 그냥 `neo4j` 다. 그래서 **후보를 순서대로 본다** — 한 이름으로 못 박으면
# 다른 구성에서 조용히 "컨테이너 없음"이 되고, 그게 대조군을 통째로 무의미하게 만든다.
COMPOSE_SERVICE: dict[str, tuple[str, ...]] = {"graph": ("graph-bolt", "neo4j")}


def inspect_health(name: str) -> tuple[str, str] | None:
    """없는 컨테이너면 None. 있으면 (결과, 상태)."""
    try:
        out = subprocess.run(
            ["docker", "inspect", "--format",
             "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", name],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as exc:
        return ERROR, f"docker inspect 실패: {type(exc).__name__}"
    if out.returncode != 0:
        return None
    status = out.stdout.strip()
    return (PASS, status) if status in ("healthy", "none") else (FAIL, status)


def docker_health(project: str, service_id: str) -> tuple[str, str]:
    """compose healthcheck 가 뭐라 하는지. 우리 판정이 아니라 **대조군**이다."""
    for candidate in COMPOSE_SERVICE.get(service_id, (service_id,)):
        found = inspect_health(f"{project}-{candidate}-1")
        if found is not None:
            return found
    return ERROR, "컨테이너 없음"


def docker_exec_code(project: str, service: str, url: str) -> tuple[str, str]:
    """컨테이너 **안에서** 부른다 — 호스트에 포트를 안 연 서비스를 재려고.

    이미지마다 든 도구가 다르다. parser·gateway 는 Java 이미지라 `python` 이 없고
    `curl` 이 있다(compose healthcheck 도 그쪽만 curl 을 쓴다). 둘 다 없으면
    **fail 이 아니라 error** 다 — 서비스가 안 되는 게 아니라 우리가 못 잰 것이다.
    """
    name = f"{project}-{service}-1"
    script = (
        "import urllib.request,urllib.error,sys\n"
        f"try: print(urllib.request.urlopen('{url}',timeout=3).status)\n"
        "except urllib.error.HTTPError as e: print(e.code)\n"
        "except Exception as e: print('ERR:'+type(e).__name__); sys.exit(3)\n"
    )
    attempts = (
        ["docker", "exec", name, "curl", "-s", "-o", "/dev/null",
         "-w", "%{http_code}", "--max-time", "3", url],
        ["docker", "exec", name, "python", "-c", script],
    )
    missing_tool = []
    for cmd in attempts:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        except Exception as exc:
            return ERROR, f"docker exec 실패: {type(exc).__name__}"
        combined = (out.stdout + out.stderr)
        if "executable file not found" in combined:
            missing_tool.append(cmd[3])
            continue
        text = out.stdout.strip()
        if out.returncode != 0 or text.startswith("ERR:") or not text:
            return ERROR, text or f"exit={out.returncode}"
        return PASS, text
    return ERROR, f"컨테이너에 잴 도구가 없다: {', '.join(missing_tool)}"


# ---------------------------------------------------------------------------
# 서비스별 프로브
# ---------------------------------------------------------------------------

class Probes:
    def __init__(self, args: argparse.Namespace) -> None:
        self.p = args

    # -- graph (저장소) ----------------------------------------------------
    #
    # 서비스 id 를 `neo4j` 라고 부르지 않는다. **엔진 이름이 아니라 역할 이름이다** —
    # 설치본의 저장소는 Ontological 이고, 앱이 보는 것은 Neo4j **프로토콜**을 말하는
    # Bolt 게이트웨이다. id 를 엔진에 묶어 두면 엔진을 바꿀 때마다 계약이 깨진다.

    def graph_health(self) -> tuple[str, str]:
        return (PASS, "bolt open") if port_open("127.0.0.1", self.p.bolt) else (FAIL, "bolt closed")

    def graph_capability(self) -> tuple[str, str]:
        """**포트 열림으로 판정하면 안 된다** (T022).

        bolt 핸드셰이크는 성공하는데 그 graph 가 없으면 **조회에서야** 터진다
        (`DatabaseNotFound`). 실제로 그렇게 새서 로그를 뒤져 찾아낸 적이 있다.
        그래서 여기서는 **설정된 graph 에 질의를 한 번 던진다.**

        건수는 판정에 안 쓴다 — 갓 만든 graph 는 0 건이 정상이다. 질의가 **돌았는지**가
        판정이다. 0 건을 실패로 보면 정상 부재를 고장으로 읽는다.
        """
        if not port_open("127.0.0.1", self.p.bolt):
            return SKIPPED, "bolt 가 안 열려 있어 재지 않음"
        if not (self.p.graph_user and self.p.graph_name):
            return ERROR, "graph 자격증명이 없어 재지 못함 (--graph-user/--graph-name)"
        password = os.environ.get("ROBO_NEO4J_PASSWORD") or os.environ.get("OG_PASSWORD")
        if not password:
            return ERROR, "ROBO_NEO4J_PASSWORD 가 없어 재지 못함"
        try:
            from neo4j import GraphDatabase
        except ImportError:
            # **fail 이 아니라 error 다.** 저장소가 안 되는 게 아니라 우리가 못 잰 것이다.
            return ERROR, "neo4j 드라이버 없음 — 재지 못함"
        uri = f"bolt://127.0.0.1:{self.p.bolt}"
        try:
            driver = GraphDatabase.driver(uri, auth=(self.p.graph_user, password))
        except Exception as exc:
            return ERROR, f"드라이버 생성 실패: {type(exc).__name__}"
        try:
            with driver.session(database=self.p.graph_name) as session:
                count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            return PASS, f"graph '{self.p.graph_name}' 조회됨 (노드 {count})"
        except Exception as exc:
            # 상세에 **비밀정보를 싣지 않는다.** 드라이버 예외 문구에 URI 는 들어가도
            # 자격증명은 안 들어가지만, 그래도 첫 줄만 자른다.
            return FAIL, f"graph '{self.p.graph_name}' 질의 실패: {str(exc).splitlines()[0][:90]}"
        finally:
            driver.close()

    # -- gateway -----------------------------------------------------------
    def gateway_health(self) -> tuple[str, str]:
        outcome, detail = http_code(f"http://127.0.0.1:{self.p.gateway}/actuator/health")
        if outcome is ERROR:
            return ERROR, detail
        return (PASS, detail) if detail == "200" else (FAIL, f"actuator={detail}")

    def gateway_capability(self) -> tuple[str, str]:
        """**판정은 "직접 호출과 같은 코드인가"다.** 절대 코드로 보지 않는다.
        `/api/gateway/antlr/` 는 500 이 정상일 수 있다 — parser 직접도 500 이므로."""
        via, via_detail = http_code(f"http://127.0.0.1:{self.p.gateway}/api/gateway/antlr/")
        if via is ERROR:
            return ERROR, f"게이트웨이 도달 불가: {via_detail}"
        direct, direct_detail = docker_exec_code(self.p.project, "parser", "http://127.0.0.1:8081/antlr/")
        if direct is ERROR:
            return ERROR, f"parser 직접 호출 불가: {direct_detail}"
        if via_detail == direct_detail:
            return PASS, f"게이트웨이 {via_detail} == 직접 {direct_detail}"
        return FAIL, f"게이트웨이 {via_detail} != 직접 {direct_detail}"

    # -- analyzer ----------------------------------------------------------
    def analyzer_health(self) -> tuple[str, str]:
        outcome, detail = http_code(f"http://127.0.0.1:{self.p.analyzer}/")
        return (outcome, detail) if outcome is ERROR else (PASS, detail)

    def analyzer_capability(self) -> tuple[str, str]:
        return ERROR, "LLM 자격증명 확인 미구현 — T021 에서 넣는다"

    # -- catalog / fabric --------------------------------------------------
    def catalog_health(self) -> tuple[str, str]:
        return docker_exec_code(self.p.project, "catalog", "http://127.0.0.1:5503/robo/check-data/")

    def fabric_health(self) -> tuple[str, str]:
        return docker_exec_code(self.p.project, "fabric", "http://127.0.0.1:8404/health")

    # -- parser ------------------------------------------------------------
    def parser_health(self) -> tuple[str, str]:
        return docker_exec_code(self.p.project, "parser", "http://127.0.0.1:8081/")

    # -- pdf2bpmn ----------------------------------------------------------
    def pdf2bpmn_health(self) -> tuple[str, str]:
        outcome, detail = http_code(f"http://127.0.0.1:{self.p.pdf2bpmn}/healthz")
        if outcome is ERROR:
            return ERROR, detail
        return (PASS, detail) if detail == "200" else (FAIL, f"healthz={detail}")

    def pdf2bpmn_capability(self) -> tuple[str, str]:
        """**이 스펙 전체의 근거 실험 자리.** healthz 200 이면서 502 인 상태를 잡아야 한다.
        실제 BPMN 생성을 쓰지 않는다 — 12.6초·비용."""
        return ERROR, "자격증명 유효성 확인 미구현 — T024 에서 넣는다"


PROBE_TABLE: dict[str, dict[str, str]] = {
    "graph":    {"health": "graph_health",    "capability": "graph_capability"},
    "gateway":  {"health": "gateway_health",  "capability": "gateway_capability"},
    "analyzer": {"health": "analyzer_health", "capability": "analyzer_capability"},
    "catalog":  {"health": "catalog_health"},
    "fabric":   {"health": "fabric_health"},
    "parser":   {"health": "parser_health"},
    "pdf2bpmn": {"health": "pdf2bpmn_health", "capability": "pdf2bpmn_capability"},
}


def run(args: argparse.Namespace) -> list[ProbeResult]:
    import time

    probes = Probes(args)
    results: list[ProbeResult] = []
    for service_id, kinds in PROBE_TABLE.items():
        for kind, method_name in kinds.items():
            method: Callable[[], tuple[str, str]] = getattr(probes, method_name)
            started = time.monotonic()
            try:
                outcome, detail = method()
            except Exception as exc:
                # 프로브가 터진 것은 **fail 이 아니라 error 다.**
                outcome, detail = ERROR, f"프로브 예외: {type(exc).__name__}"
            results.append(ProbeResult(
                service_id, kind, outcome, detail,
                int((time.monotonic() - started) * 1000),
            ))
    return results


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="robo-mac-measure", help="compose 프로젝트 이름")
    parser.add_argument("--gateway", type=int, required=True)
    parser.add_argument("--analyzer", type=int, required=True)
    parser.add_argument("--pdf2bpmn", type=int, required=True)
    # `--neo4j` 는 옛 이름이다. 같은 자리로 받아 두되 새 이름을 쓴다 — 조용히
    # 안 먹는 인자가 되면 포트가 0 이 되어 "bolt closed" 로 잘못 보인다.
    parser.add_argument("--bolt", "--neo4j", type=int, required=True, dest="bolt",
                        help="Bolt 게이트웨이의 호스트 포트")
    parser.add_argument("--graph-user", default=os.environ.get("ROBO_NEO4J_USER"),
                        help="Bolt 로그인 사용자 (= Postgres role)")
    parser.add_argument("--graph-name", default=os.environ.get("ROBO_NEO4J_DATABASE"),
                        help="존재를 확인할 graph 이름")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--compare-health", action="store_true",
        help="compose healthcheck 와 나란히 찍는다 — 둘이 갈리는 자리를 보려고",
    )
    args = parser.parse_args(argv)

    results = run(args)

    if args.json:
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
    else:
        mark = {PASS: "✓", FAIL: "✗", ERROR: "!", SKIPPED: "-"}
        for r in results:
            line = f"  {mark[r.outcome]} {r.service_id:9} {r.kind:11} {r.outcome:8} {r.detail}"
            if args.compare_health and r.kind == "capability":
                ho, hd = docker_health(args.project, r.service_id)
                line += f"   [compose: {hd}]"
            print(line)

    counts = {k: sum(1 for r in results if r.outcome == k) for k in (PASS, FAIL, ERROR, SKIPPED)}
    summary = f"pass {counts[PASS]} · fail {counts[FAIL]} · error {counts[ERROR]} · skipped {counts[SKIPPED]}"
    # **`--json` 은 기계가 읽는 출력이다.** 사람용 요약을 같은 스트림에 섞으면
    # 받는 쪽의 `json.loads` 가 깨진다 — 실제로 깨졌고, 증상은 "프로브를 못 읽었다"로
    # 보여서 원인이 프로브 실패처럼 읽혔다.
    print(f"\n{summary}", file=sys.stderr if args.json else sys.stdout)

    # **error 는 fail 과 다르게 센다.** 뭉치면 "재지 못한 것"이 "안 되는 것"이 된다.
    if counts[FAIL]:
        return 1
    if counts[ERROR]:
        return 3          # 재지 못했다 — "안 된다"가 아니라 "모른다"
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
