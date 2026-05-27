"""Read-only Figma REST client for validating a file key + token.

Self-contained for feature 016 — does NOT import 009's `figma_api.py`
(cross-feature import would violate Constitution V).
"""

from __future__ import annotations

from typing import TypedDict

import httpx


FIGMA_API_BASE = "https://api.figma.com"
DEFAULT_TIMEOUT_SEC = 10.0


class FigmaFileMetadata(TypedDict, total=False):
    ok: bool
    fileName: str
    error: str  # populated when ok=False


def _format_429(resp: httpx.Response) -> str:
    retry_after = resp.headers.get("retry-after")
    plan_tier = resp.headers.get("x-figma-plan-tier")
    limit_type = resp.headers.get("x-figma-rate-limit-type")

    wait_part = ""
    if retry_after:
        try:
            secs = int(float(retry_after))
            if secs >= 3600:
                wait_part = f" 약 {secs // 3600}시간 {(secs % 3600) // 60}분 후 재시도 가능."
            elif secs >= 60:
                wait_part = f" 약 {secs // 60}분 후 재시도 가능."
            else:
                wait_part = f" {secs}초 후 재시도 가능."
        except ValueError:
            wait_part = f" Retry-After: {retry_after}."

    plan_part = ""
    if plan_tier or limit_type:
        bits = [b for b in (plan_tier, limit_type and f"{limit_type} 카테고리") if b]
        plan_part = f" (Figma 플랜: {', '.join(bits)})"

    return f"Figma API 호출 한도를 초과했습니다 (429).{wait_part}{plan_part}"


async def validate_file(file_key: str, api_token: str) -> FigmaFileMetadata:
    """Fetch minimal file metadata. Returns {ok, fileName} on success
    or {ok: False, error: <korean message>} on failure.

    No retries — the user is waiting on the connect modal. Network glitches
    surface as an immediate "접근할 수 없습니다" with the underlying detail.
    """
    if not file_key:
        return {"ok": False, "error": "Figma 파일 키가 비어 있습니다."}
    if not api_token:
        return {"ok": False, "error": "Figma 토큰이 비어 있습니다."}

    headers = {"X-Figma-Token": api_token}
    url = f"{FIGMA_API_BASE}/v1/files/{file_key}?depth=1"

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SEC) as client:
            resp = await client.get(url, headers=headers)
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"Figma 응답 시간이 초과되었거나 네트워크 오류입니다: {e!s}"}

    if resp.status_code == 401 or resp.status_code == 403:
        return {"ok": False, "error": "Figma 토큰이 유효하지 않거나 파일 접근 권한이 없습니다."}
    if resp.status_code == 404:
        return {"ok": False, "error": f"Figma 파일을 찾을 수 없습니다 (file_key={file_key})."}
    if resp.status_code == 429:
        return {"ok": False, "error": _format_429(resp)}
    if resp.status_code >= 400:
        return {"ok": False, "error": f"Figma API 오류 ({resp.status_code})."}

    try:
        data = resp.json()
    except Exception:
        return {"ok": False, "error": "Figma 응답을 해석할 수 없습니다."}

    name = data.get("name") or "Untitled"
    return {"ok": True, "fileName": str(name)}
