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
         collect(DISTINCT {sequence: bl.sequence, coupled_domain: bl.coupled_domain, title: bl.title, given: bl.given, `when`: bl.`when`, `then`: bl.`then`}) AS scenarios,
         collect(DISTINCT {name: rt.name, is_estimated: rt.is_estimated}) AS reads_tables,
         collect(DISTINCT {name: wt.name, is_estimated: wt.is_estimated}) AS writes_tables
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

        def _format_tables(table_list):
            result = []
            for t in (table_list or []):
                if isinstance(t, dict) and t.get("name"):
                    label = t["name"]
                    if t.get("is_estimated"):
                        label += "(추정)"
                    result.append(label)
                elif isinstance(t, str) and t:
                    result.append(t)
            return result

        reads = _format_tables(row.get("reads_tables"))
        writes = _format_tables(row.get("writes_tables"))

        lines: list[str] = [f"## {name}"]
        if actor:
            lines.append(f"Actor: {actor}")
        has_estimated = any("(추정)" in t for t in reads + writes)
        if reads or writes:
            tables_parts = []
            if reads:
                tables_parts.append(f"READS: {', '.join(reads)}")
            if writes:
                tables_parts.append(f"WRITES: {', '.join(writes)}")
            lines.append(f"Tables: {' | '.join(tables_parts)}")
        if has_estimated:
            lines.append("⚠️ (추정) 표시된 테이블은 코드 패턴에서 추정한 것이며, DDL/헤더파일로 확정되지 않았습니다. 확신하지 마세요.")
        lines.append("")

        # 비즈니스 로직 시나리오 (sequence 순서대로 = 비즈니스 프로세스 흐름)
        valid_scenarios = [sc for sc in scenarios if isinstance(sc, dict) and sc.get("title")]
        has_bl = bool(valid_scenarios)

        if has_bl:
            # 흐름도: BL[1] → BL[2] → BL[3] (도메인 경계 표시)
            flow_parts = []
            coupled_bls = []
            own_domain_bls = []
            for sc in valid_scenarios:
                seq = sc.get("sequence", "")
                domain = sc.get("coupled_domain")
                if domain:
                    flow_parts.append(f"BL[{seq}]*")
                    coupled_bls.append((seq, domain, sc.get("title", "")))
                else:
                    flow_parts.append(f"BL[{seq}]")
                    own_domain_bls.append(seq)

            lines.append("### 비즈니스 프로세스 흐름:")
            lines.append(f"  {' → '.join(flow_parts)}")

            # 도메인 경계 요약
            if coupled_bls:
                lines.append("")
                lines.append("### 도메인 경계 (Cross-Domain Coupling):")
                lines.append(f"  현재 도메인: BL[{', '.join(str(s) for s in own_domain_bls)}]")
                for seq, domain, title in coupled_bls:
                    lines.append(f"  ★ BL[{seq}] → {domain} 도메인 (분리 대상): {title}")
                lines.append("  → 커플링된 BL은 이후 DDD 전환 시 별도 서비스/이벤트로 분리해야 할 대상입니다")

            lines.append("")
            lines.append("### 비즈니스 규칙 상세:")
            for sc in valid_scenarios:
                seq = sc.get("sequence", "")
                domain = sc.get("coupled_domain")
                coupled_info = f" [★ {domain} 도메인]" if domain else ""
                lines.append(f"  - BL[{seq}]{coupled_info}: {sc['title']}")
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
            "- BL 번호는 비즈니스 프로세스의 흐름 순서입니다 (BL[1] → BL[2] → ...)",
            "- ★표시 BL은 다른 도메인의 로직이 현재 함수에 포함된 것 (Cross-Domain Coupling)",
            "- 커플링된 BL은 해당 도메인의 별도 US로 분리하거나, 도메인 간 이벤트/호출로 표현하세요",
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
           t.description AS table_description,
           collect(DISTINCT {
             name: c.name, dtype: c.dtype,
             pk: c.is_primary_key, nullable: c.nullable,
             default_value: c.default_value,
             description: c.description
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
        table_name = row["table_name"]
        table_desc = row.get("table_description") or ""
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
        header = f"  {table_name}({cols}){fk_text}"
        if table_desc:
            header += f"\n    설명: {table_desc}"
        # 컬럼 설명이 있는 경우 추가
        col_descs = [c for c in cols_list if c.get("description")]
        if col_descs:
            header += "\n    컬럼설명: " + ", ".join(
                f"{c['name']}={c['description']}" for c in col_descs
            )
        lines.append(header)
    return "\n".join(lines)
