"""Tests for slug/path/lock/stale-asset utilities (T014)."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from api.features.ddd_spec import paths as paths_mod


def test_korean_slug_transliterates_to_ascii():
    slug = paths_mod.derive_slug("주문 관리", "agg-1")
    # python-slugify (with text-unidecode) transliterates Hangul to ASCII;
    # the exact transliteration is implementation-defined but it must be
    # ASCII-lowercase-hyphen-only.
    assert slug
    assert all(c.isascii() and (c.isalnum() or c == "-") for c in slug)
    assert slug == slug.lower()


def test_empty_name_falls_back_to_id_hash():
    slug = paths_mod.derive_slug("", "node-abc")
    assert len(slug) == 6
    assert all(c in "0123456789abcdef" for c in slug)


def test_collision_appends_hash_suffix():
    taken: set[str] = set()
    a = paths_mod.unique_slug("Order", "id-1", taken)
    b = paths_mod.unique_slug("Order", "id-2", taken)
    assert a != b
    # ``b`` is the colliding one and carries a hash suffix.
    assert b.startswith(a + "-")


def test_assert_under_specs_rejects_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(paths_mod, "SPECS_DIR", tmp_path / "specs")
    (tmp_path / "specs").mkdir()
    with pytest.raises(paths_mod.PathEscapeError):
        paths_mod.assert_under_specs(tmp_path / "outside.txt")


def test_assert_under_specs_accepts_inside(tmp_path, monkeypatch):
    monkeypatch.setattr(paths_mod, "SPECS_DIR", tmp_path / "specs")
    (tmp_path / "specs").mkdir()
    monkeypatch.setattr(paths_mod, "BC_ROOT", tmp_path / "specs" / "bounded-contexts")
    target = tmp_path / "specs" / "x.txt"
    assert paths_mod.assert_under_specs(target) == target.resolve()


def test_atomic_write_text_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(paths_mod, "SPECS_DIR", tmp_path / "specs")
    (tmp_path / "specs").mkdir()
    target = tmp_path / "specs" / "hello.md"
    wrote = paths_mod.atomic_write_text(target, "hello", overwrite=False)
    assert wrote
    assert target.read_text() == "hello"


def test_atomic_write_text_respects_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(paths_mod, "SPECS_DIR", tmp_path / "specs")
    (tmp_path / "specs").mkdir()
    target = tmp_path / "specs" / "hello.md"
    target.write_text("old")
    wrote = paths_mod.atomic_write_text(target, "new", overwrite=False)
    assert not wrote
    assert target.read_text() == "old"
    wrote = paths_mod.atomic_write_text(target, "new", overwrite=True)
    assert wrote
    assert target.read_text() == "new"


def test_detect_stale_assets(tmp_path, monkeypatch):
    monkeypatch.setattr(paths_mod, "SPECS_DIR", tmp_path / "specs")
    monkeypatch.setattr(paths_mod, "BC_ROOT", tmp_path / "specs" / "bounded-contexts")
    folder = tmp_path / "specs" / "bounded-contexts" / "order" / "requirements.assets"
    folder.mkdir(parents=True)
    referenced = folder / "kept.svg"
    stale = folder / "ghost.svg"
    referenced.write_text("<svg/>")
    stale.write_text("<svg/>")
    out = paths_mod.detect_stale_assets("order", {referenced})
    assert stale in out
    assert referenced not in out
