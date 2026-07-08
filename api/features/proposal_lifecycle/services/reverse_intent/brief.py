"""무손실 브리프 — Aggregate 그룹을 그래프 그대로(요약 없이) 텍스트로.

예산 초과 시 오퍼레이션 경계로만 서브분할(룰·문장 중간 절대 안 자름 = 오퍼레이션 원자).
summary 는 머리말로만 쓰고, substance 는 rollup 된 룰·GWT. PoC 이식.
"""
from __future__ import annotations

from dataclasses import dataclass

from api.features.proposal_lifecycle.services.reverse_intent.grouping import (
    AggregateGroup, Operation,
)

_CHARS_PER_TOKEN = 1.3  # 한국어 혼합 보수 추정
TOKEN_BUDGET = 20000    # 브리프 1건 목표 예산(초과 시 오퍼레이션 경계로 분할)


def estimate_tokens(text: str) -> int:
    return int(len(text) / _CHARS_PER_TOKEN)


@dataclass
class Brief:
    table: str
    text: str
    part: int          # 1-based
    total: int         # 이 테이블의 총 파트 수
    op_count: int
    rule_count: int

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.text)


def _render_op(o: Operation) -> list[str]:
    L = [f"## 오퍼레이션: {o.name}"]
    if o.summary:
        L.append(f"- 요약: {o.summary.strip()[:160]}")
    if o.rules:
        L.append("- 규칙:")
        L += [f"   - {(r or '').strip()}" for r in o.rules]
    if o.examples:
        L.append("- 시나리오:")
        for e in o.examples:
            g = (e.get("g") or "").replace("\n", " ").strip()
            w = (e.get("w") or "").replace("\n", " ").strip()
            t = (e.get("t") or "").replace("\n", " ").strip()
            if g or t:
                L.append(f"   - GIVEN {g} / WHEN {w} / THEN {t}")
    L.append("")
    return L


def _render(table: str, ops: list[Operation]) -> str:
    head = [f"# Aggregate 후보(데이터): {table}", ""]
    body: list[str] = []
    for o in ops:
        body += _render_op(o)
    return "\n".join(head + body)


def split_by_budget(group: AggregateGroup, budget: int = TOKEN_BUDGET) -> list[Brief]:
    """그룹을 예산 내 파트들로. 오퍼레이션은 통째(원자). 단일 op 가 예산 초과면 그대로 1파트."""
    parts: list[list[Operation]] = []
    cur: list[Operation] = []
    cur_tok = estimate_tokens(_render(group.table, []))  # 헤더 오버헤드
    for op in group.ops:
        op_tok = estimate_tokens("\n".join(_render_op(op)))
        if cur and cur_tok + op_tok > budget:
            parts.append(cur)
            cur, cur_tok = [], estimate_tokens(_render(group.table, []))
        cur.append(op)
        cur_tok += op_tok
    if cur:
        parts.append(cur)

    total = len(parts)
    out: list[Brief] = []
    for i, ops in enumerate(parts, start=1):
        text = _render(group.table, ops)
        out.append(
            Brief(
                table=group.table, text=text, part=i, total=total,
                op_count=len(ops), rule_count=sum(len(o.rules) for o in ops),
            )
        )
    return out
