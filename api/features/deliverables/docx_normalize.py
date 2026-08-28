"""DOCX 정본화 및 ECM 호환성 점검.

기준 구현: `local-msaez` `run_healcheck_server.py` 의 `/api/documents/normalize-docx`.

## 왜 필요한가

브라우저에서 `docx` + `jszip` 으로 만든 파일은 Word 로는 열리지만 **정본 OOXML
패키지가 아니다.** ZIP 구조가 Office 표준과 다르기 때문이다.

- `[Content_Types].xml` 이 첫 엔트리가 아니다.
- 디렉토리 엔트리(`word/`)가 포함된다.

Apache Tika 같은 엄격한 콘텐츠 검출기는 이 두 가지를 근거로 파일을
`application/zip` 으로 판정하고, ECM 은 "Word 문서가 아니다"라며 등록을 거부한다.
LibreOffice 로 열었다 다시 저장하면(= Word 로 저장한 것과 동일) 표준 패키지가
되어 검출기가 Word 문서로 인식한다.

## 이 모듈의 구성

- `normalize_docx()` — soffice headless 재직렬화. LibreOffice 없으면 명확한 오류.
- `inspect_docx_package()` — ECM 호환성 판정. LibreOffice 없이도 동작한다.
- `compare_documents()` — 정본화 전후 유실 검증(문단·표·이미지·본문 길이).
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from typing import Any

from api.platform.env import env_int, env_str

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

CONTENT_TYPES_ENTRY = "[Content_Types].xml"
_DOCUMENT_PART = "word/document.xml"
_MEDIA_PREFIX = "word/media/"

# 본문 XML 태그. 정확한 파싱 대신 태그 수를 세는 것으로 충분하다 — 목적이
# "정본화 과정에서 내용이 사라지지 않았는가" 확인이지 문서 재구성이 아니다.
_PARAGRAPH_RE = re.compile(rb"<w:p[ >]")
_TABLE_RE = re.compile(rb"<w:tbl[ >]")
_ROW_RE = re.compile(rb"<w:tr[ >]")
_TEXT_RE = re.compile(rb"<w:t(?:\s[^>]*)?>(.*?)</w:t>", re.DOTALL)


class DocxNormalizeUnavailable(RuntimeError):
    """LibreOffice 가 설치돼 있지 않아 정본화를 수행할 수 없다."""


class DocxNormalizeFailed(RuntimeError):
    """LibreOffice 는 있으나 변환에 실패했다."""


def soffice_binary() -> str | None:
    """soffice 실행 파일 경로. 없으면 None.

    `LIBREOFFICE_BIN` 으로 명시 지정할 수 있다. macOS 처럼 PATH 에 없고 앱 번들
    안에 있는 환경을 위해 알려진 경로도 함께 확인한다.
    """
    configured = env_str("LIBREOFFICE_BIN", default=None)
    if configured:
        return configured if os.path.isfile(configured) and os.access(configured, os.X_OK) else None

    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found

    for candidate in (
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/lib/libreoffice/program/soffice",
        "/opt/libreoffice/program/soffice",
    ):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def is_available() -> bool:
    return soffice_binary() is not None


def normalize_docx(data: bytes, *, timeout_s: int | None = None) -> bytes:
    """docx 바이트를 LibreOffice 로 재직렬화해 정본 OOXML 로 돌려준다.

    호출마다 `UserInstallation` 프로필을 분리한다. soffice 는 프로필 단위로
    싱글톤 락을 잡기 때문에, 프로필을 공유하면 동시 요청이 서로를 막는다.
    """
    binary = soffice_binary()
    if not binary:
        raise DocxNormalizeUnavailable(
            "LibreOffice(soffice)를 찾을 수 없습니다. 서버에 libreoffice-writer 를 설치하거나 "
            "LIBREOFFICE_BIN 환경변수로 경로를 지정하세요."
        )

    timeout = timeout_s if timeout_s is not None else env_int("DOCX_NORMALIZE_TIMEOUT_S", 120)
    tmpdir = tempfile.mkdtemp(prefix="docxnorm_")
    try:
        in_path = os.path.join(tmpdir, "input.docx")
        out_dir = os.path.join(tmpdir, "out")
        os.makedirs(out_dir, exist_ok=True)
        with open(in_path, "wb") as f:
            f.write(data)

        # non-root 로 뜨는 컨테이너에서도 쓰기 가능한 HOME 이 필요하다.
        env = dict(os.environ)
        env["HOME"] = tmpdir
        profile_uri = "file://" + os.path.join(tmpdir, "lo_profile")

        cmd = [
            binary,
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--nodefault",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "docx:MS Word 2007 XML",
            "--outdir",
            out_dir,
            in_path,
        ]
        try:
            proc = subprocess.run(cmd, env=env, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise DocxNormalizeFailed(f"변환 시간 초과({timeout}초)") from exc

        out_path = os.path.join(out_dir, "input.docx")
        if proc.returncode != 0 or not os.path.exists(out_path):
            stderr = (proc.stderr or b"").decode("utf-8", "replace")[:800]
            raise DocxNormalizeFailed(f"soffice 변환 실패 (rc={proc.returncode}) {stderr}".strip())

        with open(out_path, "rb") as f:
            out = f.read()

        # 빈 파일을 성공으로 반환하지 않는다 — 변환 실패가 "성공적으로 빈 문서"로
        # 둔갑하면 ECM 에 껍데기가 등록된다.
        if not out:
            raise DocxNormalizeFailed("변환 결과가 비어 있습니다.")
        return out
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def inspect_docx_package(data: bytes) -> dict[str, Any]:
    """ZIP 구조를 보고 ECM 콘텐츠 검출기가 Word 로 인식할지 판정한다.

    LibreOffice 없이도 동작하므로, 정본화 가능 여부와 무관하게 산출물이 등록
    가능한 상태인지 확인할 수 있다.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            infos = zf.infolist()
    except zipfile.BadZipFile:
        return {
            "valid": False,
            "ecmCompatible": False,
            "reasons": ["ZIP 패키지로 열리지 않습니다."],
            "entryCount": 0,
            "firstEntry": None,
            "contentTypesFirst": False,
            "hasDirectoryEntries": False,
            "hasDocumentPart": False,
        }

    first_entry = names[0] if names else None
    content_types_first = first_entry == CONTENT_TYPES_ENTRY
    directory_entries = [i.filename for i in infos if i.filename.endswith("/")]
    has_document = _DOCUMENT_PART in names

    reasons: list[str] = []
    if not content_types_first:
        reasons.append(
            f"`{CONTENT_TYPES_ENTRY}` 가 첫 엔트리가 아닙니다 (현재: {first_entry!r}). "
            "검출기가 application/zip 으로 판정합니다."
        )
    if directory_entries:
        reasons.append(f"디렉토리 엔트리가 {len(directory_entries)}개 있습니다 (예: {directory_entries[0]!r}).")
    if not has_document:
        reasons.append(f"`{_DOCUMENT_PART}` 본문 파트가 없습니다.")

    return {
        "valid": True,
        "ecmCompatible": not reasons,
        "reasons": reasons,
        "entryCount": len(names),
        "firstEntry": first_entry,
        "contentTypesFirst": content_types_first,
        "hasDirectoryEntries": bool(directory_entries),
        "hasDocumentPart": has_document,
    }


