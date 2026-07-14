"""요청별 Neo4j 연결 override — Electron 이 고른 연결을 요청 컨텍스트에 싣는다.

계약 (analyzer / catalog / data-fabric 과 동일):
- 헤더 ``X-Neo4j-*`` 가 있으면 그 연결을 쓴다 (Electron 데스크톱).
- 없으면 ``.env`` 를 쓴다 (브라우저/로컬 테스트/CLI).
- contextvar 라 요청별 격리 — 요청 간 오염 없음.
"""
from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class Neo4jOverride:
    """요청이 실어 보낸 Neo4j 연결. ``database`` 미지정이면 호출측 기본값 사용."""

    uri: str
    user: str
    password: str
    database: Optional[str] = None

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> Optional["Neo4jOverride"]:
        """``X-Neo4j-*`` 헤더 → override. URI 없으면 None → .env 폴백."""
        uri = headers.get("x-neo4j-uri")
        if not uri:
            return None
        return cls(
            uri=uri,
            user=headers.get("x-neo4j-user", "neo4j"),
            password=headers.get("x-neo4j-password", ""),
            database=headers.get("x-neo4j-database") or None,
        )


_override: contextvars.ContextVar[Optional[Neo4jOverride]] = contextvars.ContextVar(
    "neo4j_override", default=None
)


def set_override(conn: Optional[Neo4jOverride]) -> None:
    """현재 요청 컨텍스트의 override 설정 (미들웨어에서 1회)."""
    _override.set(conn)


def get_override() -> Optional[Neo4jOverride]:
    """현재 컨텍스트의 override 조회 (get_session 이 사용). 없으면 None → .env."""
    return _override.get()
