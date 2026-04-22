"""Phase 3.0: build a domain glossary (Korean term ↔ English code alias).

Inputs combined:
- Document: raw text + BpmTask names/descriptions + BpmActor names.
- Analyzer graph: FUNCTION identifiers, BusinessLogic titles, BusinessLogic.coupled_domain
  (often Korean, so a direct ko↔en hint), Table names.

The glossary feeds the lexical matcher (3.1) by expanding a Korean task name
into plausible English identifiers to look for in rule/function names.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.features.ingestion.hybrid.contracts import BpmSkeleton, GlossaryTerm
from api.features.ingestion.ingestion_llm_runtime import get_llm
from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session
from api.platform.observability.smart_logger import SmartLogger

_DOC_CHAR_LIMIT = 12000  # keep prompt size bounded

SYSTEM_PROMPT = """당신은 레거시 도메인 용어집 작성자입니다.
한국어 업무 용어와 영문 코드 식별자를 연결하는 사전을 만드세요.

입력으로 문서의 업무 용어(한국어)와 레거시 코드의 식별자(영문)가 주어집니다.

규칙:
- 각 항목은 하나의 도메인 의미(예: "승인", "자격 검토")를 나타냅니다.
- `term`: 한국어 대표 용어 (또는 원문 그대로).
- `aliases`: 같은 의미로 쓰이는 한국어 동의어/유사어.
- `code_candidates`: 주어진 영문 식별자 중 이 용어를 실현할 가능성이 높은 것.
  - 근거가 없는 후보는 넣지 마세요. 빈 배열이어도 됩니다.
- 기술 구현 용어(EJB/getter/log 등)는 제외합니다.
- 중복 의미는 하나로 합치세요.
"""


class _GlossaryItem(BaseModel):
    term: str
    aliases: list[str] = Field(default_factory=list)
    code_candidates: list[str] = Field(default_factory=list)


class _GlossaryResult(BaseModel):
    items: list[_GlossaryItem]


# Tokenizer recognises four token kinds:
#   1) camelCase / snake_case English words
#   2) ALLCAPS abbreviations
#   3) digit runs
#   4) Korean (Hangul syllable) runs — critical: without this, all Korean text
#      from tasks/GWT/passages is dropped, killing lexical matching.
_CAMEL_RE = re.compile(
    r"[A-Z]?[a-z]+"
    r"|[A-Z]+(?=[A-Z]|$)"
    r"|\d+"
    r"|[\uAC00-\uD7A3]+"
)


def _split_identifier(name: str) -> list[str]:
    """camelCase / snake_case / Foo.Bar → flat tokens, lowercased.
    Also extracts Korean (Hangul) word runs so cross-lingual lexical matching works.
    """
    if not name:
        return []
    parts: list[str] = []
    # Split first on punctuation/whitespace, then run the regex within each chunk.
    for chunk in re.split(r"[._:\s/,;()\[\]\"'`]+", name):
        parts.extend(m.group(0).lower() for m in _CAMEL_RE.finditer(chunk))
    return [p for p in parts if p]


def _collect_code_tokens() -> list[str]:
    """Pull identifier tokens + Korean coupled_domain labels from the analyzer graph."""
    tokens: Counter[str] = Counter()
    ko_domains: Counter[str] = Counter()
    try:
        with get_session(database=ANALYZER_NEO4J_DATABASE) as s:
            for rec in s.run(
                "MATCH (f) WHERE f.procedure_name IS NOT NULL OR f.name IS NOT NULL "
                "RETURN coalesce(f.procedure_name, f.name) AS fn, f.summary AS summary"
            ):
                for tok in _split_identifier(rec["fn"] or ""):
                    tokens[tok] += 1
            for rec in s.run("MATCH (bl:BusinessLogic) RETURN bl.title AS title, bl.coupled_domain AS domain"):
                for tok in _split_identifier(rec["title"] or ""):
                    tokens[tok] += 1
                d = (rec["domain"] or "").strip()
                if d:
                    ko_domains[d] += 1
            for rec in s.run("MATCH (t:Table) RETURN t.name AS name"):
                for tok in _split_identifier(rec["name"] or ""):
                    tokens[tok] += 1
    except Exception as e:
        SmartLogger.log(
            "WARN", "Glossary: analyzer token scan failed",
            category="ingestion.hybrid.mapping",
            params={"error": str(e)},
        )

    # Drop obvious infra tokens and 1-char noise
    drop = {
        "ejb", "cmp", "bmp", "get", "set", "is", "log", "logger", "impl",
        "home", "bean", "dao", "util", "helper", "factory", "find", "finder",
    }
    top = [t for t, _ in tokens.most_common(200) if len(t) > 2 and t not in drop]
    # Tack Korean coupled_domain labels at the front — they bridge the ko↔en gap.
    ko = [d for d, _ in ko_domains.most_common(40)]
    return ko + top


def _task_side_corpus(skeleton: BpmSkeleton) -> list[str]:
    seeds: list[str] = []
    for a in skeleton.actors:
        seeds.append(a.name)
    for t in skeleton.tasks:
        seeds.append(t.name)
        if t.description:
            seeds.append(t.description)
    return [s for s in seeds if s]


async def extract_glossary(document_text: str, skeleton: BpmSkeleton) -> list[GlossaryTerm]:
    """Run one LLM pass to produce a ko↔en glossary for Phase 3 matching."""
    doc = (document_text or "")[:_DOC_CHAR_LIMIT]
    task_seeds = _task_side_corpus(skeleton)
    code_tokens = _collect_code_tokens()

    user = (
        "### 문서 발췌\n" + doc +
        "\n\n### 업무 용어 후보 (문서/Task)\n" + ", ".join(task_seeds[:200]) +
        "\n\n### 코드 식별자 토큰 (영문 위주, 뒤쪽은 한글 coupled_domain)\n" + ", ".join(code_tokens[:200]) +
        "\n\n위 자료를 바탕으로 용어집을 JSON으로 작성하세요."
    )

    try:
        llm = get_llm()
        structured = llm.with_structured_output(_GlossaryResult)
        result: _GlossaryResult = await structured.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user),
        ])
    except Exception as e:
        SmartLogger.log(
            "WARN", "Glossary LLM extraction failed; returning empty glossary",
            category="ingestion.hybrid.mapping",
            params={"error": str(e)},
        )
        return []

    out: list[GlossaryTerm] = []
    seen_terms: set[str] = set()
    for it in result.items:
        key = it.term.strip()
        if not key or key in seen_terms:
            continue
        seen_terms.add(key)
        out.append(GlossaryTerm(
            term=key,
            aliases=[a.strip() for a in (it.aliases or []) if a.strip() and a.strip() != key],
            code_candidates=[c.strip() for c in (it.code_candidates or []) if c.strip()],
            source="llm",
        ))

    SmartLogger.log(
        "INFO", "Glossary extracted",
        category="ingestion.hybrid.mapping",
        params={"term_count": len(out)},
    )
    return out


def expand_task_tokens(task_text: str, glossary: Iterable[GlossaryTerm]) -> set[str]:
    """Given a task string, return the set of normalized tokens (aliases + code candidates)."""
    text = (task_text or "")
    tokens: set[str] = set()
    for item in _split_identifier(text):
        tokens.add(item)
    tl = text.strip()
    for g in glossary:
        if not tl:
            break
        pool = [g.term] + list(g.aliases)
        if any(p and p in text for p in pool):
            for c in g.code_candidates:
                for tok in _split_identifier(c):
                    tokens.add(tok)
    return tokens
