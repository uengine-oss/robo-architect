"""analyzer 코드 그래프 세션(읽기 전용).

무인자 get_session 은 설계 DB(NEO4J_DATABASE)로 가서 FUNCTION/TABLE 이 없어 빈
결과를 낸다 → 반드시 ANALYZER_NEO4J_DATABASE 로 라우팅한다(research D3).
"""
from __future__ import annotations

from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session


def analyzer_session(db: str | None = None):
    """analyzer 그래프 세션. db 미지정 시 기본 ANALYZER_NEO4J_DATABASE."""
    return get_session(database=db or ANALYZER_NEO4J_DATABASE)
