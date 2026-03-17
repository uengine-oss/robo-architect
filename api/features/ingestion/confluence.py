"""
Confluence integration - fetch pages from Atlassian Confluence.

Tries the v1 REST API first (/wiki/rest/api/content) for broad compatibility,
falls back to v2 (/wiki/api/v2/pages) if v1 returns 404.
"""

from __future__ import annotations

import httpx
from html.parser import HTMLParser
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.platform.observability.smart_logger import SmartLogger

router = APIRouter(prefix="/api/ingest/confluence", tags=["confluence"])


class ConfluenceCredentials(BaseModel):
    email: str
    api_token: str
    base_url: str = "https://uengine-team.atlassian.net"


class PageFetchRequest(BaseModel):
    email: str
    api_token: str
    base_url: str = "https://uengine-team.atlassian.net"
    page_id: str


class _HTMLTextExtractor(HTMLParser):
    """Extract readable text from Confluence storage-format HTML."""

    def __init__(self):
        super().__init__()
        self.result: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.result.append("\n")
        if tag == "li":
            self.result.append("  - ")

    def handle_data(self, data):
        self.result.append(data)

    def get_text(self) -> str:
        return "".join(self.result).strip()


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def _check_auth(resp: httpx.Response):
    """Raise immediately on authentication errors. Log details for debugging."""
    if resp.status_code == 401:
        SmartLogger.log("WARNING", f"Confluence 401: {resp.text[:200]}", category="confluence.auth")
        raise HTTPException(status_code=401, detail="인증 실패: 이메일 또는 API 토큰을 확인하세요.")
    if resp.status_code == 403:
        SmartLogger.log("WARNING", f"Confluence 403 for {resp.url}: {resp.text[:300]}", category="confluence.auth")
        raise HTTPException(status_code=403, detail=f"접근 권한이 없습니다. (URL: {resp.url})")


# ---------------------------------------------------------------------------
# List pages
# ---------------------------------------------------------------------------

async def _list_pages_v1(client: httpx.AsyncClient, creds: ConfluenceCredentials) -> list[dict] | None:
    """Try the v1 REST API.  Returns None when v1 is not available (404)."""
    base = creds.base_url.rstrip("/")
    url: str | None = f"{base}/wiki/rest/api/content"
    params: dict | None = {"limit": 50, "type": "page"}

    pages: list[dict] = []

    while url:
        resp = await client.get(
            url, params=params,
            auth=(creds.email, creds.api_token),
            headers={"Accept": "application/json"},
        )
        _check_auth(resp)

        if resp.status_code == 404:
            return None  # v1 not available – caller should try v2

        resp.raise_for_status()
        data = resp.json()

        for p in data.get("results", []):
            pages.append({
                "id": p.get("id"),
                "title": p.get("title", "(제목 없음)"),
                "status": p.get("status"),
                "spaceId": p.get("space", {}).get("key"),
            })

        next_link = data.get("_links", {}).get("next")
        if next_link:
            url = f"{base}{next_link}"
            params = None
        else:
            url = None

    return pages


async def _list_pages_v2(client: httpx.AsyncClient, creds: ConfluenceCredentials) -> list[dict]:
    """Fallback: v2 Cloud API."""
    base = creds.base_url.rstrip("/")
    url: str | None = f"{base}/wiki/api/v2/pages"
    params: dict | None = {"limit": 50}

    pages: list[dict] = []

    while url:
        resp = await client.get(
            url, params=params,
            auth=(creds.email, creds.api_token),
            headers={"Accept": "application/json"},
        )
        _check_auth(resp)
        resp.raise_for_status()
        data = resp.json()

        for p in data.get("results", []):
            pages.append({
                "id": p.get("id"),
                "title": p.get("title", "(제목 없음)"),
                "status": p.get("status"),
                "spaceId": p.get("spaceId"),
            })

        next_link = data.get("_links", {}).get("next")
        if next_link:
            url = f"{base}{next_link}"
            params = None
        else:
            url = None

    return pages


