"""Table detection validation and deduplication."""

from __future__ import annotations

import re
from typing import Any, Optional


def _table_flat_text(table: list[list[Any]]) -> str:
    parts: list[str] = []
    for row in table or []:
        for cell in row or []:
            if cell is not None:
                parts.append(str(cell).strip())
    return " ".join(parts)


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))


def text_similarity(a: str, b: str) -> float:
    """Jaccard similarity on word tokens."""
    sa, sb = _token_set(a), _token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def page_has_ruling_lines(page) -> bool:
    """True if the page has enough vector lines to support real tables."""
    lines = page.lines or []
    horizontal = 0
    vertical = 0
    for line in lines:
        w = abs(line.get("x1", 0) - line.get("x0", 0))
        h = abs(line.get("bottom", 0) - line.get("top", 0))
        if w > 30 and h < 3:
            horizontal += 1
        if h > 30 and w < 3:
            vertical += 1
    return horizontal >= 2 and vertical >= 2


def _median_cell_length(table: list[list[Any]]) -> float:
    lengths: list[int] = []
    for row in table:
        for cell in row or []:
            if cell is not None:
                lengths.append(len(str(cell).strip()))
    if not lengths:
        return 0.0
    lengths.sort()
    mid = len(lengths) // 2
    return float(lengths[mid])


def _table_dimensions(table: list[list[Any]]) -> tuple[int, int]:
    rows = len(table)
    cols = max((len(r) for r in table), default=0)
    return rows, cols


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x0, top, x1, bottom = bbox
    return max(x1 - x0, 0) * max(bottom - top, 0)


def is_valid_table(
    table: list[list[Any]],
    bbox: Optional[tuple[float, float, float, float]],
    page,
    *,
    allow_text_inferred: bool = False,
) -> bool:
    """
    Reject pdfplumber false positives (prose laid out in columns).
    """
    if not table or not table[0]:
        return False

    rows, cols = _table_dimensions(table)
    if rows < 2 or cols < 2:
        return False

    if not allow_text_inferred and not page_has_ruling_lines(page):
        return False

    page_area = float(page.width) * float(page.height)
    if bbox and page_area > 0:
        if _bbox_area(bbox) / page_area > 0.85 and cols >= 5:
            return False

    if cols >= 6 and _median_cell_length(table) < 12:
        return False

    non_empty = sum(
        1 for row in table for cell in (row or []) if cell and str(cell).strip()
    )
    if non_empty < rows:
        return False

    return True


def filter_tables(
    tables: list[list[list[Any]]],
    bboxes: list[tuple[float, float, float, float]],
    body_text: str,
    page,
    *,
    allow_text_inferred: bool = False,
    similarity_threshold: float = 0.55,
) -> tuple[list[list[list[Any]]], list[tuple[float, float, float, float]]]:
    """Keep only valid tables that are not duplicates of body text."""
    kept_tables: list[list[list[Any]]] = []
    kept_bboxes: list[tuple[float, float, float, float]] = []

    body_norm = body_text.lower()
    for idx, table in enumerate(tables):
        bbox = bboxes[idx] if idx < len(bboxes) else None
        if not is_valid_table(table, bbox, page, allow_text_inferred=allow_text_inferred):
            continue
        flat = _table_flat_text(table)
        if body_norm and text_similarity(flat, body_text) >= similarity_threshold:
            continue
        kept_tables.append(table)
        if bbox:
            kept_bboxes.append(bbox)

    return kept_tables, kept_bboxes
