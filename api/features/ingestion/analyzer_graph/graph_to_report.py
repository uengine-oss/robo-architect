"""
Analyzer Graph → ParsedReport 어댑터

robo-data-analyzer가 Neo4j에 저장한 그래프 데이터를 조회하여
기존 ParsedReport 객체로 조립한다.

이렇게 하면 기존 phase 파일과 report_context.py를 전혀 수정하지 않고,
analyzer 그래프 데이터를 Event Storming 생성에 활용할 수 있다.
"""

from __future__ import annotations

from typing import Any

from api.features.ingestion.legacy_report.report_models import (
    CallRelation,
    ClassDetail,
    ColumnInfo,
    ColumnLevelFK,
    DataFlow,
    FKRelation,
    FieldInfo,
    MethodInfo,
    PackageInfo,
    ParsedReport,
    SystemOverview,
    TableAccessInfo,
    TableSchema,
    UMLRelation,
)


# ---------------------------------------------------------------------------
# stereotype → role 변환
# ---------------------------------------------------------------------------

_STEREOTYPE_TO_ROLE = {
    "Command": "command",
    "BusinessLogic": "command",
    "Endpoint": "command",
    "Handler": "command",
    "Validation": "command",
    "Transactional": "command",
    "Query": "query",
    "Getter": "getter",
    "Setter": "setter",
    "Init": "lifecycle",
    "Lifecycle": "lifecycle",
    "Scheduled": "lifecycle",
}


def _to_role(stereotype: str, has_writes: bool = False) -> str:
    """FUNCTION.stereotype → MethodInfo.role 변환.

    이름 패턴보다 실제 동작을 우선:
    - WRITES 관계가 있으면 무조건 "command"
    - 테이블 접근 없으면 stereotype 기반 매핑
    """
    if has_writes:
        return "command"
    return _STEREOTYPE_TO_ROLE.get(stereotype, "command")


# ---------------------------------------------------------------------------
# Neo4j 쿼리 실행 헬퍼
# ---------------------------------------------------------------------------

def _run(client: Any, query: str, **params: Any) -> list[dict]:
    """동기 Neo4j 쿼리 실행 → dict 리스트 반환."""
    with client.session() as session:
        result = session.run(query, **params)
        return [dict(record) for record in result]


# ---------------------------------------------------------------------------
# 개별 조회 함수
# ---------------------------------------------------------------------------

def _fetch_overview(client: Any) -> SystemOverview:
    """시스템 개요 (노드 개수 집계)."""
    query = """
    OPTIONAL MATCH (pkg:PACKAGE)   WITH count(pkg)  AS pkg_cnt
    OPTIONAL MATCH (mod:MODULE)    WITH pkg_cnt, count(mod)  AS mod_cnt
    OPTIONAL MATCH (fn:FUNCTION)   WITH pkg_cnt, mod_cnt, count(fn)   AS fn_cnt
    OPTIONAL MATCH (tbl:Table)     WITH pkg_cnt, mod_cnt, fn_cnt, count(tbl)  AS tbl_cnt
    OPTIONAL MATCH (col:Column)    WITH pkg_cnt, mod_cnt, fn_cnt, tbl_cnt, count(col) AS col_cnt
    RETURN pkg_cnt, mod_cnt, fn_cnt, tbl_cnt, col_cnt
    """
    rows = _run(client, query)
    if not rows:
        return SystemOverview()
    r = rows[0]
    return SystemOverview(
        package_count=r.get("pkg_cnt", 0) or 0,
        class_count=r.get("mod_cnt", 0) or 0,
        method_count=r.get("fn_cnt", 0) or 0,
        table_count=r.get("tbl_cnt", 0) or 0,
        column_count=r.get("col_cnt", 0) or 0,
    )


