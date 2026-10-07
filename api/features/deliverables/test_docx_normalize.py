from __future__ import annotations

import io
import zipfile

import pytest

from api.features.deliverables import docx_normalize as dn


def _docx(entries, *, content_types_first=True, with_dir_entry=False):
    """docx 패키지를 메모리에 만든다.

    `content_types_first=False` 로 두면 브라우저(docx+jszip) 산출물과 같은
    비정본 구조가 된다 — ECM 검출기가 거부하는 그 형태.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if content_types_first:
            zf.writestr(dn.CONTENT_TYPES_ENTRY, "<Types/>")
        if with_dir_entry:
            zf.writestr("word/", "")
        for name, data in entries.items():
            zf.writestr(name, data)
        if not content_types_first:
            zf.writestr(dn.CONTENT_TYPES_ENTRY, "<Types/>")
    return buf.getvalue()


def _body(paragraphs=1, tables=0, rows=0, text="본문"):
    xml = "<w:document><w:body>"
    xml += "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for _ in range(paragraphs))
    xml += "".join("<w:tbl></w:tbl>" for _ in range(tables))
    xml += "".join("<w:tr></w:tr>" for _ in range(rows))
    xml += "</w:body></w:document>"
    return xml.encode("utf-8")


# ---------------------------------------------------------------------------
# ECM 호환성 판정
# ---------------------------------------------------------------------------


def test_canonical_package_is_ecm_compatible():
    data = _docx({"word/document.xml": _body()})
    result = dn.inspect_docx_package(data)

    assert result["valid"] is True
    assert result["ecmCompatible"] is True
    assert result["reasons"] == []
    assert result["firstEntry"] == dn.CONTENT_TYPES_ENTRY
    assert result["contentTypesFirst"] is True
    assert result["hasDirectoryEntries"] is False


def test_content_types_not_first_is_rejected():
    """브라우저 산출물의 대표적 결함 — 검출기가 application/zip 으로 본다."""
    data = _docx({"word/document.xml": _body()}, content_types_first=False)
    result = dn.inspect_docx_package(data)

    assert result["ecmCompatible"] is False
    assert result["contentTypesFirst"] is False
    assert any("첫 엔트리가 아닙니다" in r for r in result["reasons"])


def test_directory_entries_are_rejected():
    data = _docx({"word/document.xml": _body()}, with_dir_entry=True)
    result = dn.inspect_docx_package(data)

    assert result["ecmCompatible"] is False
    assert result["hasDirectoryEntries"] is True
    assert any("디렉토리 엔트리" in r for r in result["reasons"])


def test_missing_document_part_is_rejected():
    data = _docx({"word/styles.xml": b"<styles/>"})
    result = dn.inspect_docx_package(data)

    assert result["ecmCompatible"] is False
    assert result["hasDocumentPart"] is False


def test_non_zip_payload_is_reported_not_raised():
    result = dn.inspect_docx_package(b"not a zip at all")

    assert result["valid"] is False
    assert result["ecmCompatible"] is False
    assert result["entryCount"] == 0


def test_multiple_defects_are_all_reported():
    data = _docx({"word/document.xml": _body()}, content_types_first=False, with_dir_entry=True)
    result = dn.inspect_docx_package(data)

    assert len(result["reasons"]) == 2


# ---------------------------------------------------------------------------
# 정본화 전후 유실 검증
# ---------------------------------------------------------------------------


def test_lossless_when_content_preserved():
    before = _docx({"word/document.xml": _body(paragraphs=3, tables=2, rows=6)})
    after = _docx({"word/document.xml": _body(paragraphs=3, tables=2, rows=6)}, content_types_first=True)
    diff = dn.compare_documents(before, after)

    assert diff["lossless"] is True
    assert diff["losses"] == []
    assert diff["before"]["tables"] == 2
    assert diff["before"]["paragraphs"] == 3


def test_table_loss_is_detected():
    before = _docx({"word/document.xml": _body(tables=5)})
    after = _docx({"word/document.xml": _body(tables=3)})
    diff = dn.compare_documents(before, after)

    assert diff["lossless"] is False
    assert any("표 5 → 3" in loss for loss in diff["losses"])


def test_image_loss_is_detected():
    before = _docx({"word/document.xml": _body(), "word/media/image1.png": b"\x89PNG"})
    after = _docx({"word/document.xml": _body()})
    diff = dn.compare_documents(before, after)

    assert diff["lossless"] is False
    assert any("이미지 1 → 0" in loss for loss in diff["losses"])


def test_text_loss_is_detected():
    before = _docx({"word/document.xml": _body(paragraphs=10, text="가나다라마바사")})
    after = _docx({"word/document.xml": _body(paragraphs=2, text="가나다라마바사")})
    diff = dn.compare_documents(before, after)

    assert diff["lossless"] is False
    assert any("본문 길이" in loss for loss in diff["losses"])


def test_whitespace_only_change_is_not_a_loss():
    """변환기의 공백 정규화를 유실로 오판하지 않는다."""
    before = _docx({"word/document.xml": _body(text="가 나  다")})
    after = _docx({"word/document.xml": _body(text="가나다")})
    diff = dn.compare_documents(before, after)

    assert diff["lossless"] is True


def test_extra_paragraphs_are_not_a_loss():
    """LibreOffice 가 문단을 재구성해 늘어나는 것은 문제가 아니다."""
    before = _docx({"word/document.xml": _body(paragraphs=2)})
    after = _docx({"word/document.xml": _body(paragraphs=5)})
    diff = dn.compare_documents(before, after)

    assert diff["lossless"] is True


# ---------------------------------------------------------------------------
# LibreOffice 부재 처리
# ---------------------------------------------------------------------------


def test_normalize_raises_clear_error_without_libreoffice(monkeypatch):
    """설치돼 있지 않으면 빈 파일이나 성공 응답이 아니라 명확한 오류다."""
    monkeypatch.setattr(dn, "soffice_binary", lambda: None)

    with pytest.raises(dn.DocxNormalizeUnavailable) as exc:
        dn.normalize_docx(_docx({"word/document.xml": _body()}))

    assert "LIBREOFFICE_BIN" in str(exc.value)


def test_binary_lookup_honors_env_override(monkeypatch, tmp_path):
    fake = tmp_path / "soffice"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv("LIBREOFFICE_BIN", str(fake))

    assert dn.soffice_binary() == str(fake)
    assert dn.is_available() is True


def test_binary_lookup_rejects_nonexistent_override(monkeypatch):
    monkeypatch.setenv("LIBREOFFICE_BIN", "/nowhere/soffice")

    assert dn.soffice_binary() is None
    assert dn.is_available() is False

# ---------------------------------------------------------------------------
# LibreOffice 없이 정본화 — 재포장 (2026-10-07)
# ---------------------------------------------------------------------------


def test_repack_fixes_both_reasons_the_detector_uses():
    """`inspect` 가 대는 근거는 **둘뿐**이고, 둘 다 ZIP 배치 문제다."""
    broken = _docx(
        {"word/document.xml": _body(tables=1)}, content_types_first=False, with_dir_entry=True
    )
    assert dn.inspect_docx_package(broken)["ecmCompatible"] is False

    fixed = dn.repack_docx(broken)
    after = dn.inspect_docx_package(fixed)

    assert after["ecmCompatible"] is True
    assert after["reasons"] == []
    assert after["firstEntry"] == dn.CONTENT_TYPES_ENTRY
    assert after["hasDirectoryEntries"] is False


def test_repack_does_not_lose_content():
    """봉투를 다시 싸는 일이다 — **부품의 바이트는 손대지 않는다.**

    ECM 판정만 통과시키고 내용을 깎으면 지금보다 나쁘다. 앱의 비교 함수로 센다.
    """
    broken = _docx(
        {"word/document.xml": _body(paragraphs=3, tables=2, rows=4)},
        content_types_first=False,
        with_dir_entry=True,
    )
    fixed = dn.repack_docx(broken)

    diff = dn.compare_documents(broken, fixed)
    assert diff["lossless"] is True
    assert diff["losses"] == []
    # 본문 파트가 **바이트 그대로**인지까지 본다 — 지표가 같아도 다를 수 있다.
    original = zipfile.ZipFile(io.BytesIO(broken)).read("word/document.xml")
    repacked = zipfile.ZipFile(io.BytesIO(fixed)).read("word/document.xml")
    assert repacked == original


def test_repack_refuses_what_it_cannot_fix():
    """docx 가 아니면 **고친 척하지 않는다** — 배치 문제가 아니기 때문이다."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", _body())  # [Content_Types].xml 이 없다

    with pytest.raises(dn.DocxNormalizeFailed) as exc:
        dn.repack_docx(buf.getvalue())
    assert dn.CONTENT_TYPES_ENTRY in str(exc.value)

    with pytest.raises(dn.DocxNormalizeFailed):
        dn.repack_docx(b"not a zip at all")


