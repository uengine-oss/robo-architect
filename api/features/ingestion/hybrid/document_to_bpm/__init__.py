"""Document → BPM Skeleton (Phase 1).

Primary path: call the external pdf2bpmn A2A service (see ``a2a_client`` +
``a2a_adapter``). Fallback: the in-repo native LLM extractor (``entity_extractor``).

Output is a `ProcessBundle` of N `BpmSkeleton`s — one per top-level business
process the document describes. Multi-process support was previously flattened
by the adapter; see docs/legacy-ingestion/개선&재구조화.md §A.0 for rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from api.features.ingestion.hybrid.contracts import BpmSkeleton, ProcessBundle
from api.features.ingestion.hybrid.document_to_bpm.a2a_adapter import (
    adapt_a2a_result_to_skeleton,
)
from api.features.ingestion.hybrid.document_to_bpm.a2a_client import A2AClient
from api.features.ingestion.hybrid.document_to_bpm.config import a2a_enabled
from api.features.ingestion.hybrid.document_to_bpm.entity_extractor import (
    extract_bpm_from_document,
)
from api.platform.observability.smart_logger import SmartLogger


@dataclass
class Phase1Result:
    bundle: ProcessBundle
    source: str  # "a2a" | "native"
    error: Optional[str] = None

    @property
    def skeleton(self) -> BpmSkeleton:
        """Backward-compat flat view. Use `bundle.processes` for per-process retrieval."""
        return self.bundle.flatten()


async def extract_bpm_skeleton(
    *,
    content: str,
    session_id: str,
    pdf_path: Optional[str] = None,
    pdf_url: Optional[str] = None,
    source_pdf_name: Optional[str] = None,
) -> Phase1Result:
    """Produce a ProcessBundle using the A2A service first, native extractor as fallback.

    A2A is only attempted when (a) it is enabled via env and (b) a concrete
    ``pdf_url`` or ``pdf_path`` is available — the external service does not
    accept raw text. ``pdf_url`` is preferred because the A2A server downloads
    via httpx and does not handle local ``file://`` paths.
    """
    if a2a_enabled() and (pdf_url or pdf_path):
        try:
            bundle = await _run_via_a2a(
                pdf_url=pdf_url, pdf_path=pdf_path,
                session_id=session_id, source_pdf_name=source_pdf_name,
            )
            if bundle.processes and any(s.tasks for s in bundle.processes):
                return Phase1Result(bundle=bundle, source="a2a")
            SmartLogger.log(
                "WARNING", "A2A returned empty bundle — falling back to native",
                category="ingestion.hybrid.document_bpm",
            )
        except Exception as e:  # network, timeout, parse — fall back
            SmartLogger.log(
                "WARNING", "A2A extraction failed — falling back to native",
                category="ingestion.hybrid.document_bpm",
                params={"error": str(e)},
            )
            native_bundle = await extract_bpm_from_document(
                content, session_id=session_id, source_pdf_name=source_pdf_name,
            )
            return Phase1Result(bundle=native_bundle, source="native", error=str(e))

    native_bundle = await extract_bpm_from_document(
        content, session_id=session_id, source_pdf_name=source_pdf_name,
    )
    return Phase1Result(bundle=native_bundle, source="native")


async def _run_via_a2a(
    *,
    pdf_url: Optional[str] = None,
    pdf_path: Optional[str] = None,
    session_id: str,
    source_pdf_name: Optional[str] = None,
) -> ProcessBundle:
    client = A2AClient()
    try:
        exec_resp = await client.execute(pdf_url=pdf_url, pdf_path=pdf_path)
        task_id = exec_resp.get("task_id")
        if not task_id:
            raise RuntimeError(f"A2A execute returned no task_id: {exec_resp}")
        result = await client.wait_for_completion(task_id)
        bundle = adapt_a2a_result_to_skeleton(
            result or {},
            session_id=session_id,
            source_pdf_name=source_pdf_name,
        )
        # Backfill per-process `domain_keywords` — pdf2bpmn's output doesn't
        # include them. Agent Step 1 (module retrieval) uses keywords as its
        # query text, so empty keywords = weak retrieval. One cheap LLM call
        # per process.
        from api.features.ingestion.hybrid.document_to_bpm.a2a_adapter import (
            _backfill_domain_keywords,
        )
        for skel in bundle.processes:
            if not skel.process:
                continue
            if skel.process.domain_keywords:
                continue
            skel.process.domain_keywords = await _backfill_domain_keywords(
                name=skel.process.name,
                description=skel.process.description or skel.process.name or "",
            )
        return bundle
    finally:
        await client.aclose()