def _fetch_packages(client: Any) -> list[PackageInfo]:
    """PACKAGE 노드 → PackageInfo 목록."""
    query = """
    MATCH (p:PACKAGE)
    OPTIONAL MATCH (m:MODULE)-[:BELONGS_TO_PACKAGE]->(p)
    RETURN p.name AS name, p.fqn AS fqn, count(m) AS class_count
    ORDER BY p.name
    """
    return [
        PackageInfo(
            name=r.get("name", ""),
            full_path=r.get("fqn", ""),
            class_count=r.get("class_count", 0) or 0,
        )
        for r in _run(client, query)
    ]


def _fetch_classes(client: Any) -> list[ClassDetail]:
    """MODULE + FUNCTION + VARIABLE + 관계 → ClassDetail 목록."""

    # 1) MODULE 기본 정보 (함수가 있는 MODULE만 — Python FILE/CLASS 중복 방지)
    modules_query = """
    MATCH (m:MODULE)
    WHERE EXISTS { (m)-[:HAS_FUNCTION]->() }
    RETURN m.name AS name, m.fqn AS fqn, m.package_name AS package,
           m.summary AS summary, m.moduleStereotype AS moduleStereotype,
           labels(m) AS labels
    ORDER BY m.fqn
    """
    modules = _run(client, modules_query)

    classes: list[ClassDetail] = []
    for mod in modules:
        mod_fqn = mod.get("fqn", "")
        mod_name = mod.get("name", "")

        # MODULE stereotype → ClassDetail stereotype 변환
        mod_stereo = mod.get("moduleStereotype", "") or ""
        class_stereotype = _module_stereotype_to_class(mod_stereo)

        # 2) FUNCTION (메서드) 조회
        fn_query = """
        MATCH (m:MODULE {fqn: $fqn})-[:HAS_FUNCTION]->(f:FUNCTION)
        OPTIONAL MATCH (f)-[:WRITES]->(wt:Table)
        OPTIONAL MATCH (f)-[:READS]->(rt:Table)
        RETURN f.name AS name, f.signature AS signature,
               f.summary AS summary, f.stereotype AS stereotype,
               collect(DISTINCT wt.name) AS writes_tables,
               collect(DISTINCT rt.name) AS reads_tables
        ORDER BY f.start_line
        """
        functions = _run(client, fn_query, fqn=mod_fqn)

        methods: list[MethodInfo] = []
        table_access_set: set[tuple[str, str]] = set()

        for fn in functions:
            writes = [t for t in (fn.get("writes_tables") or []) if t]
            reads = [t for t in (fn.get("reads_tables") or []) if t]
            has_writes = len(writes) > 0
            stereotype = fn.get("stereotype", "") or ""

            methods.append(MethodInfo(
                name=fn.get("name", ""),
                signature=fn.get("signature", ""),
                role=_to_role(stereotype, has_writes),
                summary=fn.get("summary", ""),
            ))

            for t in writes:
                table_access_set.add((t, "WRITES"))
            for t in reads:
                table_access_set.add((t, "FROM"))

        # 3) VARIABLE (필드) 조회
        var_query = """
        MATCH (m:MODULE {fqn: $fqn})-[:HAS_VARIABLE]->(v:VARIABLE)
        RETURN v.name AS name, v.variable_type AS type, v.summary AS summary
        ORDER BY v.name
        """
        variables = _run(client, var_query, fqn=mod_fqn)

        fields = [
            FieldInfo(
                name=v.get("name", ""),
                type=v.get("type", ""),
                description=v.get("summary", ""),
            )
            for v in variables
        ]

        # 4) UML 관계 조회
        rel_query = """
        MATCH (m:MODULE {fqn: $fqn})-[r]->(t:MODULE)
        WHERE type(r) IN ['USES', 'EXTENDS', 'IMPLEMENTS', 'ASSOCIATION', 'DEPENDENCY', 'COMPOSITION', 'AGGREGATION']
        RETURN type(r) AS rel_type, t.name AS target, t.fqn AS target_fqn,
               CASE WHEN 'EXTERNAL' IN labels(t) THEN 'EXTERNAL' ELSE 'INTERNAL' END AS scope
        """
        relations = _run(client, rel_query, fqn=mod_fqn)

        uml_relations = [
            UMLRelation(
                direction="->",
                relation_type=r.get("rel_type", ""),
                target=r.get("target", ""),
                target_scope=r.get("scope", "INTERNAL"),
            )
            for r in relations
        ]

        # 5) table_access 조립
        table_access = [
            TableAccessInfo(table=t, access_type=a)
            for t, a in sorted(table_access_set)
        ]

        # 6) summarized_code (메서드 summary 합산)
        summarized_code = "\n".join(
            f"- {m.name}: {m.summary}" for m in methods if m.summary
        )

        # 7) ClassDetail 조립
        labels = mod.get("labels") or []
        class_type = "CLASS"
        if "INTERFACE" in labels:
            class_type = "INTERFACE"
        elif "ENUM" in labels:
            class_type = "ENUM"

        scope = "EXTERNAL" if "EXTERNAL" in labels else "INTERNAL"

        classes.append(ClassDetail(
            name=mod_name,
            fqn=mod_fqn,
            package=mod.get("package", "") or "",
            class_type=class_type,
            scope=scope,
            stereotype=class_stereotype,
            summary=mod.get("summary", "") or "",
            methods=methods,
            fields=fields,
            uml_relations=uml_relations,
            table_access=table_access,
            summarized_code=summarized_code,
        ))

    return classes


