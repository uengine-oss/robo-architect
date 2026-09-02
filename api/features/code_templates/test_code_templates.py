"""템플릿 파싱과 렌더 컨텍스트 — 실제 생성물에서 나온 결함들을 고정한다."""

from __future__ import annotations

import pytest

from api.features.code_templates.context import camel_case, java_type, pascal_case, pluralize
from api.features.code_templates.repository import (
    parse_config_fields,
    parse_template,
    resolve_set,
)


class TestParseTemplate:
    def test_front_matter_and_body(self):
        t = parse_template(
            "forEach: Aggregate\n"
            "path: {{boundedContext.nameCamelCase}}/store\n"
            "fileName: {{namePascalCase}}.java\n"
            "---\n"
            "package a.b;\n",
            "x/Y.java",
        )
        assert t.for_each == "Aggregate"
        assert t.out_path == "{{boundedContext.nameCamelCase}}/store"
        assert t.out_file_name == "{{namePascalCase}}.java"
        assert t.body == "package a.b;\n"

    def test_file_name_is_optional(self):
        t = parse_template("forEach: BoundedContext\npath: {{nameCamelCase}}\n---\nhi\n", "README.md")
        assert t.out_file_name is None
        assert t.for_each == "BoundedContext"

    def test_function_block_is_split_out(self):
        """헬퍼는 본문에 남으면 안 된다 — 그대로 두면 자바 파일에 JS 가 찍힌다."""
        t = parse_template(
            "forEach: Aggregate\npath: p\n---\n"
            "class X {}\n"
            "<function>\nwindow.$HandleBars.registerHelper('f', function(){});\n</function>\n",
            "X.java",
        )
        assert "<function>" not in t.body
        assert "registerHelper" not in t.body
        assert len(t.functions) == 1
        assert "registerHelper('f'" in t.functions[0]

    def test_no_front_matter_is_not_renderable(self):
        t = parse_template("just a file\nwith text\n", "notes.txt")
        assert t.for_each is None
        assert t.body == "just a file\nwith text\n"

    @pytest.mark.parametrize("name", ["..", "../..", "/etc", "set/../..", ""])
    def test_set_name_cannot_escape_the_templates_root(self, name):
        """이름은 사용자 입력이다. `templates/` 밖은 어떤 형태로도 거부한다."""
        with pytest.raises((ValueError, FileNotFoundError)):
            resolve_set(name)


class TestNames:
    @pytest.mark.parametrize(
        "raw,pascal,camel,plural",
        [
            ("AutoDebitApplication", "AutoDebitApplication", "autoDebitApplication", "autoDebitApplications"),
            ("auto_debit", "AutoDebit", "autoDebit", "autoDebits"),
            ("Status", "Status", "status", "statuses"),
            ("Policy", "Policy", "policy", "policies"),
            ("", "", "", ""),
        ],
    )
    def test_variants(self, raw, pascal, camel, plural):
        assert pascal_case(raw) == pascal
        assert camel_case(raw) == camel
        assert pluralize(camel_case(raw)) == plural


class TestJavaType:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            # 템플릿의 isPrimitive 가 아는 이름이어야 한다. 아니면 값 객체로
            # 취급돼 `import ….vo.boolean;` 같은 구문 오류가 생성물에 남는다.
            ("boolean", "Boolean"),
            ("int", "Integer"),
            ("UUID", "String"),
            ("LocalDateTime", "Date"),
            ("String", "String"),
            (None, "String"),
            ("", "String"),
            # 모르는 이름은 그대로 — 값 객체·열거형의 이름이다.
            ("PaymentMethod", "PaymentMethod"),
            ("List<UUID>", "List<String>"),
        ],
    )
    def test_mapping(self, raw, expected):
        assert java_type(raw) == expected


class TestConfiguration:
    """`_template/` 아래는 생성물이 아니라 생성기 설정이다."""

    def test_template_dir_marks_configuration(self):
        t = parse_template("forEach: BoundedContext\npath: p\n---\nx\n",
                           "_template/configuration.html")
        assert t.is_configuration is True

    def test_ordinary_template_is_not_configuration(self):
        t = parse_template("forEach: Aggregate\npath: p\n---\nx\n",
                           "msaez0-store/src/main/java/X.java")
        assert t.is_configuration is False

    def test_nested_template_dir_also_counts(self):
        t = parse_template("forEach: BoundedContext\npath: p\n---\nx\n",
                           "for-model/_template/configuration.html")
        assert t.is_configuration is True

    def test_reads_declared_option_fields(self):
        """옵션은 템플릿이 정한다 — 화면이 항목을 지어내면 안 된다."""
        fields = parse_config_fields(
            '<text-field :value.sync="value.serviceId" label="서비스 ID"></text-field>\n'
            '<text-field :value.sync="value.groupId" label="그룹 ID"></text-field>'
        )
        assert fields == [
            {"key": "serviceId", "label": "서비스 ID", "type": "text-field"},
            {"key": "groupId", "label": "그룹 ID", "type": "text-field"},
        ]

    def test_label_is_optional(self):
        fields = parse_config_fields('<text-field :value.sync="value.port"></text-field>')
        assert fields == [{"key": "port", "label": "port", "type": "text-field"}]

    def test_no_fields_when_nothing_declared(self):
        assert parse_config_fields("<p>설명만 있는 파일</p>") == []
        assert parse_config_fields("") == []