# ---------------------------------------------------------------------------
# 입구 — 좋은 길을 먼저, 없으면 되는 길로
# ---------------------------------------------------------------------------


def test_canonicalize_uses_soffice_when_present(monkeypatch):
    monkeypatch.setattr(dn, "is_available", lambda: True)
    monkeypatch.setattr(dn, "normalize_docx", lambda data, timeout_s=None: b"PK-from-soffice")

    out, method, reason = dn.canonicalize_docx(_docx({"word/document.xml": _body()}))

    assert (out, method, reason) == (b"PK-from-soffice", "soffice", None)


def test_canonicalize_repacks_when_soffice_missing(monkeypatch):
    """Windows 납품 PC 의 기본값이다 — **503 으로 끝나지 않는다.**"""
    monkeypatch.setattr(dn, "is_available", lambda: False)
    broken = _docx({"word/document.xml": _body()}, content_types_first=False)

    out, method, reason = dn.canonicalize_docx(broken)

    assert method == "repack"
    assert "LibreOffice" in reason
    assert dn.inspect_docx_package(out)["ecmCompatible"] is True


def test_canonicalize_falls_back_but_says_why(monkeypatch):
    """soffice 가 있는데 실패하면 재포장으로 떨어지고 **이유를 들고 온다.**

    조용히 떨어지면 "soffice 가 멀쩡히 돌고 있다" 는 착각이 남는다.
    """
    monkeypatch.setattr(dn, "is_available", lambda: True)

    def boom(data, timeout_s=None):
        raise dn.DocxNormalizeFailed("rc=1 프로필 락")

    monkeypatch.setattr(dn, "normalize_docx", boom)
    broken = _docx({"word/document.xml": _body()}, content_types_first=False, with_dir_entry=True)

    out, method, reason = dn.canonicalize_docx(broken)

    assert method == "repack"
    assert "rc=1" in reason
    assert dn.inspect_docx_package(out)["ecmCompatible"] is True


