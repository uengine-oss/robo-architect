"""Hierarchical Agentic Retrieval — Step 1: Module top-k.

Given a `BpmProcess` (name + domain_keywords) and a target `BpmTask`
(name + description), narrow the rule-search space by first identifying
which analyzer MODULEs are likely to host rules implementing this
process's tasks (docs/legacy-ingestion/개선&재구조화.md §B).

Pipeline: `Process.name + domain_keywords + Task.name` → vector query →
MODULE.summary cosine → top-k (default 5).

MODULE embeddings are cached per-session via `EmbeddingCache` to avoid
re-embedding the analyzer graph on each Task. For large graphs a future
migration can promote the cache to `MODULE.embedding` on the analyzer
side (see §B "MODULE 임베딩 캐싱").
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Optional

from api.features.ingestion.hybrid.contracts import BpmProcess, BpmTaskDTO
from api.features.ingestion.hybrid.mapper.embeddings import EmbeddingCache, cosine
from api.platform.neo4j import analyzer_database, analyzer_session, get_session
from api.platform.observability.smart_logger import SmartLogger


# ---------------------------------------------------------------------------
# 왜 0건인가 — 화면이 사람에게 옮겨 줄 수 있는 이유
#
# 룰 매핑이 0으로 끝나는 길은 여럿인데 **화면에는 전부 같은 모양("매핑 0")으로
# 보인다.** 그래서 사용자는 "기능이 고장났다" 로 읽는다. 2026-09-28 에 실제로
# 그렇게 보고됐고, 실측해 보니 원인은 ③ 이었다(문서는 인사, 코드는 수납).
#
# 이유를 여기서 한 번 정하고, 탐색이 끝날 때 그대로 올려 보낸다.
REASON_NO_ANALYSIS_LINK = "analysis_not_linked"
REASON_NO_SUMMARIES = "analysis_has_no_summaries"

# 마지막 조회가 왜 비었는지. **요청마다 다시 계산되는 값**이라 전역으로 두어도
# 섞이지 않는다 — 한 탐색 안에서 즉시 읽어 간다.
_last_reason: Optional[str] = None


def _set_last_reason(reason: Optional[str]) -> None:
    global _last_reason
    _last_reason = reason


def last_empty_reason() -> Optional[str]:
    """직전 모듈 조회가 비어 있었다면 그 이유. 비지 않았으면 `None`."""
    return _last_reason


def reset_empty_reason() -> None:
    """탐색을 시작하기 전에 비운다.

    **안 비우면 지난 탐색의 이유가 이번 결과에 붙는다.** 캐시 적중으로 모듈 조회
    자체를 건너뛴 탐색이 특히 그렇다 — 그때는 아무도 이 값을 덮어쓰지 않는다.
    """
    _set_last_reason(None)


@dataclass
class ModuleCandidate:
    fqn: str                            # analyzer-side fully-qualified name
    name: str
    summary: str
    stereotype: Optional[str] = None
    score: float = 0.0


def _module_rows() -> list[dict]:
    """Fetch MODULE (or FILE fallback) rows from the analyzer DB.

    Returns rows with {fqn, name, summary, stereotype}. `summary` is the
    primary vector target — §B in the doc confirms it's populated in Korean.

    `:MODULE` has to be in the label list, and it is the whole reason a PL/SQL
    analysis mapped nothing. The analyzer labels a module `:MODULE:<sub-label>`
    where the sub-label is the ANTLR node type — but only for Framework
    languages. DBMS carries no sub-label at all (`antlr_json_reader`), so every
    PL/SQL module is a bare `:MODULE` and matched none of the sub-labels this
    query used to list. Step 1 then returned nothing, and the process-level gate
    in `agentic_retriever` skipped the whole process as "no analyzer module
    exceeds threshold" — a sentence that reads like a finding rather than a
    schema mismatch, which is why this stayed invisible.

    The id is read as `coalesce(module_id, id)`: the analyzer's key is
    `module_id`, and `id` is kept for graphs written by an older version.
    """
    sess = analyzer_session()
    if sess is None:
        # **조용히 빈손으로 나가지 않는다.** 여기로 빠지면 아래의 경고도 못 만나고,
        # 화면에는 다른 모든 실패와 똑같은 "매핑 0" 이 된다. 사용자가 구별할 수
        # 없는 세 가지가 한 모양으로 합쳐지는 자리였다 —
        #   ① 프로젝트에 분석 짝이 없다        ← 여기
        #   ② 분석 그래프에 요약이 없다
        #   ③ 문서와 코드의 도메인이 다르다
        SmartLogger.log(
            "WARNING",
            "이 프로젝트에 분석 짝이 연결돼 있지 않다 — 룰 매핑은 전부 0이 된다",
            category="ingestion.hybrid.mapper",
            params={"reason": REASON_NO_ANALYSIS_LINK},
        )
        _set_last_reason(REASON_NO_ANALYSIS_LINK)
        return []
    with sess as s:
        rows = list(s.run(
            """
            MATCH (m)
            WHERE (m:MODULE OR m:FILE OR m:CLASS OR m:INTERFACE OR m:RECORD)
              AND m.summary IS NOT NULL AND m.summary <> ''
            RETURN coalesce(m.module_id, m.id) AS fqn, m.name AS name,
                   m.summary AS summary, m.stereotype AS stereotype
            """,
        ))
        if not rows:
            # New analyzer C graphs have PACKAGE/FILE nodes without summaries,
            # while their FUNCTION nodes carry rich semantic summaries. Treat
            # each routine as a retrieval unit; structured rules use the same
            # producer id as source_module.
            rows = list(s.run(
                """
                MATCH (f)
                WHERE (f:FUNCTION OR f:METHOD)
                  AND f.summary IS NOT NULL AND f.summary <> ''
                RETURN coalesce(f.function_id, f._id, f.id) AS fqn, f.name AS name,
                       f.summary AS summary, f.stereotype AS stereotype
                """,
            ))
    if not rows:
        # Downstream this is not an error. `agentic_retriever` sees a top module
        # score of 0.0, falls under the process gate, and skips the process with
        # "no analyzer module exceeds threshold" — which reads as a finding about
        # the code, not as an empty lookup. Say so here, once, where the reason
        # is still known.
        SmartLogger.log(
            "WARNING",
            "Analyzer DB returned no modules with a summary — every process will "
            "be skipped by the module gate",
            category="ingestion.hybrid.mapper",
            params={
                "database": analyzer_database() or "(default)",
                "reason": REASON_NO_SUMMARIES,
            },
        )
        _set_last_reason(REASON_NO_SUMMARIES)
    else:
        _set_last_reason(None)

    return [
        {
            "fqn": str(r["fqn"] or r["name"]),
            "name": str(r["name"] or r["fqn"]),
            "summary": r["summary"] or "",
            "stereotype": r.get("stereotype"),
        }
        for r in rows
        if r["summary"]
    ]


def _build_query(process: BpmProcess, task: BpmTaskDTO) -> str:
    """Compose the vector query text. Intentionally verbose — `domain_keywords`
    carry the business-domain signal that disambiguates tasks with identical
    names across processes (e.g., "입력값 검증" in 계좌등록 vs 결제승인).
    """
    parts: list[str] = []
    if process.name:
        parts.append(process.name)
    if process.domain_keywords:
        parts.extend(process.domain_keywords)
    if task.name:
        parts.append(task.name)
    if task.description:
        parts.append(task.description)
    return " ".join(parts).strip() or (task.name or "")


# §2.B P1 — PROCESS-level threshold (applied by the orchestrator, not here).
# Below this cosine (on the max task-level score for a process), the analyzer
# code was assumed to NOT implement this process.
#
# **2026-09-29: 이 문턱은 켜 두면 안 된다는 것이 실측으로 드러났다.** 같은 hr-sample
# 을 놓고 양성(HR 문서 × HR 코드)과 음성(HR 문서 × 자동납부 C 코드)을 나란히 쟀더니
# 두 분포가 겹친다 —
#
#   양성 프로세스별 최대 코사인 : 0.591 / 0.472 / 0.439
#   음성 프로세스별 최대 코사인 : 0.428 / 0.319 / 0.354
#
# 0.55 로 자르면 **정답 corpus 의 프로세스 3개 중 2개가 잘린다.** 반대로 두 분포를
# 가르는 값은 아예 없다(양성 0.439 < 음성 0.428 근접). 분포를 정규화해도(z-score)
# 뒤집히기만 한다 — 음성의 월근태마감이 z 2.98 로 양성의 같은 프로세스(z 2.67)보다
# 높다. **모듈 요약 수준의 임베딩에는 "이 코드가 이 문서를 구현하는가" 를 판정할
# 신호가 없다.**
#
# 그 판정은 원래 할 수 있는 것이 한다 — LLM 검증기다. 실제로 검증기는 연차부여
# task 에 잘못 올라온 LeaveRequestService 룰들을 전부 물렸다(= 옳게 판단했다).
# 그래서 게이트는 기본 **끔**이고, 구현이 없는 프로세스는 "검증기가 전부 물렸다"
# (`all_rejected`) 로 드러난다 — 코사인 한 숫자보다 사람이 읽을 수 있는 근거다.
#
# 대가는 LLM 비용이다: 구현이 없는 프로세스도 task 마다 검증기를 한 번 태운다.
# 대량 배치에서 그 비용이 문제가 되면 `HYBRID_PROCESS_GATE=on` 으로 되살린다
# (그때는 위 실측대로 정답이 잘릴 수 있다는 것을 알고 켜는 것이다).
MIN_MODULE_CONFIDENCE = 0.55


def process_gate_enabled() -> bool:
    """프로세스 단위 코사인 게이트를 쓸지. 기본 끔 — 위 주석의 실측 때문이다."""
    return os.getenv("HYBRID_PROCESS_GATE", "off").strip().lower() in {"1", "true", "yes", "on"}

# Per-module inclusion floor — **순위로 자르고, 절대값으로는 거의 자르지 않는다.**
#
# 예전 값은 0.45 였다. 그 숫자는 MODULE 노드에 모듈 단위 요약이 있는 corpus(C·
# PL/SQL)에서 잡은 것인데, Java 처럼 MODULE 요약이 없는 분석 그래프는 `_module_rows`
# 의 폴백을 타고 **METHOD 요약**으로 순위를 매긴다. 텍스트 길이와 추상화 수준이
# 달라지면 코사인 분포가 통째로 내려앉는다 — 그래서 같은 0.45 가 전혀 다른 뜻이 된다.
#
# 2026-09-29 실측(hr-sample, METHOD 171개 · task 28개):
#
#   월 근태 마감 프로세스의 task 8개 : 0.45 를 넘는 모듈이 **하나도 없다**
#                                   (최고 0.439, 정답인 MonthlyClosingService 는 0.37~0.39)
#   → 모듈 0개 → in_scope 0개 → 후보 0개 → task 8개 전부 `no_candidates`
#
# 즉 "어휘가 안 맞아서 못 찾은" 것이 아니라 **문턱이 정답을 잘랐다.** 문턱을 순위로
# 바꾸면(top_k 만 적용) 같은 데이터에서:
#
#   후보 0인 task   8/28 → 0/28
#   정답 룰이 후보에 든 task  14/28 → 28/28   (검증기에 가는 후보 5.7 → 10.9개)
#
# 절대 하한은 **진짜 쓰레기만** 거르는 자리로 남긴다(무관한 corpus 의 중앙값이 대략
# 0.20~0.26 이었다). 이 값으로 정답이 잘리면 안 된다 — 자를 일은 top_k 가 한다.
MIN_MODULE_INCLUSION = 0.10


async def retrieve_top_modules(
    process: BpmProcess,
    task: BpmTaskDTO,
    *,
    top_k: int = 20,
    min_inclusion_score: float = MIN_MODULE_INCLUSION,
    cache: Optional[EmbeddingCache] = None,
    module_rows: Optional[list[dict]] = None,
) -> list[ModuleCandidate]:
    """Run one Step-1 retrieval for (process, task) → top-k module candidates.

    `module_rows` may be supplied by the orchestrator when it has already
    fetched the analyzer MODULE catalog once per session (avoids re-query
    on every Task). Pass `cache` to share embeddings across tasks.

    Two-stage scoring:
      1. rank all modules by query cosine
      2. drop scores below `min_inclusion_score` (long-tail noise floor)
      3. keep the top-k of what's left

    The PROCESS-level gate (MIN_MODULE_CONFIDENCE) is applied separately in
    `run_agentic_retrieval` against the max task score.
    """
    cache = cache or EmbeddingCache()
    rows = module_rows if module_rows is not None else _module_rows()
    if not rows:
        return []

    query = _build_query(process, task)
    if not query:
        return []

    summaries = [r["summary"] for r in rows]
    # Off-loop: embed_many/embed make blocking OpenAI HTTPS calls; running them
    # on the event loop (this is awaited from the async retrieval orchestrator)
    # would freeze the whole server while OpenAI is slow.
    module_vecs = await asyncio.to_thread(cache.embed_many, summaries)
    query_vec = await asyncio.to_thread(cache.embed, query)
    if not query_vec:
        return []

    scored: list[ModuleCandidate] = []
    for row, vec in zip(rows, module_vecs):
        score = cosine(query_vec, vec)
        if score < min_inclusion_score:
            continue
        scored.append(ModuleCandidate(
            fqn=row["fqn"], name=row["name"],
            summary=row["summary"], stereotype=row.get("stereotype"),
            score=score,
        ))

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[: max(1, int(top_k))] if scored else []


def fetch_all_modules() -> list[dict]:
    """Public helper so the orchestrator can fetch MODULE rows once per run."""
    return _module_rows()
