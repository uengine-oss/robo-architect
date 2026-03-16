"""
레거시 시스템 분석 보고서 파싱 결과 데이터 모델.

Legacy Modernizer가 생성한 구조화된 마크다운 보고서를 파싱한 결과를 담는 모델.
이벤트 스토밍 요소로의 매핑에 사용된다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Section 1: 시스템 개요 ──


@dataclass
class SystemOverview:
    """시스템 전체 조감도 (Section 1)."""

    description: str = ""
    architecture_diagram: str = ""
    # 수치 요약
    package_count: int = 0
    class_count: int = 0
    interface_count: int = 0
    enum_count: int = 0
    external_count: int = 0
    method_count: int = 0
    field_count: int = 0
    table_count: int = 0
    column_count: int = 0


# ── Section 2: 패키지 구조 ──


@dataclass
class PackageInfo:
    """패키지 정보 (Section 2)."""

    name: str = ""
    full_path: str = ""
    layer: str = ""  # "servlet", "session", "entity", "util", "common"
    description: str = ""
    class_count: int = 0


# ── Section 3: 클래스 상세 ──


@dataclass
class MethodInfo:
    """메서드 정보."""

    name: str = ""
    signature: str = ""
    return_type: str = ""
    role: str = ""  # "command", "query", "lifecycle", "getter", "setter"
    summary: str = ""


@dataclass
class FieldInfo:
    """필드 정보."""

    name: str = ""
    type: str = ""
    modifiers: str = ""
    annotation: str = ""
    description: str = ""


@dataclass
class UMLRelation:
    """UML 관계."""

    direction: str = ""  # "->", "<-"
    relation_type: str = ""  # "IMPLEMENTS", "EXTENDS", "ASSOCIATION", "DEPENDENCY"
    target: str = ""
    target_scope: str = ""  # "INTERNAL", "EXTERNAL"
    note: str = ""


@dataclass
class CallInfo:
    """호출 관계."""

    target: str = ""  # "ClassName.methodName(params)"
    scope: str = ""  # "internal", "external"


@dataclass
class TableAccessInfo:
    """테이블 접근 정보."""

    table: str = ""
    access_type: str = ""  # "FROM" (읽기), "WRITES" (쓰기)
    evidence: str = ""


@dataclass
class ClassDetail:
    """클래스 상세 정보 (Section 3)."""

    # 기본 정보
    name: str = ""
    fqn: str = ""
    package: str = ""
    class_type: str = ""  # "CLASS", "INTERFACE", "ENUM"
    scope: str = ""  # "INTERNAL", "EXTERNAL"
    stereotype: str = ""  # "Session Bean (Stateless)", "Entity Bean (CMP)", etc.
    file_info: str = ""
    modifiers: str = ""
    annotations: str = ""
    implements: list[str] = field(default_factory=list)
    extends: Optional[str] = None
    comment: str = ""
    summary: str = ""

    # 매핑 정보 (Entity Bean의 경우)
    mapped_table: Optional[str] = None

    # 상세
    methods: list[MethodInfo] = field(default_factory=list)
    fields: list[FieldInfo] = field(default_factory=list)
    uml_relations: list[UMLRelation] = field(default_factory=list)
    calls_out: list[CallInfo] = field(default_factory=list)
    called_by: list[CallInfo] = field(default_factory=list)
    table_access: list[TableAccessInfo] = field(default_factory=list)
    summarized_code: str = ""


# ── Section 4: 외부 의존성 ──


@dataclass
class ExternalDep:
    """외부 의존성 (Section 4)."""

    name: str = ""
    class_type: str = ""  # "CLASS", "INTERFACE"
    relation: str = ""  # "IMPLEMENTS", "EXTENDS", "DEPENDENCY"
    used_by: list[str] = field(default_factory=list)


# ── Section 5: 설정 파일 / 쿼리 블록 ──


@dataclass
class ConfigBlockRef:
    """설정/쿼리 블록의 테이블 참조."""

    table: str = ""
    role: str = ""  # "mapping", "source", "target"
    confidence: str = ""
    evidence: str = ""


@dataclass
class ConfigBlock:
    """설정/쿼리 블록 (Section 5)."""

    file_name: str = ""
    file_path: str = ""
    block_name: str = ""
    block_type: str = ""  # "entity-descriptor", "session-descriptor", "security", "sql"
    line_range: str = ""
    summary: str = ""
    table_refs: list[ConfigBlockRef] = field(default_factory=list)


# ── Section 6: 데이터베이스 스키마 ──


@dataclass
class ColumnInfo:
    """테이블 컬럼 정보."""

    name: str = ""
    data_type: str = ""
    nullable: bool = True
    is_pk: bool = False
    description: str = ""


@dataclass
class FKRelation:
    """FK 관계."""

    direction: str = ""  # "->", "<-"
    target_table: str = ""
    fk_type: str = ""
    confidence: str = ""  # "HIGH", "MEDIUM", "LOW"
    evidence: str = ""
    source_column: Optional[str] = None
    target_column: Optional[str] = None


@dataclass
class TableSchema:
    """테이블 스키마 (Section 6)."""

    name: str = ""
    schema_name: str = ""
    mapped_entity: Optional[str] = None
    mapping_type: str = ""  # "CMP", etc.
    summary: str = ""
    columns: list[ColumnInfo] = field(default_factory=list)
    fk_relations: list[FKRelation] = field(default_factory=list)
    access_relations: list[TableAccessInfo] = field(default_factory=list)


# ── Section 7: 데이터 흐름 ──


@dataclass
class CallChain:
    """호출 체인 (Section 7.2)."""

    flow_name: str = ""  # e.g. "대출 심사 흐름"
    chain_text: str = ""  # 원본 텍스트


@dataclass
class CallRelation:
    """전체 호출 관계 (Section 7.3)."""

    caller: str = ""
    callee: str = ""
    scope: str = ""  # "internal", "external"


@dataclass
class DataFlow:
    """데이터 흐름 (Section 7)."""

    table_access_matrix: list[TableAccessInfo] = field(default_factory=list)
    call_chains: list[CallChain] = field(default_factory=list)
    call_relations: list[CallRelation] = field(default_factory=list)


# ── Section 6 하단: 컬럼 레벨 FK ──


@dataclass
class ColumnLevelFK:
    """컬럼 레벨 FK 관계."""

    source_column: str = ""  # "TABLE.column"
    target_column: str = ""  # "TABLE.column"
    fk_type: str = ""
    confidence: str = ""


# ── 최종 파싱 결과 ──


@dataclass
class ParsedReport:
    """분석 보고서 전체 파싱 결과."""

    # 메타데이터
    title: str = ""
    target_system: str = ""
    pipeline: str = ""
    generated_date: str = ""

    # 섹션별 데이터
    overview: SystemOverview = field(default_factory=SystemOverview)
    packages: list[PackageInfo] = field(default_factory=list)
    classes: list[ClassDetail] = field(default_factory=list)
    external_deps: list[ExternalDep] = field(default_factory=list)
    config_blocks: list[ConfigBlock] = field(default_factory=list)
    tables: list[TableSchema] = field(default_factory=list)
    data_flow: DataFlow = field(default_factory=DataFlow)
    column_level_fks: list[ColumnLevelFK] = field(default_factory=list)

    # ── 헬퍼 메서드 ──

    def get_session_beans(self) -> list[ClassDetail]:
        """Session Bean 클래스 목록 반환."""
        return [c for c in self.classes if "Session Bean" in c.stereotype]

    def get_entity_beans(self) -> list[ClassDetail]:
        """Entity Bean 클래스 목록 반환."""
        return [c for c in self.classes if "Entity Bean" in c.stereotype]

    def get_servlets(self) -> list[ClassDetail]:
        """Servlet 클래스 목록 반환."""
        return [c for c in self.classes if c.package.endswith(".servlet") or "Servlet" in c.name]

    def get_command_methods(self, class_name: str) -> list[MethodInfo]:
        """특정 클래스의 command 역할 메서드 반환."""
        for c in self.classes:
            if c.name == class_name:
                return [m for m in c.methods if m.role == "command"]
        return []

    def get_query_methods(self, class_name: str) -> list[MethodInfo]:
        """특정 클래스의 query 역할 메서드 반환."""
        for c in self.classes:
            if c.name == class_name:
                return [m for m in c.methods if m.role == "query"]
        return []

    def get_table_for_entity(self, entity_name: str) -> Optional[TableSchema]:
        """Entity Bean 이름에 매핑된 테이블 반환."""
        for t in self.tables:
            if t.mapped_entity == entity_name:
                return t
        return None

    def get_class_by_name(self, name: str) -> Optional[ClassDetail]:
        """클래스 이름으로 ClassDetail 검색."""
        for c in self.classes:
            if c.name == name:
                return c
        return None

    def get_associations_for_class(self, class_name: str) -> list[UMLRelation]:
        """특정 클래스의 ASSOCIATION 관계 반환."""
        cls = self.get_class_by_name(class_name)
        if not cls:
            return []
        return [r for r in cls.uml_relations if r.relation_type == "ASSOCIATION"]
