"""Remove running headers, footers, and page furniture."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

_RUNNING_HEADER_RE = re.compile(
    r"^Strategy for space research and innovation(\s+Strategy for space research and innovation)*\s*$",
    re.I,
)
_PAGE_FURNITURE_RE = re.compile(
    r"^(\d+\s+)?Ministry of Higher Education and Science\s+Denmark(\s+Ministry of Higher Education and Science\s+Denmark\s+\d+)?\s*$",
    re.I,
)
_STANDALONE_PAGE_NUM = re.compile(r"^\d{1,3}$")


def detect_running_texts(
    pages_words: list[list[dict]],
    *,
    top_band: float = 72,
    bottom_band: float = 72,
    min_page_ratio: float = 0.35,
) -> set[str]:
    """Find lines repeated across many pages (headers/footers)."""
    counts: Counter[str] = Counter()
    for words in pages_words:
        if not words:
            continue
        page_height = max(w.get("bottom", 0) for w in words) or 800
        lines = _quick_lines(words)
        for ln in lines:
            top = ln["top"]
            text = ln["text"].strip()
            if not text or len(text) < 12:
                continue
            if top < top_band or top > page_height - bottom_band:
                norm = _normalize_furniture(text)
                counts[norm] += 1
    threshold = max(2, int(len(pages_words) * min_page_ratio))
    return {t for t, c in counts.items() if c >= threshold}


def _normalize_furniture(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = _RUNNING_HEADER_RE.sub("HEADER", text)
    return text


def _quick_lines(words: list[dict], y_tolerance: float = 3) -> list[dict[str, Any]]:
    lines: list[list] = []
    for w in sorted(words, key=lambda x: (x.get("top", 0), x.get("x0", 0))):
        placed = False
        for line in lines:
            if abs(line[-1]["top"] - w["top"]) < y_tolerance:
                line.append(w)
                placed = True
                break
        if not placed:
            lines.append([w])
    result = []
    for line_words in lines:
        line_words = sorted(line_words, key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in line_words)
        result.append(
            {
                "text": text,
                "top": line_words[0]["top"],
                "x0": line_words[0]["x0"],
                "bottom": max(w["bottom"] for w in line_words),
            }
        )
    return result


def is_furniture_line(
    text: str,
    *,
    top: float,
    page_height: float,
    running_texts: set[str],
) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if _STANDALONE_PAGE_NUM.match(stripped):
        return True
    if _RUNNING_HEADER_RE.match(stripped):
        return True
    if _PAGE_FURNITURE_RE.match(stripped):
        return True
    norm = _normalize_furniture(stripped)
    if norm in running_texts:
        return True
    if re.match(
        r"^Strategy for space research and innovation\s*$",
        stripped,
        re.I,
    ):
        return True
    if "Strategy for space research and innovation" in stripped and len(stripped) < 120:
        if stripped.count("Strategy for space research and innovation") >= 2:
            return True
    return False


def filter_words_furniture(
    words: list[dict],
    running_texts: set[str],
    *,
    top_margin: float = 55,
    bottom_margin: float = 55,
) -> list[dict]:
    """Drop words belonging to header/footer lines."""
    if not words:
        return words
    page_height = max(w.get("bottom", 0) for w in words)
    lines = _quick_lines(words)
    drop_tops: set[float] = set()
    for ln in lines:
        if is_furniture_line(
            ln["text"],
            top=ln["top"],
            page_height=page_height,
            running_texts=running_texts,
        ):
            drop_tops.add(round(ln["top"]))
    if not drop_tops:
        return words
    filtered = []
    for w in words:
        if round(w.get("top", 0)) in drop_tops:
            continue
        filtered.append(w)
    return filtered
