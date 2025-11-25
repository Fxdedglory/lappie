# echo: file_searcher extract_text v0.1.0 2025-11-24

"""
File → text extraction utilities.

Currently supports:
  - .txt : UTF-8 decode
  - .pdf : pypdf text extraction (simple page concat)

Sections:
  1) Imports & helpers
  2) Extractors per type
  3) Dispatcher
"""

# =====================================================
# 1) Imports & helpers
# =====================================================

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pypdf import PdfReader


# =====================================================
# 2) Extractors per type
# =====================================================

def _extract_text_from_txt(path: Path) -> str:
    """
    Extract text from a .txt file (UTF-8 with ignore for errors).
    """
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_text_from_pdf(path: Path) -> str:
    """
    Extract text from a PDF using pypdf.

    Strategy:
      - load PdfReader
      - concatenate text from all pages with page separators
    """
    reader = PdfReader(str(path))
    pieces = []

    for i, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            pieces.append(f"\n\n--- Page {i + 1} ---\n{page_text}")

    return "".join(pieces).strip()


# =====================================================
# 3) Dispatcher
# =====================================================

def extract_text_from_file(path: Path, mime_type: Optional[str] = None) -> str:
    """
    Dispatch file → text extraction based on suffix and/or mime_type.

    Currently:
      - .txt → UTF-8
      - .pdf → pypdf
      - fallback → UTF-8 decode of raw bytes

    Args:
        path: Path to the file on disk.
        mime_type: Optional MIME hint (unused for now, but kept for future).

    Returns:
        Extracted text as a string (may be empty).
    """
    suffix = path.suffix.lower()

    if suffix == ".txt":
        return _extract_text_from_txt(path)

    if suffix == ".pdf":
        return _extract_text_from_pdf(path)

    # Fallback: treat as text
    return path.read_text(encoding="utf-8", errors="ignore")
