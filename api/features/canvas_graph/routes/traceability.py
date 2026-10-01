"""
Traceability API — DDD 노드의 출처(원본 코드) 역추적 체인

캔버스의 DDD 노드에서 원본 코드까지 전체 경로를 보여줍니다:
  DDD Node → BoundedContext → UserStory → BusinessLogic → Function → Table
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from api.platform.neo4j import analyzer_database, analyzer_session, get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _query(query: str, params: dict | None = None) -> list[dict]:
    """설계 그래프 조회 — UserStory·BC·shadow Rule 이 여기 있다."""
    with get_session() as session:
        return [dict(r) for r in session.run(query, **(params or {}))]


def _analyzer_query(query: str, params: dict | None = None) -> list[dict]:
    """레거시 분석 그래프 조회 — FUNCTION·RULE·EXAMPLE·TABLE 이 여기 있다.

    설계와 분석은 **서로 다른 graph** 다. 라벨 이름이 겹치면서 뜻이 다르기
    때문이다 — 설계의 `Command` 는 Aggregate 의 하위이고 분석의 `Command` 는
    FUNCTION 의 역할이라, 한 graph 에 두면 ES 의 모든 Command 가 FUNCTION 이
    된다. 그래서 출처 체인은 두 그래프를 오가며 재구성해야 한다.
    """
    sess = analyzer_session()
    if sess is None:
        # 분석 짝이 없는 프로젝트다. 문서만 올리고 레거시 분석은 안 한 상태가
        # 정상이므로 오류가 아니라 **빈 결과**다.
        return []
    with sess as session:
        return [dict(r) for r in session.run(query, **(params or {}))]


def _analyzer_has_nested_rules() -> bool:
    """이 분석 그래프가 `PARENT_OF` 를 쓰는가 — dbms 인가.

    한 번만 보고 기억한다. framework 그래프에는 이 관계가 아예 없어서
    되돌림 경로를 시도할 이유가 없다.
    """
    global _NESTED_RULES_CACHE
    if _NESTED_RULES_CACHE is None:
        rows = _analyzer_query("MATCH ()-[r:PARENT_OF]->() RETURN count(r) AS c")
        _NESTED_RULES_CACHE = bool(rows and (rows[0].get("c") or 0) > 0)
    return _NESTED_RULES_CACHE


_NESTED_RULES_CACHE: bool | None = None


def _analyzer_function(fid: str) -> list[dict]:
    """루틴 하나를 읽는다. 라벨을 붙인 쪽을 먼저 본다.

    라벨 없는 `MATCH (f)` 는 `og_node` 를 통째로 읽고 속성을 `og_node_json()`
    으로 행마다 푼다 — 0.11초. 라벨을 붙이면 타입 뷰의 실제 컬럼을 타서
    0.005초다. dbms 의 PROCEDURE/TRIGGER 는 FUNCTION 하위가 아닐 수 있으므로
    빈손이면 원래 형태로 되돌아간다.
    """
    body = """
        RETURN coalesce(f.function_id, f.id) AS id,
               coalesce(f.name, f.signature, f.function_id) AS name,
               f.summary AS summary,
               f.start_line AS start_line, f.end_line AS end_line,
               f.file_path AS file_path,
               f.code_text AS code_text
        LIMIT 1
    """
    rows = _analyzer_query(
        "MATCH (f:FUNCTION) WHERE f.function_id = $fid OR f.id = $fid OR f.name = $fid" + body,
        {"fid": fid},
    )
    if rows:
        return rows
    return _analyzer_query(
        "MATCH (f) WHERE f.function_id = $fid OR f.id = $fid OR f.name = $fid" + body,
        {"fid": fid},
    )


def _analyzer_table_access(fid: str) -> list[dict]:
    """루틴이 읽고 쓰는 표. dbms 는 READS/WRITES 가 자식 구문에 붙는다(spec 044 C5).

    `_analyzer_rules` 와 같은 이유로 가변길이를 기본 경로에서 뺀다.
    """
    body = """
        WHERE coalesce(op.function_id, op.id) = $fid
        OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:COLUMN)
        // 속성 이름 주의 — 이 그래프의 COLUMN 은 `data_type`·`primary_key` 다.
        // `dtype`·`is_primary_key` 로 읽으면 오류 없이 전건 null 이 된다(실측).
        WITH t, type(r) AS access,
             collect(DISTINCT {name: c.name, dtype: c.data_type,
                               pk: coalesce(c.primary_key, false)}) AS columns
        RETURN access, t.name AS table_name, columns
        ORDER BY t.name
    """
    rows = _analyzer_query("MATCH (op)-[r:READS|WRITES]->(t:TABLE)" + body, {"fid": fid})
    if rows or not _analyzer_has_nested_rules():
        return rows
    return _analyzer_query(
        "MATCH (op)-[:PARENT_OF*0..]->(_n)-[r:READS|WRITES]->(t:TABLE)" + body, {"fid": fid})


def _analyzer_rules(fns: list[str]) -> list[dict]:
    """루틴 목록에 걸린 룰을 GWT·쓰기효과와 함께 가져온다.

    빠른 쪽을 먼저 본다. 결과가 없고 그래프가 `PARENT_OF` 를 쓸 때만
    가변길이 경로로 되돌아간다.
    """
    rows = _analyzer_query(_ANALYZER_RULES_DIRECT, {"fns": fns})
    if rows or not _analyzer_has_nested_rules():
        return rows
    return _analyzer_query(_ANALYZER_RULES_NESTED, {"fns": fns})


# 분석 그래프에서 (루틴, 룰) 쌍을 GWT·쓰기효과와 함께 꺼낸다.
#
# 조인 키는 `function_id` 다. analyzer 의 FUNCTION 에는 `name` 이 없고
# (`function_id` 가 "module_id.name" 이고 표시형은 `signature`), 설계 쪽
# shadow Rule 의 `source_function` 이 그 `function_id` 를 담는다. `name` 으로
# 맞추던 종전 코드는 양쪽 다 NULL 이라 전건이 빗나갔다 — 오류 없이 0건이다.
#
# dbms 는 룰 오너가 자식 구문이라 `PARENT_OF*0..` 로 루틴을 복원한다
# (framework 는 rtn=f). spec 044 C4.
#
# **그 가변길이 구간이 출처 조회를 통째로 느리게 만든다.** 같은 패턴 안에서
# 관계 변수(`hr`)를 함께 묶으면 컴파일된 SQL 이 노드 테이블을 CROSS JOIN 하고
# 라벨 없는 `rtn` 의 속성을 `og_node_json()` 으로 행마다 푼다 — 실측 9.7초.
# `hr` 을 안 묶으면 0.08초, 가변길이를 빼면 0.01초다. 한 번 호출이 아니라
# UserStory 마다 도는 자리라 Aggregate 하나가 180초를 넘겼다.
#
# 그래서 두 벌로 나눈다. framework(java/c/python)는 룰 오너가 곧 루틴이므로
# 가변길이가 필요 없다 — 아래 DIRECT 로 끝난다. dbms 만 NESTED 로 되돌아간다.
_ANALYZER_RULES_DIRECT = """
MATCH (rtn)-[hr:HAS_RULE]->(ar:RULE)
  WHERE ar.session_id IS NULL
    AND (rtn:FUNCTION OR rtn:PROCEDURE OR rtn:METHOD OR rtn:TRIGGER)
    AND coalesce(rtn.function_id, rtn.name) IN $fns
