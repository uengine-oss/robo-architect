"""Ontological DB 는 `RETURN x {…} AS alias ORDER BY alias.prop` 을 받지 않는다
("variable 'alias' is not defined in this query"). Neo4j 는 받아서 놓치기 쉽다 — 10-31 에
BC full-tree 가 이것으로 500 이 나 설계 캔버스 · 네비게이터 · 데이터 탭이 비었다.
정렬은 MATCH 변수(rm.name)로 한다. 이 시험은 api/ 의 쿼리 문자열을 훑어 그 모양을 막는다.
"""
import re
from pathlib import Path

API = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"RETURN(.{0,600}?)ORDER BY\s+([A-Za-z_]\w*)\.", re.S)


def _alias_order_bys():
    hits = []
    for path in API.rglob("*.py"):
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        src = path.read_text(encoding="utf-8", errors="ignore")
        for m in PATTERN.finditer(src):
            ret, var = m.group(1), m.group(2)
            aliased = re.search(rf"\b(?:as|AS)\s+{var}\b", ret)
            used_as_node = re.search(rf"\b{var}\s*\{{|\b{var}\.", ret)
            if aliased and not used_as_node:
                line = src[: m.start()].count("\n") + 1
                hits.append(f"{path.relative_to(API)}:{line} ORDER BY {var}.")
    return hits


def test_no_order_by_on_projection_alias():
    assert _alias_order_bys() == []


def test_detector_catches_the_pattern(tmp_path):
    q = 'RETURN rm {.id, .name} as readmodel\n    ORDER BY readmodel.name'
    m = PATTERN.search(q)
    assert m and m.group(2) == "readmodel"
