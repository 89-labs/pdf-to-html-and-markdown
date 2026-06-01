"""Text cleaning and semantic role detection."""

from __future__ import annotations

import re

_LIST_RE = re.compile(r"^[\u2022\u2023\u25E6\u2043\*\-\+•]\s+")
_FOOTNOTE_RE = re.compile(r"^\s*\d+\s+\w")
_CID_BULLET_RE = re.compile(r"\(cid:\d+\)")


def sanitise_text(text: str) -> str:
    """Clean raw PDF text: CID artefacts, ligatures, whitespace."""
    text = _CID_BULLET_RE.sub("•", text)
    text = text.replace("\x08", "")  # TOC leader backspace dots
    text = text.replace("\x00", "").replace("\ufffd", "")
    text = re.sub(r"[\u2010\u2011\u2012\u2013\u2014]\s", "- ", text)
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


_HEADING_PREFIX_RE = re.compile(
    r"^(chapter|section|part|appendix)\b",
    re.IGNORECASE,
)


def detect_role(text: str, font_size: float, avg_font_size: float) -> str:
    """Assign semantic role from font size and patterns."""
    stripped = text.strip()
    if not stripped:
        return "blank"

    bullet_count = stripped.count("●") + stripped.count("•")
    if bullet_count >= 2 or "@" in stripped or "|" in stripped and len(stripped) > 120:
        if _LIST_RE.match(stripped):
            return "list_item"
        return "paragraph"

    ratio = font_size / avg_font_size if avg_font_size else 1.0
    looks_like_heading = (
        ratio >= 1.5
        or (ratio >= 1.25 and len(stripped) < 90 and bullet_count == 0)
    )
    if looks_like_heading and (
        _HEADING_PREFIX_RE.match(stripped) or (len(stripped) < 90 and ratio >= 1.4)
    ):
        if ratio >= 1.9:
            return "h1"
        if ratio >= 1.5:
            return "h2"
        if ratio >= 1.25 and len(stripped) < 70:
            return "h3"
    if _LIST_RE.match(stripped):
        return "list_item"
    if _FOOTNOTE_RE.match(stripped) and font_size < avg_font_size * 0.9:
        return "footnote"
    return "paragraph"


def split_merged_block(text: str, existing_role: str) -> list[dict[str, str]]:
    """Split merged PDF blocks (inline bullets, heading run-ons)."""
    if re.search(r"[•\u2022\u2023]", text):
        parts = re.split(r"\s*[•\u2022\u2023]\s*", text)
        intro = parts[0].strip()
        items = [p.strip() for p in parts[1:] if p.strip()]
        if not items:
            return [{"text": text, "role": existing_role}]
        result: list[dict[str, str]] = []
        if intro:
            result.append({"text": intro, "role": "paragraph"})
        for item in items:
            result.append({"text": item, "role": "list_item"})
        return result
    m = re.match(
        r"^(\d+\.\d+(?:\.\d+)?\s+[A-Z][^\n.!?]{3,60}?)\s{3,}(.+)$",
        text,
        re.DOTALL,
    )
    if m:
        return [
            {"text": m.group(1).strip(), "role": "h2"},
            {"text": m.group(2).strip(), "role": "paragraph"},
        ]
    return [{"text": text, "role": existing_role}]
