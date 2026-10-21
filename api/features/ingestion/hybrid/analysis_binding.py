"""Bind a BPM session to the exact project analysis it was built from.

Projects already own separate design/analyzer graphs (``prj_x`` / ``prj_x_a``).
The missing contract was temporal: a BpmSession did not record which analyzer
graph contents supplied its Rules.  Re-pointing the project or re-running code
analysis could therefore leave an old BPM eligible for exploration/promotion.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from api.platform.neo4j import analyzer_database, analyzer_session, design_database, get_session


# ⚠ 이 질의는 **두 번 죽었다** (2026-10-21 · done16 §305).
#
# ① `coalesce(n._id, ..., '')` — `_id` 는 그래프의 **내부 숫자 id**(bigint)다.
#    문자열과 섞으면 `invalid input syntax for type bigint: ""` 로 죽는다.
#    → **toString()** 으로 감싼다. catalog 에서 같은 부류를 겪었다(done15 §297).
# ② `a_key + '|' + type(rel) + '|' + b_key` — 문자열 이어붙이기가
#    `operator does not exist: text + unknown` 으로 죽는다.
#    → **이어붙이지 않는다.** 조각을 `item_values` 에 나란히 넣고 정규화는
#      파이썬에서 한다(`item_values` 는 정렬하지 않으므로 순서가 살아 있다).
#
# ⚠ 이 질의가 죽으면 **결합이 안 적히고**, 탐색은 `ANALYSIS_BINDING_MISSING` 으로
#   막히며, 화면에는 **아무 말도 안 나온다.** 고칠 때는 반드시 실제 분석 graph 에
#   돌려 본다 — 이 질의는 단위 테스트로 안 잡혔다.
_FINGERPRINT_QUERY = """
MATCH (n)
WHERE n:FUNCTION OR n:PROCEDURE OR n:METHOD OR n:TRIGGER
   OR n:RULE OR n:EXAMPLE OR n:TABLE
RETURN 'node' AS kind,
       coalesce(toString(n._id), n.function_id, n.example_id, toString(n.id), n.name, '') AS item_key,
       labels(n) AS item_labels,
       [coalesce(n.name, ''), coalesce(n.summary, ''),
        coalesce(n.statement, ''), coalesce(n.condition_description, ''),
        coalesce(n.condition, ''), coalesce(n.given, ''),
        coalesce(n.when_, ''), coalesce(n.then_, ''),
        coalesce(n.file_path, ''), toString(coalesce(n.start_line, 0)),
        toString(coalesce(n.end_line, 0))] AS item_values
UNION ALL
MATCH (a)-[rel:HAS_RULE|HAS_EXAMPLE|PARENT_OF|READS|WRITES|AFFECTS_TABLE|CALLS|HAS_FUNCTION|BELONGS_TO_PACKAGE]->(b)
WHERE (a:FUNCTION OR a:PROCEDURE OR a:METHOD OR a:TRIGGER OR a:RULE OR a:EXAMPLE)
  AND (b:FUNCTION OR b:PROCEDURE OR b:METHOD OR b:TRIGGER OR b:RULE OR b:EXAMPLE OR b:TABLE)
RETURN 'relationship' AS kind,
       type(rel) AS item_key,
       [] AS item_labels,
       [coalesce(toString(a._id), a.function_id, a.example_id, toString(a.id), a.name, ''),
        coalesce(toString(b._id), b.function_id, b.example_id, toString(b.id), b.name, ''),
        coalesce(rel.access, ''), coalesce(rel.op, ''),
        coalesce(rel.op_source, '')] AS item_values
