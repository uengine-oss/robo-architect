"""
Legacy report context extraction utilities.

Extracts phase-specific supplementary context from a ParsedReport,
with chunking support to prevent context overflow.

Each phase gets only the relevant sections it needs.
"""

from __future__ import annotations

from api.features.ingestion.legacy_report.report_models import ParsedReport
from api.features.ingestion.workflow.utils.chunking import (
    DEFAULT_CHUNK_SIZE,
    estimate_tokens,
)


# Max tokens for supplementary report context injected into prompts.
# Keep well under DEFAULT_CHUNK_SIZE to leave room for the main prompt + output.
REPORT_CONTEXT_MAX_TOKENS = 20000

# EJB lifecycle methods — framework callbacks, NOT domain concepts.
# These should be excluded from User Story generation and Command extraction.
EJB_LIFECYCLE_METHODS = frozenset({
    "ejbCreate", "ejbRemove", "ejbActivate", "ejbPassivate",
    "ejbLoad", "ejbStore", "ejbPostCreate", "ejbFindByPrimaryKey",
    "setEntityContext", "unsetEntityContext",
    "setSessionContext", "afterBegin", "beforeCompletion", "afterCompletion",
    "setMessageDrivenContext", "onMessage",
})

# Session Bean technical patterns that are NOT domain operations
EJB_TECHNICAL_PATTERNS = frozenset({
    "getConnection", "closeConnection", "getDataSource",
    "lookup", "getInitialContext", "getEJBHome",
    "getEntityManager", "getSessionContext",
})


