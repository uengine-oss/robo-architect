"""Phase 4.0: split the raw document into retrievable passages.

Strategy:
  1. Heading-based — detect Korean/numeric headings (1., 1.1, 제N조, ### Title).
     Cut the document at each heading; each chunk = heading + body until next heading.
  2. If heading split yields <3 chunks or average chunk size is too large (>2000 chars),
     fall back to a sliding char-window.

Page hints are extracted from form-feed (\f) markers if the PDF extractor
inserted them; otherwise page stays None.
"""

from __future__ import annotations

import hashlib
import re

from api.features.ingestion.hybrid.contracts import DocumentPassage

_WINDOW_CHARS = 400
_WINDOW_OVERLAP = 80
_MIN_HEADING_CHUNKS = 3
_MAX_AVG_CHUNK = 2000

_HEADING_RE = re.compile(
    r"""^\s*(
        (?:제\s*\d+\s*(?:조|장|절|항))           # 제1조 / 제2장 / 제3절
        |   (?:\d+(?:\.\d+){0,3}\.?)\s+\S        # 1. / 1.1 / 1.1.1 Title
        |   (?:[IVXLC]+\.)\s+\S                  # Roman numerals
        |   \#{1,6}\s+\S                         # Markdown #
        |   [■◆▶▷▣]\s*\S                         # bullet glyphs often used as headings
    )""",
    re.VERBOSE,
)

_PAGE_BREAK = "\f"


def _passage_id(seq: int, heading: str, text: str) -> str:
    h = hashlib.sha1((heading + "|" + text[:200]).encode("utf-8")).hexdigest()[:10]
    return f"passage_{seq:04d}_{h}"


def _page_map(text: str) -> list[tuple[int, int]]:
    """Return list of (char_offset, page_number) for page breaks in the text."""
    pages: list[tuple[int, int]] = [(0, 1)]
    cursor = 0
    page = 1
    for i, ch in enumerate(text):
        if ch == _PAGE_BREAK:
            page += 1
            pages.append((i + 1, page))
            cursor = i
    return pages


def _page_at(pages: list[tuple[int, int]], offset: int) -> int | None:
    cur: int | None = None
    for off, p in pages:
        if off <= offset:
            cur = p
        else:
            break
    return cur


def _heading_split(text: str) -> list[tuple[str, int, int]]:
    """Return list of (heading, start, end) per chunk."""
    lines = text.splitlines(keepends=True)
    boundaries: list[tuple[int, str]] = []  # (line_start_offset, heading_line)
    offset = 0
    for line in lines:
        stripped = line.strip()
        if stripped and _HEADING_RE.match(line):
            boundaries.append((offset, stripped))
        offset += len(line)
    if not boundaries:
        return [("", 0, len(text))]
    results: list[tuple[str, int, int]] = []
    boundaries.append((len(text), ""))  # sentinel end
    for i in range(len(boundaries) - 1):
        start, heading = boundaries[i]
        end = boundaries[i + 1][0]
        results.append((heading, start, end))
    # Optional preamble chunk
    if boundaries[0][0] > 0:
        results.insert(0, ("(preamble)", 0, boundaries[0][0]))
    return results


def _window_split(text: str) -> list[tuple[str, int, int]]:
    results: list[tuple[str, int, int]] = []
    n = len(text)
    step = max(1, _WINDOW_CHARS - _WINDOW_OVERLAP)
    for start in range(0, n, step):
        end = min(n, start + _WINDOW_CHARS)
        results.append(("", start, end))
        if end == n:
            break
    return results


def chunk_document(text: str) -> list[DocumentPassage]:
    if not text or not text.strip():
        return []

    pages = _page_map(text)
    method = "heading"
    segments = _heading_split(text)

    # Fallback: too few chunks or chunks too large on average → window split
    if segments:
        sizes = [(e - s) for _, s, e in segments]
        avg = sum(sizes) / max(1, len(sizes))
        if len(segments) < _MIN_HEADING_CHUNKS or avg > _MAX_AVG_CHUNK:
            method = "window"
            segments = _window_split(text)
    else:
        method = "window"
        segments = _window_split(text)

    passages: list[DocumentPassage] = []
    for idx, (heading, start, end) in enumerate(segments):
        body = text[start:end].strip()
        if not body:
            continue
        page = _page_at(pages, start)
        pid = _passage_id(idx, heading, body)
        passages.append(DocumentPassage(
            id=pid,
            heading=heading or None,
            text=body,
            page=page,
            char_start=start,
            char_end=end,
            chunk_method=method,
        ))
    return passages
