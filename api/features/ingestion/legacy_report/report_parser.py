"""
레거시 시스템 분석 보고서 마크다운 파서.

Legacy Modernizer가 생성한 구조화된 마크다운 보고서를 ParsedReport 객체로 변환한다.
두 가지 보고서 포맷을 지원한다:
  - v1 (템플릿): ### 3.N ClassName, **제목** 서브섹션
  - v2 (최종): ### ClassName, #### 제목 서브섹션
"""

from __future__ import annotations

import re
from typing import Optional

from api.features.ingestion.legacy_report.report_models import (
    CallChain,
    CallInfo,
    CallRelation,
    ClassDetail,
    ColumnInfo,
    ColumnLevelFK,
    ConfigBlock,
    ConfigBlockRef,
    DataFlow,
    ExternalDep,
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
from api.platform.observability.smart_logger import SmartLogger


def parse_legacy_report(content: str) -> ParsedReport:
    """분석 보고서 마크다운 전체를 파싱하여 ParsedReport 반환."""
    report = ParsedReport()

    # 메타데이터 파싱
    _parse_metadata(content, report)

    # 포맷 버전 감지
    is_v2 = _detect_format_v2(content)

    # 섹션 분리 (## N. 패턴)
    sections = _split_sections(content)

    for section_num, section_text in sections.items():
        if section_num == 1:
            report.overview = _parse_overview(section_text, is_v2)
        elif section_num == 2:
            report.packages = _parse_packages(section_text, is_v2)
        elif section_num == 3:
            report.classes = _parse_classes(section_text, is_v2)
        elif section_num == 4:
            report.external_deps = _parse_external_deps(section_text, is_v2)
        elif section_num == 5:
            if is_v2:
                report.config_blocks = _parse_artifact_chunks(section_text)
            else:
                report.config_blocks = _parse_config_blocks(section_text)
        elif section_num == 6:
            if is_v2:
                # v2: Section 6 is empty ("설정 파일 없음"), skip
                pass
            else:
                tables, col_fks = _parse_db_schema(section_text, is_v2)
                report.tables = tables
                report.column_level_fks = col_fks
        elif section_num == 7:
            if is_v2:
                # v2: Section 7 is DB schema
                tables, col_fks = _parse_db_schema(section_text, is_v2)
                report.tables = tables
                report.column_level_fks = col_fks
            else:
                report.data_flow = _parse_data_flow(section_text)
        elif section_num == 9:
            if is_v2:
                # v2: Section 9 is 횡단 분석 (cross-cutting analysis)
                report.data_flow = _parse_cross_analysis(section_text)

    # Section 3에서 매핑된 테이블 정보를 ClassDetail에 보강
    _enrich_class_table_mapping(report)

    return report


def _detect_format_v2(content: str) -> bool:
    """보고서 포맷 v2 여부를 감지한다.

    v2 특징: #### 서브섹션 사용, ### 3.N 패턴 없음, 섹션 9 횡단 분석 존재.
    """
    has_h4_subsections = bool(re.search(r"^#### (기본 정보|요약|메서드|필드)", content, re.MULTILINE))
    has_v1_class_pattern = bool(re.search(r"^### 3\.\d+\s+", content, re.MULTILINE))
    has_cross_analysis = bool(re.search(r"## 9\.\s*횡단 분석", content))
    return has_h4_subsections and not has_v1_class_pattern or has_cross_analysis


# ── 유틸리티 ──


def _split_sections(content: str) -> dict[int, str]:
    """## N. 패턴으로 섹션을 분리. 반환: {섹션번호: 섹션텍스트}"""
    pattern = re.compile(r"^## (\d+)\.\s", re.MULTILINE)
    matches = list(pattern.finditer(content))

    sections: dict[int, str] = {}
    for i, m in enumerate(matches):
        num = int(m.group(1))
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections[num] = content[start:end]

    return sections


def _parse_table_rows(text: str) -> list[list[str]]:
    """마크다운 테이블에서 데이터 행만 추출. 헤더와 구분선 제외."""
    rows: list[list[str]] = []
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        # 구분선 (| --- | --- |) 건너뛰기
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if all(re.match(r"^[-:]+$", c) for c in cells if c):
            continue
        rows.append(cells)
    # 첫 행이 헤더인 경우 제거 (보통 두 번째 행이 구분선이므로 이미 처리됨)
    return rows[1:] if rows else []  # 헤더 행 제외


def _extract_code_block(text: str) -> str:
    """```로 감싼 코드 블록의 내용을 추출."""
    match = re.search(r"```[\w]*\n(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _clean_text(text: str) -> str:
    """마크다운 강조, 코드 마크 등을 제거."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


# ── 메타데이터 ──


def _parse_metadata(content: str, report: ParsedReport) -> None:
    """보고서 상단 메타데이터 파싱."""
    # 제목
    m = re.search(r"^# (.+)$", content, re.MULTILINE)
    if m:
        report.title = m.group(1).strip()

    # > **분석 대상**: ...
    m = re.search(r"\*\*분석 대상\*\*\s*[:：]\s*(.+?)$", content, re.MULTILINE)
    if m:
        report.target_system = m.group(1).strip()

    # **파이프라인**: ... | **생성일**: ...
    m = re.search(r"\*\*파이프라인\*\*\s*[:：]\s*(.+?)\s*\|", content, re.MULTILINE)
    if m:
        report.pipeline = m.group(1).strip()
    m = re.search(r"\*\*생성일\*\*\s*[:：]\s*(.+?)$", content, re.MULTILINE)
    if m:
        report.generated_date = m.group(1).strip()


# ── Section 1: 시스템 개요 ──


def _parse_overview(text: str, is_v2: bool = False) -> SystemOverview:
    overview = SystemOverview()

    if is_v2:
        return _parse_overview_v2(text, overview)

    # v1 로직
    lines = text.split("\n")
    desc_lines = []
    for line in lines:
        if line.startswith("## ") or line.startswith("### ") or line.startswith("```") or line.startswith("|"):
            break
        if line.strip() and not line.startswith(">"):
            desc_lines.append(line.strip())
    overview.description = " ".join(desc_lines)

    # 아키텍처 다이어그램
    overview.architecture_diagram = _extract_code_block(text)

    # 수치 요약 테이블
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 3:
            continue
        item = _clean_text(row[1]).strip()
        try:
            val_text = row[2].strip()
            if "/" in val_text and "클래스" in item.lower() or "인터페이스" in item.lower():
                parts = [int(v.strip()) for v in val_text.split("/")]
                if len(parts) >= 3:
                    overview.class_count = parts[0]
                    overview.interface_count = parts[1]
                    overview.enum_count = parts[2]
                continue
            val = int(val_text.replace(",", ""))
        except (ValueError, IndexError):
            continue

        item_lower = item.lower()
        if "패키지" in item_lower:
            overview.package_count = val
        elif "외부" in item_lower:
            overview.external_count = val
        elif "메서드" in item_lower:
            overview.method_count = val
        elif "필드" in item_lower:
            overview.field_count = val
        elif "테이블" in item_lower:
            overview.table_count = val
        elif "컬럼" in item_lower:
            overview.column_count = val

    return overview


def _parse_overview_v2(text: str, overview: SystemOverview) -> SystemOverview:
    """v2 포맷 시스템 개요 파싱: 노드 통계 / 관계 통계 / 스테레오타입 분포."""
    # ### 1.1. 노드 통계
    node_section = re.search(r"노드 통계.*?\n((?:\|.*\n)+)", text, re.DOTALL)
    if node_section:
        rows = _parse_table_rows(node_section.group(0))
        for row in rows:
            if len(row) < 2:
                continue
            node_type = row[0].strip().upper()
            try:
                count = int(row[1].strip().replace(",", ""))
            except ValueError:
                continue
            if node_type == "METHOD":
                overview.method_count = count
            elif node_type == "FIELD":
                overview.field_count = count
            elif node_type == "CLASS":
                overview.class_count = count
            elif node_type == "COLUMN":
                overview.column_count = count
            elif node_type == "PACKAGE":
                overview.package_count = count
            elif node_type == "TABLE":
                overview.table_count = count

    # 설명 조합
    overview.description = (
        f"Classes: {overview.class_count}, Methods: {overview.method_count}, "
        f"Fields: {overview.field_count}, Tables: {overview.table_count}"
    )

    return overview


# ── Section 2: 패키지 구조 ──


def _parse_packages(text: str, is_v2: bool = False) -> list[PackageInfo]:
    if is_v2:
        return _parse_packages_v2(text)

    packages: list[PackageInfo] = []

    # v1: 트리 구조 파싱
    tree_pattern = re.compile(
        r"[├└]──\s+(\w+)/\s+([\w\s가-힣]+?)\s{2,}(.+?)$",
        re.MULTILINE,
    )

    root_match = re.search(r"^([\w.]+)$", text, re.MULTILINE)
    root_pkg = root_match.group(1) if root_match else ""

    for m in tree_pattern.finditer(text):
        pkg_name = m.group(1).strip()
        layer = m.group(2).strip()
        desc = m.group(3).strip()

        layer_key = ""
        if "웹" in layer:
            layer_key = "servlet"
        elif "비즈니스" in layer:
            layer_key = "session"
        elif "데이터" in layer:
            layer_key = "entity"
        elif "유틸" in layer:
            layer_key = "util"
        elif "공통" in layer:
            layer_key = "common"
        else:
            layer_key = pkg_name

        count_match = re.search(r"(\d+)개", desc)
        count = int(count_match.group(1)) if count_match else 0

        packages.append(PackageInfo(
            name=pkg_name,
            full_path=f"{root_pkg}.{pkg_name}" if root_pkg else pkg_name,
            layer=layer_key,
            description=desc,
            class_count=count,
        ))

    # 하위 섹션 테이블에서 추가 정보 보강
    subsections = re.split(r"^### ", text, flags=re.MULTILINE)
    for sub in subsections[1:]:
        pkg_match = re.search(r"`([\w.]+)`", sub)
        if not pkg_match:
            continue
        full_path = pkg_match.group(1)
        for pkg in packages:
            if pkg.full_path == full_path or full_path.endswith(f".{pkg.name}"):
                pkg.full_path = full_path
                break

    return packages


def _parse_packages_v2(text: str) -> list[PackageInfo]:
    """v2 포맷 패키지 파싱: ### package.name + 클래스 테이블."""
    packages: list[PackageInfo] = []

    subsections = re.split(r"^### ", text, flags=re.MULTILINE)
    for sub in subsections[1:]:
        lines = sub.strip().split("\n")
        if not lines:
            continue

        full_path = lines[0].strip()
        if not full_path or full_path.startswith("|"):
            continue

        # 패키지명 (마지막 segment)
        name = full_path.rsplit(".", 1)[-1] if "." in full_path else full_path

        # 계층 추론
        layer_key = ""
        if ".dto" in full_path:
            layer_key = "dto"
        elif ".entity" in full_path:
            layer_key = "entity"
        elif ".session" in full_path:
            layer_key = "session"
        elif ".web" in full_path or ".servlet" in full_path:
            layer_key = "servlet"
        elif ".util" in full_path:
            layer_key = "util"
        elif ".exception" in full_path:
            layer_key = "exception"
        else:
            layer_key = name

        # 클래스 테이블에서 클래스 수 카운트
        rows = _parse_table_rows(sub)
        # "-" 만 있는 행 제외
        class_count = sum(1 for r in rows if len(r) >= 2 and r[0].strip() != "-")

        packages.append(PackageInfo(
            name=name,
            full_path=full_path,
            layer=layer_key,
            description=f"{class_count} classes in {full_path}",
            class_count=class_count,
        ))

    return packages


# ── Section 3: 클래스 상세 ──


def _parse_classes(text: str, is_v2: bool = False) -> list[ClassDetail]:
    classes: list[ClassDetail] = []

    if is_v2:
        # v2: ### ClassName 패턴으로 분리 (#### 서브섹션 사용)
        class_sections = re.split(r"^### (?![\d])", text, flags=re.MULTILINE)
        for section in class_sections[1:]:
            cls = _parse_single_class_v2(section)
            if cls and cls.name:
                classes.append(cls)
    else:
        # v1: ### 3.N ClassName 패턴으로 분리
        class_sections = re.split(r"^### 3\.\d+\s+", text, flags=re.MULTILINE)
        for section in class_sections[1:]:
            cls = _parse_single_class(section)
            if cls and cls.name:
                classes.append(cls)

        # "3.3 ~ 3.N 나머지 클래스" 테이블에서 추가 클래스 목록 파싱
        remaining_match = re.search(r"나머지 클래스.*?\n((?:\|.*\n)+)", text)
        if remaining_match:
            rows = _parse_table_rows(remaining_match.group(0))
            existing_names = {c.name for c in classes}
            for row in rows:
                if len(row) >= 4:
                    name = _clean_text(row[1])
                    if name and name not in existing_names and name != "...":
                        classes.append(ClassDetail(
                            name=name,
                            package=f"com.banking.loan.{row[2].strip()}" if len(row) > 2 else "",
                            stereotype=_infer_stereotype(row[2].strip()) if len(row) > 2 else "",
                            summary=row[3].strip() if len(row) > 3 else "",
                        ))

    return classes


def _infer_stereotype(layer: str) -> str:
    """계층명에서 스테레오타입 추론."""
    layer = layer.strip().lower()
    if layer == "entity":
        return "Entity Bean (CMP)"
    elif layer == "session":
        return "Session Bean"
    elif layer == "servlet":
        return "Servlet"
    return ""


def _parse_single_class(section: str) -> Optional[ClassDetail]:
    """v1: 단일 클래스 섹션을 파싱."""
    cls = ClassDetail()

    lines = section.split("\n")
    if not lines:
        return None

    # 클래스 이름 (첫 줄)
    first_line = lines[0].strip()
    cls.name = first_line.split("\n")[0].strip()
    cls.name = re.sub(r"[#>*`]", "", cls.name).strip()

    # 기본 정보 테이블
    basic_info = _extract_subsection(section, "기본 정보")
    if basic_info:
        _parse_class_basic_info(basic_info, cls)

    # 클래스 요약
    summary_section = _extract_subsection(section, "클래스 요약")
    if summary_section:
        quote_lines = [l.lstrip("> ").strip() for l in summary_section.split("\n") if l.strip().startswith(">")]
        cls.summary = " ".join(quote_lines)

    # 메서드 테이블
    method_section = _extract_subsection(section, "메서드")
    if method_section:
        cls.methods = _parse_methods_table(method_section)

    # 필드 테이블
    field_section = _extract_subsection(section, "필드")
    if field_section:
        cls.fields = _parse_fields_table(field_section)

    # UML 관계 테이블
    uml_section = _extract_subsection(section, "UML 관계")
    if uml_section:
        cls.uml_relations = _parse_uml_relations_table(uml_section)

    # 호출 관계
    calls_section = _extract_subsection(section, "호출 관계")
    if not calls_section:
        calls_section = _extract_subsection(section, "호출하는 메서드")
    if calls_section:
        cls.calls_out, cls.called_by = _parse_calls(calls_section)

    called_by_section = _extract_subsection(section, "호출하는 메서드")
    if called_by_section and "호출자" in called_by_section:
        _, called_by = _parse_calls(called_by_section)
        if called_by:
            cls.called_by = called_by

    # 테이블 접근
    table_access_section = _extract_subsection(section, "테이블 접근")
    if table_access_section:
        cls.table_access = _parse_table_access(table_access_section)

    # 요약 코드
    code_section = _extract_subsection(section, "요약 코드")
    if code_section:
        cls.summarized_code = _extract_code_block(code_section)

    return cls


def _parse_single_class_v2(section: str) -> Optional[ClassDetail]:
    """v2: 단일 클래스 섹션을 파싱 (#### 서브섹션 사용)."""
    cls = ClassDetail()

    lines = section.split("\n")
    if not lines:
        return None

    # 클래스 이름 (첫 줄)
    first_line = lines[0].strip()
    cls.name = re.sub(r"[#>*`]", "", first_line).strip()

    # #### 로 서브섹션 분리
    subsections = _split_h4_subsections(section)

    # 기본 정보
    if "기본 정보" in subsections:
        _parse_class_basic_info_v2(subsections["기본 정보"], cls)

    # 요약
    if "요약" in subsections:
        summary_text = subsections["요약"]
        # > 인용 블록 추출
        quote_lines = [l.lstrip("> ").strip() for l in summary_text.split("\n") if l.strip().startswith(">")]
        if quote_lines:
            cls.summary = " ".join(quote_lines)
        else:
            # 인용 블록이 아닌 경우 전체 텍스트
            cls.summary = summary_text.strip()

    # 메서드
    if "메서드" in subsections:
        cls.methods = _parse_methods_table_v2(subsections["메서드"])

    # 필드
    if "필드" in subsections:
        cls.fields = _parse_fields_table_v2(subsections["필드"])

    # 구조 관계 (v2의 UML 관계)
    if "구조 관계" in subsections:
        cls.uml_relations = _parse_structural_relations_v2(subsections["구조 관계"])

    # 호출 관계
    if "호출 관계" in subsections:
        cls.calls_out, cls.called_by = _parse_calls_v2(subsections["호출 관계"])

    # 데이터 접근 (v2의 테이블 접근)
    if "데이터 접근" in subsections:
        cls.table_access = _parse_data_access_v2(subsections["데이터 접근"])

    # 요약 코드
    if "요약 코드" in subsections:
        code = _extract_code_block(subsections["요약 코드"])
        if code and code != "없음":
            cls.summarized_code = code

    return cls


def _split_h4_subsections(section: str) -> dict[str, str]:
    """#### 제목 패턴으로 서브섹션을 분리."""
    pattern = re.compile(r"^#### (.+)$", re.MULTILINE)
    matches = list(pattern.finditer(section))

    subsections: dict[str, str] = {}
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        subsections[title] = section[start:end].strip()

    return subsections


def _extract_subsection(section: str, title: str) -> Optional[str]:
    """v1: 섹션 내에서 **title** 또는 bold 제목으로 시작하는 하위 섹션을 추출."""
    # **title** 패턴
    pattern = re.compile(
        rf"\*\*{re.escape(title)}\*\*.*?\n(.*?)(?=\n\*\*[^*]+\*\*|\Z)",
        re.DOTALL,
    )
    m = pattern.search(section)
    if m:
        return m.group(0)

    # 일반 텍스트 패턴 (제목이 볼드가 아닌 경우)
    pattern2 = re.compile(
        rf"^{re.escape(title)}.*?\n(.*?)(?=\n\*\*[^*]+\*\*|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m2 = pattern2.search(section)
    return m2.group(0) if m2 else None


def _parse_class_basic_info(text: str, cls: ClassDetail) -> None:
    """v1: 기본 정보 테이블에서 ClassDetail 필드 채우기."""
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 2:
            continue
        key = _clean_text(row[0]).strip()
        val = _clean_text(row[1]).strip()

        if "타입" in key and "범위" in key:
            parts = val.split("/")
            if len(parts) >= 2:
                cls.class_type = parts[0].strip()
                cls.scope = parts[1].strip()
        elif "패키지" in key:
            cls.package = val
        elif "FQN" in key or "fqn" in key:
            cls.fqn = val
        elif "스테레오" in key:
            cls.stereotype = val
        elif "파일" in key:
            cls.file_info = val
        elif "수정자" in key:
            parts = val.split("/")
            cls.modifiers = parts[0].strip() if parts else val
            if len(parts) > 1:
                cls.annotations = parts[1].strip()
        elif "구현" in key or "implements" in key.lower():
            cls.implements = [v.strip() for v in val.split(",")]
        elif "상속" in key or "extends" in key.lower():
            cls.extends = val
        elif "주석" in key:
            cls.comment = val


def _parse_class_basic_info_v2(text: str, cls: ClassDetail) -> None:
    """v2: 기본 정보 테이블에서 ClassDetail 필드 채우기."""
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 2:
            continue
        key = _clean_text(row[0]).strip()
        val = _clean_text(row[1]).strip()
        if val == "-":
            continue

        key_lower = key.lower()
        if key == "이름":
            # 이미 첫 줄에서 파싱됨
            pass
        elif key == "타입":
            cls.class_type = val
        elif "FQN" in key or "fqn" in key:
            cls.fqn = val
        elif "패키지" in key:
            cls.package = val
        elif "스테레오" in key:
            cls.stereotype = val
        elif "파일" in key:
            cls.file_info = val
        elif "라인" in key_lower:
            pass  # line range — not in model
        elif "토큰" in key_lower:
            pass  # token count — not in model
        elif "범위" in key_lower:
            cls.scope = val


def _parse_methods_table(text: str) -> list[MethodInfo]:
    """v1: 메서드 테이블 파싱 (6열: #,이름,시그니처,반환,역할,요약)."""
    methods: list[MethodInfo] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 6:
            continue
        methods.append(MethodInfo(
            name=_clean_text(row[1]),
            signature=_clean_text(row[2]),
            return_type=_clean_text(row[3]),
            role=_clean_text(row[4]),
            summary=_clean_text(row[5]),
        ))
    return methods


def _parse_methods_table_v2(text: str) -> list[MethodInfo]:
    """v2: 메서드 테이블 파싱 (5열: 이름,시그니처,반환타입,수정자,요약)."""
    methods: list[MethodInfo] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 5:
            continue
        name = _clean_text(row[0])
        signature = _clean_text(row[1])
        return_type = _clean_text(row[2])
        modifiers = _clean_text(row[3])
        summary = _clean_text(row[4])

        # 시그니처에서 role 추론
        role = _infer_method_role(name, signature, summary)

        methods.append(MethodInfo(
            name=name,
            signature=signature,
            return_type=return_type,
            role=role,
            summary=summary,
        ))
    return methods


def _infer_method_role(name: str, signature: str, summary: str) -> str:
    """메서드 이름과 시그니처에서 role을 추론."""
    name_lower = name.lower()

    # EJB lifecycle
    if name.startswith("ejb") and len(name) > 3 and name[3].isupper():
        return "lifecycle"
    if name in ("setEntityContext", "unsetEntityContext", "setSessionContext"):
        return "lifecycle"

    # Getter
    if name_lower.startswith("get") or name_lower.startswith("is"):
        return "getter"

    # Setter
    if name_lower.startswith("set"):
        return "setter"

    # toString, equals, hashCode
    if name in ("toString", "equals", "hashCode"):
        return "utility"

    # Query indicators in summary
    summary_lower = summary.lower()
    if any(kw in summary_lower for kw in ("조회", "반환", "검색", "목록", "리스트", "select", "query", "find", "search", "읽기")):
        if not any(kw in summary_lower for kw in ("갱신", "변경", "저장", "삭제", "생성", "insert", "update", "delete", "create")):
            return "query"

    # Command indicators
    if any(kw in summary_lower for kw in ("갱신", "변경", "저장", "삭제", "생성", "처리", "실행", "등록", "승인", "거절",
                                           "insert", "update", "delete", "create", "execute", "process")):
        return "command"

    # Default: infer from return type
    if signature and "void" in signature.lower():
        return "command"

    return "query"


def _parse_fields_table(text: str) -> list[FieldInfo]:
    """v1: 필드 테이블 파싱 (6열)."""
    fields: list[FieldInfo] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 4:
            continue
        fields.append(FieldInfo(
            name=_clean_text(row[1]),
            type=_clean_text(row[2]) if len(row) > 2 else "",
            modifiers=_clean_text(row[3]) if len(row) > 3 else "",
            annotation=_clean_text(row[4]) if len(row) > 4 else "",
            description=_clean_text(row[5]) if len(row) > 5 else "",
        ))
    return fields


def _parse_fields_table_v2(text: str) -> list[FieldInfo]:
    """v2: 필드 테이블 파싱 (4열: 이름,타입,수정자,요약)."""
    fields: list[FieldInfo] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 4:
            continue
        name = _clean_text(row[0])
        type_val = _clean_text(row[1])
        modifiers = _clean_text(row[2])
        desc = _clean_text(row[3])

        # "-" 값 무시
        if name == "-":
            continue

        fields.append(FieldInfo(
            name=name,
            type=type_val if type_val != "-" else "",
            modifiers=modifiers if modifiers != "-" else "",
            description=desc if desc != "-" else "",
        ))
    return fields


def _parse_uml_relations_table(text: str) -> list[UMLRelation]:
    """v1: UML 관계 테이블 파싱."""
    relations: list[UMLRelation] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 4:
            continue
        relations.append(UMLRelation(
            direction=row[0].strip(),
            relation_type=_clean_text(row[1]),
            target=_clean_text(row[2]),
            target_scope=row[3].strip() if len(row) > 3 else "",
            note=row[4].strip() if len(row) > 4 else "",
        ))
    return relations


def _parse_structural_relations_v2(text: str) -> list[UMLRelation]:
    """v2: 구조 관계 테이블 파싱 (방향,관계,대상,속성)."""
    relations: list[UMLRelation] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 3:
            continue
        direction = row[0].strip()
        relation_type = _clean_text(row[1])
        target = _clean_text(row[2])
        props = _clean_text(row[3]) if len(row) > 3 else ""

        if target == "-":
            continue

        relations.append(UMLRelation(
            direction=direction,
            relation_type=relation_type,
            target=target,
            target_scope="INTERNAL",  # v2에서는 scope가 별도로 없음
            note=props,
        ))
    return relations


def _parse_calls(text: str) -> tuple[list[CallInfo], list[CallInfo]]:
    """v1: 호출 관계 테이블 파싱. (calls_out, called_by) 반환."""
    calls_out: list[CallInfo] = []
    called_by: list[CallInfo] = []

    parts = re.split(r"이 클래스를 호출하는", text)

    if parts:
        rows = _parse_table_rows(parts[0])
        for row in rows:
            if len(row) >= 2:
                calls_out.append(CallInfo(
                    target=_clean_text(row[0]),
                    scope=row[1].strip() if len(row) > 1 else "",
                ))

    if len(parts) > 1:
        rows = _parse_table_rows(parts[1])
        for row in rows:
            if len(row) >= 2:
                called_by.append(CallInfo(
                    target=_clean_text(row[0]),
                    scope=row[1].strip() if len(row) > 1 else "",
                ))

    return calls_out, called_by


def _parse_calls_v2(text: str) -> tuple[list[CallInfo], list[CallInfo]]:
    """v2: 호출 관계 테이블 파싱 (방향,대상,호출코드)."""
    calls_out: list[CallInfo] = []
    called_by: list[CallInfo] = []

    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 2:
            continue
        direction = row[0].strip()
        target = _clean_text(row[1])
        if target == "-":
            continue

        call = CallInfo(target=target, scope="internal")

        if direction == "→" or direction == "->":
            calls_out.append(call)
        elif direction == "←" or direction == "<-":
            called_by.append(call)

    return calls_out, called_by


def _parse_table_access(text: str) -> list[TableAccessInfo]:
    """v1: 테이블 접근 테이블 파싱."""
    accesses: list[TableAccessInfo] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 2:
            continue
        accesses.append(TableAccessInfo(
            table=_clean_text(row[0]),
            access_type=_clean_text(row[1]),
            evidence=_clean_text(row[2]) if len(row) > 2 else "",
        ))
    return accesses


def _parse_data_access_v2(text: str) -> list[TableAccessInfo]:
    """v2: 데이터 접근 테이블 파싱 (대상,관계,근거,신뢰도)."""
    accesses: list[TableAccessInfo] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 2:
            continue
        target = _clean_text(row[0])
        relation = _clean_text(row[1]) if len(row) > 1 else ""
        evidence = _clean_text(row[2]) if len(row) > 2 else ""
        if target == "-":
            continue

        # READS → FROM, WRITES → WRITES, REFER_TO → FROM
        access_type = "FROM"
        if "WRITE" in relation.upper():
            access_type = "WRITES"

        accesses.append(TableAccessInfo(
            table=target,
            access_type=access_type,
            evidence=evidence,
        ))
    return accesses


# ── Section 4: 외부 의존성 ──


def _parse_external_deps(text: str, is_v2: bool = False) -> list[ExternalDep]:
    deps: list[ExternalDep] = []
    rows = _parse_table_rows(text)

    if is_v2:
        # v2: 3열 (외부 엔티티, 타입, 참조 INTERNAL)
        for row in rows:
            if len(row) < 3:
                continue
            name = _clean_text(row[0])
            if name == "-":
                continue
            deps.append(ExternalDep(
                name=name,
                class_type=_clean_text(row[1]),
                relation="DEPENDENCY",
                used_by=[s.strip() for s in _clean_text(row[2]).split(",")],
            ))
    else:
        # v1: 5열
        for row in rows:
            if len(row) < 5:
                continue
            deps.append(ExternalDep(
                name=_clean_text(row[1]),
                class_type=_clean_text(row[2]),
                relation=_clean_text(row[3]),
                used_by=[s.strip() for s in _clean_text(row[4]).split(",")],
            ))

    return deps


# ── Section 5: 설정 파일 / 쿼리 블록 ──


def _parse_config_blocks(text: str) -> list[ConfigBlock]:
    """v1: 설정 파일 파싱."""
    blocks: list[ConfigBlock] = []

    file_sections = re.split(r"^### ", text, flags=re.MULTILINE)

    for fsec in file_sections[1:]:
        lines = fsec.strip().split("\n")
        if not lines:
            continue

        file_name = lines[0].strip()
        file_path = ""
        path_match = re.search(r"`([^`]+)`", fsec)
        if path_match:
            file_path = path_match.group(1)

        block_table_match = re.search(r"블록 목록.*?\n((?:\|.*\n)+)", fsec, re.DOTALL)
        block_rows = _parse_table_rows(block_table_match.group(0)) if block_table_match else []

        ref_table_match = re.search(r"테이블 참조.*?\n((?:\|.*\n)+)", fsec, re.DOTALL)
        ref_rows = _parse_table_rows(ref_table_match.group(0)) if ref_table_match else []

        refs_by_block: dict[str, list[ConfigBlockRef]] = {}
        for row in ref_rows:
            if len(row) >= 4:
                block_name = _clean_text(row[0])
                ref = ConfigBlockRef(
                    table=_clean_text(row[1]),
                    role=_clean_text(row[2]) if len(row) > 2 else "",
                    confidence=_clean_text(row[3]) if len(row) > 3 else "",
                    evidence=_clean_text(row[4]) if len(row) > 4 else "",
                )
                refs_by_block.setdefault(block_name, []).append(ref)

        for row in block_rows:
            if len(row) < 4:
                continue
            block_name = _clean_text(row[1])
            blocks.append(ConfigBlock(
                file_name=file_name,
                file_path=file_path,
                block_name=block_name,
                block_type=_clean_text(row[2]) if len(row) > 2 else "",
                line_range=_clean_text(row[3]) if len(row) > 3 else "",
                summary=_clean_text(row[4]) if len(row) > 4 else "",
                table_refs=refs_by_block.get(block_name, []),
            ))

    return blocks


def _parse_artifact_chunks(text: str) -> list[ConfigBlock]:
    """v2: Artifact 청크 파싱 (ejb-jar.xml 등)."""
    blocks: list[ConfigBlock] = []

    # ### 파일명 으로 분리
    file_sections = re.split(r"^### ", text, flags=re.MULTILINE)

    for fsec in file_sections[1:]:
        lines = fsec.strip().split("\n")
        if not lines:
            continue

        file_name = lines[0].strip()
        subsections = _split_h4_subsections(fsec)

        # 기본 정보
        summary = ""
        block_type = ""
        if "기본 정보" in subsections:
            rows = _parse_table_rows(subsections["기본 정보"])
            for row in rows:
                if len(row) < 2:
                    continue
                key = _clean_text(row[0])
                val = _clean_text(row[1])
                if val == "-":
                    continue
                if key == "종류":
                    block_type = val
                elif key == "요약":
                    summary = val

        # 관계 (REFER_TO)
        refs: list[ConfigBlockRef] = []
        if "관계" in subsections:
            rows = _parse_table_rows(subsections["관계"])
            for row in rows:
                if len(row) < 3:
                    continue
                direction = row[0].strip()
                relation = _clean_text(row[1])
                target = _clean_text(row[2])
                if target == "-":
                    continue
                refs.append(ConfigBlockRef(
                    table=target,
                    role=relation,
                    confidence="",
                    evidence=direction,
                ))

        blocks.append(ConfigBlock(
            file_name=file_name,
            file_path=file_name,
            block_name=file_name,
            block_type=block_type,
            summary=summary,
            table_refs=refs,
        ))

    return blocks


# ── Section 6/7: 데이터베이스 스키마 ──


def _parse_db_schema(text: str, is_v2: bool = False) -> tuple[list[TableSchema], list[ColumnLevelFK]]:
    tables: list[TableSchema] = []
    column_fks: list[ColumnLevelFK] = []

    # ### 테이블명 으로 분리
    table_sections = re.split(r"^### ", text, flags=re.MULTILINE)

    for tsec in table_sections[1:]:
        lines = tsec.strip().split("\n")
        if not lines:
            continue

        table_name = lines[0].strip()

        # "컬럼 레벨 FK" 섹션 처리
        if "컬럼 레벨 FK" in table_name or "FK_TO" in table_name:
            column_fks = _parse_column_level_fks(tsec)
            continue

        # "나머지 테이블" 요약 테이블 처리
        if "나머지 테이블" in table_name:
            rows = _parse_table_rows(tsec)
            for row in rows:
                if len(row) >= 3:
                    t_name = _clean_text(row[0])
                    if t_name and t_name != "...":
                        tables.append(TableSchema(
                            name=t_name,
                            mapped_entity=_clean_text(row[1]) if len(row) > 1 else "",
                            summary=_clean_text(row[2]) if len(row) > 2 else "",
                        ))
            continue

        if is_v2:
            table = _parse_single_table_v2(tsec, table_name)
        else:
            table = _parse_single_table(tsec, table_name)
        if table and table.name:
            tables.append(table)

    return tables, column_fks


def _parse_single_table(section: str, table_name: str) -> Optional[TableSchema]:
    """v1: 단일 테이블 섹션 파싱."""
    table = TableSchema(name=table_name)

    first_table = re.search(r"\| 속성.*?\n((?:\|.*\n)+)", section)
    if first_table:
        basic_rows = _parse_table_rows(first_table.group(0))
        for row in basic_rows:
            if len(row) < 2:
                continue
            key = _clean_text(row[0])
            val = _clean_text(row[1])
            if "스키마" in key:
                table.schema_name = val
            elif "엔티티" in key or "매핑" in key:
                parts = val.split("/")
                table.mapped_entity = parts[0].strip()
                if len(parts) > 1:
                    table.mapping_type = parts[1].strip()

    quote_match = re.search(r"^> (.+)$", section, re.MULTILINE)
    if quote_match:
        table.summary = quote_match.group(1).strip()

    col_section = _extract_subsection(section, "컬럼")
    if col_section:
        table.columns = _parse_columns_table(col_section)

    fk_section = _extract_subsection(section, "FK 관계")
    if fk_section:
        table.fk_relations = _parse_fk_relations_table(fk_section)

    access_section = _extract_subsection(section, "접근 관계")
    if access_section:
        table.access_relations = _parse_table_access_rows(access_section)

    return table


def _parse_single_table_v2(section: str, table_name: str) -> Optional[TableSchema]:
    """v2: 단일 테이블 섹션 파싱 (#### 서브섹션 사용)."""
    table = TableSchema(name=table_name)

    subsections = _split_h4_subsections(section)

    # 테이블 정보
    if "테이블 정보" in subsections:
        rows = _parse_table_rows(subsections["테이블 정보"])
        for row in rows:
            if len(row) < 2:
                continue
            key = _clean_text(row[0])
            val = _clean_text(row[1])
            if val == "-":
                continue
            if key == "스키마":
                table.schema_name = val
            elif key == "설명":
                table.summary = val
            elif key == "엔티티명":
                table.mapped_entity = val
            elif key == "매핑 타입":
                table.mapping_type = val

    # 컬럼
    if "컬럼" in subsections:
        table.columns = _parse_columns_table_v2(subsections["컬럼"])

    # FK 관계
    if "FK 관계" in subsections:
        table.fk_relations = _parse_fk_relations_table_v2(subsections["FK 관계"])

    return table


def _parse_columns_table(text: str) -> list[ColumnInfo]:
    """v1: 컬럼 테이블 파싱."""
    columns: list[ColumnInfo] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 4:
            continue
        columns.append(ColumnInfo(
            name=_clean_text(row[1]),
            data_type=_clean_text(row[2]),
            nullable=row[3].strip().upper() != "N" if len(row) > 3 else True,
            is_pk="PK" in (row[4].strip() if len(row) > 4 else ""),
            description=_clean_text(row[5]) if len(row) > 5 else "",
        ))
    return columns


def _parse_columns_table_v2(text: str) -> list[ColumnInfo]:
    """v2: 컬럼 테이블 파싱 (5열: 컬럼명,타입,Nullable,PK,설명)."""
    columns: list[ColumnInfo] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 5:
            continue
        name = _clean_text(row[0])
        if name == "-":
            continue

        data_type = _clean_text(row[1])
        nullable_str = row[2].strip()
        pk_str = row[3].strip()
        description = _clean_text(row[4])

        columns.append(ColumnInfo(
            name=name,
            data_type=data_type if data_type != "-" else "",
            nullable=nullable_str.upper() != "FALSE" and nullable_str.upper() != "N",
            is_pk=pk_str.upper() not in ("", "-", "FALSE"),
            description=description if description != "-" else "",
        ))
    return columns


def _parse_fk_relations_table(text: str) -> list[FKRelation]:
    """v1: FK 관계 테이블 파싱."""
    fks: list[FKRelation] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 4:
            continue
        fks.append(FKRelation(
            direction=row[0].strip(),
            target_table=_clean_text(row[1]),
            fk_type=_clean_text(row[2]) if len(row) > 2 else "",
            confidence=_clean_text(row[3]) if len(row) > 3 else "",
            evidence=_clean_text(row[4]) if len(row) > 4 else "",
        ))
    return fks


def _parse_fk_relations_table_v2(text: str) -> list[FKRelation]:
    """v2: FK 관계 테이블 파싱 (관계,대상,FK타입,신뢰도,근거)."""
    fks: list[FKRelation] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 5:
            continue
        relation = _clean_text(row[0])
        target = _clean_text(row[1])
        if target == "-":
            continue
        fks.append(FKRelation(
            direction="->",
            target_table=target,
            fk_type=_clean_text(row[2]) if row[2].strip() != "-" else "",
            confidence=_clean_text(row[3]) if row[3].strip() != "-" else "",
            evidence=_clean_text(row[4]) if len(row) > 4 and row[4].strip() != "-" else "",
        ))
    return fks


def _parse_table_access_rows(text: str) -> list[TableAccessInfo]:
    """v1: 접근 관계 테이블 파싱."""
    accesses: list[TableAccessInfo] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 2:
            continue
        accesses.append(TableAccessInfo(
            access_type=_clean_text(row[0]),
            table=_clean_text(row[1]),
            evidence=_clean_text(row[2]) if len(row) > 2 else "",
        ))
    return accesses


def _parse_column_level_fks(text: str) -> list[ColumnLevelFK]:
    """컬럼 레벨 FK 전체 테이블 파싱."""
    fks: list[ColumnLevelFK] = []
    rows = _parse_table_rows(text)
    for row in rows:
        if len(row) < 4:
            continue
        fks.append(ColumnLevelFK(
            source_column=_clean_text(row[1]),
            target_column=_clean_text(row[2]),
            fk_type=_clean_text(row[3]) if len(row) > 3 else "",
            confidence=_clean_text(row[4]) if len(row) > 4 else "",
        ))
    return fks


# ── Section 7 (v1) / Section 9 (v2): 데이터 흐름 ──


def _parse_data_flow(text: str) -> DataFlow:
    """v1: 데이터 흐름 섹션 파싱."""
    flow = DataFlow()

    # 7.1 테이블 접근 매트릭스
    matrix_section = re.search(r"7\.1.*?테이블 접근.*?\n((?:\|.*\n)+)", text, re.DOTALL)
    if matrix_section:
        rows = _parse_table_rows(matrix_section.group(0))
        for row in rows:
            if len(row) >= 3:
                table_name = _clean_text(row[0])
                if table_name:
                    readers = [r.strip() for r in row[1].split(",") if r.strip()]
                    for reader in readers:
                        flow.table_access_matrix.append(TableAccessInfo(
                            table=table_name, access_type="FROM", evidence=reader,
                        ))
                    if len(row) > 2:
                        writers = [w.strip() for w in row[2].split(",") if w.strip()]
                        for writer in writers:
                            flow.table_access_matrix.append(TableAccessInfo(
                                table=table_name, access_type="WRITES", evidence=writer,
                            ))

    # 7.2 호출 체인
    chain_blocks = re.finditer(
        r"\[(.+?)\]\n((?:[\w.]+\.?\w*\(?\)?\n?(?:\s+->.*\n?)*)+)",
        text,
    )
    for m in chain_blocks:
        flow.call_chains.append(CallChain(
            flow_name=m.group(1).strip(),
            chain_text=m.group(2).strip(),
        ))

    code_blocks = re.findall(r"```\n(.*?)```", text, re.DOTALL)
    for block in code_blocks:
        chain_parts = re.split(r"\[(.+?)\]", block)
        for i in range(1, len(chain_parts), 2):
            name = chain_parts[i].strip()
            chain_text = chain_parts[i + 1].strip() if i + 1 < len(chain_parts) else ""
            if name and chain_text:
                existing_names = {c.flow_name for c in flow.call_chains}
                if name not in existing_names:
                    flow.call_chains.append(CallChain(
                        flow_name=name, chain_text=chain_text,
                    ))

    # 7.3 호출 관계 전체 목록
    calls_section = re.search(r"7\.3.*?호출 관계.*?\n((?:\|.*\n)+)", text, re.DOTALL)
    if calls_section:
        rows = _parse_table_rows(calls_section.group(0))
        for row in rows:
            if len(row) >= 4:
                flow.call_relations.append(CallRelation(
                    caller=_clean_text(row[1]),
                    callee=_clean_text(row[2]),
                    scope=row[3].strip() if len(row) > 3 else "",
                ))

    return flow


def _parse_cross_analysis(text: str) -> DataFlow:
    """v2: 횡단 분석 섹션(Section 9) 파싱."""
    flow = DataFlow()

    # 9.1 테이블 접근 매트릭스
    matrix_section = re.search(r"9\.1.*?테이블 접근.*?\n((?:\|.*\n)+)", text, re.DOTALL)
    if matrix_section:
        rows = _parse_table_rows(matrix_section.group(0))
        for row in rows:
            if len(row) < 3:
                continue
            table_name = _clean_text(row[0])
            entity = _clean_text(row[1])
            access_types = _clean_text(row[2])

            if table_name == "-" or not table_name:
                continue

            # "READ, WRITE" → 개별 접근 기록
            for access_type in access_types.split(","):
                access_type = access_type.strip().upper()
                if access_type == "READ":
                    flow.table_access_matrix.append(TableAccessInfo(
                        table=table_name, access_type="FROM", evidence=entity,
                    ))
                elif access_type == "WRITE":
                    flow.table_access_matrix.append(TableAccessInfo(
                        table=table_name, access_type="WRITES", evidence=entity,
                    ))
                elif access_type == "REFER":
                    flow.table_access_matrix.append(TableAccessInfo(
                        table=table_name, access_type="FROM", evidence=f"{entity} (REFER)",
                    ))

    # 9.3 구조 관계 전체 목록 → call_relations로 매핑
    struct_section = re.search(r"9\.3.*?구조 관계.*?\n((?:\|.*\n)+)", text, re.DOTALL)
    if struct_section:
        rows = _parse_table_rows(struct_section.group(0))
        for row in rows:
            if len(row) < 3:
                continue
            relation = _clean_text(row[0])
            source = _clean_text(row[1])
            target = _clean_text(row[2])
            if source == "-" or target == "-":
                continue
            # ASSOCIATION 관계만 call_relations로 매핑
            if relation in ("ASSOCIATION", "DEPENDENCY", "COMPOSITION"):
                flow.call_relations.append(CallRelation(
                    caller=source,
                    callee=target,
                    scope="internal",
                ))

    return flow


# ── 보강 ──


def _enrich_class_table_mapping(report: ParsedReport) -> None:
    """Entity Bean 클래스에 매핑된 테이블 이름을 보강."""
    for cls in report.classes:
        if "Entity Bean" not in cls.stereotype:
            # v2: stereotype이 COMMAND/READMODEL 등으로 되어 있을 수 있음
            # Entity Bean이 아닌 경우에도 이름 기반으로 매핑 시도
            pass

        # 테이블에서 mapped_entity가 이 클래스 이름인 것 찾기
        for table in report.tables:
            if table.mapped_entity == cls.name:
                cls.mapped_table = table.name
                break

    # v2 추가: Entity Bean 클래스와 테이블 이름 기반 매핑
    # 예: CollateralBean → COLLATERAL, LoanApplicationBean → LOAN_APPLICATION
    table_names_upper = {t.name.upper(): t for t in report.tables}

    for cls in report.classes:
        if cls.mapped_table:
            continue
        # Bean 접미사 제거 후 snake_case 변환하여 테이블 매핑 시도
        bean_name = cls.name
        if bean_name.endswith("Bean"):
            core_name = bean_name[:-4]
            # PascalCase → UPPER_SNAKE_CASE
            snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", core_name).upper()
            # 정확한 매칭 시도
            if snake_name in table_names_upper:
                cls.mapped_table = table_names_upper[snake_name].name
                if not table_names_upper[snake_name].mapped_entity:
                    table_names_upper[snake_name].mapped_entity = cls.name
                continue
            # _ENTITY 접미사 변형 매칭 (e.g., CREDIT_RATING → CREDIT_RATING_ENTITY)
            snake_entity = snake_name + "_ENTITY"
            if snake_entity in table_names_upper:
                cls.mapped_table = table_names_upper[snake_entity].name
                if not table_names_upper[snake_entity].mapped_entity:
                    table_names_upper[snake_entity].mapped_entity = cls.name
                continue

    # 추가 fallback: table_access에서 실제 테이블 참조를 사용하여 매핑
    for cls in report.classes:
        if cls.mapped_table or "Entity Bean" not in cls.stereotype:
            continue
        for ta in cls.table_access:
            if ta.table.upper() in table_names_upper:
                cls.mapped_table = table_names_upper[ta.table.upper()].name
                if not table_names_upper[ta.table.upper()].mapped_entity:
                    table_names_upper[ta.table.upper()].mapped_entity = cls.name
                break

    # v2 추가: DTO 클래스에서 Entity Bean 연관 정보를 추론하여
    # 파서에서 인식하지 못한 stereotype을 보강
    _infer_stereotypes_from_packages(report)


def _infer_stereotypes_from_packages(report: ParsedReport) -> None:
    """패키지 경로에서 stereotype을 추론하여 보강."""
    for cls in report.classes:
        if cls.stereotype and cls.stereotype not in ("COMMAND/READMODEL", "READMODEL", "COMMAND", "-"):
            continue

        pkg = cls.package or cls.fqn or ""
        name = cls.name

        if ".entity" in pkg:
            if name.endswith("Bean"):
                cls.stereotype = "Entity Bean (CMP)"
            elif name.endswith("Local"):
                cls.stereotype = "Entity Local Interface"
            elif name.endswith("LocalHome"):
                cls.stereotype = "Entity LocalHome Interface"
        elif ".session" in pkg:
            if name.endswith("SessionBean"):
                cls.stereotype = "Session Bean (Stateless)"
            elif name.endswith("Session"):
                cls.stereotype = "Session Remote Interface"
            elif name.endswith("SessionHome"):
                cls.stereotype = "Session Home Interface"
        elif ".web" in pkg or ".servlet" in pkg:
            cls.stereotype = "Servlet"
        elif ".dto" in pkg:
            cls.stereotype = "DTO"
        elif ".util" in pkg:
            cls.stereotype = "Utility"
        elif ".exception" in pkg:
            cls.stereotype = "Exception"
