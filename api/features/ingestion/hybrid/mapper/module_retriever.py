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
    # **둘을 합친다 — 둘 중 하나가 아니다.**
    #
    # 예전에는 컨테이너 조회가 비었을 때만 루틴으로 폴백했다. 그러면 컨테이너
    # **하나**에 요약이 붙는 순간 루틴 코퍼스 171개가 통째로 사라진다. 그 전환은
    # 화면에 아무 흔적도 남기지 않으므로, 애널라이저가 요약을 한 단계 위로 옮기는
    # 날 매핑이 조용히 0이 된다. 실제로 robo-architect `main` 의 Step 1
    # (`container_retriever`)은 폴백이 아예 없어서 이 DB 의 그래프에서는 0건이다.
    #
    # 합쳐 두면 어느 쪽에 요약이 붙어 있든 같은 순위표에 들어온다. 범위 판정은
    # `agentic_retriever` 가 PARENT_OF 로 위아래를 이어 해결한다 — 그래서 단계가
    # 섞여도 룰이 범위 밖으로 떨어지지 않는다.
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
        # 루틴 단위 요약. 2026-08-20 이후 분석 그래프에는 컨테이너(CLASS/FILE/PACKAGE)
        # 요약이 **언어와 무관하게** 없다 — C 그래프도 FUNCTION 에만 있다(09-29 실측).
        rows += list(s.run(
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
    """검색 질의 = 프로세스 이름 + task 이름(+설명). **`domain_keywords` 는 넣지 않는다.**

    예전 주석은 키워드가 "같은 이름의 task 를 프로세스 간에 구별해 준다" 고 적었다.
    구별은 맞지만 **그 일은 `process.name` 이 이미 한다.** 키워드 8개를 더하면 task
    이름이 질의의 10% 남짓으로 눌려, **같은 프로세스 안에서 task 를 바꿔도 순위가
    거의 안 바뀐다** — 실측에서 휴가신청 13개 task 중 12개가 같은 메서드를 1위로
    뽑았다(`rejectLeave`). task 단위 검색이 사실상 프로세스 단위가 된다.

    실측 (hr-sample · METHOD 171 · task 28 · 검증기가 수락한 매핑 19건이 정답):

        질의                     recall@5   @10    @20   정답파일 hit@5
        proc + kw + task (옛것)    12/19  15/19  19/19       21/28
        proc + task (지금)         13/19  16/19  19/19       28/28
        task 만                   11/19  12/19  16/19       28/28   ← 나빠진다

    프로세스 이름은 빼면 안 된다(맨 아래 줄). 키워드만 뺀다.

    검색 **문서** 쪽은 손대지 않았다. 여섯 가지를 재 봤고 전부 이득이 없거나 나빴다.
    **다시 시도하려면 먼저 이 측정을 반박해야 한다.**

        시도                        recall@5   @10    @20   비고
        summary (현행)                13/19  16/19  19/19
        + 메서드이름·클래스이름           13/19  18/19  19/19   노이즈 범위
        + 하위함수 요약 (CALLS)         13/19  17/19  19/19   제자리
        + 테이블 물리명                 13/19  18/19  19/19   제자리 (영문 약어)
        + 테이블 논리명·요약(한국어)       10/19  17/19  19/19   **나빠짐**
        + 원문 code_text              13/19  15/19  19/19   **나빠짐**
        컨테이너 롤업 2단 (top-3 클래스)   12/19  14/19  14/19   **정답을 잃음**

    이유가 있는 것들 —
      · 테이블 사전은 커버리지가 33/171 뿐이다(READS/WRITES 가 붙는 DAO 계열만).
        그래서 DAO 가 업무 어휘를 얻어 **정답인 서비스 계층을 밀어낸다** — 불공정한
        가산점이 된다. 호출 1단계로 전파해도 35/171 로 거의 안 늘었다.
      · 컨테이너 롤업(멤버 메서드 요약을 이어 붙여 CLASS 문서를 만드는 것)은
        `@20` 이 14 에서 막힌다 — **범위 자체가 정답을 제외**한다. 클래스 28개로
        접으면 변별에 쓰던 세부가 사라진다. 평면과 같아지는 지점(top-8, 41개)에서는
        더 이상 좁히는 의미가 없다.
      · 클래스 헤더 주석(Javadoc)은 그래프에 없고(발행 계약에 `notes` 가 없다),
        **작성자 의존**이라 기댈 수 없다 — 실제 레거시 C 에는 있지만 변경이력·작성자
        노이즈가 섞이고, 없는 코드가 대부분일 것이다(사용자 판단).

    **그리고 Step 1 은 이제 병목이 아니다.** `recall@20 = 19/19` — 정답 메서드가 이미
    전부 상위 20에 들어온다. 매핑이 적은 원인은 그 뒤에 있다(교차 프로세스 중재가
    수락 72 중 41개를 지운다 — `explore_service.post_explore_arbitration` 참고).
    """
    parts: list[str] = []
    if process.name:
        parts.append(process.name)
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
# 0.55 로 자르면 **정답 corpus 의 프로세스 3개 중 2개가 잘린다**(루틴 요약 기준).
# 반대로 두 분포를
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
# 예전 값은 0.45 였다. 그 숫자는 **컨테이너(MODULE/CLASS/FILE) 요약이 있던 시절**의
# 분포에서 잡은 것이다. 애널라이저가 그 요약을 없앴다 —
#
#   2026-08-20  f91f90da  "remove aggregate summary LLMs"
#               module_summary.yaml(framework·dbms) · module_summary_contract.md
#               · module_summary_response_schema.py 삭제 → 생성 주체가 사라짐
#   2026-09-01  039ba8c8  `Module.summary` 필드까지 제거
#
# 그래서 그 뒤에 만든 분석 그래프에는 CLASS·FILE 에 요약이 **없다**. 언어와 무관하다
# — C 그래프도 FILE 에 없고 FUNCTION 에만 있다(2026-09-29 실측). 그래서
# `_module_rows` 는 폴백을 타고 **루틴(METHOD/FUNCTION) 요약**으로 순위를 매긴다
# (폴백 자체는 2026-09-22 `627dc7f` 에 붙었다).
#
# 즉 Step 1 의 입력이 "클래스가 무슨 일을 한다" 에서 "이 메서드가 무슨 일을 한다" 로
# 바뀌었는데 **문턱만 옛 분포에 남았다.** 글의 길이와 추상화 수준이 달라지면 코사인
# 분포가 통째로 내려앉는다 — 같은 0.45 가 전혀 다른 뜻이 된다.
#
# 발행 계약(`product_graph.NODE_PROPERTY_KEYS`)은 지금도 `source` 노드에 `summary` 를
# 허용한다. 막힌 것이 아니라 **채우는 쪽이 없어진 것**이다. 그리고 그것은
# **의도된 설계다** — 애널라이저 담당자 확인: *"summary 로는 열화되는 게 많아서 원문
# 코드 + 호출된 하위함수 summary 정도를 활용하고 있다."* 그러니 되살리는 것이 아니라
# **지금 계약에 맞추는 것**이 맞다. 계약이 주는 것은 루틴 단위 요약뿐이다.
#
# **그래서 이 값은 문턱이 아니다 — 0.0 이고, 자르는 일은 `top_k` 가 한다.**
# 0.45 를 0.10 으로 "낮추는" 것은 고치는 척하는 것이었다. 실측(hr-sample):
#
#   top_k=20 컷이 실제로 자르는 지점   0.306 ~ 0.393
#   0.10 에 걸리는 모듈               171개 중 2~6개 — **전부 이미 20위 밖**
#
# 즉 0.10 은 한 번도 작동하지 않았다. 코퍼스가 바뀌면 절대값의 뜻이 바뀐다는 것이
# 이 사건의 교훈이고(위 내력), 그렇다면 절대값을 **두지 않는 것**이 답이다.
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
MIN_MODULE_INCLUSION = 0.0


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

    순위로만 자른다:
      1. 질의 코사인으로 전체 순위를 낸다
      2. `min_inclusion_score` 는 기본 0.0 — **아무것도 자르지 않는다**
         (코퍼스마다 뜻이 달라지는 절대값을 두지 않기로 했다. 위 상수 주석 참고)
      3. 상위 `top_k` 만 남긴다  ← 여기가 실제 컷이다

    **Step 1 의 역할은 "고르는 것" 이 아니라 "잃지 않는 것" 이다.** 판정은 Step 3 의
    LLM 검증기가 한다. 실측에서 상위 20개는 정답을 19/19 담았지만, 그것은 메서드
    171개짜리 코퍼스다 — 수만 개 규모에서 top-k 가 정답을 담는다는 근거는 **없다.**

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


def fetch_containment() -> dict[str, str]:
    """자식 id → 부모 id. Step 1 이 고른 단계와 룰이 가리키는 단계를 잇는다.

    **이것이 없으면 조용히 0이 된다.** Step 1 은 요약이 붙은 노드를 고르는데
    (CLASS 일 수도, METHOD 일 수도 있다) 룰의 `source_module` 은 **언제나 루틴의
    id** 다. 컨테이너 단계로 고른 날에는 두 집합이 한 번도 겹치지 않는다 —
    범위에 드는 룰이 0개이고, 화면에는 다른 모든 실패와 똑같은 "매핑 0" 이 된다.
    검증 LLM 은 불리지도 않으므로 로그에도 판단 근거가 안 남는다.

    반환은 한 단계짜리 부모 맵이다. 호출자가 위로 걸어 올라간다(PACKAGE →
    CLASS → METHOD 처럼 두 단계 이상 떨어져 있어도 닿는다).
    """
    sess = analyzer_session()
    if sess is None:
        return {}
    parent: dict[str, str] = {}
    with sess as s:
        # 루틴 → 그것을 담은 컨테이너
        for r in s.run(
            """
            MATCH (c)-[:PARENT_OF]->(f)
            WHERE (f:FUNCTION OR f:METHOD OR f:PROCEDURE OR f:TRIGGER)
            RETURN coalesce(f.function_id, f._id, f.id) AS child,
                   coalesce(c.module_id, c.id) AS parent
            """,
        ):
            child, up = r["child"], r["parent"]
            if child and up:
                parent[str(child)] = str(up)
        # 컨테이너 → 그 위 컨테이너 (PACKAGE 가 CLASS 를 담는 경우)
        for r in s.run(
            """
            MATCH (c)-[:PARENT_OF]->(m)
            WHERE (m:MODULE OR m:FILE OR m:CLASS OR m:INTERFACE OR m:RECORD)
            RETURN coalesce(m.module_id, m.id) AS child,
                   coalesce(c.module_id, c.id) AS parent
            """,
        ):
            child, up = r["child"], r["parent"]
            if child and up and str(child) != str(up):
                parent.setdefault(str(child), str(up))
    return parent


def ancestors_of(node_id: str, parent: dict[str, str], *, limit: int = 16) -> list[str]:
    """`node_id` 자신 + 조상들. 순환이 있어도 멈춘다(그래프는 신뢰 대상이 아니다)."""
    out: list[str] = []
    seen: set[str] = set()
    cur = (node_id or "").strip()
    while cur and cur not in seen and len(out) < limit:
        seen.add(cur)
        out.append(cur)
        cur = (parent.get(cur) or "").strip()
    return out
