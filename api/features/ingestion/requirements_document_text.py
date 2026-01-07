"""
Requirements Document Text Extraction

Business capability: parse incoming requirements documents into plain text for downstream extraction.
"""

from __future__ import annotations

from fastapi import HTTPException

from api.platform.observability.smart_logger import SmartLogger


def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF file using PyMuPDF."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=file_content, filetype="pdf")
        text_parts: list[str] = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text_parts.append(page.get_text())

        doc.close()
        return "\n".join(text_parts)
    except ImportError:
        SmartLogger.log(
            "ERROR",
            "PDF processing requires PyMuPDF (fitz import failed)",
            category="ingestion.pdf",
        )
        raise HTTPException(
            status_code=500,
            detail="PDF processing requires PyMuPDF. Install with: pip install PyMuPDF",
        )
    except Exception as e:
        SmartLogger.log("ERROR", "Failed to parse PDF", category="ingestion.pdf", params={"error": str(e)})
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")


