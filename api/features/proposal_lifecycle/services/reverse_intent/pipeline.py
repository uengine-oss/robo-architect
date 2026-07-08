"""047 — 역추출 오케스트레이터(async, SSE용).

analyzer 세션 → 테이블 앵커 그룹핑(결정론) → 무손실 브리프(예산 분할) →
브리프별 기존 robo-proposal-intent 스킬 호출 → 테이블 병합. analyzer 그래프는 읽기 전용.
라벨 카드 상세는 labels.py(US2)가 풍부화한다.
"""
from __future__ import annotations

from typing import AsyncGenerator

from api.platform.skill_runner import run_skill_once, extract_json
from api.features.proposal_lifecycle.services.intent_runner import _build_reverse_prompt
from api.features.proposal_lifecycle.services.reverse_intent import brief as briefmod
from api.features.proposal_lifecycle.services.reverse_intent import grouping, labels
from api.features.proposal_lifecycle.services.reverse_intent.merge import merge_strategic_diffs
from api.features.proposal_lifecycle.services.reverse_intent.neo4j_read import analyzer_session

_SKILL_ROOT = "robo-proposals"
_SKILL_NAME = "robo-proposal-intent"


def build_groups(db: str) -> tuple[list[grouping.AggregateGroup], dict]:
    """그룹 + 앵커 테이블 라벨 정보(한 세션에서 함께 조회)."""
    with analyzer_session(db) as s:
        groups = grouping.assign_groups(s)
        table_info = labels.fetch_table_info(s, [g.table for g in groups])
    return groups, table_info


def preview_groups(db: str) -> list[dict]:
    """요구사항 도출 전, 선택용 그룹 카드 목록(LLM 없이·읽기 전용, FR-004)."""
    groups, table_info = build_groups(db)
    return [labels.group_card(g, table_info) for g in groups]


async def stream_reverse(
    db: str, selected: list[str] | None = None,
) -> AsyncGenerator[tuple[str, object], None]:
    """역추출 실행. selected(그룹 table 키 목록)가 주어지면 그 그룹만(FR-005/009).
    yield: phase / groups / log_line / brief_result / strategic_diff / error.
    최종 strategic_diff 저장은 호출 라우트가 담당(analyzer 그래프는 읽기 전용)."""
    yield "phase", {"phase": "grouping", "message": "코드 그래프를 데이터 단위로 그룹핑 중..."}
    try:
        groups, table_info = build_groups(db)
    except Exception as e:
        yield "error", {"code": "GRAPH_READ_FAILED", "message": f"그래프 읽기 실패: {e}"}
        return
    if selected:
        sel = set(selected)
        groups = [g for g in groups if g.table in sel]
    if not groups:
        yield "error", {"code": "NO_GROUPS",
                        "message": "선택된 데이터 그룹이 없습니다."}
        return

    yield "groups", {"groups": [labels.group_card(g, table_info) for g in groups]}

    briefs = [b for g in groups for b in briefmod.split_by_budget(g)]
    total = len(briefs)
    results: list[dict] = []
    for i, b in enumerate(briefs, start=1):
        yield "phase", {"phase": "deriving",
                        "message": f"요구사항 도출 {i}/{total} — {b.table}"}
        raw = await run_skill_once(_SKILL_ROOT, _SKILL_NAME,
                                   _build_reverse_prompt(b.text), timeout=420)
        data = extract_json(raw or "")
        results.append({"table": b.table, "data": data})
        yield "brief_result", {"table": b.table, "part": b.part, "total": b.total}

    merged = merge_strategic_diffs(results)
    yield "strategic_diff", {"strategicDiff": merged}
