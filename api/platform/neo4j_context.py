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
    # 분석 graph. 프로젝트는 설계와 분석이 **한 쌍**이다 — 설계는 분석에서 뽑은
    # 룰을 승격시킨 것이라, 둘을 따로 고르면 추적성이 엉뚱한 곳을 가리킨다.
    analyzer_database: Optional[str] = None
    # 프로젝트가 분석 짝을 **결정했는가**. 값이 비어 있는 것과 "정하지 않았다"를
    # 가르는 자리다. 이게 없으면 분석 없는 프로젝트가 `.env` 의 분석 graph 로
    # 조용히 떨어져 **남의 분석**을 자기 추적성으로 보게 된다.
    analyzer_pinned: bool = False

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> Optional["Neo4jOverride"]:
        """요청 헤더 → override. URI 없으면 None → .env 폴백.

        ``X-Neo4j-Database`` 는 런처에서 고른 *연결의 기본 graph* 이고,
        ``X-Project-Graph`` 는 사용자가 앱 안에서 고른 *현재 프로젝트*다. 한
        연결에 여러 프로젝트를 만들 수 있으므로 현재 프로젝트가 항상 우선한다.

        인증 연결 바인딩이 켜진 배포에서는 ``connection_binding`` 이 동일한
        우선순위와 권한 검사를 먼저 적용한다. 이 경로는 바인딩을 끈 로컬/개발
        실행에서도 프로젝트 전환이 같은 graph 로 떨어지지 않게 하는 폴백이다.
        """
        uri = headers.get("x-neo4j-uri")
        if not uri:
            return None
        return cls(
            uri=uri,
            user=headers.get("x-neo4j-user", "neo4j"),
            password=headers.get("x-neo4j-password", ""),
            database=(
                headers.get("x-project-graph")
                or headers.get("x-neo4j-database")
                or None
            ),
            analyzer_database=headers.get("x-analyzer-database") or None,
            # Electron 헤더는 프로젝트의 결정이 아니다 — 없으면 `.env` 가 맞다.
            analyzer_pinned=False,
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
