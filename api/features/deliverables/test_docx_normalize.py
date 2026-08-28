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
