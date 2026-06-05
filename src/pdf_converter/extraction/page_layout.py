"""Page-type detection for layout and table strategies."""

from __future__ import annotations

import re

from pdf_converter.text_utils import sanitise_text


_INDEX_RE = re.compile(r"(?:\bIndex\s+I-\d+|\bI-\d+\s*Index\b)", re.I)
_FACTOR_SHEET_RE = re.compile(
    r"UNIT\s+CONVERSION|CONVERSION\s+FACTORS",
    re.I,
)
_PHOTO_CREDITS_RE = re.compile(r"Chapter\s*\d+\s*Opener\s*:", re.I)


def page_text_hint(page, words: list[dict] | None = None) -> str:
    """Best-effort page text for heuristics when layout extract_text is sparse."""
    raw = sanitise_text(page.extract_text(layout=True) or "")
    if len(raw) >= 80:
        return raw
    if words:
        joined = sanitise_text(" ".join(w.get("text", "") for w in words))
        if joined:
            return joined
    return raw


def is_index_page(raw_text: str) -> bool:
    """Back-of-book index with I-n page markers."""
    return bool(_INDEX_RE.search(raw_text or ""))


def is_factor_sheet_page(raw_text: str) -> bool:
    """Appendix unit conversion sheets (two-column factor lists)."""
    return bool(_FACTOR_SHEET_RE.search(raw_text or ""))


def is_photo_credits_page(raw_text: str) -> bool:
    """Dense two-column photo credits (Chapter N Opener: ...)."""
    t = raw_text or ""
    return len(_PHOTO_CREDITS_RE.findall(t)) >= 2


def should_use_text_inferred_tables(
    *,
    book_mode: bool,
    allow_text_tables: bool,
    raw_text: str,
) -> bool:
    """
    Text-inferred tables help constant tables but harm indices and factor sheets.
    """
    if allow_text_tables:
        return True
    if not book_mode:
        return False
    if is_index_page(raw_text):
        return False
    if is_factor_sheet_page(raw_text):
        return False
    if is_photo_credits_page(raw_text):
        return False
    return True
