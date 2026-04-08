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


# 노드 타입별 US 탐색 쿼리 (정확한 관계 경로)
_US_QUERIES = {
    "Command": """
        MATCH (us:UserStory)-[:IMPLEMENTS]->(n:Command {id: $id})
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action, us.sourceUnitId AS src
    """,
    "Event": """
        MATCH (us:UserStory)-[:HAS_EVENT]->(n:Event {id: $id})
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action, us.sourceUnitId AS src
    """,
    "Aggregate": """
        MATCH (us:UserStory)-[:IMPLEMENTS]->(n:Aggregate {id: $id})
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action, us.sourceUnitId AS src
    """,
    "BoundedContext": """
        MATCH (us:UserStory)-[:IMPLEMENTS]->(n:BoundedContext {id: $id})
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action, us.sourceUnitId AS src
    """,
    "ReadModel": """
        MATCH (n:ReadModel {id: $id})<-[:HAS_READMODEL]-(bc:BoundedContext)<-[:IMPLEMENTS]-(us:UserStory)
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action, us.sourceUnitId AS src
    """,
    "Policy": """
        MATCH (n:Policy {id: $id})<-[:HAS_POLICY]-(bc:BoundedContext)<-[:IMPLEMENTS]-(us:UserStory)
        RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action, us.sourceUnitId AS src
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

    chains: list[list[dict]] = []

    # 2) 이 노드의 BC 찾기
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

    # 3) US 찾기 (타입별 정확한 경로)
    us_query = _US_QUERIES.get(node_type)
    if not us_query:
        # 알 수 없는 타입이면 모든 방향으로 시도
        us_query = """
            MATCH (us:UserStory)-[]->(n {id: $id})
            RETURN DISTINCT us.id AS id, us.role AS role, us.action AS action, us.sourceUnitId AS src
        """
    us_rows = _query(us_query, {"id": node_id})

    # 4) US별로 체인 구성
    for us in us_rows:
        src = us.get("src")
        if not src:
            continue

        chain: list[dict] = []

        # Step 1: DDD Node
        chain.append({
            "step": "DDD Node",
            "type": node_type,
            "name": node_info.get("displayName") or node_info.get("name", ""),
            "id": node_id,
        })

        # Step 2: Bounded Context
        if bc_info:
            chain.append({
                "step": "Bounded Context",
                "name": bc_info["name"],
                "id": bc_info["id"],
            })

        # Step 3: User Story
        chain.append({
            "step": "User Story",
            "id": us["id"],
            "role": us.get("role", ""),
            "action": us.get("action", ""),
        })

        # Step 4: Business Logic (SOURCED_FROM)
        bl_rows = _query("""
            MATCH (f)-[:HAS_BUSINESS_LOGIC]->(bl:BusinessLogic)
            WHERE f.function_id = $fid
            RETURN bl.sequence AS seq, bl.title AS title,
                   bl.coupled_domain AS coupled_domain,
                   bl.given AS given, bl.when AS wh, bl.then AS th
            ORDER BY bl.sequence
        """, {"fid": src})

        if bl_rows:
            flow = []
            couplings = []
            for r in bl_rows:
                flow.append({
                    "seq": r["seq"],
                    "title": r["title"],
                    "coupled_domain": r.get("coupled_domain"),
                    "given": r.get("given", ""),
                    "when": r.get("wh", ""),
                    "then": r.get("th", ""),
                })
                if r.get("coupled_domain"):
                    couplings.append({
                        "seq": r["seq"],
                        "domain": r["coupled_domain"],
                        "title": r["title"],
                    })
            chain.append({
                "step": "Business Logic",
                "flow": flow,
                "domain_couplings": couplings,
            })

        # Step 5: Function + READS/WRITES + 소스 위치 + 원본 코드
        func_rows = _query("""
            MATCH (f:FUNCTION {function_id: $fid})
            RETURN f.function_id AS id, f.name AS name, f.summary AS summary,
                   f.start_line AS start_line, f.end_line AS end_line,
                   f.file_path AS file_path, f.file_name AS file_name,
                   f.code_text AS code_text
        """, {"fid": src})

        if func_rows:
            f = func_rows[0]

            # READS/WRITES + Table 상세 (컬럼, 설명)
            rw_rows = _query("""
                MATCH (f:FUNCTION {function_id: $fid})-[r:READS|WRITES]->(t:Table)
                OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
                WITH t, type(r) AS access,
                     collect(DISTINCT {name: c.name, dtype: c.dtype, pk: c.is_primary_key}) AS columns
                RETURN access, t.name AS table_name, columns
                ORDER BY t.name
            """, {"fid": src})

            # 테이블 정보 구성
            tables = {}
            for r in rw_rows:
                tname = r["table_name"]
                if tname not in tables:
                    cols = [c for c in (r.get("columns") or []) if c.get("name")]
                    tables[tname] = {
                        "name": tname,
                        "columns": [{"name": c["name"], "type": c.get("dtype", ""), "pk": bool(c.get("pk"))} for c in cols],
                        "access": [],
                    }
                tables[tname]["access"].append(r["access"])
            # access 정리
            for t in tables.values():
                t["access"] = sorted(set(t["access"]))

            # 파일 위치
            file_name = f.get("file_name") or ""
            location = file_name
            if f.get("start_line"):
                location += f":{f['start_line']}"
                if f.get("end_line"):
                    location += f"-{f['end_line']}"

            chain.append({
                "step": "Function",
                "id": f["id"],
                "name": f.get("name", ""),
                "summary": f.get("summary", ""),
                "location": location,
                "code": f.get("code_text") or "",
                "tables": list(tables.values()),
            })

        chains.append(chain)

    # 중복 체인 제거 (같은 function_id면 하나만)
    seen_funcs = set()
    unique_chains = []
    for chain in chains:
        func_step = next((s for s in chain if s["step"] == "Function"), None)
        func_id = func_step["id"] if func_step else None
        if func_id and func_id in seen_funcs:
            continue
        if func_id:
            seen_funcs.add(func_id)
        unique_chains.append(chain)

    result = {
        "node": {"id": node_id, "name": node_info.get("name", ""), "type": node_type},
        "chains": unique_chains,
    }

    SmartLogger.log("INFO", f"Traceability returned: {len(unique_chains)} chains",
                    category="graph.traceability.done",
                    params={"node_id": node_id, "chain_count": len(unique_chains)})

    return result
