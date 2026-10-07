#!/usr/bin/env python3
"""서비스를 **하나씩 죽여** 모든 경우에 이름과 이유가 나오는가 (spec 058 T031).

## 왜 이 스크립트가 저장소에 있나

2026-10-07 에 이 쓸기를 **손으로 한 번** 돌려 여덟 서비스가 8/8 이름과 이유를 대고
8/8 돌아오는 것을 쟀다(`enterprise-done7` §148). 그런데 그때 쓴 것은 스크래치패드의
일회용 스크립트였다 — **다음 사람이 다시 돌릴 수 없는 측정은 측정이 아니다.**
그래서 들여왔다.

## 재는 것은 둘이다

```
① 죽이면 **이름을 대고 상태가 바뀌는가** — 몇 초 만에, 무슨 이유로
② 되살리면 **ready 로 돌아오는가** — 몇 초 만에
```

판정을 여기서 다시 하지 않는다. 앱이 로그에 적은 `runtime.service.state` 를 읽을
뿐이다 — 규칙은 `desktop/src/main/supervisor.ts` 에 있고, 그것을 파이썬으로 다시
쓰면 **재구현이 원본보다 옳아져서 결함을 가린다**(`verify_runtime_supervision.py`
머리의 같은 이야기).

## 빠지는 둘 — 성격이 다르다

```
architect  호스트 프로세스다. 죽이면 이 측정 자체가 끊긴다.
           크래시 되살리기(T051·T052)가 따로 덮는 자리다
graph      중앙 DB 다. 이 PC 가 띄운 것이 아니고, 내리면 **다른 프로젝트까지** 멎는다.
           따로, 사람이 보는 앞에서 잰다
```

둘을 `--services` 로 억지로 넣을 수는 있지만 **기본값에는 두지 않는다.**

## 쓰는 법

```
python scripts/verify_runtime_service_sweep.py              # 여덟을 차례로
python scripts/verify_runtime_service_sweep.py -s parser    # 하나만
```

앱이 **떠 있어야** 한다(감독 루프가 돌아야 로그가 나온다). 끝나면 전부 되살려
두지만, 중간에 끊으면 마지막 하나가 내려간 채 남는다 — 그때는 앱의 "다시 시도" 를
누르거나 `docker start <프로젝트>-<서비스>-1` 로 올린다.

종료 코드: 0 전부 봤다 · 1 놓친 것이 있다 · 2 아무것도 못 쟀다(로그·도커).
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import time

# 콘솔이 cp949 면 한국어 설명의 `—` 하나로 **측정 전에** 죽는다. 한 번 밟았다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # 파이프로 받는 쪽이면 그대로 둔다
        pass

DEFAULT_PROJECT = "robo-architect-desktop"
# `architect`(호스트 프로세스)·`graph`(중앙 DB)는 위 머리말의 이유로 뺀다.
DEFAULT_SERVICES = [
    "analyzer",
    "catalog",
    "fabric",
    "gateway",
    "mindsdb",
    "parser",
    "pdf2bpmn",
    "wireframe",
]
DOWN_BUDGET_S = 60
UP_BUDGET_S = 150
POLL_S = 2


def log_path() -> str:
    """가장 **최근** 로그를 쓴다 — 자정을 넘기면 날짜별 파일이 바뀐다."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SystemExit("** APPDATA 가 없다 — Windows 에서 돌린다 **")
    folder = os.path.join(appdata, "robo-architect-desktop", "logs")
    try:
        names = [n for n in os.listdir(folder) if n.startswith("desktop-") and n.endswith(".log")]
    except OSError:
        raise SystemExit("** 로그 폴더가 없다: %s — 앱을 한 번 띄운다 **" % folder)
    if not names:
        raise SystemExit("** 로그가 없다: %s **" % folder)
    return os.path.join(folder, max(names))


def rows(service: str) -> list[str]:
    """그 서비스의 상태 전이 줄만. 파일을 매번 다시 고른다(로그가 넘어갈 수 있다)."""
    text = io.open(log_path(), encoding="utf-8", errors="replace").read()
    pattern = r'"event":"runtime\.service\.state","data":\{([^}]*"service":"%s"[^}]*)\}' % re.escape(
        service
    )
    return re.findall(pattern, text)


def wait_for(service: str, want: str, budget_s: int, baseline: int) -> tuple[float | None, str]:
    """`want` 상태가 **새로** 적히기를 기다린다. 못 보면 `(None, 마지막 줄)`."""
    started = time.time()
    while time.time() - started < budget_s:
        current = rows(service)
        if len(current) > baseline:
            for row in current[baseline:]:
                if '"state":"%s"' % want in row:
                    return time.time() - started, row
            baseline = len(current)
        time.sleep(POLL_S)
    return None, (rows(service) or ["(없음)"])[-1]


def docker(action: str, container: str) -> None:
    subprocess.run(["docker", action, container], capture_output=True, timeout=120)


def reason_of(row: str) -> str:
    found = re.search(r'"reason":("[^"]*"|null)', row or "")
    return found.group(1) if found else "?"


def main() -> int:
    parser = argparse.ArgumentParser(description="서비스를 하나씩 내렸다 올린다 (058 T031)")
    parser.add_argument("-p", "--project", default=os.environ.get("ROBO_COMPOSE_PROJECT", DEFAULT_PROJECT))
    parser.add_argument("-s", "--services", nargs="+", default=DEFAULT_SERVICES)
    args = parser.parse_args()

    if subprocess.run(["docker", "version"], capture_output=True).returncode != 0:
        print("** 도커가 응답하지 않는다 **")
        return 2

    print("서비스 %d개를 하나씩 내렸다 올린다 — 로그: %s\n" % (len(args.services), log_path()), flush=True)
    results = []
    for service in args.services:
        container = "%s-%s-1" % (args.project, service)
        base = len(rows(service))
        docker("stop", container)
        down_s, down_row = wait_for(service, "failed", DOWN_BUDGET_S, base)
        base = len(rows(service))
        docker("start", container)
        up_s, up_row = wait_for(service, "ready", UP_BUDGET_S, base)
        reason = reason_of(down_row)
        results.append((service, down_s, up_s, reason))
        print(
            "  %-10s 내림 %s · 올림 %s · 이유 %s"
            % (
                service,
                ("%4.0f초" % down_s) if down_s is not None else " 못 봄",
                ("%4.0f초" % up_s) if up_s is not None else " 못 봄",
                reason[:60],
            ),
            flush=True,
        )

    print("\n── 요약 ─────────────────────────────────")
    named = [r for r in results if r[1] is not None and r[3] not in ("null", "?")]
    back = [r for r in results if r[2] is not None]
    print("  이름과 이유를 대고 상태가 바뀐 것   %d / %d" % (len(named), len(results)))
    print("  되살리니 ready 로 돌아온 것        %d / %d" % (len(back), len(results)))
    missed = [r[0] for r in results if r[1] is None or r[2] is None]
    if missed:
        print("  **놓친 것** — %s" % ", ".join(missed))
        return 1
    if len(named) < len(results):
        print("  **이유를 못 댄 것** — %s" % ", ".join(r[0] for r in results if r not in named))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
