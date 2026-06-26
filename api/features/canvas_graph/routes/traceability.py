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

from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


def _query(query: str, params: dict | None = None) -> list[dict]:
    """Neo4j 조회."""
    with get_session() as session:
        return [dict(r) for r in session.run(query, **(params or {}))]


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

    # 4) Per US, build a `source` entry: { us, rules, function }.
    #    Rules + Function are the *real* source-of-truth (verification §3.8) —
    #    DDD Node and BC are NOT included here, they belong to the node's
    #    organizational context, not its source.
    sources: list[dict] = []
    seen_us = set()  # dedup by us.id (one US can appear via multiple paths)
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
        bl_rows = _query("""
            MATCH (us:UserStory {id: $usid})-[:SOURCED_FROM]->(sr:Rule)
            // 오퍼레이션 단위(루틴) 기준 조인 — dbms 는 룰 오너가 자식 구문이라
            // PARENT_OF*0.. 로 루틴 rtn 복원(framework 는 rtn=f). spec 044 C4.
            MATCH (rtn)-[:PARENT_OF*0..]->(f)-[hr:HAS_RULE]->(ar:RULE)
              WHERE ar.session_id IS NULL
                AND (rtn:FUNCTION OR rtn:PROCEDURE OR rtn:METHOD OR rtn:TRIGGER)
                AND rtn.name = sr.source_function
                AND ar.statement = sr.title
            // 생산자 EXAMPLE 에 is_boundary 없음 → 대표예시는 첫 EXAMPLE(spec 044 C2/R4).
            OPTIONAL MATCH (ar)-[:HAS_EXAMPLE]->(e:EXAMPLE)
            WITH sr, ar, hr, rtn,
                 head(collect(DISTINCT e)) AS canonical_e
            OPTIONAL MATCH (ar)-[:HAS_EXAMPLE]->(allEx:EXAMPLE)
            WITH sr, ar, hr, rtn, canonical_e,
                 collect(DISTINCT allEx) AS examples
            // Per-Rule write ops: collect AFFECTS_TABLE edges from all Examples.
            OPTIONAL MATCH (ar)-[:HAS_EXAMPLE]->(wEx:EXAMPLE)-[at:AFFECTS_TABLE]->(wt:TABLE)
            WITH sr, ar, hr, rtn, canonical_e, examples,
                 collect(DISTINCT { table: wt.name, op: at.op }) AS writes
            RETURN hr.local_rule_id AS seq,
                   ar.statement AS title,
                   coalesce(hr.coupled_domains[0], '') AS coupled_domain,
                   canonical_e.given AS given,
                   canonical_e.when_ AS wh,
                   canonical_e.then_ AS th,
                   rtn.id AS function_id,
                   [] AS boundary_ids,
                   [w IN writes WHERE w.table IS NOT NULL AND w.op IS NOT NULL] AS writes
            ORDER BY rtn.name, hr.local_rule_id
        """, {"usid": usid})

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
                "function_id": r.get("function_id") or "",
                # writes: list of {table, op} from Example.AFFECTS_TABLE — used
                # by Aggregate primary-source view to surface DB grounding.
                "writes": r.get("writes") or [],
            })
            fid = r.get("function_id")
            if fid and fid not in function_ids:
                function_ids.append(fid)

        # 4b) Functions reached through the rules above. Multiple rules may
        # share a function — collect once per function, attach READS/WRITES.
        functions = []
        for fid in function_ids:
            func_rows = _query("""
                MATCH (f)
                WHERE f.id = $fid OR f.name = $fid
                RETURN f.id AS id, f.name AS name, f.summary AS summary,
                       f.start_line AS start_line, f.end_line AS end_line,
                       f.file_path AS file_path,
                       f.code_text AS code_text
                LIMIT 1
            """, {"fid": fid})
            if not func_rows:
                continue
            f = func_rows[0]
            real_fid = f["id"] or fid
            # dbms: READS/WRITES 는 자식 구문에 붙으므로 PARENT_OF*0.. 하향수집(spec 044 C5).
            rw_rows = _query("""
                MATCH (op {id: $fid})-[:PARENT_OF*0..]->(_n)-[r:READS|WRITES]->(t:TABLE)
                OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:COLUMN)
                WITH t, type(r) AS access,
                     collect(DISTINCT {name: c.name, dtype: c.dtype, pk: c.is_primary_key}) AS columns
                RETURN access, t.name AS table_name, columns
                ORDER BY t.name
            """, {"fid": real_fid})
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

            functions.append({
                "id": real_fid,
                "name": f.get("name", ""),
                "summary": f.get("summary", ""),
                "location": location,
                "code": f.get("code_text") or "",
                "tables": list(tables.values()),
            })

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


@router.get("/traceability/userstory/{us_id}/source-rules")
async def get_userstory_source_rules(request: Request, us_id: str) -> dict[str, Any]:
    """Return analyzer Rules a UserStory was sourced from.

    Hybrid-mode US nodes carry `(us)-[:SOURCED_FROM]->(Rule)` edges installed
    by Phase 5 promote-to-es (BpmTask → REALIZED_BY → shadow Rule, fanned out
    to every US sharing sourceUnitId). rfp/figma US nodes have no SOURCED_FROM
    so the response `rules` list is simply empty — caller decides whether to
    render the section.
    """
    rows = _query("""
        MATCH (us:UserStory {id: $usid})-[:SOURCED_FROM]->(r:Rule)
        // 오퍼레이션 단위(루틴) 기준 조인 — dbms 룰 오너=자식구문 → PARENT_OF*0.. 로 루틴 복원.
        OPTIONAL MATCH (rtn)-[:PARENT_OF*0..]->(f)-[hr:HAS_RULE]->(ar:RULE)
          WHERE ar.session_id IS NULL
            AND (rtn:FUNCTION OR rtn:PROCEDURE OR rtn:METHOD OR rtn:TRIGGER)
            AND rtn.name = r.source_function
            AND ar.statement = r.title
        RETURN r.id AS rule_id,
               r.title AS statement,
               r.source_function AS source_function,
               coalesce(hr.local_rule_id, '') AS local_id
        ORDER BY local_id, statement
    """, {"usid": us_id})

    SmartLogger.log("INFO", f"US source-rules: {len(rows)} for {us_id}",
                    category="graph.traceability.us_source_rules",
                    params={**http_context(request), "us_id": us_id, "count": len(rows)})

    return {"us_id": us_id, "rules": rows}
