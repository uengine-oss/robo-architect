"""Vision-LLM single-sentence describer for Figma components (spec 024).

Given a list of (figmaNodeId, name, image_url), downloads each thumbnail and
asks a vision-capable LLM to emit one sentence: kind + purpose. Failures
degrade to an empty description — never raise.

Provider abstraction is the existing `api.platform.llm.get_llm()`. Honors
`LLM_VISION_MODEL` env override (already used by feature 014).
"""

from __future__ import annotations

import asyncio
import base64
from typing import Iterable

import httpx
from langchain_core.messages import HumanMessage
from api.platform.llm_messages import build_system_message

from api.platform.env import env_str
from api.platform.llm import get_llm
from api.platform.observability.smart_logger import SmartLogger


_VLM_CONCURRENCY = 3
_PER_CALL_TIMEOUT_SEC = 60.0
_DOWNLOAD_TIMEOUT_SEC = 30.0

_VISION_MODEL_OVERRIDE = env_str("LLM_VISION_MODEL", default=None)

_SYSTEM_PROMPT = (
    "You receive a screenshot of a single UI component from a design system. "
    "In ONE sentence, describe (1) what kind of UI element it is "
    "(button, card, input, header/top-bar, list-item, modal, badge, chip, ...) "
    "and (2) its likely purpose / when to use it. "
    "Output ONLY that one sentence. No bullet points, no markdown, no preamble. "
    "Korean is preferred when the component's visible text is Korean; "
    "otherwise English."
)


async def _download_image(client: httpx.AsyncClient, url: str) -> tuple[bytes, str] | None:
    """Download an image and return (bytes, mime). None on failure."""
    try:
        resp = await client.get(url, timeout=_DOWNLOAD_TIMEOUT_SEC)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        SmartLogger.log(
            "WARN",
            f"figma_binding.components.vlm.image_download_failed url={url[:80]} err={e}",
            category="figma_binding.components.vlm.image_download_failed",
            params={"error": str(e)},
        )
        return None
    mime = resp.headers.get("content-type", "image/png").split(";")[0].strip() or "image/png"
    return resp.content, mime


async def _describe_one(
    sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    figma_node_id: str,
    name: str,
    image_url: str,
) -> tuple[str, str]:
    """Return (figma_node_id, description). Empty string on any failure."""
    async with sem:
        if image_url.startswith("data:"):
            # Plugin-pushed scan (no REST): the caller has already inlined the
            # PNG bytes as a data URI, so skip the HTTP fetch.
            data_url = image_url
        else:
            downloaded = await _download_image(client, image_url)
            if not downloaded:
                return figma_node_id, ""
            body, mime = downloaded
            data_url = f"data:{mime};base64,{base64.b64encode(body).decode('utf-8')}"

        kwargs: dict = {}
        if _VISION_MODEL_OVERRIDE:
            kwargs["model"] = _VISION_MODEL_OVERRIDE
        try:
            llm = get_llm(**kwargs)
        except Exception as e:  # noqa: BLE001
            SmartLogger.log(
                "WARN",
                f"figma_binding.components.vlm.llm_unavailable err={e}",
                category="figma_binding.components.vlm.llm_unavailable",
                params={"error": str(e)},
            )
            return figma_node_id, ""

        content = [
            {
                "type": "text",
                "text": f'Component name: "{name}". Describe this single UI component in one sentence.',
            },
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
        try:
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    llm.invoke,
                    [build_system_message(_SYSTEM_PROMPT), HumanMessage(content=content)],
                ),
                timeout=_PER_CALL_TIMEOUT_SEC,
            )
        except Exception as e:  # noqa: BLE001
            SmartLogger.log(
                "WARN",
                f"figma_binding.components.vlm.invoke_failed node={figma_node_id} err={e}",
                category="figma_binding.components.vlm.invoke_failed",
                params={"figmaNodeId": figma_node_id, "error": str(e)},
            )
            return figma_node_id, ""

        text = resp if isinstance(resp, str) else getattr(resp, "content", None)
        sentence = str(text or "").strip()
        if sentence.startswith("```"):
            sentence = sentence.strip("`").strip()
        sentence = sentence.replace("\n", " ").strip()
        return figma_node_id, sentence


async def describe_components(
    inputs: Iterable[tuple[str, str, str]],
    on_each: "callable | None" = None,
) -> dict[str, str]:
    """Describe each component with one VLM sentence.

    Args:
        inputs: iterable of (figma_node_id, name, image_url).
        on_each: optional callback fired after each task completes with
                 (figma_node_id, description). Used by spec 024 progress SSE
                 to surface "currently extracting X" in the UI. Best-effort:
                 a callback exception is logged but never aborts the scan.

    Returns:
        {figma_node_id: description} — missing entries / failures map to "".
    """
    items = [(nid, name, url) for nid, name, url in inputs if url]
    if not items:
        return {}

    sem = asyncio.Semaphore(_VLM_CONCURRENCY)
    out: dict[str, str] = {}

    async with httpx.AsyncClient() as client:
        tasks = [
            _describe_one(sem, client, nid, name, url) for nid, name, url in items
        ]
        for fut in asyncio.as_completed(tasks):
            try:
                nid, desc = await fut
                out[nid] = desc
                if on_each is not None:
                    try:
                        on_each(nid, desc)
                    except Exception as cb_err:  # noqa: BLE001
                        SmartLogger.log(
                            "WARN",
                            f"figma_binding.components.vlm.on_each_failed err={cb_err}",
                            category="figma_binding.components.vlm.on_each_failed",
                            params={"error": str(cb_err)},
                        )
            except Exception as e:  # noqa: BLE001
                SmartLogger.log(
                    "WARN",
                    f"figma_binding.components.vlm.task_crashed err={e}",
                    category="figma_binding.components.vlm.task_crashed",
                    params={"error": str(e)},
                )

    return out
