"""AGE 는 `OPTIONAL MATCH …` 바로 뒤의 `MATCH …` 를 받지 않는다("MATCH cannot follow OPTIONAL MATCH").
Neo4j · Ontological 은 받아서 놓치기 쉽다 — 11-26 AGE 판 비교에서 인스펙터 속성 표의
CQRS 참조(`/api/cqrs/property/{id}/references`)가 이것으로 500 이 났다.
MATCH 를 앞으로 옮기거나 사이에 WITH 를 둔다. 이 시험은 api/ 의 쿼리 문자열을 훑어 그 모양을 막는다.
"""
import re
from pathlib import Path

API = Path(__file__).resolve().parents[1]
QUERY = re.compile(r"(\"\"\"|''')(.*?)\1", re.S)
CLAUSE = re.compile(r"\b(OPTIONAL\s+MATCH|MATCH|WITH|UNWIND|CALL|RETURN|UNION)\b")


def _match_after_optional(query: str) -> bool:
    query = re.sub(r"//[^\n]*", "", query)  # 주석 속 낱말은 절이 아니다
    after_optional = False
    for clause in CLAUSE.findall(query):
        clause = " ".join(clause.split())
        if clause == "OPTIONAL MATCH":
            after_optional = True
        elif clause == "MATCH":
            if after_optional:
                return True
        else:  # WITH · UNWIND · CALL · RETURN · UNION 은 새 단계를 연다
            after_optional = False
    return False


def _hits():
    hits = []
    for path in API.rglob("*.py"):
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        src = path.read_text(encoding="utf-8", errors="ignore")
        for m in QUERY.finditer(src):
            if "MATCH" in m.group(2) and _match_after_optional(m.group(2)):
                hits.append(f"{path.relative_to(API)}:{src[: m.start()].count(chr(10)) + 1}")
    return hits


def test_no_match_right_after_optional_match():
    assert _hits() == []


def test_detector():
    assert _match_after_optional("MATCH (a)\nOPTIONAL MATCH (a)-->(b)\nMATCH (b)-->(c)\nRETURN c")
    assert not _match_after_optional("MATCH (a)\nOPTIONAL MATCH (a)-->(b)\nWITH a, b\nMATCH (a)-->(c)\nRETURN c")
    assert not _match_after_optional("// OPTIONAL MATCH 뒤에\nMATCH (a) RETURN a")
    assert not _match_after_optional("OPTIONAL MATCH (a) RETURN a\nUNION\nMATCH (a) RETURN a")
