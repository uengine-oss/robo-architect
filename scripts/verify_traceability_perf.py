"""요소별 출처 조회가 느려지지 않았는지.

느려지는 방식이 정해져 있다 — **가변길이 구간과 관계 변수를 한 패턴에 같이 두면**
컴파일된 SQL 이 노드 테이블을 CROSS JOIN 하고, 라벨 없는 노드의 속성을
`og_node_json()` 으로 행마다 푼다. 한 번 호출이면 9.7초, UserStory 마다 도니
Aggregate 하나가 180초를 넘겼다. 오류는 안 난다. 화면이 안 돌아올 뿐이다.

    robo-architect/.venv/bin/python scripts/verify_traceability_perf.py

백엔드와 그래프에 데이터가 있어야 한다.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neo4j  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# 고치기 전 실측이 Command 34초 · Event 11초 · Aggregate 180초 초과였다.
# 고친 뒤는 전부 1초 미만이다. 5초는 그 사이 어디에도 걸리지 않는 자리다.
BUDGET_S = 5.0
TYPES = ("Aggregate", "Command", "Event", "ReadModel", "Policy", "UI", "UserStory")

failed = 0


def check(ok: bool, label: str, detail: str = "") -> None:
    global failed
    print(f"{'✓' if ok else '✗'} {label}{'  ' + detail if detail else ''}")
    if not ok:
        failed += 1


driver = neo4j.GraphDatabase.driver(
    os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
)
targets: list[tuple[str, str]] = []
with driver.session(database=os.environ.get("NEO4J_DATABASE", "robo")) as s:
    for lbl in TYPES:
        row = s.run(f"MATCH (n:{lbl}) RETURN n.id AS id ORDER BY n.id LIMIT 1").single()
        if row:
            targets.append((lbl, row["id"]))

check(len(targets) >= 3, "조회할 요소가 있다", f"{len(targets)}종")
if len(targets) < 3:
    print("\n그래프가 비어 있다 — 모델을 만든 뒤에 돌린다.")
    sys.exit(1)

total = 0.0
with_sources = 0
for lbl, node_id in targets:
    started = time.time()
    try:
        body = json.load(urllib.request.urlopen(
            f"http://localhost:8000/api/graph/traceability/{node_id}", timeout=int(BUDGET_S * 8)))
        elapsed = time.time() - started
        srcs = body.get("sources") or []
        rules = sum(len(x.get("rules") or []) for x in srcs)
        if srcs:
            with_sources += 1
        check(elapsed < BUDGET_S, f"{lbl} 출처 조회가 {BUDGET_S:.0f}초 안에 온다",
              f"{elapsed:.2f}s · 출처 {len(srcs)}건 · 규칙 {rules}건")
    except Exception as e:  # noqa: BLE001 — 타임아웃도 실패로 센다
        elapsed = time.time() - started
        check(False, f"{lbl} 출처 조회가 {BUDGET_S:.0f}초 안에 온다",
              f"{elapsed:.2f}s · {str(e)[:60]}")
    total += elapsed

# 빠르기만 하고 아무것도 안 오면 고친 게 아니라 망가뜨린 것이다.
check(with_sources > 0, "실제로 출처가 실려 온다", f"{with_sources}/{len(targets)}종")
check(total < BUDGET_S * 2, "전부 합쳐도 오래 걸리지 않는다", f"{total:.2f}s")

print()
print("전부 통과" if not failed else f"실패 {failed}건")
sys.exit(1 if failed else 0)
