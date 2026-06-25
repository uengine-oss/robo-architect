"""Client for the pdf2bpmn-facade REST service (direct-parse extractor).

The facade wraps the deployed pdf2bpmn extractor's REST API: robo uploads the
PDF bytes, the extractor parses it directly (no Memento), and the facade returns
gateway-rich BPMN 2.0 XML (one document per detected process) without the
upstream's Korean-filename Content-Disposition crash.

Flow per PDF:
    POST   /api/upload            (multipart file)        -> {job_id}
    POST   /api/process/{job_id}                          -> start
    GET    /api/jobs/{job_id}      (poll until completed)  -> {status, process_ids}
    GET    /api/files/bpmn?process_id=<id>                -> BPMN XML (per process)
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Optional

import httpx

from api.features.ingestion.hybrid.document_to_bpm.config import (
    facade_timeout_s,
    facade_url,
)


class FacadeClient:
    def __init__(self, base_url: Optional[str] = None, timeout_s: Optional[float] = None):
        self.base_url = (base_url or facade_url()).rstrip("/")
        # Shared-secret header — required when the facade is publicly exposed
        # (e.g. via Cloudflare tunnel). Empty when the endpoint is unprotected.
        key = os.getenv("PDF2BPMN_FACADE_KEY", "").strip()
        headers = {"X-API-Key": key} if key else {}
        self._client = httpx.AsyncClient(
            timeout=timeout_s if timeout_s is not None else facade_timeout_s(),
            headers=headers,
        )

    async def upload(self, *, pdf_path: str, pdf_file_name: Optional[str] = None) -> str:
        name = pdf_file_name or Path(pdf_path).name
        with open(pdf_path, "rb") as f:
            content = f.read()
        r = await self._client.post(
            f"{self.base_url}/api/upload",
            files={"file": (name, content, "application/pdf")},
        )
        r.raise_for_status()
        job_id = r.json().get("job_id")
        if not job_id:
            raise RuntimeError(f"facade /api/upload returned no job_id: {r.text[:200]}")
        return job_id

    async def start(self, job_id: str) -> None:
        r = await self._client.post(f"{self.base_url}/api/process/{job_id}")
        r.raise_for_status()

    async def wait_for_completion(
        self, job_id: str, *, poll_s: float = 3.0, max_polls: int = 400
    ) -> dict[str, Any]:
        for _ in range(max_polls):
            r = await self._client.get(f"{self.base_url}/api/jobs/{job_id}")
            r.raise_for_status()
            job = r.json()
            status = (job.get("status") or "").lower()
            if status in ("completed", "error", "failed"):
                if status != "completed":
                    raise RuntimeError(
                        f"facade job {job_id} ended status={status}: {job.get('error', '')}"
                    )
                return job
            await asyncio.sleep(poll_s)
        raise TimeoutError(f"facade job {job_id} did not complete within budget")

    async def get_bpmn(self, process_id: str) -> str:
        r = await self._client.get(
            f"{self.base_url}/api/files/bpmn", params={"process_id": process_id}
        )
        r.raise_for_status()
        return r.text

    async def consulting_bpmn(
        self, *, process_name: str, consulting_outline: str
    ) -> str:
        """Gateway-rich BPMN via the facade's consulting path (Memento-free, no
        shared-store writes): document text -> consulting LLM (branches) ->
        proc-def LLM -> connected-gateway BPMN 2.0 XML. One process per call."""
        r = await self._client.post(
            f"{self.base_url}/api/consulting-bpmn",
            json={"process_name": process_name, "consulting_outline": consulting_outline},
        )
        r.raise_for_status()
        return r.text

    async def list_process_ids(self) -> list[str]:
        r = await self._client.get(f"{self.base_url}/api/processes")
        r.raise_for_status()
        return [
            p.get("proc_id")
            for p in (r.json().get("processes") or [])
            if p.get("proc_id")
        ]

    async def aclose(self) -> None:
        await self._client.aclose()
