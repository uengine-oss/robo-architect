"""Figma 가져오기가 실제로 무언가를 바꾸는가.

"가져오기를 눌러도 변화가 없다"는 신고에서 나왔다. 확인해야 할 것이 둘이다.

  1. 플러그인이 **살아 있는 프레임**을 읽어 오는가
  2. 읽어 온 것이 **그래프에 남는가**

두 번째는 같은 것을 다시 가져오는 것만으로는 증명되지 않는다 — 저장을 하든
안 하든 결과가 같다. 그래서 저장된 sceneGraph 를 일부러 흐트러뜨린 뒤,
가져오기가 Figma 원본으로 되돌려 놓는지 본다.

    robo-architect/.venv/bin/python scripts/verify_figma_pull.py

백엔드가 떠 있어야 하고 **Figma 에서 플러그인을 열어 둬야 한다.**
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neo4j  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API = "http://localhost:8000"
failed = 0


def check(ok: bool, label: str, detail: str = "") -> None:
    global failed
    print(f"{'✓' if ok else '✗'} {label}{'  ' + detail if detail else ''}")
    if not ok:
        failed += 1


def get(path: str):
    return json.load(urllib.request.urlopen(API + path, timeout=60))


def post(path: str):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(API + path, method="POST"), timeout=180))


def put(path: str, body: dict):
    return json.load(urllib.request.urlopen(urllib.request.Request(
        API + path, data=json.dumps(body).encode(), method="PUT",
        headers={"Content-Type": "application/json"}), timeout=60))


driver = neo4j.GraphDatabase.driver(
    os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))
GRAPH = os.environ.get("NEO4J_DATABASE", "robo")


def stored(uid: str) -> str:
    with driver.session(database=GRAPH) as s:
        row = s.run("MATCH (u:UI {id: $i}) RETURN u.sceneGraph AS sg", i=uid).single()
    return (row and row["sg"]) or ""


binding = get("/api/figma-binding")
check(binding.get("status") == "active", "Figma 바인딩이 활성이다",
      binding.get("figmaFileKey") or "")
if binding.get("status") != "active":
    sys.exit(1)

with driver.session(database=GRAPH) as s:
    row = s.run("""
        MATCH (u:UI)
        WHERE u.figmaNodeId IS NOT NULL AND u.sceneGraph IS NOT NULL
        RETURN u.id AS id, u.name AS name, u.figmaNodeId AS fid ORDER BY u.id LIMIT 1
    """).single()
check(row is not None, "Figma 에 연결된 UI 가 있다", row["name"] if row else "없음")
if not row:
    sys.exit(1)
uid, name, fid = row["id"], row["name"], row["fid"]
print(f"   대상: {name} · figmaNodeId={fid}")

first = post(f"/api/figma-binding/pull-frame/{uid}")
check(bool(first.get("ok")) and bool(first.get("sceneGraph")),
      "플러그인이 프레임을 읽어 온다",
      f"{first.get('figmaFrameName')} · {first.get('nodeCount')}개 노드")
original = first["sceneGraph"]

second = post(f"/api/figma-binding/pull-frame/{uid}")
check(second.get("sceneGraph") == original, "두 번 가져오면 같은 결과가 온다")

# 저장을 흐트러뜨린다 — TEXT 하나를 지운다.
wrecked = json.loads(original)
victim = next((k for k, v in wrecked["nodes"].items() if v.get("type") == "TEXT"), None)
check(victim is not None, "흐트러뜨릴 TEXT 노드가 있다", str(victim))
if victim is None:
    sys.exit(1)
del wrecked["nodes"][victim]
put(f"/api/graph/update-node/{uid}", {"sceneGraph": json.dumps(wrecked, ensure_ascii=False)})
check(stored(uid) != original, "흐트러뜨린 값이 그래프에 저장됐다",
      f"{len(json.loads(stored(uid))['nodes'])}개 노드 (원본 {len(json.loads(original)['nodes'])}개)")

third = post(f"/api/figma-binding/pull-frame/{uid}")
check(third.get("sceneGraph") == original, "가져오기가 Figma 원본을 그대로 돌려준다")
check(stored(uid) == original, "**가져온 것이 그래프에 저장된다** — 화면을 벗어나도 남는다")

print()
print("전부 통과" if not failed else f"실패 {failed}건")
sys.exit(1 if failed else 0)
