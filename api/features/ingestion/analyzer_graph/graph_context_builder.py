"""
Analyzer Graph 어댑터

robo-data-analyzer가 Neo4j에 저장한 그래프 데이터를 조회하여
BusinessLogic + Actor 중심으로 컨텍스트를 제공한다.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session

# 그룹 배치 설정
_GROUP_MAX_FUNCTIONS = 8  # 한 그룹에 최대 함수 수
_GROUP_MAX_TOKENS = 50000  # 한 그룹의 최대 토큰 추정치


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


def build_grouped_unit_contexts() -> list[tuple[str, list[str], str]]:
    """관련 함수들을 도메인 그룹으로 묶어서 컨텍스트 생성.

    그룹핑 기준:
    1. 같은 테이블을 READS/WRITES하는 함수
    2. 함수명 접두사(도메인 키워드)가 같은 함수

    Returns:
        [(group_name, [unit_id, ...], merged_context_text), ...]
    """
    # Step 1: 개별 함수 데이터 조회 (build_unit_contexts와 동일 쿼리)
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
         collect(DISTINCT rt.name) AS reads_tables,
         collect(DISTINCT wt.name) AS writes_tables
    RETURN coalesce(f.procedure_name, f.name) AS unit_name,
           coalesce(f.function_id, f.procedure_name, f.name) AS unit_id,
           f.summary AS summary,
           actors, scenarios, reads_tables, writes_tables
    ORDER BY unit_name
    """
    rows = _run(query)
    if not rows:
        return []

    # Step 2: 함수별 메타데이터 추출
    units: list[dict[str, Any]] = []
    for row in rows:
        name = row.get("unit_name") or ""
        if not name:
            continue
        reads = set(t for t in (row.get("reads_tables") or []) if t)
        writes = set(t for t in (row.get("writes_tables") or []) if t)
        units.append({
            "name": name,
            "unit_id": row.get("unit_id") or name,
            "tables": reads | writes,
            "prefix": _extract_domain_prefix(name),
            "row": row,
        })

    # Step 3: Union-Find로 관련 함수 그룹핑
    # 같은 테이블을 사용하거나 같은 접두사를 가진 함수를 연결
    n = len(units)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # 테이블 기반 연결
    table_to_units: dict[str, list[int]] = defaultdict(list)
    for i, u in enumerate(units):
        for t in u["tables"]:
            table_to_units[t].append(i)
    for indices in table_to_units.values():
        for j in range(1, len(indices)):
            union(indices[0], indices[j])

    # 접두사 기반 연결
    prefix_to_units: dict[str, list[int]] = defaultdict(list)
    for i, u in enumerate(units):
        if u["prefix"]:
            prefix_to_units[u["prefix"]].append(i)
    for indices in prefix_to_units.values():
        for j in range(1, len(indices)):
            union(indices[0], indices[j])

    # Step 4: 그룹 수집
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    # Step 5: 각 그룹의 컨텍스트 생성 (큰 그룹은 서브 배치로 분할)
    results: list[tuple[str, list[str], str]] = []

    for root, members in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
        member_units = [units[i] for i in members]

        # 그룹 이름: 가장 빈번한 접두사 또는 첫 번째 함수명
        prefix_counts: dict[str, int] = defaultdict(int)
        for u in member_units:
            if u["prefix"]:
                prefix_counts[u["prefix"]] += 1
        group_name = max(prefix_counts, key=prefix_counts.get) if prefix_counts else member_units[0]["name"]

        # 서브 배치 분할 (너무 큰 그룹)
        for batch_start in range(0, len(member_units), _GROUP_MAX_FUNCTIONS):
            batch = member_units[batch_start:batch_start + _GROUP_MAX_FUNCTIONS]
            batch_unit_ids = [u["unit_id"] for u in batch]

            # 배치 컨텍스트 구성
            batch_lines = [
                f"# Domain Group: {group_name} ({len(batch)} functions)",
                f"Related functions that operate on the SAME business domain.",
                f"Analyze these TOGETHER and create consolidated User Stories.",
                "",
            ]

            # 공통 테이블 요약
            all_tables = set()
            for u in batch:
                all_tables |= u["tables"]
            if all_tables:
                batch_lines.append(f"Shared Tables: {', '.join(sorted(all_tables))}")
                batch_lines.append("")

            # 각 함수의 BL 포함
            for u in batch:
                func_context = _build_single_unit_context(u["row"])
                batch_lines.append(func_context)
                batch_lines.append("")

            batch_lines.extend([
                "### GROUP-LEVEL GUIDELINES:",
                "- These functions are in the SAME business domain — create UNIFIED User Stories",
                "- Shared operations across functions should become ONE User Story (not duplicated)",
                f"- Target: 3~10 User Stories for this group of {len(batch)} functions",
                "- Each User Story MUST include source_bl with the BL sequence numbers",
                "- source_unit_id will be set automatically — focus on meaningful business capabilities",
            ])

            suffix = f" (batch {batch_start // _GROUP_MAX_FUNCTIONS + 1})" if len(member_units) > _GROUP_MAX_FUNCTIONS else ""
            results.append((
                f"{group_name}{suffix}",
                batch_unit_ids,
                "\n".join(batch_lines),
            ))

    return results