def _module_stereotype_to_class(mod_stereotype: str) -> str:
    """MODULE.moduleStereotype → ClassDetail.stereotype 변환.

    report_context.py가 Session Bean / Entity Bean으로 필터링하므로,
    analyzer의 Service/Repository/Entity 등을 적절히 매핑.
    """
    mapping = {
        "Service": "Session Bean (Stateless)",
        "Controller": "Session Bean (Stateless)",
        "Facade": "Session Bean (Stateless)",
        "Gateway": "Session Bean (Stateless)",
        "Entity": "Entity Bean (CMP)",
        "Repository": "Repository",
        "DTO": "DTO",
        "Config": "Config",
        "Component": "Component",
        "Util": "Util",
    }
    return mapping.get(mod_stereotype, mod_stereotype or "")


def _fetch_tables(client: Any) -> list[TableSchema]:
    """Table + Column + FK → TableSchema 목록."""
    # 테이블 목록
    tables_query = """
    MATCH (t:Table)
    RETURN t.name AS name, t.schema AS schema, t.description AS description
    ORDER BY t.name
    """
    tables = _run(client, tables_query)

    result: list[TableSchema] = []
    for tbl in tables:
        tbl_name = tbl.get("name", "")

        # 컬럼 조회
        col_query = """
        MATCH (t:Table {name: $name})-[:HAS_COLUMN]->(c:Column)
        RETURN c.name AS name, c.dtype AS dtype, c.nullable AS nullable,
               c.is_primary_key AS is_pk, c.is_unique AS is_unique,
               c.default_value AS default_value, c.description AS description
        ORDER BY c.name
        """
        columns = _run(client, col_query, name=tbl_name)

        col_infos = [
            ColumnInfo(
                name=c.get("name", ""),
                data_type=c.get("dtype", ""),
                nullable=c.get("nullable", True) if c.get("nullable") is not None else True,
                is_pk=bool(c.get("is_pk")),
                description=_build_column_description(c),
            )
            for c in columns
        ]

        # FK 관계 조회
        fk_query = """
        MATCH (t:Table {name: $name})-[fk:FK_TO_TABLE]->(target:Table)
        RETURN fk.sourceColumn AS source_col, target.name AS target_table,
               fk.targetColumn AS target_col
        """
        fks = _run(client, fk_query, name=tbl_name)

        fk_relations = [
            FKRelation(
                direction="->",
                target_table=fk.get("target_table", ""),
                source_column=fk.get("source_col", ""),
                target_column=fk.get("target_col", ""),
                confidence="HIGH",
            )
            for fk in fks
        ]

        # mapped_entity 추론: 이 테이블에 WRITES하는 Entity stereotype MODULE
        entity_query = """
        MATCH (f:FUNCTION)-[:WRITES]->(t:Table {name: $name})
        MATCH (m:MODULE)-[:HAS_FUNCTION]->(f)
        WHERE m.moduleStereotype = 'Entity'
        RETURN m.name AS entity_name LIMIT 1
        """
        entity_rows = _run(client, entity_query, name=tbl_name)
        mapped_entity = entity_rows[0].get("entity_name") if entity_rows else None

        result.append(TableSchema(
            name=tbl_name,
            schema_name=tbl.get("schema", "") or "",
            mapped_entity=mapped_entity,
            summary=tbl.get("description", "") or "",
            columns=col_infos,
            fk_relations=fk_relations,
        ))

    return result