def _document_metrics(data: bytes) -> dict[str, int]:
    """본문 파트에서 문단·표·행·본문 길이·이미지 수를 센다."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            body = zf.read(_DOCUMENT_PART) if _DOCUMENT_PART in names else b""
            images = sum(1 for n in names if n.startswith(_MEDIA_PREFIX) and not n.endswith("/"))
    except (zipfile.BadZipFile, KeyError):
        return {"paragraphs": 0, "tables": 0, "rows": 0, "textLength": 0, "images": 0}

    text = "".join(m.decode("utf-8", "replace") for m in _TEXT_RE.findall(body))
    return {
        "paragraphs": len(_PARAGRAPH_RE.findall(body)),
        "tables": len(_TABLE_RE.findall(body)),
        "rows": len(_ROW_RE.findall(body)),
        # 공백 차이는 변환기가 정규화할 수 있으므로 제외하고 비교한다.
        "textLength": len(re.sub(r"\s+", "", text)),
        "images": images,
    }


def compare_documents(before: bytes, after: bytes) -> dict[str, Any]:
    """정본화 전후를 비교해 유실 여부를 판정한다.

    LibreOffice 는 문단·표를 재구성하므로 개수가 정확히 같지 않을 수 있다. 따라서
    "동일"이 아니라 **유실**만 문제로 본다 — 표·이미지가 줄거나 본문 텍스트가
    눈에 띄게 짧아지면 경고한다.
    """
    b = _document_metrics(before)
    a = _document_metrics(after)

    losses: list[str] = []
    if a["tables"] < b["tables"]:
        losses.append(f"표 {b['tables']} → {a['tables']}")
    if a["images"] < b["images"]:
        losses.append(f"이미지 {b['images']} → {a['images']}")
    # 본문은 1% 미만 감소까지는 변환기의 공백·필드 정규화로 본다.
    if b["textLength"] and a["textLength"] < b["textLength"] * 0.99:
        losses.append(f"본문 길이 {b['textLength']} → {a['textLength']}")

    return {
        "before": b,
        "after": a,
        "lossless": not losses,
        "losses": losses,
    }
