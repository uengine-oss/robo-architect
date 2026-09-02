"""로컬 템플릿 저장소를 읽는다.

Git API 로 원격을 읽지 않는다. 납품은 내부망이고, 템플릿은
`scripts/fetch-templates.sh` 가 `templates/` 에 받아 둔 파일을 그대로 읽는다.

템플릿 한 장의 형식은 front matter 세 줄 + `---` + 본문이다.

    forEach: Aggregate
    path: {{boundedContext.nameCamelCase}}/.../domain/entity
    fileName: {{namePascalCase}}.java
    ---
    <본문>

본문 끝에는 `<function>` 블록이 붙을 수 있다. 그 안은 JavaScript 이고,
템플릿이 쓰는 Handlebars 헬퍼를 스스로 정의한다 — 렌더러가 등록해야 한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 저장소 루트의 `templates/`. 이 파일 기준으로 네 단계 위.
TEMPLATES_ROOT = Path(__file__).resolve().parents[3] / "templates"

# 렌더링 대상이 아닌 것들. `.git` 은 통째로 건너뛴다.
_SKIP_DIRS = {".git", "node_modules", "__pycache__"}
_SKIP_NAMES = {".gitkeep", ".gitignore", ".DS_Store"}

_FRONT_MATTER_KEYS = ("forEach", "path", "fileName")
_FUNCTION_BLOCK = re.compile(r"<function>(.*?)</function>", re.DOTALL)

# `_template/` 아래의 파일은 생성물이 아니라 **생성기 설정**이다.
# 기준 구현이 이 파일을 읽어 템플릿의 옵션 입력 폼을 만든다
# (`CodeGenerator.configurationTemplate`). 그래서 결과 트리에 넣으면 안 된다 —
# 납품할 소스가 아니다.
_CONFIG_DIR = "_template"

# 설정 파일이 선언하는 입력 항목.
#   <text-field :value.sync="value.serviceId" label="서비스 ID"></text-field>
_CONFIG_FIELD = re.compile(
    r"<(?P<tag>[\w-]+)[^>]*?:value\.sync\s*=\s*[\"\']value\.(?P<key>\w+)[\"\']"
    r"(?P<rest>[^>]*)>",
    re.IGNORECASE,
)
_CONFIG_LABEL = re.compile(r"label\s*=\s*[\"\'](?P<label>[^\"\']*)[\"\']", re.IGNORECASE)


@dataclass
class TemplateFile:
    """템플릿 한 장."""

    relative_path: str
    for_each: str | None
    out_path: str | None
    out_file_name: str | None
    body: str
    functions: list[str] = field(default_factory=list)

    @property
    def is_configuration(self) -> bool:
        """생성기 설정 파일인가 — `_template/` 아래에 있으면 그렇다."""
        return _CONFIG_DIR in Path(self.relative_path).parts

    def to_dict(self) -> dict[str, Any]:
        return {
            "relativePath": self.relative_path,
            "forEach": self.for_each,
            "path": self.out_path,
            "fileName": self.out_file_name,
            "body": self.body,
            "functions": self.functions,
            "isConfiguration": self.is_configuration,
        }


def parse_template(text: str, relative_path: str) -> TemplateFile:
    """front matter 를 떼어 내고 본문과 `<function>` 블록을 나눈다.

    `---` 구분자가 없으면 front matter 가 없는 것으로 본다 — 그런 파일은
    `forEach` 가 없으므로 렌더링 대상에서 자연히 빠진다.
    """
    head, sep, rest = text.partition("\n---\n")
    if not sep:
        # 파일이 `---` 로만 끝나는 경우(본문 없음)도 받아 준다.
        head, sep, rest = text.partition("\n---")
        if not sep:
            return TemplateFile(relative_path, None, None, None, text)

    directives: dict[str, str] = {}
    for line in head.splitlines():
        key, colon, value = line.partition(":")
        key = key.strip()
        if colon and key in _FRONT_MATTER_KEYS:
            directives[key] = value.strip()
        elif line.strip():
            # front matter 가 아니다 — 통째로 본문으로 되돌린다.
            return TemplateFile(relative_path, None, None, None, text)

    body = rest.lstrip("\n")
    functions = [m.group(1).strip() for m in _FUNCTION_BLOCK.finditer(body)]
    if functions:
        body = _FUNCTION_BLOCK.sub("", body).rstrip() + "\n"

    return TemplateFile(
        relative_path=relative_path,
        for_each=directives.get("forEach") or None,
        out_path=directives.get("path") or None,
        out_file_name=directives.get("fileName") or None,
        body=body,
        functions=functions,
    )


def list_template_sets() -> list[dict[str, Any]]:
    """`templates/` 바로 아래의 템플릿 묶음들."""
    if not TEMPLATES_ROOT.is_dir():
        return []
    out = []
    for child in sorted(TEMPLATES_ROOT.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        out.append({"name": child.name, "fileCount": len(_walk(child))})
    return out


def _walk(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in _SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        if p.name in _SKIP_NAMES:
            continue
        files.append(p)
    return files


def resolve_set(name: str) -> Path:
    """묶음 이름을 디렉터리로 바꾼다.

    이름은 사용자 입력이다. `templates/` 밖을 가리키는 어떤 경로도 거부한다 —
    `..` 뿐 아니라 심볼릭 링크로 빠져나가는 경우까지 실제 경로로 확인한다.
    """
    root = TEMPLATES_ROOT.resolve()
    # 빈 이름·`.` 은 루트 자체로 풀린다. 그러면 묶음 하나가 아니라 받아 둔
    # 템플릿 전부를 한꺼번에 읽게 되므로 거부한다.
    if not name or name.strip() in {"", ".", "./"}:
        raise ValueError("템플릿 묶음 이름이 비어 있습니다")
    candidate = (root / name).resolve()
    if candidate == root or root not in candidate.parents:
        raise ValueError(f"템플릿 묶음 이름이 올바르지 않습니다: {name!r}")
    if not candidate.is_dir():
        raise FileNotFoundError(f"템플릿 묶음을 찾을 수 없습니다: {name!r}")
    return candidate


def load_templates(name: str) -> list[TemplateFile]:
    """묶음 하나의 모든 템플릿을 파싱해 돌려준다."""
    root = resolve_set(name)
    out: list[TemplateFile] = []
    for p in _walk(root):
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # 바이너리는 템플릿이 아니다. 조용히 건너뛰지 않고 표시만 남긴다.
            out.append(TemplateFile(str(p.relative_to(root)), None, None, None, ""))
            continue
        out.append(parse_template(text, str(p.relative_to(root))))
    return out


def parse_config_fields(body: str) -> list[dict[str, str]]:
    """설정 파일이 선언한 입력 항목을 읽는다.

    기준 구현은 이 마크업을 Vue 컴포넌트로 렌더링해 폼을 만든다. 우리는
    필요한 것만 읽는다 — 어떤 키를 어떤 이름표로 받을 것인가.
    """
    out: list[dict[str, str]] = []
    for m in _CONFIG_FIELD.finditer(body or ""):
        label = _CONFIG_LABEL.search(m.group("rest") or "")
        out.append({
            "key": m.group("key"),
            "label": label.group("label") if label else m.group("key"),
            "type": m.group("tag").lower(),
        })
    return out


def config_fields_for(name: str) -> list[dict[str, str]]:
    """묶음 하나가 요구하는 옵션 목록. 설정 파일이 없으면 빈 목록이다."""
    fields: list[dict[str, str]] = []
    seen: set[str] = set()
    for t in load_templates(name):
        if not t.is_configuration:
            continue
        for f in parse_config_fields(t.body):
            if f["key"] in seen:
                continue
            seen.add(f["key"])
            fields.append(f)
    return fields
