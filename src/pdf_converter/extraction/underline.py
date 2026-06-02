"""Detect underlines drawn as vector lines (common for links and styled text)."""

from __future__ import annotations

from typing import Any

# Line sits just below the word bbox (pdfplumber: y grows downward).
_UNDERLINE_GAP_MIN = -6.0
_UNDERLINE_GAP_MAX = 6.0
_MIN_OVERLAP_RATIO = 0.75
_MAX_LINE_TO_WORD_WIDTH = 1.35


def _line_y(line: dict) -> float:
    return (float(line.get("top", 0)) + float(line.get("bottom", 0))) / 2


def _is_horizontal_stroke(line: dict) -> bool:
    height = abs(float(line.get("height") or 0))
    width = abs(float(line.get("width") or 0))
    if width < 3:
        return False
    if height < 1.5:
        return True
    y0, y1 = float(line.get("y0", 0)), float(line.get("y1", 0))
    return abs(y0 - y1) < 1.0 and width >= 3


def _horizontal_overlap(x0: float, x1: float, lx0: float, lx1: float) -> float:
    return max(0.0, min(x1, lx1) - max(x0, lx0))


def underline_strokes(page: Any) -> list[dict]:
    """Collect page lines (and thin rects) that may be text underlines."""
    strokes: list[dict] = []
    try:
        for line in page.lines or []:
            if _is_horizontal_stroke(line):
                strokes.append(line)
    except Exception:
        pass
    try:
        for rect in page.rects or []:
            h = abs(float(rect.get("height") or 0))
            w = abs(float(rect.get("width") or 0))
            if h < 1.5 and w >= 3:
                strokes.append(rect)
    except Exception:
        pass
    return strokes


def word_has_underline_stroke(word: dict, strokes: list[dict]) -> bool:
    wx0 = float(word.get("x0", 0))
    wx1 = float(word.get("x1", 0))
    word_w = max(wx1 - wx0, 1.0)
    word_bottom = float(word.get("bottom", word.get("top", 0)))

    for stroke in strokes:
        lx0 = float(stroke.get("x0", 0))
        lx1 = float(stroke.get("x1", 0))
        line_w = max(lx1 - lx0, 1.0)
        overlap = _horizontal_overlap(wx0, wx1, lx0, lx1)
        if overlap < word_w * _MIN_OVERLAP_RATIO:
            continue
        gap = _line_y(stroke) - word_bottom
        if gap < _UNDERLINE_GAP_MIN or gap > _UNDERLINE_GAP_MAX:
            continue
        if line_w > word_w * _MAX_LINE_TO_WORD_WIDTH:
            continue
        return True
    return False


def attach_underlines_from_strokes(page: Any, words: list[dict]) -> list[dict]:
    strokes = underline_strokes(page)
    if not strokes:
        return words
    out: list[dict] = []
    for w in words:
        w = dict(w)
        if not w.get("underline") and word_has_underline_stroke(w, strokes):
            w["underline"] = True
        out.append(w)
    return out
