"""
Analyzer Graph 어댑터

robo-data-analyzer가 Neo4j에 저장한 그래프 데이터를 조회하여
BusinessLogic + Actor 중심으로 컨텍스트를 제공한다.
"""

from __future__ import annotations

from typing import Any

from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session


def _run(query: str, params: dict | None = None) -> list[dict]:
    """동기 Neo4j 쿼리 실행 → dict 리스트 반환."""
    with get_session(database=ANALYZER_NEO4J_DATABASE) as session:
        result = session.run(query, **(params or {}))
        return [dict(record) for record in result]


def build_unit_contexts() -> list[tuple[str, str, str]]:
    """BusinessLogic이 있는 함수만 조회. BL을 sequence 순으로 정렬하여 컨텍스트 생성.

    Returns:
        [(unit_name, unit_id, context_text), ...]
    """
    query = """
    MATCH (f)-[:HAS_BUSINESS_LOGIC]->(bl:BusinessLogic)
    OPTIONAL MATCH (a:Actor)-[:ROLE]->(f)
    OPTIONAL MATCH (f)-[:READS]->(rt:Table)
    OPTIONAL MATCH (f)-[:WRITES]->(wt:Table)
    WITH f, a, bl, rt, wt
    ORDER BY bl.sequence
    WITH f,
         collect(DISTINCT a.name) AS actors,
         collect(DISTINCT {sequence: bl.sequence, title: bl.title, given: bl.given, `when`: bl.`when`, `then`: bl.`then`}) AS scenarios,
         collect(DISTINCT rt.name) AS reads_tables,
         collect(DISTINCT wt.name) AS writes_tables
    RETURN coalesce(f.procedure_name, f.name) AS unit_name,
           coalesce(f.function_id, f.procedure_name, f.name) AS unit_id,
           f.summary AS summary,
           actors, scenarios, reads_tables, writes_tables
    ORDER BY unit_name
    """
    rows = _run(query)
    results: list[tuple[str, str, str]] = []

    for row in rows:
        name = row.get("unit_name") or ""
        unit_id = row.get("unit_id") or name
        if not name:
            continue

        actors_list = [a for a in (row.get("actors") or []) if a]
        actor = ", ".join(actors_list)
        scenarios = row.get("scenarios") or []

        reads = [t for t in (row.get("reads_tables") or []) if t]
        writes = [t for t in (row.get("writes_tables") or []) if t]

        lines: list[str] = [f"## {name}"]
        if actor:
            lines.append(f"Actor: {actor}")
        if reads or writes:
            tables_parts = []
            if reads:
                tables_parts.append(f"READS: {', '.join(reads)}")
            if writes:
                tables_parts.append(f"WRITES: {', '.join(writes)}")
            lines.append(f"Tables: {' | '.join(tables_parts)}")
        lines.append("")

        # 비즈니스 로직 시나리오 (sequence 순서대로 = 비즈니스 프로세스 흐름)
        has_bl = False
        for sc in scenarios:
            if isinstance(sc, dict) and sc.get("title"):
                if not has_bl:
                    lines.append("### 비즈니스 규칙 (프로세스 흐름 순서):")
                    has_bl = True
                seq = sc.get("sequence", "")
                lines.append(f"  - BL[{seq}]: {sc['title']}")
                if sc.get("given"):
                    lines.append(f"    Given: {sc['given']}")
                if sc.get("when"):
                    lines.append(f"    When: {sc['when']}")
                if sc.get("then"):
                    lines.append(f"    Then: {sc['then']}")

        # 함수 요약 (BL 유무와 관계없이 항상 포함)
        summary = row.get("summary") or ""
        if summary:
            lines.append(f"\n### 함수 요약:\n{summary}")

        lines.extend([
            "",
            "### GUIDELINES:",
            "- BL 번호는 비즈니스 프로세스의 흐름 순서입니다",
            "- Generate User Stories from the business logic above",
            "- Each User Story MUST include a 'source_bl' field with the BL sequence numbers it originated from",
            "  Example: if a US comes from BL[1] and BL[3], set source_bl: [1, 3]",
            "- Each scenario should produce at least one User Story",
            "- Do NOT generate User Stories for implementation details",
        ])

        results.append((name, unit_id, "\n".join(lines)))

    return results


def fetch_table_schemas_for_units(unit_ids: list[str]) -> str:
    """source_unit_id 목록에서 READS/WRITES 관계로 관련 테이블 스키마를 역추적."""
    if not unit_ids:
        return ""

    query = """
    MATCH (f)-[:READS|WRITES]->(t:Table)
    WHERE f.function_id IN $unit_ids
       OR f.procedure_name IN $unit_ids
       OR f.name IN $unit_ids
    WITH DISTINCT t
    OPTIONAL MATCH (t)-[:HAS_COLUMN]->(c:Column)
    OPTIONAL MATCH (t)-[fk:FK_TO_TABLE]->(ft:Table)
    RETURN t.name AS table_name, t.schema AS schema,
           collect(DISTINCT {
             name: c.name, dtype: c.dtype,
             pk: c.is_primary_key, nullable: c.nullable,
             default_value: c.default_value
           }) AS columns,
           collect(DISTINCT {
             source_col: fk.sourceColumn,
             target_table: ft.name,
             target_col: fk.targetColumn
           }) AS fks
    """
    rows = _run(query, {"unit_ids": unit_ids})
    if not rows:
        return ""

    lines = ["[관련 테이블 스키마]"]
    for row in rows:
        cols_list = [c for c in row.get("columns", []) if c.get("name")]
        cols = ", ".join(
            f"{'*' if c.get('pk') else ''}{c['name']} {c.get('dtype', '')}"
            for c in cols_list
        )
        fks_list = [f for f in row.get("fks", []) if f.get("target_table")]
        fk_text = ""
        if fks_list:
            fk_text = " | FK: " + ", ".join(
                f"{f['source_col']}->{f['target_table']}.{f['target_col']}"
                for f in fks_list
            )
        lines.append(f"  {row['table_name']}({cols}){fk_text}")
    return "\n".join(lines)