// 생산자 EXAMPLE 에 is_boundary 없음 → 대표예시는 첫 EXAMPLE(spec 044 C2/R4).
OPTIONAL MATCH (ar)-[:HAS_EXAMPLE]->(e:EXAMPLE)
WITH rtn, hr, ar, head(collect(DISTINCT e)) AS canonical_e
// Per-Rule write effects: v2 access filters reads; legacy op-only remains additive.
OPTIONAL MATCH (ar)-[:HAS_EXAMPLE]->(wEx:EXAMPLE)-[at:AFFECTS_TABLE]->(wt:TABLE)
WITH rtn, hr, ar, canonical_e,
     collect(DISTINCT {
         table: wt.name, access: at.access, op: at.op, op_source: at.op_source
     }) AS writes
RETURN coalesce(rtn.function_id, rtn.name) AS fn,
       hr.local_rule_id             AS seq,
       ar.statement                 AS title,
       coalesce(hr.coupled_domains[0], '') AS coupled_domain,
       canonical_e.given            AS given,
       canonical_e.when_            AS wh,
       canonical_e.then_            AS th,
       [] AS boundary_ids,
       [w IN writes WHERE w.table IS NOT NULL
         AND (
           w.access IN ['WRITE', 'READ_WRITE']
           OR (w.access IS NULL AND coalesce(w.op, '') <> 'READ')
         )] AS writes
