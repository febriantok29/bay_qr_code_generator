from __future__ import annotations

import shutil
from pathlib import Path


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None and shutil.which("gs") is not None


def ocr_to_searchable_pdf(input_path: Path, output_path: Path, language: str = "ind+eng") -> tuple[bool, str]:
    """OCR scanned pages and normalize the whole document. ocrmypdf's default
    output_type is "pdfa", so this also serves as a PDF -> PDF/A converter for
    pages that already have a text layer (skip_text=True leaves them as-is
    aside from PDF/A repackaging)."""
    try:
        import ocrmypdf
    except ImportError:
        return False, "ocrmypdf belum terinstall. Install dengan: pip install ocrmypdf"

    try:
        ocrmypdf.ocr(input_path, output_path, language=language, skip_text=True, progress_bar=False)
    except Exception as e:
        return False, str(e)
    return True, ""
