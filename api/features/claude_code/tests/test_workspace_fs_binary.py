"""workspace_fs 바이너리 판정 — 큰 한글 .md 가 바이너리로 오판되지 않아야 한다.

앞 8KB 샘플 경계가 한글 한 자(3바이트)를 자르면 strict decode 가 실패해
바이너리로 판정되던 회귀(lite ⑥).
"""

from __future__ import annotations

import pytest

from api.features.claude_code.workspace_fs import (
    BINARY_SNIFF_BYTES,
    _is_binary,
    read_text_file,
)


@pytest.mark.parametrize("prefix", ["", "a", "ab"])
def test_large_korean_md_is_text(tmp_path, prefix):
    # 경계 위치 세 가지(0·1·2 바이트 밀기) 모두에서 텍스트여야 한다.
    body = prefix + ("# 제안서\n\n한글 본문입니다. " * 1000)
    raw = body.encode("utf-8")
    assert len(raw) > 20 * 1024
    p = tmp_path / "proposal.md"
    p.write_bytes(raw)

    content, size, _mtime, binary = read_text_file(str(p))

    assert binary is False
    assert content == body
    assert size == len(raw)


def test_sample_cut_mid_character_is_not_binary():
    raw = ("가" * BINARY_SNIFF_BYTES).encode("utf-8")
    # 3바이트 문자 한가운데서 자른 샘플
    assert not _is_binary(raw[: BINARY_SNIFF_BYTES + 1])
    assert not _is_binary(raw[: BINARY_SNIFF_BYTES + 2])


def test_nul_byte_is_binary():
    assert _is_binary(b"abc\x00def")


def test_invalid_utf8_in_middle_is_binary():
    assert _is_binary(b"abc\xff\xfedef")


def test_invalid_utf8_past_sample_is_binary(tmp_path):
    p = tmp_path / "late.bin"
    p.write_bytes(b"a" * (BINARY_SNIFF_BYTES + 10) + b"\xff\xfe")
    content, _size, _mtime, binary = read_text_file(str(p))
    assert binary is True
    assert content is None
