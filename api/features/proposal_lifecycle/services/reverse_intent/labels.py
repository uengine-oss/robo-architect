"""047 — 그룹 카드 자연어 라벨(US2).

제목 = 테이블 logical_name → description(DDL) → 테이블명 (폴백 체인, research D5).
성격 = 대표 op stereotype 의 한국어 매핑. analyzed_description 은 미사용(사용자 결정).
"""
from __future__ import annotations

from collections import Counter

from api.features.proposal_lifecycle.services.reverse_intent.grouping import (
    AggregateGroup, LOGIC_GROUP,
)

KIND_LABEL = {"write": "핵심 데이터", "read": "조회", "logic": "로직"}

# stereotype(영문 enum) → 한국어. 미지값은 원문, 빈값은 "기타".
STEREOTYPE_KO = {
    "Command": "데이터 변경", "Query": "조회", "Validator": "검증",
    "Adapter": "연동", "ApplicationService": "응용 서비스", "Helper": "보조",
    "Service": "서비스", "Factory": "생성", "Repository": "저장소",
    "BatchProcessor": "일괄처리", "Aggregator": "집계", "EventTrigger": "이벤트 트리거",
    "DataMutator": "데이터 변경", "DataQuery": "조회", "CursorLooper": "반복처리",
    "MetadataLookup": "메타조회", "ReportGenerator": "리포트", "DataMigrator": "데이터 이관",
    "PackageInitializer": "초기화",
}

_TABLE_INFO = """
UNWIND $names AS nm
OPTIONAL MATCH (t:TABLE {name: nm})
RETURN nm AS name, t.logical_name AS logical_name,
       coalesce(t.description, '') AS description
"""


def _stereotype_ko(st: str) -> str:
    if not st:
        return "기타"
    return STEREOTYPE_KO.get(st, st)


def fetch_table_info(session, names: list[str]) -> dict[str, dict]:
    """앵커 테이블의 라벨용 정보(logical_name/description). analyzer 세션 필요."""
    real = [n for n in names if n and n != LOGIC_GROUP]
    info: dict[str, dict] = {}
    if not real:
        return info
    for r in session.run(_TABLE_INFO, names=real):
        info[r["name"]] = {
            "logical_name": r.get("logical_name"),
            "description": r.get("description") or "",
        }
    return info


def group_card(g: AggregateGroup, table_info: dict | None = None) -> dict:
    """그룹 → 사람이 읽는 카드. table_info 없으면 제목은 테이블명 폴백."""
    table_info = table_info or {}
    ti = table_info.get(g.table, {})
    if g.table == LOGIC_GROUP:
        title = "공통 로직·검증"
    else:
        title = ti.get("logical_name") or ti.get("description") or g.table
    stereos = [o.stereotype for o in g.ops if o.stereotype]
    dominant = Counter(stereos).most_common(1)[0][0] if stereos else ""
    return {
        "table": g.table,
        "title": title,
        "kind": g.kind,
        "kindLabel": KIND_LABEL.get(g.kind, g.kind),
        "opCount": len(g.ops),
        "ruleCount": g.rule_count,
        "dominantStereotype": dominant,
        "stereotypeLabel": _stereotype_ko(dominant),
        "ops": [{"logicalName": (o.logical_name or o.name)} for o in g.ops],
    }
