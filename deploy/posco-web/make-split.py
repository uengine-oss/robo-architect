"""통합 `docker-compose.yml` 에서 분할 두 파일을 **만든다.** 손으로 고치지 않는다.

    python make-split.py          # split.db / split.ap 를 다시 쓴다
    python make-split.py --check  # 다시 만들어 보고, 커밋된 파일과 다르면 1 로 끝난다

## 왜 생성하나

서비스 정의를 세 파일에 손으로 적으면 반드시 한쪽이 뒤처지고, 뒤처진 쪽은 조용하다.
설치본도 같은 이유로 `compose.remote-graph.yml` 을 **차이만 적는 overlay** 로 뒀다.
여기서는 현장(podman)의 compose 구현이 `include`·`!reset` 같은 기능을 다 받는지
장담할 수 없어, overlay 대신 **완결된 파일 셋**을 내되 둘을 이 스크립트가 만든다.
기준은 통합 파일 하나다.

## 바꾸는 것 (그 밖에는 글자 하나 안 바꾼다)

DB 서버  graph-db · graph-init · authority · authority-init
         AP 서버가 닿아야 하므로 포트 둘(5432 · 59020)을 `${ROBO_DB_SERVER_IP}` 에 연다
AP 서버  나머지 전부 — **graph-bolt(Bolt 게이트웨이)도 AP 에 둔다**(AGE 판, 2026-11-26)
         Bolt 는 비밀번호를 평문으로 보낸다 → 망을 건너는 것은 PostgreSQL(scram-sha-256)뿐이게.
         graph-db · authority 를 가리키는 주소를 DB 서버 IP 로 바꾸고,
         DB 쪽 서비스를 기다리던 depends_on 을 뺀다(다른 서버라 compose 가 못 기다린다)
"""

import re
import sys
from typing import Dict, List, Tuple  # 3.6(RHEL 8 기본 python3)에서도 돈다 — list[str] · __future__ annotations 를 쓰지 않는다
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "docker-compose.yml"
DB_FILE = HERE / "docker-compose.split.db.yml"
AP_FILE = HERE / "docker-compose.split.ap.yml"

DB_SERVICES = ("graph-db", "graph-init", "authority", "authority-init")

DB_PORTS = {
    "graph-db": '      - "${ROBO_DB_SERVER_IP:?}:${ROBO_DB_PG_PORT:-5432}:5432"',
    "authority": '      - "${ROBO_DB_SERVER_IP:?}:${ROBO_AUTHORITY_PORT:-59020}:59020"',
}

AP_REWRITES = (
    ("OG_PG_HOST: graph-db", "OG_PG_HOST: ${ROBO_DB_SERVER_IP:?}"),
    ('OG_PG_PORT: "5432"', "OG_PG_PORT: ${ROBO_DB_PG_PORT:-5432}"),
    ("OG_BOLT_PGHOST: graph-db", "OG_BOLT_PGHOST: ${ROBO_DB_SERVER_IP:?}"),
    ('OG_BOLT_PGPORT: "5432"', "OG_BOLT_PGPORT: ${ROBO_DB_PG_PORT:-5432}"),
    ("http://authority:59020", "http://${ROBO_DB_SERVER_IP:?}:${ROBO_AUTHORITY_PORT:-59020}"),
)

HEADER = """# =====================================================================
# Robo Architect 서버 배포 (posco-web) — **{role}**
#
# ⚠ 이 파일은 `make-split.py` 가 `docker-compose.yml` 에서 만든다. 손으로 고치지 않는다.
#   고칠 것은 통합 파일에서 고치고 `python make-split.py` 를 다시 돌린다.
#
#   {usage}
#
# 두 서버의 `.env` 는 **같은 값**이어야 한다(.env.example 참고).
# 설명은 통합 파일의 주석과 README.md 에 있다.
# =====================================================================

"""


def split_blocks(text: str) -> Tuple[str, Dict[str, str], str]:
    """(services 앞, {서비스: 블록}, volumes 부터) 로 가른다."""
    head, rest = text.split("\nservices:\n", 1)
    body, tail = rest.split("\nvolumes:\n", 1)
    blocks = {}  # type: Dict[str, str]
    name = None
    for line in body.splitlines(keepends=True):
        match = re.match(r"^  ([a-z0-9-]+):\s*$", line)
        if match:
            name = match.group(1)
            blocks[name] = ""
        if name is None:
            continue  # 첫 서비스 앞의 주석
        blocks[name] += line
    return head, blocks, "volumes:\n" + tail