ORDER BY kind, item_key
"""


@dataclass(frozen=True)
class AnalysisBindingError(RuntimeError):
    code: str
    detail: str

    def __str__(self) -> str:
        return self.detail


def current_analysis_fingerprint() -> str:
    """Stable content fingerprint of the current project's analyzer graph.

    A new run with identical effective graph may keep the same fingerprint;
    that is intentional.  The guard protects semantic consistency, not a run
    timestamp.  Routine identity/summary/table access are exactly the inputs
    consumed by Rule matching and ES provenance.
    """
    session = analyzer_session()
    if session is None:
        raise AnalysisBindingError(
            "ANALYSIS_NOT_PAIRED",
            "이 프로젝트에 연결된 코드 분석 그래프가 없습니다. 프로젝트 분석을 먼저 실행하세요.",
        )
    with session as s:
        rows = [dict(rec) for rec in s.run(_FINGERPRINT_QUERY)]
    if not rows:
        raise AnalysisBindingError(
            "ANALYSIS_GRAPH_EMPTY",
            "이 프로젝트의 코드 분석 그래프가 비어 있습니다. 코드 분석을 완료한 뒤 BPM을 다시 생성하세요.",
        )
    canonical = [{
        "kind": row.get("kind") or "",
        "key": row.get("item_key") or "",
        "labels": sorted(row.get("item_labels") or []),
        "values": list(row.get("item_values") or []),
    } for row in rows]
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def bind_session_to_current_analysis(session_id: str) -> dict[str, str]:
    """Record the project/analysis pair after Rules were extracted."""
    design = design_database() or ""
    analyzer = analyzer_database() or ""
    fingerprint = current_analysis_fingerprint()
    with get_session() as s:
        rec = s.run(
            "MATCH (h:BpmSession {id: $sid, session_id: $sid}) "
            "SET h.design_graph = $design, h.analyzer_graph = $analyzer, "
            "    h.analysis_fingerprint = $fingerprint, h.analysis_bound_at = datetime() "
            "RETURN h.id AS id",
            sid=session_id,
            design=design,
            analyzer=analyzer,
            fingerprint=fingerprint,
        ).single()
    if not rec:
        raise AnalysisBindingError(
            "BPM_SESSION_NOT_FOUND",
            "BPM 세션을 찾지 못해 코드 분석과 결합할 수 없습니다. BPM을 다시 생성하세요.",
        )
    return {"design_graph": design, "analyzer_graph": analyzer, "fingerprint": fingerprint}


def assert_session_analysis_binding(session_id: str) -> dict[str, str]:
    """Fail closed unless BPM, selected project and current analysis agree."""
    with get_session() as s:
        rec = s.run(
            "MATCH (h:BpmSession {id: $sid, session_id: $sid}) "
            "RETURN h.design_graph AS design_graph, h.analyzer_graph AS analyzer_graph, "
            "       h.analysis_fingerprint AS analysis_fingerprint",
            sid=session_id,
        ).single()
    if not rec:
        raise AnalysisBindingError(
            "BPM_SESSION_NOT_FOUND",
            "이 프로젝트에서 BPM 세션을 찾지 못했습니다.",
        )
    bound_design = rec.get("design_graph")
    bound_analyzer = rec.get("analyzer_graph")
    bound_fingerprint = rec.get("analysis_fingerprint")
    if not bound_design or not bound_analyzer or not bound_fingerprint:
        raise AnalysisBindingError(
            "ANALYSIS_BINDING_MISSING",
            "이 BPM은 분석 결합 정보가 없는 이전 결과입니다. 현재 프로젝트에서 코드 분석 후 BPM을 다시 생성하세요.",
        )

    current_design = design_database() or ""
    current_analyzer = analyzer_database() or ""
    if bound_design != current_design or bound_analyzer != current_analyzer:
        raise AnalysisBindingError(
            "ANALYSIS_PROJECT_MISMATCH",
            "BPM을 만든 프로젝트/분석 그래프와 현재 선택이 다릅니다. 올바른 프로젝트를 선택하거나 BPM을 다시 생성하세요.",
        )
    current_fingerprint = current_analysis_fingerprint()
    if bound_fingerprint != current_fingerprint:
        raise AnalysisBindingError(
            "ANALYSIS_CONTENT_CHANGED",
            "BPM 생성 뒤 코드 분석 결과가 변경되었습니다. 프로세스 탐색과 ES 승격 전에 BPM을 다시 생성하세요.",
        )
    return {
        "design_graph": current_design,
        "analyzer_graph": current_analyzer,
        "fingerprint": current_fingerprint,
    }