def _extract_domain_prefix(func_name: str) -> str:
    """Extract domain prefix from function name.

    Examples:
        ValidateAutoDebitInput → AutoDebit
        ProcessAutoPaymentApplication → AutoPayment
        ChangeAutoDebitAccount → AutoDebit
        ComposeAutoDebitInquiryResponse → AutoDebit
    """
    # Remove common verb prefixes
    verbs = (
        "Validate", "Process", "Change", "Create", "Update", "Delete",
        "Register", "Check", "Compose", "Send", "Set", "Get", "Retrieve",
        "Block", "Unblock", "Terminate", "Cancel", "Confirm", "Reject",
        "Approve", "Request", "Record", "Calculate", "Determine",
        "Copy", "Save", "Correct", "Prevent", "Fail", "Pass",
    )
    name = func_name
    for v in verbs:
        if name.startswith(v) and len(name) > len(v):
            name = name[len(v):]
            break

    # Extract first 1-2 PascalCase words as domain
    parts = re.findall(r"[A-Z][a-z]+", name)
    if len(parts) >= 2:
        # "AutoDebit" (4+5=9 chars or less) → keep both
        candidate = parts[0] + parts[1]
        if len(candidate) <= 15:
            return candidate
        return parts[0]
    return parts[0] if parts else ""


def _build_single_unit_context(row: dict[str, Any]) -> str:
    """Build context text for a single function (reused by both grouped and ungrouped)."""
    name = row.get("unit_name") or row.get("unit_id") or ""
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

    valid_scenarios = [sc for sc in scenarios if isinstance(sc, dict) and sc.get("title")]

    if valid_scenarios:
        flow_parts = []
        for sc in valid_scenarios:
            seq = sc.get("sequence", "")
            domain = sc.get("coupled_domain")
            flow_parts.append(f"BL[{seq}]*" if domain else f"BL[{seq}]")
        lines.append(f"Flow: {' → '.join(flow_parts)}")

        for sc in valid_scenarios:
            seq = sc.get("sequence", "")
            domain = sc.get("coupled_domain")
            coupled_info = f" [★ {domain}]" if domain else ""
            lines.append(f"  - BL[{seq}]{coupled_info}: {sc['title']}")
            if sc.get("given"):
                lines.append(f"    Given: {sc['given']}")
            if sc.get("when"):
                lines.append(f"    When: {sc['when']}")
            if sc.get("then"):
                lines.append(f"    Then: {sc['then']}")

    summary = row.get("summary") or ""
    if summary:
        lines.append(f"Summary: {summary}")

    return "\n".join(lines)


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