def _build_column_description(col: dict) -> str:
    """컬럼 제약조건을 description에 포함."""
    parts = []
    if col.get("description"):
        parts.append(col["description"])
    flags = []
    if col.get("is_unique"):
        flags.append("UNIQUE")
    if col.get("default_value"):
        flags.append(f"DEFAULT={col['default_value']}")
    if flags:
        parts.append(f"[{', '.join(flags)}]")
    return " ".join(parts)


def _fetch_data_flow(client: Any) -> DataFlow:
    """CALLS 관계 → DataFlow."""
    # 호출 관계
    calls_query = """
    MATCH (caller:FUNCTION)-[:CALLS]->(callee:FUNCTION)
    OPTIONAL MATCH (cm:MODULE)-[:HAS_FUNCTION]->(caller)
    OPTIONAL MATCH (tm:MODULE)-[:HAS_FUNCTION]->(callee)
    RETURN cm.name + '.' + caller.name AS caller_name,
           tm.name + '.' + callee.name AS callee_name
    """
    calls = _run(client, calls_query)

    call_relations = [
        CallRelation(
            caller=c.get("caller_name", ""),
            callee=c.get("callee_name", ""),
            scope="internal",
        )
        for c in calls
        if c.get("caller_name") and c.get("callee_name")
    ]

    # DBMS: PROCEDURE/FUNCTION/TRIGGER → CALLS
    dbms_calls_query = """
    MATCH (caller)-[:CALLS]->(callee)
    WHERE any(l IN labels(caller) WHERE l IN ['PROCEDURE','FUNCTION','TRIGGER'])
    RETURN caller.procedure_name AS caller_name,
           callee.procedure_name AS callee_name
    """
    dbms_calls = _run(client, dbms_calls_query)
    call_relations.extend([
        CallRelation(
            caller=c.get("caller_name", ""),
            callee=c.get("callee_name", ""),
            scope="internal",
        )
        for c in dbms_calls
        if c.get("caller_name") and c.get("callee_name")
    ])

    # 테이블 접근 매트릭스
    access_query = """
    MATCH (f:FUNCTION)-[r:READS|WRITES]->(t:Table)
    OPTIONAL MATCH (m:MODULE)-[:HAS_FUNCTION]->(f)
    RETURN m.name AS class_name, t.name AS table_name,
           CASE type(r) WHEN 'WRITES' THEN 'WRITES' ELSE 'FROM' END AS access_type
    """
    accesses = _run(client, access_query)

    table_access_matrix = [
        TableAccessInfo(
            table=a.get("table_name", ""),
            access_type=a.get("access_type", "FROM"),
            evidence=a.get("class_name", ""),
        )
        for a in accesses
    ]

    return DataFlow(
        call_relations=call_relations,
        table_access_matrix=table_access_matrix,
    )


