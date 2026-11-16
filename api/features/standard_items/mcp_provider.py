"""POSCO 표준항목 MCP 공급원 — streamable HTTP, 도구 `searchDataDictionary`.

- 연결 하나로 여러 키워드를 조회한다(`search_many`) — 속성마다 initialize 를 다시 하지 않는다.
- 시간 초과는 짧게(기본 5초/건, `ROBO_STANDARD_MCP_TIMEOUT`). 실패는 예외가 아니라
  `StandardLookup.error` 로 돌려준다 — 설계 흐름은 멈추지 않는다.
- 연결이 한 번 실패하면 잠깐(`_BACKOFF_S`) 다시 붙지 않는다. 사내망에서 닿지 않는 주소는
  시간 초과까지 매달리므로, 애그리거트마다 5초씩 쌓이지 않게 한다.
- 같은 키워드는 프로세스 안에서 잠깐(`_CACHE_TTL_S`) 기억한다 — 애그리거트마다 `주문번호` 를
  다시 묻지 않는다.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import timedelta
from typing import Any, Iterable

from api.features.standard_items.contracts import StandardItem, StandardLookup, now_iso

TOOL_NAME = "searchDataDictionary"
DEFAULT_TIMEOUT_S = 5.0
_BACKOFF_S = 60.0
_CACHE_TTL_S = 600.0
# 한 묶음(애그리거트 하나의 속성들) 전체에 거는 상한 — 건마다 timeout 이 있어도 합이 길어지지 않게.
_BATCH_CAP_S = 30.0

# MCP 결과 칸 → StandardItem 칸.
_FIELD_MAP: dict[str, str] = {
    "standardKoreanName": "standard_korean_name",
    "standardEnglishId": "standard_english_id",
    "stdItemValueType": "value_type",
    "dataLength": "data_length",
    "decimalLength": "decimal_length",
    "codeItem": "code_item",
    "mesUnitOfMeasure": "uom",
    "macroMicroItemType": "macro_micro_type",
    "supervisoryDept": "supervisory_dept",
    "standardItemStatus": "status",
    "standardItemDefinitionContent": "definition",
    "standardItemManagementMethodExplanation": "management_method",
}
_INT_FIELDS = {"data_length", "decimal_length"}


def _to_int(v: Any) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _to_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def entry_to_item(entry: dict[str, Any]) -> StandardItem | None:
    name = _to_str(entry.get("standardKoreanName"))
    if not name:
        return None
    kwargs: dict[str, Any] = {}
    for src, dst in _FIELD_MAP.items():
        v = entry.get(src)
        kwargs[dst] = _to_int(v) if dst in _INT_FIELDS else _to_str(v)
    kwargs["standard_korean_name"] = name
    return StandardItem(**kwargs, raw=dict(entry))


def _find_entries(obj: Any) -> list[dict[str, Any]]:
    """결과 모양을 아직 현장에서 못 봤다 — 목록 · {"result": [...]} · 단건 모두 받는다."""
    if isinstance(obj, list):
        out: list[dict[str, Any]] = []
        for x in obj:
            out.extend(_find_entries(x))
        return out
    if isinstance(obj, dict):
        if "standardKoreanName" in obj:
            return [obj]
        out = []
        for v in obj.values():
            if isinstance(v, (list, dict)):
                out.extend(_find_entries(v))
        return out
    return []


def parse_call_result(result: Any) -> list[StandardItem]:
    entries: list[dict[str, Any]] = []
    structured = getattr(result, "structuredContent", None)
    if structured:
        entries = _find_entries(structured)
    if not entries:
        for c in getattr(result, "content", None) or []:
            text = getattr(c, "text", None)
            if not text:
                continue
            try:
                entries.extend(_find_entries(json.loads(text)))
            except (ValueError, TypeError):
                continue
    items = [entry_to_item(e) for e in entries]
    return [it for it in items if it is not None]


def _timeout_from_env() -> float:
    try:
        v = float(os.getenv("ROBO_STANDARD_MCP_TIMEOUT") or DEFAULT_TIMEOUT_S)
        return v if v > 0 else DEFAULT_TIMEOUT_S
    except ValueError:
        return DEFAULT_TIMEOUT_S


class McpDataDictionaryProvider:
    def __init__(self, url: str, *, timeout_s: float | None = None, language_code: str = "KO"):
        self.url = url.strip()
        self.timeout_s = timeout_s if timeout_s is not None else _timeout_from_env()
        self.language_code = language_code
        self._down_until = 0.0
        self._down_reason = ""
        self._cache: dict[str, tuple[float, StandardLookup]] = {}

    @property
    def source(self) -> str:
        return f"posco-mcp:{self.url}"

    def _fail(self, keyword: str, error: str) -> StandardLookup:
        return StandardLookup(keyword, (), self.source, now_iso(), error)

    async def search(self, keyword: str) -> StandardLookup:
        return (await self.search_many([keyword]))[keyword]

    async def search_many(self, keywords: Iterable[str]) -> dict[str, StandardLookup]:
        wanted = [k for k in dict.fromkeys(str(k).strip() for k in keywords) if k]
        out: dict[str, StandardLookup] = {}
        now = time.monotonic()
        todo: list[str] = []
        for k in wanted:
            hit = self._cache.get(k)
            if hit and hit[0] > now:
                out[k] = hit[1]
            else:
                todo.append(k)
        if not todo:
            return out
        if now < self._down_until:
            for k in todo:
                out[k] = self._fail(k, f"직전 연결 실패 — 잠시 묻지 않는다({self._down_reason})")
            return out

        try:
            fetched = await asyncio.wait_for(
                self._query(todo), timeout=min(self.timeout_s * (len(todo) + 1), max(_BATCH_CAP_S, self.timeout_s * 2))
            )
        except Exception as e:  # noqa: BLE001 — 연결/시간 초과/프로토콜 모두 '표준 미확인'
            reason = "시간 초과" if isinstance(e, (asyncio.TimeoutError, TimeoutError)) else _short(e)
            self._down_until = time.monotonic() + _BACKOFF_S
            self._down_reason = reason
            for k in todo:
                out[k] = self._fail(k, reason)
            return out

        expires = time.monotonic() + _CACHE_TTL_S
        for k in todo:
            lk = fetched[k]
            out[k] = lk
            if lk.error is None:
                self._cache[k] = (expires, lk)
        return out

    async def _query(self, keywords: list[str]) -> dict[str, StandardLookup]:
        import httpx
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        per_call = timedelta(seconds=self.timeout_s)
        out: dict[str, StandardLookup] = {}
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s), follow_redirects=True
        ) as http, streamable_http_client(self.url, http_client=http) as (read, write, _sid):
            async with ClientSession(read, write, read_timeout_seconds=per_call) as session:
                await asyncio.wait_for(session.initialize(), timeout=self.timeout_s)
                for k in keywords:
                    try:
                        res = await session.call_tool(
                            TOOL_NAME,
                            {"keyword": k, "languageCode": self.language_code},
                            read_timeout_seconds=per_call,
                        )
                    except Exception as e:  # noqa: BLE001 — 한 건 실패는 그 건만
                        out[k] = self._fail(k, _short(e))
                        continue
                    if getattr(res, "isError", False):
                        text = " ".join(
                            getattr(c, "text", "") or "" for c in (res.content or [])
                        )
                        out[k] = self._fail(k, f"도구 오류: {text[:200]}")
                        continue
                    out[k] = StandardLookup(k, tuple(parse_call_result(res)), self.source, now_iso())
        return out


def _short(e: BaseException) -> str:
    # anyio 는 ExceptionGroup 으로 싸서 던진다 — 안쪽 첫 원인을 꺼낸다.
    inner = getattr(e, "exceptions", None)
    if inner:
        return _short(inner[0])
    msg = str(e).strip() or type(e).__name__
    return f"{type(e).__name__}: {msg}"[:200]