@router.post("/pages")
async def list_confluence_pages(creds: ConfluenceCredentials) -> dict[str, Any]:
    """
    List Confluence pages using the provided credentials.
    Tries v1 REST API first, falls back to v2 if v1 returns 404.
    """
    SmartLogger.log(
        "INFO",
        "Confluence pages requested",
        category="confluence.pages.request",
        params={
            "email": creds.email,
            "base_url": creds.base_url,
            "token_length": len(creds.api_token),
            "token_prefix": creds.api_token[:8] + "...",
        },
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            pages = await _list_pages_v1(client, creds)
            if pages is None:
                SmartLogger.log("INFO", "v1 API returned 404, falling back to v2", category="confluence.pages")
                pages = await _list_pages_v2(client, creds)

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        SmartLogger.log("ERROR", f"Confluence API error: {e}", category="confluence.pages.error")
        raise HTTPException(status_code=502, detail=f"Confluence API 오류: {e.response.status_code}")
    except httpx.RequestError as e:
        SmartLogger.log("ERROR", f"Confluence connection error: {e}", category="confluence.pages.error")
        raise HTTPException(status_code=502, detail=f"Confluence 연결 실패: {str(e)}")
    except Exception as e:
        SmartLogger.log("ERROR", f"Confluence unexpected error: {type(e).__name__}: {e}", category="confluence.pages.error")
        raise HTTPException(status_code=502, detail=f"Confluence 오류: {type(e).__name__}: {str(e)}")

    SmartLogger.log("INFO", f"Fetched {len(pages)} Confluence pages", category="confluence.pages.done")
    return {"pages": pages, "total": len(pages)}


# ---------------------------------------------------------------------------
# Page content
# ---------------------------------------------------------------------------

async def _get_page_content_v1(client: httpx.AsyncClient, req: PageFetchRequest) -> dict | None:
    """v1: /wiki/rest/api/content/{id}?expand=body.storage"""
    base = req.base_url.rstrip("/")
    url = f"{base}/wiki/rest/api/content/{req.page_id}"
    params = {"expand": "body.storage"}

    resp = await client.get(
        url, params=params,
        auth=(req.email, req.api_token),
        headers={"Accept": "application/json"},
    )
    _check_auth(resp)

    if resp.status_code == 404:
        return None

    resp.raise_for_status()
    data = resp.json()
    title = data.get("title", "")
    body_html = data.get("body", {}).get("storage", {}).get("value", "")
    return {"title": title, "body_html": body_html}


async def _get_page_content_v2(client: httpx.AsyncClient, req: PageFetchRequest) -> dict:
    """v2: /wiki/api/v2/pages/{id}?body-format=storage"""
    base = req.base_url.rstrip("/")
    url = f"{base}/wiki/api/v2/pages/{req.page_id}"
    params = {"body-format": "storage"}

    resp = await client.get(
        url, params=params,
        auth=(req.email, req.api_token),
        headers={"Accept": "application/json"},
    )
    _check_auth(resp)

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="페이지를 찾을 수 없습니다.")

    resp.raise_for_status()
    data = resp.json()
    title = data.get("title", "")
    body_html = data.get("body", {}).get("storage", {}).get("value", "")
    return {"title": title, "body_html": body_html}


@router.post("/page-content")
async def get_confluence_page_content(req: PageFetchRequest) -> dict[str, Any]:
    """
    Fetch the content of a specific Confluence page.
    Returns extracted plain text.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await _get_page_content_v1(client, req)
            if result is None:
                result = await _get_page_content_v2(client, req)

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        SmartLogger.log("ERROR", f"Confluence page fetch error: {e}", category="confluence.page_content.error")
        raise HTTPException(status_code=502, detail=f"Confluence API 오류: {e.response.status_code}")
    except httpx.RequestError as e:
        SmartLogger.log("ERROR", f"Confluence connection error: {e}", category="confluence.page_content.error")
        raise HTTPException(status_code=502, detail=f"Confluence 연결 실패: {str(e)}")
    except Exception as e:
        SmartLogger.log("ERROR", f"Confluence unexpected error: {type(e).__name__}: {e}", category="confluence.page_content.error")
        raise HTTPException(status_code=502, detail=f"Confluence 오류: {type(e).__name__}: {str(e)}")

    title = result["title"]
    text = _html_to_text(result["body_html"]) if result["body_html"] else ""

    return {
        "page_id": req.page_id,
        "title": title,
        "content": text,
        "content_length": len(text),
    }
