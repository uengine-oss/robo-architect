"""Document → BPM Skeleton (Phase 1).

Primary path: call the external pdf2bpmn A2A service (see ``a2a_client`` +
``a2a_adapter``). Fallback: the in-repo native LLM extractor (``entity_extractor``).

Output is a `ProcessBundle` of N `BpmSkeleton`s — one per top-level business
process the document describes. Multi-process support was previously flattened
by the adapter; see docs/legacy-ingestion/개선&재구조화.md §A.0 for rationale.

When ``pdf_artifacts`` lists several PDFs, we run A2A once per PDF and merge
bundles so each document keeps its own extraction pass (no single merged PDF).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from api.features.ingestion.hybrid.contracts import (
    BpmProcess,
    BpmSkeleton,
    ProcessBundle,
)
from api.features.ingestion.hybrid.document_to_bpm.a2a_adapter import (
    adapt_a2a_result_to_skeleton,
    merge_process_bundles,
    parse_bpmn_xml_per_process,
    _process_id,
)
from api.features.ingestion.hybrid.document_to_bpm.a2a_client import A2AClient
from api.features.ingestion.hybrid.document_to_bpm.config import a2a_enabled, facade_url
from api.features.ingestion.hybrid.document_to_bpm.entity_extractor import (
    extract_bpm_from_document,
)
from api.features.ingestion.hybrid.document_to_bpm.facade_client import FacadeClient
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


def _normalize_pdf_artifacts(
    pdf_artifacts: Optional[list[dict[str, Optional[str]]]],
    pdf_path: Optional[str],
    pdf_url: Optional[str],
    source_pdf_name: Optional[str],
) -> Optional[list[dict[str, Optional[str]]]]:
    if pdf_artifacts:
        return list(pdf_artifacts)
    if pdf_url or pdf_path:
        return [
            {
                "pdf_url": pdf_url,
                "pdf_path": pdf_path,
                "source_pdf_name": source_pdf_name,
            }
        ]
    return None


async def extract_bpm_skeleton(
    *,
    content: str,
    session_id: str,
    pdf_path: Optional[str] = None,
    pdf_url: Optional[str] = None,
    source_pdf_name: Optional[str] = None,
    pdf_artifacts: Optional[list[dict[str, Optional[str]]]] = None,
) -> Phase1Result:
    """Produce a ProcessBundle using the A2A service first, native extractor as fallback.

    A2A is only attempted when (a) it is enabled via env and (b) at least one
    ``pdf_url`` / ``pdf_path`` is available — the external service does not
    accept raw text. ``pdf_url`` is preferred because the A2A server downloads
    via httpx and does not handle local ``file://`` paths.

    ``pdf_artifacts`` (optional) is a list of ``{"pdf_url", "pdf_path", "source_pdf_name"}``
    dicts; when multiple entries exist, A2A runs once per PDF and bundles are merged.
    """
    artifacts = _normalize_pdf_artifacts(pdf_artifacts, pdf_path, pdf_url, source_pdf_name)
    native_name = source_pdf_name or (
        (artifacts[0].get("source_pdf_name") if artifacts else None) or None
    )

    # `facade_errors` survives a facade→a2a/native fallback so the final
    # Phase1Result.error (and the runner's branch log) names *why* it fell back.
    facade_errors: list[str] = []

    # Preferred path: pdf2bpmn-facade (direct-parse REST, gateway-rich BPMN, no
    # Memento). Robo uploads the PDF bytes, so it only needs a local pdf_path.
    if facade_url() and artifacts and any(a.get("pdf_path") for a in artifacts):
        merged_bundles: list[ProcessBundle] = []
        for art in artifacts:
            pp = art.get("pdf_path")
            sn = art.get("source_pdf_name")
            if not pp:
                continue
            try:
                b = await _run_via_facade(
                    pdf_path=pp, session_id=session_id, source_pdf_name=sn,
                )
            except Exception as e:
                facade_errors.append(f"{sn or pp}: {e}")
                SmartLogger.log(
                    "WARNING", "facade extraction failed for one PDF — continuing",
                    category="ingestion.hybrid.document_bpm",
                    params={"error": str(e), "source_pdf_name": sn},
                )
                continue
            if b.processes and any(s.tasks for s in b.processes):
                merged_bundles.append(b)
            else:
                facade_errors.append(f"{sn or 'pdf'}: empty facade bundle")
        if merged_bundles:
            SmartLogger.log(
                "INFO", "facade produced Phase 1 bundle — using it",
                category="ingestion.hybrid.document_bpm",
                params={"session_id": session_id, "process_count": sum(len(b.processes) for b in merged_bundles)},
            )
            return Phase1Result(
                bundle=merge_process_bundles(merged_bundles),
                source="facade",
                error="; ".join(facade_errors) if facade_errors else None,
            )
        SmartLogger.log(
            "WARNING", "facade returned no usable bundle(s) — falling back to a2a/native",
            category="ingestion.hybrid.document_bpm",
            params={"errors": facade_errors},
        )

    if a2a_enabled() and artifacts:
        merged_bundles: list[ProcessBundle] = []
        errors: list[str] = []
        for art in artifacts:
            pu = art.get("pdf_url")
            pp = art.get("pdf_path")
            sn = art.get("source_pdf_name")
            if not pu and not pp:
                continue
            try:
                b = await _run_via_a2a(
                    pdf_url=pu,
                    pdf_path=pp,
                    session_id=session_id,
                    source_pdf_name=sn,
                )
            except Exception as e:
                label = sn or pu or pp or "pdf"
                errors.append(f"{label}: {e}")
                SmartLogger.log(
                    "WARNING",
                    "A2A extraction failed for one PDF — continuing with others",
                    category="ingestion.hybrid.document_bpm",
                    params={"error": str(e), "source_pdf_name": sn},
                )
                continue
            if b.processes and any(s.tasks for s in b.processes):
                merged_bundles.append(b)
            else:
                label = sn or "pdf"
                errors.append(f"{label}: empty A2A bundle")
                SmartLogger.log(
                    "WARNING",
                    "A2A returned empty bundle for one PDF — skipping",
                    category="ingestion.hybrid.document_bpm",
                    params={"source_pdf_name": sn},
                )

        if merged_bundles:
            bundle = merge_process_bundles(merged_bundles)
            err = "; ".join(errors) if errors else None
            return Phase1Result(bundle=bundle, source="a2a", error=err)

        SmartLogger.log(
            "WARNING",
            "A2A returned no usable bundle(s) — falling back to native",
            category="ingestion.hybrid.document_bpm",
            params={"errors": errors},
        )
        native_bundle = await extract_bpm_from_document(
            content, session_id=session_id, source_pdf_name=native_name
        )
        return Phase1Result(
            bundle=native_bundle,
            source="native",
            error="; ".join(facade_errors + errors) if (facade_errors or errors) else None,
        )

    SmartLogger.log(
        "INFO", "Phase 1 using native extractor (no facade/a2a path taken)",
        category="ingestion.hybrid.document_bpm",
        params={"session_id": session_id, "facade_errors": facade_errors or None},
    )
    native_bundle = await extract_bpm_from_document(
        content, session_id=session_id, source_pdf_name=native_name
    )
    return Phase1Result(
        bundle=native_bundle,
        source="native",
        error="; ".join(facade_errors) if facade_errors else None,
    )


def _pdf_text(pdf_path: str) -> str:
    """Extract a document's text to use as the consulting outline. The consulting
    LLM reconstructs gateways/branches from this text — no Memento needed."""
    import pymupdf  # noqa: PLC0415 — heavy import, only on the facade path

    with pymupdf.open(pdf_path) as doc:
        return "\n".join(page.get_text() for page in doc)


async def _run_via_facade(
    *,
    pdf_path: str,
    session_id: str,
    source_pdf_name: Optional[str] = None,
) -> ProcessBundle:
    """Drive the pdf2bpmn-facade **consulting** path: send the document text →
    consulting LLM (branches) → proc-def LLM → connected-gateway BPMN → parse
    into BpmSkeletons (reusing the shared BPMN parser). No Memento, no shared
    store writes — pure LLM compute on the document text."""
    client = FacadeClient()
    try:
        outline = await asyncio.to_thread(_pdf_text, pdf_path)
        if not outline.strip():
            return ProcessBundle(processes=[])
        proc_name = (source_pdf_name or "Process").rsplit(".", 1)[0]
        xml = await client.consulting_bpmn(
            process_name=proc_name, consulting_outline=outline
        )

        skeletons: list[BpmSkeleton] = []
        if (xml or "").strip().startswith("<"):
            for skel in parse_bpmn_xml_per_process(xml):
                raw_name = skel.process.name if skel.process else ""
                name = raw_name or f"Process {len(skeletons) + 1}"
                pid = _process_id(source_pdf_name or "", session_id, name)
                skel.process = BpmProcess(
                    id=pid, name=name, domain_keywords=[],
                    source_pdf_name=source_pdf_name, session_id=session_id,
                    actor_ids=[a.id for a in skel.actors],
                    task_ids=[t.id for t in skel.tasks],
                )
                for a in skel.actors:
                    a.process_id = pid
                for t in skel.tasks:
                    t.process_id = pid
                for s in skel.sequences:
                    s.process_id = pid
                for g in skel.gateways:
                    g.process_id = pid
                for fl in skel.flows:
                    fl.process_id = pid
                skeletons.append(skel)

        SmartLogger.log(
            "INFO", "facade extraction produced bundle",
            category="ingestion.hybrid.document_bpm",
            params={
                "session_id": session_id, "source_pdf_name": source_pdf_name,
                "process_count": len(skeletons),
                "gateway_total": sum(len(s.gateways) for s in skeletons),
            },
        )
        return ProcessBundle(processes=skeletons)
    finally:
        await client.aclose()


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