# ---------------------------------------------------------------------------
# 납품 대상은 Windows 다 (2026-10-07)
# ---------------------------------------------------------------------------


def test_known_paths_include_windows_default_install(monkeypatch):
    """**이 자리가 비어 있었다.** Windows 설치 관리자는 PATH 에 넣지 않는다 —
    후보 경로에 없으면 정상 설치한 PC 에서도 영원히 "없다" 로 보인다.
    """
    monkeypatch.setenv("ProgramFiles", r"C:\Program Files")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\u\AppData\Local")

    paths = dn._known_paths()

    assert any(p.endswith(r"LibreOffice\program\soffice.exe") for p in paths), paths
    assert any("Program Files" in p for p in paths)
    assert any("AppData" in p for p in paths)
    # 다른 운영체제 자리도 그대로 있어야 한다 — 맥·컨테이너에서 쓰는 길이다.
    assert "/usr/lib/libreoffice/program/soffice" in paths


def test_hint_does_not_tell_windows_users_to_install_a_linux_package(monkeypatch):
    """`libreoffice-writer` 는 Windows 에 **없는 패키지 이름**이다 — 막다른 안내였다."""
    monkeypatch.setattr(dn.os, "name", "nt")
    hint = dn.install_hint()
    assert "libreoffice-writer" not in hint
    assert "soffice.exe" in hint

    monkeypatch.setattr(dn.os, "name", "posix")
    assert "libreoffice-writer" in dn.install_hint()