def strip_comment_tail(block: str) -> str:
    """블록 끝에 붙은 '다음 서비스용' 주석·빈 줄을 뗀다(그 주석은 다음 서비스 몫이다)."""
    lines = block.splitlines(keepends=True)
    while lines and (lines[-1].strip() == "" or lines[-1].lstrip().startswith("#")) \
            and not lines[-1].startswith("      "):
        lines.pop()
    return "".join(lines)


def preamble(head: str) -> str:
    """`name:` 과 `x-*` 앵커 블록만 남긴다(헤더 주석은 새로 쓴다)."""
    keep = []
    on = False
    for line in head.splitlines(keepends=True):
        if re.match(r"^(name|x-[a-z0-9-]+):", line):
            on = True
        elif line and not line.startswith(" ") and not line.startswith("\n"):
            on = False
        if on:
            keep.append(line)
    return "".join(keep).rstrip() + "\n\n"


def add_ports(name: str, block: str) -> str:
    if name not in DB_PORTS:
        return block
    assert "    ports:" not in block, f"{name}: 통합 파일에 이미 ports 가 있다"
    anchor = "    environment:"
    assert anchor in block, f"{name}: environment 가 없다"
    return block.replace(anchor, "    ports:\n" + DB_PORTS[name] + "\n" + anchor, 1)


def drop_db_dependencies(block: str) -> str:
    lines = block.splitlines(keepends=True)
    out = []  # type: List[str]
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.rstrip() == "    depends_on:":
            deps = []  # type: List[str]
            i += 1
            while i < len(lines) and lines[i].startswith("      "):
                deps.append(lines[i])
                i += 1
            kept = []  # type: List[str]
            j = 0
            while j < len(deps):
                m = re.match(r"^      ([a-z0-9-]+):", deps[j])
                group = [deps[j]]
                j += 1
                while j < len(deps) and deps[j].startswith("        "):
                    group.append(deps[j])
                    j += 1
                if not (m and m.group(1) in DB_SERVICES):
                    kept.extend(group)
            if kept:
                out.append(line)
                out.extend(kept)
            continue
        out.append(line)
        i += 1
    return "".join(out)


def build() -> Dict[Path, str]:
    head, blocks, volumes = split_blocks(SOURCE.read_text(encoding="utf-8"))
    missing = [s for s in DB_SERVICES if s not in blocks]
    assert not missing, f"통합 파일에 없는 DB 서비스: {missing}"
    pre = preamble(head)

    db = HEADER.format(role="DB 서버", usage="docker compose -f docker-compose.split.db.yml up -d --wait")
    db += pre + "services:\n"
    for name in DB_SERVICES:
        db += add_ports(name, strip_comment_tail(blocks[name])) + "\n"
    all_volumes = re.findall(r"^  ([a-z_]+):", volumes, re.M)
    db_volumes = [v for v in all_volumes if v.startswith("graph_")]
    assert db_volumes, "통합 파일에 graph_* 볼륨이 없다"
    db = db.rstrip() + "\n\nvolumes:\n" + "".join(f"  {v}:\n" for v in db_volumes)

    ap = HEADER.format(role="AP 서버", usage="docker compose -f docker-compose.split.ap.yml up -d --wait")
    ap += pre + "services:\n"
    for name, block in blocks.items():
        if name in DB_SERVICES:
            continue
        block = strip_comment_tail(block)
        for old, new in AP_REWRITES:
            block = block.replace(old, new)
        ap += drop_db_dependencies(block) + "\n"
    ap_volumes = [v for v in all_volumes if v not in db_volumes]
    ap = ap.rstrip() + "\n\nvolumes:\n" + "".join(f"  {v}:\n" for v in ap_volumes)

    # 남은 내부 이름이 있으면 그 서비스는 다른 서버에서 **조용히 닿지 않는다.**
    for svc in DB_SERVICES:
        for hit in re.findall(rf"[/@ ]{re.escape(svc)}:\d+|: {re.escape(svc)}$", ap, re.M):
            raise SystemExit(f"AP 파일에 DB 서비스 주소가 남았다: {hit.strip()}")
    # Bolt(평문)는 망을 건너지 않는다 — 게이트웨이는 AP 에만
    if "  graph-bolt:\n" in db or "  graph-bolt:\n" not in ap:
        raise SystemExit("graph-bolt 는 AP 파일에만 있어야 한다")
    return {DB_FILE: db, AP_FILE: ap}


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for path, text in build().items():
        if check:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != text:
                stale.append(path.name)
        else:
            with open(str(path), "w", encoding="utf-8", newline="\n") as f:  # write_text(newline=) 는 3.10~
                f.write(text)
            print(f"wrote {path.name}")
    if stale:
        print("분할 파일이 통합 파일과 어긋났다 — python make-split.py 를 돌린다: " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