ORDER BY fn, seq
"""


# dbms 전용 되돌림 경로 — 룰 오너가 루틴의 자식 구문일 때만 쓴다.
_ANALYZER_RULES_NESTED = """
MATCH (rtn)-[:PARENT_OF*0..]->(f)-[hr:HAS_RULE]->(ar:RULE)
  WHERE ar.session_id IS NULL
    AND (rtn:FUNCTION OR rtn:PROCEDURE OR rtn:METHOD OR rtn:TRIGGER)
    AND coalesce(rtn.function_id, rtn.name) IN $fns
// 생산자 EXAMPLE 에 is_boundary 없음 → 대표예시는 첫 EXAMPLE(spec 044 C2/R4).
OPTIONAL MATCH (ar)-[:HAS_EXAMPLE]->(e:EXAMPLE)
WITH rtn, hr, ar, head(collect(DISTINCT e)) AS canonical_e
// Per-Rule write effects: v2 access filters reads; legacy op-only remains additive.
OPTIONAL MATCH (ar)-[:HAS_EXAMPLE]->(wEx:EXAMPLE)-[at:AFFECTS_TABLE]->(wt:TABLE)
WITH rtn, hr, ar, canonical_e,
     collect(DISTINCT {
         table: wt.name, access: at.access, op: at.op, op_source: at.op_source
     }) AS writes
RETURN coalesce(rtn.function_id, rtn.name) AS fn,
       hr.local_rule_id             AS seq,
       ar.statement                 AS title,
       coalesce(hr.coupled_domains[0], '') AS coupled_domain,
       canonical_e.given            AS given,
       canonical_e.when_            AS wh,
       canonical_e.then_            AS th,
       [] AS boundary_ids,
       [w IN writes WHERE w.table IS NOT NULL
         AND (
           w.access IN ['WRITE', 'READ_WRITE']
           OR (w.access IS NULL AND coalesce(w.op, '') <> 'READ')
         )] AS writes