def _fetch_column_level_fks(client: Any) -> list[ColumnLevelFK]:
    """Column → FK_TO_COLUMN → Column 관계."""
    query = """
    MATCH (c1:Column)-[:FK_TO_COLUMN]->(c2:Column)
    RETURN c1.fqn AS source, c2.fqn AS target
    """
    rows = _run(client, query)
    return [
        ColumnLevelFK(
            source_column=r.get("source", ""),
            target_column=r.get("target", ""),
            confidence="HIGH",
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# DBMS: PROCEDURE 노드 → ClassDetail 변환
# ---------------------------------------------------------------------------

def _fetch_procedures(client: Any) -> list[ClassDetail]:
    """PROCEDURE + 하위 DML → ClassDetail 목록."""
    proc_query = """
    MATCH (p)
    WHERE any(l IN labels(p) WHERE l IN ['PROCEDURE', 'FUNCTION', 'TRIGGER'])
    RETURN p.procedure_name AS name, p.summary AS summary,
           p.directory AS directory, p.file_name AS file_name,
           p.schema_name AS schema_name
    ORDER BY p.procedure_name
    """
    procedures = _run(client, proc_query)
    if not procedures:
        return []

    classes: list[ClassDetail] = []
    for proc in procedures:
        proc_name = proc.get("name", "")
        directory = proc.get("directory", "")
        file_name = proc.get("file_name", "")

        # 하위 DML에서 테이블 접근 정보 수집
        dml_query = """
        MATCH (p {procedure_name: $name, directory: $dir, file_name: $file})
        WHERE any(l IN labels(p) WHERE l IN ['PROCEDURE', 'FUNCTION', 'TRIGGER'])
        MATCH (p)-[:PARENT_OF*]->(dml)
        WHERE any(l IN labels(dml) WHERE l IN ['SELECT','INSERT','UPDATE','DELETE','MERGE'])
        OPTIONAL MATCH (dml)-[:WRITES]->(wt:Table)
        OPTIONAL MATCH (dml)-[:FROM]->(rt:Table)
        RETURN collect(DISTINCT wt.name) AS writes_tables,
               collect(DISTINCT rt.name) AS reads_tables
        """
        dml_rows = _run(client, dml_query, name=proc_name, dir=directory, file=file_name)

        table_access_set: set[tuple[str, str]] = set()
        has_any_writes = False
        if dml_rows:
            for t in [t for t in (dml_rows[0].get("writes_tables") or []) if t]:
                table_access_set.add((t, "WRITES"))
                has_any_writes = True
            for t in [t for t in (dml_rows[0].get("reads_tables") or []) if t]:
                table_access_set.add((t, "FROM"))

        table_access = [
            TableAccessInfo(table=t, access_type=a)
            for t, a in sorted(table_access_set)
        ]

        # 프로시저 전체를 하나의 method로 매핑
        proc_summary = proc.get("summary", "") or ""
        methods = [MethodInfo(
            name=proc_name,
            role="command" if has_any_writes else "query",
            summary=proc_summary,
        )]

        summarized_code = proc_summary

        classes.append(ClassDetail(
            name=proc_name,
            fqn=f"{directory}/{file_name}:{proc_name}",
            package=directory or "",
            stereotype="Session Bean (Stateless)",  # report_context.py가 Session Bean으로 필터링
            summary=summarized_code,
            methods=methods,
            table_access=table_access,
            summarized_code=summarized_code,
        ))

    return classes


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def build_report_from_graph(client: Any) -> ParsedReport:
    """Neo4j 그래프 데이터를 조회하여 ParsedReport 객체로 조립.

    Args:
        client: architect의 Neo4j 클라이언트 (동기, client.session() 사용)

    Returns:
        ParsedReport — 기존 phase 파일과 report_context.py가 그대로 사용 가능
    """
    overview = _fetch_overview(client)
    packages = _fetch_packages(client)

    # Framework 클래스 + DBMS 프로시저 모두 수집
    classes = _fetch_classes(client)
    procedures = _fetch_procedures(client)
    all_classes = classes + procedures

    tables = _fetch_tables(client)
    data_flow = _fetch_data_flow(client)
    column_level_fks = _fetch_column_level_fks(client)

    return ParsedReport(
        title="Analyzer Graph Data",
        overview=overview,
        packages=packages,
        classes=all_classes,
        tables=tables,
        data_flow=data_flow,
        column_level_fks=column_level_fks,
    )
