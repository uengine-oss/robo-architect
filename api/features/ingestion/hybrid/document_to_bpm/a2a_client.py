"""Thin A2A client for the external pdf2bpmn agent.

Ported from uengine-oss/process-gpt-bpmn-extractor/src/pdf2bpmn/a2a/client.py
but depends only on httpx and our local config (no pydantic protocol models —
the response bodies are simple JSON dicts and we tolerate minor schema drift).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import httpx

from api.features.ingestion.hybrid.document_to_bpm.config import (
    a2a_server_url,
    a2a_timeout_s,
)


class A2AClient:
    """Minimal async client for the pdf2bpmn A2A server."""

    def __init__(self, server_url: Optional[str] = None, timeout_s: Optional[float] = None):
        self.server_url = (server_url or a2a_server_url()).rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_s if timeout_s is not None else a2a_timeout_s())

    async def discover(self) -> dict[str, Any]:
        r = await self._client.get(f"{self.server_url}/discover")
        r.raise_for_status()
        return r.json()

    async def execute(
        self,
        pdf_path: Optional[str] = None,
        pdf_url: Optional[str] = None,
        pdf_file_name: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if not pdf_path and not pdf_url:
            raise ValueError("Either pdf_path or pdf_url must be provided")
        if pdf_path:
            pdf_path = str(Path(pdf_path).absolute())
            pdf_file_name = pdf_file_name or Path(pdf_path).name
        payload = {
            "input": {
                "pdf_url": pdf_url,
                "pdf_path": pdf_path,
                "pdf_file_name": pdf_file_name,
            },
            "task_id": task_id,
        }
        r = await self._client.post(f"{self.server_url}/execute", json=payload)
        r.raise_for_status()
        return r.json()

    async def get_status(self, task_id: str) -> dict[str, Any]:
        r = await self._client.get(f"{self.server_url}/status/{task_id}")
        r.raise_for_status()
        return r.json()

    async def get_result(self, task_id: str) -> dict[str, Any]:
        r = await self._client.get(f"{self.server_url}/result/{task_id}")
        r.raise_for_status()
        return r.json()

    async def cancel(self, task_id: str) -> dict[str, Any]:
        r = await self._client.delete(f"{self.server_url}/task/{task_id}")
        r.raise_for_status()
        return r.json()

    async def stream_events(self, task_id: str) -> AsyncGenerator[dict[str, Any], None]:
        async with self._client.stream(
            "GET",
            f"{self.server_url}/events/{task_id}",
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()
            buffer = ""
            async for chunk in response.aiter_bytes():
                buffer += chunk.decode("utf-8", errors="ignore")
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    event = _parse_sse_block(block)
                    if event:
                        yield event

    async def wait_for_completion(
        self,
        task_id: str,
        poll_interval: float = 1.0,
    ) -> dict[str, Any]:
        while True:
            status = await self.get_status(task_id)
            state = status.get("status")
            if state == "completed":
                return await self.get_result(task_id)
            if state == "failed":
                result = await self.get_result(task_id)
                raise RuntimeError(f"A2A task failed: {result.get('error') or result}")
            if state == "cancelled":
                raise RuntimeError("A2A task cancelled")
            await asyncio.sleep(poll_interval)

    async def aclose(self) -> None:
        await self._client.aclose()


def _parse_sse_block(block: str) -> Optional[dict[str, Any]]:
    lines = [ln for ln in block.strip().splitlines() if ln and not ln.startswith(":")]
    if not lines:
        return None
    event: dict[str, Any] = {}
    data_buf: list[str] = []
    for line in lines:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.lstrip()
        if key == "event":
            event["event_type"] = value
        elif key == "data":
            data_buf.append(value)
    if data_buf:
        raw = "\n".join(data_buf)
        try:
            event["data"] = json.loads(raw)
        except json.JSONDecodeError:
            event["data"] = raw
    return event or None
