"""Hybrid ingestion — external pdf2bpmn A2A service configuration."""

from __future__ import annotations

import os


def a2a_server_url() -> str:
    return os.getenv("PDF2BPMN_A2A_URL", "http://localhost:9999").rstrip("/")


def a2a_enabled() -> bool:
    return os.getenv("HYBRID_USE_A2A", "true").strip().lower() in ("1", "true", "yes", "on")


def a2a_timeout_s() -> float:
    try:
        return float(os.getenv("PDF2BPMN_A2A_TIMEOUT_S", "300"))
    except ValueError:
        return 300.0


def a2a_pdf_tmp_dir() -> str:
    """Directory where the uploaded PDF is written so the A2A service can read it.

    Must be mounted into the pdf2bpmn container if that service runs separately.
    """
    return os.getenv("PDF2BPMN_SHARED_PDF_DIR", "/tmp/hybrid_a2a_pdfs")


def hybrid_public_base_url() -> str:
    """Base URL of this backend reachable by the A2A server.

    Used to build a ``pdf_url`` for the A2A ``/execute`` input, because the
    extractor's A2A server only downloads via httpx (no ``file://`` support).
    """
    return os.getenv("HYBRID_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
