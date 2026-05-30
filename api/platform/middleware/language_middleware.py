"""
FastAPI middleware: capture the per-request generation language (feature 031).

Reads the standard HTTP `Accept-Language` header on every inbound request,
normalises it to a single BCP-47 tag, and writes it into the language
ContextVar so downstream LLM prompt construction (`build_system_message`)
picks it up automatically.

Header absence is fine — `get_request_language()` falls through to
`GENERATION_LANGUAGE_DEFAULT` (env, defaults to "en-US"). The SPA sets a
single canonical tag via its bootstrap fetch interceptor; this normalisation
also handles browser-default multi-value lists (e.g. `ko-KR,ko;q=0.9,en-US;q=0.8`)
for non-SPA clients.
"""

from __future__ import annotations

import re

from starlette.requests import Request
from starlette.responses import Response

from api.platform.language import clear_request_language, set_request_language

# BCP-47 tag character set + sane length cap (RFC 5646 allows up to 35 chars
# in extreme cases). Defensive against pathological header values from
# misbehaving clients or attempted log-injection.
_TAG_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")
_MAX_TAG_LENGTH = 35


def normalize_accept_language(raw: str | None) -> str | None:
    """Normalize an inbound `Accept-Language` header value to a single BCP-47 tag.

    - Splits on `,`, takes the first entry (highest-preference language).
    - Strips any `;q=...` suffix.
    - Lowercases the language subtag, uppercases the region subtag.
    - Rejects (returns None) on empty, non-BCP-47 charset, or over-length.

    Returns the normalised tag, or None if the value cannot be parsed.
    """
    if not raw:
        return None

    # Take the first comma-separated entry.
    first = raw.split(",", 1)[0].strip()
    if not first:
        return None

    # Drop the q-value suffix if present.
    tag = first.split(";", 1)[0].strip()
    if not tag:
        return None

    # Length cap before regex to avoid pathological inputs hitting the regex engine.
    if len(tag) > _MAX_TAG_LENGTH:
        tag = tag[:_MAX_TAG_LENGTH]

    if not _TAG_PATTERN.match(tag):
        return None

    # Canonicalise case: language→lower, region→upper, leave private/extension
    # subtags as-is. Most tags are 2-subtag (e.g. "ko-KR"); fall through cleanly
    # for single-subtag ("en") or richer ("zh-Hant-TW") forms.
    parts = tag.split("-")
    parts[0] = parts[0].lower()
    if len(parts) >= 2:
        # The second subtag is typically a region (2-letter) or script (4-letter).
        # Uppercase 2-letter regions; title-case 4-letter scripts.
        sub = parts[1]
        if len(sub) == 2:
            parts[1] = sub.upper()
        elif len(sub) == 4:
            parts[1] = sub[0].upper() + sub[1:].lower()
    return "-".join(parts)


async def language_middleware(request: Request, call_next) -> Response:
    """Read Accept-Language → normalise → set ContextVar → process request → clear.

    Registered AFTER the request-id middleware in `api.main` so the language
    log field appears alongside the request_id in every structured log line.
    """
    tag = normalize_accept_language(request.headers.get("accept-language"))
    set_request_language(tag)
    try:
        return await call_next(request)
    finally:
        # Defensive: avoid leaking into unrelated async contexts (mirrors the
        # request_id middleware's cleanup pattern).
        clear_request_language()
