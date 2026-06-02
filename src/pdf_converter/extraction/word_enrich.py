"""Enrich pdfplumber words with colors and other char-level attributes."""

from __future__ import annotations

import statistics
from typing import Any

from pdf_converter.extraction.underline import attach_underlines_from_strokes


def _word_bbox(word: dict) -> tuple[float, float, float, float]:
    return (
        float(word.get("x0", 0)),
        float(word.get("top", 0)),
        float(word.get("x1", 0)),
        float(word.get("bottom", 0)),
    )


def _overlap(word: dict, char: dict) -> bool:
    x0, top, x1, bottom = _word_bbox(word)
    cx0, ctop = float(char.get("x0", 0)), float(char.get("top", 0))
    cx1, cbottom = float(char.get("x1", 0)), float(char.get("bottom", 0))
    return cx0 < x1 and cx1 > x0 and ctop < bottom and cbottom > top


def enrich_words_from_chars(page, words: list[dict]) -> list[dict]:
    """Attach non_stroking_color from overlapping characters."""
    try:
        chars = page.chars
    except Exception:
        return words
    if not chars:
        return words

    enriched = []
    for w in words:
        w = dict(w)
        if w.get("non_stroking_color"):
            enriched.append(w)
            continue
        colors = [
            c.get("non_stroking_color")
            for c in chars
            if c.get("text", "").strip() and _overlap(w, c)
        ]
        colors = [c for c in colors if c]
        if colors:
            w["non_stroking_color"] = colors[0]
        enriched.append(w)
    return enriched


def extract_words_styled(
    page,
    *,
    use_text_flow: bool = False,
    hyperlinks: list | None = None,
) -> list[dict]:
    """Extract words with font metadata, colors, and link URIs."""
    try:
        words = page.extract_words(
            extra_attrs=["fontname", "size"],
            use_text_flow=use_text_flow,
        )
    except Exception:
        words = page.extract_words()

    words = enrich_words_from_chars(page, words)

    if hyperlinks:
        from pdf_converter.extraction.links import attach_hyperlinks_to_words

        words = attach_hyperlinks_to_words(words, hyperlinks)

    words = attach_underlines_from_strokes(page, words)

    return words
