"""Per-page PDF classification."""

from __future__ import annotations

MIN_NATIVE_CHARS = 40


def classify_page(plumber_page) -> str:
    """
    Return 'native' if page has sufficient extractable text, else 'ocr'.
    Blank pages without images are treated as native.
    """
    text = plumber_page.extract_text() or ""
    clean = text.strip()
    if len(clean) < MIN_NATIVE_CHARS:
        if plumber_page.images:
            return "ocr"
        return "native"
    return "native"
