"""Phase 3.0+ : glossary-driven term normalization for retrieval embeddings (spec 036).

평문 요구사항(한국어 GWT)과 레거시 코드 룰(개발자 약어)의 어휘 분포 차이로,
임베딩 코사인이 0.45~0.55 좁은 밴드로 collapse → 매핑돼야 할 룰이 retrieval
floor(`MIN_BL_INCLUSION`)에서 LLM 검증기 도달 전 탈락한다(recall 손실).

이 모듈은 이미 추출된 glossary(`extract_glossary`)를 임베딩 입력에 **양방향**으로
주입한다:
  - task query  ← 매칭 glossary 항목의 code_candidates(영문 약어) append
  - rule blob   ← 매칭 glossary 항목의 term/aliases(한국어 평문) append

floor·후보 예산은 건드리지 않는다. 원문은 보존하고 토큰을 덧붙이기만 하므로(append,
replace 아님), 잘못된 정규화로 무관 룰이 후보에 진입해도 최종 판정은 LLM 검증기가
한다(사용자 화면 불변). 순수 함수 — 부수효과·LLM 호출 없음.
"""

from __future__ import annotations

from api.features.ingestion.hybrid.contracts import GlossaryTerm, RuleContext, RuleDTO


def _dedup_keep_order(existing: str, additions: list[str]) -> list[str]:
    """원문(existing)에 이미 등장하지 않은 토큰만, 첫 등장 순서로 반환(결정성)."""
    out: list[str] = []
    seen: set[str] = set()
    for tok in additions:
        t = (tok or "").strip()
        if not t or t in seen or t in existing:
            continue
        seen.add(t)
        out.append(t)
    return out


def normalize_query(
    query: str,
    glossary: list[GlossaryTerm] | None,
    *,
    max_aliases_per_term: int = 5,
) -> tuple[str, bool]:
    """task query에 매칭 glossary 항목의 code_candidates를 덧붙인다.

    매칭 = 항목의 term 또는 aliases 중 하나가 query에 부분 문자열로 등장.
    반환: (정규화된 query, applied). glossary 비어있으면 (원문, False).
    """
    if not query or not glossary:
        return query, False

    additions: list[str] = []
    for g in glossary:
        pool = [g.term, *(g.aliases or [])]
        if any(p and p in query for p in pool):
            additions.extend((g.code_candidates or [])[:max_aliases_per_term])

    fresh = _dedup_keep_order(query, additions)
    if not fresh:
        return query, False
    # 원문 보존 + 정규화 토큰 append. 임베딩이 평문↔약어 양쪽 어휘를 공유하게 한다.
    return f"{query}\n[용어: {' '.join(fresh)}]", True


def normalize_rule_blob(
    blob: str,
    rule: RuleDTO | None,
    ctx: RuleContext | None,
    glossary: list[GlossaryTerm] | None,
    *,
    max_terms_per_candidate: int = 3,
) -> tuple[str, bool]:
    """rule blob에 매칭 glossary 항목의 term/aliases를 덧붙인다.

    매칭 = 항목의 code_candidates 중 하나가 rule의 source_module/source_function/
    title(소문자 비교)에 부분 문자열로 등장.
    반환: (정규화된 blob, applied). glossary 비어있으면 (원문, False).
    """
    if not blob or not glossary:
        return blob, False

    haystack_parts = [
        getattr(rule, "title", None) or "",
        getattr(rule, "source_module", None) or getattr(ctx, "source_module", None) or "",
        getattr(rule, "source_function", None) or getattr(ctx, "source_function", None) or "",
    ]
    haystack = " ".join(haystack_parts).lower()
    if not haystack.strip():
        return blob, False

    additions: list[str] = []
    for g in glossary:
        cands = [c.lower() for c in (g.code_candidates or []) if c]
        if any(c and c in haystack for c in cands):
            terms = [g.term, *(g.aliases or [])]
            additions.extend([t for t in terms if t][:max_terms_per_candidate])

    fresh = _dedup_keep_order(blob, additions)
    if not fresh:
        return blob, False
    return f"{blob}\n[업무용어: {' '.join(fresh)}]", True