def _is_business_method(method_name: str) -> bool:
    """Check if a method represents business logic (not EJB lifecycle/technical)."""
    if method_name in EJB_LIFECYCLE_METHODS:
        return False
    if method_name in EJB_TECHNICAL_PATTERNS:
        return False
    # ejbFind* methods are also lifecycle
    if method_name.startswith("ejb") and method_name[3:4].isupper():
        return False
    return True


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit within max_tokens (approximate)."""
    tokens = estimate_tokens(text)
    if tokens <= max_tokens:
        return text
    # Rough char-based truncation (4 chars ≈ 1 token)
    ratio = max_tokens / tokens
    cut = int(len(text) * ratio)
    return text[:cut] + "\n... (truncated)"


def _build_system_overview(report: ParsedReport) -> str:
    overview = report.overview
    return (
        f"Description: {overview.description}\n"
        f"Packages: {overview.package_count}, Classes: {overview.class_count}, "
        f"Tables: {overview.table_count}"
    )


def _build_packages_text(report: ParsedReport) -> str:
    if not report.packages:
        return "(no packages)"
    return "\n".join(
        f"- {pkg.name}: {pkg.description} ({pkg.class_count} classes)"
        for pkg in report.packages
    )


def _build_entity_beans_text(report: ParsedReport) -> str:
    """Entity Bean 목록 + 테이블 매핑된 추가 Entity."""
    entity_beans = report.get_entity_beans()
    lines: list[str] = []
    known = set()
    for eb in entity_beans:
        known.add(eb.name)
        agg_name = eb.name[:-4] if eb.name.endswith("Bean") else eb.name
        table = report.get_table_for_entity(eb.name)
        table_info = f" → Table: {table.name}" if table else ""
        fields_info = ""
        if eb.fields:
            fields_info = f" | Fields: {', '.join(f.name for f in eb.fields[:10])}"
        lines.append(f"- {agg_name} ({eb.name}){table_info}{fields_info}")

    for table in report.tables:
        if table.mapped_entity and table.mapped_entity not in known:
            agg_name = table.mapped_entity[:-4] if table.mapped_entity.endswith("Bean") else table.mapped_entity
            lines.append(f"- {agg_name} ({table.mapped_entity}) → Table: {table.name}")
    return "\n".join(lines) or "(no entity beans)"


def _build_session_beans_text(report: ParsedReport) -> str:
    session_beans = report.get_session_beans()
    if not session_beans:
        return "(no session beans)"
    lines: list[str] = []
    for sb in session_beans:
        cmds = [m.name for m in sb.methods if m.role == "command" and _is_business_method(m.name)]
        queries = [m.name for m in sb.methods if m.role == "query" and _is_business_method(m.name)]
        assocs = [r.target for r in sb.uml_relations if r.relation_type == "ASSOCIATION"]
        lines.append(
            f"- {sb.name}: commands={cmds}, queries={queries}, entities={assocs}"
        )
    return "\n".join(lines)


def _build_tables_fk_text(report: ParsedReport) -> str:
    if not report.tables:
        return "(no tables)"
    lines: list[str] = []
    for table in report.tables:
        fks = [fk for fk in report.column_level_fks if fk.source_column.startswith(f"{table.name}.")]
        fk_text = ""
        if fks:
            fk_text = " | FK→ " + ", ".join(fk.target_column for fk in fks)
        col_info = f" ({len(table.columns)} cols)" if table.columns else ""
        lines.append(f"- {table.name} (entity: {table.mapped_entity}){col_info}{fk_text}")
    return "\n".join(lines)


def _build_table_columns_text(report: ParsedReport) -> str:
    """테이블별 컬럼 상세 (Properties Phase용)."""
    if not report.tables:
        return "(no tables)"
    lines: list[str] = []
    for table in report.tables:
        if not table.columns:
            continue
        lines.append(f"\n### {table.name} (entity: {table.mapped_entity})")
        for col in table.columns:
            pk = " [PK]" if col.is_pk else ""
            nullable = "" if col.nullable else " NOT NULL"
            lines.append(f"  - {col.name}: {col.data_type}{pk}{nullable} — {col.description or ''}")
    return "\n".join(lines) or "(no column details)"


def _build_call_chains_text(report: ParsedReport) -> str:
    parts: list[str] = []
    for chain in report.data_flow.call_chains:
        parts.append(f"[{chain.flow_name}]\n{chain.chain_text}")
    for rel in report.data_flow.call_relations:
        caller_cls = rel.caller.split(".")[0]
        callee_cls = rel.callee.split(".")[0]
        if caller_cls != callee_cls:
            parts.append(f"Cross-call: {rel.caller} → {rel.callee}")
    return "\n\n".join(parts) if parts else "(no call chains)"


def _build_entity_detail_text(report: ParsedReport) -> str:
    """Entity Bean 상세 (상태 상수, 메서드, summarized code)."""
    entity_beans = report.get_entity_beans()
    if not entity_beans:
        return "(no entity bean details)"
    lines: list[str] = []
    for eb in entity_beans:
        agg_name = eb.name[:-4] if eb.name.endswith("Bean") else eb.name
        lines.append(f"\n### {agg_name} ({eb.stereotype})")
        # Status/state fields
        status_fields = [f for f in eb.fields if "STATUS" in f.name.upper() or "STATE" in f.name.upper()]
        if status_fields:
            lines.append("State constants:")
            for f in status_fields:
                lines.append(f"  - {f.name}: {f.description}")
        # Methods (business methods only)
        state_methods = [m for m in eb.methods if m.role in ("command", "setter") and _is_business_method(m.name)]
        if state_methods:
            lines.append("State-changing methods:")
            for m in state_methods:
                lines.append(f"  - {m.name}{m.signature}: {m.summary}")
        # Summarized code
        if eb.summarized_code:
            lines.append(f"Summarized code:\n```\n{eb.summarized_code}\n```")
    return "\n".join(lines)


def _build_session_bean_methods_text(report: ParsedReport, role_filter: str | None = None, warn_non_commands: bool = False) -> str:
    """Session Bean 메서드 상세 (EJB lifecycle methods excluded).

    warn_non_commands=True이면 query/getter 메서드에 경고 마커를 추가하여
    LLM이 이들을 Command로 생성하지 않도록 안내합니다.
    """
    session_beans = report.get_session_beans()
    if not session_beans:
        return "(no session bean methods)"
    lines: list[str] = []
    for sb in session_beans:
        methods = sb.methods
        if role_filter:
            methods = [m for m in methods if m.role == role_filter]
        # Filter out EJB lifecycle and technical methods
        methods = [m for m in methods if _is_business_method(m.name)]
        if not methods:
            continue
        lines.append(f"\n### {sb.name}")
        for m in methods:
            role_tag = m.role
            if warn_non_commands and role_tag in ("query", "getter"):
                role_tag = f"{m.role} ⚠️NOT_A_COMMAND"
            lines.append(f"  - {m.name}{m.signature} [{role_tag}]: {m.summary}")
    return "\n".join(lines) or "(no methods)"


def _build_sql_queries_text(report: ParsedReport) -> str:
    """SQL 쿼리 블록 추출 (ReadModels Phase용)."""
    sql_blocks = [b for b in report.config_blocks if b.block_type == "sql"]
    if not sql_blocks:
        return "(no SQL query blocks)"
    lines: list[str] = []
    for block in sql_blocks:
        lines.append(f"\n### {block.block_name} ({block.file_name})")
        lines.append(f"Summary: {block.summary}")
        if block.table_refs:
            refs = ", ".join(f"{r.table} ({r.role})" for r in block.table_refs)
            lines.append(f"Tables: {refs}")
    return "\n".join(lines)


def _build_entity_to_aggregate_mapping_guide(report: ParsedReport) -> str:
    """Entity Bean → Aggregate 매핑 가이드 (Aggregates Phase용).

    Entity Bean이 반드시 1:1로 Aggregate가 되는 것은 아님.
    FK 관계를 통해 Root Aggregate vs Value Object/참조 관계를 구분하는 가이드.
    """
    entity_beans = report.get_entity_beans()
    if not entity_beans:
        return ""

    lines: list[str] = [
        "## Entity Bean → Aggregate Mapping Guide",
        "",
        "IMPORTANT: Not every Entity Bean becomes an Aggregate Root.",
        "- Entity Beans with INDEPENDENT lifecycle → Aggregate Root candidates",
        "- Entity Beans referenced via FK (child tables) → Value Object or part of parent Aggregate",
        "- Entity Beans with only PK columns referencing other tables → likely join/association tables, NOT aggregates",
        "",
        "### FK-based Ownership Analysis:",
    ]

    # Analyze FK relationships to determine ownership
    for eb in entity_beans:
        agg_name = eb.name[:-4] if eb.name.endswith("Bean") else eb.name
        table = report.get_table_for_entity(eb.name)
        if not table:
            continue

        # Check incoming FKs (other tables pointing to this one)
        incoming_fks = [
            fk for fk in report.column_level_fks
            if fk.target_column.startswith(f"{table.name}.")
        ]
        # Check outgoing FKs (this table pointing to others)
        outgoing_fks = [
            fk for fk in report.column_level_fks
            if fk.source_column.startswith(f"{table.name}.")
        ]

        ownership_hint = "Aggregate Root candidate"
        if outgoing_fks and not incoming_fks:
            ownership_hint = "References other entities — might be Value Object or child of parent Aggregate"
        elif incoming_fks and not outgoing_fks:
            ownership_hint = "Referenced by others — strong Aggregate Root candidate"

        fk_details = []
        for fk in outgoing_fks:
            fk_details.append(f"  → references {fk.target_column}")
        for fk in incoming_fks:
            fk_details.append(f"  ← referenced by {fk.source_column}")

        lines.append(f"\n- **{agg_name}** ({table.name}): {ownership_hint}")
        lines.extend(fk_details)

    return "\n".join(lines)


def _build_business_rules_text(report: ParsedReport) -> str:
    """비즈니스 규칙 추출 (GWT Phase용).

    Entity Bean의 상태 상수, 유효성 검증 메서드, 조건부 로직 등에서 추론.
    """
    entity_beans = report.get_entity_beans()
    session_beans = report.get_session_beans()
    lines: list[str] = []

    for eb in entity_beans:
        agg_name = eb.name[:-4] if eb.name.endswith("Bean") else eb.name
        rules: list[str] = []

        # Status/state fields → state transition rules
        status_fields = [f for f in eb.fields if "STATUS" in f.name.upper() or "STATE" in f.name.upper()]
        if status_fields:
            for f in status_fields:
                rules.append(f"State field '{f.name}' controls lifecycle transitions")

        # Validation/check methods
        for m in eb.methods:
            if not _is_business_method(m.name):
                continue
            name_lower = m.name.lower()
            if any(kw in name_lower for kw in ("valid", "check", "verify", "can", "is_", "has_")):
                rules.append(f"Validation: {m.name} — {m.summary}")

        if rules:
            lines.append(f"\n### {agg_name}")
            for r in rules:
                lines.append(f"  - {r}")

    # Session Bean business logic hints
    for sb in session_beans:
        sb_rules: list[str] = []
        for m in sb.methods:
            if not _is_business_method(m.name):
                continue
            # Methods with conditional/validation logic
            if m.summary and any(kw in m.summary.lower() for kw in ("검증", "확인", "조건", "제한", "필수", "validate", "check", "restrict", "require")):
                sb_rules.append(f"{m.name}: {m.summary}")
        if sb_rules:
            lines.append(f"\n### {sb.name} (Service Rules)")
            for r in sb_rules:
                lines.append(f"  - {r}")

    return "\n".join(lines) or "(no business rules detected)"


def _build_command_ownership_guide(report: ParsedReport) -> str:
    """Command 소유 가이드 (Commands Phase용).

    어떤 Session Bean 메서드가 어떤 Entity Bean을 조작하는지 매핑.
    Cross-aggregate command 중복 방지 힌트.
    """
    session_beans = report.get_session_beans()
    if not session_beans:
        return ""

    lines: list[str] = [
        "## Command Ownership Guide",
        "",
        "IMPORTANT: Avoid creating duplicate Commands across Aggregates.",
        "- A Command should belong to the Aggregate whose state it primarily changes",
        "- If a Session Bean method calls multiple Entity Beans, the Command belongs to the PRIMARY target entity",
        "- Cross-aggregate coordination should be modeled as Policy (event → command), not duplicate Commands",
        "",
    ]

    for sb in session_beans:
        assocs = [r.target for r in sb.uml_relations if r.relation_type == "ASSOCIATION"]
        cmd_methods = [m for m in sb.methods if m.role == "command" and _is_business_method(m.name)]
        if not cmd_methods:
            continue

        lines.append(f"### {sb.name}")
        lines.append(f"  Associated Entities: {', '.join(assocs)}")
        for m in cmd_methods:
            # Try to determine which entity the method primarily affects
            target_hint = ""
            if m.summary:
                for assoc in assocs:
                    entity_short = assoc[:-4] if assoc.endswith("Bean") else assoc
                    if entity_short.lower() in m.summary.lower() or assoc.lower() in m.summary.lower():
                        target_hint = f" → primarily affects {entity_short}"
                        break
            lines.append(f"  - {m.name}: {m.summary}{target_hint}")

    return "\n".join(lines)


# ─── Phase-specific context builders ─────────────────────────────────────

def get_per_session_bean_us_contexts(report: ParsedReport) -> list[tuple[str, str]]:
    """Session Bean별 개별 US 생성 컨텍스트를 반환.

    Returns:
        List of (session_bean_name, context_text) tuples.
        각 SB의 비즈니스 메서드 + 관련 Entity Bean 정보만 포함.
    """
    session_beans = report.get_session_beans()
    if not session_beans:
        return []

    # 공통 시스템 개요 (간략)
    overview_text = _build_system_overview(report)
    tables_text = _build_tables_fk_text(report)

    results: list[tuple[str, str]] = []
    for sb in session_beans:
        # 비즈니스 메서드만 추출 (lifecycle/technical 제외)
        biz_commands = [m for m in sb.methods if m.role == "command" and _is_business_method(m.name)]
        biz_queries = [m for m in sb.methods if m.role in ("query", "getter") and _is_business_method(m.name)]

        # entityToDTO, entitiesToDTOs, generateId 같은 유틸리티 메서드 제외
        _util_names = {"entityToDTO", "entitiesToDTOs", "generateId",
                       "ledgerEntityToDTO", "delinquencyEntityToDTO",
                       "delinquencyEntitiesToDTOs"}
        biz_commands = [m for m in biz_commands if m.name not in _util_names]

        if not biz_commands and not biz_queries:
            continue

        # 관련 Entity Bean 식별 (ASSOCIATION 관계)
        assoc_entities = [r.target for r in sb.uml_relations if r.relation_type == "ASSOCIATION"]
        related_ebs = []
        for eb in report.get_entity_beans():
            if eb.name in assoc_entities:
                related_ebs.append(eb)

        # Context 구성
        lines: list[str] = [
            f"## Session Bean: {sb.name}",
            f"Stereotype: {sb.stereotype}",
            f"Description: {sb.comment or '(none)'}",
            "",
            "### Business Command Methods (state-changing operations):",
        ]
        for m in biz_commands:
            lines.append(f"  - {m.name}{m.signature}: {m.summary or ''}")
        if not biz_commands:
            lines.append("  (none)")

        lines.append("")
        lines.append("### Query/Getter Methods (read-only operations → ReadModel candidates, NOT Commands):")
        for m in biz_queries:
            lines.append(f"  - {m.name}{m.signature}: {m.summary or ''}")
        if not biz_queries:
            lines.append("  (none)")

        if related_ebs:
            lines.append("")
            lines.append("### Related Entity Beans (domain entities this service manages):")
            for eb in related_ebs:
                agg_name = eb.name[:-4] if eb.name.endswith("Bean") else eb.name
                table = report.get_table_for_entity(eb.name)
                table_info = f" → Table: {table.name}" if table else ""
                fields = [f.name for f in eb.fields[:10]]
                lines.append(f"  - {agg_name} ({eb.name}){table_info}")
                if fields:
                    lines.append(f"    Fields: {', '.join(fields)}")

        lines.extend([
            "",
            "### System Context:",
            overview_text,
            "",
            "### Tables:",
            tables_text,
            "",
            "### GUIDELINES:",
            "- Generate User Stories ONLY for the business methods listed above",
            "- Each business command method should produce at least one User Story",
            "- Each query method may produce a User Story for data retrieval needs",
            "- Do NOT generate User Stories for EJB lifecycle, DTO conversion, or ID generation methods",
            "- Focus on the BUSINESS CAPABILITY that each method provides to end users",
        ])

        results.append((sb.name, "\n".join(lines)))

    return results


def get_user_stories_context(report: ParsedReport, max_tokens: int = REPORT_CONTEXT_MAX_TOKENS) -> str:
    """User Stories Phase: 전체 보고서 요약 → US 역생성 컨텍스트.

    EJB lifecycle methods are excluded to prevent non-business US generation.
    """
    sections = [
        "## Legacy System Overview",
        _build_system_overview(report),
        "\n## Packages",
        _build_packages_text(report),
        "\n## Entity Beans (Domain Entities)",
        _build_entity_beans_text(report),
        "\n## Session Beans (Services) — Business Methods Only",
        _build_session_beans_text(report),
        "\n## Database Tables & FK Relationships",
        _build_tables_fk_text(report),
        "\n## Service Call Chains",
        _build_call_chains_text(report),
        "\n## GUIDELINES FOR USER STORY GENERATION",
        (
            "This is a legacy EJB system analysis. Generate User Stories for the BUSINESS CAPABILITIES only.\n"
            "DO NOT generate User Stories for:\n"
            "- EJB lifecycle callbacks (ejbCreate, ejbRemove, ejbActivate, ejbPassivate, ejbLoad, ejbStore)\n"
            "- Container-managed persistence (CMP) operations\n"
            "- JNDI lookups, DataSource management, connection pooling\n"
            "- Deployment descriptor configurations\n"
            "- Transaction management infrastructure\n"
            "\n"
            "DO generate User Stories for:\n"
            "- Business operations visible to end users (loan application, payment processing, etc.)\n"
            "- Data query and reporting needs\n"
            "- State transitions that reflect business processes\n"
            "- Cross-service business workflows"
        ),
    ]
    text = "\n".join(sections)
    return _truncate_to_tokens(text, max_tokens)


def get_bounded_contexts_context(report: ParsedReport, max_tokens: int = REPORT_CONTEXT_MAX_TOKENS) -> str:
    """BC Phase: Entity 관계, 패키지 구조, 호출 체인."""
    sections = [
        "## Legacy System — Domain Structure Reference",
        _build_system_overview(report),
        "\n## Packages",
        _build_packages_text(report),
        "\n## Entity Beans & Table Mappings",
        _build_entity_beans_text(report),
        "\n## Session Beans & Entity Associations",
        _build_session_beans_text(report),
        "\n## FK Relationships (domain coupling signals)",
        _build_tables_fk_text(report),
        "\n## Cross-Service Call Chains (BC boundary signals)",
        _build_call_chains_text(report),
        "\n## BC IDENTIFICATION GUIDELINES FOR LEGACY SYSTEMS",
        (
            "- Group by BUSINESS DOMAIN, not by EJB layer (session/entity/servlet)\n"
            "- Session Beans that share Entity Bean associations likely belong to the same BC\n"
            "- FK clusters between tables suggest a single BC\n"
            "- Cross-service call chains may indicate BC boundaries\n"
            "- Do NOT create a 'Common' or 'Infrastructure' BC for EJB framework classes"
        ),
    ]
    text = "\n".join(sections)
    return _truncate_to_tokens(text, max_tokens)


def get_aggregates_context(report: ParsedReport, max_tokens: int = REPORT_CONTEXT_MAX_TOKENS) -> str:
    """Aggregates Phase: Entity 상세, 테이블 스키마, FK → Root Agg vs VO/Enum 구분."""
    sections = [
        "## Legacy System — Entity & Schema Reference",
        "\n## Entity Bean Details (state, methods)",
        _build_entity_detail_text(report),
        "\n## Table Schemas & FK Relationships",
        _build_tables_fk_text(report),
        "\n## Table Column Details",
        _build_table_columns_text(report),
    ]

    # Add entity-to-aggregate mapping guide
    mapping_guide = _build_entity_to_aggregate_mapping_guide(report)
    if mapping_guide:
        sections.append("\n" + mapping_guide)

    sections.append(
        "\n## AGGREGATE EXTRACTION GUIDELINES FOR LEGACY EJB SYSTEMS\n"
        "- Entity Beans with CMP (Container-Managed Persistence) map to Aggregates\n"
        "- DO NOT create Aggregates for EJB infrastructure classes\n"
        "- Status/state fields in Entity Beans → Enumerations in the Aggregate\n"
        "- FK relationships indicate Aggregate boundaries:\n"
        "  - Parent table (referenced by FK) → likely Aggregate Root\n"
        "  - Child table (has FK to parent) → likely Value Object or part of parent Aggregate\n"
        "- Entity Bean fields → Aggregate properties (check table columns for complete field list)\n"
        "- If an Entity Bean has fields not parsed in detail, use the Table Column Details as fallback"
    )

    text = "\n".join(sections)
    return _truncate_to_tokens(text, max_tokens)


def get_commands_context(report: ParsedReport, max_tokens: int = REPORT_CONTEXT_MAX_TOKENS) -> str:
    """Commands Phase: Session Bean command 메서드, 상태 전이, 중복 방지 가이드."""
    sections = [
        "## Legacy System — Command Methods Reference",
        "\n## Session Bean Command Methods (business methods only)",
        _build_session_bean_methods_text(report, role_filter="command"),
        "\n## Session Bean Query Methods (NOT Commands — read-only operations)",
        "These are query/getter methods. Do NOT create Commands for these. They should become ReadModels instead.",
        _build_session_bean_methods_text(report, role_filter="query", warn_non_commands=True),
        "\n## Entity State Constants",
        _build_entity_detail_text(report),
    ]

    # Add command ownership guide
    ownership_guide = _build_command_ownership_guide(report)
    if ownership_guide:
        sections.append("\n" + ownership_guide)

    sections.append(
        "\n## COMMAND EXTRACTION GUIDELINES FOR LEGACY EJB SYSTEMS\n"
        "- Map Session Bean BUSINESS methods (not lifecycle) to Commands\n"
        "- Each Command belongs to ONE Aggregate — the one whose state it primarily changes\n"
        "- If multiple Session Beans have similar methods (e.g., both have 'approve'), "
        "create ONE Command on the correct Aggregate, not duplicates\n"
        "- EJB lifecycle methods (ejbCreate, ejbRemove, etc.) are NOT Commands\n"
        "- JNDI lookups, connection management, etc. are NOT Commands\n"
        "- Consider Entity Bean state transitions to identify missing Commands"
    )

    text = "\n".join(sections)
    return _truncate_to_tokens(text, max_tokens)


def get_events_context(report: ParsedReport, max_tokens: int = REPORT_CONTEXT_MAX_TOKENS) -> str:
    """Events Phase: 상태 상수, summarized code, 상태 전이 메서드."""
    sections = [
        "## Legacy System — State Transition Reference",
        "\n## Entity Bean State & Methods",
        _build_entity_detail_text(report),
        "\n## Session Bean Command Methods (state-changing flows)",
        _build_session_bean_methods_text(report, role_filter="command"),
    ]
    text = "\n".join(sections)
    return _truncate_to_tokens(text, max_tokens)


def get_policies_context(report: ParsedReport, max_tokens: int = REPORT_CONTEXT_MAX_TOKENS) -> str:
    """Policies Phase: cross-BC 호출 체인, 서비스 간 의존성."""
    sections = [
        "## Legacy System — Cross-Service Interactions Reference",
        "\n## Service Call Chains",
        _build_call_chains_text(report),
        "\n## Session Beans & Entity Associations",
        _build_session_beans_text(report),
    ]
    text = "\n".join(sections)
    return _truncate_to_tokens(text, max_tokens)


def _build_getter_methods_as_readmodel_hints(report: ParsedReport) -> str:
    """Session Bean getter 메서드 → ReadModel 후보 목록."""
    session_beans = report.get_session_beans()
    if not session_beans:
        return "(no getter methods)"
    lines: list[str] = []
    for sb in session_beans:
        getters = [
            m for m in sb.methods
            if m.role == "getter" and _is_business_method(m.name)
            and not m.name.startswith("get") or (m.name.startswith("get") and len(m.name) > 3)
        ]
        if not getters:
            continue
        lines.append(f"\n### {sb.name}")
        for m in getters:
            lines.append(f"  - {m.name}{m.signature}: {m.summary}")
    return "\n".join(lines) or "(no getter methods)"


def _build_table_access_summary(report: ParsedReport) -> str:
    """Data flow table access matrix → ReadModel data source hints."""
    if not report.data_flow.table_access_matrix:
        return "(no table access data)"
    lines: list[str] = []
    for ta in report.data_flow.table_access_matrix:
        lines.append(f"- {ta.table}: {ta.access_type} by {ta.evidence}")
    return "\n".join(lines)


def get_readmodels_context(report: ParsedReport, max_tokens: int = REPORT_CONTEXT_MAX_TOKENS) -> str:
    """ReadModels Phase: Session Bean query 메서드, 테이블 구조, SQL 쿼리 블록."""
    sections = [
        "## Legacy System — Query Methods Reference",
        "\n## Session Bean Query Methods (business queries only)",
        _build_session_bean_methods_text(report, role_filter="query"),
        "\n## Session Bean Getter Methods (potential ReadModel candidates)",
        "These getter methods retrieve data — each may correspond to a ReadModel.",
        _build_getter_methods_as_readmodel_hints(report),
        "\n## Table Access Patterns (which class reads/writes which table)",
        _build_table_access_summary(report),
        "\n## Table Schemas",
        _build_tables_fk_text(report),
        "\n## SQL Query Blocks",
        _build_sql_queries_text(report),
        "\n## READMODEL GUIDELINES FOR LEGACY EJB SYSTEMS\n"
        "- Session Bean QUERY and GETTER methods that return business data map to ReadModels\n"
        "- SQL query blocks reveal actual data access patterns\n"
        "- Each ReadModel should represent a specific view/query need\n"
        "- Include table column information as ReadModel properties\n"
        "- Do NOT create ReadModels for EJB lifecycle queries (ejbFindByPrimaryKey, etc.)\n"
        "- Consider creating ReadModels for: list views, detail views, search results, aggregated reports\n"
        "- Use table access patterns to identify which tables a ReadModel should join",
    ]
    text = "\n".join(sections)
    return _truncate_to_tokens(text, max_tokens)


def get_properties_context(report: ParsedReport, max_tokens: int = REPORT_CONTEXT_MAX_TOKENS) -> str:
    """Properties Phase: 테이블 컬럼 상세, 데이터 타입, Entity Bean 필드 fallback."""
    sections = [
        "## Legacy System — Table Column Reference",
        "\n## Table Column Details",
        _build_table_columns_text(report),
        "\n## FK Relationships",
        _build_tables_fk_text(report),
    ]

    # Add Entity Bean fields as fallback for tables without column details
    entity_beans = report.get_entity_beans()
    entity_fields_lines: list[str] = []
    for eb in entity_beans:
        if not eb.fields:
            continue
        table = report.get_table_for_entity(eb.name)
        # If table has no columns parsed, use Entity Bean fields as fallback
        if table and not table.columns:
            agg_name = eb.name[:-4] if eb.name.endswith("Bean") else eb.name
            entity_fields_lines.append(f"\n### {agg_name} (from Entity Bean fields — table {table.name} has no parsed columns)")
            for f in eb.fields:
                entity_fields_lines.append(f"  - {f.name}: {f.type} — {f.description or ''}")

    if entity_fields_lines:
        sections.append("\n## Entity Bean Fields (fallback for unparsed table columns)")
        sections.extend(entity_fields_lines)

    sections.append(
        "\n## PROPERTY EXTRACTION GUIDELINES\n"
        "- Use Table Column Details as the PRIMARY source for property names and types\n"
        "- If a table has no parsed columns, use Entity Bean fields as fallback\n"
        "- Map SQL data types to appropriate domain types (VARCHAR→String, INTEGER→Integer, etc.)\n"
        "- PK columns → mark as identifier properties\n"
        "- FK columns → reference properties (Value Object references)\n"
        "- Status/state columns → Enumeration type properties"
    )

    text = "\n".join(sections)
    return _truncate_to_tokens(text, max_tokens)


def get_gwt_context(report: ParsedReport, max_tokens: int = REPORT_CONTEXT_MAX_TOKENS) -> str:
    """GWT Phase: 비즈니스 규칙, 상태 전이, 유효성 검증 로직.

    GWT 테스트 케이스 생성을 위한 도메인 지식 컨텍스트.
    """
    sections = [
        "## Legacy System — Business Rules & Validation Reference",
        "\n## Business Rules (from Entity/Session Bean analysis)",
        _build_business_rules_text(report),
        "\n## Entity Bean State & Transitions",
        _build_entity_detail_text(report),
        "\n## GWT GENERATION GUIDELINES FOR LEGACY SYSTEMS\n"
        "- Use Entity Bean state constants to generate realistic test values\n"
        "- Status field transitions suggest happy/unhappy path scenarios\n"
        "- Validation methods in Entity Beans → generate negative test cases\n"
        "- Business rules from Session Bean logic → boundary condition tests\n"
        "- Use actual field names and types from the legacy system for realistic fieldValues\n"
        "- Generate at least one happy path and one error/edge case per Command",
    ]
    text = "\n".join(sections)
    return _truncate_to_tokens(text, max_tokens)
