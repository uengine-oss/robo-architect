# -*- coding: utf-8 -*-
"""앱이 **안 쓰는 2,819줄**을 기동 때 가져오지 않는가 (DEAD-1 ①).

## 왜 이 검사가 있나

`event_storming` 패키지에는 앱에서 **아무도 부르지 않는** cli 묶음 14파일이 있다
(`cli.py` · `graph.py` · `nodes.py` 파사드 · `nodes_*` 열하나 · `node_runtime.py`).
앱이 실제로 쓰는 것은 다섯이다 — `neo4j_client` · `neo4j_ops` · `prompts` ·
`state` · `structured_outputs`.

2026-10-07 에 재다가 **적혀 있던 처방이 틀린 것**을 알았다. 문서는 "phases 다섯
파일의 파사드 임포트만 끊으면 된다" 고 했는데, 끊어도 **35개가 그대로 올라왔다** —
진짜 문이 패키지 `__init__` 이었다. `__init__` 이 `.graph` 를, `.graph` 가 `.nodes` 를
끌고 오니 **`structured_outputs` 에서 이름 하나만 가져와도** 전부 따라왔다.

```
고치기 전   phases.aggregates 하나 → event_storming 모듈 35개 (죽은 쪽 13개)
고친 뒤     같은 임포트           → 3개 (죽은 쪽 0개)
api.main    전체 기동             → 25개 · **죽은 쪽 0개**
```

그래서 이 검사는 그 문을 지킨다. `__init__` 에 즉시 임포트를 다시 넣으면 **여기서
먼저 무다** — 안 그러면 조용히 되돌아가고, 아무 오류도 안 난다.

## 재는 법 — **따로 띄운 파이썬에서** 센다

같은 프로세스에서 세면 안 된다. 다른 검사가 cli 를 한 번이라도 가져왔으면
`sys.modules` 에 남아 있어 **이 검사가 거짓 실패**한다. 그래서 자식 프로세스를
띄워 거기서 센다 — 재는 도구가 먼저 틀리는 쪽이다.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# 앱이 안 부르는 쪽. 이 중 하나라도 올라오면 파사드 문이 다시 열린 것이다.
DEAD_HINTS = (".nodes", ".node_runtime", ".graph", ".cli")

_COUNT_SCRIPT = """
import json, sys
import api.features.ingestion.workflow.phases.aggregates  # noqa: F401
mods = [m for m in sys.modules if 'event_storming' in m]
print(json.dumps(mods))
"""


def _loaded_modules() -> list[str]:
    done = subprocess.run(
        [sys.executable, "-c", _COUNT_SCRIPT],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert done.returncode == 0, "자식 프로세스가 죽었다:\n%s" % done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def _dead(modules: list[str]) -> list[str]:
    return sorted(m for m in modules if any(h in m for h in DEAD_HINTS) and not m.endswith("event_storming"))


def test_phase_import_does_not_pull_cli_cluster():
    """`structured_outputs` 를 쓰는 길에 cli 묶음이 **따라오지 않는다.**"""
    modules = _loaded_modules()
    assert modules, "아무것도 못 쟀다 — 자식 프로세스의 임포트를 확인한다"
    dead = _dead(modules)
    assert dead == [], (
        "앱이 안 부르는 묶음이 기동 때 올라온다: %s\n"
        "패키지 `__init__` 이 `.graph` 를 즉시 가져오는지 본다(DEAD-1 ①)." % dead
    )


def test_live_names_still_reachable():
    """게으르게 바꿔도 **밖에서 보이는 모양은 같다.**"""
    import api.features.ingestion.event_storming as package

    assert package.create_event_storming_graph.__name__ == "create_event_storming_graph"
    assert package.EventStormingState.__name__ == "EventStormingState"


def test_unknown_name_still_raises_attribute_error():
    """`__getattr__` 을 두면 **없는 이름이 조용해지는** 사고가 난다 — 안 그런지 본다."""
    import api.features.ingestion.event_storming as package

    try:
        package.없는_이름
    except AttributeError:
        return
    raise AssertionError("없는 이름이 AttributeError 를 안 냈다")
