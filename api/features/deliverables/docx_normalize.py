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

## LibreOffice 가 **없어도** 되는 이유 (2026-10-07)

위 두 결함은 **ZIP 의 배치 문제다 — 내용이 틀린 것이 아니다.** 그래서 같은 부품을
순서만 바꿔 다시 담아도(`repack_docx`) 같은 판정을 받는다. 설치본에서 쟀다:

```
브라우저 모양 → 재포장    ecmCompatible False → **True** · 이유 0개
유실                   `compare_documents` → **lossless** (1037 → 949 바이트)
```

납품 대상은 Windows 20여 대다. LibreOffice 를 거기 다 깔지 않아도 ECM 호환
패키지를 낼 수 있어야 한다 — 그래서 `canonicalize_docx()` 는 **soffice 가 있으면
그것을, 없으면 재포장을** 쓰고 **어느 길로 냈는지 돌려준다.**

**아직 안 쟀다**: 고객 ECM(Tika)에 실제로 올려 본 적은 없다. 우리 판정
(`inspect_docx_package`)이 통과한 것이고, 그 검출기가 스키마까지 엄격히 본다면
재포장으로는 부족할 수 있다. 그때는 soffice 경로가 필요하다.

## 이 모듈의 구성

- `canonicalize_docx()` — **입구.** soffice → 실패/부재 시 재포장. 쓴 방법을 함께 준다.
- `normalize_docx()` — soffice headless 재직렬화. LibreOffice 없으면 명확한 오류.
- `repack_docx()` — 파이썬만으로 표준 배치로 다시 담는다. 외부 프로그램이 필요 없다.
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


def _known_paths() -> list[str]:
    """PATH 에 없을 때 찾아볼 자리.

    **Windows 가 빠져 있었다**(2026-10-07). macOS·Linux 세 자리만 있었는데 납품
    대상은 Windows 다 — 그리고 Windows 설치 관리자는 `soffice` 를 **PATH 에 넣지
    않는다.** 그래서 LibreOffice 를 정상 설치한 PC 에서도 `shutil.which` 가 실패하고,
    `LIBREOFFICE_BIN` 을 손으로 지정하지 않으면 영원히 "없다" 로 보였다.
    """
    paths = [
        # macOS — 앱 번들 안이라 PATH 에 없다
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        # Linux (컨테이너 포함)
        "/usr/lib/libreoffice/program/soffice",
        "/opt/libreoffice/program/soffice",
    ]
    # Windows — 기본 설치 위치 셋. 환경변수로 풀어 32/64비트와 사용자 설치를 모두 본다.
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        root = os.environ.get(var)
        if root:
            paths.append(os.path.join(root, "LibreOffice", "program", "soffice.exe"))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        paths.append(os.path.join(local, "Programs", "LibreOffice", "program", "soffice.exe"))
    return paths


def soffice_binary() -> str | None:
    """soffice 실행 파일 경로. 없으면 None.

    `LIBREOFFICE_BIN` 으로 명시 지정할 수 있다. PATH 에 없고 알려진 자리에만 있는
    환경(macOS 앱 번들 · **Windows 기본 설치**)을 위해 후보 경로도 함께 확인한다.
    """
    configured = env_str("LIBREOFFICE_BIN", default=None)
    if configured:
        return configured if os.path.isfile(configured) and os.access(configured, os.X_OK) else None

    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found

    for candidate in _known_paths():
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def install_hint() -> str:
    """플랫폼에 맞는 안내. **리눅스 패키지 이름을 Windows 사용자에게 말하지 않는다.**"""
    if os.name == "nt":
        return (
            "LibreOffice 를 설치하면(기본 위치면 자동으로 찾습니다) 정본화를 씁니다. "
            "다른 위치에 설치했다면 LIBREOFFICE_BIN 환경변수로 soffice.exe 경로를 지정하세요."
        )
    return (
        "서버에 libreoffice-writer 를 설치하거나 LIBREOFFICE_BIN 환경변수로 "
        "경로를 지정하세요."
    )


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
            "LibreOffice(soffice)를 찾을 수 없습니다. " + install_hint()
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


def repack_docx(data: bytes) -> bytes:
    """같은 부품을 **표준 배치로** 다시 담는다 — 외부 프로그램이 필요 없다.

    고치는 것은 둘이고, 그 둘이 검출기가 거부하는 근거 전부다.

    ```
    `[Content_Types].xml` 을 **첫 엔트리**로 옮긴다
    디렉터리 엔트리(`word/`)를 **버린다** — 표준 패키지에는 없다
    ```

    **부품의 바이트는 손대지 않는다.** 읽어서 그대로 다시 쓴다 — 내용을 고치는 일이
    아니라 봉투를 다시 싸는 일이다. 그래서 `compare_documents()` 가 유실 0으로 나온다.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as source:
            names = [n for n in source.namelist() if not n.endswith("/")]
            if CONTENT_TYPES_ENTRY not in names:
                # 이건 배치 문제가 아니다 — docx 가 아니거나 깨졌다. 재포장이 못 고친다.
                raise DocxNormalizeFailed(
                    f"`{CONTENT_TYPES_ENTRY}` 가 없어 재포장할 수 없습니다. docx 가 아닙니다."
                )
            ordered = [CONTENT_TYPES_ENTRY] + [n for n in names if n != CONTENT_TYPES_ENTRY]
            parts = [(name, source.read(name)) for name in ordered]
    except zipfile.BadZipFile as exc:
        raise DocxNormalizeFailed("ZIP 패키지로 열리지 않아 재포장할 수 없습니다.") from exc

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for name, payload in parts:
            target.writestr(name, payload)
    result = out.getvalue()
    if not result:
        raise DocxNormalizeFailed("재포장 결과가 비어 있습니다.")
    return result


def canonicalize_docx(data: bytes, *, timeout_s: int | None = None) -> tuple[bytes, str, str | None]:
    """정본 패키지를 만든다 — **좋은 길을 먼저, 없으면 되는 길로.**

    돌려주는 것은 `(바이트, 쓴 방법, 떨어진 이유)` 셋이다. 방법을 같이 주는 이유는
    하나다 — 나중에 "이 문서가 ECM 에서 거부됐다" 를 되짚을 때 **어느 길로 나온
    문서인지**를 알아야 한다. 응답 헤더와 로그에 그 값을 싣는다.

    ```
    soffice 있고 성공   ("soffice", None)   — Word 로 다시 저장한 것과 같다
    soffice 있고 실패   ("repack", 사유)     — 500 으로 끝내지 않는다. 배치는 고쳐 준다
    soffice 없음        ("repack", 사유)     — Windows 납품 PC 의 기본값이다
    ```

    재포장도 못 하는 경우(= docx 가 아니다)만 `DocxNormalizeFailed` 로 올린다.
    """
    if is_available():
        try:
            return normalize_docx(data, timeout_s=timeout_s), "soffice", None
        except DocxNormalizeFailed as exc:
            # **조용히 재포장으로 넘어가지 않는다** — 왜 떨어졌는지 호출자에게 준다.
            return repack_docx(data), "repack", f"soffice 변환 실패: {exc}"
    return repack_docx(data), "repack", "LibreOffice(soffice)가 없습니다. " + install_hint()


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
