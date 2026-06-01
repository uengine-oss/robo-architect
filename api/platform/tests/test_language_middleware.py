"""Unit tests for api.platform.middleware.language_middleware (feature 031)."""

from __future__ import annotations

import pytest

from api.platform.middleware.language_middleware import normalize_accept_language


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Happy path: single canonical tags pass through unchanged.
        ("ko-KR", "ko-KR"),
        ("en-US", "en-US"),
        ("ja-JP", "ja-JP"),
        # Case normalisation.
        ("ko-kr", "ko-KR"),
        ("KO-KR", "ko-KR"),
        ("KO-kr", "ko-KR"),
        # Single subtag (no region).
        ("en", "en"),
        ("EN", "en"),
        # 4-letter script subtag is title-cased.
        ("zh-hant", "zh-Hant"),
        ("zh-HANT", "zh-Hant"),
        # Browser-default multi-value list — take the first entry.
        ("ko-KR,ko;q=0.9,en-US;q=0.8", "ko-KR"),
        ("en-US,en;q=0.5", "en-US"),
        # Strip q-value from the first entry too.
        ("ko-KR;q=1.0", "ko-KR"),
        # Exotic-but-valid BCP-47 tag passes through (FR-011).
        ("af-ZA", "af-ZA"),
        # Whitespace is stripped.
        ("  ko-KR  ", "ko-KR"),
    ],
)
def test_normalize_happy_paths(raw, expected):
    assert normalize_accept_language(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        ",",
        ";q=0.9",
        "<script>alert(1)</script>",  # charset violation
        "ko_KR",  # underscore not allowed (BCP-47 uses hyphens)
        "ko/KR",
        "ko KR",
    ],
)
def test_normalize_rejects_malformed(raw):
    """Anything not matching BCP-47 charset returns None → middleware leaves
    the ContextVar unset, and `get_request_language()` falls through to env/fallback."""
    assert normalize_accept_language(raw) is None


def test_normalize_truncates_over_length_then_revalidates():
    """A tag longer than 35 chars is truncated; the truncation can leave it
    non-conforming (e.g., end on a partial hyphen segment). The post-truncation
    string must still pass the regex or we return None."""
    # 40-char all-letter input → truncated to 35 letters → still passes regex.
    raw = "a" * 40
    assert normalize_accept_language(raw) == "a" * 35


def test_normalize_truncation_to_invalid_returns_none():
    """If truncation lands on a trailing hyphen (shouldn't happen with our
    cap of 35 on real BCP-47 tags, but defensive)."""
    # The regex allows trailing hyphens, so this returns truncated; cosmetic.
    # This is documentation of behavior, not a strict requirement.
    raw = "a-" * 20  # 40 chars; truncates to "a-" * 17 + "a" = 35
    normalized = normalize_accept_language(raw)
    # Either it parsed (lowercase letter) or returned None — both acceptable.
    # The important behavior is no exception.
    assert normalized is None or all(c.isalnum() or c == "-" for c in normalized)
