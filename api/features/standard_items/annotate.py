"""속성 행에 표준항목을 붙인다 — 속성 생성 단계가 저장 직전에 부른다.

공급원이 없으면(`ROBO_STANDARD_MCP_URL` 비어 있음) 행을 **그대로** 돌려준다 — 표준 칸을 만들지
않으므로 저장 쿼리도 표준 칸을 건드리지 않는다. 공급원이 있어도 실패는 `unverified` 로 남고
예외는 밖으로 나가지 않는다.
"""

from __future__ import annotations

import os
from typing import Any

from api.features.standard_items.contracts import StandardItemProvider, StandardLookup, now_iso
from api.features.standard_items.matching import (
    match_property,
    normalize_name,
    property_standard_fields,
)
from api.platform.observability.smart_logger import SmartLogger

_provider: StandardItemProvider | None = None
_provider_key: str | None = None


def get_standard_provider() -> StandardItemProvider | None:
    """`.env` 로 켜고 끈다. 지금 공급원은 POSCO MCP 하나 — 그룹사망 공급원은 여기에 더한다."""
    global _provider, _provider_key
    url = (os.getenv("ROBO_STANDARD_MCP_URL") or "").strip()
    if not url:
        return None
    if _provider is None or _provider_key != url:
        from api.features.standard_items.mcp_provider import McpDataDictionaryProvider

        _provider = McpDataDictionaryProvider(url)
        _provider_key = url
    return _provider


def _keyword(row: dict[str, Any]) -> str:
    # 한글 이름이 표준항목명과 맞는다. displayName 이 없으면 name(영문 camelCase) 으로 묻는다.
    return str(row.get("displayName") or row.get("name") or "").strip()


def _search_forms(keyword: str) -> list[str]:
    """LLM 이 붙인 이름은 `주문 번호` 처럼 빈칸이 있고 표준항목명은 보통 `주문번호` 다 —
    빈칸을 뺀 꼴을 먼저, 다르면 원래 꼴도 묻는다(가짜 서버로 재 보니 빈칸 꼴은 0건이었다)."""
    compact = normalize_name(keyword)
    return [compact] if compact == keyword else [compact, keyword]


def _merge(keyword: str, parts: list[StandardLookup]) -> StandardLookup:
    ok = [p for p in parts if p.error is None]
    if not ok:
        return StandardLookup(keyword, (), parts[0].source, parts[0].checked_at, parts[0].error)
    seen: set[tuple] = set()
    items = []
    for p in ok:
        for it in p.items:
            key = (it.standard_korean_name, it.standard_english_id)
            if key not in seen:
                seen.add(key)
                items.append(it)
    return StandardLookup(keyword, tuple(items), ok[0].source, ok[0].checked_at)


async def annotate_property_rows(
    rows: list[dict[str, Any]],
    provider: StandardItemProvider | None = None,
    *,
    use_default: bool = True,
) -> list[dict[str, Any]]:
    if provider is None and use_default:
        provider = get_standard_provider()
    if provider is None or not rows:
        return rows

    keywords = list(dict.fromkeys(k for k in (_keyword(r) for r in rows) if k))
    forms = list(dict.fromkeys(f for k in keywords for f in _search_forms(k)))
    try:
        search_many = getattr(provider, "search_many", None)
        if search_many is not None:
            raw: dict[str, StandardLookup] = await search_many(forms)
        else:
            raw = {f: await provider.search(f) for f in forms}
        lookups = {k: _merge(k, [raw[f] for f in _search_forms(k) if f in raw]) for k in keywords}
    except Exception as e:  # noqa: BLE001 — 공급원이 계약을 어겨도 설계는 계속한다
        SmartLogger.log(
            "WARNING",
            "Standard item lookup failed — properties left unverified",
            category="ingestion.standard_items",
            params={"source": getattr(provider, "source", "?"), "error": str(e)[:300]},
        )
        lookups = {}

    out: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for r in rows:
        k = _keyword(r)
        lk = lookups.get(k) or StandardLookup(
            k, (), getattr(provider, "source", "?"), now_iso(), "조회 결과 없음(공급원 오류)"
        )
        result = match_property(k, lk)
        counts[result.state] = counts.get(result.state, 0) + 1
        out.append({**r, **property_standard_fields(result, lk)})

    SmartLogger.log(
        "INFO",
        "Standard items annotated",
        category="ingestion.standard_items",
        params={"source": getattr(provider, "source", "?"), "rows": len(rows), "counts": counts},
    )
    return out