ORDER BY fn, seq
"""


# Per-type UserStory traversal. Phase 5 promotes every ES node with an
# IMPLEMENTS edge straight to its UserStory (PRD §5.1), so all types share the
# same shape. Legacy paths (HAS_EVENT, HAS_READMODEL of BC) are still recognized
# for backwards-compat with rfp/figma-source models that pre-date Phase 5.
#
# `src` carries us.id — Phase 5 traceability is UserStory-anchored: Business
# Logic + Function are derived through (US)-[:SOURCED_FROM]->(Rule)<-[:HAS_RULE]-(f),
# not through the legacy `us.sourceUnitId = function_id` shortcut. Old US nodes
# without SOURCED_FROM still resolve via the fallback BL query at line 149.
_US_QUERIES = {
    "Command": """
        MATCH (n:Command {id: $id})-[:IMPLEMENTS]->(us:UserStory)
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               coalesce(us.id, us.sourceUnitId) AS src
        UNION
        MATCH (us:UserStory)-[:IMPLEMENTS]->(n:Command {id: $id})
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               coalesce(us.id, us.sourceUnitId) AS src
    """,
    "Event": """
        MATCH (n:Event {id: $id})-[:IMPLEMENTS]->(us:UserStory)
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               coalesce(us.id, us.sourceUnitId) AS src
        UNION
        MATCH (us:UserStory)-[:HAS_EVENT]->(n:Event {id: $id})
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               coalesce(us.id, us.sourceUnitId) AS src
    """,
    "Aggregate": """
        MATCH (n:Aggregate {id: $id})-[:IMPLEMENTS]->(us:UserStory)
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               coalesce(us.id, us.sourceUnitId) AS src
        UNION
        MATCH (us:UserStory)-[:IMPLEMENTS]->(n:Aggregate {id: $id})
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               coalesce(us.id, us.sourceUnitId) AS src
    """,
    "BoundedContext": """
        MATCH (n:BoundedContext {id: $id})-[:HAS_USERSTORY]->(us:UserStory)
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               coalesce(us.id, us.sourceUnitId) AS src
        UNION
        MATCH (us:UserStory)-[:IMPLEMENTS]->(n:BoundedContext {id: $id})
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               coalesce(us.id, us.sourceUnitId) AS src
    """,
    "ReadModel": """
        // Same fix as Policy — drop the BC fan-out that made every ReadModel
        // in a BC share identical sources. Phase 5 sets bidirectional
        // IMPLEMENTS (US ↔ ReadModel) so direct match is sufficient.
        MATCH (us:UserStory)-[:IMPLEMENTS]->(n:ReadModel {id: $id})
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               coalesce(us.id, us.sourceUnitId) AS src
        UNION
        MATCH (n:ReadModel {id: $id})-[:IMPLEMENTS]->(us:UserStory)
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               coalesce(us.id, us.sourceUnitId) AS src
    """,
    "Policy": """
        // Direct IMPLEMENTS — Phase 5 promote-to-es sets bidirectional IMPLEMENTS
        // (US ↔ Policy), so US's that specifically realize this Policy come
        // back here. The previous fallback `Policy <- HAS_POLICY <- BC <-
        // IMPLEMENTS - US` returned every US in the BC and made all Policies
        // of the same BC share identical sources — removed.
        MATCH (us:UserStory)-[:IMPLEMENTS]->(n:Policy {id: $id})
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               coalesce(us.id, us.sourceUnitId) AS src
        UNION
        MATCH (n:Policy {id: $id})-[:IMPLEMENTS]->(us:UserStory)
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action,
               coalesce(us.id, us.sourceUnitId) AS src
    """,
}


def _routine_entry(routine_id: str, cache: dict[str, dict | None]) -> dict | None:
    """분석 그래프의 루틴 하나 — 이름·요약·위치·코드·테이블.

    키는 `Rule.source_module` 이고 그것이 **루틴 노드의 id** 다(68/68 일치, 실측).
    문자열로 맞추지 않으므로 생산자가 문장 표기를 바꿔도 안 끊긴다.
    """
    if not routine_id:
        return None
    if routine_id in cache:
        return cache[routine_id]
    # **키는 노드의 내부 id(`_id`) 다.** `f.id`·`f.function_id`·`f.name` 으로 맞추던
    # 옛 조회는 이 그래프에서 전건 0이다 — METHOD 에 `id`·`function_id` 속성이 아예
    # 없다(속성은 name/signature/summary/file_path/code_text/…). 이 DB 에서 내부 id 를
    # 가리키는 것은 `_id` 뿐이고, 설계 shadow 의 `source_module` 이 그 값이다.
    rows = _analyzer_query("""
        MATCH (f) WHERE f._id = $rid
          AND (f:FUNCTION OR f:METHOD OR f:PROCEDURE OR f:TRIGGER)
        OPTIONAL MATCH (f)-[acc:READS|WRITES]->(tb:TABLE)
        // 컬럼까지 같이 읽는다. 이게 없으면 화면의 "N cols" 가 영영 안 뜬다.
        // 속성 이름은 `data_type`·`primary_key` 다 — `dtype`·`is_primary_key`
        // 로 읽으면 오류 없이 전건 null 이 된다.
        OPTIONAL MATCH (tb)-[:HAS_COLUMN]->(c:COLUMN)
        WITH f, tb.name AS table_name, type(acc) AS access,
             collect(DISTINCT {name: c.name, type: c.data_type,
                               pk: coalesce(c.primary_key, false)}) AS cols
        RETURN f.name AS name, f.summary AS summary, f.file_path AS file_path,
               f.start_line AS start_line, f.end_line AS end_line,
               f.code_text AS code_text,
               collect({table: table_name, access: access, columns: cols}) AS tables
    """, {"rid": routine_id})
    if not rows:
        cache[routine_id] = None
        return None
    f = rows[0]
    real_id = routine_id
    tables: dict[str, dict] = {}
    for r in (f.get("tables") or []):
        tname = r.get("table")
        if not tname:
            continue
        tb = tables.setdefault(tname, {"name": tname, "columns": [], "access": []})
        if r.get("access"):
            tb["access"].append(r["access"])
        if not tb["columns"]:
            # 같은 표가 READS·WRITES 두 줄로 오면 컬럼은 한 번만 담는다.
            tb["columns"] = [
                {"name": c["name"], "type": c.get("type") or "",
                 "pk": bool(c.get("pk"))}
                for c in (r.get("columns") or []) if c and c.get("name")
            ]
    for tb in tables.values():
        tb["access"] = sorted(set(tb["access"]))
    location = f.get("file_path") or ""
    if f.get("start_line"):
        location += f":{f['start_line']}"
        if f.get("end_line"):
            location += f"-{f['end_line']}"
    entry = {
        "id": real_id,
        "name": f.get("name", ""),
        "summary": f.get("summary", ""),
        "location": location,
        "code": f.get("code_text") or "",
        "tables": list(tables.values()),
    }
    cache[routine_id] = entry
    return entry


def _sources_from_persisted(
    request: Request,
    node_id: str,
    node_info: dict,
    node_type: str,
    bc_info: dict | None,
    rows: list[dict],
) -> dict:
    """영속된 `SOURCED_FROM` 엣지로 출처 응답을 만든다.

    응답 모양은 옛 경로와 같다(`sources[].us / rules / functions`) — 화면을 안
    고쳐도 된다. 룰마다 `evidence_role`(주/보조)과 `via_task_id`(어느 task 를
    거쳤는지)가 더 실린다.

    UserStory 를 못 찾은 엣지는 버리지 않고 `us.id = ""` 묶음에 남긴다 —
    **근거가 있는데 화면에서 사라지는 것이 가장 나쁘다.**
    """
    grouped: dict[str, dict] = {}
    func_cache: dict[str, dict | None] = {}
    for r in rows:
        usid = r.get("us_id") or ""
        g = grouped.setdefault(usid, {
            "us": {"id": usid, "role": r.get("role") or "", "action": r.get("action") or ""},
            "rules": [],
            "functions": [],
            "_fids": [],
        })
        g["rules"].append({
            "seq": "",
            "title": r.get("title") or "",
            "coupled_domain": None,
            "given": r.get("given") or "",
            "when": r.get("wh") or "",
            "then": r.get("th") or "",
            "boundary_example_ids": [],
            "function_id": r.get("fn") or "",
            "writes": [],
            # 여기가 새로 실리는 둘이다.
            "evidence_role": r.get("evidence_role") or "primary",
            "via_task_id": r.get("via_task_id") or "",
        })
        rid = r.get("routine_id") or ""
        if rid and rid not in g["_fids"]:
            g["_fids"].append(rid)

    sources: list[dict] = []
    for g in grouped.values():
        for rid in g.pop("_fids"):
            entry = _routine_entry(rid, func_cache)
            if entry is not None:
                g["functions"].append(entry)
        # 주 근거가 먼저 보이게 한다.
        g["rules"].sort(key=lambda x: (x["evidence_role"] != "primary", x["title"]))
        sources.append(g)
    # UserStory 를 못 찾은 묶음은 마지막에 둔다.
    sources.sort(key=lambda s: (s["us"]["id"] == "", s["us"]["id"]))

    rule_count = sum(len(s["rules"]) for s in sources)
    SmartLogger.log(
        "INFO",
        f"출처(영속 엣지): source {len(sources)} · rule {rule_count} · node {node_id}",
        category="graph.traceability.done",
        params={**http_context(request), "node_id": node_id, "node_type": node_type,
                "source_count": len(sources), "rule_count": rule_count,
                "path": "persisted"},
    )
    return {
        "node": {
            "id": node_id,
            "name": node_info.get("displayName") or node_info.get("name", ""),
            "type": node_type,
        },
        "bc": ({"id": bc_info["id"], "name": bc_info["name"]} if bc_info else None),
        "sources": sources,
    }


@router.get("/traceability/{node_id}")
async def get_traceability(request: Request, node_id: str) -> dict[str, Any]:
    """
    DDD 노드의 전체 역추적 체인을 반환합니다.

    Returns:
        {
            "chain": [
                { "step": "DDD Node", "type": "ReadModel", "name": "...", "id": "..." },
                { "step": "Bounded Context", "name": "...", "id": "..." },
                { "step": "User Story", "id": "US-012", "role": "...", "action": "..." },
                { "step": "Business Logic", "flow": [...], "domain_couplings": [...] },
                { "step": "Function", "name": "...", "summary": "...", "reads": [...], "writes": [...] }
            ]
        }
    """
    SmartLogger.log("INFO", f"Traceability requested for node {node_id}",
                    category="graph.traceability.request",
                    params={**http_context(request), "node_id": node_id})

    # 1) DDD 노드 기본 정보
    node_rows = _query(
        "MATCH (n {id: $id}) RETURN n.id AS id, n.name AS name, n.displayName AS displayName, labels(n) AS labels",
        {"id": node_id},
    )
    if not node_rows:
        raise HTTPException(status_code=404, detail="Node not found")

    node_info = node_rows[0]
    labels = [l for l in (node_info.get("labels") or []) if l not in ("Node",)]
    node_type = labels[0] if labels else "Unknown"

    # 2) 이 노드의 BC (참고용 컨텍스트, source 가 아님)
    bc_rows = _query("""
        MATCH (n {id: $id})
        OPTIONAL MATCH (n)<-[:HAS_READMODEL|HAS_POLICY|HAS_COMMAND|HAS_AGGREGATE]-(bc:BoundedContext)
        OPTIONAL MATCH (bc2:BoundedContext {id: $id})
        OPTIONAL MATCH (us_bc:UserStory)-[:IMPLEMENTS]->(n) WITH n, coalesce(bc, bc2) AS found_bc, us_bc
        OPTIONAL MATCH (us_bc)-[:IMPLEMENTS]->(bc3:BoundedContext)
        WITH n, coalesce(found_bc, bc3) AS bc WHERE bc IS NOT NULL
        RETURN DISTINCT bc.id AS id, bc.name AS name
    """, {"id": node_id})
    bc_info = bc_rows[0] if bc_rows else None

    # 3) Find UserStories — these ARE the source narrative for this ES node.
    # When the node itself IS a UserStory, treat it as its own source US so the
    # 출처 tab can surface the BL/source-rules mapping (hybrid US only).
    if node_type == "UserStory":
        us_rows = _query(
            """
            MATCH (us:UserStory {id: $id})
            RETURN us.id AS id, us.role AS role, us.action AS action,
                   coalesce(us.id, us.sourceUnitId) AS src
            """,
            {"id": node_id},
        )
    else:
        us_query = _US_QUERIES.get(node_type)
        if not us_query:
            us_query = """
                MATCH (us:UserStory)-[]->(n {id: $id})
                RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action, us.sourceUnitId AS src
            """
        us_rows = _query(us_query, {"id": node_id})

    # 4-0) **출처는 이미 그래프에 있다 — 다시 유도하지 않는다.**
    #
    # 2026-09-30 실측: 이 라우트가 화면의 출처 탭을 채우는데, Command 를 물으면
    # `rules: 0 · functions: 0` 이 나왔다. US 만 보이고 근거가 없다.
    #
    # 원인은 유도 과정의 분석 그래프 조인이었다 — `ar.statement` 로 맞추는데
    # **생산자의 `RULE` 에 `statement` 가 없다**(속성은 `condition`·
    # `condition_description`, 효과는 `__ext.effect_descriptions`). 전건 NULL 이라
    # 오류 없이 0건이 된다. `condition_description` 으로 바꿔도 안 맞는다 — 설계
    # shadow 의 `title` 은 `condition_description + ": " + 효과` 로 **합성한 문자열**
    # 이어서 68개 중 0건이 일치한다.
    #
    # 승격이 이제 요소마다 `(x)-[:SOURCED_FROM {evidence_role, via_task_id}]->(Rule)`
    # 을 남긴다(실측 Command 16/16 · Event 63/63 · ReadModel 18/18 · Aggregate 4/4).
    # 그러니 유도할 것이 없다. 그리고 루틴은 **정확한 키**로 잇는다 —
    # `Rule.source_module` 이 분석 그래프 루틴 노드의 id 다(68/68 일치, 실측).
    #
    # 엣지가 없는 노드(rfp/figma US, 이 정책 이전 데이터)는 아래 옛 경로로 간다.
    persisted = _query("""
        MATCH (n {id: $id})-[sf:SOURCED_FROM]->(r:Rule)
        OPTIONAL MATCH (us:UserStory) WHERE us.sourceUnitId = sf.via_task_id
        RETURN coalesce(us.id, '') AS us_id, us.role AS role, us.action AS action,
               r.title AS title, r.given AS given, r.when AS wh, r.then AS th,
               r.source_function AS fn, r.source_module AS routine_id,
               coalesce(sf.evidence_role, 'primary') AS evidence_role,
               sf.via_task_id AS via_task_id
    """, {"id": node_id})

    if persisted:
        return _sources_from_persisted(request, node_id, node_info, node_type,
                                       bc_info, persisted)

    # 4) Per US, build a `source` entry: { us, rules, function }.
    #    Rules + Function are the *real* source-of-truth (verification §3.8) —
    #    DDD Node and BC are NOT included here, they belong to the node's
    #    organizational context, not its source.
    sources: list[dict] = []
    seen_us = set()  # dedup by us.id (one US can appear via multiple paths)
    # 같은 루틴이 여러 UserStory 아래 다시 나온다. 요청 하나 안에서는 한 번만
    # 읽는다 — Aggregate 하나에 출처가 열일곱이면 같은 함수를 열일곱 번 읽었다.
    func_cache: dict[str, dict | None] = {}
    for us in us_rows:
        usid = us.get("id")
        if not usid or usid in seen_us:
            continue
        seen_us.add(usid)

        # 4a) Source rules — match shadow Rule (SOURCED_FROM target) to its
        # analyzer counterpart (FUNCTION-HAS_RULE chain) by (source_function,
        # statement). Then pull canonical/boundary Examples for GWT and
        # AFFECTS_TABLE write ops (INSERT/UPDATE/DELETE) — the latter is the
        # signal Aggregate primary-source emphasis depends on.
        # 설계 그래프의 shadow Rule — 어느 루틴의 어느 룰에서 왔는지만 담는다.
        shadow = _query("""
            MATCH (us:UserStory {id: $usid})-[:SOURCED_FROM]->(sr:Rule)
            RETURN DISTINCT sr.source_function AS fn, sr.title AS title
        """, {"usid": usid})

        # 분석 그래프에서 그 쌍에 해당하는 룰을 GWT·쓰기효과와 함께 가져온다.
        # 루틴 단위로 한 번에 받고 제목은 파이썬에서 맞춘다 — UNWIND 로 쌍을
        # 넘기면 값이 jsonb 가 되어 text 속성과 비교가 어긋난다.
        wanted = {(r.get("fn"), r.get("title")) for r in shadow if r.get("fn")}
        fns = sorted({fn for fn, _ in wanted})
        bl_rows = [
            r for r in (_analyzer_rules(fns) if fns else [])
            if (r.get("fn"), r.get("title")) in wanted
        ]

        # Legacy fallback for rfp/figma US's that don't have SOURCED_FROM
        if not bl_rows:
            src = us.get("src")
            if src:
                bl_rows = _query("""
                    MATCH (f)-[:HAS_BUSINESS_LOGIC]->(bl:BusinessLogic)
                    WHERE f.id = $fid
                    RETURN bl.sequence AS seq, bl.title AS title,
                           bl.coupled_domain AS coupled_domain,
                           bl.given AS given, bl.when AS wh, bl.then AS th,
                           $fid AS function_id, [] AS boundary_ids
                    ORDER BY bl.sequence
                """, {"fid": src})

        rules = []
        function_ids: list[str] = []
        for r in bl_rows or []:
            rules.append({
                "seq": r.get("seq") or "",
                "title": r.get("title") or "",
                "coupled_domain": r.get("coupled_domain"),
                "given": r.get("given") or "",
                "when": r.get("wh") or "",
                "then": r.get("th") or "",
                "boundary_example_ids": r.get("boundary_ids") or [],
                "function_id": r.get("fn") or r.get("function_id") or "",
                # writes: v2 table/access/op/op_source from Example.AFFECTS_TABLE — used
                # by Aggregate primary-source view to surface DB grounding.
                "writes": r.get("writes") or [],
            })
            fid = r.get("fn") or r.get("function_id")
            if fid and fid not in function_ids:
                function_ids.append(fid)

        # 4b) Functions reached through the rules above. Multiple rules may
        # share a function — collect once per function, attach READS/WRITES.
        functions = []
        for fid in function_ids:
            if fid in func_cache:
                if func_cache[fid] is not None:
                    functions.append(func_cache[fid])
                continue
            func_rows = _analyzer_function(fid)
            if not func_rows:
                func_cache[fid] = None
                continue
            f = func_rows[0]
            real_fid = f["id"] or fid
            rw_rows = _analyzer_table_access(real_fid)
            tables: dict[str, dict] = {}
            for r in rw_rows:
                tname = r["table_name"]
                if tname not in tables:
                    cols = [c for c in (r.get("columns") or []) if c.get("name")]
                    tables[tname] = {
                        "name": tname,
                        "columns": [{"name": c["name"], "type": c.get("dtype", ""),
                                     "pk": bool(c.get("pk"))} for c in cols],
                        "access": [],
                    }
                tables[tname]["access"].append(r["access"])
            for t in tables.values():
                t["access"] = sorted(set(t["access"]))

            file_name = f.get("file_path") or ""
            location = file_name
            if f.get("start_line"):
                location += f":{f['start_line']}"
                if f.get("end_line"):
                    location += f"-{f['end_line']}"

            entry = {
                "id": real_fid,
                "name": f.get("name", ""),
                "summary": f.get("summary", ""),
                "location": location,
                "code": f.get("code_text") or "",
                "tables": list(tables.values()),
            }
            func_cache[fid] = entry
            functions.append(entry)

        sources.append({
            "us": {
                "id": usid,
                "role": us.get("role", ""),
                "action": us.get("action", ""),
            },
            "rules": rules,
            "functions": functions,
        })

    result = {
        "node": {
            "id": node_id,
            "name": node_info.get("displayName") or node_info.get("name", ""),
            "type": node_type,
        },
        "bc": ({"id": bc_info["id"], "name": bc_info["name"]} if bc_info else None),
        "sources": sources,
    }

    SmartLogger.log("INFO", f"Traceability returned: {len(sources)} sources",
                    category="graph.traceability.done",
                    params={"node_id": node_id, "source_count": len(sources)})

    return result


@router.get("/traceability/node/{node_id}/source-rules")
async def get_node_source_rules(request: Request, node_id: str) -> dict[str, Any]:
    """어떤 ES 요소든 그 **코드 출처**를 돌려준다 — 라벨을 묻지 않는다.

    UserStory 전용이던 것을 일반화했다. 2026-09-30 실측에서 Command·Aggregate·
    Event·Policy·ReadModel 은 노드에 출처가 없었고, 그것을 돌려주는 길도 없었다.
    승격이 이제 그 요소들에도 `(x)-[:SOURCED_FROM {evidence_role, via_task_id}]->(Rule)`
    을 남기므로, 조회는 라벨과 무관하게 같은 한 줄이면 된다.

    `/traceability/userstory/{id}/source-rules` 는 같은 것을 부른다 — 프런트가
    쓰고 있어 남겨 둔다.
    """
    return _source_rules(request, node_id)


@router.get("/traceability/userstory/{us_id}/source-rules")
async def get_userstory_source_rules(request: Request, us_id: str) -> dict[str, Any]:
    """`/traceability/node/{id}/source-rules` 의 옛 이름. 동작은 같다."""
    return _source_rules(request, us_id)


def _source_rules(request: Request, node_id: str) -> dict[str, Any]:
    """Return analyzer Rules a node was sourced from.

    Hybrid-mode US nodes carry `(us)-[:SOURCED_FROM]->(Rule)` edges installed
    by Phase 5 promote-to-es (BpmTask → REALIZED_BY → shadow Rule, fanned out
    to every US sharing sourceUnitId). rfp/figma US nodes have no SOURCED_FROM
    so the response `rules` list is simply empty — caller decides whether to
    render the section.
    """
    # `evidence_role` 을 같이 돌려준다 — `primary`(주 근거) 또는 `supporting`(보조 근거).
    #
    # 굵은 레거시 룰 하나가 여러 task 를 정당하게 뒷받침한다(`applyLeave` 한
    # 메서드가 검증·저장을 다 한다). 중재는 집을 하나만 고르지만 진 쪽을 지우지
    # 않고 `supporting` 으로 남긴다(2026-09-30 정책 — 지우던 때에는 task 29개 중
    # 12개가 근거를 통째로 잃었다). 화면이 그 구분을 보여 줘야 "왜 이 룰이 두
    # 군데에 있나" 를 사람이 읽을 수 있다.
    #
    # 이 정책 전에 만든 엣지에는 `evidence_role` 이 없다 — `primary` 로 본다.
    rows = _query("""
        MATCH (n {id: $usid})-[sf:SOURCED_FROM]->(r:Rule)
        // 오퍼레이션 단위(루틴) 기준 조인 — dbms 룰 오너=자식구문 → PARENT_OF*0.. 로 루틴 복원.
        OPTIONAL MATCH (rtn)-[:PARENT_OF*0..]->(f)-[hr:HAS_RULE]->(ar:RULE)
          WHERE ar.session_id IS NULL
            AND (rtn:FUNCTION OR rtn:PROCEDURE OR rtn:METHOD OR rtn:TRIGGER)
            AND rtn.name = r.source_function
            AND ar.statement = r.title
        RETURN r.id AS rule_id,
               r.title AS statement,
               r.source_function AS source_function,
               coalesce(hr.local_rule_id, '') AS local_id,
               coalesce(sf.evidence_role, 'primary') AS evidence_role,
               sf.via_task_id AS via_task_id
        ORDER BY evidence_role, local_id, statement
    """, {"usid": node_id})

    SmartLogger.log("INFO", f"source-rules: {len(rows)} for {node_id}",
                    category="graph.traceability.us_source_rules",
                    params={**http_context(request), "node_id": node_id, "count": len(rows)})

    # `us_id` 는 옛 이름이다 — 프런트가 읽고 있어 같이 싣는다.
    return {"node_id": node_id, "us_id": node_id, "rules": rows}
